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

Latest checked core commits:

```text
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
- Request modal resource-limit UI and recommendation prefill.
- KPI cards and trend charts with quota/denominator display.
- API, agent protocol, and payload contract docs.

Validation on `server_63_dev`:

```text
backend: python manage.py test -> 111 tests OK
backend targeted: apps.containers.tests.test_workspace_limit_metadata apps.common.tests.test_legacy_workspace_limits -> 2 tests OK
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
backend Agent rows still show lvm_pool_size_gb=None for server_16_dev and server_63_dev
```

Core references:

- `docs/test-reports/2026-05-15-container-resource-limits-core-validation.md`
- `docs/test-reports/2026-05-15-container-resource-limits-completion-audit.md`
- `docs/test-reports/2026-05-15-container-resource-limits-legacy-workspace-quota-fix.md`
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
