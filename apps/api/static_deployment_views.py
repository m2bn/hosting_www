from django.shortcuts import get_object_or_404
from django.views import View

from apps.api import abuse
from apps.api.auth_utils import json_error, json_ok
from apps.api.models import Deployment, Environment, EnvironmentStatus
from apps.api.organization_views import get_user_organization_or_404, require_authenticated, require_permission
from apps.api.project_views import get_project_for_organization_or_404
from apps.api.rbac import PermissionKey
from apps.api.static_deployments import StaticDeploymentError, deploy_static_zip, rollback_static_deployment


def get_environment_for_project_or_404(organization, project, environment_public_id):
    return get_object_or_404(
        Environment,
        organization=organization,
        project=project,
        public_id=environment_public_id,
        deleted_at__isnull=True,
        status=EnvironmentStatus.ACTIVE,
    )


def serialize_deployment(deployment):
    return {
        "public_id": str(deployment.public_id),
        "project_id": str(deployment.project.public_id),
        "environment_id": str(deployment.environment.public_id),
        "status": deployment.status,
        "artifact_ref": deployment.image_ref,
        "build_job_id": str(deployment.build_job.public_id) if deployment.build_job else None,
        "started_at": deployment.started_at.isoformat() if deployment.started_at else None,
        "finished_at": deployment.finished_at.isoformat() if deployment.finished_at else None,
    }


class StaticDeploymentCreateView(View):
    def post(self, request, organization_public_id, project_public_id, environment_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        if error := require_permission(request, organization, PermissionKey.DEPLOYMENT_WRITE):
            return error
        project = get_project_for_organization_or_404(organization, project_public_id)
        try:
            abuse.ensure_project_can_deploy(project)
        except abuse.AbuseError as exc:
            return json_error(str(exc), status=403, code=exc.code)
        environment = get_environment_for_project_or_404(organization, project, environment_public_id)
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return json_error("ZIP file is required.", code="missing_file")
        try:
            deployment = deploy_static_zip(
                organization=organization,
                project=project,
                environment=environment,
                uploaded_file=uploaded_file,
                actor=request.user,
                request=request,
            )
        except StaticDeploymentError as exc:
            return json_error(str(exc), status=400, code=exc.code)
        return json_ok(serialize_deployment(deployment), status=201)


class StaticDeploymentRollbackView(View):
    def post(self, request, organization_public_id, project_public_id, environment_public_id, deployment_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        if error := require_permission(request, organization, PermissionKey.DEPLOYMENT_WRITE):
            return error
        project = get_project_for_organization_or_404(organization, project_public_id)
        environment = get_environment_for_project_or_404(organization, project, environment_public_id)
        try:
            deployment = rollback_static_deployment(
                organization=organization,
                project=project,
                environment=environment,
                deployment_public_id=deployment_public_id,
                actor=request.user,
                request=request,
            )
        except Deployment.DoesNotExist:
            return json_error("Deployment not found.", status=404, code="not_found")
        except StaticDeploymentError as exc:
            return json_error(str(exc), status=400, code=exc.code)
        return json_ok(serialize_deployment(deployment))
