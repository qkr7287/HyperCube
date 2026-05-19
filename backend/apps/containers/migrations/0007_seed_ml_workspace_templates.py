from django.db import migrations


def get_seed_admin(apps):
    User = apps.get_model("users", "CustomUser")
    admin = User.objects.filter(username="admin").first()
    if admin:
        return admin

    admin = User.objects.filter(role="admin").order_by("id").first()
    if admin:
        return admin

    from django.contrib.auth.hashers import make_password

    return User.objects.create(
        username="admin",
        password=make_password(None),
        role="admin",
        is_staff=True,
        is_superuser=True,
        is_active=True,
    )


def seed_ml_workspace_templates(apps, schema_editor):
    import sys

    if "test" in sys.argv:
        return

    ContainerTemplate = apps.get_model("containers", "ContainerTemplate")
    admin = get_seed_admin(apps)

    templates = [
        {
            "name": "PyTorch Jupyter GPU Workspace",
            "description": "Air-gapped CUDA PyTorch workspace with JupyterLab.",
            "image": "hypercube/ml-pytorch-jupyter:cuda12.4-airgap",
            "workspace_kind": "jupyter",
            "workspace_port": 8888,
            "default_max_runtime_hours": 24,
        },
        {
            "name": "TensorFlow Jupyter GPU Workspace",
            "description": "Air-gapped CUDA TensorFlow workspace with JupyterLab.",
            "image": "hypercube/ml-tensorflow-jupyter:cuda12.4-airgap",
            "workspace_kind": "jupyter",
            "workspace_port": 8888,
            "default_max_runtime_hours": 24,
        },
        {
            "name": "vLLM OpenAI API Workspace",
            "description": "Air-gapped vLLM serving workspace with OpenAI-compatible API.",
            "image": "hypercube/ml-vllm-openai:v0.8.5-airgap",
            "workspace_kind": "api",
            "workspace_port": 8000,
            "default_max_runtime_hours": 12,
        },
        {
            "name": "CUDA code-server Workspace",
            "description": "Air-gapped CUDA development workspace with code-server.",
            "image": "hypercube/ml-code-server-cuda:cuda12.4-airgap",
            "workspace_kind": "code-server",
            "workspace_port": 8080,
            "default_max_runtime_hours": 24,
        },
    ]

    for template in templates:
        ContainerTemplate.objects.update_or_create(
            name=template["name"],
            defaults={
                "description": template["description"],
                "kind": "simple",
                "category": "ml",
                "requires_gpu": True,
                "workspace_enabled": True,
                "workspace_kind": template["workspace_kind"],
                "workspace_port": template["workspace_port"],
                "default_workdir": "/workspace",
                "network_policy": "internal_only",
                "default_max_runtime_hours": template["default_max_runtime_hours"],
                "image": template["image"],
                "image_options": [],
                "env_schema": [],
                "port_schema": [],
                "default_volumes": [],
                "compose_yaml": "",
                "created_by": admin,
            },
        )


def remove_ml_workspace_templates(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0004_fix_admin_password"),
        ("containers", "0006_workspace_and_jupyter"),
    ]

    operations = [
        migrations.RunPython(seed_ml_workspace_templates, remove_ml_workspace_templates),
    ]
