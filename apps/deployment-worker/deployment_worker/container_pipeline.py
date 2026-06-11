import fnmatch
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from deployment_worker.config import settings
from deployment_worker.errors import PolicyBlockedError
from deployment_worker.statuses import ContainerBuildStatus


@dataclass(frozen=True)
class BuildLimits:
    cpu_request: str = settings.build_cpu_request
    cpu_limit: str = settings.build_cpu_limit
    memory_request: str = settings.build_memory_request
    memory_limit: str = settings.build_memory_limit
    timeout_seconds: int = settings.container_build_timeout_seconds
    max_context_bytes: int = settings.max_build_context_bytes


@dataclass(frozen=True)
class BuildContext:
    root: Path | None
    project_slug: str
    deployment_public_id: str
    build_job_public_id: str
    dockerfile: str = "Dockerfile"
    dockerignore: str = ".dockerignore"
    registry: str = settings.private_container_registry
    namespace: str | None = None
    limits: BuildLimits = field(default_factory=BuildLimits)

    @classmethod
    def from_payload(cls, payload):
        context_path = payload.get("build_context_path")
        return cls(
            root=Path(context_path).resolve() if context_path else None,
            project_slug=payload["project_slug"],
            deployment_public_id=payload["deployment_public_id"],
            build_job_public_id=payload["build_job_public_id"],
            dockerfile=payload.get("dockerfile", "Dockerfile"),
            registry=payload.get("registry", settings.private_container_registry),
            namespace=payload.get("build_namespace"),
        )

    @property
    def isolated_namespace(self):
        if self.namespace:
            return self.namespace
        return f"{settings.build_namespace_prefix}-{self.project_slug}-{self.deployment_public_id}"


@dataclass(frozen=True)
class BuildResult:
    image_ref: str
    image_digest: str
    logs_ref: str
    size_bytes: int
    status: str = ContainerBuildStatus.READY_FOR_DEPLOY


@dataclass(frozen=True)
class ImageScanResult:
    scan_report_ref: str
    sbom_ref: str
    decision: str
    critical_count: int = 0
    high_count: int = 0


class BuildStrategy(ABC):
    @abstractmethod
    def build(self, context: BuildContext) -> BuildResult:
        raise NotImplementedError

    @abstractmethod
    def build_pod_spec(self, context: BuildContext) -> dict:
        raise NotImplementedError


class DockerignoreMatcher:
    def __init__(self, patterns: Iterable[str]):
        self.patterns = [pattern for pattern in patterns if pattern and not pattern.startswith("#")]

    @classmethod
    def from_file(cls, root: Path, filename: str):
        path = root / filename
        if not path.exists():
            return cls([])
        return cls(path.read_text(encoding="utf-8").splitlines())

    def matches(self, relative_path: Path):
        normalized = relative_path.as_posix()
        for pattern in self.patterns:
            clean = pattern.strip().lstrip("/")
            if not clean:
                continue
            if clean.endswith("/") and (normalized == clean[:-1] or normalized.startswith(clean)):
                return True
            if fnmatch.fnmatch(normalized, clean) or fnmatch.fnmatch(relative_path.name, clean):
                return True
        return False


class DockerfileBuildStrategy(BuildStrategy):
    def build(self, context: BuildContext) -> BuildResult:
        context_size = self.validate_context(context)
        registry = context.registry.rstrip("/")
        image_ref = f"{registry}/{context.project_slug}:{context.deployment_public_id}"
        return BuildResult(
            image_ref=image_ref,
            image_digest=f"sha256:{context.deployment_public_id}",
            logs_ref=f"logs/build/{context.build_job_public_id}.log",
            size_bytes=max(context_size, 1),
        )

    def validate_context(self, context: BuildContext) -> int:
        if context.root is None:
            return 1024
        if not context.root.exists() or not context.root.is_dir():
            raise PolicyBlockedError("Build context does not exist.")
        dockerfile_path = (context.root / context.dockerfile).resolve()
        if not dockerfile_path.exists() or not dockerfile_path.is_file():
            raise PolicyBlockedError("Dockerfile is required for Dockerfile builds.")
        if context.root not in dockerfile_path.parents:
            raise PolicyBlockedError("Dockerfile must be inside the build context.")

        matcher = DockerignoreMatcher.from_file(context.root, context.dockerignore)
        total = 0
        for path in context.root.rglob("*"):
            relative_path = path.relative_to(context.root)
            if matcher.matches(relative_path):
                continue
            if path.is_symlink():
                raise PolicyBlockedError("Symlinks are not allowed in container build context.")
            if path.is_file():
                total += path.stat().st_size
                if total > context.limits.max_context_bytes:
                    raise PolicyBlockedError("Container build context size limit exceeded.")
        return total

    def build_pod_spec(self, context: BuildContext) -> dict:
        return {
            "namespace": context.isolated_namespace,
            "timeout_seconds": context.limits.timeout_seconds,
            "automountServiceAccountToken": False,
            "volumes": [],
            "containers": [
                {
                    "name": "builder",
                    "image": "internal/buildkit-rootless:latest",
                    "securityContext": {
                        "privileged": False,
                        "allowPrivilegeEscalation": False,
                        "runAsNonRoot": True,
                        "readOnlyRootFilesystem": True,
                        "seccompProfile": {"type": "RuntimeDefault"},
                    },
                    "resources": {
                        "requests": {"cpu": context.limits.cpu_request, "memory": context.limits.memory_request},
                        "limits": {"cpu": context.limits.cpu_limit, "memory": context.limits.memory_limit},
                    },
                    "env": [],
                }
            ],
        }


