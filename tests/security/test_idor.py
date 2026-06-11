from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from apps.api.models import (
    ApiKey,
    Deployment,
    Domain,
    DomainStatus,
    DomainType,
    Environment,
    Organization,
    OrganizationMember,
    OrganizationMemberStatus,
    Project,
    Role,
    RoleScope,
    Subscription,
    SubscriptionStatus,
    Plan,
    User,
)
from apps.api.permissions import CanDeployProject, CanManageBilling, CanManageProjects, CanViewProject, HasOrganizationPermission
from apps.api.rbac import (
    ROLE_ADMIN,
    ROLE_BILLING,
    ROLE_DEVELOPER,
    ROLE_OWNER,
    ROLE_VIEWER,
    PermissionKey,
)
from apps.api.tenancy import get_object_for_organization_or_404, get_organization_from_request


class ProjectReadProbeView(APIView):
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


class ProjectWriteProbeView(APIView):
    permission_classes = [CanManageProjects]

    def patch(self, request, organization_public_id, project_public_id):
        organization = get_organization_from_request(request, self)
        project = get_object_for_organization_or_404(
            Project,
            organization,
            public_id=project_public_id,
            deleted_at__isnull=True,
        )
        self.check_object_permissions(request, project)
        return Response({"slug": project.slug, "would_update": True})

    def delete(self, request, organization_public_id, project_public_id):
        organization = get_organization_from_request(request, self)
        project = get_object_for_organization_or_404(
            Project,
            organization,
            public_id=project_public_id,
            deleted_at__isnull=True,
        )
        self.check_object_permissions(request, project)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DomainReadProbeView(APIView):
    permission_classes = [CanViewProject]

    def get(self, request, organization_public_id, domain_public_id):
        organization = get_organization_from_request(request, self)
        domain = get_object_for_organization_or_404(
            Domain,
            organization,
            public_id=domain_public_id,
            deleted_at__isnull=True,
        )
        self.check_object_permissions(request, domain)
        return Response({"hostname": domain.hostname})


class DomainWriteProbeView(APIView):
    permission_classes = [HasOrganizationPermission]
    required_permission = PermissionKey.DOMAIN_MANAGE

    def patch(self, request, organization_public_id, domain_public_id):
        organization = get_organization_from_request(request, self)
        domain = get_object_for_organization_or_404(
            Domain,
            organization,
            public_id=domain_public_id,
            deleted_at__isnull=True,
        )
        self.check_object_permissions(request, domain)
        return Response({"hostname": domain.hostname, "would_update": True})


class DeploymentReadProbeView(APIView):
    permission_classes = [CanViewProject]

    def get(self, request, organization_public_id, deployment_public_id):
        organization = get_organization_from_request(request, self)
        deployment = get_object_for_organization_or_404(
            Deployment,
            organization,
            public_id=deployment_public_id,
        )
        self.check_object_permissions(request, deployment)
        return Response({"version": deployment.version})


class SubscriptionWriteProbeView(APIView):
    permission_classes = [CanManageBilling]

    def patch(self, request, organization_public_id, subscription_public_id):
        organization = get_organization_from_request(request, self)
        subscription = get_object_for_organization_or_404(
            Subscription,
            organization,
            public_id=subscription_public_id,
        )
        self.check_object_permissions(request, subscription)
        return Response({"would_update": True})


class DeploymentActionProbeView(APIView):
    permission_classes = [CanDeployProject]

    def post(self, request, organization_public_id, project_public_id):
        organization = get_organization_from_request(request, self)
        project = get_object_for_organization_or_404(
            Project,
            organization,
            public_id=project_public_id,
            deleted_at__isnull=True,
        )
        self.check_object_permissions(request, project)
        return Response({"would_deploy": True})


