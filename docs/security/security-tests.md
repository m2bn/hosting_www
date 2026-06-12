# Security Tests

## Cel

Katalog `tests/security` jest centralnym katalogiem regresji bezpieczeństwa. Nie zastępuje testów domenowych w `apps/api`, tylko je agreguje, opisuje i pilnuje, żeby krytyczne scenariusze były uruchamiane w CI.

## Uruchamianie

Lokalnie:

```bash
python manage.py test tests.security
```

Pełny security suite taki jak w CI:

```bash
python manage.py test \
  tests.security \
  apps.api.tests_secure_configuration \
  apps.api.tests_authentication \
  apps.api.tests_authorization \
  apps.api.tests_api_keys \
  apps.api.tests_stripe_webhooks \
  apps.api.tests_static_deployments \
  apps.api.tests_container_deployments \
  apps.api.tests_custom_domains \
  apps.api.tests_secrets \
  apps.api.tests_organizations \
  apps.api.tests_projects \
  apps.api.tests_audit_log
```

CI uruchamia ten zestaw w jobie `Security tests`.

## Pokryte Scenariusze

| Scenariusz | Główne testy |
| --- | --- |
| IDOR | `tests/security/test_idor.py` |
| CSRF | `apps/api/tests_authentication.py` |
| Brute force login | `apps/api/tests_authentication.py` |
| Rate limiting | `apps/api/tests_authentication.py`, `apps/api/tests_api_keys.py` |
| Invalid Stripe webhook signature | `apps/api/tests_stripe_webhooks.py` |
| Duplicate Stripe webhook | `apps/api/tests_stripe_webhooks.py` |
| Replay webhook | `apps/api/tests_stripe_webhooks.py` |
| Zip slip | `apps/api/tests_static_deployments.py` |
| Symlink upload | `apps/api/tests_static_deployments.py` |
| Unauthorized organization access | `apps/api/tests_organizations.py`, `tests/security/test_idor.py` |
| API key scope bypass | `apps/api/tests_api_keys.py`, `tests/security/test_idor.py` |
| Secret leakage in logs | `apps/api/tests_secrets.py` |
| SSRF prevention | `tests/security/test_ssrf_and_private_resource_guards.py` |
| Domain takeover | `apps/api/tests_custom_domains.py` |
| Privilege escalation in RBAC | `apps/api/tests_authorization.py`, `tests/security/test_idor.py` |
| Kubernetes manifest policy validation | `tests/security/test_kubernetes_manifest_policy_validation.py` |
| Insecure headers | `tests/security/test_platform_security_configuration.py` |
| CORS misconfiguration | `tests/security/test_platform_security_configuration.py`, `apps/api/tests_secure_configuration.py` |
| Public access to private resources | `apps/api/tests_secrets.py`, `tests/security/test_idor.py` |
| Missing audit logs for critical actions | `tests/security/test_audit_coverage.py` plus API module tests |

## Zasady Dodawania Testów

- Każda nowa funkcja dotykająca danych tenantów musi mieć test negatywny cross-tenant.
- Każda akcja krytyczna musi mieć test AuditLog.
- Każdy endpoint sesyjny zapisujący dane musi mieć test CSRF.
- Każdy upload lub parser archiwów musi mieć test path traversal i limitów.
- Każdy webhook musi mieć test invalid signature, duplicate event i replay.
- Każda integracja wychodząca do URL podanego przez użytkownika musi mieć test SSRF lub używać wspólnego bezpiecznego fetchera.
- Każda zmiana manifestów Kubernetes musi przechodzić testy policy i Helm/static chart tests.

## Oczekiwane Zachowanie Błędów

- Cross-tenant access powinien zwracać `404`, jeśli ujawnienie istnienia zasobu byłoby ryzykiem IDOR.
- Brak uprawnienia w znanym kontekście organizacji może zwracać `403`.
- Sekrety nigdy nie mogą pojawiać się w odpowiedziach API, logach ani AuditLog metadata.
- Webhook z niepoprawnym podpisem nie może tworzyć ani modyfikować stanu biznesowego.
- Powtórzony webhook może zwrócić `200`, ale nie może drugi raz zmienić stanu.

## CI

Job `Security tests` w `.github/workflows/ci.yml` musi pozostać wymagany dla PR. Jeżeli dodajesz nowy plik testów bezpieczeństwa, dopisz go do joba albo upewnij się, że jest odkrywany przez `tests.security`.

## Braki I Przyszłe Rozszerzenia

- Po dodaniu wspólnego HTTP fetchera należy zastąpić statyczny SSRF guard testami walidacji adresów prywatnych, redirectów i DNS rebinding.
- Po wdrożeniu realnego klastra CI powinno wykonywać `helm template`, `kubeconform` oraz Kyverno/Conftest na renderowanych manifestach.
- Po dodaniu pełnych endpointów operator panelu należy dodać testy wysokiego ryzyka z wymaganym powodem i AuditLog.
