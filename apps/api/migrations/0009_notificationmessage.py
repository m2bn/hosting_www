import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0008_update_certificate_status_choices"),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("recipient_email", models.EmailField(max_length=254)),
                ("recipient_email_hash", models.CharField(max_length=255)),
                ("event_type", models.CharField(max_length=100)),
                ("template_key", models.CharField(max_length=100)),
                ("subject", models.CharField(max_length=255)),
                ("context", models.JSONField(blank=True, default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("sending", "Sending"),
                            ("sent", "Sent"),
                            ("failed", "Failed"),
                            ("rate_limited", "Rate limited"),
                        ],
                        default="queued",
                        max_length=32,
                    ),
                ),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("last_error", models.CharField(blank=True, max_length=255)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                (
                    "organization",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="notifications", to="api.organization"),
                ),
                (
                    "project",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="notifications", to="api.project"),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="notificationmessage",
            index=models.Index(fields=["status", "created_at"], name="api_notif_status_created_idx"),
        ),
        migrations.AddIndex(
            model_name="notificationmessage",
            index=models.Index(fields=["recipient_email_hash", "created_at"], name="api_notif_rec_created_idx"),
        ),
    ]
