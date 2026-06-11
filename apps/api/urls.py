from django.urls import path

from apps.api import auth_views


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
]
