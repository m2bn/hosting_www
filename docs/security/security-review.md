# Security Review

Data przeglądu: 2026-06-13

Zakres: całe repozytorium, w tym backend Django, dashboard Next.js, worker/provisioner, manifesty Kubernetes/Helm, CI/CD, backup/restore, dokumentacja security i testy.

## Podsumowanie

Przegląd objął:

- IDOR i multi-tenancy,
- RBAC,
- CSRF,
- XSS,
- SSRF,
- RCE,
- upload plików i ZIP extraction,
- Stripe webhooks,
- API keys,
- sekrety,
- logi i AuditLog,
- CORS i security headers,
- Dockerfile/build pipeline,
- Kubernetes manifests,
- CI/CD,
- backupy i restore,
- operator console,
- rate limiting,
- dependency security,
- test coverage,
- domain takeover,
- certificate handling,
- metering abuse.

W trakcie przeglądu znaleziono dwa wysokie ryzyka i jedno średnie. Wysokie ryzyka zostały poprawione i mają testy regresyjne. Średnie ryzyko restore tar linków również zostało poprawione.

## Problemy

| ID | Opis | Ryzyko | Lokalizacja | Rekomendowana poprawka | Priorytet | Status |
|---|---|---|---|---|---|---|
| SR-001 | Reset hasła i zmiana hasła nie usuwały aktywnie wszystkich istniejących sesji użytkownika. Zmiana hasła powodowała wylogowanie bieżącej sesji, ale inne sesje nie były kasowane od razu z tabeli sesji. | Po przejęciu konta lub urządzenia atakujący mógł utrzymać aktywną sesję dłużej niż oczekuje użytkownik po resecie hasła. | `apps/api/auth_views.py`, `apps/api/auth_utils.py` | Po zapisie nowego hasła wywołać `invalidate_user_sessions(user)` dla resetu i zmiany hasła. Dodać testy dla bieżącej i równoległej sesji. | High | Fixed |
| SR-002 | Backup deployment files z S3 używał klucza obiektu jako ścieżki lokalnej bez sprawdzenia, czy wynik pozostaje wewnątrz katalogu backupu komponentu. | Złośliwy lub błędnie utworzony object key z `../` mógł zapisać plik poza katalogiem komponentu backupu i naruszyć integralność backupu. | `apps/api/backups.py` | Dodać `_safe_backup_child_path(...)` oparty o `Path.resolve()` i `relative_to(...)`; przerwać backup przy niebezpiecznym kluczu. | High | Fixed |
| SR-003 | Restore tar sprawdzał traversal ścieżek, ale nie odrzucał symlinków i hardlinków w archiwum. | Przy odtwarzaniu z nieufnego lub uszkodzonego backupu linki mogły wskazywać poza katalog restore. Backup jest szyfrowany, ale restore powinien być defensywny. | `apps/api/backups.py` | Odrzucać `member.issym()` i `member.islnk()` przed `extractall(...)`. | Medium | Fixed |
| SR-004 | HTML dokumentacji API renderował wartości schemy bez jawnego escaping HTML. Obecnie schema jest statyczna, ale wzorzec był podatny na przyszłe rozszerzenia o dane dynamiczne. | Potencjalny XSS w `/api/docs/`, jeśli w przyszłości opis endpointu albo przykład trafiłby z niekontrolowanego źródła. | `apps/api/openapi_views.py` | Escapować method, path, summary, description i JSON schemy przed wstawieniem do HTML. | Medium | Fixed |
| SR-005 | OpenAPI zawiera opis endpointu audit logs, ale w aktualnym routingu nie ma jeszcze publicznego endpointu `/organizations/{organization_public_id}/audit-logs/`. | Niespójność dokumentacji może prowadzić do błędnych integracji i mylnego założenia, że audit logs są dostępne przez API. | `apps/api/openapi.py`, `apps/api/urls.py` | Albo zaimplementować endpoint audit logs z RBAC i tenant filtering, albo oznaczyć go jako planned/not enabled w schemie. | Low | Open |
| SR-006 | `check_pending_domains(...)` z domyślnym resolverem zwracającym pustą listę może oznaczyć wszystkie pending domains jako `failed`, jeśli zostanie uruchomione bez właściwej integracji DNS. | Ryzyko operacyjne: błędne masowe przejście domen w status failed, co może pogorszyć UX i utrudnić weryfikację domen. | `apps/api/custom_domains.py` | W zadaniu okresowym wymagać jawnie skonfigurowanego resolvera DNS albo fail-closed bez zmiany statusu, jeśli resolver nie jest skonfigurowany. | Low | Open |
| SR-007 | Production settings domyślnie pozwalają na SQLite, jeśli `DJANGO_DB_ENGINE` i `DJANGO_DB_NAME` nie są ustawione. | Ryzyko błędnej konfiguracji production i uruchomienia na nieodpowiedniej bazie danych. Nie jest to bezpośrednia luka exploitable, ale istotne ryzyko operacyjne. | `config/settings/production.py` | W production wymagać PostgreSQL przez konfigurację albo jawnie blokować SQLite, chyba że ustawiono specjalną flagę awaryjną. | Medium | Open |

## Obszary Zweryfikowane Bez Istotnych Ustaleń

