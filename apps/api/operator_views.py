from django.shortcuts import get_object_or_404
from django.views import View

from apps.api import abuse
from apps.api.auth_utils import json_error, json_ok, parse_json_body
from apps.api.models import Organization, Project


def require_operator(request):
    if not request.user.is_authenticated:
        return json_error("Authentication required.", status=401, code="authentication_required")
    if not request.user.is_platform_staff:
        return json_error("Operator access required.", status=403, code="operator_required")
    if not request.user.mfa_enabled:
        return json_error("Two-factor verification required for operator actions.", status=403, code="operator_2fa_required")
    return None


def reason_from_request(request):
    data = parse_json_body(request)
    if data is None:
        raise abuse.AbuseError("Invalid JSON.", code="invalid_json")
    return abuse.require_reason(data.get("reason"))


def serialize_operator_project(project):
    return {
        "public_id": str(project.public_id),
        "organization_id": str(project.organization.public_id),
        "organization_name": project.organization.name,
        "name": project.name,
        "slug": project.slug,
        "status": project.status,
        "abuse_status": project.abuse_status,
        "abuse_reason": project.abuse_reason,
        "blocked_at": project.blocked_at.isoformat() if project.blocked_at else None,
        "blocked_by": project.blocked_by_user.email if project.blocked_by_user else None,
    }


def serialize_operator_organization(organization):
    return {
        "public_id": str(organization.public_id),
        "name": organization.name,
        "slug": organization.slug,
        "status": organization.status,
        "abuse_status": organization.abuse_status,
        "abuse_reason": organization.abuse_reason,
        "blocked_at": organization.blocked_at.isoformat() if organization.blocked_at else None,
        "blocked_by": organization.blocked_by_user.email if organization.blocked_by_user else None,
    }


class OperatorBlockedProjectsView(View):
    def get(self, request):
        if error := require_operator(request):
            return error
        projects = abuse.blocked_projects_queryset().order_by("-blocked_at", "slug")
        return json_ok({"results": [serialize_operator_project(project) for project in projects]})


class OperatorProjectMarkAbusiveView(View):
    def post(self, request, project_public_id):
        if error := require_operator(request):
            return error
        project = get_object_or_404(Project.objects.select_related("organization"), public_id=project_public_id, deleted_at__isnull=True)
        try:
            reason = reason_from_request(request)
            abuse.mark_project_abusive(project, operator=request.user, reason=reason, request=request)
        except abuse.AbuseError as exc:
            return json_error(str(exc), status=400, code=exc.code)
        return json_ok(serialize_operator_project(project))


class OperatorProjectBlockView(View):
    def post(self, request, project_public_id):
        if error := require_operator(request):
            return error
        project = get_object_or_404(Project.objects.select_related("organization"), public_id=project_public_id, deleted_at__isnull=True)
        try:
            reason = reason_from_request(request)
            abuse.block_project(project, operator=request.user, reason=reason, request=request)
        except abuse.AbuseError as exc:
            return json_error(str(exc), status=400, code=exc.code)
        return json_ok(serialize_operator_project(project))


class OperatorProjectUnblockView(View):
    def post(self, request, project_public_id):
        if error := require_operator(request):
            return error
        project = get_object_or_404(Project.objects.select_related("organization"), public_id=project_public_id, deleted_at__isnull=True)
        try:
            reason = reason_from_request(request)
            abuse.unblock_project(project, operator=request.user, reason=reason, request=request)
        except abuse.AbuseError as exc:
            return json_error(str(exc), status=400, code=exc.code)
        return json_ok(serialize_operator_project(project))


class OperatorOrganizationBlockView(View):
    def post(self, request, organization_public_id):
        if error := require_operator(request):
            return error
        organization = get_object_or_404(Organization, public_id=organization_public_id, deleted_at__isnull=True)
        try:
            reason = reason_from_request(request)
            abuse.block_organization(organization, operator=request.user, reason=reason, request=request)
        except abuse.AbuseError as exc:
            return json_error(str(exc), status=400, code=exc.code)
        return json_ok(serialize_operator_organization(organization))


class OperatorOrganizationUnblockView(View):
    def post(self, request, organization_public_id):
        if error := require_operator(request):
            return error
        organization = get_object_or_404(Organization, public_id=organization_public_id, deleted_at__isnull=True)
        try:
            reason = reason_from_request(request)
            abuse.unblock_organization(organization, operator=request.user, reason=reason, request=request)
        except abuse.AbuseError as exc:
            return json_error(str(exc), status=400, code=exc.code)
        return json_ok(serialize_operator_organization(organization))
