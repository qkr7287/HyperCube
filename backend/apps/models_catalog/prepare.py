import logging
from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.common import command_router
from apps.containers.models import ContainerRequest
from apps.containers.services.gpu_allocation import fail_reserved_gpu_allocations_for_request
from apps.containers.services.workspace import delete_workspace_token_for_request

from .models import ModelPrepareJob, ModelVersion, ModelVersionCache

logger = logging.getLogger(__name__)

ACTIVE_PREPARE_STATUSES = (
    ModelPrepareJob.Status.QUEUED,
    ModelPrepareJob.Status.DISPATCHED,
    ModelPrepareJob.Status.PREPARING,
)


def model_prepare_lease_seconds() -> int:
    return int(getattr(settings, "MODEL_PREPARE_LEASE_SECONDS", 24 * 60 * 60))


def model_prepare_progress_timeout_seconds() -> int:
    return int(getattr(settings, "MODEL_PREPARE_PROGRESS_TIMEOUT_SECONDS", 900))


def model_prepare_max_attempts() -> int:
    return int(getattr(settings, "MODEL_PREPARE_MAX_ATTEMPTS", 3))


def create_or_attach_prepare_jobs_for_request(request: ContainerRequest) -> list[ModelPrepareJob]:
    version_ids = _normalized_version_ids(request.model_version_ids)
    if not version_ids:
        request.prepare_job_ids = []
        request.deployment_phase = "create_container"
        request.save(update_fields=["prepare_job_ids", "deployment_phase", "updated_at"])
        return []
    if not request.target_agent_id:
        raise ValidationError("Model preparation requires a target agent")

    versions = list(
        ModelVersion.objects.select_related("asset")
        .filter(id__in=version_ids, status=ModelVersion.Status.AVAILABLE)
    )
    by_id = {str(version.id): version for version in versions}
    if len(by_id) != len(version_ids):
        raise ValidationError("One or more selected model versions are not available")

    now = timezone.now()
    lease_expires_at = now + timedelta(seconds=model_prepare_lease_seconds())
    waiting_jobs: list[ModelPrepareJob] = []
    job_ids: list[str] = []

    with transaction.atomic():
        for version_id in version_ids:
            version = by_id[version_id]
            cache, _ = ModelVersionCache.objects.select_for_update().get_or_create(
                agent_id=request.target_agent_id,
                version=version,
                defaults={
                    "status": ModelVersionCache.Status.MISSING,
                    "size_bytes": version.size_bytes,
                    "sha256": version.sha256,
                },
            )
            if _cache_is_ready_for_version(cache, version):
                continue

            job = (
                ModelPrepareJob.objects.select_for_update()
                .filter(
                    agent_id=request.target_agent_id,
                    version=version,
                    status__in=ACTIVE_PREPARE_STATUSES,
                )
                .order_by("created_at")
                .first()
            )
            if job is None:
                job = ModelPrepareJob.objects.create(
                    agent_id=request.target_agent_id,
                    version=version,
                    cache=cache,
                    status=ModelPrepareJob.Status.QUEUED,
                    progress_percent=0,
                    progress_message="Queued for model preparation",
                    bytes_total=version.size_bytes,
                    lease_expires_at=lease_expires_at,
                )
            job.waiting_requests.add(request)
            waiting_jobs.append(job)
            job_ids.append(str(job.id))

            cache.status = ModelVersionCache.Status.PREPARING
            cache.lease_expires_at = lease_expires_at
            cache.last_error = ""
            cache.size_bytes = version.size_bytes
            cache.sha256 = version.sha256
            cache.save(update_fields=[
                "status",
                "lease_expires_at",
                "last_error",
                "size_bytes",
                "sha256",
                "updated_at",
            ])

        request.prepare_job_ids = job_ids
        request.deployment_phase = "prepare_model_assets" if job_ids else "create_container"
        request.save(update_fields=["prepare_job_ids", "deployment_phase", "updated_at"])

    return waiting_jobs


