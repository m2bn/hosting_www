import json
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from apps.api import secrets
from apps.api.models import (
    AuditLog,
    Environment,
    EnvironmentType,
    Organization,
    OrganizationMember,
    OrganizationMemberStatus,
    Project,
    ProjectSecret,
    ProjectSecretVersion,
    Role,
    RoleScope,
    User,
)
from apps.api.rbac import ROLE_DEVELOPER, ROLE_OWNER, ROLE_VIEWER


class ProjectSecretTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.owner = User.objects.create_user(email="owner@example.com", password="secret")
        self.developer = User.objects.create_user(email="developer@example.com", password="secret")
        self.viewer = User.objects.create_user(email="viewer@example.com", password="secret")
        self.owner_role = Role.objects.create(scope=RoleScope.ORGANIZATION, key=ROLE_OWNER, name="Owner")
        self.developer_role = Role.objects.create(scope=RoleScope.ORGANIZATION, key=ROLE_DEVELOPER, name="Developer")
        self.viewer_role = Role.objects.create(scope=RoleScope.ORGANIZATION, key=ROLE_VIEWER, name="Viewer")
        self.org = Organization.objects.create(name="Acme", slug="acme", owner_user=self.owner)
        for user, role in [(self.owner, self.owner_role), (self.developer, self.developer_role), (self.viewer, self.viewer_role)]:
            OrganizationMember.objects.create(
                organization=self.org,
                user=user,
                role=role,
                status=OrganizationMemberStatus.ACTIVE,
            )
        self.project = Project.objects.create(
            organization=self.org,
            name="App",
            slug="app",
            created_by_user=self.owner,
        )
        self.other_project = Project.objects.create(
            organization=self.org,
            name="Other App",
            slug="other-app",
            created_by_user=self.owner,
        )
        self.environment = self.create_environment(self.project, "production")
        self.other_environment = self.create_environment(self.other_project, "production-other")

    def create_environment(self, project, slug):
        return Environment.objects.create(
            organization=self.org,
            project=project,
            name=slug.title(),
            slug=slug,
            type=EnvironmentType.PRODUCTION,
            kubernetes_namespace=f"{self.org.slug}-{project.slug}-{slug}",
        )

    def csrf(self):
        self.client.get(reverse("auth-csrf"))
        return self.client.cookies["csrftoken"].value

    def login(self, user):
        self.client.force_login(user)

    def secret_list_url(self, project=None, environment=None):
        return reverse(
            "project-secret-list",
            kwargs={
                "organization_public_id": self.org.public_id,
                "project_public_id": (project or self.project).public_id,
                "environment_public_id": (environment or self.environment).public_id,
            },
        )

    def secret_detail_url(self, secret, project=None, environment=None):
        return reverse(
            "project-secret-detail",
            kwargs={
                "organization_public_id": self.org.public_id,
                "project_public_id": (project or self.project).public_id,
                "environment_public_id": (environment or self.environment).public_id,
                "secret_public_id": secret.public_id,
            },
        )

    def secret_rotate_url(self, secret, project=None, environment=None):
        return reverse(
            "project-secret-rotate",
            kwargs={
                "organization_public_id": self.org.public_id,
                "project_public_id": (project or self.project).public_id,
                "environment_public_id": (environment or self.environment).public_id,
                "secret_public_id": secret.public_id,
            },
        )

    def post_secret(self, payload, user=None):
        self.login(user or self.owner)
        return self.client.post(
            self.secret_list_url(),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf(),
        )

    def test_secret_is_not_stored_as_plaintext(self):
        response = self.post_secret({"name": "DATABASE_URL", "value": "postgres://secret", "metadata": {"owner": "app"}})

        self.assertEqual(response.status_code, 201)
        secret = ProjectSecret.objects.get(name="DATABASE_URL")
        version = secret.versions.get(version=1)
        self.assertNotEqual(version.encrypted_value, "postgres://secret")
        self.assertEqual(secrets.decrypt_value(version.encrypted_value), "postgres://secret")

    def test_secret_value_is_never_returned_by_api(self):
        create_response = self.post_secret({"name": "API_TOKEN", "value": "super-secret"})
        secret = ProjectSecret.objects.get(name="API_TOKEN")

        list_response = self.client.get(self.secret_list_url())
        patch_response = self.client.patch(
            self.secret_detail_url(secret),
            data=json.dumps({"metadata": {"team": "platform"}}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf(),
        )

        self.assertNotIn("value", create_response.json())
        self.assertNotIn("super-secret", json.dumps(create_response.json()))
        self.assertNotIn("super-secret", json.dumps(list_response.json()))
        self.assertNotIn("super-secret", json.dumps(patch_response.json()))

    def test_secret_from_project_a_is_not_accessible_through_project_b(self):
        self.post_secret({"name": "SHARED_NAME", "value": "project-a-secret"})
        secret = ProjectSecret.objects.get(name="SHARED_NAME")

        response = self.client.get(self.secret_list_url(project=self.other_project, environment=self.other_environment))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])
        delete_response = self.client.delete(
            self.secret_detail_url(secret, project=self.other_project, environment=self.other_environment),
            HTTP_X_CSRFTOKEN=self.csrf(),
        )
        self.assertEqual(delete_response.status_code, 404)

    def test_viewer_cannot_create_secret(self):
        response = self.post_secret({"name": "BLOCKED_SECRET", "value": "nope"}, user=self.viewer)

        self.assertEqual(response.status_code, 403)

    def test_developer_can_create_secret(self):
        response = self.post_secret({"name": "DEVELOPER_SECRET", "value": "ok"}, user=self.developer)

        self.assertEqual(response.status_code, 201)

    def test_secret_values_do_not_appear_in_audit_log_metadata(self):
        raw_value = "top-secret-value"
        self.post_secret({"name": "AUDIT_SECRET", "value": raw_value, "metadata": {"secret": raw_value, "note": "safe"}})

        metadata_blob = json.dumps(list(AuditLog.objects.values_list("metadata", flat=True)))

        self.assertNotIn(raw_value, metadata_blob)
        self.assertIn("AUDIT_SECRET", metadata_blob)

    def test_secret_values_do_not_appear_in_application_logs(self):
        raw_value = "log-sensitive-value"
        with patch("apps.api.secrets.logger") as logger:
            response = self.post_secret({"name": "LOG_SECRET", "value": raw_value})

        self.assertEqual(response.status_code, 201)
        self.assertNotIn(raw_value, str(logger.method_calls))

    def test_rotation_creates_new_version(self):
        self.post_secret({"name": "ROTATED_SECRET", "value": "v1"})
        secret = ProjectSecret.objects.get(name="ROTATED_SECRET")

        response = self.client.post(
            self.secret_rotate_url(secret),
            data=json.dumps({"value": "v2"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf(),
        )

        self.assertEqual(response.status_code, 200)
        secret.refresh_from_db()
        self.assertEqual(secret.current_version, 2)
        self.assertEqual(ProjectSecretVersion.objects.filter(secret=secret).count(), 2)
        newest = secret.versions.order_by("-version").first()
        self.assertEqual(secrets.decrypt_value(newest.encrypted_value), "v2")

    def test_runtime_injection_is_scoped_to_project_and_environment(self):
        self.post_secret({"name": "ONLY_APP", "value": "project-a"})
        secrets.create_secret(
            organization=self.org,
            project=self.other_project,
            environment=self.other_environment,
            name="ONLY_OTHER",
            value="project-b",
            actor=self.owner,
        )

        values = secrets.runtime_secret_values_for_project(self.project, self.environment)

        self.assertEqual(values, {"ONLY_APP": "project-a"})
        self.assertNotIn("ONLY_OTHER", values)
