from decimal import Decimal

from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.api import audit_log, entitlements
from apps.api.metering import aggregate_daily, record_runtime_usage, record_storage_usage, record_transfer_usage
from apps.api.models import (
    AuditLog,
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
    UsageMetric,
    UsageRecord,
    User,
)
from apps.api.rbac import ROLE_ADMIN, ROLE_BILLING, ROLE_OWNER, ROLE_VIEWER


class MeteringTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.roles = {
            key: Role.objects.create(scope=RoleScope.ORGANIZATION, key=key, name=key.title())
            for key in [ROLE_OWNER, ROLE_ADMIN, ROLE_BILLING, ROLE_VIEWER]
        }
        self.users = {key: User.objects.create_user(email=f"{key}@example.com", password="secret") for key in self.roles}
        self.outsider = User.objects.create_user(email="outsider@example.com", password="secret")
        self.org = Organization.objects.create(name="Acme", slug="acme", owner_user=self.users[ROLE_OWNER])
        self.other_org = Organization.objects.create(name="Other", slug="other", owner_user=self.outsider)
        for role_key, user in self.users.items():
            OrganizationMember.objects.create(organization=self.org, user=user, role=self.roles[role_key], status=OrganizationMemberStatus.ACTIVE)
        OrganizationMember.objects.create(organization=self.other_org, user=self.outsider, role=self.roles[ROLE_OWNER], status=OrganizationMemberStatus.ACTIVE)
        self.plan = Plan.objects.create(
            key="metered",
            name="Metered",
            limits={
                "projects": 10,
                "storage_gb": 10,
                "transfer_gb": 10,
                "runtime_cpu_millicores": 1000,
                "runtime_memory_mb": 1024,
            },
            features={"custom_domains": True, "container_deployments": True},
        )
        Subscription.objects.create(organization=self.org, plan=self.plan, status=SubscriptionStatus.ACTIVE)
        Subscription.objects.create(organization=self.other_org, plan=self.plan, status=SubscriptionStatus.ACTIVE)
        self.project = Project.objects.create(organization=self.org, name="App", slug="app", created_by_user=self.users[ROLE_OWNER])
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
            status=DomainStatus.ACTIVE,
            verified_at=timezone.now(),
        )
        self.other_project = Project.objects.create(organization=self.other_org, name="Other", slug="other", created_by_user=self.outsider)

    def login_as(self, role_key):
        self.client.force_login(self.users[role_key])

    def usage_url(self, organization=None):
        return reverse("usage-summary", kwargs={"organization_public_id": (organization or self.org).public_id})

    def prometheus_url(self, organization=None):
        return reverse("usage-prometheus", kwargs={"organization_public_id": (organization or self.org).public_id})

    def test_storage_usage_is_aggregated_hourly_and_daily(self):
        now = timezone.now()
        record_storage_usage(organization=self.org, project=self.project, environment=self.environment, bytes_used=5 * 1024**3, measured_at=now)

        hourly = UsageRecord.objects.get(metric=UsageMetric.STORAGE_GB_HOURS)
        self.assertEqual(hourly.quantity, Decimal("5.000000"))
        self.assertEqual(hourly.period_start.minute, 0)

        daily = aggregate_daily(day=now.date())

        self.assertEqual(len(daily), 1)
        self.assertEqual(daily[0].quantity, Decimal("5.000000"))
        self.assertEqual(daily[0].source, "metering:daily:storage")

    def test_transfer_usage_is_aggregated_per_domain_project(self):
        record_transfer_usage(
            organization=self.org,
            project=self.project,
            environment=self.environment,
            domain=self.domain,
            bytes_egressed=2 * 1024**3,
            measured_at=timezone.now(),
        )

        record = UsageRecord.objects.get(metric=UsageMetric.EGRESS_BYTES)

        self.assertEqual(record.project, self.project)
        self.assertIn(str(self.domain.public_id), record.source)
        self.assertEqual(record.quantity, Decimal(2 * 1024**3))

    def test_cpu_and_ram_runtime_usage_is_aggregated(self):
        record_runtime_usage(
            organization=self.org,
            project=self.project,
            environment=self.environment,
            cpu_seconds=Decimal("123.5"),
            memory_gb_hours=Decimal("2.25"),
            measured_at=timezone.now(),
        )

        cpu = UsageRecord.objects.get(metric=UsageMetric.CPU_SECONDS)
        memory = UsageRecord.objects.get(metric=UsageMetric.MEMORY_GB_HOURS)
        self.assertEqual(cpu.quantity, Decimal("123.500000"))
        self.assertEqual(memory.quantity, Decimal("2.250000"))

    def test_80_percent_threshold_creates_alert_and_audit_log(self):
        record_storage_usage(organization=self.org, project=self.project, bytes_used=8 * 1024**3)

        self.assertTrue(SecurityEvent.objects.filter(event_type="usage.storage_gb_hours.80", organization=self.org).exists())
        self.assertTrue(AuditLog.objects.filter(action=audit_log.AuditAction.USAGE_LIMIT_THRESHOLD_REACHED, organization=self.org).exists())

    def test_90_percent_threshold_creates_alert(self):
        record_storage_usage(organization=self.org, project=self.project, bytes_used=9 * 1024**3)

        self.assertTrue(SecurityEvent.objects.filter(event_type="usage.storage_gb_hours.90", organization=self.org).exists())

    def test_100_percent_threshold_creates_limit_exceeded_audit_log(self):
        record_storage_usage(organization=self.org, project=self.project, bytes_used=10 * 1024**3)

        self.assertTrue(SecurityEvent.objects.filter(event_type="usage.storage_gb_hours.100", organization=self.org).exists())
        self.assertTrue(AuditLog.objects.filter(action=audit_log.AuditAction.USAGE_LIMIT_EXCEEDED, organization=self.org).exists())

    def test_deployment_is_blocked_after_limit_is_exceeded(self):
        record_transfer_usage(organization=self.org, project=self.project, bytes_egressed=11 * 1024**3)

        decision = entitlements.can_deploy_project(self.project)

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.code, "usage_limit_exceeded")

    def test_billing_owner_admin_can_read_usage_but_outsider_cannot(self):
        record_storage_usage(organization=self.org, project=self.project, bytes_used=1024**3)

        for role_key in [ROLE_OWNER, ROLE_ADMIN, ROLE_BILLING]:
            with self.subTest(role=role_key):
                self.login_as(role_key)
                response = self.client.get(self.usage_url())
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["results"][0]["metric"], UsageMetric.STORAGE_GB_HOURS)

        self.client.force_login(self.outsider)
        response = self.client.get(self.usage_url())

        self.assertEqual(response.status_code, 404)

    def test_viewer_usage_access_depends_on_policy(self):
        self.login_as(ROLE_VIEWER)

        response = self.client.get(self.usage_url())

        self.assertEqual(response.status_code, 403)

    @override_settings(USAGE_VIEWER_CAN_VIEW_USAGE=True)
    def test_viewer_can_read_usage_when_policy_allows(self):
        record_storage_usage(organization=self.org, project=self.project, bytes_used=1024**3)
        self.login_as(ROLE_VIEWER)

        response = self.client.get(self.usage_url())

        self.assertEqual(response.status_code, 200)

    def test_prometheus_metrics_are_tenant_scoped(self):
        UsageRecord.objects.create(
            organization=self.other_org,
            project=self.other_project,
            metric=UsageMetric.STORAGE_GB_HOURS,
            quantity=Decimal("999"),
            unit="gb_hours",
            period_start=timezone.now() - timezone.timedelta(hours=1),
            period_end=timezone.now(),
            source="test",
        )
        record_storage_usage(organization=self.org, project=self.project, bytes_used=1024**3)
        self.login_as(ROLE_BILLING)

        response = self.client.get(self.prometheus_url())

        body = response.content.decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertIn(str(self.org.public_id), body)
        self.assertNotIn(str(self.other_org.public_id), body)
