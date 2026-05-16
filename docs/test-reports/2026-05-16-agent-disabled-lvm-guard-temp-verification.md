# Agent Disabled-LVM Guard Temp Verification - 2026-05-16

## Purpose

Record the latest agent-side evidence for the container resource limits + LVM
thin workspace objective without treating local dirty code as deployed state.

This report is a core-side audit artifact only. It does not mean the
HyperCube-agent remote `dev` branch is ready for the full LVM scenario.

## Remote Agent Evidence

GitHub compare for `qkr7287/HyperCube-agent` showed the current remote `dev`
commit at the time of this audit:

```text
10d14ab225d296e458a77a2ab166f8e0a89adfe7 feat: support GPU ML workspace agent runtime
```

Remote file inspection showed these LVM/resource-limit contract gaps still exist
on remote `dev`:

```text
src/workspace-lvm.ts @ dev -> 404 Not Found
src/collectors/capacity.ts @ dev -> 404 Not Found
```

Remote `src/handlers/create-container.ts` exists, but the inspected remote file
still does not expose the backend resource-limit contract:

- `CreateParams` has no `hostConfig` field.
- `CreateParams.workspace` has Jupyter metadata (`kind`, `token`, `port`,
  `baseUrl`) but no LVM `sizeGb` / `mountTarget` contract.
- There is no `sharedMounts` field.
- `buildCreateOptions()` builds Docker `HostConfig` only from existing binds,
  restart policy, port bindings, device requests, and network mode. It does not
  map backend `params.hostConfig.Memory`, `MemorySwap`, `CpuQuota`,
  `CpuPeriod`, or `OomKillDisable`.

Therefore remote HyperCube-agent `dev` is still not a deployable counterpart for
HyperCube core PR 3's `hostConfig` + LVM workspace + shared mounts payload.

## Local Temp Verification

A temporary verification copy was made from the dirty local Windows checkout:

```text
source: C:\Users\agics\Desktop\workspace\01. git\HyperCube-agent
temp:   C:\Users\agics\Desktop\workspace\01. git\HyperCube\.agent-lvm-verify-20260516-1
```

In that temp copy only, the missing disabled-LVM guard was applied to
`src/workspace-lvm.ts`:

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

A self-test was added to `src/self-tests/resource-limits-lvm.ts` proving that
`LVM_WORKSPACE_ENABLED=false` wins even when the fake runner can return a valid
`lvs` response.

Verification commands in the temp copy:

```text
npm install --ignore-scripts --no-audit --no-fund -> passed
npm run build -> passed
node dist/self-tests/resource-limits-lvm.js -> passed
```

Observed self-test behavior:

```text
capacity_report.data.disk.lvm.available=false
thinPoolSizeGb=null
alert=null
runner did not call lvs
```

## Issue Tracking

The same evidence was recorded on HyperCube-agent issue #16 in comment
`4461583774`.

## Completion Decision

Do not mark the HyperCube resource-limit/LVM objective complete.

The temp verification proves the disabled-LVM guard is straightforward and
self-testable, but it is not deployed state. Completion still requires:

1. HyperCube-agent remote `dev` or another deployable ref contains the agent
   `hostConfig`, `capacity_report`, LVM workspace, shared mounts, create result,
   and workspace metrics implementation.
2. Agent/ops replies with `PERMISSION_OPTION=<1|2|3>`.
3. server 63 either passes the LVM preflight or explicitly selects legacy mode.
4. The full 8-step LVM validation runbook passes for real LVM mode.
