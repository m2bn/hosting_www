# Deployment pipeline i deployment-worker

## 1. Cel

Deployment-worker odpowiada za bezpieczne przeprowadzenie aplikacji klienta od źródła albo artefaktu do aktywnego runtime.

Pipeline obsługuje dwa typy deploymentu:

1. `static_site`: statyczna strona budowana do artefaktu plikowego i publikowana przez runtime statyczny albo storage/CDN.
2. `container_app`: aplikacja uruchamiana jako obraz kontenerowy w Kubernetes.

Deployment-worker wykonuje operacje asynchroniczne po tym, jak control plane zweryfikuje:

- RBAC albo API key scope;
- organization/project/environment ownership;
- status organizacji i projektu;
- status subskrypcji;
- entitlementy;
- limity planu;
- polityki bezpieczeństwa.

## 2. Komponenty

### Control plane

Control plane przyjmuje żądanie deploymentu, waliduje dostęp i zapisuje `BuildJob` oraz `Deployment`.

Nie wykonuje niezaufanego kodu klienta.

### Deployment-worker

Deployment-worker:

- pobiera `BuildJob`;
- uruchamia build w izolowanym środowisku;
- zapisuje logi builda;
- tworzy SBOM;
- uruchamia skanowanie zależności;
- uruchamia skanowanie obrazu albo artefaktu;
- publikuje artefakt;
- aktualizuje `Deployment`;
- zleca provisionerowi aktualizację runtime;
- monitoruje rollout;
- aktualizuje `RuntimeInstance`.

### Provisioner-service

Provisioner-service tworzy i uzgadnia zasoby Kubernetes, ingress, certyfikaty i storage. Deployment-worker nie powinien samodzielnie tworzyć namespace, ResourceQuota ani NetworkPolicy poza wywołaniem provisionera.

### Registry i artifact storage

Registry przechowuje obrazy kontenerowe.

Artifact storage przechowuje:

- build logs;
- static site bundles;
- SBOM;
- scan reports;
- deployment metadata.

## 3. Modele domenowe

### BuildJob

`BuildJob` reprezentuje proces przygotowania artefaktu deploymentu.

Kluczowe pola:

- `organization_id`;
- `project_id`;
- `environment_id`;
- `requested_by_user_id`;
- `source_type`: `upload`, `git`, `registry`;
- `source_ref`: zredagowana referencja źródła;
- `status`;
- `image_ref`;
- `sbom_ref`;
- `logs_ref`;
- `started_at`;
- `finished_at`.

Build job wykonuje niezaufany kod i musi działać poza control plane.

### Deployment

`Deployment` reprezentuje próbę wdrożenia konkretnej wersji do środowiska.

Kluczowe pola:

- `organization_id`;
- `project_id`;
- `environment_id`;
- `build_job_id`;
- `version`;
- `image_ref` albo `artifact_ref`;
- `status`;
- `requested_by_user_id`;
- `started_at`;
- `finished_at`;
- metadata deploymentu.

Po rozpoczęciu deploymentu artefakt i wersja są immutable.

### RuntimeInstance

`RuntimeInstance` reprezentuje zmaterializowany stan runtime.

Kluczowe pola:

- `organization_id`;
- `project_id`;
- `environment_id`;
- `deployment_id`;
- `kubernetes_namespace`;
- `workload_name`;
- `status`;
- `replica_count`;
- `last_observed_at`.

`RuntimeInstance` nie jest źródłem prawdy dla konfiguracji; jest widokiem obserwowanego stanu.

## 4. Statusy pipeline

Wspólny model statusów deploymentu:

- `queued`: deployment lub build oczekuje;
- `building`: trwa budowa static bundle albo obrazu;
- `scanning`: trwa skan zależności, SBOM albo obrazu;
- `deploying`: artifact jest wdrażany do runtime;
- `active`: nowa wersja obsługuje ruch;
- `failed`: build, scan albo rollout zakończył się błędem;
- `rolled_back`: deployment został wycofany do poprzedniej aktywnej wersji.

Mapowanie na obecne modele może być przejściowo realizowane przez status `BuildJob` i `Deployment`, ale docelowo `Deployment.status` powinien odzwierciedlać powyższy stan.

Dozwolone przejścia:

```text
queued -> building -> scanning -> deploying -> active
queued -> deploying -> active
building -> failed
scanning -> failed
deploying -> failed
active -> rolled_back
failed -> queued
```

