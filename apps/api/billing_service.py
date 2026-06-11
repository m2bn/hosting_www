import hashlib
import logging
from datetime import datetime, timezone as datetime_timezone
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.api import audit_log
from apps.api.models import Invoice, InvoiceStatus, Organization, Plan, PlanStatus, Subscription, SubscriptionStatus, WebhookEvent, WebhookEventStatus


logger = logging.getLogger(__name__)


class BillingError(Exception):
    def __init__(self, message, code="billing_error"):
        super().__init__(message)
        self.code = code


class StripeConfigurationError(BillingError):
    pass


class StripeCheckoutError(BillingError):
    pass


class StripeWebhookSignatureError(BillingError):
    pass


SUPPORTED_WEBHOOK_TYPES = {
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.paid",
    "invoice.payment_failed",
    "checkout.session.completed",
}


def get_active_plan_or_error(plan_key):
    plan = Plan.objects.filter(key=plan_key, status=PlanStatus.ACTIVE).first()
    if not plan:
        raise BillingError("Plan is not available.", code="plan_not_found")
    if not plan.stripe_price_id:
        raise BillingError("Plan is not configured for Stripe checkout.", code="plan_without_stripe_price")
    return plan


def create_subscription_checkout(organization, plan, user, request_id):
    if not settings.STRIPE_SECRET_KEY:
        raise StripeConfigurationError("Stripe checkout is not configured.", code="stripe_not_configured")
    stripe = _stripe_module()
    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        with transaction.atomic():
            locked_organization = Organization.objects.select_for_update().get(pk=organization.pk)
            customer_id = _get_or_create_customer(stripe, locked_organization, user, request_id)
            session = stripe.checkout.Session.create(
                mode="subscription",
                customer=customer_id,
                line_items=[{"price": plan.stripe_price_id, "quantity": 1}],
                success_url=settings.STRIPE_CHECKOUT_SUCCESS_URL,
                cancel_url=settings.STRIPE_CHECKOUT_CANCEL_URL,
                client_reference_id=str(locked_organization.public_id),
                metadata=_stripe_metadata(locked_organization, plan),
                subscription_data={"metadata": _stripe_metadata(locked_organization, plan)},
                idempotency_key=_checkout_idempotency_key(locked_organization, plan, user, request_id),
            )
    except BillingError:
        raise
    except Exception as exc:
        raise StripeCheckoutError(_safe_stripe_error(exc), code="stripe_checkout_failed") from exc

    return {
        "checkout_session_id": session.id,
        "checkout_url": session.url,
        "stripe_customer_id": customer_id,
        "plan_key": plan.key,
    }


def construct_webhook_event(payload, signature):
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise StripeConfigurationError("Stripe webhook is not configured.", code="stripe_webhook_not_configured")
    stripe = _stripe_module()
    try:
        return stripe.Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)
    except Exception as exc:
        raise StripeWebhookSignatureError("Invalid Stripe webhook signature.", code="invalid_signature") from exc


def process_webhook_event(stripe_event, payload):
    event_id = stripe_event.get("id")
    event_type = stripe_event.get("type")
    if not event_id or not event_type:
        raise BillingError("Stripe webhook event is malformed.", code="malformed_webhook")

    payload_hash = hashlib.sha256(payload).hexdigest()
    with transaction.atomic():
        webhook_event, created = WebhookEvent.objects.select_for_update().get_or_create(
            provider="stripe",
            provider_event_id=event_id,
            defaults={
                "event_type": event_type,
                "status": WebhookEventStatus.VERIFIED,
                "signature_valid": True,
                "payload_hash": payload_hash,
            },
        )
        if not created:
            if webhook_event.status == WebhookEventStatus.PROCESSED:
                return webhook_event, False
            if webhook_event.payload_hash != payload_hash:
                webhook_event.status = WebhookEventStatus.FAILED
                webhook_event.last_error = "Duplicate Stripe event id with different payload hash."
                webhook_event.save(update_fields=["status", "last_error", "updated_at"])
                raise BillingError("Duplicate Stripe event id has a different payload.", code="duplicate_payload_mismatch")

        webhook_event.status = WebhookEventStatus.PROCESSING
        webhook_event.signature_valid = True
        webhook_event.processing_attempts += 1
        webhook_event.save(update_fields=["status", "signature_valid", "processing_attempts", "updated_at"])

        try:
            if event_type in SUPPORTED_WEBHOOK_TYPES:
                organization = _apply_webhook_event(stripe_event)
                webhook_event.organization = organization
                webhook_event.status = WebhookEventStatus.PROCESSED
            else:
                organization = None
                webhook_event.status = WebhookEventStatus.IGNORED
            webhook_event.processed_at = timezone.now()
            webhook_event.last_error = ""
            webhook_event.save(update_fields=["organization", "status", "processed_at", "last_error", "updated_at"])
            return webhook_event, True
        except Exception as exc:
            webhook_event.status = WebhookEventStatus.FAILED
            webhook_event.last_error = _safe_stripe_error(exc)
            webhook_event.save(update_fields=["status", "last_error", "updated_at"])
            logger.warning(
                "stripe_webhook_processing_failed",
                extra={"event_id": event_id, "event_type": event_type, "error_code": getattr(exc, "code", "billing_error")},
            )
            raise


