"""Celery periodic tasks for metrics persistence and cleanup."""

import json
import logging
from datetime import datetime, timedelta

from celery import shared_task
from django.conf import settings
from django.db import connection
from django.db.models import Avg, Count, IntegerField, Max
from django.db.models.expressions import RawSQL
from django.utils import timezone

logger = logging.getLogger(__name__)


# ── 자원 이벤트 판정 상수 (frontend fleet-events.ts 와 일치) ──────────────
# (warn, crit) 임계 — classifyHealth / detectFleetEvents 와 동일 기준.
RESOURCE_THRESHOLDS = {
    "cpu": (70.0, 90.0),
    "memory": (75.0, 90.0),
    "gpu": (80.0, 95.0),
}
# disk 는 변동이 느려 임계 초과가 한 번 뜨면 라이프사이클상 계속 active 로
# 남는다 — 순간적 자원 "이벤트"로는 부적합해 판정 대상에서 제외한다.
RESOURCE_METRICS = ("cpu", "memory", "gpu")
SPIKE_DELTA = 25.0       # 직전 평균 대비 %p 이상 급등
SPIKE_FLOOR = 55.0       # spike 로 인정할 현재값 하한 (idle 출렁임 제외)
SPARKLINE_MINUTES = 10   # spike 판정용 1분 bucket 윈도우


@shared_task(name="apps.metrics.tasks.flush_metrics_to_db")
def flush_metrics_to_db():
    """Redis에 캐시된 최신 메트릭을 PostgreSQL에 bulk insert.

    Celery Beat이 5초마다 실행한다 (config/settings/base.py에서 설정).
    server:active_ids SET을 읽어 활성 Agent 목록을 얻고, 각 Agent의 최신
    system / container metrics를 한 번에 Insert한다. Agent가 끊어진 경우
    TTL로 자연스럽게 정리된다.
    """
    from apps.agents.models import Agent
    from apps.common.redis_client import get_redis_client
    from apps.metrics.models import ContainerMetricsHistory, SystemMetricsHistory

    r = get_redis_client()
    active_ids = list(r.smembers("server:active_ids"))

    if not active_ids:
        return "no active servers"

    # 한 번에 Agent 조회 (N+1 방지)
    agents_by_id = {str(a.id): a for a in Agent.objects.filter(id__in=active_ids)}

    system_records: list[SystemMetricsHistory] = []
    container_records: list[ContainerMetricsHistory] = []

    for server_id in active_ids:
        agent = agents_by_id.get(server_id)
        if not agent:
            logger.warning("Agent %s not found while flushing metrics", server_id)
            continue

        system_records.extend(_collect_system_metrics(r, agent))
        container_records.extend(_collect_container_metrics(r, agent))

    if system_records:
        SystemMetricsHistory.objects.bulk_create(system_records)
    if container_records:
        ContainerMetricsHistory.objects.bulk_create(container_records)

    summary = (
        f"flushed {len(system_records)} system + {len(container_records)} container records"
    )
    logger.info(summary)
    return summary


@shared_task(name="apps.metrics.tasks.cleanup_old_metrics")
def cleanup_old_metrics():
    """METRICS_RETENTION_DAYS 이전 데이터를 삭제. 매일 03:00 실행."""
    from apps.metrics.models import ContainerMetricsHistory, SystemMetricsHistory

    retention_days = getattr(settings, "METRICS_RETENTION_DAYS", 7)
    cutoff = timezone.now() - timedelta(days=retention_days)

    sys_count, _ = SystemMetricsHistory.objects.filter(recorded_at__lt=cutoff).delete()
    ctr_count, _ = ContainerMetricsHistory.objects.filter(recorded_at__lt=cutoff).delete()

    summary = (
        f"deleted {sys_count} system + {ctr_count} container records older than {cutoff}"
    )
    logger.info(summary)
    return summary


# ----------------------------------------------------------------------
# Rollup precomputation — server-2d 의 1h/24h/7d range 차트가 매 호출
# 28일 ×10M+ rows GROUP BY 를 안 하게끔 *_rollup 테이블에 누적 저장.
# Celery beat 가 (3600, lookback=3) / (86400, lookback=3) 두 번 호출.
# ----------------------------------------------------------------------


