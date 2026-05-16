# LVM Thin Workspace Full Validation Runbook

This runbook is the completion gate for the container resource limits + LVM
thin workspace objective after the agent/ops blocker is resolved.

It is intentionally split from `lvm-thin-workspace-host-setup.md`: host setup is
operator work; this document is the backend/frontend integration proof path.

## Preconditions

Do not start this runbook until all of these are true:

```text
PERMISSION_OPTION=<1|2|3> has been answered on HyperCube-agent issue #16
server_63_dev has the selected permission/runtime path deployed
bash docs/runbooks/lvm-thin-workspace-preflight.sh hypercube-agent-dev-63 hc-backend exits 0
```

For real LVM mode, `PERMISSION_OPTION` must be `1` or `2`. If the explicit
answer is `3`, run only the legacy-mode checks in the final section.

## 1. Confirm Core and Agent Inputs

Run from the server 63 HyperCube checkout:

```bash
cd /home/agics/ts/HyperCube
bash docs/runbooks/lvm-thin-workspace-preflight.sh hypercube-agent-dev-63 hc-backend
```

Expected:

```text
OK   LVM thin workspace host preflight passed
```

Then confirm backend capacity has a non-null LVM pool for `server_63_dev`:

```bash
docker exec hc-backend python manage.py shell -c "
from apps.agents.models import Agent
for a in Agent.objects.order_by('hostname'):
    print(a.hostname, a.cpu_cores, a.ram_total_mb, a.lvm_pool_size_gb, a.capacity_updated_at)
"
```

Expected for LVM mode:

```text
server_63_dev <cpu_cores> <ram_total_mb> <non-null lvm_pool_size_gb> <recent timestamp>
```

If `lvm_pool_size_gb` is `None`, stop. Backend will intentionally stay in
legacy mode and omit LVM `workspace.sizeGb`, `workspace.mountTarget`, and
`sharedMounts`.

## 2. Validate Backend Recommendation Endpoint

Pick the PyTorch Jupyter template and `server_63_dev` agent:

```bash
docker exec hc-backend python manage.py shell -c "
from apps.agents.models import Agent
from apps.containers.models import ContainerTemplate
from apps.containers.services.recommend import recommend_resource_limits
agent = Agent.objects.get(hostname='server_63_dev')
template = ContainerTemplate.objects.get(name='PyTorch Jupyter GPU Workspace')
rec = recommend_resource_limits(agent, template)
print(rec.as_dict())
print('template_min', template.min_cpu_percent, template.min_memory_mb, template.min_workspace_gb)
"
```

Expected:

- `cpu_percent`, `memory_mb`, and `workspace_gb` are present.
- Values are at or above the template `min_*` floors.
- `capacity_complete` is `True` in LVM mode.

## 3. Dry-Run the Create Payload Before Submitting

Use an unsaved request object so the payload can be inspected without creating a
container:

```bash
docker exec hc-backend python manage.py shell -c "
from django.contrib.auth import get_user_model
from apps.agents.models import Agent
from apps.containers.models import ContainerRequest, ContainerTemplate
from apps.containers.serializers import ContainerRequestSerializer
from apps.containers.services.deployment import build_agent_payload
User = get_user_model()
user = User.objects.filter(is_active=True).first()
agent = Agent.objects.get(hostname='server_63_dev')
template = ContainerTemplate.objects.get(name='PyTorch Jupyter GPU Workspace')
serializer = ContainerRequestSerializer(data={
    'action': 'create',
    'template': str(template.id),
    'target_agent': str(agent.id),
    'custom_name': 'lvm-validation-dry-run',
    'cpu_percent': 400,
    'memory_mb': 16384,
    'workspace_gb': 100,
}, context={'request': type('Req', (), {'user': user})()})
serializer.is_valid(raise_exception=True)
req = ContainerRequest(requester=user, **serializer.validated_data)
req.id = '00000000-0000-4000-8000-000000000063'
payload = build_agent_payload(req, workspace_secret='dryrun-token')
params = payload['params']
print('has_hostConfig', params.get('hostConfig'))
print('workspace', params.get('workspace'))
print('sharedMounts', params.get('sharedMounts'))
"
```

Expected for LVM mode:

```text
hostConfig has memory/memorySwap/cpuQuota/cpuPeriod/oomKillDisable
workspace includes sizeGb=100 and mountTarget=/workspace
workspace still includes Jupyter metadata when template workspace is enabled
sharedMounts includes /mnt/datasets -> /datasets:ro and /mnt/models -> /models:ro
```

If `workspace.sizeGb`, `workspace.mountTarget`, or `sharedMounts` are missing in
LVM mode, stop and inspect `Agent.lvm_pool_size_gb` plus
`backend/apps/containers/services/deployment.py`.

## 4. Submit a Real Request

