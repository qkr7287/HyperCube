# Workspace Quota — Full Validation Runbook

Date adopted: 2026-05-16
Supersedes: `docs/runbooks/archived/lvm-thin-workspace-host-setup.md`
Tracking: HyperCube `progress.md` "워크스페이스 quota 슬라이스" section.

Goal: per-container `/workspace` hard enforcement on the host via XFS
project quota on a loop-mounted xfs file (option 4b). One-time host
setup, then end-to-end verification: `df /workspace == hard_gb`,
`dd` over limit returns `ENOSPC`, neighbouring containers untouched.

This document is the operator gate. Every step records its evidence
inline; the slice is "done" only when every PASS marker is filled in.

## 0. Roles

| Step | Who | Where |
| ---- | --- | ----- |
| 1 Host setup (5 lines) | Operator with root on server-63 | server-63 shell |
| 2 Preflight | Operator | server-63 shell |
| 3 Agent rework deploy | HyperCube-agent owner | agent repo CI |
| 4 Backend / browser verification | HyperCube core (you) | core repo + dev browser |
| 5 In-container df / dd evidence | Operator + you | container shell |
| 6 Sign-off | You | this runbook |

## 1. One-time host setup (operator)

Run on server-63 as root. Five commands total. Idempotent.

```bash
apt-get install -y xfsprogs quota                                            # xfs_quota + setquota
fallocate -l 2000G /var/lib/hypercube/workspaces.img                         # loop file (size = workspace pool)
mkfs.xfs /var/lib/hypercube/workspaces.img                                   # native xfs (do NOT touch /dev/sdb*)
mkdir -p /var/lib/hypercube/workspaces                                       # mount point
mount -o loop,prjquota /var/lib/hypercube/workspaces.img /var/lib/hypercube/workspaces
```

Persist across reboot via `/etc/fstab`:

```fstab
/var/lib/hypercube/workspaces.img  /var/lib/hypercube/workspaces  xfs  loop,prjquota  0 0
```

The agent container must bind-mount `/var/lib/hypercube/workspaces` and
either run privileged or with `CAP_SYS_ADMIN` + `/dev/loop-control` so
it can invoke `xfs_quota -x -c "project -s -p ..."` and
`setquota -P <prjid> <hard_gb_bytes> ...`.

**ARCHIVE protection**: `/dev/sdb` / `/dev/sdb2` ARCHIVE must NOT be
touched. The loop file lives on the existing root (`/`) ext4 filesystem.

Evidence to paste back here:

```text
PASS host setup: agics (operator) 2026-05-16T05:32Z
  (sized to 200G to fit / 297G free; fstab line not yet added — mount survives only current boot)
mount output:
    /var/lib/hypercube/workspaces.img on /var/lib/hypercube/workspaces type xfs
        (rw,relatime,attr2,inode64,logbufs=8,logbsize=32k,prjquota)
xfs_quota -x -c "state -p" /var/lib/hypercube/workspaces:
    Project quota state on /var/lib/hypercube/workspaces (/dev/loop18)
      Accounting:  ON
      Enforcement: ON
```

## 2. Preflight (read-only)

From the HyperCube core checkout:

```bash
bash docs/runbooks/workspace-quota-preflight.sh hypercube-agent-dev-63 hc-backend
```

Expected:

```text
RESULT: PASS — workspace quota gate is open.
```

If any check fails the script prints the offending command output and
exits non-zero. Fix the failing check and re-run; do not move to step 3.

```text
PARTIAL preflight: 2026-05-16T08:24Z exit=1
  PASS host xfsprogs / quota tooling x3
  PASS workspace loop file + mount x3 (incl. prjquota)
  PASS agent runtime can drive xfs_quota x3 (post agent rework deploy)
  FAIL [backend Agent capacity row] — script treats server_16_dev (legacy mode) as
       a fleet-wide failure; needs hostname filter or mixed-mode-aware check.
       Track as minor follow-up; not a slice blocker.
```

## 3. Agent rework deploy

Tracking issue / PR for the agent repo: `qkr7287/HyperCube-agent#16`.
The earlier LVM PR `#17` is **superseded**; the rework lands as either a
fresh PR or a forced-push to the existing branch (the agent owner
decides). Self-contained agent prompt is checked into the core repo at
`progress.md` "PR #17 rework prompt" section — paste it verbatim to the
agent dev session.

Acceptance for this step:

- `hypercube-agent-dev-63` container is running the new build.
- 5 minutes of `docker logs hypercube-agent-dev-63` shows no
  `workspace-quota` errors.
- Agent self-test `src/self-tests/resource-limits-quota.ts`
  (rename of `resource-limits-lvm.ts`) returns ok.

```text
PASS agent deploy (partial): 2026-05-16T05:58Z head 024028e on hypercube-agent-dev-63 + dev-16
  capacity_report, recommend, create_container payload, hostConfig mapping, workspace bind,
  project assignment, prjquota Enforcement=ON all verified by core.
OPEN BUG: setquota value 1024× over-scaled (workspace_gb=10 -> 10T). See
  qkr7287/HyperCube-agent#16 comment 4466315428 and
  docs/test-reports/2026-05-16-workspace-quota-agent-rework-live-evidence.md.
  Self-test pass on agent side; this is a unit-conversion regression caught only by
  in-container dd evidence (step 5 below).
```