def dispatch_prepare_jobs(jobs: list[ModelPrepareJob]) -> None:
    for job in jobs:
        dispatch_prepare_job(job)


def dispatch_prepare_job(job: ModelPrepareJob) -> bool:
    job = ModelPrepareJob.objects.select_related("agent", "version", "version__asset").get(id=job.id)
    if job.status != ModelPrepareJob.Status.QUEUED:
        return False

    agent_channel = command_router.get_agent_channel(str(job.agent_id))
    if not agent_channel:
        fail_prepare_job(job, "agent offline before model preparation dispatch")
        return False

    now = timezone.now()
    job.status = ModelPrepareJob.Status.DISPATCHED
    job.dispatched_at = now
    job.last_progress_at = now
    job.lease_expires_at = now + timedelta(seconds=model_prepare_lease_seconds())
    job.progress_message = "Model preparation dispatched to agent"
    job.save(update_fields=[
        "status",
        "dispatched_at",
        "last_progress_at",
        "lease_expires_at",
        "progress_message",
        "updated_at",
    ])

    command_router.record_pending(str(job.id), "__api__", str(job.agent_id))
    payload = {
        "type": "command",
        "requestId": str(job.id),
        "command": "prepare_model_assets",
        "params": _prepare_job_payload(job),
    }
    try:
        async_to_sync(get_channel_layer().send)(agent_channel, {
            "type": "ws.send",
            "payload": payload,
        })
        logger.info("[model-prepare] sent job %s to agent %s", job.id, job.agent_id)
        return True
    except Exception:
        logger.exception("[model-prepare] failed to dispatch job %s", job.id)
        fail_prepare_job(job, "agent model preparation dispatch failed")
        return False


def handle_prepare_progress(data: dict) -> bool:
    request_id = data.get("requestId")
    if not request_id:
        return False
    try:
        job = ModelPrepareJob.objects.select_related("cache").get(id=request_id)
    except (ModelPrepareJob.DoesNotExist, ValueError, TypeError):
        return False

    body = data.get("data") or {}
    percent = data.get("percent")
    if percent is None:
        percent = body.get("percent")
    bytes_done = body.get("bytesDone") or body.get("bytes_done")
    message = data.get("message") or body.get("message") or "Preparing model assets"

    now = timezone.now()
    job.status = ModelPrepareJob.Status.PREPARING
    job.started_at = job.started_at or now
    job.last_progress_at = now
    job.progress_percent = _bounded_percent(percent)
    job.progress_message = str(message)
    if isinstance(bytes_done, int):
        job.bytes_done = max(0, bytes_done)
    job.lease_expires_at = now + timedelta(seconds=model_prepare_lease_seconds())
    job.save(update_fields=[
        "status",
        "started_at",
        "last_progress_at",
        "progress_percent",
        "progress_message",
        "bytes_done",
        "lease_expires_at",
        "updated_at",
    ])
    if job.cache_id:
        ModelVersionCache.objects.filter(id=job.cache_id).update(
            status=ModelVersionCache.Status.PREPARING,
            lease_expires_at=job.lease_expires_at,
            updated_at=now,
        )
    _fan_out_prepare_progress(job)
    return True


def handle_prepare_response(data: dict) -> bool:
    request_id = data.get("requestId")
    if not request_id:
        return False
    try:
        job = ModelPrepareJob.objects.select_related("cache", "version", "version__asset").get(id=request_id)
    except (ModelPrepareJob.DoesNotExist, ValueError, TypeError):
        return False

    if data.get("success"):
        try:
            _mark_prepare_job_ready(job, data.get("data") or {})
        except ValidationError as exc:
            fail_prepare_job(job, str(exc))
        else:
            _dispatch_ready_waiters(job)
    else:
        fail_prepare_job(job, str(data.get("error") or "model preparation failed"))
    return True


