# Final Architecture Review

Data przegladu: 2026-06-13

Zakres: backend Django, dashboard Next.js, worker/provisioner, modele domenowe, ADR-y, dokumentacja security/runbooki, CI/CD, Kubernetes/Helm, Terraform, observability, backup/restore i testy.

## Executive Summary

Architektura jest spojna z kierunkiem z `docs/architecture/vision.md`: repo rozdziela control plane, dashboard, runtime Kubernetes, billing, observability, backup/restore i operacje platformy. Najmocniej zaimplementowane sa: model domenowy, multi-tenancy w backendzie, RBAC, auth, Stripe checkout/webhooki, API keys, static/container deployment MVP, domeny, certyfikaty, metering, audit logi oraz security tests.

Repo nie jest jednak jeszcze gotowe jako production platforma hostingu klientow end-to-end. Najwieksza roznica miedzy wizja a stanem kodu dotyczy wykonawczej warstwy data plane: provisioner, deployment-worker, Terraform i observability sa w duzej mierze bazowymi implementacjami albo kontraktami, z mockami/adapters zamiast pelnej integracji produkcyjnej. To jest akceptowalne dla obecnego etapu, ale wymaga jawnego oznaczenia przed release.

## Zgodnosc z Vision

| Obszar z vision.md | Ocena | Uzasadnienie |
|---|---|---|
| Multi-tenant SaaS | Zgodne | `Organization` jest granica tenantowa; endpointy organizacyjne i projektowe wymagaja organization context. |
| Uzytkownicy, organizacje, projekty | Zgodne | Modele i endpointy istnieja, z testami RBAC i IDOR. |
| Billing subskrypcyjny Stripe | Czesc produkcyjna, czesc MVP | Checkout, webhooki i lokalny billing state istnieja. Brakuje jeszcze pelnego customer portal, reconciliation jobow i operacyjnych procedur korekt. |
| Runtime aplikacji w Kubernetes | Czesc MVP | Sa manifesty, Helm i provisioner-service. Pelne runtime reconciliation i produkcyjne rollouty sa jeszcze bazowe. |
| Izolacja tenantow | Zgodne projektowo, czesciowo wykonawczo | Backend ma konsekwentny tenant filtering. Kubernetes baseline ma namespace, quota, NetworkPolicy i PSA, ale provisioner nie weryfikuje ownershipu istniejacych zasobow przed kazdym update/delete. |
| Domeny wlasne i SSL | Zgodne dla MVP | Domain verification, cert status i integration point cert-manager istnieja. Pelna automatyzacja DNS/providerow pozostaje poza MVP. |
| Audit logs | Zgodne w backendzie, niespojnosc API docs | `AuditLog` jest append-only i uzywany szeroko, ale publiczny endpoint audit logs jest opisany w dokumentacji API, a nie wystepuje w routingu. |
| Monitoring i metering | Czesc MVP | Metering backendowy i konfiguracje observability istnieja. Instrumentacja OpenTelemetry/Prometheus dla wszystkich procesow nie jest jeszcze pelna. |
| OWASP ASVS L2 i droga do L3 | Zgodne projektowo | Security baseline, threat model, security review i testy istnieja. L3 nadal wymaga mocniejszej izolacji, SSO/polityk org i twardszego SDLC. |

## Aktualnosc ADR

