# GPU ML Workspace Next Session Handoff

Date: 2026-05-12
Target: complete v1 by Friday, 2026-05-15
Repo: HyperCube core, `C:\Users\agics\Desktop\workspace\01. git\HyperCube`

## Start Here

The user wants a complete v1 GPU hosting and ML Workspace flow, not a reduced notebook-only demo.

Complete v1 means:

1. GPU agent reports inventory.
2. User creates an ML Workspace request from the dashboard.
3. User selects a GPU slice and ML template.
4. User uploads/registers model assets in HyperCube.
5. Agent prepares/caches selected model assets with visible progress.
6. Backend reserves GPU, dispatches container creation, and releases/fails cleanly.
7. Workspace opens Jupyter through the platform.
8. Dashboard shows workspace, GPU, model, progress, and failure state.
9. Airgap mode is enforced: no external model/image/package downloads at runtime.

Do not restart the discussion from generic GPU hosting. Continue from the design in:

- `docs/gpu-ml-workspace-design.md`
- `docs/runbooks/gpu-workspace-reconcile.md`
- `docs/runbooks/ml-image-airgap-build.md`
- `docs/operations.md`

## Current Operating Assumptions

- Development runs through server 63.
- Local Windows checkout is the authoritative editor/git workspace.
- Mutagen sync mirrors this repo to `hc-dev-63:/home/agics/ts/HyperCube`.
- Docker compose and containers run on `192.168.0.63`.
- Frontend is expected at `http://192.168.0.63:33000/`.
- Backend is expected at `http://192.168.0.63:38000/`.
- Do not start a competing local dev server on the Windows machine.
- Always check `git status --short` before editing. The worktree may contain unrelated user changes.

Useful operation reference:

- `docs/operations.md`, section "Dev on server 63 (remote Docker, local editing)"

## Scope Boundaries

HyperCube core repo owns:

- Django models, migrations, serializers, viewsets, Celery tasks.
- Channels response handling and workspace proxy.
- Frontend request modal, model catalog, workspace page, detail chips.
- Core docs and protocol docs.

HyperCube-agent repo owns:

- `system_info.gpu_inventory`
- Docker NVIDIA `DeviceRequests`
- `image_inspect`
- Jupyter env/base URL/port handling.
- `prepare_model_assets`
- Agent-local model cache.
- Container network policy enforcement.

Agent repo changes must be handled in a separate HyperCube-agent session or GitHub issue. Do not mix agent code edits into this repo.

## Non-Negotiable Design Decisions

- Airgap first. No Hugging Face, GitHub, public S3, Docker Hub, GHCR, NGC, pip, apt, npm, or git clone at runtime.
- First model storage backend is HyperCube server local disk through `HC_MODEL_STORAGE_DIR`.
- NAS and MinIO are later scale-out options, not required for first implementation.
- Model transfer must not be folded into `create_container`.
- Use `prepare_model_assets` with progress and a prepare-job fan-out state machine.
- GPU allocation uses `reserved -> active -> released/failed`.
- Add reservation timeout cleanup in the same PR that introduces reservations.
- Do not persist plaintext Jupyter tokens in relational DB.
- Store token reference and expiry in DB; keep plaintext token in Redis or equivalent volatile secret storage.
- Full GPU exclusive is the first production path.
- MIG/shared support can be scaffolded, but shared mode stays disabled until memory accounting/enforcement exists.

## Friday Complete v1 Work Order

### Track 0: Guardrails

Before code changes:

1. Run `git status --short`.
2. Read this file and `docs/gpu-ml-workspace-design.md` sections:
   - Executive Decision
   - Data Model
   - Agent Protocol
   - Backend Approval and Deployment Sequence
   - Workspace Proxy and Jupyter
   - Implementation Plan
   - Agent Repo Handoff Prompt
3. Leave unrelated existing changes untouched.
4. Keep migrations small and review field/null/default/index choices when implementing.

### Track 1: GPU Inventory

Core repo:

- Add GPU device/slice models.
- Add inventory upsert service.
- Add `/api/agents/{id}/gpus/`.
- Add Celery refresh task and beat schedule.
- Add protocol docs.
- Add tests for upsert/offline behavior.

Agent repo:

- Implement `system_info` subCommand `gpu_inventory`.
- Return no-GPU or no-`nvidia-smi` gracefully.

### Track 2: Full GPU Allocation

Core repo:

- Add `GpuAllocation`.
- Add request-time GPU slice relation table.
- Extend request/container serializers.
- Reserve slices during approval.
- Dispatch `create_container.gpus`.
- Mark allocation active only after successful create response.
- Release/fail on delete/create failure.
- Add reservation janitor.

Agent repo:

- Add Docker NVIDIA device request handling.
- Fail clearly when requested device is not present.

### Track 3: Workspace and Jupyter

Core repo:

- Add workspace fields.
- Add one-time open ticket API.
- Add HTTP/WS proxy or decide tunnel before implementation.
- Add nginx workspace route.
- Add `/user/workspaces`.
- Add "Open Jupyter" action.

Agent repo:

- Inject Jupyter token/base URL/port env.
- Expose workspace port and return host port.
- Enforce or explicitly report `network_policy=internal_only` as `not_enforced`.

Critical gate:

- If backend cannot reach `agent.ip_address:workspace_host_port`, direct proxy cannot be used. Use an agent-side tunnel/reverse-proxy design instead.

### Track 4a: Model Catalog and Upload

Core repo:

- Add `apps.models_catalog`.
- Add `ModelAsset` and `ModelVersion`.
- Add `HC_MODEL_STORAGE_DIR`.
- Add upload/admin import with checksum and temp-file cleanup.
- Add `/user/models`.
- No agent cache or container mount yet in this subtrack.

### Track 4b: Agent Cache and Prepare

Core repo:

- Add `ModelVersionCache`.
- Add `ModelPrepareJob`.
- Dispatch `prepare_model_assets` before `create_container`.
- Use `ModelPrepareJob.id` as command request id.
- Fan out prepare progress to all waiting `ContainerRequest` rows.
- Use short atomic state transitions only; never hold DB row locks during transfer/checksum.

Agent repo:

- Pull from HyperCube backend internal content endpoint using approved Agent token in a header.
- Verify checksum.
- Write temp path, then atomic move to cache path.
- Mount cached model path read-only during `create_container`.

### Track 4c: Model Picker UX

Core repo:

- Add model picker to `NewRequestModal`.
- Submit selected model versions with the workspace request.
- Show selected/mounted model chips on workspace/container detail.

### Track 5: Policy, Quotas, Shared GPU Guardrail

Core repo:

- Add backend policy settings for shared GPU mode, active workspace quota,
  active GPU slice quota, and max workspace runtime.
- Reject shared GPU requests unless `HC_GPU_SHARED_MODE_ENABLED=true`.
- Enforce runtime policy both on request creation and workspace runtime
  extension.
- Enforce per-user active workspace/GPU quotas at approval time, before GPU
  reservation.
- Keep shared GPU opt-in explicit in the request modal and show that shared mode
  remains experimental until memory accounting/enforcement is verified.

Agent repo:

- Keep shared GPU disabled by default. Do not treat `allowShared=true` as
  production-ready until memory accounting and enforcement behavior are tested.

## First New Session Prompt

Paste this into a new Codex/Claude session:

```text
We are in HyperCube core at C:\Users\agics\Desktop\workspace\01. git\HyperCube.

Read docs/gpu-ml-workspace-next-session.md first, then docs/gpu-ml-workspace-design.md only for the relevant section you are implementing.

Goal: implement complete v1 GPU ML Workspace by Friday 2026-05-15 in airgapped mode.

Do not restart planning from scratch. Continue from the existing design.

Current priority: start Track 1 GPU Inventory in HyperCube core unless the user says otherwise.

Rules:
- Run git status before editing.
- Leave unrelated changes untouched.
- Do not start a local dev server on Windows; dev runs on server 63 through Mutagen.
- Keep HyperCube-agent implementation as a separate issue/session. In this repo, only update protocol docs/handoff prompts for agent work.
- No external downloads, public model imports, public image pulls, pip/apt/npm installs, or git clone runtime paths.
- Full GPU exclusive is the first production path. MIG/shared can be scaffolded later.
- Model preparation must be a separate prepare_model_assets command, not hidden inside create_container.

When done, report changed files, tests run, and any blockers that require server 63 or HyperCube-agent access.
```

## Current Worktree Note

At the time this handoff was written, `git status --short` showed unrelated frontend modifications and one untracked airgap test artifact. Re-check before acting:

- `frontend/src/lib/components/ContainerKpiBar.svelte`
- `frontend/src/lib/components/ProcessTopPanel.svelte`
- `frontend/src/routes/user/containers/[containerId]/+page.svelte`
- `hc-airgap-test...`

Treat them as user/existing changes unless the user explicitly says they belong to this task.

## Definition of Done for Complete v1

- Existing non-GPU container requests still work.
- GPU inventory is visible per agent.
- Full GPU exclusive request can be approved without race allocation.
- Stale reservation is cleaned automatically.
- Jupyter workspace opens for owner and rejects non-owner.
- Workspace token plaintext is not serialized or stored in DB.
- Model asset can be uploaded/imported without external network.
- Agent prepare command reports progress and verifies checksum.
- Workspace container starts with selected GPU and read-only model mount.
- Dashboard shows workspace status, GPU, model, and progress/failure state.
- Server 63 runbook or validation notes list any manual GPU/image steps.
- Track 5 policy tests pass with shared mode disabled by default and explicitly
  enabled only for shared-mode test cases.
