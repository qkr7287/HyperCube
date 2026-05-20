import json
from ipaddress import ip_address
import secrets
from datetime import timedelta

from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

# 메인 UI active 판정 grace (serializers.py / tasks.py와 일치)
ACTIVE_GRACE_SECONDS = 5 * 60

from apps.common.permissions import IsServerAdminOrAbove, IsSuperAdmin

from .models import Agent, AgentStatusEvent
from .serializers import (
    AgentSerializer,
    AgentStatusEventSerializer,
    AgentStatusSerializer,
    GpuDeviceSerializer,
)


def _issue_token() -> str:
    return f"agent_{secrets.token_urlsafe(32)}"


def _client_ip(request) -> str | None:
    """Prefer nginx's observed client IP over client-controlled headers."""
    candidates = [
        request.META.get("HTTP_X_REAL_IP"),
        request.META.get("REMOTE_ADDR"),
    ]

    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        # Fallback only. nginx also sends X-Real-IP, which is safer because it
        # overwrites any client-supplied value with nginx's observed peer.
        candidates.append(xff.split(",")[0].strip())

    for value in candidates:
        if not value:
            continue
        value = str(value).strip()
        try:
            ip_address(value)
        except ValueError:
            continue
        return value
    return None


@extend_schema_view(
    list=extend_schema(
        summary="Agent 목록 조회",
        description="등록된 모든 Agent를 조회합니다. status, hostname, ip_address로 필터링/검색 가능.",
    ),
    retrieve=extend_schema(
        summary="Agent 상세 조회",
        description="특정 Agent의 상세 정보를 조회합니다. 컨테이너 수 포함.",
    ),
    create=extend_schema(
        summary="Agent 등록 (자동 승인)",
        description=(
            "새 Agent를 등록합니다. 자동으로 승인되며 응답에 token이 즉시 포함됩니다. "
            "hostname 중복 시 기존 Agent를 그대로 반환합니다 (idempotent, 기존 token 유지)."
        ),
    ),
    update=extend_schema(
        summary="Agent 정보 수정",
        description="Agent의 hostname, ip_address 등 정보를 수정합니다.",
    ),
    partial_update=extend_schema(
        summary="Agent 부분 수정",
        description="Agent 정보를 부분적으로 수정합니다.",
    ),
    destroy=extend_schema(
        summary="Agent 삭제",
        description="Agent를 삭제합니다. 연결된 컨테이너 데이터도 함께 삭제됩니다. SuperAdmin 전용.",
    ),
)
class AgentViewSet(ModelViewSet):
    """
    서버 Agent 관리 API.

    각 모니터링 대상 서버에 설치된 Agent를 등록/승인/관리합니다.
    Agent가 승인되면 JWT 토큰을 발급받아 WebSocket으로 데이터를 전송할 수 있습니다.
    """

    queryset = Agent.objects.prefetch_related("containers").all()
    serializer_class = AgentSerializer
    filterset_fields = ["status"]
    search_fields = ["hostname", "ip_address"]
    ordering_fields = ["hostname", "registered_at", "status", "last_seen_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        # ?active=true → last_seen_at 5분 이내인 것만 (메인 UI 기본 필터)
        active_param = self.request.query_params.get("active")
        if active_param and active_param.lower() in ("1", "true", "yes"):
            cutoff = timezone.now() - timedelta(seconds=ACTIVE_GRACE_SECONDS)
            qs = qs.filter(last_seen_at__gte=cutoff).exclude(
                status=Agent.Status.ARCHIVED
            )
        return qs

    def get_permissions(self):
        if self.action in ("create", "check_status"):
            return [AllowAny()]
        if self.action in ("list", "retrieve", "latest_metrics", "gpus"):
            # 사용자도 서버 목록 조회 가능 (요청 폼에서 대상 서버 선택 필요)
            from rest_framework.permissions import IsAuthenticated
            return [IsAuthenticated()]
        if self.action == "destroy":
            return [IsSuperAdmin()]
        return [IsServerAdminOrAbove()]

    def create(self, request, *args, **kwargs):
        """Agent 자가 등록 + 자동 승인.

        - hostname 중복 시 기존 Agent를 그대로 반환 (idempotent, 기존 token 유지)
        - 신규 등록 시 status=approved, token 즉시 발급, approved_at 기록
        - ip_address는 agent가 자체 보고한 값을 쓰지 않고, 백엔드가 관측한
          실제 TCP peer (필요 시 X-Forwarded-For)를 권위 있는 값으로 사용한다.
          Agent가 Docker bridge 내부 IP(172.x/192.168.192.x 등)를 보고하는
          경우가 많아서 운영자에게 유용한 정보가 아니기 때문.
        """
        observed_ip = _client_ip(request)

        hostname = request.data.get("hostname")
        if hostname:
            existing = Agent.objects.filter(hostname=hostname).first()
            if existing:
                changed_fields = []
                # 과거에 pending/rejected였던 항목도 이번 등록을 계기로 자동 승인.
                if existing.status != Agent.Status.APPROVED or not existing.token:
                    existing.status = Agent.Status.APPROVED
                    existing.approved_at = existing.approved_at or timezone.now()
                    if not existing.token:
                        existing.token = _issue_token()
                    changed_fields.extend(["status", "approved_at", "token"])
                if observed_ip and existing.ip_address != observed_ip:
                    existing.ip_address = observed_ip
                    changed_fields.append("ip_address")
                if changed_fields:
                    existing.save(update_fields=changed_fields)
                return Response(
                    AgentSerializer(existing).data,
                    status=status.HTTP_200_OK,
                )

        # Inject the backend-observed IP into the payload so validation
        # succeeds even when the agent omits `ip_address` (it now does).
        payload = {k: v for k, v in request.data.items()}
        if observed_ip and not payload.get("ip_address"):
            payload["ip_address"] = observed_ip

        serializer = self.get_serializer(data=payload)
        serializer.is_valid(raise_exception=True)
        save_kwargs = {
            "status": Agent.Status.APPROVED,
            "token": _issue_token(),
            "approved_at": timezone.now(),
        }
        # Trust what we observed over what the client sent.
        if observed_ip:
            save_kwargs["ip_address"] = observed_ip
        agent = serializer.save(**save_kwargs)
        return Response(
            AgentSerializer(agent).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="Agent 상태/토큰 조회",
        description=(
            "Agent의 현재 상태와 token을 반환합니다. 자동 승인 정책 이후 항상 "
            "approved + token이 함께 반환됩니다 (호환성 유지용)."
        ),
        responses=AgentStatusSerializer,
    )
    @action(detail=True, methods=["get"], url_path="status")
    def check_status(self, request, pk=None):
        agent = self.get_object()
        return Response(AgentStatusSerializer(agent).data)

    @extend_schema(
        summary="Agent 상태 변화 이력 조회",
        description=(
            "최근 Agent online/offline 전환 이력을 시간 역순으로 반환합니다. "
            "기본 50건, ?limit=N 으로 조절. Dashboard '최근 상태 변화' 패널이 "
            "mount 시 호출하여 백엔드/브라우저 down 동안 놓친 이벤트를 복구합니다."
        ),
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="status-events",
        permission_classes=[IsAuthenticated],
    )
    def status_events(self, request):
        try:
            limit = int(request.query_params.get("limit", 50))
        except ValueError:
            limit = 50
        limit = max(1, min(limit, 500))
        qs = AgentStatusEvent.objects.order_by("-occurred_at")[:limit]
        return Response(AgentStatusEventSerializer(qs, many=True).data)

    @extend_schema(
        summary="Agent 최신 메트릭 조회",
        description="Redis 캐시에서 Agent의 최신 시스템 메트릭(CPU/Memory/Disk)을 반환합니다. Agent 오프라인 시 null.",
    )
    @action(detail=True, methods=["get"], url_path="latest-metrics")
    def latest_metrics(self, request, pk=None):
        agent = self.get_object()
        from apps.common.redis_client import get_redis_client

        r = get_redis_client()
        raw = r.get(f"server:{agent.id}:system")
        if not raw:
            return Response({"cpu": None, "memory": None, "disk": None, "timestamp": None})

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return Response({"cpu": None, "memory": None, "disk": None, "timestamp": None})

        body = payload.get("data") or {}
        body["timestamp"] = payload.get("timestamp")
        return Response(body)

    @extend_schema(
        summary="Agent GPU inventory",
        description="Return the latest GPU devices and allocatable slices reported by this Agent.",
        responses=GpuDeviceSerializer(many=True),
    )
    @action(detail=True, methods=["get"], url_path="gpus")
    def gpus(self, request, pk=None):
        agent = self.get_object()
        devices = agent.gpu_devices.prefetch_related("slices").order_by("index")
        return Response({
            "agent": str(agent.id),
            "hostname": agent.hostname,
            "devices": GpuDeviceSerializer(devices, many=True).data,
        })

    @extend_schema(
        summary="Agent host port usage",
        description=(
            "Host ports in use on this agent. Combines HyperCube-managed ports "
            "(running containers + pending/approved requests) with an on-demand "
            "host_port_scan of the agent's TCP LISTEN ports. coverage=full when "
            "the agent answered the scan, hypercube-only when it did not."
        ),
    )
    @action(detail=True, methods=["get"], url_path="used-ports")
    def used_ports(self, request, pk=None):
        from apps.common import command_router
        from apps.containers.services.host_ports import collect_managed_host_ports

        agent = self.get_object()
        seen: dict[tuple, dict] = {}
        for entry in collect_managed_host_ports(agent):
            seen.setdefault((entry["port"], entry["proto"]), entry)

        # agent 의 host_port_scan 으로 host 전체 TCP LISTEN 포트를 합친다.
        # 오프라인/타임아웃이면 HyperCube-known 포트만으로 응답.
        coverage = "hypercube-only"
        scan = command_router.dispatch_command_and_wait(
            str(agent.id), "host_port_scan", {}
        )
        if scan.get("success"):
            for entry in (scan.get("data") or {}).get("ports", []):
                try:
                    port = int(entry["port"])
                except (KeyError, TypeError, ValueError):
                    continue
                proto = str(entry.get("proto") or "tcp")
                seen.setdefault(
                    (port, proto),
                    {"port": port, "proto": proto, "source": "host-scan"},
                )
            coverage = "full"

        ports = sorted(seen.values(), key=lambda entry: entry["port"])
        return Response({
            "agent": str(agent.id),
            "hostname": agent.hostname,
            "used_ports": ports,
            "coverage": coverage,
        })
