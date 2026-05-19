from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from http.cookies import SimpleCookie
from urllib import parse

import websockets
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.exceptions import PermissionDenied

from .services.workspace import (
    WORKSPACE_SESSION_COOKIE,
    consume_workspace_ticket,
    get_workspace_plaintext_token,
    resolve_workspace_container,
    validate_workspace_session,
    workspace_upstream_endpoint,
)

logger = logging.getLogger(__name__)

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "trailers",
    "transfer-encoding",
    "upgrade",
}
WEBSOCKET_HANDSHAKE_HEADERS = {
    "host",
    "cookie",
    "authorization",
    "origin",
    "sec-websocket-accept",
    "sec-websocket-extensions",
    "sec-websocket-key",
    "sec-websocket-protocol",
    "sec-websocket-version",
}
AUTH_SUBPROTOCOL_MARKERS = {"hypercube.jwt", "hypercube.agent"}


@dataclass(frozen=True)
class WorkspaceWebSocketContext:
    upstream_url: str
    container_id: str
    agent_id: str
    upstream: str
    upstream_mode: str


class WorkspaceWebSocketConsumer(AsyncWebsocketConsumer):
    """Proxy Jupyter/code-server workspace WebSockets to the agent host port."""

    async def connect(self):
        self.upstream = None
        self.upstream_reader_task = None
        workspace_key = self.scope["url_route"]["kwargs"]["workspace_key"]

        try:
            context = await _resolve_workspace_context(
                workspace_key=workspace_key,
                ticket=_query_param(self.scope, "ticket"),
                session_cookie=_cookie_value(self.scope, WORKSPACE_SESSION_COOKIE),
                path=self.scope.get("path") or "",
                raw_query=self.scope.get("query_string", b""),
            )
        except PermissionDenied:
            await self.close(code=4401)
            return
        except Exception:
            logger.exception("[workspace-ws] failed to resolve workspace=%s", workspace_key)
            await self.close(code=1011)
            return

        subprotocols = _upstream_subprotocols(self.scope.get("subprotocols") or [])
        headers = _upstream_headers(self.scope)

        try:
            connector = _connect_upstream(
                context.upstream_url,
                headers=headers,
                subprotocols=subprotocols,
            )
            self.upstream = await connector.__aenter__()
            self.upstream_connector = connector
        except Exception:
            logger.exception(
                "[workspace-ws] upstream connect failed container=%s agent=%s upstream=%s mode=%s",
                context.container_id,
                context.agent_id,
                context.upstream,
                context.upstream_mode,
            )
            await self.close(code=1011)
            return

        await self.accept(subprotocol=self.upstream.subprotocol)
        self.upstream_reader_task = asyncio.create_task(self._pump_upstream_to_client())

    async def disconnect(self, close_code):
        task = getattr(self, "upstream_reader_task", None)
        if task:
            task.cancel()
        upstream = getattr(self, "upstream", None)
        if upstream:
            await upstream.close()
        connector = getattr(self, "upstream_connector", None)
        if connector:
            await connector.__aexit__(None, None, None)

    async def receive(self, text_data=None, bytes_data=None):
        upstream = getattr(self, "upstream", None)
        if upstream is None:
            return
        try:
            if bytes_data is not None:
                await upstream.send(bytes_data)
            elif text_data is not None:
                await upstream.send(text_data)
        except Exception:
            logger.exception("[workspace-ws] browser-to-upstream send failed")
            await self.close(code=1011)

    async def _pump_upstream_to_client(self):
        try:
            async for message in self.upstream:
                if isinstance(message, bytes):
                    await self.send(bytes_data=message)
                else:
                    await self.send(text_data=message)
        except asyncio.CancelledError:
            raise
        except websockets.exceptions.ConnectionClosed as exc:
            await self.close(code=exc.code, reason=exc.reason)
        except Exception:
            logger.exception("[workspace-ws] upstream-to-browser pump failed")
            await self.close(code=1011)


