# Container Resource Limits Completion Audit Addendum - 2026-05-16

## Objective Restated

Deliver HyperCube backend/frontend support for container resource limits,
host-capacity recommendations, an LVM thin workspace contract, and quota-aware
KPI/chart display across PR 1 through PR 5, then validate, commit, and push.

## Audit Result

Core backend/frontend work is implemented and pushed to HyperCube `dev`.
The full goal is not complete because the server-63 LVM thin workspace
end-to-end gate is still blocked by external agent/ops runtime setup:

- HyperCube-agent issue #16 still has no `PERMISSION_OPTION=<1|2|3>` reply.
- `server_63_dev` and `hypercube-agent-dev-63` still lack required LVM tools.
- Required workspace/shared-mount roots are still absent.
- Backend Agent rows still have `lvm_pool_size_gb=None`.

## Current Remote Evidence

GitHub compare shows remote HyperCube `dev` is currently identical to
`ea9c25952d02fca1c88c5f55100eb79f463fb493`.
The latest implementation/audit chain includes:

```text
7454fdd feat(containers): add resource limits and workspace quotas
1f12568 docs(containers): clarify template model path in audit
e9e8394 fix(containers): clear unenforced legacy workspace quota
bf30668 chore(containers): normalize workspace service line endings
8e81883 docs(containers): record 2026-05-16 lvm blocker recheck
c7fec88 docs(containers): add 2026-05-16 completion audit addendum
ea9c259 docs(containers): link 2026-05-16 audit addendum
```

## Prompt-to-Artifact Checklist

| Requirement or gate | Evidence inspected | Status |
| --- | --- | --- |
| Required specs reviewed before work | Existing audit records the local synced resource-limit plan HTML and `docs/agent-integration-lvm-thin-spec.ko.html` inspection | Done |
| PR 1 template weights/floors | Existing audit maps `ContainerTemplate` fields in `backend/apps/containers/models.py` and migration `0010_template_weights.py` | Done |
| PR 1 Agent capacity model | Existing audit maps `backend/apps/agents/models.py` and migration `0008_agent_capacity.py` | Done |
| PR 1 `capacity_report` handling | Existing audit maps `backend/apps/common/consumers.py` and consumer tests | Done |
| PR 1 recommendation helper | Existing audit maps `backend/apps/containers/services/recommend.py` and `test_recommend.py` | Done |
| PR 2 request schema and validation | Existing audit maps `ContainerRequest` model/serializer fields, min-floor validation, and tests | Done |
| PR 2 Container limit model | Existing audit maps `Container` limit fields and migration `0011_container_resource_limits.py` | Done |
| PR 2 update-limits regression | Existing audit maps `backend/apps/containers/viewsets.py` and `test_viewsets.py` | Done |
| PR 3 agent `hostConfig` payload | Existing audit maps `backend/apps/containers/services/deployment.py` and `test_deployment.py` | Done |
| PR 3 LVM `workspace`/`sharedMounts` payload | Existing audit maps conditional LVM payload emission based on Agent LVM capacity | Core done |
| PR 3 create result workspace persistence | Existing audit maps `backend/apps/common/consumers.py`, `services/workspace.py`, and consumer tests | Done |
| PR 3 workspace metrics to KPI API | Existing audit maps `backend/apps/containers/viewsets.py` Redis/DB merge | Done |
| PR 3 docs sync | Existing audit maps `docs/api.md`, `docs/agent-protocol.md`, and `docs/agent-payload-contract.md` | Done |
| PR 4 resource-limit UI | Existing audit maps `ResourceLimitForm.svelte`, `NewRequestModal.svelte`, and component tests | Done |
| PR 4 recommend endpoint | Existing audit maps `ContainerViewSet.recommend`, route resolver evidence, and API docs | Done |
| PR 5 KPI/chip quota display | Existing audit maps `ContainerKpiBar.svelte` and tests for limits/unlimited | Done |
| PR 5 chart denominator labels | Existing audit maps `UserMetricChart.svelte`, `EChartLine.svelte`, and container detail route props | Done |
| Legacy no-LVM compatibility | `docs/test-reports/2026-05-15-container-resource-limits-legacy-workspace-quota-fix.md` records the no-unenforced-quota follow-up; progress records 111 backend tests | Done |
| Backend tests | `progress.md` records `python manage.py test -> 111 tests OK`; prior targeted follow-up recorded 2 tests OK | Done |
| Frontend tests/check/E2E | `progress.md` records 57 unit tests, `npm run check` 0 errors/193 warnings, and E2E 3 passed | Done |
| Migrations on server 63 | `progress.md` records `agents.0008`, `containers.0010`, `containers.0011` applied | Done |
| Commit and push | GitHub compare shows `dev` is identical to `ea9c25952d02fca1c88c5f55100eb79f463fb493`; implementation and audit docs are committed on `dev` | Done |
| Agent permission option chosen | HyperCube-agent issue #16 comments were fetched on 2026-05-16; no `PERMISSION_OPTION=<1|2|3>` reply exists | Blocked |
| server-63 host LVM tools | 2026-05-16 preflight output: host `lvs` unavailable; cannot inspect thin pool | Blocked |
| agent runtime LVM tools | 2026-05-16 preflight output: agent `lvcreate`, `lvs`, and `lvremove` missing; `lvs: not found` | Blocked |
| shared mount/workspace roots | 2026-05-16 preflight output: `/mnt/datasets`, `/mnt/models`, `/var/lib/hypercube/workspaces` missing | Blocked |
| backend Agent LVM capacity | 2026-05-16 preflight output: `server_16_dev` and `server_63_dev` have `lvm_pool_size_gb=None` | Blocked |
| full 8-step LVM scenario | Cannot execute until the blocked LVM/agent/ops gates above are resolved | Blocked |

## 2026-05-16 Preflight Evidence

Command run from `/home/agics/ts/HyperCube` on server 63:

```bash
bash docs/runbooks/lvm-thin-workspace-preflight.sh hypercube-agent-dev-63 hc-backend
```

Observed result:

```text
PREFLIGHT_EXIT:1
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
backend Agent rows still show lvm_pool_size_gb=None for server_16_dev and server_63_dev
```

## Completion Decision

Do not mark the goal complete yet. The core repo is ready for integration, but
full completion requires a successful agent/ops path:

1. HyperCube-agent issue #16 receives `PERMISSION_OPTION=<1|2|3>`.
2. If LVM is enabled, server 63 and the deployed agent expose the required LVM
   tools and a visible thin pool.
3. Shared mount/workspace roots exist, or the policy is explicitly changed and
   docs/contracts are updated.
4. Agent sends `capacity_report.data.disk.lvm.available=true` with
   `thinPoolSizeGb`, and backend stores `Agent.lvm_pool_size_gb`.
5. A new PyTorch Jupyter request sends `hostConfig`, `workspace`, and
   `sharedMounts`; the agent creates/mounts/binds the LVM thin volume.
6. Backend stores `Container.workspace_device` and the container reports the
   requested `/workspace` quota through `df /workspace`.
