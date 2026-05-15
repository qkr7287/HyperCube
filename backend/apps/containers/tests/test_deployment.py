from django.test import TestCase

from apps.containers.services.deployment import build_agent_payload

from .factories import create_agent, create_request, create_template, create_user


class AgentCreatePayloadTests(TestCase):
    def setUp(self):
        self.admin = create_user(role="admin", username="payload-admin")
        self.user = create_user(role="user", username="payload-user")

    def test_create_payload_includes_host_config_lvm_workspace_and_shared_mounts(self):
        agent = create_agent(
            hostname="payload-agent",
            cpu_cores=24,
            ram_total_mb=262144,
            lvm_pool_size_gb=3000,
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
            "sizeGb": 100,
            "mountTarget": "/workspace",
        })
        self.assertEqual(params["sharedMounts"], [
            {"source": "/mnt/datasets", "target": "/datasets", "readOnly": True},
            {"source": "/mnt/models", "target": "/models", "readOnly": True},
        ])

    def test_lvm_workspace_is_omitted_when_agent_has_no_lvm_capacity(self):
        agent = create_agent(hostname="payload-legacy-agent", lvm_pool_size_gb=None)
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
