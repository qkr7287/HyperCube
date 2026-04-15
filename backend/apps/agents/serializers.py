from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from .models import Agent, ServerAssignment

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


class ServerAssignmentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    agent_hostname = serializers.CharField(source="agent.hostname", read_only=True)

    class Meta:
        model = ServerAssignment
        fields = [
            "id",
            "user",
            "agent",
            "username",
            "agent_hostname",
            "created_at",
        ]
        read_only_fields = ["created_at"]
