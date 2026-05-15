# Container Resource Limits Final Gate Audit - 2026-05-16

## Objective Restated

Deliver HyperCube backend/frontend support for container resource limits,
host-capacity recommendations, an LVM thin workspace contract, and quota-aware
KPI/chart display across PR 1 through PR 5. The goal also requires validation,
commit, push, and a successful server-63 integration path with the HyperCube
agent.

## Current Decision

Do not mark the goal complete.

The core HyperCube backend/frontend implementation is on `dev` and the current
no-LVM compatibility path is validated, but the required LVM thin workspace
end-to-end gate is still blocked outside the core repo. The missing evidence is
not a proxy signal problem: the concrete runtime commands and backend capacity
rows still show that server 63 cannot run the LVM workspace scenario.

## Current Remote Evidence

GitHub compare evidence collected during this audit:

```text
HyperCube dev == cfda1df37fe7ccc0dd90e71406af6a01367a6aa7
cfda1df37fe7ccc0dd90e71406af6a01367a6aa7 docs(containers): refresh lvm validation progress
```

HyperCube-agent issue #16 evidence collected during this audit:

```text
No PERMISSION_OPTION=<1|2|3> reply exists in the fetched issue comments.
The latest tracking comment still asks agent/ops for PERMISSION_OPTION,
LVM_PREFLIGHT, and CAPACITY_REPORT.
```

Server 63 preflight command rerun during this audit:

```bash
cd /home/agics/ts/HyperCube
bash docs/runbooks/lvm-thin-workspace-preflight.sh hypercube-agent-dev-63 hc-backend
```

Observed result:

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
backend Agent rows:
agent-register-smoke-after-migrate None None None None
server_16_dev 12 39760 None 2026-05-15 16:03:40.813793+00:00
server_63_dev 12 15897 None 2026-05-15 16:03:41.076664+00:00
FAIL LVM thin workspace host preflight failed
```

## Prompt-to-Artifact Checklist

| Requirement / gate | Concrete artifact or evidence inspected | Status |
| --- | --- | --- |
| Required Korean resource-limit planning spec reviewed | Prior audit records inspection of `docs/container-resource-limits-기획.ko.html` from GitHub `dev` | Done |
| Required agent LVM thin contract spec reviewed | Prior audit records inspection of `docs/agent-integration-lvm-thin-spec.ko.html` from GitHub `dev` | Done |
| PR 1 template weights and min floors | Prior audit maps `ContainerTemplate` fields in `backend/apps/containers/models.py` and migration evidence | Done |
| PR 1 Agent capacity model | Prior audit maps `backend/apps/agents/models.py` and migration evidence | Done |
| PR 1 capacity_report handling | Prior audit maps `backend/apps/common/consumers.py` plus consumer tests | Done |
| PR 1 recommendation helper | Prior audit maps `backend/apps/containers/services/recommend.py` plus recommendation tests | Done |
| PR 2 ContainerRequest CPU/memory/workspace schema | Prior audit maps `backend/apps/containers/serializers.py` and `ContainerRequest` model fields | Done |
| PR 2 min floor validation | Prior audit maps serializer validation and tests | Done |
| PR 2 Container limit/device fields | Prior audit maps `Container` fields and migration evidence | Done |
| PR 2 update-limits regression | Prior audit maps `backend/apps/containers/viewsets.py` and update-limit tests | Done |
| PR 3 hostConfig payload | Prior audit maps `backend/apps/containers/services/deployment.py`; targeted server-63 tests passed | Done |
| PR 3 LVM workspace and sharedMounts payload contract | Core payload builder has conditional LVM fields; live no-LVM dry-run omits them when `Agent.lvm_pool_size_gb=None` | Core done; live LVM path blocked |
| PR 3 create_container_result workspace_device persistence | Prior audit maps `backend/apps/common/consumers.py` and workspace metadata tests | Core done; live LVM result blocked |
| PR 3 workspace metrics to KPI API | Prior audit maps Redis/DB merge path in `backend/apps/containers/viewsets.py` | Core done; live LVM metric blocked |
| PR 3 docs sync | Prior audit maps `docs/api.md`, `docs/agent-protocol.md`, and `docs/agent-payload-contract.md` | Done |
| PR 4 ResourceLimitForm and request modal | Prior audit maps `frontend/src/lib/components/ResourceLimitForm.svelte` and `NewRequestModal.svelte` plus tests | Done |
| PR 4 recommend endpoint | Prior audit maps `ContainerViewSet.recommend` and API docs | Done |
| PR 5 KPI quota chips and unlimited state | Prior audit maps `ContainerKpiBar.svelte` and tests | Done |
| PR 5 chart denominator labels | Prior audit maps `UserMetricChart.svelte`, `EChartLine.svelte`, and container detail props | Done |
| Backend tests | Progress/audit evidence records 111 tests OK plus targeted 7 tests OK on server 63 | Done |
| Frontend tests/check/E2E | Progress/audit evidence records 57 tests OK, `npm run check` 0 errors/193 warnings, E2E 3 passed | Done |
| Backend mypy if present | Progress/audit evidence records no mypy config/dependency/module | Not applicable |
| Commit and push | GitHub compare confirms remote `dev` at `cfda1df37fe7ccc0dd90e71406af6a01367a6aa7` before this report | Done |
| Agent/ops permission option | HyperCube-agent issue #16 fetched during this audit; no `PERMISSION_OPTION=<1|2|3>` answer exists | Blocked |
| server-63 host LVM readiness | Preflight rerun during this audit shows host `lvcreate`, `lvs`, and `lvremove` missing | Blocked |
| agent runtime LVM readiness | Preflight rerun during this audit shows agent `lvcreate`, `lvs`, and `lvremove` missing | Blocked |
| shared mounts/workspace root | Preflight rerun during this audit shows `/mnt/datasets`, `/mnt/models`, and `/var/lib/hypercube/workspaces` missing | Blocked |
| backend Agent LVM capacity | Preflight rerun during this audit shows `server_63_dev ... lvm_pool_size_gb=None` | Blocked |
| Full 8-step LVM scenario | `docs/runbooks/lvm-thin-workspace-full-validation.md` preconditions are not met; cannot run the create/mount/df/KPI proof | Blocked |

## Why Existing Green Tests Are Not Enough

The green backend/frontend tests verify core behavior and the no-LVM compatibility
path. They do not prove that server 63 can create an LVM thin volume, mount it,
bind it into the created container, return `workspace_device`, emit workspace
metrics, or show `df /workspace` at the requested quota. The current preflight
failure directly blocks that proof path.

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

Until those gates pass, the correct status is: core ready, external LVM/agent
runtime gate blocked, goal not complete.
