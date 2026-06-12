import base64
import hashlib
import hmac
import json
import secrets
import struct
import time

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone
from cryptography.fernet import Fernet

from apps.api import audit_log
from apps.api.models import (
    AuditActorType,
    AuditResult,
    AuthToken,
    AuthTokenPurpose,
    OrganizationMember,
    OrganizationMemberStatus,
    RoleScope,
    TwoFactorDevice,
    TwoFactorRecoveryCode,
)
from apps.api.rbac import ROLE_ADMIN, ROLE_OWNER


TOKEN_TTL_SECONDS = 60 * 60
PASSWORD_RESET_TTL_SECONDS = 60 * 30
TOTP_STEP_SECONDS = 30
TOTP_DIGITS = 6


def fernet():
    key_material = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(key_material)
    return Fernet(key)


def encrypt_secret(raw_secret):
    return fernet().encrypt(raw_secret.encode("utf-8")).decode("ascii")


def decrypt_secret(ciphertext):
    return fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")


def parse_json_body(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return None


def json_error(message, status=400, code="invalid_request"):
    return JsonResponse({"detail": message, "code": code}, status=status)


def json_ok(data=None, status=200):
    return JsonResponse(data or {"ok": True}, status=status)


def client_ip(request):
    return request.META.get("REMOTE_ADDR", "")


def hash_for_audit(value):
    if not value:
        return ""
    salted = f"{settings.SECRET_KEY}:{value}".encode("utf-8")
    return hashlib.sha256(salted).hexdigest()


def audit_event(request, action, result, user=None, actor_type=AuditActorType.USER, metadata=None):
    actor = user if user and getattr(user, "is_authenticated", False) else None
    return audit_log.record(
        action=action,
        request=request,
        actor=actor,
        actor_type=actor_type if actor else AuditActorType.SYSTEM,
        target_type="auth",
        target_id=str(actor.public_id) if actor else "",
        result=result,
        metadata=metadata or {},
    )


def login_rate_limit_key(request, email):
    return f"auth-login:{hash_for_audit(client_ip(request))}:{hash_for_audit((email or '').lower())}"


def is_login_rate_limited(request, email):
    key = login_rate_limit_key(request, email)
    attempts = cache.get(key, 0)
    return attempts >= settings.AUTH_LOGIN_RATE_LIMIT_ATTEMPTS


def record_failed_login(request, email):
    key = login_rate_limit_key(request, email)
    attempts = cache.get(key, 0) + 1
    cache.set(key, attempts, settings.AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS)
    return attempts


def clear_failed_logins(request, email):
    cache.delete(login_rate_limit_key(request, email))


def user_requires_2fa(user):
    if user.is_platform_staff:
        return True
    return OrganizationMember.objects.filter(
        user=user,
        status=OrganizationMemberStatus.ACTIVE,
        role__scope=RoleScope.ORGANIZATION,
        role__key__in=[ROLE_OWNER, ROLE_ADMIN],
    ).exists()


def enabled_2fa_device(user):
    try:
        device = user.two_factor_device
    except TwoFactorDevice.DoesNotExist:
        return None
    return device if device.is_enabled else None


def base32_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def normalize_base32_secret(secret):
    padding = "=" * ((8 - len(secret) % 8) % 8)
    return secret.upper() + padding


def totp_code(secret, for_time=None):
    for_time = int(for_time or time.time())
    counter = int(for_time // TOTP_STEP_SECONDS)
    key = base64.b32decode(normalize_base32_secret(secret))
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10**TOTP_DIGITS)).zfill(TOTP_DIGITS)


def verify_totp(secret, code):
    code = str(code or "").strip()
    if not code.isdigit() or len(code) != TOTP_DIGITS:
        return False
    now = int(time.time())
    for drift in (-1, 0, 1):
        expected = totp_code(secret, now + drift * TOTP_STEP_SECONDS)
        if hmac.compare_digest(expected, code):
            return True
    return False


