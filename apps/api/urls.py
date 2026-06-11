from django.urls import path

from apps.api import auth_views, organization_views, project_views


urlpatterns = [
    path("auth/csrf/", auth_views.CsrfTokenView.as_view(), name="auth-csrf"),
    path("auth/register/", auth_views.RegisterView.as_view(), name="auth-register"),
    path("auth/login/", auth_views.LoginView.as_view(), name="auth-login"),
    path("auth/logout/", auth_views.LogoutView.as_view(), name="auth-logout"),
    path("auth/me/", auth_views.CurrentUserView.as_view(), name="auth-me"),
    path("auth/password/reset/", auth_views.PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path("auth/password/reset/confirm/", auth_views.PasswordResetConfirmView.as_view(), name="auth-password-reset-confirm"),
    path("auth/password/change/", auth_views.PasswordChangeView.as_view(), name="auth-password-change"),
    path("auth/email/verify/", auth_views.EmailVerificationView.as_view(), name="auth-email-verify"),
    path("auth/2fa/setup/", auth_views.TwoFactorSetupView.as_view(), name="auth-2fa-setup"),
    path("auth/2fa/enable/", auth_views.TwoFactorEnableView.as_view(), name="auth-2fa-enable"),
    path("auth/2fa/disable/", auth_views.TwoFactorDisableView.as_view(), name="auth-2fa-disable"),
    path("organizations/", organization_views.OrganizationListCreateView.as_view(), name="organization-list"),
    path(
        "organizations/<uuid:organization_public_id>/",
        organization_views.OrganizationDetailView.as_view(),
        name="organization-detail",
    ),
    path(
        "organizations/<uuid:organization_public_id>/members/",
        organization_views.OrganizationMemberListCreateView.as_view(),
        name="organization-member-list",
    ),
    path(
        "organizations/<uuid:organization_public_id>/members/<uuid:member_public_id>/",
        organization_views.OrganizationMemberDetailView.as_view(),
        name="organization-member-detail",
    ),
    path(
        "organizations/<uuid:organization_public_id>/projects/",
        project_views.ProjectListCreateView.as_view(),
        name="project-list",
    ),
    path(
        "organizations/<uuid:organization_public_id>/projects/<uuid:project_public_id>/",
        project_views.ProjectDetailView.as_view(),
        name="project-detail",
    ),
    path(
        "organizations/<uuid:organization_public_id>/projects/<uuid:project_public_id>/archive/",
        project_views.ProjectArchiveView.as_view(),
        name="project-archive",
    ),
    path(
        "organizations/<uuid:organization_public_id>/projects/<uuid:project_public_id>/restore/",
        project_views.ProjectRestoreView.as_view(),
        name="project-restore",
    ),
]
