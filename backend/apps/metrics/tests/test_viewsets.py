from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.metrics.models import ContainerMetricsHistory
from apps.containers.tests.factories import create_container, create_user


class ContainerMetricsViewSetTest(APITestCase):
    def setUp(self):
        self.user = create_user(role="user", username="owner")
        self.other_user = create_user(role="user", username="other")
        self.admin = create_user(role="admin", username="admin")

        self.owned_container = create_container(
            container_id="owned12345678",
            requester=self.user,
        )
        self.other_container = create_container(
            container_id="other12345678",
            requester=self.other_user,
            name="other-container",
        )

        ContainerMetricsHistory.objects.create(
            agent=self.owned_container.agent,
            container_id=self.owned_container.container_id,
            cpu_usage=12.5,
            memory_usage=1024,
            memory_limit=2048,
            memory_percent=50.0,
            network_rx=100,
            network_tx=200,
            disk_read=300,
            disk_write=400,
            raw_data={"containerId": self.owned_container.container_id},
            recorded_at=timezone.now(),
        )
        ContainerMetricsHistory.objects.create(
            agent=self.other_container.agent,
            container_id=self.other_container.container_id,
            cpu_usage=22.5,
            memory_usage=512,
            memory_limit=2048,
            memory_percent=25.0,
            network_rx=10,
            network_tx=20,
            disk_read=30,
            disk_write=40,
            raw_data={"containerId": self.other_container.container_id},
            recorded_at=timezone.now(),
        )

    def test_user_only_sees_owned_container_metrics(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/metrics/containers/?page_size=100")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()["data"]
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["container_id"], self.owned_container.container_id)

    def test_admin_sees_all_container_metrics(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get("/api/metrics/containers/?page_size=100")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()["data"]
        self.assertEqual(payload["count"], 2)