Przejście `failed -> queued` jest ręcznym retry albo automatycznym retry tylko dla błędów przejściowych.

## 5. Static site deployment

Przepływ:

1. Control plane tworzy `BuildJob` i `Deployment` ze statusem `queued`.
2. Worker pobiera źródło: upload albo repozytorium.
3. Worker uruchamia build w izolowanym środowisku.
4. Worker zapisuje build logs do artifact storage.
5. Worker waliduje output directory.
6. Worker sprawdza limit rozmiaru artefaktu.
7. Worker tworzy SBOM zależności, jeśli używany jest package manager.
8. Worker uruchamia dependency scanning.
9. Worker publikuje static bundle do storage prefix projektu.
10. Worker zleca provisionerowi aktualizację ingress/routingu.
11. Po potwierdzeniu gotowości routing przechodzi na nową wersję.
12. `Deployment.status` przechodzi na `active`.

Artefakty:

- `artifact_ref`: referencja do static bundle;
- `logs_ref`: logi builda;
- `sbom_ref`;
- `scan_report_ref`;
- `checksum`;
- `size_bytes`.

## 6. Container app deployment

Przepływ:

1. Control plane tworzy `BuildJob` i `Deployment` ze statusem `queued`.
2. Worker pobiera źródło: upload, git albo gotowy obraz z registry.
3. Jeśli źródłem nie jest gotowy obraz, worker buduje obraz w izolowanym builderze.
4. Worker taguje obraz deterministycznym tagiem.
5. Worker generuje SBOM.
6. Worker skanuje zależności.
7. Worker skanuje obraz kontenerowy.
8. Worker podpisuje obraz albo zapisuje attestation.
9. Worker pushuje obraz do registry.
10. Worker zleca provisionerowi rollout w namespace projektu.
11. Worker obserwuje readiness rollout.
12. `RuntimeInstance` zostaje zaktualizowany.
13. `Deployment.status` przechodzi na `active`.

Artefakty:

- `image_ref`;
- immutable digest obrazu;
- podpis albo attestation;
- `sbom_ref`;
- `scan_report_ref`;
- `logs_ref`;
- runtime metadata.

## 7. Logi builda

Build logs są zapisywane poza bazą danych, np. w object storage.

Wymagania:

- logi są strumieniowane w trakcie builda;
- logi są przypisane do `organization_id`, `project_id`, `build_job_id`;
- dostęp do logów wymaga `logs.read`;
- logi nie mogą zawierać sekretów platformy;
- logi powinny przechodzić przez redakcję znanych wzorców sekretów;
- retencja logów jest konfigurowalna per plan albo globalnie;
- `logs_ref` nie może być publicznym URL bez autoryzacji.

Build job nie dostaje sekretów control plane. Jeśli aplikacja klienta potrzebuje build-time secrets, muszą być one oddzielnym mechanizmem z jawnym allowlist, szyfrowaniem i redakcją logów.

## 8. Limity czasu builda

Limity muszą być wymuszane przez scheduler/build runtime, nie tylko przez aplikację.

Baseline:

- static site: 10 minut;
- container app: 20 minut;
- dependency scan: 5 minut;
- image scan: 10 minut;
- rollout wait: 10 minut.

Przekroczenie limitu czasu kończy job statusem `failed` z kodem `timeout`.

Timeouty powinny być zależne od planu, ale nie mogą być dowolnie zwiększane przez request użytkownika.

## 9. Limity rozmiaru artefaktów

Baseline:

- upload source archive: 250 MB;
- static site bundle: 500 MB;
- pojedynczy plik static site: 50 MB;
- container image compressed size: 2 GB;
- build logs: 100 MB na job;
- SBOM/scan report: 50 MB.

Przekroczenie limitu:

- zatrzymuje build;
- zapisuje zredagowany błąd;
- nie publikuje artefaktu;
- zapisuje audit/security event, jeśli wygląda jak abuse.

## 10. Skanowanie zależności

Dependency scanning dotyczy:

- package lock files;
- manifestów zależności;
- vendored dependencies, jeśli obecne;
- base image dependencies dla container app.

Wyniki:

- `scan_report_ref`;
- severity summary;
- policy decision: `pass`, `warn`, `block`.

MVP:

- blokuj `critical` exploitable vulnerabilities;
- ostrzegaj dla `high`;
- pozwól operatorowi zarejestrować wyjątek z datą wygaśnięcia.

## 11. Skanowanie obrazów

Image scanning uruchamiane jest przed rolloutem.

Wymagania:

- skan po digest, nie po mutable tag;
- scan report przypisany do `image_ref` i digestu;
- wynik skanu zapisany jako metadata deploymentu;
- polityka blokuje obrazy z krytycznymi podatnościami, malware albo niedozwolonym base image;
- obraz bez skanu nie może przejść do `deploying`, chyba że istnieje jawny break-glass operatora.

## 12. Podpisywanie i tagowanie obrazów

Tagowanie:

- tag mutable typu `latest` nie może być źródłem prawdy deploymentu;
- każdy obraz otrzymuje immutable tag, np. `project_slug:deployment_public_id`;
- `Deployment.image_ref` powinien zawierać digest.

Podpisywanie:

- docelowo używamy podpisów obrazów albo attestations;
- podpis obejmuje digest, SBOM i metadata builda;
- admission policy może wymagać podpisu przed uruchomieniem w runtime.

## 13. Metadata deploymentu

Deployment metadata powinno zawierać:

- `deployment_public_id`;
- `build_job_public_id`;
- `source_type`;
- zredagowane `source_ref`;
- commit SHA albo artifact checksum;
- image digest;
- SBOM reference;
- scan report reference;
- builder version;
- runtime template version;
- provisioner job id;
- requested by user/API key;
- timestamps przejść statusów;
- rollback target, jeśli dotyczy.

Metadata nie może zawierać:

- sekretów;
- tokenów dostępowych;
- pełnych credentials registry;
- prywatnych URL z podpisem długiego życia.

## 14. Rollback

Rollback przywraca poprzedni aktywny deployment w tym samym środowisku.

Warunki:

- poprzedni artefakt lub obraz nadal istnieje;
- poprzedni deployment przeszedł scan policy;
- organizacja i projekt są aktywne;
- użytkownik ma `deployment.write`;
- rollback jest audytowany.

Przepływ:

1. Control plane wybiera poprzedni `active` deployment jako rollback target.
2. Tworzy nowy deployment typu rollback albo oznacza istniejący jako target.
3. Worker zleca provisionerowi rollout poprzedniego obrazu/artefaktu.
4. Po readiness nowy stan przechodzi na `active`.
5. Deployment wycofany otrzymuje status `rolled_back`.

Rollback nie uruchamia ponownego builda, ale może wymagać ponownego sprawdzenia, czy artefakt nadal spełnia aktualną politykę bezpieczeństwa.

## 15. Separacja build environment od control plane

Build environment jest niezaufany.

Wymagania:

- buildy działają poza procesami Django/API;
- builder działa w osobnym namespace albo dedykowanym klastrze;
- brak dostępu do bazy control plane;
- brak dostępu do sekretów control plane;
- brak dostępu do RabbitMQ credentials innych niż minimalne pobranie joba i zapis statusu przez kontrolowany kanał;
- brak możliwości wywołania Kubernetes API runtime poza ograniczonym adapterem;
- egress buildera jest ograniczony;
- workspace builda jest jednorazowy;
- cache builda jest izolowany per tenant albo bezpiecznie namespaced.

Build job może dostać tylko:

- zredagowaną referencję źródła;
- jednorazowe scoped credentials do pobrania źródła, jeśli konieczne;
- limity zasobów;
- identyfikatory tenant/project/deployment;
- endpoint do przesyłania logów/statusu o ograniczonym zakresie.

## 16. Retry

Retry jest idempotentny i zależny od typu błędu.

Retry automatyczny:

- chwilowy błąd registry;
- chwilowy błąd storage;
- chwilowy błąd Kubernetes/provisioner;
- timeout sieciowy;
- konflikt optimistic locking.

Brak retry automatycznego:

- błąd kompilacji aplikacji;
- brak zależności w projekcie klienta;
- przekroczony limit artefaktu;
- critical vulnerability;
- niepoprawny Dockerfile;
- policy violation;
- brak uprawnień.

Polityka:

- maksymalnie 3 próby builda dla błędów infrastruktury;
- maksymalnie 5 prób rollout/provisioner;
- exponential backoff z jitterem;
- retry zachowuje ten sam `deployment_id` i idempotency key;
- każde podejście ma osobne logs segment albo attempt number.