| Obszar | Wynik | Dowód/weryfikacja |
|---|---|---|
| IDOR | Endpointy organizacji/projektów/domen/deploymentów używają organization context i testów cross-tenant. | `apps/api/project_views.py`, `apps/api/domain_views.py`, `apps/api/static_deployment_views.py`, `tests/security/test_idor.py` |
| RBAC | Role owner/admin/developer/billing/viewer są centralnie mapowane; testy pokrywają role krytyczne. | `apps/api/rbac.py`, `apps/api/tests_authorization.py` |
| CSRF | Endpointy sesyjne i mutujące są chronione middleware CSRF; Stripe webhook jest świadomie zwolniony i wymaga podpisu. | `apps/api/tests_authentication.py`, `apps/api/billing_views.py` |
| XSS | Dashboard nie używa `dangerouslySetInnerHTML`, `innerHTML`, `eval` ani token storage. API docs HTML został dodatkowo escapowany. | `apps/dashboard/src`, `apps/api/openapi_views.py` |
| SSRF | Moduły upload/deployment nie wykonują bezpośrednich fetchy URL-i użytkownika. | `tests/security/test_ssrf_and_private_resource_guards.py` |
| RCE | Container build spec deklaruje izolowany namespace, brak privileged i brak sekretów control plane. Pełne wykonanie buildów jest nadal mockowane/MVP. | `apps/api/container_deployments.py`, `apps/deployment-worker/deployment_worker/container_pipeline.py` |
| Upload plików | Static i container ZIP mają walidację rozszerzenia, MIME, rozmiaru, limitów i skanowania artefaktów. | `apps/api/static_deployments.py`, `apps/api/container_deployments.py`, `apps/api/artifact_scanning.py` |
| ZIP extraction | Zip slip i symlinki są odrzucane; dodano defensywną poprawkę restore tar. | `apps/api/tests_static_deployments.py`, `apps/api/tests_container_deployments.py`, `apps/api/tests_backup_restore.py` |
| Stripe webhooks | Podpis jest wymagany, eventy są idempotentne, duplicate payload mismatch jest blokowany, powiązanie customer/org jest weryfikowane. | `apps/api/billing_service.py`, `apps/api/tests_stripe_webhooks.py` |
| API keys | Klucze są hashowane, widoczne raz, mają scope, expiration, revoked status i rate limiting. | `apps/api/api_keys.py`, `apps/api/api_key_authentication.py`, `apps/api/tests_api_keys.py` |
| Sekrety | Sekrety projektu są szyfrowane, nie zwracane przez API, metadata jest sanitizowana. | `apps/api/secrets.py`, `apps/api/secret_views.py`, `apps/api/tests_secrets.py` |
| Logi | Filtr redakcji sekretów i structured logs są skonfigurowane. | `config/logging_filters.py`, `config/structured_logging.py` |
| CORS | CORS jest allowlist-based, bez wildcard credentials. | `config/security_headers.py`, `tests/security/test_platform_security_configuration.py` |
| Security headers | CSP, Referrer-Policy, Permissions-Policy, X-Frame-Options i nosniff są testowane. | `config/security_headers.py`, `apps/api/tests_secure_configuration.py` |
| Kubernetes manifests | Runtime i platform services mają non-root, seccomp, brak privileged, resource limits, NetworkPolicy. | `infra/helm`, `infra/kubernetes`, `tests/security/test_kubernetes_manifest_policy_validation.py` |
| CI/CD | CI obejmuje lint, testy, deploy check, security tests, dependency scanning, secret scanning, SAST, SBOM i manifest policies. | `.github/workflows/ci.yml` |
| Operator console | Operator endpoints wymagają platform staff, 2FA i powodów dla akcji blokujących. | `apps/api/operator_views.py`, `apps/api/tests_abuse_handling.py` |
| Audit logs | AuditLog jest append-only na poziomie aplikacji; metadata jest sanitizowana. | `apps/api/audit_log.py`, `apps/api/tests_audit_log.py` |
| Rate limiting | Login i API key mają rate limiting testowany regresyjnie. | `apps/api/auth_utils.py`, `apps/api/api_keys.py`, `apps/api/tests_authentication.py`, `apps/api/tests_api_keys.py` |
| Dependency security | CI używa `pip-audit`; wcześniejszy problem `cryptography` wymagał aktualizacji zależności i jest objęty pipeline. | `.github/workflows/ci.yml`, `pyproject.toml` |
| Domain takeover | Domeny są unikalne globalnie dla aktywnych rekordów, mają TXT verification i blokadę system domains. | `apps/api/custom_domains.py`, `apps/api/tests_custom_domains.py` |
| Certificate handling | Certyfikaty są żądane po weryfikacji domeny; ręczny upload klucza prywatnego nie jest dostępny w MVP. | `apps/api/certificates.py`, `apps/api/tests_certificates.py` |
| Metering abuse | Usage jest przypisany do organization/project; threshold alerts i blokady limitów są testowane. | `apps/api/metering.py`, `apps/api/tests_metering.py` |

## Poprawki Wykonane W Ramach Przeglądu

- Dodano aktywne unieważnianie sesji po resecie i zmianie hasła.
- Dodano testy regresyjne dla unieważniania bieżącej i równoległej sesji.
- Zabezpieczono backup deployment files przed traversal przez klucze S3.
- Zabezpieczono restore tar przed symlinkami i hardlinkami.
- Dodano testy regresyjne dla backup path traversal i tar linków.
- Dodano escaping HTML w `/api/docs/`.

## Rekomendacje Następne

1. Domknąć `SR-005`: zaimplementować endpoint audit logs albo usunąć go z publicznej schemy do czasu implementacji.
2. Domknąć `SR-006`: wymusić jawny DNS resolver w jobie okresowej weryfikacji domen.
3. Domknąć `SR-007`: zablokować SQLite w production settings.
4. Rozszerzyć testy SAST/SCA o dashboard npm audit i pinning akcji GitHub Actions do SHA dla wyższego poziomu supply-chain.
5. Przed production wykonać zewnętrzny pentest i ćwiczenie disaster recovery.