@shared_task(name="apps.metrics.tasks.compute_metrics_rollups")
def compute_metrics_rollups(bucket_seconds: int, lookback_buckets: int = 3):
    """직전 lookback_buckets 개 bucket 을 raw 에서 다시 계산해서 rollup 테이블에 upsert.

    - 진행 중 bucket 은 매번 새로 갱신
    - 직전 1~2개 bucket 도 다시 (지연 도착 / 재시작 보정)
    - lookback_buckets 를 크게 주면 backfill 용으로도 사용 가능
    """
    from apps.metrics.models import (
        ContainerMetricsHistory,
        ContainerMetricsRollup,
        StackMetricsRollup,
        SystemMetricsHistory,
        SystemMetricsRollup,
    )

    if bucket_seconds <= 0:
        return "noop: bucket_seconds must be positive"

    since = timezone.now() - timedelta(seconds=bucket_seconds * lookback_buckets)
    bucket_expr = RawSQL(
        "(floor(extract(epoch from recorded_at) / %s) * %s)::bigint",
        (bucket_seconds, bucket_seconds),
        output_field=IntegerField(),
    )

    sys_n = _rebuild_system_rollups(bucket_seconds, since, bucket_expr, SystemMetricsHistory, SystemMetricsRollup)
    con_n, stk_n = _rebuild_container_and_stack_rollups(
        bucket_seconds, since, bucket_expr, ContainerMetricsHistory, ContainerMetricsRollup, StackMetricsRollup,
    )
    summary = f"rollup bucket={bucket_seconds}s: system={sys_n}, container={con_n}, stack={stk_n}"
    logger.info(summary)
    return summary


def _bucket_epoch_to_dt(epoch_sec: int):
    from datetime import timezone as dt_timezone
    return datetime.fromtimestamp(int(epoch_sec), tz=dt_timezone.utc)


def _rebuild_system_rollups(bucket_seconds, since, bucket_expr, History, Rollup):
    sys_db_cols = _system_db_columns()
    annotations = dict(
        cpu_avg=Avg("cpu_usage"),
        cpu_max=Max("cpu_usage"),
        memory_usage_avg=Avg("memory_usage"),
        memory_usage_max=Max("memory_usage"),
        disk_usage_avg=Avg("disk_usage"),
        disk_usage_max=Max("disk_usage"),
        network_rx_max=Max("network_rx"),
        network_tx_max=Max("network_tx"),
        sample_count=Count("id"),
    )
    if "gpu_usage" in sys_db_cols:
        annotations.update(
            gpu_usage_avg=Avg("gpu_usage"),
            gpu_usage_max=Max("gpu_usage"),
            gpu_memory_used_avg=Avg("gpu_memory_used"),
            gpu_memory_used_max=Max("gpu_memory_used"),
            gpu_memory_total_avg=Avg("gpu_memory_total"),
        )
    if "cpu_power_w" in sys_db_cols:
        annotations.update(cpu_power_w_avg=Avg("cpu_power_w"))
    if "cpu_temp_c" in sys_db_cols:
        annotations.update(cpu_temp_c_max=Max("cpu_temp_c"))

    rows = list(
        History.objects.filter(recorded_at__gte=since)
        .order_by()  # 모델 Meta.ordering 이 GROUP BY 에 끼어들어 duplicate 만드는 것 방지
        .annotate(bucket_epoch=bucket_expr)
        .values("agent_id", "bucket_epoch")
        .annotate(**annotations)
    )
    if not rows:
        return 0
    instances = [
        Rollup(
            agent_id=r["agent_id"],
            bucket_seconds=bucket_seconds,
            bucket_start=_bucket_epoch_to_dt(r["bucket_epoch"]),
            cpu_avg=r.get("cpu_avg"),
            cpu_max=r.get("cpu_max"),
            memory_usage_avg=r.get("memory_usage_avg"),
            memory_usage_max=r.get("memory_usage_max"),
            disk_usage_avg=r.get("disk_usage_avg"),
            disk_usage_max=r.get("disk_usage_max"),
            network_rx_max=r.get("network_rx_max"),
            network_tx_max=r.get("network_tx_max"),
            gpu_usage_avg=r.get("gpu_usage_avg"),
            gpu_usage_max=r.get("gpu_usage_max"),
            gpu_memory_used_avg=int(r["gpu_memory_used_avg"]) if r.get("gpu_memory_used_avg") is not None else None,
            gpu_memory_used_max=r.get("gpu_memory_used_max"),
            gpu_memory_total_avg=int(r["gpu_memory_total_avg"]) if r.get("gpu_memory_total_avg") is not None else None,
            cpu_power_w_avg=r.get("cpu_power_w_avg"),
            cpu_temp_c_max=r.get("cpu_temp_c_max"),
            sample_count=int(r.get("sample_count") or 0),
        )
        for r in rows
    ]
    Rollup.objects.bulk_create(
        instances,
        update_conflicts=True,
        unique_fields=["agent", "bucket_seconds", "bucket_start"],
        update_fields=[
            "cpu_avg", "cpu_max", "memory_usage_avg", "memory_usage_max",
            "disk_usage_avg", "disk_usage_max", "network_rx_max", "network_tx_max",
            "gpu_usage_avg", "gpu_usage_max", "gpu_memory_used_avg",
            "gpu_memory_used_max", "gpu_memory_total_avg",
            "cpu_power_w_avg", "cpu_temp_c_max", "sample_count", "updated_at",
        ],
    )
    return len(instances)


