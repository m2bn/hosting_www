import json
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.api import audit_log
from apps.api.certificates import create_expiry_alerts, mark_acme_error, mark_dns_error, request_certificate_renewal
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
    SecurityEvent,
    Subscription,
    SubscriptionStatus,
    User,
)
from apps.api.rbac import ROLE_ADMIN, ROLE_OWNER


class CertificateTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.owner_role = Role.objects.create(scope=RoleScope.ORGANIZATION, key=ROLE_OWNER, name="Owner")
        self.admin_role = Role.objects.create(scope=RoleScope.ORGANIZATION, key=ROLE_ADMIN, name="Admin")
        self.owner = User.objects.create_user(email="owner@example.com", password="secret")
        self.admin = User.objects.create_user(email="admin@example.com", password="secret")
        self.outsider = User.objects.create_user(email="outsider@example.com", password="secret")
        self.org = Organization.objects.create(name="Acme", slug="acme", owner_user=self.owner)
        self.other_org = Organization.objects.create(name="Other", slug="other", owner_user=self.outsider)
        OrganizationMember.objects.create(organization=self.org, user=self.owner, role=self.owner_role, status=OrganizationMemberStatus.ACTIVE)
        OrganizationMember.objects.create(organization=self.org, user=self.admin, role=self.admin_role, status=OrganizationMemberStatus.ACTIVE)
        OrganizationMember.objects.create(organization=self.other_org, user=self.outsider, role=self.owner_role, status=OrganizationMemberStatus.ACTIVE)
        plan = Plan.objects.create(
            key="certs",
            name="Certs",
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
        self.domain = Domain.objects.create(
            organization=self.org,
            project=self.project,
            environment=self.environment,
            hostname="www.customer.test",
            type=DomainType.CUSTOM,
            status=DomainStatus.VERIFIED,
            verified_at=timezone.now(),
        )
        self.domain.set_verification_token("token")
        self.domain.save(update_fields=["verification_token_hash", "updated_at"])

    def csrf(self):
        self.client.get(reverse("auth-csrf"))
        return self.client.cookies["csrftoken"].value

    def login_as(self, user):
        self.client.force_login(user)

    def cert_url(self, domain=None, organization=None, project=None, environment=None):
        return reverse(
            "certificate-list",
            kwargs={
                "organization_public_id": (organization or self.org).public_id,
                "project_public_id": (project or self.project).public_id,
                "environment_public_id": (environment or self.environment).public_id,
                "domain_public_id": (domain or self.domain).public_id,
            },
        )

    def test_domain_verified_creates_certificate_request(self):
        self.login_as(self.admin)
        captured = {}

        def fake_request(certificate):
            captured["certificate"] = certificate
            return {"requested": True, "secret_name": certificate.kubernetes_secret_name}

        with patch("apps.api.certificates.CertManagerClient.request_certificate", side_effect=fake_request):
            with patch("apps.api.custom_domains.DNSResolver.txt_records", return_value=["token"]):
                response = self.client.post(
                    reverse(
                        "domain-verify",
                        kwargs={
                            "organization_public_id": self.org.public_id,
                            "project_public_id": self.project.public_id,
                            "environment_public_id": self.environment.public_id,
                            "domain_public_id": self.domain.public_id,
                        },
                    ),
                    HTTP_X_CSRFTOKEN=self.csrf(),
                )

        self.assertEqual(response.status_code, 200)
        certificate = Certificate.objects.get(domain=self.domain)
        self.assertEqual(certificate.status, CertificateStatus.PENDING)
        self.assertEqual(captured["certificate"], certificate)
        self.assertTrue(AuditLog.objects.filter(action=audit_log.AuditAction.CERTIFICATE_REQUESTED, project=self.project).exists())

    def test_dns_error_sets_certificate_failed(self):
        certificate = Certificate.objects.create(
            organization=self.org,
            domain=self.domain,
            status=CertificateStatus.ISSUING,
            kubernetes_secret_name="cert-secret",
        )

        mark_dns_error(certificate=certificate, reason="TXT record missing")

        certificate.refresh_from_db()
        self.assertEqual(certificate.status, CertificateStatus.FAILED)
        self.assertEqual(certificate.last_error, "TXT record missing")
        self.assertTrue(AuditLog.objects.filter(action=audit_log.AuditAction.CERTIFICATE_STATUS_CHANGED, target_id=str(certificate.public_id)).exists())

    def test_acme_error_sets_certificate_failed(self):
        certificate = Certificate.objects.create(
            organization=self.org,
            domain=self.domain,
            status=CertificateStatus.ISSUING,
            kubernetes_secret_name="cert-secret",
        )

        mark_acme_error(certificate=certificate, reason="ACME rate limited")

        certificate.refresh_from_db()
        self.assertEqual(certificate.status, CertificateStatus.FAILED)
        self.assertEqual(certificate.last_error, "ACME rate limited")

    def test_expiring_certificate_generates_alert(self):
        certificate = Certificate.objects.create(
            organization=self.org,
            domain=self.domain,
            status=CertificateStatus.ACTIVE,
            not_before=timezone.now() - timezone.timedelta(days=80),
            not_after=timezone.now() + timezone.timedelta(days=3),
            kubernetes_secret_name="cert-secret",
        )

        alerts = create_expiry_alerts(days=14)

        self.assertEqual(len(alerts), 1)
        self.assertTrue(SecurityEvent.objects.filter(event_type="certificate.expiring", correlation_id=str(certificate.public_id)).exists())
        self.assertTrue(AuditLog.objects.filter(action=audit_log.AuditAction.CERTIFICATE_EXPIRING, target_id=str(certificate.public_id)).exists())

    def test_renewal_sets_renewal_pending_and_calls_cert_manager(self):
        certificate = Certificate.objects.create(
            organization=self.org,
            domain=self.domain,
            status=CertificateStatus.ACTIVE,
            not_after=timezone.now() + timezone.timedelta(days=7),
            kubernetes_secret_name="cert-secret",
        )

        with patch("apps.api.certificates.CertManagerClient.renew_certificate", return_value={"renewal": True}) as mocked:
            request_certificate_renewal(certificate=certificate)

        certificate.refresh_from_db()
        self.assertEqual(certificate.status, CertificateStatus.RENEWAL_PENDING)
        mocked.assert_called_once()

    def test_private_key_upload_is_rejected(self):
        self.login_as(self.admin)

        response = self.client.post(
            self.cert_url(),
            data=json.dumps({"private_key": "-----BEGIN PRIVATE KEY-----"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "private_key_upload_not_supported")

    def test_user_outside_organization_cannot_see_certificate(self):
        Certificate.objects.create(
            organization=self.org,
            domain=self.domain,
            status=CertificateStatus.ACTIVE,
            kubernetes_secret_name="cert-secret",
        )
        self.login_as(self.outsider)

        response = self.client.get(self.cert_url())

        self.assertEqual(response.status_code, 404)
