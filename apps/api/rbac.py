from dataclasses import dataclass

from apps.api.models import OrganizationMember, OrganizationMemberStatus, RoleScope


class PermissionKey:
    ORGANIZATION_VIEW = "organization.view"
    ORGANIZATION_MANAGE = "organization.manage"
    MEMBER_MANAGE = "member.manage"
    PROJECT_VIEW = "project.view"
    PROJECT_CREATE = "project.create"
    PROJECT_MANAGE = "project.manage"
    DEPLOYMENT_WRITE = "deployment.write"
    DOMAIN_MANAGE = "domain.manage"
    LOGS_READ = "logs.read"
    BILLING_VIEW = "billing.view"
    BILLING_MANAGE = "billing.manage"
    API_KEY_MANAGE = "api_key.manage"


ROLE_OWNER = "owner"
ROLE_ADMIN = "admin"
ROLE_DEVELOPER = "developer"
ROLE_BILLING = "billing"
ROLE_VIEWER = "viewer"


BASE_ROLE_KEYS = frozenset(
    {
        ROLE_OWNER,
        ROLE_ADMIN,
        ROLE_DEVELOPER,
        ROLE_BILLING,
        ROLE_VIEWER,
    }
)


ROLE_PERMISSIONS = {
    ROLE_OWNER: frozenset(
        {
            PermissionKey.ORGANIZATION_VIEW,
            PermissionKey.ORGANIZATION_MANAGE,
            PermissionKey.MEMBER_MANAGE,
            PermissionKey.PROJECT_VIEW,
            PermissionKey.PROJECT_CREATE,
            PermissionKey.PROJECT_MANAGE,
            PermissionKey.DEPLOYMENT_WRITE,
            PermissionKey.DOMAIN_MANAGE,
            PermissionKey.LOGS_READ,
            PermissionKey.BILLING_VIEW,
            PermissionKey.BILLING_MANAGE,
            PermissionKey.API_KEY_MANAGE,
        }
    ),
    ROLE_ADMIN: frozenset(
        {
            PermissionKey.ORGANIZATION_VIEW,
            PermissionKey.MEMBER_MANAGE,
            PermissionKey.PROJECT_VIEW,
            PermissionKey.PROJECT_CREATE,
            PermissionKey.PROJECT_MANAGE,
            PermissionKey.DEPLOYMENT_WRITE,
            PermissionKey.DOMAIN_MANAGE,
            PermissionKey.LOGS_READ,
            PermissionKey.API_KEY_MANAGE,
        }
    ),
    ROLE_DEVELOPER: frozenset(
        {
            PermissionKey.ORGANIZATION_VIEW,
            PermissionKey.PROJECT_VIEW,
            PermissionKey.DEPLOYMENT_WRITE,
            PermissionKey.LOGS_READ,
        }
    ),
    ROLE_BILLING: frozenset(
        {
            PermissionKey.ORGANIZATION_VIEW,
            PermissionKey.BILLING_VIEW,
            PermissionKey.BILLING_MANAGE,
        }
    ),
    ROLE_VIEWER: frozenset(
        {
            PermissionKey.ORGANIZATION_VIEW,
            PermissionKey.PROJECT_VIEW,
            PermissionKey.LOGS_READ,
            PermissionKey.BILLING_VIEW,
        }
    ),
}


@dataclass(frozen=True)
class MembershipContext:
    membership: OrganizationMember

    @property
    def role_key(self):
        return self.membership.role.key

    @property
    def permissions(self):
        return ROLE_PERMISSIONS.get(self.role_key, frozenset())

    def has_role(self, *role_keys):
        return self.role_key in role_keys

    def has_permission(self, permission_key):
        return permission_key in self.permissions


def get_active_membership(user, organization):
    if not user or not user.is_authenticated or not organization:
        return None

    return (
        OrganizationMember.objects.select_related("role", "organization", "user")
        .filter(
            user=user,
            organization=organization,
            status=OrganizationMemberStatus.ACTIVE,
            role__scope=RoleScope.ORGANIZATION,
        )
        .first()
    )


def get_membership_context(user, organization):
    membership = get_active_membership(user, organization)
    if membership is None:
        return None
    return MembershipContext(membership=membership)


def user_has_role(user, organization, *role_keys):
    context = get_membership_context(user, organization)
    return bool(context and context.has_role(*role_keys))


def user_has_permission(user, organization, permission_key):
    context = get_membership_context(user, organization)
    return bool(context and context.has_permission(permission_key))
