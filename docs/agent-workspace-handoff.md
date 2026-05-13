# HyperCube-agent Handoff: Workspace/Jupyter Runtime

Scope: HyperCube-agent repository only. Do not implement this in HyperCube core.

Core now sends optional `create_container.params.workspace` when a template has
`workspace_enabled=true`:

```json
{
  "workspace": {
    "kind": "jupyter",
    "token": "<plaintext secret for the container only>",
    "port": 8888,
    "baseUrl": "/workspace/<container-request-id>/",
    "workdir": "/workspace"
  },
  "networkPolicy": "internal_only"
}
```

Agent requirements:

- Inject `JUPYTER_TOKEN`, `JUPYTER_PORT`, `JUPYTER_BASE_URL`, and
  `JUPYTER_WORKDIR` or equivalent image-specific settings.
- Bind the workspace internal port to a host port reachable from the HyperCube
  backend host.
- Return `data.workspace.hostPort`, `internalPort`, `baseUrl`, `kind`, and
  optional `health` in the `create_container` success response.
- Do not log the plaintext token.
- Enforce `networkPolicy=internal_only`, or return a clear `not_enforced`
  result before the request is marked production-ready.
- Existing create_container behavior must remain unchanged when `workspace` is
  absent.

Core validation still requires a real backend-to-agent reachability smoke test:
`backend -> agent.ip_address:workspace_host_port`.
