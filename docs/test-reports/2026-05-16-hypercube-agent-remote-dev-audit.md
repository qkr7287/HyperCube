# HyperCube-agent Remote Dev Audit - 2026-05-16

## Purpose

This report separates local agent checkout evidence from remote/deployable
HyperCube-agent `dev` evidence for the container resource limits + LVM thin
workspace objective.

## Findings

The local Windows checkout at
`C:\Users\agics\Desktop\workspace\01. git\HyperCube-agent` contains LVM,
capacity, HostConfig, workspace metrics, and self-test scaffolding. That local
checkout is not clean and must not be treated as deployed state.

Local evidence collected from that checkout:

```text
git status --short --branch
## dev...origin/dev [ahead 4]
 M Dockerfile
 M Dockerfile.dev
 M docker-compose.dev.yml
 M docker-compose.yml
 M docs/PROTOCOL.md
 M installer/install-template.sh
 M package.json
 M scripts/dev-off.sh
 M scripts/dev-on.sh
 M scripts/dev-supervisor.sh
 M src/collectors/docker.ts
 M src/collectors/gpu-per-container.ts
 M src/collectors/system.ts
 M src/config.ts
 M src/handlers/control.ts
 M src/handlers/create-container.ts
 M src/handlers/delete-container.ts
 M src/handlers/index.ts
 M src/handlers/system-info.ts
 M src/index.ts
 M src/sync/delta.ts
 M src/types/index.ts
?? docs/gpu-ml-workspace-agent-report.md
?? src/capabilities.ts
?? src/collectors/capacity.ts
?? src/handlers/container-processes.ts
?? src/handlers/image-inspect.ts
?? src/handlers/prepare-model-assets.ts
?? src/network-policy.ts
?? src/self-tests/
?? src/utils/command-runner.ts
?? src/utils/gpu-inventory.ts
?? src/utils/model-cache.ts
?? src/workspace-lvm.ts
?? src/workspace-recovery.ts
```

Local self-test evidence:

```text
npm run self-test:lvm-workspace -> passed
npm run self-test:network-policy -> passed
npm run self-test:gpu-per-container -> passed
```

Remote GitHub evidence for `qkr7287/HyperCube-agent` `dev`:

```text
fetch file: src/workspace-lvm.ts @ dev
result: GitHub API 404 Not Found
```

Therefore the LVM workspace implementation observed locally is not available on
remote `HyperCube-agent` `dev` at the time of this audit.

## Acceptance Impact

The HyperCube core repo can stay in legacy mode safely, but the full objective
cannot be completed until agent-side work is committed, pushed, deployed, and
validated.

Before the full 8-step LVM validation can run, HyperCube-agent must provide a
remote/deployable implementation for:

- `capacity_report` with `disk.lvm.available`, `thinPoolSizeGb`, and graceful
  `available=false` fallback.
- `create_container.params.hostConfig` mapping to Docker HostConfig.
- LVM thin workspace provisioning and cleanup.
- `create_container_result.data.workspace.device` reporting.
- `container_metrics.data.workspace` reporting.
- `sharedMounts` read-only bind handling.
- disabled-LVM option-3 behavior: `LVM_WORKSPACE_ENABLED=false` must force
  `disk.lvm.available=false` without probing or advertising LVM.

## Current Completion Decision

Do not mark the HyperCube resource-limit/LVM objective complete.

The remaining proof path still requires:

1. HyperCube-agent issue #16 receives `PERMISSION_OPTION=<1|2|3>`.
2. Agent code is committed and pushed to a deployable ref.
3. Agent is deployed to `server_63_dev`.
4. `docs/runbooks/lvm-thin-workspace-preflight.sh` exits 0 for LVM mode, or
   option 3 legacy mode is explicitly selected and verified.
5. `docs/runbooks/lvm-thin-workspace-full-validation.md` passes the real
   end-to-end scenario.
