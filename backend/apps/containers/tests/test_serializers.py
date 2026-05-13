from django.test import TestCase

from apps.containers.serializers import ContainerSerializer

from .factories import create_container


class ContainerSerializerTest(TestCase):
    def test_contains_expected_fields(self):
        container = create_container()
        serializer = ContainerSerializer(container)
        expected = {
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
        }
        self.assertEqual(set(serializer.data.keys()), expected)

    def test_agent_hostname_populated(self):
        container = create_container()
        serializer = ContainerSerializer(container)
        self.assertEqual(serializer.data["agent_hostname"], "test-host")
