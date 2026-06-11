from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from django.views import View

from apps.api import api_keys
from apps.api.auth_utils import json_error, json_ok, parse_json_body
from apps.api.models import ApiKey, ApiKeyStatus
from apps.api.organization_views import get_user_organization_or_404, require_authenticated, require_permission
from apps.api.project_views import get_project_for_organization_or_404
from apps.api.rbac import PermissionKey


def serialize_api_key(api_key, raw_key=None):
    data = {
        "public_id": str(api_key.public_id),
        "name": api_key.name,
        "prefix": api_key.prefix,
        "scopes": api_key.scopes,
        "scope_type": "project" if api_key.project_id else "organization",
        "organization_id": str(api_key.organization.public_id),
        "project_id": str(api_key.project.public_id) if api_key.project_id else None,
        "status": api_key.status,
        "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
        "last_used_at": api_key.last_used_at.isoformat() if api_key.last_used_at else None,
        "revoked_at": api_key.revoked_at.isoformat() if api_key.revoked_at else None,
    }
    if raw_key:
        data["key"] = raw_key
    return data


def parse_expires_at(value):
    if not value:
        return None
    parsed = parse_datetime(value)
    return parsed


def parse_scopes(data):
    scopes = data.get("scopes") or []
    if not isinstance(scopes, list) or not all(isinstance(scope, str) and scope.strip() for scope in scopes):
        return None
    return [scope.strip() for scope in scopes]


class OrganizationApiKeyListCreateView(View):
    def get(self, request, organization_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        if error := require_permission(request, organization, PermissionKey.API_KEY_MANAGE):
            return error
        queryset = ApiKey.objects.filter(organization=organization, project__isnull=True).exclude(status=ApiKeyStatus.REVOKED)
        return json_ok({"results": [serialize_api_key(api_key) for api_key in queryset]})

    def post(self, request, organization_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        if error := require_permission(request, organization, PermissionKey.API_KEY_MANAGE):
            return error
        data = parse_json_body(request)
        if data is None:
            return json_error("Invalid JSON.")
        name = (data.get("name") or "").strip()
        scopes = parse_scopes(data)
        expires_at = parse_expires_at(data.get("expires_at"))
        if not name or scopes is None:
            return json_error("Name and scopes are required.")
        api_key, raw_key = api_keys.create_api_key(
            organization=organization,
            created_by_user=request.user,
            name=name,
            scopes=scopes,
            expires_at=expires_at,
            request=request,
        )
        return json_ok(serialize_api_key(api_key, raw_key=raw_key), status=201)


class ProjectApiKeyListCreateView(View):
    def get(self, request, organization_public_id, project_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        if error := require_permission(request, organization, PermissionKey.API_KEY_MANAGE):
            return error
        project = get_project_for_organization_or_404(organization, project_public_id)
        queryset = ApiKey.objects.filter(organization=organization, project=project).exclude(status=ApiKeyStatus.REVOKED)
        return json_ok({"results": [serialize_api_key(api_key) for api_key in queryset]})

    def post(self, request, organization_public_id, project_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        if error := require_permission(request, organization, PermissionKey.API_KEY_MANAGE):
            return error
        project = get_project_for_organization_or_404(organization, project_public_id)
        data = parse_json_body(request)
        if data is None:
            return json_error("Invalid JSON.")
        name = (data.get("name") or "").strip()
        scopes = parse_scopes(data)
        expires_at = parse_expires_at(data.get("expires_at"))
        if not name or scopes is None:
            return json_error("Name and scopes are required.")
        api_key, raw_key = api_keys.create_api_key(
            organization=organization,
            project=project,
            created_by_user=request.user,
            name=name,
            scopes=scopes,
            expires_at=expires_at,
            request=request,
        )
        return json_ok(serialize_api_key(api_key, raw_key=raw_key), status=201)


class ApiKeyRotateView(View):
    def post(self, request, organization_public_id, api_key_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        if error := require_permission(request, organization, PermissionKey.API_KEY_MANAGE):
            return error
        api_key = get_object_or_404(ApiKey, organization=organization, public_id=api_key_public_id)
        raw_key = api_keys.rotate_api_key(api_key, actor=request.user, request=request)
        return json_ok(serialize_api_key(api_key, raw_key=raw_key))


class ApiKeyRevokeView(View):
    def post(self, request, organization_public_id, api_key_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        if error := require_permission(request, organization, PermissionKey.API_KEY_MANAGE):
            return error
        api_key = get_object_or_404(ApiKey, organization=organization, public_id=api_key_public_id)
        api_keys.revoke_api_key(api_key, actor=request.user, request=request)
        return json_ok(serialize_api_key(api_key))
