import logging

from deployment_worker.adapters import ArtifactScanner, ContainerBuilder, RuntimeDeployer, StaticSiteBuilder
from deployment_worker.backoff import retry_countdown
from deployment_worker.celery_app import celery_app
from deployment_worker.config import settings
from deployment_worker.errors import DeploymentWorkerError, PolicyBlockedError
from deployment_worker.repository import repository
from deployment_worker.statuses import BuildJobStatus, DeploymentStatus


logger = logging.getLogger(__name__)


def log_context(operation, payload):
    return {
        "correlation_id": payload.get("correlation_id", payload.get("request_id", "")),
        "request_id": payload.get("request_id", ""),
        "operation": operation,
        "organization_public_id": payload.get("organization_public_id", ""),
        "project_public_id": payload.get("project_public_id", ""),
        "environment_public_id": payload.get("environment_public_id", ""),
        "build_job_public_id": payload.get("build_job_public_id", ""),
        "deployment_public_id": payload.get("deployment_public_id", ""),
        "attempt": payload.get("attempt", 1),
    }


def update_statuses(payload, *, build_status=None, deployment_status=None, metadata=None):
    if build_status and payload.get("build_job_public_id"):
        repository.update_build_job(payload["build_job_public_id"], build_status, metadata=metadata)
    if deployment_status and payload.get("deployment_public_id"):
        repository.update_deployment(payload["deployment_public_id"], deployment_status, metadata=metadata)


def record_audit(event_type, payload, metadata=None):
    repository.record_event(
        event_type,
        {
            "organization_public_id": payload.get("organization_public_id"),
            "project_public_id": payload.get("project_public_id"),
            "environment_public_id": payload.get("environment_public_id"),
            "build_job_public_id": payload.get("build_job_public_id"),
            "deployment_public_id": payload.get("deployment_public_id"),
            "correlation_id": payload.get("correlation_id", payload.get("request_id", "")),
            "metadata": metadata or {},
        },
    )


def execute(operation, payload, handler, task=None):
    context = log_context(operation, payload)
    logger.info("deployment_task_started", extra={**context, "status": "running"})
    try:
        result = handler()
        logger.info("deployment_task_succeeded", extra={**context, "status": "succeeded"})
        return {"status": "succeeded", "result": result}
    except DeploymentWorkerError as exc:
        logger.warning("deployment_task_failed", extra={**context, "status": "failed", "error_code": exc.code})
        update_statuses(payload, build_status=BuildJobStatus.FAILED, deployment_status=DeploymentStatus.FAILED, metadata={"error_code": exc.code})
        record_audit("deployment.failed", payload, metadata={"error_code": exc.code})
        if exc.retryable and task is not None and getattr(task.request, "retries", 0) < settings.max_retry_attempts:
            raise task.retry(exc=exc, countdown=retry_countdown(getattr(task.request, "retries", 0) + 1))
        return {"status": "failed_retryable" if exc.retryable else "failed_terminal", "error_code": exc.code}


def ensure_no_control_plane_secrets(payload):
    forbidden = {"control_plane_secret", "database_url", "django_secret_key", "stripe_secret_key"}
    leaked = forbidden.intersection({str(key).lower() for key in payload.keys()})
    if leaked:
        raise PolicyBlockedError("Payload contains forbidden control plane secret fields.")


@celery_app.task(bind=True, name="deployment.create_static_deployment", time_limit=settings.static_build_timeout_seconds)
def create_static_deployment(self, payload):
    def handler():
        ensure_no_control_plane_secrets(payload)
        update_statuses(payload, build_status=BuildJobStatus.RUNNING, deployment_status=DeploymentStatus.BUILDING)
        record_audit("build_job.started", payload)
        result = StaticSiteBuilder().build(payload)
        if result["size_bytes"] > settings.max_static_artifact_bytes:
            raise PolicyBlockedError("Static artifact size limit exceeded.")
        update_statuses(payload, build_status=BuildJobStatus.SUCCEEDED, deployment_status=DeploymentStatus.SCANNING, metadata=result)
        record_audit("build_job.succeeded", payload, metadata={"artifact_ref": result["artifact_ref"], "checksum": result["checksum"]})
        return result

    return execute("create_static_deployment", payload, handler, task=self)


@celery_app.task(bind=True, name="deployment.create_container_deployment", time_limit=settings.container_build_timeout_seconds)
def create_container_deployment(self, payload):
    def handler():
        ensure_no_control_plane_secrets(payload)
        update_statuses(payload, build_status=BuildJobStatus.RUNNING, deployment_status=DeploymentStatus.BUILDING)
        record_audit("build_job.started", payload)
        result = ContainerBuilder().build(payload)
        if result["size_bytes"] > settings.max_container_image_bytes:
            raise PolicyBlockedError("Container image size limit exceeded.")
        update_statuses(payload, build_status=BuildJobStatus.SUCCEEDED, deployment_status=DeploymentStatus.SCANNING, metadata=result)
        record_audit("build_job.succeeded", payload, metadata={"image_ref": result["image_ref"], "image_digest": result["image_digest"]})
        return result

    return execute("create_container_deployment", payload, handler, task=self)


@celery_app.task(bind=True, name="deployment.scan_artifact", time_limit=settings.scan_timeout_seconds)
def scan_artifact(self, payload):
    def handler():
        ensure_no_control_plane_secrets(payload)
        update_statuses(payload, deployment_status=DeploymentStatus.SCANNING)
        result = ArtifactScanner().scan(payload)
        if result["decision"] == "block":
            raise PolicyBlockedError("Artifact scan blocked deployment.")
        update_statuses(payload, deployment_status=DeploymentStatus.DEPLOYING, metadata=result)
        record_audit("deployment.scan_passed", payload, metadata={"scan_report_ref": result["scan_report_ref"], "sbom_ref": result["sbom_ref"]})
        return result

    return execute("scan_artifact", payload, handler, task=self)


@celery_app.task(bind=True, name="deployment.deploy_to_runtime", time_limit=settings.deploy_timeout_seconds)
def deploy_to_runtime(self, payload):
    def handler():
        ensure_no_control_plane_secrets(payload)
        update_statuses(payload, deployment_status=DeploymentStatus.DEPLOYING)
        record_audit("deployment.started", payload)
        result = RuntimeDeployer().deploy(payload)
        update_statuses(payload, deployment_status=DeploymentStatus.ACTIVE, metadata=result)
        record_audit("deployment.active", payload, metadata=result)
        return result

    return execute("deploy_to_runtime", payload, handler, task=self)


@celery_app.task(bind=True, name="deployment.rollback_deployment", time_limit=settings.deploy_timeout_seconds)
def rollback_deployment(self, payload):
    def handler():
        ensure_no_control_plane_secrets(payload)
        update_statuses(payload, deployment_status=DeploymentStatus.DEPLOYING)
        record_audit("deployment.rollback_started", payload, metadata={"target": payload["target_deployment_public_id"]})
        result = RuntimeDeployer().rollback(payload)
        update_statuses(payload, deployment_status=DeploymentStatus.ROLLED_BACK, metadata=result)
        record_audit("deployment.rolled_back", payload, metadata=result)
        return result

    return execute("rollback_deployment", payload, handler, task=self)

