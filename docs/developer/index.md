# Developer Documentation

Ten katalog opisuje, jak lokalnie rozwijać platformę i jak dodawać zmiany bez łamania multi-tenancy, RBAC, audytu i zasad bezpieczeństwa.

## Rozdziały

1. [Lokalne uruchomienie](local-development.md)
2. [Struktura repozytorium](repository-structure.md)
3. [Backend development](backend-development.md)
4. [Frontend development](frontend-development.md)
5. [Testy i migracje](testing-and-migrations.md)
6. [Usługi lokalne](local-services.md)
7. [Endpointy, RBAC i multi-tenancy](endpoints-rbac-tenancy.md)
8. [AuditLog i entitlements](auditlog-and-entitlements.md)
9. [Bezpieczeństwo i Definition of Secure Done](security-and-secure-done.md)
10. [Checklist przed pull requestem](pull-request-checklist.md)

## Najważniejsze zasady

- Każdy dostęp do zasobu tenantowego musi mieć kontekst organizacji.
- Nie pobieraj zasobów projektowych globalnym `Project.objects.get(public_id=...)`.
- Backend jest źródłem prawdy dla RBAC, entitlements, billing i tenant isolation.
- UI może ukrywać akcje, ale nie jest mechanizmem autoryzacji.
- Krytyczne akcje muszą tworzyć `AuditLog`.
- Sekrety, tokeny, hasła i kody 2FA nigdy nie trafiają do logów ani metadata audytu.
