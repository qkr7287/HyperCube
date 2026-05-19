"""Level 2 host-burden estimation.

Produces a `BurdenSnapshot` for a single container, matching the frontend
`frontend/src/lib/mocks/host-burden.ts:BurdenSnapshot` shape so the panel can
swap from the mock fetcher to this endpoint with no UI changes.

Estimation model
----------------
* GPU power / temp: direct (`nvidia-smi power.draw / temperature.gpu`).
* CPU power: RAPL package (`/sys/class/powercap/intel-rapl`) — direct when
  agent reports it, otherwise Fan model fallback:
        P_cpu = P_idle + (P_max - P_idle) * (cpu_usage / 100)
  (Fan et al., "Power Provisioning for a Warehouse-sized Computer", ISCA 2007)
* CPU temp: direct (`/sys/class/thermal/thermal_zone*/temp`); else null.
* Container share: this container's CPU% / host CPU% applied to CPU dynamic
  power, and GPU usage ratio applied to GPU power. Level 2 — see
  HostBurdenPanel disclaimer. Container temp delta = (host - idle) * GPU usage
  ratio (rough but useful proxy).

Per-host parameters
-------------------
``P_idle`` and ``P_max`` are read from the latest known values; if RAPL is
present, idle is taken as the lowest observed cpu_power_w over the last 2h,
max as the highest. When neither is available we fall back to a 35W/125W
constant (i5-10400 class) so the chart still has a usable scale. Same idea
for GPU — TDP defaults to 200W (3060 Ti class) until first real reading.

Sparkline returns last 32 host samples (CPU+GPU+idle when total).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.containers.models import Container
from apps.metrics.models import ContainerMetricsHistory, SystemMetricsHistory


SPARK_LEN = 32
HISTORY_WINDOW = timedelta(hours=2)
CALIBRATION_WINDOW = timedelta(days=1)

# Fallback when host has never reported real numbers (RAPL/IPMI 미지원 환경).
# 운영자 시야에 0/null 빈 차트만 보이는 것보단 "추정 max 기준" 으로 그리는 게 낫다.
DEFAULT_CPU_TDP_W = 125.0
DEFAULT_CPU_IDLE_W = 35.0
DEFAULT_GPU_TDP_W = 200.0
DEFAULT_IDLE_BASELINE_C = 38.0  # GPU idle 평형 온도 (RTX 30 series class)


def _round(x: float | None, n: int = 1) -> float | None:
    return None if x is None else round(float(x), n)


@dataclass
class _HostStats:
    """Per-agent calibration cached at call time (cheap to recompute)."""
    cpu_idle_w: float
    cpu_tdp_w: float
    gpu_tdp_w: float
    gpu_idle_c: float


def _calibrate_host(agent_id) -> _HostStats:
    """Pick min/max observed power over the last day for Fan-model bounds.

    Falls back to module-level defaults when the host has never sent RAPL or
    nvidia-smi power. Read-only — calling this on every request is fine since
    the underlying scan covers a tiny BRIN-indexed window.
    """
    since = timezone.now() - CALIBRATION_WINDOW
    qs = SystemMetricsHistory.objects.filter(
        agent_id=agent_id,
        recorded_at__gte=since,
    )

    cpu_powers = list(qs.exclude(cpu_power_w__isnull=True).values_list("cpu_power_w", flat=True))
    gpu_powers = list(qs.exclude(gpu_power_w__isnull=True).values_list("gpu_power_w", flat=True))
    gpu_temps = list(qs.exclude(gpu_temperature_max__isnull=True).values_list("gpu_temperature_max", flat=True))

    # observed max 가 default TDP 보다 작으면 default 채택. idle-만 한 호스트가
    # 게이지 max=현재값 으로 잡혀 needle 이 항상 끝에 닿는 걸 방지.
    return _HostStats(
        cpu_idle_w=min(cpu_powers) if cpu_powers else DEFAULT_CPU_IDLE_W,
        cpu_tdp_w=max(max(cpu_powers), DEFAULT_CPU_TDP_W) if cpu_powers else DEFAULT_CPU_TDP_W,
        gpu_tdp_w=max(max(gpu_powers), DEFAULT_GPU_TDP_W) if gpu_powers else DEFAULT_GPU_TDP_W,
        gpu_idle_c=min(gpu_temps) if gpu_temps else DEFAULT_IDLE_BASELINE_C,
    )


def _estimate_cpu_power(sample: SystemMetricsHistory, host: _HostStats) -> float:
    """Direct (RAPL) when available, otherwise Fan-model fallback from CPU%.

    Returning a number rather than null because the chart needs a host value to
    draw the gauge — the disclaimer pill already communicates the estimation.
    """
    if sample.cpu_power_w is not None:
        return float(sample.cpu_power_w)
    util = max(0.0, min(100.0, float(sample.cpu_usage or 0))) / 100.0
    return host.cpu_idle_w + (host.cpu_tdp_w - host.cpu_idle_w) * util


def _latest_container_metric(container: Container) -> ContainerMetricsHistory | None:
    """Most recent ContainerMetricsHistory row for this container, or None."""
    cid = container.container_id
    return (
        ContainerMetricsHistory.objects
        .filter(agent_id=container.agent_id, container_id__in=[cid, cid[:12]])
        .order_by("-recorded_at")
        .first()
    )


def _other_containers_w(
    agent_id,
    own_container_id: str,
    host_cpu_dynamic_w: float,
    host_cpu_usage_pct: float,
    host_gpu_power_w: float,
    host_gpu_usage_pct: float,
    since,
) -> float:
    """Sum estimated W for other containers on the same agent.

    Same proportionality model as the focal container; intended to make the
    breakdown bar add up sensibly without per-container precision.
    """
    rows = (
        ContainerMetricsHistory.objects
        .filter(agent_id=agent_id, recorded_at__gte=since)
        .exclude(container_id__in=[own_container_id, own_container_id[:12]])
        .order_by("container_id", "-recorded_at")
        .distinct("container_id")
        .values("container_id", "cpu_usage", "gpu_usage")
    )
    total = 0.0
    cpu_denom = max(host_cpu_usage_pct, 1.0)
    gpu_denom = max(host_gpu_usage_pct, 1.0)
    for row in rows:
        c_cpu = float(row.get("cpu_usage") or 0)
        c_gpu = float(row.get("gpu_usage") or 0)
        total += host_cpu_dynamic_w * (c_cpu / cpu_denom)
        total += host_gpu_power_w * (c_gpu / gpu_denom)
    return total


def _zones(host_max: float, *, ok=0.7, warn=0.85, danger=0.95) -> dict[str, float]:
    return {"ok": host_max * ok, "warn": host_max * warn, "danger": host_max * danger}


def _spark(values: list[float], length: int = SPARK_LEN) -> list[float]:
    if not values:
        return []
    if len(values) >= length:
        return values[-length:]
    return values


def build_burden_snapshot(container: Container) -> dict[str, Any]:
    """Compose the BurdenSnapshot dict the HostBurdenPanel expects.

    Container-share semantics deliberately match the mock: 0-1 ratio that the
    panel multiplies for display. UI tolerates missing pieces (e.g. CPU temp
    null) and the disclaimer pill already explains the Level 1/2 model.
    """
    agent_id = container.agent_id
    host = _calibrate_host(agent_id)

    since = timezone.now() - HISTORY_WINDOW
    history = list(
        SystemMetricsHistory.objects
        .filter(agent_id=agent_id, recorded_at__gte=since)
        .order_by("recorded_at")
        .values(
            "recorded_at", "cpu_usage", "cpu_power_w", "cpu_temp_c",
            "gpu_usage", "gpu_power_w", "gpu_temperature_max",
        )
    )
    if not history:
        # Agent 가 system_metrics 를 한 번도 안 보낸 경우 — chart 가 모두 null 인 채로
        # 그려질 수밖에 없으니 빈 snapshot 으로 응답 (frontend 가 ok/empty 처리).
        return _empty_snapshot(host)

    latest = SystemMetricsHistory.objects.filter(agent_id=agent_id).order_by("-recorded_at").first()
    assert latest is not None  # history 가 비어있지 않으므로

    # Estimate / direct power readings for the host
    cpu_power_now = _estimate_cpu_power(latest, host)
    cpu_dynamic = max(0.0, cpu_power_now - host.cpu_idle_w)
    gpu_power_now = float(latest.gpu_power_w) if latest.gpu_power_w is not None else 0.0
    gpu_temp_now = float(latest.gpu_temperature_max) if latest.gpu_temperature_max is not None else host.gpu_idle_c

    # Container share calculation
    container_metric = _latest_container_metric(container)
    container_cpu_pct = float(container_metric.cpu_usage or 0) if container_metric else 0.0
    container_gpu_pct = float(container_metric.gpu_usage or 0) if container_metric else 0.0
    host_cpu_pct = float(latest.cpu_usage or 0)
    host_gpu_pct = float(latest.gpu_usage or 0)

    cpu_share_ratio = (container_cpu_pct / host_cpu_pct) if host_cpu_pct > 0 else 0.0
    gpu_share_ratio = (container_gpu_pct / host_gpu_pct) if host_gpu_pct > 0 else 0.0
    cpu_share_ratio = max(0.0, min(1.0, cpu_share_ratio))
    gpu_share_ratio = max(0.0, min(1.0, gpu_share_ratio))

    container_cpu_w = cpu_dynamic * cpu_share_ratio
    container_gpu_w = gpu_power_now * gpu_share_ratio
    container_total_w = container_cpu_w + container_gpu_w

    # Host total power for the "total" tab
    host_total_w = cpu_power_now + gpu_power_now + 0.0  # idle 은 cpu_power_now 에 이미 포함
    total_max = host.cpu_tdp_w + host.gpu_tdp_w
    this_container_pct = (container_total_w / host_total_w) if host_total_w > 0 else 0.0

    # Breakdown — idle 은 RAPL idle 추정 (cpu_idle_w), 나머지는 dynamic 으로 분배
    idle_w = host.cpu_idle_w
    other_w = _other_containers_w(
        agent_id=agent_id,
        own_container_id=container.container_id,
        host_cpu_dynamic_w=cpu_dynamic,
        host_cpu_usage_pct=host_cpu_pct,
        host_gpu_power_w=gpu_power_now,
        host_gpu_usage_pct=host_gpu_pct,
        since=since,
    )
    headroom_w = max(0.0, total_max - host_total_w)

    # Temp delta — host 가 idle 평형 위로 끌어올린 만큼 중 컨테이너 GPU usage 비율
    temp_container_delta = max(0.0, gpu_temp_now - host.gpu_idle_c) * gpu_share_ratio

    # Sparklines
    gpu_temp_spark = _spark([
        float(r["gpu_temperature_max"]) for r in history if r["gpu_temperature_max"] is not None
    ])
    gpu_power_spark = _spark([float(r["gpu_power_w"]) for r in history if r["gpu_power_w"] is not None])
    cpu_power_spark = _spark([
        _estimate_cpu_power(
            SystemMetricsHistory(cpu_usage=r["cpu_usage"], cpu_power_w=r["cpu_power_w"]),
            host,
        )
        for r in history
    ])
    total_power_spark = _spark([
        _estimate_cpu_power(
            SystemMetricsHistory(cpu_usage=r["cpu_usage"], cpu_power_w=r["cpu_power_w"]),
            host,
        ) + float(r["gpu_power_w"] or 0)
        for r in history
    ])

    return {
        "updatedAt": int(latest.recorded_at.timestamp() * 1000),
        "gpuTemp": {
            "hostValue": _round(gpu_temp_now),
            "hostMax": 90,
            "containerShare": _round(gpu_share_ratio, 3),
            "zones": {"ok": 70, "warn": 80, "danger": 85},
            "sparkline": [_round(v) for v in gpu_temp_spark],
        },
        "gpuPower": {
            "hostValue": _round(gpu_power_now),
            "hostMax": _round(host.gpu_tdp_w),
            "containerShare": _round(gpu_share_ratio, 3),
            "zones": _zones(host.gpu_tdp_w, ok=0.6, warn=0.8, danger=0.93),
            "sparkline": [_round(v) for v in gpu_power_spark],
        },
        "cpuPower": {
            "hostValue": _round(cpu_power_now),
            "hostMax": _round(host.cpu_tdp_w),
            "containerShare": _round(cpu_share_ratio, 3),
            "zones": _zones(host.cpu_tdp_w, ok=0.55, warn=0.75, danger=0.92),
            "sparkline": [_round(v) for v in cpu_power_spark],
        },
        "totalPower": {
            "hostValue": _round(host_total_w),
            "hostMax": _round(total_max),
            "containerShare": _round(this_container_pct, 3),
            "thisContainerPct": _round(this_container_pct, 3),
            "zones": _zones(total_max, ok=0.55, warn=0.75, danger=0.9),
            "sparkline": [_round(v) for v in total_power_spark],
            "breakdown": {
                "thisContainerW": _round(container_total_w),
                "otherContainersW": _round(other_w),
                "idleW": _round(idle_w),
                "headroomW": _round(headroom_w),
            },
        },
        "maxTemp": {
            "hostValue": _round(gpu_temp_now),
            "hostMax": 90,
            "containerShare": _round(gpu_share_ratio, 3),
            "zones": {"ok": 70, "warn": 80, "danger": 85},
            "sparkline": [_round(v) for v in gpu_temp_spark],
            "hotspot": "GPU",
            "idleBaselineC": _round(host.gpu_idle_c),
            "containerDeltaC": _round(temp_container_delta),
        },
    }


def _empty_snapshot(host: _HostStats) -> dict[str, Any]:
    """Returned when no SystemMetricsHistory is available yet.

    Keeps the shape exact so the frontend doesn't need a separate branch — every
    sparkline is an empty list and hostValue is 0, which the gauge renders as a
    needle at min position.
    """
    total_max = host.cpu_tdp_w + host.gpu_tdp_w
    base = lambda host_max, zones: {
        "hostValue": 0,
        "hostMax": _round(host_max),
        "containerShare": 0,
        "zones": zones,
        "sparkline": [],
    }
    return {
        "updatedAt": int(timezone.now().timestamp() * 1000),
        "gpuTemp": {**base(90, {"ok": 70, "warn": 80, "danger": 85})},
        "gpuPower": {**base(host.gpu_tdp_w, _zones(host.gpu_tdp_w, ok=0.6, warn=0.8, danger=0.93))},
        "cpuPower": {**base(host.cpu_tdp_w, _zones(host.cpu_tdp_w, ok=0.55, warn=0.75, danger=0.92))},
        "totalPower": {
            **base(total_max, _zones(total_max, ok=0.55, warn=0.75, danger=0.9)),
            "thisContainerPct": 0,
            "breakdown": {
                "thisContainerW": 0,
                "otherContainersW": 0,
                "idleW": _round(host.cpu_idle_w),
                "headroomW": _round(total_max),
            },
        },
        "maxTemp": {
            **base(90, {"ok": 70, "warn": 80, "danger": 85}),
            "hotspot": "GPU",
            "idleBaselineC": _round(host.gpu_idle_c),
            "containerDeltaC": 0,
        },
    }
