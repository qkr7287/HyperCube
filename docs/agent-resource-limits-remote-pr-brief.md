# HyperCube-agent Remote PR Brief: Resource Limits + LVM Thin Workspace

Date: 2026-05-16
Scope: `qkr7287/HyperCube-agent`
Core counterpart: HyperCube `dev` container resource limits implementation
Tracking issue: `qkr7287/HyperCube-agent#16`

## Current State

HyperCube core is implemented and pushed. The remaining blocker is the agent
remote/deployable implementation plus server-63 LVM/legacy-mode decision.

Latest verified core `dev` head when this brief was written:

```text
4603f1f7aed2f4c16e2f0807121014ece17e649f docs(containers): refresh agent lvm verification progress
```

Latest inspected HyperCube-agent remote `dev` head:

```text
10d14ab225d296e458a77a2ab166f8e0a89adfe7 feat: support GPU ML workspace agent runtime
```

## Remote `dev` Gaps To Patch

The following were inspected on remote `qkr7287/HyperCube-agent` `dev` and are
not yet deployable for the core PR 3 payload contract:

```text
src/workspace-lvm.ts @ dev -> 404 Not Found
src/collectors/capacity.ts @ dev -> 404 Not Found
```

Remote `src/handlers/create-container.ts` exists but still lacks:

- `params.hostConfig` input.
- Mapping `params.hostConfig.memory` -> Docker `HostConfig.Memory`.
- Mapping `params.hostConfig.memorySwap` -> Docker `HostConfig.MemorySwap`.
- Mapping `params.hostConfig.cpuQuota` -> Docker `HostConfig.CpuQuota`.
- Mapping `params.hostConfig.cpuPeriod` -> Docker `HostConfig.CpuPeriod`.
- Mapping `params.hostConfig.oomKillDisable` -> Docker
  `HostConfig.OomKillDisable`.
- `workspace.sizeGb` / `workspace.mountTarget` LVM provisioning.
- `sharedMounts` read-only/read-write bind handling.
- `create_container_result.data.workspace.device` / `mountPoint` / `sizeGb`
  reporting.
- rollback/cleanup when Docker create/start/network validation fails after LVM
  provisioning.

Remote `src/types/index.ts`, `src/config.ts`, `src/index.ts`,
`src/collectors/docker.ts`, and `src/handlers/delete-container.ts` also need the
matching capacity/workspace types, config, periodic `capacity_report`, workspace
metrics, and workspace cleanup hooks.

## Minimum File Set

Implement the agent PR against current remote `dev`, not the stale local
`origin/dev` in the Windows checkout.

Expected file set:

```text
Dockerfile
Dockerfile.dev
docker-compose.dev.yml
docker-compose.yml
package.json
src/config.ts
src/index.ts
src/types/index.ts
src/collectors/capacity.ts
src/collectors/docker.ts
src/handlers/create-container.ts
src/handlers/delete-container.ts
src/handlers/index.ts
src/sync/delta.ts
src/utils/command-runner.ts
src/workspace-lvm.ts
src/workspace-recovery.ts
src/self-tests/resource-limits-lvm.ts
```

Optional if not already on the target branch:

```text
src/self-tests/create-container-network-policy.ts
```

## Required Behavior

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

Graceful fallback:

- LVM missing/unavailable: `disk.lvm.available=false`.
- `LVM_WORKSPACE_ENABLED=false`: `disk.lvm.available=false` without probing
  `lvs`, even if LVM exists on the host.
- Do not fabricate `thinPoolSizeGb`.

### create_container

Agent must consume backend `params.hostConfig` and map it into Dockerode
`HostConfig`:

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

Agent must consume optional LVM workspace payload:

```json
{
  "workspace": {
    "sizeGb": 100,
    "mountTarget": "/workspace"
  }
}
```

Agent must consume optional shared mounts:

```json
{
  "sharedMounts": [
    { "source": "/mnt/datasets", "target": "/datasets", "readOnly": true },
    { "source": "/mnt/models", "target": "/models", "readOnly": true }
  ]
}
```

Expected create result workspace fields when LVM is used:

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

## Disabled-LVM Guard Patch

A temp copy verification proved this guard and self-test pass:

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

Add a self-test beside the graceful fallback test proving:

```text
LVM_WORKSPACE_ENABLED=false
fake runner has valid lvs response
capacity_report.data.disk.lvm.available=false
runner did not call lvs
```

Temp verification evidence already recorded in:

```text
docs/test-reports/2026-05-16-agent-disabled-lvm-guard-temp-verification.md
HyperCube-agent issue #16 comment 4461583774
```

## Validation Commands

Local agent PR validation:

```bash
npm install --ignore-scripts --no-audit --no-fund
npm run build
node dist/self-tests/resource-limits-lvm.js
npm run self-test:network-policy
npm run self-test:gpu-per-container
```

Server-63 preflight after deploy:

```bash
cd /home/agics/ts/HyperCube
bash docs/runbooks/lvm-thin-workspace-preflight.sh hypercube-agent-dev-63 hc-backend
```

Full proof after preflight is green:

```text
docs/runbooks/lvm-thin-workspace-full-validation.md
```

## Current Blockers

Do not claim the full HyperCube resource-limit/LVM objective complete until:

1. Agent/ops replies on `qkr7287/HyperCube-agent#16` with
   `PERMISSION_OPTION=<1|2|3>`.
2. The agent PR is merged/pushed to a deployable ref.
3. The deployable agent reports either real LVM capacity or explicit legacy
   mode (`disk.lvm.available=false`).
4. server 63 passes preflight for real LVM mode, or option 3 legacy mode is
   explicitly selected and verified.
5. The full 8-step LVM validation succeeds for real LVM mode.
