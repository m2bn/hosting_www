# Secrets management

## 1. Cel

Secrets management przechowuje zmienne środowiskowe aplikacji klientów w sposób bezpieczny dla multi-tenant SaaS.

Sekrety są przypisane do:

- organizacji;
- projektu;
- środowiska.

Runtime może otrzymać wyłącznie sekrety należące do konkretnego projektu i środowiska.

## 2. Model danych

`ProjectSecret` przechowuje:

- nazwę zmiennej środowiskowej;
- organizację;
- projekt;
- środowisko;
- metadane;
- aktualny numer wersji;
- status i soft delete.

`ProjectSecretVersion` przechowuje:

- numer wersji;
- zaszyfrowaną wartość;
- autora wersji;
- timestamps.

Wartość sekretu nigdy nie jest przechowywana plaintextem.

## 3. Szyfrowanie

Wartości sekretów są szyfrowane przed zapisem przez Fernet.

Źródło klucza:

- preferowane: `SECRETS_ENCRYPTION_KEY`;
- fallback lokalny: klucz pochodny z `SECRET_KEY`.

Docelowo moduł może zostać podmieniony na integrację z zewnętrznym secrets managerem. Kontrakt API i runtime injection nie powinny wtedy ulec zmianie.

## 4. API

API może zwracać tylko:

- `public_id`;
- `name`;
- `environment_id`;
- `metadata`;
- `current_version`;
- `created_at`;
- `updated_at`.

API nigdy nie zwraca:

- wartości sekretu;
- ciphertextu;
- poprzednich wersji wartości.

## 5. Walidacja nazw

Nazwy sekretów muszą być poprawnymi nazwami zmiennych środowiskowych:

```text
^[A-Z_][A-Z0-9_]{0,127}$
```

Przykłady poprawne:

- `DATABASE_URL`;
- `API_TOKEN`;
- `_INTERNAL_FLAG`.

Przykłady niedozwolone:

- `database_url`;
- `1TOKEN`;
- `TOKEN-WITH-DASH`.

## 6. RBAC

Zarządzanie sekretami wymaga `secret.manage`.

W bazowych rolach:

- `owner`: może zarządzać sekretami;
- `admin`: może zarządzać sekretami;
- `developer`: może zarządzać sekretami;
- `viewer`: nie może tworzyć, aktualizować, usuwać ani rotować sekretów;
- `billing`: nie zarządza sekretami.

## 7. Wersjonowanie i rotacja

Utworzenie sekretu tworzy wersję `1`.

Aktualizacja wartości albo rotacja tworzy kolejną wersję:

- stara wersja pozostaje w bazie jako ciphertext;
- `current_version` wskazuje najnowszą wersję;
- runtime injection używa najnowszej wersji.

Usunięcie sekretu ustawia `deleted_at` i status `deleted`.

## 8. Runtime injection

Runtime injection musi filtrować po:

- `organization`;
- `project`;
- `environment`;
- `status=active`;
- `deleted_at IS NULL`.

Sekret projektu A nie może zostać wstrzyknięty do projektu B, nawet jeśli nazwa zmiennej jest taka sama.

## 9. AuditLog i logi

AuditLog zapisuje:

- utworzenie sekretu;
- aktualizację sekretu;
- rotację sekretu;
- usunięcie sekretu.

AuditLog może zawierać:

- nazwę sekretu;
- identyfikator środowiska;
- numer wersji.

AuditLog nie może zawierać:

- wartości sekretu;
- ciphertextu;
- tokenów, haseł ani kluczy z metadanych.

Logi aplikacyjne nie mogą zawierać wartości sekretów ani wyjątków z pełnym payloadem requestu.

## 10. Testy wymagane

Każda zmiana modułu musi utrzymywać testy:

- sekret nie jest zapisany plaintextem;
- API nie zwraca wartości sekretu;
- sekret projektu A nie jest dostępny dla projektu B;
- `viewer` nie może tworzyć sekretów;
- `developer` może zarządzać sekretami;
- wartości sekretów nie pojawiają się w AuditLog metadata;
- wartości sekretów nie pojawiają się w logach;
- rotacja tworzy nową wersję;
- runtime injection jest ograniczone do konkretnego projektu i środowiska.
