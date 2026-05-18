from rest_framework import serializers

from .models import ModelAsset, ModelPrepareJob, ModelUploadRequest, ModelVersion, ModelVersionCache
from .services import create_model_upload_request


class ModelVersionSerializer(serializers.ModelSerializer):
    uploaded_by_username = serializers.CharField(source="uploaded_by.username", read_only=True, default=None)
    asset_name = serializers.CharField(source="asset.name", read_only=True)
    asset_slug = serializers.CharField(source="asset.slug", read_only=True)

    class Meta:
        model = ModelVersion
        fields = [
            "id",
            "asset",
            "asset_name",
            "asset_slug",
            "version",
            "original_filename",
            "storage_path",
            "size_bytes",
            "sha256",
            "status",
            "metadata",
            "uploaded_by",
            "uploaded_by_username",
            "created_at",
        ]
        read_only_fields = fields


class ModelAssetSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source="owner.username", read_only=True)
    version_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = ModelAsset
        fields = [
            "id",
            "owner",
            "owner_username",
            "name",
            "slug",
            "description",
            "visibility",
            "framework",
            "task",
            "tags",
            "version_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "owner", "owner_username", "version_count", "created_at", "updated_at"]

    def validate_tags(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("tags must be a list")
        return [str(item) for item in value]


class ModelVersionUploadSerializer(serializers.Serializer):
    version = serializers.CharField(max_length=80)
    file = serializers.FileField()
    metadata = serializers.JSONField(required=False)


class ModelVersionImportSerializer(serializers.Serializer):
    version = serializers.CharField(max_length=80)
    source_path = serializers.CharField(max_length=1024)
    metadata = serializers.JSONField(required=False)


class ModelUploadRequestSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True, required=True)
    requester_username = serializers.CharField(source="requester.username", read_only=True)
    reviewer_username = serializers.CharField(source="reviewer.username", read_only=True, default=None)
    created_asset_slug = serializers.CharField(source="created_asset.slug", read_only=True, default=None)
    created_version_label = serializers.CharField(source="created_version.version", read_only=True, default=None)
    created_template_name = serializers.CharField(source="created_template.name", read_only=True, default=None)

    class Meta:
        model = ModelUploadRequest
        fields = [
            "id",
            "requester",
            "requester_username",
            "reviewer",
            "reviewer_username",
            "name",
            "slug",
            "description",
            "framework",
            "task",
            "tags",
            "version",
            "template_name",
            "template_description",
            "base_image",
            "requires_gpu",
            "workspace_kind",
            "workspace_port",
            "default_max_runtime_hours",
            "min_cpu_percent",
            "min_memory_mb",
            "min_workspace_gb",
            "file",
            "original_filename",
            "size_bytes",
            "sha256",
            "status",
            "review_note",
            "reviewed_at",
            "created_asset",
            "created_asset_slug",
            "created_version",
            "created_version_label",
            "created_template",
            "created_template_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "requester",
            "requester_username",
            "reviewer",
            "reviewer_username",
            "original_filename",
            "size_bytes",
            "sha256",
            "status",
            "review_note",
            "reviewed_at",
            "created_asset",
            "created_asset_slug",
            "created_version",
            "created_version_label",
            "created_template",
            "created_template_name",
            "created_at",
            "updated_at",
        ]

    def validate_tags(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("tags must be a list")
        return [str(item) for item in value]

    def create(self, validated_data):
        uploaded_file = validated_data.pop("file")
        requester = self.context["request"].user
        return create_model_upload_request(requester=requester, uploaded_file=uploaded_file, **validated_data)


class ModelUploadRequestReviewSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class ModelVersionCacheSerializer(serializers.ModelSerializer):
    agent_hostname = serializers.CharField(source="agent.hostname", read_only=True)
    asset_slug = serializers.CharField(source="version.asset.slug", read_only=True)
    version_label = serializers.CharField(source="version.version", read_only=True)

    class Meta:
        model = ModelVersionCache
        fields = [
            "id",
            "agent",
            "agent_hostname",
            "version",
            "asset_slug",
            "version_label",
            "status",
            "cache_path",
            "size_bytes",
            "sha256",
            "last_verified_at",
            "lease_expires_at",
            "last_error",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ModelPrepareJobSerializer(serializers.ModelSerializer):
    agent_hostname = serializers.CharField(source="agent.hostname", read_only=True)
    asset_slug = serializers.CharField(source="version.asset.slug", read_only=True)
    version_label = serializers.CharField(source="version.version", read_only=True)

    class Meta:
        model = ModelPrepareJob
        fields = [
            "id",
            "agent",
            "agent_hostname",
            "version",
            "asset_slug",
            "version_label",
            "cache",
            "status",
            "transfer_mode",
            "progress_percent",
            "progress_message",
            "bytes_total",
            "bytes_done",
            "lease_expires_at",
            "dispatched_at",
            "started_at",
            "completed_at",
            "failed_at",
            "error",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
