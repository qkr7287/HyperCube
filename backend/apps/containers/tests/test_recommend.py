from django.test import TestCase

from apps.containers.services.recommend import (
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
            lvm_pool_size_gb=3000,
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
            lvm_pool_size_gb=5,
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
