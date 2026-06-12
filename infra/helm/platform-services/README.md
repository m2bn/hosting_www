# Platform Services Helm Chart

Helm chart for the SaaS hosting platform control-plane services:

- `api`
- `dashboard`
- `billing-service`
- `provisioner-service`
- `deployment-worker`
- `notification-service`
- `metering-service`

## Design

The chart uses one shared service template pattern and service-specific values. Each enabled service receives:

- `Deployment`
- `Service`
- `ConfigMap`
- `Secret` or `ExternalSecret`
- `NetworkPolicy`
- `PodDisruptionBudget`
- `HorizontalPodAutoscaler` when enabled

## Environments

Use environment-specific values files:

```bash
helm upgrade --install platform-services ./infra/helm/platform-services \
  --namespace platform-staging \
  --create-namespace \
  -f ./infra/helm/platform-services/values-staging.yaml
```

```bash
helm upgrade --install platform-services ./infra/helm/platform-services \
  --namespace platform \
  --create-namespace \
  -f ./infra/helm/platform-services/values-production.yaml
```

## Secrets

Do not put secret values in `values.yaml`, `values-staging.yaml`, or `values-production.yaml`.

The chart supports External Secrets:

```yaml
externalSecrets:
  enabled: true
  secretStoreRef:
    name: platform-production-secrets
    kind: ClusterSecretStore
```

Each service defines `secretKeys`, which are names of required environment variables. They are not secret values. The default remote secret path is:

```text
platform/<namespace>/<service>/<KEY>
```

If External Secrets is disabled, the chart creates empty placeholder Kubernetes Secrets so local clusters can mount the expected `envFrom` sources. Populate those placeholders out of band for non-production test environments only.

## Security Baseline

The chart sets:

- `runAsNonRoot: true`
- `allowPrivilegeEscalation: false`
- dropped Linux capabilities
- `seccompProfile: RuntimeDefault`
- `privileged: false`
- `readOnlyRootFilesystem: true` where possible
- resource requests and limits for every service
- liveness and readiness probes
- namespace Pod Security labels set to `restricted`
- service account token automount disabled by default
- NetworkPolicy ingress and egress controls

`deployment-worker` has `readOnlyRootFilesystem: false` because build orchestration commonly needs writable temporary directories. Runtime build jobs should still use isolated namespaces and restricted build pods.

## Tests

Static chart tests:

```bash
python infra/helm/platform-services/tests/test_chart_static.py
```

Pytest, if available:

```bash
pytest infra/helm/platform-services/tests
```

Helm render validation:

```bash
helm lint infra/helm/platform-services
helm template platform-services infra/helm/platform-services -f infra/helm/platform-services/values-staging.yaml
helm template platform-services infra/helm/platform-services -f infra/helm/platform-services/values-production.yaml
```

Cluster smoke test after install:

```bash
helm test platform-services --namespace platform
```

## Production Checklist

- External Secrets is enabled.
- Production images use immutable tags or digests.
- All services have requests and limits.
- HPA is enabled for request-serving and scalable worker services.
- PDB is enabled for replicated services.
- NetworkPolicy egress CIDRs are restricted to real dependencies.
- No secret values exist in values files or rendered ConfigMaps.
- CI runs Helm lint, static chart tests, and manifest policy checks.