def generate_recovery_codes(device, count=8):
    raw_codes = []
    TwoFactorRecoveryCode.objects.filter(device=device, used_at__isnull=True).delete()
    for _ in range(count):
        raw_code = secrets.token_urlsafe(12)
        recovery_code = TwoFactorRecoveryCode(device=device)
        recovery_code.set_code(raw_code)
        recovery_code.save()
        raw_codes.append(raw_code)
    return raw_codes


def verify_recovery_code(device, raw_code):
    for recovery_code in device.recovery_codes.filter(used_at__isnull=True):
        if recovery_code.check_code(raw_code):
            recovery_code.mark_used()
            return True
    return False


def create_auth_token(user, purpose, ttl_seconds):
    raw_token = secrets.token_urlsafe(32)
    token = AuthToken(
        user=user,
        purpose=purpose,
        expires_at=timezone.now() + timezone.timedelta(seconds=ttl_seconds),
    )
    token.set_token(raw_token)
    token.save()
    return raw_token, token


def consume_auth_token(raw_token, purpose):
    for token in AuthToken.objects.select_related("user").filter(
        purpose=purpose,
        used_at__isnull=True,
        expires_at__gt=timezone.now(),
    ):
        if token.check_token(raw_token):
            token.mark_used()
            return token.user
    return None


def invalidate_user_sessions(user):
    session_auth_hash = user.get_session_auth_hash()
    for session in Session.objects.filter(expire_date__gte=timezone.now()):
        data = session.get_decoded()
        if str(data.get("_auth_user_id")) == str(user.pk) and data.get("_auth_user_hash") != session_auth_hash:
            session.delete()


def authenticate_and_login(request, email, password, totp=None, recovery_code=None):
    if is_login_rate_limited(request, email):
        audit_event(request, audit_log.AuditAction.AUTH_LOGIN_RATE_LIMITED, AuditResult.DENIED)
        return None, json_error("Too many login attempts.", status=429, code="rate_limited")

    user = authenticate(request, username=email, password=password)
    if user is None:
        record_failed_login(request, email)
        audit_event(request, audit_log.AuditAction.AUTH_LOGIN_FAILED, AuditResult.FAILED)
        return None, json_error("Invalid credentials.", status=400, code="invalid_credentials")

    if user_requires_2fa(user):
        device = enabled_2fa_device(user)
        if device is None:
            audit_event(request, audit_log.AuditAction.AUTH_2FA_REQUIRED, AuditResult.DENIED, user=user)
            return None, json_error("Two-factor authentication setup is required.", status=403, code="2fa_setup_required")
        if recovery_code:
            if not verify_recovery_code(device, recovery_code):
                record_failed_login(request, email)
                audit_event(request, audit_log.AuditAction.AUTH_2FA_RECOVERY_CODE_FAILED, AuditResult.FAILED, user=user)
                return None, json_error("Invalid two-factor code.", status=400, code="invalid_2fa")
            audit_event(request, audit_log.AuditAction.AUTH_2FA_RECOVERY_CODE_USED, AuditResult.SUCCESS, user=user)
        elif not verify_totp(decrypt_secret(device.secret), totp):
            record_failed_login(request, email)
            audit_event(request, audit_log.AuditAction.AUTH_2FA_FAILED, AuditResult.FAILED, user=user)
            return None, json_error("Invalid two-factor code.", status=400, code="invalid_2fa")
        device.last_used_at = timezone.now()
        device.save(update_fields=["last_used_at", "updated_at"])

    clear_failed_logins(request, email)
    login(request, user)
    user.last_login_at = timezone.now()
    user.save(update_fields=["last_login_at", "updated_at"])
    audit_event(request, audit_log.AuditAction.AUTH_LOGIN_SUCCEEDED, AuditResult.SUCCESS, user=user)
    return user, None


def create_email_verification_token(user):
    return create_auth_token(user, AuthTokenPurpose.EMAIL_VERIFICATION, TOKEN_TTL_SECONDS)


def create_password_reset_token(user):
    return create_auth_token(user, AuthTokenPurpose.PASSWORD_RESET, PASSWORD_RESET_TTL_SECONDS)
