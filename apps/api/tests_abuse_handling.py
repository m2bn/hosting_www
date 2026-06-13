import io
import json
import zipfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.api import abuse, audit_log
from apps.api.models import (
    AbuseStatus,
    AuditLog,
    Organization,
    OrganizationMember,
    OrganizationMemberStatus,
    Plan,
    Project,
    ProjectStatus,
    Role,
    RoleScope,
    SecurityEvent,
    Subscription,
    SubscriptionStatus,
    User,
)
from apps.api.rbac import ROLE_DEVELOPER, ROLE_OWNER


@override_settings(
    STATIC_DEPLOYMENT_MAX_ZIP_BYTES=1024 * 1024,
    STATIC_DEPLOYMENT_MAX_FILES=5,
    STATIC_DEPLOYMENT_MAX_UNPACKED_BYTES=1024,
    STATIC_DEPLOYMENT_LOCAL_ROOT="outputs/test-abuse-static-deployments",
)
class AbuseHandlingTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.operator = User.objects.create_user(
            email="operator@example.com",
            password="secret",
            is_platform_staff=True,
            mfa_enabled=True,
        )
        self.user = User.objects.create_user(email="developer@example.com", password="secret")
        self.owner = User.objects.create_user(email="owner@example.com", password="secret")
        self.owner_role = Role.objects.create(scope=RoleScope.ORGANIZATION, key=ROLE_OWNER, name="Owner")
        self.developer_role = Role.objects.create(scope=RoleScope.ORGANIZATION, key=ROLE_DEVELOPER, name="Developer")
        self.organization = Organization.objects.create(name="Acme", slug="acme", owner_user=self.owner)
        OrganizationMember.objects.create(
            organization=self.organization,
            user=self.owner,
            role=self.owner_role,
            status=OrganizationMemberStatus.ACTIVE,
        )
        OrganizationMember.objects.create(
            organization=self.organization,
            user=self.user,
            role=self.developer_role,
            status=OrganizationMemberStatus.ACTIVE,
        )
        plan = Plan.objects.create(
            key="abuse-pro",
            name="Abuse Pro",
            limits={"projects": 10, "storage_gb": 1, "transfer_gb": 100},
            features={"custom_domains": True, "container_deployments": True},
        )
        Subscription.objects.create(organization=self.organization, plan=plan, status=SubscriptionStatus.ACTIVE)
        create_response = self._create_project()
        self.project = Project.objects.get(public_id=create_response.json()["public_id"])
        self.environment = self.project.default_environment

    def csrf(self):
        self.client.get(reverse("auth-csrf"))
        return self.client.cookies["csrftoken"].value

    def post_json(self, name, kwargs, payload, user=None):
        self.client.force_login(user or self.operator)
        return self.client.post(
            reverse(name, kwargs=kwargs),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf(),
        )

    def _create_project(self):
        self.client.force_login(self.owner)
        return self.client.post(
            reverse("project-list", kwargs={"organization_public_id": self.organization.public_id}),
            data=json.dumps({"name": "App", "slug": "app"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf(),
        )

    def zip_file(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("index.html", "<h1>Hello</h1>")
        return SimpleUploadedFile("site.zip", buffer.getvalue(), content_type="application/zip")

    def test_operator_marks_project_abusive(self):
        response = self.post_json(
            "operator-project-abusive",
            {"project_public_id": self.project.public_id},
            {"reason": "Phishing report ABUSE-1"},
        )

        self.assertEqual(response.status_code, 200)
        self.project.refresh_from_db()
        self.assertEqual(self.project.abuse_status, AbuseStatus.FLAGGED)
        self.assertEqual(self.project.status, ProjectStatus.ACTIVE)
        self.assertIn("Phishing report", self.project.abuse_reason)
        self.assertTrue(AuditLog.objects.filter(action=audit_log.AuditAction.ABUSE_PROJECT_FLAGGED, project=self.project).exists())

    def test_operator_blocks_project_and_blocked_project_is_listed(self):
        response = self.post_json(
            "operator-project-block",
            {"project_public_id": self.project.public_id},
            {"reason": "Malware hosted on deployment"},
        )

        self.assertEqual(response.status_code, 200)
        self.project.refresh_from_db()
        self.assertEqual(self.project.abuse_status, AbuseStatus.BLOCKED)
        self.assertEqual(self.project.status, ProjectStatus.SUSPENDED)
        self.assertIsNotNone(self.project.blocked_at)
        self.assertEqual(self.project.blocked_by_user, self.operator)
        self.assertTrue(AuditLog.objects.filter(action=audit_log.AuditAction.ABUSE_PROJECT_BLOCKED, project=self.project).exists())

        self.client.force_login(self.operator)
        list_response = self.client.get(reverse("operator-blocked-project-list"))
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["results"][0]["public_id"], str(self.project.public_id))

    def test_operator_blocks_organization(self):
        response = self.post_json(
            "operator-organization-block",
            {"organization_public_id": self.organization.public_id},
            {"reason": "Repeated malware deployments"},
        )

        self.assertEqual(response.status_code, 200)
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.abuse_status, AbuseStatus.BLOCKED)
        self.assertEqual(self.organization.status, "suspended")
        self.assertIn("Repeated malware", self.organization.abuse_reason)
        self.assertTrue(
            AuditLog.objects.filter(action=audit_log.AuditAction.ABUSE_ORGANIZATION_BLOCKED, organization=self.organization).exists()
        )

    def test_abuse_action_requires_reason(self):
        response = self.post_json(
            "operator-project-block",
            {"project_public_id": self.project.public_id},
            {"reason": "   "},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "reason_required")
        self.project.refresh_from_db()
        self.assertEqual(self.project.abuse_status, AbuseStatus.CLEAR)

    def test_regular_user_cannot_block_project(self):
        response = self.post_json(
            "operator-project-block",
            {"project_public_id": self.project.public_id},
            {"reason": "Nope"},
            user=self.user,
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "operator_required")

    def test_blocked_project_cannot_deploy_and_sees_safe_message(self):
        abuse.block_project(self.project, operator=self.operator, reason="Malware scan failed")
        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                "static-deployment-create",
                kwargs={
                    "organization_public_id": self.organization.public_id,
                    "project_public_id": self.project.public_id,
                    "environment_public_id": self.environment.public_id,
                },
            ),
            data={"file": self.zip_file()},
            HTTP_X_CSRFTOKEN=self.csrf(),
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "project_blocked")
        self.assertEqual(response.json()["detail"], abuse.safe_blocked_message())
        self.assertNotIn("Malware scan failed", response.content.decode())

    def test_operator_can_unblock_project(self):
        abuse.block_project(self.project, operator=self.operator, reason="Initial block")

        response = self.post_json(
            "operator-project-unblock",
            {"project_public_id": self.project.public_id},
            {"reason": "Content removed and reviewed"},
        )

        self.assertEqual(response.status_code, 200)
        self.project.refresh_from_db()
        self.assertEqual(self.project.abuse_status, AbuseStatus.CLEAR)
        self.assertEqual(self.project.status, ProjectStatus.ACTIVE)
        self.assertEqual(self.project.abuse_reason, "")
        self.assertTrue(AuditLog.objects.filter(action=audit_log.AuditAction.ABUSE_PROJECT_UNBLOCKED, project=self.project).exists())

    def test_abuse_alerts_create_security_events_and_audit_logs(self):
        for signal in [
            abuse.AbuseSignal.EXCESSIVE_TRANSFER,
            abuse.AbuseSignal.TOO_MANY_DEPLOYMENTS,
            abuse.AbuseSignal.SUSPICIOUS_DOMAIN,
            abuse.AbuseSignal.MALWARE_SCAN_FAILED,
            abuse.AbuseSignal.HIGH_4XX_5XX_RATE,
        ]:
            abuse.create_abuse_alert(signal, organization=self.organization, project=self.project, metadata={"count": 10})

        self.assertEqual(SecurityEvent.objects.filter(category="abuse", project=self.project).count(), 5)
        self.assertEqual(AuditLog.objects.filter(action=audit_log.AuditAction.ABUSE_ALERT_CREATED, project=self.project).count(), 5)
