from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotAuthenticated, PermissionDenied

from apps.api.models import Organization, OrganizationStatus
from apps.api.rbac import get_membership_context


ORGANIZATION_CONTEXT_KWARGS = (
    "organization_public_id",
    "organization_id",
    "org_public_id",
    "org_id",
)


def get_organization_from_request(request, view=None):
    kwargs = getattr(view, "kwargs", {}) if view is not None else {}
    for key in ORGANIZATION_CONTEXT_KWARGS:
        value = kwargs.get(key)
        if value:
            return get_object_or_404(
                Organization,
                public_id=value,
                deleted_at__isnull=True,
                status__in=[OrganizationStatus.ACTIVE, OrganizationStatus.SUSPENDED],
            )

    organization = getattr(request, "organization", None)
    if organization is not None:
        return organization

    return None


def require_organization_membership(user, organization):
    if not user or not user.is_authenticated:
        raise NotAuthenticated("Authentication is required.")

    context = get_membership_context(user, organization)
    if context is None:
        raise PermissionDenied("Active organization membership is required.")
    return context.membership


def filter_queryset_for_organization(queryset, organization):
    return queryset.filter(organization=organization)


def get_object_for_organization_or_404(queryset_or_model, organization, **lookup):
    if organization is None:
        raise PermissionDenied("Organization context is required.")

    queryset = getattr(queryset_or_model, "_default_manager", queryset_or_model)
    queryset = filter_queryset_for_organization(queryset, organization)
    return get_object_or_404(queryset, **lookup)
