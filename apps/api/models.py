import uuid

from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class TimeStampedModel(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at", "updated_at"])


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("The email address must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_platform_staff", True)
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser, TimeStampedModel):
    username = None
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255, blank=True)
    is_email_verified = models.BooleanField(default=False)
    is_platform_staff = models.BooleanField(default=False)
    mfa_enabled = models.BooleanField(default=False)
    last_login_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        indexes = [
            models.Index(fields=["email"], name="api_user_email_idx"),
            models.Index(fields=["is_active"], name="api_user_active_idx"),
        ]

    def __str__(self):
        return self.email


class OrganizationStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"
    PENDING_DELETION = "pending_deletion", "Pending deletion"
    DELETED = "deleted", "Deleted"


class Organization(TimeStampedModel, SoftDeleteModel):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=120)
    status = models.CharField(max_length=32, choices=OrganizationStatus.choices, default=OrganizationStatus.ACTIVE)
    billing_email = models.EmailField(blank=True)
    owner_user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="owned_organizations")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["slug"],
                condition=Q(deleted_at__isnull=True),
                name="uniq_active_organization_slug",
            ),
        ]
        indexes = [
            models.Index(fields=["slug"], name="api_org_slug_idx"),
            models.Index(fields=["status"], name="api_org_status_idx"),
        ]

    def __str__(self):
        return self.name


class RoleScope(models.TextChoices):
    ORGANIZATION = "organization", "Organization"
    PROJECT = "project", "Project"
    PLATFORM = "platform", "Platform"


class Role(TimeStampedModel):
    scope = models.CharField(max_length=32, choices=RoleScope.choices)
    key = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_system = models.BooleanField(default=True)
    permissions = models.ManyToManyField("Permission", related_name="roles", blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["scope", "key"], name="uniq_role_scope_key"),
        ]
        indexes = [
            models.Index(fields=["scope", "key"], name="api_role_scope_key_idx"),
        ]

    def __str__(self):
        return f"{self.scope}:{self.key}"


class Permission(TimeStampedModel):
    key = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100)

    class Meta:
        indexes = [
            models.Index(fields=["category"], name="api_perm_category_idx"),
        ]

    def __str__(self):
        return self.key


class OrganizationMemberStatus(models.TextChoices):
    INVITED = "invited", "Invited"
    ACTIVE = "active", "Active"
    DISABLED = "disabled", "Disabled"
    REMOVED = "removed", "Removed"


class OrganizationMember(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="organization_memberships")
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="organization_members")
    status = models.CharField(
        max_length=32,
        choices=OrganizationMemberStatus.choices,
        default=OrganizationMemberStatus.INVITED,
    )
    invited_by_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_organization_invites",
    )
    joined_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"],
                condition=~Q(status=OrganizationMemberStatus.REMOVED),
                name="uniq_active_org_member_user",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "status"], name="api_member_user_status_idx"),
            models.Index(fields=["organization", "status"], name="api_member_org_status_idx"),
        ]


class ProjectStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"
    PENDING_DELETION = "pending_deletion", "Pending deletion"
    DELETED = "deleted", "Deleted"


class Project(TimeStampedModel, SoftDeleteModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="projects")
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=120)
    status = models.CharField(max_length=32, choices=ProjectStatus.choices, default=ProjectStatus.ACTIVE)
    default_environment = models.ForeignKey(
        "Environment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_for_projects",
    )
    created_by_user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="created_projects")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "slug"],
                condition=Q(deleted_at__isnull=True),
                name="uniq_active_project_org_slug",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "status"], name="api_project_org_status_idx"),
        ]

    def __str__(self):
        return f"{self.organization.slug}/{self.slug}"


class EnvironmentType(models.TextChoices):
    PRODUCTION = "production", "Production"
    STAGING = "staging", "Staging"
    PREVIEW = "preview", "Preview"
    DEVELOPMENT = "development", "Development"


class EnvironmentStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"
    DELETED = "deleted", "Deleted"


class Environment(TimeStampedModel, SoftDeleteModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="environments")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="environments")
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=120)
    type = models.CharField(max_length=32, choices=EnvironmentType.choices, default=EnvironmentType.PRODUCTION)
    status = models.CharField(max_length=32, choices=EnvironmentStatus.choices, default=EnvironmentStatus.ACTIVE)
    kubernetes_namespace = models.CharField(max_length=253, unique=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["project", "slug"],
                condition=Q(deleted_at__isnull=True),
                name="uniq_active_env_project_slug",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "project", "status"], name="api_env_org_project_status_idx"),
        ]

    def clean(self):
        if self.project_id and self.organization_id and self.project.organization_id != self.organization_id:
            raise ValidationError({"organization": "Environment organization must match project organization."})


class BuildJobStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    RUNNING = "running", "Running"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"


class SourceType(models.TextChoices):
    UPLOAD = "upload", "Upload"
    GIT = "git", "Git"
    REGISTRY = "registry", "Registry"


class BuildJob(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="build_jobs")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="build_jobs")
    environment = models.ForeignKey(
        Environment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="build_jobs",
    )
    requested_by_user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="requested_build_jobs")
    source_type = models.CharField(max_length=32, choices=SourceType.choices)
    source_ref = models.CharField(max_length=512)
    status = models.CharField(max_length=32, choices=BuildJobStatus.choices, default=BuildJobStatus.QUEUED)
    image_ref = models.CharField(max_length=512, blank=True)
    sbom_ref = models.CharField(max_length=512, blank=True)
    logs_ref = models.CharField(max_length=512, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "project", "status"], name="api_build_org_proj_status_idx"),
            models.Index(fields=["created_at"], name="api_build_created_idx"),
        ]

    def clean(self):
        validate_project_scope(self.organization_id, self.project)
        validate_environment_scope(self.organization_id, self.project_id, self.environment)


class DeploymentStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    BUILDING = "building", "Building"
    DEPLOYING = "deploying", "Deploying"
    RUNNING = "running", "Running"
    FAILED = "failed", "Failed"
    ROLLED_BACK = "rolled_back", "Rolled back"
    CANCELLED = "cancelled", "Cancelled"


class Deployment(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="deployments")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="deployments")
    environment = models.ForeignKey(Environment, on_delete=models.CASCADE, related_name="deployments")
    build_job = models.ForeignKey(
        BuildJob,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deployments",
    )
    version = models.CharField(max_length=100)
    image_ref = models.CharField(max_length=512)
    status = models.CharField(max_length=32, choices=DeploymentStatus.choices, default=DeploymentStatus.QUEUED)
    requested_by_user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="requested_deployments")
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["environment", "-created_at"], name="api_deploy_env_created_idx"),
            models.Index(fields=["organization", "project", "status"], name="api_deploy_org_proj_status_idx"),
        ]

    def clean(self):
        validate_environment_scope(self.organization_id, self.project_id, self.environment)
        if self.build_job:
            validate_project_scope(self.organization_id, self.build_job.project)


class DomainType(models.TextChoices):
    PLATFORM = "platform", "Platform"
    CUSTOM = "custom", "Custom"


class DomainStatus(models.TextChoices):
    PENDING_VERIFICATION = "pending_verification", "Pending verification"
    VERIFIED = "verified", "Verified"
    ACTIVE = "active", "Active"
    FAILED = "failed", "Failed"
    DISABLED = "disabled", "Disabled"
    DELETED = "deleted", "Deleted"


class Domain(TimeStampedModel, SoftDeleteModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="domains")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="domains")
    environment = models.ForeignKey(Environment, on_delete=models.CASCADE, related_name="domains")
    hostname = models.CharField(max_length=253)
    type = models.CharField(max_length=32, choices=DomainType.choices, default=DomainType.CUSTOM)
    status = models.CharField(
        max_length=32,
        choices=DomainStatus.choices,
        default=DomainStatus.PENDING_VERIFICATION,
    )
    verification_token_hash = models.CharField(max_length=255, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["hostname"],
                condition=Q(deleted_at__isnull=True),
                name="uniq_active_domain_hostname",
            ),
            models.CheckConstraint(
                condition=~Q(status=DomainStatus.ACTIVE) | Q(verified_at__isnull=False),
                name="domain_active_needs_verified",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "project", "status"], name="api_domain_org_proj_status_idx"),
        ]

    def clean(self):
        self.hostname = self.hostname.lower().rstrip(".")
        validate_environment_scope(self.organization_id, self.project_id, self.environment)

    def set_verification_token(self, token):
        self.verification_token_hash = make_password(token)

    def check_verification_token(self, token):
        return check_password(token, self.verification_token_hash)


class CertificateStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ISSUED = "issued", "Issued"
    RENEWING = "renewing", "Renewing"
    FAILED = "failed", "Failed"
    REVOKED = "revoked", "Revoked"
    EXPIRED = "expired", "Expired"


class Certificate(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="certificates")
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, related_name="certificates")
    provider = models.CharField(max_length=50, default="acme")
    status = models.CharField(max_length=32, choices=CertificateStatus.choices, default=CertificateStatus.PENDING)
    not_before = models.DateTimeField(null=True, blank=True)
    not_after = models.DateTimeField(null=True, blank=True)
    serial_number_hash = models.CharField(max_length=255, blank=True)
    kubernetes_secret_name = models.CharField(max_length=253)
    last_error = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["domain", "status"], name="api_cert_domain_status_idx"),
            models.Index(fields=["not_after"], name="api_cert_not_after_idx"),
        ]

    def clean(self):
        if self.domain_id and self.organization_id and self.domain.organization_id != self.organization_id:
            raise ValidationError({"organization": "Certificate organization must match domain organization."})


class PlanStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    ARCHIVED = "archived", "Archived"


class Plan(TimeStampedModel):
    key = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=32, choices=PlanStatus.choices, default=PlanStatus.ACTIVE)
    stripe_price_id = models.CharField(max_length=255, unique=True)
    limits = models.JSONField(default=dict)
    features = models.JSONField(default=dict)

    class Meta:
        indexes = [
            models.Index(fields=["status"], name="api_plan_status_idx"),
        ]

    def __str__(self):
        return self.key


class SubscriptionStatus(models.TextChoices):
    TRIALING = "trialing", "Trialing"
    ACTIVE = "active", "Active"
    PAST_DUE = "past_due", "Past due"
    UNPAID = "unpaid", "Unpaid"
    CANCELLED = "cancelled", "Cancelled"
    INCOMPLETE = "incomplete", "Incomplete"
    PAUSED = "paused", "Paused"


class Subscription(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    stripe_customer_id = models.CharField(max_length=255)
    stripe_subscription_id = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=32, choices=SubscriptionStatus.choices, default=SubscriptionStatus.INCOMPLETE)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization"],
                condition=Q(status__in=[SubscriptionStatus.TRIALING, SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE]),
                name="uniq_live_subscription_per_org",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "status"], name="api_sub_org_status_idx"),
            models.Index(fields=["stripe_customer_id"], name="api_sub_stripe_customer_idx"),
        ]


class InvoiceStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    OPEN = "open", "Open"
    PAID = "paid", "Paid"
    VOID = "void", "Void"
    UNCOLLECTIBLE = "uncollectible", "Uncollectible"


class Invoice(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="invoices")
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
    )
    stripe_invoice_id = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=32, choices=InvoiceStatus.choices)
    amount_due = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    hosted_invoice_url = models.URLField(max_length=2048, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(amount_due__gte=0), name="invoice_amount_due_nonnegative"),
            models.CheckConstraint(condition=Q(amount_paid__gte=0), name="invoice_amount_paid_nonneg"),
        ]
        indexes = [
            models.Index(fields=["organization", "-issued_at"], name="api_invoice_org_issued_idx"),
        ]


class UsageMetric(models.TextChoices):
    CPU_SECONDS = "cpu_seconds", "CPU seconds"
    MEMORY_GB_HOURS = "memory_gb_hours", "Memory GB hours"
    STORAGE_GB_HOURS = "storage_gb_hours", "Storage GB hours"
    EGRESS_BYTES = "egress_bytes", "Egress bytes"
    BUILD_MINUTES = "build_minutes", "Build minutes"


class UsageRecord(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="usage_records")
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="usage_records")
    environment = models.ForeignKey(
        Environment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="usage_records",
    )
    metric = models.CharField(max_length=64, choices=UsageMetric.choices)
    quantity = models.DecimalField(max_digits=20, decimal_places=6)
    unit = models.CharField(max_length=32)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    source = models.CharField(max_length=100)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gte=0), name="usage_quantity_nonnegative"),
            models.CheckConstraint(condition=Q(period_end__gt=models.F("period_start")), name="usage_period_valid"),
        ]
        indexes = [
            models.Index(fields=["organization", "period_start", "period_end"], name="api_usage_org_period_idx"),
            models.Index(fields=["project", "metric", "period_start"], name="api_usage_project_metric_idx"),
        ]

    def clean(self):
        validate_project_scope(self.organization_id, self.project)
        validate_environment_scope(self.organization_id, self.project_id, self.environment)


class ApiKeyStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    REVOKED = "revoked", "Revoked"
    EXPIRED = "expired", "Expired"


class ApiKey(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="api_keys")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True, blank=True, related_name="api_keys")
    created_by_user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="created_api_keys")
    name = models.CharField(max_length=255)
    prefix = models.CharField(max_length=32, unique=True)
    key_hash = models.CharField(max_length=255)
    scopes = models.JSONField(default=list)
    status = models.CharField(max_length=32, choices=ApiKeyStatus.choices, default=ApiKeyStatus.ACTIVE)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "status"], name="api_apikey_org_status_idx"),
        ]

    def clean(self):
        validate_project_scope(self.organization_id, self.project)

    def set_key(self, raw_key):
        self.key_hash = make_password(raw_key)

    def check_key(self, raw_key):
        return check_password(raw_key, self.key_hash)


class AuditActorType(models.TextChoices):
    USER = "user", "User"
    API_KEY = "api_key", "API key"
    SYSTEM = "system", "System"
    OPERATOR = "operator", "Operator"


class AuditResult(models.TextChoices):
    SUCCESS = "success", "Success"
    DENIED = "denied", "Denied"
    FAILED = "failed", "Failed"


class AuditLog(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs")
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs")
    actor_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs")
    actor_type = models.CharField(max_length=32, choices=AuditActorType.choices)
    actor_ref = models.CharField(max_length=255, blank=True)
    action = models.CharField(max_length=150)
    target_type = models.CharField(max_length=100)
    target_id = models.CharField(max_length=100)
    result = models.CharField(max_length=32, choices=AuditResult.choices)
    ip_address_hash = models.CharField(max_length=255, blank=True)
    user_agent_hash = models.CharField(max_length=255, blank=True)
    correlation_id = models.CharField(max_length=100)
    metadata = models.JSONField(default=dict)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "-created_at"], name="api_audit_org_created_idx"),
            models.Index(fields=["project", "-created_at"], name="api_audit_project_created_idx"),
            models.Index(fields=["actor_user", "-created_at"], name="api_audit_actor_created_idx"),
            models.Index(fields=["correlation_id"], name="api_audit_correlation_idx"),
        ]


class SecuritySeverity(models.TextChoices):
    INFO = "info", "Info"
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    CRITICAL = "critical", "Critical"