def _rebuild_container_and_stack_rollups(
    bucket_seconds, since, bucket_expr, History, ContainerRollup, StackRollup
):
    con_cols = _container_db_columns(History._meta.db_table)
    has_gpu = "gpu_usage" in con_cols
    has_raw = {"cpu_usage_raw", "cpu_cores_quota"}.issubset(con_cols)
    has_stack = "stack" in con_cols

    # Container rollup
    con_aggs = dict(
        cpu_usage_pct_avg=Avg("cpu_usage"),
        cpu_usage_pct_max=Max("cpu_usage"),
        memory_avg=Avg("memory_usage"),
        memory_max=Max("memory_usage"),
        memory_percent_avg=Avg("memory_percent"),
        network_rx_max=Max("network_rx"),
        network_tx_max=Max("network_tx"),
        disk_read_max=Max("disk_read"),
        disk_write_max=Max("disk_write"),
        sample_count=Count("id"),
    )
    if has_raw:
        con_aggs.update(
            cpu_usage_raw_avg=Avg("cpu_usage_raw"),
            cpu_usage_raw_max=Max("cpu_usage_raw"),
            cpu_cores_quota_avg=Avg("cpu_cores_quota"),
        )
    if has_gpu:
        con_aggs.update(
            gpu_usage_avg=Avg("gpu_usage"),
            gpu_usage_max=Max("gpu_usage"),
            gpu_memory_used_avg=Avg("gpu_memory_used"),
            gpu_memory_used_max=Max("gpu_memory_used"),
            gpu_memory_total_avg=Avg("gpu_memory_total"),
        )

    # stack 은 GROUP BY 키에서 빼고 Max() 로 가져옴 — 같은 (agent, container, bucket)
    # 안에 라벨 변경이 일어나도 unique 제약 위반 안 함. (드물지만 발생)
    con_values = ["agent_id", "container_id", "bucket_epoch"]
    if has_stack:
        con_aggs["stack_last"] = Max("stack")
    con_rows = list(
        History.objects.filter(recorded_at__gte=since)
        .order_by()
        .annotate(bucket_epoch=bucket_expr)
        .values(*con_values)
        .annotate(**con_aggs)
    )
    con_instances = [
        ContainerRollup(
            agent_id=r["agent_id"],
            container_id=r["container_id"],
            stack=r.get("stack_last") or "Unmanaged",
            bucket_seconds=bucket_seconds,
            bucket_start=_bucket_epoch_to_dt(r["bucket_epoch"]),
            cpu_usage_pct_avg=r.get("cpu_usage_pct_avg"),
            cpu_usage_pct_max=r.get("cpu_usage_pct_max"),
            cpu_usage_raw_avg=r.get("cpu_usage_raw_avg"),
            cpu_usage_raw_max=r.get("cpu_usage_raw_max"),
            cpu_cores_quota_avg=r.get("cpu_cores_quota_avg"),
            memory_avg=r.get("memory_avg"),
            memory_max=r.get("memory_max"),
            memory_percent_avg=r.get("memory_percent_avg"),
            network_rx_max=r.get("network_rx_max"),
            network_tx_max=r.get("network_tx_max"),
            disk_read_max=r.get("disk_read_max"),
            disk_write_max=r.get("disk_write_max"),
            gpu_usage_avg=r.get("gpu_usage_avg"),
            gpu_usage_max=r.get("gpu_usage_max"),
            gpu_memory_used_avg=int(r["gpu_memory_used_avg"]) if r.get("gpu_memory_used_avg") is not None else None,
            gpu_memory_used_max=r.get("gpu_memory_used_max"),
            gpu_memory_total_avg=int(r["gpu_memory_total_avg"]) if r.get("gpu_memory_total_avg") is not None else None,
            sample_count=int(r.get("sample_count") or 0),
        )
        for r in con_rows
    ]
    if con_instances:
        ContainerRollup.objects.bulk_create(
            con_instances,
            update_conflicts=True,
            unique_fields=["agent", "container_id", "bucket_seconds", "bucket_start"],
            update_fields=[
                "stack", "cpu_usage_pct_avg", "cpu_usage_pct_max",
                "cpu_usage_raw_avg", "cpu_usage_raw_max", "cpu_cores_quota_avg",
                "memory_avg", "memory_max", "memory_percent_avg",
                "network_rx_max", "network_tx_max", "disk_read_max", "disk_write_max",
                "gpu_usage_avg", "gpu_usage_max", "gpu_memory_used_avg",
                "gpu_memory_used_max", "gpu_memory_total_avg",
                "sample_count", "updated_at",
            ],
        )

    # Stack rollup — denormalized stack 컬럼이 없으면 skip (구버전 schema).
    stk_count = 0
    if has_stack:
        stk_aggs = dict(
            cpu_avg=Avg("cpu_usage"),
            cpu_max=Max("cpu_usage"),
            memory_percent_avg=Avg("memory_percent"),
            memory_percent_max=Max("memory_percent"),
            memory_bytes_avg=Avg("memory_usage"),
            network_rx_max=Max("network_rx"),
            network_tx_max=Max("network_tx"),
            disk_read_max=Max("disk_read"),
            disk_write_max=Max("disk_write"),
            container_count=Count("container_id", distinct=True),
            sample_count=Count("id"),
        )
        if has_gpu:
            stk_aggs.update(
                gpu_usage_avg=Avg("gpu_usage"),
                gpu_usage_max=Max("gpu_usage"),
                gpu_memory_used_avg=Avg("gpu_memory_used"),
                gpu_memory_used_max=Max("gpu_memory_used"),
                gpu_memory_total_avg=Avg("gpu_memory_total"),
            )
        stk_rows = list(
            History.objects.filter(recorded_at__gte=since)
            .order_by()
            .annotate(bucket_epoch=bucket_expr)
            .values("agent_id", "stack", "bucket_epoch")
            .annotate(**stk_aggs)
        )
        stk_instances = [
            StackRollup(
                agent_id=r["agent_id"],
                stack=r["stack"],
                bucket_seconds=bucket_seconds,
                bucket_start=_bucket_epoch_to_dt(r["bucket_epoch"]),
                cpu_avg=r.get("cpu_avg"),
                cpu_max=r.get("cpu_max"),
                memory_percent_avg=r.get("memory_percent_avg"),
                memory_percent_max=r.get("memory_percent_max"),
                memory_bytes_avg=int(r["memory_bytes_avg"]) if r.get("memory_bytes_avg") is not None else None,
                network_rx_max=r.get("network_rx_max"),
                network_tx_max=r.get("network_tx_max"),
                disk_read_max=r.get("disk_read_max"),
                disk_write_max=r.get("disk_write_max"),
                gpu_usage_avg=r.get("gpu_usage_avg"),
                gpu_usage_max=r.get("gpu_usage_max"),
                gpu_memory_used_avg=int(r["gpu_memory_used_avg"]) if r.get("gpu_memory_used_avg") is not None else None,
                gpu_memory_used_max=r.get("gpu_memory_used_max"),
                gpu_memory_total_avg=int(r["gpu_memory_total_avg"]) if r.get("gpu_memory_total_avg") is not None else None,
                container_count=int(r.get("container_count") or 0),
                sample_count=int(r.get("sample_count") or 0),
            )
            for r in stk_rows
        ]
        if stk_instances:
            StackRollup.objects.bulk_create(
                stk_instances,
                update_conflicts=True,
                unique_fields=["agent", "stack", "bucket_seconds", "bucket_start"],
                update_fields=[
                    "cpu_avg", "cpu_max", "memory_percent_avg", "memory_percent_max",
                    "memory_bytes_avg", "network_rx_max", "network_tx_max",
                    "disk_read_max", "disk_write_max",
                    "gpu_usage_avg", "gpu_usage_max", "gpu_memory_used_avg",
                    "gpu_memory_used_max", "gpu_memory_total_avg",
                    "container_count", "sample_count", "updated_at",
                ],
            )
        stk_count = len(stk_instances)

    return len(con_instances), stk_count


