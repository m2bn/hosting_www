from django.shortcuts import get_object_or_404
from django.views import View

from apps.api import artifact_scanning
from apps.api.auth_utils import json_error, json_ok, parse_json_body
from apps.api.models import ArtifactScan
from apps.api.operator_views import require_operator
from apps.api.organization_views import get_user_organization_or_404, require_authenticated, require_permission
from apps.api.project_views import get_project_for_organization_or_404
from apps.api.rbac import PermissionKey


class ProjectArtifactScanListView(View):
    def get(self, request, organization_public_id, project_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        if error := require_permission(request, organization, PermissionKey.PROJECT_VIEW):
            return error
        project = get_project_for_organization_or_404(organization, project_public_id)
        scans = (
            ArtifactScan.objects.select_related("organization", "project", "deployment", "build_job")
            .filter(organization=organization, project=project)
            .order_by("-created_at")
        )
        return json_ok({"results": [artifact_scanning.serialize_scan(scan) for scan in scans]})


class OperatorArtifactScanOverrideView(View):
    def post(self, request, scan_public_id):
        if error := require_operator(request):
            return error
        data = parse_json_body(request)
        if data is None:
            return json_error("Invalid JSON.", status=400, code="invalid_json")
        scan = get_object_or_404(
            ArtifactScan.objects.select_related("organization", "project", "deployment", "build_job", "overridden_by_user"),
            public_id=scan_public_id,
        )
        try:
            artifact_scanning.override_scan(scan, operator=request.user, reason=data.get("reason"), request=request)
        except artifact_scanning.ScanOverrideError as exc:
            return json_error(str(exc), status=403 if exc.code.startswith("operator") else 400, code=exc.code)
        return json_ok(artifact_scanning.serialize_scan(scan, include_operator_details=True))
