from asgiref.sync import async_to_sync
from django.test import TransactionTestCase

from apps.common.consumers import MonitoringConsumer, _command_response_from_create_result
from apps.containers.models import Container
from apps.containers.tests.factories import create_agent, create_container, create_request, create_template, create_user


class CapacityReportConsumerTests(TransactionTestCase):
    def test_capacity_report_with_workspace_quota_updates_agent_pool(self):
        agent = create_agent(hostname="capacity-host", ip_address="10.0.0.50")
        consumer = MonitoringConsumer()
        consumer.server_id = str(agent.id)

        async_to_sync(consumer._handle_capacity_report)(
            {
                "type": "capacity_report",
                "agentId": str(agent.id),
                "timestamp": "2026-05-16T15:00:00Z",
                "data": {
                    "cpu": {
                        "cores": 24,
                        "model": "Intel Xeon Gold 6248 @ 2.50GHz",
                        "architecture": "x64",
                    },
                    "memory": {"totalMb": 262144},
                    "disk": {
                        "rootTotalGb": 3700,
                        "rootUsedGb": 120,
                        "filesystem": "ext4",
                        "workspaceQuota": {
                            "available": True,
                            "mountPath": "/var/lib/hypercube/workspaces",
                            "totalGb": 2000,
                            "freeGb": 1850,
                            "hardEnforced": True,
                        },
                    },
                    "network": {
                        "primaryInterface": "eth0",
                        "speedMbps": 10000,
                    },
                },
            }
        )

        agent.refresh_from_db()
        self.assertEqual(agent.cpu_cores, 24)
        self.assertEqual(agent.cpu_model, "Intel Xeon Gold 6248 @ 2.50GHz")
        self.assertEqual(agent.ram_total_mb, 262144)
        self.assertEqual(agent.disk_total_gb, 3700)
        self.assertEqual(agent.workspace_pool_total_gb, 2000)
        self.assertEqual(agent.workspace_pool_free_gb, 1850)
        self.assertEqual(agent.workspace_pool_mount, "/var/lib/hypercube/workspaces")
        self.assertTrue(agent.workspace_hard_enforcement)
        self.assertEqual(agent.nic_speed_mbps, 10000)
        self.assertEqual(agent.filesystem, "ext4")
        self.assertIsNotNone(agent.capacity_updated_at)

    def test_capacity_report_falls_back_to_legacy_lvm_payload(self):
        agent = create_agent(hostname="capacity-legacy", ip_address="10.0.0.51")
        consumer = MonitoringConsumer()
        consumer.server_id = str(agent.id)

        async_to_sync(consumer._handle_capacity_report)(
            {
                "type": "capacity_report",
                "data": {
                    "cpu": {"cores": 12},
                    "memory": {"totalMb": 16384},
                    "disk": {
                        "filesystem": "ext4",
                        "lvm": {
                            "available": True,
                            "vg": "vg0",
                            "thinPool": "thin_pool",
                            "thinPoolSizeGb": 3000,
                        },
                    },
                    "network": {"speedMbps": 10000},
                },
            }
        )

        agent.refresh_from_db()
        self.assertEqual(agent.workspace_pool_total_gb, 3000)
        self.assertFalse(agent.workspace_hard_enforcement)

    def test_capacity_report_clears_pool_when_quota_unavailable(self):
        agent = create_agent(
            hostname="capacity-partial",
            ip_address="10.0.0.52",
            workspace_pool_total_gb=3000,
            workspace_pool_free_gb=2500,
            workspace_hard_enforcement=True,
            nic_speed_mbps=10000,
        )
        consumer = MonitoringConsumer()
        consumer.server_id = str(agent.id)

        async_to_sync(consumer._handle_capacity_report)(
            {
                "type": "capacity_report",
                "data": {
                    "cpu": {"cores": None},
                    "memory": {},
                    "disk": {
                        "filesystem": "xfs",
                        "workspaceQuota": {"available": False},
                    },
                    "network": {"speedMbps": None},
                },
            }
        )

        agent.refresh_from_db()
        self.assertIsNone(agent.cpu_cores)
        self.assertEqual(agent.filesystem, "xfs")
        self.assertIsNone(agent.workspace_pool_total_gb)
        self.assertIsNone(agent.workspace_pool_free_gb)
        self.assertEqual(agent.workspace_pool_mount, "")
        self.assertFalse(agent.workspace_hard_enforcement)
        self.assertEqual(agent.nic_speed_mbps, 10000)
        self.assertIsNotNone(agent.capacity_updated_at)

    def test_create_response_copies_request_limits_to_container(self):
        admin = create_user(role="admin", username="capacity-admin")
        user = create_user(role="user", username="capacity-user")
        agent = create_agent(
            hostname="capacity-create",
            ip_address="10.0.0.53",
            workspace_pool_total_gb=2000,
            workspace_hard_enforcement=True,
        )
        template = create_template(created_by=admin, name="Capacity Template")
        request = create_request(
            requester=user,
            template=template,
            target_agent=agent,
            cpu_percent=400,
            memory_mb=16384,
            workspace_gb=100,
        )
        consumer = MonitoringConsumer()
        consumer.server_id = str(agent.id)

        async_to_sync(consumer._update_request_from_response)(
            {
                "type": "command_response",
                "requestId": str(request.id),
                "success": True,
                "data": {
                    "containerId": "abc123def4567890",
                    "name": "limited",
                    "image": "nginx:latest",
                    "state": "running",
                    "workspace": {
                        "path": "/var/lib/hypercube/workspaces/abc123def456",
                        "projectId": 100123,
                        "hardGb": 100,
                    },
                },
            }
        )

        container = Container.objects.get(container_id="abc123def456")
        self.assertEqual(container.cpu_percent_limit, 400)
        self.assertEqual(container.memory_mb_limit, 16384)
        self.assertEqual(container.workspace_gb_limit, 100)
        self.assertEqual(container.workspace_device, "/var/lib/hypercube/workspaces/abc123def456")
        self.assertEqual(container.workspace_project_id, 100123)
        self.assertIsNotNone(container.limit_updated_at)

    def test_create_container_result_alias_updates_request_and_workspace_path(self):
        admin = create_user(role="admin", username="alias-admin")
        user = create_user(role="user", username="alias-user")
        agent = create_agent(
            hostname="alias-create",
            ip_address="10.0.0.54",
            workspace_pool_total_gb=500,
            workspace_hard_enforcement=True,
        )
        template = create_template(created_by=admin, name="Alias Template")
        request = create_request(
            requester=user,
            template=template,
            target_agent=agent,
            cpu_percent=200,
            memory_mb=4096,
            workspace_gb=50,
        )
        consumer = MonitoringConsumer()
        consumer.server_id = str(agent.id)

        response = _command_response_from_create_result(
            {
                "type": "create_container_result",
                "requestId": str(request.id),
                "data": {
                    "ok": True,
                    "containerId": "abcdef1234567890",
                    "name": "alias",
                    "image": "nginx:latest",
                    "workspace": {
                        "path": "/var/lib/hypercube/workspaces/abcdef123456",
                        "projectId": 100456,
                        "hardGb": 50,
                    },
                },
            }
        )
        async_to_sync(consumer._update_request_from_response)(response)

        container = Container.objects.get(container_id="abcdef123456")
        self.assertEqual(container.workspace_device, "/var/lib/hypercube/workspaces/abcdef123456")
        self.assertEqual(container.workspace_project_id, 100456)
        self.assertEqual(container.workspace_gb_limit, 50)

    def test_create_container_result_accepts_legacy_lvm_workspace_fields(self):
        admin = create_user(role="admin", username="legacy-alias-admin")
        user = create_user(role="user", username="legacy-alias-user")
        agent = create_agent(
            hostname="legacy-alias-create",
            ip_address="10.0.0.55",
            workspace_pool_total_gb=500,
        )
        template = create_template(created_by=admin, name="Legacy Alias Template")
        request = create_request(
            requester=user,
            template=template,
            target_agent=agent,
            cpu_percent=200,
            memory_mb=4096,
            workspace_gb=50,
        )
        consumer = MonitoringConsumer()
        consumer.server_id = str(agent.id)

        response = _command_response_from_create_result(
            {
                "type": "create_container_result",
                "requestId": str(request.id),
                "data": {
                    "ok": True,
                    "containerId": "fedcba6543210000",
                    "name": "legacy-alias",
                    "image": "nginx:latest",
                    "workspace": {
                        "device": "/dev/vg0/cid_fedcba654321",
                        "sizeGb": 50,
                    },
                },
            }
        )
        async_to_sync(consumer._update_request_from_response)(response)

        container = Container.objects.get(container_id="fedcba654321")
        # Legacy `device` is accepted into the workspace_device column so a
        # partially-upgraded fleet still populates the field.
        self.assertEqual(container.workspace_device, "/dev/vg0/cid_fedcba654321")
        self.assertEqual(container.workspace_gb_limit, 50)
        self.assertIsNone(container.workspace_project_id)

    def test_create_container_result_without_request_id_updates_existing_container_workspace(self):
        user = create_user(role="user", username="no-request-id-user")
        agent = create_agent(hostname="no-request-id-agent", ip_address="10.0.0.56")
        container = create_container(
            requester=user,
            agent=agent,
            container_id="fedcba654321",
            workspace_gb_limit=None,
        )
        consumer = MonitoringConsumer()
        consumer.server_id = str(agent.id)

        async_to_sync(consumer._update_container_workspace_from_create_result)(
            {
                "type": "create_container_result",
                "data": {
                    "ok": True,
                    "containerId": "fedcba6543219999",
                    "workspace": {
                        "path": "/var/lib/hypercube/workspaces/fedcba654321",
                        "projectId": 200999,
                        "hardGb": 80,
                    },
                },
            }
        )

        container.refresh_from_db()
        self.assertEqual(container.workspace_device, "/var/lib/hypercube/workspaces/fedcba654321")
        self.assertEqual(container.workspace_project_id, 200999)
        self.assertEqual(container.workspace_gb_limit, 80)

    def test_create_response_without_quota_pool_does_not_persist_unenforced_workspace_limit(self):
        admin = create_user(role="admin", username="legacy-workspace-admin")
        user = create_user(role="user", username="legacy-workspace-user")
        agent = create_agent(
            hostname="legacy-workspace-agent",
            ip_address="10.0.0.57",
            workspace_pool_total_gb=None,
        )
        template = create_template(created_by=admin, name="Legacy Workspace Template")
        request = create_request(
            requester=user,
            template=template,
            target_agent=agent,
            cpu_percent=200,
            memory_mb=4096,
            workspace_gb=50,
        )
        consumer = MonitoringConsumer()
        consumer.server_id = str(agent.id)

        async_to_sync(consumer._update_request_from_response)(
            {
                "type": "command_response",
                "requestId": str(request.id),
                "success": True,
                "data": {
                    "containerId": "123456abcdef9999",
                    "name": "legacy-workspace",
                    "image": "nginx:latest",
                    "state": "running",
                },
            }
        )

        container = Container.objects.get(container_id="123456abcdef")
        self.assertEqual(container.cpu_percent_limit, 200)
        self.assertEqual(container.memory_mb_limit, 4096)
        self.assertIsNone(container.workspace_gb_limit)
        self.assertIsNone(container.workspace_device)
        self.assertIsNone(container.workspace_project_id)
