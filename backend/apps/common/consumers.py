import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger(__name__)

REDIS_CACHE_TTL = 60  # seconds
ACTIVE_IDS_KEY = "server:active_ids"
ACTIVE_IDS_TTL = 120  # seconds


class MonitoringConsumer(AsyncWebsocketConsumer):
    """
    서버 모니터링 WebSocket Hub.

    - Agent: 데이터 송신 → Redis 캐시 + 브라우저 브로드캐스트 + Container 모델 갱신
    - Browser: 같은 그룹의 데이터 수신만 가능
    """

    async def connect(self):
        self.server_id = self.scope["url_route"]["kwargs"]["server_id"]
        self.group_name = f"server_{self.server_id}"
        self.is_agent = self.scope.get("is_agent", False)
        user = self.scope.get("user", AnonymousUser())

        if isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close(code=4001)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        client_type = "agent" if self.is_agent else "browser"
        await self.send(text_data=json.dumps({
            "type": "connection",
            "message": f"Connected to server {self.server_id}",
            "server_id": self.server_id,
            "client_type": client_type,
        }))

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        """Agent만 데이터 전송 가능. Browser는 수신만."""
        if text_data is None:
            return
        if not self.is_agent:
            await self.send(text_data=json.dumps({
                "error": "Only agents can send data",
            }))
            return

        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({"error": "Invalid JSON"}))
            return

        data["server_id"] = self.server_id
        msg_type = data.get("type", "unknown")

        # 1. Redis 캐시 (최신 상태)
        await self._cache_to_redis(msg_type, data)

        # 2. 브라우저 브로드캐스트 (기존 동작)
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "server_message", "data": data},
        )

        # 3. containers 메시지면 Container 모델 갱신
        if msg_type == "containers":
            await self._update_containers(data)

    async def server_message(self, event):
        """그룹 메시지를 WebSocket으로 전달."""
        await self.send(text_data=json.dumps(event["data"]))

    # ------------------------------------------------------------------
    # Redis 캐시
    # ------------------------------------------------------------------

    async def _cache_to_redis(self, msg_type, data):
        """수신 데이터를 Redis에 merge 저장. Delta Sync로 부분 데이터만 올 수 있으므로
        기존 캐시와 병합하여 항상 전체 상태를 유지한다."""
        from apps.common.redis_client import get_redis_client

        try:
            r = get_redis_client()

            if msg_type == "system_metrics":
                key = f"server:{self.server_id}:system"
                merged = _merge_cached(r, key, data)
                r.set(key, json.dumps(merged), ex=REDIS_CACHE_TTL)
            elif msg_type == "containers":
                key = f"server:{self.server_id}:containers"
                r.set(key, json.dumps(data), ex=REDIS_CACHE_TTL)
            elif msg_type == "container_metrics":
                container_id = data.get("data", {}).get("containerId", "unknown")
                key = f"server:{self.server_id}:container:{container_id}:metrics"
                merged = _merge_cached(r, key, data)
                r.set(key, json.dumps(merged), ex=REDIS_CACHE_TTL)
            else:
                return

            pipe = r.pipeline(transaction=False)
            pipe.sadd(ACTIVE_IDS_KEY, self.server_id)
            pipe.expire(ACTIVE_IDS_KEY, ACTIVE_IDS_TTL)
            pipe.execute()
        except Exception:
            logger.exception("[ws] Redis cache write failed for %s", self.server_id)

    # ------------------------------------------------------------------
    # Container 모델 갱신
    # ------------------------------------------------------------------

    async def _update_containers(self, data):
        try:
            await self._sync_update_containers(data)
        except Exception:
            logger.exception("[ws] Container model update failed for %s", self.server_id)

    @database_sync_to_async
    def _sync_update_containers(self, data):
        from apps.agents.models import Agent
        from apps.containers.models import Container

        try:
            agent = Agent.objects.get(id=self.server_id)
        except Agent.DoesNotExist:
            logger.warning("[ws] Agent %s not found for container update", self.server_id)
            return

        container_list = data.get("data", {}).get("containers", [])
        seen_ids = set()

        for c in container_list:
            cid = c.get("id", "")
            if not cid:
                continue
            seen_ids.add(cid)
            Container.objects.update_or_create(
                container_id=cid,
                defaults={
                    "name": c.get("name", ""),
                    "image": c.get("image", ""),
                    "agent": agent,
                    "status": _normalize_status(c.get("state", "created")),
                },
            )

        # 보고에서 빠진 컨테이너는 exited로 마킹
        if seen_ids:
            agent.containers.exclude(container_id__in=seen_ids).update(status="exited")


def _normalize_status(state: str) -> str:
    """Docker container state → Container.Status 값 매핑."""
    valid = {"running", "stopped", "paused", "exited", "created", "restarting", "dead"}
    state = (state or "").lower()
    return state if state in valid else "created"


def _merge_cached(r, key: str, new_data: dict) -> dict:
    """Redis에 저장된 기존 데이터와 새 delta 데이터를 병합.

    Delta Sync에서 변경된 필드만 오기 때문에, 기존 캐시의 data 부분에
    새 data를 shallow merge하여 항상 전체 상태를 유지한다.
    """
    existing_raw = r.get(key)
    if not existing_raw:
        return new_data

    try:
        existing = json.loads(existing_raw)
    except (json.JSONDecodeError, TypeError):
        return new_data

    # timestamp는 항상 새 값으로
    existing["timestamp"] = new_data.get("timestamp", existing.get("timestamp"))
    existing["server_id"] = new_data.get("server_id", existing.get("server_id"))

    # data 부분을 shallow merge (새 키가 있으면 덮어쓰기, 없으면 기존 유지)
    old_body = existing.get("data") or {}
    new_body = new_data.get("data") or {}
    old_body.update(new_body)
    existing["data"] = old_body

    return existing
