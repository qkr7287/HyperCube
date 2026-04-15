from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.common.permissions import IsAdmin

from .models import Container, ContainerRequest, ContainerTemplate
from .serializers import (
    ContainerRequestSerializer,
    ContainerSerializer,
    ContainerTemplateSerializer,
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

        # TODO: Agent wiring — Phase 3.2.4에서 여기서 Agent에 create_container / delete_container 발송
        # 발송 성공 시 status=deploying으로 전환, 결과에 따라 deployed/failed.

        return Response(self.get_serializer(req_obj).data)

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
