import hashlib
import logging

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.utils import timezone

from apps.api import audit_log
from apps.api.models import NotificationMessage, NotificationStatus


logger = logging.getLogger(__name__)


SECRET_CONTEXT_KEYS = {"token", "reset_token", "verification_token", "password", "secret", "api_key"}
CRITICAL_EVENTS = {
    "payment_failed",
    "deployment_failed",
    "certificate_failed",
    "limit_80",
    "limit_90",
    "limit_100",
}


TEMPLATES = {
    "email_verification": {
        "subject": "Verify your email address",
        "body": "Hello,\n\nVerify your email: {action_url}\n\nIf you did not create this account, ignore this message.",
    },
    "password_reset": {
        "subject": "Reset your password",
        "body": "Hello,\n\nReset your password: {action_url}\n\nIf you did not request this, ignore this message.",
    },
    "organization_invitation": {
        "subject": "You have been invited to an organization",
        "body": "Hello,\n\nYou have been invited to {organization_name}.",
    },
    "payment_failed": {
        "subject": "Payment failed",
        "body": "Payment failed for {organization_name}. Please update billing details.",
    },
    "invoice_paid": {
        "subject": "Invoice paid",
        "body": "Invoice {invoice_id} has been paid.",
    },
    "deployment_failed": {
        "subject": "Deployment failed",
        "body": "Deployment {deployment_id} failed for project {project_name}.",
    },
    "deployment_succeeded": {
        "subject": "Deployment succeeded",
        "body": "Deployment {deployment_id} succeeded for project {project_name}.",
    },
    "domain_verified": {
        "subject": "Domain verified",
        "body": "Domain {domain} has been verified.",
    },
    "certificate_failed": {
        "subject": "Certificate failed",
        "body": "Certificate issuance failed for {domain}.",
    },
    "limit_80": {
        "subject": "Usage reached 80%",
        "body": "{metric} usage reached 80% of the plan limit.",
    },
    "limit_90": {
        "subject": "Usage reached 90%",
        "body": "{metric} usage reached 90% of the plan limit.",
    },
    "limit_100": {
        "subject": "Usage limit reached",
        "body": "{metric} usage reached 100% of the plan limit.",
    },
}


class NotificationRateLimited(Exception):
    pass


class EmailClient:
    def send(self, *, recipient_email, subject, body):
        return send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [recipient_email], fail_silently=False)


def send_email_verification(user, raw_token, request=None):
    action_url = f"{settings.NOTIFICATION_BASE_URL}/verify-email?token={raw_token}"
    return enqueue_notification(
        event_type="email_verification",
        recipient_email=user.email,
        context={"action_url": action_url, "token": raw_token},
        request=request,
        actor=user,
        send_now=True,
    )


def send_password_reset(user, raw_token, request=None):
    action_url = f"{settings.NOTIFICATION_BASE_URL}/reset-password?token={raw_token}"
    return enqueue_notification(
        event_type="password_reset",
        recipient_email=user.email,
        context={"action_url": action_url, "token": raw_token},
        request=request,
        actor=user,
        send_now=True,
    )


def enqueue_notification(
    *,
    event_type,
    recipient_email,
    context=None,
    organization=None,
    project=None,
    request=None,
    actor=None,
    send_now=False,
    email_client=None,
):
    normalized_email = (recipient_email or "").strip().lower()
    if not normalized_email:
        raise ValueError("recipient_email is required")
    if is_rate_limited(normalized_email):
        message = _create_message(
            event_type=event_type,
            recipient_email=normalized_email,
            context=context or {},
            organization=organization,
            project=project,
            status=NotificationStatus.RATE_LIMITED,
            last_error="rate_limited",
        )
        _audit_notification(audit_log.AuditAction.NOTIFICATION_RATE_LIMITED, message, request=request, actor=actor)
        raise NotificationRateLimited("Notification rate limit exceeded.")

    record_send_attempt(normalized_email)
    message = _create_message(
        event_type=event_type,
        recipient_email=normalized_email,
        context=context or {},
        organization=organization,
        project=project,
    )
    if send_now:
        process_notification(message, runtime_context=context or {}, request=request, actor=actor, email_client=email_client)
    return message