def _get_or_create_customer(stripe, organization, user, request_id):
    if organization.stripe_customer_id:
        return organization.stripe_customer_id

    customer = stripe.Customer.create(
        email=organization.billing_email or user.email,
        name=organization.name,
        metadata={"organization_public_id": str(organization.public_id)},
        idempotency_key=f"stripe-customer:{organization.public_id}:{request_id}",
    )
    organization.stripe_customer_id = customer.id
    organization.save(update_fields=["stripe_customer_id", "updated_at"])
    return customer.id


def _apply_webhook_event(stripe_event):
    event_type = stripe_event["type"]
    data_object = stripe_event.get("data", {}).get("object", {})
    if event_type == "checkout.session.completed":
        organization = _organization_from_stripe_object(data_object)
        _verify_or_bind_customer(organization, data_object.get("customer"))
        audit_log.record(
            action=audit_log.AuditAction.BILLING_CHANGED,
            actor_type="system",
            organization=organization,
            target_type="stripe_checkout_session",
            target_id=data_object.get("id", ""),
            metadata={"event_type": event_type},
        )
        return organization
    if event_type.startswith("customer.subscription."):
        organization = _upsert_subscription(data_object, deleted=event_type.endswith(".deleted"))
        audit_log.record(
            action=audit_log.AuditAction.BILLING_CHANGED,
            actor_type="system",
            organization=organization,
            target_type="subscription",
            target_id=data_object.get("id", ""),
            metadata={"event_type": event_type, "status": data_object.get("status")},
        )
        return organization
    if event_type in {"invoice.paid", "invoice.payment_failed"}:
        organization = _upsert_invoice(data_object, paid=event_type == "invoice.paid")
        audit_log.record(
            action=audit_log.AuditAction.BILLING_CHANGED,
            actor_type="system",
            organization=organization,
            target_type="invoice",
            target_id=data_object.get("id", ""),
            metadata={"event_type": event_type},
        )
        return organization
    return None


def _upsert_subscription(subscription_object, deleted=False):
    organization = _organization_from_stripe_object(subscription_object)
    customer_id = subscription_object.get("customer", "")
    _verify_or_bind_customer(organization, customer_id)
    plan = _plan_from_subscription_object(subscription_object)
    stripe_subscription_id = subscription_object.get("id", "")
    if not stripe_subscription_id:
        raise BillingError("Stripe subscription id is missing.", code="missing_subscription_id")

    status = SubscriptionStatus.CANCELED if deleted else _subscription_status(subscription_object.get("status"))
    subscription, _ = Subscription.objects.update_or_create(
        stripe_subscription_id=stripe_subscription_id,
        defaults={
            "organization": organization,
            "plan": plan,
            "stripe_customer_id": customer_id or organization.stripe_customer_id,
            "status": status,
            "current_period_start": _timestamp(subscription_object.get("current_period_start")),
            "current_period_end": _timestamp(subscription_object.get("current_period_end")),
            "cancel_at_period_end": bool(subscription_object.get("cancel_at_period_end", False)),
        },
    )
    return subscription.organization


