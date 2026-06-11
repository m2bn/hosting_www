import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.api import audit_log
from apps.api.models import AuditLog, Organization, OrganizationMember, OrganizationMemberStatus, Plan, Role, RoleScope, User
from apps.api.rbac import ROLE_ADMIN, ROLE_BILLING, ROLE_DEVELOPER, ROLE_OWNER, ROLE_VIEWER


@override_settings(
    STRIPE_SECRET_KEY="sk_test_unit",
    STRIPE_CHECKOUT_SUCCESS_URL="https://dashboard.example.test/billing/success",
    STRIPE_CHECKOUT_CANCEL_URL="https://dashboard.example.test/billing/cancel",
)
class BillingCheckoutTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.roles = {
            key: Role.objects.create(scope=RoleScope.ORGANIZATION, key=key, name=key.title())
            for key in [ROLE_OWNER, ROLE_ADMIN, ROLE_DEVELOPER, ROLE_BILLING, ROLE_VIEWER]
        }
        self.users = {
            key: User.objects.create_user(email=f"{key}@example.com", password="secret")
            for key in self.roles
        }
        self.outsider = User.objects.create_user(email="outsider@example.com", password="secret")
        self.org = Organization.objects.create(
            name="Acme",
            slug="acme",
            billing_email="billing@example.com",
            owner_user=self.users[ROLE_OWNER],
        )
        self.other_org = Organization.objects.create(name="Other", slug="other", owner_user=self.outsider)
        for role_key, user in self.users.items():
            OrganizationMember.objects.create(
                organization=self.org,
                user=user,
                role=self.roles[role_key],
                status=OrganizationMemberStatus.ACTIVE,
            )
        OrganizationMember.objects.create(
            organization=self.other_org,
            user=self.outsider,
            role=self.roles[ROLE_OWNER],
            status=OrganizationMemberStatus.ACTIVE,
        )
        self.plan = Plan.objects.create(
            key="pro",
            name="Pro",
            stripe_price_id="price_pro_local",
            limits={"projects": 5},
            features={"custom_domains": True, "container_deployments": True},
        )
        self.free_plan = Plan.objects.create(key="free", name="Free")

    def csrf(self):
        self.client.get(reverse("auth-csrf"))
        return self.client.cookies["csrftoken"].value

    def login_as(self, role_key):
        self.client.force_login(self.users[role_key])

    def checkout(self, role_key=None, organization=None, payload=None):
        if role_key:
            self.login_as(role_key)
        organization = organization or self.org
        return self.client.post(
            reverse("billing-checkout", kwargs={"organization_public_id": organization.public_id}),
            data=json.dumps(payload or {"plan_key": self.plan.key}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf(),
            HTTP_X_REQUEST_ID="req-checkout-test",
        )

    def stripe_stub(self):
        stripe = SimpleNamespace()
        stripe.Customer = SimpleNamespace(create=Mock(return_value=SimpleNamespace(id="cus_test_123")))
        stripe.checkout = SimpleNamespace(
            Session=SimpleNamespace(create=Mock(return_value=SimpleNamespace(id="cs_test_123", url="https://stripe.test/session")))
        )
        return stripe

    def test_owner_can_start_checkout(self):
        stripe = self.stripe_stub()
        with patch("apps.api.billing_service._stripe_module", return_value=stripe):
            response = self.checkout(ROLE_OWNER)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["checkout_url"], "https://stripe.test/session")
        self.org.refresh_from_db()
        self.assertEqual(self.org.stripe_customer_id, "cus_test_123")
        self.assertTrue(
            AuditLog.objects.filter(action=audit_log.AuditAction.BILLING_CHECKOUT_STARTED, organization=self.org).exists()
        )

    def test_billing_can_start_checkout(self):
        stripe = self.stripe_stub()
        with patch("apps.api.billing_service._stripe_module", return_value=stripe):
            response = self.checkout(ROLE_BILLING)

        self.assertEqual(response.status_code, 201)

    def test_viewer_cannot_start_checkout(self):
        response = self.checkout(ROLE_VIEWER)

        self.assertEqual(response.status_code, 403)

    def test_developer_cannot_start_checkout(self):
        response = self.checkout(ROLE_DEVELOPER)

        self.assertEqual(response.status_code, 403)

    def test_user_outside_organization_cannot_start_checkout(self):
        self.client.force_login(self.outsider)

        response = self.checkout(role_key=None, organization=self.org)

        self.assertEqual(response.status_code, 404)

    def test_plan_without_active_stripe_price_id_cannot_be_checked_out(self):
        self.login_as(ROLE_OWNER)

        response = self.checkout(role_key=None, payload={"plan_key": self.free_plan.key})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "plan_without_stripe_price")

    def test_frontend_cannot_force_another_price_id(self):
        stripe = self.stripe_stub()
        with patch("apps.api.billing_service._stripe_module", return_value=stripe):
            response = self.checkout(
                ROLE_OWNER,
                payload={"plan_key": self.plan.key, "stripe_price_id": "price_attacker_controlled"},
            )

        self.assertEqual(response.status_code, 201)
        session_kwargs = stripe.checkout.Session.create.call_args.kwargs
        self.assertEqual(session_kwargs["line_items"][0]["price"], "price_pro_local")
        self.assertNotEqual(session_kwargs["line_items"][0]["price"], "price_attacker_controlled")
        self.assertEqual(session_kwargs["metadata"]["organization_public_id"], str(self.org.public_id))
        self.assertEqual(session_kwargs["success_url"], "https://dashboard.example.test/billing/success")
        self.assertEqual(session_kwargs["cancel_url"], "https://dashboard.example.test/billing/cancel")
        self.assertIn("idempotency_key", session_kwargs)

    def test_existing_stripe_customer_is_reused(self):
        self.org.stripe_customer_id = "cus_existing"
        self.org.save(update_fields=["stripe_customer_id", "updated_at"])
        stripe = self.stripe_stub()

        with patch("apps.api.billing_service._stripe_module", return_value=stripe):
            response = self.checkout(ROLE_OWNER)

        self.assertEqual(response.status_code, 201)
        stripe.Customer.create.assert_not_called()
        self.assertEqual(stripe.checkout.Session.create.call_args.kwargs["customer"], "cus_existing")
