import uuid

from django.db.models import Q
from rest_framework import serializers

from apps.agents.models import GpuSlice
from apps.models_catalog.models import ModelAsset, ModelVersion

from .services.policy import request_payload_policy_errors
from .services.recommend import min_limit_errors, recommend_resource_limits
from .models import (
    ConsoleSession,
    Container,
    ContainerEvent,
    ContainerRequest,
    ContainerRequestGpuSlice,
    ContainerTemplate,
)


class ContainerEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContainerEvent
        fields = ["id", "ts", "kind", "exit_code", "signal", "health_status"]
        read_only_fields = fields


class ConsoleSessionSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = ConsoleSession
        fields = [
            "id",
            "exec_id",
            "username",
            "cmd",
            "user_param",
            "tty",
            "opened_at",
            "closed_at",
            "duration_seconds",
            "exit_code",
            "close_reason",
        ]
        read_only_fields = fields


class ContainerSerializer(serializers.ModelSerializer):
    agent_hostname = serializers.CharField(source="agent.hostname", read_only=True)
    requester_username = serializers.CharField(
        source="requester.username", read_only=True, default=None, allow_null=True
    )
    mounted_model_versions = serializers.SerializerMethodField()

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
            "allocated_gpu_slice_ids",
            "mounted_model_version_ids",
            "mounted_model_versions",
            "workspace_enabled",
            "workspace_kind",
            "workspace_internal_port",
            "workspace_host_port",
            "workspace_base_url",
            "workspace_health",
            "workspace_max_runtime_hours",
            "workspace_runtime_expires_at",
            "workspace_token_expires_at",
            "cpu_percent_limit",
            "memory_mb_limit",
            "workspace_gb_limit",
            "workspace_device",
            "workspace_project_id",
            "limit_updated_at",
        ]
        read_only_fields = [
            "last_seen",
            "requester_username",
            "allocated_gpu_slice_ids",
            "mounted_model_version_ids",
            "mounted_model_versions",
            "workspace_enabled",
            "workspace_kind",
            "workspace_internal_port",
            "workspace_host_port",
            "workspace_base_url",
            "workspace_health",
            "workspace_max_runtime_hours",
            "workspace_runtime_expires_at",
            "workspace_token_expires_at",
            "cpu_percent_limit",
            "memory_mb_limit",
            "workspace_gb_limit",
            "workspace_device",
            "workspace_project_id",
            "limit_updated_at",
        ]

    def get_mounted_model_versions(self, obj):
        return _model_version_briefs(obj.mounted_model_version_ids)


class MyContainerSerializer(ContainerSerializer):
    request_id = serializers.UUIDField(
        source="created_via_request_id",
        read_only=True,
        allow_null=True,
    )
    template_name = serializers.CharField(
        source="created_via_request.template.name",
        read_only=True,
        default=None,
        allow_null=True,
    )
    requested_at = serializers.DateTimeField(
        source="created_via_request.created_at",
        read_only=True,
        allow_null=True,
    )
    request_status = serializers.CharField(
        source="created_via_request.status",
        read_only=True,
        default=None,
        allow_null=True,
    )
    review_note = serializers.CharField(
        source="created_via_request.review_note",
        read_only=True,
        default="",
    )
    custom_env = serializers.JSONField(
        source="created_via_request.custom_env",
        read_only=True,
    )
    custom_ports = serializers.JSONField(
        source="created_via_request.custom_ports",
        read_only=True,
    )
    selected_image = serializers.CharField(
        source="created_via_request.selected_image",
        read_only=True,
        default="",
    )

    class Meta(ContainerSerializer.Meta):
        fields = ContainerSerializer.Meta.fields + [
            "request_id",
            "template_name",
            "requested_at",
            "request_status",
            "review_note",
            "custom_env",
            "custom_ports",
            "selected_image",
        ]


class WorkspaceSerializer(MyContainerSerializer):
    class Meta(MyContainerSerializer.Meta):
        fields = MyContainerSerializer.Meta.fields


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
            "category",
            "requires_gpu",
            "workspace_enabled",
            "workspace_kind",
            "workspace_port",
            "default_workdir",
            "network_policy",
            "default_max_runtime_hours",
            "cpu_weight",
            "ram_weight",
            "disk_weight",
            "min_cpu_percent",
            "min_memory_mb",
            "min_workspace_gb",
            "image",
            "image_options",
            "env_schema",
            "port_schema",
            "default_volumes",
            "default_model_version_ids",
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
        workspace_enabled = attrs.get("workspace_enabled")
        if workspace_enabled is None and self.instance:
            workspace_enabled = self.instance.workspace_enabled
        workspace_kind = attrs.get("workspace_kind") or (
            self.instance.workspace_kind if self.instance else ""
        )
        if workspace_enabled and not workspace_kind:
            raise serializers.ValidationError(
                {"workspace_kind": "workspace_kind is required when workspace is enabled."}
            )
        return attrs


