import hashlib
import uuid

from django.conf import settings

from apps.api.models import AuditActorType, AuditLog, AuditResult, ApiKey, User


SECRET_METADATA_KEYS = {
    "password",
    "current_password",
    "new_password",
    "token",
    "secret",
    "api_key",
    "authorization",
    "recovery_code",
    "totp",
    "code",
}


class AuditAction:
    AUTH_REGISTERED = "auth.registered"
    AUTH_LOGIN_SUCCEEDED = "auth.login.succeeded"
    AUTH_LOGIN_FAILED = "auth.login.failed"
    AUTH_LOGIN_RATE_LIMITED = "auth.login.rate_limited"
    AUTH_LOGOUT = "auth.logout"
    AUTH_PASSWORD_RESET_REQUESTED = "auth.password_reset.requested"
    AUTH_PASSWORD_RESET_COMPLETED = "auth.password_reset.completed"
    AUTH_PASSWORD_CHANGED = "auth.password_changed"
    AUTH_EMAIL_VERIFIED = "auth.email_verified"
    AUTH_2FA_ENABLED = "auth.2fa.enabled"
    AUTH_2FA_DISABLED = "auth.2fa.disabled"
    AUTH_2FA_RECOVERY_CODE_USED = "auth.2fa.recovery_code_used"
    AUTH_2FA_RECOVERY_CODE_FAILED = "auth.2fa.recovery_code_failed"
    AUTH_2FA_REQUIRED = "auth.login.2fa_required"
    AUTH_2FA_FAILED = "auth.login.2fa_failed"

    ORGANIZATION_CREATED = "organization.created"
    ORGANIZATION_UPDATED = "organization.updated"
    ORGANIZATION_DELETED = "organization.deleted"
    ORGANIZATION_MEMBER_ADDED = "organization_member.added"
    ORGANIZATION_MEMBER_REMOVED = "organization_member.removed"
    ORGANIZATION_MEMBER_ROLE_CHANGED = "organization_member.role_changed"

    PROJECT_CREATED = "project.created"
    PROJECT_UPDATED = "project.updated"
    PROJECT_DELETED = "project.deleted"

    DEPLOYMENT_STARTED = "deployment.started"
    DEPLOYMENT_FAILED = "deployment.failed"
    DEPLOYMENT_ACTIVATED = "deployment.active"
    DEPLOYMENT_ROLLED_BACK = "deployment.rolled_back"

    DOMAIN_ADDED = "domain.added"
    DOMAIN_VERIFIED = "domain.verified"
    DOMAIN_ACTIVATED = "domain.activated"
    DOMAIN_DISABLED = "domain.disabled"
    DOMAIN_VERIFICATION_FAILED = "domain.verification_failed"
    DOMAIN_REMOVED = "domain.removed"
    CERTIFICATE_REQUESTED = "certificate.requested"
    CERTIFICATE_STATUS_CHANGED = "certificate.status_changed"
    CERTIFICATE_RENEWAL_REQUESTED = "certificate.renewal_requested"
    CERTIFICATE_EXPIRING = "certificate.expiring"

    BILLING_CHANGED = "billing.changed"
    BILLING_CHECKOUT_STARTED = "billing.checkout.started"
    USAGE_LIMIT_THRESHOLD_REACHED = "usage.limit_threshold_reached"
    USAGE_LIMIT_EXCEEDED = "usage.limit_exceeded"
    NOTIFICATION_SENT = "notification.sent"
    NOTIFICATION_FAILED = "notification.failed"
    NOTIFICATION_RATE_LIMITED = "notification.rate_limited"

    API_KEY_CREATED = "api_key.created"
    API_KEY_USED_HIGH_RISK = "api_key.used_high_risk"
    API_KEY_DELETED = "api_key.deleted"
    API_KEY_ROTATED = "api_key.rotated"

    SECRET_CHANGED = "secret.changed"
    SECRET_CREATED = "secret.created"
    SECRET_UPDATED = "secret.updated"
    SECRET_ROTATED = "secret.rotated"
    SECRET_DELETED = "secret.deleted"
    OPERATOR_ACTION = "operator.action"


def get_ip_address(request):
    if request is None:
        return None
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.META.get("REMOTE_ADDR")


def get_user_agent(request):
    if request is None:
        return ""
    return request.META.get("HTTP_USER_AGENT", "")[:512]


def get_request_id(request):
    if request is None:
        return str(uuid.uuid4())
    return getattr(request, "request_id", None) or request.META.get("HTTP_X_REQUEST_ID") or str(uuid.uuid4())


def hash_for_audit(value):
    if not value:
        return ""
    salted = f"{settings.SECRET_KEY}:{value}".encode("utf-8")
    return hashlib.sha256(salted).hexdigest()


def sanitize_metadata(value):
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            if str(key).lower() in SECRET_METADATA_KEYS:
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = sanitize_metadata(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_metadata(item) for item in value]
    return value


def actor_values(actor=None, actor_type=None):
    if actor_type:
        resolved_type = actor_type
    elif isinstance(actor, ApiKey):
        resolved_type = AuditActorType.API_KEY
    elif isinstance(actor, User) and actor.is_platform_staff:
        resolved_type = AuditActorType.OPERATOR
    elif isinstance(actor, User):
        resolved_type = AuditActorType.USER
    else:
        resolved_type = AuditActorType.SYSTEM

    if actor is None:
        return resolved_type, "", "anonymous", None

    public_id = getattr(actor, "public_id", None)
    actor_id = str(public_id or getattr(actor, "pk", ""))
    actor_ref = actor_id
    actor_user = actor if isinstance(actor, User) else None
    return resolved_type, actor_id, actor_ref, actor_user


def record(
    *,
    action,
    request=None,
    actor=None,
    actor_type=None,
    organization=None,
    project=None,
    target_type,
    target_id="",
    result=AuditResult.SUCCESS,
    metadata=None,
):
    resolved_actor_type, resolved_actor_id, actor_ref, actor_user = actor_values(actor, actor_type)
    ip_address = get_ip_address(request)
    user_agent = get_user_agent(request)
    request_id = get_request_id(request)
    sanitized_metadata = sanitize_metadata(metadata or {})

    return AuditLog.objects.create(
        actor_user=actor_user,
        actor_type=resolved_actor_type,
        actor_id=resolved_actor_id,
        actor_ref=actor_ref,
        organization=organization,
        project=project,
        action=action,
        target_type=target_type,
        target_id=str(target_id or ""),
        result=result,
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
        ip_address_hash=hash_for_audit(ip_address),
        user_agent_hash=hash_for_audit(user_agent),
        correlation_id=request_id,
        metadata=sanitized_metadata,
    )
