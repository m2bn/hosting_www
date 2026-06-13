import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0010_user_anonymized_at_user_deleted_at_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="abuse_status",
            field=models.CharField(
                choices=[("clear", "Clear"), ("flagged", "Flagged"), ("blocked", "Blocked")],
                default="clear",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="organization",
            name="abuse_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="organization",
            name="abuse_marked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="organization",
            name="blocked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="organization",
            name="blocked_by_user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="blocked_organizations",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="project",
            name="abuse_status",
            field=models.CharField(
                choices=[("clear", "Clear"), ("flagged", "Flagged"), ("blocked", "Blocked")],
                default="clear",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="project",
            name="abuse_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="project",
            name="abuse_marked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="project",
            name="blocked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="project",
            name="blocked_by_user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="blocked_projects",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddIndex(
            model_name="organization",
            index=models.Index(fields=["abuse_status"], name="api_org_abuse_status_idx"),
        ),
        migrations.AddIndex(
            model_name="project",
            index=models.Index(fields=["organization", "abuse_status"], name="api_project_org_abuse_idx"),
        ),
    ]
