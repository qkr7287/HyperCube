# HyperCube-agent PR17 Server-63 Runtime Sync - 2026-05-16

## Status

HyperCube-agent PR #17 is still draft and the overall LVM thin workspace goal is
not complete, but the dev server-63 agent runtime has now been synced far enough
to validate the non-destructive runtime path.

This report supersedes the older statement that PR #17 was not deployed to
server 63. The code is not merged, and the real LVM end-to-end path is still
blocked by host/runtime prerequisites.

## Remote Runtime Sync

Runtime target:

```text
host: hc-dev-63
runtime path: /home/agics/ts/agent-dev
agent container: hypercube-agent-dev-63
backend container: hc-backend
```

Files synced from the PR #17 remote-safe temp workspace into the bind-mounted
agent runtime included the LVM workspace implementation, capacity/types/sync
changes, and the GPU collector needed to preserve the current GPU contract.

Backups created before applying runtime changes:

```text
/home/agics/ts/agent-dev-pr17-sync-backup-20260516T010102Z.tgz
src/collectors/gpu-per-container.ts.pre-pr17-20260516T010343Z
src/self-tests/gpu-per-container.ts.pre-pr17-stale-20260516T010420Z
```

The stale remote `src/self-tests/gpu-per-container.ts` was moved out of the
TypeScript build because it was not present in the PR #17 temp tree and expected
an old `__test` export from the GPU collector.

GPU collector hash after sync:

```text
3022143779459cde0f4fae00591fc88cca5a4d0e0dfd0f6808a9b061a9081948  src/collectors/gpu-per-container.ts
```

## Runtime Validation

Command run inside the dev agent container:

```bash
docker exec hypercube-agent-dev-63 sh -lc 'cd /app && npm run build && node dist/self-tests/resource-limits-lvm.js && node dist/self-tests/create-container-network-policy.js'
```

Observed result:

```text
> hypercube-agent@1.0.0 build
> tsc

resource limits and LVM workspace self-test passed
create_container networkPolicy self-test passed
```

## Restart and Capacity Report

The agent container was restarted after build/self-test success.

Observed reconnect log excerpt:

```text
Starting HyperCube Agent (server_63_dev)
Docker connection established.
Agent registered: 053ce574-c2b3-474b-a8ca-a34ec43f9d52 (approved)
ws Connected.
Collecting every 5000ms
```

Backend `Agent` row after restart:

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

This confirms the restarted agent is reporting host capacity and the backend is
updating the Agent model. It also confirms the host remains in legacy/no-LVM
mode because `lvm_pool_size_gb` is still `null`.

## Latest Preflight

Command:

```bash
cd /home/agics/ts/HyperCube
bash docs/runbooks/lvm-thin-workspace-preflight.sh hypercube-agent-dev-63 hc-backend
```

Observed result: exit 1.

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
server_16_dev 12 39760 None 2026-05-16 01:03:45.206653+00:00
server_63_dev 12 15897 None 2026-05-16 01:04:44.080208+00:00
FAIL LVM thin workspace host preflight failed
```

## Current Gate

The non-destructive agent runtime path is validated on server 63. The remaining
completion gate is still operational:

1. Choose and record `PERMISSION_OPTION=<1|2|3>` in HyperCube-agent issue #16.
2. If LVM mode is selected, install/provide LVM tooling in the host and agent
   runtime.
3. Prepare an approved thin pool without touching existing data disks unless an
   operator explicitly approves it.
4. Create/provide `/mnt/datasets`, `/mnt/models`, and
   `/var/lib/hypercube/workspaces`.
5. Re-run the preflight until it exits 0.
6. Run the full 8-step LVM `/workspace` validation.

No LVM pool creation, package installation, or disk mutation was attempted.
