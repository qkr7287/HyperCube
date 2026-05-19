from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Q

from apps.containers.models import Container, ContainerRequest, GpuAllocation


ACTIVE_WORKSPACE_STATUSES = [
    Container.Status.CREATED,
    Container.Status.RUNNING,
    Container.Status.PAUSED,
    Container.Status.RESTARTING,
]


def gpu_shared_mode_enabled() -> bool:
    return bool(getattr(settings, "HC_GPU_SHARED_MODE_ENABLED", False))


def max_active_workspaces_per_user() -> int:
    return int(getattr(settings, "HC_MAX_ACTIVE_WORKSPACES_PER_USER", 2))


def max_active_gpu_slices_per_user() -> int:
    return int(getattr(settings, "HC_MAX_ACTIVE_GPU_SLICES_PER_USER", 1))


def max_workspace_runtime_hours() -> int:
    return int(getattr(settings, "HC_MAX_WORKSPACE_RUNTIME_HOURS", 72))


def request_payload_policy_errors(*, gpu_share_ok=False, requested_max_runtime_hours=None) -> dict:
    errors = {}
    if gpu_share_ok and not gpu_shared_mode_enabled():
        errors["gpu_share_ok"] = "Shared GPU mode is disabled until memory accounting policy is enabled."

    max_hours = max_workspace_runtime_hours()
    if max_hours > 0 and requested_max_runtime_hours and requested_max_runtime_hours > max_hours:
        errors["requested_max_runtime_hours"] = (
            f"Workspace runtime cannot exceed {max_hours} hours."
        )
    return errors


def enforce_approval_policy(request: ContainerRequest) -> None:
    """Validate quota/runtime policy at approval time while the request row is locked."""
    errors = request_payload_policy_errors(
        gpu_share_ok=request.gpu_share_ok,
        requested_max_runtime_hours=request.requested_max_runtime_hours,
    )
    if errors:
        raise ValidationError(errors)

    if request.workspace_enabled_snapshot:
        _enforce_active_workspace_quota(request)
    _enforce_active_gpu_quota(request)


def enforce_runtime_extension_policy(container: Container, additional_hours: int) -> None:
    max_hours = max_workspace_runtime_hours()
    if max_hours <= 0:
        return
    current_hours = container.workspace_max_runtime_hours or 0
    if current_hours + additional_hours > max_hours:
        raise ValidationError(
            f"Workspace runtime cannot exceed {max_hours} hours."
        )


def _enforce_active_workspace_quota(request: ContainerRequest) -> None:
    limit = max_active_workspaces_per_user()
    if limit <= 0:
        return
    active_count = Container.objects.filter(
        requester=request.requester,
        workspace_enabled=True,
        status__in=ACTIVE_WORKSPACE_STATUSES,
    ).count()
    if active_count >= limit:
        raise ValidationError(
            f"Active workspace quota exceeded: maximum {limit} per user."
        )


def _enforce_active_gpu_quota(request: ContainerRequest) -> None:
    limit = max_active_gpu_slices_per_user()
    if limit <= 0:
        return
    selected_count = request.gpu_slice_selections.count()
    if selected_count <= 0:
        return

    active_count = (
        GpuAllocation.objects.filter(
            status__in=[GpuAllocation.Status.RESERVED, GpuAllocation.Status.ACTIVE],
        )
        .filter(
            Q(container_request__requester=request.requester)
            | Q(container__requester=request.requester)
        )
        .count()
    )
    if active_count + selected_count > limit:
        raise ValidationError(
            f"GPU quota exceeded: maximum {limit} active or reserved GPU slice per user."
        )