| ADR | Status | Ocena |
|---|---|---|
| ADR-0001 Django + DRF | Accepted | Aktualne. Implementacja faktycznie uzywa Django jako control plane. Uwaga: czesc endpointow jest na `django.views.View`, a nie DRF, wiec ADR nalezy interpretowac jako decyzje stosu, nie ze wszystkie endpointy sa ViewSetami DRF. |
| ADR-0002 Next.js + TypeScript | Accepted | Aktualne. `apps/dashboard` jest Next.js + TypeScript. |
| ADR-0003 PostgreSQL | Accepted | Aktualne produkcyjnie. Uwaga: development/test uzywaja SQLite; production settings powinny blokowac przypadkowe SQLite przed go-live. |
| ADR-0004 Kubernetes runtime | Accepted | Aktualne. Manifesty i provisioner potwierdzaja kierunek. |
| ADR-0005 Stripe Billing | Accepted | Aktualne. Checkout i webhooki sa zaimplementowane. |
| ADR-0006 MinIO/S3-compatible storage | Accepted | Aktualne. Static deployments i backup obsluguja lokalny storage/S3. |
| ADR-0007 Celery + RabbitMQ | Accepted | Aktualne kierunkowo. Worker/provisioner maja Celery, ale produkcyjna trwalosc idempotency store wymaga dopracowania. |
| ADR-0008 OTel + Prometheus + Grafana + Loki | Accepted | Aktualne. Istnieja przyklady konfiguracji; pelna instrumentacja aplikacji pozostaje praca przed production. |
| ADR-0009 Namespace per tenant/project | Accepted | Aktualne. Helm/runtime baseline sa zgodne. |
| ADR-0010 Monorepo | Accepted | Aktualne. Repo jest monorepo. Przed production potrzebne CODEOWNERS albo rownowazne reguly review dla obszarow krytycznych. |

## Spojnosc Modelu Domenowego

Model domenowy jest w duzej mierze spojny z implementacja `apps/api/models.py`: encje glownych tenantow, projekty, srodowiska, deploymenty, domeny, certyfikaty, billing, usage, API keys, AuditLog, SecurityEvent, BuildJob, RuntimeInstance i WebhookEvent istnieja.

Zauwazone roznice:

| Obszar | Stan | Ryzyko | Rekomendacja |
|---|---|---|---|
| Role MVP | Dokumenty historycznie wymieniaja czasem `owner/admin/developer/viewer`, a implementacja ma tez `billing`. | Niskie | Ujednolicic wszystkie dokumenty, aby `billing` bylo jawnie rola bazowa MVP. |
| Statusy deploymentu | `domain-model.md` uzywa `running`, `deployment-pipeline.md` uzywa `active`, model Django ma `running`, worker ma `active`. | Srednie | Ustalic jeden kanoniczny model statusow i zmapowac statusy BuildJob/Deployment/RuntimeInstance. |
| Certificate status | Model zostal zmigrowany do statusow zgodnych z cert-manager MVP, ale starsze fragmenty dokumentacji uzywaja `issued/renewing/revoked`. | Niskie | Uaktualnic `domain-model.md` albo dodac tabele mapowania statusow historycznych. |
| AuditLog API | Dokumentacja API opisuje endpoint audit logs, ale routing go nie zawiera. | Niskie | Zaimplementowac endpoint albo oznaczyc go jako planned/not enabled. |
| Eventy domenowe | Dokumentacja zaklada event/outbox pattern, ale implementacja zapisuje bezposrednio AuditLog i statusy. | Srednie | Przed produkcja zdecydowac, czy MVP akceptuje brak outboxa, czy dodajemy transactional outbox dla billing/provisioning/deployment. |

## Multi-Tenancy

Multi-tenancy w backendzie jest konsekwentne na poziomie glownego API:

- zasoby projektowe sa pobierane przez organization context;
- helpery typu `get_user_organization_or_404`, `get_project_for_organization_or_404` i filtry po `organization` sa uzywane w endpointach krytycznych;
- testy security obejmuja IDOR, cross-tenant access, API key scope bypass i unauthorized organization access;
- API key ma organization/project binding i scopes.

Ryzyko pozostaje w warstwie operatorskiej i infrastrukturalnej:

- operator endpoints uzywaja globalnego lookupu po `public_id`, co jest poprawne dla operatora, ale wymaga mocnego audytu, 2FA i powodu;
- provisioner bazowo usuwa namespace przez nazwe wynikajaca z payloadu i nie odczytuje istniejacych labels przed kazdym delete;
- object storage i runtime musza miec provider-level policies, nie tylko prefix konwencje.

## Provisioning

Provisioner jest idempotentny na poziomie kontraktu taskow i nazw zasobow:

- taski generuja idempotency key;
- create ignoruje konflikt `409`;
- delete ignoruje `404`;
- retry ma exponential backoff;
- zasoby maja deterministyczne nazwy i labels.

