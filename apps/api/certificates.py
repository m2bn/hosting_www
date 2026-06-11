from django.conf import settings
from django.utils import timezone

from apps.api import audit_log
from apps.api.models import Certificate, CertificateStatus, DomainStatus, SecurityEvent, SecuritySeverity


class CertificateError(Exception):
    def __init__(self, message, code="certificate_error"):
        super().__init__(message)
        self.code = code


class CertManagerClient:
    def request_certificate(self, certificate):
        return {
            "domain": certificate.domain.hostname,
            "provider": certificate.provider,
            "secret_name": certificate.kubernetes_secret_name,
        }

    def renew_certificate(self, certificate):
        return {
            "domain": certificate.domain.hostname,
            "provider": certificate.provider,
            "secret_name": certificate.kubernetes_secret_name,
            "renewal": True,
        }


def serialize_certificate(certificate):
    return {
        "public_id": str(certificate.public_id),
        "domain_id": str(certificate.domain.public_id),
        "hostname": certificate.domain.hostname,
        "provider": certificate.provider,
        "status": certificate.status,
        "not_before": certificate.not_before.isoformat() if certificate.not_before else None,
        "not_after": certificate.not_after.isoformat() if certificate.not_after else None,
        "kubernetes_secret_name": certificate.kubernetes_secret_name,
        "last_error": certificate.last_error,
    }


def certificate_secret_name(domain):
    return f"cert-{str(domain.public_id)[:12]}"


def request_certificate_for_domain(*, domain, actor=None, request=None, cert_manager=None):
    if domain.status not in [DomainStatus.VERIFIED, DomainStatus.ACTIVE]:
        raise CertificateError("Domain must be verified before requesting a certificate.", code="domain_not_verified")
    cert_manager = cert_manager or CertManagerClient()
    certificate, created = Certificate.objects.get_or_create(
        organization=domain.organization,
        domain=domain,
        defaults={
            "provider": settings.CUSTOM_DOMAIN_CERT_MANAGER_PROVIDER,
            "status": CertificateStatus.PENDING,
            "kubernetes_secret_name": certificate_secret_name(domain),
        },
    )
    if certificate.status in [CertificateStatus.FAILED, CertificateStatus.EXPIRED]:
        certificate.status = CertificateStatus.PENDING
        certificate.last_error = ""
        certificate.save(update_fields=["status", "last_error", "updated_at"])
    result = cert_manager.request_certificate(certificate)
    audit_log.record(
        action=audit_log.AuditAction.CERTIFICATE_REQUESTED,
        request=request,
        actor=actor,
        organization=domain.organization,
        project=domain.project,
        target_type="certificate",
        target_id=certificate.public_id,
        metadata={"created": created, "provider": certificate.provider, "cert_manager": result},
    )
    return certificate


def update_certificate_status(*, certificate, status, actor=None, request=None, reason="", not_before=None, not_after=None):
    previous_status = certificate.status
    certificate.status = status
    if not_before is not None:
        certificate.not_before = not_before
    if not_after is not None:
        certificate.not_after = not_after
    certificate.last_error = reason if status == CertificateStatus.FAILED else ""
    certificate.save(update_fields=["status", "not_before", "not_after", "last_error", "updated_at"])
    audit_log.record(
        action=audit_log.AuditAction.CERTIFICATE_STATUS_CHANGED,
        request=request,
        actor=actor,
        organization=certificate.organization,
        project=certificate.domain.project,
        target_type="certificate",
        target_id=certificate.public_id,
        metadata={"previous_status": previous_status, "status": status, "reason": reason},
    )
    return certificate


def mark_dns_error(*, certificate, reason="DNS validation failed.", actor=None, request=None):
    return update_certificate_status(certificate=certificate, status=CertificateStatus.FAILED, actor=actor, request=request, reason=reason)


def mark_acme_error(*, certificate, reason="ACME issuance failed.", actor=None, request=None):
    return update_certificate_status(certificate=certificate, status=CertificateStatus.FAILED, actor=actor, request=request, reason=reason)


def request_certificate_renewal(*, certificate, actor=None, request=None, cert_manager=None):
    cert_manager = cert_manager or CertManagerClient()
    previous_status = certificate.status
    certificate.status = CertificateStatus.RENEWAL_PENDING
    certificate.save(update_fields=["status", "updated_at"])
    result = cert_manager.renew_certificate(certificate)
    audit_log.record(
        action=audit_log.AuditAction.CERTIFICATE_RENEWAL_REQUESTED,
        request=request,
        actor=actor,
        organization=certificate.organization,
        project=certificate.domain.project,
        target_type="certificate",
        target_id=certificate.public_id,
        metadata={"previous_status": previous_status, "cert_manager": result},
    )
    return certificate


def create_expiry_alerts(*, now=None, days=None):
    now = now or timezone.now()
    days = settings.CERTIFICATE_EXPIRY_ALERT_DAYS if days is None else days
    threshold = now + timezone.timedelta(days=days)
    expiring = Certificate.objects.select_related("organization", "domain", "domain__project").filter(
        status=CertificateStatus.ACTIVE,
        not_after__isnull=False,
        not_after__lte=threshold,
    )
    alerts = []
    for certificate in expiring:
        event, _ = SecurityEvent.objects.get_or_create(
            organization=certificate.organization,
            project=certificate.domain.project,
            category="certificate",
            event_type="certificate.expiring",
            source="certificate-monitor",
            correlation_id=str(certificate.public_id),
            defaults={
                "severity": SecuritySeverity.HIGH,
                "metadata": {
                    "certificate_public_id": str(certificate.public_id),
                    "domain": certificate.domain.hostname,
                    "not_after": certificate.not_after.isoformat(),
                },
            },
        )
        audit_log.record(
            action=audit_log.AuditAction.CERTIFICATE_EXPIRING,
            organization=certificate.organization,
            project=certificate.domain.project,
            target_type="certificate",
            target_id=certificate.public_id,
            metadata={"domain": certificate.domain.hostname, "not_after": certificate.not_after.isoformat()},
        )
        alerts.append(event)
    return alerts
