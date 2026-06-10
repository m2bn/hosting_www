# ADR-0007: Celery + RabbitMQ jako system zadań asynchronicznych

## Status

Accepted

## Kontekst

Platforma wykonuje wiele operacji asynchronicznych: provisioning Kubernetes, obsługę webhooków, deploymenty, buildy, metering, wysyłkę e-maili, rewalidację domen, odnowienia certyfikatów, reconciliation billing i zadania administracyjne.

Potrzebujemy sprawdzonego systemu kolejek dobrze współpracującego z Django.

## Decyzja

Zadania asynchroniczne realizujemy przez Celery z RabbitMQ jako brokerem.

## Konsekwencje pozytywne

- Celery jest dojrzałym standardem w ekosystemie Python/Django.
- RabbitMQ dobrze obsługuje durable queues, routing, retry, dead-lettering i backpressure.
- Łatwo oddzielić workerów według klas zadań, priorytetów i poziomu zaufania.
- Celery wspiera retry, harmonogramy i idempotentne wzorce przetwarzania.
- Pasuje do operacji provisioningowych, które nie powinny blokować requestów HTTP.

## Konsekwencje negatywne

- Celery wymaga dyscypliny idempotencji, timeouts i kontroli retry.
- RabbitMQ jest dodatkowym komponentem operacyjnym wymagającym monitoringu i backupu konfiguracji.
- Błędy serializacji albo zbyt duże payloady mogą obniżać stabilność kolejek.
- Zadania mogą wykonać się po zmianie uprawnień lub usunięciu zasobu, jeśli nie sprawdzimy stanu przy wykonaniu.

## Alternatywy

- Redis jako broker Celery: prostszy, ale słabszy dla trwałości i bardziej złożonych wzorców kolejek.
- Dramatiq/RQ: prostsze biblioteki, ale mniejszy ekosystem niż Celery.
- Kafka: mocny event streaming, ale zbyt ciężki jako podstawowa kolejka zadań MVP.
- Cloud-managed queues: mniej operacji, ale większe związanie z providerem.

## Wpływ na bezpieczeństwo

- Payloady zadań muszą zawierać minimalne dane i nie mogą zawierać sekretów.
- Worker musi ponownie sprawdzać tenant context, stan zasobu i uprawnienia, jeśli zadanie wykonuje operację wrażliwą.
- Zadania muszą być idempotentne, aby retry nie powodował podwójnych operacji billingowych lub provisioningowych.
- Kolejki muszą być odseparowane według poziomu zaufania, np. billing, deployment, build, notifications.
- Dostęp do RabbitMQ musi wymagać uwierzytelnienia, TLS w produkcji i minimalnych uprawnień per worker.