Nie jest jeszcze produkcyjnie kompletny:

- idempotency store jest `InMemoryIdempotencyStore`, opisany jako dev/test;
- create/update nie weryfikuje, czy istniejacy namespace/resource z konfliktem ma zgodne tenant labels;
- delete namespace nie sprawdza labels przed usunieciem;
- storage prefix jest zwracany jako string, ale nie ma realnej integracji z bucket policy/lifecycle;
- reconcile jest aliasem `provision_project`, bez wykrywania driftu i osieroconych zasobow.

## Billing i Entitlements

Billing poprawnie steruje kluczowymi entitlementami:

- centralny modul `apps/api/entitlements.py` decyduje o tworzeniu projektow, domenach, deploymentach, limitach storage/transfer/runtime;
- statusy `canceled/cancelled`, `unpaid` i `incomplete` blokuja nowe zasoby;
- `past_due` ma grace period;
- Stripe webhooki sa weryfikowane podpisem, idempotentne i aktualizuja lokalny `Subscription`/`Invoice`;
- checkout wybiera `stripe_price_id` z lokalnego `Plan`, a nie z frontendu.

Ryzyka przed production:

- brak cyklicznego reconciliation ze Stripe API po awariach webhookow;
- brak customer portal/self-service cancel/update poza Checkout;
- brak twardego modelu korekt usage/billing;
- brak jednoznacznej polityki dla organizacji bez subskrypcji poza ustawieniem `ENTITLEMENTS_NO_SUBSCRIPTION_POLICY`.

## Deployment Pipeline

Pipeline jest bezpiecznie zaprojektowany i ma testy interfejsow:

- static ZIP ma walidacje rozmiaru, zip slip, symlinkow, manifestu i storage prefix;
- container deployment respektuje `.dockerignore`, limit contextu, wymaga Dockerfile, mockuje build/push/scan/runtime;
- skanowanie artefaktow i obrazow blokuje critical findings;
- RBAC blokuje viewer/billing dla deploymentow;
- deployment logs nie sa publicznym URL.

Nie jest jeszcze pelnym produkcyjnym build systemem:

- `DockerfileBuildStrategy.build()` zwraca syntetyczny `image_digest`, zamiast faktycznego buildkit/registry flow;
- deployment-worker korzysta z adapterow/memory repository w warstwie bazowej;
- skanery sa polityka/mockiem, nie pelna integracja z realnym scannerem;
- brak podpisywania obrazow i admission enforcement po digest/signature;
- runtime deploy step zwraca spec, ale nie robi pelnego rollout wait/reconcile z Kubernetes.

## Kubernetes Runtime

Runtime jest dobrze odseparowany w manifestach:

- namespace per project/environment;
- Pod Security Restricted;
- default deny ingress i egress;
- dopuszczony DNS egress;
- ResourceQuota i LimitRange;
- `runAsNonRoot`, `allowPrivilegeEscalation=false`, `readOnlyRootFilesystem`, `seccompProfile RuntimeDefault`;
- brak `hostPath`, `hostNetwork`, `hostPID`, `privileged`;
- Kyverno blokuje kluczowe niebezpieczne konfiguracje.

Do dopracowania:

- obraz baseline uzywa przykladowego taga `latest`; produkcja powinna uzywac immutable digest;
- NetworkPolicy nie pokazuje jeszcze pelnych allowlist dla ingress controller, registry, scannerow i wymaganych egressow aplikacji;
- Helm chart jest bazowy i wymaga integracji z realnym provisionerem oraz External Secrets;
- potrzebne testy na realnym klastrze staging, nie tylko statyczna walidacja manifestow.

## Observability

Observability obejmuje kluczowe procesy na poziomie projektu:

- request/correlation ID;
- structured logs;
- dokumentowany OpenTelemetry tracing dla API, Celery, Stripe, deploymentow i provisioningu;
- Prometheus/Grafana/Loki/Otel collector przyklady;
- alerty dla API error rate, kolejki buildow, Stripe webhookow, certyfikatow, storage, DB latency i deployment failures.

