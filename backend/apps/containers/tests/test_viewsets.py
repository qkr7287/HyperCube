from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch

from .factories import create_container, create_request, create_template, create_user


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
