from rest_framework import serializers

from .models import ContainerMetricsHistory, SystemMetricsHistory


class SystemMetricsHistorySerializer(serializers.ModelSerializer):
    agent_hostname = serializers.CharField(source="agent.hostname", read_only=True)

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
            "recorded_at",
        ]


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
