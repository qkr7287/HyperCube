# HyperCube-agent Handoff: Resource Limits and LVM Thin Workspace

Date: 2026-05-16
Scope: `qkr7287/HyperCube-agent`
Core counterpart: HyperCube container resource limits PR 1-5
Tracking issue: https://github.com/qkr7287/HyperCube-agent/issues/16
Agent draft PR: https://github.com/qkr7287/HyperCube-agent/pull/17
Latest core reports:

```text
docs/test-reports/2026-05-16-container-resource-limits-final-gate-audit.md
docs/test-reports/2026-05-16-agent-pr17-file-audit.md
docs/test-reports/2026-05-16-agent-pr17-server63-runtime-sync.md
```

Core backend/frontend is ready on HyperCube `dev` for the current no-LVM
compatibility path. HyperCube-agent PR #17 exists as the deployable agent-side
implementation and has been synced into the server-63 dev bind-mounted runtime
for non-destructive validation. Full LVM thin workspace completion is still
blocked until the server-63 host/runtime LVM gate is resolved and the full
8-step `/workspace` validation passes.

## Current State

```text
repo: qkr7287/HyperCube-agent
branch: codex/resource-limits-lvm-agent
base: dev
head: 8d55d46855a0d51e123c0f0c2256face7dcd1e99
state: open draft
mergeable: true
changed files: 21
GitHub Actions: CI run 21 passed
tracking issue #16: open; no PERMISSION_OPTION=<1|2|3> reply in fetched comments
```

PR #17 implements:

- `capacity_report` on startup/reconnect/periodic timer and `request_capacity`.
- Docker `HostConfig` mapping for backend resource limits.
- LVM thin workspace create/rollback/delete/recovery.
- `sharedMounts` bind handling.
- `container_metrics.workspace` reporting.
- LVM thin-pool system/capacity metrics.
- `LVM_WORKSPACE_ENABLED=false` no-probe legacy guard.
- Existing GPU per-container multi-source contract preservation.

Remote PR-head file audit:

```text
report: docs/test-reports/2026-05-16-agent-pr17-file-audit.md
head: 8d55d46855a0d51e123c0f0c2256face7dcd1e99
CI run 25948355854 / run 21: completed, success
job 76281100630 Type check & build: success
fetched files: src/collectors/docker.ts, src/sync/delta.ts, src/config.ts,
src/workspace-recovery.ts, src/collectors/system.ts,
src/self-tests/resource-limits-lvm.ts, package.json, src/index.ts
```

The file audit confirms the PR head contains workspace metrics, system LVM
metrics, capacity-report wiring, disabled-LVM no-probe behavior, recovery
wiring, and self-test coverage.

Validation run from the remote-safe temp agent workspace:

```bash
npm run build
node dist/self-tests/resource-limits-lvm.js
npm run self-test:network-policy
```

Observed result: all passed.

Server-63 runtime sync has also been validated inside the dev agent container:

```bash
docker exec hypercube-agent-dev-63 sh -lc 'cd /app && npm run build && node dist/self-tests/resource-limits-lvm.js && node dist/self-tests/create-container-network-policy.js'
```

Observed result: build passed, `resource limits and LVM workspace self-test
passed`, and `create_container networkPolicy self-test passed`.

Runtime sync details:

```text
host: hc-dev-63
runtime path: /home/agics/ts/agent-dev
agent container: hypercube-agent-dev-63
backup: /home/agics/ts/agent-dev-pr17-sync-backup-20260516T010102Z.tgz
stale GPU collector backup: src/collectors/gpu-per-container.ts.pre-pr17-20260516T010343Z
stale GPU self-test backup: src/self-tests/gpu-per-container.ts.pre-pr17-stale-20260516T010420Z
```

After restart, backend Agent capacity for `server_63_dev` updated:

```json
{
  "hostname": "server_63_dev",
  "cpu_cores": 12,
  "cpu_model": "Intel(R) Core(TM) i5-10400 CPU @ 2.90GHz",
  "ram_total_mb": 15897,
  "disk_total_gb": 457,
  "lvm_pool_size_gb": null,
  "nic_speed_mbps": null,
  "filesystem": "overlay",
  "target_users": 4,
  "safety_margin": 0.8,
  "capacity_updated_at": "2026-05-16 01:04:44.080208+00:00"
}
```

This confirms capacity reporting works in the synced runtime. It also confirms
server 63 remains in legacy/no-LVM mode because `lvm_pool_size_gb` is still
`null`.

## Core References

```text
docs/container-resource-limits-기획.ko.html
docs/agent-integration-lvm-thin-spec.ko.html
docs/agent-payload-contract.md
docs/agent-protocol.md
docs/runbooks/lvm-thin-workspace-host-setup.md
docs/runbooks/lvm-thin-workspace-preflight.sh
docs/runbooks/lvm-thin-workspace-full-validation.md
docs/test-reports/2026-05-16-container-resource-limits-final-gate-audit.md
docs/test-reports/2026-05-16-agent-pr17-draft-status.md
docs/test-reports/2026-05-16-agent-pr17-file-audit.md
docs/test-reports/2026-05-16-agent-pr17-server63-runtime-sync.md
progress.md
```

Do not change HyperCube core from the agent issue unless the backend-agent
contract proves impossible. Core-side contract, docs, migrations, backend tests,
frontend tests, and Playwright E2E are already pushed.

## Current Blocker

Latest server_63_dev preflight command:

```bash
cd /home/agics/ts/HyperCube
bash docs/runbooks/lvm-thin-workspace-preflight.sh hypercube-agent-dev-63 hc-backend
```

Observed blocker evidence:

```text
exit code: 1
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
server_63_dev lvm_pool_size_gb=None
```

## Required Agent/Operator Decisions

