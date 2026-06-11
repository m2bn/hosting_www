import json
from decimal import Decimal
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.api import audit_log, billing_service
from apps.api.models import AuditLog, Invoice, InvoiceStatus, Organization, Plan, Subscription, SubscriptionStatus, User, WebhookEvent, WebhookEventStatus


@override_settings(STRIPE_WEBHOOK_SECRET="whsec_unit")
class StripeWebhookTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.user = User.objects.create_user(email="owner@example.com", password="secret")
        self.org = Organization.objects.create(
            name="Acme",
            slug="acme",
            billing_email="billing@example.com",
            owner_user=self.user,
            stripe_customer_id="cus_acme",
        )
        self.plan = Plan.objects.create(
            key="pro",
            name="Pro",
            stripe_price_id="price_pro",
            limits={"projects": 5},
            features={"custom_domains": True, "container_deployments": True},
        )

    def post_event(self, event, payload=None, signature="sig_valid"):
        payload = payload if payload is not None else {"id": event.get("id"), "type": event.get("type")}
        with patch("apps.api.billing_service.construct_webhook_event", return_value=event):
            return self.client.post(
                reverse("stripe-webhook"),
                data=json.dumps(payload),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE=signature,
            )

    def metadata(self):
        return {"organization_public_id": str(self.org.public_id), "plan_key": self.plan.key}

    def subscription_object(self, status="active", subscription_id="sub_123"):
        return {
            "id": subscription_id,
            "customer": self.org.stripe_customer_id,
            "status": status,
            "metadata": self.metadata(),
            "current_period_start": 1_700_000_000,
            "current_period_end": 1_702_592_000,
            "cancel_at_period_end": False,
            "items": {"data": [{"price": {"id": self.plan.stripe_price_id}}]},
        }

    def subscription_event(self, event_type, status="active", event_id="evt_sub"):
        return {
            "id": event_id,
            "type": event_type,
            "data": {"object": self.subscription_object(status=status)},
        }

    def invoice_object(self, invoice_id="in_123", subscription_id="sub_123", amount_paid=2500):
        return {
            "id": invoice_id,
            "customer": self.org.stripe_customer_id,
            "subscription": subscription_id,
            "metadata": self.metadata(),
            "amount_due": 2500,
            "amount_paid": amount_paid,
            "currency": "usd",
            "hosted_invoice_url": "https://stripe.test/invoice",
            "created": 1_700_000_000,
            "status_transitions": {"paid_at": 1_700_000_100},
        }

    def test_missing_signature_is_rejected(self):
        response = self.client.post(
            reverse("stripe-webhook"),
            data=json.dumps({"id": "evt_missing", "type": "checkout.session.completed"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "missing_signature")

    def test_invalid_signature_is_rejected(self):
        with patch(
            "apps.api.billing_service.construct_webhook_event",
            side_effect=billing_service.StripeWebhookSignatureError("Invalid Stripe webhook signature.", "invalid_signature"),
        ):
            response = self.client.post(
                reverse("stripe-webhook"),
                data=json.dumps({"id": "evt_invalid", "type": "checkout.session.completed"}),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="bad",
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_signature")
        self.assertFalse(WebhookEvent.objects.filter(provider_event_id="evt_invalid").exists())

    def test_checkout_session_completed_binds_customer_and_audits(self):
        self.org.stripe_customer_id = ""
        self.org.save(update_fields=["stripe_customer_id", "updated_at"])
        event = {
            "id": "evt_checkout",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_123",
                    "customer": "cus_new",
                    "metadata": self.metadata(),
                }
            },
        }

        response = self.post_event(event)

        self.assertEqual(response.status_code, 200)
        self.org.refresh_from_db()
        self.assertEqual(self.org.stripe_customer_id, "cus_new")
        webhook = WebhookEvent.objects.get(provider_event_id="evt_checkout")
        self.assertEqual(webhook.status, WebhookEventStatus.PROCESSED)
        self.assertEqual(webhook.organization, self.org)
        self.assertTrue(AuditLog.objects.filter(action=audit_log.AuditAction.BILLING_CHANGED, organization=self.org).exists())

    def test_subscription_created_updates_local_subscription(self):
        event = self.subscription_event("customer.subscription.created", status="active", event_id="evt_sub_created")

        response = self.post_event(event)

        self.assertEqual(response.status_code, 200)
        subscription = Subscription.objects.get(stripe_subscription_id="sub_123")
        self.assertEqual(subscription.organization, self.org)
        self.assertEqual(subscription.plan, self.plan)
        self.assertEqual(subscription.status, SubscriptionStatus.ACTIVE)

    def test_subscription_updated_updates_status(self):
        Subscription.objects.create(
            organization=self.org,
            plan=self.plan,
            stripe_customer_id=self.org.stripe_customer_id,
            stripe_subscription_id="sub_123",
            status=SubscriptionStatus.ACTIVE,
        )
        event = self.subscription_event("customer.subscription.updated", status="past_due", event_id="evt_sub_updated")

        response = self.post_event(event)

        self.assertEqual(response.status_code, 200)
        subscription = Subscription.objects.get(stripe_subscription_id="sub_123")
        self.assertEqual(subscription.status, SubscriptionStatus.PAST_DUE)

    def test_subscription_deleted_cancels_local_subscription(self):
        Subscription.objects.create(
            organization=self.org,
            plan=self.plan,
            stripe_customer_id=self.org.stripe_customer_id,
            stripe_subscription_id="sub_123",
            status=SubscriptionStatus.ACTIVE,
        )
        event = self.subscription_event("customer.subscription.deleted", status="canceled", event_id="evt_sub_deleted")

        response = self.post_event(event)

        self.assertEqual(response.status_code, 200)
        subscription = Subscription.objects.get(stripe_subscription_id="sub_123")
        self.assertEqual(subscription.status, SubscriptionStatus.CANCELED)

    def test_invoice_paid_upserts_invoice(self):
        subscription = Subscription.objects.create(
            organization=self.org,
            plan=self.plan,
            stripe_customer_id=self.org.stripe_customer_id,
            stripe_subscription_id="sub_123",
            status=SubscriptionStatus.ACTIVE,
        )
        event = {
            "id": "evt_invoice_paid",
            "type": "invoice.paid",
            "data": {"object": self.invoice_object()},
        }

        response = self.post_event(event)

        self.assertEqual(response.status_code, 200)
        invoice = Invoice.objects.get(stripe_invoice_id="in_123")
        self.assertEqual(invoice.organization, self.org)
        self.assertEqual(invoice.subscription, subscription)
        self.assertEqual(invoice.status, InvoiceStatus.PAID)
        self.assertEqual(invoice.amount_paid, Decimal("25"))
        self.assertIsNotNone(invoice.paid_at)

    def test_invoice_payment_failed_upserts_open_invoice(self):
        event = {
            "id": "evt_invoice_failed",
            "type": "invoice.payment_failed",
            "data": {"object": self.invoice_object(invoice_id="in_failed", amount_paid=0)},
        }

        response = self.post_event(event)

        self.assertEqual(response.status_code, 200)
        invoice = Invoice.objects.get(stripe_invoice_id="in_failed")
        self.assertEqual(invoice.status, InvoiceStatus.OPEN)
        self.assertEqual(invoice.amount_due, Decimal("25"))
        self.assertEqual(invoice.amount_paid, Decimal("0"))
        self.assertIsNone(invoice.paid_at)

    def test_duplicate_webhook_is_idempotent(self):
        event = self.subscription_event("customer.subscription.created", event_id="evt_duplicate")

        first_response = self.post_event(event)
        second_response = self.post_event(event)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertTrue(first_response.json()["processed"])
        self.assertFalse(second_response.json()["processed"])
        self.assertEqual(Subscription.objects.filter(stripe_subscription_id="sub_123").count(), 1)
        webhook = WebhookEvent.objects.get(provider_event_id="evt_duplicate")
        self.assertEqual(webhook.processing_attempts, 1)

    def test_replay_webhook_returns_ok_without_second_state_change(self):
        event = self.subscription_event("customer.subscription.created", event_id="evt_replay")
        self.post_event(event)
        Subscription.objects.filter(stripe_subscription_id="sub_123").update(status=SubscriptionStatus.PAST_DUE)

        response = self.post_event(event)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["processed"])
        subscription = Subscription.objects.get(stripe_subscription_id="sub_123")
        self.assertEqual(subscription.status, SubscriptionStatus.PAST_DUE)
