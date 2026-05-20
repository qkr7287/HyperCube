from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("containers", "0018_template_network_policy_default"),
    ]

    operations = [
        migrations.AddField(
            model_name="containerrequest",
            name="workspace_host_port",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