class SecurityEventStatus(models.TextChoices):
    OPEN = "open", "Open"
    TRIAGED = "triaged", "Triaged"
    RESOLVED = "resolved", "Resolved"
    FALSE_POSITIVE = "false_positive", "False positive"


class SecurityEvent(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True, related_name="security_events")
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="security_events")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="security_events")
    severity = models.CharField(max_length=32, choices=SecuritySeverity.choices)
    category = models.CharField(max_length=100)
    event_type = models.CharField(max_length=150)
    source = models.CharField(max_length=100)
    status = models.CharField(max_length=32, choices=SecurityEventStatus.choices, default=SecurityEventStatus.OPEN)
    correlation_id = models.CharField(max_length=100)
    metadata = models.JSONField(default=dict)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["severity", "status", "-created_at"], name="api_secevent_sev_status_idx"),
            models.Index(fields=["organization", "-created_at"], name="api_secevent_org_created_idx"),
        ]


class RuntimeInstanceStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    DEGRADED = "degraded", "Degraded"
    FAILED = "failed", "Failed"
    TERMINATED = "terminated", "Terminated"


class RuntimeInstance(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="runtime_instances")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="runtime_instances")
    environment = models.ForeignKey(Environment, on_delete=models.CASCADE, related_name="runtime_instances")
    deployment = models.ForeignKey(Deployment, on_delete=models.CASCADE, related_name="runtime_instances")
    kubernetes_namespace = models.CharField(max_length=253)
    workload_name = models.CharField(max_length=253)
    status = models.CharField(max_length=32, choices=RuntimeInstanceStatus.choices, default=RuntimeInstanceStatus.PENDING)
    replica_count = models.PositiveIntegerField(default=0)
    last_observed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["kubernetes_namespace", "workload_name"],
                condition=~Q(status=RuntimeInstanceStatus.TERMINATED),
                name="uniq_active_runtime_workload",
            ),
        ]
        indexes = [
            models.Index(fields=["environment", "status"], name="api_runtime_env_status_idx"),
        ]

    def clean(self):
        validate_environment_scope(self.organization_id, self.project_id, self.environment)
        if self.deployment_id and self.deployment.environment_id != self.environment_id:
            raise ValidationError({"deployment": "Runtime deployment must match environment."})


class WebhookEventStatus(models.TextChoices):
    RECEIVED = "received", "Received"
    VERIFIED = "verified", "Verified"
    PROCESSING = "processing", "Processing"
    PROCESSED = "processed", "Processed"
    FAILED = "failed", "Failed"
    IGNORED = "ignored", "Ignored"


class WebhookEvent(TimeStampedModel):
    provider = models.CharField(max_length=50)
    provider_event_id = models.CharField(max_length=255)
    event_type = models.CharField(max_length=150)
    status = models.CharField(max_length=32, choices=WebhookEventStatus.choices, default=WebhookEventStatus.RECEIVED)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="webhook_events",
    )
    signature_valid = models.BooleanField(default=False)
    payload_hash = models.CharField(max_length=255)
    received_at = models.DateTimeField(default=timezone.now)
    processed_at = models.DateTimeField(null=True, blank=True)
    processing_attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["provider", "provider_event_id"], name="uniq_webhook_provider_event"),
        ]
        indexes = [
            models.Index(fields=["status", "received_at"], name="api_webhook_status_recv_idx"),
        ]


def validate_project_scope(organization_id, project):
    if project and organization_id and project.organization_id != organization_id:
        raise ValidationError({"project": "Project must belong to the same organization."})


def validate_environment_scope(organization_id, project_id, environment):
    if not environment:
        return
    if organization_id and environment.organization_id != organization_id:
        raise ValidationError({"environment": "Environment must belong to the same organization."})
    if project_id and environment.project_id != project_id:
        raise ValidationError({"environment": "Environment must belong to the same project."})
