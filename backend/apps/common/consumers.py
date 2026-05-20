import asyncio
import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer
from django.contrib.auth.models import AnonymousUser

from apps.common import agent_presence, command_router

logger = logging.getLogger(__name__)

GLOBAL_GROUP = "global_events"

REDIS_CACHE_TTL = 60  # seconds (system_metrics: Agent가 ~5s 간격 delta로 자주 갱신)
# container_metrics TTL은 Agent의 full snapshot interval(60s)보다 여유있게 커야
# Delta 없이 idle 컨테이너도 캐시 공백이 안 생긴다 (agent 293f84f).
CONTAINER_METRICS_CACHE_TTL = 150  # seconds
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
        self._disconnected = False
        self.server_id = self.scope["url_route"]["kwargs"]["server_id"]
        self.group_name = f"server_{self.server_id}"
        self.is_agent = self.scope.get("is_agent", False)
        user = self.scope.get("user", AnonymousUser())

        if isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close(code=4001)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept(subprotocol=self.scope.get("ws_accept_subprotocol"))

        if self.is_agent:
            try:
                command_router.register_agent(self.server_id, self.channel_name)
            except Exception:
                logger.exception("[ws] Redis agent registration failed — rejecting WS")
                await self.close(code=1011)
                return
            await self._touch_presence(force=True)

        client_type = "agent" if self.is_agent else "browser"
        await self.send(text_data=json.dumps({
            "type": "connection",
            "message": f"Connected to server {self.server_id}",
            "server_id": self.server_id,
            "client_type": client_type,
        }))

        # Agent에 주기적 heartbeat 전송 (좀비 WS 세션 감지용)
        if self.is_agent:
            self._heartbeat_task = asyncio.ensure_future(self._send_heartbeat_loop())

        # Browser 재접속 시 초기 스냅샷: Redis 캐시된 최신 상태를 즉시 송신
        # (Agent는 Delta Sync라 재전송 안 함. 이후 Delta가 자연스럽게 덮어씀)
        if not self.is_agent:
            await self._replay_from_redis()

    async def disconnect(self, close_code):
        self._disconnected = True
        if hasattr(self, "_heartbeat_task"):
            self._heartbeat_task.cancel()
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        if getattr(self, "is_agent", False):
            command_router.unregister_agent(self.server_id, self.channel_name)
        else:
            # Browser disconnect: 이 channel 이 가지고 있던 활성 log stream 모두
            # agent 에 unsubscribe 송신 + registry 정리. agent 가 해당 streamId 를
            # 모르면 idempotent 처리한다는 합의대로.
            await self._cleanup_browser_streams()

    async def _cleanup_browser_streams(self):
        import uuid
        active = command_router.streams_by_channel(self.channel_name)
        for stream_id in active:
            info = command_router.get_stream_info(stream_id) or {}
            agent_channel = command_router.get_agent_channel(info.get("server_id", ""))
            kind = info.get("kind", "logs")
            if agent_channel:
                if kind == "exec":
                    payload = {
                        "type": "command",
                        "requestId": str(uuid.uuid4()),
                        "command": "exec_close",
                        "params": {"execId": stream_id},
                    }
                else:
                    payload = {
                        "type": "command",
                        "requestId": str(uuid.uuid4()),
                        "command": "logs_unsubscribe",
                        "params": {"streamId": stream_id},
                    }
                try:
                    await self.channel_layer.send(agent_channel, {
                        "type": "ws.send",
                        "payload": payload,
                    })
                except Exception:
                    logger.exception("[ws] failed to forward stream cleanup kind=%s", kind)
            if kind == "exec":
                await self._close_console_session(
                    exec_id=stream_id,
                    exit_code=None,
                    reason="browser_disconnect",
                )
            command_router.remove_stream(stream_id)

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
            handled = await self._route_command_response(data)
            if not handled:
                await self._update_request_from_response(data)
            return

        if msg_type == "create_container_result":
            response = _command_response_from_create_result(data)
            if response.get("requestId"):
                handled = await self._route_command_response(response)
                if not handled:
                    await self._update_request_from_response(response)
            else:
                await self._update_container_workspace_from_create_result(data)
            return

        if msg_type == "command_progress":
            await self._route_command_progress(data)
            return

        if msg_type in ("log_chunk", "log_stream_end"):
            await self._route_log_stream_message(data)
            return

        if msg_type in ("exec_chunk", "exec_end"):
            await self._route_exec_stream_message(data)
            return

        if msg_type == "container_events":
            await self._handle_container_events(data)
            # 같은 메시지를 group broadcast 도 — admin/소유자 viewer 가
            # 실시간 이벤트를 받을 수 있게 (현 단계는 frontend 가 REST polling
            # 하지만 향후 WS push 전환 대비).
            data["server_id"] = self.server_id
            await self.channel_layer.group_send(
                self.group_name,
                {"type": "server_message", "data": data},
            )
            return

        if msg_type == "capacity_report":
            await self._handle_capacity_report(data)
            data["server_id"] = self.server_id
            await self.channel_layer.group_send(
                self.group_name,
                {"type": "server_message", "data": data},
            )
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
        if getattr(self, "_disconnected", False):
            return
        try:
            await self.send(text_data=json.dumps(event["data"]))
        except RuntimeError:
            logger.debug("[ws] dropped group message after websocket close")

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

        # transition: offline → online — record durably first, then push
        # so a browser that polls the REST endpoint immediately after a
        # missed websocket frame still finds the event in the log.
        await self._record_online_event(
            hostname=agent["hostname"],
            occurred_at_iso=agent["last_seen_at"],
            previous_offline_seconds=agent["previous_offline_seconds"],
        )
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

    @database_sync_to_async
    def _record_online_event(self, hostname: str, occurred_at_iso: str,
                             previous_offline_seconds: int | None) -> None:
        """Persist an online transition for the dashboard event log.

        Called only on the offline→online edge (`mark_notified_active`
        returned a fresh add). Mirrors the offline write in
        detect_offline_agents so the event-log panel can replay both
        sides of every flap.
        """
        from datetime import datetime

        from apps.agents.models import AgentStatusEvent

        try:
            occurred_at = datetime.fromisoformat(occurred_at_iso)
        except ValueError:
            from django.utils import timezone
            occurred_at = timezone.now()

        AgentStatusEvent.objects.create(
            agent_id=self.server_id,
            hostname=hostname,
            status=AgentStatusEvent.Status.ONLINE,
            occurred_at=occurred_at,
            previous_offline_seconds=previous_offline_seconds,
        )

    async def ws_send(self, event):
        """임의의 payload를 현재 WS로 그대로 전달 (직접 라우팅용)."""
        if getattr(self, "_disconnected", False):
            return
        try:
            await self.send(text_data=json.dumps(event["payload"]))
        except RuntimeError:
            logger.debug("[ws] dropped direct message after websocket close")

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

        # Long-running stream subscription 등록 / 해제 hook.
        # logs_subscribe: 이 requestId 가 곧 streamId 가 됨 → log_chunk/end 라우팅 키.
        # logs_unsubscribe: optimistic remove (agent 응답 기다리지 않음 — 실패해도
        #                   browser 가 이미 cleanup 의도).
        command_name = data.get("command")
        if command_name == "logs_subscribe":
            command_router.record_stream(request_id, self.channel_name, self.server_id, kind="logs")
        elif command_name == "logs_unsubscribe":
            stream_id = ((data.get("params") or {}).get("streamId")) or ""
            if stream_id:
                command_router.remove_stream(stream_id)
        elif command_name == "exec_open":
            # requestId 가 곧 execId (== streamId).
            command_router.record_stream(request_id, self.channel_name, self.server_id, kind="exec")
            # ConsoleSession audit row 즉시 생성. 응답 실패 시 _route_command_response 가
            # close_reason="open_failed" 로 갱신.
            await self._open_console_session(
                exec_id=request_id,
                params=data.get("params") or {},
            )
        elif command_name == "exec_close":
            exec_id = ((data.get("params") or {}).get("execId")) or ""
            if exec_id:
                command_router.remove_stream(exec_id)

        # Agent에게 원본 메시지 그대로 전달 (Agent는 requestId로 매칭)
        await self.channel_layer.send(agent_channel, {
            "type": "ws.send",
            "payload": data,
        })

    async def _route_log_stream_message(self, data: dict):
        """Agent의 log_chunk / log_stream_end 를 streamId 매핑된 Browser 로 forward.
        log_stream_end 도착 시 stream registry 도 정리."""
        stream_id = data.get("streamId")
        if not stream_id:
            return
        info = command_router.get_stream_info(stream_id)
        browser_channel = (info or {}).get("browser")
        if browser_channel:
            await self.channel_layer.send(browser_channel, {
                "type": "ws.send",
                "payload": data,
            })
        if data.get("type") == "log_stream_end":
            command_router.remove_stream(stream_id)

    async def _route_exec_stream_message(self, data: dict):
        """Agent의 exec_chunk / exec_end 를 execId(=streamId) 매핑된 Browser 로 forward.
        exec_end 도착 시 stream registry 정리 + ConsoleSession 닫기."""
        exec_id = data.get("execId")
        if not exec_id:
            return
        info = command_router.get_stream_info(exec_id)
        browser_channel = (info or {}).get("browser")
        if browser_channel:
            await self.channel_layer.send(browser_channel, {
                "type": "ws.send",
                "payload": data,
            })
        if data.get("type") == "exec_end":
            await self._close_console_session(
                exec_id=exec_id,
                exit_code=data.get("exitCode"),
                reason=str(data.get("reason") or "natural"),
            )
            command_router.remove_stream(exec_id)

    @database_sync_to_async
    def _open_console_session(self, exec_id: str, params: dict) -> None:
        """exec_open 발신 시점에 ConsoleSession audit row 생성.

        user/container 매핑 실패해도 routing 자체는 막지 않음 — 단지 audit 누락만
        발생. 권한 검사는 별도 (Browser 측에서 본인 컨테이너만 exec_open 발송).
        """
        from apps.containers.models import ConsoleSession, Container

        container_id = params.get("containerId") or ""
        if not container_id:
            return
        try:
            container = Container.objects.filter(
                container_id__startswith=container_id[:12],
            ).first()
        except Exception:
            container = None
        if not container:
            return

        user = self.scope.get("user")
        if user is None or not getattr(user, "is_authenticated", False):
            return

        cmd = params.get("cmd") or []
        if not isinstance(cmd, list):
            cmd = [str(cmd)]
        try:
            ConsoleSession.objects.create(
                user=user,
                container=container,
                exec_id=exec_id,
                cmd=cmd,
                user_param=str(params.get("user") or ""),
                tty=bool(params.get("tty", True)),
            )
        except Exception:
            logger.exception("[exec] failed to create ConsoleSession exec_id=%s", exec_id)

    @database_sync_to_async
    def _close_console_session(self, exec_id: str, exit_code, reason: str) -> None:
        """exec_end 또는 disconnect 시 ConsoleSession 종료 갱신. idempotent."""
        from django.utils import timezone

        from apps.containers.models import ConsoleSession

        try:
            sess = ConsoleSession.objects.filter(exec_id=exec_id).first()
        except Exception:
            sess = None
        if not sess or sess.closed_at:
            return
        now = timezone.now()
        sess.closed_at = now
        sess.duration_seconds = max(0, int((now - sess.opened_at).total_seconds()))
        if isinstance(exit_code, int):
            sess.exit_code = exit_code
        sess.close_reason = reason[:32]
        sess.save(update_fields=["closed_at", "duration_seconds", "exit_code", "close_reason"])

    async def _route_command_response(self, data: dict) -> bool:
        """Agent가 보낸 command_response를 요청 Browser로 라우팅.

        browser_channel 이 REST sentinel(`__rest__`) 이면 forward 대신 Redis
        에 저장 → REST endpoint 가 fetch_response 로 polling.
        `__api__` 는 dispatch-only(요청 승인 flow) — DB 갱신만 일어남.
        """
        request_id = data.get("requestId")
        if not request_id:
            logger.warning("[ws] command_response missing requestId")
            return False

        pending = command_router.pop_pending(request_id)
        if not pending:
            return False

        browser_channel = pending.get("browser")
        if not browser_channel:
            return False

        if browser_channel == command_router.REST_SENTINEL:
            command_router.store_response(request_id, data)
            return True

        from apps.agents.services.gpu_inventory import GPU_INVENTORY_SENTINEL

        if browser_channel == GPU_INVENTORY_SENTINEL:
            await self._apply_gpu_inventory_response(data, pending)
            return True

        if browser_channel.startswith("__"):
            return False

        await self.channel_layer.send(browser_channel, {
            "type": "ws.send",
            "payload": data,
        })

        # exec_open 실패 응답: stream registry 정리 + ConsoleSession close.
        # success 응답이면 stream 은 유지 (계속 exec_chunk routing 필요).
        if not data.get("success"):
            info = command_router.get_stream_info(request_id)
            if info and info.get("kind") == "exec":
                await self._close_console_session(
                    exec_id=request_id,
                    exit_code=None,
                    reason=str(data.get("error") or "open_failed")[:32],
                )
                command_router.remove_stream(request_id)

        return False

    @database_sync_to_async
    def _apply_gpu_inventory_response(self, data: dict, pending: dict):
        from apps.agents.services.gpu_inventory import apply_gpu_inventory

        agent_id = pending.get("server_id") or self.server_id
        try:
            apply_gpu_inventory(agent_id, data)
        except Exception:
            logger.exception("[gpu-inventory] Failed to apply response for agent %s", agent_id)

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
            if browser_channel and not str(browser_channel).startswith("__"):
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
        from apps.models_catalog.prepare import handle_prepare_progress

        request_id = data.get("requestId")
        if not request_id:
            return
        if handle_prepare_progress(data):
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
        from django.utils import timezone

        from apps.containers.models import Container, ContainerRequest
        from apps.containers.services.gpu_allocation import (
            activate_gpu_allocations_for_request,
            fail_reserved_gpu_allocations_for_request,
            release_gpu_allocations_for_container,
        )
        from apps.containers.services.workspace import (
            apply_workspace_metadata_from_response,
            delete_workspace_token_for_container,
            delete_workspace_token_for_request,
        )
        from apps.models_catalog.prepare import handle_prepare_response

        request_id = data.get("requestId")
        if not request_id:
            return
        if handle_prepare_response(data):
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
            limit_defaults = _container_limit_defaults_from_request(req, timezone.now())

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
                            **limit_defaults,
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
                                **limit_defaults,
                            },
                        )
                        if first_obj is None:
                            first_obj = obj
                if first_obj is not None and not req.target_container:
                    req.target_container = first_obj
                if req.target_container:
                    apply_workspace_metadata_from_response(
                        req,
                        req.target_container,
                        resp_data.get("workspace"),
                    )
                    if req.model_version_ids:
                        req.target_container.mounted_model_version_ids = list(req.model_version_ids)
                        req.target_container.save(update_fields=["mounted_model_version_ids", "last_seen"])
                    activate_gpu_allocations_for_request(req, req.target_container)

            # delete 요청: Container row 삭제
            elif req.action == "delete" and req.target_container:
                release_gpu_allocations_for_container(req.target_container)
                delete_workspace_token_for_container(req.target_container)
                req.target_container.delete()
                req.target_container = None

        else:
            req.status = "failed"
            req.progress_message = data.get("error", "unknown error")
            fail_reserved_gpu_allocations_for_request(req, req.progress_message)
            delete_workspace_token_for_request(req)

        req.deployment_log += f"\n--- command_response ---\n{json.dumps(data, ensure_ascii=False, indent=2)}"
        req.save(update_fields=[
            "status", "progress_percent", "progress_message",
            "target_container", "deployment_log", "updated_at",
        ])

    # ------------------------------------------------------------------
    # Redis 캐시
    # ------------------------------------------------------------------

    @database_sync_to_async
    def _handle_container_events(self, data: dict):
        """Agent의 container_events 메시지를 ContainerEvent 행으로 저장.

        - container_id 는 full(64) 또는 short(12) 둘 다 허용 — agent 가 full 송신
          하지만 backend Container.container_id 는 12자 short 가 truth.
        - 알 수 없는 container 는 silently skip (방금 생성됐지만 containers
          snapshot 아직 안 도착한 케이스).
        """
        from datetime import datetime
        from apps.containers.models import Container, ContainerEvent

        events = (data.get("data") or {}).get("events") or []
        if not isinstance(events, list) or not events:
            return

        # 이 agent 의 모든 컨테이너 한 번에 prefetch — N+1 방지.
        agent_id = self.server_id
        containers = {
            c.container_id: c
            for c in Container.objects.filter(agent_id=agent_id)
        }

        rows = []
        valid_kinds = set(ContainerEvent.Kind.values)
        for ev in events:
            if not isinstance(ev, dict):
                continue
            kind = ev.get("kind")
            if kind not in valid_kinds:
                logger.debug("[ws] unknown container_event kind=%s", kind)
                continue
            cid_full = ev.get("containerId") or ""
            cid_short = cid_full[:12]
            container = containers.get(cid_short)
            if container is None:
                # 신규 컨테이너 일 수 있음 (start 이벤트가 containers snapshot 보다 먼저).
                # 다음 snapshot 후 도착할 이벤트로 보강.
                continue
            ts_raw = ev.get("ts")
            try:
                # ISO8601 파싱. Z suffix Python 3.11+ 지원, 안전하게 +00:00 변환.
                ts = datetime.fromisoformat((ts_raw or "").replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                logger.warning("[ws] invalid container_event ts=%r kind=%s", ts_raw, kind)
                continue
            rows.append(ContainerEvent(
                container=container,
                agent_id=agent_id,
                ts=ts,
                kind=kind,
                exit_code=ev.get("exitCode") if isinstance(ev.get("exitCode"), int) else None,
                signal=str(ev.get("signal") or "")[:20],
                health_status=str(ev.get("healthStatus") or "")[:20],
                raw=ev,
            ))

        if rows:
            ContainerEvent.objects.bulk_create(rows, ignore_conflicts=False)

    @database_sync_to_async
    def _update_container_workspace_from_create_result(self, data: dict) -> None:
        from django.utils import timezone

        from apps.containers.models import Container

        resp_data = data.get("data") or {}
        container_id = _short_cid(resp_data.get("containerId", ""))
        workspace = resp_data.get("workspace") if isinstance(resp_data.get("workspace"), dict) else {}
        if not container_id or not workspace:
            return
        try:
            container = Container.objects.get(container_id=container_id)
        except Container.DoesNotExist:
            logger.warning("[ws] create_container_result without requestId has unknown container %s", container_id)
            return

        update_fields = []
        # New wire (`path`) supersedes the legacy `device` / `mountPoint`
        # the LVM-thin agent shipped. Both land in `workspace_device`.
        device = (
            workspace.get("path")
            or workspace.get("mountPoint")
            or workspace.get("device")
            or workspace.get("workspaceDevice")
        )
        if device:
            container.workspace_device = str(device)[:255]
            update_fields.append("workspace_device")
        project_id = _positive_int_or_none(
            workspace.get("projectId") or workspace.get("project_id")
        )
        if project_id:
            container.workspace_project_id = project_id
            update_fields.append("workspace_project_id")
        hard_gb = _positive_int_or_none(
            workspace.get("hardGb")
            or workspace.get("sizeGb")
            or workspace.get("size_gb")
        )
        if hard_gb and not container.workspace_gb_limit:
            container.workspace_gb_limit = hard_gb
            container.limit_updated_at = timezone.now()
            update_fields.extend(["workspace_gb_limit", "limit_updated_at"])
        if update_fields:
            update_fields.append("last_seen")
            container.save(update_fields=update_fields)

    @database_sync_to_async
    def _handle_capacity_report(self, data: dict) -> None:
        from django.utils import timezone

        from apps.agents.models import Agent

        try:
            agent = Agent.objects.get(id=self.server_id)
        except Agent.DoesNotExist:
            logger.warning("[ws] Agent %s not found for capacity_report", self.server_id)
            return

        body = data.get("data") or {}
        cpu = body.get("cpu") if isinstance(body.get("cpu"), dict) else {}
        memory = body.get("memory") if isinstance(body.get("memory"), dict) else {}
        disk = body.get("disk") if isinstance(body.get("disk"), dict) else {}
        quota = (
            disk.get("workspaceQuota")
            if isinstance(disk.get("workspaceQuota"), dict)
            else {}
        )
        # Backward compat: agents pre-quota-rework still ship `disk.lvm`.
        # We map the legacy thinPoolSizeGb into the new pool total when the
        # new field is absent so a partial fleet upgrade keeps capacity
        # rows populated until every agent ships the workspace-quota build.
        legacy_lvm = disk.get("lvm") if isinstance(disk.get("lvm"), dict) else {}
        network = body.get("network") if isinstance(body.get("network"), dict) else {}

        updates = {}
        _set_if_int(updates, "cpu_cores", cpu.get("cores"))
        _set_if_str(updates, "cpu_model", cpu.get("model"), max_length=255)
        _set_if_int(updates, "ram_total_mb", memory.get("totalMb"))
        _set_if_int(updates, "disk_total_gb", disk.get("rootTotalGb"))
        _set_if_str(updates, "filesystem", disk.get("filesystem"), max_length=64)
        _set_if_int(updates, "nic_speed_mbps", network.get("speedMbps"))

        quota_available = quota.get("available")
        legacy_available = legacy_lvm.get("available")
        if quota_available is False or (
            quota_available is None and legacy_available is False
        ):
            updates["workspace_pool_total_gb"] = None
            updates["workspace_pool_free_gb"] = None
            updates["workspace_pool_mount"] = ""
            updates["workspace_hard_enforcement"] = False
        else:
            total_gb = quota.get("totalGb")
            if total_gb is None:
                total_gb = legacy_lvm.get("thinPoolSizeGb")
            _set_if_int(updates, "workspace_pool_total_gb", total_gb)
            _set_if_int(updates, "workspace_pool_free_gb", quota.get("freeGb"))
            _set_if_str(
                updates, "workspace_pool_mount", quota.get("mountPath"), max_length=255
            )
            if "hardEnforced" in quota:
                updates["workspace_hard_enforcement"] = bool(quota.get("hardEnforced"))

        updates["capacity_updated_at"] = timezone.now()
        for field, value in updates.items():
            setattr(agent, field, value)
        agent.save(update_fields=list(updates))

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
                r.set(key, json.dumps(merged), ex=CONTAINER_METRICS_CACHE_TTL)
            else:
                return

            pipe = r.pipeline(transaction=False)
            pipe.sadd(ACTIVE_IDS_KEY, self.server_id)
            pipe.expire(ACTIVE_IDS_KEY, ACTIVE_IDS_TTL)
            pipe.execute()
        except Exception:
            logger.exception("[ws] Redis cache write failed for %s", self.server_id)

    HEARTBEAT_INTERVAL = 15  # seconds

    async def _send_heartbeat_loop(self):
        """Agent WS에 주기적 heartbeat 전송. Agent가 수신 침묵을 감지해 좀비
        세션 탈출(재접속)할 수 있게 한다. WS 끊기면 자연히 종료."""
        try:
            while True:
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)
                await self.send(text_data=json.dumps({"type": "heartbeat"}))
        except Exception:
            pass  # WS closed or cancelled — loop ends

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


