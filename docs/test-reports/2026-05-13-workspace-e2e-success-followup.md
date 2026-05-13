# Workspace E2E Success Follow-up - 2026-05-13

## Source Report

`docs/test-reports/2026-05-13-workspace-e2e-success.md` records all runtime
workspace acceptance checks as PASS:

- `hc-ml-internal` is `internal=true`.
- Workspace container is not attached to the external bridge network.
- `/user/workspaces` opens JupyterLab.
- Jupyter terminal `nvidia-smi` shows RTX 3060 Ti.
- PyTorch CUDA is available.
- The actual model bind-mount directory is read-only.
- Workspace egress to `1.1.1.1:443` is blocked.

## Follow-ups Applied

The report listed two remaining follow-ups. Both are now handled in the core
repo:

1. Backend permanent network join:
   - `docker-compose.dev.yml`
   - `docker-compose.prod.yml`
   - `deploy/docker-compose.yml`

   `hc-backend` now joins the external `hc-ml-internal` network in addition to
   the normal `hc-network`.

2. Read-only mount smoke correction:
   - `docs/runbooks/ml-image-airgap-build.md`

   The runbook now checks
   `touch /workspace/models/<model-dir>/write-test`, not the writable parent
   directory `/workspace/models`.

## Validation

Local static validation:

```text
git diff --check: PASS
docker compose -f docker-compose.yml -f docker-compose.dev.yml config --quiet: PASS
docker compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet: PASS
docker compose -f deploy/docker-compose.yml config --quiet: PASS
```

Runtime validation remains the already recorded server-63 result in the source
report. This local session cannot directly SSH to `hc-dev-63` because `ssh` is
sandbox-denied.

## Remaining Operational Note

Because `hc-ml-internal` is declared as an external network, the target host
must have it before backend startup or recreate:

```bash
docker network inspect hc-ml-internal >/dev/null 2>&1 || \
  docker network create --internal hc-ml-internal
```
