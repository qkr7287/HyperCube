import uuid

from django.conf import settings
from django.db import models

from apps.agents.models import Agent, GpuSlice


class ContainerTemplate(models.Model):
    """관리자가 등록하는 컨테이너 템플릿.

    - simple: 단일 Docker 이미지 기반 (image_options 중 선택 가능)
    - compose: docker-compose YAML 전체 등록
    - env_schema / port_schema 로 사용자 입력 폼 동적 생성
    """

    class Kind(models.TextChoices):
        SIMPLE = "simple", "Simple (single container)"
        COMPOSE = "compose", "Docker Compose"

    class Category(models.TextChoices):
        GENERAL = "general", "General"
        ML = "ml", "ML"

    class WorkspaceKind(models.TextChoices):
        JUPYTER = "jupyter", "Jupyter"
        CODE_SERVER = "code-server", "code-server"
        API = "api", "API"

    class NetworkPolicy(models.TextChoices):
        INTERNAL_ONLY = "internal_only", "Internal only"
        NONE = "none", "None"
        CUSTOM = "custom", "Custom"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    category = models.CharField(
        max_length=24,
        choices=Category.choices,
        default=Category.GENERAL,
    )
    requires_gpu = models.BooleanField(default=False)
    workspace_enabled = models.BooleanField(default=False)
    workspace_kind = models.CharField(
        max_length=32,
        choices=WorkspaceKind.choices,
        blank=True,
        default="",
    )
    workspace_port = models.PositiveIntegerField(null=True, blank=True, default=8888)
    default_workdir = models.CharField(max_length=255, blank=True, default="/workspace")
    network_policy = models.CharField(
        max_length=32,
        choices=NetworkPolicy.choices,
        default=NetworkPolicy.INTERNAL_ONLY,
    )
    default_max_runtime_hours = models.PositiveIntegerField(null=True, blank=True)
    cpu_weight = models.FloatField(default=1.0)
    ram_weight = models.FloatField(default=1.0)
    disk_weight = models.FloatField(default=1.0)
    min_cpu_percent = models.PositiveIntegerField(default=100)
    min_memory_mb = models.PositiveIntegerField(default=2048)
    min_workspace_gb = models.PositiveIntegerField(default=10)

    # simple 전용
    image = models.CharField(max_length=255, blank=True, default="")
    # 여러 태그/베이스 이미지 후보: [{"label":"Postgres 15","image":"postgres:15"}, ...]
    image_options = models.JSONField(default=list, blank=True)
    # 환경변수 스키마: [{"key":"POSTGRES_PASSWORD","required":true,"type":"password","default":"","description":""}]
    env_schema = models.JSONField(default=list, blank=True)
    # 포트 스키마: [{"internal":5432,"host_default":15432,"description":"DB port"}]
    port_schema = models.JSONField(default=list, blank=True)
    default_volumes = models.JSONField(default=list, blank=True)
    default_model_version_ids = models.JSONField(default=list, blank=True)
    # Inference recipe id used by the base-image launcher to auto-start a
    # gradio UI for the mounted model. "none" disables auto-launch. Source of
    # truth for the id catalogue lives in
    # apps.containers.launcher_recipes.LauncherRecipe (mirrored into the base
    # image as /opt/hc/launcher_recipes.json).
    launcher_recipe_id = models.CharField(max_length=64, blank=True, default="none")
    # launcher_recipe_id == '__custom__' 일 때 사용자가 직접 입력한 model_class /
    # processor_class / app_template / trust_remote_code 를 저장. 카탈로그 외 모델
    # variant (SmolVLM, Phi-3-Vision 등) 를 즉시 자동 실행하기 위한 inline recipe.
    launcher_overrides = models.JSONField(default=dict, blank=True)

    # compose 전용
    compose_yaml = models.TextField(blank=True, default="")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="authored_templates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "container_templates"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} [{self.get_kind_display()}]"


