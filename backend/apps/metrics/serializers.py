from rest_framework import serializers

from .models import ContainerMetricsHistory, SystemMetricsHistory


class SystemMetricsHistorySerializer(serializers.ModelSerializer):
    agent_hostname = serializers.CharField(source="agent.hostname", read_only=True)
    # raw_data JSON 에서 꺼내오는 파생 필드들 — 컬럼 추가 없이 차트용으로 노출.
    network_connections = serializers.SerializerMethodField()
    processes_total = serializers.SerializerMethodField()
    processes_running = serializers.SerializerMethodField()
    logins_total = serializers.SerializerMethodField()
    # CPU / Disk 상세 — fleet 카드 피크 셀에서 "% + 실제 값" 표시용.
    # Agent의 system.collect 결과를 raw_data.cpu / raw_data.disk에서 파싱.
    cpu_cores = serializers.SerializerMethodField()
    cpu_threads = serializers.SerializerMethodField()
    cpu_load_avg_1m = serializers.SerializerMethodField()
    disk_used = serializers.SerializerMethodField()
    disk_total = serializers.SerializerMethodField()
    # GPU array carried through so the sidebar sparkline + GPU detail modal
    # can chart per-GPU usage/memory/temperature without paying for the full
    # raw_data payload. List of {index, vendor, model, memoryTotal, memoryUsed,
    # usage, temperature} — `[]` when the host has no discrete GPU.
    gpu = serializers.SerializerMethodField()

    class Meta:
        model = SystemMetricsHistory
        fields = [
            "id",
            "agent",
            "agent_hostname",
            "cpu_usage",
            "cpu_cores",
            "cpu_threads",
            "cpu_load_avg_1m",
            "memory_usage",
            "memory_used",
            "memory_total",
            "disk_usage",
            "disk_used",
            "disk_total",
            "network_rx",
            "network_tx",
            "network_connections",
            "processes_total",
            "processes_running",
            "logins_total",
            "gpu",
            "recorded_at",
        ]

    def _raw(self, obj):
        return obj.raw_data or {}

    def get_network_connections(self, obj):
        return (self._raw(obj).get("network") or {}).get("connections")

    def get_processes_total(self, obj):
        return (self._raw(obj).get("processes") or {}).get("total")

    def get_processes_running(self, obj):
        return (self._raw(obj).get("processes") or {}).get("running")

    def get_logins_total(self, obj):
        return (self._raw(obj).get("logins") or {}).get("total")

    def get_cpu_cores(self, obj):
        return (self._raw(obj).get("cpu") or {}).get("cores")

    def get_cpu_threads(self, obj):
        # Agent가 threads를 안 보내는 경우도 있어 cores로 폴백.
        cpu = self._raw(obj).get("cpu") or {}
        return cpu.get("threads") or cpu.get("cores")

    def get_cpu_load_avg_1m(self, obj):
        # Agent에 load_avg_1m이 추가되면 자동 노출. 없으면 null.
        return (self._raw(obj).get("cpu") or {}).get("load_avg_1m")

    def get_disk_used(self, obj):
        return (self._raw(obj).get("disk") or {}).get("used")

    def get_disk_total(self, obj):
        return (self._raw(obj).get("disk") or {}).get("total")

    def get_gpu(self, obj):
        gpu = self._raw(obj).get("gpu")
        return gpu if isinstance(gpu, list) else []


class SystemMetricsHistoryDetailSerializer(SystemMetricsHistorySerializer):
    class Meta(SystemMetricsHistorySerializer.Meta):
        fields = SystemMetricsHistorySerializer.Meta.fields + ["raw_data"]


class ContainerMetricsHistorySerializer(serializers.ModelSerializer):
    agent_hostname = serializers.CharField(source="agent.hostname", read_only=True)

    class Meta:
        model = ContainerMetricsHistory
        fields = [
            "id",
            "agent",
            "agent_hostname",
            "container_id",
            "cpu_usage",
            "memory_usage",
            "memory_limit",
            "memory_percent",
            "network_rx",
            "network_tx",
            "disk_read",
            "disk_write",
            "gpu_usage",
            "gpu_memory_used",
            "gpu_memory_total",
            "recorded_at",
        ]


class ContainerMetricsHistoryDetailSerializer(ContainerMetricsHistorySerializer):
    class Meta(ContainerMetricsHistorySerializer.Meta):
        fields = ContainerMetricsHistorySerializer.Meta.fields + ["raw_data"]
