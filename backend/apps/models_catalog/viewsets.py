from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404
from django.db.models import Count
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from apps.agents.models import Agent

from apps.common.permissions import IsAdmin

from .models import ModelAsset, ModelPrepareJob, ModelUploadRequest, ModelVersion, ModelVersionCache
from .prepare import can_agent_stream_version, mount_path_for_version
from .serializers import (
    ModelAssetSerializer,
    ModelPrepareJobSerializer,
    ModelUploadRequestReviewSerializer,
    ModelUploadRequestSerializer,
    ModelVersionCacheSerializer,
    ModelVersionImportSerializer,
    ModelVersionSerializer,
    ModelVersionUploadSerializer,
)
from .services import (
    import_model_version_from_offline_path,
    model_version_file_path,
    approve_model_upload_request,
    reject_model_upload_request,
    save_uploaded_model_version,
)


class ModelAssetViewSet(ModelViewSet):
    serializer_class = ModelAssetSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    filterset_fields = ["visibility", "framework", "task"]
    search_fields = ["name", "slug", "description", "framework", "task"]
    ordering_fields = ["name", "created_at", "updated_at"]

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy", "upload_version", "import_version"):
            return [IsAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = (
            ModelAsset.objects.select_related("owner")
            .annotate(version_count=Count("versions"))
            .order_by("name")
        )
        user = self.request.user
        if getattr(user, "role", None) == "admin":
            return qs
        return qs.filter(visibility=ModelAsset.Visibility.SHARED)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def update(self, request, *args, **kwargs):
        asset = self.get_object()
        if not _can_write_asset(asset, request.user):
            return Response({"detail": "Only the owner or admin can modify this asset."}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        asset = self.get_object()
        if not _can_write_asset(asset, request.user):
            return Response({"detail": "Only the owner or admin can modify this asset."}, status=status.HTTP_403_FORBIDDEN)
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        asset = self.get_object()
        if not _can_write_asset(asset, request.user):
            return Response({"detail": "Only the owner or admin can delete this asset."}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    @action(
        detail=True,
        methods=["post"],
        url_path="versions/upload",
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload_version(self, request, pk=None):
        asset = self.get_object()
        serializer = ModelVersionUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            version = save_uploaded_model_version(
                asset=asset,
                uploaded_file=serializer.validated_data["file"],
                version=serializer.validated_data["version"],
                uploaded_by=request.user,
                metadata=serializer.validated_data.get("metadata") or {},
            )
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ModelVersionSerializer(version).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="versions/import")
    def import_version(self, request, pk=None):
        asset = self.get_object()
        serializer = ModelVersionImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            version = import_model_version_from_offline_path(
                asset=asset,
                source_path=serializer.validated_data["source_path"],
                version=serializer.validated_data["version"],
                uploaded_by=request.user,
                metadata=serializer.validated_data.get("metadata") or {},
            )
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ModelVersionSerializer(version).data, status=status.HTTP_201_CREATED)


class ModelVersionViewSet(ReadOnlyModelViewSet):
    serializer_class = ModelVersionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["asset", "status", "sha256"]
    ordering_fields = ["created_at", "size_bytes"]

    def get_queryset(self):
        visible_assets = ModelAsset.objects.all()
        user = self.request.user
        if getattr(user, "role", None) != "admin":
            visible_assets = visible_assets.filter(visibility=ModelAsset.Visibility.SHARED)
        return ModelVersion.objects.select_related("asset", "uploaded_by").filter(asset__in=visible_assets)

    @action(detail=False, methods=["get"], url_path="cache-status")
    def cache_status(self, request):
        agent_id = request.query_params.get("agent")
        if not agent_id:
            return Response({"detail": "agent query parameter is required"}, status=status.HTTP_400_BAD_REQUEST)

        version_filter = _split_csv(request.query_params.get("versions", ""))
        versions_qs = self.get_queryset()
        if version_filter:
            versions_qs = versions_qs.filter(id__in=version_filter)
        versions = list(versions_qs)
        caches = {
            str(cache.version_id): cache
            for cache in ModelVersionCache.objects.filter(
                agent_id=agent_id,
                version__in=versions,
            ).select_related("version", "version__asset")
        }
        jobs = {
            str(job.version_id): job
            for job in ModelPrepareJob.objects.filter(
                agent_id=agent_id,
                version__in=versions,
                status__in=[
                    ModelPrepareJob.Status.QUEUED,
                    ModelPrepareJob.Status.DISPATCHED,
                    ModelPrepareJob.Status.PREPARING,
                ],
            ).order_by("created_at")
        }

        results = []
        for version in versions:
            cache = caches.get(str(version.id))
            job = jobs.get(str(version.id))
            results.append({
                "version": str(version.id),
                "asset": str(version.asset_id),
                "assetSlug": version.asset.slug,
                "versionLabel": version.version,
                "mountPath": mount_path_for_version(version),
                "status": cache.status if cache else ModelVersionCache.Status.MISSING,
                "cachePath": cache.cache_path if cache else "",
                "sha256": version.sha256,
                "sizeBytes": version.size_bytes,
                "prepareJob": {
                    "id": str(job.id),
                    "status": job.status,
                    "progressPercent": job.progress_percent,
                    "progressMessage": job.progress_message,
                } if job else None,
            })
        return Response({"results": results})

    @action(
        detail=True,
        methods=["get"],
        url_path="content",
        authentication_classes=[],
        permission_classes=[AllowAny],
    )
    def content(self, request, pk=None):
        agent = _agent_from_request(request)
        if not agent:
            return Response({"detail": "Valid agent bearer token required."}, status=status.HTTP_403_FORBIDDEN)
        try:
            version = ModelVersion.objects.select_related("asset").get(
                pk=pk,
                status=ModelVersion.Status.AVAILABLE,
            )
        except ModelVersion.DoesNotExist as exc:
            raise Http404 from exc
        if not can_agent_stream_version(agent, version):
            return Response({"detail": "No active prepare job authorizes this transfer."}, status=status.HTTP_403_FORBIDDEN)
        try:
            path = model_version_file_path(version)
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        response = FileResponse(path.open("rb"), as_attachment=True, filename=version.original_filename)
        response["Content-Length"] = str(version.size_bytes)
        response["X-HyperCube-Model-Version"] = str(version.id)
        response["X-HyperCube-Model-SHA256"] = version.sha256
        return response


class ModelUploadRequestViewSet(ModelViewSet):
    serializer_class = ModelUploadRequestSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    filterset_fields = ["status", "framework", "task"]
    search_fields = ["name", "slug", "description", "template_name", "original_filename"]
    ordering_fields = ["created_at", "updated_at", "status", "name"]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        qs = ModelUploadRequest.objects.select_related(
            "requester",
            "reviewer",
            "created_asset",
            "created_version",
            "created_template",
        )
        if getattr(self.request.user, "role", None) == "admin":
            return qs
        return qs.filter(requester=self.request.user)

    def get_permissions(self):
        if self.action in ("approve", "reject"):
            return [IsAdmin()]
        return [IsAuthenticated()]

    def destroy(self, request, *args, **kwargs):
        upload_request = self.get_object()
        if upload_request.status != ModelUploadRequest.Status.PENDING:
            return Response(
                {"detail": "Only pending model upload requests can be deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        upload_request = self.get_object()
        serializer = ModelUploadRequestReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            approved = approve_model_upload_request(
                upload_request,
                reviewer=request.user,
                note=serializer.validated_data.get("note", ""),
            )
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ModelUploadRequestSerializer(approved, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        upload_request = self.get_object()
        serializer = ModelUploadRequestReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            rejected = reject_model_upload_request(
                upload_request,
                reviewer=request.user,
                note=serializer.validated_data.get("note", ""),
            )
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ModelUploadRequestSerializer(rejected, context={"request": request}).data)


class ModelVersionCacheViewSet(ReadOnlyModelViewSet):
    serializer_class = ModelVersionCacheSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["agent", "version", "status"]
    ordering_fields = ["updated_at", "last_verified_at"]

    def get_queryset(self):
        return _visible_caches_for_user(self.request.user)


class ModelPrepareJobViewSet(ReadOnlyModelViewSet):
    serializer_class = ModelPrepareJobSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["agent", "version", "status"]
    ordering_fields = ["created_at", "updated_at"]

    def get_queryset(self):
        return _visible_prepare_jobs_for_user(self.request.user)


def _can_write_asset(asset, user) -> bool:
    return getattr(user, "role", None) == "admin"


def _visible_assets_for_user(user):
    qs = ModelAsset.objects.all()
    if getattr(user, "role", None) == "admin":
        return qs
    return qs.filter(visibility=ModelAsset.Visibility.SHARED)


def _visible_caches_for_user(user):
    return (
        ModelVersionCache.objects.select_related("agent", "version", "version__asset")
        .filter(version__asset__in=_visible_assets_for_user(user))
    )


def _visible_prepare_jobs_for_user(user):
    return (
        ModelPrepareJob.objects.select_related("agent", "version", "version__asset", "cache")
        .filter(version__asset__in=_visible_assets_for_user(user))
    )


def _split_csv(raw: str) -> list[str]:
    return [item.strip() for item in str(raw or "").split(",") if item.strip()]


def _agent_from_request(request):
    header = request.headers.get("Authorization") or ""
    prefix = "Bearer "
    if not header.startswith(prefix):
        return None
    token = header[len(prefix):].strip()
    if not token.startswith("agent_"):
        return None
    return Agent.objects.filter(token=token, status=Agent.Status.APPROVED).first()
