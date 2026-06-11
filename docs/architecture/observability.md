# Observability Baseline

## Cel

Observability baseline ma zapewnić spójny obraz działania control plane, workerów, provisionera i runtime klientów. Każdy sygnał musi być możliwy do korelacji przez `request_id` lub `correlation_id`.

## Sygnały

### Logs

- Wszystkie logi aplikacyjne są emitowane jako JSON.
- Każdy log powinien zawierać `timestamp`, `level`, `logger`, `message`.
- Dla requestów API wymagane są `request_id` i `correlation_id`.
- Dla operacji tenant-scoped zalecane są `organization_public_id`, `project_public_id`, `environment_public_id`.
- Sekrety, tokeny, hasła, kody 2FA, API keys i wartości sekretów klientów muszą być redagowane.
- Logi trafiają do Loki przez Promtail lub OpenTelemetry Collector.

### Traces

OpenTelemetry powinien obejmować:

- requesty API Django/DRF,
- taski Celery,
- webhooki Stripe,
- deploymenty,
- provisioning Kubernetes,
- zapytania do PostgreSQL,
- wywołania Stripe, registry, S3/MinIO i Kubernetes API.

Trace context jest propagowany przez:

- nagłówki HTTP `traceparent` i `tracestate`,
- `X-Request-ID`,
- Celery headers: `correlation_id`, `traceparent`.

### Metrics

Metryki są eksportowane w formacie Prometheus. Nazwy powinny używać prefiksu `platform_`.

## Metryki Techniczne

- `platform_http_requests_total`
- `platform_http_request_duration_seconds`
- `platform_http_errors_total`
- `platform_database_query_duration_seconds`
- `platform_queue_depth`
- `platform_celery_task_duration_seconds`
- `platform_celery_task_failures_total`

## Metryki Biznesowe

- `platform_deployments_total`
- `platform_deployment_failures_total`
- `platform_active_projects`
- `platform_billing_payment_failures_total`
- `platform_usage_storage_gb`
- `platform_usage_transfer_gb`
- `platform_active_subscriptions`

## Alerty

- wysoki error rate API,
- rosnąca kolejka buildów,
- failujące webhooki Stripe,
- certyfikaty bez odnowienia lub blisko expiry,
- storage powyżej 80/90/100% limitu,
- wysokie latency bazy,
- deployment failure rate powyżej progu.

## Dashboard Grafana

Dashboard bazowy powinien pokazywać:

- API RPS, p95 latency i error rate,
- DB p95 latency,
- kolejki Celery/RabbitMQ,
- task duration i task failures,
- deployment success/failure,
- Stripe webhook failures,
- cert-manager failures i expiring certificates,
- storage/transfer usage,
- aktywne projekty i subskrypcje.

## Loki

Log labels powinny być ograniczone, aby nie tworzyć wysokiej kardynalności:

- `service`,
- `environment`,
- `level`,
- `namespace`,
- `pod`.

`request_id`, `organization_public_id` i `project_public_id` powinny pozostać polami JSON, nie labelami Loki.

## Retencja

- Metryki techniczne: minimum 30 dni.
- Metryki biznesowe i billingowe: minimum 13 miesięcy albo zgodnie z wymaganiami finansowymi.
- Logi aplikacyjne: minimum 30 dni; AuditLog jest oddzielnym źródłem prawdy i ma dłuższą retencję.
- Trace sampling w produkcji: head sampling 5-10% oraz tail sampling dla błędów.

## Bezpieczeństwo

- Dane osobowe i sekrety nie mogą trafiać do logów, trace attributes ani metryk.
- Dostęp do Grafany, Loki i Prometheus wymaga SSO oraz RBAC operatorów.
- Dashboardy tenant usage muszą używać tenant-scoped API albo jawnych filtrów organizacji.
