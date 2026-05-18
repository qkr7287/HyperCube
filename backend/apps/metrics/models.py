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
    memory_available = models.BigIntegerField(
        null=True, blank=True,
        help_text=(
            "Linux MemAvailable (bytes). buffer/cache 를 사용으로 잘못 카운트하지 않도록 "
            "정확한 메모리 사용률 = (total - available) / total. Agent v3+ 에서 채움. "
            "구버전 Agent 는 null."
        ),
    )
    disk_usage = models.FloatField(help_text="디스크 사용률 (%)")
    network_rx = models.BigIntegerField(help_text="누적 수신 bytes")
    network_tx = models.BigIntegerField(help_text="누적 송신 bytes")
    # GPU (선택). 다중 GPU 호스트는 array 평균 / 최대값 / 합산값 으로 단일화해 저장.
    # 호스트 자체에 GPU 가 없거나 Agent 가 보고 안 하면 null. 모든 fleet 차트가
    # gpu_usage 컬럼 단일을 보고 sparkline/aggregation 결정.
    gpu_usage = models.FloatField(
        null=True, blank=True,
        help_text="GPU 사용률 (%) — 다중 GPU 평균. GPU 없으면 null.",
    )
    gpu_count = models.IntegerField(
        null=True, blank=True,
        help_text="장착 GPU 개수.",
    )
    gpu_memory_used = models.BigIntegerField(
        null=True, blank=True,
        help_text="GPU VRAM 사용 합산 (bytes).",
    )
    gpu_memory_total = models.BigIntegerField(
        null=True, blank=True,
        help_text="GPU VRAM 전체 합산 (bytes).",
    )
    gpu_temperature_max = models.FloatField(
        null=True, blank=True,
        help_text="GPU 최고 온도 (°C). 다중 GPU 중 가장 뜨거운 값.",
    )
    gpu_power_w = models.FloatField(
        null=True, blank=True,
        help_text="GPU 전체 전력 합산 (W). nvidia-smi power.draw 합. 다중 GPU 합산.",
    )
    cpu_power_w = models.FloatField(
        null=True, blank=True,
        help_text=(
            "CPU package 평균 전력 (W). Intel/AMD RAPL energy_uj 차분으로 계산. "
            "multi-socket 합산. RAPL 미지원 / 권한 없음 시 null."
        ),
    )
    cpu_temp_c = models.FloatField(
        null=True, blank=True,
        help_text=(
            "CPU package 온도 (°C). thermal_zone (x86_pkg_temp/coretemp/k10temp) 우선. "
            "센서 없으면 null."
        ),
    )
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
    gpu_usage = models.FloatField(
        null=True, blank=True,
        help_text="컨테이너 GPU 사용률 (0~100, %). Agent가 PID 매핑으로 계산. 측정 불가 시 null.",
    )
    gpu_memory_used = models.BigIntegerField(
        null=True, blank=True,
        help_text="컨테이너 GPU 메모리 사용량 (bytes). 측정 불가 시 null.",
    )
    gpu_memory_total = models.BigIntegerField(
        null=True, blank=True,
        help_text="컨테이너에 할당된 GPU 메모리 한도 (bytes). 측정 불가 시 null.",
    )
    # Denormalized stack bucket. Resolved at write time from container labels
    # so historical analytics stay accurate even when labels later change.
    # Resolution mirrors `frontend/src/lib/utils/container-grouping.ts`.
    stack = models.CharField(
        max_length=128,
        default="Unmanaged",
        help_text=(
            "라벨에서 추출한 스택 이름. 우선순위: hypercube.stack → "
            "com.docker.compose.project → working_dir → 'Unmanaged'."
        ),
    )
    raw_data = models.JSONField(help_text="Agent로부터 받은 container_metrics 전체 payload")
    recorded_at = models.DateTimeField(db_index=True, help_text="Agent가 수집한 시각")

    class Meta:
        db_table = "container_metrics_history"
        ordering = ["-recorded_at"]
        indexes = [
            models.Index(fields=["agent", "container_id", "-recorded_at"]),
            models.Index(fields=["container_id", "-recorded_at"]),
            models.Index(fields=["agent", "stack", "-recorded_at"], name="cmhist_agent_stack_ts_idx"),
        ]

    def __str__(self):
        return f"{self.container_id[:12]} @ {self.recorded_at}"


# ----------------------------------------------------------------------
# Rollup tables — long-range (1h/24h/7d) 차트의 사전 집계 결과.
# raw history 위에서 매번 GROUP BY 하면 28일 ×10M+ rows scan 으로 30s+ 걸려서,
# Celery beat 으로 주기 적재 → viewset 이 bucket size 가 3600 / 86400 일 때 여기서 SELECT.
# bucket_seconds 컬럼으로 hourly·daily 를 한 테이블에 같이 저장한다 (테이블 수 절약).
# ----------------------------------------------------------------------


