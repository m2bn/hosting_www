# Notification Service

## Cel

Notification-service odpowiada za transakcyjne wiadomości e-mail wysyłane przez platformę. Jest projektowany jako outbox z możliwością późniejszego przeniesienia przetwarzania do Celery/RabbitMQ.

## Obsługiwane Zdarzenia

- `email_verification`
- `password_reset`
- `organization_invitation`
- `payment_failed`
- `invoice_paid`
- `deployment_failed`
- `deployment_succeeded`
- `domain_verified`
- `certificate_failed`
- `limit_80`
- `limit_90`
- `limit_100`

## Przepływ

1. Moduł biznesowy tworzy jednorazowy token, jeśli jest potrzebny.
2. Token jest zapisywany jako hash w modelu domenowym, np. `AuthToken`.
3. Notification-service renderuje wiadomość i wysyła ją przez skonfigurowany backend e-mail.
4. `NotificationMessage` przechowuje status kolejki, próby, szablon i zredagowany kontekst.
5. Tokeny i linki z tokenami są redagowane w kontekście kolejki oraz logach.

## Retry

Wiadomość po błędzie wraca do statusu `queued`, dopóki liczba prób nie przekroczy `NOTIFICATION_MAX_RETRY_ATTEMPTS`. Docelowo retry powinien być obsługiwany przez Celery z exponential backoff.

## Rate Limiting

Rate limiting działa per recipient hash:

- `NOTIFICATION_RATE_LIMIT_ATTEMPTS`
- `NOTIFICATION_RATE_LIMIT_WINDOW_SECONDS`

Po przekroczeniu limitu tworzony jest rekord `rate_limited` i wpis AuditLog.

## Bezpieczeństwo

- Reset hasła i email verification nie ujawniają, czy e-mail istnieje.
- Tokeny jednorazowe są przechowywane jako hash.
- Tokeny nie są zapisywane w `NotificationMessage.context`.
- Tokeny nie są logowane.
- Krytyczne powiadomienia są audytowane.

## Operacyjnie

W pierwszej wersji wysyłka może działać synchronicznie przez outbox. W produkcji worker powinien cyklicznie wywoływać `process_queued_notifications()` albo wykonywać pojedyncze wiadomości z Celery.
