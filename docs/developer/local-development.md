# Lokalne uruchomienie

## Wymagania

- Python 3.12+
- Node.js zgodny z dashboardem Next.js
- npm
- PostgreSQL lokalnie albo SQLite/testowa baza, zależnie od konfiguracji
- opcjonalnie Docker, MinIO, RabbitMQ, lokalny Kubernetes

## Backend

1. Utwórz środowisko wirtualne.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Zainstaluj zależności.

```powershell
python -m pip install --upgrade pip
python -m pip install -e .
```

3. Ustaw konfigurację lokalną.

```powershell
$env:DJANGO_SETTINGS_MODULE="config.settings.development"
$env:DJANGO_SECRET_KEY="dev-secret-change-me"
```

4. Uruchom migracje.

```powershell
python manage.py migrate
```

5. Uruchom backend.

```powershell
python manage.py runserver
```

## Dashboard

```powershell
cd apps/dashboard
npm install
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Dashboard używa sesji cookie httpOnly i CSRF. Nie dodawaj tokenów do `localStorage`.

## Plik `.env`

Użyj `.env.example` jako punktu startowego, ale nie wpisuj tam prawdziwych sekretów. Sekrety lokalne trzymaj poza repozytorium.

Minimalne zmienne dla developmentu:

```text
DJANGO_SETTINGS_MODULE=config.settings.development
DJANGO_SECRET_KEY=local-dev-secret
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
STRIPE_TEST_MODE=true
```
