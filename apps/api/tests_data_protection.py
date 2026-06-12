import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.api import data_protection, secrets
from apps.api.models import (
    AuditLog,
    DataDeletionRequest,
    DataDeletionStatus,
    DataExportRequest,
    DataExportStatus,
    Environment,
    EnvironmentType,
    Organization,
    OrganizationMember,
    OrganizationMemberStatus,
    OrganizationStatus,
    Project,
    ProjectStatus,
    Role,
    RoleScope,
    User,
)
from apps.api.rbac import ROLE_OWNER, ROLE_VIEWER


class DataProtectionTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.export_root = Path(self.temp_dir.name) / "exports"
        self.deployment_root = Path(self.temp_dir.name) / "deployments"
        self.owner = User.objects.create_user(email="owner@example.com", password="secret", full_name="Owner")
        self.viewer = User.objects.create_user(email="viewer@example.com", password="secret")
        self.outsider = User.objects.create_user(email="outsider@example.com", password="secret")
        self.owner_role = Role.objects.create(scope=RoleScope.ORGANIZATION, key=ROLE_OWNER, name="Owner")
        self.viewer_role = Role.objects.create(scope=RoleScope.ORGANIZATION, key=ROLE_VIEWER, name="Viewer")
        self.org = Organization.objects.create(name="Acme", slug="acme", owner_user=self.owner, billing_email="billing@acme.test")
        self.other_org = Organization.objects.create(name="Other", slug="other", owner_user=self.outsider)
        OrganizationMember.objects.create(organization=self.org, user=self.owner, role=self.owner_role, status=OrganizationMemberStatus.ACTIVE)
        OrganizationMember.objects.create(organization=self.org, user=self.viewer, role=self.viewer_role, status=OrganizationMemberStatus.ACTIVE)
        OrganizationMember.objects.create(organization=self.other_org, user=self.outsider, role=self.owner_role, status=OrganizationMemberStatus.ACTIVE)
        self.project = Project.objects.create(organization=self.org, name="App", slug="app", created_by_user=self.owner)
        self.other_project = Project.objects.create(organization=self.other_org, name="Other App", slug="other-app", created_by_user=self.outsider)
        self.environment = self.create_environment(self.org, self.project, "production")
        self.other_environment = self.create_environment(self.other_org, self.other_project, "production")
        secrets.create_secret(
            organization=self.org,
            project=self.project,
            environment=self.environment,
            name="DATABASE_URL",
            value="postgres://plaintext-secret",
            actor=self.owner,
            metadata={"note": "safe", "secret": "metadata-secret"},
        )

    def create_environment(self, organization, project, slug):
        return Environment.objects.create(
            organization=organization,
            project=project,
            name=slug.title(),
            slug=slug,
            type=EnvironmentType.PRODUCTION,
            kubernetes_namespace=f"{organization.slug}-{project.slug}-{slug}",
        )

    def csrf(self):
        self.client.get(reverse("auth-csrf"))
        return self.client.cookies["csrftoken"].value

    def login(self, user):
        self.client.force_login(user)

    def post_json(self, url):
        return self.client.post(url, data=json.dumps({}), content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf())

    def read_export_zip(self, export):
        with zipfile.ZipFile(export.file_path) as archive:
            return {name: json.loads(archive.read(name).decode("utf-8")) for name in archive.namelist()}

    @override_settings(DATA_EXPORT_URL_TTL_SECONDS=3600)
    def test_user_exports_own_data(self):
        with override_settings(DATA_EXPORT_STORAGE_ROOT=str(self.export_root)):
            self.login(self.owner)
            response = self.post_json(reverse("data-export-user"))

        self.assertEqual(response.status_code, 202)
        export = DataExportRequest.objects.get(scope="user")
        self.assertEqual(export.status, DataExportStatus.COMPLETED)
        payload = self.read_export_zip(export)
        self.assertEqual(payload["user.json"]["email"], "owner@example.com")
        self.assertNotIn("outsider@example.com", json.dumps(payload))
        self.assertTrue(AuditLog.objects.filter(action="data_export.requested", actor_user=self.owner).exists())

    def test_owner_exports_organization_data_without_plaintext_secrets_or_other_tenant_data(self):
        with override_settings(DATA_EXPORT_STORAGE_ROOT=str(self.export_root)):
            self.login(self.owner)
            response = self.post_json(reverse("data-export-organization", kwargs={"organization_public_id": self.org.public_id}))

        self.assertEqual(response.status_code, 202)
        export = DataExportRequest.objects.get(scope="organization")
        payload = self.read_export_zip(export)
        blob = json.dumps(payload)
        self.assertIn("Acme", blob)
        self.assertIn("DATABASE_URL", blob)
        self.assertNotIn("postgres://plaintext-secret", blob)
        self.assertNotIn("metadata-secret", blob)
        self.assertNotIn(str(self.other_org.public_id), blob)
        self.assertNotIn("Other App", blob)

    def test_user_from_organization_a_cannot_export_organization_b(self):
        with override_settings(DATA_EXPORT_STORAGE_ROOT=str(self.export_root)):
            self.login(self.owner)
            response = self.post_json(reverse("data-export-organization", kwargs={"organization_public_id": self.other_org.public_id}))

        self.assertEqual(response.status_code, 404)
        self.assertFalse(DataExportRequest.objects.filter(organization=self.other_org).exists())

    def test_export_download_link_is_temporal_and_bound_to_requester(self):
        with override_settings(DATA_EXPORT_STORAGE_ROOT=str(self.export_root)):
            self.login(self.owner)
            create_response = self.post_json(reverse("data-export-user"))
            export = DataExportRequest.objects.get(scope="user")

            valid_response = self.client.get(create_response.json()["download_url"])
            invalid_response = self.client.get(reverse("data-export-download", kwargs={"export_public_id": export.public_id}) + "?token=wrong")
            self.client.force_login(self.outsider)
            outsider_response = self.client.get(create_response.json()["download_url"])
            valid_response.close()

        self.assertEqual(valid_response.status_code, 200)
        self.assertEqual(invalid_response.status_code, 403)
        self.assertEqual(outsider_response.status_code, 404)

    def test_user_deletion_soft_deletes_account_and_audits_request(self):
        self.login(self.viewer)
        response = self.post_json(reverse("data-delete-user"))

        self.assertEqual(response.status_code, 202)
        self.viewer.refresh_from_db()
        self.assertFalse(self.viewer.is_active)
        self.assertIsNotNone(self.viewer.deleted_at)
        self.assertTrue(DataDeletionRequest.objects.filter(target_user=self.viewer, status=DataDeletionStatus.SOFT_DELETED).exists())
        self.assertTrue(AuditLog.objects.filter(action="data_deletion.requested", actor_user=self.viewer).exists())

    @override_settings(DATA_DELETION_RETENTION_DAYS=0)
    def test_organization_soft_delete_and_retention_hard_delete_storage_and_project_data(self):
        org_storage = self.deployment_root / str(self.org.public_id) / str(self.project.public_id)
        org_storage.mkdir(parents=True)
        (org_storage / "index.html").write_text("ok", encoding="utf-8")

        with override_settings(STATIC_DEPLOYMENT_LOCAL_ROOT=str(self.deployment_root)):
            self.login(self.owner)
            response = self.post_json(reverse("data-delete-organization", kwargs={"organization_public_id": self.org.public_id}))
            self.assertEqual(response.status_code, 202)
            self.org.refresh_from_db()
            self.project.refresh_from_db()
            self.assertEqual(self.org.status, OrganizationStatus.PENDING_DELETION)
            self.assertEqual(self.project.status, ProjectStatus.PENDING_DELETION)
            self.assertTrue(org_storage.exists())

            deletion = DataDeletionRequest.objects.get(organization=self.org)
            deletion.retention_until = timezone.now()
            deletion.save(update_fields=["retention_until", "updated_at"])
            finalized = data_protection.finalize_expired_deletions()

        self.assertEqual(len(finalized), 1)
        self.assertFalse(Organization.objects.filter(public_id=self.org.public_id).exists())
        self.assertFalse(Project.objects.filter(public_id=self.project.public_id).exists())
        self.assertFalse(org_storage.exists())

    def tearDown(self):
        shutil.rmtree(self.export_root, ignore_errors=True)
        shutil.rmtree(self.deployment_root, ignore_errors=True)