## 4. Backend / browser verification

Backend tests:

```bash
ssh hc-dev-63 "docker exec hc-backend python manage.py test apps.containers apps.agents apps.common apps.metrics"
```

Expect: `Ran 100 tests in <Ns> OK` (or higher count if new tests added).

Frontend:

```bash
cd frontend && npm test && npm run check
```

Expect: Vitest passes (currently 58 tests across 4 files);
`svelte-check found 0 errors`.

Browser (hc-dev-63 isolated context, user1 / agics12!@):

1. Open `http://192.168.0.63:3000/user/containers/new` (or wherever
   `NewRequestModal` is launched).
2. Pick the PyTorch Jupyter template, pick `server_63_dev` as target.
3. Confirm the recommend prefill: `workspace_gb` matches
   `min_workspace_gb` or the host-pool-derived value, the
   `host의 X% 점유 · hard enforced` label is present.
4. Submit the request. Watch the container provisioning to `deployed`.
5. Inspect the container detail page: KPI workspace chip shows
   `X / Y GB`; `UserMetricChart` denominator equals the requested
   `hard_gb`.

```text
PASS backend tests: d03e046 2026-05-16T08:18Z Ran 100 tests in 80.679s OK
PASS frontend tests: 2026-05-16T08:18Z Vitest 58/58 + svelte-check 0 errors / 193 warnings
PASS browser flow: 70106824ba37 2026-05-16T08:24Z
  prefill: cpu_percent=200 memory_mb=3072 workspace_gb=40
  recommend response includes workspace_pool_total_gb=200, workspace_pool_free_gb=199,
    workspace_hard_enforcement=true
  "host의 X% 점유 · hard enforced" label rendered on Workspace slider for server_63_dev
  request a1ee6632 -> approved -> deployed (<5s)
  Container row: workspace_device=/var/lib/hypercube/workspaces/e22020af450e
                 workspace_project_id=1340189 workspace_gb_limit=10
  Docker inspect: HostConfig.Memory=2147483648 CpuQuota=100000 CpuPeriod=100000
                  Bind mount e22020af450e -> /workspace present
```

## 5. In-container hard enforcement evidence

From an exec into the newly created container (requested hard_gb=20):

```bash
df -h /workspace
# expect: Size column == 20G (matches requested hard_gb)
dd if=/dev/zero of=/workspace/big bs=1M count=20480
# expect: dd: write error: No space left on device
rm -f /workspace/big
```

Cross-check from a different user's container on the same host:

```bash
docker exec <other-container> df -h /workspace
# expect: independent Size value, unaffected by neighbour's dd
```

```text
PARTIAL df /workspace == hard_gb: 2026-05-16T09:10Z
    With as-shipped agent: df shows 199G (limit was 10T due to setquota unit bug).
    With manual `xfs_quota -x -c "limit -p bhard=5g 1340189"`: df shows 5.0G as expected.
    Mechanism proven; awaiting agent fix to remove the manual step.

PASS dd over limit -> ENOSPC: 2026-05-16T09:13Z
    Container 70106824ba37 (project 1340189, manual bhard=5g):
      dd if=/dev/zero of=/workspace/big bs=1M count=6144
      dd: error writing '/workspace/big': No space left on device
      5121+0 records in / 5120+0 records out
      5368709120 bytes (5.0GB) copied, 16.19 s
    xfs report: #1340189   5G   5G   5G

PASS neighbour container unaffected: 4856610649d6 (project 5959819, manual bhard=2g)
    Before A's dd:   df  2.0G   0   2.0G   0%
    During A's dd:   df  2.0G   0   2.0G   0%  (unchanged)
    After:           dd 3G -> ENOSPC at 2147483648 bytes; xfs report 5959819 2G/2G,
                     1340189 still at 5G/5G (each project independent).
    Container 70106824ba37 and 4856610649d6 are left in place with cleaned files
    and corrected quotas (5G/2G) for the agent dev to verify the fix in-place.
```

## 6. Sign-off

The slice is complete when every PASS marker above is filled in and
the agent self-test stays green for 24 h. Update `progress.md` with
the sign-off timestamp and close `HyperCube-agent#16`.

**Sign-off status (2026-05-16T09:15Z): BLOCKED on agent setquota unit
fix.** Steps 1, 2 (host portion), 3 (deploy portion), 4 are all PASS.
Step 5 mechanism is PROVEN with manual quota correction but the
as-shipped agent over-scales the limit by 1024×, so the runbook's
acceptance ("df /workspace == hard_gb out of the box") is not yet met.
Once the agent re-deploys with the correct unit math (and projects
1340189, 5959819 self-correct to 10G/10G on next reconcile), this
runbook flips to full PASS; PR #17 to ready-for-review;
`HyperCube-agent#16` close.
