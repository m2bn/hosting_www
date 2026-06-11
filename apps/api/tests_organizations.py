import json

from django.test import Client, TestCase
from django.urls import reverse

from apps.api import audit_log
from apps.api.models import AuditLog, Organization, OrganizationMember, OrganizationMemberStatus, Role, RoleScope, User
from apps.api.rbac import ROLE_ADMIN, ROLE_BILLING, ROLE_DEVELOPER, ROLE_OWNER, ROLE_VIEWER


class OrganizationApiTests(TestCase):
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
        for role_key, user in self.users.items():
            OrganizationMember.objects.create(
                organization=self.org,
                user=user,
                role=self.roles[role_key],
                status=OrganizationMemberStatus.ACTIVE,
            )
        self.owner_member = OrganizationMember.objects.get(organization=self.org, user=self.users[ROLE_OWNER])

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

    def test_user_sees_only_organizations_where_they_are_member(self):
        other_org = Organization.objects.create(name="Other", slug="other", owner_user=self.outsider)
        OrganizationMember.objects.create(
            organization=other_org,
            user=self.outsider,
            role=self.roles[ROLE_OWNER],
            status=OrganizationMemberStatus.ACTIVE,
        )
        self.login_as(ROLE_VIEWER)

        response = self.request("get", "organization-list")

        self.assertEqual(response.status_code, 200)
        slugs = [item["slug"] for item in response.json()["results"]]
        self.assertEqual(slugs, ["acme"])

    def test_owner_can_create_update_and_delete_organization(self):
        self.login_as(ROLE_OWNER)

        create_response = self.request(
            "post",
            "organization-list",
            payload={"name": "New Org", "slug": "new-org", "billing_email": "billing@example.com"},
        )
        self.assertEqual(create_response.status_code, 201)
        created_org = Organization.objects.get(slug="new-org")
        self.assertTrue(
            OrganizationMember.objects.filter(
                organization=created_org,
                user=self.users[ROLE_OWNER],
                role__key=ROLE_OWNER,
                status=OrganizationMemberStatus.ACTIVE,
            ).exists()
        )

        update_response = self.request(
            "patch",
            "organization-detail",
            kwargs={"organization_public_id": self.org.public_id},
            payload={"name": "Acme Updated"},
        )
        self.assertEqual(update_response.status_code, 200)
        self.org.refresh_from_db()
        self.assertEqual(self.org.name, "Acme Updated")

        delete_response = self.request(
            "delete",
            "organization-detail",
            kwargs={"organization_public_id": self.org.public_id},
        )
        self.assertEqual(delete_response.status_code, 204)
        self.org.refresh_from_db()
        self.assertIsNotNone(self.org.deleted_at)
        self.assertTrue(AuditLog.objects.filter(action=audit_log.AuditAction.ORGANIZATION_DELETED).exists())

    def test_admin_can_manage_members(self):
        self.login_as(ROLE_ADMIN)

        add_response = self.request(
            "post",
            "organization-member-list",
            kwargs={"organization_public_id": self.org.public_id},
            payload={"email": "new-member@example.com", "role": ROLE_VIEWER},
        )
        self.assertEqual(add_response.status_code, 201)
        member_public_id = add_response.json()["public_id"]

        role_response = self.request(
            "patch",
            "organization-member-detail",
            kwargs={"organization_public_id": self.org.public_id, "member_public_id": member_public_id},
            payload={"role": ROLE_DEVELOPER},
        )
        self.assertEqual(role_response.status_code, 200)
        self.assertEqual(role_response.json()["role"], ROLE_DEVELOPER)

        remove_response = self.request(
            "delete",
            "organization-member-detail",
            kwargs={"organization_public_id": self.org.public_id, "member_public_id": member_public_id},
        )
        self.assertEqual(remove_response.status_code, 204)
        self.assertTrue(AuditLog.objects.filter(action=audit_log.AuditAction.ORGANIZATION_MEMBER_REMOVED).exists())

    def test_viewer_has_read_only_access(self):
        self.login_as(ROLE_VIEWER)

        detail_response = self.request(
            "get",
            "organization-detail",
            kwargs={"organization_public_id": self.org.public_id},
        )
        self.assertEqual(detail_response.status_code, 200)

        update_response = self.request(
            "patch",
            "organization-detail",
            kwargs={"organization_public_id": self.org.public_id},
            payload={"name": "Nope"},
        )
        self.assertEqual(update_response.status_code, 403)

        add_member_response = self.request(
            "post",
            "organization-member-list",
            kwargs={"organization_public_id": self.org.public_id},
            payload={"email": "blocked@example.com", "role": ROLE_VIEWER},
        )
        self.assertEqual(add_member_response.status_code, 403)

    def test_developer_cannot_manage_members(self):
        self.login_as(ROLE_DEVELOPER)

        response = self.request(
            "post",
            "organization-member-list",
            kwargs={"organization_public_id": self.org.public_id},
            payload={"email": "blocked@example.com", "role": ROLE_VIEWER},
        )

        self.assertEqual(response.status_code, 403)

    def test_billing_cannot_manage_members(self):
        self.login_as(ROLE_BILLING)

        response = self.request(
            "post",
            "organization-member-list",
            kwargs={"organization_public_id": self.org.public_id},
            payload={"email": "blocked@example.com", "role": ROLE_VIEWER},
        )

        self.assertEqual(response.status_code, 403)

    def test_user_outside_organization_has_no_access(self):
        self.client.force_login(self.outsider)

        detail_response = self.request(
            "get",
            "organization-detail",
            kwargs={"organization_public_id": self.org.public_id},
        )
        members_response = self.request(
            "get",
            "organization-member-list",
            kwargs={"organization_public_id": self.org.public_id},
        )

        self.assertEqual(detail_response.status_code, 404)
        self.assertEqual(members_response.status_code, 404)

    def test_cannot_remove_or_downgrade_last_owner(self):
        self.login_as(ROLE_OWNER)

        remove_response = self.request(
            "delete",
            "organization-member-detail",
            kwargs={"organization_public_id": self.org.public_id, "member_public_id": self.owner_member.public_id},
        )
        self.assertEqual(remove_response.status_code, 400)
        self.assertEqual(remove_response.json()["code"], "last_owner")

        downgrade_response = self.request(
            "patch",
            "organization-member-detail",
            kwargs={"organization_public_id": self.org.public_id, "member_public_id": self.owner_member.public_id},
            payload={"role": ROLE_ADMIN},
        )
        self.assertEqual(downgrade_response.status_code, 400)
        self.assertEqual(downgrade_response.json()["code"], "last_owner")
