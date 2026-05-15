from asgiref.sync import async_to_sync
from django.test import TransactionTestCase

from apps.common.consumers import MonitoringConsumer, _command_response_from_create_result
from apps.containers.models import Container
from apps.containers.tests.factories import create_agent, create_container, create_request, create_template, create_user


class CapacityReportConsumerTests(TransactionTestCase):
    def test_capacity_report_updates_agent_capacity_fields(self):
        agent = create_agent(hostname="capacity-host", ip_address="10.0.0.50")
        consumer = MonitoringConsumer()
        consumer.server_id = str(agent.id)

        async_to_sync(consumer._handle_capacity_report)(
            {
                "type": "capacity_report",
                "agentId": str(agent.id),
                "timestamp": "2026-05-15T15:00:00Z",
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
                        "lvm": {
                            "available": True,
                            "vg": "vg0",
                            "thinPool": "thin_pool",
                            "thinPoolSizeGb": 3000,
                            "thinPoolUsedGb": 432,
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
        self.assertEqual(agent.lvm_pool_size_gb, 3000)
        self.assertEqual(agent.nic_speed_mbps, 10000)
        self.assertEqual(agent.filesystem, "ext4")
        self.assertIsNotNone(agent.capacity_updated_at)

    def test_capacity_report_accepts_partial_null_fields(self):
        agent = create_agent(
            hostname="capacity-partial",
            ip_address="10.0.0.51",
            lvm_pool_size_gb=3000,
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
                    "disk": {"filesystem": "xfs", "lvm": {"available": False}},
                    "network": {"speedMbps": None},
                },
            }
        )

        agent.refresh_from_db()
        self.assertIsNone(agent.cpu_cores)
        self.assertEqual(agent.filesystem, "xfs")
        self.assertIsNone(agent.lvm_pool_size_gb)
        self.assertEqual(agent.nic_speed_mbps, 10000)
        self.assertIsNotNone(agent.capacity_updated_at)

    def test_create_response_copies_request_limits_to_container(self):
        admin = create_user(role="admin", username="capacity-admin")
        user = create_user(role="user", username="capacity-user")
        agent = create_agent(hostname="capacity-create", ip_address="10.0.0.52")
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
                        "device": "/dev/vg0/cid_abc123def456",
                        "mountPoint": "/var/lib/hypercube/workspaces/abc123def456",
                        "sizeGb": 100,
                    },
                },
            }
        )

        container = Container.objects.get(container_id="abc123def456")
        self.assertEqual(container.cpu_percent_limit, 400)
        self.assertEqual(container.memory_mb_limit, 16384)
        self.assertEqual(container.workspace_gb_limit, 100)
        self.assertEqual(container.workspace_device, "/dev/vg0/cid_abc123def456")
        self.assertIsNotNone(container.limit_updated_at)

    def test_create_container_result_alias_updates_request_and_workspace_device(self):
        admin = create_user(role="admin", username="alias-admin")
        user = create_user(role="user", username="alias-user")
        agent = create_agent(hostname="alias-create", ip_address="10.0.0.53")
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
                        "device": "/dev/vg0/cid_abcdef123456",
                        "sizeGb": 50,
                    },
                },
            }
        )
        async_to_sync(consumer._update_request_from_response)(response)

        container = Container.objects.get(container_id="abcdef123456")
        self.assertEqual(container.workspace_device, "/dev/vg0/cid_abcdef123456")
        self.assertEqual(container.workspace_gb_limit, 50)

    def test_create_container_result_without_request_id_updates_existing_container_workspace(self):
        user = create_user(role="user", username="no-request-id-user")
        agent = create_agent(hostname="no-request-id-agent", ip_address="10.0.0.54")
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
                        "device": "/dev/vg0/cid_fedcba654321",
                        "sizeGb": 80,
                    },
                },
            }
        )

        container.refresh_from_db()
        self.assertEqual(container.workspace_device, "/dev/vg0/cid_fedcba654321")
        self.assertEqual(container.workspace_gb_limit, 80)
