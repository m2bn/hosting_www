# API keys

## 1. Cel

API keys służą do dostępu maszynowego do API platformy. Klucze mogą być przypisane do całej organizacji albo do jednego projektu.

Klucz API nie zastępuje RBAC ani tenant isolation. Jest dodatkowym ograniczeniem nad użytkownikiem, który utworzył klucz.

## 2. Format i przechowywanie

Pełna wartość klucza ma format:

```text
<prefix>.<secret>
```

W bazie przechowywane są tylko:

- `prefix`: jawny identyfikator klucza;
- `key_hash`: hash pełnej wartości klucza;
- `scopes`;
- `expires_at`;
- `last_used_at`;
- `revoked_at`;
- `status`.

Pełna wartość klucza jest pokazywana tylko raz: po utworzeniu albo rotacji. Listy i szczegóły kluczy pokazują tylko prefix i metadane.

## 3. Zakres klucza

Klucz organizacyjny:

- ma `organization`;
- nie ma `project`;
- może działać tylko w tej organizacji;
- nadal wymaga odpowiedniego scope.

Klucz projektowy:

- ma `organization` i `project`;
- może działać tylko na tym projekcie;
- nie może odczytać ani zmienić innego projektu w tej samej organizacji;
- nie może działać w innej organizacji.

## 4. Scopes

Scopes używają tych samych nazw co permission keys, np.:

- `project.view`;
- `project.manage`;
- `deployment.write`;
- `api_key.manage`;
- `billing.manage`.

Akcja jest dozwolona tylko wtedy, gdy:

- użytkownik powiązany z kluczem ma wymagane RBAC permission w organizacji;
- klucz ma wymagany scope;
- organizacja i projekt pasują do bindingu klucza;
- klucz jest aktywny, nieodwołany i niewygasły.

## 5. Rotacja i unieważnienie

Rotacja:

- generuje nowy prefix i secret;
- zapisuje tylko hash nowej pełnej wartości;
- unieważnia starą pełną wartość;
- zwraca nową pełną wartość tylko raz;
- zapisuje `AuditLog` z akcją `api_key.rotated`.

Unieważnienie:

- ustawia status `revoked`;
- ustawia `revoked_at`;
- blokuje dalszą autoryzację;
- zapisuje `AuditLog` z akcją `api_key.deleted`.

## 6. Rate limiting

Autoryzacja API key ma limit per `prefix`.

Limit jest konfigurowany przez:

- `API_KEY_RATE_LIMIT_ATTEMPTS`;
- `API_KEY_RATE_LIMIT_WINDOW_SECONDS`.

Limit dotyczy także poprawnych requestów. Dzięki temu pojedynczy wyciek klucza ma ograniczony wpływ operacyjny.

## 7. AuditLog

Logujemy:

- utworzenie klucza: `api_key.created`;
- rotację klucza: `api_key.rotated`;
- unieważnienie klucza: `api_key.deleted`;
- użycie klucza do akcji wysokiego ryzyka: `api_key.used_high_risk`.

Za wysokie ryzyko uznajemy m.in.:

- `deployment.write`;
- `project.manage`;
- `billing.manage`;
- `api_key.manage`.

AuditLog może zawierać `prefix`, scope i identyfikator klucza, ale nigdy pełną wartość klucza.

## 8. Czego nie wolno robić

- Nie wolno logować pełnej wartości klucza.
- Nie wolno przechowywać pełnej wartości klucza w bazie.
- Nie wolno pozwolić frontendowi ustalać `organization_id` albo `project_id` poza kontekstem URL.
- Nie wolno traktować poprawnego klucza jako globalnego dostępu do platformy.
- Nie wolno pomijać RBAC użytkownika powiązanego z kluczem.
- Nie wolno pomijać object-level tenant checks przy API key authentication.

## 9. Testy wymagane

Każda zmiana API keys musi utrzymywać testy:

- klucz działa dla poprawnego projektu;
- klucz nie działa dla innego projektu;
- klucz organizacyjny nie działa dla innej organizacji;
- revoked key nie działa;
- expired key nie działa;
- scope jest wymagany;
- hash jest zapisany zamiast plaintext;
- pełna wartość klucza jest pokazywana tylko raz;
- API key nie omija RBAC ani tenant isolation;
- rate limiting per key działa;
- akcje wysokiego ryzyka zapisują AuditLog.
