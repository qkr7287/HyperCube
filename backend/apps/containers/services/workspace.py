import json
import secrets
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from apps.common.redis_client import get_redis_client
from apps.containers.models import Container, ContainerRequest, ContainerTemplate
from apps.containers.services.policy import enforce_runtime_extension_policy

WORKSPACE_TICKET_SALT = "hypercube.workspace.ticket"
WORKSPACE_SESSION_SALT = "hypercube.workspace.session"
WORKSPACE_SESSION_COOKIE = "hc_workspace_session"


@dataclass(frozen=True)
class WorkspaceSecret:
    token_ref: str
    token: str
    expires_at: object


@dataclass(frozen=True)
class WorkspaceUpstreamEndpoint:
    scheme: str
    host: str
    port: int
    mode: str

    @property
    def netloc(self) -> str:
        return f"{self.host}:{self.port}"


def workspace_token_ttl_seconds() -> int:
    return int(getattr(settings, "WORKSPACE_TOKEN_TTL_SECONDS", 24 * 60 * 60))


def workspace_ticket_ttl_seconds() -> int:
    return int(getattr(settings, "WORKSPACE_TICKET_TTL_SECONDS", 60))


def workspace_session_ttl_seconds() -> int:
    return int(getattr(settings, "WORKSPACE_SESSION_TTL_SECONDS", 8 * 60 * 60))


def workspace_token_key(token_ref: str) -> str:
    return f"workspace:token:{token_ref}"


def workspace_ticket_key(nonce: str) -> str:
    return f"workspace:ticket:{nonce}"


def workspace_base_url_for_request(request: ContainerRequest) -> str:
    return f"/workspace/{request.id}/"


def workspace_key_for_container(container: Container) -> str:
    base_url = container.workspace_base_url or ""
    parts = [part for part in base_url.split("/") if part]
    if len(parts) >= 2 and parts[0] == "workspace":
        return parts[1]
    if container.created_via_request_id:
        return str(container.created_via_request_id)
    return container.container_id


def resolve_workspace_container(workspace_key: str) -> Container | None:
    qs = Container.objects.select_related(
        "agent",
        "requester",
        "created_via_request",
        "created_via_request__template",
    )
    container = qs.filter(container_id=workspace_key).first()
    if container:
        return container
    return qs.filter(created_via_request_id=workspace_key).first()


def workspace_upstream_endpoint(container: Container) -> WorkspaceUpstreamEndpoint | None:
    """Return the backend-reachable workspace upstream endpoint.

    Published host ports are valid for normal workspaces. For
    networkPolicy=internal_only workspaces, the agent deliberately does not
    publish a host port, so the backend must reach the container over a shared
    Docker internal network by container DNS name and internal port.
    """
    explicit = _endpoint_from_health(container)
    if explicit:
        return explicit

    internal_port = _positive_int(container.workspace_internal_port) or _positive_int(
        container.workspace_host_port
    )
    if _uses_internal_workspace_network(container):
        host = _docker_dns_name(container.name)
        if host and internal_port:
            return WorkspaceUpstreamEndpoint(
                scheme="http",
                host=host,
                port=internal_port,
                mode="docker-internal",
            )

    host_port = _positive_int(container.workspace_host_port)
    agent_ip = getattr(container.agent, "ip_address", "")
    if agent_ip and host_port:
        return WorkspaceUpstreamEndpoint(
            scheme="http",
            host=agent_ip,
            port=host_port,
            mode="agent-host-port",
        )
    return None


def prepare_workspace_secret_for_request(
    request: ContainerRequest,
    *,
    now=None,
) -> WorkspaceSecret | None:
    if not request.workspace_enabled_snapshot:
        return None
    now = now or timezone.now()
    token_ref = request.workspace_token_ref or secrets.token_urlsafe(24)
    token = secrets.token_urlsafe(48)

    # No Redis TTL: the workspace token lives as long as the container.
    # delete_workspace_token_for_container/_for_request remove it on
    # container deletion / request rejection.
    get_redis_client().set(workspace_token_key(token_ref), token)
    request.workspace_token_ref = token_ref
    request.workspace_token_expires_at = None
    request.deployment_phase = "create_container"
    request.save(
        update_fields=[
            "workspace_token_ref",
            "workspace_token_expires_at",
            "deployment_phase",
            "updated_at",
        ]
    )
    return WorkspaceSecret(token_ref=token_ref, token=token, expires_at=None)


def workspace_payload_for_request(
    request: ContainerRequest,
    secret: WorkspaceSecret | None,
) -> dict | None:
    if not request.workspace_enabled_snapshot:
        return None
    if not secret:
        raise ValidationError("Workspace secret is required for workspace create")
    template = request.template
    payload = {
        "kind": request.workspace_kind_snapshot or (template.workspace_kind if template else "jupyter"),
        "token": secret.token,
        "port": (template.workspace_port if template else None) or 8888,
        "baseUrl": workspace_base_url_for_request(request),
        "workdir": (template.default_workdir if template else "") or "/workspace",
    }
    # 요청 시 지정한 host port. 없으면 키를 생략 — 미적용 agent 는 기존
    # 동작(host port = internal port)을 유지한다 (하위호환).
    if request.workspace_host_port:
        payload["hostPort"] = request.workspace_host_port
    return payload


