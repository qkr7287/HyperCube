# GPU ML Workspace Validation

Use this after HyperCube-agent issue #14 is deployed to `server_63_dev` and
`server_16_dev`.

2026-05-13 operator report: issue #14 is deployed to
`hypercube-agent-dev-63` and `hypercube-agent-dev-16`; both agent containers
passed typecheck/build plus loopback `params.assets[0].sha256`
`backend_stream` tests. This file is now the core/server validation checklist.

## Server 63 Commands

Run from the local workstation:

```bash
ssh hc-dev-63 "cd /home/agics/ts/HyperCube && docker compose -f docker-compose.yml -f docker-compose.dev.yml --env-file .env.dev up -d --no-build --force-recreate backend"
ssh hc-dev-63 "cd /home/agics/ts/HyperCube && docker compose -f docker-compose.yml -f docker-compose.dev.yml --env-file .env.dev exec -T backend python manage.py migrate"
ssh hc-dev-63 "cd /home/agics/ts/HyperCube && docker compose -f docker-compose.yml -f docker-compose.dev.yml --env-file .env.dev exec -T backend python manage.py check"
ssh hc-dev-63 "cd /home/agics/ts/HyperCube && docker compose -f docker-compose.yml -f docker-compose.dev.yml --env-file .env.dev exec -T backend python manage.py test apps.common apps.agents apps.containers apps.models_catalog --verbosity 2"
ssh hc-dev-63 "cd /home/agics/ts/HyperCube && docker compose -f docker-compose.yml -f docker-compose.dev.yml --env-file .env.dev exec -T backend python manage.py shell -c \"from apps.agents.tasks import refresh_gpu_inventories; print(refresh_gpu_inventories())\""
```

Expected:

- Backend stays healthy.
- Targeted tests pass.
- `server_63_dev` has one available RTX 3060 Ti full GPU slice.
- `server_16_dev` stays approved and does not crash without `nvidia-smi`.

## P0 Happy Path

1. Open `http://192.168.0.63:3000/`.
2. Confirm `/user/models` has a tiny available model version.
3. Open `/user`, create a request from the modal:
   - template: `PyTorch Jupyter GPU Workspace`
   - agent: `server_63_dev`
   - GPU: RTX 3060 Ti full slice
   - model: tiny model version
4. Approve the request as admin.
5. Confirm the request moves:
   - `prepare_model_assets`
   - `create_container`
   - `deployed`
6. Open `/user/workspaces` and launch the workspace.

Expected:

- Agent accepts `params.assets[0].sha256`.
- `ModelPrepareJob.status == ready`.
- `ModelVersionCache.status == ready`.
- `create_container.params.modelMounts[]` includes a read-only mount.
- Workspace opens for the owner.

## Runtime Checks

Inside the Jupyter workspace:

```bash
nvidia-smi
ls -la /workspace/models
```

Expected:

- `nvidia-smi` shows the RTX 3060 Ti.
- The selected model is visible under `/workspace/models/...`.
- The model mount is read-only.

On `server_63_dev`, identify the deployed workspace container and verify the
agent-enforced network policy:

```bash
CID=<deployed-workspace-container-id-or-name>

docker inspect "$CID" \
  --format 'network_mode={{.HostConfig.NetworkMode}} networks={{json .NetworkSettings.Networks}}'
docker network inspect hc-ml-internal --format 'internal={{.Internal}}'
docker network inspect hc-ml-internal \
  --format '{{range .Containers}}{{.Name}}{{"\n"}}{{end}}'
```

Expected:

- `hc-ml-internal` exists and reports `internal=true`.
- The workspace container is attached only to the expected internal workspace
  network, not to the normal external bridge network.
- `hc-backend` is also attached to `hc-ml-internal`; backend uses Docker DNS
  `<workspace-container-name>:<internal-port>` for internal-only workspaces.

Run mount and egress smoke checks from the target host:

```bash
docker exec "$CID" sh -lc 'MODEL_DIR="$(find /workspace/models -mindepth 1 -maxdepth 1 -type d | head -n 1)"; test -n "$MODEL_DIR"; touch "$MODEL_DIR/write-test" && echo UNEXPECTED_WRITE || echo READ_ONLY_OK'
docker exec -i "$CID" python - <<'PY'
import socket

s = socket.socket()
s.settimeout(5)
try:
    s.connect(("1.1.1.1", 443))
except Exception as exc:
    print("EGRESS_BLOCKED", type(exc).__name__, str(exc))
else:
    raise SystemExit("UNEXPECTED_EGRESS_ALLOWED")
PY
```

Expected:

- The write test prints `READ_ONLY_OK`.
- The egress check prints `EGRESS_BLOCKED`.

## P1/P2 Checks

Run a second request with the same model:

- Expected: cache is reused; prepare is skipped or very short.

Try `server_16_dev` with the ML template:

- Expected: no selectable GPU slice or a 400 response; no backend or agent crash.

Check logs:

```bash
ssh hc-dev-63 "cd /home/agics/ts/HyperCube && docker compose -f docker-compose.yml -f docker-compose.dev.yml --env-file .env.dev logs --since=30m backend | grep -Ei 'token=|agent_|eyJ|fatal|traceback|exception|model-prepare|workspace'"
ssh hc-dev-63 "docker logs hypercube-agent-dev-63 --since 30m | grep -Ei 'token=|agent_|eyJ|fatal|traceback|exception|prepare_model_assets|create_container|modelMounts|workspace'"
```

Expected:

- No fatal/import crash.
- No token in query-string logs.
- `prepare_model_assets` progress and response are visible.
- `create_container` receives `workspace`, `gpus`, and `modelMounts`.

## Track 5 Policy Checks

Run after migrations:

```bash
ssh hc-dev-63 "cd /home/agics/ts/HyperCube && docker compose -f docker-compose.yml -f docker-compose.dev.yml --env-file .env.dev exec -T backend python manage.py test apps.containers.tests.test_policy apps.containers.tests.test_gpu_allocation --verbosity 2"
```

Expected:

- Shared GPU request is rejected while `HC_GPU_SHARED_MODE_ENABLED=false`.
- Template/default runtime and explicit requested runtime cannot exceed
  `HC_MAX_WORKSPACE_RUNTIME_HOURS`.
- Approval rejects users who already exceed active workspace/GPU quotas.
- Shared GPU allocation only succeeds in tests where shared mode and
  per-slice `allow_shared` are both explicitly enabled.

## WebSocket Token Hygiene

After the backend/frontend refresh, open the browser devtools Network tab and
reload `/user`.

Expected:

- Browser WebSocket URLs do not contain `?token=`.
- Browser WebSocket handshakes use the `hypercube.jwt` subprotocol.
- Global events, server monitoring, console, and log-tail sockets still connect.
- Backend logs do not print JWTs or agent tokens from browser WebSocket URLs.
