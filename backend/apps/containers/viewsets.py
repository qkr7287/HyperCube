from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.viewsets import ModelViewSet

from apps.common.permissions import IsServerAdminOrAbove

from .models import Container
from .serializers import ContainerSerializer


@extend_schema_view(
    list=extend_schema(
        summary="컨테이너 목록 조회",
        description="DB에 저장된 모든 컨테이너를 조회합니다. agent, status로 필터링, name/image로 검색 가능.",
    ),
    retrieve=extend_schema(
        summary="컨테이너 상세 조회",
        description="특정 컨테이너의 상세 정보를 조회합니다.",
    ),
    create=extend_schema(
        summary="컨테이너 등록",
        description="Agent가 보고한 컨테이너 정보를 DB에 저장합니다.",
    ),
    update=extend_schema(
        summary="컨테이너 정보 수정",
        description="컨테이너 정보를 수정합니다 (status 업데이트 등).",
    ),
    partial_update=extend_schema(
        summary="컨테이너 부분 수정",
        description="컨테이너 정보를 부분적으로 수정합니다.",
    ),
    destroy=extend_schema(
        summary="컨테이너 삭제",
        description="DB에서 컨테이너 레코드를 삭제합니다.",
    ),
)
class ContainerViewSet(ModelViewSet):
    """
    Docker 컨테이너 관리 API.

    Agent가 수집한 컨테이너 정보를 DB에 저장/조회합니다.
    실시간 metrics, logs, control 기능은 추후 구현 예정입니다.
    """

    queryset = Container.objects.select_related("agent").all()
    serializer_class = ContainerSerializer
    filterset_fields = ["agent", "status"]
    search_fields = ["name", "image"]
    ordering_fields = ["name", "status", "last_seen"]
    permission_classes = [IsServerAdminOrAbove]
