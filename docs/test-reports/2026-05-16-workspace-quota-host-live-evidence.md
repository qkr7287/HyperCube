# Workspace quota — host-side live evidence (2026-05-16)

Verifies option 4b (XFS project quota on a loop-mounted xfs file) end-to-end
**at the host level** on `server_63_dev`. Agent-runtime and per-container
slice remains blocked on `qkr7287/HyperCube-agent#17` rework; this report
covers only the layers we can prove without that.

## Host setup (1-time, operator)

Run on `hc-dev-63` as root via the staged script
(`~/workspace-quota-setup.sh`):

```text
[1/5] apt install xfsprogs quota          -> installed (xfsprogs 5.13.0-1ubuntu2.1, quota 4.06-1build2)
[2/5] fallocate 200G loop file            -> /var/lib/hypercube/workspaces.img
[3/5] mkfs.xfs                             -> isize=512  crc=1  projid32bit=1  blocks=52428800
[4/5] mkdir mount point                    -> /var/lib/hypercube/workspaces
[5/5] mount loop,prjquota                  -> /dev/loop18, mount opts include prjquota
--- verify ---
mount         : /var/lib/hypercube/workspaces.img on /var/lib/hypercube/workspaces type xfs (rw,relatime,attr2,inode64,logbufs=8,logbsize=32k,prjquota)
xfs_quota -x  : Project quota header printed, table shows project #0 0/0/0
df            : /dev/loop18  200G  1.5G  199G  1%  /var/lib/hypercube/workspaces
```

Sized to 200 G to fit the 297 G free on `sda2 (/)`. Operator chose not
to add the fstab line; mount survives only the current boot.

## Preflight (`docs/runbooks/workspace-quota-preflight.sh`)

```text
== Host xfsprogs / quota tooling        PASS x3
== Workspace loop file + mount          PASS x3 (incl. prjquota)
== Agent runtime can drive xfs_quota    FAIL — xfs_quota missing in hypercube-agent-dev-63, mount not bind-mounted in
== Backend Agent capacity row           FAIL — column existed after `migrate agents 0009 / containers 0012`,
                                                but Agent.workspace_pool_total_gb is NULL until agent ships the quota wire
RESULT: FAIL — fix the items above before flipping any container to hard quota.
```

Host gate is fully open. The two remaining FAILs both trace back to the
HyperCube-agent rework (`docs/agent-workspace-quota-handoff.md`).

## Smoke test — hard enforcement + neighbour isolation

Run on `hc-dev-63` as root via the staged script
(`~/workspace-quota-smoketest.sh`). Creates two simulated container
workspace directories with distinct project ids and hard limits, then
exercises them.

```text
[2] assign project ids                 1001 -> .../c-test-a   1002 -> .../c-test-b
[3] set hard limits                    A: bhard=100m   B: bhard=200m
[4] initial report
    #1001    0   0   100M
    #1002    0   0   200M

[5] dd 150MB into A  (expect ENOSPC near 100MB)
    dd: error writing '.../c-test-a/big': No space left on device
    101+0 records in / 100+0 records out
    104857600 bytes (105 MB, 100 MiB) copied, 0.0597054 s
    -rw-r--r-- 1 root root 100M ... /c-test-a/big

[6] dd 150MB into B  (expect success, B unaffected)
    150+0 records in / 150+0 records out
    157286400 bytes (157 MB, 150 MiB) copied, 0.027541 s
    -rw-r--r-- 1 root root 150M ... /c-test-b/big

[7] post report
    #1001    100M    0   100M
    #1002    150M    0   200M

[cleanup] both project quotas reset to bhard=0 and dirs removed (EXIT trap)
```

## What this proves

- **Hard enforcement is real**: kernel xfs returns `ENOSPC` to userspace
  exactly at the project's `bhard` boundary. No grace, no soft fallback.
- **Per-project isolation is real**: exhausting one project's quota has
  zero effect on a sibling project sharing the same loop-mounted xfs.
- **Accounting is exact**: `xfs_quota report -h` matches actually-written
  bytes (100M / 150M) at the byte level after the run.

## What is still NOT proven (deferred)

- The HyperCube agent automatically assigning a per-container project id
  on workspace prepare. (Needs PR #17 rework.)
- A real HyperCube user container hitting ENOSPC inside its `/workspace`
  bind mount. (Needs the agent change above and a mount of
  `/var/lib/hypercube/workspaces` into `hypercube-agent-dev-63`.)
- Backend `Agent.workspace_pool_total_gb` becoming non-null on a live
  `capacity_report` push. (Same dependency.)

These items remain stop conditions and are tracked in
`progress.md` and `docs/agent-workspace-quota-handoff.md`.
