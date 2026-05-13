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

    model_mounts = _model_mounts_payload(req_obj)
    if model_mounts:
        params["modelMounts"] = model_mounts

    if req_obj.workspace_enabled_snapshot:
        if workspace_secret is None:
            workspace_secret = prepare_workspace_secret_for_request(req_obj)
        params["workspace"] = workspace_payload_for_request(req_obj, workspace_secret)
        params["networkPolicy"] = tpl.network_policy if tpl else "none"

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
