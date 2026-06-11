from deployment_worker.config import settings
from deployment_worker.container_pipeline import BuildContext, DockerfileBuildStrategy, ImageScanStep, RuntimeDeployStep, RollbackStep


class StaticSiteBuilder:
    def build(self, payload):
        return {
            "artifact_ref": f"artifacts/static/{payload['deployment_public_id']}.tar.gz",
            "logs_ref": f"logs/build/{payload['build_job_public_id']}.log",
            "checksum": f"sha256:{payload['deployment_public_id']}",
            "size_bytes": min(settings.max_static_artifact_bytes, 1024),
        }


class ContainerBuilder:
    def build(self, payload):
        result = DockerfileBuildStrategy().build(BuildContext.from_payload(payload))
        return {
            "image_ref": result.image_ref,
            "image_digest": result.image_digest,
            "logs_ref": result.logs_ref,
            "size_bytes": min(settings.max_container_image_bytes, result.size_bytes),
            "build_status": result.status,
        }


class ArtifactScanner:
    def scan(self, payload):
        result = ImageScanStep().scan(payload)
        return {
            "scan_report_ref": result.scan_report_ref,
            "sbom_ref": result.sbom_ref,
            "decision": result.decision,
            "critical_count": result.critical_count,
            "high_count": result.high_count,
        }


class RuntimeDeployer:
    def deploy(self, payload):
        return RuntimeDeployStep().deploy(payload)

    def rollback(self, payload):
        return RollbackStep().rollback(payload)