def fail_prepare_job(job: ModelPrepareJob, error: str) -> None:
    now = timezone.now()
    error = str(error or "model preparation failed")
    ModelPrepareJob.objects.filter(id=job.id).update(
        status=ModelPrepareJob.Status.FAILED,
        progress_message=error,
        error=error,
        failed_at=now,
        lease_expires_at=None,
        updated_at=now,
    )
    if job.cache_id:
        ModelVersionCache.objects.filter(id=job.cache_id).update(
            status=ModelVersionCache.Status.FAILED,
            last_error=error,
            lease_expires_at=None,
            updated_at=now,
        )

    waiting_requests = list(job.waiting_requests.all())
    for request in waiting_requests:
        if request.status not in (
            ContainerRequest.Status.APPROVED,
            ContainerRequest.Status.DEPLOYING,
        ):
            continue
        request.status = ContainerRequest.Status.FAILED
        request.deployment_phase = "prepare_model_assets"
        request.progress_message = error
        request.save(update_fields=["status", "deployment_phase", "progress_message", "updated_at"])
        fail_reserved_gpu_allocations_for_request(request, error)
        delete_workspace_token_for_request(request)


def requeue_prepare_job(job: ModelPrepareJob, *, now=None) -> bool:
    """stuck 된 prepare job 을 QUEUED 로 되돌리고 재dispatch.

    agent 의 prepare_model_assets 는 sha256 일치 파일을 재다운로드 없이
    skip 하는 멱등 명령이라 안전하게 재시도할 수 있다.
    """
    now = now or timezone.now()
    job.status = ModelPrepareJob.Status.QUEUED
    job.attempt_count = (job.attempt_count or 0) + 1
    job.last_progress_at = now
    job.lease_expires_at = now + timedelta(seconds=model_prepare_lease_seconds())
    job.progress_message = (
        f"Re-dispatching model preparation (retry {job.attempt_count})"
    )
    job.save(update_fields=[
        "status",
        "attempt_count",
        "last_progress_at",
        "lease_expires_at",
        "progress_message",
        "updated_at",
    ])
    logger.info("[model-prepare] requeued job %s (attempt %s)", job.id, job.attempt_count)
    return dispatch_prepare_job(job)


def reconcile_agent_prepare_jobs(agent_id, *, now=None) -> int:
    """agent 재접속 시 호출 — 그 agent 의 stuck prepare job 을 즉시 복구.

    WS 끊김으로 prepare 응답이 유실되면 job 이 progress 중간에 멈춘다.
    cleanup_stale 의 progress watchdog 과 같은 기준이되, 다음 주기(최대
    60초)를 기다리지 않고 reconnect 즉시 적용한다.
    """
    now = now or timezone.now()
    progress_deadline = now - timedelta(seconds=model_prepare_progress_timeout_seconds())
    max_attempts = model_prepare_max_attempts()
    jobs = list(
        ModelPrepareJob.objects.filter(
            agent_id=agent_id,
            status__in=ACTIVE_PREPARE_STATUSES,
            last_progress_at__lt=progress_deadline,
        )[:100]
    )
    for job in jobs:
        if (job.attempt_count or 0) >= max_attempts:
            fail_prepare_job(
                job,
                "model preparation stalled — agent reconnected without progress",
            )
        else:
            requeue_prepare_job(job, now=now)
    return len(jobs)


