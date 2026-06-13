import io
import zipfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from unittest.mock import patch

from apps.api import audit_log
from apps.api.container_deployments import ScanResult
from apps.api.models import (
    ArtifactScan,
    ArtifactScanStatus,
    ArtifactScanType,
    AuditLog,
    Deployment,
    Environment,
    EnvironmentType,
    Organization,
    OrganizationMember,
    OrganizationMemberStatus,
    Plan,
    Project,
    Role,
    RoleScope,
    Subscription,
    SubscriptionStatus,
    User,
)
from apps.api.rbac import ROLE_DEVELOPER, ROLE_OWNER


@override_settings(
    STATIC_DEPLOYMENT_LOCAL_ROOT="outputs/test-artifact-scans-static",
    STATIC_DEPLOYMENT_MAX_ZIP_BYTES=1024 * 1024,
    STATIC_DEPLOYMENT_MAX_FILES=20,
    STATIC_DEPLOYMENT_MAX_UNPACKED_BYTES=1024 * 1024,
    CONTAINER_DEPLOYMENT_MAX_CONTEXT_ZIP_BYTES=1024 * 1024,
    CONTAINER_DEPLOYMENT_MAX_CONTEXT_BYTES=1024 * 1024,
    CONTAINER_DEPLOYMENT_BUILD_TIMEOUT_SECONDS=30,
    CONTAINER_DEPLOYMENT_REGISTRY="registry.test/private",
)
class ArtifactScanningTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.owner_role = Role.objects.create(scope=RoleScope.ORGANIZATION, key=ROLE_OWNER, name="Owner")
        self.developer_role = Role.objects.create(scope=RoleScope.ORGANIZATION, key=ROLE_DEVELOPER, name="Developer")
        self.owner = User.objects.create_user(email="owner@example.com", password="secret")
        self.developer = User.objects.create_user(email="dev@example.com", password="secret")
        self.outsider = User.objects.create_user(email="outsider@example.com", password="secret")
        self.operator = User.objects.create_user(email="operator@example.com", password="secret", is_platform_staff=True, mfa_enabled=True)
        self.operator_without_2fa = User.objects.create_user(email="operator-no-2fa@example.com", password="secret", is_platform_staff=True)

        self.org = Organization.objects.create(name="Acme", slug="acme", owner_user=self.owner)
        self.other_org = Organization.objects.create(name="Other", slug="other", owner_user=self.outsider)
        OrganizationMember.objects.create(organization=self.org, user=self.owner, role=self.owner_role, status=OrganizationMemberStatus.ACTIVE)
        OrganizationMember.objects.create(organization=self.org, user=self.developer, role=self.developer_role, status=OrganizationMemberStatus.ACTIVE)
        OrganizationMember.objects.create(organization=self.other_org, user=self.outsider, role=self.owner_role, status=OrganizationMemberStatus.ACTIVE)

        plan = Plan.objects.create(
            key="scan-test",
            name="Scan Test",
            limits={"projects": 10, "storage_gb": 10, "transfer_gb": 100},
            features={"custom_domains": True, "container_deployments": True},
        )
        Subscription.objects.create(organization=self.org, plan=plan, status=SubscriptionStatus.ACTIVE)
        Subscription.objects.create(organization=self.other_org, plan=plan, status=SubscriptionStatus.ACTIVE)

        self.project = Project.objects.create(organization=self.org, name="App", slug="app", created_by_user=self.owner)
        self.environment = Environment.objects.create(
            organization=self.org,
            project=self.project,
            name="Production",
            slug="production",
            type=EnvironmentType.PRODUCTION,
            kubernetes_namespace="acme-app-production",
        )
        self.other_project = Project.objects.create(organization=self.other_org, name="Other", slug="other", created_by_user=self.outsider)
        self.other_environment = Environment.objects.create(
            organization=self.other_org,
            project=self.other_project,
            name="Production",
            slug="production",
            type=EnvironmentType.PRODUCTION,
            kubernetes_namespace="other-app-production",
        )

    def csrf(self):
        self.client.get(reverse("auth-csrf"))
        return self.client.cookies["csrftoken"].value

    def login_as(self, user):
        self.client.force_login(user)

    def zip_bytes(self, files):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, content in files.items():
                archive.writestr(name, content)
        return buffer.getvalue()

    def post_static_zip(self, files):
        self.login_as(self.developer)
        uploaded = SimpleUploadedFile("site.zip", self.zip_bytes(files), content_type="application/zip")
        return self.client.post(
            reverse(
                "static-deployment-create",
                kwargs={
                    "organization_public_id": self.org.public_id,
                    "project_public_id": self.project.public_id,
                    "environment_public_id": self.environment.public_id,
                },
            ),
            data={"file": uploaded},
            HTTP_X_CSRFTOKEN=self.csrf(),
        )

    def post_container_zip(self):
        self.login_as(self.developer)
        uploaded = SimpleUploadedFile(
            "context.zip",
            self.zip_bytes({"Dockerfile": "FROM nginx\n", "app.py": "print('ok')"}),
            content_type="application/zip",
        )
        return self.client.post(
            reverse(
                "container-deployment-create",
                kwargs={
                    "organization_public_id": self.org.public_id,
                    "project_public_id": self.project.public_id,
                    "environment_public_id": self.environment.public_id,
                },
            ),
            data={"file": uploaded},
            HTTP_X_CSRFTOKEN=self.csrf(),
        )

    def test_clean_artifact_creates_clean_scan_result(self):
        response = self.post_static_zip({"index.html": "<h1>ok</h1>"})

        self.assertEqual(response.status_code, 201)
        scan = ArtifactScan.objects.get(project=self.project)
        self.assertEqual(scan.scan_type, ArtifactScanType.STATIC_ZIP)
        self.assertEqual(scan.status, ArtifactScanStatus.CLEAN)
        self.assertEqual(scan.critical_count, 0)
        self.assertTrue(AuditLog.objects.filter(action=audit_log.AuditAction.ARTIFACT_SCAN_COMPLETED, project=self.project).exists())

    def test_infected_artifact_mock_blocks_static_deployment(self):
        response = self.post_static_zip({"assets/malware.js": "alert('bad')"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "infected_artifact")
        scan = ArtifactScan.objects.get(project=self.project)
        self.assertEqual(scan.status, ArtifactScanStatus.BLOCKED)
        self.assertEqual(scan.critical_count, 1)
        self.assertFalse(Deployment.objects.filter(project=self.project, status="running").exists())
        self.assertTrue(AuditLog.objects.filter(action=audit_log.AuditAction.ARTIFACT_SCAN_BLOCKED, project=self.project).exists())

    def test_critical_vulnerability_blocks_container_deployment(self):
        scan_result = ScanResult(report_ref="scan://report", sbom_ref="sbom://report", critical_count=1)
        with patch("apps.api.container_deployments.ImageScanner.scan", return_value=scan_result):
            response = self.post_container_zip()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "critical_vulnerability")
        scan = ArtifactScan.objects.get(project=self.project)
        self.assertEqual(scan.scan_type, ArtifactScanType.CONTAINER_IMAGE)
        self.assertEqual(scan.status, ArtifactScanStatus.BLOCKED)

    def test_operator_override_records_reason_and_audit_log(self):
        self.post_static_zip({"malware.js": "bad"})
        scan = ArtifactScan.objects.get(project=self.project)
        self.login_as(self.operator)

        response = self.client.post(
            reverse("operator-artifact-scan-override", kwargs={"scan_public_id": scan.public_id}),
            data={"reason": "False positive verified in isolated sandbox"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf(),
        )

        self.assertEqual(response.status_code, 200)
        scan.refresh_from_db()
        self.assertEqual(scan.status, ArtifactScanStatus.OVERRIDDEN)
        self.assertEqual(scan.overridden_by_user, self.operator)
        self.assertIn("False positive", scan.override_reason)
        self.assertTrue(AuditLog.objects.filter(action=audit_log.AuditAction.ARTIFACT_SCAN_OVERRIDE, project=self.project).exists())

    def test_override_requires_operator_2fa_and_reason(self):
        self.post_static_zip({"malware.js": "bad"})
        scan = ArtifactScan.objects.get(project=self.project)

        self.login_as(self.developer)
        response = self.client.post(
            reverse("operator-artifact-scan-override", kwargs={"scan_public_id": scan.public_id}),
            data={"reason": "nope"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf(),
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "operator_required")

        self.login_as(self.operator_without_2fa)
        response = self.client.post(
            reverse("operator-artifact-scan-override", kwargs={"scan_public_id": scan.public_id}),
            data={"reason": "nope"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf(),
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "operator_2fa_required")

        self.login_as(self.operator)
        response = self.client.post(
            reverse("operator-artifact-scan-override", kwargs={"scan_public_id": scan.public_id}),
            data={"reason": ""},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "reason_required")

    def test_user_from_organization_a_cannot_see_scan_results_for_organization_b(self):
        ArtifactScan.objects.create(
            organization=self.other_org,
            project=self.other_project,
            environment=self.other_environment,
            scan_type=ArtifactScanType.STATIC_ZIP,
            artifact_ref="static-upload:other.zip",
            status=ArtifactScanStatus.BLOCKED,
            critical_count=1,
        )
        self.login_as(self.developer)

        response = self.client.get(
            reverse(
                "project-artifact-scan-list",
                kwargs={
                    "organization_public_id": self.other_org.public_id,
                    "project_public_id": self.other_project.public_id,
                },
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_project_user_can_list_own_scan_results_without_sensitive_refs(self):
        self.post_static_zip({"index.html": "ok"})
        self.login_as(self.developer)

        response = self.client.get(
            reverse(
                "project-artifact-scan-list",
                kwargs={
                    "organization_public_id": self.org.public_id,
                    "project_public_id": self.project.public_id,
                },
            )
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()["results"][0]
        self.assertNotIn("report_ref", result)
        self.assertNotIn("sbom_ref", result)
        self.assertEqual(result["project_id"], str(self.project.public_id))
