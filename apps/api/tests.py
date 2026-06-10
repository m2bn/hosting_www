from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.api.models import (
    ApiKey,
    Deployment,
    Domain,
    DomainStatus,
    DomainType,
    Environment,
    EnvironmentType,
    Invoice,
    InvoiceStatus,
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
    WebhookEvent,
)


class DomainModelFactory:
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com",
            password="not-secret",
            is_email_verified=True,
        )
        self.org = Organization.objects.create(
            name="Acme",
            slug="acme",
            billing_email="billing@example.com",
            owner_user=self.user,
        )
        self.role = Role.objects.create(
            scope=RoleScope.ORGANIZATION,
            key="owner",
            name="Owner",
        )
        self.project = Project.objects.create(
            organization=self.org,
            name="Website",
            slug="website",
            created_by_user=self.user,
        )
        self.environment = Environment.objects.create(
            organization=self.org,
            project=self.project,
            name="Production",
            slug="production",
            type=EnvironmentType.PRODUCTION,
            kubernetes_namespace="org-acme-project-website-prod",
        )
        self.project.default_environment = self.environment
        self.project.save(update_fields=["default_environment", "updated_at"])


class PublicIdentifierTests(DomainModelFactory, TestCase):
    def test_models_use_internal_bigint_and_public_uuid(self):
        self.assertIsInstance(self.org.id, int)
        self.assertIsNotNone(self.org.public_id)
        self.assertNotEqual(str(self.org.id), str(self.org.public_id))


