# HyperCube Progress

## Current Work - 2026-05-16

### Container Resource Limits / LVM Thin Workspace

Core repo status: implemented, validated, committed, and pushed to `dev`.
Full LVM thin workspace end-to-end validation is still blocked by server 63
host/agent runtime setup and the missing agent-side permission decision.

Implementation baseline:

```text
7454fdd feat(containers): add resource limits and workspace quotas
```

Latest implementation/audit commits before this progress refresh:

```text
af5f3c3 docs(containers): add lvm full validation runbook
bc26acd docs(agent): refresh lvm handoff validation status
bd8c3ce docs(containers): record final blocker re-audit evidence
e04738c docs(containers): record backend mypy status in progress
1165c24 docs(containers): record backend mypy status
b678469 docs(containers): record live no-lvm payload progress
1c03ff9 docs(containers): record live no-lvm payload dry-run
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

Latest re-audit evidence:

- Required planning specs were rechecked from GitHub `dev` via file API:
  `docs/container-resource-limits-기획.ko.html` and
  `docs/agent-integration-lvm-thin-spec.ko.html`.
- GitHub compare verified HyperCube `dev` was identical to
  `af5f3c3c44f6e83afb0e1652c465d52447540b60` before this progress refresh.
- `docs/runbooks/lvm-thin-workspace-full-validation.md` now records the gated
  8-step end-to-end proof path to run after the agent/ops LVM blocker is fixed.
- Server 63 targeted backend recheck:
  `python manage.py test apps.containers.tests.test_recommend
  apps.containers.tests.test_deployment.AgentCreatePayloadTests
  apps.common.tests.test_legacy_workspace_limits.LegacyWorkspaceLimitConsumerTests
  --verbosity 1` -> 7 tests OK.

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
backend targeted re-audit: apps.containers.tests.test_recommend apps.containers.tests.test_deployment.AgentCreatePayloadTests apps.common.tests.test_legacy_workspace_limits.LegacyWorkspaceLimitConsumerTests -> 7 tests OK
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
- `docs/runbooks/lvm-thin-workspace-full-validation.md`
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
4. Re-run `docs/runbooks/lvm-thin-workspace-preflight.sh` until it exits 0, or
   confirm the explicit legacy-mode path.
5. Run `docs/runbooks/lvm-thin-workspace-full-validation.md` for the real LVM
   8-step validation path.
6. Submit a new PyTorch Jupyter request and confirm backend sends
   `hostConfig`, `workspace`, and `sharedMounts` when LVM is available.
7. Confirm agent creates/mounts the LVM thin volume.
8. Confirm backend stores `Container.workspace_device`.
9. Confirm container `df /workspace` shows the requested workspace quota.
