# Provisioner-service

## 1. Cel provisionera

Provisioner-service odpowiada za bezpieczne, idempotentne i audytowalne przygotowanie zasobów infrastrukturalnych potrzebnych do uruchamiania aplikacji klientów.

Provisioner jest wykonawcą decyzji control plane. Nie decyduje samodzielnie o uprawnieniach użytkownika, planie billingowym ani entitlementach. Otrzymuje zlecenie po tym, jak backend zweryfikuje RBAC, multi-tenancy, status subskrypcji i limity.

Główne cele:

- tworzenie i utrzymywanie zasobów Kubernetes per projekt i środowisko;
- wymuszanie izolacji projektów przez namespace, service account, NetworkPolicy, ResourceQuota i LimitRange;
- przygotowanie storage bucket/prefix dla artefaktów, uploadów i danych runtime;
- konfiguracja ingressu, domen i certificate requestów;
- usuwanie albo dezaktywacja zasobów po soft-delete projektu;
- okresowy reconcile stanu deklaratywnego z faktycznym stanem infrastruktury;
- odporność na retry, duplikaty jobów i częściowe awarie.

## 2. Granice odpowiedzialności

Provisioner robi:

- tworzy namespace Kubernetes dla projektu albo środowiska zgodnie z przyjętym modelem izolacji;
- tworzy service account dla workloadów klienta;
- tworzy ResourceQuota i LimitRange wynikające z planu oraz runtime limits;
- tworzy bazowe NetworkPolicy;
- tworzy bucket albo prefix storage dla projektu;
- tworzy ingress dla domen platformowych i własnych;
- tworzy certificate request dla domen wymagających TLS;
- wykonuje reconcile zasobów;
- oznacza status provisioning jobów;
- zapisuje techniczne błędy i metryki operacyjne.

Provisioner nie robi:

- nie autoryzuje użytkowników końcowych;
- nie interpretuje ról RBAC dashboardu;
- nie podejmuje decyzji billingowych;
- nie przyjmuje danych bezpośrednio z frontendu;
- nie buduje obrazów kontenerowych;
- nie przechowuje plaintext sekretów klientów;
- nie udostępnia publicznego API dla klientów.

## 3. Model wywołania

Control plane zapisuje żądanie jako provisioning job. Worker provisionera pobiera job, wykonuje operację i aktualizuje status.

Minimalny model joba:

- `public_id`;
- `organization_id`;
- `project_id`;
- `environment_id` opcjonalnie;
- `domain_id` opcjonalnie;
- `operation`;
- `idempotency_key`;
- `status`;
- `attempt_count`;
- `next_retry_at`;
- `last_error_code`;
- `last_error_message`;
- `started_at`;
- `finished_at`;
- `created_at`;
- `updated_at`.

Statusy:

- `queued`: job oczekuje;
- `running`: job jest wykonywany;
- `succeeded`: operacja zakończona;
- `failed_retryable`: błąd przejściowy, job będzie ponowiony;
- `failed_terminal`: błąd trwały, wymaga interwencji albo zmiany konfiguracji;
- `cancelled`: job anulowany przed wykonaniem;
- `superseded`: job zastąpiony nowszym zleceniem dla tego samego zasobu.

## 4. Przepływ tworzenia projektu

1. Backend tworzy `Project` i domyślne `Environment`.
2. Backend sprawdza entitlementy: limit projektów, status subskrypcji, runtime limits.
3. Backend zapisuje provisioning job `project.provision`.
4. Provisioner pobiera job i tworzy zasoby w kolejności:
   - namespace;
   - labels i annotations identyfikujące organizację, projekt i środowisko;
   - service account;
   - ResourceQuota;
   - LimitRange;
   - bazowe NetworkPolicy;
   - storage bucket/prefix;
   - opcjonalny ingress dla domeny platformowej;
   - opcjonalny certificate request.
5. Provisioner zapisuje status joba `succeeded`.
6. Backend może oznaczyć projekt jako gotowy do deploymentu.

Każdy krok musi być idempotentny. Jeśli namespace istnieje z poprawnymi labelami, krok jest uznany za wykonany. Jeśli istnieje, ale należy do innego projektu lub organizacji, job kończy się błędem terminalnym.

## 5. Przepływ usuwania projektu

Soft-delete projektu w control plane nie oznacza natychmiastowego twardego usunięcia danych.

1. Backend ustawia `Project.deleted_at` i status `deleted` albo `pending_deletion`.
2. Backend zapisuje provisioning job `project.deprovision`.
3. Provisioner:
   - blokuje nowe deploymenty;
   - skaluje workloady do zera albo usuwa workloady runtime;
   - usuwa ingressy i certificate requesty;
   - usuwa albo oznacza do retencji storage prefix;
   - usuwa service account, ResourceQuota, LimitRange i NetworkPolicy;
   - usuwa namespace, jeśli nie zawiera zasobów objętych retencją.
4. Jeśli obowiązuje retencja danych, provisioner oznacza zasoby labelami `deletion-pending` i zapisuje kolejny job cleanup po okresie retencji.

