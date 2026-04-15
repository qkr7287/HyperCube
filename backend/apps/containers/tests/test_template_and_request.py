from rest_framework import status
from rest_framework.test import APITestCase

from apps.containers.models import ContainerRequest, ContainerTemplate

from .factories import (
    create_agent,
    create_container,
    create_request,
    create_template,
    create_user,
)


class ContainerTemplateAPITest(APITestCase):
    def setUp(self):
        self.admin = create_user(role="admin", username="admin")
        self.user = create_user(role="user", username="user1")
        self.template = create_template(
            created_by=self.admin, name="Postgres 15", image="postgres:15"
        )

    # ---- 조회 권한 ----
    def test_list_requires_auth(self):
        res = self.client.get("/api/templates/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_list_templates(self):
        self.client.force_authenticate(user=self.user)
        res = self.client.get("/api/templates/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.json()["data"]["count"], 1)

    def test_admin_can_list_templates(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.get("/api/templates/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    # ---- 쓰기 권한 ----
    def test_user_cannot_create_template(self):
        self.client.force_authenticate(user=self.user)
        res = self.client.post(
            "/api/templates/",
            {"name": "T1", "kind": "simple", "image": "redis:7"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_create_simple_template(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.post(
            "/api/templates/",
            {"name": "Redis", "kind": "simple", "image": "redis:7"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.json())
        self.assertEqual(res.json()["data"]["created_by_username"], "admin")

    def test_admin_can_create_compose_template(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.post(
            "/api/templates/",
            {
                "name": "Stack",
                "kind": "compose",
                "compose_yaml": "services:\n  web:\n    image: nginx\n",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.json())

    def test_simple_template_requires_image_or_image_options(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.post(
            "/api/templates/",
            {"name": "Empty", "kind": "simple"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_compose_template_requires_yaml(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.post(
            "/api/templates/",
            {"name": "EmptyCompose", "kind": "compose"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class ContainerRequestAPITest(APITestCase):
    def setUp(self):
        self.admin = create_user(role="admin", username="admin")
        self.user = create_user(role="user", username="user1")
        self.other_user = create_user(role="user", username="user2")
        self.agent = create_agent(hostname="server-a", ip_address="10.0.0.1")
        self.template = create_template(
            created_by=self.admin, name="Nginx", image="nginx:1.27"
        )

    def _create_payload(self, **overrides):
        payload = {
            "action": "create",
            "template": str(self.template.id),
            "target_agent": str(self.agent.id),
            "custom_name": "my-nginx",
            "custom_env": {"KEY": "value"},
        }
        payload.update(overrides)
        return payload

    # ---- 제출 ----
    def test_user_can_submit_create_request(self):
        self.client.force_authenticate(user=self.user)
        res = self.client.post("/api/requests/", self._create_payload(), format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.json())
        data = res.json()["data"]
        self.assertEqual(data["status"], "pending")
        self.assertEqual(data["requester_username"], "user1")

    def test_create_request_needs_template_and_target(self):
        self.client.force_authenticate(user=self.user)
        res = self.client.post(
            "/api/requests/",
            {"action": "create", "custom_name": "x"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_request_needs_target_container(self):
        self.client.force_authenticate(user=self.user)
        res = self.client.post(
            "/api/requests/",
            {"action": "delete"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_can_submit_delete_request(self):
        container = create_container(
            agent=self.agent,
            container_id="abc0001abc00",
            name="target",
            requester=self.user,
        )
        self.client.force_authenticate(user=self.user)
        res = self.client.post(
            "/api/requests/",
            {"action": "delete", "target_container": container.container_id},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.json())

    # ---- 조회 격리 ----
    def test_user_sees_only_own_requests(self):
        create_request(
            requester=self.user, template=self.template, target_agent=self.agent
        )
        create_request(
            requester=self.other_user, template=self.template, target_agent=self.agent
        )
        self.client.force_authenticate(user=self.user)
        res = self.client.get("/api/requests/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.json()["data"]["count"], 1)
        self.assertEqual(
            res.json()["data"]["results"][0]["requester_username"], "user1"
        )

    def test_admin_sees_all_requests(self):
        create_request(
            requester=self.user, template=self.template, target_agent=self.agent
        )
        create_request(
            requester=self.other_user, template=self.template, target_agent=self.agent
        )
        self.client.force_authenticate(user=self.admin)
        res = self.client.get("/api/requests/")
        self.assertEqual(res.json()["data"]["count"], 2)

    # ---- 승인/반려 ----
    def test_user_cannot_approve(self):
        r = create_request(
            requester=self.user, template=self.template, target_agent=self.agent
        )
        self.client.force_authenticate(user=self.user)
        res = self.client.post(f"/api/requests/{r.id}/approve/", {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_approves_pending(self):
        r = create_request(
            requester=self.user, template=self.template, target_agent=self.agent
        )
        self.client.force_authenticate(user=self.admin)
        res = self.client.post(
            f"/api/requests/{r.id}/approve/",
            {"note": "ok"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.json())
        r.refresh_from_db()
        self.assertEqual(r.status, ContainerRequest.Status.APPROVED)
        self.assertEqual(r.reviewer_id, self.admin.id)
        self.assertEqual(r.review_note, "ok")

    def test_admin_rejects_pending(self):
        r = create_request(
            requester=self.user, template=self.template, target_agent=self.agent
        )
        self.client.force_authenticate(user=self.admin)
        res = self.client.post(
            f"/api/requests/{r.id}/reject/",
            {"note": "no capacity"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        r.refresh_from_db()
        self.assertEqual(r.status, ContainerRequest.Status.REJECTED)

    def test_cannot_approve_already_approved(self):
        r = create_request(
            requester=self.user,
            template=self.template,
            target_agent=self.agent,
            status=ContainerRequest.Status.APPROVED,
        )
        self.client.force_authenticate(user=self.admin)
        res = self.client.post(f"/api/requests/{r.id}/approve/", {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # ---- 취소 ----
    def test_user_can_delete_own_pending(self):
        r = create_request(
            requester=self.user, template=self.template, target_agent=self.agent
        )
        self.client.force_authenticate(user=self.user)
        res = self.client.delete(f"/api/requests/{r.id}/")
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

    def test_cannot_delete_deploying(self):
        r = create_request(
            requester=self.user,
            template=self.template,
            target_agent=self.agent,
            status=ContainerRequest.Status.DEPLOYING,
        )
        self.client.force_authenticate(user=self.user)
        res = self.client.delete(f"/api/requests/{r.id}/")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
