# Workspace E2E Follow-up Report - 2026-05-13

## Context

Previous report: `docs/test-reports/2026-05-13-workspace-e2e.md`.

The workspace container reached `deployed` with:

- `networkPolicy=internal_only` enforced by the agent.
- `hc-ml-internal` Docker network reporting `internal=true`.
- External egress to `1.1.1.1:443` blocked.
- Container-side `nvidia-smi` passing with RTX 3060 Ti visible.
- Actual model directory bind mount confirmed read-only.
- `/user/workspaces` showing the running workspace card.

The remaining failure was Jupyter UI load:

```text
502 Workspace upstream fetch failed
```

Root cause: backend proxy used `agent.ip_address:workspace_host_port`, but
internal-only workspaces are not host-published. The deployed container had
`Ports={"8888/tcp": null}` while DB metadata still had
`workspace_host_port=8888`.

## Core Changes Applied

Backend workspace upstream selection now supports internal-only workspaces:

- `backend/apps/containers/services/workspace.py`
  - Added `workspace_upstream_endpoint()`.
  - For `networkPolicy=internal_only`, upstream becomes
    `<container name>:<workspace_internal_port>`.
  - Normal non-internal workspaces still use `agent.ip:workspace_host_port`.
  - `open` ticket issuing no longer requires `workspace_host_port` when an
    internal Docker DNS endpoint is available.
- `backend/apps/containers/workspace_proxy.py`
  - HTTP proxy now uses the selected upstream endpoint.
- `backend/apps/containers/workspace_ws.py`
  - Jupyter WebSocket proxy now uses the same selected upstream endpoint.
- `backend/apps/containers/tests/test_workspaces.py`
  - Added coverage for internal-only Docker DNS endpoint selection.
  - Added coverage for opening an internal-only workspace without host port.
- `backend/apps/containers/tests/test_workspace_ws.py`
  - Updated helper test for netloc-based WebSocket upstream URL building.

Docs updated:

- `docs/gpu-ml-workspace-validation.md`
  - Added `hc-backend` join check for `hc-ml-internal`.
  - Corrected read-only smoke to write inside the actual model directory.
- `docs/agent-protocol.md`
  - Documented host-port behavior for normal workspaces and Docker DNS behavior
    for `internal_only`.
- `docs/agent-payload-contract.md`
  - Clarified that `hostPort` can be null/omitted for `internal_only`.

## Operational Requirement Before Retest

`hc-backend` must join the same internal Docker network as the workspace
container:

```bash
docker network connect hc-ml-internal hc-backend || true
```

Then verify from the backend container:

```bash
docker exec hc-backend python - <<'PY'
import socket
s = socket.create_connection(("e2e-netpolicy", 8888), 5)
s.close()
print("BACKEND_TO_WORKSPACE_OK")
PY
```

Use the actual workspace container name if it is not `e2e-netpolicy`.

## Retest Target

After deploying this core change and joining `hc-backend` to
`hc-ml-internal`, retry:

1. `/user/workspaces` -> `Jupyter open`.
2. `/workspace/<request-id>/lab?ticket=...` should no longer return 502.
3. JupyterLab UI should load.
4. Kernel WebSocket should connect.
5. Jupyter terminal `nvidia-smi` should pass.
6. Touch inside `/workspace/models/<model-dir>/` should fail read-only.