def cleanup_stale_model_prepare_jobs(*, now=None) -> int:
    """주기 task — stuck 된 prepare job 을 정리한다.

    두 종류의 stuck:
      1. lease 만료 (전체 데드라인 초과) → 무조건 실패.
      2. progress 무응답 watchdog (agent 침묵) → 재시도 여지가 있으면
         재dispatch, 시도 한도 초과면 실패.
    """
    now = now or timezone.now()
    handled = 0

    # 1. 전체 데드라인(lease) 만료.
    expired = list(
        ModelPrepareJob.objects.filter(
            status__in=ACTIVE_PREPARE_STATUSES,
            lease_expires_at__lt=now,
        )[:100]
    )
    for job in expired:
        job.status = ModelPrepareJob.Status.STALE
        job.failed_at = now
        job.error = "model preparation lease expired"
        job.save(update_fields=["status", "failed_at", "error", "updated_at"])
        fail_prepare_job(job, "model preparation lease expired")
        handled += 1

    # 2. progress 무응답 watchdog — 마지막 progress 후 N초간 침묵.
    progress_deadline = now - timedelta(seconds=model_prepare_progress_timeout_seconds())
    expired_ids = {job.id for job in expired}
    stuck = [
        job
        for job in ModelPrepareJob.objects.filter(
            status__in=ACTIVE_PREPARE_STATUSES,
            last_progress_at__lt=progress_deadline,
        )[:100]
        if job.id not in expired_ids
    ]
    max_attempts = model_prepare_max_attempts()
    for job in stuck:
        if (job.attempt_count or 0) >= max_attempts:
            fail_prepare_job(
                job,
                f"model preparation stalled — no agent progress after {job.attempt_count} retries",
            )
        else:
            requeue_prepare_job(job, now=now)
        handled += 1

    return handled


def model_mounts_payload_for_request(request: ContainerRequest) -> list[dict]:
    version_ids = _normalized_version_ids(request.model_version_ids)
    if not version_ids:
        return []
    caches = {
        str(cache.version_id): cache
        for cache in ModelVersionCache.objects.select_related("version", "version__asset")
        .filter(agent_id=request.target_agent_id, version_id__in=version_ids)
    }
    mounts = []
    for version_id in version_ids:
        cache = caches.get(version_id)
        if not cache or not _cache_is_ready_for_version(cache, cache.version):
            raise ValidationError("Selected model assets are not ready on the target agent")
        mounts.append({
            "versionId": str(cache.version_id),
            "assetSlug": cache.version.asset.slug,
            "sourcePath": cache.cache_path,
            "mountPath": mount_path_for_version(cache.version),
            "readOnly": True,
            "sha256": cache.version.sha256,
            "sizeBytes": cache.version.size_bytes,
        })
    return mounts


def mount_path_for_version(version: ModelVersion) -> str:
    version_slug = slugify(version.version) or str(version.id)[:8]
    return f"/workspace/models/{version.asset.slug}@{version_slug}"


def can_agent_stream_version(agent, version: ModelVersion) -> bool:
    return ModelPrepareJob.objects.filter(
        agent=agent,
        version=version,
        status__in=ACTIVE_PREPARE_STATUSES,
    ).exists()


def _prepare_job_payload(job: ModelPrepareJob) -> dict:
    version = job.version
    return {
        "jobId": str(job.id),
        "transferMode": job.transfer_mode,
        "assets": [
            {
                "versionId": str(version.id),
                "assetId": str(version.asset_id),
                "assetSlug": version.asset.slug,
                "version": version.version,
                "sizeBytes": version.size_bytes,
                "sha256": version.sha256,
                "checksum": version.sha256,
                "source": {
                    "type": ModelPrepareJob.TransferMode.BACKEND_STREAM,
                    "contentUrl": f"/api/model-versions/{version.id}/content/",
                    "auth": "agent_bearer",
                    "sha256": version.sha256,
                    "checksum": version.sha256,
                    "sizeBytes": version.size_bytes,
                },
                "mountPath": mount_path_for_version(version),
            }
        ],
    }


