from rest_framework import serializers

from .models import AlertRule, AuditLog, Template


class TemplateSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(
        source="created_by.username", read_only=True
    )

    class Meta:
        model = Template
        fields = [
            "id",
            "name",
            "category",
            "config",
            "created_by",
            "created_by_username",
            "is_builtin",
            "created_at",
        ]
        read_only_fields = ["id", "created_by", "created_at"]


class AlertRuleSerializer(serializers.ModelSerializer):
    agent_hostname = serializers.CharField(
        source="agent.hostname", read_only=True, default=None
    )

    class Meta:
        model = AlertRule
        fields = [
            "id",
            "agent",
            "agent_hostname",
            "metric",
            "threshold",
            "action",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class AuditLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(
        source="user.username", read_only=True, default="System"
    )

    class Meta:
        model = AuditLog
        fields = ["id", "user", "username", "action", "target", "timestamp"]
        read_only_fields = fields
