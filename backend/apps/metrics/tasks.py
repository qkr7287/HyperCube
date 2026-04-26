"""Celery periodic tasks for metrics persistence and cleanup."""

import json
import logging
from datetime import datetime, timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


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

    if gpus and isinstance(gpus, list):
        # 다중 GPU 호스트도 단일 컬럼으로 aggregation 가능하게 평균·합산·최대값 정규화.
        usage_vals = [_as_float(g.get("usage")) for g in gpus if g.get("usage") is not None]
        mem_used_vals = [_as_int(g.get("memoryUsed")) for g in gpus if g.get("memoryUsed") is not None]
        mem_total_vals = [_as_int(g.get("memoryTotal")) for g in gpus if g.get("memoryTotal") is not None]
        temp_vals = [_as_float(g.get("temperature")) for g in gpus if g.get("temperature") is not None]
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


def _collect_container_metrics(r, agent):
    """server:{id}:container:*:metrics 패턴의 모든 키를 스캔해서 인스턴스 생성."""
    from apps.metrics.models import ContainerMetricsHistory

    records = []
    pattern = f"server:{agent.id}:container:*:metrics"

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
