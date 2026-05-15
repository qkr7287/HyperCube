from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.containers.models import ContainerRequest, ContainerTemplate
from apps.containers.services.workspace import apply_workspace_metadata_from_response

from .factories import create_agent, create_container, create_request, create_template, create_user


class WorkspaceLimitMetadataTests(APITestCase):
    def test_apply_metadata_clears_unreported_workspace_limit(self):
        admin = create_user(role="admin", username="limit-metadata-admin")
        user = create_user(role="user", username="limit-metadata-user")
        agent = create_agent(hostname="limit-metadata-agent", ip_address="10.0.0.61")
        template = create_template(
            created_by=admin,
            name="Limit Metadata Template",
            workspace_enabled=True,
            workspace_kind=ContainerTemplate.WorkspaceKind.JUPYTER,
            workspace_port=8888,
        )
        request = create_request(
            requester=user,
            template=template,
            target_agent=agent,
            status=ContainerRequest.Status.DEPLOYED,
            workspace_enabled_snapshot=True,
            workspace_kind_snapshot=ContainerTemplate.WorkspaceKind.JUPYTER,
            workspace_token_ref="limit-metadata-ref",
            workspace_token_expires_at=timezone.now() + timedelta(hours=24),
        )
        container = create_container(
            agent=agent,
            requester=user,
            created_via_request=request,
            container_id="limmeta12345",
            workspace_enabled=True,
            workspace_gb_limit=50,
            workspace_device="/dev/vg0/cid_limmeta12345",
        )

        apply_workspace_metadata_from_response(request, container, None)

        container.refresh_from_db()
        self.assertIsNone(container.workspace_gb_limit)
        self.assertIsNone(container.workspace_device)