class Container(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        STOPPED = "stopped", "Stopped"
        PAUSED = "paused", "Paused"
        EXITED = "exited", "Exited"
        CREATED = "created", "Created"
        RESTARTING = "restarting", "Restarting"
        DEAD = "dead", "Dead"

    container_id = models.CharField(max_length=64, primary_key=True)
    name = models.CharField(max_length=255)
    image = models.CharField(max_length=255)
    agent = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        related_name="containers",
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.CREATED,
    )
    last_seen = models.DateTimeField(auto_now=True)

    # 누가 요청해서 만든 컨테이너인가 (익명/외부 발견은 null)
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_containers",
    )
    # 어느 요청으로 생성됐는가 (compose 그룹 식별용)
    created_via_request = models.ForeignKey(
        "ContainerRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_containers",
    )
    allocated_gpu_slice_ids = models.JSONField(default=list, blank=True)
    mounted_model_version_ids = models.JSONField(default=list, blank=True)
    workspace_enabled = models.BooleanField(default=False)
    workspace_kind = models.CharField(max_length=32, blank=True, default="")
    workspace_internal_port = models.PositiveIntegerField(null=True, blank=True)
    workspace_host_port = models.PositiveIntegerField(null=True, blank=True)
    workspace_base_url = models.CharField(max_length=255, blank=True, default="")
    workspace_health = models.JSONField(default=dict, blank=True)
    workspace_max_runtime_hours = models.PositiveIntegerField(null=True, blank=True)
    workspace_runtime_expires_at = models.DateTimeField(null=True, blank=True)
    workspace_token_ref = models.CharField(max_length=64, blank=True, default="")
    workspace_token_expires_at = models.DateTimeField(null=True, blank=True)
    cpu_percent_limit = models.PositiveIntegerField(null=True, blank=True)
    memory_mb_limit = models.PositiveIntegerField(null=True, blank=True)
    workspace_gb_limit = models.PositiveIntegerField(null=True, blank=True)
    # Mount path on the host where the XFS-quota-backed workspace lives.
    # Replaces the LVM thin device path; the field name is kept so existing
    # consumers / admin / serializers and the agent-side payload `path`
    # land in the same column.
    workspace_device = models.CharField(max_length=255, null=True, blank=True)
    # XFS project id used by `xfs_quota` / `setquota` to enforce the limit.
    workspace_project_id = models.PositiveIntegerField(null=True, blank=True)
    limit_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "containers"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.get_status_display()}) @ {self.agent.hostname}"


class ContainerEvent(models.Model):
    """Agent가 Dockerode events stream 으로부터 push하는 컨테이너 라이프사이클 이벤트.

    Frontend 차트의 markLine 표시 + 이벤트 패널의 source. agent-payload-contract
    의 `container_events` 메시지 schema 1:1 매핑.
    """

    class Kind(models.TextChoices):
        START = "start", "Start"
        STOP = "stop", "Stop"
        DIE = "die", "Die"
        RESTART = "restart", "Restart"
        PAUSE = "pause", "Pause"
        UNPAUSE = "unpause", "Unpause"
        KILL = "kill", "Kill"
        OOM = "oom", "OOM"
        HEALTH_STATUS = "health_status", "Health Status"

    id = models.BigAutoField(primary_key=True)
    container = models.ForeignKey(
        Container,
        on_delete=models.CASCADE,
        related_name="events",
    )
    # 같은 agent 가 보낸 이벤트인지 cross-check 용 (container.agent 와 동일해야).
    agent = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        related_name="container_events",
    )
    ts = models.DateTimeField(help_text="Docker event 발생 시각 (UTC)")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    # 추가 필드 (kind 별 — exitCode/signal/healthStatus). 누락은 null.
    exit_code = models.IntegerField(null=True, blank=True)
    signal = models.CharField(max_length=20, blank=True, default="")
    health_status = models.CharField(max_length=20, blank=True, default="")
    # 원본 raw payload (디버깅 / 향후 schema 확장 대비). agent 가 보낸 event dict.
    raw = models.JSONField(default=dict, blank=True)
    # Backend 가 받은 시각 (지연 분석용). agent ts 와 다를 수 있음.
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "container_events"
        ordering = ["-ts"]
        indexes = [
            models.Index(fields=["container", "-ts"]),
            models.Index(fields=["agent", "-ts"]),
        ]

    def __str__(self):
        return f"{self.kind} {self.container.container_id[:12]} @ {self.ts.isoformat()}"


