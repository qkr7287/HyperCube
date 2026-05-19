import json
import logging
import time
import uuid
from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from apps.common import command_router
from apps.common.permissions import IsAdmin
from apps.common.redis_client import get_redis_client
from apps.agents.models import Agent
from apps.metrics.burden import build_burden_snapshot
from apps.metrics.models import ContainerMetricsHistory
from apps.metrics.serializers import ContainerMetricsHistorySerializer
from apps.models_catalog.prepare import (
    create_or_attach_prepare_jobs_for_request,
    dispatch_prepare_jobs,
)

from .services.gpu_allocation import (
    GpuReservationError,
    fail_reserved_gpu_allocations_for_request,
    gpu_payload_for_request,
    reserve_gpu_slices_for_request,
)
from .services.deployment import dispatch_request_to_agent
from .services.policy import enforce_approval_policy
from .services.recommend import recommend_resource_limits
from .services.workspace import (
    apply_workspace_metadata_from_response,
    build_workspace_open_url,
    delete_workspace_token_for_request,
    extend_workspace_runtime,
    issue_workspace_open_ticket,
    prepare_workspace_secret_for_request,
    workspace_payload_for_request,
    workspace_ticket_ttl_seconds,
)

logger = logging.getLogger(__name__)

from .models import (
    ConsoleSession,
    Container,
    ContainerEvent,
    GpuAllocation,
    ContainerRequest,
    ContainerTemplate,
)
from .serializers import (
    ConsoleSessionSerializer,
    ContainerEventSerializer,
    ContainerRequestSerializer,
    ContainerSerializer,
    ContainerTemplateSerializer,
    MyContainerSerializer,
    ReviewActionSerializer,
    WorkspaceSerializer,
)


