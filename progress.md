# HyperCube Progress

## Current Work - 2026-05-16

### Container Resource Limits / LVM Thin Workspace

Core repo status: implemented, validated, committed, and pushed to `dev`.
The overall objective is still not complete because the real server-63 LVM thin
workspace path has not passed end-to-end validation.

Core implementation baseline:

```text
7454fdd feat(containers): add resource limits and workspace quotas
```

Recent docs/status commits before this progress refresh:

```text
eb4af51 docs: refresh final gate audit with agent file audit
e550e85 docs: record agent pr17 file audit in progress
402f8dc docs: record agent pr17 file audit
3b48784 docs: refresh lvm host setup runbook for pr17 gate
cca0ab6 docs: update progress with final gate audit refresh
d7675f6 docs: refresh final gate audit after agent runtime sync
2ae54c6 docs: refresh agent lvm handoff after runtime sync
112fdd9 docs: update resource limit progress after agent runtime sync
73963b4 docs: record agent pr17 server63 runtime sync
```

Latest agent-side status:

```text
HyperCube-agent PR: https://github.com/qkr7287/HyperCube-agent/pull/17
state: open draft
branch: codex/resource-limits-lvm-agent
head: 8d55d46855a0d51e123c0f0c2256face7dcd1e99
base: qkr7287/HyperCube-agent:dev @ 10d14ab225d296e458a77a2ab166f8e0a89adfe7
mergeable: true
changed files: 21
GitHub Actions: CI run 21 passed for PR #17 head
tracking issue: qkr7287/HyperCube-agent#16, title refreshed to server-63 runtime gate
latest fetched comments: no PERMISSION_OPTION=<1|2|3> reply yet
```

PR #17 implements the missing deployable agent-side contract:

- `capacity_report` on startup/reconnect/periodic timer and `request_capacity`.
- Docker `HostConfig` mapping for backend CPU/memory limits.
- LVM thin workspace create/rollback/delete/recovery.
- `sharedMounts` bind handling.
- `container_metrics.workspace` reporting.
- LVM thin-pool system/capacity metrics.
- `LVM_WORKSPACE_ENABLED=false` no-probe legacy guard.
- Current GPU per-container multi-source contract preservation.

Agent PR validation from the remote-safe temp workspace:

```bash
npm run build
node dist/self-tests/resource-limits-lvm.js
npm run self-test:network-policy
```

Observed result: all passed.

Agent PR #17 file-level audit on the remote PR head:

```text
head: 8d55d46855a0d51e123c0f0c2256face7dcd1e99
CI run 25948355854 / run 21: completed, success
job 76281100630 Type check & build: success
fetched files: src/collectors/docker.ts, src/sync/delta.ts, src/config.ts,
src/workspace-recovery.ts, src/collectors/system.ts,
src/self-tests/resource-limits-lvm.ts, package.json, src/index.ts
```

Server-63 runtime sync status:

```text
runtime path: /home/agics/ts/agent-dev
agent container: hypercube-agent-dev-63
backup: /home/agics/ts/agent-dev-pr17-sync-backup-20260516T010102Z.tgz
latest runtime validation: build + resource-limits-lvm self-test + network-policy self-test passed
agent restart: reconnected to backend
capacity_updated_at: 2026-05-16 01:04:44.080208+00:00
lvm_pool_size_gb: None
```

Implemented core scope:

- Template resource weights and min floors.
- Agent capacity columns and `capacity_report` handling.
- Host-capacity resource recommendation helper and REST endpoint.
- ContainerRequest CPU/memory/workspace fields and validation.
- Container CPU/memory/workspace limit snapshots and workspace device fields.
- Agent create payload `hostConfig`, LVM `workspace`, and `sharedMounts`.
- Workspace metadata persistence from create result.
- Legacy no-LVM mode keeps existing Jupyter workspace metadata while omitting
  only LVM `sizeGb`, `mountTarget`, and `sharedMounts`.
- Legacy no-LVM create responses keep CPU/memory limits but do not persist an
  unenforced `workspace_gb_limit` unless the agent returns concrete workspace
  metadata.
- Live server-63 dry-run confirms `server_63_dev` keeps `hostConfig` but omits
  LVM `sizeGb`, `mountTarget`, and `sharedMounts` while `lvm_pool_size_gb=None`.
- Request modal resource-limit UI and recommendation prefill.
- KPI cards and trend charts with quota/denominator display.
- API, agent protocol, and payload contract docs.

Validation recorded for `server_63_dev`:

```text
backend: python manage.py test -> 111 tests OK
backend targeted: apps.containers.tests.test_workspace_limit_metadata apps.common.tests.test_legacy_workspace_limits -> 2 tests OK
backend targeted PR3 legacy/no-LVM hostConfig path -> 5 tests OK
backend targeted re-audit: apps.containers.tests.test_recommend apps.containers.tests.test_deployment.AgentCreatePayloadTests apps.common.tests.test_legacy_workspace_limits.LegacyWorkspaceLimitConsumerTests -> 7 tests OK
backend mypy: not applicable; no mypy config/dependency and hc-backend has no mypy module
frontend: npm test -- --run -> 57 tests passed
frontend: npm run check -> 0 errors, 193 warnings
frontend: npm run e2e -> 3 passed
migrations: agents.0008, containers.0010, containers.0011 applied
agent PR #17 CI: passed
server-63 agent runtime sync: build + resource-limits-lvm self-test + network-policy self-test passed
```

