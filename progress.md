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
ea6c7aa docs(agent): add remote pr brief for lvm resource limits
37b6a36 docs(agent): record disabled lvm temp verification
a9abb5a docs(agent): add remote dev audit for lvm gate
cf9780d docs(agent): record disabled lvm acceptance gate
7e0bcc3 docs(agent): refresh lvm handoff head
d8b7221 docs(containers): add final lvm gate audit
cfda1df docs(containers): refresh lvm validation progress
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
  `a9abb5aa0904ded70c1dddf7fd9cb6f0fc980208` before this progress refresh.
- `docs/test-reports/2026-05-16-hypercube-agent-remote-dev-audit.md` records
  that local HyperCube-agent has LVM/capacity scaffolding and passing self-tests,
  but remote `qkr7287/HyperCube-agent` `dev` returned 404 for
  `src/workspace-lvm.ts`; local dirty code must not be treated as deployed.
- `docs/test-reports/2026-05-16-agent-disabled-lvm-guard-temp-verification.md`
  records a temp-copy verification of the disabled-LVM guard plus the latest
  remote agent code gaps: `src/workspace-lvm.ts` and `src/collectors/capacity.ts`
  are still missing on remote `dev`, and remote `src/handlers/create-container.ts`
  does not consume backend `params.hostConfig`, LVM `workspace.sizeGb` /
  `mountTarget`, or `sharedMounts` yet.
- `docs/agent-resource-limits-remote-pr-brief.md` is the current paste-ready
  implementation brief for the HyperCube-agent PR. It lists the remote `dev`
  gaps, minimum file set, required `capacity_report`, `hostConfig`, LVM
  workspace, `sharedMounts`, workspace metrics behavior, disabled-LVM guard,
  and validation commands.
- `docs/agent-lvm-thin-handoff.md` now points agent-side work at the current
  final gate audit, preflight script, host setup runbook, full-validation
  runbook, and the option-3 disabled-LVM acceptance rule.
- Local HyperCube-agent read-only audit found LVM/capacity code scaffolding and
  passing self-tests (`self-test:lvm-workspace`, `self-test:network-policy`,
  `self-test:gpu-per-container`) but identified one agent-side acceptance item:
  `LVM_WORKSPACE_ENABLED=false` must force `disk.lvm.available=false` without
  probing `lvs`.
- HyperCube-agent issue #16 comments `4461477025` and `4461583774` record the
  local agent code audit note, recommended patch shape, temp-copy verification,
  and required self-test.
- `docs/test-reports/2026-05-16-container-resource-limits-final-gate-audit.md`
  records the prompt-to-artifact checklist and confirms the remaining blocked
  gates are external server-63/agent LVM runtime requirements.
- `docs/runbooks/lvm-thin-workspace-full-validation.md` records the gated
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
- `docs/test-reports/2026-05-16-container-resource-limits-final-gate-audit.md`
- `docs/test-reports/2026-05-16-hypercube-agent-remote-dev-audit.md`
- `docs/test-reports/2026-05-16-agent-disabled-lvm-guard-temp-verification.md`
- `docs/agent-resource-limits-remote-pr-brief.md`
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
- Remote `qkr7287/HyperCube-agent` `dev` still does not contain the LVM
  workspace/capacity implementation observed in the dirty Windows checkout.
- Remote HyperCube-agent `src/handlers/create-container.ts` still lacks the
  backend `params.hostConfig`, LVM `workspace.sizeGb` / `mountTarget`, and
  `sharedMounts` handling needed for PR 3's live payload contract.
- HyperCube-agent still needs the disabled-LVM acceptance patch before option 3
  can be considered fully safe on a host where LVM exists but is intentionally
  disabled.

Next completion gate:

1. Agent/ops replies on HyperCube-agent #16 with `PERMISSION_OPTION=<1|2|3>`.
2. Commit/push/deploy the selected HyperCube-agent implementation path.
3. Confirm `capacity_report` includes `disk.lvm.available=true` and
   `thinPoolSizeGb`, or explicitly choose `PERMISSION_OPTION=3` legacy mode.
4. If choosing `PERMISSION_OPTION=3`, confirm `LVM_WORKSPACE_ENABLED=false`
   forces `disk.lvm.available=false` without probing `lvs`.
5. Re-run `docs/runbooks/lvm-thin-workspace-preflight.sh` until it exits 0, or
   confirm the explicit legacy-mode path.
6. Run `docs/runbooks/lvm-thin-workspace-full-validation.md` for the real LVM
   8-step validation path.
7. Submit a new PyTorch Jupyter request and confirm backend sends
   `hostConfig`, `workspace`, and `sharedMounts` when LVM is available.
8. Confirm agent creates/mounts the LVM thin volume.
9. Confirm backend stores `Container.workspace_device`.
10. Confirm container `df /workspace` shows the requested workspace quota.
