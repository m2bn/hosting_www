# Abuse Handling Runbook

## Cel

Ten runbook opisuje podstawowy proces obsługi nadużyć platformy: phishing, malware, spam, nadmierny transfer, nadużywanie deploymentów, podejrzane domeny i nietypowo wysoki poziom błędów 4xx/5xx.

Mechanizm techniczny pozwala operatorowi:

- oznaczyć projekt jako abusive,
- zablokować projekt,
- zablokować organizację,
- zapisać powód blokady,
- odblokować projekt lub organizację,
- zobaczyć listę zablokowanych projektów w operator console,
- wygenerować alerty `SecurityEvent` dla podejrzanych zachowań.

Blokada nie usuwa danych. Usuwanie danych wymaga osobnej procedury retencji i data deletion.

## Sygnały Abuse

System rejestruje alerty dla:

- `excessive_transfer` - nadmierny transfer lub podejrzenie DDoS/proxy abuse,
- `too_many_deployments` - zbyt wiele deploymentów w krótkim czasie,
- `suspicious_domain` - domena podobna do phishingu, brand impersonation albo świeżo przejęta,
- `malware_scan_failed` - skan malware lub image scan wykrył zagrożenie,
- `high_4xx_5xx_rate` - nietypowo dużo błędów 4xx/5xx.

Alerty są zapisywane jako `SecurityEvent` z kategorią `abuse` i audytowane przez `AuditLog`.

## Statusy

Projekt i organizacja mają `abuse_status`:

- `clear` - brak aktywnej blokady abuse,
- `flagged` - projekt oznaczony do triage, ale nie zablokowany,
- `blocked` - zasób zablokowany operatorsko.

Projekt lub organizacja zablokowana abuse przechodzi też w status `suspended`. Nowe deploymenty są blokowane bez ujawniania szczegółowego powodu użytkownikowi.

## Bezpieczny Komunikat Dla Użytkownika

Użytkownik widzi komunikat:

```text
This resource is temporarily unavailable. Contact support if you believe this is a mistake.
```

Nie ujawniamy publicznie, czy powodem jest malware, phishing, chargeback, zgłoszenie prawne albo dochodzenie operatora.

## Procedura Triage

1. Otwórz alert `SecurityEvent` albo zgłoszenie abuse.
2. Sprawdź projekt, organizację, domeny, ostatnie deploymenty, billing i audit logi.
3. Zweryfikuj, czy sygnał jest false positive.
4. Jeśli ryzyko jest wysokie, zablokuj projekt. Jeśli abuse dotyczy wielu projektów albo organizacja jest jednoznacznie złośliwa, zablokuj organizację.
5. Wpisz konkretny powód, np. numer zgłoszenia, wynik skanu albo ticket incydentu.
6. Nie usuwaj danych w ramach abuse triage.

## Blokada Projektu

Operator wywołuje endpoint blokady projektu z powodem. Efekt:

- `project.abuse_status = blocked`,
- `project.status = suspended`,
- `project.abuse_reason` zapisuje powód,
- `blocked_at` i `blocked_by_user` są ustawione,
- `AuditLog` zapisuje `abuse.project.blocked`,
- nowe deploymenty są odrzucane.

## Blokada Organizacji

Operator blokuje organizację, gdy abuse dotyczy całego tenanta. Efekt:

- `organization.abuse_status = blocked`,
- `organization.status = suspended`,
- powód, operator i czas blokady są zapisane,
- `AuditLog` zapisuje `abuse.organization.blocked`,
- projekty organizacji nie mogą przyjmować nowych deploymentów.

## Odblokowanie

Odblokowanie wymaga powodu, np.:

- treść została usunięta,
- domena została zweryfikowana jako legalna,
- skan malware był false positive,
- klient zakończył remediation.

Odblokowanie zapisuje `AuditLog`:

- `abuse.project.unblocked`,
- `abuse.organization.unblocked`.

## Zakaz Usuwania Danych

Abuse handling nie usuwa:

- projektów,
- organizacji,
- deploymentów,
- logów,
- plików w storage,
- audit logów.

Usunięcie danych wymaga procedury z `docs/security/data-protection.md` i runbooków retencji/restore.

## Minimalne Dane Do Analizy

Operator powinien zebrać:

- `organization_public_id`,
- `project_public_id`,
- domeny i statusy certyfikatów,
- ostatnie deploymenty,
- wyniki skanów,
- usage transfer/storage,
- próbki statusów HTTP,
- AuditLog dla ostatnich akcji użytkowników/API keys,
- źródło zgłoszenia abuse.

Nie kopiuj sekretów klienta, wartości env vars ani prywatnych danych poza zatwierdzony system incydentowy.

## Testy Regresyjne

Testy znajdują się w `apps/api/tests_abuse_handling.py` i sprawdzają:

- operator blokuje projekt,
- operator blokuje organizację,
- akcja wymaga powodu,
- zwykły user nie może blokować,
- zablokowany projekt nie może deployować,
- odblokowanie przywraca projekt,
- alerty abuse tworzą `SecurityEvent` i `AuditLog`.

Uruchom:

```bash
python manage.py test apps.api.tests_abuse_handling
```

## Kryteria Gotowości

- Każda akcja operatorska wymaga 2FA i `is_platform_staff`.
- Każda akcja wysokiego ryzyka wymaga powodu.
- Każda akcja abuse zapisuje AuditLog.
- Użytkownik dostaje bezpieczny komunikat.
- Blokada nie kasuje danych.
- Odblokowanie jest możliwe i audytowane.
- Lista zablokowanych projektów jest dostępna operatorom.