Usuwanie musi być bezpieczne tenantowo: provisioner usuwa wyłącznie zasoby z labelami zgodnymi z `organization_public_id`, `project_public_id` i `environment_public_id`.

## 6. Przepływ dodawania domeny

1. Backend waliduje domenę, ownership projektu i uprawnienia użytkownika.
2. Backend zapisuje `Domain` w statusie `pending_verification`.
3. Po weryfikacji DNS backend zapisuje job `domain.provision`.
4. Provisioner:
   - tworzy albo aktualizuje ingress;
   - tworzy certificate request;
   - wiąże certyfikat z ingress po wystawieniu;
   - zapisuje techniczny status provisioning joba.
5. Control plane aktualizuje status domeny na `active`, gdy certyfikat i ingress są gotowe.

Provisioner nie decyduje, czy domena należy do klienta. To musi być zweryfikowane wcześniej przez control plane.

## 7. Reconcile zasobów

Provisioner działa w dwóch trybach:

- event-driven: wykonuje joby tworzone przez control plane;
- periodic reconcile: okresowo porównuje stan deklaratywny z faktycznym stanem infrastruktury.

Reconcile sprawdza:

- czy namespace istnieje i ma poprawne labels;
- czy ResourceQuota odpowiada aktualnemu planowi;
- czy LimitRange odpowiada runtime limits;
- czy NetworkPolicy jest obecna;
- czy service account istnieje i ma minimalne uprawnienia;
- czy ingress odpowiada aktywnym domenom;
- czy certificate request istnieje dla aktywnych domen;
- czy storage bucket/prefix istnieje;
- czy nie ma zasobów osieroconych albo z cudzym tenant label.

Reconcile nie powinien usuwać zasobów bez polityki bezpieczeństwa. Wykryte zasoby osierocone trafiają do raportu albo osobnego cleanup joba.

## 8. Idempotency keys

Każda operacja musi mieć deterministyczny `idempotency_key`.

Przykłady:

- `project.provision:{project_public_id}:{environment_public_id}`;
- `project.deprovision:{project_public_id}`;
- `domain.provision:{domain_public_id}`;
- `domain.deprovision:{domain_public_id}`;
- `reconcile.project:{project_public_id}:{generation}`;

Ten sam `idempotency_key` nie może utworzyć dwóch niezależnych jobów aktywnych. Jeśli job już istnieje i jest `succeeded`, kolejne wywołanie zwraca jego wynik.

Zasoby Kubernetes również muszą mieć deterministyczne nazwy i labels, np.:

- namespace: `org-<org-slug>-project-<project-slug>-<short-project-id>`;
- service account: `runtime`;
- ResourceQuota: `project-quota`;
- LimitRange: `project-limits`;
- NetworkPolicy: `default-deny`, `allow-ingress`, `allow-dns`;
- ingress: `domain-<domain-short-id>`;
- certificate request: `cert-<domain-short-id>`.

## 9. Model błędów

Błędy dzielimy na przejściowe i terminalne.

Błędy przejściowe:

- timeout Kubernetes API;
- konflikt optimistic locking;
- chwilowy brak dostępności S3/MinIO;
- chwilowy brak dostępności cert-managera;
- limit rate API providera;
- błąd sieciowy.

Błędy terminalne:

- namespace istnieje, ale ma labels innej organizacji;
- brak wymaganego planu albo runtime limits w danych wejściowych joba;
- niepoprawna nazwa domeny;
- domena wskazuje na inny projekt;
- brak wymaganych uprawnień service account provisionera;
- policy admission odrzuca manifest jako niezgodny z baseline security;
- storage bucket ma konflikt ownershipu.

Provisioner nie powinien zapisywać pełnych payloadów z sekretami ani manifestów zawierających dane wrażliwe w `last_error_message`.

## 10. Retry policy

Retry dotyczy tylko błędów przejściowych.

Polityka:

- maksymalnie 8 prób;
- exponential backoff z jitterem;
- bazowe opóźnienie: 10 sekund;
- maksymalne opóźnienie: 30 minut;
- po przekroczeniu limitu job przechodzi w `failed_terminal`;
- retry nie może tworzyć duplikatów zasobów.

Przykład backoffu:

```text
10s, 30s, 90s, 5m, 10m, 20m, 30m, 30m
```

Job może zostać ręcznie ponowiony przez operatora, ale retry operatora tworzy nowy attempt z tym samym `idempotency_key`.

## 11. Wymagane uprawnienia Kubernetes

Provisioner powinien działać na dedykowanym service account z minimalnym RBAC.

Zakres cluster-level:

- create/get/list/watch/update/patch/delete `namespaces`;
- get/list/watch `nodes` tylko jeśli wymagane do diagnostyki, domyślnie nie;
- create/get/list/watch/update/patch/delete `networkpolicies` w namespace projektu;
- create/get/list/watch/update/patch/delete `resourcequotas` w namespace projektu;
- create/get/list/watch/update/patch/delete `limitranges` w namespace projektu;
- create/get/list/watch/update/patch/delete `serviceaccounts` w namespace projektu;
- create/get/list/watch/update/patch/delete `services` i `ingresses` w namespace projektu;
- create/get/list/watch/update/patch/delete certificate resources używane przez cert-manager;
- brak uprawnień do odczytu Kubernetes Secrets z namespace klientów, chyba że osobny proces runtime injection tego wymaga.

