from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.containers.models import ContainerRequest, ContainerTemplate
from apps.containers.services.workspace import (
    consume_workspace_ticket,
    issue_workspace_open_ticket,
    workspace_upstream_endpoint,
)

from .factories import create_agent, create_container, create_request, create_template, create_user


class FakeRedis:
    def __init__(self):
        self.store = {}

    def set(self, key, value, ex=None, nx=False):
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    def get(self, key):
        return self.store.get(key)

    def delete(self, key):
        existed = key in self.store
        self.store.pop(key, None)
        return 1 if existed else 0

    def expire(self, key, seconds):
        return key in self.store


class DummyLayer:
    def __init__(self):
        self.messages = []

    async def send(self, channel, message):
        self.messages.append((channel, message))


class WorkspaceAPITest(APITestCase):
    def setUp(self):
        self.admin = create_user(role="admin", username="ws-admin")
        self.user = create_user(role="user", username="ws-user")
        self.other_user = create_user(role="user", username="ws-other")
        self.agent = create_agent(hostname="ws-agent", ip_address="10.0.0.9")
        self.template = create_template(
            created_by=self.admin,
            name="PyTorch Jupyter",
            image="hypercube/ml-pytorch-jupyter:cuda12.4-airgap",
            category=ContainerTemplate.Category.ML,
            workspace_enabled=True,
            workspace_kind=ContainerTemplate.WorkspaceKind.JUPYTER,
            workspace_port=8888,
            default_max_runtime_hours=24,
        )
        self.request = create_request(
            requester=self.user,
            template=self.template,
            target_agent=self.agent,
            status=ContainerRequest.Status.DEPLOYED,
            workspace_enabled_snapshot=True,
            workspace_kind_snapshot=ContainerTemplate.WorkspaceKind.JUPYTER,
            workspace_token_ref="ws-ref",
            workspace_token_expires_at=timezone.now() + timedelta(hours=24),
        )
        self.container = create_container(
            agent=self.agent,
            requester=self.user,
            created_via_request=self.request,
            container_id="wsabc1234567",
            name="workspace",
            image=self.template.image,
            workspace_enabled=True,
            workspace_kind=ContainerTemplate.WorkspaceKind.JUPYTER,
            workspace_internal_port=8888,
            workspace_host_port=39021,
            workspace_base_url=f"/workspace/{self.request.id}/",
            workspace_token_ref="ws-ref",
            workspace_token_expires_at=timezone.now() + timedelta(hours=24),
        )

    @patch("apps.containers.services.workspace.get_redis_client")
    def test_open_issues_short_lived_ticket_without_plaintext_token(self, mocked_redis):
        mocked_redis.return_value = FakeRedis()
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            f"/api/workspaces/{self.container.container_id}/open/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.json())
        body = response.json()["data"]
        self.assertTrue(body["url"].startswith(f"/workspace/{self.request.id}/lab?ticket="))
        self.assertNotIn("token=", body["url"])
        self.assertEqual(body["expiresInSeconds"], 60)

    def test_open_rejects_non_owner(self):
        self.client.force_authenticate(user=self.other_user)

        response = self.client.post(
            f"/api/workspaces/{self.container.container_id}/open/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("apps.containers.services.workspace.get_redis_client")
    def test_open_allows_internal_policy_without_host_port(self, mocked_redis):
        mocked_redis.return_value = FakeRedis()
        self.container.workspace_host_port = None
        self.container.save(update_fields=["workspace_host_port", "last_seen"])
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            f"/api/workspaces/{self.container.container_id}/open/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.json())

    def test_internal_policy_uses_container_dns_and_internal_port(self):
        self.container.workspace_host_port = None
        endpoint = workspace_upstream_endpoint(self.container)

        self.assertIsNotNone(endpoint)
        self.assertEqual(endpoint.netloc, "workspace:8888")
        self.assertEqual(endpoint.mode, "docker-internal")

    def test_none_policy_uses_agent_host_port(self):
        self.template.network_policy = ContainerTemplate.NetworkPolicy.NONE
        self.template.save(update_fields=["network_policy", "updated_at"])

        endpoint = workspace_upstream_endpoint(self.container)

        self.assertIsNotNone(endpoint)
        self.assertEqual(endpoint.netloc, "10.0.0.9:39021")
        self.assertEqual(endpoint.mode, "agent-host-port")

    @patch("apps.containers.services.workspace.get_redis_client")
    def test_workspace_ticket_is_one_time_use(self, mocked_redis):
        mocked_redis.return_value = FakeRedis()
        ticket = issue_workspace_open_ticket(self.container, self.user)

        first_payload = consume_workspace_ticket(ticket, self.container)
        self.assertEqual(first_payload["cid"], self.container.container_id)
        with self.assertRaises(PermissionDenied):
            consume_workspace_ticket(ticket, self.container)

    @patch("apps.containers.services.deployment.command_router.get_agent_channel", return_value="agent-channel")
    @patch("apps.containers.services.deployment.command_router.record_pending")
    @patch("apps.containers.services.deployment.get_channel_layer")
    @patch("apps.containers.services.workspace.get_redis_client")
    def test_workspace_approval_dispatches_workspace_payload(
        self,
        mocked_redis,
        mocked_layer,
        mocked_record_pending,
        mocked_agent_channel,
    ):
        mocked_redis.return_value = FakeRedis()
        dummy_layer = DummyLayer()
        mocked_layer.return_value = dummy_layer
        req = create_request(
            requester=self.user,
            template=self.template,
            target_agent=self.agent,
            workspace_enabled_snapshot=True,
            workspace_kind_snapshot=ContainerTemplate.WorkspaceKind.JUPYTER,
        )
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(f"/api/requests/{req.id}/approve/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.json())
        payload = dummy_layer.messages[0][1]["payload"]
        workspace = payload["params"]["workspace"]
        self.assertEqual(workspace["kind"], ContainerTemplate.WorkspaceKind.JUPYTER)
        self.assertEqual(workspace["port"], 8888)
        self.assertEqual(workspace["baseUrl"], f"/workspace/{req.id}/")
        self.assertIn("token", workspace)
        self.assertNotIn("token_ref", workspace)
