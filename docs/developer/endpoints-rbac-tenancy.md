# Endpointy, RBAC i multi-tenancy

## Zasada główna

Każdy dostęp do zasobu organizacyjnego wymaga organization context. Nie wolno pobierać zasobów projektowych globalnie po samym `public_id`.

## Bezpieczny endpoint organizacyjny

Przykład wzorca dla endpointu, który aktualizuje projekt:

```python
from django.views import View

from apps.api import audit_log
from apps.api.auth_utils import json_error, json_ok, parse_json_body
from apps.api.organization_views import get_user_organization_or_404, require_authenticated, require_permission
from apps.api.project_views import get_project_for_organization_or_404
from apps.api.rbac import PermissionKey


class ProjectNameView(View):
    def patch(self, request, organization_public_id, project_public_id):
        if error := require_authenticated(request):
            return error

        organization = get_user_organization_or_404(request.user, organization_public_id)
        if error := require_permission(request, organization, PermissionKey.PROJECT_MANAGE):
            return error

        project = get_project_for_organization_or_404(organization, project_public_id)
        data = parse_json_body(request)
        if data is None:
            return json_error("Invalid JSON.", code="invalid_json")

        project.name = (data.get("name") or "").strip()
        project.save(update_fields=["name", "updated_at"])

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
        return json_ok({"public_id": str(project.public_id), "name": project.name})
```

## Bezpieczne filtrowanie querysetu

Bezpiecznie:

```python
from apps.api.tenancy import get_object_for_organization_or_404
from apps.api.models import Project

project = get_object_for_organization_or_404(
    Project,
    organization,
    public_id=project_public_id,
    deleted_at__isnull=True,
)
```

Niebezpiecznie:

```python
project = Project.objects.get(public_id=project_public_id)
```

Drugi przykład jest podatny na IDOR, bo nie sprawdza organizacji.

## Role

Role bazowe:

- `owner`: pełna kontrola nad organizacją.
- `admin`: zarządzanie projektami, członkami i technicznymi zasobami.
- `developer`: projekty, deploymenty, sekrety i logi.
- `billing`: płatności, faktury i usage.
- `viewer`: odczyt wybranych zasobów.

Centralne mapowanie ról znajduje się w `apps/api/rbac.py`.

## Dodanie testu IDOR

Minimalny wzorzec:

```python
def test_user_from_org_a_cannot_update_project_from_org_b(self):
    self.client.force_login(self.user_from_org_a)
    response = self.client.patch(
        reverse(
            "project-detail",
            kwargs={
                "organization_public_id": self.org_b.public_id,
                "project_public_id": self.project_b.public_id,
            },
        ),
        data={"name": "attacker change"},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=self.csrf(),
    )

    self.assertEqual(response.status_code, 404)
    self.project_b.refresh_from_db()
    self.assertNotEqual(self.project_b.name, "attacker change")
```

Test powinien używać realnych modeli i realnego endpointu, jeśli endpoint istnieje.
