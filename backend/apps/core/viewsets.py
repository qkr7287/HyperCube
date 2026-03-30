from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from apps.common.permissions import IsServerAdminOrAbove, IsSuperAdmin, IsViewer

from .models import AlertRule, AuditLog, Template
from .serializers import AlertRuleSerializer, AuditLogSerializer, TemplateSerializer


@extend_schema_view(
    list=extend_schema(
        summary="템플릿 목록 조회",
        description="Docker 컨테이너 생성 템플릿을 조회합니다. category, is_builtin으로 필터링 가능. 모든 인증 사용자 조회 가능.",
    ),
    retrieve=extend_schema(
        summary="템플릿 상세 조회",
        description="특정 템플릿의 config(Docker 설정) 포함 상세 정보를 조회합니다.",
    ),
    create=extend_schema(
        summary="템플릿 생성",
        description="새 Docker 컨테이너 생성 템플릿을 등록합니다. ServerAdmin 이상.",
    ),
    update=extend_schema(
        summary="템플릿 수정",
        description="템플릿 정보(name, category, config)를 수정합니다.",
    ),
    destroy=extend_schema(
        summary="템플릿 삭제",
        description="템플릿을 삭제합니다. 빌트인 템플릿 삭제 시 주의.",
    ),
)
class TemplateViewSet(ModelViewSet):
    """
    Docker 컨테이너 템플릿 API.

    자주 사용하는 Docker 컨테이너 설정을 템플릿으로 저장하고 재사용합니다.
    config 필드에 이미지, 포트, 환경변수 등 Docker 설정을 JSON으로 저장합니다.
    """

    queryset = Template.objects.select_related("created_by").all()
    serializer_class = TemplateSerializer
    filterset_fields = ["category", "is_builtin"]
    search_fields = ["name"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsViewer()]
        return [IsServerAdminOrAbove()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


@extend_schema_view(
    list=extend_schema(
        summary="알림 규칙 목록",
        description="설정된 모니터링 알림 규칙을 조회합니다. agent, metric으로 필터링 가능. agent가 null이면 전역 규칙.",
    ),
    retrieve=extend_schema(
        summary="알림 규칙 상세",
        description="특정 알림 규칙의 상세 정보 (임계치, 대상 metric 등)를 조회합니다.",
    ),
    create=extend_schema(
        summary="알림 규칙 생성",
        description="CPU/Memory/Disk 임계치 알림 규칙을 생성합니다. agent를 지정하지 않으면 전역 규칙.",
    ),
    update=extend_schema(
        summary="알림 규칙 수정",
        description="알림 규칙의 임계치, 대상 metric, action을 수정합니다.",
    ),
    destroy=extend_schema(
        summary="알림 규칙 삭제",
        description="알림 규칙을 삭제합니다.",
    ),
)
class AlertRuleViewSet(ModelViewSet):
    """
    모니터링 알림 규칙 API.

    서버별 또는 전역으로 CPU/Memory/Disk 사용률 임계치를 설정합니다.
    임계치 초과 시 알림이 발생합니다 (알림 엔진은 Phase 3에서 구현).
    """

    queryset = AlertRule.objects.select_related("agent").all()
    serializer_class = AlertRuleSerializer
    filterset_fields = ["agent", "metric"]
    permission_classes = [IsSuperAdmin]


@extend_schema_view(
    list=extend_schema(
        summary="감사 로그 목록",
        description="시스템 감사 로그를 조회합니다. user, action으로 필터링, action/target으로 검색 가능. SuperAdmin 전용.",
    ),
    retrieve=extend_schema(
        summary="감사 로그 상세",
        description="특정 감사 로그의 상세 정보를 조회합니다.",
    ),
)
class AuditLogViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    """
    감사 로그 API (읽기 전용).

    사용자의 주요 행동(Agent 승인, 컨테이너 제어 등)을 기록합니다.
    로그는 시스템에서 자동 생성되며, API로는 조회만 가능합니다.
    """

    queryset = AuditLog.objects.select_related("user").all()
    serializer_class = AuditLogSerializer
    filterset_fields = ["user", "action"]
    search_fields = ["action", "target"]
    ordering_fields = ["timestamp"]
    permission_classes = [IsSuperAdmin]
