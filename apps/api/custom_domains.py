import re
import secrets

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.api import audit_log
from apps.api.certificates import request_certificate_for_domain
from apps.api.entitlements import can_add_domain
from apps.api.models import Domain, DomainStatus, DomainType


HOSTNAME_RE = re.compile(r"^(?=.{1,253}$)(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))*$")


class CustomDomainError(Exception):
    def __init__(self, message, code="custom_domain_error"):
        super().__init__(message)
        self.code = code


class DNSResolver:
    def txt_records(self, name):
        return []


class DomainProvisionerClient:
    def provision_domain(self, domain):
        return {
            "ingress_requested": True,
            "certificate_requested": True,
            "domain_public_id": str(domain.public_id),
        }

    def deprovision_domain(self, domain):
        return {"domain_public_id": str(domain.public_id), "deprovision_requested": True}


def serialize_domain(domain, include_instructions=False, verification_token=None):
    data = {
        "public_id": str(domain.public_id),
        "organization_id": str(domain.organization.public_id),
        "project_id": str(domain.project.public_id),
        "environment_id": str(domain.environment.public_id),
        "hostname": domain.hostname,
        "status": domain.status,
        "verified_at": domain.verified_at.isoformat() if domain.verified_at else None,
    }
    if include_instructions:
        data["dns_instructions"] = dns_instructions(domain.hostname, verification_token)
    return data


def create_domain(*, organization, project, environment, hostname, actor, request=None):
    entitlement = can_add_domain(organization)
    if not entitlement.allowed:
        raise CustomDomainError("Custom domains are not allowed by current entitlements.", code=entitlement.code or "entitlement_denied")
    normalized = normalize_hostname(hostname)
    _validate_hostname(normalized)
    _ensure_not_system_domain(normalized)
    _ensure_hostname_available(normalized, organization)
    token = generate_verification_token()
    with transaction.atomic():
        domain = Domain.objects.create(
            organization=organization,
            project=project,
            environment=environment,
            hostname=normalized,
            type=DomainType.CUSTOM,
            status=DomainStatus.PENDING_VERIFICATION,
        )
        domain.set_verification_token(token)
        domain.full_clean()
        domain.save(update_fields=["verification_token_hash", "hostname", "updated_at"])
        audit_log.record(
            action=audit_log.AuditAction.DOMAIN_ADDED,
            request=request,
            actor=actor,
            organization=organization,
            project=project,
            target_type="domain",
            target_id=domain.public_id,
            metadata={"hostname": domain.hostname, "status": domain.status},
        )
    return domain, token


def verify_domain(*, organization, project, environment, domain_public_id, actor, request=None, resolver=None, provisioner=None):
    resolver = resolver or DNSResolver()
    provisioner = provisioner or DomainProvisionerClient()
    domain = (
        Domain.objects.filter(
            organization=organization,
            project=project,
            environment=environment,
            public_id=domain_public_id,
            deleted_at__isnull=True,
        )
        .first()
    )
    if domain is None:
        raise Domain.DoesNotExist()
    records = resolver.txt_records(verification_record_name(domain.hostname))
    if not any(domain.check_verification_token(_clean_txt_record(record)) for record in records):
        domain.status = DomainStatus.FAILED
        domain.save(update_fields=["status", "updated_at"])
        audit_log.record(
            action=audit_log.AuditAction.DOMAIN_VERIFICATION_FAILED,
            request=request,
            actor=actor,
            organization=organization,
            project=project,
            target_type="domain",
            target_id=domain.public_id,
            metadata={"hostname": domain.hostname},
        )
        raise CustomDomainError("TXT verification record does not match.", code="txt_verification_failed")

    with transaction.atomic():
        domain = Domain.objects.select_for_update().get(pk=domain.pk)
        domain.status = DomainStatus.VERIFIED
        domain.verified_at = timezone.now()
        domain.save(update_fields=["status", "verified_at", "updated_at"])
        certificate = request_certificate_for_domain(domain=domain, actor=actor, request=request)
        provisioner_result = provisioner.provision_domain(domain)
        audit_log.record(
            action=audit_log.AuditAction.DOMAIN_VERIFIED,
            request=request,
            actor=actor,
            organization=organization,
            project=project,
            target_type="domain",
            target_id=domain.public_id,
            metadata={
                "hostname": domain.hostname,
                "certificate_public_id": str(certificate.public_id),
                "provisioner": provisioner_result,
            },
        )
    return domain