Luki przed production:

- konfiguracje sa przykladowe i wymagaja produkcyjnego storage, auth, retention i deploymentu przez Helm/Kustomize;
- nie wszystkie procesy eksportuja jeszcze realne metryki wymienione w `docs/architecture/observability.md`;
- brak potwierdzonej propagacji trace context przez wszystkie taski Celery i worker/provisioner;
- brak runbooku SLO/error budget dla API, dashboardu, deploymentow i runtime traffic.

## Backup i Restore

Backup/restore jest kompletny jako bazowa procedura MVP:

- PostgreSQL przez `pg_dump` albo fallback `dumpdata`;
- metadane S3/MinIO;
- pliki deploymentow;
- konfiguracja platformy z allowlisty;
- fingerprinty sekretow, bez plaintext;
- szyfrowanie Fernet/passphrase;
- retencja;
- restore tylko do staging/recovery z blokada production;
- test restore i bezpieczna ekstrakcja tar.

Ryzyka:

- restore nadal jest glownie rozpakowaniem i walidacja manifestu; odtworzenie DB, bucketow i sekretow jest opisane proceduralnie, nie w pelni zautomatyzowane;
- backup object storage moze byc kosztowny i wymaga provider-level lifecycle/immutability;
- brak job scheduling/alertow backupu w IaC;
- brak okresowego restore drill jako automatycznego pipeline.

## Dokumentacja i Niespojnosci Kod/Dokumentacja

Dokumentacja jest szeroka i aktualna kierunkowo, ale wymaga porzadkowania przed production:

| Niespojnosc | Lokalizacja | Priorytet | Rekomendacja |
|---|---|---|---|
| Audit logs endpoint opisany w API docs, brak routingu. | `docs/developer/api-documentation.md`, `apps/api/openapi.py`, `apps/api/urls.py` | Medium | Dodac endpoint albo oznaczyc jako planned. |
| Statusy deploymentu `running` vs `active`. | `docs/architecture/domain-model.md`, `docs/architecture/deployment-pipeline.md`, `apps/api/models.py`, `apps/deployment-worker/deployment_worker/statuses.py` | Medium | Ustalic kanon i migration/API mapping. |
| Production readiness checklist ma statusy `not_started`, mimo wielu gotowych elementow. | `docs/runbooks/production-readiness-checklist.md` | Low | Uaktualnic statusy po tym przegladzie. |
| Terraform opisuje pelna infrastrukture, ale implementacja jest provider-agnostic scaffold. | `infra/terraform`, `docs/runbooks/infrastructure.md` | Medium | Oznaczyc jako scaffold i wybrac providera przed production. |
| Observability docs wymienia pelne trace/metrics, ale implementacja ma przyklady konfiguracji. | `docs/architecture/observability.md`, `infra/observability` | Medium | Rozdzielic "required signals" od "currently implemented". |
| Provisioner docs wymagaja label validation przed update/delete, kod jeszcze tego nie robi. | `docs/architecture/provisioner.md`, `apps/provisioner-service/provisioner_service/k8s.py` | High | Dodac odczyt i walidacje labels przed mutate/delete. |

## Rzeczy Gotowe

- Wizja architektury, threat model, security baseline, ADR-y i domain model.
- Backend control plane z modelami domenowymi i migracjami.
- RBAC dla `owner`, `admin`, `developer`, `billing`, `viewer`.
- Tenant-scoped API dla organizacji, projektow, domen, deploymentow, secrets, usage, API keys i billing checkout.
- Auth oparty o bezpieczne sesje cookie, CSRF i 2FA dla operatorow/adminow/ownerow zgodnie z obecnym zakresem.
- Stripe Checkout i webhook processing z idempotencja.
- Centralne entitlements.
- AuditLog append-only na poziomie aplikacji.
- API keys z hashowaniem, prefixem, scopes, expiration, revoke/rotate.
- Secrets management z szyfrowaniem i brakiem zwracania plaintext.
- Static deployment ZIP z walidacjami bezpieczenstwa.
- Bazowy container deployment flow z Dockerfile, `.dockerignore`, scanning policy i rollbackiem.
- Custom domains z TXT verification i ochrona przed domain takeover.
- Certificate lifecycle i runbook failure.
- Metering i usage access control.
- Backup/restore MVP.
- Kubernetes runtime baseline, Helm charts i Kyverno policies.
- CI z lint/test/security/dependency/secret/SAST/SBOM/Kubernetes checks.
- Security tests katalogowe i load testing plan.
- Dokumentacja user/developer/API/runbooki.

