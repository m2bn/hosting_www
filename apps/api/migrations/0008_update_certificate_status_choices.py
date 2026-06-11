from django.db import migrations, models


def forward_statuses(apps, schema_editor):
    Certificate = apps.get_model("api", "Certificate")
    Certificate.objects.filter(status="issued").update(status="active")
    Certificate.objects.filter(status="renewing").update(status="renewal_pending")
    Certificate.objects.filter(status="revoked").update(status="failed")


def backward_statuses(apps, schema_editor):
    Certificate = apps.get_model("api", "Certificate")
    Certificate.objects.filter(status="active").update(status="issued")
    Certificate.objects.filter(status="renewal_pending").update(status="renewing")


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0007_projectsecret_projectsecretversion_and_more"),
    ]

    operations = [
        migrations.RunPython(forward_statuses, backward_statuses),
        migrations.AlterField(
            model_name="certificate",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("issuing", "Issuing"),
                    ("active", "Active"),
                    ("renewal_pending", "Renewal pending"),
                    ("failed", "Failed"),
                    ("expired", "Expired"),
                ],
                default="pending",
                max_length=32,
            ),
        ),
    ]
