from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from apps.api.models import Domain, DomainStatus, Plan, Project, ProjectStatus, Subscription, SubscriptionStatus, UsageMetric, UsageRecord


PLAN_FREE = "free"
PLAN_PRO = "pro"
PLAN_BUSINESS = "business"

LIMIT_PROJECTS = "projects"
LIMIT_STORAGE_GB = "storage_gb"
LIMIT_TRANSFER_GB = "transfer_gb"
LIMIT_RUNTIME_CPU_MILLICORES = "runtime_cpu_millicores"
LIMIT_RUNTIME_MEMORY_MB = "runtime_memory_mb"

FEATURE_CUSTOM_DOMAINS = "custom_domains"
FEATURE_CONTAINER_DEPLOYMENTS = "container_deployments"

DEFAULT_FREE_LIMITS = {
    LIMIT_PROJECTS: 1,
    LIMIT_STORAGE_GB: 1,
    LIMIT_TRANSFER_GB: 10,
    LIMIT_RUNTIME_CPU_MILLICORES: 250,
    LIMIT_RUNTIME_MEMORY_MB: 512,
}
DEFAULT_FREE_FEATURES = {
    FEATURE_CUSTOM_DOMAINS: False,
    FEATURE_CONTAINER_DEPLOYMENTS: False,
}

BLOCKING_SUBSCRIPTION_STATUSES = {
    SubscriptionStatus.CANCELED,
    SubscriptionStatus.CANCELLED,
    SubscriptionStatus.UNPAID,
    SubscriptionStatus.INCOMPLETE,
}
SERVICE_ACTIVE_STATUSES = {
    SubscriptionStatus.ACTIVE,
    SubscriptionStatus.TRIALING,
}


@dataclass(frozen=True)
class EntitlementDecision:
    allowed: bool
    reason: str = ""
    code: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class EntitlementContext:
    subscription: Subscription | None
    plan: Plan | None
    limits: dict
    features: dict
    status: str
    past_due_in_grace: bool = False

    @property
    def service_active(self):
        if self.status in SERVICE_ACTIVE_STATUSES:
            return True
        return self.status == SubscriptionStatus.PAST_DUE and self.past_due_in_grace

    @property
    def resource_creation_allowed(self):
        if self.status in BLOCKING_SUBSCRIPTION_STATUSES:
            return False
        return self.service_active


def get_entitlement_context(organization):
    subscription = _current_subscription(organization)
    if subscription:
        return EntitlementContext(
            subscription=subscription,
            plan=subscription.plan,
            limits={**DEFAULT_FREE_LIMITS, **(subscription.plan.limits or {})},
            features={**DEFAULT_FREE_FEATURES, **(subscription.plan.features or {})},
            status=subscription.status,
            past_due_in_grace=_past_due_in_grace(subscription),
        )
    if getattr(settings, "ENTITLEMENTS_NO_SUBSCRIPTION_POLICY", "free") == "free":
        free_plan = _free_plan()
        return EntitlementContext(
            subscription=None,
            plan=free_plan,
            limits={**DEFAULT_FREE_LIMITS, **((free_plan.limits if free_plan else {}) or {})},
            features={**DEFAULT_FREE_FEATURES, **((free_plan.features if free_plan else {}) or {})},
            status=SubscriptionStatus.ACTIVE,
        )
    return EntitlementContext(
        subscription=None,
        plan=None,
        limits={},
        features={},
        status="missing_subscription",
    )


def can_create_project(organization):
    context = get_entitlement_context(organization)
    if not context.resource_creation_allowed:
        return _deny_for_subscription_status(context)

    limit = get_project_limit(organization)
    usage = _active_project_count(organization)
    if limit is not None and usage >= limit:
        return EntitlementDecision(
            False,
            "Project limit exceeded.",
            code="project_limit_exceeded",
            metadata={"limit": limit, "usage": usage},
        )
    return EntitlementDecision(True, metadata={"limit": limit, "usage": usage})


def can_add_domain(organization):
    context = get_entitlement_context(organization)
    if not context.resource_creation_allowed:
        return _deny_for_subscription_status(context)
    if not can_use_custom_domain(organization).allowed:
        return EntitlementDecision(False, "Custom domains are not enabled for this plan.", code="custom_domains_disabled")
    return EntitlementDecision(True)


def can_deploy_project(project):
    context = get_entitlement_context(project.organization)
    if not context.resource_creation_allowed:
        return _deny_for_subscription_status(context)
    if not can_use_container_deployment(project.organization).allowed:
        return EntitlementDecision(
            False,
            "Container deployments are not enabled for this plan.",
            code="container_deployments_disabled",
        )
    return EntitlementDecision(True)


def can_use_custom_domain(organization):
    context = get_entitlement_context(organization)
    return _feature_decision(context, FEATURE_CUSTOM_DOMAINS, "custom_domains_disabled")


def can_use_container_deployment(organization):
    context = get_entitlement_context(organization)
    return _feature_decision(context, FEATURE_CONTAINER_DEPLOYMENTS, "container_deployments_disabled")


def get_project_limit(organization):
    return _limit_value(get_entitlement_context(organization), LIMIT_PROJECTS)


def get_storage_limit(organization):
    return _limit_value(get_entitlement_context(organization), LIMIT_STORAGE_GB)


def get_transfer_limit(organization):
    return _limit_value(get_entitlement_context(organization), LIMIT_TRANSFER_GB)


def get_runtime_limits(project):
    context = get_entitlement_context(project.organization)
    return {
        "cpu_millicores": _limit_value(context, LIMIT_RUNTIME_CPU_MILLICORES),
        "memory_mb": _limit_value(context, LIMIT_RUNTIME_MEMORY_MB),
    }


def storage_usage_exceeds_limit(organization):
    return _usage_exceeds_limit(organization, UsageMetric.STORAGE_GB_HOURS, get_storage_limit(organization))


def transfer_usage_exceeds_limit(organization):
    return _usage_exceeds_limit(organization, UsageMetric.EGRESS_BYTES, get_transfer_limit(organization), divisor=Decimal(1024**3))


def _current_subscription(organization):
    relevant_statuses = [
        SubscriptionStatus.ACTIVE,
        SubscriptionStatus.TRIALING,
        SubscriptionStatus.PAST_DUE,
        SubscriptionStatus.INCOMPLETE,
        SubscriptionStatus.UNPAID,
        SubscriptionStatus.CANCELED,
        SubscriptionStatus.CANCELLED,
    ]
    return (
        Subscription.objects.select_related("plan")
        .filter(organization=organization, status__in=relevant_statuses)
        .order_by("-created_at")
        .first()
    )


def _free_plan():
    return Plan.objects.filter(key=PLAN_FREE, status="active").first()


def _past_due_in_grace(subscription):
    if subscription.status != SubscriptionStatus.PAST_DUE:
        return False
    grace_days = getattr(settings, "ENTITLEMENTS_PAST_DUE_GRACE_DAYS", 7)
    if grace_days <= 0:
        return False
    if not subscription.current_period_end:
        return True
    return timezone.now() <= subscription.current_period_end + timedelta(days=grace_days)


def _deny_for_subscription_status(context):
    return EntitlementDecision(
        False,
        "Subscription status does not allow this action.",
        code="subscription_blocked",
        metadata={"status": context.status, "past_due_in_grace": context.past_due_in_grace},
    )


def _feature_decision(context, feature_key, denial_code):
    if not context.service_active:
        return _deny_for_subscription_status(context)
    if bool(context.features.get(feature_key, False)):
        return EntitlementDecision(True)
    return EntitlementDecision(False, "Feature is not enabled for this plan.", code=denial_code)


def _limit_value(context, key):
    value = context.limits.get(key)
    if value in [None, "unlimited"]:
        return None
    return int(value)


def _active_project_count(organization):
    return Project.objects.filter(organization=organization, deleted_at__isnull=True).exclude(status=ProjectStatus.DELETED).count()


def _usage_exceeds_limit(organization, metric, limit, divisor=Decimal(1)):
    if limit is None:
        return EntitlementDecision(True, metadata={"limit": None})
    usage = UsageRecord.objects.filter(organization=organization, metric=metric).aggregate(total=Sum("quantity"))["total"]
    normalized_usage = Decimal(usage or 0) / divisor
    if normalized_usage > Decimal(limit):
        return EntitlementDecision(
            False,
            "Usage limit exceeded.",
            code="usage_limit_exceeded",
            metadata={"metric": metric, "limit": limit, "usage": str(normalized_usage)},
        )
    return EntitlementDecision(True, metadata={"metric": metric, "limit": limit, "usage": str(normalized_usage)})
