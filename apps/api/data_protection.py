import hashlib
import json
import secrets
import shutil
import zipfile
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import logout
from django.contrib.sessions.models import Session
from django.db import transaction
from django.utils import timezone

from apps.api import audit_log
from apps.api.models import (
    ApiKey,
    AuditLog,
    BuildJob,
    Certificate,
    DataDeletionRequest,
    DataDeletionScope,
    DataDeletionStatus,
    DataExportRequest,
    DataExportScope,
    DataExportStatus,
    Deployment,
    Domain,
    DomainStatus,
    Environment,
    EnvironmentStatus,
    Invoice,
    OrganizationMember,
    OrganizationMemberStatus,
    OrganizationStatus,
    Project,
    ProjectSecret,
    ProjectStatus,
    Subscription,
    UsageRecord,
)


def request_user_export(*, user, request=None):
    export = DataExportRequest.objects.create(requested_by_user=user, scope=DataExportScope.USER)
    audit_log.record(
        action=audit_log.AuditAction.DATA_EXPORT_REQUESTED,
        request=request,
        actor=user,
        target_type="data_export",
        target_id=export.public_id,
        metadata={"scope": DataExportScope.USER},
    )
    return generate_export(export)


def request_organization_export(*, organization, user, request=None):
    export = DataExportRequest.objects.create(
        requested_by_user=user,
        organization=organization,
        scope=DataExportScope.ORGANIZATION,
    )
    audit_log.record(
        action=audit_log.AuditAction.DATA_EXPORT_REQUESTED,
        request=request,
        actor=user,
        organization=organization,
        target_type="data_export",
        target_id=export.public_id,
        metadata={"scope": DataExportScope.ORGANIZATION},
    )
    return generate_export(export)


def generate_export(export):
    export.status = DataExportStatus.PROCESSING
    export.save(update_fields=["status", "updated_at"])
    try:
        payload = _user_export_payload(export.requested_by_user) if export.scope == DataExportScope.USER else _organization_export_payload(export.organization)
        path = _write_export_zip(export, payload)
        raw_token = secrets.token_urlsafe(32)
        export.set_download_token(raw_token)
        export.file_path = str(path)
        export.file_sha256 = _sha256_file(path)
        export.status = DataExportStatus.COMPLETED
        export.completed_at = timezone.now()
        export.download_expires_at = timezone.now() + timedelta(seconds=settings.DATA_EXPORT_URL_TTL_SECONDS)
        export.save(update_fields=["download_token_hash", "file_path", "file_sha256", "status", "completed_at", "download_expires_at", "updated_at"])
        audit_log.record(
            action=audit_log.AuditAction.DATA_EXPORT_COMPLETED,
            actor=export.requested_by_user,
            organization=export.organization,
            target_type="data_export",
            target_id=export.public_id,
            metadata={"scope": export.scope, "sha256": export.file_sha256},
        )
        export.raw_download_token = raw_token
        return export
    except Exception as exc:
        export.status = DataExportStatus.FAILED
        export.failed_reason = exc.__class__.__name__
        export.save(update_fields=["status", "failed_reason", "updated_at"])
        raise


def export_download_url(export, request=None):
    token = getattr(export, "raw_download_token", "")
    path = f"/api/data-exports/{export.public_id}/download/"
    if request:
        return request.build_absolute_uri(f"{path}?token={token}")
    return f"{path}?token={token}"


def verify_export_download(export, token):
    if export.status != DataExportStatus.COMPLETED or not export.file_path:
        return False
    if not export.download_expires_at or export.download_expires_at <= timezone.now():
        return False
    return export.check_download_token(token or "")


@transaction.atomic
def request_user_deletion(*, user, request=None):
    retention_until = timezone.now() + timedelta(days=settings.DATA_DELETION_RETENTION_DAYS)
    deletion = DataDeletionRequest.objects.create(
        requested_by_user=user,
        target_user=user,
        scope=DataDeletionScope.USER,
        status=DataDeletionStatus.SOFT_DELETED,
        retention_until=retention_until,
    )
    user.is_active = False
    user.deleted_at = timezone.now()
    user.save(update_fields=["is_active", "deleted_at", "updated_at"])
    Session.objects.filter(session_data__contains=str(user.pk)).delete()
    audit_log.record(
        action=audit_log.AuditAction.DATA_DELETION_REQUESTED,
        request=request,
        actor=user,
        target_type="user",
        target_id=user.public_id,
        metadata={"scope": DataDeletionScope.USER, "retention_until": retention_until.isoformat()},
    )
    if request:
        logout(request)
    return deletion


@transaction.atomic
def request_organization_deletion(*, organization, user, request=None):
    retention_until = timezone.now() + timedelta(days=settings.DATA_DELETION_RETENTION_DAYS)
    deletion = DataDeletionRequest.objects.create(
        requested_by_user=user,
        organization=organization,
        scope=DataDeletionScope.ORGANIZATION,
        status=DataDeletionStatus.SOFT_DELETED,
        retention_until=retention_until,
    )
    organization.status = OrganizationStatus.PENDING_DELETION
    organization.deleted_at = timezone.now()
    organization.save(update_fields=["status", "deleted_at", "updated_at"])
    Project.objects.filter(organization=organization, deleted_at__isnull=True).update(status=ProjectStatus.PENDING_DELETION, deleted_at=timezone.now())
    Environment.objects.filter(organization=organization, deleted_at__isnull=True).update(status=EnvironmentStatus.DELETED, deleted_at=timezone.now())
    Domain.objects.filter(organization=organization, deleted_at__isnull=True).update(status=DomainStatus.DELETED, deleted_at=timezone.now())
    OrganizationMember.objects.filter(organization=organization).exclude(status=OrganizationMemberStatus.REMOVED).update(status=OrganizationMemberStatus.DISABLED)
    audit_log.record(
        action=audit_log.AuditAction.DATA_DELETION_REQUESTED,
        request=request,
        actor=user,
        organization=organization,
        target_type="organization",
        target_id=organization.public_id,
        metadata={"scope": DataDeletionScope.ORGANIZATION, "retention_until": retention_until.isoformat()},
    )
    return deletion


@transaction.atomic
def finalize_expired_deletions(now=None):
    now = now or timezone.now()
    finalized = []
    requests = DataDeletionRequest.objects.select_related("organization", "target_user").filter(
        status=DataDeletionStatus.SOFT_DELETED,
        retention_until__lte=now,
    )
    for deletion in requests:
        if deletion.scope == DataDeletionScope.ORGANIZATION and deletion.organization:
            _delete_deployment_files_for_organization(deletion.organization)
            org_public_id = str(deletion.organization.public_id)
            deletion.organization.delete()
            deletion.organization = None
            deletion.status = DataDeletionStatus.HARD_DELETED
            deletion.completed_at = now
            deletion.metadata = {"deleted_organization_public_id": org_public_id}
            deletion.save(update_fields=["organization", "status", "completed_at", "metadata", "updated_at"])
        elif deletion.scope == DataDeletionScope.USER and deletion.target_user:
            user = deletion.target_user
            user.email = f"deleted-{user.public_id}@deleted.local"
            user.full_name = ""
            user.set_unusable_password()
            user.anonymized_at = now
            user.save(update_fields=["email", "full_name", "password", "anonymized_at", "updated_at"])
            deletion.status = DataDeletionStatus.HARD_DELETED
            deletion.completed_at = now
            deletion.save(update_fields=["status", "completed_at", "updated_at"])
        audit_log.record(
            action=audit_log.AuditAction.DATA_DELETION_COMPLETED,
            actor_type="system",
            target_type="data_deletion",
            target_id=deletion.public_id,
            metadata={"scope": deletion.scope},
        )
        finalized.append(deletion)
    return finalized


def _user_export_payload(user):
    memberships = OrganizationMember.objects.filter(user=user).select_related("organization", "role")
    return {
        "manifest": {"scope": DataExportScope.USER, "generated_at": timezone.now().isoformat()},
        "user": _user_dict(user),
        "memberships": [
            {
                "organization_public_id": str(member.organization.public_id),
                "organization_name": member.organization.name,
                "role": member.role.key,
                "status": member.status,
            }
            for member in memberships
        ],
        "api_keys": [_api_key_dict(key) for key in ApiKey.objects.filter(created_by_user=user)],
        "audit_logs": [_audit_dict(entry) for entry in AuditLog._base_manager.filter(actor_user=user).order_by("-created_at")[:500]],
    }


def _organization_export_payload(organization):
    projects = Project.objects.filter(organization=organization)
    return {
        "manifest": {"scope": DataExportScope.ORGANIZATION, "generated_at": timezone.now().isoformat(), "organization_public_id": str(organization.public_id)},
        "organization": _organization_dict(organization),
        "members": [_member_dict(member) for member in OrganizationMember.objects.filter(organization=organization).select_related("user", "role")],
        "projects": [_project_dict(project) for project in projects],
        "environments": [_environment_dict(env) for env in Environment.objects.filter(organization=organization)],
        "domains": [_domain_dict(domain) for domain in Domain.objects.filter(organization=organization)],
        "certificates": [_certificate_dict(cert) for cert in Certificate.objects.filter(organization=organization)],
        "deployments": [_deployment_dict(deployment) for deployment in Deployment.objects.filter(organization=organization)],
        "build_jobs": [_build_job_dict(job) for job in BuildJob.objects.filter(organization=organization)],
        "usage": [_usage_dict(record) for record in UsageRecord.objects.filter(organization=organization)],
        "billing": {
            "subscriptions": [_subscription_dict(subscription) for subscription in Subscription.objects.filter(organization=organization)],
            "invoices": [_invoice_dict(invoice) for invoice in Invoice.objects.filter(organization=organization)],
        },
        "api_keys": [_api_key_dict(key) for key in ApiKey.objects.filter(organization=organization)],
        "secrets": [_secret_dict(secret) for secret in ProjectSecret.objects.filter(organization=organization)],
        "audit_logs": [_audit_dict(entry) for entry in AuditLog._base_manager.filter(organization=organization).order_by("-created_at")[:1000]],
    }