def apply_workspace_metadata_from_response(
    request: ContainerRequest,
    container: Container,
    response_workspace: dict | None,
    *,
    now=None,
) -> None:
    now = now or timezone.now()
    template = request.template
    response_workspace = response_workspace or {}
    limit_fields = _workspace_limit_fields_from_response(container, response_workspace, now)
    if not response_workspace:
        limit_fields.extend(
            field for field in _clear_unreported_workspace_limit(container) if field not in limit_fields
        )
    if not request.workspace_enabled_snapshot:
        if limit_fields:
            container.save(update_fields=limit_fields)
        return
    max_hours = request.requested_max_runtime_hours or (
        template.default_max_runtime_hours if template else None
    )
    # Lifecycle-bound model: token + runtime live as long as the container.
    # No wall-clock expiry is enforced; the field stays NULL so the UI does
    # not show a misleading "expires at" timestamp.
    runtime_expires_at = None

    container.workspace_enabled = True
    container.workspace_kind = (
        response_workspace.get("kind")
        or request.workspace_kind_snapshot
        or (template.workspace_kind if template else "")
    )
    container.workspace_internal_port = (
        response_workspace.get("internalPort")
        or (template.workspace_port if template else None)
    )
    container.workspace_host_port = response_workspace.get("hostPort")
    container.workspace_base_url = (
        response_workspace.get("baseUrl")
        or workspace_base_url_for_request(request)
    )
    container.workspace_health = _workspace_health_from_response(response_workspace)
    container.workspace_max_runtime_hours = max_hours
    container.workspace_runtime_expires_at = runtime_expires_at
    container.workspace_token_ref = request.workspace_token_ref
    container.workspace_token_expires_at = request.workspace_token_expires_at
    update_fields = [
        "workspace_enabled",
        "workspace_kind",
        "workspace_internal_port",
        "workspace_host_port",
        "workspace_base_url",
        "workspace_health",
        "workspace_max_runtime_hours",
        "workspace_runtime_expires_at",
        "workspace_token_ref",
        "workspace_token_expires_at",
        "last_seen",
    ]
    update_fields.extend(field for field in limit_fields if field not in update_fields)
    container.save(update_fields=update_fields)


def _workspace_limit_fields_from_response(
    container: Container,
    response_workspace: dict,
    now,
) -> list[str]:
    update_fields: list[str] = []
    # `path` is the new wire (mount path under /var/lib/hypercube/workspaces);
    # `device` / `mountPoint` are still accepted so a pre-rework agent push
    # does not blank the column during a partial fleet upgrade.
    device = (
        response_workspace.get("path")
        or response_workspace.get("mountPoint")
        or response_workspace.get("device")
        or response_workspace.get("workspaceDevice")
    )
    if device:
        container.workspace_device = str(device)[:255]
        update_fields.append("workspace_device")

    project_id = _positive_int(
        response_workspace.get("projectId")
        or response_workspace.get("project_id")
    )
    if project_id:
        container.workspace_project_id = project_id
        update_fields.append("workspace_project_id")

    hard_gb = _positive_int(
        response_workspace.get("hardGb")
        or response_workspace.get("sizeGb")
        or response_workspace.get("size_gb")
    )
    if hard_gb and not container.workspace_gb_limit:
        container.workspace_gb_limit = hard_gb
        container.limit_updated_at = now
        update_fields.extend(["workspace_gb_limit", "limit_updated_at"])

    if update_fields:
        update_fields.append("last_seen")
    return update_fields


def _clear_unreported_workspace_limit(container: Container) -> list[str]:
    update_fields: list[str] = []
    if container.workspace_gb_limit is not None:
        container.workspace_gb_limit = None
        update_fields.append("workspace_gb_limit")
    if container.workspace_device:
        container.workspace_device = None
        update_fields.append("workspace_device")
    if container.workspace_project_id is not None:
        container.workspace_project_id = None
        update_fields.append("workspace_project_id")
    return update_fields


def delete_workspace_token_ref(token_ref: str) -> None:
    if token_ref:
        get_redis_client().delete(workspace_token_key(token_ref))


def delete_workspace_token_for_request(request: ContainerRequest) -> None:
    delete_workspace_token_ref(request.workspace_token_ref)


def delete_workspace_token_for_container(container: Container) -> None:
    delete_workspace_token_ref(container.workspace_token_ref)


def get_workspace_plaintext_token(container: Container) -> str | None:
    if not container.workspace_token_ref:
        return None
    return get_redis_client().get(workspace_token_key(container.workspace_token_ref))


