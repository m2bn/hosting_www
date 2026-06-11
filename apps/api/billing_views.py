from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View

from apps.api import audit_log, billing_service
from apps.api.auth_utils import json_error, json_ok, parse_json_body
from apps.api.organization_views import get_user_organization_or_404, require_authenticated, require_role
from apps.api.rbac import ROLE_BILLING, ROLE_OWNER


class SubscriptionCheckoutView(View):
    def post(self, request, organization_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        if error := require_role(request, organization, ROLE_OWNER, ROLE_BILLING):
            return error
        data = parse_json_body(request)
        if data is None:
            return json_error("Invalid JSON.")

        plan_key = (data.get("plan_key") or "").strip().lower()
        if not plan_key:
            return json_error("Plan key is required.")

        try:
            plan = billing_service.get_active_plan_or_error(plan_key)
            checkout = billing_service.create_subscription_checkout(
                organization=organization,
                plan=plan,
                user=request.user,
                request_id=getattr(request, "request_id", ""),
            )
        except billing_service.BillingError as exc:
            return json_error(str(exc), status=400, code=exc.code)

        audit_log.record(
            action=audit_log.AuditAction.BILLING_CHECKOUT_STARTED,
            request=request,
            actor=request.user,
            organization=organization,
            target_type="plan",
            target_id=plan.public_id,
            metadata={"plan_key": plan.key, "checkout_session_id": checkout["checkout_session_id"]},
        )
        return json_ok(checkout, status=201)


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(View):
    def post(self, request):
        signature = request.META.get("HTTP_STRIPE_SIGNATURE", "")
        if not signature:
            return json_error("Stripe signature is required.", status=400, code="missing_signature")
        try:
            stripe_event = billing_service.construct_webhook_event(request.body, signature)
            webhook_event, processed = billing_service.process_webhook_event(stripe_event, request.body)
        except billing_service.StripeWebhookSignatureError as exc:
            return json_error(str(exc), status=400, code=exc.code)
        except billing_service.BillingError as exc:
            return json_error(str(exc), status=400, code=exc.code)
        return json_ok(
            {
                "received": True,
                "processed": processed,
                "event_id": webhook_event.provider_event_id,
                "status": webhook_event.status,
            }
        )
