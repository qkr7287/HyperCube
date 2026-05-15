# Container Resource Limits Core Validation - 2026-05-15

Target: `server_63_dev` / `hc-dev-63` / branch `dev`

Scope: HyperCube core backend/frontend implementation for container resource
limits, host-capacity recommendation, agent payload contract, and quota-aware
KPI/chart display.

## Result

Core backend/frontend is implemented, migrated, tested, and pushed to `dev`.
Full LVM thin workspace creation is not yet end-to-end verified because the
currently deployed `hypercube-agent-dev-63` runtime does not expose LVM tooling
or LVM thin capacity.

Remote `dev` HEAD verified by GitHub API:

```text
2ed75bcfb06a9dfa90bf6be81fff47eb969d3597
```

Commits:

```text
7454fdd feat(containers): add resource limits and workspace quotas
5580b11 fix(ui): trim integer quota byte labels
2ed75bc test(e2e): align container KPI selectors
```

## Core Validation

### Backend

Command:

```bash
ssh hc-dev-63 "docker exec hc-backend python manage.py test"
```

Observed:

```text
Found 108 test(s).
System check identified no issues (0 silenced).
Ran 108 tests in 83.414s
OK
```

Migrations:

```bash
ssh hc-dev-63 "docker exec hc-backend python manage.py showmigrations agents containers"
```

Observed relevant entries:

```text
[X] agents.0008_agent_capacity
[X] containers.0010_template_weights
[X] containers.0011_container_resource_limits
```

### Frontend

Command:

```bash
ssh hc-dev-63 "docker exec hc-frontend-dev npm test -- --run"
```

Observed:

```text
Test Files  4 passed (4)
Tests       57 passed (57)
```

Command:

```bash
ssh hc-dev-63 "docker exec hc-frontend-dev npm run check"
```

Observed:

```text
svelte-check found 0 errors and 193 warnings in 30 files
```

Command:

```bash
ssh hc-dev-63 "docker exec -e E2E_USER=user1 -e E2E_PASS='agics12!@' -e E2E_CONTAINER_ID=05eddec05865 hc-frontend-dev npm run e2e"
```

Observed:

```text
3 passed (10.2s)
```

## Implemented Core Artifacts

- Template weights and min floors:
  `backend/apps/containers/models.py`,
  `backend/apps/containers/migrations/0010_template_weights.py`
- Agent capacity model:
  `backend/apps/agents/models.py`,
  `backend/apps/agents/migrations/0008_agent_capacity.py`
- `capacity_report` consumer handling:
  `backend/apps/common/consumers.py`
- Recommendation helper and endpoint:
  `backend/apps/containers/services/recommend.py`,
  `backend/apps/containers/viewsets.py`
- ContainerRequest and Container limit snapshots:
  `backend/apps/containers/models.py`,
  `backend/apps/containers/serializers.py`,
  `backend/apps/containers/migrations/0011_container_resource_limits.py`
- Agent create payload `hostConfig`, LVM workspace, and shared mounts:
  `backend/apps/containers/services/deployment.py`
- Workspace result persistence:
  `backend/apps/containers/services/workspace.py`,
  `backend/apps/common/consumers.py`
- Request UI resource limit form and recommendation prefill:
  `frontend/src/lib/components/ResourceLimitForm.svelte`,
  `frontend/src/lib/components/NewRequestModal.svelte`
- KPI and chart denominator display:
  `frontend/src/lib/components/ContainerKpiBar.svelte`,
  `frontend/src/lib/components/UserMetricChart.svelte`,
  `frontend/src/lib/components/charts/EChartLine.svelte`,
  `frontend/src/routes/user/containers/[containerId]/+page.svelte`
- Contract docs:
  `docs/api.md`,
  `docs/agent-protocol.md`,
  `docs/agent-payload-contract.md`

## LVM Thin Integration Blocker

Current backend Agent rows show capacity reports are being accepted, but LVM
pool capacity is unavailable:

```text
server_63_dev cpu_cores=12 ram_total_mb=15897 lvm_pool_size_gb=None capacity_updated_at=2026-05-15T09:12:49Z
server_16_dev cpu_cores=12 ram_total_mb=39760 lvm_pool_size_gb=None capacity_updated_at=2026-05-15T09:03:40Z
```

Current `hypercube-agent-dev-63` runtime evidence:

```text
docker exec hypercube-agent-dev-63 sh -lc "command -v lvcreate || true; command -v lvs || true; lvs 2>&1 | head -20 || true"
bash: line 1: lvs: command not found
```

Agent source scan on `server_63_dev` did not find LVM/resource-limit contract
implementation:

```bash
grep -R "capacity_report\\|hostConfig\\|sharedMounts\\|lvcreate\\|workspaceDevice\\|thinPool" -n /home/agics/ts/agent-dev/src
```

Observed: no matches.

The agent container is privileged, but only these binds are present:

```text
/var/run/utmp:/var/run/utmp:ro
/var/log/wtmp:/host/var/log/wtmp:ro
/etc/hostname:/host/etc/hostname:ro
/home/agics/ts/agent-dev:/app:rw
/var/run/docker.sock:/var/run/docker.sock:ro
/proc:/host/proc:ro
```

## Remaining 8-Step Integration Scenario

The following items are still not proven end-to-end on `server_63_dev`:

1. Agent reports LVM thin pool capacity with `lvm.available=true`.
2. Backend Agent row updates `lvm_pool_size_gb`.
3. New request uses PyTorch Jupyter and prefilled CPU/memory/workspace limits.
4. Backend sends `create_container` with `hostConfig`, `workspace`, and
   `sharedMounts`.
5. Agent runs `lvcreate`, `mkfs`, and `mount`.
6. Agent reports `create_container_result.workspace.device`.
7. Backend stores `Container.workspace_device`.
8. Container `df /workspace` shows the requested LVM thin size.

## Next Agent-Side Gate

Before declaring the whole initiative complete, deploy an agent build that
implements `docs/agent-integration-lvm-thin-spec.ko.html` sections 3, 4, 5, and
6, then rerun the 8-step scenario above.

Minimum negative smoke path:

```bash
docker exec hypercube-agent-dev-63 sh -lc 'command -v lvcreate; command -v lvs'
docker exec hypercube-agent-dev-63 sh -lc 'lvs --units g'
```

Expected before backend LVM mode is enabled:

```text
lvcreate and lvs exist
capacity_report includes disk.lvm.available=true and thinPoolSizeGb
```