Record the chosen path in issue #16 before attempting full LVM validation:

```text
PERMISSION_OPTION=<1|2|3>
LVM_DEVICE=<approved block device or existing vg/thin pool>
NFS_DATASETS=<NFS export or explicit shared-mount policy change>
NFS_MODELS=<NFS export or explicit shared-mount policy change>
```

Permission options:

- `1`: privileged agent container with host LVM tooling available in the agent runtime.
- `2`: host-side helper/service invoked by the agent.
- `3`: no LVM on this host yet; agent must report `disk.lvm.available=false`.

Do not use `/dev/sdb` or `/dev/sdb2` for LVM unless an operator explicitly
confirms that the existing ARCHIVE data may be destroyed or has been migrated.

## Contract Checklist

### capacity_report

Agent must send:

```json
{
  "type": "capacity_report",
  "agentId": "...",
  "timestamp": "...",
  "data": {
    "cpu": { "cores": 24, "model": "...", "architecture": "x64" },
    "memory": { "totalMb": 262144 },
    "disk": {
      "rootTotalGb": 3700,
      "rootUsedGb": 120,
      "filesystem": "ext4",
      "lvm": {
        "available": true,
        "vg": "vg0",
        "thinPool": "thin_pool",
        "thinPoolSizeGb": 3000,
        "thinPoolUsedGb": 432,
        "usedPct": 14.4,
        "alert": "ok"
      }
    },
    "network": { "primaryInterface": "eth0", "speedMbps": 10000 }
  }
}
```

Fallback rules:

- LVM missing/unavailable: `disk.lvm.available=false`.
- `LVM_WORKSPACE_ENABLED=false`: `disk.lvm.available=false` without probing `lvs`.
- Do not fabricate `thinPoolSizeGb`; backend treats missing LVM capacity as
  legacy mode and omits LVM `workspace` fields from create payloads.

### create_container

Backend sends lower camel case:

```json
{
  "hostConfig": {
    "memory": 17179869184,
    "memorySwap": 17179869184,
    "cpuQuota": 400000,
    "cpuPeriod": 100000,
    "oomKillDisable": false
  },
  "workspace": {
    "sizeGb": 100,
    "mountTarget": "/workspace"
  },
  "sharedMounts": [
    { "source": "/mnt/datasets", "target": "/datasets", "readOnly": true },
    { "source": "/mnt/models", "target": "/models", "readOnly": true }
  ]
}
```

Agent maps these into Dockerode `HostConfig`, provisions the LVM thin volume,
binds the mounted workspace to `/workspace`, and keeps existing Jupyter
workspace metadata (`kind`, `token`, `port`, `baseUrl`, `workdir`) intact.

### create_container_result

When LVM is used, agent returns workspace metadata so core can persist
`Container.workspace_device`:

```json
{
  "workspace": {
    "id": "05eddec05865",
    "device": "/dev/vg0/cid_05eddec05865",
    "mountPoint": "/var/lib/hypercube/workspaces/05eddec05865",
    "mountTarget": "/workspace",
    "sizeGb": 100
  }
}
```

### container_metrics

For LVM-managed containers, add:

```json
{
  "workspace": {
    "device": "/dev/vg0/cid_05eddec05865",
    "mountPoint": "/var/lib/hypercube/workspaces/05eddec05865",
    "sizeGb": 100,
    "usedGb": 2,
    "availableGb": 98,
    "usedPct": 2
  }
}
```

Core UI already displays workspace quota and usage when this arrives.

## Validation Required on server_63_dev

Minimum read-only preflight from the HyperCube core checkout:

```bash
bash docs/runbooks/lvm-thin-workspace-preflight.sh hypercube-agent-dev-63 hc-backend
```

This script checks host LVM tools, shared mount roots, agent-runtime LVM tools,
`lvs --units g`, and backend Agent capacity rows. It exits non-zero until the
host and agent runtime are ready for LVM mode.

Expected before backend LVM mode can be verified:

```text
lvcreate and lvs exist on the host and in the agent runtime
lvs --units g shows the configured thin pool
shared NFS mount roots exist
workspace root exists
capacity_report includes disk.lvm.available=true and thinPoolSizeGb
```

Full 8-step integration gate:

1. Agent sends `capacity_report` with `disk.lvm.available=true`.
2. Backend Agent row updates `lvm_pool_size_gb`.
3. User creates PyTorch Jupyter request with resource recommendation prefill.
4. Backend sends `create_container` with `hostConfig`, LVM `workspace.sizeGb`,
   LVM `workspace.mountTarget`, and `sharedMounts`.
5. Agent runs `lvcreate`, `mkfs`, and `mount`.
6. Agent reports `create_container_result.workspace.device`.
7. Backend stores `Container.workspace_device`.
8. Container `df /workspace` shows the requested LVM thin size.

Core-side tests already green:

```text
backend full suite: 111 tests OK
backend targeted re-audit: 7 tests OK
frontend vitest: 57 passed
frontend svelte-check: 0 errors, 193 existing warnings
frontend e2e: 3 passed
backend mypy: not applicable; no mypy config/dependency and hc-backend has no mypy module
```

## Regression Rules

- Existing `create_container` requests without LVM `params.workspace.sizeGb` and
  `params.workspace.mountTarget` must keep working.
- Existing Jupyter workspace metadata in `params.workspace` must keep working.
- Existing hosts without LVM capacity must stay in legacy mode.
- If `LVM_WORKSPACE_ENABLED=false`, capacity reporting must stay in legacy mode
  and not advertise LVM availability.
- Existing `update_container` / `update-limits` behavior must keep working.
- Existing GPU allocation, model mount, network policy, logs, exec, and metrics
  behavior must not regress.
- Do not add runtime downloads in the agent hot path.
