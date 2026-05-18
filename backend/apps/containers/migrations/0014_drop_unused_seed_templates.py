from django.db import migrations


# 0007 seeded four ML templates, but only PyTorch Jupyter has a real airgap
# image built. TensorFlow / code-server / vLLM templates pointed at images
# that were never produced, so any container request for them failed at
# deploy. Drop them so the catalog reflects what actually runs. Users can
# always re-register them via the wizard once the images exist.
UNUSED_TEMPLATE_NAMES = (
    "TensorFlow Jupyter GPU Workspace",
    "CUDA code-server Workspace",
    "vLLM OpenAI API Workspace",
)


def drop_unused_seed_templates(apps, schema_editor):
    import sys
    if "test" in sys.argv:
        return
    ContainerTemplate = apps.get_model("containers", "ContainerTemplate")
    ContainerTemplate.objects.filter(name__in=UNUSED_TEMPLATE_NAMES).delete()


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ("containers", "0013_template_default_models"),
    ]

    operations = [
        migrations.RunPython(drop_unused_seed_templates, noop_reverse),
    ]
