from types import SimpleNamespace

from django.test import TestCase
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from apps.api.models import (
    Environment,
    Organization,
    OrganizationMember,
    OrganizationMemberStatus,
    Project,
    Role,
    RoleScope,
    User,
)
from apps.api.permissions import (
    CanDeployProject,
    CanManageBilling,
    CanManageProjects,
    CanViewProject,
    HasOrganizationPermission,
    HasOrganizationRole,
    IsOrganizationMember,
)
from apps.api.rbac import (
    ROLE_ADMIN,
    ROLE_BILLING,
    ROLE_DEVELOPER,
    ROLE_OWNER,
    ROLE_VIEWER,
    PermissionKey,
    user_has_permission,
    user_has_role,
)
from apps.api.tenancy import (
    get_object_for_organization_or_404,
    get_organization_from_request,
    require_organization_membership,
)


class ProjectProbeView(APIView):
    permission_classes = [CanViewProject]

    def get(self, request, organization_public_id, project_public_id):
        organization = get_organization_from_request(request, self)
        project = get_object_for_organization_or_404(
            Project,
            organization,
            public_id=project_public_id,
            deleted_at__isnull=True,
        )
        self.check_object_permissions(request, project)
        return Response({"slug": project.slug})


class AuthorizationTestCase(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.roles = {
            key: Role.objects.create(scope=RoleScope.ORGANIZATION, key=key, name=key.title())
            for key in [ROLE_OWNER, ROLE_ADMIN, ROLE_DEVELOPER, ROLE_BILLING, ROLE_VIEWER]
        }
        self.users = {
            key: User.objects.create_user(email=f"{key}@example.com", password="secret")
            for key in self.roles
        }
        self.outsider = User.objects.create_user(email="outsider@example.com", password="secret")
        self.org = Organization.objects.create(
            name="Acme",
            slug="acme",
            owner_user=self.users[ROLE_OWNER],
        )
        self.other_org = Organization.objects.create(
            name="Other",
            slug="other",
            owner_user=self.outsider,
        )
        self.project = Project.objects.create(
            organization=self.org,
            name="Website",
            slug="website",
            created_by_user=self.users[ROLE_OWNER],
        )
        self.environment = Environment.objects.create(
            organization=self.org,
            project=self.project,
            name="Production",
            slug="production",
            kubernetes_namespace="acme-website-production",
        )
        self.other_project = Project.objects.create(
            organization=self.other_org,
            name="Other Website",
            slug="other-website",
            created_by_user=self.outsider,
        )
        Environment.objects.create(
            organization=self.other_org,
            project=self.other_project,
            name="Production",
            slug="production",
            kubernetes_namespace="other-website-production",
        )

        for role_key, user in self.users.items():
            OrganizationMember.objects.create(
                organization=self.org,
                user=user,
                role=self.roles[role_key],
                status=OrganizationMemberStatus.ACTIVE,
            )

    def make_request(self, user, organization=None):
        request = self.factory.get("/")
        force_authenticate(request, user=user)
        request.user = user
        view = SimpleNamespace(
            kwargs={"organization_public_id": organization.public_id if organization else self.org.public_id},
            action=None,
        )
        return request, view

    def assert_permission_matrix(self, permission_class, expected_by_role):
        for role_key, expected in expected_by_role.items():
            request, view = self.make_request(self.users[role_key])
            result = permission_class().has_permission(request, view)
            self.assertEqual(result, expected, f"{permission_class.__name__} mismatch for {role_key}")

    def test_is_organization_member_allows_active_members_only(self):
        self.assert_permission_matrix(
            IsOrganizationMember,
            {
                ROLE_OWNER: True,
                ROLE_ADMIN: True,
                ROLE_DEVELOPER: True,
                ROLE_BILLING: True,
                ROLE_VIEWER: True,
            },
        )

        request, view = self.make_request(self.outsider)
        self.assertFalse(IsOrganizationMember().has_permission(request, view))

    def test_role_mapping_for_owner_admin_developer_billing_viewer(self):
        self.assert_permission_matrix(
            CanManageBilling,
            {
                ROLE_OWNER: True,
                ROLE_ADMIN: False,
                ROLE_DEVELOPER: False,
                ROLE_BILLING: True,
                ROLE_VIEWER: False,
            },
        )
        self.assert_permission_matrix(
            CanManageProjects,
            {
                ROLE_OWNER: True,
                ROLE_ADMIN: True,
                ROLE_DEVELOPER: False,
                ROLE_BILLING: False,
                ROLE_VIEWER: False,
            },
        )
        self.assert_permission_matrix(
            CanDeployProject,
            {
                ROLE_OWNER: True,
                ROLE_ADMIN: True,
                ROLE_DEVELOPER: True,
                ROLE_BILLING: False,
                ROLE_VIEWER: False,
            },
        )
        self.assert_permission_matrix(
            CanViewProject,
            {
                ROLE_OWNER: True,
                ROLE_ADMIN: True,
                ROLE_DEVELOPER: True,
                ROLE_BILLING: False,
                ROLE_VIEWER: True,
            },
        )

    def test_user_has_role_and_permission_helpers(self):
        self.assertTrue(user_has_role(self.users[ROLE_OWNER], self.org, ROLE_OWNER))
        self.assertFalse(user_has_role(self.users[ROLE_VIEWER], self.org, ROLE_ADMIN))
        self.assertTrue(user_has_permission(self.users[ROLE_DEVELOPER], self.org, PermissionKey.DEPLOYMENT_WRITE))
        self.assertFalse(user_has_permission(self.users[ROLE_DEVELOPER], self.org, PermissionKey.BILLING_MANAGE))

    def test_require_organization_membership_returns_active_membership(self):
        membership = require_organization_membership(self.users[ROLE_OWNER], self.org)

        self.assertEqual(membership.organization, self.org)
        self.assertEqual(membership.user, self.users[ROLE_OWNER])

        with self.assertRaises(PermissionDenied):
            require_organization_membership(self.outsider, self.org)

    def test_has_organization_role_can_be_configured_per_view(self):
        request, view = self.make_request(self.users[ROLE_ADMIN])
        view.allowed_roles = {ROLE_OWNER, ROLE_ADMIN}

        self.assertTrue(HasOrganizationRole().has_permission(request, view))

        request, view = self.make_request(self.users[ROLE_VIEWER])
        view.allowed_roles = {ROLE_OWNER, ROLE_ADMIN}

        self.assertFalse(HasOrganizationRole().has_permission(request, view))

    def test_permissions_can_be_checked_per_action(self):
        request, view = self.make_request(self.users[ROLE_ADMIN])
        view.action = "create"
        view.permission_required_by_action = {"create": PermissionKey.PROJECT_CREATE}

        self.assertTrue(HasOrganizationPermission().has_permission(request, view))

        request, view = self.make_request(self.users[ROLE_VIEWER])
        view.action = "create"
        view.permission_required_by_action = {"create": PermissionKey.PROJECT_CREATE}

        self.assertFalse(HasOrganizationPermission().has_permission(request, view))

    def test_get_object_for_organization_or_404_never_uses_global_project_lookup(self):
        project = get_object_for_organization_or_404(
            Project,
            self.org,
            public_id=self.project.public_id,
        )
        self.assertEqual(project, self.project)

        with self.assertRaisesMessage(Exception, "No Project matches"):
            get_object_for_organization_or_404(
                Project,
                self.org,
                public_id=self.other_project.public_id,
            )

    def test_view_denies_access_to_project_from_another_organization(self):
        view = ProjectProbeView.as_view()

        request = self.factory.get("/")
        force_authenticate(request, user=self.users[ROLE_OWNER])
        response = view(
            request,
            organization_public_id=self.org.public_id,
            project_public_id=self.project.public_id,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        request = self.factory.get("/")
        force_authenticate(request, user=self.users[ROLE_OWNER])
        response = view(
            request,
            organization_public_id=self.org.public_id,
            project_public_id=self.other_project.public_id,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_view_denies_member_of_one_org_using_other_org_context(self):
        view = ProjectProbeView.as_view()
        request = self.factory.get("/")
        force_authenticate(request, user=self.users[ROLE_OWNER])

        response = view(
            request,
            organization_public_id=self.other_org.public_id,
            project_public_id=self.other_project.public_id,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_object_permission_rejects_cross_tenant_object(self):
        request, view = self.make_request(self.users[ROLE_OWNER], organization=self.org)

        self.assertFalse(CanViewProject().has_object_permission(request, view, self.other_project))

    def test_object_permission_rejects_cross_tenant_organization_object(self):
        request, view = self.make_request(self.users[ROLE_OWNER], organization=self.org)
        view.required_permission = PermissionKey.ORGANIZATION_MANAGE

        self.assertFalse(HasOrganizationPermission().has_object_permission(request, view, self.other_org))
