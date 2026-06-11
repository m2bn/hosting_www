import json

from django.test import Client, TestCase
from django.urls import reverse

from apps.api import audit_log
from apps.api.models import AuditLog, Organization, OrganizationMember, OrganizationMemberStatus, Plan, Project, ProjectStatus, Role, RoleScope, Subscription, SubscriptionStatus, User
from apps.api.rbac import ROLE_ADMIN, ROLE_BILLING, ROLE_DEVELOPER, ROLE_OWNER, ROLE_VIEWER


class ProjectApiTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.roles = {
            key: Role.objects.create(scope=RoleScope.ORGANIZATION, key=key, name=key.title())
            for key in [ROLE_OWNER, ROLE_ADMIN, ROLE_DEVELOPER, ROLE_BILLING, ROLE_VIEWER]
        }
        self.users = {
            key: User.objects.create_user(email=f"{key}@example.com", password="secret")
            for key in self.roles
        }
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
        self.plan = Plan.objects.create(
            key="project-tests",
            name="Project Tests",
            limits={"projects": 10, "storage_gb": 100, "transfer_gb": 1000},
            features={"custom_domains": True, "container_deployments": True},
        )
        Subscription.objects.create(
            organization=self.org,
            plan=self.plan,
            status=SubscriptionStatus.ACTIVE,
        )
        self.project = Project.objects.create(
            organization=self.org,
            name="Storefront",
            slug="storefront",
            created_by_user=self.users[ROLE_OWNER],
        )
        self.other_project = Project.objects.create(
            organization=self.other_org,
            name="Other Project",
            slug="other-project",
            created_by_user=self.outsider,
        )

    def csrf(self):
        self.client.get(reverse("auth-csrf"))
        return self.client.cookies["csrftoken"].value

    def login_as(self, role_key):
        self.client.force_login(self.users[role_key])

    def request(self, method, path_name, kwargs=None, payload=None):
        kwargs = kwargs or {}
        data = json.dumps(payload or {})
        if method == "get":
            return self.client.get(reverse(path_name, kwargs=kwargs))
        return getattr(self.client, method)(
            reverse(path_name, kwargs=kwargs),
            data=data,
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf(),
        )

    def project_list_kwargs(self):
        return {"organization_public_id": self.org.public_id}

    def project_detail_kwargs(self, project=None, organization=None):
        project = project or self.project
        organization = organization or self.org
        return {
            "organization_public_id": organization.public_id,
            "project_public_id": project.public_id,
        }

    def test_owner_admin_developer_can_create_project(self):
        for role_key in [ROLE_OWNER, ROLE_ADMIN, ROLE_DEVELOPER]:
            with self.subTest(role=role_key):
                self.login_as(role_key)
                response = self.request(
                    "post",
                    "project-list",
                    kwargs=self.project_list_kwargs(),
                    payload={"name": f"{role_key.title()} Project", "slug": f"{role_key}-project"},
                )

                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.json()["slug"], f"{role_key}-project")
                self.assertTrue(
                    AuditLog.objects.filter(
                        action=audit_log.AuditAction.PROJECT_CREATED,
                        organization=self.org,
                        target_id=response.json()["public_id"],
                    ).exists()
                )

    def test_viewer_cannot_create_project(self):
        self.login_as(ROLE_VIEWER)

        response = self.request(
            "post",
            "project-list",
            kwargs=self.project_list_kwargs(),
            payload={"name": "Blocked", "slug": "blocked"},
        )

        self.assertEqual(response.status_code, 403)

    def test_billing_cannot_create_project(self):
        self.login_as(ROLE_BILLING)

        response = self.request(
            "post",
            "project-list",
            kwargs=self.project_list_kwargs(),
            payload={"name": "Blocked", "slug": "billing-blocked"},
        )

        self.assertEqual(response.status_code, 403)

    def test_project_create_requires_entitlement(self):
        self.login_as(ROLE_OWNER)
        self.org.subscriptions.update(status=SubscriptionStatus.UNPAID)

        response = self.request(
            "post",
            "project-list",
            kwargs=self.project_list_kwargs(),
            payload={"name": "Blocked", "slug": "entitlement-blocked"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "entitlement_denied")

    def test_user_outside_organization_cannot_see_project(self):
        self.client.force_login(self.outsider)

        list_response = self.request("get", "project-list", kwargs=self.project_list_kwargs())
        detail_response = self.request(
            "get",
            "project-detail",
            kwargs=self.project_detail_kwargs(),
        )

        self.assertEqual(list_response.status_code, 404)
        self.assertEqual(detail_response.status_code, 404)

    def test_user_from_org_a_cannot_modify_project_from_org_b(self):
        self.login_as(ROLE_OWNER)

        response = self.request(
            "patch",
            "project-detail",
            kwargs=self.project_detail_kwargs(project=self.other_project, organization=self.org),
            payload={"name": "Cross Tenant Update"},
        )

        self.assertEqual(response.status_code, 404)
        self.other_project.refresh_from_db()
        self.assertEqual(self.other_project.name, "Other Project")

    def test_soft_delete_hides_project_from_default_list_and_restore_returns_it(self):
        self.login_as(ROLE_OWNER)

        delete_response = self.request(
            "delete",
            "project-detail",
            kwargs=self.project_detail_kwargs(),
        )
        self.assertEqual(delete_response.status_code, 204)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, ProjectStatus.DELETED)
        self.assertIsNotNone(self.project.deleted_at)

        list_response = self.request("get", "project-list", kwargs=self.project_list_kwargs())
        self.assertEqual(list_response.status_code, 200)
        self.assertNotIn(str(self.project.public_id), [item["public_id"] for item in list_response.json()["results"]])

        restore_response = self.request(
            "post",
            "project-restore",
            kwargs=self.project_detail_kwargs(),
        )
        self.assertEqual(restore_response.status_code, 200)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, ProjectStatus.ACTIVE)
        self.assertIsNone(self.project.deleted_at)

    def test_archive_project_sets_suspended_status(self):
        self.login_as(ROLE_ADMIN)

        response = self.request(
            "post",
            "project-archive",
            kwargs=self.project_detail_kwargs(),
        )

        self.assertEqual(response.status_code, 200)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, ProjectStatus.SUSPENDED)

    def test_project_update_and_delete_create_audit_logs(self):
        self.login_as(ROLE_ADMIN)

        update_response = self.request(
            "patch",
            "project-detail",
            kwargs=self.project_detail_kwargs(),
            payload={"name": "Updated Storefront"},
        )
        delete_response = self.request(
            "delete",
            "project-detail",
            kwargs=self.project_detail_kwargs(),
        )

        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(delete_response.status_code, 204)
        self.assertTrue(
            AuditLog.objects.filter(action=audit_log.AuditAction.PROJECT_UPDATED, project=self.project).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(action=audit_log.AuditAction.PROJECT_DELETED, project=self.project).exists()
        )
