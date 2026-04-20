import json
import logging
from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from apps.common import command_router
from apps.common.permissions import IsAdmin
from apps.common.redis_client import get_redis_client
from apps.metrics.models import ContainerMetricsHistory
from apps.metrics.serializers import ContainerMetricsHistorySerializer

logger = logging.getLogger(__name__)

from .models import Container, ContainerRequest, ContainerTemplate
from .serializers import (
    ContainerRequestSerializer,
    ContainerSerializer,
    ContainerTemplateSerializer,
    MyContainerSerializer,
    ReviewActionSerializer,
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
                    "network_stats": [],
                }
            )

        body = payload.get("data") or {}
        body["timestamp"] = payload.get("timestamp")
        body["containerId"] = body.get("containerId") or container.container_id
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
        serializer.save(
            requester=self.request.user,
            status=ContainerRequest.Status.PENDING,
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

        req_obj.status = ContainerRequest.Status.APPROVED
        req_obj.reviewer = request.user
        req_obj.reviewed_at = timezone.now()
        req_obj.review_note = serializer.validated_data.get("note", "")
        req_obj.save(update_fields=["status", "reviewer", "reviewed_at", "review_note", "updated_at"])

        # Agent에 명령 발송 (비동기 — sendCommand는 WS 기반이므로 여기서는
        # channel_layer를 통해 Agent에 직접 전송한다. requestId = ContainerRequest.id
        # 이므로 command_response/progress가 오면 Consumer가 DB를 갱신한다.)
        self._dispatch_to_agent(req_obj)

        return Response(self.get_serializer(req_obj).data)

    def _dispatch_to_agent(self, req_obj):
        """승인된 요청을 Agent WS 채널로 발송.

        requestId = ContainerRequest.id 를 사용하므로,
        Agent의 command_response/command_progress가 돌아오면
        MonitoringConsumer가 같은 requestId로 DB를 갱신한다.
        """
        agent_channel = command_router.get_agent_channel(str(req_obj.target_agent_id))
        if not agent_channel:
            req_obj.status = ContainerRequest.Status.FAILED
            req_obj.progress_message = "Agent 오프라인 — 명령 발송 불가"
            req_obj.save(update_fields=["status", "progress_message", "updated_at"])
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
                payload = {
                    "type": "command",
                    "requestId": str(req_obj.id),
                    "command": "create_container",
                    "params": {
                        "image": req_obj.selected_image or (tpl.image if tpl else ""),
                        "name": req_obj.custom_name or f"hc-{str(req_obj.id)[:8]}",
                        "env": req_obj.custom_env or {},
                        "ports": ports,
                        "volumes": list(tpl.default_volumes) if tpl else [],
                    },
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
