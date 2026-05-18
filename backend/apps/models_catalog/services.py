import hashlib
import os
import shutil
import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import slugify

from .models import ModelAsset, ModelUploadRequest, ModelVersion


def storage_root() -> Path:
    root = Path(settings.HC_MODEL_STORAGE_DIR).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def import_root() -> Path:
    root = Path(settings.HC_MODEL_IMPORT_DIR).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_uploaded_model_version(asset, uploaded_file, version, uploaded_by, metadata=None):
    filename = _safe_filename(uploaded_file.name)
    if not filename:
        raise ValidationError("Uploaded file must have a valid filename")
    return _store_stream(
        asset=asset,
        version=version,
        filename=filename,
        chunks=uploaded_file.chunks(),
        uploaded_by=uploaded_by,
        metadata=metadata or {},
    )


def create_model_upload_request(requester, uploaded_file, **data):
    filename = _safe_filename(uploaded_file.name)
    if not filename:
        raise ValidationError("Uploaded file must have a valid filename")

    upload_request = ModelUploadRequest.objects.create(
        requester=requester,
        slug=data.get("slug") or slugify(data.get("name", "")) or uuid.uuid4().hex[:12],
        **{key: value for key, value in data.items() if key != "slug"},
    )
    try:
        _store_request_file(upload_request, uploaded_file, filename)
    except Exception:
        _delete_request_file(upload_request)
        upload_request.delete()
        raise
    return upload_request


def approve_model_upload_request(upload_request, reviewer, note=""):
    from apps.containers.models import ContainerTemplate

    with transaction.atomic():
        req = ModelUploadRequest.objects.select_for_update().get(pk=upload_request.pk)
        if req.status != ModelUploadRequest.Status.PENDING:
            raise ValidationError("Only pending model upload requests can be approved")
        source_path = _request_file_path(req)
        if not source_path.is_file():
            raise ValidationError("Uploaded model file does not exist")

        asset = ModelAsset.objects.create(
            owner=req.requester,
            name=req.name,
            slug=_unique_asset_slug(req.slug or req.name),
            description=req.description,
            visibility=ModelAsset.Visibility.SHARED,
            framework=req.framework,
            task=req.task,
            tags=req.tags or [],
        )
        final_rel = _relative_storage_path(asset, req.version, req.original_filename)
        final_path = storage_root() / final_rel
        final_path.parent.mkdir(parents=True, exist_ok=True)
        if final_path.exists():
            raise ValidationError("A file already exists for this approved model version")
        os.replace(source_path, final_path)

        version = ModelVersion.objects.create(
            asset=asset,
            version=req.version,
            original_filename=req.original_filename,
            storage_path=final_rel.as_posix(),
            size_bytes=req.size_bytes,
            sha256=req.sha256,
            metadata={"model_upload_request": str(req.id)},
            uploaded_by=req.requester,
        )
        template = ContainerTemplate.objects.create(
            name=_unique_template_name(req.template_name or f"{req.name} Workspace"),
            description=req.template_description
            or f"Approved model upload request for {req.name}:{req.version}.",
            kind=ContainerTemplate.Kind.SIMPLE,
            category=ContainerTemplate.Category.ML,
            requires_gpu=req.requires_gpu,
            workspace_enabled=True,
            workspace_kind=req.workspace_kind or ContainerTemplate.WorkspaceKind.JUPYTER,
            workspace_port=req.workspace_port or 8888,
            default_workdir="/workspace",
            network_policy=ContainerTemplate.NetworkPolicy.INTERNAL_ONLY,
            default_max_runtime_hours=req.default_max_runtime_hours,
            min_cpu_percent=req.min_cpu_percent,
            min_memory_mb=req.min_memory_mb,
            min_workspace_gb=req.min_workspace_gb,
            image=req.base_image,
            image_options=[],
            env_schema=[],
            port_schema=[],
            default_volumes=[],
            default_model_version_ids=[str(version.id)],
            compose_yaml="",
            created_by=reviewer,
        )
        req.status = ModelUploadRequest.Status.APPROVED
        req.reviewer = reviewer
        req.review_note = note or ""
        from django.utils import timezone

        req.reviewed_at = timezone.now()
        req.created_asset = asset
        req.created_version = version
        req.created_template = template
        req.save(
            update_fields=[
                "status",
                "reviewer",
                "review_note",
                "reviewed_at",
                "created_asset",
                "created_version",
                "created_template",
                "updated_at",
            ]
        )
    return req


def reject_model_upload_request(upload_request, reviewer, note=""):
    from django.utils import timezone

    with transaction.atomic():
        req = ModelUploadRequest.objects.select_for_update().get(pk=upload_request.pk)
        if req.status != ModelUploadRequest.Status.PENDING:
            raise ValidationError("Only pending model upload requests can be rejected")
        req.status = ModelUploadRequest.Status.REJECTED
        req.reviewer = reviewer
        req.review_note = note or ""
        req.reviewed_at = timezone.now()
        req.save(update_fields=["status", "reviewer", "review_note", "reviewed_at", "updated_at"])
    return req


