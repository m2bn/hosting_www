from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.api import entitlements
from apps.api.models import Organization, Plan, Project, Subscription, SubscriptionStatus, UsageMetric, UsageRecord, User


class EntitlementsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="owner@example.com", password="secret")
        self.org = Organization.objects.create(name="Acme", slug="acme", owner_user=self.user)
        self.free_plan = self.create_plan(
            "free",
            "Free",
            projects=1,
            storage_gb=1,
            transfer_gb=10,
            custom_domains=False,
            container_deployments=False,
            cpu=250,
            memory=512,
        )
        self.pro_plan = self.create_plan(
            "pro",
            "Pro",
            projects=5,
            storage_gb=100,
            transfer_gb=1000,
            custom_domains=True,
            container_deployments=True,
            cpu=1000,
            memory=2048,
        )
        self.business_plan = self.create_plan(
            "business",
            "Business",
            projects=50,
            storage_gb=1000,
            transfer_gb=10000,
            custom_domains=True,
            container_deployments=True,
            cpu=4000,
            memory=8192,
        )

    def create_plan(self, key, name, projects, storage_gb, transfer_gb, custom_domains, container_deployments, cpu, memory):
        return Plan.objects.create(
            key=key,
            name=name,
            limits={
                "projects": projects,
                "storage_gb": storage_gb,
                "transfer_gb": transfer_gb,
                "runtime_cpu_millicores": cpu,
                "runtime_memory_mb": memory,
            },
            features={
                "custom_domains": custom_domains,
                "container_deployments": container_deployments,
            },
        )

    def subscribe(self, plan, status=SubscriptionStatus.ACTIVE, current_period_end=None):
        return Subscription.objects.create(
            organization=self.org,
            plan=plan,
            status=status,
            current_period_end=current_period_end,
        )

    def create_project(self, slug="app"):
        return Project.objects.create(
            organization=self.org,
            name=slug.title(),
            slug=slug,
            created_by_user=self.user,
        )

    def test_free_plan_limits_and_features(self):
        self.subscribe(self.free_plan)

        self.assertEqual(entitlements.get_project_limit(self.org), 1)
        self.assertEqual(entitlements.get_storage_limit(self.org), 1)
        self.assertEqual(entitlements.get_transfer_limit(self.org), 10)
        self.assertFalse(entitlements.can_use_custom_domain(self.org).allowed)
        self.assertFalse(entitlements.can_use_container_deployment(self.org).allowed)

    def test_pro_plan_limits_and_features(self):
        self.subscribe(self.pro_plan)

        project = self.create_project()

        self.assertEqual(entitlements.get_project_limit(self.org), 5)
        self.assertEqual(entitlements.get_runtime_limits(project), {"cpu_millicores": 1000, "memory_mb": 2048})
        self.assertTrue(entitlements.can_use_custom_domain(self.org).allowed)
        self.assertTrue(entitlements.can_deploy_project(project).allowed)

    def test_business_plan_limits_and_features(self):
        self.subscribe(self.business_plan)

        project = self.create_project()

        self.assertEqual(entitlements.get_project_limit(self.org), 50)
        self.assertEqual(entitlements.get_storage_limit(self.org), 1000)
        self.assertEqual(entitlements.get_transfer_limit(self.org), 10000)
        self.assertEqual(entitlements.get_runtime_limits(project), {"cpu_millicores": 4000, "memory_mb": 8192})

    def test_active_and_trialing_allow_resource_creation(self):
        for status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]:
            with self.subTest(status=status):
                self.org.subscriptions.all().delete()
                self.subscribe(self.pro_plan, status=status)

                self.assertTrue(entitlements.can_create_project(self.org).allowed)

    @override_settings(ENTITLEMENTS_PAST_DUE_GRACE_DAYS=7)
    def test_past_due_allows_actions_during_grace_period(self):
        self.subscribe(
            self.pro_plan,
            status=SubscriptionStatus.PAST_DUE,
            current_period_end=timezone.now() - timedelta(days=3),
        )

        self.assertTrue(entitlements.can_create_project(self.org).allowed)

    @override_settings(ENTITLEMENTS_PAST_DUE_GRACE_DAYS=7)
    def test_past_due_blocks_actions_after_grace_period(self):
        self.subscribe(
            self.pro_plan,
            status=SubscriptionStatus.PAST_DUE,
            current_period_end=timezone.now() - timedelta(days=9),
        )

        decision = entitlements.can_create_project(self.org)

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.code, "subscription_blocked")

    def test_canceled_and_unpaid_block_new_resources_and_deployments(self):
        for status in [SubscriptionStatus.CANCELED, SubscriptionStatus.UNPAID]:
            with self.subTest(status=status):
                self.org.subscriptions.all().delete()
                self.subscribe(self.pro_plan, status=status)
                project = self.create_project(slug=f"app-{status}")

                self.assertFalse(entitlements.can_create_project(self.org).allowed)
                self.assertFalse(entitlements.can_deploy_project(project).allowed)

    def test_project_limit_is_enforced(self):
        self.subscribe(self.free_plan)
        self.create_project()

        decision = entitlements.can_create_project(self.org)

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.code, "project_limit_exceeded")
        self.assertEqual(decision.metadata["limit"], 1)

    def test_storage_limit_is_enforced(self):
        self.subscribe(self.free_plan)
        now = timezone.now()
        UsageRecord.objects.create(
            organization=self.org,
            metric=UsageMetric.STORAGE_GB_HOURS,
            quantity=Decimal("2"),
            unit="gb_hours",
            period_start=now - timedelta(hours=1),
            period_end=now,
            source="test",
        )

        decision = entitlements.storage_usage_exceeds_limit(self.org)

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.code, "usage_limit_exceeded")

    def test_transfer_limit_is_enforced(self):
        self.subscribe(self.free_plan)
        now = timezone.now()
        UsageRecord.objects.create(
            organization=self.org,
            metric=UsageMetric.EGRESS_BYTES,
            quantity=Decimal(11 * 1024**3),
            unit="bytes",
            period_start=now - timedelta(hours=1),
            period_end=now,
            source="test",
        )

        decision = entitlements.transfer_usage_exceeds_limit(self.org)

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.code, "usage_limit_exceeded")

    def test_missing_subscription_uses_free_policy_by_default(self):
        self.assertEqual(entitlements.get_project_limit(self.org), 1)
        self.assertFalse(entitlements.can_use_custom_domain(self.org).allowed)
        self.assertTrue(entitlements.can_create_project(self.org).allowed)

    @override_settings(ENTITLEMENTS_NO_SUBSCRIPTION_POLICY="deny")
    def test_missing_subscription_can_be_deny_by_default(self):
        decision = entitlements.can_create_project(self.org)

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.code, "subscription_blocked")
