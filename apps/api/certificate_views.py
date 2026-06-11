from django.views import View

from apps.api.auth_utils import json_error, json_ok, parse_json_body
from apps.api.certificates import serialize_certificate
from apps.api.models import Certificate, Domain
from apps.api.organization_views import get_user_organization_or_404, require_authenticated
from apps.api.project_views import get_project_for_organization_or_404
from apps.api.static_deployment_views import get_environment_for_project_or_404


class CertificateListView(View):
    def get(self, request, organization_public_id, project_public_id, environment_public_id, domain_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        project = get_project_for_organization_or_404(organization, project_public_id)
        environment = get_environment_for_project_or_404(organization, project, environment_public_id)
        domain = Domain.objects.filter(
            organization=organization,
            project=project,
            environment=environment,
            public_id=domain_public_id,
            deleted_at__isnull=True,
        ).first()
        if domain is None:
            return json_error("Domain not found.", status=404, code="not_found")
        certificates = Certificate.objects.filter(organization=organization, domain=domain).order_by("-created_at")
        return json_ok({"results": [serialize_certificate(certificate) for certificate in certificates]})

    def post(self, request, organization_public_id, project_public_id, environment_public_id, domain_public_id):
        if error := require_authenticated(request):
            return error
        data = parse_json_body(request)
        if data is None:
            return json_error("Invalid JSON.")
        if "private_key" in data or "certificate_pem" in data:
            return json_error("Manual private key upload is not supported.", status=400, code="private_key_upload_not_supported")
        return json_error("Manual certificate upload is not supported.", status=405, code="manual_certificate_upload_disabled")
