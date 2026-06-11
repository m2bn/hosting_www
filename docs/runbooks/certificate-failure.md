# Runbook: Certificate Failure

## Symptoms

- `Certificate.status = failed` or `expired`.
- `Domain.status` remains `verified`, but TLS is not active.
- Security alert `certificate.expiring` appears.
- cert-manager reports DNS01/HTTP01/ACME errors.

## Immediate Checks

1. Confirm the domain is scoped to the expected organization, project, and environment.
2. Check the domain TXT verification record still exists.
3. Inspect cert-manager `Certificate`, `CertificateRequest`, `Order`, and `Challenge` resources in the project namespace.
4. Check DNS propagation from more than one resolver.
5. Review ACME errors for rate limits, CAA failures, invalid authorization, or account issues.

## Remediation

- DNS error: ask the customer to restore/fix DNS records, then retry certificate request.
- ACME rate limit: wait for the provider window or switch to a permitted fallback issuer.
- Expiring certificate: trigger renewal and monitor status until `active`.
- Expired certificate: keep ingress serving the last safe state, mark the certificate `expired`, and create a high-priority incident.

## Security Notes

- Do not accept private key upload in the first version.
- Do not copy private keys into tickets, logs, AuditLog metadata, or chat.
- Provisioner must only request certificates for verified domains.
- Certificate status changes must be recorded in AuditLog.

## Escalation

Escalate to platform operations when:

- renewal fails twice,
- the certificate expires within 72 hours,
- ACME account or issuer errors affect multiple tenants,
- DNS ownership appears suspicious or inconsistent.
