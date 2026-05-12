# GPU Hosting and ML Workspace Design

Date: 2026-05-12
Scope: HyperCube core repo. HyperCube-agent changes are called out separately.

## Executive Decision

Claude Code's plan is directionally good: it correctly identifies GPU inventory, GPU allocation, model assets, ML templates, and a Jupyter reverse proxy as the missing pieces. The plan also fits HyperCube's existing approval flow because `ContainerRequestViewSet.approve` already dispatches `create_container` to an agent and `MonitoringConsumer._update_request_from_response` already turns agent responses into `Container` rows.

However, I would not implement it exactly as written. The main corrections are:

1. Treat **ML Workspace** as the product object, not just "a container with a GPU". A workspace is `{container + GPU allocation + mounted model assets + Jupyter access + user dashboard}`.
2. Do not rely on backend-written Docker named volumes as the model distribution mechanism. Docker named volumes are local to a Docker daemon. A backend container writing `/var/hc-models` does not automatically make that volume available on a remote agent host.
3. Add a real **agent-local asset cache** model and a model prepare/sync step before mount.
4. Use `reserved -> active -> released/failed` allocation lifecycle. Do not mark GPU allocation `active` before the agent successfully creates the container.
5. Use a short-lived signed workspace open ticket instead of putting the user's JWT access token in a `/workspace/...` URL.
6. Configure Jupyter with a `base_url=/workspace/<container_id>/` or equivalent. Otherwise Jupyter's redirects, static files, and websocket paths are likely to break behind a path proxy.
7. Run the feature in **airgapped mode by default**. No runtime component may pull from Hugging Face, GitHub, GHCR, Docker Hub, pip, apt, npm, S3, or any other external network. Models and datasets come only from user/admin uploads, and runtime images come only from offline image import or an internal registry.
8. Do **not** fold model preparation into `create_container`. From PR 4 onward, model cache preparation is a separate `prepare_model_assets` command with `command_progress` updates.
9. First implementation stores uploaded model assets on the HyperCube server local disk. Use a configured path such as `HC_MODEL_STORAGE_DIR`, not arbitrary scattered directories.
10. Add a reservation timeout janitor with PR 2. A crashed or disconnected agent must not leave GPU slices locked forever.
11. Do not persist the plaintext Jupyter workspace token in relational tables. Store only a token reference/hash in DB and keep the plaintext token in Redis or another in-memory secret store with a controlled TTL.
12. Reuse the existing approved Agent token for agent-to-backend asset API authentication in the first implementation; scope and harden it in the new model catalog endpoints instead of adding a second service account system immediately.

Recommended implementation order:

1. GPU inventory and admin/API visibility.
2. Full-GPU exclusive allocation and agent `create_container.gpus`.
3. Workspace templates and Jupyter open flow.
4. Model catalog, upload, separate asset prepare command, agent cache, and read-only model mounts.
5. MIG/shared GPU, quotas, scheduling, and stronger multi-agent asset distribution.

## Airgap Operating Constraint

This design assumes the target deployment has no external internet access and must not attempt external egress.

Allowed network paths:

- Browser to HyperCube web/API on the local network.
- HyperCube backend to approved agents on the local network.
- Agents to HyperCube backend on the local network.
- Optional internal-only Docker registry or shared file server, if the operator deploys one inside the same offline environment.

Forbidden runtime paths:

- Pulling model weights from Hugging Face, GitHub, Kaggle, public S3, or vendor APIs.
- Pulling container images from GHCR, Docker Hub, NGC, Quay, or any public registry.
- Running `pip install`, `apt install`, `npm install`, `git clone`, or model download scripts against the internet from a workspace.
- Agent-side calls to arbitrary user-provided URLs.

Operational rule:

- Container images are brought in as tar files with `docker load`, or pushed by an operator into an internal offline registry.
- Models/datasets are uploaded through HyperCube UI/API or imported by an admin from an offline directory.
- The backend stores uploaded assets under the configured HyperCube server model directory and exposes them only through an authenticated internal transfer endpoint. Agents must not fetch model data from public networks.
- Workspaces may serve Jupyter through the backend proxy, but workspace containers should have external egress blocked by host firewall or Docker network policy.

## Benchmark Summary