def _write_export_zip(export, payload):
    root = Path(settings.DATA_EXPORT_STORAGE_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{export.public_id}.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(payload["manifest"], indent=2, default=str))
        for key, value in payload.items():
            if key == "manifest":
                continue
            archive.writestr(f"{key}.json", json.dumps(value, indent=2, default=str))
    return path


def _delete_deployment_files_for_organization(organization):
    root = Path(settings.STATIC_DEPLOYMENT_LOCAL_ROOT)
    if not root.exists():
        return
    org_prefix = root / str(organization.public_id)
    if org_prefix.exists() and org_prefix.is_dir():
        shutil.rmtree(org_prefix)


def _user_dict(user):
    return {"public_id": str(user.public_id), "email": user.email, "full_name": user.full_name, "is_email_verified": user.is_email_verified, "created_at": user.created_at.isoformat()}


def _organization_dict(org):
    return {"public_id": str(org.public_id), "name": org.name, "slug": org.slug, "status": org.status, "billing_email": org.billing_email, "created_at": org.created_at.isoformat()}


def _member_dict(member):
    return {"public_id": str(member.public_id), "user_public_id": str(member.user.public_id), "email": member.user.email, "role": member.role.key, "status": member.status}


def _project_dict(project):
    return {"public_id": str(project.public_id), "name": project.name, "slug": project.slug, "status": project.status, "deleted_at": project.deleted_at.isoformat() if project.deleted_at else None}


def _environment_dict(env):
    return {"public_id": str(env.public_id), "project_public_id": str(env.project.public_id), "name": env.name, "slug": env.slug, "type": env.type, "status": env.status}


def _domain_dict(domain):
    return {"public_id": str(domain.public_id), "project_public_id": str(domain.project.public_id), "hostname": domain.hostname, "type": domain.type, "status": domain.status, "verified_at": domain.verified_at.isoformat() if domain.verified_at else None}


def _certificate_dict(cert):
    return {"public_id": str(cert.public_id), "domain_public_id": str(cert.domain.public_id), "provider": cert.provider, "status": cert.status, "not_after": cert.not_after.isoformat() if cert.not_after else None}


def _deployment_dict(deployment):
    return {"public_id": str(deployment.public_id), "project_public_id": str(deployment.project.public_id), "environment_public_id": str(deployment.environment.public_id), "version": deployment.version, "image_ref": deployment.image_ref, "status": deployment.status}


def _build_job_dict(job):
    return {"public_id": str(job.public_id), "project_public_id": str(job.project.public_id), "source_type": job.source_type, "source_ref": job.source_ref, "status": job.status, "image_ref": job.image_ref, "logs_ref": job.logs_ref}


def _usage_dict(record):
    return {"public_id": str(record.public_id), "project_public_id": str(record.project.public_id) if record.project else None, "metric": record.metric, "quantity": str(record.quantity), "unit": record.unit, "period_start": record.period_start.isoformat(), "period_end": record.period_end.isoformat()}


def _subscription_dict(subscription):
    return {"public_id": str(subscription.public_id), "plan": subscription.plan.key, "status": subscription.status, "current_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None}


def _invoice_dict(invoice):
    return {"public_id": str(invoice.public_id), "status": invoice.status, "amount_due": str(invoice.amount_due), "amount_paid": str(invoice.amount_paid), "currency": invoice.currency, "issued_at": invoice.issued_at.isoformat() if invoice.issued_at else None}


def _api_key_dict(api_key):
    return {"public_id": str(api_key.public_id), "organization_public_id": str(api_key.organization.public_id), "project_public_id": str(api_key.project.public_id) if api_key.project else None, "name": api_key.name, "prefix": api_key.prefix, "scopes": api_key.scopes, "status": api_key.status, "last_used_at": api_key.last_used_at.isoformat() if api_key.last_used_at else None, "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None}


def _secret_dict(secret):
    return {"public_id": str(secret.public_id), "project_public_id": str(secret.project.public_id), "environment_public_id": str(secret.environment.public_id), "name": secret.name, "status": secret.status, "metadata": audit_log.sanitize_metadata(secret.metadata), "current_version": secret.current_version, "created_at": secret.created_at.isoformat()}


def _audit_dict(entry):
    return {"public_id": str(entry.public_id), "action": entry.action, "target_type": entry.target_type, "target_id": entry.target_id, "result": entry.result, "created_at": entry.created_at.isoformat(), "metadata": audit_log.sanitize_metadata(entry.metadata)}


def _sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
