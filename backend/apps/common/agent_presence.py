"""Agent presence tracking — Redis 기반.

`agents:notified_active` SET에 "Backend가 현재 active로 인지하고 알린 Agent ID"를
보관한다. Consumer가 새로 receive할 때 / Celery beat task가 주기 점검할 때
이 SET과 실제 last_seen_at을 비교해 transition을 감지한다.
"""

import logging

from apps.common.redis_client import get_redis_client

logger = logging.getLogger(__name__)

NOTIFIED_ACTIVE_KEY = "agents:notified_active"
LAST_SEEN_MARKER_KEY = "agent:last_seen_marker:{server_id}"
LAST_SEEN_MARKER_TTL = 60  # seconds


def mark_notified_active(server_id: str) -> bool:
    """Active 알림을 보냈다고 표시. 신규 추가면 True 반환 (즉, transition)."""
    r = get_redis_client()
    return bool(r.sadd(NOTIFIED_ACTIVE_KEY, server_id))


def clear_notified_active(server_id: str) -> bool:
    """Active 알림 표시 제거. 제거됐으면 True (transition)."""
    r = get_redis_client()
    return bool(r.srem(NOTIFIED_ACTIVE_KEY, server_id))


def get_notified_active() -> set[str]:
    r = get_redis_client()
    return set(r.smembers(NOTIFIED_ACTIVE_KEY))


def should_update_last_seen(server_id: str) -> bool:
    """Rate-limit: 최근 60초 안에 갱신했으면 skip.

    Redis 마커 SET (NX, EX=60). 성공하면 갱신 권한을 얻은 것.
    """
    r = get_redis_client()
    key = LAST_SEEN_MARKER_KEY.format(server_id=server_id)
    return bool(r.set(key, "1", nx=True, ex=LAST_SEEN_MARKER_TTL))
