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

    def test_approve_agent(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f"/api/agents/{self.agent.id}/manage-status/",
            {"action": "approve"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.agent.refresh_from_db()
        self.assertEqual(self.agent.status, "approved")

    def test_reject_agent(self):
        self.client.force_authenticate(user=self.admin)
        pending = create_agent(hostname="pending-host", status="pending")
        response = self.client.post(
            f"/api/agents/{pending.id}/manage-status/",
            {"action": "reject"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        pending.refresh_from_db()
        self.assertEqual(pending.status, "rejected")
