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
            "token",
            "registered_at",
            "approved_at",
            "last_seen_at",
            "archived_at",
            "cpu_cores",
            "cpu_model",
            "ram_total_mb",
            "disk_total_gb",
            "lvm_pool_size_gb",
            "nic_speed_mbps",
            "filesystem",
            "target_users",
            "safety_margin",
            "capacity_updated_at",
            "is_active",
            "container_count",
        }
        self.assertEqual(set(serializer.data.keys()), expected)

    def test_token_is_returned_on_response(self):
        """자동 승인 정책 이후 token은 응답에 포함되어야 한다 (Agent가 받아서 사용)."""
        agent = create_agent(token="agent_xxx")
        serializer = AgentSerializer(agent)
        self.assertEqual(serializer.data["token"], "agent_xxx")

    def test_client_cannot_set_token_on_write(self):
        """read_only이므로 input에 token이 있어도 무시돼야 한다."""
        serializer = AgentSerializer(
            data={
                "hostname": "fresh-host",
                "ip_address": "10.0.0.1",
                "token": "hacker-provided-token",
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertNotIn("token", serializer.validated_data)
