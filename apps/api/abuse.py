from django.utils import timezone

from apps.api import audit_log
from apps.api.models import (
    AbuseStatus,
    AuditResult,
    Organization,
    OrganizationStatus,
    Project,
    ProjectStatus,
    SecurityEvent,
    SecurityEventStatus,
    SecuritySeverity,
)


class AbuseError(Exception):
    def __init__(self, message, code="abuse_blocked"):
        super().__init__(message)
        self.code = code


class AbuseSignal:
    EXCESSIVE_TRANSFER = "excessive_transfer"
    TOO_MANY_DEPLOYMENTS = "too_many_deployments"
    SUSPICIOUS_DOMAIN = "suspicious_domain"
    MALWARE_SCAN_FAILED = "malware_scan_failed"
    HIGH_4XX_5XX_RATE = "high_4xx_5xx_rate"


ABUSE_ALERT_SEVERITY = {
    AbuseSignal.EXCESSIVE_TRANSFER: SecuritySeverity.HIGH,
    AbuseSignal.TOO_MANY_DEPLOYMENTS: SecuritySeverity.MEDIUM,
    AbuseSignal.SUSPICIOUS_DOMAIN: SecuritySeverity.HIGH,
    AbuseSignal.MALWARE_SCAN_FAILED: SecuritySeverity.CRITICAL,
    AbuseSignal.HIGH_4XX_5XX_RATE: SecuritySeverity.MEDIUM,
}


def require_reason(reason):
    normalized = (reason or "").strip()
    if not normalized:
        raise AbuseError("A reason is required for abuse actions.", code="reason_required")
    return normalized


def safe_blocked_message():
    return "This resource is temporarily unavailable. Contact support if you believe this is a mistake."


def mark_project_abusive(project, *, operator, reason, request=None):
    reason = require_reason(reason)
    project.abuse_status = AbuseStatus.FLAGGED
    project.abuse_reason = reason
    project.abuse_marked_at = timezone.now()
    project.save(update_fields=["abuse_status", "abuse_reason", "abuse_marked_at", "updated_at"])
    return audit_log.record(
        action=audit_log.AuditAction.ABUSE_PROJECT_FLAGGED,
        request=request,
        actor=operator,
        organization=project.organization,
        project=project,
        target_type="project",
        target_id=project.public_id,
        result=AuditResult.SUCCESS,
        metadata={"reason": reason},
    )


def block_project(project, *, operator, reason, request=None):
    reason = require_reason(reason)
    project.abuse_status = AbuseStatus.BLOCKED
    project.status = ProjectStatus.SUSPENDED
    project.abuse_reason = reason
    project.blocked_at = timezone.now()
    project.blocked_by_user = operator
    project.save(update_fields=["abuse_status", "status", "abuse_reason", "blocked_at", "blocked_by_user", "updated_at"])
    return audit_log.record(
        action=audit_log.AuditAction.ABUSE_PROJECT_BLOCKED,
        request=request,
        actor=operator,
        organization=project.organization,
        project=project,
        target_type="project",
        target_id=project.public_id,
        result=AuditResult.SUCCESS,
        metadata={"reason": reason},
    )


def unblock_project(project, *, operator, reason, request=None):
    reason = require_reason(reason)
    project.abuse_status = AbuseStatus.CLEAR
    project.status = ProjectStatus.ACTIVE
    project.abuse_reason = ""
    project.blocked_at = None
    project.blocked_by_user = None
    project.save(update_fields=["abuse_status", "status", "abuse_reason", "blocked_at", "blocked_by_user", "updated_at"])
    return audit_log.record(
        action=audit_log.AuditAction.ABUSE_PROJECT_UNBLOCKED,
        request=request,
        actor=operator,
        organization=project.organization,
        project=project,
        target_type="project",
        target_id=project.public_id,
        result=AuditResult.SUCCESS,
        metadata={"reason": reason},
    )


def block_organization(organization, *, operator, reason, request=None):
    reason = require_reason(reason)
    organization.abuse_status = AbuseStatus.BLOCKED
    organization.status = OrganizationStatus.SUSPENDED
    organization.abuse_reason = reason
    organization.blocked_at = timezone.now()
    organization.blocked_by_user = operator
    organization.save(update_fields=["abuse_status", "status", "abuse_reason", "blocked_at", "blocked_by_user", "updated_at"])
    return audit_log.record(
        action=audit_log.AuditAction.ABUSE_ORGANIZATION_BLOCKED,
        request=request,
        actor=operator,
        organization=organization,
        target_type="organization",
        target_id=organization.public_id,
        result=AuditResult.SUCCESS,
        metadata={"reason": reason},
    )


def unblock_organization(organization, *, operator, reason, request=None):
    reason = require_reason(reason)
    organization.abuse_status = AbuseStatus.CLEAR
    organization.status = OrganizationStatus.ACTIVE
    organization.abuse_reason = ""
    organization.blocked_at = None
    organization.blocked_by_user = None
    organization.save(update_fields=["abuse_status", "status", "abuse_reason", "blocked_at", "blocked_by_user", "updated_at"])
    return audit_log.record(
        action=audit_log.AuditAction.ABUSE_ORGANIZATION_UNBLOCKED,
        request=request,
        actor=operator,
        organization=organization,
        target_type="organization",
        target_id=organization.public_id,
        result=AuditResult.SUCCESS,
        metadata={"reason": reason},
    )


def ensure_project_can_deploy(project):
    organization = project.organization
    if organization.abuse_status == AbuseStatus.BLOCKED or organization.status == OrganizationStatus.SUSPENDED:
        raise AbuseError(safe_blocked_message(), code="organization_blocked")
    if project.abuse_status == AbuseStatus.BLOCKED or project.status == ProjectStatus.SUSPENDED:
        raise AbuseError(safe_blocked_message(), code="project_blocked")


def create_abuse_alert(signal, *, organization=None, project=None, user=None, metadata=None, correlation_id="abuse-monitor"):
    severity = ABUSE_ALERT_SEVERITY.get(signal, SecuritySeverity.MEDIUM)
    event = SecurityEvent.objects.create(
        organization=organization,
        project=project,
        user=user,
        severity=severity,
        category="abuse",
        event_type=signal,
        source="abuse-monitor",
        status=SecurityEventStatus.OPEN,
        correlation_id=correlation_id,
        metadata=metadata or {},
    )
    audit_log.record(
        action=audit_log.AuditAction.ABUSE_ALERT_CREATED,
        actor_type="system",
        organization=organization,
        project=project,
        target_type="security_event",
        target_id=event.public_id,
        metadata={"signal": signal, "severity": severity},
    )
    return event


def blocked_projects_queryset():
    return Project.objects.select_related("organization", "blocked_by_user").filter(abuse_status=AbuseStatus.BLOCKED)