class ContainerRequest(models.Model):
    """사용자가 제출하는 컨테이너 생성/삭제 요청.

    action=create 시: template + target_agent 필수, custom_name/env/ports 지정
    action=delete 시: target_container 필수 (compose 그룹이면 Backend가 전체 삭제 처리)
    """

    class Action(models.TextChoices):
        CREATE = "create", "Create"
        DELETE = "delete", "Delete"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        DEPLOYING = "deploying", "Deploying"
        DEPLOYED = "deployed", "Deployed"
        FAILED = "failed", "Failed"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="submitted_requests",
    )
    action = models.CharField(max_length=10, choices=Action.choices)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
    )

    # create 전용 ---
    template = models.ForeignKey(
        ContainerTemplate,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="requests",
    )
    target_agent = models.ForeignKey(
        Agent,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="deployment_requests",
    )
    custom_name = models.CharField(max_length=255, blank=True, default="")
    # image_options 중 선택된 image (없으면 template.image)
    selected_image = models.CharField(max_length=255, blank=True, default="")
    custom_env = models.JSONField(default=dict, blank=True)
    custom_ports = models.JSONField(default=list, blank=True)
    gpu_slice_ids_snapshot = models.JSONField(default=list, blank=True)
    gpu_share_ok = models.BooleanField(default=False)
    model_version_ids = models.JSONField(default=list, blank=True)
    workspace_enabled_snapshot = models.BooleanField(default=False)
    workspace_kind_snapshot = models.CharField(max_length=32, blank=True, default="")
    requested_max_runtime_hours = models.PositiveIntegerField(null=True, blank=True)
    cpu_percent = models.PositiveIntegerField(null=True, blank=True)
    memory_mb = models.PositiveIntegerField(null=True, blank=True)
    workspace_gb = models.PositiveIntegerField(null=True, blank=True)
    prepare_job_ids = models.JSONField(default=list, blank=True)
    deployment_phase = models.CharField(max_length=32, blank=True, default="")
    workspace_token_ref = models.CharField(max_length=64, blank=True, default="")
    workspace_token_expires_at = models.DateTimeField(null=True, blank=True)

    # delete 전용 ---
    target_container = models.ForeignKey(
        Container,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delete_requests",
    )
    # delete 요청 시 컨테이너 이름 스냅샷.
    # target_container 가 on_delete=SET_NULL 이라 컨테이너 삭제 후 라벨이 사라지는
    # 문제를 막기 위해 요청 시점 이름을 영구 보존한다.
    target_container_snapshot_name = models.CharField(
        max_length=255, blank=True, default=""
    )

    # 승인/반려 공통 ---
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True, default="")

    # 진행 상황 (Agent command_progress 이벤트로 갱신) ---
    progress_message = models.TextField(blank=True, default="")
    progress_percent = models.PositiveSmallIntegerField(null=True, blank=True)
    deployment_log = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "container_requests"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["requester", "status"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.action} [{self.status}] by {self.requester.username} @ {self.created_at:%Y-%m-%d %H:%M}"


class ContainerRequestGpuSlice(models.Model):
    request = models.ForeignKey(
        ContainerRequest,
        on_delete=models.CASCADE,
        related_name="gpu_slice_selections",
    )
    slice = models.ForeignKey(
        GpuSlice,
        on_delete=models.PROTECT,
        related_name="request_selections",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("request", "slice")]
        indexes = [models.Index(fields=["request", "slice"])]

    def __str__(self):
        return f"{self.request_id} -> {self.slice_id}"


class GpuAllocation(models.Model):
    class Status(models.TextChoices):
        RESERVED = "reserved", "Reserved"
        ACTIVE = "active", "Active"
        RELEASED = "released", "Released"
        FAILED = "failed", "Failed"

    class ShareMode(models.TextChoices):
        EXCLUSIVE = "exclusive", "Exclusive"
        SHARED = "shared", "Shared"

    slice = models.ForeignKey(
        GpuSlice,
        on_delete=models.PROTECT,
        related_name="allocations",
    )
    container_request = models.ForeignKey(
        ContainerRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gpu_allocations",
    )
    container = models.ForeignKey(
        Container,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gpu_allocations",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.RESERVED,
    )
    share_mode = models.CharField(
        max_length=16,
        choices=ShareMode.choices,
        default=ShareMode.EXCLUSIVE,
    )
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

    def __str__(self):
        return f"{self.slice_id} {self.status} for {self.container_request_id}"


class ConsoleSession(models.Model):
    """B4 — Console exec 감사 로그 (세션 레벨만, 키스트로크 미기록).

    Portainer 모델 채택: console 권한 = full shell 권한. 명령 차단 X.
    audit 은 누가 / 언제 / 어떤 컨테이너로 / 얼마나 사용했는지만 추적.
    """

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="console_sessions",
    )
    container = models.ForeignKey(
        Container,
        on_delete=models.CASCADE,
        related_name="console_sessions",
    )
    # exec_open 의 requestId == streamId == execId. UUID 문자열.
    exec_id = models.CharField(max_length=64, unique=True)
    # exec_open 시 보낸 cmd / user / tty (사용 흔적 보존)
    cmd = models.JSONField(default=list, blank=True)
    user_param = models.CharField(max_length=64, blank=True, default="")
    tty = models.BooleanField(default=True)

    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    # exec_end 의 exitCode/reason (정상 종료 / disconnect / container_stopped)
    exit_code = models.IntegerField(null=True, blank=True)
    close_reason = models.CharField(max_length=32, blank=True, default="")

    class Meta:
        db_table = "console_sessions"
        ordering = ["-opened_at"]
        indexes = [
            models.Index(fields=["user", "-opened_at"], name="console_ses_user_idx"),
            models.Index(fields=["container", "-opened_at"], name="console_ses_cont_idx"),
        ]

    def __str__(self):
        return f"console {self.exec_id[:8]} {self.user.username} -> {self.container.name}"
