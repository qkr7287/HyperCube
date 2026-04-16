import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer
from django.contrib.auth.models import AnonymousUser

from apps.common import agent_presence, command_router

logger = logging.getLogger(__name__)

GLOBAL_GROUP = "global_events"

REDIS_CACHE_TTL = 60  # seconds (주기적 데이터: system_metrics, container_metrics)
CONTAINERS_CACHE_TTL = 600  # seconds (스냅샷성 데이터: 변경 드물어 오래 유지)
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

        if self.is_agent:
            command_router.register_agent(self.server_id, self.channel_name)
            await self._touch_presence(force=True)

        client_type = "agent" if self.is_agent else "browser"
        await self.send(text_data=json.dumps({
            "type": "connection",
            "message": f"Connected to server {self.server_id}",
            "server_id": self.server_id,
            "client_type": client_type,
        }))

        # Browser 재접속 시 초기 스냅샷: Redis 캐시된 최신 상태를 즉시 송신
        # (Agent는 Delta Sync라 재전송 안 함. 이후 Delta가 자연스럽게 덮어씀)
        if not self.is_agent:
            await self._replay_from_redis()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        if getattr(self, "is_agent", False):
            command_router.unregister_agent(self.server_id, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        """Agent: 데이터 송신 + command_response. Browser: command 발행만."""
        if text_data is None:
            return
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({"error": "Invalid JSON"}))
            return

        msg_type = data.get("type", "unknown")

        if not self.is_agent:
            if msg_type == "command":
                await self._handle_browser_command(data)
                return
            await self.send(text_data=json.dumps({
                "error": "Only agents can send data",
            }))
            return

        # --- Agent path ---
        # Agent가 살아있는 동안 레지스트리를 주기적으로 refresh (TTL 300s).
        # connect() 1회 등록만으로는 5분 후 만료되어 명령 라우팅이 깨진다.
        command_router.register_agent(self.server_id, self.channel_name)
        await self._touch_presence()

        if msg_type == "command_response":
            await self._route_command_response(data)
            await self._update_request_from_response(data)
            return

        if msg_type == "command_progress":
            await self._route_command_progress(data)
            return

        data["server_id"] = self.server_id

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
    # Presence (last_seen_at + global agent_status_change events)
    # ------------------------------------------------------------------

    async def _touch_presence(self, force: bool = False):
        """Agent 메시지 수신 시 last_seen_at 갱신 (60초 rate-limit) +
        새로 active로 전환된 경우 global 채널로 online 이벤트 broadcast.

        force=True면 rate-limit 무시 (connect 직후).
        """
        if not (force or agent_presence.should_update_last_seen(self.server_id)):
            return

        agent = await self._update_last_seen()
        if not agent:
            return

        was_already_active = not agent_presence.mark_notified_active(self.server_id)
        if was_already_active:
            return

        # transition: offline → online
        await self.channel_layer.group_send(
            GLOBAL_GROUP,
            {
                "type": "global.event",
                "payload": {
                    "type": "agent_status_change",
                    "status": "online",
                    "server_id": self.server_id,
                    "hostname": agent["hostname"],
                    "last_seen_at": agent["last_seen_at"],
                    "previous_offline_seconds": agent["previous_offline_seconds"],
                },
            },
        )

    @database_sync_to_async
    def _update_last_seen(self) -> dict | None:
        from django.utils import timezone

        from apps.agents.models import Agent

        try:
            agent = Agent.objects.get(id=self.server_id)
        except Agent.DoesNotExist:
            return None

        now = timezone.now()
        prev = agent.last_seen_at
        offline_secs = int((now - prev).total_seconds()) if prev else None

        update_fields = ["last_seen_at"]
        agent.last_seen_at = now

        # archived 상태에서 데이터가 다시 들어오면 자동 복귀
        if agent.status == Agent.Status.ARCHIVED:
            agent.status = Agent.Status.APPROVED
            agent.archived_at = None
            update_fields += ["status", "archived_at"]

        agent.save(update_fields=update_fields)
        return {
            "hostname": agent.hostname,
            "last_seen_at": now.isoformat(),
            "previous_offline_seconds": offline_secs,
        }

    async def ws_send(self, event):
        """임의의 payload를 현재 WS로 그대로 전달 (직접 라우팅용)."""
        await self.send(text_data=json.dumps(event["payload"]))

    # ------------------------------------------------------------------
    # Command routing
    # ------------------------------------------------------------------

    async def _handle_browser_command(self, data: dict):
        """Browser가 보낸 command를 해당 server의 Agent 채널로 포워딩."""
        request_id = data.get("requestId")
        if not request_id:
            await self.send(text_data=json.dumps({
                "type": "command_response",
                "success": False,
                "error": "missing_request_id",
            }))
            return

        agent_channel = command_router.get_agent_channel(self.server_id)
        if not agent_channel:
            await self.send(text_data=json.dumps({
                "type": "command_response",
                "requestId": request_id,
                "success": False,
                "error": "agent_offline",
            }))
            return

        command_router.record_pending(request_id, self.channel_name, self.server_id)

        # Agent에게 원본 메시지 그대로 전달 (Agent는 requestId로 매칭)
        await self.channel_layer.send(agent_channel, {
            "type": "ws.send",
            "payload": data,
        })

    async def _route_command_response(self, data: dict):
        """Agent가 보낸 command_response를 요청 Browser로 라우팅."""
        request_id = data.get("requestId")
        if not request_id:
            logger.warning("[ws] command_response missing requestId")
            return

        pending = command_router.pop_pending(request_id)
        if not pending:
            # 타임아웃/중복 응답 — 조용히 폐기
            return

        browser_channel = pending.get("browser")
        if not browser_channel:
            return

        await self.channel_layer.send(browser_channel, {
            "type": "ws.send",
            "payload": data,
        })

    async def _route_command_progress(self, data: dict):
        """Agent의 command_progress를 요청 Browser로 포워딩 + DB 갱신 + global broadcast."""
        request_id = data.get("requestId")
        if not request_id:
            return

        # pending map에서 browser channel 조회 (pop 하지 않음 — progress는 여러 번 옴)
        pending = command_router.pop_pending(request_id)
        if pending:
            # 다시 저장 (pop했으므로)
            command_router.record_pending(request_id, pending["browser"], pending["server_id"])
            browser_channel = pending.get("browser")
            if browser_channel:
                await self.channel_layer.send(browser_channel, {
                    "type": "ws.send",
                    "payload": data,
                })

        # DB 갱신: ContainerRequest.progress_message / progress_percent
        await self._update_request_progress(data)

        # global broadcast (user 페이지가 자기 요청 progress 받음)
        await self.channel_layer.group_send(
            GLOBAL_GROUP,
            {"type": "global.event", "payload": data},
        )

    @database_sync_to_async
    def _update_request_progress(self, data: dict):
        """command_progress → ContainerRequest DB 갱신."""
        from apps.containers.models import ContainerRequest

        request_id = data.get("requestId")
        if not request_id:
            return
        try:
            req = ContainerRequest.objects.get(id=request_id)
        except (ContainerRequest.DoesNotExist, Exception):
            return

        req.progress_message = data.get("message", "")
        req.progress_percent = data.get("percent")
        fields = ["progress_message", "progress_percent", "updated_at"]

        if req.status == "approved":
            req.status = "deploying"
            fields.append("status")

        req.save(update_fields=fields)

    @database_sync_to_async
    def _update_request_from_response(self, data: dict):
        """command_response (최종 결과) → ContainerRequest + Container DB 갱신."""
        from apps.containers.models import Container, ContainerRequest

        request_id = data.get("requestId")
        if not request_id:
            return
        try:
            req = ContainerRequest.objects.get(id=request_id)
        except (ContainerRequest.DoesNotExist, Exception):
            return

        success = data.get("success", False)
        resp_data = data.get("data", {})

        if success:
            req.status = "deployed"
            req.progress_percent = 100
            req.progress_message = "완료"

            # Container row 생성 (create 요청인 경우)
            # Agent의 container sync는 12자 short ID를 사용하므로 동일 기준으로 정규화
            if req.action == "create":
                container_id = _short_cid(resp_data.get("containerId", ""))
                containers = resp_data.get("containers", [])

                if container_id:
                    obj, _ = Container.objects.update_or_create(
                        container_id=container_id,
                        defaults={
                            "name": resp_data.get("name", req.custom_name),
                            "image": resp_data.get("image", req.selected_image),
                            "agent": req.target_agent,
                            "status": resp_data.get("state", "running"),
                            "requester": req.requester,
                            "created_via_request": req,
                        },
                    )
                    req.target_container = obj
                # compose: 여러 컨테이너 — 첫 번째를 target_container로 링크
                first_obj = None
                for c in containers:
                    cid = _short_cid(c.get("containerId", ""))
                    if cid:
                        obj, _ = Container.objects.update_or_create(
                            container_id=cid,
                            defaults={
                                "name": c.get("name", ""),
                                "image": c.get("image", ""),
                                "agent": req.target_agent,
                                "status": c.get("state", "running"),
                                "requester": req.requester,
                                "created_via_request": req,
                            },
                        )
                        if first_obj is None:
                            first_obj = obj
                if first_obj is not None and not req.target_container:
                    req.target_container = first_obj

            # delete 요청: Container row 삭제
            elif req.action == "delete" and req.target_container:
                req.target_container.delete()
                req.target_container = None

        else:
            req.status = "failed"
            req.progress_message = data.get("error", "unknown error")

        req.deployment_log += f"\n--- command_response ---\n{json.dumps(data, ensure_ascii=False, indent=2)}"
        req.save(update_fields=[
            "status", "progress_percent", "progress_message",
            "target_container", "deployment_log", "updated_at",
        ])

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
                r.set(key, json.dumps(data), ex=CONTAINERS_CACHE_TTL)
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

    async def _replay_from_redis(self):
        """Redis 캐시에서 최신 스냅샷을 읽어 현재 WS로 송신.

        Browser 재접속 시 초기 데이터를 복원한다. Agent는 Delta Sync라
        변경분만 주기적으로 보내므로 Browser가 빈 상태로 기다리게 되는
        문제를 방지.
        """
        from apps.common.redis_client import get_redis_client

        try:
            r = get_redis_client()
            # 순서: system_metrics → containers → container_metrics
            # (container_metrics는 컨테이너 목록이 먼저 있어야 의미 있음)
            for key in (
                f"server:{self.server_id}:system",
                f"server:{self.server_id}:containers",
            ):
                raw = r.get(key)
                if raw:
                    await self.send(text_data=raw)

            # container_metrics: 여러 컨테이너가 개별 키에 저장됨
            pattern = f"server:{self.server_id}:container:*:metrics"
            for key in r.scan_iter(match=pattern, count=100):
                raw = r.get(key)
                if raw:
                    await self.send(text_data=raw)
        except Exception:
            logger.exception("[ws] Redis replay failed for %s", self.server_id)

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


def _short_cid(cid: str) -> str:
    """Docker container ID를 12자 short form으로 정규화. Agent container sync가 12자를
    사용하므로 command_response의 full ID(64자)도 동일 기준으로 맞춘다."""
    return (cid or "")[:12]


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


class GlobalEventsConsumer(AsyncWebsocketConsumer):
    """전역 cross-cutting 이벤트 채널.

    로그인한 모든 Browser가 하나의 group(global_events)에 join하고,
    Backend가 broadcast하는 시스템 이벤트(agent_status_change 등)를
    수신한다. Agent는 접속하지 않는다.
    """

    async def connect(self):
        user = self.scope.get("user", AnonymousUser())
        if isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close(code=4001)
            return
        if self.scope.get("is_agent"):
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(GLOBAL_GROUP, self.channel_name)
        await self.accept()
        await self.send(text_data=json.dumps({
            "type": "connection",
            "channel": "global",
            "message": "Connected to global events channel.",
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(GLOBAL_GROUP, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # 클라이언트는 send 권한 없음. 무시.
        return

    async def global_event(self, event):
        await self.send(text_data=json.dumps(event["payload"]))
