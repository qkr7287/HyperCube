"""Tests for the inference recipe catalogue + its propagation into agent env.

Guards two contracts:
  1. The python catalogue and the image-shipped launcher_recipes.json never
     drift (image build regenerates JSON, but the test catches stale checkout).
  2. build_agent_payload injects HC_LAUNCHER_RECIPE + HC_MODEL_DIR when a
     template has a non-'none' recipe AND a model version is attached.
"""
import json
from pathlib import Path

from django.test import TestCase

from apps.containers.launcher_recipes import (
    NONE_RECIPE_ID,
    export_catalogue_json,
    get_recipe,
    is_auto,
    is_valid,
    list_recipes,
)
from apps.containers.services.deployment import _launcher_env_for_request
from apps.models_catalog.models import ModelAsset, ModelVersion

from .factories import create_agent, create_request, create_template, create_user


REPO_ROOT = Path(__file__).resolve().parents[4]
IMAGE_RECIPES_JSON = REPO_ROOT / "packaging" / "ml-images" / "pytorch-jupyter" / "launcher_recipes.json"


class LauncherRecipeCatalogueTests(TestCase):
    def test_required_recipes_present(self):
        ids = {r.id for r in list_recipes()}
        self.assertIn("qwen2-vl", ids)
        self.assertIn("auto-causal-lm", ids)
        self.assertIn(NONE_RECIPE_ID, ids)

    def test_none_is_not_auto(self):
        self.assertFalse(is_auto(NONE_RECIPE_ID))
        self.assertTrue(is_auto("qwen2-vl"))

    def test_get_recipe_rejects_unknown(self):
        self.assertTrue(is_valid("qwen2-vl"))
        self.assertFalse(is_valid("bogus"))
        with self.assertRaises(KeyError):
            get_recipe("bogus")

    def test_image_json_matches_catalogue(self):
        if not IMAGE_RECIPES_JSON.is_file():
            self.skipTest("packaging/ml-images JSON not present in this checkout")
        image_payload = json.loads(IMAGE_RECIPES_JSON.read_text(encoding="utf-8"))
        backend_payload = json.loads(export_catalogue_json())
        self.assertEqual(
            image_payload,
            backend_payload,
            "launcher_recipes.json out of sync with apps.containers.launcher_recipes — "
            "re-run packaging/ml-images/build-pytorch-jupyter.sh or regenerate the JSON.",
        )


class LauncherEnvPropagationTests(TestCase):
    def setUp(self):
        self.admin = create_user(role="admin", username="recipe-admin")
        self.user = create_user(role="user", username="recipe-user")
        self.agent = create_agent(hostname="recipe-agent")
        self.asset = ModelAsset.objects.create(
            owner=self.admin,
            name="Qwen2 VL 2B",
            slug="qwen2-vl-2b-instruct",
            visibility=ModelAsset.Visibility.SHARED,
        )
        self.version = ModelVersion.objects.create(
            asset=self.asset,
            version="v1",
            original_filename="model.tar.gz",
            storage_path="dummy.tar.gz",
            sha256="0" * 64,
        )

    def _make_request(self, *, recipe_id, attach_model=True, overrides=None):
        template = create_template(
            created_by=self.admin,
            launcher_recipe_id=recipe_id,
            launcher_overrides=overrides or {},
        )
        return create_request(
            requester=self.user,
            template=template,
            target_agent=self.agent,
            model_version_ids=[str(self.version.id)] if attach_model else [],
        )

    def test_none_recipe_injects_no_launcher_env(self):
        request = self._make_request(recipe_id="none")
        self.assertEqual(_launcher_env_for_request(request), {})

    def test_qwen2vl_recipe_injects_recipe_env_with_model_dir(self):
        request = self._make_request(recipe_id="qwen2-vl")
        env = _launcher_env_for_request(request)
        self.assertEqual(env["HC_LAUNCHER_RECIPE"], "qwen2-vl")
        self.assertEqual(env["HC_MODEL_DIR"], "/workspace/qwen2-vl-2b-instruct")
        self.assertEqual(env["HC_GRADIO_PORT"], "7860")
        self.assertEqual(env["HC_GRADIO_ROOT_PATH"], "/proxy/7860")

    def test_recipe_skipped_when_no_model_attached(self):
        request = self._make_request(recipe_id="qwen2-vl", attach_model=False)
        self.assertEqual(_launcher_env_for_request(request), {})

    def test_custom_recipe_injects_override_env(self):
        request = self._make_request(
            recipe_id="__custom__",
            overrides={
                "model_class": "Idefics3ForConditionalGeneration",
                "processor_class": "AutoProcessor",
                "app_template": "gradio_vlm_chat",
                "trust_remote_code": True,
            },
        )
        env = _launcher_env_for_request(request)
        self.assertEqual(env["HC_LAUNCHER_RECIPE"], "__custom__")
        self.assertEqual(env["HC_LAUNCHER_MODEL_CLASS"], "Idefics3ForConditionalGeneration")
        self.assertEqual(env["HC_LAUNCHER_PROCESSOR_CLASS"], "AutoProcessor")
        self.assertEqual(env["HC_LAUNCHER_APP_TEMPLATE"], "gradio_vlm_chat")
        self.assertEqual(env["HC_LAUNCHER_TRUST_REMOTE_CODE"], "true")

    def test_custom_recipe_without_model_class_yields_no_env(self):
        request = self._make_request(
            recipe_id="__custom__",
            overrides={"app_template": "gradio_text_chat"},  # model_class 누락
        )
        self.assertEqual(_launcher_env_for_request(request), {})
