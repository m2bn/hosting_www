# Provisioner Kubernetes RBAC

## 1. Cel

Provisioner-service potrzebuje uprawnień Kubernetes wyłącznie do tworzenia i utrzymywania zasobów izolacji projektu.

Nie wolno nadawać provisionerowi `cluster-admin`. RBAC musi być ograniczony do minimalnego zestawu zasobów i czasowników wymaganych przez provisioning oraz reconcile.

## 2. Service account

Provisioner powinien działać jako dedykowany service account, np.:

```text
namespace: platform-system
serviceAccount: provisioner-service
```

Ten service account jest używany tylko przez provisioner-service. Nie używają go workloady klientów.

## 3. Wymagane uprawnienia cluster-scope

Provisioner potrzebuje ograniczonego dostępu cluster-scope do namespace, ponieważ tworzy namespace per projekt albo środowisko.

Minimalne uprawnienia:

```text
apiGroup: ""
resource: namespaces
verbs: get, list, watch, create, update, patch, delete
```

Uzasadnienie:

- `create`: utworzenie namespace projektu;
- `get/list/watch`: reconcile i diagnostyka driftu;
- `update/patch`: labels i annotations zarządzane przez provisioner;
- `delete`: deprovision po soft-delete i po okresie retencji.

Provisioner musi przed `update`, `patch` i `delete` sprawdzić labels:

- `managed_by=provisioner`;
- `organization_public_id`;
- `project_public_id`;
- `environment_public_id`.

## 4. Wymagane uprawnienia namespace-scope

W namespace projektu provisioner potrzebuje:

```text
apiGroup: ""
resources:
  - serviceaccounts
  - services
  - resourcequotas
  - limitranges
verbs: get, list, watch, create, update, patch, delete
```

```text
apiGroup: networking.k8s.io
resources:
  - networkpolicies
  - ingresses
verbs: get, list, watch, create, update, patch, delete
```

```text
apiGroup: cert-manager.io
resources:
  - certificates
  - certificaterequests
verbs: get, list, watch, create, update, patch, delete
```

Jeśli używamy Gateway API zamiast Ingress:

```text
apiGroup: gateway.networking.k8s.io
resources:
  - httproutes
verbs: get, list, watch, create, update, patch, delete
```

## 5. Uprawnienia niewymagane i zakazane

Provisioner nie powinien mieć:

- `cluster-admin`;
- `*` na wszystkich zasobach;
- możliwości tworzenia `ClusterRoleBinding`;
- możliwości tworzenia albo modyfikowania `ClusterRole`;
- możliwości modyfikowania admission policies;
- możliwości tworzenia privileged workloadów;
- `pods/exec`;
- `pods/portforward`;
- odczytu `secrets` w namespace klientów;
- dostępu do sekretów platformowych poza własnym namespace;
- możliwości modyfikowania node, kube-system albo control-plane components.

## 6. Kubernetes Secrets

Domyślnie provisioner nie czyta Kubernetes Secrets klientów.

Jeśli runtime injection będzie wymagał tworzenia Kubernetes Secret, należy wydzielić osobny, wąski komponent albo dodać minimalne uprawnienie:

```text
apiGroup: ""
resource: secrets
verbs: get, create, update, patch, delete
```

Warunki:

- tylko w namespace projektu;
- tylko dla sekretów z `managed_by=provisioner`;
- brak `list/watch`, jeśli nie jest wymagane;
- brak logowania wartości sekretów;
- oddzielny threat model dla tej integracji.

## 7. Storage provider

Uprawnienia do storage bucket/prefix nie powinny wynikać z Kubernetes RBAC.

Provisioner powinien używać osobnej tożsamości IAM albo konta technicznego z uprawnieniami ograniczonymi do:

- tworzenia prefixu projektu;
- ustawienia policy/ACL projektu;
- oznaczania prefixu do retencji;
- usuwania prefixu po okresie retencji.

Zakazane:

- dostęp do bucketów innych środowisk;
- globalny admin storage;
- odczyt obiektów klientów, jeśli provisioner potrzebuje tylko zarządzać prefixami.

## 8. Reconcile i delete safety

Przed modyfikacją albo usunięciem zasobu provisioner musi potwierdzić:

- zgodność `managed_by=provisioner`;
- zgodność `organization_public_id`;
- zgodność `project_public_id`;
- zgodność `environment_public_id`;
- zgodność nazwy zasobu z deterministycznym schematem.

Jeśli zasób istnieje, ale labels wskazują innego tenanta, operacja musi zakończyć się błędem terminalnym i alertem bezpieczeństwa.

## 9. Audyt i monitoring RBAC

Wymagane kontrole:

- okresowy audit, czy service account nie ma `cluster-admin`;
- alert na zmianę ClusterRole/ClusterRoleBinding provisionera;
- alert na użycie verbs spoza baseline;
- metryka błędów `Forbidden` z Kubernetes API;
- metryka operacji delete per resource kind;
- logowanie `resource_kind`, `resource_name`, `namespace`, `project_public_id`, `operation`, `request_id`.

Logi nie mogą zawierać:

- kubeconfig;
- bearer tokenów;
- wartości sekretów;
- prywatnych kluczy TLS;
- pełnych manifestów z danymi wrażliwymi.

## 10. Minimalny szkic polityki

Docelowy manifest powinien być przygotowany jako osobny plik deploymentowy, ale baseline logiczny wygląda tak:

```text
ClusterRole provisioner-service:
  namespaces: get/list/watch/create/update/patch/delete

Role provisioner-managed-namespace:
  serviceaccounts: get/list/watch/create/update/patch/delete
  services: get/list/watch/create/update/patch/delete
  resourcequotas: get/list/watch/create/update/patch/delete
  limitranges: get/list/watch/create/update/patch/delete
  networkpolicies: get/list/watch/create/update/patch/delete
  ingresses: get/list/watch/create/update/patch/delete
  certificates/certificaterequests: get/list/watch/create/update/patch/delete
```

Ten szkic nie jest jeszcze pełnym manifestem runtime. Pełne manifesty powinny zostać dodane dopiero po decyzji o docelowym modelu namespace i cert-manager/Gateway API.
