from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ResourceRecommendation:
    cpu_percent: int
    memory_mb: int
    workspace_gb: int
    target_users: int
    safety_margin: float
    capacity_complete: bool

    def as_dict(self) -> dict:
        return asdict(self)


def recommend_resource_limits(agent, template, target_users: int | None = None) -> ResourceRecommendation:
    """Calculate template-aware container limits from agent host capacity.

    CPU is represented as Docker quota percent where 100 means one full core.
    Memory is MB. Workspace is GB from the LVM thin pool.
    """

    users = _positive_int(target_users if target_users is not None else getattr(agent, "target_users", None), 4)
    safety_margin = _positive_float(getattr(agent, "safety_margin", None), 0.8)

    host_capacity_cpu = _non_negative_int(getattr(agent, "cpu_cores", None)) * 100
    host_capacity_ram = _non_negative_int(getattr(agent, "ram_total_mb", None))
    host_capacity_disk = _non_negative_int(getattr(agent, "lvm_pool_size_gb", None))

    cpu = _round_to_step(
        (host_capacity_cpu * safety_margin / users) * _positive_float(getattr(template, "cpu_weight", None), 1.0),
        100,
    )
    memory = _round_to_step(
        (host_capacity_ram * safety_margin / users) * _positive_float(getattr(template, "ram_weight", None), 1.0),
        1024,
    )
    workspace = _round_to_step(
        (host_capacity_disk * safety_margin / users) * _positive_float(getattr(template, "disk_weight", None), 1.0),
        10,
    )

    return ResourceRecommendation(
        cpu_percent=max(cpu, _non_negative_int(getattr(template, "min_cpu_percent", None))),
        memory_mb=max(memory, _non_negative_int(getattr(template, "min_memory_mb", None))),
        workspace_gb=max(workspace, _non_negative_int(getattr(template, "min_workspace_gb", None))),
        target_users=users,
        safety_margin=safety_margin,
        capacity_complete=bool(host_capacity_cpu and host_capacity_ram and host_capacity_disk),
    )


def min_limit_errors(
    template,
    *,
    cpu_percent: int | None = None,
    memory_mb: int | None = None,
    workspace_gb: int | None = None,
) -> dict[str, str]:
    errors: dict[str, str] = {}
    min_cpu = _non_negative_int(getattr(template, "min_cpu_percent", None))
    min_memory = _non_negative_int(getattr(template, "min_memory_mb", None))
    min_workspace = _non_negative_int(getattr(template, "min_workspace_gb", None))

    if cpu_percent is not None and int(cpu_percent) < min_cpu:
        errors["cpu_percent"] = f"Minimum CPU limit is {min_cpu} percent."
    if memory_mb is not None and int(memory_mb) < min_memory:
        errors["memory_mb"] = f"Minimum memory limit is {min_memory} MB."
    if workspace_gb is not None and int(workspace_gb) < min_workspace:
        errors["workspace_gb"] = f"Minimum workspace limit is {min_workspace} GB."
    return errors


def _round_to_step(value: float, step: int) -> int:
    if value <= 0:
        return 0
    return int(round(value / step) * step)


def _positive_int(value, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _non_negative_int(value) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)


def _positive_float(value, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default
