from rest_framework import serializers

from .models import Agent, ServerAssignment


class AgentSerializer(serializers.ModelSerializer):
    container_count = serializers.IntegerField(
        source="containers.count", read_only=True
    )

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
            "container_count",
        ]
        read_only_fields = ["id", "status", "registered_at", "approved_at"]
        extra_kwargs = {
            "token": {"write_only": True},
        }


class AgentStatusSerializer(serializers.ModelSerializer):
    """Agent 상태/토큰 조회용 (polling 응답)"""

    class Meta:
        model = Agent
        fields = ["id", "status", "token"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # pending/rejected 상태에서는 token 노출하지 않음
        if instance.status != Agent.Status.APPROVED:
            data["token"] = None
        return data


class AgentApproveSerializer(serializers.Serializer):
    """Agent 승인/거절 액션용"""

    action = serializers.ChoiceField(choices=["approve", "reject"])


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
