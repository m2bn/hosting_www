# CI/CD Security

## Cel

GitHub Actions CI ma blokować regresje jakości, błędy bezpieczeństwa i krytyczne podatności przed merge do `main`.

## Workflow

Główny workflow znajduje się w:

```text
.github/workflows/ci.yml
```

Uruchamia się dla:

- `pull_request`,
- `push` do `main`.

## Joby

- `Lint backend`: Ruff dla kodu Python.
- `Backend tests`: `python manage.py check`, sprawdzenie migracji i pełny test suite.
- `Django production deploy check`: `python manage.py check --deploy` z production settings i testowymi envami CI.
- `Security tests`: osobny job dla testów security, auth, secure config i API keys.
- `Dependency scanning`: `pip-audit --strict`.
- `Secret scanning`: Gitleaks.
- `SAST`: Semgrep OWASP Top 10 i secrets.
- `Generate SBOM`: CycloneDX SBOM przez Anchore/Syft.
- `Container image scanning`: Trivy dla każdego znalezionego `Dockerfile`; brak Dockerfile kończy job sukcesem.
- `Kubernetes manifests and policies`: Helm lint/template, kubeconform i Kyverno policy checks.
- `CI required status`: agregujący status do ustawienia jako required check w branch protection.

## Sekrety

- Workflow nie zawiera sekretów.
- Produkcyjne sekrety muszą być przekazywane wyłącznie przez GitHub Actions secrets.
- CI używa wyłącznie wartości testowych tam, gdzie Django wymaga obecności zmiennych środowiskowych.
- Tokeny zewnętrznych skanerów, jeśli kiedyś będą wymagane, muszą być dodane jako `secrets.*`, nigdy jako plaintext.

## Blokowanie Merge

W branch protection dla `main` należy ustawić jako required status:

```text
CI required status
```

Ten job zależy od wszystkich krytycznych jobów i kończy się błędem, jeśli którykolwiek z nich nie przejdzie.

## Krytyczne Podatności

- `pip-audit --strict` blokuje znane podatności zależności.
- Trivy blokuje obrazy z podatnościami `CRITICAL`.
- Semgrep z `--error` blokuje wykryte istotne problemy SAST.
- Gitleaks blokuje znalezione sekrety.
- Kyverno/kubeconform blokują niezgodne manifesty runtime.

## Cache

Workflow używa cache pip przez `actions/setup-python`.

## Zasady Utrzymania

- Nie obniżać severity skanerów bez decyzji ADR albo wyjątku risk acceptance.
- Nie dodawać `continue-on-error` do jobów security.
- Nie logować wartości sekretów ani tokenów w krokach CI.
- Aktualizować wersje akcji cyklicznie.
- Dla nowych języków i runtime dodać odpowiedni lint, SAST, dependency scanning i SBOM.