Zakazy:

- brak `cluster-admin`;
- brak możliwości tworzenia ClusterRoleBinding dla workloadów klientów;
- brak możliwości patchowania admission policies;
- brak możliwości odczytu sekretów innych namespace;
- brak możliwości exec do podów klientów;
- brak możliwości tworzenia privileged podów.

## 12. Granice zaufania

Granice:

- dashboard/API użytkownika jest poza granicą provisionera;
- control plane jest źródłem deklaratywnego stanu;
- provisioner ufa tylko jobom zapisanym przez backend;
- Kubernetes API jest zewnętrzną granicą wykonawczą;
- storage provider jest zewnętrzną granicą danych;
- cert-manager/ACME jest zewnętrzną granicą certyfikatów;
- registry i runtime workloady klientów są niezaufane.

Provisioner nie ufa:

- danym z frontendu;
- nazwom zasobów przekazanym przez klienta bez normalizacji;
- stanowi istniejących zasobów bez weryfikacji tenant labels;
- workloadom klienta;
- logom z aplikacji klienta.

## 13. Wymagania bezpieczeństwa

- Każdy zasób musi mieć labels: `organization_public_id`, `project_public_id`, `environment_public_id`, `managed_by=provisioner`.
- Provisioner musi sprawdzać labels przed update/delete zasobu.
- NetworkPolicy musi domyślnie blokować ruch przychodzący i wychodzący poza dozwolone cele.
- Egress do metadata services cloud providera musi być blokowany.
- ResourceQuota i LimitRange muszą być tworzone przed deploymentem workloadów.
- Service account runtime nie może mieć uprawnień do Kubernetes API, jeśli aplikacja klienta ich nie potrzebuje.
- Ingress musi wskazywać tylko service z tego samego namespace.
- Certificate request musi być tworzony tylko dla zweryfikowanej domeny.
- Storage bucket/prefix musi być izolowany per projekt i nie może być współdzielony między tenantami bez policy boundary.
- Manifesty muszą przejść przez walidację policy admission.
- Provisioner nie może logować sekretów, tokenów, kubeconfigów ani pełnych payloadów błędów providera.
- Wszystkie operacje mutujące muszą mieć AuditLog albo techniczny event powiązany z provisioning jobem.

## 14. Wymagania logowania

Logi provisionera muszą być strukturalne.

Pola wymagane:

- `request_id` albo `correlation_id`;
- `job_id`;
- `idempotency_key`;
- `operation`;
- `organization_public_id`;
- `project_public_id`;
- `environment_public_id`;
- `resource_kind`;
- `resource_name`;
- `attempt`;
- `status`;
- `duration_ms`;
- `error_code` opcjonalnie.

Zakazane w logach:

- wartości sekretów;
- tokeny API;
- kubeconfig;
- pełne certyfikaty prywatne;
- pełne payloady webhooków;
- dane osobowe niepotrzebne do diagnostyki.

## 15. Wymagania monitoringu

Metryki:

- liczba jobów per status;
- czas wykonania joba per operation;
- liczba retry per operation;
- liczba błędów terminalnych;
- liczba błędów przejściowych;
- liczba reconcile driftów;
- liczba zasobów osieroconych;
- czas utworzenia namespace;
- czas wystawienia certyfikatu;
- czas aktywacji ingressu.

Alerty:

- wzrost `failed_terminal`;
- job `running` dłużej niż próg;
- kolejka jobów rośnie przez określony czas;
- cert request nie kończy się w SLA;
- reconcile wykrywa zasoby z niezgodnymi tenant labels;
- provisioner traci dostęp do Kubernetes API;
- provisioner używa zbyt szerokich uprawnień względem baseline.

Tracing:

- każdy provisioning job powinien być osobnym trace root albo spanem;
- kroki Kubernetes, storage i cert-manager powinny być child spanami;
- trace nie może zawierać sekretów ani pełnych manifestów z danymi wrażliwymi.

## 16. Kryteria gotowości MVP

Provisioner może wejść do MVP, gdy:

- wszystkie operacje są idempotentne;
- retry z backoffem jest testowany;
- namespace, ResourceQuota, LimitRange i NetworkPolicy są tworzone przed deploymentem;
- delete/deprovision sprawdza tenant labels przed usunięciem;
- service account provisionera nie ma `cluster-admin`;
- logi i metryki są dostępne w observability stack;
- istnieją testy integracyjne na happy path i częściowe awarie;
- istnieje runbook ręcznego retry i obsługi `failed_terminal`;
- istnieje test bezpieczeństwa potwierdzający, że projekt A nie może usunąć ani zmodyfikować zasobów projektu B.
