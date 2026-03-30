from rest_framework import serializers

from .models import Container


class ContainerSerializer(serializers.ModelSerializer):
    agent_hostname = serializers.CharField(source="agent.hostname", read_only=True)

    class Meta:
        model = Container
        fields = [
            "container_id",
            "name",
            "image",
            "agent",
            "agent_hostname",
            "status",
            "last_seen",
        ]
        read_only_fields = ["last_seen"]