_CONTAINER_DB_COLUMNS_CACHE: dict[str, set[str]] = {}


def _container_db_columns(table_name: str) -> set[str]:
    cached = _CONTAINER_DB_COLUMNS_CACHE.get(table_name)
    if cached is not None:
        return cached
    try:
        with connection.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
                [table_name],
            )
            cols = {row[0] for row in cur.fetchall()}
    except Exception:
        cols = set()
    _CONTAINER_DB_COLUMNS_CACHE[table_name] = cols
    return cols


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _collect_system_metrics(r, agent):
    """server:{id}:system 키를 읽어 SystemMetricsHistory 인스턴스 생성."""
    from apps.metrics.models import SystemMetricsHistory

    raw = r.get(f"server:{agent.id}:system")
    if not raw:
        return []

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Invalid JSON in server:%s:system", agent.id)
        return []

    body = payload.get("data", {}) or {}
    cpu = body.get("cpu") or {}
    memory = body.get("memory") or {}
    disk = body.get("disk") or {}
    network = body.get("network") or {}
    gpus = body.get("gpu") or []  # Agent payload contract: array of GPU dicts. 없으면 [].

    kwargs = dict(
        agent=agent,
        cpu_usage=_as_float(cpu.get("usage")),
        memory_usage=_as_float(memory.get("usage")),
        memory_used=_as_int(memory.get("used")),
        memory_total=_as_int(memory.get("total")),
        disk_usage=_as_float(disk.get("usage")),
        network_rx=_as_int(network.get("rx")),
        network_tx=_as_int(network.get("tx")),
        raw_data=body,
        recorded_at=_parse_timestamp(payload.get("timestamp")),
    )

    # 신규 nullable 컬럼 — migration 0005 적용된 환경에서만 채움. 구버전 Agent /
    # 미적용 환경에선 그대로 raw_data 에만 보존.
    db_cols = _system_db_columns()
    if "memory_available" in db_cols:
        # Agent 가 안 보내면 None. Linux 에서 정확한 사용률 계산용 (MemAvailable).
        avail = memory.get("available")
        kwargs["memory_available"] = _as_int(avail) if avail is not None else None

    # Level 2 호스트 부담 추정: CPU package 전력/온도 (RAPL + thermal_zone).
    # Agent 가 안 보내면 (구버전 / RAPL 미지원 호스트) null.
    if "cpu_power_w" in db_cols:
        cpu_w = cpu.get("packagePowerW")
        kwargs["cpu_power_w"] = _as_float(cpu_w) if cpu_w is not None else None
    if "cpu_temp_c" in db_cols:
        cpu_t = cpu.get("tempC")
        kwargs["cpu_temp_c"] = _as_float(cpu_t) if cpu_t is not None else None

    if gpus and isinstance(gpus, list):
        # 다중 GPU 호스트도 단일 컬럼으로 aggregation 가능하게 평균·합산·최대값 정규화.
        usage_vals = [_as_float(g.get("usage")) for g in gpus if g.get("usage") is not None]
        mem_used_vals = [_as_int(g.get("memoryUsed")) for g in gpus if g.get("memoryUsed") is not None]
        mem_total_vals = [_as_int(g.get("memoryTotal")) for g in gpus if g.get("memoryTotal") is not None]
        # 온도: 새 키 temperatureC 우선, 구 key temperature fallback.
        temp_vals = [
            _as_float(g.get("temperatureC") if g.get("temperatureC") is not None else g.get("temperature"))
            for g in gpus
            if (g.get("temperatureC") is not None or g.get("temperature") is not None)
        ]
        # 전력: 신규 key powerDrawW. 안 보내는 GPU 만 skip 하고 나머지 합산.
        power_vals = [_as_float(g.get("powerDrawW")) for g in gpus if g.get("powerDrawW") is not None]
        if "gpu_count" in db_cols:
            kwargs["gpu_count"] = len(gpus)
        if "gpu_usage" in db_cols and usage_vals:
            kwargs["gpu_usage"] = sum(usage_vals) / len(usage_vals)
        if "gpu_memory_used" in db_cols and mem_used_vals:
            kwargs["gpu_memory_used"] = sum(mem_used_vals)
        if "gpu_memory_total" in db_cols and mem_total_vals:
            kwargs["gpu_memory_total"] = sum(mem_total_vals)
        if "gpu_temperature_max" in db_cols and temp_vals:
            kwargs["gpu_temperature_max"] = max(temp_vals)
        if "gpu_power_w" in db_cols and power_vals:
            kwargs["gpu_power_w"] = sum(power_vals)
    else:
        # 호스트에 GPU 없음. count=0 만 채워서 "GPU 보고는 했고 0대" 표시.
        if "gpu_count" in db_cols:
            kwargs["gpu_count"] = 0

    return [SystemMetricsHistory(**kwargs)]