## 17. Model błędów

Kategorie:

- `validation_error`: błędny request albo konfiguracja projektu;
- `authorization_error`: brak uprawnień;
- `entitlement_error`: plan/subskrypcja nie pozwala;
- `source_fetch_error`: nie można pobrać źródła;
- `build_error`: build aplikacji nie przeszedł;
- `artifact_limit_exceeded`;
- `dependency_scan_failed`;
- `image_scan_failed`;
- `policy_blocked`;
- `registry_error`;
- `storage_error`;
- `provisioner_error`;
- `rollout_timeout`;
- `internal_error`.

Błąd widoczny dla użytkownika musi być zredagowany. Szczegóły techniczne trafiają do logów strukturalnych bez sekretów.

## 18. Wymagania bezpieczeństwa

- Build environment nie ma sekretów control plane.
- Build environment nie ma uprawnień `cluster-admin`.
- Build job nie może montować hostPath.
- Build job działa jako non-root, jeśli technologia buildera na to pozwala.
- Builder ma limity CPU/RAM/storage.
- Egress buildera jest ograniczony do źródeł, registry, storage i skanerów.
- Obrazy są skanowane przed deploymentem.
- Artefakty mają checksum.
- Obrazy są referencjonowane po digest.
- Logs i metadata są redagowane.
- SBOM jest tworzony dla każdej wersji produkcyjnej.
- Runtime admission policy blokuje niebezpieczne PodSpec.
- Deployment worker waliduje tenant context przy każdym status update.
- API key nie może wdrażać poza swoim scope.

## 19. Wymagania audytu

AuditLog:

- `deployment.requested`;
- `build_job.started`;
- `build_job.succeeded`;
- `build_job.failed`;
- `deployment.started`;
- `deployment.active`;
- `deployment.failed`;
- `deployment.rolled_back`;
- `deployment.cancelled`;
- `scan.blocked`;
- `break_glass.deployment_allowed`, jeśli operator dopuści wyjątek.

Każdy wpis powinien zawierać:

- actor type: user, API key, system, operator;
- organization/project/environment;
- deployment id;
- build job id;
- source type;
- artifact/image digest;
- result;
- request id/correlation id.

AuditLog nie może zawierać:

- sekretów;
- pełnych tokenów;
- raw build logs;
- pełnego payloadu skanera;
- signed URLs o długim TTL.

## 20. Wymagania monitoringu

Metryki:

- liczba deploymentów per status;
- czas builda per typ deploymentu;
- czas skanowania;
- czas rollout;
- failure rate per category;
- retry count;
- queue age;
- artifact size;
- image size;
- vulnerability counts per severity;
- rollback count;
- active runtime replicas;
- rollout timeout count.

Logi:

- strukturalne;
- z `request_id`, `correlation_id`, `organization_public_id`, `project_public_id`, `deployment_public_id`, `build_job_public_id`;
- bez sekretów;
- z kodem błędu, a nie pełnym exception payloadem z danymi klienta.

Alerty:

- kolejka deploymentów rośnie przez określony czas;
- wzrost `failed` dla buildów lub rolloutów;
- skaner obrazów niedostępny;
- registry niedostępne;
- storage artifactów niedostępny;
- build jobs przekraczają timeout;
- deploymenty wiszą w `deploying`;
- krytyczne podatności blokują wielu tenantów;
- rollback rate przekracza próg.

Tracing:

- trace root: deployment request;
- child spans: source fetch, build, dependency scan, image scan, push artifact, provisioner call, rollout wait;
- trace attributes bez sekretów.

## 21. Kryteria gotowości MVP

Deployment-worker jest gotowy do MVP, gdy:

- static site i container app mają osobne ścieżki testowe;
- build działa poza control plane;
- build job nie ma dostępu do sekretów control plane;
- logi builda są strumieniowane i redagowane;
- limity czasu i rozmiaru artefaktu są wymuszane;
- skan zależności i obrazów blokuje critical vulnerabilities;
- rollout używa provisionera i runtime security baseline;
- retry jest idempotentny;
- rollback działa dla ostatniej aktywnej wersji;
- metadata deploymentu zapisuje digest/checksum i scan refs;
- AuditLog pokrywa request, start, success/failure i rollback;
- monitoring ma metryki kolejki, czasu builda, skanowania i rolloutów.
