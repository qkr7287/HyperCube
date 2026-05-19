import uuid
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.agents.models import Agent, GpuDevice, GpuSlice

GPU_INVENTORY_SENTINEL = "__gpu_inventory__"
GPU_INVENTORY_REQUEST_PREFIX = "gpu-inventory"


def build_gpu_inventory_request_id(agent_id: str) -> str:
    return f"{GPU_INVENTORY_REQUEST_PREFIX}:{agent_id}:{uuid.uuid4()}"


def is_gpu_inventory_request_id(request_id: str | None) -> bool:
    return bool(request_id and request_id.startswith(f"{GPU_INVENTORY_REQUEST_PREFIX}:"))


def mark_agent_gpu_inventory_offline(agent: Agent | str, *, when=None) -> dict:
    if not isinstance(agent, Agent):
        agent = Agent.objects.get(id=agent)

    when = when or timezone.now()
    device_count = agent.gpu_devices.update(
        status=GpuDevice.HardwareStatus.OFFLINE,
        last_seen_at=when,
    )
    slice_count = GpuSlice.objects.filter(gpu__agent=agent).update(
        status=GpuSlice.HardwareStatus.OFFLINE,
        last_seen_at=when,
    )
    return {"devices": device_count, "slices": slice_count}


@transaction.atomic
def apply_gpu_inventory(agent: Agent | str, payload: dict[str, Any]) -> dict:
    """Upsert one agent's reported GPU inventory.

    The service accepts either the agent command envelope
    `{success, data: {gpus: [...]}}` or the inner `{gpus: [...]}` payload.
    Missing capabilities and command failures make prior inventory offline.
    """
    if not isinstance(agent, Agent):
        agent = Agent.objects.select_for_update().get(id=agent)

    now = timezone.now()
    if not isinstance(payload, dict):
        marked = mark_agent_gpu_inventory_offline(agent, when=now)
        return {"ok": False, "status": "offline", "reason": "invalid payload", **marked}

    success = payload.get("success", True)
    if success is False:
        marked = mark_agent_gpu_inventory_offline(agent, when=now)
        return {
            "ok": False,
            "status": "offline",
            "reason": str(payload.get("error") or "gpu inventory unavailable"),
            **marked,
        }

    data = payload.get("data") if "data" in payload else payload
    if not isinstance(data, dict):
        marked = mark_agent_gpu_inventory_offline(agent, when=now)
        return {"ok": False, "status": "offline", "reason": "invalid data", **marked}

    raw_gpus = data.get("gpus", [])
    if raw_gpus is None:
        raw_gpus = []
    if not isinstance(raw_gpus, list):
        marked = mark_agent_gpu_inventory_offline(agent, when=now)
        return {"ok": False, "status": "offline", "reason": "gpus must be a list", **marked}

    seen_device_ids: set[int] = set()
    seen_slice_device_ids: set[str] = set()

    for fallback_index, raw_gpu in enumerate(raw_gpus):
        if not isinstance(raw_gpu, dict):
            continue

        index = _as_int(_first(raw_gpu, "index", "gpuIndex"), fallback_index)
        vendor = str(_first(raw_gpu, "vendor", default="NVIDIA") or "NVIDIA")[:32]
        name = str(_first(raw_gpu, "name", "model", default="Unknown GPU") or "Unknown GPU")[:160]
        gpu_uuid = str(
            _first(raw_gpu, "uuid", "gpuUuid", "deviceUuid", "id", default="")
            or f"agent-{agent.id}-gpu-{index}"
        )[:96]
        total_memory_mb = _as_int(_first(raw_gpu, "totalMemoryMb", "total_memory_mb", "memoryMb", "memory_mb"), 0)
        mig_capable = _as_bool(_first(raw_gpu, "migCapable", "mig_capable"), False)
        mig_enabled = _as_bool(_first(raw_gpu, "migEnabled", "mig_enabled"), False)
        status = _normalize_device_status(_first(raw_gpu, "status"), GpuDevice.HardwareStatus.AVAILABLE)

        gpu, _ = GpuDevice.objects.update_or_create(
            agent=agent,
            index=index,
            defaults={
                "vendor": vendor,
                "name": name,
                "uuid": gpu_uuid,
                "pci_bus_id": str(_first(raw_gpu, "pciBusId", "pci_bus_id", default="") or "")[:64],
                "total_memory_mb": total_memory_mb,
                "driver_version": str(_first(raw_gpu, "driverVersion", "driver_version", default="") or "")[:64],
                "cuda_version": str(_first(raw_gpu, "cudaVersion", "cuda_version", default="") or "")[:64],
                "mig_capable": mig_capable,
                "mig_enabled": mig_enabled,
                "status": status,
                "last_seen_at": now,
            },
        )
        seen_device_ids.add(gpu.id)

        raw_slices = _first(raw_gpu, "slices", "gpuSlices", default=None)
        if raw_slices is None and not mig_enabled and _is_nvidia_allocatable(vendor, gpu_uuid):
            raw_slices = [{
                "kind": GpuSlice.Kind.FULL,
                "deviceId": gpu_uuid,
                "memoryMb": total_memory_mb,
            }]
        if not isinstance(raw_slices, list):
            raw_slices = []

        for raw_slice in raw_slices:
            if not isinstance(raw_slice, dict):
                continue
            device_id = str(
                _first(raw_slice, "deviceId", "device_id", "uuid", "id", default="")
                or ""
            )[:128]
            if not device_id:
                continue
            mig_profile = str(_first(raw_slice, "profile", "migProfile", "mig_profile", default="") or "")[:64]
            kind = str(_first(raw_slice, "kind", default=GpuSlice.Kind.MIG if mig_profile else GpuSlice.Kind.FULL) or "")
            if kind not in GpuSlice.Kind.values:
                kind = GpuSlice.Kind.MIG if mig_profile else GpuSlice.Kind.FULL
            memory_mb = _as_int(_first(raw_slice, "memoryMb", "memory_mb"), total_memory_mb)
            label = str(_first(raw_slice, "label", default="") or _default_slice_label(name, kind, mig_profile))[:128]
            slice_status = _normalize_slice_status(_first(raw_slice, "status"), status)

            GpuSlice.objects.update_or_create(
                device_id=device_id,
                defaults={
                    "gpu": gpu,
                    "kind": kind,
                    "label": label,
                    "mig_profile": mig_profile,
                    "memory_mb": memory_mb,
                    "allow_shared": _as_bool(_first(raw_slice, "allowShared", "allow_shared"), False),
                    "status": slice_status,
                    "last_seen_at": now,
                },
            )
            seen_slice_device_ids.add(device_id)

    stale_devices = agent.gpu_devices.exclude(id__in=seen_device_ids)
    stale_slices = GpuSlice.objects.filter(gpu__agent=agent)
    if seen_slice_device_ids:
        stale_slices = stale_slices.exclude(device_id__in=seen_slice_device_ids)

    stale_device_count = stale_devices.update(
        status=GpuDevice.HardwareStatus.OFFLINE,
        last_seen_at=now,
    )
    stale_slice_count = stale_slices.update(
        status=GpuSlice.HardwareStatus.OFFLINE,
        last_seen_at=now,
    )

    return {
        "ok": True,
        "status": "available",
        "devices": len(seen_device_ids),
        "slices": len(seen_slice_device_ids),
        "stale_devices": stale_device_count,
        "stale_slices": stale_slice_count,
    }


def _first(data: dict[str, Any], *keys: str, default=None):
    for key in keys:
        if key in data:
            return data[key]
    return default


def _as_int(value, default: int) -> int:
    if value in (None, ""):
        return default
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _as_bool(value, default: bool) -> bool:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}
    return bool(value)


def _normalize_device_status(value, default: str) -> str:
    value = str(value or default).lower()
    return value if value in GpuDevice.HardwareStatus.values else default


def _normalize_slice_status(value, default: str) -> str:
    value = str(value or default).lower()
    return value if value in GpuSlice.HardwareStatus.values else GpuSlice.HardwareStatus.AVAILABLE


def _is_nvidia_allocatable(vendor: str, gpu_uuid: str) -> bool:
    return vendor.lower() == "nvidia" or gpu_uuid.startswith("GPU-")


def _default_slice_label(gpu_name: str, kind: str, mig_profile: str) -> str:
    if kind == GpuSlice.Kind.MIG and mig_profile:
        return f"{gpu_name} {mig_profile}"
    return f"{gpu_name} full GPU"
