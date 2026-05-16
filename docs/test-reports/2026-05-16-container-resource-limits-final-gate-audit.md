# Container Resource Limits Final Gate Audit - 2026-05-16

## Objective Restated

Deliver HyperCube backend/frontend support for container resource limits,
host-capacity recommendations, an LVM thin workspace contract, and quota-aware
KPI/chart display across PR 1 through PR 5. The goal also requires validation,
commit/push, and a successful server-63 integration path with the HyperCube
agent.

## Current Decision

Do not mark the goal complete.

The HyperCube core backend/frontend implementation is pushed to `dev`, and the
server-63 no-LVM compatibility path is validated. HyperCube-agent PR #17 now
contains the deployable agent-side implementation and has been synced into the
server-63 dev bind-mounted runtime for non-destructive validation. However, the
required real LVM thin `/workspace` end-to-end gate is still blocked by missing
host/runtime prerequisites and a missing operator permission decision.

## Current Evidence

HyperCube-agent PR state:

```text
PR: https://github.com/qkr7287/HyperCube-agent/pull/17
state: open draft
branch: codex/resource-limits-lvm-agent
head: 8d55d46855a0d51e123c0f0c2256face7dcd1e99
base: qkr7287/HyperCube-agent:dev @ 10d14ab225d296e458a77a2ab166f8e0a89adfe7
mergeable: true
changed files: 21
GitHub Actions: CI run 21 passed
```

HyperCube-agent PR #17 file-level audit:

```text
report: docs/test-reports/2026-05-16-agent-pr17-file-audit.md
commit: 402f8dc010485e59f1305a49b18edd8c7d77e664
CI run 25948355854 / run 21: completed, success
job 76281100630 Type check & build: success
inspected PR-head files: src/collectors/docker.ts, src/sync/delta.ts,
src/config.ts, src/workspace-recovery.ts, src/collectors/system.ts,
src/self-tests/resource-limits-lvm.ts, package.json, src/index.ts
```

The file audit confirms PR #17 contains workspace metrics, system LVM metrics,
capacity-report wiring, disabled-LVM no-probe behavior, recovery wiring, and
self-test coverage on the remote PR head.

Server-63 agent runtime sync evidence:

```text
host: hc-dev-63
runtime path: /home/agics/ts/agent-dev
agent container: hypercube-agent-dev-63
backup: /home/agics/ts/agent-dev-pr17-sync-backup-20260516T010102Z.tgz
runtime validation: build + resource-limits-lvm self-test + network-policy self-test passed
agent restart: reconnected to backend
```

Runtime command that passed inside `hypercube-agent-dev-63`:

```bash
cd /app
npm run build
node dist/self-tests/resource-limits-lvm.js
node dist/self-tests/create-container-network-policy.js
```

Backend Agent row after runtime restart:

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

HyperCube-agent issue #16 status:

```text
Issue title refreshed: feat(lvm): complete server-63 LVM thin workspace runtime gate
No PERMISSION_OPTION=<1|2|3> reply exists in fetched issue comments.
The issue body now asks for PERMISSION_OPTION, LVM_DEVICE, NFS_DATASETS, and NFS_MODELS.
Latest issue comment records the PR #17 file audit and current preflight blocker.
```

Server-63 preflight command rerun for this audit:

```bash
cd /home/agics/ts/HyperCube
bash docs/runbooks/lvm-thin-workspace-preflight.sh hypercube-agent-dev-63 hc-backend
```

Observed result:

```text
exit code: 1
FAIL host command 'lvcreate' is missing
FAIL host command 'lvs' is missing
OK   host command 'mkfs.ext4' -> /usr/sbin/mkfs.ext4
OK   host command 'mount' -> /usr/bin/mount
OK   host command 'umount' -> /usr/bin/umount
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
backend Agent rows:
agent-register-smoke-after-migrate None None None None
server_16_dev 12 39760 None 2026-05-16 01:03:45.206653+00:00
server_63_dev 12 15897 None 2026-05-16 01:04:44.080208+00:00
FAIL LVM thin workspace host preflight failed
```

## Prompt-to-Artifact Checklist

