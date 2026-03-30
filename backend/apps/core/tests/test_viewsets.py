from rest_framework import status
from rest_framework.test import APITestCase

from .factories import create_audit_log, create_template, create_user


class TemplateViewSetTest(APITestCase):
    def setUp(self):
        self.admin = create_user(role="super_admin", username="admin")
        self.viewer = create_user(role="viewer", username="viewer")

    def test_list_templates_as_viewer(self):
        create_template(user=self.admin)
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get("/api/templates/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data["success"])

    def test_create_template_as_viewer_forbidden(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.post(
            "/api/templates/",
            {"name": "New", "category": "web", "config": {}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AuditLogViewSetTest(APITestCase):
    def setUp(self):
        self.admin = create_user(role="super_admin", username="admin")
        self.viewer = create_user(role="viewer", username="viewer")

    def test_list_audit_logs_as_admin(self):
        create_audit_log(user=self.admin)
        self.client.force_authenticate(user=self.admin)
        response = self.client.get("/api/audit-logs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_audit_logs_viewer_forbidden(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get("/api/audit-logs/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
