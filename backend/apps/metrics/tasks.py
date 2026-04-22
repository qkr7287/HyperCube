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

    return [SystemMetricsHistory(
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
    )]


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

        records.append(ContainerMetricsHistory(
            agent=agent,
            container_id=body.get("containerId", ""),
            cpu_usage=_as_float(cpu.get("usage")),
            memory_usage=_as_int(memory.get("usage")),
            memory_limit=_as_int(memory.get("limit")),
            memory_percent=_as_float(memory.get("percent")),
            network_rx=_as_int(network.get("rx")),
            network_tx=_as_int(network.get("tx")),
            disk_read=_as_int(disk.get("read")),
            disk_write=_as_int(disk.get("write")),
            raw_data=body,
            recorded_at=_parse_timestamp(payload.get("timestamp")),
        ))

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
