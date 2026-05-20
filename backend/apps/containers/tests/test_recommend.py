from django.test import TestCase

from apps.containers.services.recommend import (
    max_limit_errors,
    min_limit_errors,
    recommend_resource_limits,
)

from .factories import create_agent, create_template, create_user


class ResourceRecommendationTests(TestCase):
    def setUp(self):
        self.admin = create_user(role="admin", username="recommend-admin")

    def test_recommends_from_agent_capacity_and_template_weights(self):
        agent = create_agent(
            cpu_cores=24,
            ram_total_mb=262144,
            workspace_pool_total_gb=3000,
            target_users=4,
            safety_margin=0.8,
        )
        template = create_template(
            created_by=self.admin,
            name="PyTorch Jupyter",
            cpu_weight=1.0,
            ram_weight=1.0,
            disk_weight=1.0,
        )

        result = recommend_resource_limits(agent, template)

        self.assertEqual(result.cpu_percent, 500)
        self.assertEqual(result.memory_mb, 51 * 1024)
        self.assertEqual(result.workspace_gb, 600)
        self.assertTrue(result.capacity_complete)

    def test_recommendation_applies_template_hard_floors(self):
        agent = create_agent(
            cpu_cores=1,
            ram_total_mb=1024,
            workspace_pool_total_gb=5,
            target_users=8,
            safety_margin=0.8,
        )
        template = create_template(
            created_by=self.admin,
            name="Floor Template",
            min_cpu_percent=200,
            min_memory_mb=4096,
            min_workspace_gb=20,
        )

        result = recommend_resource_limits(agent, template)

        self.assertEqual(result.cpu_percent, 200)
        self.assertEqual(result.memory_mb, 4096)
        self.assertEqual(result.workspace_gb, 20)

    def test_min_limit_errors_reports_values_below_hard_floor(self):
        template = create_template(
            created_by=self.admin,
            name="Strict Template",
            min_cpu_percent=200,
            min_memory_mb=4096,
            min_workspace_gb=20,
        )

        errors = min_limit_errors(
            template,
            cpu_percent=100,
            memory_mb=2048,
            workspace_gb=10,
        )

        self.assertEqual(set(errors), {"cpu_percent", "memory_mb", "workspace_gb"})

    def test_max_limit_errors_reports_values_above_host_capacity(self):
        agent = create_agent(
            cpu_cores=4,
            ram_total_mb=16384,
            workspace_pool_total_gb=100,
        )
        template = create_template(created_by=self.admin, name="Max Template")

        errors = max_limit_errors(
            template,
            agent,
            cpu_percent=500,        # > 4 cores * 100 = 400
            memory_mb=16000,        # > 16384 - 4096 = 12288
            workspace_gb=200,       # > pool 100
        )

        self.assertEqual(set(errors), {"cpu_percent", "memory_mb", "workspace_gb"})

    def test_max_limit_errors_passes_within_capacity(self):
        agent = create_agent(
            cpu_cores=8,
            ram_total_mb=32768,
            workspace_pool_total_gb=500,
        )
        template = create_template(created_by=self.admin, name="Fit Template")

        errors = max_limit_errors(
            template,
            agent,
            cpu_percent=400,
            memory_mb=8192,
            workspace_gb=100,
        )

        self.assertEqual(errors, {})

    def test_max_limit_errors_skips_disk_when_no_quota_pool(self):
        # quota pool 미보고 호스트는 디스크 상한 검사를 건너뛴다.
        agent = create_agent(cpu_cores=4, ram_total_mb=16384, workspace_pool_total_gb=None)
        template = create_template(created_by=self.admin, name="No Pool Template")

        errors = max_limit_errors(template, agent, workspace_gb=99999)

        self.assertNotIn("workspace_gb", errors)
