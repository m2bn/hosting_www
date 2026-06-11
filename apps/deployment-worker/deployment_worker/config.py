import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DeploymentWorkerSettings:
    broker_url: str = os.environ.get("DEPLOYMENT_WORKER_BROKER_URL", "amqp://guest:guest@localhost:5672//")
    result_backend: str = os.environ.get("DEPLOYMENT_WORKER_RESULT_BACKEND", "rpc://")
    max_retry_attempts: int = int(os.environ.get("DEPLOYMENT_WORKER_MAX_RETRY_ATTEMPTS", "3"))
    retry_base_seconds: int = int(os.environ.get("DEPLOYMENT_WORKER_RETRY_BASE_SECONDS", "10"))
    retry_max_seconds: int = int(os.environ.get("DEPLOYMENT_WORKER_RETRY_MAX_SECONDS", "900"))
    static_build_timeout_seconds: int = int(os.environ.get("STATIC_BUILD_TIMEOUT_SECONDS", "600"))
    container_build_timeout_seconds: int = int(os.environ.get("CONTAINER_BUILD_TIMEOUT_SECONDS", "1200"))
    scan_timeout_seconds: int = int(os.environ.get("DEPLOYMENT_SCAN_TIMEOUT_SECONDS", "600"))
    deploy_timeout_seconds: int = int(os.environ.get("DEPLOYMENT_ROLLOUT_TIMEOUT_SECONDS", "600"))
    max_static_artifact_bytes: int = int(os.environ.get("MAX_STATIC_ARTIFACT_BYTES", str(500 * 1024 * 1024)))
    max_container_image_bytes: int = int(os.environ.get("MAX_CONTAINER_IMAGE_BYTES", str(2 * 1024 * 1024 * 1024)))
    max_build_context_bytes: int = int(os.environ.get("MAX_BUILD_CONTEXT_BYTES", str(512 * 1024 * 1024)))
    private_container_registry: str = os.environ.get("PRIVATE_CONTAINER_REGISTRY", "registry.example.com/private")
    build_namespace_prefix: str = os.environ.get("BUILD_NAMESPACE_PREFIX", "build")
    build_cpu_limit: str = os.environ.get("BUILD_CPU_LIMIT", "2")
    build_memory_limit: str = os.environ.get("BUILD_MEMORY_LIMIT", "4Gi")
    build_cpu_request: str = os.environ.get("BUILD_CPU_REQUEST", "500m")
    build_memory_request: str = os.environ.get("BUILD_MEMORY_REQUEST", "1Gi")
    runtime_cpu_limit: str = os.environ.get("RUNTIME_CPU_LIMIT", "1")
    runtime_memory_limit: str = os.environ.get("RUNTIME_MEMORY_LIMIT", "512Mi")
    runtime_cpu_request: str = os.environ.get("RUNTIME_CPU_REQUEST", "100m")
    runtime_memory_request: str = os.environ.get("RUNTIME_MEMORY_REQUEST", "128Mi")
    control_plane_api_url: str = os.environ.get("CONTROL_PLANE_API_URL", "")
    control_plane_api_token: str = os.environ.get("CONTROL_PLANE_API_TOKEN", "")


settings = DeploymentWorkerSettings()