| Service | What to copy | What not to copy blindly |
|---|---|---|
| RunPod Pods | GPU pod UX, templates, JupyterLab/VS Code/SSH entry points, persistent network volume mounted at `/workspace`. Official docs describe Pods as GPU/CPU compute for AI workloads with template-based deployment and JupyterLab/VS Code access. Network volumes are persistent storage and for Pods typically replace the default volume disk at `/workspace`. Sources: [RunPod Pods](https://docs.runpod.io/pods/overview), [RunPod network volumes](https://docs.runpod.io/storage/network-volumes). | RunPod can control its cloud/network/storage plane. HyperCube currently has remote agents over websocket plus observed IPs, so storage and proxy reachability must be explicit. Do not copy RunPod's public cloud download/API assumptions into airgapped HyperCube. |
| Paperspace Notebooks | "Notebook as workspace" UX: web Jupyter IDE, shared persistent storage, templates as tiles. Templates can define container image, repository, and startup scripts. Sources: [Paperspace Notebooks](https://docs.digitalocean.com/products/paperspace/notebooks/), [Notebook Templates](https://docs.digitalocean.com/products/paperspace/notebooks/concepts/notebook-templates/). | Their hosted notebook product hides scheduling/proxy/storage complexity. HyperCube must model those explicitly. In airgap mode, repository/startup-script download features must be disabled or restricted to internal sources. |
| SageMaker Studio Spaces | Separate the workspace/app concept from raw compute. Studio spaces have storage volume, app type, image, and private/shared ownership. Source: [SageMaker Studio spaces](https://docs.aws.amazon.com/en_us/sagemaker/latest/dg/studio-updated-spaces.html). | AWS IAM/EBS/EFS abstractions are too heavy for HyperCube MVP. Copy the product shape, not the cloud dependency. |
| Vertex AI Workbench | Instance creation surfaces JupyterLab version, machine type/GPU, post-startup script, metadata. Source: [Create Vertex AI Workbench instance](https://cloud.google.com/vertex-ai/docs/workbench/instances/create). | Vertex is VM-first. HyperCube is container-on-agent-first. |
| Azure ML compute instance | Managed ML workstation with Jupyter/JupyterLab/VS Code, preconfigured ML packages and GPU drivers, idle shutdown. Source: [Azure ML compute instance](https://learn.microsoft.com/en-us/azure/machine-learning/concept-compute-instance?view=azureml-api-2). | Azure's "one owner workstation" model does not match HyperCube's approval-based multi-user container hosting unless we add quotas and ownership rules. |

Technical runtime references:

- Docker supports NVIDIA GPU access through `--gpus`, with a requirement for NVIDIA container runtime/tooling. Source: [docker container run](https://docs.docker.com/reference/cli/docker/container/run).
- NVIDIA Container Toolkit supports GPU enumeration through `--gpus` or `NVIDIA_VISIBLE_DEVICES`; values can include GPU UUIDs. Source: [NVIDIA Container Toolkit Docker config](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/docker-specialized.html).
- Docker Compose GPU reservations require `capabilities` and can use `device_ids`; `count` and `device_ids` are mutually exclusive. Source: [Docker Compose GPU support](https://docs.docker.com/compose/how-tos/gpu-support/).

## Current HyperCube Fit

Repo facts verified before this design:

- `ContainerTemplate`, `Container`, and `ContainerRequest` live in `backend/apps/containers/models.py`.
- `ContainerRequestViewSet.approve` currently changes `pending -> approved`, records reviewer metadata, then calls `_dispatch_to_agent`.
- `_dispatch_to_agent` currently sends `create_container` with image, name, env, ports, and template default volumes.
- `MonitoringConsumer._route_command_response` already treats `__api__` as dispatch-only and `_update_request_from_response` creates/updates `Container` rows after agent success.
- `Agent` currently has host identity, IP, token, status, and `last_seen_at`, but no GPU inventory model.
- `SystemMetricsHistory` and `ContainerMetricsHistory` already include optional GPU usage/memory columns. These are monitoring metrics, not allocation inventory.
- `nginx/nginx.conf` currently proxies `/api/`, `/ws/`, `/django-admin/`, and static SPA paths. There is no workspace proxy route yet.
- `frontend/src/lib/components/NewRequestModal.svelte` currently loads templates and active agents, then submits `action/template/target_agent/custom_env/custom_ports`. There is no GPU/model/workspace selection yet.

Implication: the least disruptive approach is to extend the current request/dispatch/consumer lifecycle instead of introducing a completely new scheduler in the first PR.

## Product Model

Use these product terms consistently:

- **GPU Host**: an approved HyperCube Agent server with NVIDIA runtime installed.
- **GPU Device**: one physical GPU reported by the agent.
- **GPU Slice**: allocatable unit. Phase 1 supports full GPU only. Later supports static NVIDIA MIG instances.
- **Model Asset**: logical model/dataset bundle registered by a user or admin.
- **Model Version**: immutable version of a model asset with checksum, size, source, and internal storage URI.
- **Agent Asset Cache**: per-agent copy of a model version that can be mounted into containers on that agent.
- **ML Template**: container template with Jupyter/vLLM/code-server startup expectations.
- **ML Workspace**: user-facing object that references the runtime container, GPU allocation, mounted model versions, and Jupyter access state.

## User Flow

1. Admin installs HyperCube-agent on a GPU server and verifies `nvidia-smi` and NVIDIA container runtime.
2. Backend periodically asks the agent for `system_info { subCommand: "gpu_inventory" }`.
3. User opens "새 ML 워크스페이스".
4. User selects an ML template such as PyTorch + Jupyter, TensorFlow + Jupyter, vLLM serve, or code-server + CUDA.
5. User selects an active agent. UI then loads that agent's GPU slices.
6. User selects one full GPU or MIG slice.
7. User optionally uploads/selects model assets already stored in HyperCube. External URL import is not offered. If the selected agent does not have the model cached, the UI shows "준비 필요".
8. User submits a normal `ContainerRequest`.
9. Admin approves. Backend reserves GPU slices under `select_for_update` and sets a reservation timeout.
10. If selected models are missing on the target agent, backend dispatches `prepare_model_assets` as its own command and streams progress through existing `command_progress`.
11. After all selected models are ready in the agent cache, backend dispatches `create_container` with GPU device IDs and read-only model mounts.
12. Agent starts Jupyter and returns host port plus runtime metadata.
13. Backend marks allocation active, stores workspace metadata without a plaintext token, and exposes the workspace on `/user/workspaces`.
14. User clicks "Jupyter 열기". Frontend requests a short-lived open ticket and opens `/workspace/<container_id>/lab?ticket=<ticket>`.
15. Backend validates ticket/session, proxies HTTP and websocket traffic to Jupyter, and never exposes the Jupyter token to the user.
16. User monitors CPU/memory/GPU/network/disk/process/log/console from the existing container dashboard and controls start/stop/restart from HyperCube.

## Data Model

### `backend/apps/agents/models.py`

Add physical inventory:

```python
class GpuDevice(models.Model):
    agent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, related_name="gpu_devices")
    index = models.PositiveSmallIntegerField()
    vendor = models.CharField(max_length=32, default="NVIDIA")
    name = models.CharField(max_length=160)
    uuid = models.CharField(max_length=96, unique=True)
    pci_bus_id = models.CharField(max_length=64, blank=True, default="")
    total_memory_mb = models.PositiveIntegerField()
    driver_version = models.CharField(max_length=64, blank=True, default="")
    cuda_version = models.CharField(max_length=64, blank=True, default="")
    mig_capable = models.BooleanField(default=False)
    mig_enabled = models.BooleanField(default=False)
    status = models.CharField(max_length=16, default="available")  # available/offline/error
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("agent", "index")]
```

Add allocatable inventory:

```python
class GpuSlice(models.Model):
    gpu = models.ForeignKey(GpuDevice, on_delete=models.CASCADE, related_name="slices")
    kind = models.CharField(max_length=16)  # full/mig
    device_id = models.CharField(max_length=128, unique=True)  # GPU-... or MIG-...
    label = models.CharField(max_length=128, blank=True, default="")
    mig_profile = models.CharField(max_length=64, blank=True, default="")
    memory_mb = models.PositiveIntegerField()
    allow_shared = models.BooleanField(default=False)
    status = models.CharField(max_length=16, default="available")  # available/offline/error
    last_seen_at = models.DateTimeField(null=True, blank=True)
```

Do not store `in_use` as the hardware status. Availability should be derived from active/reserved allocations. Hardware status and allocation state are different concepts.

### `backend/apps/containers/models.py`

Extend templates conservatively:

```python
class ContainerTemplate(models.Model):
    category = models.CharField(max_length=24, default="general")  # general/ml
    requires_gpu = models.BooleanField(default=False)
    workspace_enabled = models.BooleanField(default=False)
    workspace_kind = models.CharField(max_length=32, blank=True, default="")  # jupyter/code-server/vllm
    workspace_port = models.PositiveIntegerField(null=True, blank=True, default=8888)
    default_workdir = models.CharField(max_length=255, blank=True, default="/workspace")
    network_policy = models.CharField(max_length=32, default="internal_only")  # internal_only/none/custom
```

Extend requests:

```python
class ContainerRequest(models.Model):
    gpu_slice_ids = models.JSONField(default=list, blank=True)
    gpu_share_ok = models.BooleanField(default=False)
    model_version_ids = models.JSONField(default=list, blank=True)
    is_workspace = models.BooleanField(default=False)
    workspace_token_ref = models.CharField(max_length=64, blank=True, default="")
    workspace_token_hash = models.CharField(max_length=128, blank=True, default="")
    workspace_token_expires_at = models.DateTimeField(null=True, blank=True)
```

Extend containers:

```python
class Container(models.Model):
    allocated_gpu_slice_ids = models.JSONField(default=list, blank=True)
    mounted_model_version_ids = models.JSONField(default=list, blank=True)
    workspace_enabled = models.BooleanField(default=False)
    workspace_kind = models.CharField(max_length=32, blank=True, default="")
    workspace_internal_port = models.PositiveIntegerField(null=True, blank=True)
    workspace_host_port = models.PositiveIntegerField(null=True, blank=True)
    workspace_base_url = models.CharField(max_length=255, blank=True, default="")
    workspace_token_ref = models.CharField(max_length=64, blank=True, default="")
    workspace_token_hash = models.CharField(max_length=128, blank=True, default="")
    workspace_token_expires_at = models.DateTimeField(null=True, blank=True)
```

Add allocation lifecycle:

```python
class GpuAllocation(models.Model):
    slice = models.ForeignKey("agents.GpuSlice", on_delete=models.PROTECT, related_name="allocations")
    container_request = models.ForeignKey(ContainerRequest, on_delete=models.SET_NULL, null=True, blank=True)
    container = models.ForeignKey(Container, on_delete=models.SET_NULL, null=True, blank=True, related_name="gpu_allocations")
    status = models.CharField(max_length=16, default="reserved")  # reserved/active/released/failed
    share_mode = models.CharField(max_length=16, default="exclusive")  # exclusive/shared
    requested_at = models.DateTimeField(auto_now_add=True)
    reserved_until = models.DateTimeField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True, default="")

    class Meta:
        indexes = [
            models.Index(fields=["slice", "status"]),
            models.Index(fields=["container_request", "status"]),
            models.Index(fields=["container", "status"]),
        ]
```

The request JSON fields are snapshots for serializer/API convenience. `GpuAllocation` is the source of truth.

Workspace token handling:

- Generate the plaintext Jupyter token only at dispatch time.
- Store plaintext in Redis as `workspace:token:<workspace_token_ref>` with an operator-configured TTL. Refresh the TTL while the workspace is active or on successful open-ticket use.
- Store only `workspace_token_ref`, `workspace_token_hash`, and expiry metadata in Postgres.
- If Redis loses the plaintext token, the running container may continue, but the proxy must refuse new Jupyter opens until the workspace is restarted or the token is rotated through a controlled backend action.
- Redact token refs/hashes from `__str__`, admin list display, serializers, logs, and deployment log rendering.

### New `backend/apps/models_catalog/`

```python
class ModelAsset(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=160)
    slug = models.SlugField(unique=True)
    framework = models.CharField(max_length=64, blank=True, default="")
    task = models.CharField(max_length=64, blank=True, default="")
    license = models.CharField(max_length=128, blank=True, default="")
    visibility = models.CharField(max_length=16, default="private")  # private/team/public
    description = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
```

```python
class ModelVersion(models.Model):
    asset = models.ForeignKey(ModelAsset, on_delete=models.CASCADE, related_name="versions")
    version = models.CharField(max_length=64)
    source_type = models.CharField(max_length=32, default="upload")  # upload/admin_import only
    storage_backend = models.CharField(max_length=32, default="nas")  # local/nas/minio/admin_import
    storage_uri = models.CharField(max_length=512)
    size_bytes = models.BigIntegerField(default=0)
    checksum = models.CharField(max_length=128, blank=True, default="")
    status = models.CharField(max_length=24, default="ready")  # uploading/ready/failed/deleted
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("asset", "version")]
```

```python
class ModelVersionCache(models.Model):
    version = models.ForeignKey(ModelVersion, on_delete=models.CASCADE, related_name="agent_caches")
    agent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, related_name="model_caches")
    status = models.CharField(max_length=24, default="missing")  # missing/preparing/ready/failed/stale
    cache_path = models.CharField(max_length=512, blank=True, default="")
    size_bytes = models.BigIntegerField(default=0)
    checksum = models.CharField(max_length=128, blank=True, default="")
    last_verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("version", "agent")]
```

Storage options:

| Option | Use case | Decision |
|---|---|---|
| A. HyperCube server local storage | First implementation. User uploads or admin imports land under a backend-managed directory such as `/var/lib/hypercube/model-assets`. Agent downloads from an authenticated backend endpoint over the internal network during `prepare_model_assets`. | Default MVP. Simple, airgap-safe, and enough to build the workflow end to end. |
| B. Shared NAS path | Later scale-out option for multi-agent sites or repeated 100GB+ model distribution. Backend and GPU agents see the same offline NFS/CIFS/local shared mount. | Optional later optimization, not required for the first build. |
| C. Internal MinIO/S3-compatible storage | Larger sites that want object storage semantics inside the closed network. | Later option; adds an operational dependency. |
| Admin import | Operator pre-places a tar/zip/model directory on the HyperCube server or an agent host, then registers it through an admin-only import action. | Supported for airgap ingestion. |

For the first implementation, plan around option A. A 100GB+ model transfer can still take a long time, so it must run through separate `prepare_model_assets` progress and must not be hidden inside `create_container`. Add NAS or internal object storage later only if local backend storage becomes the bottleneck.

Use internal URI schemes such as:

- `hc-upload://models/<model_version_id>` for files uploaded through HyperCube.
- `hc-import://models/<model_version_id>` for admin-imported offline files.
- `hc-local://models/<asset_slug>/<version>/` for files stored under `HC_MODEL_STORAGE_DIR`.
- `nas://models/<asset_slug>/<version>/` for a later backend-approved shared storage path.
- `agent-cache://<agent_id>/<model_version_id>` for verified agent-local cache rows.

Do not store external URLs in `storage_uri`.

## Agent Protocol

### `system_info` subCommand: `gpu_inventory`

Request:

```json
{
  "type": "command",
  "requestId": "...",
  "command": "system_info",
  "params": { "subCommand": "gpu_inventory" }
}
```

Success data:

```json
{
  "gpus": [
    {
      "index": 0,
      "vendor": "NVIDIA",
      "name": "NVIDIA H100 80GB HBM3",
      "uuid": "GPU-...",
      "pciBusId": "00000000:81:00.0",
      "totalMemoryMb": 81920,
      "driverVersion": "550.54.15",
      "cudaVersion": "12.4",
      "migCapable": true,
      "migEnabled": true,
      "slices": [
        {
          "kind": "mig",
          "deviceId": "MIG-...",
          "profile": "1g.10gb",
          "memoryMb": 10240
        }
      ]
    },
    {
      "index": 1,
      "vendor": "NVIDIA",
      "name": "NVIDIA GeForce RTX 4090",
      "uuid": "GPU-...",
      "pciBusId": "00000000:82:00.0",
      "totalMemoryMb": 24564,
      "migCapable": false,
      "migEnabled": false,
      "slices": [
        {
          "kind": "full",
          "deviceId": "GPU-...",
          "profile": "",
          "memoryMb": 24564
        }
      ]
    }
  ]
}
```

Failure:

```json
{ "success": false, "error": "nvidia-smi not available" }
```

Backend behavior:

- If inventory fails, mark GPU devices/slices for that agent offline.
- If an active allocation disappears from inventory, keep allocation active but mark hardware offline/error for operator visibility.
- Use `transaction.atomic()` and `select_for_update()` in inventory application so stale rows do not race with approval.

### `prepare_model_assets` command

This command is mandatory from PR 4 onward. Do not fold model preparation into `create_container`.

Reason: first-time preparation of a 100GB+ model can take tens of minutes. If it is hidden inside container creation, the user sees no meaningful progress, the operator cannot distinguish "copying model" from "container failed", and a reserved GPU slice can stay locked until the long operation times out.

Use the same `ContainerRequest.id` as `requestId` so existing `command_progress` handling updates `ContainerRequest.progress_message` and `progress_percent`. Backend must also track the current deployment phase, because a successful `prepare_model_assets` response is not a deployed container. On prepare success, backend updates `ModelVersionCache` rows and then dispatches `create_container`; on prepare failure/timeout, backend fails the request and releases or fails reserved allocations.

```json
{
  "command": "prepare_model_assets",
  "params": {
    "transferMode": "nas_copy",
    "assets": [
      {
        "versionId": "uuid",
        "storageUri": "nas://models/llama/v1/",
        "checksum": "sha256:...",
        "sizeBytes": 214748364800,
        "targetPath": "/var/lib/hypercube/models/asset-slug/v1"
      }
    ]
  }
}
```

Transfer modes:

- `nas_copy`: preferred production airgap mode. Backend resolves `nas://...` to an allowlisted shared path visible to the target agent. Agent copies into its cache path or performs an approved local bind/cache operation. No public network is used.
- `backend_stream`: fallback for small assets. Agent calls a backend endpoint such as `GET /api/model-versions/<id>/content/` over the internal network. This path is not the default for 100GB+ assets.
- `preseeded`: admin has already placed the model on the agent. Backend verifies the cache row and asks the agent to checksum the local path.

Authentication for `backend_stream`:

- Reuse the existing approved `Agent.token` in an HTTP header, for example `Authorization: Bearer agent_...`.
- Do not put the agent token in a query string.
- Add an agent-token DRF authentication class for model content endpoints. It should authenticate `Agent.status="approved"` and attach the agent identity to the request.
- The content endpoint must verify that the requesting agent is the target agent for a pending `prepare_model_assets` operation or is otherwise explicitly allowed to cache that model version.
- The endpoint must never redirect to an external object store.

Progress:

```json
{
  "type": "command_progress",
  "requestId": "<container-request-id>",
  "message": "Preparing model llama/v1: 37%",
  "percent": 37,
  "phase": "prepare_model_assets"
}
```

The agent should write atomically into a temp path, verify checksum, then move into the cache path. Progress must be based on bytes copied or verified, not just coarse stage names.

### `create_container` extensions

Add optional fields. If absent, existing behavior must remain unchanged.

```json
{
  "image": "hypercube/ml-pytorch-jupyter:cuda12.4-airgap",
  "name": "hc-abc12345",
  "env": {},
  "ports": [],
  "volumes": [],
  "gpus": [
    {
      "deviceId": "GPU-...",
      "kind": "full"
    }
  ],
  "modelMounts": [
    {
      "versionId": "uuid",
      "sourcePath": "/var/lib/hypercube/models/llama/v1",
      "mountPath": "/workspace/models/llama@v1",
      "readOnly": true
    }
  ],
  "workspace": {
    "kind": "jupyter",
    "token": "server-generated-secret",
    "port": 8888,
    "baseUrl": "/workspace/abc123def456/"
  }
}
```

Agent implementation notes:

- Map `gpus[].deviceId` into Dockerode `HostConfig.DeviceRequests`.
- For NVIDIA, include capabilities for GPU/compute/utility.
- Add `NVIDIA_VISIBLE_DEVICES=<device ids>` as a compatibility fallback when needed.
- Add read-only bind mounts for `modelMounts`.
- Reject `create_container` if any requested `modelMounts.sourcePath` is not already in a verified `ready` agent cache. `create_container` must not start copying large models.
- Apply the requested `network_policy`. MVP should support at least `internal_only`, where the workspace can be reached through HyperCube but cannot reach the public internet.
- Inject Jupyter env:
  - `JUPYTER_TOKEN`
  - `JUPYTER_PORT`
  - `JUPYTER_BASE_URL`
  - `JUPYTER_WORKDIR`
- The image entrypoint should start Jupyter with the configured base URL and token.
- Return bound host port and workspace health data.

Success data:

```json
{
  "containerId": "abc123def456...",
  "name": "hc-abc12345",
  "image": "hypercube/ml-pytorch-jupyter:cuda12.4-airgap",
  "state": "running",
  "workspace": {
    "kind": "jupyter",
    "hostPort": 39021,
    "internalPort": 8888,
    "baseUrl": "/workspace/abc123def456/"
  }
}
```

## Backend Flow

### Inventory

Files:

- `backend/apps/agents/models.py`
- `backend/apps/agents/services/gpu_inventory.py`
- `backend/apps/agents/viewsets.py`
- `backend/apps/agents/tasks.py`
- `backend/apps/common/consumers.py`
- `backend/config/settings/base.py`

Add:

- `GpuDevice`, `GpuSlice`
- `apply_gpu_inventory(agent_id, payload)`
- `GET /api/agents/{id}/gpus/`
- Celery task `refresh_gpu_inventories`
- `CELERY_BEAT_SCHEDULE["refresh-gpu-inventories"]`
- `MonitoringConsumer._route_command_response` branch for inventory responses if using `__api__`

Important: for request/response correlation, either:

- keep `requestId` in `command_router.record_pending(..., "__api__", ...)`, and branch before `_update_request_from_response`, or
- store REST-style response in Redis and let the task poll.

The first option fits the existing dispatch-only pattern but must avoid trying to interpret inventory responses as `ContainerRequest` responses.

### Approval and Allocation

Files:

- `backend/apps/containers/models.py`
- `backend/apps/containers/serializers.py`
- `backend/apps/containers/viewsets.py`
- `backend/apps/common/consumers.py`

Approval algorithm:

```python
with transaction.atomic():
    req = ContainerRequest.objects.select_for_update().get(id=pk)
    slices = list(GpuSlice.objects.select_for_update().filter(id__in=req.gpu_slice_ids))

    if len(slices) != len(req.gpu_slice_ids):
        return 400

    for s in slices:
        active_or_reserved = GpuAllocation.objects.filter(
            slice=s,
            status__in=["reserved", "active"],
        ).count()
        if active_or_reserved and not (req.gpu_share_ok and s.allow_shared):
            return 400

    token = secrets.token_urlsafe(32) if req.is_workspace else ""
    token_ref = secrets.token_urlsafe(24) if token else ""
    req.workspace_token_ref = token_ref
    req.workspace_token_hash = hash_workspace_token(token) if token else ""
    req.workspace_token_expires_at = now() + WORKSPACE_TOKEN_TTL if token else None
    req.status = "approved"
    req.save(...)

    if token:
        redis.setex(f"workspace:token:{token_ref}", WORKSPACE_TOKEN_TTL_SECONDS, token)

    for s in slices:
        GpuAllocation.objects.create(
            slice=s,
            container_request=req,
            status="reserved",
            share_mode="shared" if req.gpu_share_ok and s.allow_shared else "exclusive",
            reserved_until=now() + GPU_RESERVE_TIMEOUT,
        )
```

Recommended defaults:

- `GPU_RESERVE_TIMEOUT = 10 minutes` for PR 2.
- `WORKSPACE_TOKEN_TTL_SECONDS = 24 hours` for PR 3, refreshed on successful workspace open while the container is active.
- Plaintext workspace token exists only in memory/Redis and in the agent command payload at dispatch time.

Deployment sequence:

1. Reserve GPU allocations.
2. If `model_version_ids` is non-empty and any version is not `ready` in `ModelVersionCache` for the target agent, dispatch `prepare_model_assets`.
3. While preparation is running, keep request status `deploying` and show `command_progress`.
4. On prepare success, verify/update cache rows, then dispatch `create_container`.
5. On prepare failure or timeout, mark the request failed and release/fail reserved allocations.
6. If no model preparation is needed, dispatch `create_container` immediately.

Response handling detail:

- Extend the pending command context or `ContainerRequest` with a deployment phase such as `prepare_model_assets` or `create_container`.
- `_update_request_from_response` must not mark the request `deployed` for a successful `prepare_model_assets` response.
- A successful prepare response should update cache rows and enqueue/send `create_container`.
- Only a successful `create_container` response should create/update the `Container` row and move GPU allocations to `active`.

After agent success:

- Create/update `Container`.
- Copy workspace token reference/hash, workspace port/base URL, allocated slice IDs, model version IDs into `Container`.
- Change `GpuAllocation.status` from `reserved` to `active`, set `container` and `activated_at`.

After agent failure/timeout:

- Change `reserved` allocations to `failed` or `released`.
- Keep failure detail in `ContainerRequest.deployment_log`.

Reservation janitor:

- Add a Celery beat task in PR 2, for example `cleanup_expired_gpu_reservations`, running every minute.
- Find `GpuAllocation(status="reserved", reserved_until__lt=now())`.
- Mark those allocations `failed`, set `failed_at`, and write `failure_reason="reservation timeout"`.
- Mark the linked `ContainerRequest` failed if it has no active container and append a timeout entry to `deployment_log`.
- The task must be idempotent so concurrent agent failure handling and janitor cleanup do not double-release the same allocation.

On delete:

- Release active allocations.
- Delete or mark container per current behavior.

### Workspace Open API

Add:

- `POST /api/workspaces/{container_id}/open/`
- `GET /api/workspaces/`
- optionally `GET /api/workspaces/{container_id}/`

`open` response:

```json
{
  "url": "/workspace/abc123def456/lab?ticket=short-lived-signed-ticket",
  "expiresInSeconds": 60
}
```

The ticket should encode:

- user ID
- container ID
- expiry
- nonce

Store nonce in Redis for one-time use if possible. Do not put the user's long-lived JWT in the workspace URL.

## Workspace Proxy

Files:

- `backend/apps/containers/workspace_proxy.py`
- `backend/apps/containers/urls.py`
- `backend/config/routing.py`
- `nginx/nginx.conf`
- `nginx/nginx.dev.conf`

MVP assumption:

- Backend can reach the agent host IP and workspace host port.
- Agent firewall allows workspace host ports only from the backend host.
- Jupyter host port must not be broadly public.
- In airgapped production, enforce egress blocking outside the local HyperCube network with firewall rules, Docker network policy, or an equivalent host-level control.

Nginx:

```nginx
location ~ ^/workspace/(?<cid>[^/]+)(?<rest>/.*)?$ {
    proxy_pass http://backend:8000/workspace/$cid$rest$is_args$args;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 86400;
}
```

Backend proxy requirements:

- Validate ticket or workspace session cookie.
- Verify `container.requester == request.user` or admin permission.
- Resolve upstream: `http://{container.agent.ip_address}:{container.workspace_host_port}`.
- Preserve path under `/workspace/<cid>/...` if Jupyter uses matching base URL.
- Append or inject Jupyter token upstream, but never return it to the browser.
- Support both HTTP streaming and websocket upgrade.

If remote agents are behind NAT or not reachable from backend, this MVP proxy will not work. The next design should be an agent-side websocket tunnel or an agent-side reverse proxy registered with the backend.

## Frontend UX

### Request Modal

File: `frontend/src/lib/components/NewRequestModal.svelte`

Change from 2-step generic modal to 3-step workspace-capable modal:

1. Template
   - Tabs: `일반`, `ML`
   - ML template card badges: GPU, Jupyter, vLLM, CUDA version.
2. Target
   - Agent selector.
   - After agent selection, load `/api/agents/{id}/gpus/`.
   - GPU slice tiles with status, memory, profile, allocation count.
   - Disable submit if selected template requires GPU and no GPU slice is selected.
3. Assets
   - Model asset/version chips.
   - Show cache state for selected agent: ready/preparing/missing.
   - Upload/import status only. Do not offer Hugging Face, Git, URL, or public registry import options.
   - Mount path preview: `/workspace/models/<slug>@<version>`.

Submit body additions:

```json
{
  "gpu_slice_ids": ["..."],
  "gpu_share_ok": false,
  "model_version_ids": ["..."],
  "is_workspace": true
}
```

### New Routes

- `frontend/src/routes/user/workspaces/+page.svelte`
  - Workspace cards.
  - Open Jupyter button.
  - GPU/model chips.
  - status/agent/last_seen/current GPU usage.
- `frontend/src/routes/user/models/+page.svelte`
  - Model catalog.
  - filters: framework/task/visibility/owner.
- `frontend/src/routes/user/models/[slug]/+page.svelte`
  - versions, upload, cache status per agent.

### Existing Container Detail

File: `frontend/src/routes/user/containers/[containerId]/+page.svelte`

Add:

- GPU allocation chip row.
- Model mount chip row.
- Workspace open button when `workspace_enabled=true`.
- Jupyter health indicator if available.

Do not remove the existing logs/console/process/metrics layout. The workspace is a higher-level entry point, but the existing container dashboard is still the control plane.

## ML Template Seeds

Seed these admin templates:

1. `PyTorch + Jupyter`
   - image: `hypercube/ml-pytorch-jupyter:cuda12.4-airgap`
   - requires GPU: true
   - workspace: jupyter
   - port: 8888
2. `TensorFlow + Jupyter`
   - image: `hypercube/ml-tensorflow-jupyter:cuda12.4-airgap`
3. `vLLM Serve`
   - image: `hypercube/ml-vllm-openai:<pinned-version>-airgap`
   - requires GPU: true
   - workspace kind: api
   - default exposed port: 8000
4. `code-server + CUDA`
   - image: `hypercube/ml-code-server-cuda:cuda12.4-airgap`
   - workspace kind: code-server
   - port: 8080

Pin image versions. Do not use floating `latest` in production templates.

Airgap image handling:

- Build images outside the restricted site.
- Save them as tar archives with `docker save`.
- Move them into the site through the approved offline media process.
- Load them on each GPU agent with `docker load`, or push them into an internal registry reachable only inside the offline network.
- Template validation should fail if the selected image is not present on the target agent and no internal registry is configured.

## Security Requirements

- Never store or serialize plaintext `workspace_token` through normal container serializers, admin lists, deployment logs, or debug logs.
- Store only `workspace_token_ref` and `workspace_token_hash` in Postgres. Keep the plaintext Jupyter token in Redis or an equivalent volatile secret store.
- Redact token references and hashes from model `__str__`, admin list display, logs, and API responses unless a privileged operational endpoint explicitly needs the reference.
- Use short-lived open tickets for `/workspace/...`.
- Jupyter upstream port must be reachable only by backend or trusted network.
- Model upload must enforce owner, visibility, quota, max file size, path traversal prevention, and checksum.
- Mount model assets read-only by default.
- User-provided templates/images should be admin-approved before GPU access.
- GPU shared mode must be opt-in per slice and per request.
- Jupyter images should run as a non-root user unless the template explicitly requires root.
- Disable external URL imports and external package/model downloads in the product UI.
- Agent code must reject model preparation requests that contain `http://`, `https://`, `s3://`, `git://`, or other non-HyperCube source URIs.
- Agent-to-backend model content requests must use the existing approved Agent token in an HTTP header, with endpoint-level authorization for the target model version and target agent.
- Workspace templates should document that packages and model files must be pre-baked into the offline image or uploaded through HyperCube.

## Implementation PR Plan

### PR 1: GPU Inventory

Backend:

- Add `GpuDevice`, `GpuSlice` migrations in agents app.
- Add inventory service.
- Add `/api/agents/{id}/gpus/`.
- Add Celery task and beat schedule.
- Add agent protocol docs.

Agent:

- Implement `system_info.gpu_inventory`.

Validation:

- Unit test inventory upsert/offline behavior.
- Manual: send fake inventory response and verify API output.

### PR 2: Full GPU Allocation

Backend:

- Add request/container fields and `GpuAllocation`.
- Add serializer fields.
- Add approval reservation logic.
- Add `reserved_until`, `failed_at`, `failure_reason`, and `cleanup_expired_gpu_reservations` Celery beat task.
- Extend `_dispatch_to_agent` with `gpus`.
- Update `_update_request_from_response` for active/release lifecycle.

Agent:

- Extend `create_container` with GPU device requests.

Frontend:

- Add GPU tile selector after agent selection.
- Add GPU chips to detail.

Validation:

- Race test: two approvals for same exclusive slice; only one succeeds.
- Timeout test: stale `reserved` allocation becomes `failed`, request gets timeout detail, and the slice becomes allocatable again.
- Agent payload test: selected slice produces correct `gpus` array.

### PR 3: Workspace and Jupyter

Backend:

- Add workspace fields using token reference/hash, not plaintext token persistence.
- Add workspace open endpoint with signed ticket.
- Add HTTP/WS proxy.
- Add nginx workspace route.
- Add workspace network policy field enforcement plan.
- Store plaintext Jupyter token only in Redis or equivalent volatile secret storage.

Agent:

- Inject Jupyter env/base URL/token.
- Return workspace host port.

Frontend:

- Add `/user/workspaces`.
- Add "Open Jupyter" flow.

Validation:

- 403 for non-owner workspace.
- Expired ticket rejected.
- Jupyter Lab loads through `/workspace/<cid>/lab`.
- Jupyter websocket/kernel connection works.

### PR 4: Model Catalog and Agent Cache

Backend:

- Add `apps.models_catalog`.
- Add model asset/version/cache models.
- Add upload API with checksum and progress support.
- Add shared-storage metadata for `nas://...` and a small-asset authenticated backend streaming fallback. No external signed download URLs.
- Add agent-token HTTP authentication for model content/cache endpoints.
- Add deployment phase handling so `prepare_model_assets` success dispatches `create_container` instead of marking the request deployed.

Agent:

- Add `prepare_model_assets` as a separate command. Do not fold cache preparation into `create_container`.
- Prepare model content from shared NAS, admin-preseeded local cache, or small-asset backend stream only.
- Verify checksum.
- Mount cached paths read-only.

Frontend:

- Add `/user/models`.
- Add drag/drop upload.
- Add model picker in request modal.

Validation:

- Upload large file.
- Verify no external URL import path exists in UI/API.
- Verify 100GB+ model preparation exposes progress through `command_progress` and does not lock the UI in a silent create step.
- Agent cache status transitions missing/preparing/ready/failed.
- Container sees model at expected mount path.

### PR 5: MIG, Shared, Quotas, Cleanup

- Static MIG slice support in inventory and UI.
- Shared opt-in with explicit warnings.
- Per-user GPU quota and workspace duration limits.
- Idle shutdown based on Jupyter activity or no GPU/process activity.
- Garbage collection for failed allocations and stale model cache.

## Review of Claude Code Plan

Keep:

- `system_info` subCommand for GPU inventory.
- Full + static MIG scope.
- Exclusive default and shared opt-in.
- Agent-first GPU tile UX.
- Reuse of existing `ContainerRequest` approval flow.
- Platform ML template set.
- JupyterLab as the first workspace IDE.
- Nginx + Django/Channels proxy because frontend is static.
- Split agent work into a self-contained contract.
- User-uploaded model assets and offline image import as the only supported content path.

Change:

- Replace backend-written named volume assumption with model asset storage plus agent-local cache.
- Remove Hugging Face/Git/S3/public registry runtime assumptions.
- Allocation status should be `reserved` before container creation and `active` only after success.
- Add reservation timeout cleanup so reserved allocations cannot stay locked forever.
- Replace plaintext `workspace_token` fields with Redis-held plaintext plus DB token reference/hash.
- Add signed workspace open tickets. Do not put the normal JWT access token in the Jupyter URL.
- Configure Jupyter base URL. A simple path-stripping proxy is fragile.
- Make `GpuSlice.status` hardware state only; derive usage from `GpuAllocation`.
- Add `ModelVersionCache` so UI can say whether a model is available on the selected agent.
- Make `prepare_model_assets` a separate PR 4 command with progress, not a hidden part of `create_container`.
- Prefer shared NAS paths for large airgapped models; keep Django streaming as a small-asset fallback.
- Put Jupyter proxy reachability assumptions in operations docs before calling it production-safe.

## Agent Repo Handoff Prompt

```text
Add GPU ML Workspace support to HyperCube-agent. HyperCube core changes are handled in a separate PR.

Compatibility requirement:
- If the new optional params are absent, existing system_info, create_container, metrics, control, logs, and exec behavior must remain unchanged.

1. system_info subCommand "gpu_inventory"
- If nvidia-smi is missing, return success=false with error="nvidia-smi not available".
- Return NVIDIA GPU devices and allocatable slices.
- MIG enabled GPU: return only MIG slices, not a full slice.
- MIG disabled GPU: return one full slice.
- deviceId must be the GPU UUID or MIG UUID accepted by the NVIDIA container runtime.

2. prepare_model_assets command
- Required for model catalog support. Do not fold model preparation into create_container.
- Emit command_progress using the same ContainerRequest.id requestId and phase="prepare_model_assets".
- Supported transfer modes:
  - nas_copy: preferred airgap mode. Copy from a backend-approved shared NAS path.
  - backend_stream: small-asset fallback. Pull from HyperCube backend over the internal network only.
  - preseeded: verify an admin-prepared local cache path.
- For backend_stream, call backend with the existing approved Agent token in an HTTP header such as Authorization: Bearer agent_...
- Do not put the token in a query string.
- Reject http://, https://, s3://, git://, public registry pulls, git clone, Hugging Face downloads, package install downloads, or any external network source.
- Write into a temp path, verify checksum, then atomically move into the cache path.
- Progress must be based on bytes copied/verified when possible.

3. create_container optional params
- gpus?: [{ deviceId, kind }]
  Add Dockerode NVIDIA DeviceRequests.
- modelMounts?: [{ sourcePath, mountPath, readOnly }]
  Bind mount verified agent-local cache paths read-only.
- workspace?: { kind, token, port, baseUrl }
  Inject template env for Jupyter/code-server and create port binding.
  Return data.workspace.hostPort/internalPort/baseUrl.

4. preflight
- Fail create_container if GPU deviceId is missing on the host.
- Fail create_container if any modelMounts.sourcePath is missing or not verified.
- create_container must not copy large models. Model preparation happens only in prepare_model_assets.
- Image must already be docker loaded on the agent host or pullable from an internal offline registry.
- Return a clear error string so backend can fail/release the allocation.

5. regression
- Do not change existing metrics payload, container list payload, control, logs, or exec commands.
- Requests without the new optional fields must behave exactly as before.
```

<!-- Legacy broken-encoding prompt block intentionally hidden. Do not use.
### Legacy Prompt Block

The block below is left only as historical context from an earlier draft with broken local encoding. Do not use it for implementation; use the canonical prompt above.

```text
HyperCube-agent에 GPU ML Workspace 지원을 추가해주세요. HyperCube core는 별도 PR입니다.

반드시 기존 동작을 유지하세요. 새 파라미터가 없으면 기존 create_container와 system_info 동작은 동일해야 합니다.

1. system_info subCommand "gpu_inventory"
- nvidia-smi가 없으면 success=false, error="nvidia-smi not available".
- NVIDIA GPU 목록과 MIG slice 목록을 반환합니다.
- MIG enabled GPU는 full slice를 만들지 않습니다.
- MIG disabled GPU는 full slice 1개를 반환합니다.
- deviceId는 Docker/NVIDIA runtime에서 사용할 GPU UUID 또는 MIG UUID입니다.

2. create_container optional params
- gpus?: [{ deviceId, kind }]
  Dockerode HostConfig.DeviceRequests에 NVIDIA device request를 추가합니다.
- modelMounts?: [{ sourcePath, mountPath, readOnly }]
  agent-local cache path를 read-only bind mount합니다.
- workspace?: { kind, token, port, baseUrl }
  Jupyter/code-server 템플릿 이미지가 사용할 env를 주입하고 port binding을 자동 생성합니다.
  create_container 응답 data.workspace.hostPort/internalPort/baseUrl을 반환합니다.

3. preflight
- GPU deviceId가 현재 호스트에 없으면 create_container 실패.
- modelMounts.sourcePath가 없으면 create_container 실패.
- 요청에 외부 URL, public registry pull, git clone, HF download 같은 외부 네트워크 의존이 있으면 실패.
- image는 이미 agent host에 `docker load` 되어 있거나 내부 오프라인 registry에서만 pull 가능해야 합니다.
- 실패 시 backend가 allocation을 release할 수 있도록 명확한 error string을 반환합니다.

4. regression
- 기존 metrics payload, container list payload, control/logs/exec 명령은 변경하지 마세요.
- 신규 optional field가 없는 요청은 기존과 동일해야 합니다.
```

Agent handoff amendments:

- `prepare_model_assets` is required for model catalog support. It must be a separate command from `create_container`.
- The agent must emit `command_progress` for model preparation using the same `ContainerRequest.id` requestId and `phase="prepare_model_assets"`.
- `create_container` must only mount already prepared cache paths. It must fail fast if `modelMounts.sourcePath` is missing or not verified.
- For large airgapped models, prefer `transferMode="nas_copy"` from a backend-approved shared path. `backend_stream` is a small-asset fallback, not the default for 100GB+ models.
- For backend streaming fallback, call the backend with the existing approved Agent token in an HTTP header such as `Authorization: Bearer agent_...`. Do not pass the token in a query string.
- The agent must reject external URL/source schemes for model preparation and must never run internet package/model download steps as part of a workspace request.

-->
## Open Questions

These do not block PR 1-2, but should be decided before model catalog/proxy production rollout:

1. Backend and agents are always on the same routable LAN, or do we need an outbound websocket tunnel for Jupyter?
2. Confirm the production shared-storage shape: NFS, CIFS, local bind mount, or another offline NAS mechanism. The recommended large-model default is `nas://...`, not Django streaming.
3. Decide whether internal MinIO is needed later, or whether NAS plus admin import is enough.
4. Per-user quota policy: max active workspaces, max GPU count, max runtime hours, max model storage.
5. Admin approval policy: can ML workspaces auto-approve if a slice is free, or must every GPU request be reviewed?
6. Do users need inference endpoint publishing in addition to Jupyter, or is that a later feature?
