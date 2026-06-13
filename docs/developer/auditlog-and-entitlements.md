# AuditLog i entitlements

## AuditLog

AuditLog zapisuje ważne działania użytkowników, API keys, operatorów i systemu. Krytyczne akcje muszą być audytowane.

Loguj między innymi:

- logowanie i logout,
- zmiany członków i ról,
- tworzenie, aktualizację i usuwanie projektów,
- deployment, rollback i blokady deploymentu,
- domeny i certyfikaty,
- billing,
- API keys,
- sekrety,
- export/usuwanie danych,
- działania operatora,
- abuse handling i override skanów.

## Dodanie AuditLog

```python
from apps.api import audit_log

audit_log.record(
    action=audit_log.AuditAction.PROJECT_UPDATED,
    request=request,
    actor=request.user,
    organization=organization,
    project=project,
    target_type="project",
    target_id=project.public_id,
    metadata={"fields": ["name"]},
)
```

Nie dodawaj do metadata:

- haseł,
- tokenów,
- kluczy API,
- sekretów projektu,
- kodów 2FA,
- prywatnych kluczy,
- pełnych payloadów z danymi osobowymi.

## Entitlements

Entitlements określają, co organizacja może zrobić w ramach planu i statusu subskrypcji.

Logika znajduje się w `apps/api/entitlements.py`. Endpointy nie powinny samodzielnie liczyć limitów.

Poprawnie:

```python
from apps.api.entitlements import can_create_project

decision = can_create_project(organization)
if not decision.allowed:
    return json_error("Project creation is not allowed by current entitlements.", status=403, code="entitlement_denied")
```

Niepoprawnie:

```python
if organization.projects.count() >= 10:
    return json_error("Limit exceeded")
```

Drugi przykład omija centralną politykę planów, grace period i status subskrypcji.

## Deployment entitlements

Deploymenty powinny używać:

- `can_deploy_static_site(project)`,
- `can_deploy_project(project)`,
- `can_use_container_deployment(organization)`.

Statusy `canceled` i `unpaid` powinny blokować nowe deploymenty i nowe zasoby zgodnie z polityką.