def _mark_prepare_job_ready(job: ModelPrepareJob, response_data: dict) -> None:
    cache_path = (
        response_data.get("cachePath")
        or response_data.get("sourcePath")
        or response_data.get("path")
        or ""
    )
    if not cache_path:
        raise ValidationError("model preparation response did not include cachePath")
    reported_sha = response_data.get("sha256") or job.version.sha256
    if reported_sha != job.version.sha256:
        raise ValidationError("model preparation checksum mismatch")

    now = timezone.now()
    cache = job.cache
    if cache is None:
        cache, _ = ModelVersionCache.objects.get_or_create(
            agent=job.agent,
            version=job.version,
        )
    cache.status = ModelVersionCache.Status.READY
    cache.cache_path = str(cache_path)
    cache.size_bytes = job.version.size_bytes
    cache.sha256 = job.version.sha256
    cache.last_verified_at = now
    cache.lease_expires_at = None
    cache.last_error = ""
    cache.save(update_fields=[
        "status",
        "cache_path",
        "size_bytes",
        "sha256",
        "last_verified_at",
        "lease_expires_at",
        "last_error",
        "updated_at",
    ])

    job.cache = cache
    job.status = ModelPrepareJob.Status.READY
    job.progress_percent = 100
    job.progress_message = "Model assets ready"
    job.bytes_done = job.version.size_bytes
    job.completed_at = now
    job.lease_expires_at = None
    job.error = ""
    job.save(update_fields=[
        "cache",
        "status",
        "progress_percent",
        "progress_message",
        "bytes_done",
        "completed_at",
        "lease_expires_at",
        "error",
        "updated_at",
    ])
    _fan_out_prepare_progress(job)


def _dispatch_ready_waiters(job: ModelPrepareJob) -> None:
    from apps.containers.services.deployment import dispatch_request_to_agent
    from apps.containers.services.workspace import prepare_workspace_secret_for_request

    for request in job.waiting_requests.select_related("template", "target_agent").all():
        if request.status not in (
            ContainerRequest.Status.APPROVED,
            ContainerRequest.Status.DEPLOYING,
        ):
            continue
        if not _all_prepare_jobs_ready(request):
            continue
        try:
            secret = prepare_workspace_secret_for_request(request)
            request.deployment_phase = "create_container"
            request.progress_message = "Model assets ready; creating container"
            request.progress_percent = None
            request.save(update_fields=[
                "deployment_phase",
                "progress_message",
                "progress_percent",
                "updated_at",
            ])
            dispatch_request_to_agent(request, workspace_secret=secret)
        except Exception as exc:
            error = str(exc)
            request.status = ContainerRequest.Status.FAILED
            request.progress_message = error
            request.save(update_fields=["status", "progress_message", "updated_at"])
            fail_reserved_gpu_allocations_for_request(request, error)
            delete_workspace_token_for_request(request)


def _fan_out_prepare_progress(job: ModelPrepareJob) -> None:
    message = job.progress_message or "Preparing model assets"
    percent = job.progress_percent
    now = timezone.now()
    updates = []
    for request in job.waiting_requests.all():
        if request.status not in (
            ContainerRequest.Status.APPROVED,
            ContainerRequest.Status.DEPLOYING,
        ):
            continue
        request.status = ContainerRequest.Status.DEPLOYING
        request.deployment_phase = "prepare_model_assets"
        request.progress_message = message
        request.progress_percent = percent
        request.updated_at = now
        updates.append(request)
    if updates:
        ContainerRequest.objects.bulk_update(
            updates,
            ["status", "deployment_phase", "progress_message", "progress_percent", "updated_at"],
        )


def _all_prepare_jobs_ready(request: ContainerRequest) -> bool:
    job_ids = request.prepare_job_ids or []
    if not job_ids:
        return True
    return not ModelPrepareJob.objects.filter(
        id__in=job_ids,
    ).exclude(status=ModelPrepareJob.Status.READY).exists()


def _cache_is_ready_for_version(cache: ModelVersionCache, version: ModelVersion) -> bool:
    return (
        cache.status == ModelVersionCache.Status.READY
        and bool(cache.cache_path)
        and cache.sha256 == version.sha256
        and cache.size_bytes == version.size_bytes
    )


def _bounded_percent(value):
    if value is None:
        return None
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return None


def _normalized_version_ids(values) -> list[str]:
    normalized = []
    seen = set()
    for value in values or []:
        text = str(value)
        if text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized
