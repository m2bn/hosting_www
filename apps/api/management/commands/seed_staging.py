import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.api.models import (
    AuditActorType,
    AuditLog,
    AuditResult,
    Certificate,
    CertificateStatus,
    Deployment,
    DeploymentStatus,
    Domain,
    DomainStatus,
    DomainType,
    Environment,
    EnvironmentStatus,
    EnvironmentType,
    Invoice,
    InvoiceStatus,
    Organization,
    OrganizationMember,
    OrganizationMemberStatus,
    Permission,
    Plan,
    PlanStatus,
    Project,
    ProjectStatus,
    Role,
    RoleScope,
    Subscription,
    SubscriptionStatus,
    UsageMetric,
    UsageRecord,
    User,
)
from apps.api.rbac import BASE_ROLE_KEYS, ROLE_PERMISSIONS


class Command(BaseCommand):
    help = "Seed idempotent staging-only data for smoke and e2e tests."

    def handle(self, *args, **options):
        if os.environ.get("ENVIRONMENT") != "staging":
            raise CommandError("seed_staging can only run with ENVIRONMENT=staging.")
        if os.environ.get("STAGING_ALLOW_SEED") != "true":
            raise CommandError("Set STAGING_ALLOW_SEED=true to seed staging data.")

        password = os.environ.get("STAGING_SEED_PASSWORD")

        with transaction.atomic():
            roles = self._seed_roles()
            plan = self._seed_plan()
            owner = self._user("owner.staging@example.com", "Staging Owner", password)
            developer = self._user("developer.staging@example.com", "Staging Developer", password)
            viewer = self._user("viewer.staging@example.com", "Staging Viewer", password)
            billing = self._user("billing.staging@example.com", "Staging Billing", password)

            organization, _ = Organization.objects.update_or_create(
                slug="staging-acme",
                defaults={
                    "name": "Staging Acme",
                    "billing_email": "billing.staging@example.com",
                    "stripe_customer_id": "cus_staging_seed",
                    "owner_user": owner,
                    "status": "active",
                },
            )

            for user, role_key in [
                (owner, "owner"),
                (developer, "developer"),
                (viewer, "viewer"),
                (billing, "billing"),
            ]:
                OrganizationMember.objects.update_or_create(
                    organization=organization,
                    user=user,
                    defaults={
                        "role": roles[role_key],
                        "status": OrganizationMemberStatus.ACTIVE,
                        "joined_at": timezone.now(),
                    },
                )

            project, _ = Project.objects.update_or_create(
                organization=organization,
                slug="staging-web",
                defaults={
                    "name": "Staging Web",
                    "status": ProjectStatus.ACTIVE,
                    "created_by_user": owner,
                },
            )

            environment, _ = Environment.objects.update_or_create(
                project=project,
                slug="staging",
                defaults={
                    "organization": organization,
                    "name": "Staging",
                    "type": EnvironmentType.STAGING,
                    "status": EnvironmentStatus.ACTIVE,
                    "kubernetes_namespace": "proj-staging-acme-staging-web",
                },
            )
            if project.default_environment_id != environment.id:
                project.default_environment = environment
                project.save(update_fields=["default_environment", "updated_at"])

            subscription, _ = Subscription.objects.update_or_create(
                organization=organization,
                defaults={
                    "plan": plan,
                    "stripe_customer_id": "cus_staging_seed",
                    "stripe_subscription_id": "sub_staging_seed",
                    "status": SubscriptionStatus.TRIALING,
                    "current_period_start": timezone.now(),
                    "current_period_end": timezone.now() + timezone.timedelta(days=14),
                },
            )

            Invoice.objects.update_or_create(
                stripe_invoice_id="in_staging_seed_paid",
                defaults={
                    "organization": organization,
                    "subscription": subscription,
                    "status": InvoiceStatus.PAID,
                    "amount_due": "0.00",
                    "amount_paid": "0.00",
                    "currency": "USD",
                    "issued_at": timezone.now(),
                    "paid_at": timezone.now(),
                },
            )

            deployment, _ = Deployment.objects.update_or_create(
                organization=organization,
                project=project,
                environment=environment,
                version="staging-seed-001",
                defaults={
                    "image_ref": "registry.example.com/platform/staging-web:seed",
                    "status": DeploymentStatus.RUNNING,
                    "requested_by_user": owner,
                    "started_at": timezone.now(),
                    "finished_at": timezone.now(),
                },
            )

            domain, _ = Domain.objects.update_or_create(
                hostname="staging-web.apps.staging.example.com",
                defaults={
                    "organization": organization,
                    "project": project,
                    "environment": environment,
                    "type": DomainType.PLATFORM,
                    "status": DomainStatus.ACTIVE,
                    "verified_at": timezone.now(),
                },
            )

            Certificate.objects.update_or_create(
                domain=domain,
                defaults={
                    "organization": organization,
                    "provider": "cert-manager",
                    "status": CertificateStatus.ACTIVE,
                    "kubernetes_secret_name": "staging-web-tls",
                    "not_before": timezone.now(),
                    "not_after": timezone.now() + timezone.timedelta(days=80),
                },
            )

            UsageRecord.objects.update_or_create(
                organization=organization,
                project=project,
                environment=environment,
                metric=UsageMetric.STORAGE_GB_HOURS,
                period_start=timezone.now() - timezone.timedelta(hours=1),
                period_end=timezone.now(),
                source="staging-seed",
                defaults={
                    "quantity": "1.000000",
                    "unit": "GBh",
                },
            )

            AuditLog.objects.create(
                organization=organization,
                project=project,
                actor_user=owner,
                actor_type=AuditActorType.SYSTEM,
                actor_id="staging-seed",
                actor_ref="seed_staging",
                action="staging.seed",
                target_type="environment",
                target_id=str(environment.public_id),
                result=AuditResult.SUCCESS,
                correlation_id="staging-seed",
                metadata={"deployment_id": str(deployment.public_id)},
            )

        self.stdout.write(self.style.SUCCESS("Seeded staging data."))

    def _seed_roles(self):
        permissions = {}
        for role_permissions in ROLE_PERMISSIONS.values():
            for permission_key in role_permissions:
                permissions[permission_key], _ = Permission.objects.update_or_create(
                    key=permission_key,
                    defaults={"category": permission_key.split(".", 1)[0], "description": permission_key},
                )

        roles = {}
        for role_key in BASE_ROLE_KEYS:
            role, _ = Role.objects.update_or_create(
                scope=RoleScope.ORGANIZATION,
                key=role_key,
                defaults={"name": role_key.title(), "description": f"Base {role_key} role.", "is_system": True},
            )
            role.permissions.set([permissions[key] for key in ROLE_PERMISSIONS[role_key]])
            roles[role_key] = role
        return roles

    def _seed_plan(self):
        plan, _ = Plan.objects.update_or_create(
            key="staging-pro",
            defaults={
                "name": "Staging Pro",
                "status": PlanStatus.ACTIVE,
                "stripe_price_id": "price_staging_seed",
                "limits": {
                    "projects": 5,
                    "storage_gb": 25,
                    "transfer_gb": 100,
                    "runtime_cpu": "1",
                    "runtime_memory": "1Gi",
                },
                "features": {
                    "custom_domains": True,
                    "container_deployments": True,
                },
            },
        )
        return plan

    def _user(self, email, full_name, password):
        user, created = User.objects.update_or_create(
            email=email,
            defaults={
                "full_name": full_name,
                "is_active": True,
                "is_email_verified": True,
            },
        )
        if created or password:
            if password:
                user.set_password(password)
            else:
                user.set_unusable_password()
            user.save(update_fields=["password", "updated_at"])
        return user
