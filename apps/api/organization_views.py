from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views import View

from apps.api import audit_log
from apps.api.auth_utils import json_error, json_ok, parse_json_body
from apps.api.models import (
    Organization,
    OrganizationMember,
    OrganizationMemberStatus,
    OrganizationStatus,
    Role,
    RoleScope,
    User,
)
from apps.api.rbac import ROLE_OWNER, BASE_ROLE_KEYS, PermissionKey, user_has_permission, user_has_role


def role_for_key(role_key):
    if role_key not in BASE_ROLE_KEYS:
        return None
    role, _ = Role.objects.get_or_create(
        scope=RoleScope.ORGANIZATION,
        key=role_key,
        defaults={"name": role_key.title(), "is_system": True},
    )
    return role


def active_memberships_for_user(user):
    return OrganizationMember.objects.filter(
        user=user,
        status=OrganizationMemberStatus.ACTIVE,
        organization__deleted_at__isnull=True,
    ).select_related("organization", "role")


def organization_queryset_for_user(user):
    return (
        Organization.objects.filter(
            members__user=user,
            members__status=OrganizationMemberStatus.ACTIVE,
            deleted_at__isnull=True,
        )
        .exclude(status=OrganizationStatus.DELETED)
        .distinct()
    )


def get_user_organization_or_404(user, organization_public_id):
    return get_object_or_404(organization_queryset_for_user(user), public_id=organization_public_id)


def serialize_organization(organization):
    return {
        "public_id": str(organization.public_id),
        "name": organization.name,
        "slug": organization.slug,
        "status": organization.status,
        "billing_email": organization.billing_email,
    }


def serialize_member(member):
    return {
        "public_id": str(member.public_id),
        "user": {
            "public_id": str(member.user.public_id),
            "email": member.user.email,
            "full_name": member.user.full_name,
        },
        "role": member.role.key,
        "status": member.status,
        "joined_at": member.joined_at.isoformat() if member.joined_at else None,
    }


def active_owner_count(organization):
    return OrganizationMember.objects.filter(
        organization=organization,
        status=OrganizationMemberStatus.ACTIVE,
        role__scope=RoleScope.ORGANIZATION,
        role__key=ROLE_OWNER,
    ).count()


def require_authenticated(request):
    if not request.user.is_authenticated:
        return json_error("Authentication is required.", status=401, code="not_authenticated")
    return None


def require_permission(request, organization, permission_key):
    if not user_has_permission(request.user, organization, permission_key):
        return json_error("Permission denied.", status=403, code="permission_denied")
    return None


def require_role(request, organization, *role_keys):
    if not user_has_role(request.user, organization, *role_keys):
        return json_error("Permission denied.", status=403, code="permission_denied")
    return None


class OrganizationListCreateView(View):
    def get(self, request):
        if error := require_authenticated(request):
            return error
        organizations = [serialize_organization(org) for org in organization_queryset_for_user(request.user)]
        return json_ok({"results": organizations})

    @transaction.atomic
    def post(self, request):
        if error := require_authenticated(request):
            return error
        data = parse_json_body(request)
        if data is None:
            return json_error("Invalid JSON.")
        name = (data.get("name") or "").strip()
        slug = (data.get("slug") or "").strip().lower()
        billing_email = (data.get("billing_email") or "").strip()
        if not name or not slug:
            return json_error("Name and slug are required.")

        owner_role = role_for_key(ROLE_OWNER)
        organization = Organization.objects.create(
            name=name,
            slug=slug,
            billing_email=billing_email,
            owner_user=request.user,
        )
        OrganizationMember.objects.create(
            organization=organization,
            user=request.user,
            role=owner_role,
            status=OrganizationMemberStatus.ACTIVE,
            joined_at=timezone.now(),
        )
        audit_log.record(
            action=audit_log.AuditAction.ORGANIZATION_CREATED,
            request=request,
            actor=request.user,
            organization=organization,
            target_type="organization",
            target_id=organization.public_id,
        )
        return json_ok(serialize_organization(organization), status=201)