## Rzeczy Ryzykowne

- Provisioner ma in-memory idempotency store i nie weryfikuje tenant labels przed delete/update istniejacych zasobow.
- Deployment-worker i container build sa nadal bazowe/mockowane, bez realnego buildkit/registry/signing/admission flow.
- Terraform jest scaffoldem bez wybranego providera i bez realnych zasobow produkcyjnych.
- Observability ma przyklady konfiguracji, ale nie pelna instrumentacje wszystkich procesow.
- Statusy deploymentu nie sa jednolite miedzy dokumentami, modelem i workerem.
- Audit logs sa opisane jako API surface, ale endpoint nie istnieje.
- Production settings i runtime infrastruktura wymagaja finalnego hardeningu po wyborze chmury.
- Backup restore production jest proceduralny, nie w pelni zautomatyzowany ani regularnie drillowany.

## Rzeczy Wymagajace Poprawy Przed Production

1. Zaimplementowac produkcyjny idempotency store dla provisionera, np. PostgreSQL/Redis z lockami i TTL.
2. Dodac label ownership validation w provisionerze przed update/delete namespace, ingress, certificate i innych zasobow.
3. Zastapic mock/synthetic container build realnym izolowanym builderem, registry push, scan po digest i rollout wait.
4. Wymusic immutable image digest i opcjonalnie podpis/attestation w runtime.
5. Ujednolicic statusy `Deployment`/`BuildJob`/`RuntimeInstance` w dokumentacji, API i workerze.
6. Zaimplementowac albo usunac z dokumentacji endpoint audit logs.
7. Wybrac cloud provider i zastapic Terraform `terraform_data` realnymi modulami.
8. Dodac realne OpenTelemetry/Prometheus exporters do API, Celery, workerow i provisionera.
9. Dodac Stripe reconciliation job i runbook korekt billingowych.
10. Zautomatyzowac backup schedule, monitoring backupow i okresowy restore drill.
11. Ustawic CODEOWNERS/reguly review dla `apps/api`, `infra`, `.github`, `docs/security` i `docs/architecture/adr`.
12. Uruchomic testy e2e i smoke tests na staging z prawdziwymi zaleznosciami: PostgreSQL, RabbitMQ, object storage, Kubernetes, Stripe test mode.
13. Uaktualnic production readiness checklist na podstawie faktycznych dowodow.

## Rzeczy Do Zrobienia Po Pierwszym Release

- Niestandardowe role RBAC i uprawnienia per projekt.
- SSO/SAML/OIDC i polityki bezpieczenstwa per organizacja.
- Dedykowane node poole albo klastry dla tenantow wysokiego ryzyka.
- Zaawansowany WAF, DDoS protection i abuse automation per domena.
- Pelny usage-based billing i budzety kosztowe.
- Data residency i retencja per organizacja.
- Git-based deployments i preview environments.
- Podpisywanie obrazow i policy admission wymagajace attestations.
- Self-service export logow, metryk i audit trail.
- Formalny ASVS Level 3 gap assessment.
- Regularne pentesty, threat-model refresh i chaos/DR exercises.

## Konkluzja

Architektura jest dobrze ustawiona i zgodna z zalozeniami produktu oraz security baseline. Repo jest mocne jako secure MVP control plane z rozbudowana dokumentacja i testami. Przed production najwazniejsza praca nie polega na dodawaniu kolejnych funkcji biznesowych, tylko na domknieciu wykonawczej warstwy runtime: trwaly provisioner, realny build/deploy pipeline, produkcyjna infrastruktura, observability i restore drills.
