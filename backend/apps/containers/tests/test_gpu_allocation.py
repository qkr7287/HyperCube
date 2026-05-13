from datetime import timedelta
from unittest.mock import patch

from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.agents.models import GpuDevice, GpuSlice
from apps.containers.models import (
    ContainerRequest,
    ContainerRequestGpuSlice,
    GpuAllocation,
)
from apps.containers.services.gpu_allocation import (
    activate_gpu_allocations_for_request,
    cleanup_expired_gpu_reservations,
    fail_reserved_gpu_allocations_for_request,
)

from .factories import (
    create_agent,
    create_container,
    create_request,
    create_template,
    create_user,
)


class DummyLayer:
    def __init__(self):
        self.messages = []

    async def send(self, channel, message):
        self.messages.append((channel, message))


def create_gpu_slice(agent, device_id="GPU-test"):
    gpu = GpuDevice.objects.create(
        agent=agent,
        index=0,
        vendor="NVIDIA",
        name="NVIDIA Test GPU",
        uuid=device_id,
        total_memory_mb=24564,
        status=GpuDevice.HardwareStatus.AVAILABLE,
    )
    return GpuSlice.objects.create(
        gpu=gpu,
        kind=GpuSlice.Kind.FULL,
        device_id=device_id,
        label="NVIDIA Test GPU full GPU",
        memory_mb=24564,
        status=GpuSlice.HardwareStatus.AVAILABLE,
    )


