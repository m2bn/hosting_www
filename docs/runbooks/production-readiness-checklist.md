# Production Readiness Checklist

Ta checklista służy do decyzji go-live dla środowiska production. Każdy punkt musi mieć właściciela, status, dowód weryfikacji i datę ostatniego sprawdzenia.

## Statusy

- `not_started`: prace nie rozpoczęte.
- `in_progress`: prace trwają.
- `blocked`: punkt zablokowany.
- `ready`: gotowe i zweryfikowane.
- `accepted_risk`: świadomie zaakceptowane ryzyko z opisem i właścicielem.

## Checklist

| Obszar | Wymaganie | Status | Osoba odpowiedzialna | Dowód/weryfikacja | Data sprawdzenia |
|---|---|---|---|---|---|
| Security | OWASP ASVS Level 2 baseline jest spełniony dla zakresu MVP. | not_started | TBD | Wynik przeglądu `docs/security/security-baseline.md`, testy security w CI. | TBD |
| Security | Wszystkie endpointy tenantowe filtrują dane po organizacji i mają testy IDOR. | not_started | TBD | Wynik `python manage.py test tests.security apps.api.tests_authorization apps.api.tests_artifact_scanning`. | TBD |
| Security | CSRF działa dla endpointów sesyjnych i modyfikujących dane. | not_started | TBD | Testy CSRF, review konfiguracji cookies i dashboard API client. | TBD |
| Security | Security headers, CSP, HSTS, cookie flags i CORS są skonfigurowane dla production. | not_started | TBD | `python manage.py check --deploy`, testy secure configuration, przegląd nagłówków na staging. | TBD |
| Rate limiting | Rate limiting działa dla logowania, API keys i wysyłki e-maili. | not_started | TBD | Testy brute force/rate limit, metryki 429 na staging. | TBD |
| Operator access | Dostęp operatora wymaga roli operatora, 2FA i audytu akcji wysokiego ryzyka. | not_started | TBD | Testy operator console, przegląd AuditLog dla akcji operatora. | TBD |
| Secret rotation | Istnieje procedura rotacji `DJANGO_SECRET_KEY`, kluczy szyfrowania, Stripe, S3/MinIO i API keys. | not_started | TBD | Runbook rotacji, test rotacji w staging, lista sekretów w secret managerze. | TBD |
| Dependency scanning | Dependency scanning blokuje podatności krytyczne. | not_started | TBD | Wynik CI `dependency scanning`, `pip-audit`, npm audit/SCA. | TBD |
| Artifact scanning | Static ZIP, zależności i obrazy kontenerowe są skanowane przed deploymentem. | not_started | TBD | Testy `apps.api.tests_artifact_scanning`, konfiguracja scannerów, wyniki w panelu projektu. | TBD |
| Penetration testing | Wykonano test penetracyjny MVP albo formalny security review przed go-live. | not_started | TBD | Raport pentest/security review, lista zaakceptowanych ryzyk. | TBD |
| Billing | Stripe test mode jest zweryfikowany na staging, production używa wyłącznie live keys z secret managera. | not_started | TBD | Test checkout, test webhooków, kontrola konfiguracji `STRIPE_TEST_MODE`. | TBD |
| Billing | Webhooki Stripe mają weryfikację podpisu, idempotencję i alerty błędów. | not_started | TBD | Testy webhooków, dashboard błędów, alert `StripeWebhookFailures`. | TBD |
| Billing | Plany, limity i entitlements są zgodne z ofertą handlową. | not_started | TBD | Przegląd `docs/architecture/entitlements.md`, testy planów Free/Pro/Business. | TBD |
| Billing | Faktury i historia płatności są dostępne dla ról owner/billing. | not_started | TBD | Test dashboardu billingowego, test RBAC. | TBD |
| Backup | Backup PostgreSQL jest skonfigurowany, szyfrowany i objęty retencją. | not_started | TBD | Wynik skryptu backupu, lokalizacja backupu, metadane szyfrowania, retencja. | TBD |
| Backup | Backup storage deploymentów i metadanych S3/MinIO jest skonfigurowany. | not_started | TBD | Run backup storage, lista obiektów testowych, raport backupu. | TBD |
| Backup | Backup sekretów/kluczy jest wykonywany w bezpiecznej formie bez plaintext w logach. | not_started | TBD | Przegląd logów backupu, fingerprinty sekretów, polityka least privilege. | TBD |
| Restore | Restore do staging został przetestowany z ostatniego backupu. | not_started | TBD | Wynik management command restore test, raport spójności danych. | TBD |
| Restore | Restore nie może nadpisać production bez jawnego potwierdzenia. | not_started | TBD | Test zabezpieczenia restore, review skryptu `restore`. | TBD |
| Disaster recovery | RPO i RTO są zdefiniowane i zaakceptowane. | not_started | TBD | `docs/runbooks/backup-and-restore.md`, podpisana decyzja właściciela produktu. | TBD |
| Disaster recovery | Procedura odtworzenia środowiska production jest przećwiczona na staging. | not_started | TBD | Wynik ćwiczenia DR, czas odtworzenia, lista problemów. | TBD |
| Monitoring | Metryki techniczne API, DB, queue, tasks, deploymentów i webhooków są zbierane. | not_started | TBD | Prometheus targets healthy, dashboard Grafana, próbki metryk. | TBD |
| Monitoring | Metryki biznesowe deploymentów, subskrypcji, storage i transferu są zbierane. | not_started | TBD | Dashboard biznesowy, test danych meteringu. | TBD |
| Alerting | Alerty krytyczne są skonfigurowane i routowane do właściwych osób. | not_started | TBD | Test alertu, konfiguracja Alertmanager/on-call, potwierdzenie odbioru. | TBD |
| Alerting | Alerty obejmują error rate, kolejki buildów, Stripe webhooki, certyfikaty, storage i DB latency. | not_started | TBD | `infra/observability/platform-alerts.yml`, testy alertów na staging. | TBD |
| Logging | Logi aplikacyjne są strukturalne, zawierają request_id/correlation_id i nie zawierają sekretów. | not_started | TBD | Przegląd logów staging, test redakcji sekretów. | TBD |
| Audit logs | AuditLog jest append-only na poziomie aplikacji i zapisuje krytyczne akcje. | not_started | TBD | Testy AuditLog, próba update/delete, review listy zdarzeń. | TBD |
| Incident response | Runbook incident response jest aktualny i znany zespołowi. | not_started | TBD | `docs/runbooks/incident-response.md`, ćwiczenie pierwszych 30 minut. | TBD |
| Incident response | Zdefiniowano severity levels, role, kanały komunikacji i proces postmortem. | not_started | TBD | Matryca ról, szablon postmortem, lista kontaktów. | TBD |
| Legal/RODO | Klasyfikacja danych, retencja, eksport i usuwanie danych są opisane i wdrożone. | not_started | TBD | `docs/security/data-protection.md`, testy data export/deletion. | TBD |
| Legal/RODO | Procedura obsługi żądania użytkownika i właściciela organizacji jest gotowa. | not_started | TBD | Test eksportu danych, test usunięcia konta, szablony odpowiedzi supportu. | TBD |
| Abuse handling | Operator może blokować projekt/organizację, wymagany jest powód i AuditLog. | not_started | TBD | Testy abuse handling, `docs/runbooks/abuse-handling.md`. | TBD |
| Abuse handling | Alerty abuse obejmują nadmierny transfer, deployment spam, podejrzane domeny, malware i błędy 4xx/5xx. | not_started | TBD | Testy alertów, dashboard abuse/security events. | TBD |
| Domain handling | Dodanie domeny wymaga weryfikacji TXT i blokuje takeover cudzej domeny. | not_started | TBD | Testy custom domains, ręczny test DNS na staging. | TBD |
| Domain handling | Domeny systemowe platformy są zablokowane. | not_started | TBD | Testy system hostname/suffix denylist, konfiguracja production. | TBD |
| Certificate renewal | Automatyczne certyfikaty przez cert-manager działają dla domen staging i production. | not_started | TBD | Test cert-manager, status Certificate, próbna domena. | TBD |
| Certificate renewal | Alerty dla certyfikatów wygasających i runbook awarii certyfikatu są gotowe. | not_started | TBD | `docs/runbooks/certificate-failure.md`, test alertu expiry. | TBD |
| Rollback | Static i container deployments obsługują rollback do poprzedniej wersji. | not_started | TBD | Testy rollback, ręczny test staging, AuditLog rollbacku. | TBD |
| Database migrations | Migracje przechodzą `makemigrations --check --dry-run` i są bezpieczne operacyjnie. | not_started | TBD | Wynik CI, review migracji, plan rollbacku migracji. | TBD |
| Database migrations | Istnieje procedura wykonywania migracji przy deployu production. | not_started | TBD | Runbook deployu, smoke test po migracji. | TBD |
| Load testing | Wykonano testy wydajnościowe na staging dla logowania, projektów, deploymentów, webhooków i rate limitów. | not_started | TBD | Raport k6/Locust, `docs/runbooks/load-testing.md`. | TBD |
| Load testing | Progi akceptacji latency, error rate i throughput są spełnione. | not_started | TBD | Wyniki testów, dashboard Grafana z czasu testu. | TBD |
| Koszt infrastruktury | Oszacowano koszt staging i production oraz ustawiono budżety/alerty kosztowe. | not_started | TBD | Kalkulacja kosztów, alert budżetowy cloud/provider, owner kosztów. | TBD |
| Koszt infrastruktury | Limity autoscalingu i storage chronią przed niekontrolowanym kosztem. | not_started | TBD | HPA limits, ResourceQuota, bucket lifecycle, cost alert test. | TBD |
| Procedury supportu | Support ma instrukcje obsługi typowych spraw: login, billing, domeny, deployment, dane użytkownika. | not_started | TBD | Playbook supportu, makra odpowiedzi, ścieżka eskalacji. | TBD |
| Procedury supportu | Support nie ma dostępu do sekretów klientów i używa zasady least privilege. | not_started | TBD | Review uprawnień, test braku podglądu sekretów, AuditLog dostępu. | TBD |

## Decyzja Go-Live

Przed uruchomieniem production:

- wszystkie punkty krytyczne muszą mieć status `ready`,
- punkty `accepted_risk` muszą mieć właściciela, termin ponownego przeglądu i opis ryzyka,
- punkty `blocked` wymagają decyzji no-go albo formalnej akceptacji ryzyka,
- wynik checklisty musi zostać zapisany w systemie zarządzania zmianą albo w zatwierdzonym issue.
