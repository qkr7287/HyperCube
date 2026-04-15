from rest_framework import status
from rest_framework.test import APITestCase

from .factories import create_agent, create_user


class AgentViewSetTest(APITestCase):
    def setUp(self):
        self.admin = create_user(role="super_admin", username="admin")
        self.server_admin = create_user(role="server_admin", username="sadmin")
        self.viewer = create_user(role="viewer", username="viewer")
        self.agent = create_agent()

    def test_list_agents_as_server_admin(self):
        self.client.force_authenticate(user=self.server_admin)
        response = self.client.get("/api/agents/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data["success"])

    def test_list_agents_as_viewer_forbidden(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get("/api/agents/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_agents_unauthenticated(self):
        response = self.client.get("/api/agents/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_register_new_agent_auto_approves_and_returns_token(self):
        response = self.client.post(
            "/api/agents/",
            {"hostname": "fresh-host", "ip_address": "10.0.0.5"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        body = response.json()["data"]
        self.assertEqual(body["status"], "approved")
        self.assertTrue(body["token"].startswith("agent_"))
        self.assertIsNotNone(body["approved_at"])

    def test_register_idempotent_on_duplicate_hostname(self):
        first = self.client.post(
            "/api/agents/",
            {"hostname": "dup-host", "ip_address": "10.0.0.6"},
            format="json",
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        original_token = first.json()["data"]["token"]

        second = self.client.post(
            "/api/agents/",
            {"hostname": "dup-host", "ip_address": "10.0.0.6"},
            format="json",
        )
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        # 같은 hostname이면 기존 token 그대로 반환
        self.assertEqual(second.json()["data"]["token"], original_token)

    def test_manage_status_endpoint_removed(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f"/api/agents/{self.agent.id}/manage-status/",
            {"action": "approve"},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
