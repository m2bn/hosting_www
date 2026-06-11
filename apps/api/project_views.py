from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views import View

from apps.api import audit_log
from apps.api.auth_utils import json_error, json_ok, parse_json_body
from apps.api.entitlements import can_create_project
from apps.api.models import Environment, EnvironmentStatus, EnvironmentType, Project, ProjectStatus
from apps.api.organization_views import get_user_organization_or_404, require_authenticated, require_permission
from apps.api.rbac import PermissionKey


def project_queryset_for_organization(organization, include_deleted=False):
    queryset = Project.objects.filter(organization=organization)
    if not include_deleted:
        queryset = queryset.filter(deleted_at__isnull=True).exclude(status=ProjectStatus.DELETED)
    return queryset


def get_project_for_organization_or_404(organization, project_public_id, include_deleted=False):
    return get_object_or_404(
        project_queryset_for_organization(organization, include_deleted=include_deleted),
        public_id=project_public_id,
    )


def serialize_project(project):
    return {
        "public_id": str(project.public_id),
        "organization_id": str(project.organization.public_id),
        "name": project.name,
        "slug": project.slug,
        "status": project.status,
        "deleted_at": project.deleted_at.isoformat() if project.deleted_at else None,
    }


def default_namespace(organization, project):
    return f"org-{organization.slug}-project-{project.slug}-{str(project.public_id)[:8]}-production"[:253]


class ProjectListCreateView(View):
    def get(self, request, organization_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        projects = project_queryset_for_organization(organization)
        return json_ok({"results": [serialize_project(project) for project in projects]})

    @transaction.atomic
    def post(self, request, organization_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        if error := require_permission(request, organization, PermissionKey.PROJECT_CREATE):
            return error
        entitlement = can_create_project(organization)
        if not entitlement.allowed:
            return json_error("Project creation is not allowed by current entitlements.", status=403, code="entitlement_denied")
        data = parse_json_body(request)
        if data is None:
            return json_error("Invalid JSON.")
        name = (data.get("name") or "").strip()
        slug = (data.get("slug") or "").strip().lower()
        if not name or not slug:
            return json_error("Name and slug are required.")
        project = Project.objects.create(
            organization=organization,
            name=name,
            slug=slug,
            created_by_user=request.user,
        )
        environment = Environment.objects.create(
            organization=organization,
            project=project,
            name="Production",
            slug="production",
            type=EnvironmentType.PRODUCTION,
            status=EnvironmentStatus.ACTIVE,
            kubernetes_namespace=default_namespace(organization, project),
        )
        project.default_environment = environment
        project.save(update_fields=["default_environment", "updated_at"])
        audit_log.record(
            action=audit_log.AuditAction.PROJECT_CREATED,
            request=request,
            actor=request.user,
            organization=organization,
            project=project,
            target_type="project",
            target_id=project.public_id,
        )
        return json_ok(serialize_project(project), status=201)


class ProjectDetailView(View):
    def get(self, request, organization_public_id, project_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        project = get_project_for_organization_or_404(organization, project_public_id)
        return json_ok(serialize_project(project))

    @transaction.atomic
    def patch(self, request, organization_public_id, project_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        if error := require_permission(request, organization, PermissionKey.PROJECT_MANAGE):
            return error
        project = get_project_for_organization_or_404(organization, project_public_id)
        data = parse_json_body(request)
        if data is None:
            return json_error("Invalid JSON.")
        for field in ["name"]:
            if field in data:
                setattr(project, field, (data.get(field) or "").strip())
        project.save(update_fields=["name", "updated_at"])
        audit_log.record(
            action=audit_log.AuditAction.PROJECT_UPDATED,
            request=request,
            actor=request.user,
            organization=organization,
            project=project,
            target_type="project",
            target_id=project.public_id,
            metadata={"fields": [field for field in ["name"] if field in data]},
        )
        return json_ok(serialize_project(project))

    @transaction.atomic
    def delete(self, request, organization_public_id, project_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        if error := require_permission(request, organization, PermissionKey.PROJECT_MANAGE):
            return error
        project = get_project_for_organization_or_404(organization, project_public_id)
        project.status = ProjectStatus.DELETED
        project.deleted_at = timezone.now()
        project.save(update_fields=["status", "deleted_at", "updated_at"])
        audit_log.record(
            action=audit_log.AuditAction.PROJECT_DELETED,
            request=request,
            actor=request.user,
            organization=organization,
            project=project,
            target_type="project",
            target_id=project.public_id,
        )
        return json_ok(status=204)


class ProjectArchiveView(View):
    @transaction.atomic
    def post(self, request, organization_public_id, project_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        if error := require_permission(request, organization, PermissionKey.PROJECT_MANAGE):
            return error
        project = get_project_for_organization_or_404(organization, project_public_id)
        project.status = ProjectStatus.SUSPENDED
        project.save(update_fields=["status", "updated_at"])
        audit_log.record(
            action=audit_log.AuditAction.PROJECT_UPDATED,
            request=request,
            actor=request.user,
            organization=organization,
            project=project,
            target_type="project",
            target_id=project.public_id,
            metadata={"status": ProjectStatus.SUSPENDED},
        )
        return json_ok(serialize_project(project))


class ProjectRestoreView(View):
    @transaction.atomic
    def post(self, request, organization_public_id, project_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        if error := require_permission(request, organization, PermissionKey.PROJECT_MANAGE):
            return error
        project = get_project_for_organization_or_404(organization, project_public_id, include_deleted=True)
        project.status = ProjectStatus.ACTIVE
        project.deleted_at = None
        project.save(update_fields=["status", "deleted_at", "updated_at"])
        audit_log.record(
            action=audit_log.AuditAction.PROJECT_UPDATED,
            request=request,
            actor=request.user,
            organization=organization,
            project=project,
            target_type="project",
            target_id=project.public_id,
            metadata={"status": ProjectStatus.ACTIVE},
        )
        return json_ok(serialize_project(project))
