# Workspace quota — agent rework live evidence (2026-05-16 17:30 KST)

Core-side validation of `qkr7287/HyperCube-agent` PR #17 (head `024028e`)
after the agent developer deployed the rework on `server_63_dev` and
`server_16_dev`. Captures what passed, the one open bug, and the manual
fix that proves the underlying mechanism works.

## What passed (in order along the slice)

### Backend Agent capacity row

```
server_63_dev:  cpu=12  ram=15897 MB
  workspace_pool_total_gb       = 200
  workspace_pool_free_gb        = 199
  workspace_pool_mount          = /var/lib/hypercube/workspaces
  workspace_hard_enforcement    = true
  capacity_updated_at           = 2026-05-16 08:03:29 UTC

server_16_dev (no host setup — legacy mode kept):
  pool fields = NULL
  workspace_hard_enforcement    = false
```

Regression rule satisfied: an agent on a host without xfs+prjquota
setup keeps reporting capacity, does not crash, and signals
`available=false` cleanly. Backend stores it as legacy.

### Backend test suite

```
ssh hc-dev-63 "docker exec hc-backend python manage.py test apps.containers apps.agents apps.common apps.metrics"
Ran 100 tests in 80.679s — OK
```

### Frontend

```
cd frontend && npm test     -> 4 files, 58 passed (Vitest 2.9 s)
cd frontend && npm run check -> svelte-check: 0 errors, 193 warnings (all pre-existing unused CSS)
```

### Recommend API

```
GET /api/containers/recommend/?template=183da5b0-...&agent=053ce574-...
{
  "cpu_percent": 200, "memory_mb": 3072, "workspace_gb": 40,
  "min_cpu_percent": 100, "min_memory_mb": 2048, "min_workspace_gb": 10,
  "workspace_pool_total_gb": 200, "workspace_pool_free_gb": 199,
  "workspace_hard_enforcement": true,
  "capacity_complete": true, "target_users": 4, "safety_margin": 0.8
}
```

Frontend NewRequestModal renders the prefill correctly and shows the
label `host의 20% 점유 · hard enforced` next to the Workspace slider
when server_63_dev is selected (screenshot in chrome session).

### Container deploy

```
POST /api/requests/                   -> id a1ee6632-618d-4960-a0a7-3c8cf3f22cdb (pending)
POST /api/requests/<id>/approve/      -> approved
(poll)                                 -> deployed in <5 s,
                                          target_container = 70106824ba37
```

Backend `Container` row after deploy:

```
container_id          = 70106824ba37 (full sha truncated above)
workspace_device      = /var/lib/hypercube/workspaces/e22020af450e
workspace_project_id  = 1340189
workspace_gb_limit    = 10
cpu_percent_limit     = 100
memory_mb_limit       = 2048
limit_updated_at      = 2026-05-16 08:24:38 UTC
```

Docker inspect of `70106824ba37`:

```
HostConfig.Memory     = 2147483648   (= 2048 MiB)
HostConfig.CpuQuota   = 100000
HostConfig.CpuPeriod  = 100000       (=> 1.0 cores)
Mounts                = /var/lib/hypercube/workspaces/e22020af450e -> /workspace
                       /mnt/datasets -> /datasets
                       /mnt/models   -> /models
```

`lsattr` on the workspace dir (from the agent container):

```
1340189 -------------------P-- /var/lib/hypercube/workspaces/e22020af450e
```

`xfs_quota -x -c 'state -p' /var/lib/hypercube/workspaces`:

```
Project quota state on /var/lib/hypercube/workspaces (/dev/loop18)
  Accounting:  ON
  Enforcement: ON
  Inode: #131 (3 blocks, 3 extents)
```

## Open bug — setquota unit off by 1024×

`xfs_quota -x -c 'report -hN' /var/lib/hypercube/workspaces`
immediately after deploy (workspace_gb=10):

```
#1340189    0    10T    10T   00 [------]
```

Soft and hard report `10T` rather than `10G`. dd inside the container
writes 10 GB without ENOSPC:

```
$ docker exec 70106824ba37 sh -c 'dd if=/dev/zero of=/workspace/big bs=1M count=10241'
10241+0 records in
10241+0 records out
10738466816 bytes (10.0GB) copied, 31.97 s, 320.3MB/s
# no error — quota at 10T is well above the 10G write
```

Manual correction with `xfs_quota -x -c 'limit -p bhard=10g bsoft=10g 1340189'`
gives the report `0 10G 10G`, and the next dd run fails cleanly at the
expected boundary:

```
$ docker exec 70106824ba37 sh -c 'dd if=/dev/zero of=/workspace/big bs=1M count=11264'
dd: error writing '/workspace/big': No space left on device
10241+0 records in
10240+0 records out
10737418240 bytes (10.0GB) copied, 35.06 s, 292.0MB/s
```

Post-test report (cleanup `rm -f /workspace/big`):

```
#1340189   0   10G   10G   00 [------]
```

`setquota -P <id> <bsoft> <bhard> 0 0 <mount>` takes block-soft and
block-hard in **1 KiB blocks**. If the agent passes `hardGb * 1024**3`
(bytes) the kernel scales it by 1024 → `hardGb × 1 TiB`. The 10 GB
request → 10 TiB enforcement matches exactly. Reported as
`qkr7287/HyperCube-agent#16` comment 4466315428.

## What the validation runbook still needs

`docs/runbooks/workspace-quota-full-validation.md` steps 4–6:

- A redeploy with the agent fix that lands the same report row as
  `#<projectid>   0   10G   10G` with no manual `limit -p` call.
- dd over `hardGb*1024+1` MiB from inside the container hitting ENOSPC.
- A neighbour quota container on the same host showing independent
  used/limit, dd in container A not affecting container B's df.
- `bash docs/runbooks/workspace-quota-preflight.sh hypercube-agent-dev-63 hc-backend`
  exit 0. Note: the preflight's `[backend Agent capacity row]` check
  currently treats `server_16_dev` (legacy mode) as a failure. A small
  fix to filter on `hostname` or to allow mixed-mode fleets is a minor
  follow-up.

PR #17 stays draft until the redeploy lands.
