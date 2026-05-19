"""Agent lifecycle Celery tasks.

- detect_offline_agents: 30초마다, last_seen_at 기준 5분 grace 초과한 active
  Agent를 찾아 global 채널로 offline 이벤트 push.
- archive_dormant_agents: 매일 03:30, 7일 이상 dormant이면 status=archived.
- delete_archived_agents: 매일 04:00, archived 상태가 30일 추가로 지속되면
  hard delete (cascade로 컨테이너/이력도 함께 정리).
"""

import logging
from datetime import timedelta

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.utils import timezone

from apps.agents.models import Agent, AgentStatusEvent
from apps.agents.services.gpu_inventory import (
    GPU_INVENTORY_SENTINEL,
    build_gpu_inventory_request_id,
    mark_agent_gpu_inventory_offline,
)
from apps.common import agent_presence, command_router

logger = logging.getLogger(__name__)

GRACE_PERIOD_SECONDS = 5 * 60  # 5분
ARCHIVE_AFTER_DAYS = 7
HARD_DELETE_AFTER_ARCHIVED_DAYS = 30
GLOBAL_GROUP = "global_events"


def _push_global_event(payload: dict) -> None:
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(
        GLOBAL_GROUP,
        {"type": "global.event", "payload": payload},
    )


@shared_task
def detect_offline_agents():
    """Active로 알려진 Agent 중 grace period 초과한 항목 → offline 이벤트."""
    notified = agent_presence.get_notified_active()
    if not notified:
        return "no active agents tracked"

    cutoff = timezone.now() - timedelta(seconds=GRACE_PERIOD_SECONDS)
    transitioned = []

    for server_id in notified:
        try:
            agent = Agent.objects.only(
                "id", "hostname", "last_seen_at"
            ).get(id=server_id)
        except Agent.DoesNotExist:
            agent_presence.clear_notified_active(server_id)
            continue

        if agent.last_seen_at is None or agent.last_seen_at < cutoff:
            agent_presence.clear_notified_active(server_id)
            occurred_at = agent.last_seen_at or timezone.now()
            offline_at = occurred_at.isoformat()
            # Persist BEFORE broadcasting so a refresh that lands between
            # the broadcast and the DB write still surfaces the event in
            # the dashboard's "최근 상태 변화" panel.
            AgentStatusEvent.objects.create(
                agent=agent,
                hostname=agent.hostname,
                status=AgentStatusEvent.Status.OFFLINE,
                occurred_at=occurred_at,
            )
            _push_global_event({
                "type": "agent_status_change",
                "status": "offline",
                "server_id": str(agent.id),
                "hostname": agent.hostname,
                "last_seen_at": offline_at,
            })
            transitioned.append(agent.hostname)

    return f"offline transitions: {transitioned}"


@shared_task
def refresh_gpu_inventories():
    """Ask connected approved agents for GPU inventory."""
    layer = get_channel_layer()
    sent = 0
    marked_offline = 0
    failed = 0

    for agent in Agent.objects.filter(status=Agent.Status.APPROVED).only("id", "hostname"):
        agent_id = str(agent.id)
        agent_channel = command_router.get_agent_channel(agent_id)
        if not agent_channel or layer is None:
            mark_agent_gpu_inventory_offline(agent)
            marked_offline += 1
            continue

        request_id = build_gpu_inventory_request_id(agent_id)
        command_router.record_pending(request_id, GPU_INVENTORY_SENTINEL, agent_id)
        payload = {
            "type": "command",
            "requestId": request_id,
            "command": "system_info",
            "params": {"subCommand": "gpu_inventory"},
        }

        try:
            async_to_sync(layer.send)(agent_channel, {
                "type": "ws.send",
                "payload": payload,
            })
            sent += 1
        except Exception:
            logger.exception("[gpu-inventory] Failed to dispatch to agent %s", agent_id)
            mark_agent_gpu_inventory_offline(agent)
            failed += 1

    return f"gpu inventory refresh sent={sent} offline={marked_offline} failed={failed}"


@shared_task
def archive_dormant_agents():
    """7일 이상 데이터 못 받은 approved Agent → status=archived."""
    cutoff = timezone.now() - timedelta(days=ARCHIVE_AFTER_DAYS)
    qs = Agent.objects.filter(
        status=Agent.Status.APPROVED,
        last_seen_at__lt=cutoff,
    )
    count = 0
    for agent in qs:
        agent.status = Agent.Status.ARCHIVED
        agent.archived_at = timezone.now()
        agent.save(update_fields=["status", "archived_at"])
        count += 1
    return f"archived {count} agents"


@shared_task
def delete_archived_agents():
    """archived된 지 30일 추가 경과한 Agent → hard delete."""
    cutoff = timezone.now() - timedelta(days=HARD_DELETE_AFTER_ARCHIVED_DAYS)
    qs = Agent.objects.filter(
        status=Agent.Status.ARCHIVED,
        archived_at__lt=cutoff,
    )
    count = qs.count()
    qs.delete()
    return f"hard-deleted {count} agents"
