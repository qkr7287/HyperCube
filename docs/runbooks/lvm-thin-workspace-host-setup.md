# LVM Thin Workspace Host Setup Runbook

This runbook is the operator gate for enabling HyperCube per-container
`/workspace` quotas through LVM thin volumes.

It applies to `server_63_dev` first, then to any future GPU agent host.

## Scope

Backend/frontend support is already implemented in HyperCube core:

- Container request limits: `cpu_percent`, `memory_mb`, `workspace_gb`.
- Agent capacity telemetry: `capacity_report`.
- Agent create payload: `hostConfig`, LVM `workspace`, `sharedMounts`.
- KPI/chart quota display.

This runbook covers only the host/agent runtime prerequisites required before
the full LVM end-to-end scenario can be declared complete.

## Current server_63_dev State

Observed on 2026-05-15:

```text
host command -v lvcreate -> <empty>
host command -v lvs -> <empty>
host command -v mkfs.ext4 -> /usr/sbin/mkfs.ext4
host command -v mount -> /usr/bin/mount
host lvs --units g -> bash: line 1: lvs: command not found

/dev/sda2 ext4 mounted at /
/dev/sdb2 vfat mounted at /media/agics/ARCHIVE
/mnt/datasets -> missing
/mnt/models -> missing

hypercube-agent-dev-63 command -v lvcreate -> <empty>
hypercube-agent-dev-63 command -v lvs -> <empty>
```

Do not use `/dev/sdb` or `/dev/sdb2` for LVM unless an operator explicitly
confirms that the existing ARCHIVE data may be destroyed or has been migrated.

## Preconditions

Before enabling LVM mode, record these decisions in the HyperCube-agent tracking
issue:

```text
PERMISSION_OPTION=<1|2|3>
LVM_DEVICE=<approved block device or existing vg/thin pool>
NFS_DATASETS=<NFS export or explicit shared-mount policy change>
NFS_MODELS=<NFS export or explicit shared-mount policy change>
```

Permission options:

- `1`: privileged agent container with host LVM tooling available in the agent
  runtime.
- `2`: host-side helper/service invoked by the agent.
- `3`: no LVM on this host yet; agent must report `disk.lvm.available=false`.

## Non-Destructive Preflight

Run on the host:

```bash
set -eu

echo "[tools]"
command -v lvcreate || true
command -v lvs || true
command -v mkfs.ext4 || true
command -v mount || true
command -v umount || true
command -v lvremove || true

echo "[storage]"
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT
df -hT / /var/lib/docker /mnt/datasets /mnt/models 2>&1 || true

echo "[lvm]"
lvs --units g 2>&1 || true
vgs --units g 2>&1 || true
pvs --units g 2>&1 || true
```

Run inside the deployed agent container:

```bash
docker exec hypercube-agent-dev-63 sh -lc '
  command -v lvcreate || true
  command -v lvs || true
  command -v mkfs.ext4 || true
  command -v mount || true
  command -v umount || true
  command -v lvremove || true
  lvs --units g 2>&1 || true
'
```

Expected before LVM mode can be validated:

```text
lvcreate/lvs/mkfs.ext4/mount/umount/lvremove exist where the chosen permission
model needs them
lvs --units g shows vg0/thin_pool or the configured equivalent
/mnt/datasets and /mnt/models exist, or sharedMounts are explicitly disabled or
changed in the backend-agent contract
```

## Host Package Gate

If the host lacks LVM tools, install the required packages through the approved
host administration process. Example for Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y lvm2 nfs-common util-linux e2fsprogs
```

Do not install packages from inside the agent hot path.

## Thin Pool Setup

Use an existing volume group and thin pool if one is already provisioned.

To create a new pool, first choose an approved empty block device. The following
example is intentionally parameterized; do not paste it with a real disk until
the device is confirmed safe:

```bash
export HC_LVM_DEVICE=/dev/<approved-empty-device>
export HC_LVM_VG=vg0
export HC_LVM_THIN_POOL=thin_pool

lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT "$HC_LVM_DEVICE"
sudo wipefs -n "$HC_LVM_DEVICE"

