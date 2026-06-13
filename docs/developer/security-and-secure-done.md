# Bezpieczeństwo i Definition of Secure Done

## Zasady bezpieczeństwa

- OWASP ASVS Level 2 jest bazą wymagań.
- Każdy tenant musi być izolowany logicznie i operacyjnie.
- Każdy endpoint modyfikujący dane musi wymagać CSRF przy sesjach cookie.
- Nie używaj JWT w `localStorage`.
- Nie przechowuj sekretów w plaintext.
- Nie loguj sekretów.
- Nie ujawniaj istnienia cudzych zasobów.
- Nie licz limitów poza modułem entitlements.
- Nie wykonuj deploymentu, jeśli skan artefaktu blokuje zmianę.
- Operator override wymaga 2FA, powodu i AuditLog.

## Definition of Secure Done

Moduł jest gotowy security-wise, jeśli:

- ma jasno określonego właściciela danych,
- każdy queryset tenantowy filtruje po organizacji,
- role i permissions są sprawdzone po stronie backendu,
- dodano testy pozytywne i negatywne RBAC,
- dodano test IDOR dla dostępu cross-tenant,
- akcje krytyczne tworzą `AuditLog`,
- metadata audytu nie zawiera sekretów,
- endpointy sesyjne wymagają CSRF,
- błędy nie ujawniają danych innych tenantów,
- sekrety są hashowane albo szyfrowane,
- limity są sprawdzane przez entitlements,
- uploady są walidowane po stronie backendu,
- skanowanie artefaktów jest uwzględnione tam, gdzie dotyczy,
- testy przechodzą lokalnie,
- migracje są kompletne i sprawdzone przez `makemigrations --check --dry-run`.

## Przykłady czerwonych flag

- `Project.objects.get(public_id=...)` w endpointzie.
- `Organization.objects.get(public_id=...)` bez membership check.
- `metadata={"token": token}` w AuditLog.
- sprawdzanie roli tylko w UI.
- ręczne liczenie limitów planu w widoku.
- endpoint POST bez CSRF.
- logowanie pełnego payloadu Stripe webhooka.
- zwracanie sekretu projektu po utworzeniu albo aktualizacji.
