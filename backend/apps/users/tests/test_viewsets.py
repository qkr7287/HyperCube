from rest_framework import status
from rest_framework.test import APITestCase

from .factories import create_user


class UserViewSetTest(APITestCase):
    def setUp(self):
        self.admin = create_user(role="admin", username="admin")
        self.viewer = create_user(role="user", username="viewer")

    def test_list_users_as_admin(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get("/api/users/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data["success"])

    def test_list_users_as_viewer_forbidden(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get("/api/users/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_me_endpoint(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get("/api/users/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["data"]["username"], "viewer")
