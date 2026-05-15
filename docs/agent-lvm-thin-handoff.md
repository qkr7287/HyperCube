# HyperCube-agent Handoff: Resource Limits and LVM Thin Workspace

Date: 2026-05-15
Scope: `qkr7287/HyperCube-agent`
Core counterpart: HyperCube container resource limits PR 1-5
Tracking issue: https://github.com/qkr7287/HyperCube-agent/issues/16

Core backend/frontend is ready on HyperCube `dev`.

Core commit verified:

```text
c0bb50f2839d21022197ebcf7861cdbc17388050
```

Core validation report:

```text
docs/test-reports/2026-05-15-container-resource-limits-core-validation.md
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
server_63_dev cpu_cores=12 ram_total_mb=15897 lvm_pool_size_gb=None capacity_updated_at=2026-05-15T09:12:49Z
server_16_dev cpu_cores=12 ram_total_mb=39760 lvm_pool_size_gb=None capacity_updated_at=2026-05-15T09:03:40Z
```

Runtime evidence on `hypercube-agent-dev-63`:

```bash
docker exec hypercube-agent-dev-63 sh -lc 'command -v lvcreate || true; command -v lvs || true; lvs 2>&1 | head -20 || true'
```

Observed:

```text
bash: line 1: lvs: command not found
```

Source scan on `server_63_dev` currently finds no LVM/resource-limit contract
implementation:

```bash
grep -R "capacity_report\|hostConfig\|sharedMounts\|lvcreate\|workspaceDevice\|thinPool" -n /home/agics/ts/agent-dev/src
```

Observed: no matches.

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

Fallback rule:

- If LVM tools or pool are unavailable, send `disk.lvm.available=false`.
- Do not fabricate `thinPoolSizeGb`; backend treats missing LVM capacity as
  legacy mode and omits `workspace` from create payloads.

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

When backend sends `params.workspace`, allocate a per-container thin volume and
mount it into the container at `/workspace`.

Backend shape:

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

Minimum preflight:

```bash
docker exec hypercube-agent-dev-63 sh -lc 'command -v lvcreate; command -v lvs'
docker exec hypercube-agent-dev-63 sh -lc 'lvs --units g'
```

Expected before backend LVM mode can be verified:

```text
lvcreate and lvs exist
capacity_report includes disk.lvm.available=true and thinPoolSizeGb
```

Full 8-step integration gate:

1. Agent sends `capacity_report` with `disk.lvm.available=true`.
2. Backend Agent row updates `lvm_pool_size_gb`.
3. User creates PyTorch Jupyter request with resource recommendation prefill.
4. Backend sends `create_container` with `hostConfig`, `workspace`, and
   `sharedMounts`.
5. Agent runs `lvcreate`, `mkfs`, and `mount`.
6. Agent reports `create_container_result.workspace.device`.
7. Backend stores `Container.workspace_device`.
8. Container `df /workspace` shows the requested LVM thin size.

Core-side tests already green:

```text
backend: 108 tests OK
frontend vitest: 57 passed
frontend svelte-check: 0 errors
frontend e2e: 3 passed
```

## Regression Rules

- Existing `create_container` requests without `params.workspace` must keep
  working.
- Existing hosts without LVM capacity must stay in legacy mode.
- Existing `update_container` / `update-limits` behavior must keep working.
- Existing GPU allocation, model mount, network policy, logs, exec, and metrics
  behavior must not regress.
- Do not add runtime downloads in the agent hot path.
