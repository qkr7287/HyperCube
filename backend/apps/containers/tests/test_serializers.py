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
        }
        self.assertEqual(set(serializer.data.keys()), expected)

    def test_agent_hostname_populated(self):
        container = create_container()
        serializer = ContainerSerializer(container)
        self.assertEqual(serializer.data["agent_hostname"], "test-host")
