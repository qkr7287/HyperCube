# HyperCube-agent PR17 Draft Status - 2026-05-16

## Objective Gate

The active objective is not complete yet. HyperCube core PR 1-5 work is
implemented on `dev`, but full completion requires a deployable agent-side LVM
workspace implementation plus the server-63 end-to-end validation path.

## Evidence Checked

- Required specs were read from HyperCube `dev` through the GitHub file API:
  - `docs/container-resource-limits-기획.ko.html`
  - `docs/agent-integration-lvm-thin-spec.ko.html`
- HyperCube-agent PR: https://github.com/qkr7287/HyperCube-agent/pull/17
- HyperCube-agent tracking issue: https://github.com/qkr7287/HyperCube-agent/issues/16
- Server-63 preflight command:

```bash
cd /home/agics/ts/HyperCube
bash docs/runbooks/lvm-thin-workspace-preflight.sh hypercube-agent-dev-63 hc-backend
```

## Agent PR State

Draft PR #17 is open against `qkr7287/HyperCube-agent:dev`.

```text
branch: codex/resource-limits-lvm-agent
base: dev
head: 8d55d46855a0d51e123c0f0c2256face7dcd1e99
base sha: 10d14ab225d296e458a77a2ab166f8e0a89adfe7
state: open
mergeable: true
draft: true
changed files: 21
additions/deletions: 1588 / 110
```

PR #17 implements the deployable agent-side contract that was previously only
available in the dirty Windows checkout or temp verification copy:

- `capacity_report` on startup, reconnect, periodic timer, and `request_capacity`.
- Docker `HostConfig` mapping for backend `memory`, `memorySwap`, `cpuQuota`,
  `cpuPeriod`, and `oomKillDisable`.
- LVM thin workspace provisioning from `workspace.sizeGb` and
  `workspace.mountTarget`.
- `sharedMounts` bind handling.
- LVM workspace rollback on `mkfs`, `mount`, Docker create/start, and network
  validation failures.
- Workspace cleanup on delete and remount recovery on agent start.
- `container_metrics.workspace` reporting from LVM workspace labels.
- LVM thin-pool info in system/capacity metrics.
- Disabled-LVM guard: `LVM_WORKSPACE_ENABLED=false` reports
  `disk.lvm.available=false` without probing `lvs`.
- Existing GPU per-container contract is preserved, including `indices` and
  `pmon|dcgm-mig|host-util-solo|vram-only` source values.

## Agent Validation

Validation was run from the temporary remote-safe workspace under the HyperCube
core checkout, after copying the agent worktree and preserving the current
remote GPU contract.

```bash
npm run build
node dist/self-tests/resource-limits-lvm.js
npm run self-test:network-policy
```

Observed result: all passed.

No GitHub status checks were present for PR #17 at the time of this report.

## Prompt-to-Artifact Checklist Delta

| Requirement | Evidence | Status |
| --- | --- | --- |
| Agent `capacity_report` implementation | PR #17 includes `src/collectors/capacity.ts`, `src/index.ts`, `src/types/index.ts` | Draft PR ready |
| Agent `hostConfig` mapping | PR #17 includes `src/handlers/create-container.ts`; self-test validates mapping | Draft PR ready |
| LVM workspace create/rollback/delete | PR #17 includes `src/workspace-lvm.ts`, `src/workspace-recovery.ts`, handler updates, self-test | Draft PR ready |
| `sharedMounts` | PR #17 self-test checks `/mnt/datasets:/datasets:ro` and `/mnt/models:/models:rw` mapping | Draft PR ready |
| `container_metrics.workspace` | PR #17 includes `src/collectors/docker.ts`, `src/sync/delta.ts`, `src/types/index.ts` | Draft PR ready |
| Disabled-LVM no-probe guard | PR #17 self-test includes `assertCapacityReportDisabledLvmDoesNotProbe` | Draft PR ready |
| Deploy to server 63 | PR remains draft and unmerged | Blocked |
| server-63 LVM host prerequisites | Latest preflight still fails | Blocked |
| Full 8-step `/workspace` LVM validation | Cannot run until host/agent prerequisites pass | Blocked |

## Latest Server-63 Blocker

Preflight still fails with:

```text
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
server_16_dev 12 39760 None 2026-05-16 00:03:40.815470+00:00
server_63_dev 12 15897 None 2026-05-16 00:03:41.014804+00:00
```

## Next Gate

1. Review and merge/deploy HyperCube-agent PR #17, or keep it draft until the
   host permission model is chosen.
2. Record `PERMISSION_OPTION=<1|2|3>` in issue #16.
3. If LVM mode is chosen, prepare server 63 with `lvm2`, an approved thin pool,
   `/mnt/datasets`, `/mnt/models`, and `/var/lib/hypercube/workspaces`.
4. Re-run `docs/runbooks/lvm-thin-workspace-preflight.sh` until it exits 0.
5. Run `docs/runbooks/lvm-thin-workspace-full-validation.md` and capture the
   real 8-step result.