class SystemMetricsRollup(models.Model):
    """SystemMetricsHistory 의 시간/일 단위 사전 집계."""

    id = models.BigAutoField(primary_key=True)
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="system_rollups")
    bucket_seconds = models.IntegerField(help_text="3600 (1h) 또는 86400 (1d).")
    bucket_start = models.DateTimeField(help_text="bucket 시작 시각 (aware datetime).")

    cpu_avg = models.FloatField(null=True, blank=True)
    cpu_max = models.FloatField(null=True, blank=True)
    memory_usage_avg = models.FloatField(null=True, blank=True)
    memory_usage_max = models.FloatField(null=True, blank=True)
    disk_usage_avg = models.FloatField(null=True, blank=True)
    disk_usage_max = models.FloatField(null=True, blank=True)
    network_rx_max = models.BigIntegerField(null=True, blank=True)
    network_tx_max = models.BigIntegerField(null=True, blank=True)
    gpu_usage_avg = models.FloatField(null=True, blank=True)
    gpu_usage_max = models.FloatField(null=True, blank=True)
    gpu_memory_used_avg = models.BigIntegerField(null=True, blank=True)
    gpu_memory_used_max = models.BigIntegerField(null=True, blank=True)
    gpu_memory_total_avg = models.BigIntegerField(null=True, blank=True)
    cpu_power_w_avg = models.FloatField(null=True, blank=True)
    cpu_temp_c_max = models.FloatField(null=True, blank=True)

    sample_count = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "system_metrics_rollup"
        unique_together = [("agent", "bucket_seconds", "bucket_start")]
        indexes = [
            models.Index(fields=["agent", "bucket_seconds", "-bucket_start"]),
        ]


class ContainerMetricsRollup(models.Model):
    """ContainerMetricsHistory 의 시간/일 단위 사전 집계."""

    id = models.BigAutoField(primary_key=True)
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="container_rollups")
    container_id = models.CharField(max_length=64)
    stack = models.CharField(max_length=128, default="Unmanaged")
    bucket_seconds = models.IntegerField()
    bucket_start = models.DateTimeField()

    cpu_usage_pct_avg = models.FloatField(null=True, blank=True)
    cpu_usage_pct_max = models.FloatField(null=True, blank=True)
    cpu_usage_raw_avg = models.FloatField(null=True, blank=True)
    cpu_usage_raw_max = models.FloatField(null=True, blank=True)
    cpu_cores_quota_avg = models.FloatField(null=True, blank=True)
    memory_avg = models.FloatField(null=True, blank=True)
    memory_max = models.FloatField(null=True, blank=True)
    memory_percent_avg = models.FloatField(null=True, blank=True)
    network_rx_max = models.BigIntegerField(null=True, blank=True)
    network_tx_max = models.BigIntegerField(null=True, blank=True)
    disk_read_max = models.BigIntegerField(null=True, blank=True)
    disk_write_max = models.BigIntegerField(null=True, blank=True)
    gpu_usage_avg = models.FloatField(null=True, blank=True)
    gpu_usage_max = models.FloatField(null=True, blank=True)
    gpu_memory_used_avg = models.BigIntegerField(null=True, blank=True)
    gpu_memory_used_max = models.BigIntegerField(null=True, blank=True)
    gpu_memory_total_avg = models.BigIntegerField(null=True, blank=True)

    sample_count = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "container_metrics_rollup"
        unique_together = [("agent", "container_id", "bucket_seconds", "bucket_start")]
        indexes = [
            models.Index(fields=["agent", "bucket_seconds", "-bucket_start"]),
            models.Index(fields=["agent", "stack", "bucket_seconds", "-bucket_start"], name="cmroll_agent_stack_idx"),
        ]


class StackMetricsRollup(models.Model):
    """스택 단위 메트릭의 시간/일 단위 사전 집계 — server-2d "스택 평균 추이" 차트의 직접 소스."""

    id = models.BigAutoField(primary_key=True)
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="stack_rollups")
    stack = models.CharField(max_length=128)
    bucket_seconds = models.IntegerField()
    bucket_start = models.DateTimeField()

    cpu_avg = models.FloatField(null=True, blank=True)
    cpu_max = models.FloatField(null=True, blank=True)
    memory_percent_avg = models.FloatField(null=True, blank=True)
    memory_percent_max = models.FloatField(null=True, blank=True)
    memory_bytes_avg = models.BigIntegerField(null=True, blank=True)
    network_rx_max = models.BigIntegerField(null=True, blank=True)
    network_tx_max = models.BigIntegerField(null=True, blank=True)
    disk_read_max = models.BigIntegerField(null=True, blank=True)
    disk_write_max = models.BigIntegerField(null=True, blank=True)
    gpu_usage_avg = models.FloatField(null=True, blank=True)
    gpu_usage_max = models.FloatField(null=True, blank=True)
    gpu_memory_used_avg = models.BigIntegerField(null=True, blank=True)
    gpu_memory_used_max = models.BigIntegerField(null=True, blank=True)
    gpu_memory_total_avg = models.BigIntegerField(null=True, blank=True)

    container_count = models.IntegerField(default=0)
    sample_count = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "stack_metrics_rollup"
        unique_together = [("agent", "stack", "bucket_seconds", "bucket_start")]
        indexes = [
            models.Index(fields=["agent", "bucket_seconds", "-bucket_start"]),
        ]
