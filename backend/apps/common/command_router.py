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
RESPONSE_TTL = 30    # seconds, REST poll window

AGENT_REG_KEY = "agent_channel:{server_id}"
PENDING_KEY = "cmd_pending:{request_id}"
RESPONSE_KEY = "cmd_response:{request_id}"

# REST에서 동기 wait 할 때 browser_channel 자리에 넣는 sentinel.
# Consumer는 이 값을 보고 channel_layer forward 대신 store_response 만 수행.
REST_SENTINEL = "__rest__"


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


def store_response(request_id: str, response: dict, ttl: int = RESPONSE_TTL) -> None:
    """Agent의 command_response를 REST waiter가 polling 할 수 있도록 저장."""
    r = get_redis_client()
    r.set(RESPONSE_KEY.format(request_id=request_id), json.dumps(response), ex=ttl)


def fetch_response(request_id: str) -> Optional[dict]:
    """저장된 응답을 fetch + 즉시 삭제 (race 방지). 없으면 None."""
    r = get_redis_client()
    key = RESPONSE_KEY.format(request_id=request_id)
    raw = r.get(key)
    if raw is None:
        return None
    r.delete(key)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Malformed response entry for %s", request_id)
        return None


# ----- Long-running stream subscriptions (logs_subscribe etc.) -----
# stream_id 단위로 browser_channel 을 별도 보관. 일반 command pending 과 달리
# pop 하지 않고 다중 메시지 routing 에 사용. TTL 1h (장시간 tail 허용).

STREAM_KEY = "cmd_stream:{stream_id}"
STREAM_BY_CHANNEL_KEY = "cmd_streams_by_channel:{channel}"
STREAM_TTL = 3600  # 1 hour — tail 세션 최대 수명


def record_stream(stream_id: str, browser_channel: str, server_id: str) -> None:
    r = get_redis_client()
    payload = json.dumps({"browser": browser_channel, "server_id": server_id})
    r.set(STREAM_KEY.format(stream_id=stream_id), payload, ex=STREAM_TTL)
    by_channel = STREAM_BY_CHANNEL_KEY.format(channel=browser_channel)
    r.sadd(by_channel, stream_id)
    r.expire(by_channel, STREAM_TTL)


def get_stream_info(stream_id: str) -> Optional[dict]:
    r = get_redis_client()
    raw = r.get(STREAM_KEY.format(stream_id=stream_id))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def remove_stream(stream_id: str) -> None:
    """stream entry 와 by-channel set 양쪽에서 정리."""
    r = get_redis_client()
    info = get_stream_info(stream_id)
    if info:
        by_channel = STREAM_BY_CHANNEL_KEY.format(channel=info.get("browser", ""))
        r.srem(by_channel, stream_id)
    r.delete(STREAM_KEY.format(stream_id=stream_id))


def streams_by_channel(browser_channel: str) -> list:
    """browser_channel 이 활성으로 가진 모든 stream_id 목록.
    Browser disconnect 시 일괄 cleanup 용."""
    r = get_redis_client()
    members = r.smembers(STREAM_BY_CHANNEL_KEY.format(channel=browser_channel))
    return list(members)
