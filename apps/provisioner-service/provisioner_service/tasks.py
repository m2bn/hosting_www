import logging

from provisioner_service.backoff import retry_countdown
from provisioner_service.celery_app import celery_app
from provisioner_service.config import settings
from provisioner_service.idempotency import store
from provisioner_service.k8s import KubernetesProvisioner, ProjectRef, ProvisionerError


logger = logging.getLogger(__name__)


def project_ref(payload):
    return ProjectRef(
        organization_public_id=payload["organization_public_id"],
        project_public_id=payload["project_public_id"],
        environment_public_id=payload["environment_public_id"],
        project_slug=payload["project_slug"],
        environment_slug=payload.get("environment_slug", "production"),
    )


def idempotency_key(operation, payload):
    explicit = payload.get("idempotency_key")
    if explicit:
        return explicit
    if "domain_public_id" in payload:
        return f"{operation}:{payload['domain_public_id']}"
    return f"{operation}:{payload['project_public_id']}:{payload.get('environment_public_id', '')}"


def execute(operation, payload, handler, task=None):
    key = idempotency_key(operation, payload)
    record, should_run = store.begin(key)
    if not should_run:
        return {"status": "succeeded", "idempotent": True, "result": record.result}

    log_context = {
        "request_id": payload.get("request_id", ""),
        "correlation_id": payload.get("correlation_id", payload.get("request_id", "")),
        "job_id": payload.get("job_id", ""),
        "idempotency_key": key,
        "operation": operation,
        "organization_public_id": payload.get("organization_public_id", ""),
        "project_public_id": payload.get("project_public_id", ""),
        "environment_public_id": payload.get("environment_public_id", ""),
        "domain_public_id": payload.get("domain_public_id", ""),
        "attempt": payload.get("attempt", 1),
    }
    logger.info("provisioning_job_started", extra={**log_context, "status": "running"})
    try:
        result = handler()
        store.complete(key, result)
        logger.info("provisioning_job_succeeded", extra={**log_context, "status": "succeeded"})
        return {"status": "succeeded", "idempotent": False, "result": result}
    except ProvisionerError as exc:
        store.fail(key, {"error_code": exc.code})
        logger.warning("provisioning_job_failed", extra={**log_context, "status": "failed", "error_code": exc.code})
        if exc.retryable and task is not None and getattr(task.request, "retries", 0) < settings.max_retry_attempts:
            raise task.retry(exc=exc, countdown=retry_countdown(getattr(task.request, "retries", 0) + 1))
        return {"status": "failed_retryable" if exc.retryable else "failed_terminal", "error_code": exc.code}


@celery_app.task(bind=True, name="provisioner.provision_project")
def provision_project(self, payload):
    ref = project_ref(payload)
    client = KubernetesProvisioner()
    return execute(
        "project.provision",
        payload,
        lambda: client.provision_project(ref, quotas=payload.get("quotas"), limits=payload.get("limits")),
        task=self,
    )


@celery_app.task(bind=True, name="provisioner.deprovision_project")
def deprovision_project(self, payload):
    ref = project_ref(payload)
    client = KubernetesProvisioner()
    return execute("project.deprovision", payload, lambda: client.deprovision_project(ref), task=self)


@celery_app.task(bind=True, name="provisioner.reconcile_project")
def reconcile_project(self, payload):
    ref = project_ref(payload)
    client = KubernetesProvisioner()
    return execute(
        "project.reconcile",
        payload,
        lambda: client.reconcile_project(ref, quotas=payload.get("quotas"), limits=payload.get("limits")),
        task=self,
    )


@celery_app.task(bind=True, name="provisioner.provision_domain")
def provision_domain(self, payload):
    ref = project_ref(payload)
    domain = {"public_id": payload["domain_public_id"], "hostname": payload["hostname"]}
    client = KubernetesProvisioner()
    return execute("domain.provision", payload, lambda: client.provision_domain(ref, domain), task=self)


@celery_app.task(bind=True, name="provisioner.deprovision_domain")
def deprovision_domain(self, payload):
    ref = project_ref(payload)
    domain = {"public_id": payload["domain_public_id"], "hostname": payload["hostname"]}
    client = KubernetesProvisioner()
    return execute("domain.deprovision", payload, lambda: client.deprovision_domain(ref, domain), task=self)


@celery_app.task(bind=True, name="provisioner.provision_certificate")
def provision_certificate(self, payload):
    ref = project_ref(payload)
    domain = {"public_id": payload["domain_public_id"], "hostname": payload["hostname"]}
    client = KubernetesProvisioner()
    return execute("certificate.provision", payload, lambda: client.provision_certificate(ref, domain), task=self)

