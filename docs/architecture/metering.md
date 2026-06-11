# Metering Service

## Cel

Metering-service zbiera i agreguje zużycie zasobów platformy per organizacja i projekt. Dane są podstawą limitów planu, alertów, raportów billingowych i decyzji o blokadzie lub throttlingu.

## Zakres

- storage per project,
- transfer per domain/project,
- CPU seconds runtime,
- memory GB-hours runtime,
- agregacja godzinowa,
- agregacja dzienna,
- zapis do `UsageRecord`,
- alerty przy 80%, 90% i 100% limitu,
- metryki Prometheus.

## Model Danych

Każdy `UsageRecord` musi zawierać:

- `organization`,
- `project`,
- opcjonalnie `environment`,
- `metric`,
- `quantity`,
- `period_start`,
- `period_end`,
- `source`.

Dane bez `organization` i `project` są odrzucane.

## Limity

Metering korzysta z lokalnych limitów planu przez moduł `entitlements`. Endpointy nie liczą limitów samodzielnie.

- `storage_gb` mapuje się na `storage_gb_hours`.
- `transfer_gb` mapuje się na `egress_bytes`.
- limity runtime są raportowane jako usage CPU/RAM i mogą być użyte do throttlingu runtime.

Po przekroczeniu 100% `can_deploy_project(project)` odmawia deploymentu.

## Alerty

Przy progach 80%, 90% i 100% tworzony jest `SecurityEvent` oraz wpis `AuditLog`.

## Dostęp

- `owner`, `admin`, `billing` mogą odczytywać usage.
- `viewer` może odczytywać usage tylko, jeśli `USAGE_VIEWER_CAN_VIEW_USAGE=true`.
- Użytkownik spoza organizacji otrzymuje `404`.

## Prometheus

Endpoint organizacyjny eksportuje:

```text
platform_usage_quantity{organization="<id>",project="<id>",metric="<metric>"} <quantity>
```

Eksport jest tenant-scoped i wymaga tych samych uprawnień co API usage.