# ---------- Requests ----------

class ContainerRequestSerializer(serializers.ModelSerializer):
    """사용자가 제출하는 컨테이너 요청 (생성/삭제)."""

    cpu_percent = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
        max_value=10000,
    )
    memory_mb = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    workspace_gb = serializers.IntegerField(required=False, allow_null=True, min_value=0)
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
    gpu_slice_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        write_only=True,
    )
    selected_gpu_slice_ids = serializers.SerializerMethodField()
    selected_model_versions = serializers.SerializerMethodField()

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
            "gpu_slice_ids",
            "selected_gpu_slice_ids",
            "gpu_slice_ids_snapshot",
            "gpu_share_ok",
            "model_version_ids",
            "selected_model_versions",
            "workspace_enabled_snapshot",
            "workspace_kind_snapshot",
            "requested_max_runtime_hours",
            "cpu_percent",
            "memory_mb",
            "workspace_gb",
            "prepare_job_ids",
            "deployment_phase",
            "workspace_token_expires_at",
            # delete-specific
            "target_container",
            "target_container_name",
            "target_container_snapshot_name",
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
            "target_container_snapshot_name",
            "reviewer",
            "reviewer_username",
            "reviewed_at",
            "progress_message",
            "progress_percent",
            "deployment_log",
            "selected_gpu_slice_ids",
            "selected_model_versions",
            "gpu_slice_ids_snapshot",
            "workspace_enabled_snapshot",
            "workspace_kind_snapshot",
            "prepare_job_ids",
            "deployment_phase",
            "workspace_token_expires_at",
            "created_at",
            "updated_at",
        ]

    def get_selected_gpu_slice_ids(self, obj):
        return list(obj.gpu_slice_selections.order_by("id").values_list("slice_id", flat=True))

    def get_selected_model_versions(self, obj):
        return _model_version_briefs(obj.model_version_ids)

    def validate(self, attrs):
        action = attrs.get("action") or (self.instance.action if self.instance else None)
        gpu_slice_ids = attrs.get("gpu_slice_ids")
        model_version_ids = attrs.get("model_version_ids")
        requested_hours = attrs.get("requested_max_runtime_hours")
        template = attrs.get("template") or (self.instance and self.instance.template)
        if (
            action == ContainerRequest.Action.CREATE
            and requested_hours is None
            and template
            and template.default_max_runtime_hours
        ):
            requested_hours = template.default_max_runtime_hours
        if requested_hours is not None and requested_hours <= 0:
            raise serializers.ValidationError(
                {"requested_max_runtime_hours": "Runtime must be a positive hour value."}
            )
        policy_errors = request_payload_policy_errors(
            gpu_share_ok=attrs.get("gpu_share_ok") or False,
            requested_max_runtime_hours=requested_hours,
        )
        if policy_errors:
            raise serializers.ValidationError(policy_errors)

        if action == ContainerRequest.Action.CREATE:
            if not template:
                raise serializers.ValidationError(
                    {"template": "create 요청은 template을 지정해야 합니다."}
                )
            if not (attrs.get("target_agent") or (self.instance and self.instance.target_agent)):
                raise serializers.ValidationError(
                    {"target_agent": "create 요청은 target_agent를 지정해야 합니다."}
                )
            target_agent = attrs.get("target_agent") or (self.instance and self.instance.target_agent)
            self._apply_resource_limit_defaults(attrs, template, target_agent)
            if gpu_slice_ids is not None:
                normalized_ids = _normalize_gpu_slice_ids(gpu_slice_ids)
                slices = list(GpuSlice.objects.select_related("gpu").filter(id__in=normalized_ids))
                if len(slices) != len(normalized_ids):
                    raise serializers.ValidationError(
                        {"gpu_slice_ids": "One or more GPU slices do not exist."}
                    )
                if target_agent and any(slice_obj.gpu.agent_id != target_agent.id for slice_obj in slices):
                    raise serializers.ValidationError(
                        {"gpu_slice_ids": "GPU slices must belong to the target agent."}
                    )
                attrs["gpu_slice_ids"] = normalized_ids
            if template and template.requires_gpu and not (
                attrs.get("gpu_slice_ids")
                or (self.instance and self.instance.gpu_slice_selections.exists())
            ):
                raise serializers.ValidationError(
                    {"gpu_slice_ids": "This template requires a GPU slice."}
                )
            if model_version_ids is not None:
                attrs["model_version_ids"] = self._validate_model_version_ids(model_version_ids)
        elif action == ContainerRequest.Action.DELETE:
            if gpu_slice_ids:
                raise serializers.ValidationError(
                    {"gpu_slice_ids": "delete requests cannot select GPU slices."}
                )
            if model_version_ids:
                raise serializers.ValidationError(
                    {"model_version_ids": "delete requests cannot select model versions."}
                )
            target_container = attrs.get("target_container") or (
                self.instance and self.instance.target_container
            )
            if not target_container:
                raise serializers.ValidationError(
                    {"target_container": "delete 요청은 target_container를 지정해야 합니다."}
                )
            target_agent = attrs.get("target_agent") or (
                self.instance and self.instance.target_agent
            )
            if target_agent and target_agent.id != target_container.agent_id:
                raise serializers.ValidationError(
                    {"target_agent": "target_agent must match target_container.agent."}
                )
            attrs["target_agent"] = target_container.agent
        return attrs

    def create(self, validated_data):
        gpu_slice_ids = validated_data.pop("gpu_slice_ids", None)
        self._apply_workspace_snapshots(validated_data)
        request = super().create(validated_data)
        if gpu_slice_ids is not None:
            self._set_gpu_slice_selections(request, gpu_slice_ids)
        return request

    def update(self, instance, validated_data):
        gpu_slice_ids = validated_data.pop("gpu_slice_ids", None)
        self._apply_workspace_snapshots(validated_data, instance=instance)
        request = super().update(instance, validated_data)
        if gpu_slice_ids is not None:
            self._set_gpu_slice_selections(request, gpu_slice_ids)
        return request

    def _apply_workspace_snapshots(self, data, instance=None):
        template = data.get("template") or (instance.template if instance else None)
        if not template:
            return
        data["workspace_enabled_snapshot"] = bool(template.workspace_enabled)
        data["workspace_kind_snapshot"] = template.workspace_kind if template.workspace_enabled else ""
        if data.get("requested_max_runtime_hours") is None and template.default_max_runtime_hours:
            data["requested_max_runtime_hours"] = template.default_max_runtime_hours

    def _apply_resource_limit_defaults(self, data, template, target_agent):
        recommendation = recommend_resource_limits(target_agent, template)
        if data.get("cpu_percent") is None:
            data["cpu_percent"] = recommendation.cpu_percent
        if data.get("memory_mb") is None:
            data["memory_mb"] = recommendation.memory_mb
        if data.get("workspace_gb") is None:
            data["workspace_gb"] = recommendation.workspace_gb

        errors = min_limit_errors(
            template,
            cpu_percent=data.get("cpu_percent"),
            memory_mb=data.get("memory_mb"),
            workspace_gb=data.get("workspace_gb"),
        )
        if errors:
            raise serializers.ValidationError(errors)

    def _set_gpu_slice_selections(self, request, gpu_slice_ids):
        ContainerRequestGpuSlice.objects.filter(request=request).delete()
        rows = [
            ContainerRequestGpuSlice(request=request, slice_id=slice_id)
            for slice_id in gpu_slice_ids
        ]
        ContainerRequestGpuSlice.objects.bulk_create(rows)
        request.gpu_slice_ids_snapshot = list(gpu_slice_ids)
        request.save(update_fields=["gpu_slice_ids_snapshot", "updated_at"])

    def _validate_model_version_ids(self, values):
        if not isinstance(values, list):
            raise serializers.ValidationError("model_version_ids must be a list")
        for value in values:
            try:
                uuid.UUID(str(value))
            except (TypeError, ValueError) as exc:
                raise serializers.ValidationError("model_version_ids must contain valid UUID values") from exc
        normalized = _normalize_model_version_ids(values)
        if not normalized:
            return []

        qs = ModelVersion.objects.select_related("asset").filter(
            id__in=normalized,
            status=ModelVersion.Status.AVAILABLE,
        )
        request = self.context.get("request")
        user = request.user if request else None
        if getattr(user, "role", None) != "admin":
            qs = qs.filter(
                Q(asset__owner=user)
                | Q(asset__visibility=ModelAsset.Visibility.SHARED)
            )
        found = {str(version.id) for version in qs}
        if found != set(normalized):
            raise serializers.ValidationError("One or more model versions are not available")
        return normalized


class ReviewActionSerializer(serializers.Serializer):
    """Request 승인/반려 입력."""

    note = serializers.CharField(required=False, allow_blank=True, max_length=2000)


def _normalize_gpu_slice_ids(values):
    normalized = []
    seen = set()
    for value in values or []:
        if value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def _normalize_model_version_ids(values):
    normalized = []
    seen = set()
    for value in values or []:
        text = str(value)
        if text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def _model_version_briefs(version_ids):
    ids = []
    for value in _normalize_model_version_ids(version_ids):
        try:
            uuid.UUID(str(value))
        except (TypeError, ValueError):
            continue
        ids.append(value)
    if not ids:
        return []
    versions = {
        str(version.id): version
        for version in ModelVersion.objects.select_related("asset").filter(id__in=ids)
    }
    return [
        {
            "id": str(version.id),
            "asset": str(version.asset_id),
            "asset_name": version.asset.name,
            "asset_slug": version.asset.slug,
            "version": version.version,
            "sha256": version.sha256,
            "size_bytes": version.size_bytes,
        }
        for version_id in ids
        if (version := versions.get(version_id)) is not None
    ]
