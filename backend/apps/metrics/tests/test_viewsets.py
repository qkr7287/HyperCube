from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.metrics.models import ContainerMetricsHistory
from apps.containers.tests.factories import create_agent, create_container, create_user


class ContainerMetricsViewSetTest(APITestCase):
    def setUp(self):
        self.user = create_user(role="user", username="owner")
        self.other_user = create_user(role="user", username="other")
        self.admin = create_user(role="admin", username="admin")
        self.agent = create_agent(hostname="metrics-agent")

        self.owned_container = create_container(
            agent=self.agent,
            container_id="owned12345678",
            requester=self.user,
        )
        self.other_container = create_container(
            agent=self.agent,
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
        response = self.client.get(f"/api/metrics/containers/?agent={self.agent.id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()["data"]
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["container_id"], self.owned_container.container_id)

    def test_admin_sees_all_container_metrics(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(f"/api/metrics/containers/?agent={self.agent.id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()["data"]
        self.assertEqual(len(payload), 2)


class ContainerBucketsContractTest(APITestCase):
    """`/api/metrics/containers/buckets/` 응답 필드 단위 회귀 보호.

    Frontend `+page.svelte` 가 history rows 를 만들 때 `r.cpu_max` 를 그대로
    cpu_usage_max 슬롯에 박아 KPI 카드 "피크" 가 그 값을 렌더. backend 가
    `cpu_max` 를 0-100 % 가 아니라 cores 단위(예: 0-N)로 돌리면 화면에
    "피크 N%" 같이 잘못된 % 로 보이게 됨. 이 contract 가 깨지지 않게 잠금.
    """

    def setUp(self):
        self.user = create_user(role="user", username="bucket-owner")
        self.agent = create_agent(hostname="bucket-agent")
        self.container = create_container(
            agent=self.agent, container_id="bktcontainer", requester=self.user
        )
        now = timezone.now()
        # 동일 1m bucket 으로 떨어지는 3 sample. cpu_usage 는 0-100 % 라 가정.
        for pct in (10.0, 20.0, 80.0):
            ContainerMetricsHistory.objects.create(
                agent=self.agent,
                container_id=self.container.container_id,
                cpu_usage=pct,
                memory_usage=1024,
                memory_limit=4096,
                memory_percent=25.0,
                network_rx=0,
                network_tx=0,
                disk_read=0,
                disk_write=0,
                raw_data={"containerId": self.container.container_id},
                recorded_at=now,
            )

    def _fetch_bucket(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            f"/api/metrics/containers/buckets/?bucket=1m&container_id={self.container.container_id}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # common renderer 가 {success, data} 로 감싸므로 data 안을 본다
        payload = response.json()["data"]
        self.assertEqual(payload["bucket_seconds"], 60)
        self.assertEqual(len(payload["results"]), 1)
        return payload["results"][0]

    def test_cpu_max_is_percent_not_cores(self):
        row = self._fetch_bucket()
        # peak of (10, 20, 80) is 80%, average is ~36.67%
        self.assertAlmostEqual(row["cpu_max"], 80.0, places=2)
        self.assertAlmostEqual(row["cpu_usage_pct_max"], 80.0, places=2)
        self.assertLessEqual(row["cpu_max"], 100.0, msg="cpu_max must be 0-100 %, not cores")
        self.assertGreaterEqual(row["cpu_max"], 0.0)

    def test_cpu_avg_matches_arithmetic_mean(self):
        row = self._fetch_bucket()
        # arithmetic mean of (10, 20, 80) = 36.666... → rounded(2) = 36.67
        self.assertAlmostEqual(row["cpu_avg"], 36.67, places=2)
        self.assertAlmostEqual(row["cpu_usage_pct_avg"], 36.67, places=2)

    def test_backwards_compat_cpu_avg_max_mirrors_pct_fields(self):
        # `cpu_avg` / `cpu_max` 는 frontend 호환용 alias 로 cpu_usage_pct_* 와 동일
        row = self._fetch_bucket()
        self.assertEqual(row["cpu_avg"], row["cpu_usage_pct_avg"])
        self.assertEqual(row["cpu_max"], row["cpu_usage_pct_max"])

    def test_memory_percent_avg_returned(self):
        row = self._fetch_bucket()
        # 3 sample 모두 25.0 — avg 25, max 도 25 여야 함
        self.assertAlmostEqual(row["memory_percent_avg"], 25.0, places=2)
