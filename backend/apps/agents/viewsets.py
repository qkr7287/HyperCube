import json
import secrets
from datetime import timedelta

from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

# 메인 UI active 판정 grace (serializers.py / tasks.py와 일치)
ACTIVE_GRACE_SECONDS = 5 * 60

from apps.common.permissions import IsServerAdminOrAbove, IsSuperAdmin

from .models import Agent
from .serializers import (
    AgentSerializer,
    AgentStatusSerializer,
)


def _issue_token() -> str:
    return f"agent_{secrets.token_urlsafe(32)}"


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
        if self.action == "destroy":
            return [IsSuperAdmin()]
        return [IsServerAdminOrAbove()]

    def create(self, request, *args, **kwargs):
        """Agent 자가 등록 + 자동 승인.

        - hostname 중복 시 기존 Agent를 그대로 반환 (idempotent, 기존 token 유지)
        - 신규 등록 시 status=approved, token 즉시 발급, approved_at 기록
        """
        hostname = request.data.get("hostname")
        if hostname:
            existing = Agent.objects.filter(hostname=hostname).first()
            if existing:
                # 과거에 pending/rejected였던 항목도 이번 등록을 계기로 자동 승인.
                if existing.status != Agent.Status.APPROVED or not existing.token:
                    existing.status = Agent.Status.APPROVED
                    existing.approved_at = existing.approved_at or timezone.now()
                    if not existing.token:
                        existing.token = _issue_token()
                    existing.save(update_fields=["status", "approved_at", "token"])
                return Response(
                    AgentSerializer(existing).data,
                    status=status.HTTP_200_OK,
                )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        agent = serializer.save(
            status=Agent.Status.APPROVED,
            token=_issue_token(),
            approved_at=timezone.now(),
        )
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


