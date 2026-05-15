# HyperCube-agent Handoff: Resource Limits and LVM Thin Workspace

Date: 2026-05-16
Scope: `qkr7287/HyperCube-agent`
Core counterpart: HyperCube container resource limits PR 1-5
Tracking issue: https://github.com/qkr7287/HyperCube-agent/issues/16

Core backend/frontend is ready on HyperCube `dev` for the current no-LVM
compatibility path. Full LVM thin workspace completion is still blocked until
the agent/ops runtime gate below is resolved.

Current verified core HEAD before this handoff refresh:

```text
688a5eb2ca268a7c8c343dd5e4b0e1e35aa2b87f docs(containers): record refreshed lvm agent handoff
```

Core implementation baseline:

```text
7454fdd feat(containers): add resource limits and workspace quotas
```

Check the current HyperCube core HEAD before validating:

```bash
gh api repos/qkr7287/HyperCube/git/ref/heads/dev --jq '.object.sha'
```

Core validation and gate reports:

```text
docs/test-reports/2026-05-15-container-resource-limits-core-validation.md
docs/test-reports/2026-05-16-container-resource-limits-completion-audit-addendum.md
docs/test-reports/2026-05-16-container-resource-limits-final-gate-audit.md
docs/runbooks/lvm-thin-workspace-preflight.sh
docs/runbooks/lvm-thin-workspace-host-setup.md
docs/runbooks/lvm-thin-workspace-full-validation.md
progress.md
```

Spec documents in the core repo:

- Container resource limits plan:
  `https://raw.githubusercontent.com/qkr7287/HyperCube/dev/docs/container-resource-limits-%EA%B8%B0%ED%9A%8D.ko.html`
- `docs/agent-integration-lvm-thin-spec.ko.html`
- `docs/agent-payload-contract.md`
- `docs/agent-protocol.md`

Do not change HyperCube core from this issue unless the backend-agent contract
proves impossible. Core-side contract, docs, migrations, backend tests, frontend
tests, and Playwright E2E are already pushed.

## Current Blocker

Backend is accepting capacity reports, but the currently deployed agents report
no LVM thin pool:

```text
agent-register-smoke-after-migrate cpu_cores=None ram_total_mb=None lvm_pool_size_gb=None capacity_updated_at=None
server_16_dev cpu_cores=12 ram_total_mb=39760 lvm_pool_size_gb=None capacity_updated_at=2026-05-15T16:03:40.813793+00:00
server_63_dev cpu_cores=12 ram_total_mb=15897 lvm_pool_size_gb=None capacity_updated_at=2026-05-15T16:03:41.076664+00:00
```

