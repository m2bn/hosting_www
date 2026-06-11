from django.conf import settings
from django.contrib.auth import logout
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import ensure_csrf_cookie

from apps.api.audit_log import AuditAction
from apps.api.auth_utils import (
    audit_event,
    authenticate_and_login,
    base32_secret,
    consume_auth_token,
    create_email_verification_token,
    create_password_reset_token,
    generate_recovery_codes,
    encrypt_secret,
    decrypt_secret,
    json_error,
    json_ok,
    parse_json_body,
    verify_totp,
)
from apps.api.models import AuditResult, AuthTokenPurpose, TwoFactorDevice, User


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfTokenView(View):
    def get(self, request):
        return json_ok({"csrf": "ok"})


class RegisterView(View):
    def post(self, request):
        data = parse_json_body(request)
        if data is None:
            return json_error("Invalid JSON.")
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        full_name = data.get("full_name") or ""
        if not email or not password:
            return json_error("Email and password are required.")
        if User.objects.filter(email=email).exists():
            return json_error("Registration could not be completed.", status=400, code="registration_failed")

        user = User.objects.create_user(email=email, password=password, full_name=full_name)
        raw_token, _ = create_email_verification_token(user)
        audit_event(request, AuditAction.AUTH_REGISTERED, AuditResult.SUCCESS, user=user)
        response = {"public_id": str(user.public_id), "email": user.email}
        if settings.AUTH_RETURN_DEBUG_TOKENS:
            response["email_verification_token"] = raw_token
        return json_ok(response, status=201)


class LoginView(View):
    def post(self, request):
        data = parse_json_body(request)
        if data is None:
            return json_error("Invalid JSON.")
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        user, error = authenticate_and_login(
            request,
            email=email,
            password=password,
            totp=data.get("totp"),
            recovery_code=data.get("recovery_code"),
        )
        if error:
            return error
        return json_ok({"public_id": str(user.public_id), "email": user.email})


class LogoutView(View):
    def post(self, request):
        user = request.user if request.user.is_authenticated else None
        if user:
            audit_event(request, AuditAction.AUTH_LOGOUT, AuditResult.SUCCESS, user=user)
        logout(request)
        return json_ok()


class CurrentUserView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return json_error("Authentication is required.", status=401, code="not_authenticated")
        return json_ok(
            {
                "public_id": str(request.user.public_id),
                "email": request.user.email,
                "full_name": request.user.full_name,
                "mfa_enabled": request.user.mfa_enabled,
                "is_email_verified": request.user.is_email_verified,
            }
        )


class PasswordResetRequestView(View):
    def post(self, request):
        data = parse_json_body(request)
        if data is None:
            return json_error("Invalid JSON.")
        email = (data.get("email") or "").strip().lower()
        user = User.objects.filter(email=email, is_active=True).first()
        if user:
            create_password_reset_token(user)
            audit_event(request, AuditAction.AUTH_PASSWORD_RESET_REQUESTED, AuditResult.SUCCESS, user=user)
        else:
            audit_event(request, AuditAction.AUTH_PASSWORD_RESET_REQUESTED, AuditResult.SUCCESS)
        return json_ok({"detail": "If the account exists, password reset instructions have been sent."})


class PasswordResetConfirmView(View):
    def post(self, request):
        data = parse_json_body(request)
        if data is None:
            return json_error("Invalid JSON.")
        user = consume_auth_token(data.get("token") or "", AuthTokenPurpose.PASSWORD_RESET)
        if user is None:
            return json_error("Invalid or expired token.", status=400, code="invalid_token")
        password = data.get("password") or ""
        if not password:
            return json_error("Password is required.")
        user.set_password(password)
        user.save(update_fields=["password", "updated_at"])
        audit_event(request, AuditAction.AUTH_PASSWORD_RESET_COMPLETED, AuditResult.SUCCESS, user=user)
        return json_ok()


class PasswordChangeView(View):
    def post(self, request):
        if not request.user.is_authenticated:
            return json_error("Authentication is required.", status=401, code="not_authenticated")
        data = parse_json_body(request)
        if data is None:
            return json_error("Invalid JSON.")
        if not request.user.check_password(data.get("current_password") or ""):
            return json_error("Invalid current password.", status=400, code="invalid_password")
        new_password = data.get("new_password") or ""
        if not new_password:
            return json_error("New password is required.")
        user = request.user
        user.set_password(new_password)
        user.save(update_fields=["password", "updated_at"])
        audit_event(request, AuditAction.AUTH_PASSWORD_CHANGED, AuditResult.SUCCESS, user=user)
        logout(request)
        return json_ok()


class EmailVerificationView(View):
    def post(self, request):
        data = parse_json_body(request)
        if data is None:
            return json_error("Invalid JSON.")
        user = consume_auth_token(data.get("token") or "", AuthTokenPurpose.EMAIL_VERIFICATION)
        if user is None:
            return json_error("Invalid or expired token.", status=400, code="invalid_token")
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified", "updated_at"])
        audit_event(request, AuditAction.AUTH_EMAIL_VERIFIED, AuditResult.SUCCESS, user=user)
        return json_ok()


class TwoFactorSetupView(View):
    def post(self, request):
        if not request.user.is_authenticated:
            return json_error("Authentication is required.", status=401, code="not_authenticated")
        raw_secret = base32_secret()
        device, created = TwoFactorDevice.objects.get_or_create(
            user=request.user,
            defaults={"secret": encrypt_secret(raw_secret)},
        )
        if device.is_enabled:
            return json_error("Two-factor authentication is already enabled.", status=400, code="2fa_already_enabled")
        if not created:
            raw_secret = decrypt_secret(device.secret)
        return json_ok({"secret": raw_secret})


class TwoFactorEnableView(View):
    def post(self, request):
        if not request.user.is_authenticated:
            return json_error("Authentication is required.", status=401, code="not_authenticated")
        data = parse_json_body(request)
        if data is None:
            return json_error("Invalid JSON.")
        try:
            device = request.user.two_factor_device
        except TwoFactorDevice.DoesNotExist:
            return json_error("Two-factor setup is required.", status=400, code="2fa_setup_required")
        if not verify_totp(decrypt_secret(device.secret), data.get("totp")):
            return json_error("Invalid two-factor code.", status=400, code="invalid_2fa")
        device.enabled_at = timezone.now()
        device.save(update_fields=["enabled_at", "updated_at"])
        request.user.mfa_enabled = True
        request.user.save(update_fields=["mfa_enabled", "updated_at"])
        recovery_codes = generate_recovery_codes(device)
        audit_event(request, AuditAction.AUTH_2FA_ENABLED, AuditResult.SUCCESS, user=request.user)
        return json_ok({"recovery_codes": recovery_codes})


class TwoFactorDisableView(View):
    def post(self, request):
        if not request.user.is_authenticated:
            return json_error("Authentication is required.", status=401, code="not_authenticated")
        data = parse_json_body(request)
        if data is None:
            return json_error("Invalid JSON.")
        try:
            device = request.user.two_factor_device
        except TwoFactorDevice.DoesNotExist:
            return json_ok()
        if not request.user.check_password(data.get("password") or ""):
            return json_error("Invalid password.", status=400, code="invalid_password")
        device.delete()
        request.user.mfa_enabled = False
        request.user.save(update_fields=["mfa_enabled", "updated_at"])
        audit_event(request, AuditAction.AUTH_2FA_DISABLED, AuditResult.SUCCESS, user=request.user)
        return json_ok()
