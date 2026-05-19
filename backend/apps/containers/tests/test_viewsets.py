import json
from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from .factories import create_agent, create_container, create_request, create_template, create_user


class ContainerViewSetTest(APITestCase):
    def setUp(self):
        self.admin = create_user(role="admin", username="sadmin")
        self.viewer = create_user(role="user", username="viewer")
        self.container = create_container()

    def test_list_containers(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get("/api/containers/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data["success"])

    def test_retrieve_container(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(f"/api/containers/{self.container.container_id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["data"]["name"], "test-container")

    def test_viewer_forbidden(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get("/api/containers/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_authenticated_user_can_get_resource_recommendation(self):
        agent = create_agent(
            hostname="recommend-host",
            ip_address="10.0.0.30",
            cpu_cores=24,
            ram_total_mb=262144,
            workspace_pool_total_gb=3000,
            target_users=4,
            safety_margin=0.8,
        )
        template = create_template(created_by=self.admin, name="Recommend Template")
        self.client.force_authenticate(user=self.viewer)

        for base_path in ("/api/containers", "/api/v1/containers"):
            response = self.client.get(
                f"{base_path}/recommend/?template={template.id}&agent={agent.id}"
            )

            self.assertEqual(response.status_code, status.HTTP_200_OK, response.json())
            payload = response.json()["data"]
            self.assertEqual(payload["cpu_percent"], 500)
            self.assertEqual(payload["memory_mb"], 51 * 1024)
            self.assertEqual(payload["workspace_gb"], 600)
            self.assertEqual(payload["template"], str(template.id))
            self.assertEqual(payload["agent"], str(agent.id))


class MyContainerViewSetTest(APITestCase):
    def setUp(self):
        self.user = create_user(role="user", username="owner")
        self.other_user = create_user(role="user", username="other")
        self.admin = create_user(role="admin", username="admin")

        template = create_template(created_by=self.admin)
        owned_request = create_request(
            requester=self.user,
            template=template,
            status="deployed",
        )
        other_request = create_request(
            requester=self.other_user,
            template=template,
            status="deployed",
        )

        self.owned_container = create_container(
            container_id="owned12345678",
            requester=self.user,
            created_via_request=owned_request,
        )
        self.other_container = create_container(
            container_id="other12345678",
            requester=self.other_user,
            created_via_request=other_request,
            name="other-container",
        )

    def test_user_only_sees_owned_containers(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/my-containers/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()["data"]
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["container_id"], self.owned_container.container_id)
        self.assertEqual(payload["results"][0]["template_name"], "Test Nginx")

    def test_user_cannot_retrieve_other_users_container(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f"/api/my-containers/{self.other_container.container_id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("apps.containers.viewsets.get_redis_client")
    def test_current_metrics_returns_empty_network_stats_when_cache_missing(self, mocked_redis):
        mocked_redis.return_value.get.return_value = None
        mocked_redis.return_value.scan_iter.return_value = []

        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            f"/api/my-containers/{self.owned_container.container_id}/current-metrics/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()["data"]
        self.assertEqual(payload["containerId"], self.owned_container.container_id)
        self.assertEqual(payload["network_stats"], [])

    @patch("apps.containers.viewsets.get_redis_client")
    def test_current_metrics_merges_workspace_limit_metadata(self, mocked_redis):
        self.owned_container.workspace_gb_limit = 100
        self.owned_container.workspace_device = "/dev/vg0/cid_owned12345678"
        self.owned_container.save(update_fields=["workspace_gb_limit", "workspace_device", "last_seen"])
        mocked_redis.return_value.get.return_value = json.dumps({
            "timestamp": "2026-05-15T00:00:00Z",
            "data": {
                "containerId": self.owned_container.container_id,
                "workspace": {"usedGb": 12, "usedPct": 12.0},
            },
        })

        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            f"/api/my-containers/{self.owned_container.container_id}/current-metrics/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        workspace = response.json()["data"]["workspace"]
        self.assertEqual(workspace["usedGb"], 12)
        self.assertEqual(workspace["sizeGb"], 100)
        self.assertEqual(workspace["device"], "/dev/vg0/cid_owned12345678")

    @patch("apps.containers.viewsets.MyContainerViewSet._dispatch_and_wait")
    def test_update_limits_updates_container_limit_snapshot(self, mocked_dispatch):
        mocked_dispatch.return_value = {"success": True, "data": {"ok": True}}
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            f"/api/my-containers/{self.owned_container.container_id}/update-limits/",
            {"cpu_percent": 400, "memory_mb": 16384},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.json())
        self.owned_container.refresh_from_db()
        self.assertEqual(self.owned_container.cpu_percent_limit, 400)
        self.assertEqual(self.owned_container.memory_mb_limit, 16384)
        self.assertIsNotNone(self.owned_container.limit_updated_at)
