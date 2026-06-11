import json
from datetime import timedelta

from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from apps.api import audit_log
from apps.api.api_key_authentication import ApiKeyAuthentication
from apps.api.api_keys import create_api_key
from apps.api.models import AuditLog, ApiKey, ApiKeyStatus, Organization, OrganizationMember, OrganizationMemberStatus, Project, Role, RoleScope, User
from apps.api.permissions import CanManageProjects, CanViewProject
from apps.api.rbac import ROLE_OWNER, ROLE_VIEWER, PermissionKey
from apps.api.tenancy import get_object_for_organization_or_404, get_organization_from_request


class ApiKeyProjectReadView(APIView):
    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [CanViewProject]

    def get(self, request, organization_public_id, project_public_id):
        organization = get_organization_from_request(request, self)
        project = get_object_for_organization_or_404(Project, organization, public_id=project_public_id, deleted_at__isnull=True)
        self.check_object_permissions(request, project)
        return Response({"slug": project.slug})


class ApiKeyProjectManageView(APIView):
    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [CanManageProjects]

    def post(self, request, organization_public_id, project_public_id):
        organization = get_organization_from_request(request, self)
        project = get_object_for_organization_or_404(Project, organization, public_id=project_public_id, deleted_at__isnull=True)
        self.check_object_permissions(request, project)
        return Response({"managed": project.slug})


class ApiKeyTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.factory = APIRequestFactory()
        self.owner = User.objects.create_user(email="owner@example.com", password="secret")
        self.viewer = User.objects.create_user(email="viewer@example.com", password="secret")
        self.outsider = User.objects.create_user(email="outsider@example.com", password="secret")
        self.owner_role = Role.objects.create(scope=RoleScope.ORGANIZATION, key=ROLE_OWNER, name="Owner")
        self.viewer_role = Role.objects.create(scope=RoleScope.ORGANIZATION, key=ROLE_VIEWER, name="Viewer")
        self.org = Organization.objects.create(name="Acme", slug="acme", owner_user=self.owner)
        self.other_org = Organization.objects.create(name="Other", slug="other", owner_user=self.outsider)
        OrganizationMember.objects.create(
            organization=self.org,
            user=self.owner,
            role=self.owner_role,
            status=OrganizationMemberStatus.ACTIVE,
        )
        OrganizationMember.objects.create(
            organization=self.org,
            user=self.viewer,
            role=self.viewer_role,
            status=OrganizationMemberStatus.ACTIVE,
        )
        OrganizationMember.objects.create(
            organization=self.other_org,
            user=self.outsider,
            role=self.owner_role,
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
        self.foreign_project = Project.objects.create(
            organization=self.other_org,
            name="Foreign App",
            slug="foreign-app",
            created_by_user=self.outsider,
        )

    def csrf(self):
        self.client.get(reverse("auth-csrf"))
        return self.client.cookies["csrftoken"].value

    def post_json(self, path_name, kwargs, payload):
        return self.client.post(
            reverse(path_name, kwargs=kwargs),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf(),
        )

    def create_project_key(self, scopes=None, user=None, project=None, expires_at=None):
        return create_api_key(
            organization=self.org,
            project=project or self.project,
            created_by_user=user or self.owner,
            name="Project key",
            scopes=scopes or [PermissionKey.PROJECT_VIEW],
            expires_at=expires_at,
        )

    def api_request(self, view_cls, raw_key, organization, project, method="get"):
        request = getattr(self.factory, method)("/", HTTP_AUTHORIZATION=f"Bearer {raw_key}")
        return view_cls.as_view()(request, organization_public_id=organization.public_id, project_public_id=project.public_id)

    def test_full_key_is_visible_only_once_after_creation(self):
        self.client.force_login(self.owner)

        response = self.post_json(
            "project-api-key-list",
            {"organization_public_id": self.org.public_id, "project_public_id": self.project.public_id},
            {"name": "CI", "scopes": [PermissionKey.PROJECT_VIEW]},
        )

        self.assertEqual(response.status_code, 201)
        raw_key = response.json()["key"]
        api_key = ApiKey.objects.get(prefix=response.json()["prefix"])
        self.assertNotEqual(api_key.key_hash, raw_key)
        self.assertTrue(api_key.check_key(raw_key))

        list_response = self.client.get(
            reverse(
                "project-api-key-list",
                kwargs={"organization_public_id": self.org.public_id, "project_public_id": self.project.public_id},
            )
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertNotIn("key", list_response.json()["results"][0])
        self.assertTrue(AuditLog.objects.filter(action=audit_log.AuditAction.API_KEY_CREATED, organization=self.org).exists())

    def test_key_works_for_correct_project(self):
        _, raw_key = self.create_project_key()

        response = self.api_request(ApiKeyProjectReadView, raw_key, self.org, self.project)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["slug"], self.project.slug)
        api_key = ApiKey.objects.get(prefix=raw_key.split(".", 1)[0])
        self.assertIsNotNone(api_key.last_used_at)

    def test_project_key_does_not_work_for_another_project(self):
        _, raw_key = self.create_project_key()

        response = self.api_request(ApiKeyProjectReadView, raw_key, self.org, self.other_project)

        self.assertEqual(response.status_code, 403)

    def test_organization_key_does_not_work_for_another_organization(self):
        _, raw_key = create_api_key(
            organization=self.org,
            created_by_user=self.owner,
            name="Org key",
            scopes=[PermissionKey.PROJECT_VIEW],
        )

        response = self.api_request(ApiKeyProjectReadView, raw_key, self.other_org, self.foreign_project)

        self.assertEqual(response.status_code, 403)

    def test_revoked_key_does_not_work(self):
        api_key, raw_key = self.create_project_key()
        api_key.status = ApiKeyStatus.REVOKED
        api_key.revoked_at = timezone.now()
        api_key.save(update_fields=["status", "revoked_at", "updated_at"])

        response = self.api_request(ApiKeyProjectReadView, raw_key, self.org, self.project)

        self.assertEqual(response.status_code, 403)

    def test_expired_key_does_not_work(self):
        _, raw_key = self.create_project_key(expires_at=timezone.now() - timedelta(minutes=1))

        response = self.api_request(ApiKeyProjectReadView, raw_key, self.org, self.project)

        self.assertEqual(response.status_code, 403)

    def test_scope_is_required(self):
        _, raw_key = self.create_project_key(scopes=["logs.read"])

        response = self.api_request(ApiKeyProjectReadView, raw_key, self.org, self.project)

        self.assertEqual(response.status_code, 403)

    def test_api_key_does_not_bypass_user_rbac(self):
        _, raw_key = self.create_project_key(scopes=[PermissionKey.PROJECT_MANAGE], user=self.viewer)

        response = self.api_request(ApiKeyProjectManageView, raw_key, self.org, self.project, method="post")

        self.assertEqual(response.status_code, 403)

    def test_rotation_returns_new_key_and_invalidates_old_key(self):
        api_key, old_raw_key = self.create_project_key()
        self.client.force_login(self.owner)

        response = self.post_json(
            "api-key-rotate",
            {"organization_public_id": self.org.public_id, "api_key_public_id": api_key.public_id},
            {},
        )

        self.assertEqual(response.status_code, 200)
        new_raw_key = response.json()["key"]
        self.assertNotEqual(new_raw_key, old_raw_key)
        self.assertEqual(self.api_request(ApiKeyProjectReadView, old_raw_key, self.org, self.project).status_code, 403)
        self.assertEqual(self.api_request(ApiKeyProjectReadView, new_raw_key, self.org, self.project).status_code, 200)
        self.assertTrue(AuditLog.objects.filter(action=audit_log.AuditAction.API_KEY_ROTATED, organization=self.org).exists())

    def test_revoke_invalidates_key(self):
        api_key, raw_key = self.create_project_key()
        self.client.force_login(self.owner)

        response = self.post_json(
            "api-key-revoke",
            {"organization_public_id": self.org.public_id, "api_key_public_id": api_key.public_id},
            {},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.api_request(ApiKeyProjectReadView, raw_key, self.org, self.project).status_code, 403)
        self.assertTrue(AuditLog.objects.filter(action=audit_log.AuditAction.API_KEY_DELETED, organization=self.org).exists())

    @override_settings(API_KEY_RATE_LIMIT_ATTEMPTS=1, API_KEY_RATE_LIMIT_WINDOW_SECONDS=60)
    def test_rate_limiting_per_key(self):
        _, raw_key = self.create_project_key()

        first_response = self.api_request(ApiKeyProjectReadView, raw_key, self.org, self.project)
        second_response = self.api_request(ApiKeyProjectReadView, raw_key, self.org, self.project)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 429)

    def test_high_risk_api_key_use_is_audited(self):
        _, raw_key = self.create_project_key(scopes=[PermissionKey.PROJECT_MANAGE])

        response = self.api_request(ApiKeyProjectManageView, raw_key, self.org, self.project, method="post")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(AuditLog.objects.filter(action=audit_log.AuditAction.API_KEY_USED_HIGH_RISK, organization=self.org).exists())
