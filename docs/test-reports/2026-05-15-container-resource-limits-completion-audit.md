# Container Resource Limits Completion Audit - 2026-05-15

Objective:

> Add container resource limits, host-capacity based recommendations, LVM thin
> workspace contract, and quota-aware KPI/chart display to HyperCube
> backend/frontend across PR 1 through PR 5, then validate, commit, and push.

Current result: core backend/frontend is complete and pushed. The full objective
is not complete because the server-63 host/agent LVM thin integration gate is
still blocked by missing host LVM tooling, missing shared mount roots, and
`Agent.lvm_pool_size_gb=None`.

Remote HyperCube `dev` was verified by GitHub API during this audit. Re-check
the current HEAD when resuming:

```bash
gh api repos/qkr7287/HyperCube/git/ref/heads/dev --jq '.object.sha'
```

Audited implementation evidence chain includes:

```text
7454fdd feat(containers): add resource limits and workspace quotas
557cdf8 docs(agent): link lvm preflight script
58dd250 test(containers): cover legacy workspace payload without lvm
7f2ca42 docs(containers): record recommend route resolver evidence
```

Path note: the prompt names `backend/apps/templates/models.py`, but this repo
does not have a `backend/apps/templates` app. The actual template model is
`backend/apps/containers/models.py::ContainerTemplate` (`db_table =
"container_templates"`), so the template weight work is implemented there.

## Prompt-to-Artifact Checklist

| Requirement | Evidence | Status |
| --- | --- | --- |
| Read container resource limit plan and agent LVM spec | Local synced resource-limit plan HTML and `docs/agent-integration-lvm-thin-spec.ko.html` inspected | Done |
| PR 1: Template weight fields | `backend/apps/containers/models.py` has `cpu_weight`, `ram_weight`, `disk_weight`, `min_cpu_percent`, `min_memory_mb`, `min_workspace_gb`; migration `0010_template_weights.py` exists | Done |
| PR 1: Agent capacity fields | `backend/apps/agents/models.py` has `cpu_cores`, `cpu_model`, `ram_total_mb`, `disk_total_gb`, `lvm_pool_size_gb`, `nic_speed_mbps`, `filesystem`, `target_users`, `safety_margin`, `capacity_updated_at`; migration `0008_agent_capacity.py` exists | Done |
| PR 1: `capacity_report` handling | `backend/apps/common/consumers.py` updates Agent capacity fields; `backend/apps/common/tests/test_consumers.py` covers full and partial/null reports plus no-LVM workspace limit omission | Done |
| PR 1: recommendation helper | `backend/apps/containers/services/recommend.py`; `backend/apps/containers/tests/test_recommend.py` covers 24-core/256 GB/3000 GB host recommendation and hard floors | Done |
| PR 2: request schema | `backend/apps/containers/models.py` and `serializers.py` expose `cpu_percent`, `memory_mb`, `workspace_gb`; serializer fills defaults from recommendation | Done |
| PR 2: Container limit model fields | `Container` has `cpu_percent_limit`, `memory_mb_limit`, `workspace_gb_limit`, `workspace_device`, `limit_updated_at`; migration `0011_container_resource_limits.py` exists | Done |
| PR 2: min floor reject | `min_limit_errors` and serializer validation; tests in `test_recommend.py` and `test_template_and_request.py` cover below-floor rejection | Done |
| PR 2: `update-limits` regression | `backend/apps/containers/viewsets.py` updates CPU/memory limit snapshots; `test_viewsets.py` checks persisted limits and `limit_updated_at` | Done |
| PR 3: create payload `hostConfig` | `backend/apps/containers/services/deployment.py` emits `memory`, `memorySwap`, `cpuQuota`, `cpuPeriod`, `oomKillDisable`; `test_deployment.py` covers mapping | Done |
| PR 3: LVM `workspace` and `sharedMounts` | `deployment.py` emits `workspace.sizeGb`, `mountTarget=/workspace`, and read-only `/mnt/datasets`, `/mnt/models` only when the target Agent has LVM pool capacity | Core done |
| PR 3: create result workspace persistence | `backend/apps/common/consumers.py` and `services/workspace.py` store `workspace.device` and `sizeGb`; consumer/workspace tests also clear unreported workspace quotas so legacy paths do not show unenforced disk limits | Done |
| PR 3: workspace metrics to KPI API | `backend/apps/containers/viewsets.py` merges Redis workspace metrics with DB `workspace_gb_limit` / `workspace_device` | Done |
| PR 3: docs sync | `docs/api.md`, `docs/agent-protocol.md`, `docs/agent-payload-contract.md` include resource limit, `hostConfig`, workspace, `sharedMounts`, and result schema changes | Done |
| PR 4: UI form component | `frontend/src/lib/components/ResourceLimitForm.svelte`; component tests cover recommendation values, host share labels, and warnings | Done |
| PR 4: request flow prefill and submit | `frontend/src/lib/components/NewRequestModal.svelte` fetches `/api/containers/recommend/?template=...&agent=...` and submits `cpu_percent`, `memory_mb`, `workspace_gb` | Done |
| PR 4: backend recommend endpoint | `backend/apps/containers/viewsets.py`; route is documented in `docs/api.md`; `test_viewsets.py` covers authenticated endpoint access; Django resolver maps both `/api/containers/recommend/` and `/api/v1/containers/recommend/` to `ContainerViewSet.recommend` | Done |
| PR 5: KPI limit chips and workspace card | `frontend/src/lib/components/ContainerKpiBar.svelte`; tests check `limit 4 cores`, `limit 16 GB`, `limit 100 GB`, and `unlimited` | Done |
| PR 5: chart denominator labels | `frontend/src/lib/components/UserMetricChart.svelte`, `charts/EChartLine.svelte`, and `routes/user/containers/[containerId]/+page.svelte` pass CPU/memory denominator labels | Done |
| Backward compatibility for legacy containers | Backend omits LVM `workspace` / `sharedMounts` when `agent.lvm_pool_size_gb` is absent; E2E target `05eddec05865` passes with legacy/unlimited path | Done |
| Backward compatibility for legacy Jupyter workspaces | `backend/apps/containers/tests/test_deployment.py` verifies existing Jupyter workspace metadata is preserved while only LVM `sizeGb` / `mountTarget` / `sharedMounts` are omitted for no-LVM agents | Done |
| Backend tests | On `server_63_dev`, `docker exec hc-backend python manage.py test` ran 111 tests: OK | Done |
| Frontend unit tests | On `server_63_dev`, `docker exec hc-frontend-dev npm test -- --run` ran 57 tests: passed | Done |
| Frontend check | On `server_63_dev`, `docker exec hc-frontend-dev npm run check`: 0 errors, 193 warnings | Done |
| E2E | On `server_63_dev`, `docker exec -e E2E_USER=user1 -e E2E_PASS='agics12!@' -e E2E_CONTAINER_ID=05eddec05865 hc-frontend-dev npm run e2e`: 3 passed | Done |
| Migrations applied on server-63 | `showmigrations agents containers` shows `[X] 0008_agent_capacity`, `[X] 0010_template_weights`, `[X] 0011_container_resource_limits` | Done |
| Commit and push | Remote `dev` contains the implementation evidence chain and later audit-only doc refresh commits verified through the GitHub API | Done |
| Repeatable LVM preflight | `docs/runbooks/lvm-thin-workspace-preflight.sh` is a read-only host/agent/backend capacity check; syntax passed with `bash -n` | Done |
| Agent permission option chosen | HyperCube-agent issue #16 remains open and has no reply with `PERMISSION_OPTION=<1|2|3>` | Blocked |
| Agent reports LVM thin capacity | Backend Agent rows show `server_63_dev lvm_pool_size_gb=None` and `server_16_dev lvm_pool_size_gb=None` | Blocked |
| server-63 LVM host preflight | Host `command -v lvcreate` and `command -v lvs` are empty; `lvs --units g` returns `lvs: command not found` | Blocked |
| Agent runtime LVM preflight | `docker exec hypercube-agent-dev-63 ... command -v lvcreate/lvs` is empty; `lvs --units g` returns `lvs: not found` | Blocked |
| Shared mount preflight | `/mnt/datasets` and `/mnt/models` are missing on `server_63_dev` | Blocked |
| Full 8-step LVM scenario | Cannot run until LVM tooling/thin pool/shared mounts/permission option are available | Blocked |

