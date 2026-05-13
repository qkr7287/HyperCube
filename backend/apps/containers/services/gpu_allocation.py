from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.agents.models import GpuDevice, GpuSlice
from apps.containers.models import Container, ContainerRequest, GpuAllocation

GPU_RESERVE_TIMEOUT = timedelta(minutes=10)


class GpuReservationError(ValueError):
    pass


def reserve_gpu_slices_for_request(
    request: ContainerRequest,
    *,
    now=None,
    timeout: timedelta = GPU_RESERVE_TIMEOUT,
) -> list[GpuAllocation]:
    """Reserve selected GPU slices for an approved request.

    Call inside a transaction that has locked the ContainerRequest row.
    """
    now = now or timezone.now()
    slice_ids = list(
        request.gpu_slice_selections.order_by("id").values_list("slice_id", flat=True)
    )
    if not slice_ids:
        return []

    if request.template and request.template.kind == "compose":
        raise GpuReservationError("GPU allocation is not supported for compose templates yet")

    slices = list(
        GpuSlice.objects.select_for_update()
        .select_related("gpu")
        .filter(id__in=slice_ids)
    )
    if len(slices) != len(set(slice_ids)):
        raise GpuReservationError("One or more requested GPU slices do not exist")

    slices_by_id = {slice_obj.id: slice_obj for slice_obj in slices}
    ordered_slices = [slices_by_id[slice_id] for slice_id in slice_ids]
    reserved_until = now + timeout
    allocations: list[GpuAllocation] = []

    for slice_obj in ordered_slices:
        if slice_obj.gpu.agent_id != request.target_agent_id:
            raise GpuReservationError("Requested GPU slice does not belong to the target agent")
        if slice_obj.status != GpuSlice.HardwareStatus.AVAILABLE:
            raise GpuReservationError("Requested GPU slice is not available")
        if slice_obj.gpu.status != GpuDevice.HardwareStatus.AVAILABLE:
            raise GpuReservationError("Requested GPU device is not available")

        existing = list(
            GpuAllocation.objects.select_for_update().filter(
                slice=slice_obj,
                status__in=[GpuAllocation.Status.RESERVED, GpuAllocation.Status.ACTIVE],
            )
        )
        if existing:
            shared_allowed = (
                request.gpu_share_ok
                and slice_obj.allow_shared
                and all(a.share_mode == GpuAllocation.ShareMode.SHARED for a in existing)
            )
            if not shared_allowed:
                raise GpuReservationError("Requested GPU slice is already reserved or active")

        share_mode = (
            GpuAllocation.ShareMode.SHARED
            if request.gpu_share_ok and slice_obj.allow_shared
            else GpuAllocation.ShareMode.EXCLUSIVE
        )
        allocations.append(
            GpuAllocation.objects.create(
                slice=slice_obj,
                container_request=request,
                status=GpuAllocation.Status.RESERVED,
                share_mode=share_mode,
                reserved_until=reserved_until,
            )
        )

    return allocations


def gpu_payload_for_request(request: ContainerRequest) -> list[dict]:
    allocations = (
        request.gpu_allocations.select_related("slice")
        .filter(status=GpuAllocation.Status.RESERVED)
        .order_by("id")
    )
    return [
        {
            "deviceId": allocation.slice.device_id,
            "kind": allocation.slice.kind,
        }
        for allocation in allocations
    ]


def activate_gpu_allocations_for_request(
    request: ContainerRequest,
    container: Container | None,
    *,
    now=None,
) -> list[int]:
    now = now or timezone.now()
    allocations = list(
        request.gpu_allocations.select_related("slice")
        .filter(status=GpuAllocation.Status.RESERVED)
        .order_by("id")
    )
    slice_ids = [allocation.slice_id for allocation in allocations]
    for allocation in allocations:
        allocation.status = GpuAllocation.Status.ACTIVE
        allocation.container = container
        allocation.activated_at = now
        allocation.save(update_fields=["status", "container", "activated_at"])
    if container is not None:
        container.allocated_gpu_slice_ids = slice_ids
        container.save(update_fields=["allocated_gpu_slice_ids", "last_seen"])
    return slice_ids


def fail_reserved_gpu_allocations_for_request(
    request: ContainerRequest,
    reason: str,
    *,
    now=None,
) -> int:
    now = now or timezone.now()
    qs = request.gpu_allocations.filter(status=GpuAllocation.Status.RESERVED)
    count = 0
    for allocation in qs:
        allocation.status = GpuAllocation.Status.FAILED
        allocation.failed_at = now
        allocation.failure_reason = reason
        allocation.save(update_fields=["status", "failed_at", "failure_reason"])
        count += 1
    return count


def release_gpu_allocations_for_container(
    container: Container,
    *,
    now=None,
) -> int:
    now = now or timezone.now()
    qs = container.gpu_allocations.filter(
        status__in=[GpuAllocation.Status.RESERVED, GpuAllocation.Status.ACTIVE]
    )
    count = 0
    for allocation in qs:
        allocation.status = GpuAllocation.Status.RELEASED
        allocation.released_at = now
        allocation.save(update_fields=["status", "released_at"])
        count += 1
    return count


@transaction.atomic
def cleanup_expired_gpu_reservations(*, now=None) -> int:
    now = now or timezone.now()
    allocations = list(
        GpuAllocation.objects.select_for_update()
        .filter(status=GpuAllocation.Status.RESERVED, reserved_until__lt=now)
    )
    touched_requests: set[str] = set()

    for allocation in allocations:
        allocation.status = GpuAllocation.Status.FAILED
        allocation.failed_at = now
        allocation.failure_reason = "reservation timeout"
        allocation.save(update_fields=["status", "failed_at", "failure_reason"])

        request = allocation.container_request
        if request is None or str(request.id) in touched_requests:
            continue
        touched_requests.add(str(request.id))
        has_active_container = bool(request.target_container_id)
        has_live_allocation = request.gpu_allocations.filter(
            status__in=[GpuAllocation.Status.RESERVED, GpuAllocation.Status.ACTIVE]
        ).exists()
        if not has_active_container and not has_live_allocation:
            request.status = ContainerRequest.Status.FAILED
            request.progress_message = "GPU reservation timeout"
            request.deployment_log += "\n--- gpu_allocation ---\nreservation timeout"
            request.save(update_fields=[
                "status",
                "progress_message",
                "deployment_log",
                "updated_at",
            ])

    return len(allocations)
