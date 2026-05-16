# HyperCube Progress

## Current Work - 2026-05-16 (workspace quota slice)

### Decision (2026-05-16): LVM thin → XFS prjquota on loop file (option 4b)

Per-container `/workspace` hard enforcement now ships via XFS project
quota on a loop-mounted xfs file, not LVM thin volumes. Zero reboot /
partition reshape; the operator runs a 5-line host setup once. The
earlier LVM plan (and `qkr7287/HyperCube-agent#17`) is superseded.

Self-contained agent rework prompt: `docs/agent-workspace-quota-handoff.md`.
Full validation runbook: `docs/runbooks/workspace-quota-full-validation.md`.

### Slice status

- Backend: DONE — migrations `agents/0009_workspace_quota_capacity`,
  `containers/0012_workspace_quota_metadata`; consumers / services /
  serializers / admin / viewsets all renamed; legacy LVM wire still
  accepted as transitional fallback.
- Backend tests: 100/100 OK on hc-dev-63.
- Frontend: DONE — `ResourceLimitForm` / `NewRequestModal` /
  `ContainerKpiBar` / container detail copy all on the quota wire.
- Frontend tests: 58/58 vitest OK; `svelte-check` 0 errors.
- Docs: DONE — `agent-payload-contract.md`, `agent-protocol.md`,
  `api.md`, `operations.md` all rewritten in quota terms with the
  legacy LVM fallback documented.
- Runbooks: `workspace-quota-preflight.sh` and
  `workspace-quota-full-validation.md` shipped; old LVM runbooks moved
  to `docs/runbooks/archived/` with supersede headers.

### Stop-condition handoffs (external)

1. ~~**Operator host setup**~~ — DONE 2026-05-16 on server-63 with a
   200G loop file (sized to fit `/`'s 297G free, not the 2 TB
   placeholder shown in earlier handoffs). Live evidence is in
   `docs/test-reports/2026-05-16-workspace-quota-host-live-evidence.md`.
   Re-mount survives only the current boot; fstab line not yet added
   (operator chose to skip the optional reboot-survival entry).

2. **HyperCube-agent PR rework** — paste
   `docs/agent-workspace-quota-handoff.md` verbatim to the agent
   developer. Either force-push #17 or open a fresh PR; close #16 only
   after the full-validation runbook has every PASS marker filled in.
   Until then, agent capacity rows continue to land via the legacy LVM
   wire and `Agent.workspace_pool_total_gb` stays NULL.

### Live evidence — host-side hard enforcement (2026-05-16)

Recorded on server-63 (`/dev/loop18` -> `/var/lib/hypercube/workspaces`,
200 G XFS, mounted with `loop,prjquota`):

- Project 1001 with `bhard=100m`: `dd ... count=150` stopped at 100 MiB
  with `No space left on device` (104857600 bytes written, then ENOSPC).
- Project 1002 with `bhard=200m` on the same mount: `dd ... count=150`
  completed cleanly (157286400 bytes). Neighbour isolation proven.
- Post-run `xfs_quota report -h` confirms `1001: 100M/100M` and
  `1002: 150M/200M`. Cleanup trap restored both projects to `bhard=0`.

### Remaining acceptance (deferred — needs PR #17 rework)

- `df /workspace` inside a real HyperCube container equals requested
  `hardGb` (needs agent to set the project id on the workspace bind
  mount).
- `dd ... bs=1M count=$((hardGb*1024+1))` fails with `ENOSPC` from
  inside the container.
- A neighbour HyperCube container on the same host is unaffected.
- `workspace-quota-preflight.sh` exits 0 — currently FAIL on `[agent
  runtime can drive xfs_quota]` (no `xfs_quota` binary in
  `hypercube-agent-dev-63`, no bind mount of `/var/lib/hypercube/
  workspaces` into the agent container) and on `[backend Agent capacity
  row]` (column exists post-migration, but the row is NULL until the
  agent ships the quota wire).

### Earlier LVM-thin work (superseded — kept for history)

Core repo status before pivot: implemented, validated, committed, and
pushed to `dev`. Full LVM thin end-to-end validation was blocked by
server 63 host/agent runtime setup and the missing agent-side
permission decision — the option-4b decision resolves both.

Implementation baseline:

```text
7454fdd feat(containers): add resource limits and workspace quotas
```

Latest checked core commits before this progress refresh:

```text
867f87d docs(containers): record no-lvm hostconfig progress
385a53c docs(containers): record no-lvm hostconfig validation
a1b033c docs(containers): expand lvm progress preflight evidence
93f439a docs(containers): expand latest lvm preflight evidence
e4e9e9a docs(containers): clarify lvm audit compare baseline
fce24b1 docs(containers): refresh lvm progress head evidence
3e97028 docs(containers): refresh lvm audit head evidence
ea9c259 docs(containers): link 2026-05-16 audit addendum
c7fec88 docs(containers): add 2026-05-16 completion audit addendum
8e81883 docs(containers): record 2026-05-16 lvm blocker recheck
bf30668 chore(containers): normalize workspace service line endings
e9e8394 fix(containers): clear unenforced legacy workspace quota
1f12568 docs(containers): clarify template model path in audit
```

Implemented core scope:

- Template resource weights and min floors.
- Agent capacity columns and `capacity_report` handling.
- Host-capacity resource recommendation helper and REST endpoint.
- ContainerRequest CPU/memory/workspace fields and validation.
- Container CPU/memory/workspace limit snapshots and workspace device fields.
- Agent create payload `hostConfig`, LVM `workspace`, and `sharedMounts`.
- Workspace metadata persistence from create result.
- Legacy no-LVM mode keeps existing Jupyter workspace metadata while omitting
  only LVM `sizeGb`, `mountTarget`, and `sharedMounts`.
- Legacy no-LVM create responses keep CPU/memory limits but do not persist an
  unenforced `workspace_gb_limit` unless the agent returns concrete workspace
  metadata.
- Live server-63 dry-run confirms `server_63_dev` keeps `hostConfig` but omits
  LVM `sizeGb`, `mountTarget`, and `sharedMounts` while `lvm_pool_size_gb=None`.
- Request modal resource-limit UI and recommendation prefill.
- KPI cards and trend charts with quota/denominator display.
- API, agent protocol, and payload contract docs.

Validation on `server_63_dev`:

```text
backend: python manage.py test -> 111 tests OK
backend targeted: apps.containers.tests.test_workspace_limit_metadata apps.common.tests.test_legacy_workspace_limits -> 2 tests OK
backend targeted PR3 legacy/no-LVM hostConfig path -> 5 tests OK
backend mypy: not applicable; no mypy config/dependency and hc-backend has no mypy module
frontend: npm test -- --run -> 57 tests passed
frontend: npm run check -> 0 errors, 193 warnings
frontend: npm run e2e -> 3 passed
migrations: agents.0008, containers.0010, containers.0011 applied
```

2026-05-16 LVM preflight from `/home/agics/ts/HyperCube`:

```bash
bash docs/runbooks/lvm-thin-workspace-preflight.sh hypercube-agent-dev-63 hc-backend
```

Current result:

```text
PREFLIGHT_EXIT:1
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
backend Agent rows still show lvm_pool_size_gb=None for server_16_dev and server_63_dev
```

Core references:

- `docs/test-reports/2026-05-15-container-resource-limits-core-validation.md`
- `docs/test-reports/2026-05-15-container-resource-limits-completion-audit.md`
- `docs/test-reports/2026-05-15-container-resource-limits-legacy-workspace-quota-fix.md`
- `docs/test-reports/2026-05-16-container-resource-limits-completion-audit-addendum.md`
- `docs/agent-lvm-thin-handoff.md`
- `docs/runbooks/lvm-thin-workspace-host-setup.md`
- `docs/runbooks/lvm-thin-workspace-preflight.sh`
- HyperCube-agent tracking issue: `qkr7287/HyperCube-agent#16`

Remaining blocker:

- Full LVM thin workspace creation is not yet proven end-to-end.
- Current `server_63_dev` host and `hypercube-agent-dev-63` both lack
  `lvs/lvcreate/lvremove`; `lvm2`/thin pool setup is not present.
- `/mnt/datasets`, `/mnt/models`, and `/var/lib/hypercube/workspaces` are not
  present on `server_63_dev`, so the shared-mount/workspace-root part cannot be
  validated yet.
- Current Agent rows report `lvm_pool_size_gb=None`, so backend stays in legacy
  mode and omits LVM `workspace` payloads for those agents.
- HyperCube-agent issue #16 still has no `PERMISSION_OPTION=<1|2|3>` reply.

Next completion gate:

1. Agent/ops replies on HyperCube-agent #16 with `PERMISSION_OPTION=<1|2|3>`.
2. Implement/deploy the selected HyperCube-agent permission path.
3. Confirm `capacity_report` includes `disk.lvm.available=true` and
   `thinPoolSizeGb`, or explicitly choose `PERMISSION_OPTION=3` legacy mode.
4. Submit a new PyTorch Jupyter request and confirm backend sends
   `hostConfig`, `workspace`, and `sharedMounts` when LVM is available.
5. Confirm agent creates/mounts the LVM thin volume.
6. Confirm backend stores `Container.workspace_device`.
7. Confirm container `df /workspace` shows the requested workspace quota.
