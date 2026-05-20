from rest_framework import status
from rest_framework.test import APITestCase

from apps.containers.models import Container, ContainerRequest, ContainerTemplate
from apps.containers.services.host_ports import (
    collect_managed_host_ports,
    host_port_in_use,
)
from apps.containers.services.workspace import workspace_payload_for_request

from .factories import create_agent, create_request, create_template, create_user


class HostPortCollectionTest(APITestCase):
    def setUp(self):
        self.user = create_user(role="user", username="hp-user")
        self.agent = create_agent(hostname="hp-agent", ip_address="10.5.5.5")

    def test_running_workspace_container_port_is_collected(self):
        Container.objects.create(
            container_id="run1234567890",
            name="ws-running",
            image="ml:latest",
            agent=self.agent,
            status=Container.Status.RUNNING,
            workspace_host_port=8888,
        )
        ports = [e["port"] for e in collect_managed_host_ports(self.agent)]
        self.assertIn(8888, ports)

    def test_exited_container_port_is_ignored(self):
        Container.objects.create(
            container_id="exit123456789",
            name="ws-exited",
            image="ml:latest",
            agent=self.agent,
            status=Container.Status.EXITED,
            workspace_host_port=8890,
        )
        ports = [e["port"] for e in collect_managed_host_ports(self.agent)]
        self.assertNotIn(8890, ports)

    def test_pending_request_workspace_port_is_collected(self):
        create_request(
            requester=self.user,
            target_agent=self.agent,
            status=ContainerRequest.Status.APPROVED,
            workspace_host_port=8889,
        )
        self.assertTrue(host_port_in_use(self.agent, 8889))

    def test_custom_ports_host_values_are_collected(self):
        create_request(
            requester=self.user,
            target_agent=self.agent,
            status=ContainerRequest.Status.DEPLOYING,
            custom_ports=[{"host": 15432, "container": 5432, "protocol": "tcp"}],
        )
        self.assertTrue(host_port_in_use(self.agent, 15432))

    def test_exclude_request_id_skips_self(self):
        req = create_request(
            requester=self.user,
            target_agent=self.agent,
            status=ContainerRequest.Status.APPROVED,
            workspace_host_port=8891,
        )
        self.assertFalse(
            host_port_in_use(self.agent, 8891, exclude_request_id=req.id)
        )

    def test_used_ports_endpoint_returns_sorted_unique(self):
        Container.objects.create(
            container_id="run9876543210",
            name="ws-a",
            image="ml:latest",
            agent=self.agent,
            status=Container.Status.RUNNING,
            workspace_host_port=9001,
        )
        admin = create_user(role="admin", username="hp-admin")
        self.client.force_authenticate(user=admin)

        response = self.client.get(f"/api/agents/{self.agent.id}/used-ports/")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.json())
        data = response.json()["data"]
        self.assertEqual(data["coverage"], "hypercube-only")
        self.assertIn(9001, [e["port"] for e in data["used_ports"]])


class WorkspacePayloadHostPortTest(APITestCase):
    def setUp(self):
        self.admin = create_user(role="admin", username="wp-admin")
        self.user = create_user(role="user", username="wp-user")
        self.agent = create_agent(hostname="wp-agent", ip_address="10.6.6.6")
        self.template = create_template(
            created_by=self.admin,
            name="WS Template",
            workspace_enabled=True,
            workspace_kind=ContainerTemplate.WorkspaceKind.JUPYTER,
            workspace_port=8888,
        )

    class _Secret:
        token = "tok"

    def _request(self, **kwargs):
        return create_request(
            requester=self.user,
            template=self.template,
            target_agent=self.agent,
            workspace_enabled_snapshot=True,
            workspace_kind_snapshot=ContainerTemplate.WorkspaceKind.JUPYTER,
            **kwargs,
        )

    def test_payload_includes_host_port_when_set(self):
        req = self._request(workspace_host_port=8889)
        payload = workspace_payload_for_request(req, self._Secret())
        self.assertEqual(payload["hostPort"], 8889)

    def test_payload_omits_host_port_when_null(self):
        req = self._request()
        payload = workspace_payload_for_request(req, self._Secret())
        self.assertNotIn("hostPort", payload)