def mark_domain_active(*, organization, project, environment, domain_public_id, actor=None, request=None):
    with transaction.atomic():
        domain = Domain.objects.select_for_update().get(
            organization=organization,
            project=project,
            environment=environment,
            public_id=domain_public_id,
            deleted_at__isnull=True,
        )
        if not domain.verified_at:
            raise CustomDomainError("Domain must be verified before activation.", code="domain_not_verified")
        domain.status = DomainStatus.ACTIVE
        domain.save(update_fields=["status", "updated_at"])
        audit_log.record(
            action=audit_log.AuditAction.DOMAIN_ACTIVATED,
            request=request,
            actor=actor,
            organization=organization,
            project=project,
            target_type="domain",
            target_id=domain.public_id,
            metadata={"hostname": domain.hostname},
        )
    return domain


def disable_domain(*, organization, project, environment, domain_public_id, actor, request=None, provisioner=None):
    provisioner = provisioner or DomainProvisionerClient()
    with transaction.atomic():
        domain = Domain.objects.select_for_update().get(
            organization=organization,
            project=project,
            environment=environment,
            public_id=domain_public_id,
            deleted_at__isnull=True,
        )
        domain.status = DomainStatus.DISABLED
        domain.save(update_fields=["status", "updated_at"])
        provisioner.deprovision_domain(domain)
        audit_log.record(
            action=audit_log.AuditAction.DOMAIN_DISABLED,
            request=request,
            actor=actor,
            organization=organization,
            project=project,
            target_type="domain",
            target_id=domain.public_id,
            metadata={"hostname": domain.hostname},
        )
    return domain


def normalize_hostname(hostname):
    return (hostname or "").strip().lower().rstrip(".")


def generate_verification_token():
    return f"cdv_{secrets.token_urlsafe(32)}"


def verification_record_name(hostname):
    return f"{settings.CUSTOM_DOMAIN_TXT_RECORD_PREFIX}.{hostname}"


def dns_instructions(hostname, token):
    return {
        "type": "TXT",
        "name": verification_record_name(hostname),
        "value": token,
    }


def domains_due_for_verification(limit=100):
    return Domain.objects.filter(status=DomainStatus.PENDING_VERIFICATION, deleted_at__isnull=True).order_by("created_at")[:limit]


def check_pending_domains(*, resolver=None, provisioner=None, limit=100):
    results = []
    for domain in domains_due_for_verification(limit=limit):
        try:
            verify_domain(
                organization=domain.organization,
                project=domain.project,
                environment=domain.environment,
                domain_public_id=domain.public_id,
                actor=None,
                resolver=resolver,
                provisioner=provisioner,
            )
            results.append({"domain_public_id": str(domain.public_id), "status": DomainStatus.VERIFIED})
        except CustomDomainError as exc:
            results.append({"domain_public_id": str(domain.public_id), "status": DomainStatus.FAILED, "code": exc.code})
    return results


def _validate_hostname(hostname):
    if not hostname or "." not in hostname or not HOSTNAME_RE.match(hostname):
        raise CustomDomainError("Invalid hostname.", code="invalid_hostname")


def _ensure_not_system_domain(hostname):
    system_hostnames = {item.lower() for item in settings.CUSTOM_DOMAIN_SYSTEM_HOSTNAMES}
    system_suffixes = {item.lower().lstrip(".") for item in settings.CUSTOM_DOMAIN_SYSTEM_SUFFIXES}
    if hostname in system_hostnames:
        raise CustomDomainError("System domain cannot be added as a custom domain.", code="system_domain")
    for suffix in system_suffixes:
        if hostname == suffix or hostname.endswith(f".{suffix}"):
            raise CustomDomainError("System domain cannot be added as a custom domain.", code="system_domain")


def _ensure_hostname_available(hostname, organization):
    existing = Domain.objects.filter(hostname=hostname, deleted_at__isnull=True).first()
    if existing is None:
        return
    if existing.organization_id == organization.id:
        raise CustomDomainError("Domain is already assigned to this organization.", code="domain_exists")
    raise CustomDomainError("Domain is already assigned to another organization.", code="domain_taken")


def _clean_txt_record(record):
    return str(record).strip().strip('"')