Latest LVM preflight from `/home/agics/ts/HyperCube`:

```bash
bash docs/runbooks/lvm-thin-workspace-preflight.sh hypercube-agent-dev-63 hc-backend
```

Current result:

```text
PREFLIGHT_EXIT:1
FAIL host command 'lvcreate' is missing
FAIL host command 'lvs' is missing
FAIL host command 'lvremove' is missing
FAIL /mnt/datasets is missing
FAIL /mnt/models is missing
FAIL /var/lib/hypercube/workspaces is missing
FAIL host lvs unavailable; cannot inspect thin pool
OK   agent container 'hypercube-agent-dev-63' exists
FAIL agent command 'lvcreate' is missing
FAIL agent command 'lvs' is missing
OK   agent command 'mkfs.ext4' -> /usr/sbin/mkfs.ext4
OK   agent command 'mount' -> /usr/bin/mount
OK   agent command 'umount' -> /usr/bin/umount
FAIL agent command 'lvremove' is missing
FAIL agent lvs command failed
sh: 1: lvs: not found
agent-register-smoke-after-migrate None None None None
server_16_dev 12 39760 None 2026-05-16 01:03:45.206653+00:00
server_63_dev 12 15897 None 2026-05-16 01:04:44.080208+00:00
FAIL LVM thin workspace host preflight failed
```

Core references:

- `docs/test-reports/2026-05-15-container-resource-limits-core-validation.md`
- `docs/test-reports/2026-05-15-container-resource-limits-completion-audit.md`
- `docs/test-reports/2026-05-15-container-resource-limits-legacy-workspace-quota-fix.md`
- `docs/test-reports/2026-05-16-container-resource-limits-completion-audit-addendum.md`
- `docs/test-reports/2026-05-16-container-resource-limits-final-gate-audit.md`
- `docs/test-reports/2026-05-16-hypercube-agent-remote-dev-audit.md`
- `docs/test-reports/2026-05-16-agent-disabled-lvm-guard-temp-verification.md`
- `docs/test-reports/2026-05-16-agent-pr17-draft-status.md`
- `docs/test-reports/2026-05-16-agent-pr17-server63-runtime-sync.md`
- `docs/test-reports/2026-05-16-agent-pr17-file-audit.md`
- `docs/agent-resource-limits-remote-pr-brief.md`
- `docs/agent-lvm-thin-handoff.md`
- `docs/runbooks/lvm-thin-workspace-host-setup.md`
- `docs/runbooks/lvm-thin-workspace-preflight.sh`
- `docs/runbooks/lvm-thin-workspace-full-validation.md`
- HyperCube-agent tracking issue: `qkr7287/HyperCube-agent#16`
- HyperCube-agent draft PR: `qkr7287/HyperCube-agent#17`

Remaining blocker:

- Full LVM thin workspace creation is not yet proven end-to-end.
- HyperCube-agent PR #17 is open as draft; server-63 runtime has been synced and
  self-tested, but the PR is not merged.
- HyperCube-agent issue #16 still has no `PERMISSION_OPTION=<1|2|3>` reply.
- Current `server_63_dev` host and `hypercube-agent-dev-63` both lack
  `lvs/lvcreate/lvremove`; `lvm2`/thin pool setup is not present.
- `/mnt/datasets`, `/mnt/models`, and `/var/lib/hypercube/workspaces` are not
  present on `server_63_dev`, so the shared-mount/workspace-root part cannot be
  validated yet.
- Current Agent rows report `lvm_pool_size_gb=None`, so backend stays in legacy
  mode and omits LVM `workspace` payloads for those agents.

Next completion gate:

1. Agent/ops replies on HyperCube-agent #16 with `PERMISSION_OPTION=<1|2|3>`,
   `LVM_DEVICE`, `NFS_DATASETS`, and `NFS_MODELS`.
2. If LVM mode is selected, prepare server 63 with `lvm2`, an approved thin
   pool, `/mnt/datasets`, `/mnt/models`, and `/var/lib/hypercube/workspaces`.
3. Re-run `docs/runbooks/lvm-thin-workspace-preflight.sh` until it exits 0.
4. Review/merge/deploy HyperCube-agent PR #17 through the chosen permission path.
5. Run `docs/runbooks/lvm-thin-workspace-full-validation.md` for the real LVM
   8-step validation path.
6. Submit a new PyTorch Jupyter request and confirm backend sends `hostConfig`,
   `workspace`, and `sharedMounts` when LVM is available.
7. Confirm agent creates/mounts the LVM thin volume.
8. Confirm backend stores `Container.workspace_device`.
9. Confirm container `df /workspace` shows the requested workspace quota.
