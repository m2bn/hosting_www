import os
from dataclasses import dataclass


def bool_env(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ProvisionerSettings:
    broker_url: str = os.environ.get("PROVISIONER_BROKER_URL", "amqp://guest:guest@localhost:5672//")
    result_backend: str = os.environ.get("PROVISIONER_RESULT_BACKEND", "rpc://")
    kubernetes_namespace_prefix: str = os.environ.get("PROVISIONER_NAMESPACE_PREFIX", "proj")
    kubernetes_in_cluster: bool = bool_env("PROVISIONER_KUBERNETES_IN_CLUSTER", False)
    kubeconfig_path: str = os.environ.get("PROVISIONER_KUBECONFIG", "")
    storage_bucket_prefix: str = os.environ.get("PROVISIONER_STORAGE_BUCKET_PREFIX", "projects")
    max_retry_attempts: int = int(os.environ.get("PROVISIONER_MAX_RETRY_ATTEMPTS", "8"))
    retry_base_seconds: int = int(os.environ.get("PROVISIONER_RETRY_BASE_SECONDS", "10"))
    retry_max_seconds: int = int(os.environ.get("PROVISIONER_RETRY_MAX_SECONDS", "1800"))


settings = ProvisionerSettings()

