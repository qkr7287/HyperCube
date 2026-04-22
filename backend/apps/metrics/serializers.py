from rest_framework import serializers

from .models import ContainerMetricsHistory, SystemMetricsHistory


class SystemMetricsHistorySerializer(serializers.ModelSerializer):
    agent_hostname = serializers.CharField(source="agent.hostname", read_only=True)
    # raw_data JSON 에서 꺼내오는 파생 필드들 — 컬럼 추가 없이 차트용으로 노출.
    network_connections = serializers.SerializerMethodField()
    processes_total = serializers.SerializerMethodField()
    processes_running = serializers.SerializerMethodField()
    logins_total = serializers.SerializerMethodField()
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
            "memory_usage",
            "memory_used",
            "memory_total",
            "disk_usage",
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
            "recorded_at",
        ]


class ContainerMetricsHistoryDetailSerializer(ContainerMetricsHistorySerializer):
    class Meta(ContainerMetricsHistorySerializer.Meta):
        fields = ContainerMetricsHistorySerializer.Meta.fields + ["raw_data"]