def _set_if_int(updates: dict, field: str, value) -> None:
    if value is None:
        return
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return
    if parsed < 0:
        return
    updates[field] = parsed


def _set_if_str(updates: dict, field: str, value, *, max_length: int) -> None:
    if value is None:
        return
    updates[field] = str(value)[:max_length]


def _positive_int_or_none(value) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _container_limit_defaults_from_request(req, updated_at) -> dict:
    defaults = {
        "cpu_percent_limit": req.cpu_percent,
        "memory_mb_limit": req.memory_mb,
    }
    target_agent = getattr(req, "target_agent", None)
    # Only persist the per-container workspace quota when the agent host
    # actually enforces it. Without quota the limit would be a label that
    # nothing checks at runtime, which is worse than not showing one.
    if _agent_supports_workspace_quota(target_agent):
        defaults["workspace_gb_limit"] = req.workspace_gb
    if any(value is not None for value in defaults.values()):
        defaults["limit_updated_at"] = updated_at
    return defaults


def _agent_supports_workspace_quota(agent) -> bool:
    if agent is None:
        return False
    # pool 이 있어도 hard enforcement (prjquota 마운트) 가 아니면 quota 한도는
    # 실제로 강제되지 않는다. agent 도 prjquota 없는 mount 에 xfs_quota 를
    # 걸려다 create 가 실패하므로, 두 조건을 모두 요구한다.
    return bool(
        getattr(agent, "workspace_pool_total_gb", None)
        and getattr(agent, "workspace_hard_enforcement", False)
    )