class GpuAllocationRequestAPITest(APITestCase):
    def setUp(self):
        self.admin = create_user(role="admin", username="gpu-admin")
        self.user = create_user(role="user", username="gpu-user")
        self.agent = create_agent(hostname="gpu-agent")
        self.template = create_template(created_by=self.admin)
        self.slice = create_gpu_slice(self.agent)

    def test_request_create_writes_gpu_slice_selection_rows(self):
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

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.json())
        request_id = response.json()["data"]["id"]
        req = ContainerRequest.objects.get(id=request_id)
        self.assertEqual(req.gpu_slice_ids_snapshot, [self.slice.id])
        self.assertEqual(
            list(req.gpu_slice_selections.values_list("slice_id", flat=True)),
            [self.slice.id],
        )

    def test_request_rejects_gpu_slice_from_different_agent(self):
        other_agent = create_agent(hostname="other-gpu-agent")
        other_slice = create_gpu_slice(other_agent, device_id="GPU-other")
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/requests/",
            {
                "action": "create",
                "template": str(self.template.id),
                "target_agent": str(self.agent.id),
                "gpu_slice_ids": [other_slice.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_approve_reserves_gpu_and_dispatches_create_payload(self):
        req = create_request(
            requester=self.user,
            template=self.template,
            target_agent=self.agent,
        )
        ContainerRequestGpuSlice.objects.create(request=req, slice=self.slice)
        dummy_layer = DummyLayer()
        self.client.force_authenticate(user=self.admin)

        with (
            patch("apps.containers.services.deployment.command_router.get_agent_channel", return_value="agent-channel"),
            patch("apps.containers.services.deployment.command_router.record_pending"),
            patch("apps.containers.services.deployment.get_channel_layer", return_value=dummy_layer),
        ):
            response = self.client.post(f"/api/requests/{req.id}/approve/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.json())
        allocation = GpuAllocation.objects.get(container_request=req)
        self.assertEqual(allocation.status, GpuAllocation.Status.RESERVED)
        self.assertIsNotNone(allocation.reserved_until)
        self.assertEqual(len(dummy_layer.messages), 1)
        payload = dummy_layer.messages[0][1]["payload"]
        self.assertEqual(payload["command"], "create_container")
        self.assertEqual(
            payload["params"]["gpus"],
            [{"deviceId": self.slice.device_id, "kind": GpuSlice.Kind.FULL}],
        )

    def test_second_exclusive_approval_for_same_slice_is_rejected(self):
        first = create_request(
            requester=self.user,
            template=self.template,
            target_agent=self.agent,
            custom_name="first",
        )
        second = create_request(
            requester=self.user,
            template=self.template,
            target_agent=self.agent,
            custom_name="second",
        )
        ContainerRequestGpuSlice.objects.create(request=first, slice=self.slice)
        ContainerRequestGpuSlice.objects.create(request=second, slice=self.slice)
        dummy_layer = DummyLayer()
        self.client.force_authenticate(user=self.admin)

        with (
            patch("apps.containers.services.deployment.command_router.get_agent_channel", return_value="agent-channel"),
            patch("apps.containers.services.deployment.command_router.record_pending"),
            patch("apps.containers.services.deployment.get_channel_layer", return_value=dummy_layer),
        ):
            first_response = self.client.post(f"/api/requests/{first.id}/approve/", {}, format="json")
            second_response = self.client.post(f"/api/requests/{second.id}/approve/", {}, format="json")

        self.assertEqual(first_response.status_code, status.HTTP_200_OK, first_response.json())
        self.assertEqual(second_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            GpuAllocation.objects.filter(slice=self.slice, status=GpuAllocation.Status.RESERVED).count(),
            1,
        )

    @override_settings(HC_GPU_SHARED_MODE_ENABLED=True)
    def test_shared_approval_allows_same_shareable_slice(self):
        self.slice.allow_shared = True
        self.slice.save(update_fields=["allow_shared"])
        other_user = create_user(role="user", username="gpu-user-2")
        first = create_request(
            requester=self.user,
            template=self.template,
            target_agent=self.agent,
            custom_name="shared-first",
            gpu_share_ok=True,
        )
        second = create_request(
            requester=other_user,
            template=self.template,
            target_agent=self.agent,
            custom_name="shared-second",
            gpu_share_ok=True,
        )
        ContainerRequestGpuSlice.objects.create(request=first, slice=self.slice)
        ContainerRequestGpuSlice.objects.create(request=second, slice=self.slice)
        dummy_layer = DummyLayer()
        self.client.force_authenticate(user=self.admin)

        with (
            patch("apps.containers.services.deployment.command_router.get_agent_channel", return_value="agent-channel"),
            patch("apps.containers.services.deployment.command_router.record_pending"),
            patch("apps.containers.services.deployment.get_channel_layer", return_value=dummy_layer),
        ):
            first_response = self.client.post(f"/api/requests/{first.id}/approve/", {}, format="json")
            second_response = self.client.post(f"/api/requests/{second.id}/approve/", {}, format="json")

        self.assertEqual(first_response.status_code, status.HTTP_200_OK, first_response.json())
        self.assertEqual(second_response.status_code, status.HTTP_200_OK, second_response.json())
        modes = list(
            GpuAllocation.objects.filter(slice=self.slice)
            .order_by("id")
            .values_list("share_mode", flat=True)
        )
        self.assertEqual(modes, [GpuAllocation.ShareMode.SHARED, GpuAllocation.ShareMode.SHARED])

    def test_allocation_lifecycle_helpers_activate_fail_and_cleanup(self):
        req = create_request(
            requester=self.user,
            template=self.template,
            target_agent=self.agent,
            status=ContainerRequest.Status.APPROVED,
        )
        allocation = GpuAllocation.objects.create(
            slice=self.slice,
            container_request=req,
            reserved_until=timezone.now() + timedelta(minutes=10),
        )
        container = create_container(
            agent=self.agent,
            requester=self.user,
            created_via_request=req,
            container_id="gpuabc123456",
        )

        activate_gpu_allocations_for_request(req, container)
        allocation.refresh_from_db()
        container.refresh_from_db()
        self.assertEqual(allocation.status, GpuAllocation.Status.ACTIVE)
        self.assertEqual(allocation.container, container)
        self.assertEqual(container.allocated_gpu_slice_ids, [self.slice.id])

        fail_reserved_gpu_allocations_for_request(req, "no-op")
        allocation.refresh_from_db()
        self.assertEqual(allocation.status, GpuAllocation.Status.ACTIVE)

        stale_req = create_request(
            requester=self.user,
            template=self.template,
            target_agent=self.agent,
            status=ContainerRequest.Status.APPROVED,
            custom_name="stale",
        )
        stale_allocation = GpuAllocation.objects.create(
            slice=self.slice,
            container_request=stale_req,
            reserved_until=timezone.now() - timedelta(minutes=1),
        )

        count = cleanup_expired_gpu_reservations()

        self.assertEqual(count, 1)
        stale_allocation.refresh_from_db()
        stale_req.refresh_from_db()
        self.assertEqual(stale_allocation.status, GpuAllocation.Status.FAILED)
        self.assertEqual(stale_req.status, ContainerRequest.Status.FAILED)
