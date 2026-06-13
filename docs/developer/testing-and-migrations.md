# Testy i migracje

## Backend

Podstawowy zestaw:

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

Wybrany moduł:

```powershell
python manage.py test apps.api.tests_projects
python manage.py test apps.api.tests_artifact_scanning
```

## Security tests

Testy bezpieczeństwa powinny obejmować:

- IDOR,
- CSRF,
- rate limiting,
- RBAC privilege escalation,
- API key scope bypass,
- brak wycieku sekretów w logach,
- Stripe webhook signature,
- zip slip i symlinki,
- tenant isolation.

## Frontend

```powershell
cd apps/dashboard
npm run lint
npm run typecheck
npm run test
npm run test:e2e
```

## Migracje bazy

Po zmianie modeli:

```powershell
python manage.py makemigrations
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test
```

Migracje powinny być deterministyczne i bezpieczne dla danych. Dla dużych tabel unikaj operacji, które długo blokują zapis w production.

## Testy migracji

Jeśli migracja przenosi dane albo zmienia constraint, dodaj test regresyjny na docelowe zachowanie modelu lub endpointu.

## Sprzątanie po testach

Testy mogą tworzyć lokalne artefakty, na przykład katalogi storage. Nie commituj:

- `__pycache__`,
- `.ruff_cache`,
- lokalnych uploadów,
- lokalnych backupów,
- plików `.env`.
