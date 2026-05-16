from django.test import TestCase

from apps.containers.models import ContainerTemplate
from apps.containers.services.deployment import build_agent_payload

from .factories import create_agent, create_request, create_template, create_user


class AgentCreatePayloadTests(TestCase):
    def setUp(self):
        self.admin = create_user(role="admin", username="payload-admin")
        self.user = create_user(role="user", username="payload-user")

    def test_create_payload_includes_host_config_workspace_quota_and_shared_mounts(self):
        agent = create_agent(
            hostname="payload-agent",
            cpu_cores=24,
            ram_total_mb=262144,
            workspace_pool_total_gb=3000,
            workspace_hard_enforcement=True,
        )
        template = create_template(created_by=self.admin, default_workdir="/home/jovyan")
        request = create_request(
            requester=self.user,
            template=template,
            target_agent=agent,
            cpu_percent=400,
            memory_mb=16384,
            workspace_gb=100,
        )

        payload = build_agent_payload(request)
        params = payload["params"]

        self.assertEqual(payload["command"], "create_container")
        self.assertEqual(params["hostConfig"], {
            "memory": 16384 * 1024 * 1024,
            "memorySwap": 16384 * 1024 * 1024,
            "cpuQuota": 400000,
            "cpuPeriod": 100000,
            "oomKillDisable": False,
        })
        self.assertEqual(params["workspace"], {
            "hardGb": 100,
            "mountTarget": "/workspace",
        })
        self.assertEqual(params["sharedMounts"], [
            {"source": "/mnt/datasets", "target": "/datasets", "readOnly": True},
            {"source": "/mnt/models", "target": "/models", "readOnly": True},
        ])

    def test_workspace_quota_is_omitted_when_agent_has_no_quota_pool(self):
        agent = create_agent(hostname="payload-legacy-agent", workspace_pool_total_gb=None)
        template = create_template(created_by=self.admin)
        request = create_request(
            requester=self.user,
            template=template,
            target_agent=agent,
            cpu_percent=200,
            memory_mb=4096,
            workspace_gb=50,
        )

        params = build_agent_payload(request)["params"]

        self.assertIn("hostConfig", params)
        self.assertNotIn("workspace", params)
        self.assertNotIn("sharedMounts", params)

    def test_workspace_metadata_is_preserved_without_quota_workspace_payload(self):
        agent = create_agent(hostname="payload-workspace-legacy-agent", workspace_pool_total_gb=None)
        template = create_template(
            created_by=self.admin,
            workspace_enabled=True,
            workspace_kind=ContainerTemplate.WorkspaceKind.JUPYTER,
            workspace_port=8888,
            default_workdir="/home/jovyan",
        )
        request = create_request(
            requester=self.user,
            template=template,
            target_agent=agent,
            cpu_percent=200,
            memory_mb=4096,
            workspace_gb=50,
            workspace_enabled_snapshot=True,
            workspace_kind_snapshot=ContainerTemplate.WorkspaceKind.JUPYTER,
        )

        params = build_agent_payload(request)["params"]

        self.assertIn("hostConfig", params)
        self.assertEqual(params["workspace"]["kind"], "jupyter")
        self.assertEqual(params["workspace"]["port"], 8888)
        self.assertEqual(params["workspace"]["workdir"], "/home/jovyan")
        self.assertNotIn("hardGb", params["workspace"])
        self.assertNotIn("mountTarget", params["workspace"])
        self.assertNotIn("sharedMounts", params)