Use the UI request modal or REST API. For the browser path, expected UI behavior:

- Select `PyTorch Jupyter GPU Workspace`.
- Select `server_63_dev`.
- ResourceLimitForm pre-fills recommended CPU/memory/workspace values.
- Submit with a 100 GB workspace for validation.

For API-driven validation, submit a request as a real user and approve it as an
admin through the existing request flow. Do not bypass the request lifecycle for
the final proof.

Record the request id and resulting container id:

```bash
docker exec hc-backend python manage.py shell -c "
from apps.containers.models import ContainerRequest
for r in ContainerRequest.objects.order_by('-created_at')[:5]:
    print(r.id, r.status, r.custom_name, r.cpu_percent, r.memory_mb, r.workspace_gb, r.target_container_id)
"
```

Expected:

```text
request status eventually deployed
target_container_id is populated
cpu_percent/memory_mb/workspace_gb match the submitted limits
```

## 5. Verify Agent LVM Actions

On the host:

```bash
sudo lvs -o lv_name,vg_name,lv_size,data_percent,lv_tags --units g
findmnt /var/lib/hypercube/workspaces
```

Expected:

- A managed `cid_<short-container-id>` thin LV exists.
- The LV is mounted under `/var/lib/hypercube/workspaces/<short-container-id>`.

Inside the created container:

```bash
docker exec <container-id-or-name> df -h /workspace
docker exec <container-id-or-name> mount | grep ' /workspace '
```

Expected:

```text
/workspace visible size matches requested workspace_gb
/workspace is backed by the per-container mounted host workspace
```

## 6. Verify Backend Workspace Persistence

```bash
docker exec hc-backend python manage.py shell -c "
from apps.containers.models import Container
for c in Container.objects.order_by('-last_seen')[:10]:
    print(c.container_id, c.name, c.cpu_percent_limit, c.memory_mb_limit, c.workspace_gb_limit, c.workspace_device)
"
```

Expected for the new validation container:

```text
cpu_percent_limit=<submitted cpu_percent>
memory_mb_limit=<submitted memory_mb>
workspace_gb_limit=<submitted workspace_gb>
workspace_device=/dev/<vg>/cid_<short-container-id>
```

## 7. Verify Workspace Metrics and UI Denominators

Wait for at least one `container_metrics` push, then check current metrics:

```bash
docker exec hc-backend python manage.py shell -c "
import json
from apps.common.redis_client import get_redis_client
from apps.containers.models import Container
c = Container.objects.order_by('-last_seen').first()
r = get_redis_client()
keys = [
    f'server:{c.agent_id}:container:{c.container_id}:metrics',
    f'server:{c.agent_id}:container:{c.container_id[:12]}:metrics',
]
for key in keys:
    raw = r.get(key)
    if raw:
        print(key)
        print(json.dumps(json.loads(raw).get('data', {}).get('workspace'), ensure_ascii=False, indent=2))
"
```

Expected:

```text
workspace.device is present
workspace.sizeGb is present
workspace.usedGb/availableGb/usedPct are present after the agent reports them
```

Browser checks on `/user/containers/<containerId>`:

- `ContainerKpiBar` CPU chip shows `limit <n> cores`.
- Memory chip shows `limit <n> GB`.
- Workspace card shows `limit <n> GB` and used/limit raw text.
- CPU chart label shows `CPU % (of <n> cores quota)`.
- Memory chart label shows `Memory % (of <n> GB quota)`.
- Tooltip denominator line identifies the quota.

## 8. Pass/Fail Decision

Pass only if all of these are true:

```text
capacity_report populated Agent.lvm_pool_size_gb
recommendation endpoint returned capacity_complete=True
create payload included hostConfig, LVM workspace fields, and sharedMounts
agent created and mounted the thin LV
container df /workspace showed the requested quota
backend stored Container.workspace_device
workspace metrics reached backend
KPI cards and charts displayed quota denominators
existing no-LVM containers still render with unlimited/legacy hints
```

Any missing item means the overall objective is not complete.

## Legacy-Mode Check for PERMISSION_OPTION=3

If the explicit operational decision is `PERMISSION_OPTION=3`, validate legacy
compatibility instead of LVM creation:

```bash
cd /home/agics/ts/HyperCube
bash docs/runbooks/lvm-thin-workspace-preflight.sh hypercube-agent-dev-63 hc-backend || true
```

Expected legacy state:

```text
Agent.lvm_pool_size_gb=None
agent capacity_report uses disk.lvm.available=false
create payload still includes hostConfig
create payload omits LVM workspace.sizeGb and workspace.mountTarget
create payload omits sharedMounts
existing Jupyter workspace metadata remains intact
KPI chips for legacy containers show unlimited/host hints
```

Legacy mode does not satisfy the full LVM thin workspace DoD. It is only a
backward-compatible operating mode until LVM is enabled.