def issue_workspace_open_ticket(container: Container, user) -> str:
    _assert_workspace_owner(container, user)
    if not container.workspace_enabled:
        raise ValidationError("Workspace is not enabled for this container")
    if workspace_upstream_endpoint(container) is None:
        if _uses_internal_workspace_network(container):
            raise ValidationError(
                "Workspace is unreachable. The template uses network_policy="
                "internal_only, which only works when the backend and the "
                "agent share a Docker daemon. For a cross-host agent, recreate "
                "the container from a template with network_policy=none."
            )
        raise ValidationError("Workspace host port is not ready")

    nonce = secrets.token_urlsafe(24)
    payload = {
        "uid": str(user.id),
        "cid": container.container_id,
        "wk": workspace_key_for_container(container),
        "nonce": nonce,
    }
    ttl = workspace_ticket_ttl_seconds()
    created = get_redis_client().set(
        workspace_ticket_key(nonce),
        json.dumps(payload),
        nx=True,
        ex=ttl,
    )
    if not created:
        raise ValidationError("Could not reserve workspace ticket nonce")
    return signing.dumps(payload, salt=WORKSPACE_TICKET_SALT)


def consume_workspace_ticket(ticket: str, container: Container) -> dict:
    try:
        payload = signing.loads(
            ticket,
            salt=WORKSPACE_TICKET_SALT,
            max_age=workspace_ticket_ttl_seconds(),
        )
    except signing.BadSignature as exc:
        raise PermissionDenied("Invalid or expired workspace ticket") from exc

    _validate_workspace_payload(payload, container)
    nonce = payload.get("nonce") or ""
    key = workspace_ticket_key(nonce)
    raw = get_redis_client().get(key)
    if not raw:
        raise PermissionDenied("Invalid or expired workspace ticket")
    deleted = get_redis_client().delete(key)
    if not deleted:
        raise PermissionDenied("Workspace ticket has already been used")
    return payload


def issue_workspace_session(container: Container, user_id: str) -> str:
    payload = {
        "uid": str(user_id),
        "cid": container.container_id,
        "wk": workspace_key_for_container(container),
        "nonce": secrets.token_urlsafe(16),
    }
    return signing.dumps(payload, salt=WORKSPACE_SESSION_SALT)


def validate_workspace_session(session_value: str, container: Container) -> dict:
    try:
        payload = signing.loads(
            session_value,
            salt=WORKSPACE_SESSION_SALT,
            max_age=workspace_session_ttl_seconds(),
        )
    except signing.BadSignature as exc:
        raise PermissionDenied("Invalid workspace session") from exc
    _validate_workspace_payload(payload, container)
    return payload


def build_workspace_open_url(container: Container, ticket: str, path: str = "lab") -> str:
    base_url = container.workspace_base_url or f"/workspace/{workspace_key_for_container(container)}/"
    base_url = base_url if base_url.endswith("/") else f"{base_url}/"
    suffix = path.lstrip("/")
    return f"{base_url}{suffix}?{urlencode({'ticket': ticket})}"


def extend_workspace_runtime(container: Container, additional_hours: int):
    # Deprecated in the lifecycle-bound workspace model: the token has no
    # wall-clock TTL and lives until the container is deleted. The endpoint
    # is kept as a no-op so older clients do not break, but it intentionally
    # does not touch Redis TTL (which would re-introduce an expiry).
    if additional_hours <= 0:
        raise ValidationError("additional_hours must be positive")
    return container


def _validate_workspace_payload(payload: dict, container: Container) -> None:
    if payload.get("cid") != container.container_id:
        raise PermissionDenied("Workspace ticket does not match this container")
    if payload.get("wk") != workspace_key_for_container(container):
        raise PermissionDenied("Workspace ticket does not match this workspace")


def _assert_workspace_owner(container: Container, user) -> None:
    if getattr(user, "role", None) == "admin":
        return
    if container.requester_id != getattr(user, "id", None):
        raise PermissionDenied("Workspace is not owned by this user")


def _workspace_health_from_response(response_workspace: dict) -> dict:
    health = dict(response_workspace.get("health") or {})
    for key in (
        "networkPolicy",
        "networkName",
        "proxy",
        "upstream",
    ):
        if key in response_workspace and key not in health:
            health[key] = response_workspace[key]
    return health


def _endpoint_from_health(container: Container) -> WorkspaceUpstreamEndpoint | None:
    health = container.workspace_health or {}
    for key in ("upstream", "proxy"):
        spec = health.get(key)
        if not isinstance(spec, dict):
            continue
        host = _docker_dns_name(
            spec.get("host")
            or spec.get("hostname")
            or spec.get("dnsName")
        )
        port = _positive_int(spec.get("port") or spec.get("internalPort"))
        if host and port:
            return WorkspaceUpstreamEndpoint(
                scheme=str(spec.get("scheme") or "http"),
                host=host,
                port=port,
                mode=str(spec.get("mode") or key),
            )
    return None


def _uses_internal_workspace_network(container: Container) -> bool:
    request = getattr(container, "created_via_request", None)
    template = getattr(request, "template", None) if request else None
    return (
        getattr(template, "network_policy", None)
        == ContainerTemplate.NetworkPolicy.INTERNAL_ONLY
    )


def _docker_dns_name(value) -> str:
    return str(value or "").strip().lstrip("/")


def _positive_int(value) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None
