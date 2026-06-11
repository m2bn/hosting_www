from dataclasses import dataclass

from provisioner_service.config import settings


class ProvisionerError(Exception):
    retryable = False
    code = "provisioner_error"


class RetryableProvisionerError(ProvisionerError):
    retryable = True
    code = "retryable_error"


class TerminalProvisionerError(ProvisionerError):
    retryable = False
    code = "terminal_error"


@dataclass(frozen=True)
class ProjectRef:
    organization_public_id: str
    project_public_id: str
    environment_public_id: str
    project_slug: str
    environment_slug: str = "production"

    @property
    def namespace(self):
        short_id = self.project_public_id.split("-", 1)[0]
        return f"{settings.kubernetes_namespace_prefix}-{self.project_slug}-{short_id}"[:63]

    @property
    def labels(self):
        return {
            "managed_by": "provisioner",
            "organization_public_id": self.organization_public_id,
            "project_public_id": self.project_public_id,
            "environment_public_id": self.environment_public_id,
        }


class KubernetesProvisioner:
    def __init__(self, core_v1=None, networking_v1=None, custom_objects=None):
        self.core_v1 = core_v1
        self.networking_v1 = networking_v1
        self.custom_objects = custom_objects
        if not all([self.core_v1, self.networking_v1, self.custom_objects]):
            self._load_clients()

    def provision_project(self, ref, quotas=None, limits=None):
        self.ensure_namespace(ref)
        self.ensure_service_account(ref)
        self.ensure_resource_quota(ref, quotas or {})
        self.ensure_limit_range(ref, limits or {})
        self.ensure_network_policy(ref)
        self.ensure_storage_prefix(ref)
        return {"namespace": ref.namespace}

    def deprovision_project(self, ref):
        self.delete_ingresses(ref)
        self.delete_certificate_requests(ref)
        self.delete_storage_prefix(ref)
        self.delete_namespace(ref)
        return {"namespace": ref.namespace}

    def reconcile_project(self, ref, quotas=None, limits=None):
        return self.provision_project(ref, quotas=quotas, limits=limits)

    def provision_domain(self, ref, domain):
        self.ensure_ingress(ref, domain)
        return {"namespace": ref.namespace, "domain": domain["hostname"]}

    def deprovision_domain(self, ref, domain):
        self.delete_ingress(ref, domain)
        return {"namespace": ref.namespace, "domain": domain["hostname"]}

    def provision_certificate(self, ref, domain):
        self.ensure_certificate_request(ref, domain)
        return {"namespace": ref.namespace, "domain": domain["hostname"]}

    def ensure_namespace(self, ref):
        body = {"metadata": {"name": ref.namespace, "labels": ref.labels}}
        self._create_or_ignore_exists(self.core_v1.create_namespace, body=body)

    def ensure_service_account(self, ref):
        body = {"metadata": {"name": "runtime", "namespace": ref.namespace, "labels": ref.labels}}
        self._create_or_ignore_exists(self.core_v1.create_namespaced_service_account, namespace=ref.namespace, body=body)

    def ensure_resource_quota(self, ref, quotas):
        body = {"metadata": {"name": "project-quota", "labels": ref.labels}, "spec": {"hard": quotas}}
        self._create_or_ignore_exists(self.core_v1.create_namespaced_resource_quota, namespace=ref.namespace, body=body)

    def ensure_limit_range(self, ref, limits):
        body = {
            "metadata": {"name": "project-limits", "labels": ref.labels},
            "spec": {"limits": [{"type": "Container", **limits}] if limits else []},
        }
        self._create_or_ignore_exists(self.core_v1.create_namespaced_limit_range, namespace=ref.namespace, body=body)

    def ensure_network_policy(self, ref):
        body = {
            "metadata": {"name": "default-deny", "labels": ref.labels},
            "spec": {"podSelector": {}, "policyTypes": ["Ingress", "Egress"]},
        }
        self._create_or_ignore_exists(self.networking_v1.create_namespaced_network_policy, namespace=ref.namespace, body=body)

    def ensure_storage_prefix(self, ref):
        return f"{settings.storage_bucket_prefix}/{ref.organization_public_id}/{ref.project_public_id}/"

    def ensure_ingress(self, ref, domain):
        body = {
            "metadata": {"name": f"domain-{domain['public_id'][:8]}", "labels": ref.labels},
            "spec": {"rules": [{"host": domain["hostname"]}]},
        }
        self._create_or_ignore_exists(self.networking_v1.create_namespaced_ingress, namespace=ref.namespace, body=body)

    def ensure_certificate_request(self, ref, domain):
        body = {
            "apiVersion": "cert-manager.io/v1",
            "kind": "Certificate",
            "metadata": {"name": f"cert-{domain['public_id'][:8]}", "namespace": ref.namespace, "labels": ref.labels},
            "spec": {"dnsNames": [domain["hostname"]], "secretName": f"tls-{domain['public_id'][:8]}"},
        }
        self._create_or_ignore_exists(
            self.custom_objects.create_namespaced_custom_object,
            group="cert-manager.io",
            version="v1",
            namespace=ref.namespace,
            plural="certificates",
            body=body,
        )

    def delete_ingresses(self, ref):
        self._delete_or_ignore_not_found(
            self.networking_v1.delete_collection_namespaced_ingress,
            namespace=ref.namespace,
            label_selector="managed_by=provisioner",
        )

    def delete_certificate_requests(self, ref):
        self._delete_or_ignore_not_found(
            self.custom_objects.delete_collection_namespaced_custom_object,
            group="cert-manager.io",
            version="v1",
            namespace=ref.namespace,
            plural="certificates",
            label_selector="managed_by=provisioner",
        )

    def delete_storage_prefix(self, ref):
        return f"{settings.storage_bucket_prefix}/{ref.organization_public_id}/{ref.project_public_id}/"

    def delete_namespace(self, ref):
        self._delete_or_ignore_not_found(self.core_v1.delete_namespace, name=ref.namespace)

    def delete_ingress(self, ref, domain):
        self._delete_or_ignore_not_found(
            self.networking_v1.delete_namespaced_ingress,
            name=f"domain-{domain['public_id'][:8]}",
            namespace=ref.namespace,
        )

    def _create_or_ignore_exists(self, func, **kwargs):
        try:
            return func(**kwargs)
        except Exception as exc:
            if getattr(exc, "status", None) == 409:
                return None
            raise RetryableProvisionerError("Kubernetes create operation failed.") from exc

    def _delete_or_ignore_not_found(self, func, **kwargs):
        try:
            return func(**kwargs)
        except Exception as exc:
            if getattr(exc, "status", None) == 404:
                return None
            raise RetryableProvisionerError("Kubernetes delete operation failed.") from exc

    def _load_clients(self):
        try:
            from kubernetes import client, config
            if settings.kubernetes_in_cluster:
                config.load_incluster_config()
            elif settings.kubeconfig_path:
                config.load_kube_config(config_file=settings.kubeconfig_path)
            else:
                config.load_kube_config()
            self.core_v1 = self.core_v1 or client.CoreV1Api()
            self.networking_v1 = self.networking_v1 or client.NetworkingV1Api()
            self.custom_objects = self.custom_objects or client.CustomObjectsApi()
        except Exception as exc:
            raise RetryableProvisionerError("Kubernetes client is not available.") from exc
