import os
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.containers.models import ContainerRequest
from apps.containers.tests.factories import create_agent, create_request, create_template, create_user
from apps.models_catalog.models import ModelAsset, ModelPrepareJob, ModelVersionCache
from apps.models_catalog.prepare import (
    cleanup_stale_model_prepare_jobs,
    handle_prepare_response,
    reconcile_agent_prepare_jobs,
)
from apps.models_catalog.services import save_uploaded_model_version


class DummyLayer:
    def __init__(self):
        self.messages = []

    async def send(self, channel, message):
        self.messages.append((channel, message))


class ModelPrepareAPITest(APITestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.storage_dir = os.path.join(self.tempdir.name, "storage")
        self.import_dir = os.path.join(self.tempdir.name, "import")
        Path(self.import_dir).mkdir(parents=True, exist_ok=True)
        self.settings_override = override_settings(
            HC_MODEL_STORAGE_DIR=self.storage_dir,
            HC_MODEL_IMPORT_DIR=self.import_dir,
            MODEL_PREPARE_LEASE_SECONDS=3600,
        )
        self.settings_override.enable()
        self.admin = create_user(role="admin", username="prepare-admin")
        self.user = create_user(role="user", username="prepare-user")
        self.agent = create_agent(
            hostname="prepare-agent",
            ip_address="10.1.1.9",
            token="agent_prepare_token",
        )
        self.template = create_template(
            created_by=self.admin,
            name="Tiny ML Workspace",
            image="hypercube/ml-tiny-jupyter:airgap",
        )
        self.asset = ModelAsset.objects.create(
            owner=self.user,
            name="Tiny Local Model",
            slug="tiny-local-model",
        )
        self.version = save_uploaded_model_version(
            asset=self.asset,
            uploaded_file=SimpleUploadedFile("tiny-model.bin", b"tiny local model bytes"),
            version="v1",
            uploaded_by=self.user,
            metadata={"test": True},
        )

    def tearDown(self):
        self.settings_override.disable()
        self.tempdir.cleanup()

    @patch("apps.models_catalog.prepare.command_router.get_agent_channel", return_value="agent-channel")
    @patch("apps.models_catalog.prepare.command_router.record_pending")
    @patch("apps.models_catalog.prepare.get_channel_layer")
    def test_approval_dispatches_prepare_before_create_for_missing_cache(
        self,
        mocked_layer,
        mocked_record_pending,
        mocked_agent_channel,
    ):
        dummy_layer = DummyLayer()
        mocked_layer.return_value = dummy_layer
        request = create_request(
            requester=self.user,
            template=self.template,
            target_agent=self.agent,
            model_version_ids=[str(self.version.id)],
        )
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(f"/api/requests/{request.id}/approve/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.json())
        request.refresh_from_db()
        self.assertEqual(request.status, ContainerRequest.Status.APPROVED)
        self.assertEqual(request.deployment_phase, "prepare_model_assets")
        job = ModelPrepareJob.objects.get(version=self.version, agent=self.agent)
        self.assertEqual(request.prepare_job_ids, [str(job.id)])
        self.assertEqual(job.status, ModelPrepareJob.Status.DISPATCHED)
        payload = dummy_layer.messages[0][1]["payload"]
        self.assertEqual(payload["requestId"], str(job.id))
        self.assertEqual(payload["command"], "prepare_model_assets")
        asset = payload["params"]["assets"][0]
        self.assertEqual(asset["sha256"], self.version.sha256)
        self.assertEqual(asset["checksum"], self.version.sha256)
        self.assertEqual(asset["source"]["sha256"], self.version.sha256)
        self.assertEqual(asset["source"]["checksum"], self.version.sha256)
        self.assertEqual(asset["source"]["contentUrl"], f"/api/model-versions/{self.version.id}/content/")
        self.assertNotEqual(payload["command"], "create_container")

    @patch("apps.containers.services.deployment.command_router.get_agent_channel", return_value="agent-channel")
    @patch("apps.containers.services.deployment.command_router.record_pending")
    @patch("apps.containers.services.deployment.get_channel_layer")
    def test_prepare_response_dispatches_create_with_read_only_model_mount(
        self,
        mocked_layer,
        mocked_record_pending,
        mocked_agent_channel,
    ):
        dummy_layer = DummyLayer()
        mocked_layer.return_value = dummy_layer
        request = create_request(
            requester=self.user,
            template=self.template,
            target_agent=self.agent,
            status=ContainerRequest.Status.APPROVED,
            model_version_ids=[str(self.version.id)],
            deployment_phase="prepare_model_assets",
        )
        cache = ModelVersionCache.objects.create(
            agent=self.agent,
            version=self.version,
            status=ModelVersionCache.Status.PREPARING,
            size_bytes=self.version.size_bytes,
            sha256=self.version.sha256,
        )
        job = ModelPrepareJob.objects.create(
            agent=self.agent,
            version=self.version,
            cache=cache,
            status=ModelPrepareJob.Status.DISPATCHED,
            bytes_total=self.version.size_bytes,
            lease_expires_at=timezone.now(),
        )
        job.waiting_requests.add(request)
        request.prepare_job_ids = [str(job.id)]
        request.save(update_fields=["prepare_job_ids", "updated_at"])

        handled = handle_prepare_response({
            "requestId": str(job.id),
            "success": True,
            "data": {
                "cachePath": "/var/lib/hypercube-agent/model-cache/tiny-local-model/v1",
                "sha256": self.version.sha256,
            },
        })

        self.assertTrue(handled)
        job.refresh_from_db()
        cache.refresh_from_db()
        request.refresh_from_db()
        self.assertEqual(job.status, ModelPrepareJob.Status.READY)
        self.assertEqual(cache.status, ModelVersionCache.Status.READY)
        self.assertEqual(request.deployment_phase, "create_container")
        payload = dummy_layer.messages[0][1]["payload"]
        self.assertEqual(payload["command"], "create_container")
        mount = payload["params"]["modelMounts"][0]
        self.assertEqual(mount["versionId"], str(self.version.id))
        self.assertEqual(mount["sourcePath"], cache.cache_path)
        self.assertEqual(mount["mountPath"], "/workspace/models/tiny-local-model@v1")
        self.assertIs(mount["readOnly"], True)

    @patch("apps.containers.services.deployment.command_router.get_agent_channel", return_value="agent-channel")
    @patch("apps.containers.services.deployment.command_router.record_pending")
    @patch("apps.containers.services.deployment.get_channel_layer")
    def test_approval_skips_prepare_when_agent_cache_is_ready(
        self,
        mocked_layer,
        mocked_record_pending,
        mocked_agent_channel,
    ):
        dummy_layer = DummyLayer()
        mocked_layer.return_value = dummy_layer
        cache_path = "/var/lib/hypercube-agent/model-cache/tiny-local-model/v1"
        ModelVersionCache.objects.create(
            agent=self.agent,
            version=self.version,
            status=ModelVersionCache.Status.READY,
            cache_path=cache_path,
            size_bytes=self.version.size_bytes,
            sha256=self.version.sha256,
            last_verified_at=timezone.now(),
        )
        request = create_request(
            requester=self.user,
            template=self.template,
            target_agent=self.agent,
            model_version_ids=[str(self.version.id)],
        )
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(f"/api/requests/{request.id}/approve/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.json())
        request.refresh_from_db()
        self.assertEqual(request.prepare_job_ids, [])
        self.assertEqual(request.deployment_phase, "create_container")
        self.assertEqual(ModelPrepareJob.objects.filter(version=self.version, agent=self.agent).count(), 0)
        payload = dummy_layer.messages[0][1]["payload"]
        self.assertEqual(payload["command"], "create_container")
        mount = payload["params"]["modelMounts"][0]
        self.assertEqual(mount["sourcePath"], cache_path)
        self.assertEqual(mount["sha256"], self.version.sha256)

    def test_prepare_response_accepts_source_path_alias(self):
        cache = ModelVersionCache.objects.create(
            agent=self.agent,
            version=self.version,
            status=ModelVersionCache.Status.PREPARING,
            size_bytes=self.version.size_bytes,
            sha256=self.version.sha256,
        )
        job = ModelPrepareJob.objects.create(
            agent=self.agent,
            version=self.version,
            cache=cache,
            status=ModelPrepareJob.Status.DISPATCHED,
            bytes_total=self.version.size_bytes,
            lease_expires_at=timezone.now(),
        )

        handled = handle_prepare_response({
            "requestId": str(job.id),
            "success": True,
            "data": {
                "sourcePath": "/var/lib/hypercube-agent/model-cache/tiny-local-model/v1",
                "sha256": self.version.sha256,
            },
        })

        self.assertTrue(handled)
        job.refresh_from_db()
        cache.refresh_from_db()
        self.assertEqual(job.status, ModelPrepareJob.Status.READY)
        self.assertEqual(cache.status, ModelVersionCache.Status.READY)
        self.assertEqual(cache.cache_path, "/var/lib/hypercube-agent/model-cache/tiny-local-model/v1")

    def test_agent_token_streams_lightweight_model_content_for_active_prepare_job(self):
        cache = ModelVersionCache.objects.create(
            agent=self.agent,
            version=self.version,
            status=ModelVersionCache.Status.PREPARING,
        )
        ModelPrepareJob.objects.create(
            agent=self.agent,
            version=self.version,
            cache=cache,
            status=ModelPrepareJob.Status.DISPATCHED,
        )

        response = self.client.get(
            f"/api/model-versions/{self.version.id}/content/",
            HTTP_AUTHORIZATION="Bearer agent_prepare_token",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(b"".join(response.streaming_content), b"tiny local model bytes")
        self.assertEqual(response["X-HyperCube-Model-SHA256"], self.version.sha256)

    def test_cache_status_reports_missing_and_ready(self):
        ModelVersionCache.objects.create(
            agent=self.agent,
            version=self.version,
            status=ModelVersionCache.Status.READY,
            cache_path="/var/lib/hypercube-agent/model-cache/tiny-local-model/v1",
            size_bytes=self.version.size_bytes,
            sha256=self.version.sha256,
            last_verified_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/model-versions/cache-status/?agent={self.agent.id}&versions={self.version.id}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.json())
        result = response.json()["data"]["results"][0]
        self.assertEqual(result["version"], str(self.version.id))
        self.assertEqual(result["status"], ModelVersionCache.Status.READY)
        self.assertEqual(result["mountPath"], "/workspace/models/tiny-local-model@v1")


@override_settings(
    MODEL_PREPARE_LEASE_SECONDS=3600,
    MODEL_PREPARE_PROGRESS_TIMEOUT_SECONDS=900,
    MODEL_PREPARE_MAX_ATTEMPTS=3,
)
class PrepareJobWatchdogTest(APITestCase):
    """progress 무응답 watchdog + reconnect reconcile."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.storage_override = override_settings(
            HC_MODEL_STORAGE_DIR=os.path.join(self.tempdir.name, "storage"),
            HC_MODEL_IMPORT_DIR=os.path.join(self.tempdir.name, "import"),
        )
        self.storage_override.enable()
        self.user = create_user(role="user", username="wd-user")
        self.agent = create_agent(
            hostname="wd-agent", ip_address="10.2.2.2", token="agent_wd_token"
        )
        self.asset = ModelAsset.objects.create(
            owner=self.user, name="Watchdog Model", slug="wd-model"
        )
        self.version = save_uploaded_model_version(
            asset=self.asset,
            uploaded_file=SimpleUploadedFile("wd.bin", b"watchdog model bytes"),
            version="v1",
            uploaded_by=self.user,
            metadata={},
        )

    def tearDown(self):
        self.storage_override.disable()
        self.tempdir.cleanup()

    def _make_job(self, *, last_progress_offset, attempt_count=0, lease_offset=3600):
        now = timezone.now()
        return ModelPrepareJob.objects.create(
            agent=self.agent,
            version=self.version,
            status=ModelPrepareJob.Status.PREPARING,
            bytes_total=self.version.size_bytes,
            last_progress_at=now - timedelta(seconds=last_progress_offset),
            attempt_count=attempt_count,
            lease_expires_at=now + timedelta(seconds=lease_offset),
        )

    def test_recent_progress_job_is_left_alone(self):
        job = self._make_job(last_progress_offset=10)
        handled = cleanup_stale_model_prepare_jobs()
        job.refresh_from_db()
        self.assertEqual(handled, 0)
        self.assertEqual(job.status, ModelPrepareJob.Status.PREPARING)

    @patch("apps.models_catalog.prepare.dispatch_prepare_job", return_value=True)
    def test_stalled_job_is_requeued(self, mocked_dispatch):
        job = self._make_job(last_progress_offset=1000, attempt_count=0)
        handled = cleanup_stale_model_prepare_jobs()
        job.refresh_from_db()
        self.assertEqual(handled, 1)
        self.assertEqual(job.status, ModelPrepareJob.Status.QUEUED)
        self.assertEqual(job.attempt_count, 1)
        mocked_dispatch.assert_called_once()

    @patch("apps.models_catalog.prepare.dispatch_prepare_job", return_value=True)
    def test_stalled_job_fails_after_max_attempts(self, mocked_dispatch):
        job = self._make_job(last_progress_offset=1000, attempt_count=3)
        handled = cleanup_stale_model_prepare_jobs()
        job.refresh_from_db()
        self.assertEqual(handled, 1)
        self.assertEqual(job.status, ModelPrepareJob.Status.FAILED)
        mocked_dispatch.assert_not_called()

    def test_lease_expired_job_fails(self):
        # lease 만료 job 은 STALE 을 거쳐 fail_prepare_job 으로 FAILED 가 된다.
        job = self._make_job(last_progress_offset=10, lease_offset=-10)
        handled = cleanup_stale_model_prepare_jobs()
        job.refresh_from_db()
        self.assertEqual(handled, 1)
        self.assertEqual(job.status, ModelPrepareJob.Status.FAILED)

    @patch("apps.models_catalog.prepare.dispatch_prepare_job", return_value=True)
    def test_reconcile_agent_requeues_stuck_job_on_reconnect(self, mocked_dispatch):
        job = self._make_job(last_progress_offset=1000, attempt_count=0)
        recovered = reconcile_agent_prepare_jobs(str(self.agent.id))
        job.refresh_from_db()
        self.assertEqual(recovered, 1)
        self.assertEqual(job.status, ModelPrepareJob.Status.QUEUED)
        self.assertEqual(job.attempt_count, 1)

    @patch("apps.models_catalog.prepare.dispatch_prepare_job", return_value=True)
    def test_reconcile_leaves_healthy_job_untouched(self, mocked_dispatch):
        job = self._make_job(last_progress_offset=10)
        recovered = reconcile_agent_prepare_jobs(str(self.agent.id))
        job.refresh_from_db()
        self.assertEqual(recovered, 0)
        self.assertEqual(job.status, ModelPrepareJob.Status.PREPARING)
        mocked_dispatch.assert_not_called()