@database_sync_to_async
def _resolve_workspace_context(
    *,
    workspace_key: str,
    ticket: str,
    session_cookie: str,
    path: str,
    raw_query: bytes,
) -> WorkspaceWebSocketContext:
    container = resolve_workspace_container(workspace_key)
    if not container or not container.workspace_enabled:
        raise PermissionDenied("Workspace is not available")

    if ticket:
        consume_workspace_ticket(ticket, container)
    elif session_cookie:
        validate_workspace_session(session_cookie, container)
    else:
        raise PermissionDenied("Workspace ticket or session required")

    if not container.agent:
        raise PermissionDenied("Workspace upstream is not ready")
    endpoint = workspace_upstream_endpoint(container)
    if endpoint is None:
        raise PermissionDenied("Workspace upstream is not ready")

    upstream_token = get_workspace_plaintext_token(container)
    if not upstream_token:
        raise PermissionDenied("Workspace token is unavailable")

    return WorkspaceWebSocketContext(
        upstream_url=_build_upstream_ws_url(
            netloc=endpoint.netloc,
            path=path,
            raw_query=raw_query,
            upstream_token=upstream_token,
        ),
        container_id=container.container_id,
        agent_id=str(container.agent_id),
        upstream=endpoint.netloc,
        upstream_mode=endpoint.mode,
    )


def _build_upstream_ws_url(
    *,
    netloc: str,
    path: str,
    raw_query: bytes,
    upstream_token: str,
) -> str:
    query_pairs = [
        (key, value)
        for key, value in parse.parse_qsl(
            raw_query.decode("utf-8", errors="ignore"),
            keep_blank_values=True,
        )
        if key != "ticket"
    ]
    query_pairs.append(("token", upstream_token))
    return parse.urlunparse((
        "ws",
        netloc,
        path,
        "",
        parse.urlencode(query_pairs),
        "",
    ))


def _query_param(scope: dict, name: str) -> str:
    params = parse.parse_qs(
        (scope.get("query_string") or b"").decode("utf-8", errors="ignore"),
        keep_blank_values=True,
    )
    values = params.get(name) or []
    return values[0] if values else ""


def _cookie_value(scope: dict, name: str) -> str:
    for key, value in scope.get("headers") or []:
        if key.lower() != b"cookie":
            continue
        cookie = SimpleCookie()
        cookie.load(value.decode("latin1"))
        morsel = cookie.get(name)
        return morsel.value if morsel else ""
    return ""


def _upstream_headers(scope: dict) -> list[tuple[str, str]]:
    headers: list[tuple[str, str]] = []
    for raw_key, raw_value in scope.get("headers") or []:
        key = raw_key.decode("latin1")
        lowered = key.lower()
        if lowered in HOP_BY_HOP_HEADERS or lowered in WEBSOCKET_HANDSHAKE_HEADERS:
            continue
        if lowered.startswith("sec-websocket-"):
            continue
        headers.append((key, raw_value.decode("latin1")))
    headers.append(("X-Forwarded-Proto", "ws"))
    return headers


def _upstream_subprotocols(subprotocols: list[str]) -> list[str] | None:
    forwarded: list[str] = []
    skip_next = False
    for protocol in subprotocols:
        if skip_next:
            skip_next = False
            continue
        if protocol in AUTH_SUBPROTOCOL_MARKERS:
            skip_next = True
            continue
        forwarded.append(protocol)
    return forwarded or None


def _connect_upstream(uri: str, *, headers: list[tuple[str, str]], subprotocols: list[str] | None):
    kwargs = {
        "subprotocols": subprotocols,
        "open_timeout": 10,
        "close_timeout": 5,
        "ping_interval": None,
    }
    try:
        return websockets.connect(uri, additional_headers=headers, proxy=None, **kwargs)
    except TypeError:
        try:
            return websockets.connect(uri, additional_headers=headers, **kwargs)
        except TypeError:
            return websockets.connect(uri, extra_headers=headers, **kwargs)