def _upsert_invoice(invoice_object, paid):
    organization = _organization_from_stripe_object(invoice_object)
    customer_id = invoice_object.get("customer", "")
    _verify_or_bind_customer(organization, customer_id)
    subscription = None
    subscription_id = invoice_object.get("subscription")
    if subscription_id:
        subscription = Subscription.objects.filter(organization=organization, stripe_subscription_id=subscription_id).first()
    stripe_invoice_id = invoice_object.get("id", "")
    if not stripe_invoice_id:
        raise BillingError("Stripe invoice id is missing.", code="missing_invoice_id")

    Invoice.objects.update_or_create(
        stripe_invoice_id=stripe_invoice_id,
        defaults={
            "organization": organization,
            "subscription": subscription,
            "status": InvoiceStatus.PAID if paid else InvoiceStatus.OPEN,
            "amount_due": _cents_to_decimal(invoice_object.get("amount_due", 0)),
            "amount_paid": _cents_to_decimal(invoice_object.get("amount_paid", 0)),
            "currency": (invoice_object.get("currency") or "usd").lower(),
            "hosted_invoice_url": invoice_object.get("hosted_invoice_url", "") or "",
            "issued_at": _timestamp(invoice_object.get("created")),
            "paid_at": _timestamp(invoice_object.get("status_transitions", {}).get("paid_at")) if paid else None,
        },
    )
    return organization


def _organization_from_stripe_object(stripe_object):
    metadata = stripe_object.get("metadata") or {}
    organization_public_id = metadata.get("organization_public_id")
    customer_id = stripe_object.get("customer", "")
    organization = None
    if organization_public_id:
        organization = Organization.objects.filter(public_id=organization_public_id).first()
    if organization and customer_id and organization.stripe_customer_id and organization.stripe_customer_id != customer_id:
        raise BillingError("Stripe customer does not match organization.", code="customer_organization_mismatch")
    if organization:
        return organization
    if customer_id:
        organization = Organization.objects.filter(stripe_customer_id=customer_id).first()
    if not organization:
        raise BillingError("Organization could not be resolved for Stripe event.", code="organization_not_found")
    return organization


def _verify_or_bind_customer(organization, customer_id):
    if not customer_id:
        return
    if organization.stripe_customer_id and organization.stripe_customer_id != customer_id:
        raise BillingError("Stripe customer does not match organization.", code="customer_organization_mismatch")
    if not organization.stripe_customer_id:
        organization.stripe_customer_id = customer_id
        organization.save(update_fields=["stripe_customer_id", "updated_at"])


def _plan_from_subscription_object(subscription_object):
    price_id = None
    items = subscription_object.get("items", {}).get("data", [])
    if items:
        price_id = (items[0].get("price") or {}).get("id")
    metadata = subscription_object.get("metadata") or {}
    plan_key = metadata.get("plan_key")
    queryset = Plan.objects.filter(status=PlanStatus.ACTIVE)
    plan = queryset.filter(stripe_price_id=price_id).first() if price_id else None
    if not plan and plan_key:
        plan = queryset.filter(key=plan_key).first()
    if not plan:
        raise BillingError("Stripe subscription price is not mapped to a local plan.", code="plan_not_found")
    return plan


def _subscription_status(stripe_status):
    mapping = {
        "incomplete": SubscriptionStatus.INCOMPLETE,
        "trialing": SubscriptionStatus.TRIALING,
        "active": SubscriptionStatus.ACTIVE,
        "past_due": SubscriptionStatus.PAST_DUE,
        "canceled": SubscriptionStatus.CANCELED,
        "unpaid": SubscriptionStatus.UNPAID,
    }
    return mapping.get(stripe_status, SubscriptionStatus.INCOMPLETE)


def _timestamp(value):
    if not value:
        return None
    return datetime.fromtimestamp(int(value), tz=datetime_timezone.utc)


def _cents_to_decimal(value):
    return Decimal(value or 0) / Decimal("100")


def _stripe_metadata(organization, plan):
    return {
        "organization_public_id": str(organization.public_id),
        "plan_key": plan.key,
        "plan_public_id": str(plan.public_id),
    }


def _checkout_idempotency_key(organization, plan, user, request_id):
    return f"checkout:{organization.public_id}:{plan.public_id}:{user.public_id}:{request_id}"


def _stripe_module():
    try:
        import stripe
    except ImportError as exc:
        raise StripeConfigurationError("Stripe SDK is not installed.", code="stripe_sdk_missing") from exc
    return stripe


def _safe_stripe_error(exc):
    message = str(exc)
    secret = settings.STRIPE_SECRET_KEY
    if secret:
        message = message.replace(secret, "[REDACTED]")
    return message[:500] or "Stripe checkout failed."
