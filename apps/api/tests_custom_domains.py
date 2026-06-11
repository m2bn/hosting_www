import json
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.api import audit_log
from apps.api.custom_domains import verification_record_name
from apps.api.models import (
    AuditLog,
    Certificate,
    CertificateStatus,
    Domain,
    DomainStatus,
    DomainType,
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
from apps.api.rbac import ROLE_ADMIN, ROLE_DEVELOPER, ROLE_OWNER, ROLE_VIEWER


@override_settings(
    CUSTOM_DOMAIN_SYSTEM_HOSTNAMES={"app.platform.test"},
    CUSTOM_DOMAIN_SYSTEM_SUFFIXES={"platform.test"},
)
class CustomDomainTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.roles = {
            key: Role.objects.create(scope=RoleScope.ORGANIZATION, key=key, name=key.title())
            for key in [ROLE_OWNER, ROLE_ADMIN, ROLE_DEVELOPER, ROLE_VIEWER]
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
            key="domains",
            name="Domains",
            limits={"projects": 10, "storage_gb": 10, "transfer_gb": 100},
            features={"custom_domains": True, "container_deployments": True},
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

    def domain_url(self, organization=None, project=None, environment=None):
        return reverse(
            "domain-list",
            kwargs={
                "organization_public_id": (organization or self.org).public_id,
                "project_public_id": (project or self.project).public_id,
                "environment_public_id": (environment or self.environment).public_id,
            },
        )

    def create_domain(self, hostname="www.customer.test", user=None, organization=None, project=None, environment=None):
        self.login_as(user or self.users[ROLE_ADMIN])
        return self.client.post(
            self.domain_url(organization=organization, project=project, environment=environment),
            data=json.dumps({"hostname": hostname}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf(),
        )

    def verify_url(self, domain, organization=None, project=None, environment=None):
        return reverse(
            "domain-verify",
            kwargs={
                "organization_public_id": (organization or self.org).public_id,
                "project_public_id": (project or self.project).public_id,
                "environment_public_id": (environment or self.environment).public_id,
                "domain_public_id": domain.public_id,
            },
        )

    def test_correct_txt_verification_marks_domain_verified_and_requests_certificate(self):
        create_response = self.create_domain()
        self.assertEqual(create_response.status_code, 201)
        token = create_response.json()["dns_instructions"]["value"]
        domain = Domain.objects.get(public_id=create_response.json()["public_id"])
        self.assertNotEqual(domain.verification_token_hash, token)
        self.assertTrue(domain.check_verification_token(token))
        self.assertEqual(create_response.json()["dns_instructions"]["name"], verification_record_name("www.customer.test"))

        with patch("apps.api.custom_domains.DNSResolver.txt_records", return_value=[token]):
            response = self.client.post(self.verify_url(domain), HTTP_X_CSRFTOKEN=self.csrf())

        self.assertEqual(response.status_code, 200)
        domain.refresh_from_db()
        self.assertEqual(domain.status, DomainStatus.VERIFIED)
        self.assertIsNotNone(domain.verified_at)
        certificate = Certificate.objects.get(domain=domain)
        self.assertEqual(certificate.status, CertificateStatus.PENDING)
        self.assertTrue(AuditLog.objects.filter(action=audit_log.AuditAction.DOMAIN_VERIFIED, project=self.project).exists())

    def test_wrong_txt_fails_verification(self):
        create_response = self.create_domain(hostname="bad.customer.test")
        domain = Domain.objects.get(public_id=create_response.json()["public_id"])

        with patch("apps.api.custom_domains.DNSResolver.txt_records", return_value=["wrong-token"]):
            response = self.client.post(self.verify_url(domain), HTTP_X_CSRFTOKEN=self.csrf())

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "txt_verification_failed")
        domain.refresh_from_db()
        self.assertEqual(domain.status, DomainStatus.FAILED)
        self.assertTrue(AuditLog.objects.filter(action=audit_log.AuditAction.DOMAIN_VERIFICATION_FAILED, project=self.project).exists())

    def test_domain_assigned_to_other_organization_is_blocked(self):
        Domain.objects.create(
            organization=self.other_org,
            project=self.other_project,
            environment=self.other_environment,
            hostname="owned.customer.test",
            type=DomainType.CUSTOM,
            status=DomainStatus.VERIFIED,
        )

        response = self.create_domain(hostname="owned.customer.test")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "domain_taken")

    def test_pending_domain_takeover_attempt_is_blocked(self):
        Domain.objects.create(
            organization=self.other_org,
            project=self.other_project,
            environment=self.other_environment,
            hostname="pending.customer.test",
            type=DomainType.CUSTOM,
            status=DomainStatus.PENDING_VERIFICATION,
        )

        response = self.create_domain(hostname="pending.customer.test")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "domain_taken")

    def test_system_domain_is_blocked(self):
        response = self.create_domain(hostname="tenant.platform.test")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "system_domain")

    def test_viewer_cannot_add_domain(self):
        response = self.create_domain(hostname="viewer.customer.test", user=self.users[ROLE_VIEWER])

        self.assertEqual(response.status_code, 403)

    def test_developer_cannot_add_domain_by_default_policy(self):
        response = self.create_domain(hostname="dev.customer.test", user=self.users[ROLE_DEVELOPER])

        self.assertEqual(response.status_code, 403)

    def test_user_from_org_a_cannot_modify_domain_from_org_b(self):
        domain = Domain.objects.create(
            organization=self.other_org,
            project=self.other_project,
            environment=self.other_environment,
            hostname="other.customer.test",
            type=DomainType.CUSTOM,
            status=DomainStatus.PENDING_VERIFICATION,
        )
        self.login_as(self.users[ROLE_OWNER])

        response = self.client.post(
            self.verify_url(domain, organization=self.org, project=self.other_project, environment=self.other_environment),
            HTTP_X_CSRFTOKEN=self.csrf(),
        )

        self.assertEqual(response.status_code, 404)

    def test_token_is_not_written_to_audit_metadata(self):
        response = self.create_domain(hostname="audit.customer.test")

        self.assertEqual(response.status_code, 201)
        token = response.json()["dns_instructions"]["value"]
        metadata_blob = json.dumps(list(AuditLog.objects.values_list("metadata", flat=True)))
        self.assertNotIn(token, metadata_blob)