class OrganizationDeleteProbeView(APIView):
    permission_classes = [HasOrganizationPermission]
    required_permission = PermissionKey.ORGANIZATION_MANAGE

    def delete(self, request, organization_public_id):
        organization = get_organization_from_request(request, self)
        self.check_object_permissions(request, organization)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ApiKeyProjectReadProbeView(APIView):
    def get(self, request, organization_public_id, project_public_id):
        organization = get_organization_from_request(request, self)
        api_key = self.get_api_key(request, organization)
        if PermissionKey.PROJECT_VIEW not in api_key.scopes:
            raise PermissionDenied("API key does not have project view scope.")

        project = get_object_for_organization_or_404(
            Project,
            organization,
            public_id=project_public_id,
            deleted_at__isnull=True,
        )
        if api_key.project_id and api_key.project_id != project.id:
            raise PermissionDenied("API key is bound to another project.")
        return Response({"slug": project.slug})

    def get_api_key(self, request, organization):
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if not header.startswith("Bearer "):
            raise PermissionDenied("API key is required.")

        token = header.removeprefix("Bearer ").strip()
        prefix = token.split(".", 1)[0]
        api_key = get_object_for_organization_or_404(
            ApiKey,
            organization,
            prefix=prefix,
            status="active",
        )
        if not api_key.check_key(token):
            raise PermissionDenied("Invalid API key.")
        return api_key


class IdorSecurityTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.roles = {
            key: Role.objects.create(scope=RoleScope.ORGANIZATION, key=key, name=key.title())
            for key in [ROLE_OWNER, ROLE_ADMIN, ROLE_DEVELOPER, ROLE_BILLING, ROLE_VIEWER]
        }
        self.users = {
            key: User.objects.create_user(email=f"{key}@tenant-a.example", password="secret")
            for key in self.roles
        }
        self.tenant_b_owner = User.objects.create_user(email="owner@tenant-b.example", password="secret")

        self.org_a = Organization.objects.create(name="Tenant A", slug="tenant-a", owner_user=self.users[ROLE_OWNER])
        self.org_b = Organization.objects.create(name="Tenant B", slug="tenant-b", owner_user=self.tenant_b_owner)

        for role_key, user in self.users.items():
            OrganizationMember.objects.create(
                organization=self.org_a,
                user=user,
                role=self.roles[role_key],
                status=OrganizationMemberStatus.ACTIVE,
            )
        OrganizationMember.objects.create(
            organization=self.org_b,
            user=self.tenant_b_owner,
            role=self.roles[ROLE_OWNER],
            status=OrganizationMemberStatus.ACTIVE,
        )

        self.project_a = self.create_project_bundle(self.org_a, self.users[ROLE_OWNER], "project-a")
        self.project_a_other = self.create_project_bundle(self.org_a, self.users[ROLE_OWNER], "project-a-other")
        self.project_b = self.create_project_bundle(self.org_b, self.tenant_b_owner, "project-b")
        self.plan = Plan.objects.create(key="starter", name="Starter", stripe_price_id="price_starter")
        self.subscription_a = Subscription.objects.create(
            organization=self.org_a,
            plan=self.plan,
            stripe_customer_id="cus_a",
            stripe_subscription_id="sub_a",
            status=SubscriptionStatus.ACTIVE,
        )

        self.raw_project_a_key = "ak_project_a.raw-secret"
        self.project_a_api_key = ApiKey(
            organization=self.org_a,
            project=self.project_a["project"],
            created_by_user=self.users[ROLE_OWNER],
            name="Project A key",
            prefix="ak_project_a",
            scopes=[PermissionKey.PROJECT_VIEW],
        )
        self.project_a_api_key.set_key(self.raw_project_a_key)
        self.project_a_api_key.save()

    def create_project_bundle(self, organization, owner, slug):
        project = Project.objects.create(
            organization=organization,
            name=slug.title(),
            slug=slug,
            created_by_user=owner,
        )
        environment = Environment.objects.create(
            organization=organization,
            project=project,
            name="Production",
            slug="production",
            kubernetes_namespace=f"{organization.slug}-{slug}-production",
        )
        domain = Domain.objects.create(
            organization=organization,
            project=project,
            environment=environment,
            hostname=f"{slug}.example.com",
            type=DomainType.CUSTOM,
            status=DomainStatus.VERIFIED,
            verified_at=timezone.now(),
        )
        deployment = Deployment.objects.create(
            organization=organization,
            project=project,
            environment=environment,
            version="v1",
            image_ref=f"registry.example.com/{organization.slug}/{slug}:v1",
            requested_by_user=owner,
        )
        return {
            "project": project,
            "environment": environment,
            "domain": domain,
            "deployment": deployment,
        }

    def authenticated_request(self, method, user, data=None):
        request = getattr(self.factory, method)("/", data=data or {}, format="json")
        force_authenticate(request, user=user)
        return request

    def assert_tenant_a_user_cannot_access_tenant_b_resource(self, view_cls, method, resource_kwarg, resource):
        view = view_cls.as_view()
        request = self.authenticated_request(method, self.users[ROLE_OWNER])
        response = view(
            request,
            organization_public_id=self.org_a.public_id,
            **{resource_kwarg: resource.public_id},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_tenant_a_user_cannot_retrieve_tenant_b_project(self):
        self.assert_tenant_a_user_cannot_access_tenant_b_resource(
            ProjectReadProbeView,
            "get",
            "project_public_id",
            self.project_b["project"],
        )

    def test_tenant_a_user_cannot_update_tenant_b_project(self):
        self.assert_tenant_a_user_cannot_access_tenant_b_resource(
            ProjectWriteProbeView,
            "patch",
            "project_public_id",
            self.project_b["project"],
        )

    def test_tenant_a_user_cannot_delete_tenant_b_project(self):
        self.assert_tenant_a_user_cannot_access_tenant_b_resource(
            ProjectWriteProbeView,
            "delete",
            "project_public_id",
            self.project_b["project"],
        )

    def test_tenant_a_user_cannot_retrieve_tenant_b_domain(self):
        self.assert_tenant_a_user_cannot_access_tenant_b_resource(
            DomainReadProbeView,
            "get",
            "domain_public_id",
            self.project_b["domain"],
        )

    def test_tenant_a_user_cannot_update_tenant_b_domain(self):
        self.assert_tenant_a_user_cannot_access_tenant_b_resource(
            DomainWriteProbeView,
            "patch",
            "domain_public_id",
            self.project_b["domain"],
        )

    def test_tenant_a_user_cannot_retrieve_tenant_b_deployment(self):
        self.assert_tenant_a_user_cannot_access_tenant_b_resource(
            DeploymentReadProbeView,
            "get",
            "deployment_public_id",
            self.project_b["deployment"],
        )

    def test_user_without_billing_role_cannot_update_subscription(self):
        view = SubscriptionWriteProbeView.as_view()
        request = self.authenticated_request("patch", self.users[ROLE_DEVELOPER])

        response = view(
            request,
            organization_public_id=self.org_a.public_id,
            subscription_public_id=self.subscription_a.public_id,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_viewer_cannot_deploy_project(self):
        view = DeploymentActionProbeView.as_view()
        request = self.authenticated_request("post", self.users[ROLE_VIEWER])

        response = view(
            request,
            organization_public_id=self.org_a.public_id,
            project_public_id=self.project_a["project"].public_id,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_developer_cannot_delete_organization(self):
        view = OrganizationDeleteProbeView.as_view()
        request = self.authenticated_request("delete", self.users[ROLE_DEVELOPER])

        response = view(request, organization_public_id=self.org_a.public_id)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_billing_user_cannot_deploy_project(self):
        view = DeploymentActionProbeView.as_view()
        request = self.authenticated_request("post", self.users[ROLE_BILLING])

        response = view(
            request,
            organization_public_id=self.org_a.public_id,
            project_public_id=self.project_a["project"].public_id,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_project_a_api_key_cannot_retrieve_project_b_data(self):
        view = ApiKeyProjectReadProbeView.as_view()
        request = self.factory.get("/", HTTP_AUTHORIZATION=f"Bearer {self.raw_project_a_key}")

        response = view(
            request,
            organization_public_id=self.org_a.public_id,
            project_public_id=self.project_b["project"].public_id,
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_project_a_api_key_cannot_retrieve_another_project_in_same_organization(self):
        view = ApiKeyProjectReadProbeView.as_view()
        request = self.factory.get("/", HTTP_AUTHORIZATION=f"Bearer {self.raw_project_a_key}")

        response = view(
            request,
            organization_public_id=self.org_a.public_id,
            project_public_id=self.project_a_other["project"].public_id,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
