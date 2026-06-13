# Frontend Development

## Uruchomienie

```powershell
cd apps/dashboard
npm install
npm run dev -- --hostname 127.0.0.1 --port 3000
```

## Testy i checki

```powershell
cd apps/dashboard
npm run lint
npm run typecheck
npm run test
npm run test:e2e
```

## Klient API

Dashboard komunikuje się z backendem przez sesje cookie httpOnly. Nie przechowuj tokenów w `localStorage`, `sessionStorage` ani w stanie React.

Każde żądanie modyfikujące dane powinno:

- wysyłać cookies,
- mieć poprawny CSRF token,
- obsługiwać `401`, `403` i `404`,
- pokazywać bezpieczny komunikat błędu.

## RBAC w UI

UI może ukrywać przyciski, których użytkownik nie powinien używać, ale backend nadal musi autoryzować każdą akcję.

Przykład:

- viewer nie widzi przycisku deploymentu,
- billing nie widzi przycisku deploymentu,
- developer nie widzi akcji billingowych,
- owner/admin widzą akcje zależnie od modułu.

## Obsługa 403 i 404

Nie pokazuj użytkownikowi, że cudzy zasób istnieje. Dla błędów 403/404 używaj neutralnego komunikatu, na przykład:

```text
Nie masz dostępu do tego zasobu albo zasób nie istnieje.
```

## Formularze

Walidacja frontendowa poprawia UX, ale nie zastępuje walidacji backendowej. Backend musi ponownie sprawdzić pliki, limity, domeny, role, entitlements i CSRF.
