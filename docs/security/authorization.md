# Autoryzacja, RBAC i multi-tenancy

## 1. Cel

Ten dokument opisuje zasady autoryzacji dla backendu Django REST Framework. Celem jest uniknięcie IDOR, przypadkowych globalnych zapytań i mieszania danych tenantów.

Podstawowa reguła: każdy dostęp do zasobu organizacyjnego musi mieć jawny `organization context`, a każdy dostęp do zasobu projektowego musi być zawężony przez organizację.

## 2. Zasady multi-tenancy

- Główną granicą tenanta jest `Organization`.
- Użytkownik może należeć do wielu organizacji przez `OrganizationMember`.
- Rola użytkownika jest przypisana per organizacja, nie globalnie.
- Zasoby projektowe, takie jak `Project`, `Environment`, `Deployment`, `Domain`, `BuildJob`, `RuntimeInstance`, `UsageRecord` i `ApiKey`, muszą być filtrowane po `organization`.
- Publiczne UUID nie zastępuje autoryzacji. `public_id` jest tylko identyfikatorem, nie dowodem dostępu.
- Endpoint nie może pobierać zasobu tenantowego bez wcześniejszego ustalenia organizacji.
- Object-level permission musi odrzucać zarówno obiekty z innym `organization_id`, jak i obiekt `Organization`, którego `id` nie zgadza się z kontekstem URL.
- Błędy nie powinny ujawniać, czy zasób istnieje w innej organizacji.

## 3. Zasady RBAC

Centralne mapowanie ról na uprawnienia znajduje się w `apps/api/rbac.py`.

Role bazowe:

- `owner`: pełny dostęp do organizacji, projektów, deploymentów, billing, API keys i członkostw.
- `admin`: zarządzanie projektami, deploymentami, domenami, API keys i członkostwami bez billing manage.
- `developer`: tworzenie i odczyt projektów, deploymenty i logi.
- `billing`: billing view/manage bez dostępu projektowego.
- `viewer`: odczyt projektów, logów i billing view bez zmian.

Organization API stosuje dodatkowe zasady:

- lista organizacji jest filtrowana wyłącznie przez aktywne członkostwo użytkownika;
- szczegóły organizacji są dostępne tylko dla aktywnych członków tej organizacji;
- aktualizacja organizacji wymaga `organization.manage`;
- soft delete organizacji jest dozwolony tylko dla roli `owner`;
- zarządzanie członkami wymaga `member.manage`, czyli w bazowym modelu `owner` albo `admin`;
- nie wolno usunąć ostatniego aktywnego ownera;
- nie wolno obniżyć roli ostatniego aktywnego ownera.

Project API stosuje dodatkowe zasady:

- lista projektów zawsze wymaga `organization_public_id` w URL i aktywnego członkostwa w tej organizacji;
- lista projektów domyślnie ukrywa projekty z `deleted_at` oraz statusem `deleted`;
- utworzenie projektu wymaga `project.create`, czyli w bazowym modelu `owner`, `admin` albo `developer`;
- rola `billing` nie może tworzyć projektów, o ile centralna polityka RBAC nie zostanie jawnie zmieniona;
- rola `viewer` ma tylko odczyt;
- aktualizacja, archiwizacja, przywrócenie i soft delete projektu wymagają `project.manage`;
- lookup projektu musi być wykonywany przez organizację z URL, np. `Project.objects.filter(organization=organization, ...)`;
- tworzenie projektu musi przejść przez moduł entitlements. Brak konfiguracji entitlementów ma być odmową dostępu, a nie domyślnym allow;
- każda akcja mutująca zapisuje `AuditLog`.

Uprawnienia są sprawdzane per akcja przez permission keys, np.:

- `project.view`
- `project.manage`
- `project.create`
- `deployment.write`
- `billing.manage`

API keys mają dwa poziomy ograniczeń:

- tenant binding: klucz należy do jednej organizacji i nie może działać poza nią;
- project binding: jeśli klucz ma `project_id`, nie może działać na innym projekcie nawet w tej samej organizacji.

Viewset może deklarować mapę:

```python
permission_required_by_action = {
    "list": PermissionKey.PROJECT_VIEW,
    "retrieve": PermissionKey.PROJECT_VIEW,
    "create": PermissionKey.PROJECT_CREATE,
    "deploy": PermissionKey.DEPLOYMENT_WRITE,
}
```

## 4. Filtrowanie querysetów

Każdy queryset zasobu tenantowego musi być zawężony do organizacji.

Bezpiecznie:

```python
def get_queryset(self):
    organization = get_organization_from_request(self.request, self)
    require_organization_membership(self.request.user, organization)
    return Project.objects.filter(organization=organization, deleted_at__isnull=True)
```

Niebezpiecznie:

```python
def get_queryset(self):
    return Project.objects.all()
```

Niebezpiecznie:

```python
project = Project.objects.get(public_id=project_public_id)
```

Bezpiecznie:

```python
project = get_object_for_organization_or_404(
    Project,
    organization,
    public_id=project_public_id,
    deleted_at__isnull=True,
)
```

## 5. Helpery

### `require_organization_membership`

Używaj, gdy endpoint wymaga aktywnego członkostwa w organizacji.

