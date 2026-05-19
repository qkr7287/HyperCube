import uuid

from django.conf import settings
from django.db import models


class ModelAsset(models.Model):
    class Visibility(models.TextChoices):
        PRIVATE = "private", "Private"
        SHARED = "shared", "Shared"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="model_assets",
    )
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True)
    description = models.TextField(blank=True, default="")
    visibility = models.CharField(
        max_length=16,
        choices=Visibility.choices,
        default=Visibility.PRIVATE,
    )
    framework = models.CharField(max_length=64, blank=True, default="")
    task = models.CharField(max_length=64, blank=True, default="")
    tags = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["owner", "visibility"]),
            models.Index(fields=["framework", "task"]),
        ]

    def __str__(self):
        return self.name


class ModelVersion(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(
        ModelAsset,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version = models.CharField(max_length=80)
    original_filename = models.CharField(max_length=255)
    storage_path = models.CharField(max_length=512)
    size_bytes = models.BigIntegerField(default=0)
    sha256 = models.CharField(max_length=64)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.AVAILABLE,
    )
    metadata = models.JSONField(default=dict, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_model_versions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = [("asset", "version")]
        indexes = [
            models.Index(fields=["asset", "version"]),
            models.Index(fields=["sha256"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.asset.slug}:{self.version}"


class ModelUploadRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="model_upload_requests",
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_model_upload_requests",
    )
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, blank=True, default="")
    description = models.TextField(blank=True, default="")
    framework = models.CharField(max_length=64, blank=True, default="")
    task = models.CharField(max_length=64, blank=True, default="")
    tags = models.JSONField(default=list, blank=True)
    version = models.CharField(max_length=80, default="v1")
    template_name = models.CharField(max_length=100, blank=True, default="")
    template_description = models.TextField(blank=True, default="")
    # Inference recipe id picked in the upload wizard. Copied verbatim into
    # the ContainerTemplate created at approval time.
    launcher_recipe_id = models.CharField(max_length=64, blank=True, default="none")
    launcher_overrides = models.JSONField(default=dict, blank=True)
    base_image = models.CharField(
        max_length=255,
        default="hypercube/ml-pytorch-jupyter:cuda12.4-airgap",
    )
    requires_gpu = models.BooleanField(default=True)
    workspace_kind = models.CharField(max_length=32, blank=True, default="jupyter")
    workspace_port = models.PositiveIntegerField(default=8888)
    default_max_runtime_hours = models.PositiveIntegerField(null=True, blank=True, default=24)
    min_cpu_percent = models.PositiveIntegerField(default=100)
    min_memory_mb = models.PositiveIntegerField(default=2048)
    min_workspace_gb = models.PositiveIntegerField(default=10)
    original_filename = models.CharField(max_length=255, blank=True, default="")
    upload_storage_path = models.CharField(max_length=512, blank=True, default="")
    size_bytes = models.BigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    review_note = models.TextField(blank=True, default="")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_asset = models.ForeignKey(
        ModelAsset,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_upload_requests",
    )
    created_version = models.ForeignKey(
        ModelVersion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_upload_requests",
    )
    created_template = models.ForeignKey(
        "containers.ContainerTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_model_upload_requests",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["requester", "status"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["slug"]),
        ]

    def __str__(self):
        return f"{self.name}:{self.version} ({self.status})"


class ModelVersionCache(models.Model):
    class Status(models.TextChoices):
        MISSING = "missing", "Missing"
        PREPARING = "preparing", "Preparing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(
        "agents.Agent",
        on_delete=models.CASCADE,
        related_name="model_version_caches",
    )
    version = models.ForeignKey(
        ModelVersion,
        on_delete=models.CASCADE,
        related_name="agent_caches",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.MISSING,
    )
    cache_path = models.CharField(max_length=512, blank=True, default="")
    size_bytes = models.BigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True, default="")
    last_verified_at = models.DateTimeField(null=True, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("agent", "version")]
        indexes = [
            models.Index(fields=["agent", "status"], name="mvcache_agent_status_idx"),
            models.Index(fields=["version", "status"], name="mvcache_version_status_idx"),
            models.Index(fields=["lease_expires_at"], name="mvcache_lease_expires_idx"),
        ]

    def __str__(self):
        return f"{self.agent_id} {self.version_id} {self.status}"


class ModelPrepareJob(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        DISPATCHED = "dispatched", "Dispatched"
        PREPARING = "preparing", "Preparing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"
        STALE = "stale", "Stale"

    class TransferMode(models.TextChoices):
        BACKEND_STREAM = "backend_stream", "Backend stream"
        PRESEEDED = "preseeded", "Preseeded"
        NAS_COPY = "nas_copy", "NAS copy"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(
        "agents.Agent",
        on_delete=models.CASCADE,
        related_name="model_prepare_jobs",
    )
    version = models.ForeignKey(
        ModelVersion,
        on_delete=models.CASCADE,
        related_name="prepare_jobs",
    )
    cache = models.ForeignKey(
        ModelVersionCache,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prepare_jobs",
    )
    waiting_requests = models.ManyToManyField(
        "containers.ContainerRequest",
        related_name="model_prepare_jobs",
        blank=True,
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.QUEUED,
    )
    transfer_mode = models.CharField(
        max_length=24,
        choices=TransferMode.choices,
        default=TransferMode.BACKEND_STREAM,
    )
    progress_percent = models.PositiveSmallIntegerField(null=True, blank=True)
    progress_message = models.TextField(blank=True, default="")
    bytes_total = models.BigIntegerField(default=0)
    bytes_done = models.BigIntegerField(default=0)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["agent", "version", "status"], name="mpjob_agent_ver_status_idx"),
            models.Index(fields=["status", "lease_expires_at"], name="mpjob_status_lease_idx"),
            models.Index(fields=["created_at"], name="mpjob_created_at_idx"),
        ]

    def __str__(self):
        return f"{self.version_id} on {self.agent_id}: {self.status}"
