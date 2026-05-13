from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from apps.agents.models import GpuDevice, GpuSlice
from apps.agents.services.gpu_inventory import apply_gpu_inventory

from .factories import create_agent, create_user


def rtx_4090_payload():
    return {
        "success": True,
        "data": {
            "gpus": [
                {
                    "index": 0,
                    "vendor": "NVIDIA",
                    "name": "NVIDIA GeForce RTX 4090",
                    "uuid": "GPU-4090",
                    "pciBusId": "00000000:82:00.0",
                    "totalMemoryMb": 24564,
                    "driverVersion": "550.54.15",
                    "cudaVersion": "12.4",
                    "migCapable": False,
                    "migEnabled": False,
                    "slices": [
                        {
                            "kind": "full",
                            "deviceId": "GPU-4090",
                            "memoryMb": 24564,
                        }
                    ],
                }
            ]
        },
    }


class GpuInventoryServiceTest(TestCase):
    def setUp(self):
        self.agent = create_agent(hostname="gpu-host")

    def test_apply_gpu_inventory_upserts_device_and_slice(self):
        result = apply_gpu_inventory(self.agent, rtx_4090_payload())

        self.assertTrue(result["ok"])
        self.assertEqual(result["devices"], 1)
        self.assertEqual(result["slices"], 1)

        gpu = GpuDevice.objects.get(agent=self.agent, index=0)
        self.assertEqual(gpu.name, "NVIDIA GeForce RTX 4090")
        self.assertEqual(gpu.uuid, "GPU-4090")
        self.assertEqual(gpu.total_memory_mb, 24564)
        self.assertEqual(gpu.status, GpuDevice.HardwareStatus.AVAILABLE)

        slice_obj = GpuSlice.objects.get(gpu=gpu)
        self.assertEqual(slice_obj.kind, GpuSlice.Kind.FULL)
        self.assertEqual(slice_obj.device_id, "GPU-4090")
        self.assertEqual(slice_obj.memory_mb, 24564)
        self.assertFalse(slice_obj.allow_shared)

    def test_apply_gpu_inventory_marks_stale_inventory_offline(self):
        apply_gpu_inventory(self.agent, rtx_4090_payload())

        result = apply_gpu_inventory(self.agent, {"success": True, "data": {"gpus": []}})

        self.assertTrue(result["ok"])
        self.assertEqual(result["devices"], 0)
        self.assertEqual(result["stale_devices"], 1)
        self.assertEqual(result["stale_slices"], 1)
        self.assertEqual(
            GpuDevice.objects.get(agent=self.agent).status,
            GpuDevice.HardwareStatus.OFFLINE,
        )
        self.assertEqual(
            GpuSlice.objects.get(gpu__agent=self.agent).status,
            GpuSlice.HardwareStatus.OFFLINE,
        )

    def test_failed_inventory_response_marks_existing_inventory_offline(self):
        apply_gpu_inventory(self.agent, rtx_4090_payload())

        result = apply_gpu_inventory(
            self.agent,
            {"success": False, "error": "nvidia-smi not available"},
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "offline")
        self.assertIn("nvidia-smi", result["reason"])
        self.assertEqual(
            GpuDevice.objects.get(agent=self.agent).status,
            GpuDevice.HardwareStatus.OFFLINE,
        )
        self.assertEqual(
            GpuSlice.objects.get(gpu__agent=self.agent).status,
            GpuSlice.HardwareStatus.OFFLINE,
        )


class GpuInventoryAPITest(APITestCase):
    def setUp(self):
        self.admin = create_user(role="admin", username="gpu-admin")
        self.agent = create_agent(hostname="api-gpu-host")
        apply_gpu_inventory(self.agent, rtx_4090_payload())

    def test_agent_gpus_endpoint_returns_nested_inventory(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(f"/api/agents/{self.agent.id}/gpus/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()["data"]
        self.assertEqual(body["agent"], str(self.agent.id))
        self.assertEqual(body["devices"][0]["uuid"], "GPU-4090")
        self.assertEqual(body["devices"][0]["slices"][0]["device_id"], "GPU-4090")
