import hashlib
import os
import tempfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.containers.models import ContainerTemplate
from apps.containers.tests.factories import create_user
from apps.models_catalog.models import ModelAsset, ModelUploadRequest, ModelVersion


class ModelCatalogAPITest(APITestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.storage_dir = os.path.join(self.tempdir.name, "storage")
        self.import_dir = os.path.join(self.tempdir.name, "import")
        Path(self.import_dir).mkdir(parents=True, exist_ok=True)
        self.settings_override = override_settings(
            HC_MODEL_STORAGE_DIR=self.storage_dir,
            HC_MODEL_IMPORT_DIR=self.import_dir,
        )
        self.settings_override.enable()
        self.user = create_user(role="user", username="model-owner")
        self.other_user = create_user(role="user", username="model-other")
        self.admin = create_user(role="admin", username="model-admin")

    def tearDown(self):
        self.settings_override.disable()
        self.tempdir.cleanup()

    def test_admin_can_create_asset_and_upload_version_with_checksum(self):
        self.client.force_authenticate(user=self.admin)
        create_response = self.client.post(
            "/api/model-assets/",
            {
                "name": "Llama Local",
                "slug": "llama-local",
                "visibility": ModelAsset.Visibility.SHARED,
                "framework": "pytorch",
                "task": "text-generation",
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED, create_response.json())
        asset_id = create_response.json()["data"]["id"]

        payload = b"offline model bytes"
        upload_response = self.client.post(
            f"/api/model-assets/{asset_id}/versions/upload/",
            {
                "version": "v1",
                "file": SimpleUploadedFile("weights.bin", payload),
            },
            format="multipart",
        )

        self.assertEqual(upload_response.status_code, status.HTTP_201_CREATED, upload_response.json())
        version = ModelVersion.objects.get(asset_id=asset_id, version="v1")
        self.assertEqual(version.sha256, hashlib.sha256(payload).hexdigest())
        self.assertEqual(version.size_bytes, len(payload))
        self.assertTrue((Path(self.storage_dir) / version.storage_path).exists())
        self.assertEqual(list((Path(self.storage_dir) / "_tmp").glob("*")), [])

    def test_user_cannot_directly_create_asset_or_upload_version(self):
        self.client.force_authenticate(user=self.user)
        create_response = self.client.post(
            "/api/model-assets/",
            {
                "name": "Llama Local",
                "slug": "llama-local",
                "visibility": ModelAsset.Visibility.PRIVATE,
                "framework": "pytorch",
                "task": "text-generation",
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)

        asset = ModelAsset.objects.create(owner=self.admin, name="Shared Model", slug="shared-model", visibility=ModelAsset.Visibility.SHARED)
        payload = b"offline model bytes"
        upload_response = self.client.post(
            f"/api/model-assets/{asset.id}/versions/upload/",
            {
                "version": "v1",
                "file": SimpleUploadedFile("weights.bin", payload),
            },
            format="multipart",
        )

        self.assertEqual(upload_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_private_asset_is_hidden_from_other_user(self):
        ModelAsset.objects.create(
            owner=self.user,
            name="Private Model",
            slug="private-model",
        )
        self.client.force_authenticate(user=self.other_user)

        response = self.client.get("/api/model-assets/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["data"]["count"], 0)

    def test_user_upload_request_approval_creates_shared_model_and_template(self):
        self.client.force_authenticate(user=self.user)
        payload = b"browser uploaded model bytes"

        create_response = self.client.post(
            "/api/model-upload-requests/",
            {
                "name": "Tiny Vision",
                "slug": "tiny-vision",
                "version": "v1",
                "framework": "pytorch",
                "task": "image-classification",
                "template_name": "Tiny Vision Workspace",
                "base_image": "hypercube/ml-pytorch-jupyter:cuda12.4-airgap",
                "file": SimpleUploadedFile("tiny.pt", payload),
            },
            format="multipart",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED, create_response.json())
        request_id = create_response.json()["data"]["id"]
        upload_request = ModelUploadRequest.objects.get(id=request_id)
        self.assertEqual(upload_request.status, ModelUploadRequest.Status.PENDING)
        self.assertEqual(upload_request.sha256, hashlib.sha256(payload).hexdigest())
        self.assertTrue((Path(self.storage_dir) / upload_request.upload_storage_path).exists())

        user_approve_response = self.client.post(
            f"/api/model-upload-requests/{request_id}/approve/",
            {"note": "ok"},
            format="json",
        )
        self.assertEqual(user_approve_response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.admin)
        approve_response = self.client.post(
            f"/api/model-upload-requests/{request_id}/approve/",
            {"note": "approved"},
            format="json",
        )

        self.assertEqual(approve_response.status_code, status.HTTP_200_OK, approve_response.json())
        upload_request.refresh_from_db()
        self.assertEqual(upload_request.status, ModelUploadRequest.Status.APPROVED)
        asset = ModelAsset.objects.get(slug="tiny-vision")
        version = ModelVersion.objects.get(asset=asset, version="v1")
        template = ContainerTemplate.objects.get(name="Tiny Vision Workspace")
        self.assertEqual(asset.visibility, ModelAsset.Visibility.SHARED)
        self.assertEqual(version.sha256, hashlib.sha256(payload).hexdigest())
        self.assertEqual(template.default_model_version_ids, [str(version.id)])
        self.assertEqual(template.category, ContainerTemplate.Category.ML)
        self.assertTrue((Path(self.storage_dir) / version.storage_path).exists())

    def test_admin_import_rejects_external_url_and_path_traversal(self):
        asset = ModelAsset.objects.create(
            owner=self.admin,
            name="Imported Model",
            slug="imported-model",
        )
        self.client.force_authenticate(user=self.admin)

        external_response = self.client.post(
            f"/api/model-assets/{asset.id}/versions/import/",
            {"version": "v1", "source_path": "https://example.com/model.bin"},
            format="json",
        )
        traversal_response = self.client.post(
            f"/api/model-assets/{asset.id}/versions/import/",
            {"version": "v2", "source_path": "../outside.bin"},
            format="json",
        )

        self.assertEqual(external_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(traversal_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_can_import_from_offline_directory(self):
        asset = ModelAsset.objects.create(
            owner=self.admin,
            name="Offline Import",
            slug="offline-import",
        )
        source = Path(self.import_dir) / "model.bin"
        source.write_bytes(b"airgap")
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            f"/api/model-assets/{asset.id}/versions/import/",
            {"version": "v1", "source_path": "model.bin"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.json())
        version = ModelVersion.objects.get(asset=asset, version="v1")
        self.assertTrue((Path(self.storage_dir) / version.storage_path).exists())