class BuildpackStrategy(BuildStrategy):
    def build(self, context: BuildContext) -> BuildResult:
        raise NotImplementedError("Buildpack support is a placeholder and is not enabled yet.")

    def build_pod_spec(self, context: BuildContext) -> dict:
        raise NotImplementedError("Buildpack support is a placeholder and is not enabled yet.")


class ImageScanStep:
    def evaluate(self, result: ImageScanResult) -> ImageScanResult:
        if result.critical_count > 0 or result.decision == "block":
            raise PolicyBlockedError("Image scan blocked deployment because policy found critical vulnerabilities.")
        return result

    def scan(self, payload) -> ImageScanResult:
        result = ImageScanResult(
            scan_report_ref=f"scans/{payload['deployment_public_id']}.json",
            sbom_ref=f"sbom/{payload['deployment_public_id']}.json",
            decision=payload.get("scan_decision", "pass"),
            critical_count=int(payload.get("critical_vulnerabilities", 0)),
            high_count=int(payload.get("high_vulnerabilities", 0)),
        )
        return self.evaluate(result)


class RuntimeDeployStep:
    def deployment_spec(self, payload) -> dict:
        namespace = payload.get("kubernetes_namespace")
        if not namespace:
            raise PolicyBlockedError("Project namespace is required for runtime deployment.")

        readiness_probe = payload.get("readiness_probe", {"httpGet": {"path": "/", "port": 8080}})
        liveness_probe = payload.get("liveness_probe", {"httpGet": {"path": "/", "port": 8080}})
        return {
            "namespace": namespace,
            "image_ref": payload.get("image_ref"),
            "image_digest": payload.get("image_digest"),
            "workload_name": payload.get("workload_name", "runtime"),
            "readinessProbe": readiness_probe,
            "livenessProbe": liveness_probe,
            "networkPolicyRequired": True,
            "securityContext": {
                "privileged": False,
                "allowPrivilegeEscalation": False,
                "runAsNonRoot": True,
                "readOnlyRootFilesystem": True,
                "seccompProfile": {"type": "RuntimeDefault"},
            },
            "resources": {
                "requests": {"cpu": settings.runtime_cpu_request, "memory": settings.runtime_memory_request},
                "limits": {"cpu": settings.runtime_cpu_limit, "memory": settings.runtime_memory_limit},
            },
        }

    def deploy(self, payload) -> dict:
        spec = self.deployment_spec(payload)
        if not spec["image_ref"] or not spec["image_digest"]:
            raise PolicyBlockedError("Scanned image reference and digest are required for runtime deployment.")
        return {
            "runtime_instance_ref": f"runtime/{payload['deployment_public_id']}",
            "namespace": spec["namespace"],
            "workload_name": spec["workload_name"],
            "spec": spec,
        }


class RollbackStep:
    def rollback(self, payload) -> dict:
        namespace = payload.get("kubernetes_namespace")
        target = payload.get("target_deployment_public_id")
        if not namespace or not target:
            raise PolicyBlockedError("Rollback requires project namespace and target deployment.")
        return {
            "rolled_back_to": target,
            "namespace": namespace,
            "workload_name": payload.get("workload_name", "runtime"),
        }
