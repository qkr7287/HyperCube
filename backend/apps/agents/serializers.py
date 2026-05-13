from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from .models import Agent, AgentStatusEvent, GpuDevice, GpuSlice

# 메인 UI active 판정 grace (Backend tasks.py와 일치 시켜야 함)
_ACTIVE_GRACE_SECONDS = 5 * 60


class AgentSerializer(serializers.ModelSerializer):
    container_count = serializers.IntegerField(
        source="containers.count", read_only=True
    )
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = Agent
        fields = [
            "id",
            "hostname",
            "ip_address",
            "status",
            "token",
            "registered_at",
            "approved_at",
            "last_seen_at",
            "archived_at",
            "is_active",
            "container_count",
        ]
        # token은 register 응답에서 Agent가 즉시 사용해야 하므로 노출.
        # 클라이언트가 set 못 하게 read_only 처리.
        read_only_fields = [
            "id",
            "status",
            "token",
            "registered_at",
            "approved_at",
            "last_seen_at",
            "archived_at",
        ]

    def get_is_active(self, obj: Agent) -> bool:
        if obj.last_seen_at is None:
            return False
        return obj.last_seen_at >= timezone.now() - timedelta(seconds=_ACTIVE_GRACE_SECONDS)


class AgentStatusSerializer(serializers.ModelSerializer):
    """Agent 상태/토큰 조회용. 자동 승인 정책 이후 항상 approved + token 반환."""

    class Meta:
        model = Agent
        fields = ["id", "status", "token"]


class AgentStatusEventSerializer(serializers.ModelSerializer):
    """Snapshot of one online/offline transition for the dashboard log."""

    server_id = serializers.CharField(source="agent_id", read_only=True)

    class Meta:
        model = AgentStatusEvent
        fields = [
            "id",
            "server_id",
            "hostname",
            "status",
            "occurred_at",
            "previous_offline_seconds",
        ]


class GpuSliceSerializer(serializers.ModelSerializer):
    class Meta:
        model = GpuSlice
        fields = [
            "id",
            "kind",
            "device_id",
            "label",
            "mig_profile",
            "memory_mb",
            "allow_shared",
            "status",
            "last_seen_at",
        ]


class GpuDeviceSerializer(serializers.ModelSerializer):
    slices = GpuSliceSerializer(many=True, read_only=True)

    class Meta:
        model = GpuDevice
        fields = [
            "id",
            "index",
            "vendor",
            "name",
            "uuid",
            "pci_bus_id",
            "total_memory_mb",
            "driver_version",
            "cuda_version",
            "mig_capable",
            "mig_enabled",
            "status",
            "last_seen_at",
            "slices",
        ]


