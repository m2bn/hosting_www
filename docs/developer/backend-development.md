# Backend Development

## Styl pracy

Backend jest control plane platformy. Każda zmiana powinna być projektowana z myślą o multi-tenancy, bezpieczeństwie i audycie.

Przy dodawaniu nowej funkcji sprawdź:

- jaki model domenowy jest właścicielem danych,
- czy zasób należy do organizacji i projektu,
- jakie role mogą go czytać albo modyfikować,
- czy akcja wymaga entitlements,
- czy akcja powinna tworzyć `AuditLog`,
- jakie testy IDOR są potrzebne.

## Modele

Modele tenantowe powinny mieć:

- `organization`,
- opcjonalnie `project`,
- `public_id` jako publiczny identyfikator,
- `created_at` i `updated_at`,
- indeksy pod najczęstsze zapytania,
- constraints scoped per tenant.

Nie używaj internal `id` w URL-ach publicznego API.

## Widoki

W istniejącym kodzie wiele endpointów używa klasycznych Django `View`. DRF permissions istnieją dla warstwy autoryzacji i testów, ale nowe endpointy powinny zachowywać te same zasady:

- najpierw `require_authenticated`,
- potem pobranie organizacji przez membership,
- potem sprawdzenie permission/role,
- potem pobranie zasobu filtrowanego po organizacji.

## Błędy API

Używaj `json_error(...)` i stabilnych kodów błędów. Nie ujawniaj informacji, czy cudzy zasób istnieje. Dla zasobów spoza organizacji preferuj `404`, nie `403`.

## Sekrety

Nie zapisuj sekretów w plaintext. Nie dodawaj sekretów do:

- logów,
- `AuditLog.metadata`,
- odpowiedzi API,
- wyjątków widocznych dla użytkownika,
- testowych snapshotów.