_SYSTEM_DB_COLUMNS_CACHE: set[str] | None = None


def _system_db_columns() -> set[str]:
    """system_metrics_history 의 실제 컬럼. tasks.py 안에서 캐시."""
    global _SYSTEM_DB_COLUMNS_CACHE
    if _SYSTEM_DB_COLUMNS_CACHE is not None:
        return _SYSTEM_DB_COLUMNS_CACHE
    from django.db import connection
    try:
        with connection.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
                ["system_metrics_history"],
            )
            cols = {row[0] for row in cur.fetchall()}
    except Exception:
        cols = set()
    _SYSTEM_DB_COLUMNS_CACHE = cols
    return cols


def _load_stack_lookup(r, agent_id):
    """Build {container_id_or_short: stack} map from the cached containers list.

    Avoids per-row Redis lookups (one fetch per flush vs N) and keeps stack
    resolution co-located with the `resolveGroup` chain used by the frontend.
    Returns empty dict if cache is missing/expired — callers fall back to
    'Unmanaged' which matches frontend behaviour for unlabelled containers.
    """
    from apps.metrics.utils import resolve_stack

    raw = r.get(f"server:{agent_id}:containers")
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}

    out: dict[str, str] = {}
    containers = (payload.get("data") or {}).get("containers") or []
    for c in containers:
        cid = c.get("id") or ""
        if not cid:
            continue
        labels = c.get("labels") or {}
        stack = resolve_stack(labels)
        out[cid] = stack
        # Also key by 12-char short form because metrics payloads commonly use it.
        out[cid[:12]] = stack
    return out


