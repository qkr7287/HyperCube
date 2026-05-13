import hashlib
import os
import shutil
import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import slugify

from .models import ModelAsset, ModelVersion


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