def _command_response_from_create_result(data: dict) -> dict:
    resp_data = data.get("data") or {}
    success = data.get("success")
    if success is None:
        success = bool(resp_data.get("ok"))
    request_id = data.get("requestId") or resp_data.get("requestId")
    response = {
        "type": "command_response",
        "requestId": request_id,
        "success": success,
        "data": resp_data,
    }
    if data.get("error"):
        response["error"] = data.get("error")
    return response


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
        self._disconnected = False
        user = self.scope.get("user", AnonymousUser())
        if isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close(code=4001)
            return
        if self.scope.get("is_agent"):
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(GLOBAL_GROUP, self.channel_name)
        await self.accept(subprotocol=self.scope.get("ws_accept_subprotocol"))
        await self.send(text_data=json.dumps({
            "type": "connection",
            "channel": "global",
            "message": "Connected to global events channel.",
        }))

    async def disconnect(self, close_code):
        self._disconnected = True
        await self.channel_layer.group_discard(GLOBAL_GROUP, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # 클라이언트는 send 권한 없음. 무시.
        return

    async def global_event(self, event):
        if getattr(self, "_disconnected", False):
            return
        try:
            await self.send(text_data=json.dumps(event["payload"]))
        except RuntimeError:
            logger.debug("[ws] dropped global event after websocket close")
