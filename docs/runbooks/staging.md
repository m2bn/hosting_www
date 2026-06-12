# Staging Runbook

## Cel

Staging jest odizolowanym środowiskiem przedprodukcyjnym do walidacji deployów, integracji Stripe test mode, webhooków, smoke testów, e2e i zmian infrastruktury bez dostępu do danych produkcyjnych.

## Wymagania Izolacji

- Osobny namespace Kubernetes: `platform-staging`.
- Osobna baza danych PostgreSQL.
- Osobne Redis i RabbitMQ.
- Osobny bucket S3/MinIO.
- Osobne sekrety w secrets managerze.
- Osobne domeny: `app.staging.example.com`, `api.staging.example.com`, `*.apps.staging.example.com`.
- Stripe wyłącznie w test mode.
- Brak dostępu do produkcyjnych baz, bucketów, Stripe live mode, sekretów i backupów.

## Pliki Konfiguracyjne

- `infra/staging/namespace.yaml` - namespace staging z Pod Security Restricted.
- `infra/staging/external-secrets.example.yaml` - przykład integracji External Secrets.
- `infra/staging/stripe-webhooks.example.json` - kontrakt webhooków Stripe test mode.
- `infra/staging/e2e.env.example` - zmienne wymagane do testów e2e.
- `infra/helm/platform-services/values-staging.yaml` - wartości Helm dla usług platformy.
- `infra/terraform/envs/staging/terraform.tfvars.example` - przykładowa konfiguracja infrastruktury staging.

## Provisioning

1. Utwórz lub zaktualizuj infrastrukturę staging:

```bash
cd infra/terraform/envs/staging
terraform init
terraform plan -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars
```

2. Utwórz namespace:

```bash
kubectl apply -f infra/staging/namespace.yaml
```

3. Skonfiguruj External Secrets dla staging. Nie używaj produkcyjnego `ClusterSecretStore`.

4. Zainstaluj usługi:

```bash
helm upgrade --install platform-services infra/helm/platform-services \
  --namespace platform-staging \
  --create-namespace \
  -f infra/helm/platform-services/values-staging.yaml
```

## Sekrety

Sekrety staging muszą żyć pod osobnym prefiksem, na przykład:

```text
platform/platform-staging/<service>/<KEY>
```

Wymagane sekrety obejmują:

- `DJANGO_SECRET_KEY`
- `DATABASE_URL`
- `REDIS_URL`
- `RABBITMQ_URL`
- `STRIPE_SECRET_KEY` z prefiksem `sk_test_`
- `STRIPE_WEBHOOK_SECRET` dla staging endpointu
- `PROJECT_SECRET_ENCRYPTION_KEY`
- `BACKUP_ENCRYPTION_KEY`
- klucze S3/MinIO staging
- hasło `STAGING_SEED_PASSWORD` tylko dla kont testowych

Nie wolno kopiować sekretów production do staging.

## Stripe Test Mode

Staging używa wyłącznie Stripe test mode.

Webhook endpoint:

```text
https://api.staging.example.com/api/billing/stripe/webhook/
```

Obsługiwane eventy:

- `checkout.session.completed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.paid`
- `invoice.payment_failed`

Po konfiguracji webhooka zapisz signing secret w secrets managerze pod:

```text
platform/platform-staging/billing-service/STRIPE_WEBHOOK_SECRET
```

## Seed Danych Testowych

Seed wykonuj tylko na staging:

```bash
ENVIRONMENT=staging \
STAGING_ALLOW_SEED=true \
STAGING_SEED_PASSWORD=<from-secret-manager> \
python manage.py seed_staging --settings=config.settings.staging
```

Seed tworzy:

- organizację `Staging Acme`,
- konta owner/developer/viewer/billing,
- plan `staging-pro`,
- subskrypcję trialing,
- projekt `Staging Web`,
- środowisko `staging`,
- platformową domenę staging,
- certyfikat testowy,
- przykładowe usage,
- AuditLog `staging.seed`.

Jeżeli `STAGING_SEED_PASSWORD` nie jest podane, konta dostają unusable password i nie mogą być użyte do e2e loginu.

## Smoke Tests Po Deployu

Po każdym deployu uruchom:

```bash
python scripts/smoke_staging.py \
  --api-url https://api.staging.example.com \
  --dashboard-url https://app.staging.example.com
```

Minimalne warunki sukcesu:

- API `/healthz` zwraca 2xx/3xx.
- API `/livez` zwraca 2xx/3xx.
- Dashboard ładuje stronę startową.
- Brak krytycznych alertów w dashboardzie observability.

## E2E Tests

1. Przygotuj plik env poza repo na bazie `infra/staging/e2e.env.example`.
2. Upewnij się, że seed staging utworzył konto testowe.
3. Uruchom testy dashboardu:

```bash
cd apps/dashboard
npm run test:e2e
```

Testy e2e nie mogą używać kont produkcyjnych ani danych produkcyjnych.

## Observability

Staging musi mieć osobny dashboard observability z filtrem:

```text
environment="staging"
namespace="platform-staging"
```

Dashboard powinien pokazywać:

- request rate i error rate API,
- latency API,
- health usług platformy,
- queue depth RabbitMQ,
- Celery task failures,
- Stripe webhook failures,
- deployment failures,
- cert-manager errors,
- usage/metering pipeline status.

Alerty staging mogą trafiać do osobnego kanału niż production i muszą być oznaczone jako staging.

## Ochrona Przed Dostępem Do Production

Staging nie może mieć:

- routingu sieciowego do production database,
- dostępu IAM do production bucketów,
- dostępu do production secrets manager paths,
- Stripe live secret key,
- production webhook signing secret,
- produkcyjnych backupów,
- produkcyjnych kubeconfigów.

Kontrole:

- `config.settings.staging` odmawia uruchomienia, jeśli `STRIPE_TEST_MODE=false`.
- `config.settings.staging` odmawia uruchomienia z kluczem `sk_live_`.
- CI powinno skanować manifesty i env pod kątem produkcyjnych hostów i live Stripe keys.
- Terraform staging używa osobnego state i osobnych nazw zasobów.

## Checklist Deployu Staging

- Terraform plan staging zaakceptowany.
- Helm values staging nie zawierają sekretów.
- External Secrets zsynchronizowane.
- Migracje Django wykonane.
- `seed_staging` wykonany tylko z `ENVIRONMENT=staging`.
- Stripe webhook test mode skonfigurowany.
- Smoke tests przeszły.
- E2E tests przeszły.
- Dashboard observability nie pokazuje krytycznych błędów.

## Rollback

1. Wstrzymaj dalsze deploye na staging.
2. Cofnij ostatni release Helm:

```bash
helm rollback platform-services --namespace platform-staging
```

3. Jeżeli problem dotyczy migracji, odtwórz staging z backupu zgodnie z `docs/runbooks/backup-and-restore.md`.
4. Uruchom smoke tests.
5. Udokumentuj problem w changelogu release candidate.
