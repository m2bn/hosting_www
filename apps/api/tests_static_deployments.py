import io
import shutil
import zipfile
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.api import audit_log
from apps.api.models import (
    AuditLog,
    Deployment,
    DeploymentStatus,
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
    UsageMetric,
    UsageRecord,
    User,
)
from apps.api.rbac import ROLE_ADMIN, ROLE_BILLING, ROLE_DEVELOPER, ROLE_OWNER, ROLE_VIEWER


@override_settings(
    STATIC_DEPLOYMENT_MAX_ZIP_BYTES=1024 * 1024,
    STATIC_DEPLOYMENT_MAX_FILES=5,
    STATIC_DEPLOYMENT_MAX_UNPACKED_BYTES=1024,
    STATIC_DEPLOYMENT_LOCAL_ROOT="outputs/test-static-deployments",
)
class StaticDeploymentTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.roles = {
            key: Role.objects.create(scope=RoleScope.ORGANIZATION, key=key, name=key.title())
            for key in [ROLE_OWNER, ROLE_ADMIN, ROLE_DEVELOPER, ROLE_BILLING, ROLE_VIEWER]
        }
        self.users = {key: User.objects.create_user(email=f"{key}@example.com", password="secret") for key in self.roles}
        self.outsider = User.objects.create_user(email="outsider@example.com", password="secret")
        self.org = Organization.objects.create(name="Acme", slug="acme", owner_user=self.users[ROLE_OWNER])
        self.other_org = Organization.objects.create(name="Other", slug="other", owner_user=self.outsider)
        for role_key, user in self.users.items():
            OrganizationMember.objects.create(
                organization=self.org,
                user=user,
                role=self.roles[role_key],
                status=OrganizationMemberStatus.ACTIVE,
            )
        OrganizationMember.objects.create(
            organization=self.other_org,
            user=self.outsider,
            role=self.roles[ROLE_OWNER],
            status=OrganizationMemberStatus.ACTIVE,
        )
        plan = Plan.objects.create(
            key="static-pro",
            name="Static Pro",
            limits={"projects": 10, "storage_gb": 1, "transfer_gb": 100},
            features={"custom_domains": True, "container_deployments": False},
        )
        Subscription.objects.create(organization=self.org, plan=plan, status=SubscriptionStatus.ACTIVE)
        Subscription.objects.create(organization=self.other_org, plan=plan, status=SubscriptionStatus.ACTIVE)
        self.project = Project.objects.create(organization=self.org, name="App", slug="app", created_by_user=self.users[ROLE_OWNER])
        self.environment = Environment.objects.create(
            organization=self.org,
            project=self.project,
            name="Production",
            slug="production",
            type=EnvironmentType.PRODUCTION,
            kubernetes_namespace="acme-app-production",
        )
        self.other_project = Project.objects.create(
            organization=self.other_org,
            name="Other",
            slug="other",
            created_by_user=self.outsider,
        )
        self.other_environment = Environment.objects.create(
            organization=self.other_org,
            project=self.other_project,
            name="Production",
            slug="production",
            type=EnvironmentType.PRODUCTION,
            kubernetes_namespace="other-app-production",
        )

    def tearDown(self):
        shutil.rmtree("outputs/test-static-deployments", ignore_errors=True)

    def csrf(self):
        self.client.get(reverse("auth-csrf"))
        return self.client.cookies["csrftoken"].value

    def login_as(self, role_key):
        self.client.force_login(self.users[role_key])

    def zip_bytes(self, files):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, content in files.items():
                if isinstance(content, zipfile.ZipInfo):
                    archive.writestr(content, "")
                else:
                    archive.writestr(name, content)
        return buffer.getvalue()

    def upload(self, role_key=ROLE_DEVELOPER, files=None, content=None, name="site.zip", organization=None, project=None, environment=None):
        self.login_as(role_key)
        payload = content if content is not None else self.zip_bytes(files or {"index.html": "<h1>Hello</h1>"})
        uploaded = SimpleUploadedFile(name, payload, content_type="application/zip")
        return self.client.post(
            reverse(
                "static-deployment-create",
                kwargs={
                    "organization_public_id": (organization or self.org).public_id,
                    "project_public_id": (project or self.project).public_id,
                    "environment_public_id": (environment or self.environment).public_id,
                },
            ),
            data={"file": uploaded},
            HTTP_X_CSRFTOKEN=self.csrf(),
        )

    def test_valid_zip_creates_static_deployment(self):
        response = self.upload(files={"index.html": "<h1>Hello</h1>", "assets/app.js": "console.log('ok')"})

        self.assertEqual(response.status_code, 201)
        deployment = Deployment.objects.get(public_id=response.json()["public_id"])
        self.assertEqual(deployment.status, DeploymentStatus.RUNNING)
        self.assertTrue(Path(deployment.image_ref, "manifest.json").exists())
        self.assertTrue(AuditLog.objects.filter(action=audit_log.AuditAction.DEPLOYMENT_ACTIVATED, project=self.project).exists())
        self.assertTrue(UsageRecord.objects.filter(project=self.project, metric=UsageMetric.STORAGE_GB_HOURS).exists())

    def test_zip_slip_is_rejected(self):
        response = self.upload(files={"../evil.html": "owned"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "zip_slip")

    def test_symlink_is_rejected(self):
        info = zipfile.ZipInfo("link.html")
        info.external_attr = 0o120777 << 16

        response = self.upload(files={"link.html": info})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "symlink_not_allowed")

    @override_settings(STATIC_DEPLOYMENT_MAX_ZIP_BYTES=100)
    def test_zip_size_limit_is_enforced(self):
        response = self.upload(content=b"PK" + b"x" * 200)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "zip_too_large")

    def test_file_count_limit_is_enforced(self):
        files = {f"{idx}.html": "x" for idx in range(6)}

        response = self.upload(files=files)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "too_many_files")

    def test_unpacked_size_limit_is_enforced(self):
        response = self.upload(files={"index.html": "x" * 2048})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "unpacked_too_large")

    def test_storage_limit_is_enforced(self):
        now = timezone.now()
        UsageRecord.objects.create(
            organization=self.org,
            project=self.project,
            environment=self.environment,
            metric=UsageMetric.STORAGE_GB_HOURS,
            quantity=Decimal("1"),
            unit="gb",
            period_start=now,
            period_end=now + timedelta(seconds=1),
            source="test",
        )

        response = self.upload()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "storage_limit_exceeded")

    def test_rollback_switches_active_deployment(self):
        first_response = self.upload(files={"index.html": "v1"})
        second_response = self.upload(files={"index.html": "v2"})
        first = Deployment.objects.get(public_id=first_response.json()["public_id"])
        second = Deployment.objects.get(public_id=second_response.json()["public_id"])
        self.assertEqual(second.status, DeploymentStatus.RUNNING)
        first.refresh_from_db()
        self.assertEqual(first.status, DeploymentStatus.ROLLED_BACK)

        response = self.client.post(
            reverse(
                "static-deployment-rollback",
                kwargs={
                    "organization_public_id": self.org.public_id,
                    "project_public_id": self.project.public_id,
                    "environment_public_id": self.environment.public_id,
                    "deployment_public_id": first.public_id,
                },
            ),
            HTTP_X_CSRFTOKEN=self.csrf(),
        )

        self.assertEqual(response.status_code, 200)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, DeploymentStatus.RUNNING)
        self.assertEqual(second.status, DeploymentStatus.ROLLED_BACK)
        self.assertTrue(AuditLog.objects.filter(action=audit_log.AuditAction.DEPLOYMENT_ROLLED_BACK, project=self.project).exists())

    def test_user_from_org_a_cannot_deploy_to_project_b(self):
        response = self.upload(organization=self.org, project=self.other_project, environment=self.other_environment)

        self.assertEqual(response.status_code, 404)

    def test_viewer_cannot_deploy(self):
        response = self.upload(role_key=ROLE_VIEWER)

        self.assertEqual(response.status_code, 403)

    def test_billing_cannot_deploy(self):
        response = self.upload(role_key=ROLE_BILLING)

        self.assertEqual(response.status_code, 403)
