import secrets

from django.core.cache import cache
from django.utils import timezone

from apps.api import audit_log
from apps.api.models import ApiKey, ApiKeyStatus, AuditActorType


API_KEY_PREFIX_BYTES = 9
API_KEY_SECRET_BYTES = 32
HIGH_RISK_SCOPES = {
    "deployment.write",
    "project.manage",
    "billing.manage",
    "api_key.manage",
}


def generate_api_key_value():
    prefix = f"ak_{secrets.token_urlsafe(API_KEY_PREFIX_BYTES)}"[:32]
    secret = secrets.token_urlsafe(API_KEY_SECRET_BYTES)
    return prefix, f"{prefix}.{secret}"


def create_api_key(*, organization, project=None, created_by_user, name, scopes, expires_at=None, request=None):
    prefix, raw_key = generate_api_key_value()
    api_key = ApiKey(
        organization=organization,
        project=project,
        created_by_user=created_by_user,
        name=name,
        prefix=prefix,
        scopes=list(scopes or []),
        expires_at=expires_at,
    )
    api_key.set_key(raw_key)
    api_key.full_clean()
    api_key.save()
    audit_log.record(
        action=audit_log.AuditAction.API_KEY_CREATED,
        request=request,
        actor=created_by_user,
        organization=organization,
        project=project,
        target_type="api_key",
        target_id=api_key.public_id,
        metadata={"prefix": api_key.prefix, "scopes": api_key.scopes, "project_id": str(project.public_id) if project else ""},
    )
    return api_key, raw_key


def rotate_api_key(api_key, *, actor=None, request=None):
    prefix, raw_key = generate_api_key_value()
    api_key.prefix = prefix
    api_key.set_key(raw_key)
    api_key.last_used_at = None
    api_key.revoked_at = None
    api_key.status = ApiKeyStatus.ACTIVE
    api_key.full_clean()
    api_key.save(update_fields=["prefix", "key_hash", "last_used_at", "revoked_at", "status", "updated_at"])
    audit_log.record(
        action=audit_log.AuditAction.API_KEY_ROTATED,
        request=request,
        actor=actor,
        organization=api_key.organization,
        project=api_key.project,
        target_type="api_key",
        target_id=api_key.public_id,
        metadata={"prefix": api_key.prefix},
    )
    return raw_key


def revoke_api_key(api_key, *, actor=None, request=None):
    api_key.status = ApiKeyStatus.REVOKED
    api_key.revoked_at = timezone.now()
    api_key.save(update_fields=["status", "revoked_at", "updated_at"])
    audit_log.record(
        action=audit_log.AuditAction.API_KEY_DELETED,
        request=request,
        actor=actor,
        organization=api_key.organization,
        project=api_key.project,
        target_type="api_key",
        target_id=api_key.public_id,
        metadata={"prefix": api_key.prefix},
    )


def mark_api_key_used(api_key, *, request=None, scope=None):
    api_key.last_used_at = timezone.now()
    api_key.save(update_fields=["last_used_at", "updated_at"])
    if scope in HIGH_RISK_SCOPES:
        audit_log.record(
            action=audit_log.AuditAction.API_KEY_USED_HIGH_RISK,
            request=request,
            actor=api_key,
            actor_type=AuditActorType.API_KEY,
            organization=api_key.organization,
            project=api_key.project,
            target_type="api_key",
            target_id=api_key.public_id,
            metadata={"prefix": api_key.prefix, "scope": scope},
        )


def is_api_key_expired(api_key):
    return bool(api_key.expires_at and api_key.expires_at <= timezone.now())


def parse_api_key(raw_key):
    if not raw_key or "." not in raw_key:
        return "", ""
    prefix, _ = raw_key.split(".", 1)
    return prefix, raw_key


def rate_limit_key(prefix):
    return f"api-key-rate-limit:{prefix}"


def increment_rate_limit(prefix, attempts, window_seconds):
    key = rate_limit_key(prefix)
    current = cache.get(key, 0) + 1
    cache.set(key, current, window_seconds)
    return current > attempts


def clear_rate_limit(prefix):
    cache.delete(rate_limit_key(prefix))