def _collect_container_metrics(r, agent):
    """server:{id}:container:*:metrics 패턴의 모든 키를 스캔해서 인스턴스 생성."""
    from apps.metrics.models import ContainerMetricsHistory

    records = []
    pattern = f"server:{agent.id}:container:*:metrics"
    stack_by_cid = _load_stack_lookup(r, agent.id)

    for key in r.scan_iter(match=pattern, count=100):
        raw = r.get(key)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON in %s", key)
            continue

        body = payload.get("data", {}) or {}
        cpu = body.get("cpu") or {}
        memory = body.get("memory") or {}
        network = body.get("network") or {}
        disk = body.get("disk") or {}

        # Agent v2: cpu.usage_pct (정규화 0-100, nullable) + cpu.cores_quota (nullable).
        # cores_quota 결정 실패 시 둘 다 null로 옴. usage(raw)는 항상 채워짐.
        # 구버전 agent: usage_pct/cores_quota 키 없음 → cores 또는 cpu_count로 fallback.
        usage_raw = _as_float(cpu.get("usage"))
        usage_pct_raw = cpu.get("usage_pct")
        cores_quota_raw = cpu.get("cores_quota")
        if cores_quota_raw is None:
            # 구버전 fallback: 같은 페이로드에 cores 가 있으면 사용
            cores_quota_raw = cpu.get("cores")
        cores_quota_f = _as_float(cores_quota_raw) if cores_quota_raw is not None else None

        # 정규화 cpu_usage 결정:
        # - usage_pct 가 명시적으로 null 이면 그대로 null 저장 (Agent가 측정 불가 표시)
        # - usage_pct 가 number 면 그대로 사용
        # - 키 자체가 없으면 (구버전) → cores_quota 로 fallback 정규화
        if "usage_pct" in cpu:
            if usage_pct_raw is None:
                usage_norm = None
            else:
                usage_norm = _as_float(usage_pct_raw)
        elif cores_quota_f and cores_quota_f >= 1:
            usage_norm = usage_raw / cores_quota_f
        else:
            usage_norm = usage_raw
        # Display layer expects 0-100; clamp defensively (null 은 통과).
        if usage_norm is not None:
            usage_norm = max(0.0, min(100.0, usage_norm))

        # Build kwargs and include the new normalization fields only when the
        # model supports them (i.e. migration 0002 has been applied).
        kwargs = dict(
            agent=agent,
            container_id=body.get("containerId", ""),
            cpu_usage=usage_norm,
            memory_usage=_as_int(memory.get("usage")),
            memory_limit=_as_int(memory.get("limit")),
            memory_percent=_as_float(memory.get("percent")),
            network_rx=_as_int(network.get("rx")),
            network_tx=_as_int(network.get("tx")),
            disk_read=_as_int(disk.get("read")),
            disk_write=_as_int(disk.get("write")),
            raw_data=body,
            recorded_at=_parse_timestamp(payload.get("timestamp")),
        )
        # 마이그레이션 적용 여부에 따라 새 컬럼 사용 가능성 분기.
        from django.db import connection
        with connection.cursor() as cur:
            cur.execute(
                "SELECT column_name, is_nullable FROM information_schema.columns WHERE table_name = %s",
                [ContainerMetricsHistory._meta.db_table],
            )
            db_col_info = {row[0]: row[1] for row in cur.fetchall()}
        if "cpu_usage_raw" in db_col_info:
            kwargs["cpu_usage_raw"] = usage_raw
        if "cpu_cores_quota" in db_col_info:
            kwargs["cpu_cores_quota"] = cores_quota_f
        # cpu_usage가 DB에서 NOT NULL인데 (0003 미적용) usage_norm이 None이면
        # IntegrityError가 나므로 raw 값으로 fallback.
        if kwargs.get("cpu_usage") is None and db_col_info.get("cpu_usage", "YES") == "NO":
            kwargs["cpu_usage"] = usage_raw if usage_raw is not None else 0.0

        # Per-container GPU (Agent v3 contract). Skip silently when the
        # migration that adds gpu_* columns hasn't been applied yet.
        gpu_block = body.get("gpu") if isinstance(body.get("gpu"), dict) else None
        if gpu_block:
            if "gpu_usage" in db_col_info:
                gpu_usage_raw = gpu_block.get("usage")
                kwargs["gpu_usage"] = None if gpu_usage_raw is None else _as_float(gpu_usage_raw)
            if "gpu_memory_used" in db_col_info:
                gmu = gpu_block.get("memoryUsed", gpu_block.get("memory_used"))
                kwargs["gpu_memory_used"] = _as_int(gmu) if gmu is not None else None
            if "gpu_memory_total" in db_col_info:
                gmt = gpu_block.get("memoryTotal", gpu_block.get("memory_total"))
                kwargs["gpu_memory_total"] = _as_int(gmt) if gmt is not None else None

        # Denormalized stack — only set when the column exists (0007 applied).
        if "stack" in db_col_info:
            cid = kwargs["container_id"] or ""
            kwargs["stack"] = (
                stack_by_cid.get(cid)
                or stack_by_cid.get(cid[:12])
                or "Unmanaged"
            )

        records.append(ContainerMetricsHistory(**kwargs))

    return records


def _parse_timestamp(value):
    """ISO8601 문자열 → aware datetime. 실패 시 현재 시각."""
    if not value:
        return timezone.now()
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return timezone.now()
    if dt.tzinfo is None:
        return timezone.make_aware(dt)
    return dt


def _as_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _as_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


# ----------------------------------------------------------------------
# Resource events — 자원 임계 초과/급증 이벤트 라이프사이클.
# detect_resource_events 가 1분 주기로 활성 agent 의 메트릭을 평가해
# (agent, metric) 단위 ResourceEvent 를 생성/갱신/해소한다.
# ----------------------------------------------------------------------


def _evaluate_metric(metric: str, spark: list[float]) -> dict | None:
    """metric 의 1분 bucket sparkline → 이벤트 후보. 후보 없으면 None.

    threshold(현재값이 임계 초과) 와 spike(직전 평균 대비 급등) 를 모두 보고,
    더 심각한 쪽(critical threshold > spike > warning threshold)을 채택한다.
    """
    if not spark:
        return None
    current = spark[-1]
    warn, crit = RESOURCE_THRESHOLDS[metric]

    candidate = None
    if current >= warn:
        severity = "critical" if current >= crit else "warning"
        candidate = {
            "kind": "threshold",
            "value": current,
            "delta": None,
            "severity": severity,
            "score": (3000 if severity == "critical" else 1000) + current,
        }

    if len(spark) >= 3:
        baseline = sum(spark[:-1]) / len(spark[:-1])
        delta = current - baseline
        if delta >= SPIKE_DELTA and current >= SPIKE_FLOOR:
            score = 2000 + delta
            if candidate is None or score > candidate["score"]:
                candidate = {
                    "kind": "spike",
                    "value": current,
                    "delta": delta,
                    "severity": "critical" if current >= crit else "warning",
                    "score": score,
                }
    return candidate


def _top_cause_container(agent_id, metric: str, since):
    """이벤트가 난 agent 에서 해당 지표 사용률이 가장 높은 컨테이너.

    disk 는 컨테이너 단위 의미가 약해 호출하지 않는다. 모두 0% 이거나 데이터가
    없으면 (None, None) — 호스트 프로세스가 원인이라 보고 컨테이너를 표시 안 함.
    """
    from apps.containers.models import Container
    from apps.metrics.models import ContainerMetricsHistory

    field = {"cpu": "cpu_usage", "memory": "memory_percent", "gpu": "gpu_usage"}.get(metric)
    if field is None:
        return None, None

    row = (
        ContainerMetricsHistory.objects.filter(agent_id=agent_id, recorded_at__gte=since)
        .exclude(**{f"{field}__isnull": True})
        .order_by(f"-{field}")
        .values("container_id", field)
        .first()
    )
    if not row or not row.get(field) or row[field] <= 0:
        return None, None

    container_id = row["container_id"]
    name = (
        Container.objects.filter(container_id=container_id)
        .values_list("name", flat=True)
        .first()
    )
    return (name or container_id[:12]), float(row[field])