| Requirement / gate | Concrete artifact or evidence inspected | Status |
| --- | --- | --- |
| Required Korean resource-limit planning spec reviewed | `docs/container-resource-limits-기획.ko.html` fetched from GitHub `dev` | Done |
| Required agent LVM thin contract spec reviewed | `docs/agent-integration-lvm-thin-spec.ko.html` fetched from GitHub `dev` | Done |
| PR 1 template weights and min floors | `ContainerTemplate` fields in `backend/apps/containers/models.py`; migration `0010_template_weights.py` | Done |
| PR 1 Agent capacity model | `Agent` fields in `backend/apps/agents/models.py`; migration `0008_agent_capacity.py` | Done |
| PR 1 capacity_report handling | `backend/apps/common/consumers.py`; `backend/apps/common/tests/test_consumers.py` | Done |
| PR 1 recommendation helper | `backend/apps/containers/services/recommend.py`; `backend/apps/containers/tests/test_recommend.py` | Done |
| PR 2 ContainerRequest CPU/memory/workspace schema | `ContainerRequest` model and serializer fields | Done |
| PR 2 min floor validation | `ContainerRequestSerializer._apply_resource_limit_defaults` plus min-limit tests | Done |
| PR 2 Container limit/device fields | `Container` fields and migration `0011_container_resource_limits.py` | Done |
| PR 2 update-limits regression | Prior server-63 targeted backend tests recorded in `progress.md` | Done |
| PR 3 hostConfig payload | `backend/apps/containers/services/deployment.py` maps memory/cpu to lower-camel agent payload | Done |
| PR 3 LVM workspace and sharedMounts payload contract | Core payload builder conditionally sends LVM `workspace` and `sharedMounts` only when `Agent.lvm_pool_size_gb` exists | Core done; live LVM path blocked |
| PR 3 create_container_result workspace_device persistence | `backend/apps/common/consumers.py` and consumer tests cover workspace metadata persistence | Core done; live LVM result blocked |
| PR 3 workspace metrics to KPI API | `MyContainerViewSet.current_metrics` merges workspace metrics and DB snapshot | Core done; live LVM metric blocked |
| PR 3 docs sync | `docs/api.md`, `docs/agent-protocol.md`, `docs/agent-payload-contract.md` fetched from `dev` | Done |
| PR 4 ResourceLimitForm | `frontend/src/lib/components/ResourceLimitForm.svelte` fetched from `dev` | Done |
| PR 4 request modal recommendation prefill and submit fields | `frontend/src/lib/components/NewRequestModal.svelte` fetches `/api/containers/recommend/` and submits `cpu_percent`, `memory_mb`, `workspace_gb` | Done |
| PR 4 recommend endpoint | `ContainerViewSet.recommend` and `docs/api.md` expose `/api/containers/recommend/` and `/api/v1/containers/recommend/` | Done |
| PR 5 KPI quota chips and unlimited state | `frontend/src/lib/components/ContainerKpiBar.svelte` includes CPU/memory/workspace limit chips and denominator tooltip text | Done |
| PR 5 chart denominator labels | `UserMetricChart.svelte` and container detail route pass y-axis and denominator text | Done |
| Backend tests | `progress.md` records 111 tests OK and targeted 7 tests OK on server 63 | Done |
| Frontend tests/check/E2E | `progress.md` records 57 tests OK, `npm run check` 0 errors/193 warnings, E2E 3 passed | Done |
| Backend mypy if present | `progress.md` records no mypy config/dependency/module | Not applicable |
| Core commit and push | Core implementation/docs are present on GitHub `dev`; latest progress update pushed by GitHub contents API | Done |
| Agent PR exists | PR #17 open draft, mergeable, CI success | Done, draft |
| Agent PR file-level audit | `docs/test-reports/2026-05-16-agent-pr17-file-audit.md`; PR-head files fetched from `8d55d46855a0d51e123c0f0c2256face7dcd1e99` | Done |
| Agent server-63 non-destructive runtime validation | build + resource-limits-lvm self-test + network-policy self-test passed in `hypercube-agent-dev-63` | Done |
| Agent/ops permission option | Issue #16 has no `PERMISSION_OPTION=<1|2|3>` answer | Blocked |
| server-63 host LVM readiness | Current preflight shows host `lvcreate`, `lvs`, and `lvremove` missing | Blocked |
| agent runtime LVM readiness | Current preflight shows agent `lvcreate`, `lvs`, and `lvremove` missing | Blocked |
| shared mounts/workspace root | Current preflight shows `/mnt/datasets`, `/mnt/models`, and `/var/lib/hypercube/workspaces` missing | Blocked |
| backend Agent LVM capacity | Current backend row shows `server_63_dev.lvm_pool_size_gb=None` | Blocked |
| Full 8-step LVM scenario | Preflight preconditions are not met, so create/mount/df/KPI proof cannot run | Blocked |

## Why Existing Green Tests Are Not Enough

The green backend/frontend tests verify core behavior and the no-LVM compatibility
path. The agent PR tests verify the non-destructive agent code path. Neither set
proves that server 63 can create an LVM thin volume, mount it, bind it into the
created container, return `workspace_device`, emit workspace metrics, or show
`df /workspace` at the requested quota. The current preflight failure directly
blocks that proof path.

## Remaining Completion Gate

The next valid completion attempt starts only after all of these are true:

1. HyperCube-agent issue #16 receives `PERMISSION_OPTION=<1|2|3>`.
2. For real LVM mode, server 63 and the deployed agent expose `lvcreate`, `lvs`,
   `lvremove`, `mkfs.ext4`, `mount`, and `umount` through the selected
   permission path.
3. `/mnt/datasets`, `/mnt/models`, and `/var/lib/hypercube/workspaces` exist or
   the contract is deliberately changed and docs are updated.
4. Agent sends `capacity_report.data.disk.lvm.available=true` with a thin-pool
   size and backend stores non-null `Agent.lvm_pool_size_gb` for `server_63_dev`.
5. `docs/runbooks/lvm-thin-workspace-preflight.sh` exits 0.
6. `docs/runbooks/lvm-thin-workspace-full-validation.md` passes the real
   create-container, LVM mount, backend persistence, metrics, and UI denominator
   checks.

Until those gates pass, the correct status is: core ready, agent PR/runtime
non-destructive path validated, external LVM/ops gate blocked, goal not complete.
