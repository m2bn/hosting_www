# Kubernetes runtime security

## 1. Cel

Runtime Kubernetes uruchamia aplikacje klientów w izolowanych namespace per projekt. Baseline ma ograniczyć blast radius pojedynczego workloadu i wymusić minimalny standard bezpieczeństwa przed wdrożeniem pełnego provisionera.

Artefakty:

- `infra/kubernetes/customer-runtime-baseline.yaml`: przykładowe manifesty bazowe;
- `infra/helm/customer-runtime`: Helm chart dla runtime projektu;
- `infra/policies/kyverno-runtime-baseline.yaml`: polityki admission.

## 2. Namespace per project

Każdy projekt powinien dostać osobny namespace z labelami:

- `app.kubernetes.io/managed-by=provisioner`;
- `platform.example.com/organization-id`;
- `platform.example.com/project-id`;
- `platform.example.com/environment-id`.

Namespace musi wymuszać Pod Security Restricted:

- `pod-security.kubernetes.io/enforce=restricted`;
- `pod-security.kubernetes.io/audit=restricted`;
- `pod-security.kubernetes.io/warn=restricted`.

## 3. ResourceQuota i LimitRange

Każdy namespace projektu musi mieć:

- `ResourceQuota`: twarde limity CPU, RAM i liczby podów;
- `LimitRange`: domyślne request/limit dla kontenerów.

Workload bez limitów nie powinien przejść admission.

## 4. NetworkPolicy

Baseline tworzy:

- `default-deny-ingress`;
- `default-deny-egress`;
- `allow-dns-egress`.

Egress jest domyślnie zablokowany. Pierwszym dopuszczonym wyjątkiem jest DNS do `kube-system` na TCP/UDP 53.

Dalsze wyjątki, np. egress do registry, storage, telemetry collector albo zewnętrznych API klienta, muszą być jawne i generowane z konfiguracji projektu.

## 5. Workload security context

Deployment runtime musi mieć:

- `automountServiceAccountToken=false`;
- `runAsNonRoot=true`;
- `allowPrivilegeEscalation=false`;
- `privileged=false`;
- `readOnlyRootFilesystem=true`, jeśli aplikacja nie wymaga zapisu;
- `seccompProfile.type=RuntimeDefault`;
- `capabilities.drop=["ALL"]`;
- CPU/RAM requests i limits;
- `readinessProbe`;
- `livenessProbe`.

Zakazane:

- `hostPath`;
- `hostNetwork`;
- `hostPID`;
- privileged containers;
- service account token mount, jeśli nie jest potrzebny;
- brak resource limits.

## 6. Polityki Kyverno

`infra/policies/kyverno-runtime-baseline.yaml` blokuje:

- privileged containers;
- hostPath;
- hostNetwork;
- hostPID;
- hostIPC;
- `allowPrivilegeEscalation=true`;
- brak CPU/RAM requests i limits;
- brak `runAsNonRoot`;
- brak `seccompProfile RuntimeDefault`;
- namespace bez Pod Security Restricted labels.

Polityki powinny działać w trybie `Enforce` dla runtime klientów.

## 7. Service account

Runtime workload używa service account `runtime`.

Domyślnie:

- `automountServiceAccountToken=false`;
- brak RBAC do Kubernetes API;
- brak możliwości odczytu Kubernetes Secrets.

Jeśli aplikacja klienta wymaga dostępu do Kubernetes API, musi to być osobna funkcja enterprise z osobnym threat model i explicit allowlist.

## 8. Storage i filesystem

`readOnlyRootFilesystem=true` jest baseline.

Jeśli aplikacja potrzebuje zapisu:

- preferuj ephemeral volume `emptyDir` z limitem size;
- nie używaj `hostPath`;
- nie montuj host filesystem;
- nie zapisuj sekretów do trwałego wolumenu bez szyfrowania i retencji.

## 9. Probes

Każdy workload musi mieć:

- `readinessProbe`: decyduje o ruchu do poda;
- `livenessProbe`: restartuje zawieszony workload.

Brak probes utrudnia bezpieczne rollouty i rollbacki.

## 10. Testy polityk

Testy lokalne znajdują się w `tests/infrastructure/test_kubernetes_runtime_security.py`.

Sprawdzają:

- namespace isolation labels;
- Pod Security Restricted labels;
- ResourceQuota i LimitRange;
- default deny ingress/egress;
- allow DNS egress;
- restricted security context;
- brak niebezpiecznych pól w baseline;
- obecność reguł Kyverno.

W CI docelowo należy dodać:

- `helm template` dla chartu;
- Kyverno CLI albo Conftest na renderowanych manifestach;
- testy negatywne manifestów z `privileged`, `hostPath`, `hostNetwork`, brakiem limits i brakiem seccomp.

## 11. Granice zaufania

Manifest runtime jest generowany przez platformę, nie przez klienta.

Klient może dostarczać:

- obraz aplikacji;
- port;
- healthcheck paths;
- zmienne środowiskowe;
- deklarowane zależności egress.

Platforma musi walidować te dane przed renderingiem manifestów.

Klient nie może dostarczać dowolnego PodSpec, volume mounts, securityContext ani NetworkPolicy bez policy review.

## 12. Następne kroki

Przed produkcją trzeba dodać:

- pełny rendering chartu z danych projektu;
- integrację provisioner-service z Helm albo Kubernetes API;
- testy negatywne admission policy w CI;
- osobne egress policies dla registry, object storage i telemetry;
- image signing i admission dla zaufanych obrazów;
- runtime secret injection bez logowania wartości sekretów.
