from django.urls import path

from apps.api import api_key_views, auth_views, billing_views, certificate_views, container_deployment_views, domain_views, metering_views, organization_views, project_views, secret_views, static_deployment_views


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
    path("billing/stripe/webhook/", billing_views.StripeWebhookView.as_view(), name="stripe-webhook"),
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
        "organizations/<uuid:organization_public_id>/billing/checkout/",
        billing_views.SubscriptionCheckoutView.as_view(),
        name="billing-checkout",
    ),
    path(
        "organizations/<uuid:organization_public_id>/usage/",
        metering_views.UsageSummaryView.as_view(),
        name="usage-summary",
    ),
    path(
        "organizations/<uuid:organization_public_id>/usage/prometheus/",
        metering_views.UsagePrometheusView.as_view(),
        name="usage-prometheus",
    ),
    path(
        "organizations/<uuid:organization_public_id>/api-keys/",
        api_key_views.OrganizationApiKeyListCreateView.as_view(),
        name="organization-api-key-list",
    ),
    path(
        "organizations/<uuid:organization_public_id>/api-keys/<uuid:api_key_public_id>/rotate/",
        api_key_views.ApiKeyRotateView.as_view(),
        name="api-key-rotate",
    ),
    path(
        "organizations/<uuid:organization_public_id>/api-keys/<uuid:api_key_public_id>/revoke/",
        api_key_views.ApiKeyRevokeView.as_view(),
        name="api-key-revoke",
    ),
    path(
        "organizations/<uuid:organization_public_id>/projects/<uuid:project_public_id>/",
        project_views.ProjectDetailView.as_view(),
        name="project-detail",
    ),
    path(
        "organizations/<uuid:organization_public_id>/projects/<uuid:project_public_id>/api-keys/",
        api_key_views.ProjectApiKeyListCreateView.as_view(),
        name="project-api-key-list",
    ),
    path(
        "organizations/<uuid:organization_public_id>/projects/<uuid:project_public_id>/environments/<uuid:environment_public_id>/secrets/",
        secret_views.ProjectSecretListCreateView.as_view(),
        name="project-secret-list",
    ),
    path(
        "organizations/<uuid:organization_public_id>/projects/<uuid:project_public_id>/environments/<uuid:environment_public_id>/deployments/static/",
        static_deployment_views.StaticDeploymentCreateView.as_view(),
        name="static-deployment-create",
    ),
    path(
        "organizations/<uuid:organization_public_id>/projects/<uuid:project_public_id>/environments/<uuid:environment_public_id>/domains/",
        domain_views.DomainListCreateView.as_view(),
        name="domain-list",
    ),
    path(
        "organizations/<uuid:organization_public_id>/projects/<uuid:project_public_id>/environments/<uuid:environment_public_id>/domains/<uuid:domain_public_id>/",
        domain_views.DomainDetailView.as_view(),
        name="domain-detail",
    ),
    path(
        "organizations/<uuid:organization_public_id>/projects/<uuid:project_public_id>/environments/<uuid:environment_public_id>/domains/<uuid:domain_public_id>/verify/",
        domain_views.DomainVerifyView.as_view(),
        name="domain-verify",
    ),
    path(
        "organizations/<uuid:organization_public_id>/projects/<uuid:project_public_id>/environments/<uuid:environment_public_id>/domains/<uuid:domain_public_id>/certificates/",
        certificate_views.CertificateListView.as_view(),
        name="certificate-list",
    ),
    path(
        "organizations/<uuid:organization_public_id>/projects/<uuid:project_public_id>/environments/<uuid:environment_public_id>/deployments/container/",
        container_deployment_views.ContainerDeploymentCreateView.as_view(),
        name="container-deployment-create",
    ),
    path(
        "organizations/<uuid:organization_public_id>/projects/<uuid:project_public_id>/environments/<uuid:environment_public_id>/deployments/container/<uuid:deployment_public_id>/logs/",
        container_deployment_views.ContainerDeploymentLogsView.as_view(),
        name="container-deployment-logs",
    ),
    path(
        "organizations/<uuid:organization_public_id>/projects/<uuid:project_public_id>/environments/<uuid:environment_public_id>/deployments/container/<uuid:deployment_public_id>/rollback/",
        container_deployment_views.ContainerDeploymentRollbackView.as_view(),
        name="container-deployment-rollback",
    ),
    path(
        "organizations/<uuid:organization_public_id>/projects/<uuid:project_public_id>/environments/<uuid:environment_public_id>/deployments/<uuid:deployment_public_id>/rollback/",
        static_deployment_views.StaticDeploymentRollbackView.as_view(),
        name="static-deployment-rollback",
    ),
    path(
        "organizations/<uuid:organization_public_id>/projects/<uuid:project_public_id>/environments/<uuid:environment_public_id>/secrets/<uuid:secret_public_id>/",
        secret_views.ProjectSecretDetailView.as_view(),
        name="project-secret-detail",
    ),
    path(
        "organizations/<uuid:organization_public_id>/projects/<uuid:project_public_id>/environments/<uuid:environment_public_id>/secrets/<uuid:secret_public_id>/rotate/",
        secret_views.ProjectSecretRotateView.as_view(),
        name="project-secret-rotate",
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