def process_notification(message, *, runtime_context=None, request=None, actor=None, email_client=None):
    if message.attempts >= settings.NOTIFICATION_MAX_RETRY_ATTEMPTS:
        message.status = NotificationStatus.FAILED
        message.last_error = "max_retries_exceeded"
        message.save(update_fields=["status", "last_error", "updated_at"])
        return message
    email_client = email_client or EmailClient()
    template = TEMPLATES[message.template_key]
    render_context = {**message.context, **(runtime_context or {})}
    body = template["body"].format(**_safe_format_context(render_context))
    message.status = NotificationStatus.SENDING
    message.attempts += 1
    message.save(update_fields=["status", "attempts", "updated_at"])
    try:
        email_client.send(recipient_email=message.recipient_email, subject=message.subject, body=body)
    except Exception as exc:
        message.status = NotificationStatus.QUEUED if message.attempts < settings.NOTIFICATION_MAX_RETRY_ATTEMPTS else NotificationStatus.FAILED
        message.last_error = exc.__class__.__name__
        message.save(update_fields=["status", "last_error", "updated_at"])
        logger.warning(
            "notification_send_failed",
            extra={"notification_public_id": str(message.public_id), "event_type": message.event_type, "error_code": message.last_error},
        )
        if message.status == NotificationStatus.FAILED:
            _audit_notification(audit_log.AuditAction.NOTIFICATION_FAILED, message, request=request, actor=actor)
        return message

    message.status = NotificationStatus.SENT
    message.sent_at = timezone.now()
    message.last_error = ""
    message.save(update_fields=["status", "sent_at", "last_error", "updated_at"])
    if message.event_type in CRITICAL_EVENTS:
        _audit_notification(audit_log.AuditAction.NOTIFICATION_SENT, message, request=request, actor=actor)
    return message


def process_queued_notifications(limit=100):
    processed = []
    messages = NotificationMessage.objects.filter(status=NotificationStatus.QUEUED).order_by("created_at")[:limit]
    for message in messages:
        processed.append(process_notification(message))
    return processed


def is_rate_limited(email):
    return int(cache.get(_rate_limit_key(email), 0)) >= settings.NOTIFICATION_RATE_LIMIT_ATTEMPTS


def record_send_attempt(email):
    key = _rate_limit_key(email)
    attempts = int(cache.get(key, 0)) + 1
    cache.set(key, attempts, settings.NOTIFICATION_RATE_LIMIT_WINDOW_SECONDS)
    return attempts


def sanitize_context(context):
    sanitized = {}
    for key, value in (context or {}).items():
        if str(key).lower() in SECRET_CONTEXT_KEYS:
            sanitized[key] = "[REDACTED]"
        elif str(key).lower().endswith("_url") and "token=" in str(value):
            sanitized[key] = str(value).split("token=", 1)[0] + "token=[REDACTED]"
        else:
            sanitized[key] = value
    return sanitized


def recipient_hash(email):
    return hashlib.sha256(f"{settings.SECRET_KEY}:{email.lower()}".encode("utf-8")).hexdigest()


def _create_message(*, event_type, recipient_email, context, organization=None, project=None, status=NotificationStatus.QUEUED, last_error=""):
    template = TEMPLATES[event_type]
    return NotificationMessage.objects.create(
        organization=organization,
        project=project,
        recipient_email=recipient_email,
        recipient_email_hash=recipient_hash(recipient_email),
        event_type=event_type,
        template_key=event_type,
        subject=template["subject"],
        context=sanitize_context(context),
        status=status,
        last_error=last_error,
    )


def _rate_limit_key(email):
    return f"notification-send:{recipient_hash(email)}"


def _safe_format_context(context):
    class SafeDict(dict):
        def __missing__(self, key):
            return ""

    return SafeDict(context or {})


def _audit_notification(action, message, request=None, actor=None):
    audit_log.record(
        action=action,
        request=request,
        actor=actor,
        organization=message.organization,
        project=message.project,
        target_type="notification",
        target_id=message.public_id,
        metadata={"event_type": message.event_type, "status": message.status, "attempts": message.attempts},
    )
