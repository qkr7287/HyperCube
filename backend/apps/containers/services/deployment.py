import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.exceptions import ValidationError

from apps.common import command_router
from apps.containers.models import ContainerRequest

from .gpu_allocation import fail_reserved_gpu_allocations_for_request, gpu_payload_for_request
from .workspace import (
    delete_workspace_token_for_request,
    prepare_workspace_secret_for_request,
    workspace_payload_for_request,
)

logger = logging.getLogger(__name__)

CPU_PERIOD_US = 100_000
BYTES_PER_MB = 1024 * 1024
DEFAULT_SHARED_MOUNTS = [
    {"source": "/mnt/datasets", "target": "/datasets", "readOnly": True},
    {"source": "/mnt/models", "target": "/models", "readOnly": True},
]


def dispatch_request_to_agent(req_obj: ContainerRequest, workspace_secret=None) -> bool:
    agent_channel = command_router.get_agent_channel(str(req_obj.target_agent_id))
    if not agent_channel:
        req_obj.status = ContainerRequest.Status.FAILED
        req_obj.progress_message = "Agent offline; cannot dispatch request"
        req_obj.save(update_fields=["status", "progress_message", "updated_at"])
        fail_reserved_gpu_allocations_for_request(req_obj, "agent offline before dispatch")
        delete_workspace_token_for_request(req_obj)
        return False

    try:
        payload = build_agent_payload(req_obj, workspace_secret=workspace_secret)
    except Exception as exc:
        req_obj.status = ContainerRequest.Status.FAILED
        req_obj.progress_message = str(exc)
        req_obj.save(update_fields=["status", "progress_message", "updated_at"])
        fail_reserved_gpu_allocations_for_request(req_obj, str(exc))
        delete_workspace_token_for_request(req_obj)
        return False

    command_router.record_pending(str(req_obj.id), "__api__", str(req_obj.target_agent_id))

    try:
        layer = get_channel_layer()
        async_to_sync(layer.send)(agent_channel, {
            "type": "ws.send",
            "payload": payload,
        })
        logger.info(
            "[dispatch] sent %s to agent %s (req %s)",
            payload["command"],
            req_obj.target_agent_id,
            req_obj.id,
        )
        return True
    except Exception:
        logger.exception("[dispatch] failed to send request %s", req_obj.id)
        req_obj.status = ContainerRequest.Status.FAILED
        req_obj.progress_message = "Agent command dispatch failed"
        req_obj.save(update_fields=["status", "progress_message", "updated_at"])
        fail_reserved_gpu_allocations_for_request(req_obj, "agent dispatch failed")
        delete_workspace_token_for_request(req_obj)
        return False


def build_agent_payload(req_obj: ContainerRequest, workspace_secret=None) -> dict:
    if req_obj.action == ContainerRequest.Action.CREATE:
        return _build_create_payload(req_obj, workspace_secret=workspace_secret)
    if req_obj.action == ContainerRequest.Action.DELETE:
        return {
            "type": "command",
            "requestId": str(req_obj.id),
            "command": "delete_container",
            "params": {
                "containerId": req_obj.target_container_id or "",
                "force": True,
            },
        }
    raise ValidationError("Unsupported request action")


def _build_create_payload(req_obj: ContainerRequest, workspace_secret=None) -> dict:
    tpl = req_obj.template
    if tpl and tpl.kind == "compose":
        return {
            "type": "command",
            "requestId": str(req_obj.id),
            "command": "compose_up",
            "params": {
                "projectName": req_obj.custom_name or f"hc-{str(req_obj.id)[:8]}",
                "composeYaml": tpl.compose_yaml,
                "env": req_obj.custom_env or {},
            },
        }

    ports = [p for p in (req_obj.custom_ports or []) if isinstance(p, dict)]
    params = {
        "image": req_obj.selected_image or (tpl.image if tpl else ""),
        "name": req_obj.custom_name or f"hc-{str(req_obj.id)[:8]}",
        "env": req_obj.custom_env or {},
        "ports": ports,
        "volumes": list(tpl.default_volumes) if tpl else [],
        "gpus": gpu_payload_for_request(req_obj),
    }

    host_config = _host_config_payload(req_obj)
    if host_config:
        params["hostConfig"] = host_config

    model_mounts = _model_mounts_payload(req_obj)
    if model_mounts:
        params["modelMounts"] = model_mounts

    quota_workspace = _workspace_quota_payload(req_obj)
    workspace_meta = None
    if req_obj.workspace_enabled_snapshot:
        if workspace_secret is None:
            workspace_secret = prepare_workspace_secret_for_request(req_obj)
        workspace_meta = workspace_payload_for_request(req_obj, workspace_secret)
        params["networkPolicy"] = tpl.network_policy if tpl else "none"

    if workspace_meta or quota_workspace:
        workspace_payload = {}
        if workspace_meta:
            workspace_payload.update(workspace_meta)
        if quota_workspace:
            workspace_payload.update(quota_workspace)
        params["workspace"] = workspace_payload

    if quota_workspace:
        params["sharedMounts"] = list(DEFAULT_SHARED_MOUNTS)

    return {
        "type": "command",
        "requestId": str(req_obj.id),
        "command": "create_container",
        "params": params,
    }


def _model_mounts_payload(req_obj: ContainerRequest) -> list[dict]:
    if not req_obj.model_version_ids:
        return []
    from apps.models_catalog.prepare import model_mounts_payload_for_request

    return model_mounts_payload_for_request(req_obj)


def _host_config_payload(req_obj: ContainerRequest) -> dict:
    payload = {}
    if req_obj.memory_mb is not None:
        memory_bytes = int(req_obj.memory_mb) * BYTES_PER_MB
        payload["memory"] = memory_bytes
        payload["memorySwap"] = memory_bytes
    if req_obj.cpu_percent is not None:
        payload["cpuQuota"] = int(req_obj.cpu_percent) * 1000
        payload["cpuPeriod"] = CPU_PERIOD_US
    if payload:
        payload["oomKillDisable"] = False
    return payload


def _workspace_quota_payload(req_obj: ContainerRequest) -> dict | None:
    """Per-container workspace quota slice (XFS prjquota on a loop file).

    Returns None when either the requester did not pick a workspace size or
    the target host has no quota pool reported, in which case the agent
    skips the prjquota allocation and the container only sees the model
    mounts / shared mounts the operator already published.
    """
    if not req_obj.workspace_gb:
        return None
    agent = req_obj.target_agent
    if not agent or not getattr(agent, "workspace_pool_total_gb", None):
        return None
    return {
        "hardGb": int(req_obj.workspace_gb),
        "mountTarget": "/workspace",
    }