class TenantConstraintTests(DomainModelFactory, TestCase):
    def test_active_organization_slug_is_unique_until_soft_deleted(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Organization.objects.create(name="Other", slug="acme", owner_user=self.user)

        self.org.soft_delete()
        Organization.objects.create(name="Other", slug="acme", owner_user=self.user)

    def test_project_slug_is_unique_per_active_organization(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Project.objects.create(
                    organization=self.org,
                    name="Duplicate",
                    slug="website",
                    created_by_user=self.user,
                )

        other_org = Organization.objects.create(name="Other", slug="other", owner_user=self.user)
        Project.objects.create(
            organization=other_org,
            name="Website",
            slug="website",
            created_by_user=self.user,
        )

    def test_organization_member_is_unique_while_not_removed(self):
        OrganizationMember.objects.create(
            organization=self.org,
            user=self.user,
            role=self.role,
            status=OrganizationMemberStatus.ACTIVE,
            joined_at=timezone.now(),
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                OrganizationMember.objects.create(
                    organization=self.org,
                    user=self.user,
                    role=self.role,
                    status=OrganizationMemberStatus.DISABLED,
                )

        OrganizationMember.objects.filter(organization=self.org, user=self.user).update(
            status=OrganizationMemberStatus.REMOVED
        )
        OrganizationMember.objects.create(
            organization=self.org,
            user=self.user,
            role=self.role,
            status=OrganizationMemberStatus.ACTIVE,
        )

    def test_environment_must_belong_to_project_organization(self):
        other_org = Organization.objects.create(name="Other", slug="other", owner_user=self.user)
        env = Environment(
            organization=other_org,
            project=self.project,
            name="Bad",
            slug="bad",
            kubernetes_namespace="bad-namespace",
        )

        with self.assertRaises(ValidationError):
            env.full_clean()


class SecretStorageTests(DomainModelFactory, TestCase):
    def test_api_key_hashes_secret_and_verifies_raw_key(self):
        api_key = ApiKey(
            organization=self.org,
            project=self.project,
            created_by_user=self.user,
            name="CI",
            prefix="sk_live_123",
            scopes=["deployment.write"],
        )
        api_key.set_key("raw-secret-value")
        api_key.save()

        api_key.refresh_from_db()
        self.assertNotEqual(api_key.key_hash, "raw-secret-value")
        self.assertTrue(api_key.check_key("raw-secret-value"))
        self.assertFalse(api_key.check_key("wrong-value"))

    def test_domain_verification_token_is_hashed(self):
        domain = Domain(
            organization=self.org,
            project=self.project,
            environment=self.environment,
            hostname="Example.COM.",
            type=DomainType.CUSTOM,
        )
        domain.set_verification_token("dns-token")
        domain.full_clean()
        domain.save()

        domain.refresh_from_db()
        self.assertEqual(domain.hostname, "example.com")
        self.assertNotEqual(domain.verification_token_hash, "dns-token")
        self.assertTrue(domain.check_verification_token("dns-token"))


class BusinessConstraintTests(DomainModelFactory, TestCase):
    def test_active_domain_requires_verification_timestamp(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Domain.objects.create(
                    organization=self.org,
                    project=self.project,
                    environment=self.environment,
                    hostname="example.com",
                    type=DomainType.CUSTOM,
                    status=DomainStatus.ACTIVE,
                )

    def test_active_domain_hostname_is_globally_unique_until_soft_deleted(self):
        domain = Domain.objects.create(
            organization=self.org,
            project=self.project,
            environment=self.environment,
            hostname="example.com",
            type=DomainType.CUSTOM,
            status=DomainStatus.VERIFIED,
            verified_at=timezone.now(),
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Domain.objects.create(
                    organization=self.org,
                    project=self.project,
                    environment=self.environment,
                    hostname="example.com",
                    type=DomainType.CUSTOM,
                    status=DomainStatus.VERIFIED,
                    verified_at=timezone.now(),
                )

        domain.soft_delete()
        Domain.objects.create(
            organization=self.org,
            project=self.project,
            environment=self.environment,
            hostname="example.com",
            type=DomainType.CUSTOM,
            status=DomainStatus.VERIFIED,
            verified_at=timezone.now(),
        )

    def test_only_one_live_subscription_per_organization(self):
        plan = Plan.objects.create(key="starter", name="Starter", stripe_price_id="price_starter")
        Subscription.objects.create(
            organization=self.org,
            plan=plan,
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_123",
            status=SubscriptionStatus.ACTIVE,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Subscription.objects.create(
                    organization=self.org,
                    plan=plan,
                    stripe_customer_id="cus_123",
                    stripe_subscription_id="sub_456",
                    status=SubscriptionStatus.PAST_DUE,
                )

    def test_webhook_events_are_idempotent_by_provider_event_id(self):
        WebhookEvent.objects.create(
            provider="stripe",
            provider_event_id="evt_123",
            event_type="invoice.payment_failed",
            payload_hash="hash-1",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                WebhookEvent.objects.create(
                    provider="stripe",
                    provider_event_id="evt_123",
                    event_type="invoice.payment_failed",
                    payload_hash="hash-1",
                )

    def test_usage_record_period_and_quantity_constraints(self):
        now = timezone.now()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                UsageRecord.objects.create(
                    organization=self.org,
                    project=self.project,
                    environment=self.environment,
                    metric=UsageMetric.CPU_SECONDS,
                    quantity=-1,
                    unit="seconds",
                    period_start=now,
                    period_end=now + timedelta(hours=1),
                    source="prometheus",
                )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                UsageRecord.objects.create(
                    organization=self.org,
                    project=self.project,
                    environment=self.environment,
                    metric=UsageMetric.CPU_SECONDS,
                    quantity=1,
                    unit="seconds",
                    period_start=now,
                    period_end=now,
                    source="prometheus",
                )

    def test_invoice_amounts_cannot_be_negative(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Invoice.objects.create(
                    organization=self.org,
                    stripe_invoice_id="in_123",
                    status=InvoiceStatus.OPEN,
                    amount_due=-1,
                    amount_paid=0,
                    currency="usd",
                )


class RelatedNameTests(DomainModelFactory, TestCase):
    def test_related_names_are_readable_for_common_queries(self):
        deployment = Deployment.objects.create(
            organization=self.org,
            project=self.project,
            environment=self.environment,
            version="v1",
            image_ref="registry.example.com/acme/website:v1",
            requested_by_user=self.user,
        )

        self.assertEqual(list(self.org.projects.all()), [self.project])
        self.assertEqual(list(self.project.environments.all()), [self.environment])
        self.assertEqual(list(self.environment.deployments.all()), [deployment])
