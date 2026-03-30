from rest_framework import status
from rest_framework.test import APITestCase

from .factories import create_container, create_user


class ContainerViewSetTest(APITestCase):
    def setUp(self):
        self.admin = create_user(role="server_admin", username="sadmin")
        self.viewer = create_user(role="viewer", username="viewer")
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
