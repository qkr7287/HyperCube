from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.agents.models import GpuDevice, GpuSlice
from apps.containers.models import ContainerRequest, ContainerRequestGpuSlice, ContainerTemplate, GpuAllocation

from .factories import create_agent, create_container, create_request, create_template, create_user


def create_gpu_slice(agent, device_id="GPU-policy", index=None):
    if index is None:
        index = GpuDevice.objects.filter(agent=agent).count()
    gpu = GpuDevice.objects.create(
        agent=agent,
        index=index,
        vendor="NVIDIA",
        name="NVIDIA Policy GPU",
        uuid=device_id,
        total_memory_mb=24564,
        status=GpuDevice.HardwareStatus.AVAILABLE,
    )
    return GpuSlice.objects.create(
        gpu=gpu,
        kind=GpuSlice.Kind.FULL,
        device_id=device_id,
        label="NVIDIA Policy GPU full GPU",
        memory_mb=24564,
        status=GpuSlice.HardwareStatus.AVAILABLE,
    )


class WorkspacePolicyAPITest(APITestCase):
    def setUp(self):
        self.admin = create_user(role="admin", username="policy-admin")
        self.user = create_user(role="user", username="policy-user")
        self.agent = create_agent(hostname="policy-agent")
        self.template = create_template(
            created_by=self.admin,
            name="Policy Jupyter",
            image="hypercube/ml-pytorch-jupyter:cuda12.4-airgap",
            category=ContainerTemplate.Category.ML,
            requires_gpu=True,
            workspace_enabled=True,
            workspace_kind=ContainerTemplate.WorkspaceKind.JUPYTER,
            workspace_port=8888,
            default_max_runtime_hours=24,
        )
        self.slice = create_gpu_slice(self.agent)

    def test_shared_gpu_request_is_rejected_when_shared_mode_disabled(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/requests/",
            {
                "action": "create",
                "template": str(self.template.id),
                "target_agent": str(self.agent.id),
                "gpu_slice_ids": [self.slice.id],
                "gpu_share_ok": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(HC_MAX_WORKSPACE_RUNTIME_HOURS=12)
    def test_runtime_request_cannot_exceed_policy_limit(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/requests/",
            {
                "action": "create",
                "template": str(self.template.id),
                "target_agent": str(self.agent.id),
                "gpu_slice_ids": [self.slice.id],
                "requested_max_runtime_hours": 24,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(HC_MAX_WORKSPACE_RUNTIME_HOURS=12)
    def test_template_default_runtime_cannot_exceed_policy_limit(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/requests/",
            {
                "action": "create",
                "template": str(self.template.id),
                "target_agent": str(self.agent.id),
                "gpu_slice_ids": [self.slice.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(HC_MAX_ACTIVE_WORKSPACES_PER_USER=1)
    def test_approval_rejects_active_workspace_quota_exceeded(self):
        existing_req = create_request(
            requester=self.user,
            template=self.template,
            target_agent=self.agent,
            status=ContainerRequest.Status.DEPLOYED,
            workspace_enabled_snapshot=True,
            workspace_kind_snapshot=ContainerTemplate.WorkspaceKind.JUPYTER,
        )
        create_container(
            agent=self.agent,
            requester=self.user,
            created_via_request=existing_req,
            container_id="quota-ws-01",
            workspace_enabled=True,
            workspace_kind=ContainerTemplate.WorkspaceKind.JUPYTER,
            workspace_host_port=39021,
        )
        req = create_request(
            requester=self.user,
            template=self.template,
            target_agent=self.agent,
            workspace_enabled_snapshot=True,
            workspace_kind_snapshot=ContainerTemplate.WorkspaceKind.JUPYTER,
        )
        ContainerRequestGpuSlice.objects.create(request=req, slice=self.slice)
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(f"/api/requests/{req.id}/approve/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(GpuAllocation.objects.filter(container_request=req).exists())

    @override_settings(HC_MAX_ACTIVE_GPU_SLICES_PER_USER=1)
    def test_approval_rejects_active_gpu_quota_exceeded(self):
        active_req = create_request(
            requester=self.user,
            template=self.template,
            target_agent=self.agent,
            status=ContainerRequest.Status.DEPLOYED,
        )
        GpuAllocation.objects.create(
            slice=self.slice,
            container_request=active_req,
            status=GpuAllocation.Status.ACTIVE,
        )
        other_slice = create_gpu_slice(self.agent, device_id="GPU-policy-2")
        req = create_request(
            requester=self.user,
            template=self.template,
            target_agent=self.agent,
            workspace_enabled_snapshot=True,
            workspace_kind_snapshot=ContainerTemplate.WorkspaceKind.JUPYTER,
        )
        ContainerRequestGpuSlice.objects.create(request=req, slice=other_slice)
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(f"/api/requests/{req.id}/approve/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(GpuAllocation.objects.filter(container_request=req).exists())
