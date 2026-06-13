# Load Testing Runbook

## Cel

Load testy służą do sprawdzenia, czy staging wytrzymuje podstawowy ruch użytkowników i integracji przed promocją zmian do production. Testy obejmują krytyczne ścieżki SaaS: logowanie, listę projektów, upload statycznej strony, deployment, webhooki Stripe, logi deploymentu, dashboard i rate limiting API.

Nie uruchamiaj testów przeciwko production.

## Narzędzie

Używamy k6:

```bash
k6 version
```

Scenariusze znajdują się w:

```text
tests/performance/k6/staging.load.js
```

Test statyczny konfiguracji, uruchamiany w CI:

```bash
python manage.py test tests.performance
```

## Scenariusze

- `login` - pobiera CSRF token i wykonuje logowanie sesyjne cookie.
- `projects_list` - pobiera listę projektów w organizacji.
- `static_upload` - uploaduje małą statyczną stronę ZIP.
- `deployment` - wykonuje bazowy deployment statyczny.
- `stripe_webhook` - wysyła testowy event webhooka Stripe.
- `deployment_logs` - pobiera logi deploymentu.
- `dashboard` - ładuje dashboard webowy.
- `api_rate_limit` - wykonuje serię błędnych logowań i oczekuje `429`.

## Progi Akceptacji

Minimalne progi w skrypcie k6:

- globalny `http_req_failed < 5%`,
- login `p95 < 750 ms`, `p99 < 1500 ms`,
- lista projektów `p95 < 800 ms`,
- upload statycznej strony `p95 < 5000 ms`,
- deployment request `p95 < 8000 ms`,
- webhook Stripe `p95 < 1000 ms`,
- pobieranie logów deploymentu `p95 < 1000 ms`,
- dashboard `p95 < 1200 ms`,
- rate limit: co najmniej 95% sprawdzeń musi wykryć `429`.

Przed production release wszystkie progi muszą przejść na staging. Jeżeli próg nie przejdzie, release wymaga jawnej decyzji technicznej i wpisu w changelogu.

## Przygotowanie Staging

1. Upewnij się, że staging jest wdrożony zgodnie z `docs/runbooks/staging.md`.
2. Uruchom seed danych:

```bash
ENVIRONMENT=staging \
STAGING_ALLOW_SEED=true \
STAGING_SEED_PASSWORD=<from-secret-manager> \
python manage.py seed_staging --settings=config.settings.staging
```

3. Przygotuj wartości z seed/staging API:

- `LOAD_TEST_ORG_ID`
- `LOAD_TEST_PROJECT_ID`
- `LOAD_TEST_ENVIRONMENT_ID`
- `LOAD_TEST_DEPLOYMENT_ID`
- `LOAD_TEST_USER_EMAIL`
- `LOAD_TEST_USER_PASSWORD`

4. Opcjonalnie skonfiguruj `STRIPE_WEBHOOK_SECRET` z testowego webhook endpointu. Bez niego scenariusz webhooków sprawdza szybką ścieżkę odrzucenia niepoprawnego podpisu.

## Uruchomienie Na Staging

Z katalogu `tests/performance/k6`:

```bash
cd tests/performance/k6
k6 run staging.load.js \
  -e LOAD_TEST_ENV=staging \
  -e API_BASE_URL=https://api.staging.example.com \
  -e DASHBOARD_BASE_URL=https://app.staging.example.com \
  -e LOAD_TEST_USER_EMAIL=owner.staging@example.com \
  -e LOAD_TEST_USER_PASSWORD="$LOAD_TEST_USER_PASSWORD" \
  -e LOAD_TEST_ORG_ID="$LOAD_TEST_ORG_ID" \
  -e LOAD_TEST_PROJECT_ID="$LOAD_TEST_PROJECT_ID" \
  -e LOAD_TEST_ENVIRONMENT_ID="$LOAD_TEST_ENVIRONMENT_ID" \
  -e LOAD_TEST_DEPLOYMENT_ID="$LOAD_TEST_DEPLOYMENT_ID" \
  -e STRIPE_WEBHOOK_SECRET="$STRIPE_WEBHOOK_SECRET"
```

Skrypt ma staging guard:

- wymaga `LOAD_TEST_ENV=staging` dla zdalnych URL-i,
- odmawia uruchomienia dla production-looking URL-i,
- nie wymaga żadnych produkcyjnych sekretów.

## Profile Obciążenia

Domyślny profil jest niski i bezpieczny dla staging. Można go regulować zmiennymi:

- `K6_LOGIN_VUS`, `K6_LOGIN_DURATION`
- `K6_PROJECTS_VUS`, `K6_PROJECTS_DURATION`
- `K6_UPLOAD_VUS`, `K6_UPLOAD_ITERATIONS`
- `K6_DEPLOYMENT_VUS`, `K6_DEPLOYMENT_ITERATIONS`
- `K6_STRIPE_WEBHOOK_RATE`, `K6_STRIPE_WEBHOOK_DURATION`
- `K6_LOGS_VUS`, `K6_LOGS_DURATION`
- `K6_DASHBOARD_VUS`, `K6_DASHBOARD_DURATION`
- `K6_RATE_LIMIT_ITERATIONS`

Zwiększaj obciążenie stopniowo. Nie rób stress testu na staging bez uzgodnienia z operatorem platformy.

## Dane I Bezpieczeństwo

- Używaj wyłącznie kont stagingowych.
- Używaj wyłącznie Stripe test mode.
- Nie używaj production database, production bucketów, production webhook secret ani production domen.
- Upload ZIP w testach zawiera tylko minimalną statyczną stronę testową.
- Wyniki testów mogą zawierać URL-e staging i statusy HTTP, ale nie mogą zawierać haseł ani sekretów.

## Interpretacja Wyników

Po teście sprawdź:

- czy wszystkie thresholdy k6 przeszły,
- czy staging observability nie pokazuje wzrostu error rate,
- czy kolejki RabbitMQ/Celery wróciły do normy,
- czy deployment-worker nie zostawił zadań w stanie failed,
- czy Stripe webhook duplicate/replay nie zmienił stanu wielokrotnie,
- czy rate limiting zwrócił `429`.

## CI

CI nie odpala pełnego load testu przeciwko staging automatycznie. CI uruchamia statyczną walidację konfiguracji:

```bash
python manage.py test tests.performance
```

Pełny k6 run powinien być uruchamiany ręcznie lub przez osobny manual workflow po deployu staging.