## Current Server-63 Blocking Evidence

Backend Agent rows:

```text
('agent-register-smoke-after-migrate', None, None, None, None)
('server_16_dev', 12, 39760, None, 2026-05-15T09:03:40Z)
('server_63_dev', 12, 15897, None, 2026-05-15T09:12:49Z)
```

Host and agent LVM preflight:

```text
HOST
lvs: command not found
MOUNTS
datasets:missing
models:missing
AGENT
lvs: not found
```

Read-only scripted preflight:

```text
bash docs/runbooks/lvm-thin-workspace-preflight.sh hypercube-agent-dev-63 hc-backend
PREFLIGHT_EXIT:1
```

Key failures observed:

```text
host command 'lvcreate' is missing
host command 'lvs' is missing
host command 'lvremove' is missing
/mnt/datasets is missing
/mnt/models is missing
/var/lib/hypercube/workspaces is missing
agent command 'lvcreate' is missing
agent command 'lvs' is missing
agent command 'lvremove' is missing
agent lvs command failed
server_63_dev 12 15897 None 2026-05-15 10:03:40.980780+00:00
```

The core implementation is intentionally in legacy mode for those agents until
`capacity_report.data.disk.lvm.available=true` and `thinPoolSizeGb` reach the
backend.

## Remaining Completion Gate

Do not mark the initiative complete until all of the following are observed on
`server_63_dev`:

1. A permission model is chosen in HyperCube-agent issue #16.
2. Host and agent runtime both expose `lvcreate`, `lvs`, `mkfs.ext4`, `mount`,
   `umount`, and `lvremove`.
3. A configured thin pool is visible through `lvs --units g`.
4. `/mnt/datasets` and `/mnt/models` exist or the shared-mount policy is
   explicitly changed.
5. Agent sends `capacity_report` with `disk.lvm.available=true` and
   `thinPoolSizeGb`.
6. Backend Agent row updates `lvm_pool_size_gb`.
7. A new PyTorch Jupyter request causes backend to send `hostConfig`,
   `workspace`, and `sharedMounts`.
8. Agent creates, formats, mounts, and binds the LVM thin workspace.
9. Agent returns `create_container_result.workspace.device`.
10. Backend stores `Container.workspace_device`.
11. Container `df /workspace` shows the requested workspace quota.
