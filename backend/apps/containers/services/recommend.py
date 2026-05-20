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

    CPU is Docker quota percent where 100 = one full core, memory is MB,
    workspace is GB drawn from the host's XFS-quota workspace pool
    (`Agent.workspace_pool_total_gb`).
    """

    users = _positive_int(target_users if target_users is not None else getattr(agent, "target_users", None), 4)
    safety_margin = _positive_float(getattr(agent, "safety_margin", None), 0.8)

    host_capacity_cpu = _non_negative_int(getattr(agent, "cpu_cores", None)) * 100
    host_capacity_ram = _non_negative_int(getattr(agent, "ram_total_mb", None))
    host_capacity_disk = _non_negative_int(getattr(agent, "workspace_pool_total_gb", None))

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


# 메모리 max 산정 시 host RAM 에서 예약하는 헤드룸 (MB). frontend
# ResourceLimitForm 의 memoryMax 계산(`hostMemoryMb - 4096`)과 동일하게 유지.
MEMORY_HOST_RESERVE_MB = 4096


def max_limit_errors(
    template,
    agent,
    *,
    cpu_percent: int | None = None,
    memory_mb: int | None = None,
    workspace_gb: int | None = None,
) -> dict[str, str]:
    """host capacity 기반 상한 검사. min_limit_errors 와 대칭.

    CPU·메모리는 cgroup 이 항상 enforce 하므로 host 물리 용량을 상한으로 둔다.
    디스크는 agent 가 quota pool 을 보고할 때만 상한이 의미 있고, 미보고
    호스트는 검사를 건너뛴다 (enforce 불가능한 한도를 거절해봐야 무의미).
    """
    errors: dict[str, str] = {}

    cpu_cores = _non_negative_int(getattr(agent, "cpu_cores", None))
    if cpu_percent is not None and cpu_cores > 0:
        max_cpu = cpu_cores * 100
        if int(cpu_percent) > max_cpu:
            errors["cpu_percent"] = f"Maximum CPU limit is {max_cpu} percent ({cpu_cores} cores)."

    ram_total = _non_negative_int(getattr(agent, "ram_total_mb", None))
    if memory_mb is not None and ram_total > 0:
        max_memory = max(1024, ram_total - MEMORY_HOST_RESERVE_MB)
        if int(memory_mb) > max_memory:
            errors["memory_mb"] = f"Maximum memory limit is {max_memory} MB."

    pool_gb = _non_negative_int(getattr(agent, "workspace_pool_total_gb", None))
    if workspace_gb is not None and pool_gb > 0:
        if int(workspace_gb) > pool_gb:
            errors["workspace_gb"] = f"Maximum disk limit is {pool_gb} GB (host quota pool)."

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