Latest server_63_dev preflight rerun:

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
server_63_dev 12 15897 None 2026-05-15 16:03:41.076664+00:00
```

`/home/agics/ts/agent-dev/src` has LVM workspace scaffolding, but full
validation is still blocked until the host has `lvm2`, a configured thin pool,
the shared dataset/model mounts, workspace root, and a chosen agent permission
option.

## Local Agent Code Audit

The local `C:\Users\agics\Desktop\workspace\01. git\HyperCube-agent` checkout
was inspected from the core session. It is a dirty worktree, so do not treat it
as deployed state, but these local self-tests passed:

```text
npm run self-test:lvm-workspace -> passed
npm run self-test:network-policy -> passed
npm run self-test:gpu-per-container -> passed
```

One option-3 acceptance item remains for the agent code:

```text
If LVM_WORKSPACE_ENABLED=false, capacity_report.data.disk.lvm.available must be false without probing lvs.
```

Patch expectation in `src/workspace-lvm.ts`:

```ts
if (!config.enabled) {
  return {
    available: false,
    vg: config.volumeGroup,
    thinPool: config.thinPool,
    thinPoolSizeGb: null,
    thinPoolUsedGb: null,
    usedPct: null,
    alert: null,
  };
}
```

Add a self-test next to `assertCapacityReportGracefulLvmFallback()` that proves
`LVM_WORKSPACE_ENABLED=false` wins even if a fake runner would otherwise return
a valid `lvs` result.

## Required Agent Work

### 1. capacity_report

Implement agent -> backend host capacity telemetry per
`docs/agent-integration-lvm-thin-spec.ko.html` section 3.

Required shape:

```json
{
  "type": "capacity_report",
  "agentId": "053ce574-c2b3-474b-a8ca-a34ec43f9d52",
  "timestamp": "2026-05-15T15:00:00Z",
  "data": {
    "cpu": {
      "cores": 24,
      "model": "Intel Xeon Gold 6248 @ 2.50GHz",
      "architecture": "x64"
    },
    "memory": {
      "totalMb": 262144
    },
    "disk": {
      "rootTotalGb": 3700,
      "rootUsedGb": 120,
      "filesystem": "ext4",
      "lvm": {
        "available": true,
        "vg": "vg0",
        "thinPool": "thin_pool",
        "thinPoolSizeGb": 3000,
        "thinPoolUsedGb": 432
      }
    },
    "network": {
      "primaryInterface": "eth0",
      "speedMbps": 10000
    }
  }
}
```

Fallback rules:

- If LVM tools or pool are unavailable, send `disk.lvm.available=false`.
- If LVM is intentionally disabled by config, send `disk.lvm.available=false`
  even if `lvs` would succeed.
- Do not fabricate `thinPoolSizeGb`; backend treats missing LVM capacity as
  legacy mode and omits LVM `workspace` fields from create payloads.

### 2. create_container HostConfig

Read backend `create_container.params.hostConfig` and map it into Dockerode
`HostConfig` while preserving existing network, GPU, restart, env, model mount,
and workspace/Jupyter behavior.

Backend sends lower camel case:

```json
{
  "hostConfig": {
    "memory": 17179869184,
    "memorySwap": 17179869184,
    "cpuQuota": 400000,
    "cpuPeriod": 100000,
    "oomKillDisable": false
  }
}
```

Agent maps to Docker names:

```ts
const hostConfig = {
  Memory: params.hostConfig.memory,
  MemorySwap: params.hostConfig.memorySwap,
  CpuQuota: params.hostConfig.cpuQuota,
  CpuPeriod: params.hostConfig.cpuPeriod,
  OomKillDisable: params.hostConfig.oomKillDisable
};
```

### 3. LVM Thin Workspace

When backend sends LVM fields in `params.workspace`, allocate a per-container
thin volume and mount it into the container at `/workspace`.

Backend shape when LVM is available:

```json
{
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

Compatibility note: existing Jupyter workspace metadata may also be present in
`params.workspace` (`kind`, `token`, `port`, `baseUrl`, `workdir`). Do not drop
that metadata when adding the LVM bind mount.

Expected agent behavior:

- Create thin LV: `lvcreate -V {sizeGb}G -T vg0/thin_pool -n cid_{shortId}`.
- Format if needed: `mkfs.ext4 /dev/vg0/cid_{shortId}`.
- Mount to host path: `/var/lib/hypercube/workspaces/{shortId}`.
- Bind host workspace mount to container `params.workspace.mountTarget`.
- Bind `sharedMounts` as read-only where `readOnly=true`.
- Roll back LV, mount, and container if any create step fails.
- On container remove, unmount and `lvremove` the corresponding volume when safe.

### 4. create_container_result Workspace Metadata

Return workspace metadata so core can persist `Container.workspace_device`.

```json
{
  "type": "create_container_result",
  "requestId": "request-uuid",
  "data": {
    "ok": true,
    "containerId": "05eddec05865...",
    "workspace": {
      "device": "/dev/vg0/cid_05eddec05865",
      "mountPoint": "/var/lib/hypercube/workspaces/05eddec05865",
      "sizeGb": 100
    }
  }
}
```

Core accepts both legacy `command_response` and `create_container_result`.

### 5. container_metrics Workspace Field

Extend per-container metrics with workspace usage.

```json
{
  "type": "container_metrics",
  "data": {
    "containerId": "05eddec05865",
    "workspace": {
      "device": "/dev/vg0/cid_05eddec05865",
      "sizeGb": 100,
      "usedGb": 12,
      "availableGb": 88,
      "usedPct": 12.0
    }
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

Manual equivalent:

```bash
command -v lvcreate
command -v lvs
lvs --units g
docker exec hypercube-agent-dev-63 sh -lc 'command -v lvcreate; command -v lvs'
docker exec hypercube-agent-dev-63 sh -lc 'lvs --units g'
test -d /mnt/datasets
test -d /mnt/models
test -d /var/lib/hypercube/workspaces
```

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