@extend_schema_view(
    list=extend_schema(
        summary="컨테이너 목록 조회",
        description="DB에 저장된 모든 컨테이너를 조회합니다. agent, status로 필터링, name/image로 검색 가능.",
    ),
    retrieve=extend_schema(summary="컨테이너 상세 조회"),
)
class ContainerViewSet(ModelViewSet):
    """Docker 컨테이너 레코드 조회/관리 (admin 전용)."""

    queryset = Container.objects.select_related("agent", "requester").all()
    serializer_class = ContainerSerializer
    filterset_fields = ["agent", "status", "requester"]
    search_fields = ["name", "image"]
    ordering_fields = ["name", "status", "last_seen"]
    permission_classes = [IsAdmin]

    @extend_schema(
        summary="컨테이너 자원 한도 추천",
        description=(
            "template weight와 agent capacity를 조합해 CPU/메모리/workspace 추천값을 반환합니다. "
            "query: ?template=<uuid>&agent=<uuid>."
        ),
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="recommend",
        permission_classes=[IsAuthenticated],
    )
    def recommend(self, request):
        template_id = request.query_params.get("template")
        agent_id = request.query_params.get("agent")
        if not template_id or not agent_id:
            return Response(
                {"detail": "template and agent query parameters are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            template = ContainerTemplate.objects.get(id=template_id)
        except (ContainerTemplate.DoesNotExist, ValueError):
            return Response({"detail": "template not found"}, status=status.HTTP_404_NOT_FOUND)
        try:
            agent = Agent.objects.get(id=agent_id)
        except (Agent.DoesNotExist, ValueError):
            return Response({"detail": "agent not found"}, status=status.HTTP_404_NOT_FOUND)

        recommendation = recommend_resource_limits(agent, template)
        payload = recommendation.as_dict()
        payload.update({
            "template": str(template.id),
            "agent": str(agent.id),
            "min_cpu_percent": template.min_cpu_percent,
            "min_memory_mb": template.min_memory_mb,
            "min_workspace_gb": template.min_workspace_gb,
            "workspace_pool_total_gb": agent.workspace_pool_total_gb,
            "workspace_pool_free_gb": agent.workspace_pool_free_gb,
            "workspace_hard_enforcement": agent.workspace_hard_enforcement,
        })
        return Response(payload)


@extend_schema_view(
    list=extend_schema(
        summary="내 컨테이너 목록 조회",
        description="로그인 사용자가 직접 요청해 생성된 컨테이너만 조회합니다.",
    ),
    retrieve=extend_schema(
        summary="내 컨테이너 상세 조회",
        description="로그인 사용자가 직접 요청해 생성된 단일 컨테이너의 상세 정보를 조회합니다.",
    ),
)
class MyContainerViewSet(ReadOnlyModelViewSet):
    queryset = Container.objects.select_related(
        "agent",
        "requester",
        "created_via_request",
        "created_via_request__template",
    ).all()
    serializer_class = MyContainerSerializer
    filterset_fields = ["status", "agent"]
    search_fields = ["name", "image"]
    ordering_fields = ["name", "status", "last_seen"]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return super().get_queryset().filter(requester=self.request.user)

    @extend_schema(
        summary="내 컨테이너 최신 메트릭 조회",
        description="Redis 캐시에서 현재 컨테이너의 최신 CPU/메모리/네트워크/디스크 메트릭을 조회합니다.",
    )
    @action(detail=True, methods=["get"], url_path="current-metrics")
    def current_metrics(self, request, pk=None):
        container = self.get_object()
        r = get_redis_client()

        payload = None
        cache_keys = [
            f"server:{container.agent_id}:container:{container.container_id}:metrics",
            f"server:{container.agent_id}:container:{container.container_id[:12]}:metrics",
        ]

        for key in cache_keys:
            raw = r.get(key)
            if not raw:
                continue
            try:
                payload = json.loads(raw)
                break
            except json.JSONDecodeError:
                payload = None

        if payload is None:
            pattern = f"server:{container.agent_id}:container:{container.container_id[:12]}*:metrics"
            for key in r.scan_iter(match=pattern, count=20):
                raw = r.get(key)
                if not raw:
                    continue
                try:
                    payload = json.loads(raw)
                    break
                except json.JSONDecodeError:
                    payload = None

        if payload is None:
            return Response(
                {
                    "timestamp": None,
                    "containerId": container.container_id,
                    "cpu": None,
                    "memory": None,
                    "network": None,
                    "disk": None,
                    "workspace": _container_workspace_snapshot(container),
                    "network_stats": [],
                }
            )

        body = dict(payload.get("data") or {})
        body["timestamp"] = payload.get("timestamp")
        body["containerId"] = body.get("containerId") or container.container_id
        body["workspace"] = _merge_workspace_snapshot(body.get("workspace"), container)
        return Response(body)

    @extend_schema(
        summary="내 컨테이너 메트릭 히스토리 조회",
        description="로그인 사용자의 컨테이너에 대한 시계열 메트릭을 지정 범위로 조회합니다.",
    )
    @action(detail=True, methods=["get"], url_path="metrics-history")
    def metrics_history(self, request, pk=None):
        container = self.get_object()
        range_key = request.query_params.get("range", "1h")
        try:
            limit = min(int(request.query_params.get("limit", "240")), 500)
        except ValueError:
            limit = 240

        range_map = {
            "1m": timedelta(minutes=1),
            "5m": timedelta(minutes=5),
            "1h": timedelta(hours=1),
            "6h": timedelta(hours=6),
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
        }
        from_delta = range_map.get(range_key, range_map["1h"])
        from_time = timezone.now() - from_delta

        metrics_qs = ContainerMetricsHistory.objects.filter(
            agent=container.agent,
            container_id__startswith=container.container_id[:12],
            recorded_at__gte=from_time,
        ).order_by("-recorded_at")[:limit]

        serializer = ContainerMetricsHistorySerializer(metrics_qs, many=True)
        return Response(list(reversed(serializer.data)))

    # ----- Agent on-demand control / inspect -----

    # Agent.control 이 허용하는 7개 중, "remove" 는 request flow(action=delete)로
    # 분리되어야 하므로 제외. 사용자 페이지에서 destructive remove 직접 노출 금지.
    _VALID_CONTROL_ACTIONS = frozenset(["start", "stop", "restart", "pause", "unpause", "kill"])
    _AGENT_COMMAND_TIMEOUT = 15.0  # seconds

    # control 성공 시 Container.status 를 즉시 갱신할 매핑.
    # Agent의 다음 containers snapshot(60초)을 기다리지 않고 사용자 UX 즉시 반영.
    # 다음 snapshot이 도착하면 그 값으로 덮어씌워짐 (truth source 는 여전히 agent).
    _ACTION_TO_STATUS = {
        "start":   "running",
        "restart": "running",
        "unpause": "running",
        "pause":   "paused",
        "stop":    "exited",
        "kill":    "exited",
    }

    def _dispatch_and_wait(self, server_id: str, command: str, params: dict) -> dict:
        """REST에서 Agent로 명령 발송 + 동기 대기.

        Redis에 store_response 된 응답을 polling. Agent 오프라인이면 즉시 fail.
        timeout 도달 시 success=False, error="timeout".
        """
        agent_channel = command_router.get_agent_channel(server_id)
        if not agent_channel:
            return {"success": False, "error": "agent_offline"}

        request_id = str(uuid.uuid4())
        command_router.record_pending(request_id, command_router.REST_SENTINEL, server_id)

        payload = {
            "type": "command",
            "requestId": request_id,
            "command": command,
            "params": params,
        }

        try:
            layer = get_channel_layer()
            async_to_sync(layer.send)(agent_channel, {
                "type": "ws.send",
                "payload": payload,
            })
        except Exception:
            logger.exception("[my-container] dispatch failed cmd=%s", command)
            return {"success": False, "error": "dispatch_failed"}

        deadline = time.monotonic() + self._AGENT_COMMAND_TIMEOUT
        while time.monotonic() < deadline:
            resp = command_router.fetch_response(request_id)
            if resp is not None:
                return resp
            time.sleep(0.1)
        return {"success": False, "error": "timeout"}

    def _agent_resp_to_http(self, resp: dict) -> Response:
        """Agent command_response → DRF Response. EnvelopeJSONRenderer 더블래핑 방지를 위해
        success 시엔 data만, fail 시엔 error 만 직접 반환 (renderer 가 envelope 추가)."""
        if resp.get("success"):
            return Response(resp.get("data") or {}, status=status.HTTP_200_OK)

        err = resp.get("error") or "agent_error"
        if err == "agent_offline":
            return Response({"detail": "Agent 오프라인 — 명령 발송 불가"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        if err == "timeout":
            return Response({"detail": "Agent 응답 타임아웃 (15초)"}, status=status.HTTP_504_GATEWAY_TIMEOUT)
        if err == "dispatch_failed":
            return Response({"detail": "Agent 명령 발송 실패"}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({"detail": str(err)}, status=status.HTTP_502_BAD_GATEWAY)

    @extend_schema(
        summary="컨테이너 라이프사이클 제어",
        description=(
            "본인 소유 컨테이너에 start/stop/restart/pause/unpause/kill 명령 발송. "
            "Agent에 WS 명령을 보내고 응답까지 동기 대기 (최대 15초). "
            "remove는 request flow(action=delete)로 분리되어 있어 여기서는 차단."
        ),
    )
    @action(detail=True, methods=["post"], url_path="control")
    def control(self, request, pk=None):
        container = self.get_object()
        action_name = (request.data.get("action") or "").strip().lower()
        if action_name not in self._VALID_CONTROL_ACTIONS:
            return Response(
                {"detail": f"invalid action. valid: {sorted(self._VALID_CONTROL_ACTIONS)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        resp = self._dispatch_and_wait(
            server_id=str(container.agent_id),
            command="control",
            params={
                "containerId": container.container_id,
                "action": action_name,
            },
        )

        # Optimistic Container.status 갱신 — agent snapshot(60s) 기다리지 않고
        # UI 즉시 반영. 다음 snapshot 이 truth 로 덮어씌움.
        if resp.get("success"):
            new_status = self._ACTION_TO_STATUS.get(action_name)
            if new_status and container.status != new_status:
                container.status = new_status
                container.save(update_fields=["status", "last_seen"])

        return self._agent_resp_to_http(resp)

    @extend_schema(
        summary="컨테이너 라이프사이클 이벤트 조회",
        description=(
            "본인 소유 컨테이너의 최근 라이프사이클 이벤트(start/stop/die/restart/"
            "pause/unpause/kill/oom/health_status). agent 가 Dockerode events stream "
            "으로 push 한 데이터에서 읽음. since(ISO8601)/limit query."
        ),
    )
    @action(detail=True, methods=["get"], url_path="events")
    def events(self, request, pk=None):
        container = self.get_object()
        qs = ContainerEvent.objects.filter(container=container).order_by("-ts")

        since_raw = request.query_params.get("since")
        if since_raw:
            from datetime import datetime
            try:
                since_dt = datetime.fromisoformat(since_raw.replace("Z", "+00:00"))
                qs = qs.filter(ts__gte=since_dt)
            except ValueError:
                return Response(
                    {"detail": "since must be ISO8601 timestamp"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            limit = min(int(request.query_params.get("limit", "100")), 500)
        except ValueError:
            limit = 100

        rows = list(qs[:limit])
        # 시간 오름차순으로 응답 (frontend 차트 mark 편의).
        rows.reverse()
        return Response(ContainerEventSerializer(rows, many=True).data)

    @extend_schema(
        summary="컨테이너 내부 프로세스 top-N",
        description=(
            "본인 소유 컨테이너의 프로세스 목록을 sortBy(cpu|mem) 기준 내림차순 "
            "정렬해 limit 개 반환. agent 가 호스트 관찰만으로 수집 (컨테이너 "
            "내부 ps 의존 X) — minimal image 도 동작."
        ),
    )
    @action(detail=True, methods=["get"], url_path="processes")
    def processes(self, request, pk=None):
        container = self.get_object()
        sort_by = (request.query_params.get("sortBy") or "cpu").strip().lower()
        if sort_by not in ("cpu", "mem"):
            sort_by = "cpu"
        try:
            limit = int(request.query_params.get("limit", "20"))
        except ValueError:
            limit = 20
        limit = max(1, min(100, limit))

        resp = self._dispatch_and_wait(
            server_id=str(container.agent_id),
            command="container_processes",
            params={
                "containerId": container.container_id,
                "sortBy": sort_by,
                "limit": limit,
            },
        )
        return self._agent_resp_to_http(resp)

    _VALID_RESTART_POLICIES = frozenset(["no", "on-failure", "unless-stopped", "always"])

    @extend_schema(
        summary="컨테이너 자원 한도 / 재시작 정책 수정",
        description=(
            "본인 소유 컨테이너의 메모리 / CPU 한도, 재시작 정책을 즉시 수정. "
            "agent 의 dockerode container.update() 호출 — 재시작 불필요. "
            "body: { memory_mb?: int, cpu_percent?: int (0~N00), restart_policy?: 'no'|'on-failure'|'unless-stopped'|'always', restart_max_retry?: int }. "
            "한 필드만 보내도 그것만 갱신 (나머지는 기존 값 유지)."
        ),
    )
    @action(detail=True, methods=["post"], url_path="update-limits")
    def update_limits(self, request, pk=None):
        container = self.get_object()
        body = request.data or {}
        params: dict = {"containerId": container.container_id}

        # memory_mb 1MB 이상. 0 이면 unlimited (params 에 0 그대로 전달, agent 해석).
        mem_raw = body.get("memory_mb")
        if mem_raw is not None:
            try:
                mem = int(mem_raw)
            except (TypeError, ValueError):
                return Response({"detail": "memory_mb must be integer"}, status=status.HTTP_400_BAD_REQUEST)
            if mem < 0:
                return Response({"detail": "memory_mb must be >= 0"}, status=status.HTTP_400_BAD_REQUEST)
            params["memory_mb"] = mem

        # cpu_percent: 100 = 1 core. 0 = unlimited.
        cpu_raw = body.get("cpu_percent")
        if cpu_raw is not None:
            try:
                cpu = int(cpu_raw)
            except (TypeError, ValueError):
                return Response({"detail": "cpu_percent must be integer"}, status=status.HTTP_400_BAD_REQUEST)
            if cpu < 0 or cpu > 10000:
                return Response({"detail": "cpu_percent must be 0~10000"}, status=status.HTTP_400_BAD_REQUEST)
            params["cpu_percent"] = cpu

        # restart_policy
        rp = body.get("restart_policy")
        if rp is not None:
            rp = str(rp).strip()
            if rp not in self._VALID_RESTART_POLICIES:
                return Response(
                    {"detail": f"invalid restart_policy. valid: {sorted(self._VALID_RESTART_POLICIES)}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            params["restart_policy"] = rp

        max_retry = body.get("restart_max_retry")
        if max_retry is not None:
            try:
                params["restart_max_retry"] = max(0, int(max_retry))
            except (TypeError, ValueError):
                return Response({"detail": "restart_max_retry must be integer"}, status=status.HTTP_400_BAD_REQUEST)

        if len(params) == 1:  # containerId 만, 다른 필드 없음
            return Response({"detail": "no fields to update"}, status=status.HTTP_400_BAD_REQUEST)

        resp = self._dispatch_and_wait(
            server_id=str(container.agent_id),
            command="update_container",
            params=params,
        )
        if resp.get("success"):
            limit_updates = {}
            if "cpu_percent" in params:
                limit_updates["cpu_percent_limit"] = params["cpu_percent"]
            if "memory_mb" in params:
                limit_updates["memory_mb_limit"] = params["memory_mb"]
            if limit_updates:
                for field, value in limit_updates.items():
                    setattr(container, field, value)
                container.limit_updated_at = timezone.now()
                container.save(update_fields=[*limit_updates.keys(), "limit_updated_at"])
        return self._agent_resp_to_http(resp)

    @extend_schema(
        summary="컨테이너 inspect (Docker inspect subset)",
        description="본인 소유 컨테이너의 현재 inspect 데이터 (state.health, mounts, networkSettings 등).",
    )
    @action(detail=True, methods=["get"], url_path="inspect")
    def inspect(self, request, pk=None):
        container = self.get_object()
        resp = self._dispatch_and_wait(
            server_id=str(container.agent_id),
            command="inspect",
            params={"containerId": container.container_id},
        )
        return self._agent_resp_to_http(resp)

    @extend_schema(
        summary="호스트 자원 부담 + 이 컨테이너 추정 영향도",
        description=(
            "Level 2 추정 (Fan + RAPL + nvidia-smi). 응답 shape 은 frontend 의 "
            "`BurdenSnapshot` 과 동일. agent 가 power/temp 를 안 보내는 호스트는 "
            "Fan 모델 fallback + null 필드로 graceful 처리."
        ),
    )
    @action(detail=True, methods=["get"], url_path="burden")
    def burden(self, request, pk=None):
        container = self.get_object()
        return Response(build_burden_snapshot(container))

    @extend_schema(
        summary="컨테이너 콘솔 세션 audit 조회",
        description=(
            "본인 소유 컨테이너의 콘솔 exec 세션 audit 로그. 세션 레벨만 기록 "
            "(누가/언제/cmd/얼마/exitCode/close_reason). 키스트로크는 미기록."
        ),
    )
    @action(detail=True, methods=["get"], url_path="console-sessions")
    def console_sessions(self, request, pk=None):
        container = self.get_object()
        try:
            limit = min(int(request.query_params.get("limit", "50")), 200)
        except ValueError:
            limit = 50
        qs = ConsoleSession.objects.filter(container=container).select_related("user").order_by("-opened_at")[:limit]
        return Response(ConsoleSessionSerializer(qs, many=True).data)


@extend_schema_view(
    list=extend_schema(summary="ML workspace list"),
    retrieve=extend_schema(summary="ML workspace detail"),
)
class WorkspaceViewSet(ReadOnlyModelViewSet):
    queryset = Container.objects.select_related(
        "agent",
        "requester",
        "created_via_request",
        "created_via_request__template",
    ).filter(workspace_enabled=True)
    serializer_class = WorkspaceSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "container_id"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if getattr(user, "role", None) != "admin":
            qs = qs.filter(requester=user)
        return qs

    @action(detail=True, methods=["post"], url_path="open")
    def open(self, request, container_id=None):
        container = self.get_object()
        try:
            ticket = issue_workspace_open_ticket(container, request.user)
        except PermissionDenied:
            return Response({"detail": "Workspace is not owned by this user"}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        # Optional `path` lets the client target a subpath served by
        # jupyter-server-proxy (e.g. "proxy/7860/" for the auto-launched gradio
        # UI). Defaults to "lab" for the JupyterLab UI.
        requested_path = (request.data.get("path") if hasattr(request, "data") else None) or "lab"
        return Response({
            "url": build_workspace_open_url(container, ticket, path=str(requested_path)),
            "expiresInSeconds": workspace_ticket_ttl_seconds(),
        })

    @action(detail=True, methods=["post"], url_path="extend-runtime")
    def extend_runtime(self, request, container_id=None):
        container = self.get_object()
        try:
            additional_hours = int(request.data.get("additional_hours", 1))
            extend_workspace_runtime(container, additional_hours)
        except (TypeError, ValueError):
            return Response({"detail": "additional_hours must be an integer"}, status=status.HTTP_400_BAD_REQUEST)
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(container).data)


# ---------- Templates ----------

@extend_schema_view(
    list=extend_schema(
        summary="컨테이너 템플릿 목록",
        description="관리자가 등록한 모든 템플릿을 조회합니다. 로그인한 모든 사용자가 조회 가능하며, 작성/수정/삭제는 admin 전용입니다.",
    ),
    retrieve=extend_schema(summary="템플릿 상세"),
    create=extend_schema(summary="템플릿 등록 (admin only)"),
    update=extend_schema(summary="템플릿 수정 (admin only)"),
    partial_update=extend_schema(summary="템플릿 부분 수정 (admin only)"),
    destroy=extend_schema(summary="템플릿 삭제 (admin only)"),
)
class LauncherRecipeListView(APIView):
    """Read-only catalogue of inference recipes the base image knows about.

    Source of truth: apps.containers.launcher_recipes. The wizard fetches this
    so the recipe list stays in sync without hard-coding it in two places.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        from .launcher_recipes import list_recipes

        return Response({"recipes": [r.as_dict() for r in list_recipes()]})


class ContainerTemplateViewSet(ModelViewSet):
    queryset = ContainerTemplate.objects.select_related("created_by").all()
    serializer_class = ContainerTemplateSerializer
    filterset_fields = ["kind"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at", "updated_at"]

    def get_permissions(self):
        # 조회는 인증된 모든 사용자, 쓰기는 admin만
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsAdmin()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# ---------- Requests ----------

@extend_schema_view(
    list=extend_schema(
        summary="컨테이너 요청 목록",
        description="admin은 전체 요청, 일반 user는 자기가 제출한 요청만 볼 수 있습니다.",
    ),
    retrieve=extend_schema(summary="요청 상세"),
    create=extend_schema(
        summary="요청 생성",
        description="컨테이너 생성(action=create) 또는 삭제(action=delete)를 요청합니다. 제출자는 request.user로 자동 설정되며, 상태는 pending으로 시작합니다.",
    ),
    destroy=extend_schema(
        summary="요청 취소",
        description="pending 상태의 요청을 취소합니다. admin은 모든 요청, user는 자기 요청만 취소 가능합니다.",
    ),
)
class ContainerRequestViewSet(ModelViewSet):
    queryset = ContainerRequest.objects.select_related(
        "requester", "reviewer", "template", "target_agent", "target_container"
    ).all()
    serializer_class = ContainerRequestSerializer
    filterset_fields = ["action", "status", "target_agent"]
    ordering_fields = ["created_at", "updated_at", "status"]
    # list/retrieve/create/destroy만 허용 (update/partial_update는 별도 액션으로)
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_permissions(self):
        # admin 전용 액션 (@action 데코레이터의 permission_classes는 get_permissions 오버라이드에 의해 가려지므로
        # 여기서 명시적으로 분기해야 한다)
        if self.action in ("approve", "reject"):
            return [IsAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        # admin은 전체, 나머지는 자기 것만
        if getattr(user, "role", None) != "admin":
            qs = qs.filter(requester=user)
        return qs

    def perform_create(self, serializer):
        target = serializer.validated_data.get("target_container")
        snapshot_name = getattr(target, "name", "") or "" if target else ""
        serializer.save(
            requester=self.request.user,
            status=ContainerRequest.Status.PENDING,
            target_container_snapshot_name=snapshot_name,
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # 승인되어 진행된 요청은 취소 불가 (Agent가 이미 실행 중일 수 있음)
        if instance.status not in (
            ContainerRequest.Status.PENDING,
            ContainerRequest.Status.REJECTED,
            ContainerRequest.Status.FAILED,
        ):
            return Response(
                {"detail": f"상태 '{instance.status}'인 요청은 삭제할 수 없습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    # ----- admin 전용 액션 -----

    @extend_schema(
        summary="요청 승인 (admin only)",
        description="요청을 approved 상태로 전환하고, 이어서 deploying 상태로 Agent에 작업을 위임합니다 (Agent 연동은 별도 커밋에서).",
        request=ReviewActionSerializer,
        responses=ContainerRequestSerializer,
    )
    @action(detail=True, methods=["post"], url_path="approve", permission_classes=[IsAdmin])
    def approve(self, request, pk=None):
        req_obj = self.get_object()
        if req_obj.status != ContainerRequest.Status.PENDING:
            return Response(
                {"detail": f"pending 상태가 아닌 요청은 승인할 수 없습니다 (현재: {req_obj.status})."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = ReviewActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        prepare_jobs = []
        workspace_secret = None
        with transaction.atomic():
            req_obj = (
                ContainerRequest.objects.select_for_update()
                .get(pk=req_obj.pk)
            )
            if req_obj.status != ContainerRequest.Status.PENDING:
                return Response(
                    {"detail": f"pending request required (current: {req_obj.status})."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                enforce_approval_policy(req_obj)
                reserve_gpu_slices_for_request(req_obj)
                prepare_jobs = create_or_attach_prepare_jobs_for_request(req_obj)
                if not prepare_jobs:
                    workspace_secret = prepare_workspace_secret_for_request(req_obj)
            except GpuReservationError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            except ValidationError as exc:
                fail_reserved_gpu_allocations_for_request(req_obj, str(exc))
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as exc:
                fail_reserved_gpu_allocations_for_request(req_obj, "workspace/model preparation setup failed")
                return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

            req_obj.status = ContainerRequest.Status.APPROVED
            req_obj.reviewer = request.user
            req_obj.reviewed_at = timezone.now()
            req_obj.review_note = serializer.validated_data.get("note", "")
            req_obj.save(update_fields=["status", "reviewer", "reviewed_at", "review_note", "updated_at"])

        # Agent에 명령 발송 (비동기 — sendCommand는 WS 기반이므로 여기서는
        # channel_layer를 통해 Agent에 직접 전송한다. requestId = ContainerRequest.id
        # 이므로 command_response/progress가 오면 Consumer가 DB를 갱신한다.)
        if prepare_jobs:
            dispatch_prepare_jobs(prepare_jobs)
        else:
            self._dispatch_to_agent(req_obj, workspace_secret=workspace_secret)
        req_obj.refresh_from_db()

        return Response(self.get_serializer(req_obj).data)

    def _dispatch_to_agent(self, req_obj, workspace_secret=None):
        """승인된 요청을 Agent WS 채널로 발송.

        requestId = ContainerRequest.id 를 사용하므로,
        Agent의 command_response/command_progress가 돌아오면
        MonitoringConsumer가 같은 requestId로 DB를 갱신한다.
        """
        dispatch_request_to_agent(req_obj, workspace_secret=workspace_secret)
        return
        agent_channel = command_router.get_agent_channel(str(req_obj.target_agent_id))
        if not agent_channel:
            req_obj.status = ContainerRequest.Status.FAILED
            req_obj.progress_message = "Agent 오프라인 — 명령 발송 불가"
            req_obj.save(update_fields=["status", "progress_message", "updated_at"])
            fail_reserved_gpu_allocations_for_request(req_obj, "agent offline before dispatch")
            delete_workspace_token_for_request(req_obj)
            return

        # pending map에 기록 (Consumer가 응답 라우팅할 때 사용)
        # browser_channel은 없지만(REST 호출이므로) — DB 갱신만으로 충분
        command_router.record_pending(str(req_obj.id), "__api__", str(req_obj.target_agent_id))

        if req_obj.action == "create":
            tpl = req_obj.template
            if tpl and tpl.kind == "compose":
                payload = {
                    "type": "command",
                    "requestId": str(req_obj.id),
                    "command": "compose_up",
                    "params": {
                        "projectName": req_obj.custom_name or f"hc-{str(req_obj.id)[:8]}",
                        "composeYaml": tpl.compose_yaml,
                        "env": req_obj.custom_env or {},
                    },
                }
            else:
                ports = []
                for p in (req_obj.custom_ports or []):
                    if isinstance(p, dict):
                        ports.append(p)
                gpus = gpu_payload_for_request(req_obj)
                workspace_payload = workspace_payload_for_request(req_obj, workspace_secret)
                params = {
                    "image": req_obj.selected_image or (tpl.image if tpl else ""),
                    "name": req_obj.custom_name or f"hc-{str(req_obj.id)[:8]}",
                    "env": req_obj.custom_env or {},
                    "ports": ports,
                    "volumes": list(tpl.default_volumes) if tpl else [],
                    "gpus": gpus,
                }
                if workspace_payload:
                    params["workspace"] = workspace_payload
                    params["networkPolicy"] = tpl.network_policy if tpl else "none"
                payload = {
                    "type": "command",
                    "requestId": str(req_obj.id),
                    "command": "create_container",
                    "params": params,
                }
        elif req_obj.action == "delete":
            cid = req_obj.target_container_id or ""
            payload = {
                "type": "command",
                "requestId": str(req_obj.id),
                "command": "delete_container",
                "params": {"containerId": cid, "force": True},
            }
        else:
            return

        try:
            layer = get_channel_layer()
            async_to_sync(layer.send)(agent_channel, {
                "type": "ws.send",
                "payload": payload,
            })
            logger.info("[dispatch] Sent %s to agent %s (req %s)",
                        payload["command"], req_obj.target_agent_id, req_obj.id)
        except Exception:
            logger.exception("[dispatch] Failed to send to agent")
            req_obj.status = ContainerRequest.Status.FAILED
            req_obj.progress_message = "Agent 명령 발송 실패"
            req_obj.save(update_fields=["status", "progress_message", "updated_at"])
            fail_reserved_gpu_allocations_for_request(req_obj, "agent dispatch failed")
            delete_workspace_token_for_request(req_obj)

    @extend_schema(
        summary="요청 반려 (admin only)",
        description="요청을 rejected 상태로 전환합니다. 반려 사유를 note에 담아 남길 수 있습니다.",
        request=ReviewActionSerializer,
        responses=ContainerRequestSerializer,
    )
    @action(detail=True, methods=["post"], url_path="reject", permission_classes=[IsAdmin])
    def reject(self, request, pk=None):
        req_obj = self.get_object()
        if req_obj.status != ContainerRequest.Status.PENDING:
            return Response(
                {"detail": f"pending 상태가 아닌 요청은 반려할 수 없습니다 (현재: {req_obj.status})."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = ReviewActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        req_obj.status = ContainerRequest.Status.REJECTED
        req_obj.reviewer = request.user
        req_obj.reviewed_at = timezone.now()
        req_obj.review_note = serializer.validated_data.get("note", "")
        req_obj.save(update_fields=["status", "reviewer", "reviewed_at", "review_note", "updated_at"])

        return Response(self.get_serializer(req_obj).data)


def _container_workspace_snapshot(container: Container) -> dict | None:
    workspace = {}
    if container.workspace_device:
        # `path` is the new wire; keep `device` populated for any browser
        # build still on the LVM-thin field name until the FE rolls forward.
        workspace["path"] = container.workspace_device
        workspace["device"] = container.workspace_device
    if container.workspace_project_id:
        workspace["projectId"] = container.workspace_project_id
    if container.workspace_gb_limit:
        workspace["hardGb"] = container.workspace_gb_limit
        workspace["sizeGb"] = container.workspace_gb_limit
    return workspace or None


def _merge_workspace_snapshot(metrics_workspace, container: Container) -> dict | None:
    workspace = dict(metrics_workspace) if isinstance(metrics_workspace, dict) else {}
    if container.workspace_device:
        workspace.setdefault("path", container.workspace_device)
        workspace.setdefault("device", container.workspace_device)
    if container.workspace_project_id and not workspace.get("projectId"):
        workspace["projectId"] = container.workspace_project_id
    if container.workspace_gb_limit:
        workspace.setdefault("hardGb", container.workspace_gb_limit)
        workspace.setdefault("sizeGb", container.workspace_gb_limit)
    return workspace or None