# Destructive from this point onward.
# Requires explicit operator approval for HC_LVM_DEVICE.
sudo pvcreate "$HC_LVM_DEVICE"
sudo vgcreate "$HC_LVM_VG" "$HC_LVM_DEVICE"
sudo lvcreate -L 80%VG -T "$HC_LVM_VG/$HC_LVM_THIN_POOL"
sudo lvs --units g "$HC_LVM_VG/$HC_LVM_THIN_POOL"
```

If a partition is already mounted or has a filesystem, stop and get operator
approval. Do not overwrite mounted filesystems.

## Shared Mount Setup

The backend sends these read-only shared mounts when LVM workspace mode is
active:

```text
/mnt/datasets -> /datasets:ro
/mnt/models -> /models:ro
```

Prepare them through NFS or a deliberately approved equivalent:

```bash
sudo mkdir -p /mnt/datasets /mnt/models

# Example only. Replace <nfs-server> and exports with the operator-approved
# values, then persist through /etc/fstab or systemd mount units.
sudo mount -t nfs -o ro <nfs-server>:/datasets /mnt/datasets
sudo mount -t nfs -o ro <nfs-server>:/models /mnt/models

findmnt /mnt/datasets
findmnt /mnt/models
```

## Agent Runtime Gate

After host setup, ensure the agent can use the chosen permission model.

For option `1`, the agent container must expose the required tooling and host
mount namespace permissions. The minimum smoke path is:

```bash
docker exec hypercube-agent-dev-63 sh -lc '
  command -v lvcreate
  command -v lvs
  command -v mkfs.ext4
  command -v mount
  command -v umount
  command -v lvremove
  lvs --units g
'
```

For option `2`, run the same host preflight plus the helper-specific smoke test
defined by the agent implementation. The helper must own rollback for failed
`lvcreate`, `mkfs.ext4`, `mount`, `umount`, and `lvremove` operations.

For option `3`, do not send `workspace` from backend. The agent must report:

```json
{
  "disk": {
    "lvm": {
      "available": false
    }
  }
}
```

## Backend Readiness Check

After agent deployment, confirm capacity reaches the backend:

```bash
docker exec hc-backend python manage.py shell -c "
from apps.agents.models import Agent
for a in Agent.objects.order_by('hostname'):
    print(a.hostname, a.cpu_cores, a.ram_total_mb, a.lvm_pool_size_gb, a.capacity_updated_at)
"
```

Expected for LVM mode:

```text
server_63_dev <cpu> <ram> <non-null lvm_pool_size_gb> <recent timestamp>
```

If `lvm_pool_size_gb` remains `None`, backend stays in legacy mode and omits the
LVM `workspace` payload.

## Full Validation Gate

Only after the gates above pass, run the integration scenario:

1. Agent sends `capacity_report` with `disk.lvm.available=true`.
2. Backend Agent row updates `lvm_pool_size_gb`.
3. Submit a new PyTorch Jupyter request with recommended CPU/memory/workspace
   values.
4. Confirm backend sends `create_container.params.hostConfig`,
   `params.workspace`, and `params.sharedMounts`.
5. Confirm agent runs `lvcreate`, `mkfs.ext4`, and `mount`.
6. Confirm agent returns `create_container_result.data.workspace.device`.
7. Confirm backend stores `Container.workspace_device`.
8. Confirm inside the container:

```bash
df -h /workspace
mount | grep ' /workspace '
```

The visible `/workspace` size must match the requested `workspace_gb`.

## Rollback Notes

For a failed test container, the agent should remove only volumes it created and
identified through its managed labels. Manual cleanup must verify the volume
name before deletion:

```bash
lvs -o lv_name,vg_name,lv_size,origin,data_percent,lv_tags
sudo umount /var/lib/hypercube/workspaces/<short-container-id>
sudo lvremove -f vg0/cid_<short-container-id>
sudo rmdir /var/lib/hypercube/workspaces/<short-container-id>
```

Never run broad `lvremove`, `rm -rf`, or `wipefs` commands from this runbook.
