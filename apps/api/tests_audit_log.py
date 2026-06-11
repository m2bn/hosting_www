import json

from django.test import Client, TestCase
from django.urls import reverse

from apps.api import audit_log
from apps.api.models import AuditActorType, AuditLog, AuditResult, Organization, Project, User


class AuditLogTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.user = User.objects.create_user(email="audited@example.com", password="secret")
        self.organization = Organization.objects.create(name="Acme", slug="acme", owner_user=self.user)
        self.project = Project.objects.create(
            organization=self.organization,
            name="Website",
            slug="website",
            created_by_user=self.user,
        )

    def csrf(self):
        self.client.get(reverse("auth-csrf"))
        return self.client.cookies["csrftoken"].value

    def test_record_creates_required_audit_fields_and_sanitizes_metadata(self):
        record = audit_log.record(
            action=audit_log.AuditAction.PROJECT_CREATED,
            actor=self.user,
            organization=self.organization,
            project=self.project,
            target_type="project",
            target_id=self.project.public_id,
            metadata={
                "safe": "value",
                "password": "do-not-store",
                "nested": {"token": "secret-token"},
                "items": [{"api_key": "secret-key"}],
            },
        )

        self.assertEqual(record.actor_type, AuditActorType.USER)
        self.assertEqual(record.actor_id, str(self.user.public_id))
        self.assertEqual(record.organization, self.organization)
        self.assertEqual(record.project, self.project)
        self.assertEqual(record.target_type, "project")
        self.assertEqual(record.target_id, str(self.project.public_id))
        self.assertEqual(record.metadata["safe"], "value")
        self.assertEqual(record.metadata["password"], "[REDACTED]")
        self.assertEqual(record.metadata["nested"]["token"], "[REDACTED]")
        self.assertEqual(record.metadata["items"][0]["api_key"], "[REDACTED]")

    def test_audit_log_cannot_be_updated_by_model_save(self):
        record = audit_log.record(
            action=audit_log.AuditAction.ORGANIZATION_UPDATED,
            actor=self.user,
            organization=self.organization,
            target_type="organization",
            target_id=self.organization.public_id,
        )

        record.action = "tampered"
        with self.assertRaises(RuntimeError):
            record.save()

    def test_audit_log_cannot_be_updated_by_queryset(self):
        record = audit_log.record(
            action=audit_log.AuditAction.ORGANIZATION_UPDATED,
            actor=self.user,
            organization=self.organization,
            target_type="organization",
            target_id=self.organization.public_id,
        )

        with self.assertRaises(RuntimeError):
            AuditLog.objects.filter(pk=record.pk).update(action="tampered")

    def test_audit_log_cannot_be_deleted_by_model_or_queryset(self):
        record = audit_log.record(
            action=audit_log.AuditAction.ORGANIZATION_DELETED,
            actor=self.user,
            organization=self.organization,
            target_type="organization",
            target_id=self.organization.public_id,
        )

        with self.assertRaises(RuntimeError):
            record.delete()
        with self.assertRaises(RuntimeError):
            AuditLog.objects.filter(pk=record.pk).delete()

    def test_request_id_middleware_sets_response_header_and_audit_request_id(self):
        response = self.client.post(
            reverse("auth-login"),
            data=json.dumps({"email": "audited@example.com", "password": "secret"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf(),
            HTTP_X_REQUEST_ID="req-test-123",
            HTTP_USER_AGENT="AuditTest/1.0",
            REMOTE_ADDR="203.0.113.10",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["X-Request-ID"], "req-test-123")

        record = AuditLog.objects.get(action=audit_log.AuditAction.AUTH_LOGIN_SUCCEEDED)
        self.assertEqual(record.request_id, "req-test-123")
        self.assertEqual(record.correlation_id, "req-test-123")
        self.assertEqual(record.ip_address, "203.0.113.10")
        self.assertEqual(record.user_agent, "AuditTest/1.0")
        self.assertEqual(record.result, AuditResult.SUCCESS)
