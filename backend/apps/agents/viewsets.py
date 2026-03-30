from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.common.permissions import IsServerAdminOrAbove, IsSuperAdmin

from .models import Agent, ServerAssignment
from .serializers import (
    AgentApproveSerializer,
    AgentSerializer,
    ServerAssignmentSerializer,
)


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
        summary="Agent 등록",
        description="새 Agent를 등록합니다. 등록 후 status는 pending 상태이며, 관리자 승인이 필요합니다.",
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
    ordering_fields = ["hostname", "registered_at", "status"]

    def get_permissions(self):
        if self.action in ("create", "destroy", "manage_status"):
            return [IsSuperAdmin()]
        return [IsServerAdminOrAbove()]

    @extend_schema(
        summary="Agent 승인/거절",
        description='Agent의 상태를 변경합니다. action: "approve" (승인) 또는 "reject" (거절).',
        request=AgentApproveSerializer,
        responses=AgentSerializer,
    )
    @action(detail=True, methods=["post"], url_path="manage-status")
    def manage_status(self, request, pk=None):
        agent = self.get_object()
        serializer = AgentApproveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if serializer.validated_data["action"] == "approve":
            agent.status = Agent.Status.APPROVED
            agent.approved_at = timezone.now()
        else:
            agent.status = Agent.Status.REJECTED
        agent.save(update_fields=["status", "approved_at"])
        return Response(AgentSerializer(agent).data)


@extend_schema_view(
    list=extend_schema(
        summary="서버 할당 목록",
        description="사용자-Agent 간 할당 관계를 조회합니다.",
    ),
    create=extend_schema(
        summary="서버 할당 생성",
        description="사용자에게 Agent(서버) 접근 권한을 할당합니다.",
    ),
    destroy=extend_schema(
        summary="서버 할당 해제",
        description="사용자의 Agent 접근 권한을 해제합니다.",
    ),
)
class ServerAssignmentViewSet(ModelViewSet):
    """
    서버 할당 관리 API.

    사용자별로 접근 가능한 서버(Agent)를 관리합니다.
    SuperAdmin만 할당/해제할 수 있습니다.
    """

    queryset = ServerAssignment.objects.select_related("user", "agent").all()
    serializer_class = ServerAssignmentSerializer
    filterset_fields = ["user", "agent"]
    permission_classes = [IsSuperAdmin]
