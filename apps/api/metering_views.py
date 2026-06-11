from django.conf import settings
from django.http import HttpResponse
from django.views import View

from apps.api.auth_utils import json_error, json_ok
from apps.api.metering import prometheus_metrics, usage_summary
from apps.api.organization_views import get_user_organization_or_404, require_authenticated
from apps.api.rbac import ROLE_ADMIN, ROLE_BILLING, ROLE_OWNER, ROLE_VIEWER, user_has_role


def can_view_usage(user, organization):
    if user_has_role(user, organization, ROLE_OWNER, ROLE_ADMIN, ROLE_BILLING):
        return True
    return bool(settings.USAGE_VIEWER_CAN_VIEW_USAGE and user_has_role(user, organization, ROLE_VIEWER))


class UsageSummaryView(View):
    def get(self, request, organization_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        if not can_view_usage(request.user, organization):
            return json_error("Permission denied.", status=403, code="permission_denied")
        return json_ok({"results": usage_summary(organization)})


class UsagePrometheusView(View):
    def get(self, request, organization_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        if not can_view_usage(request.user, organization):
            return json_error("Permission denied.", status=403, code="permission_denied")
        return HttpResponse(prometheus_metrics(organization), content_type="text/plain; version=0.0.4")
