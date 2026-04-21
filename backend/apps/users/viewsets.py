from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.common.permissions import IsSuperAdmin, IsViewer

from .models import CustomUser
from .serializers import UserListSerializer, UserSerializer


@extend_schema_view(
    list=extend_schema(
        summary="사용자 목록 조회",
        description="등록된 모든 사용자를 조회합니다. role, is_active로 필터링 가능. SuperAdmin 전용.",
    ),
    retrieve=extend_schema(
        summary="사용자 상세 조회",
        description="특정 사용자의 상세 정보를 조회합니다.",
    ),
    create=extend_schema(
        summary="사용자 생성",
        description="새 사용자를 생성합니다. SuperAdmin 전용.",
    ),
    update=extend_schema(
        summary="사용자 정보 수정",
        description="사용자 정보(role, email 등)를 수정합니다.",
    ),
    destroy=extend_schema(
        summary="사용자 삭제",
        description="사용자를 삭제합니다. SuperAdmin 전용.",
    ),
)
class UserViewSet(ModelViewSet):
    """
    사용자 관리 API.

    시스템 사용자의 CRUD를 관리합니다.
    역할: super_admin (전체 관리), server_admin (할당된 서버 관리), viewer (읽기 전용).
    """

    queryset = CustomUser.objects.all().order_by("id")
    serializer_class = UserSerializer
    filterset_fields = ["role", "is_active"]
    search_fields = ["username", "email"]

    def get_permissions(self):
        if self.action == "me":
            return [IsViewer()]
        return [IsSuperAdmin()]

    def get_serializer_class(self):
        if self.action == "list":
            return UserListSerializer
        return UserSerializer

    @extend_schema(
        summary="내 정보 조회",
        description="현재 로그인한 사용자의 정보를 반환합니다. 모든 인증된 사용자 접근 가능.",
        responses=UserSerializer,
    )
    @action(detail=False, methods=["get"])
    def me(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)