class OrganizationDetailView(View):
    def get(self, request, organization_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        return json_ok(serialize_organization(organization))

    @transaction.atomic
    def patch(self, request, organization_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        if error := require_permission(request, organization, PermissionKey.ORGANIZATION_MANAGE):
            return error
        data = parse_json_body(request)
        if data is None:
            return json_error("Invalid JSON.")
        for field in ["name", "billing_email"]:
            if field in data:
                setattr(organization, field, (data.get(field) or "").strip())
        organization.save(update_fields=["name", "billing_email", "updated_at"])
        audit_log.record(
            action=audit_log.AuditAction.ORGANIZATION_UPDATED,
            request=request,
            actor=request.user,
            organization=organization,
            target_type="organization",
            target_id=organization.public_id,
            metadata={"fields": [field for field in ["name", "billing_email"] if field in data]},
        )
        return json_ok(serialize_organization(organization))

    @transaction.atomic
    def delete(self, request, organization_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        if error := require_role(request, organization, ROLE_OWNER):
            return error
        organization.status = OrganizationStatus.DELETED
        organization.deleted_at = timezone.now()
        organization.save(update_fields=["status", "deleted_at", "updated_at"])
        audit_log.record(
            action=audit_log.AuditAction.ORGANIZATION_DELETED,
            request=request,
            actor=request.user,
            organization=organization,
            target_type="organization",
            target_id=organization.public_id,
        )
        return json_ok(status=204)


class OrganizationMemberListCreateView(View):
    def get(self, request, organization_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        members = (
            OrganizationMember.objects.filter(organization=organization)
            .exclude(status=OrganizationMemberStatus.REMOVED)
            .select_related("user", "role")
        )
        return json_ok({"results": [serialize_member(member) for member in members]})

    @transaction.atomic
    def post(self, request, organization_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        if error := require_permission(request, organization, PermissionKey.MEMBER_MANAGE):
            return error
        data = parse_json_body(request)
        if data is None:
            return json_error("Invalid JSON.")
        email = (data.get("email") or "").strip().lower()
        role_key = (data.get("role") or "").strip()
        role = role_for_key(role_key)
        if not email or role is None:
            return json_error("Valid email and role are required.")
        user, _ = User.objects.get_or_create(email=email, defaults={"is_active": True})
        member, created = OrganizationMember.objects.get_or_create(
            organization=organization,
            user=user,
            defaults={
                "role": role,
                "status": OrganizationMemberStatus.ACTIVE,
                "invited_by_user": request.user,
                "joined_at": timezone.now(),
            },
        )
        if not created:
            if member.status != OrganizationMemberStatus.REMOVED:
                return json_error("User is already a member.", status=400, code="member_exists")
            member.role = role
            member.status = OrganizationMemberStatus.ACTIVE
            member.invited_by_user = request.user
            member.joined_at = timezone.now()
            member.save(update_fields=["role", "status", "invited_by_user", "joined_at", "updated_at"])
        audit_log.record(
            action=audit_log.AuditAction.ORGANIZATION_MEMBER_ADDED,
            request=request,
            actor=request.user,
            organization=organization,
            target_type="organization_member",
            target_id=member.public_id,
            metadata={"role": role.key},
        )
        return json_ok(serialize_member(member), status=201)


class OrganizationMemberDetailView(View):
    @transaction.atomic
    def patch(self, request, organization_public_id, member_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        if error := require_permission(request, organization, PermissionKey.MEMBER_MANAGE):
            return error
        data = parse_json_body(request)
        if data is None:
            return json_error("Invalid JSON.")
        member = get_object_or_404(
            OrganizationMember.objects.select_related("role", "user"),
            organization=organization,
            public_id=member_public_id,
        )
        role_key = (data.get("role") or "").strip()
        role = role_for_key(role_key)
        if role is None:
            return json_error("Valid role is required.")
        if member.role.key == ROLE_OWNER and role.key != ROLE_OWNER and active_owner_count(organization) <= 1:
            return json_error("Cannot downgrade the last owner.", status=400, code="last_owner")
        previous_role = member.role.key
        member.role = role
        member.save(update_fields=["role", "updated_at"])
        audit_log.record(
            action=audit_log.AuditAction.ORGANIZATION_MEMBER_ROLE_CHANGED,
            request=request,
            actor=request.user,
            organization=organization,
            target_type="organization_member",
            target_id=member.public_id,
            metadata={"previous_role": previous_role, "role": role.key},
        )
        return json_ok(serialize_member(member))

    @transaction.atomic
    def delete(self, request, organization_public_id, member_public_id):
        if error := require_authenticated(request):
            return error
        organization = get_user_organization_or_404(request.user, organization_public_id)
        if error := require_permission(request, organization, PermissionKey.MEMBER_MANAGE):
            return error
        member = get_object_or_404(
            OrganizationMember.objects.select_related("role", "user"),
            organization=organization,
            public_id=member_public_id,
        )
        if member.role.key == ROLE_OWNER and active_owner_count(organization) <= 1:
            return json_error("Cannot remove the last owner.", status=400, code="last_owner")
        member.status = OrganizationMemberStatus.REMOVED
        member.save(update_fields=["status", "updated_at"])
        audit_log.record(
            action=audit_log.AuditAction.ORGANIZATION_MEMBER_REMOVED,
            request=request,
            actor=request.user,
            organization=organization,
            target_type="organization_member",
            target_id=member.public_id,
        )
        return json_ok(status=204)
