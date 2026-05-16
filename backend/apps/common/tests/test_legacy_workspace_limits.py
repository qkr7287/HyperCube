from asgiref.sync import async_to_sync
from django.test import TransactionTestCase

from apps.common.consumers import MonitoringConsumer
from apps.containers.models import Container
from apps.containers.tests.factories import create_agent, create_request, create_template, create_user


class LegacyWorkspaceLimitConsumerTests(TransactionTestCase):
    def test_create_response_without_lvm_does_not_persist_unenforced_workspace_limit(self):
        admin = create_user(role="admin", username="legacy-workspace-admin-standalone")
        user = create_user(role="user", username="legacy-workspace-user-standalone")
        agent = create_agent(
            hostname="legacy-workspace-agent-standalone",
            ip_address="10.0.0.62",
            workspace_pool_total_gb=None,
        )
        template = create_template(created_by=admin, name="Legacy Workspace Standalone Template")
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