def import_model_version_from_offline_path(asset, source_path, version, uploaded_by, metadata=None):
    source = _resolve_import_source(source_path)
    if not source.is_file():
        raise ValidationError("Import source file does not exist")

    def chunks():
        with source.open("rb") as handle:
            while True:
                block = handle.read(1024 * 1024)
                if not block:
                    break
                yield block

    return _store_stream(
        asset=asset,
        version=version,
        filename=_safe_filename(source.name),
        chunks=chunks(),
        uploaded_by=uploaded_by,
        metadata=metadata or {},
    )


def model_version_file_path(version: ModelVersion) -> Path:
    root = storage_root()
    path = (root / version.storage_path).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValidationError("Stored model path escapes HC_MODEL_STORAGE_DIR") from exc
    if not path.is_file():
        raise ValidationError("Stored model file does not exist")
    return path


def _store_stream(asset, version, filename, chunks, uploaded_by, metadata):
    version = str(version or "").strip()
    if not version:
        raise ValidationError("version is required")
    if ModelVersion.objects.filter(asset=asset, version=version).exists():
        raise ValidationError("This model version already exists")

    root = storage_root()
    tmp_dir = root / "_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / f"{uuid.uuid4().hex}.upload"
    final_rel = _relative_storage_path(asset, version, filename)
    final_path = root / final_rel
    final_path.parent.mkdir(parents=True, exist_ok=True)
    if final_path.exists():
        raise ValidationError("A file already exists for this model version")

    digest = hashlib.sha256()
    size = 0
    try:
        with tmp_path.open("wb") as out:
            for chunk in chunks:
                if not chunk:
                    continue
                out.write(chunk)
                digest.update(chunk)
                size += len(chunk)
        if size <= 0:
            raise ValidationError("Uploaded model file is empty")
        os.replace(tmp_path, final_path)
        with transaction.atomic():
            return ModelVersion.objects.create(
                asset=asset,
                version=version,
                original_filename=filename,
                storage_path=final_rel.as_posix(),
                size_bytes=size,
                sha256=digest.hexdigest(),
                metadata=metadata or {},
                uploaded_by=uploaded_by,
            )
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        if final_path.exists() and not ModelVersion.objects.filter(storage_path=final_rel.as_posix()).exists():
            final_path.unlink()
        raise


def _store_request_file(upload_request: ModelUploadRequest, uploaded_file, filename: str) -> None:
    root = storage_root()
    rel = Path("_requests") / str(upload_request.id) / filename
    final_path = root / rel
    final_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = final_path.with_suffix(final_path.suffix + f".{uuid.uuid4().hex}.tmp")
    digest = hashlib.sha256()
    size = 0
    try:
        with tmp_path.open("wb") as out:
            for chunk in uploaded_file.chunks():
                if not chunk:
                    continue
                out.write(chunk)
                digest.update(chunk)
                size += len(chunk)
        if size <= 0:
            raise ValidationError("Uploaded model file is empty")
        os.replace(tmp_path, final_path)
        upload_request.original_filename = filename
        upload_request.upload_storage_path = rel.as_posix()
        upload_request.size_bytes = size
        upload_request.sha256 = digest.hexdigest()
        upload_request.save(
            update_fields=[
                "original_filename",
                "upload_storage_path",
                "size_bytes",
                "sha256",
                "updated_at",
            ]
        )
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        if final_path.exists():
            final_path.unlink()
        raise


def _request_file_path(upload_request: ModelUploadRequest) -> Path:
    root = storage_root()
    path = (root / upload_request.upload_storage_path).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValidationError("Stored upload request path escapes HC_MODEL_STORAGE_DIR") from exc
    return path


def _delete_request_file(upload_request: ModelUploadRequest) -> None:
    if not upload_request.upload_storage_path:
        return
    try:
        path = _request_file_path(upload_request)
    except ValidationError:
        return
    if path.exists():
        path.unlink()


def _unique_asset_slug(raw_value: str) -> str:
    base = slugify(raw_value) or uuid.uuid4().hex[:12]
    slug = base[:180]
    suffix = 2
    while ModelAsset.objects.filter(slug=slug).exists():
        tail = f"-{suffix}"
        slug = f"{base[:180 - len(tail)]}{tail}"
        suffix += 1
    return slug


def _unique_template_name(raw_value: str) -> str:
    from apps.containers.models import ContainerTemplate

    base = str(raw_value or "Uploaded Model Workspace").strip()[:100]
    if not base:
        base = "Uploaded Model Workspace"
    name = base
    suffix = 2
    while ContainerTemplate.objects.filter(name=name).exists():
        tail = f" {suffix}"
        name = f"{base[:100 - len(tail)]}{tail}"
        suffix += 1
    return name


def _relative_storage_path(asset: ModelAsset, version: str, filename: str) -> Path:
    version_slug = slugify(version) or uuid.uuid4().hex
    return Path(str(asset.id)) / version_slug / filename


def _safe_filename(raw_name: str) -> str:
    name = Path(raw_name or "").name
    if name in ("", ".", ".."):
        return ""
    return name.replace("\\", "_").replace("/", "_")


def _resolve_import_source(source_path: str) -> Path:
    raw = str(source_path or "").strip()
    if "://" in raw:
        raise ValidationError("External URL imports are not allowed")
    root = import_root()
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValidationError("Import source must stay inside HC_MODEL_IMPORT_DIR") from exc
    return resolved
