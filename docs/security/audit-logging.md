# Audit logging

## 1. Cel

AuditLog jest centralnym, append-only dziennikiem działań użytkowników, API keys, systemu i operatorów platformy. Służy do dochodzeń bezpieczeństwa, rozliczalności operacji, analizy incydentów i spełnienia wymagań OWASP ASVS Level 2.

AuditLog nie zastępuje logów technicznych ani metryk. Jest osobnym rejestrem zdarzeń biznesowych i bezpieczeństwa.

## 2. Centralny helper

Do zapisu zdarzeń należy używać wyłącznie:

```python
from apps.api import audit_log

audit_log.record(
    action=audit_log.AuditAction.PROJECT_CREATED,
    request=request,
    actor=request.user,
    organization=organization,
    project=project,
    target_type="project",
    target_id=project.public_id,
    metadata={"source": "dashboard"},
)
```

Nie należy tworzyć `AuditLog` bezpośrednio w endpointach, workerach ani serwisach domenowych, chyba że kod znajduje się wewnątrz centralnego modułu audytu.

## 3. Wymagane pola

Każde zdarzenie zawiera:

- `actor_type`: `user`, `api_key`, `operator` albo `system`;
- `actor_id`: publiczny identyfikator aktora, jeśli istnieje;
- `organization_id`: organizacja, której dotyczy zdarzenie, jeśli dotyczy;
- `project_id`: projekt, jeśli zdarzenie dotyczy projektu;
- `action`: stabilny klucz akcji;
- `target_type`: typ obiektu docelowego;
- `target_id`: publiczny identyfikator albo bezpieczny identyfikator obiektu docelowego;
- `ip_address`: adres IP klienta lub źródła requestu;
- `user_agent`: user agent requestu;
- `request_id`: identyfikator requestu/korelacji;
- `metadata`: dodatkowe dane bez sekretów;
- `created_at`: czas utworzenia.

## 4. Request ID

`config.request_id.RequestIdMiddleware` ustawia `request.request_id` dla każdego requestu. Jeśli klient przekaże `X-Request-ID`, wartość jest propagowana. W przeciwnym razie generowany jest UUID.

Odpowiedź HTTP zawiera nagłówek:

```text
X-Request-ID: <request-id>
```

Ten sam identyfikator trafia do `AuditLog.request_id` i `AuditLog.correlation_id`.

## 5. Append-only

Na poziomie aplikacji `AuditLog` jest append-only:

- `AuditLog.save()` odrzuca aktualizację istniejącego rekordu;
- `AuditLog.delete()` jest zablokowane;
- `AuditLog.objects.filter(...).update(...)` jest zablokowane;
- `AuditLog.objects.filter(...).delete()` jest zablokowane.

Migracje, backup/restore i administracyjne operacje bazodanowe pozostają poza zwykłym API aplikacji i muszą być kontrolowane operacyjnie.

## 6. Metadata i sekrety

`audit_log.record(...)` sanitizuje metadata rekurencyjnie. Następujące klucze są redagowane:

- `password`
- `current_password`
- `new_password`
- `token`
- `secret`
- `api_key`
- `authorization`
- `recovery_code`
- `totp`
- `code`

Przykład:

```python
metadata={
    "password": "secret",
    "nested": {"token": "abc"},
}
```

Zostanie zapisane jako:

```python
metadata={
    "password": "[REDACTED]",
    "nested": {"token": "[REDACTED]"},
}
```

Nie wolno umieszczać pełnych payloadów requestów w metadata.

## 7. Akcje audytowe

Centralne stałe akcji znajdują się w `apps/api/audit_log.py` w klasie `AuditAction`.

Wymagane obszary:

- logowanie;
- logout;
- nieudane logowanie;
- reset hasła;
- zmiana hasła;
- weryfikacja e-maila;
- włączenie 2FA;
- wyłączenie 2FA;
- użycie recovery code;
- utworzenie organizacji;
- aktualizacja organizacji;
- usunięcie organizacji;
- dodanie członka;
- usunięcie członka;
- zmiana roli;
- utworzenie projektu;
- aktualizacja projektu;
- usunięcie projektu;
- deployment;
- rollback;
- dodanie domeny;
- usunięcie domeny;
- zmiany billingowe;
- utworzenie API key;
- usunięcie API key;
- rotacja API key;
- zmiany sekretów;
- akcje operatora platformy.

Aktualne endpointy authentication są już zintegrowane z centralnym helperem. Przyszłe moduły biznesowe muszą używać tych samych stałych i helpera `audit_log.record(...)`.

## 8. Przykłady

### Użytkownik

```python
audit_log.record(
    action=audit_log.AuditAction.PROJECT_UPDATED,
    request=request,
    actor=request.user,
    organization=project.organization,
    project=project,
    target_type="project",
    target_id=project.public_id,
)
```

### API key

```python
audit_log.record(
    action=audit_log.AuditAction.DEPLOYMENT_STARTED,
    request=request,
    actor=api_key,
    organization=api_key.organization,
    project=project,
    target_type="deployment",
    target_id=deployment.public_id,
)
```

### Operator platformy

```python
audit_log.record(
    action=audit_log.AuditAction.OPERATOR_ACTION,
    request=request,
    actor=request.user,
    organization=organization,
    target_type="organization",
    target_id=organization.public_id,
    metadata={"reason": "support_ticket"},
)
```

Jeśli `request.user.is_platform_staff` jest prawdziwe, helper klasyfikuje aktora jako `operator`.

## 9. Czego nie wolno robić

- Nie wolno aktualizować ani usuwać rekordów `AuditLog` przez zwykły kod aplikacji.
- Nie wolno zapisywać haseł, tokenów, recovery codes, TOTP ani sekretów w metadata.
- Nie wolno używać zmiennych nazw akcji tworzonych dynamicznie bez kontroli.
- Nie wolno pomijać `organization` dla zdarzeń tenantowych.
- Nie wolno pomijać `project` dla zdarzeń projektowych.
- Nie wolno traktować logów technicznych jako zamiennika AuditLog.

## 10. Testy

Minimalne testy dla audytu:

- `audit_log.record(...)` zapisuje wymagane pola;
- metadata jest sanitizowane;
- request id trafia do odpowiedzi i rekordu audytu;
- update istniejącego `AuditLog` przez `save()` jest zablokowany;
- `QuerySet.update()` jest zablokowany;
- `delete()` modelu jest zablokowane;
- `QuerySet.delete()` jest zablokowany.