```python
organization = get_organization_from_request(request, view)
membership = require_organization_membership(request.user, organization)
```

Helper zwraca aktywne członkostwo albo rzuca błąd autoryzacji.

### `get_object_for_organization_or_404`

Używaj do pobierania każdego zasobu organizacyjnego lub projektowego.

```python
project = get_object_for_organization_or_404(
    Project,
    organization,
    public_id=project_public_id,
)
```

Ten helper najpierw zawęża queryset do organizacji, a dopiero potem wykonuje lookup po `public_id`.

### `get_organization_from_request`

Używaj w widokach, które mają `organization_public_id` w URL.

```python
organization = get_organization_from_request(request, self)
```

Jeżeli endpoint nie ma kontekstu organizacji, nie powinien obsługiwać zasobów tenantowych.

## 6. Permission classes DRF

Dostępne klasy:

- `IsOrganizationMember`
- `HasOrganizationRole`
- `HasOrganizationPermission`
- `CanManageBilling`
- `CanManageProjects`
- `CanDeployProject`
- `CanViewProject`

Przykład:

```python
class ProjectViewSet(ModelViewSet):
    permission_classes = [HasOrganizationPermission]
    permission_required_by_action = {
        "list": PermissionKey.PROJECT_VIEW,
        "retrieve": PermissionKey.PROJECT_VIEW,
        "create": PermissionKey.PROJECT_CREATE,
        "update": PermissionKey.PROJECT_MANAGE,
        "destroy": PermissionKey.PROJECT_MANAGE,
    }

    def get_queryset(self):
        organization = get_organization_from_request(self.request, self)
        return Project.objects.filter(organization=organization, deleted_at__isnull=True)
```

Dla akcji specjalnej:

```python
class DeploymentView(APIView):
    permission_classes = [CanDeployProject]
```

## 7. Czego nie wolno robić

- Nie wolno używać `Project.objects.get(public_id=...)` bez filtra organizacji.
- Nie wolno ufać `organization_id` przekazanemu w body requestu.
- Nie wolno filtrować danych tenantowych wyłącznie w UI.
- Nie wolno zwracać globalnych list projektów, domen, deploymentów, faktur, logów ani API keys.
- Nie wolno zwracać globalnej listy organizacji; lista musi wynikać z `OrganizationMember`.
- Nie wolno sprawdzać wyłącznie `request.user.is_authenticated` dla zasobów organizacyjnych.
- Nie wolno używać globalnych ról użytkownika do decyzji tenantowych.
- Nie wolno zakładać, że posiadanie UUID zasobu oznacza prawo dostępu.
- Nie wolno traktować API key z poprawnym scope jako globalnego w organizacji, jeśli klucz jest przypisany do konkretnego projektu.
- Nie wolno wykonywać jobów asynchronicznych bez ponownej walidacji tenant context.

## 8. Przykłady

### Bezpieczne pobranie projektu

```python
class ProjectDetail(APIView):
    permission_classes = [CanViewProject]

    def get(self, request, organization_public_id, project_public_id):
        organization = get_organization_from_request(request, self)
        project = get_object_for_organization_or_404(
            Project,
            organization,
            public_id=project_public_id,
            deleted_at__isnull=True,
        )
        self.check_object_permissions(request, project)
        return Response({"slug": project.slug})
```

### Niebezpieczne pobranie projektu

```python
class ProjectDetail(APIView):
    def get(self, request, project_public_id):
        project = Project.objects.get(public_id=project_public_id)
        return Response({"slug": project.slug})
```

Problem: jeśli atakujący pozna `public_id` projektu innej organizacji, endpoint zwróci cudzy zasób.

### Bezpieczna autoryzacja per akcja

```python
class ProjectViewSet(ModelViewSet):
    permission_classes = [HasOrganizationPermission]
    permission_required_by_action = {
        "list": PermissionKey.PROJECT_VIEW,
        "create": PermissionKey.PROJECT_CREATE,
    }
```

### Niebezpieczna autoryzacja per metoda HTTP

```python
if request.method == "POST":
    allow = request.user.is_authenticated
```

Problem: metoda HTTP nie opisuje intencji biznesowej. Dwie akcje `POST` mogą wymagać różnych uprawnień.

## 9. Testy wymagane dla nowych modułów

Każdy moduł tenantowy musi mieć testy:

- użytkownik bez członkostwa dostaje `403`;
- użytkownik z rolą bez wymaganego uprawnienia dostaje `403`;
- dostęp do zasobu innej organizacji przez `public_id` zwraca `404` albo `403` bez ujawnienia danych;
- API key przypisany do projektu nie może odczytać ani zmienić innego projektu w tej samej organizacji;
- queryset listujący zwraca wyłącznie zasoby organizacji z URL;
- queryset listujący organizacje zwraca wyłącznie organizacje, w których użytkownik ma aktywne członkostwo;
- testy członkostwa obejmują owner/admin/developer/billing/viewer oraz użytkownika spoza organizacji;
- testy członkostwa blokują usunięcie lub downgrade ostatniego ownera;
- każda akcja viewsetu ma przypisany permission key;
- job asynchroniczny ponownie sprawdza organizację i ownership zasobu.
