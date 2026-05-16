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
PASS host setup: <operator initials> <UTC timestamp>
mount output:
    /var/lib/hypercube/workspaces.img on /var/lib/hypercube/workspaces type xfs (rw,loop=...,prjquota)
xfs_quota -x -c "state" /var/lib/hypercube/workspaces:
    Project quota state on /var/lib/hypercube/workspaces (/dev/loopN)
      Accounting: ON
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
PASS preflight: <UTC timestamp>
exit code: 0
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
PASS agent deploy: <UTC timestamp>
agent image: <digest>
self-test stdout:
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
PASS backend tests: <commit hash> <UTC timestamp> Ran N tests OK
PASS frontend tests: <UTC timestamp>
PASS browser flow: <container_id> <UTC timestamp>
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
PASS df /workspace == hard_gb: <UTC timestamp>
    df output: ...
PASS dd over limit -> ENOSPC: <UTC timestamp>
    dd stderr: dd: error writing '/workspace/big': No space left on device
PASS neighbour container unaffected: <other_container_id>
    df output: ...
```

## 6. Sign-off

The slice is complete when every PASS marker above is filled in and
the agent self-test stays green for 24 h. Update `progress.md` with
the sign-off timestamp and close `HyperCube-agent#16`.
