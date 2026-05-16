# HyperCube-agent PR #17 File Audit - 2026-05-16

## Scope

This report records the file-level audit performed against HyperCube-agent PR #17
for the HyperCube container resource limits and LVM thin workspace objective.

Repository: `qkr7287/HyperCube-agent`
PR: https://github.com/qkr7287/HyperCube-agent/pull/17
Head: `8d55d46855a0d51e123c0f0c2256face7dcd1e99`
State at audit: open, draft, mergeable

## CI Evidence

GitHub Actions workflow run for the PR head was fetched by commit SHA:

```text
workflow: CI
run_id: 25948355854
run_number: 21
status: completed
conclusion: success
job: Type check & build
job_id: 76281100630
steps: Install deps, Type check, Build all success
combined legacy statuses: []
```

## Files Inspected

The following files were fetched from PR head
`8d55d46855a0d51e123c0f0c2256face7dcd1e99`:

```text
src/collectors/docker.ts
src/sync/delta.ts
src/config.ts
src/workspace-recovery.ts
src/collectors/system.ts
src/self-tests/resource-limits-lvm.ts
package.json
src/index.ts
```

Earlier PR-head inspection also covered:

```text
src/collectors/capacity.ts
src/handlers/create-container.ts
src/workspace-lvm.ts
src/types/index.ts
```

## Findings

`src/collectors/docker.ts` includes `collectWorkspaceUsageFromLabels()` in the
container metrics collection path and conditionally adds `workspace` to
`container_metrics` without changing the existing network/GPU metrics shape.

`src/sync/delta.ts` includes workspace delta thresholds and preserves the current
GPU per-container contract, including `indices` comparison and the existing
source transitions.

`src/config.ts` adds `lvmWorkspace` config with defaults for enabled state,
volume group, thin pool, mount root, UID, and GID. It validates UID/GID as
non-negative integers.

`src/collectors/system.ts` passes optional `lvmWorkspace` into
`collectLvmThinPoolInfo()` and includes `system_metrics.data.lvm.thinPool` only
when collection returns data.

`src/index.ts` sends capacity reports on reconnect and startup, handles the
`request_capacity` command, wires `config.lvmWorkspace` into system collection,
and calls `recoverLvmWorkspaceMounts()` after the initial capacity report.

`src/workspace-recovery.ts` scans active containers for managed workspace labels
and remounts recoverable LVM workspaces when LVM mode is enabled.

`src/self-tests/resource-limits-lvm.ts` exercises HostConfig/sharedMount mapping,
capacity report schema, graceful LVM fallback, disabled-LVM no-probe behavior,
LVM command order, mkfs/mount rollback, remount behavior, and Docker
create/start cleanup rollback.

`package.json` exposes `self-test:lvm-workspace` as
`npm run build && node dist/self-tests/resource-limits-lvm.js`.

## Current Gate

This file audit does not change the completion status. The PR implementation is
present and CI is green, but the full HyperCube objective remains blocked until
server 63 has a selected LVM permission option and a passing LVM preflight.

Current known blocker state:

```text
HyperCube-agent issue #16 has no PERMISSION_OPTION=<1|2|3> reply.
server_63_dev host is missing lvcreate, lvs, and lvremove.
hypercube-agent-dev-63 is missing lvcreate, lvs, and lvremove.
/mnt/datasets, /mnt/models, and /var/lib/hypercube/workspaces are missing.
backend Agent row for server_63_dev still has lvm_pool_size_gb=None.
```

The correct status remains: core ready, agent PR/runtime non-destructive path
validated, LVM/ops gate blocked, goal not complete.
