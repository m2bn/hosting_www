from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.views import View

from apps.api import secrets
from apps.api.auth_utils import json_error, json_ok, parse_json_body
from apps.api.models import Environment, EnvironmentStatus, ProjectSecret, ProjectSecretStatus
from apps.api.organization_views import get_user_organization_or_404, require_authenticated, require_permission
from apps.api.project_views import get_project_for_organization_or_404
from apps.api.rbac import PermissionKey


def get_environment_for_project_or_404(organization, project, environment_public_id):
    return get_object_or_404(
        Environment,
        organization=organization,
        project=project,
        public_id=environment_public_id,
        deleted_at__isnull=True,
        status=EnvironmentStatus.ACTIVE,
    )


def secret_queryset(organization, project, environment):
    return ProjectSecret.objects.filter(
        organization=organization,
        project=project,
        environment=environment,
        deleted_at__isnull=True,
    ).exclude(status=ProjectSecretStatus.DELETED)


def serialize_secret(secret):
    return {
        "public_id": str(secret.public_id),
        "name": secret.name,
        "environment_id": str(secret.environment.public_id),
        "metadata": secret.metadata,
        "current_version": secret.current_version,
        "created_at": secret.created_at.isoformat(),
        "updated_at": secret.updated_at.isoformat(),
    }


class ProjectSecretListCreateView(View):
    def get(self, request, organization_public_id, project_public_id, environment_public_id):
        context = self.context_or_error(request, organization_public_id, project_public_id, environment_public_id)
        if not isinstance(context, tuple):
            return context
        organization, project, environment = context
        items = secret_queryset(organization, project, environment).order_by("name")
        return json_ok({"results": [serialize_secret(secret) for secret in items]})

    def post(self, request, organization_public_id, project_public_id, environment_public_id):
        context = self.context_or_error(request, organization_public_id, project_public_id, environment_public_id)
        if not isinstance(context, tuple):
            return context
        organization, project, environment = context
        if error := require_permission(request, organization, PermissionKey.SECRET_MANAGE):
            return error
        data = parse_json_body(request)
        if data is None:
            return json_error("Invalid JSON.")
        try:
            secret = secrets.create_secret(
                organization=organization,
                project=project,
                environment=environment,
                name=data.get("name"),
                value=data.get("value", ""),
                metadata=data.get("metadata"),
                actor=request.user,
                request=request,
            )
        except ValidationError as exc:
            return json_error("; ".join(exc.messages))
        return json_ok(serialize_secret(secret), status=201)

    def context_or_error(self, request, organization_public_id, project_public_id, environment_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        project = get_project_for_organization_or_404(organization, project_public_id)
        environment = get_environment_for_project_or_404(organization, project, environment_public_id)
        return organization, project, environment


class ProjectSecretDetailView(View):
    def patch(self, request, organization_public_id, project_public_id, environment_public_id, secret_public_id):
        context = self.context_or_error(request, organization_public_id, project_public_id, environment_public_id, secret_public_id)
        if not isinstance(context, tuple):
            return context
        organization, project, environment, secret = context
        if error := require_permission(request, organization, PermissionKey.SECRET_MANAGE):
            return error
        data = parse_json_body(request)
        if data is None:
            return json_error("Invalid JSON.")
        try:
            secret = secrets.update_secret(
                secret=secret,
                value=data["value"] if "value" in data else None,
                metadata=data.get("metadata") if "metadata" in data else None,
                actor=request.user,
                request=request,
            )
        except ValidationError as exc:
            return json_error("; ".join(exc.messages))
        return json_ok(serialize_secret(secret))

    def delete(self, request, organization_public_id, project_public_id, environment_public_id, secret_public_id):
        context = self.context_or_error(request, organization_public_id, project_public_id, environment_public_id, secret_public_id)
        if not isinstance(context, tuple):
            return context
        organization, project, environment, secret = context
        if error := require_permission(request, organization, PermissionKey.SECRET_MANAGE):
            return error
        secrets.delete_secret(secret=secret, actor=request.user, request=request)
        return json_ok(status=204)

    def context_or_error(self, request, organization_public_id, project_public_id, environment_public_id, secret_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        project = get_project_for_organization_or_404(organization, project_public_id)
        environment = get_environment_for_project_or_404(organization, project, environment_public_id)
        secret = get_object_or_404(secret_queryset(organization, project, environment), public_id=secret_public_id)
        return organization, project, environment, secret


class ProjectSecretRotateView(View):
    def post(self, request, organization_public_id, project_public_id, environment_public_id, secret_public_id):
        context = ProjectSecretDetailView().context_or_error(
            request,
            organization_public_id,
            project_public_id,
            environment_public_id,
            secret_public_id,
        )
        if not isinstance(context, tuple):
            return context
        organization, project, environment, secret = context
        if error := require_permission(request, organization, PermissionKey.SECRET_MANAGE):
            return error
        data = parse_json_body(request)
        if data is None:
            return json_error("Invalid JSON.")
        if "value" not in data:
            return json_error("Value is required.")
        secret = secrets.rotate_secret(secret=secret, value=data["value"], actor=request.user, request=request)
        return json_ok(serialize_secret(secret))
