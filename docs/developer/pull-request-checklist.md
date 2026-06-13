# Checklist przed pull requestem

## Kod

- [ ] Zmiana jest ograniczona do wymaganego zakresu.
- [ ] Nie ma przypadkowych refactorów.
- [ ] Nie ma sekretów, tokenów ani lokalnych plików `.env`.
- [ ] Nie ma `__pycache__`, `.ruff_cache`, lokalnych uploadów ani backupów.
- [ ] Nazwy endpointów, modeli i pól są spójne z domeną.

## Backend

- [ ] Każdy zasób organizacyjny ma organization context.
- [ ] Querysety są filtrowane po organizacji.
- [ ] Nie ma globalnego lookupu po samym `public_id`.
- [ ] RBAC jest sprawdzany po stronie backendu.
- [ ] Entitlements są sprawdzane przez centralny moduł.
- [ ] Krytyczne akcje tworzą `AuditLog`.
- [ ] Sekrety nie trafiają do odpowiedzi API ani logów.
- [ ] Migracje są dodane i sprawdzone.

## Frontend

- [ ] Nie ma tokenów w `localStorage`.
- [ ] Żądania modyfikujące dane obsługują CSRF.
- [ ] UI ukrywa akcje niedostępne dla roli użytkownika.
- [ ] UI nie jest jedyną warstwą autoryzacji.
- [ ] Błędy 403/404 są neutralne i nie ujawniają cudzych zasobów.

## Testy

- [ ] `python manage.py check`
- [ ] `python manage.py makemigrations --check --dry-run`
- [ ] `python manage.py test`
- [ ] Testy RBAC dla ról, których dotyczy zmiana.
- [ ] Test IDOR dla dostępu między organizacjami.
- [ ] Test CSRF, jeśli endpoint modyfikuje dane.
- [ ] Test AuditLog dla krytycznej akcji.
- [ ] Test entitlements, jeśli zmiana dotyczy limitów.

## Security review

- [ ] Czy zmiana wprowadza nowy upload albo przetwarzanie plików?
- [ ] Czy zmiana może dotknąć sekretów?
- [ ] Czy zmiana wpływa na billing albo Stripe?
- [ ] Czy zmiana dodaje nowy webhook?
- [ ] Czy zmiana dotyka deploymentów, domen albo certyfikatów?
- [ ] Czy operator override wymaga 2FA i powodu?
- [ ] Czy logi i AuditLog są bezpieczne?
