from rest_framework import serializers

from .models import Container, ContainerRequest, ContainerTemplate


class ContainerSerializer(serializers.ModelSerializer):
    agent_hostname = serializers.CharField(source="agent.hostname", read_only=True)
    requester_username = serializers.CharField(
        source="requester.username", read_only=True, default=None, allow_null=True
    )

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
            "requester",
            "requester_username",
            "created_via_request",
        ]
        read_only_fields = ["last_seen", "requester_username"]


# ---------- Templates ----------

class ContainerTemplateSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = ContainerTemplate
        fields = [
            "id",
            "name",
            "description",
            "kind",
            "image",
            "image_options",
            "env_schema",
            "port_schema",
            "default_volumes",
            "compose_yaml",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_by_username", "created_at", "updated_at"]

    def validate(self, attrs):
        kind = attrs.get("kind") or (self.instance.kind if self.instance else None)
        if kind == ContainerTemplate.Kind.SIMPLE:
            # simple 템플릿은 image 또는 image_options 중 하나 필수
            image = attrs.get("image") or (self.instance.image if self.instance else "")
            image_options = attrs.get("image_options")
            if image_options is None and self.instance:
                image_options = self.instance.image_options
            if not image and not image_options:
                raise serializers.ValidationError(
                    {"image": "simple 템플릿은 image 또는 image_options 중 하나를 지정해야 합니다."}
                )
        elif kind == ContainerTemplate.Kind.COMPOSE:
            compose_yaml = attrs.get("compose_yaml") or (
                self.instance.compose_yaml if self.instance else ""
            )
            if not compose_yaml.strip():
                raise serializers.ValidationError(
                    {"compose_yaml": "compose 템플릿은 compose_yaml을 반드시 입력해야 합니다."}
                )
        return attrs


# ---------- Requests ----------

class ContainerRequestSerializer(serializers.ModelSerializer):
    """사용자가 제출하는 컨테이너 요청 (생성/삭제)."""

    requester_username = serializers.CharField(
        source="requester.username", read_only=True, default=None, allow_null=True
    )
    reviewer_username = serializers.CharField(
        source="reviewer.username", read_only=True, default=None, allow_null=True
    )
    template_name = serializers.CharField(
        source="template.name", read_only=True, default=None, allow_null=True
    )
    target_agent_hostname = serializers.CharField(
        source="target_agent.hostname", read_only=True, default=None, allow_null=True
    )
    target_container_name = serializers.CharField(
        source="target_container.name", read_only=True, default=None, allow_null=True
    )

    class Meta:
        model = ContainerRequest
        fields = [
            "id",
            "requester",
            "requester_username",
            "action",
            "status",
            # create-specific
            "template",
            "template_name",
            "target_agent",
            "target_agent_hostname",
            "custom_name",
            "selected_image",
            "custom_env",
            "custom_ports",
            # delete-specific
            "target_container",
            "target_container_name",
            # review
            "reviewer",
            "reviewer_username",
            "reviewed_at",
            "review_note",
            # progress
            "progress_message",
            "progress_percent",
            "deployment_log",
            # audit
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "requester",
            "requester_username",
            "status",
            "template_name",
            "target_agent_hostname",
            "target_container_name",
            "reviewer",
            "reviewer_username",
            "reviewed_at",
            "progress_message",
            "progress_percent",
            "deployment_log",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        action = attrs.get("action") or (self.instance.action if self.instance else None)

        if action == ContainerRequest.Action.CREATE:
            if not (attrs.get("template") or (self.instance and self.instance.template)):
                raise serializers.ValidationError(
                    {"template": "create 요청은 template을 지정해야 합니다."}
                )
            if not (attrs.get("target_agent") or (self.instance and self.instance.target_agent)):
                raise serializers.ValidationError(
                    {"target_agent": "create 요청은 target_agent를 지정해야 합니다."}
                )
        elif action == ContainerRequest.Action.DELETE:
            if not (
                attrs.get("target_container")
                or (self.instance and self.instance.target_container)
            ):
                raise serializers.ValidationError(
                    {"target_container": "delete 요청은 target_container를 지정해야 합니다."}
                )
        return attrs


class ReviewActionSerializer(serializers.Serializer):
    """Request 승인/반려 입력."""

    note = serializers.CharField(required=False, allow_blank=True, max_length=2000)
