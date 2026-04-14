"""Agent on-demand command routing.

- Agent 연결 시 Redis에 (server_id -> channel_name) 레지스트리 저장.
- Browser가 발행한 command를 해당 Agent 채널로 직접 라우팅.
- Agent가 보낸 command_response를 요청 Browser 채널로 직접 라우팅.
"""

import json
import logging
from typing import Optional

from apps.common.redis_client import get_redis_client

logger = logging.getLogger(__name__)

AGENT_REG_TTL = 300  # seconds, Agent가 살아있는 동안만 유효
PENDING_TTL = 30     # seconds, 명령 타임아웃

AGENT_REG_KEY = "agent_channel:{server_id}"
PENDING_KEY = "cmd_pending:{request_id}"


def register_agent(server_id: str, channel_name: str) -> None:
    r = get_redis_client()
    r.set(AGENT_REG_KEY.format(server_id=server_id), channel_name, ex=AGENT_REG_TTL)


def unregister_agent(server_id: str, channel_name: str) -> None:
    """자기 소유 채널일 때만 삭제 (재연결 race 방지)."""
    r = get_redis_client()
    key = AGENT_REG_KEY.format(server_id=server_id)
    current = r.get(key)
    if current == channel_name:
        r.delete(key)


def get_agent_channel(server_id: str) -> Optional[str]:
    r = get_redis_client()
    return r.get(AGENT_REG_KEY.format(server_id=server_id))


def record_pending(request_id: str, browser_channel: str, server_id: str) -> None:
    r = get_redis_client()
    payload = json.dumps({"browser": browser_channel, "server_id": server_id})
    r.set(PENDING_KEY.format(request_id=request_id), payload, ex=PENDING_TTL)


def pop_pending(request_id: str) -> Optional[dict]:
    r = get_redis_client()
    key = PENDING_KEY.format(request_id=request_id)
    raw = r.get(key)
    if not raw:
        return None
    r.delete(key)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Malformed pending entry for %s", request_id)
        return None
