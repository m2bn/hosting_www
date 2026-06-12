from pathlib import Path

from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.views import View

from apps.api import data_protection
from apps.api.auth_utils import json_error, json_ok
from apps.api.models import DataExportRequest
from apps.api.organization_views import get_user_organization_or_404, require_authenticated, require_role
from apps.api.rbac import ROLE_OWNER


def serialize_export(export, request=None):
    return {
        "public_id": str(export.public_id),
        "scope": export.scope,
        "status": export.status,
        "download_url": data_protection.export_download_url(export, request=request) if export.status == "completed" else "",
        "download_expires_at": export.download_expires_at.isoformat() if export.download_expires_at else None,
        "file_sha256": export.file_sha256,
    }


def serialize_deletion(deletion):
    return {
        "public_id": str(deletion.public_id),
        "scope": deletion.scope,
        "status": deletion.status,
        "retention_until": deletion.retention_until.isoformat(),
    }


class UserDataExportRequestView(View):
    def post(self, request):
        if error := require_authenticated(request):
            return error
        export = data_protection.request_user_export(user=request.user, request=request)
        return json_ok(serialize_export(export, request=request), status=202)


class OrganizationDataExportRequestView(View):
    def post(self, request, organization_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        if error := require_role(request, organization, ROLE_OWNER):
            return error
        export = data_protection.request_organization_export(organization=organization, user=request.user, request=request)
        return json_ok(serialize_export(export, request=request), status=202)


class DataExportDownloadView(View):
    def get(self, request, export_public_id):
        if error := require_authenticated(request):
            return error
        export = get_object_or_404(DataExportRequest.objects.select_related("requested_by_user", "organization"), public_id=export_public_id)
        if export.requested_by_user_id != request.user.id:
            return json_error("Not found.", status=404, code="not_found")
        token = request.GET.get("token", "")
        if not data_protection.verify_export_download(export, token):
            return json_error("Export link is invalid or expired.", status=403, code="export_link_invalid")
        return FileResponse(Path(export.file_path).open("rb"), as_attachment=True, filename=Path(export.file_path).name)


class UserDeletionRequestView(View):
    def post(self, request):
        if error := require_authenticated(request):
            return error
        deletion = data_protection.request_user_deletion(user=request.user, request=request)
        return json_ok(serialize_deletion(deletion), status=202)


class OrganizationDeletionRequestView(View):
    def post(self, request, organization_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        if error := require_role(request, organization, ROLE_OWNER):
            return error
        deletion = data_protection.request_organization_deletion(organization=organization, user=request.user, request=request)
        return json_ok(serialize_deletion(deletion), status=202)
