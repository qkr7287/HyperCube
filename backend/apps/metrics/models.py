import uuid

from django.db import models

from apps.agents.models import Agent


class SystemMetricsHistory(models.Model):
    """Agent로부터 수신한 시스템 메트릭의 시계열 히스토리."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        related_name="system_metrics",
    )
    cpu_usage = models.FloatField(help_text="CPU 사용률 (%)")
    memory_usage = models.FloatField(help_text="메모리 사용률 (%)")
    memory_used = models.BigIntegerField(help_text="사용 메모리 (MB)")
    memory_total = models.BigIntegerField(help_text="전체 메모리 (MB)")
    disk_usage = models.FloatField(help_text="디스크 사용률 (%)")
    network_rx = models.BigIntegerField(help_text="누적 수신 bytes")
    network_tx = models.BigIntegerField(help_text="누적 송신 bytes")
    raw_data = models.JSONField(help_text="Agent로부터 받은 system_metrics 전체 payload")
    recorded_at = models.DateTimeField(db_index=True, help_text="Agent가 수집한 시각")

    class Meta:
        db_table = "system_metrics_history"
        ordering = ["-recorded_at"]
        indexes = [
            models.Index(fields=["agent", "-recorded_at"]),
        ]

    def __str__(self):
        return f"{self.agent.hostname} @ {self.recorded_at}"


class ContainerMetricsHistory(models.Model):
    """컨테이너 단위 메트릭의 시계열 히스토리."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        related_name="container_metrics",
    )
    container_id = models.CharField(max_length=64, db_index=True)
    cpu_usage = models.FloatField(
        null=True, blank=True,
        help_text=(
            "컨테이너 CPU 사용률 (0~100 정규화). 신규 Agent의 cpu.usage_pct 값을 그대로 저장. "
            "Agent가 cores_quota 결정 실패 시 null 저장됨. "
            "구버전 Agent는 cpu.usage / cores 로 fallback 계산해 채움."
        ),
    )
    cpu_usage_raw = models.FloatField(
        null=True, blank=True,
        help_text="Docker stats raw 코어 합산 % (정보 보존용). Agent v2 이상에서 채움.",
    )
    cpu_cores_quota = models.FloatField(
        null=True, blank=True,
        help_text="이 컨테이너에 허용된 논리 코어 수. cgroup 한도 또는 호스트 코어 수.",
    )
    memory_usage = models.BigIntegerField(help_text="메모리 사용량 (bytes)")
    memory_limit = models.BigIntegerField(help_text="메모리 한도 (bytes)")
    memory_percent = models.FloatField(help_text="메모리 사용률 (%)")
    network_rx = models.BigIntegerField(help_text="누적 수신 bytes")
    network_tx = models.BigIntegerField(help_text="누적 송신 bytes")
    disk_read = models.BigIntegerField(help_text="누적 디스크 read bytes")
    disk_write = models.BigIntegerField(help_text="누적 디스크 write bytes")
    raw_data = models.JSONField(help_text="Agent로부터 받은 container_metrics 전체 payload")
    recorded_at = models.DateTimeField(db_index=True, help_text="Agent가 수집한 시각")

    class Meta:
        db_table = "container_metrics_history"
        ordering = ["-recorded_at"]
        indexes = [
            models.Index(fields=["agent", "container_id", "-recorded_at"]),
            models.Index(fields=["container_id", "-recorded_at"]),
        ]

    def __str__(self):
        return f"{self.container_id[:12]} @ {self.recorded_at}"
