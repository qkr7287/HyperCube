import logging
from urllib import error as urlerror
from urllib import parse, request as urlrequest

from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt

from .services.workspace import (
    WORKSPACE_SESSION_COOKIE,
    consume_workspace_ticket,
    get_workspace_plaintext_token,
    issue_workspace_session,
    resolve_workspace_container,
    validate_workspace_session,
    workspace_session_ttl_seconds,
    workspace_upstream_endpoint,
)

logger = logging.getLogger(__name__)

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


@csrf_exempt
def workspace_proxy(request, workspace_key: str, upstream_path: str = ""):
    container = resolve_workspace_container(workspace_key)
    if not container or not container.workspace_enabled:
        return HttpResponseForbidden("Workspace is not available")

    try:
        session_payload = _authenticate_workspace_request(request, container)
    except PermissionDenied:
        return HttpResponseForbidden("Invalid or expired workspace ticket")
    if session_payload is None:
        return HttpResponseForbidden("Workspace ticket or session required")

    if request.headers.get("Upgrade", "").lower() == "websocket":
        return HttpResponse(
            "Workspace websocket requests must be handled by the ASGI websocket route",
            status=426,
        )

    endpoint = workspace_upstream_endpoint(container)
    if endpoint is None:
        return HttpResponseBadRequest("Workspace upstream is not ready")

    upstream_token = get_workspace_plaintext_token(container)
    if not upstream_token:
        return HttpResponse("Workspace token is unavailable; restart or rotate the workspace", status=502)

    try:
        upstream_response = _fetch_upstream(request, container, upstream_token, endpoint)
    except urlerror.HTTPError as exc:
        response = HttpResponse(exc.read(), status=exc.code)
        _copy_response_headers(exc.headers, response)
        _maybe_set_session_cookie(request, response, container, session_payload)
        return response
    except Exception:
        logger.exception(
            "[workspace-proxy] upstream fetch failed container=%s agent=%s upstream=%s mode=%s",
            container.container_id,
            container.agent_id,
            endpoint.netloc,
            endpoint.mode,
        )
        return HttpResponse("Workspace upstream fetch failed", status=502)

    body = upstream_response.read()
    response = HttpResponse(body, status=upstream_response.status)
    _copy_response_headers(upstream_response.headers, response)
    _maybe_set_session_cookie(request, response, container, session_payload)
    return response


def _authenticate_workspace_request(request, container):
    ticket = request.GET.get("ticket")
    session_value = request.COOKIES.get(WORKSPACE_SESSION_COOKIE)

    if ticket:
        try:
            payload = consume_workspace_ticket(ticket, container)
            payload["_new_session"] = True
            return payload
        except PermissionDenied:
            # Ticket invalid or already consumed. JupyterLab routinely
            # redirects /lab → /lab/workspaces/auto-X?ticket=...&reset
            # carrying the original (now-spent) ticket in the query, so
            # if a valid session cookie was already set by the first
            # request we should accept that and continue. Re-raise only
            # if there is no session to fall back to.
            if not session_value:
                raise

    if not session_value:
        return None
    try:
        return validate_workspace_session(session_value, container)
    except PermissionDenied:
        return None


def _fetch_upstream(request, container, upstream_token: str, endpoint):
    query = request.GET.copy()
    query.pop("ticket", None)
    query["token"] = upstream_token

    upstream_url = parse.urlunparse((
        endpoint.scheme,
        endpoint.netloc,
        request.path,
        "",
        query.urlencode(),
        "",
    ))
    headers = _forward_headers(request)
    data = request.body if request.method not in ("GET", "HEAD") else None
    upstream_request = urlrequest.Request(
        upstream_url,
        data=data,
        headers=headers,
        method=request.method,
    )
    return urlrequest.urlopen(upstream_request, timeout=15)


def _forward_headers(request) -> dict:
    headers = {}
    for key, value in request.headers.items():
        lowered = key.lower()
        if lowered in HOP_BY_HOP_HEADERS or lowered in {"host", "cookie", "authorization"}:
            continue
        headers[key] = value
    if request.content_type:
        headers["Content-Type"] = request.content_type
    return headers


def _copy_response_headers(source_headers, response) -> None:
    for key, value in source_headers.items():
        lowered = key.lower()
        if lowered in HOP_BY_HOP_HEADERS:
            continue
        # Drop Content-Length only — Django recomputes it from the body it
        # sees. Content-Encoding must be forwarded: urllib.request does not
        # auto-decompress, so an upstream gzipped JS/CSS asset would be
        # delivered to the browser as raw gzip bytes with the encoding
        # header stripped, breaking gradio/JupyterLab static asset parsing
        # (SyntaxError: Invalid or unexpected token).
        if lowered == "content-length":
            continue
        response[key] = value


def _maybe_set_session_cookie(request, response, container, payload) -> None:
    if not payload.get("_new_session"):
        return
    session_value = issue_workspace_session(container, payload["uid"])
    response.set_cookie(
        WORKSPACE_SESSION_COOKIE,
        session_value,
        max_age=workspace_session_ttl_seconds(),
        httponly=True,
        samesite="Lax",
        path=container.workspace_base_url or request.path,
    )
