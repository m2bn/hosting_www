from django.views import View

from apps.api.auth_utils import json_error, json_ok
from apps.api.container_deployments import ContainerDeploymentError, deploy_container_from_zip, deployment_logs, rollback_container_deployment
from apps.api.static_deployment_views import get_environment_for_project_or_404, serialize_deployment
from apps.api.organization_views import get_user_organization_or_404, require_authenticated, require_permission
from apps.api.project_views import get_project_for_organization_or_404
from apps.api.rbac import PermissionKey


class ContainerDeploymentCreateView(View):
    def post(self, request, organization_public_id, project_public_id, environment_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        if error := require_permission(request, organization, PermissionKey.DEPLOYMENT_WRITE):
            return error
        project = get_project_for_organization_or_404(organization, project_public_id)
        environment = get_environment_for_project_or_404(organization, project, environment_public_id)
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return json_error("Build context ZIP is required.", code="missing_file")
        try:
            deployment = deploy_container_from_zip(
                organization=organization,
                project=project,
                environment=environment,
                uploaded_file=uploaded_file,
                actor=request.user,
                request=request,
            )
        except ContainerDeploymentError as exc:
            return json_error(str(exc), status=400, code=exc.code)
        return json_ok(serialize_deployment(deployment), status=201)


class ContainerDeploymentRollbackView(View):
    def post(self, request, organization_public_id, project_public_id, environment_public_id, deployment_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        if error := require_permission(request, organization, PermissionKey.DEPLOYMENT_WRITE):
            return error
        project = get_project_for_organization_or_404(organization, project_public_id)
        environment = get_environment_for_project_or_404(organization, project, environment_public_id)
        try:
            deployment = rollback_container_deployment(
                organization=organization,
                project=project,
                environment=environment,
                deployment_public_id=deployment_public_id,
                actor=request.user,
                request=request,
            )
        except ContainerDeploymentError as exc:
            return json_error(str(exc), status=400, code=exc.code)
        return json_ok(serialize_deployment(deployment))


class ContainerDeploymentLogsView(View):
    def get(self, request, organization_public_id, project_public_id, environment_public_id, deployment_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        if error := require_permission(request, organization, PermissionKey.LOGS_READ):
            return error
        project = get_project_for_organization_or_404(organization, project_public_id)
        environment = get_environment_for_project_or_404(organization, project, environment_public_id)
        deployment = environment.deployments.filter(organization=organization, project=project, public_id=deployment_public_id).first()
        if deployment is None:
            return json_error("Deployment not found.", status=404, code="not_found")
        return json_ok({"results": deployment_logs(deployment)})
