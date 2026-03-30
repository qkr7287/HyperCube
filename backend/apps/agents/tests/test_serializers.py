from django.test import TestCase

from apps.agents.serializers import AgentSerializer

from .factories import create_agent


class AgentSerializerTest(TestCase):
    def test_contains_expected_fields(self):
        agent = create_agent()
        serializer = AgentSerializer(agent)
        expected = {
            "id",
            "hostname",
            "ip_address",
            "status",
            "registered_at",
            "approved_at",
            "container_count",
        }
        self.assertEqual(set(serializer.data.keys()), expected)

    def test_token_is_write_only(self):
        agent = create_agent()
        serializer = AgentSerializer(agent)
        self.assertNotIn("token", serializer.data)
