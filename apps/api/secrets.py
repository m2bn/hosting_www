import base64
import hashlib
import logging
import re

from cryptography.fernet import Fernet
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.api import audit_log
from apps.api.models import ProjectSecret, ProjectSecretStatus, ProjectSecretVersion


ENV_NAME_RE = re.compile(r"^[A-Z_][A-Z0-9_]{0,127}$")
SENSITIVE_METADATA_KEYS = {"value", "secret", "token", "password", "key"}
logger = logging.getLogger(__name__)


def validate_secret_name(name):
    normalized = (name or "").strip()
    if not ENV_NAME_RE.fullmatch(normalized):
        raise ValidationError("Secret name must be a valid environment variable name.")
    return normalized


def validate_metadata(metadata):
    if metadata is None:
        return {}
    if not isinstance(metadata, dict):
        raise ValidationError("Metadata must be an object.")
    sanitized = {}
    for key, value in metadata.items():
        if str(key).lower() in SENSITIVE_METADATA_KEYS:
            continue
        sanitized[key] = value
    return sanitized


def encrypt_value(raw_value):
    return _fernet().encrypt(str(raw_value).encode("utf-8")).decode("ascii")


def decrypt_value(encrypted_value):
    return _fernet().decrypt(encrypted_value.encode("ascii")).decode("utf-8")


@transaction.atomic
def create_secret(*, organization, project, environment, name, value, metadata=None, actor=None, request=None):
    secret_name = validate_secret_name(name)
    safe_metadata = validate_metadata(metadata)
    secret = ProjectSecret.objects.create(
        organization=organization,
        project=project,
        environment=environment,
        name=secret_name,
        metadata=safe_metadata,
        created_by_user=actor,
    )
    ProjectSecretVersion.objects.create(
        secret=secret,
        version=1,
        encrypted_value=encrypt_value(value),
        created_by_user=actor,
    )
    _record_secret_event(audit_log.AuditAction.SECRET_CREATED, secret, actor=actor, request=request)
    return secret


@transaction.atomic
def update_secret(*, secret, value=None, metadata=None, actor=None, request=None):
    update_fields = []
    if metadata is not None:
        secret.metadata = validate_metadata(metadata)
        update_fields.extend(["metadata", "updated_at"])
    if value is not None:
        _create_next_version(secret, value, actor)
        secret.refresh_from_db()
    if update_fields:
        secret.save(update_fields=update_fields)
    _record_secret_event(audit_log.AuditAction.SECRET_UPDATED, secret, actor=actor, request=request)
    return secret


@transaction.atomic
def rotate_secret(*, secret, value, actor=None, request=None):
    _create_next_version(secret, value, actor)
    secret.refresh_from_db()
    _record_secret_event(audit_log.AuditAction.SECRET_ROTATED, secret, actor=actor, request=request)
    return secret


def delete_secret(*, secret, actor=None, request=None):
    secret.status = ProjectSecretStatus.DELETED
    secret.deleted_at = timezone.now()
    secret.save(update_fields=["status", "deleted_at", "updated_at"])
    _record_secret_event(audit_log.AuditAction.SECRET_DELETED, secret, actor=actor, request=request)


def runtime_secret_values_for_project(project, environment):
    secrets = ProjectSecret.objects.filter(
        organization=project.organization,
        project=project,
        environment=environment,
        status=ProjectSecretStatus.ACTIVE,
        deleted_at__isnull=True,
    )
    values = {}
    for secret in secrets:
        version = secret.versions.order_by("-version").first()
        if version:
            values[secret.name] = decrypt_value(version.encrypted_value)
    return values


def _create_next_version(secret, raw_value, actor):
    next_version = secret.current_version + 1
    ProjectSecretVersion.objects.create(
        secret=secret,
        version=next_version,
        encrypted_value=encrypt_value(raw_value),
        created_by_user=actor,
    )
    secret.current_version = next_version
    secret.save(update_fields=["current_version", "updated_at"])


def _record_secret_event(action, secret, actor=None, request=None):
    audit_log.record(
        action=action,
        request=request,
        actor=actor,
        organization=secret.organization,
        project=secret.project,
        target_type="project_secret",
        target_id=secret.public_id,
        metadata={
            "name": secret.name,
            "environment_id": str(secret.environment.public_id),
            "version": secret.current_version,
        },
    )


def _fernet():
    configured_key = getattr(settings, "SECRETS_ENCRYPTION_KEY", "")
    if configured_key:
        return Fernet(configured_key.encode("ascii"))
    key_material = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key_material))
