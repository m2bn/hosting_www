# ADR-0002: Next.js + TypeScript jako dashboard

## Status

Accepted

## Kontekst

Platforma potrzebuje dashboardu dla użytkowników, organizacji i operatorów. Dashboard będzie obsługiwał projekty, deploymenty, domeny, logi, billing, API keys, role, ustawienia bezpieczeństwa i przepływy administracyjne.

Frontend musi być typowany, łatwy do rozwijania, zgodny z nowoczesnymi wzorcami UX oraz gotowy na integrację z REST API control plane.

## Decyzja

Dashboard budujemy w Next.js z TypeScript.

## Konsekwencje pozytywne

- TypeScript ogranicza błędy kontraktów API i ułatwia refaktoryzację dużego dashboardu.
- Next.js zapewnia dojrzały ekosystem routingu, renderowania, bundlingu i optymalizacji.
- Framework dobrze wspiera komponentową architekturę UI i stopniowe rozdzielanie panelu użytkownika od panelu admina.
- Możliwe jest generowanie typów klienta API na podstawie kontraktów backendu.
- Next.js ma szerokie wsparcie narzędziowe, testowe i hostingowe.

## Konsekwencje negatywne

- Next.js wprowadza złożoność renderowania server/client components i zarządzania granicami danych.
- Nieostrożne użycie SSR może przypadkowo ujawnić dane użytkownika lub tenant context.
- Dashboard może stać się zbyt gruby, jeśli logika autoryzacji zostanie przeniesiona do UI.
- Aktualizacje frameworka i zależności frontendowych wymagają aktywnego zarządzania supply chain.

## Alternatywy

- Vite + React: prostszy model SPA, ale mniej gotowych mechanizmów aplikacyjnych niż Next.js.
- Remix: dobry model webowy i formularze, ale mniejszy ekosystem w niektórych zespołach.
- Vue/Nuxt: produktywny stos, ale mniej spójny z preferencją TypeScript/React.
- Server-rendered Django templates: prostsze dla MVP, ale mniej ergonomiczne dla złożonego dashboardu operacyjnego.

## Wpływ na bezpieczeństwo

- UI nie jest źródłem prawdy dla autoryzacji; wszystkie decyzje RBAC muszą być egzekwowane przez backend.
- Dashboard musi używać bezpiecznych cookies, CSRF protection i nie przechowywać tokenów sesyjnych w `localStorage`.
- Wymagane są security headers, CSP, ochrona przed XSS i bezpieczne renderowanie logów oraz danych kontrolowanych przez klientów.
- Dane pobierane server-side muszą być izolowane per request, aby uniknąć wycieku między sesjami lub tenantami.
- Frontend build pipeline musi obejmować dependency scanning, secret scanning i kontrolę zależności npm.
