# Struktura repozytorium

## Główne katalogi

- `apps/api`: backend Django, modele, widoki, RBAC, auth, billing, deploymenty i testy backendowe.
- `apps/dashboard`: dashboard Next.js + TypeScript.
- `apps/deployment-worker`: bazowy worker deploymentów.
- `apps/provisioner-service`: bazowy provisioner zasobów runtime.
- `config/settings`: ustawienia Django dla developmentu, testów, stagingu i production.
- `docs`: dokumentacja architektoniczna, security, runbooki, user docs i developer docs.
- `infra`: Kubernetes, Helm, observability, staging i Terraform.
- `scripts`: skrypty operacyjne, backup/restore i pomocnicze.
- `tests/security`: testy bezpieczeństwa uruchamiane w CI.
- `tests/performance`: scenariusze wydajnościowe.

## Backend

Najważniejsze pliki backendu:

- `apps/api/models.py`: modele domenowe.
- `apps/api/rbac.py`: role i centralne mapowanie uprawnień.
- `apps/api/tenancy.py`: helpery tenant context.
- `apps/api/permissions.py`: klasy permission dla DRF.
- `apps/api/audit_log.py`: centralny helper audytu.
- `apps/api/entitlements.py`: limity i uprawnienia planów.
- `apps/api/urls.py`: routing API.

## Frontend

Dashboard znajduje się w `apps/dashboard`.

Typowy układ:

- `src/app`: strony Next.js.
- `src/components`: komponenty UI i modułowe sekcje.
- `src/lib`: klient API, typy, helpers.
- `e2e`: testy Playwright.

## Infrastruktura

- `infra/helm`: chart platformy.
- `infra/kubernetes`: bazowe manifesty runtime.
- `infra/policies`: polityki Kyverno/OPA/Conftest.
- `infra/observability`: Prometheus, Grafana, Loki i alerty.
- `infra/terraform`: struktura IaC dla stagingu i production.
