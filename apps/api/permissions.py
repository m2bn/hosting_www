from rest_framework.permissions import BasePermission

from apps.api.api_keys import mark_api_key_used
from apps.api.models import ApiKey, Project
from apps.api.rbac import (
    ROLE_ADMIN,
    ROLE_BILLING,
    ROLE_DEVELOPER,
    ROLE_OWNER,
    ROLE_VIEWER,
    PermissionKey,
    get_membership_context,
)
from apps.api.tenancy import get_organization_from_request


class OrganizationPermissionBase(BasePermission):
    message = "Organization context is required."

    def get_organization(self, request, view):
        return get_organization_from_request(request, view)

    def get_membership_context(self, request, view):
        organization = self.get_organization(request, view)
        if organization is None:
            return None
        return get_membership_context(request.user, organization)


class IsOrganizationMember(OrganizationPermissionBase):
    message = "Active organization membership is required."

    def has_permission(self, request, view):
        return self.get_membership_context(request, view) is not None


class HasOrganizationRole(OrganizationPermissionBase):
    allowed_roles = frozenset()
    message = "Required organization role is missing."

    def get_allowed_roles(self, view):
        return frozenset(getattr(view, "allowed_roles", self.allowed_roles))

    def has_permission(self, request, view):
        context = self.get_membership_context(request, view)
        return bool(context and context.has_role(*self.get_allowed_roles(view)))


class HasOrganizationPermission(OrganizationPermissionBase):
    required_permission = None
    message = "Required organization permission is missing."

    def get_required_permission(self, request, view):
        action = getattr(view, "action", None)
        action_map = getattr(view, "permission_required_by_action", {})
        if action and action in action_map:
            return action_map[action]
        return getattr(view, "required_permission", self.required_permission)

    def has_permission(self, request, view):
        required_permission = self.get_required_permission(request, view)
        if not required_permission:
            return False
        context = self.get_membership_context(request, view)
        if not context or not context.has_permission(required_permission):
            return False
        return self.has_api_key_permission(request, view, required_permission)

    def has_object_permission(self, request, view, obj):
        organization = self.get_organization(request, view)
        if organization is None:
            return False
        if getattr(getattr(obj, "_meta", None), "model_name", None) == "organization":
            if obj.id != organization.id:
                return False
        obj_organization_id = getattr(obj, "organization_id", None)
        if obj_organization_id is not None and obj_organization_id != organization.id:
            return False
        api_key = getattr(request, "auth", None)
        if isinstance(api_key, ApiKey):
            if api_key.organization_id != organization.id:
                return False
            if api_key.project_id:
                if isinstance(obj, Project) and obj.id != api_key.project_id:
                    return False
                obj_project_id = getattr(obj, "project_id", None)
                if obj_project_id is not None and obj_project_id != api_key.project_id:
                    return False
        return self.has_permission(request, view)

    def has_api_key_permission(self, request, view, required_permission):
        api_key = getattr(request, "auth", None)
        if not isinstance(api_key, ApiKey):
            return True
        organization = self.get_organization(request, view)
        if organization is None or api_key.organization_id != organization.id:
            return False
        project_public_id = getattr(view, "kwargs", {}).get("project_public_id")
        if api_key.project_id and project_public_id:
            if not Project.objects.filter(id=api_key.project_id, public_id=project_public_id).exists():
                return False
        if required_permission not in api_key.scopes:
            return False
        mark_api_key_used(api_key, request=request, scope=required_permission)
        return True


class CanManageBilling(HasOrganizationPermission):
    required_permission = PermissionKey.BILLING_MANAGE


class CanManageProjects(HasOrganizationPermission):
    required_permission = PermissionKey.PROJECT_MANAGE


class CanDeployProject(HasOrganizationPermission):
    required_permission = PermissionKey.DEPLOYMENT_WRITE


class CanViewProject(HasOrganizationPermission):
    required_permission = PermissionKey.PROJECT_VIEW


class IsOwner(HasOrganizationRole):
    allowed_roles = frozenset({ROLE_OWNER})


class IsOwnerOrAdmin(HasOrganizationRole):
    allowed_roles = frozenset({ROLE_OWNER, ROLE_ADMIN})


class IsAnyBaseOrganizationRole(HasOrganizationRole):
    allowed_roles = frozenset({ROLE_OWNER, ROLE_ADMIN, ROLE_DEVELOPER, ROLE_BILLING, ROLE_VIEWER})
