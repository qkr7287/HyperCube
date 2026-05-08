import uuid

from django.conf import settings
from django.db import models

from apps.agents.models import Agent


class ContainerTemplate(models.Model):
    """관리자가 등록하는 컨테이너 템플릿.

    - simple: 단일 Docker 이미지 기반 (image_options 중 선택 가능)
    - compose: docker-compose YAML 전체 등록
    - env_schema / port_schema 로 사용자 입력 폼 동적 생성
    """

    class Kind(models.TextChoices):
        SIMPLE = "simple", "Simple (single container)"
        COMPOSE = "compose", "Docker Compose"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    kind = models.CharField(max_length=10, choices=Kind.choices)

    # simple 전용
    image = models.CharField(max_length=255, blank=True, default="")
    # 여러 태그/베이스 이미지 후보: [{"label":"Postgres 15","image":"postgres:15"}, ...]
    image_options = models.JSONField(default=list, blank=True)
    # 환경변수 스키마: [{"key":"POSTGRES_PASSWORD","required":true,"type":"password","default":"","description":""}]
    env_schema = models.JSONField(default=list, blank=True)
    # 포트 스키마: [{"internal":5432,"host_default":15432,"description":"DB port"}]
    port_schema = models.JSONField(default=list, blank=True)
    default_volumes = models.JSONField(default=list, blank=True)

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

    # delete 전용 ---
    target_container = models.ForeignKey(
        Container,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delete_requests",
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