@shared_task(name="apps.metrics.tasks.detect_resource_events")
def detect_resource_events():
    """1분 주기 — 활성 agent 의 자원 임계 초과/급증을 판정해 ResourceEvent
    라이프사이클((agent, metric) 단위 활성 1건)을 생성/갱신/해소한다."""
    from collections import defaultdict

    from django.db import transaction

    from apps.agents.models import Agent
    from apps.metrics.models import ResourceEvent, SystemMetricsHistory

    now = timezone.now()
    window_start = now - timedelta(minutes=SPARKLINE_MINUTES)
    bucket_expr = RawSQL(
        "(floor(extract(epoch from recorded_at) / 60) * 60)::bigint",
        (),
        output_field=IntegerField(),
    )
    rows = list(
        SystemMetricsHistory.objects.filter(recorded_at__gte=window_start)
        .order_by()
        .annotate(bucket_epoch=bucket_expr)
        .values("agent_id", "bucket_epoch")
        .annotate(
            cpu=Avg("cpu_usage"),
            memory=Avg("memory_usage"),
            gpu=Avg("gpu_usage"),
            gpu_count=Max("gpu_count"),
        )
    )
    if not rows:
        return "no recent metrics"

    buckets_by_agent: dict = defaultdict(list)
    for row in rows:
        buckets_by_agent[row["agent_id"]].append(row)

    agents_by_id = {a.id: a for a in Agent.objects.filter(id__in=buckets_by_agent.keys())}
    active_events = {
        (e.agent_id, e.metric): e
        for e in ResourceEvent.objects.filter(ended_at__isnull=True)
    }

    to_create: list = []
    to_update: list = []
    seen: set = set()

    for agent_id, agent_buckets in buckets_by_agent.items():
        agent = agents_by_id.get(agent_id)
        if not agent:
            continue
        agent_buckets.sort(key=lambda r: r["bucket_epoch"])
        gpu_count = max((r["gpu_count"] or 0) for r in agent_buckets)

        for metric in RESOURCE_METRICS:
            if metric == "gpu" and gpu_count <= 0:
                continue
            spark = [r[metric] for r in agent_buckets if r[metric] is not None]
            candidate = _evaluate_metric(metric, spark)
            if candidate is None:
                continue

            seen.add((agent_id, metric))
            cause_name, cause_value = _top_cause_container(
                agent_id, metric, now - timedelta(minutes=1)
            )

            warn, crit = RESOURCE_THRESHOLDS[metric]
            existing = active_events.get((agent_id, metric))
            if existing:
                existing.last_seen_at = now
                existing.last_value = candidate["value"]
                existing.peak_value = max(existing.peak_value, candidate["value"])
                existing.kind = candidate["kind"]
                if candidate["delta"] is not None:
                    existing.spike_delta = max(existing.spike_delta or 0.0, candidate["delta"])
                existing.severity = "critical" if existing.peak_value >= crit else "warning"
                existing.cause_container_name = cause_name
                existing.cause_container_value = cause_value
                existing.updated_at = now
                to_update.append(existing)
            else:
                to_create.append(
                    ResourceEvent(
                        agent=agent,
                        hostname=agent.hostname,
                        metric=metric,
                        kind=candidate["kind"],
                        severity=candidate["severity"],
                        started_at=now,
                        last_seen_at=now,
                        peak_value=candidate["value"],
                        last_value=candidate["value"],
                        spike_delta=candidate["delta"],
                        cause_container_name=cause_name,
                        cause_container_value=cause_value,
                    )
                )

    # 후보가 사라진 활성 이벤트 → 자동 해소.
    to_resolve = [
        event
        for (agent_id, metric), event in active_events.items()
        if (agent_id, metric) not in seen
    ]
    for event in to_resolve:
        event.ended_at = now
        event.ended_reason = ResourceEvent.EndedReason.RESOLVED
        event.updated_at = now

    with transaction.atomic():
        if to_create:
            ResourceEvent.objects.bulk_create(to_create)
        if to_update:
            ResourceEvent.objects.bulk_update(
                to_update,
                [
                    "last_seen_at", "last_value", "peak_value", "kind", "spike_delta",
                    "severity", "cause_container_name", "cause_container_value", "updated_at",
                ],
            )
        if to_resolve:
            ResourceEvent.objects.bulk_update(
                to_resolve, ["ended_at", "ended_reason", "updated_at"]
            )

    summary = (
        f"resource events: +{len(to_create)} new, "
        f"~{len(to_update)} ongoing, -{len(to_resolve)} resolved"
    )
    logger.info(summary)
    return summary
