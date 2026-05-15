# HyperCube Progress

## Current Work - 2026-05-15

### Container Resource Limits / LVM Thin Workspace

Core repo status: implemented, validated, committed, and pushed to `dev`.

Implementation baseline:

```text
7454fdd feat(containers): add resource limits and workspace quotas
```

Later `dev` commits add UI/test/doc follow-up. Check the current remote HEAD
when resuming:

```bash
gh api repos/qkr7287/HyperCube/git/ref/heads/dev --jq '.object.sha'
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
frontend: npm test -- --run -> 57 tests passed
frontend: npm run check -> 0 errors, 193 warnings
frontend: npm run e2e -> 3 passed
migrations: agents.0008, containers.0010, containers.0011 applied
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
  `lvs/lvcreate`; `lvm2`/thin pool setup is not present.
- `/mnt/datasets` and `/mnt/models` are not present on `server_63_dev`, so the
  NFS shared-mount part of the agent payload cannot be validated yet.
- Current Agent rows report `lvm_pool_size_gb=None`, so backend stays in legacy
  mode and omits LVM `workspace` payloads for those agents.

Next completion gate:

1. Implement and deploy HyperCube-agent #16.
2. Confirm `capacity_report` includes `disk.lvm.available=true` and
   `thinPoolSizeGb`.
3. Submit a new PyTorch Jupyter request and confirm backend sends
   `hostConfig`, `workspace`, and `sharedMounts`.
4. Confirm agent creates/mounts the LVM thin volume.
5. Confirm backend stores `Container.workspace_device`.
6. Confirm container `df /workspace` shows the requested workspace quota.
