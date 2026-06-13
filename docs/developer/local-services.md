# Usługi lokalne

## Celery i RabbitMQ

Platforma używa Celery/RabbitMQ dla zadań asynchronicznych, takich jak deploymenty, provisioning, powiadomienia i metering.

W development worker może działać lokalnie albo przez tryb inline zależny od konkretnej usługi. Jeśli uruchamiasz prawdziwy worker, użyj osobnego terminala i lokalnego brokera RabbitMQ.

Przykładowe zmienne:

```text
CELERY_BROKER_URL=amqp://guest:guest@localhost:5672//
CELERY_RESULT_BACKEND=rpc://
```

## Stripe test mode

Development i staging muszą używać Stripe test mode.

Zasady:

- używaj tylko kluczy `sk_test_...`,
- nie commituj kluczy Stripe,
- webhook endpoint musi weryfikować podpis,
- testy powinny mockować Stripe SDK, chyba że testujesz integrację ręcznie.

Przykładowe zmienne:

```text
STRIPE_TEST_MODE=true
STRIPE_SECRET_KEY=sk_test_local
STRIPE_WEBHOOK_SECRET=whsec_local
STRIPE_CHECKOUT_SUCCESS_URL=http://localhost:3000/billing/success
STRIPE_CHECKOUT_CANCEL_URL=http://localhost:3000/billing/cancel
```

## MinIO/S3

MinIO może służyć lokalnie jako S3-compatible storage dla deploymentów i backupów.

Zasady:

- używaj osobnych bucketów dla developmentu,
- nie mieszaj danych staging/production,
- nie loguj access key ani secret key,
- prefiksy obiektów muszą zawierać organization/project/deployment context.

## Kubernetes local development

Do lokalnych testów runtime możesz użyć `kind`, `minikube` albo innego lokalnego klastra.

Zasady:

- nie używaj `cluster-admin` dla provisionera,
- namespace per project,
- Pod Security Restricted,
- NetworkPolicy default deny,
- ResourceQuota i LimitRange,
- brak `hostPath`, `privileged`, `hostNetwork`, `hostPID`.

Manifesty i polityki znajdują się w `infra/kubernetes`, `infra/helm` i `infra/policies`.
