# ADR-0001: Django + DRF jako backend control plane

## Status

Accepted

## Kontekst

Control plane platformy zarządza użytkownikami, organizacjami, projektami, billingiem, domenami, certyfikatami, deploymentami, audytem i integracją z Kubernetes. Wymaga dojrzałego frameworka webowego, sprawdzonego ORM, dobrego modelu migracji, solidnego ekosystemu bezpieczeństwa oraz szybkiego budowania API.

Backend musi wspierać OWASP ASVS Level 2, centralną autoryzację, audyt zdarzeń, integracje asynchroniczne i możliwość późniejszego podniesienia wymagań do ASVS Level 3.

## Decyzja

Backend control plane budujemy w Django z Django REST Framework jako główną warstwą API.

## Konsekwencje pozytywne

- Django dostarcza sprawdzone mechanizmy bezpieczeństwa: auth, hashowanie haseł, ochronę CSRF, middleware, walidację formularzy i bezpieczne domyślne wzorce.
- DRF przyspiesza budowę REST API, serializację, walidację i testowanie endpointów.
- Django ORM oraz migracje dobrze pasują do relacyjnego modelu organizacji, projektów, ról, billing state i audytu.
- Ekosystem Django ma dojrzałe biblioteki dla administracji, RBAC, integracji z Celery, PostgreSQL i observability.
- Framework jest dobrze znany zespołom backendowym, co obniża ryzyko operacyjne.
- Django Admin może być użyty jako narzędzie wewnętrzne na wczesnym etapie, po silnym ograniczeniu dostępu i audycie.

## Konsekwencje negatywne

- Django jest aplikacją synchroniczną z natury, więc część operacji I/O-heavy wymaga Celery albo świadomego użycia async.
- DRF może prowadzić do zbyt dużej logiki w serializerach i viewsetach, jeśli nie ustalimy granic serwisowych.
- Monolityczny control plane może rosnąć zbyt szybko bez modularnej struktury aplikacji.
- Django Admin nie powinien być traktowany jako docelowy panel operatorski bez dodatkowych zabezpieczeń.
- Wysoka elastyczność ORM może ukrywać kosztowne zapytania i problemy N+1.

## Alternatywy

- FastAPI: bardzo dobry dla async API i typowania, ale wymaga większej liczby decyzji infrastrukturalnych wokół auth, admina, migracji i konwencji.
- NestJS: spójny z TypeScript, ale słabsze dopasowanie do dojrzałego modelu relacyjnego i Django-like admin/backoffice.
- Ruby on Rails: podobna produktywność do Django, ale mniej naturalny wybór przy planowanym ekosystemie Python/Celery.
- Go z chi/routerem: wysoka wydajność i prosty deployment, ale większy koszt budowy funkcji SaaS control plane od zera.

## Wpływ na bezpieczeństwo

- Django daje mocny baseline dla ASVS L2, ale wymaga rygorystycznej konfiguracji `SECURE_*`, cookies, CSRF, HSTS, CORS i sesji.
- Autoryzacja tenantowa nie może polegać wyłącznie na mechanizmach DRF permissions; potrzebujemy centralnych testowalnych reguł RBAC.
- Każdy queryset musi być filtrowany tenant context, aby uniknąć IDOR.
- Admin endpoints wymagają 2FA, krótszych sesji, pełnego audytu i ograniczenia dostępu.
- Należy wymusić testy bezpieczeństwa dla serializerów, permissions, object-level authorization i operacji asynchronicznych.
