from django.views import View

from apps.api.auth_utils import json_error, json_ok, parse_json_body
from apps.api.custom_domains import CustomDomainError, create_domain, disable_domain, serialize_domain, verify_domain
from apps.api.models import Domain
from apps.api.organization_views import get_user_organization_or_404, require_authenticated, require_permission
from apps.api.project_views import get_project_for_organization_or_404
from apps.api.rbac import PermissionKey
from apps.api.static_deployment_views import get_environment_for_project_or_404


class DomainListCreateView(View):
    def get(self, request, organization_public_id, project_public_id, environment_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        project = get_project_for_organization_or_404(organization, project_public_id)
        environment = get_environment_for_project_or_404(organization, project, environment_public_id)
        domains = Domain.objects.filter(
            organization=organization,
            project=project,
            environment=environment,
            deleted_at__isnull=True,
        ).order_by("hostname")
        return json_ok({"results": [serialize_domain(domain) for domain in domains]})

    def post(self, request, organization_public_id, project_public_id, environment_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        if error := require_permission(request, organization, PermissionKey.DOMAIN_MANAGE):
            return error
        project = get_project_for_organization_or_404(organization, project_public_id)
        environment = get_environment_for_project_or_404(organization, project, environment_public_id)
        data = parse_json_body(request)
        if data is None:
            return json_error("Invalid JSON.")
        try:
            domain, token = create_domain(
                organization=organization,
                project=project,
                environment=environment,
                hostname=data.get("hostname"),
                actor=request.user,
                request=request,
            )
        except CustomDomainError as exc:
            return json_error(str(exc), status=400, code=exc.code)
        return json_ok(serialize_domain(domain, include_instructions=True, verification_token=token), status=201)


class DomainVerifyView(View):
    def post(self, request, organization_public_id, project_public_id, environment_public_id, domain_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        if error := require_permission(request, organization, PermissionKey.DOMAIN_MANAGE):
            return error
        project = get_project_for_organization_or_404(organization, project_public_id)
        environment = get_environment_for_project_or_404(organization, project, environment_public_id)
        try:
            domain = verify_domain(
                organization=organization,
                project=project,
                environment=environment,
                domain_public_id=domain_public_id,
                actor=request.user,
                request=request,
            )
        except Domain.DoesNotExist:
            return json_error("Domain not found.", status=404, code="not_found")
        except CustomDomainError as exc:
            return json_error(str(exc), status=400, code=exc.code)
        return json_ok(serialize_domain(domain))


class DomainDetailView(View):
    def delete(self, request, organization_public_id, project_public_id, environment_public_id, domain_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        if error := require_permission(request, organization, PermissionKey.DOMAIN_MANAGE):
            return error
        project = get_project_for_organization_or_404(organization, project_public_id)
        environment = get_environment_for_project_or_404(organization, project, environment_public_id)
        try:
            domain = disable_domain(
                organization=organization,
                project=project,
                environment=environment,
                domain_public_id=domain_public_id,
                actor=request.user,
                request=request,
            )
        except Domain.DoesNotExist:
            return json_error("Domain not found.", status=404, code="not_found")
        return json_ok(serialize_domain(domain))
