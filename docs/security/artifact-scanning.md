# Artifact Scanning Policy

## Cel

Polityka skanowania artefaktów ma zatrzymywać wdrożenia, które mogą narazić platformę, innych tenantów albo użytkowników końcowych klientów. Obejmuje static deployments ZIP, obrazy kontenerowe oraz zależności aplikacji.

## Zakres

- ZIP static deployment: walidacja archiwum, skan plików po bezpiecznym rozpakowaniu, wykrywanie sygnatur malware i niedozwolonych artefaktów.
- Obrazy kontenerowe: skanowanie obrazu po buildzie i przed deploymentem do namespace projektu.
- Zależności: skan manifestów zależności i SBOM, docelowo w pipeline builda oraz CI.
- Wyniki skanowania są przypisane do `Organization`, `Project`, opcjonalnie `Environment`, `BuildJob` i `Deployment`.

## Decyzje polityki

Deployment jest blokowany, gdy:

- skaner ZIP wykryje malware albo artefakt oznaczony jako krytyczny,
- skaner obrazu kontenerowego wykryje podatność krytyczną,
- skan zależności wykryje podatność krytyczną objętą polityką blokującą,
- skaner zakończy się stanem, którego nie można bezpiecznie zinterpretować.

Wyniki wysokie, średnie i niskie są zapisywane i widoczne w panelu projektu, ale nie blokują deploymentu w bazowej polityce. Ta decyzja może zostać zaostrzena dla planów enterprise albo regulowanych środowisk.

## Operator Override

Override jest dozwolony tylko, gdy spełnione są wszystkie warunki:

- aktor jest operatorem platformy,
- operator ma włączone 2FA,
- wynik skanu ma status `blocked`,
- operator podaje konkretny powód,
- decyzja jest zapisana w `AuditLog`.

Override nie usuwa wyniku skanu i nie kasuje historii. Zmienia status wyniku na `overridden`, zapisuje operatora, powód i czas decyzji. Nie wolno używać override do omijania braku skanu.

## Widoczność wyników

Użytkownicy widzą tylko wyniki skanowania swoich projektów w kontekście organizacji, której są członkami. API nie udostępnia wyników przez globalne ID bez organization/project context.

Widok użytkownika nie zwraca wrażliwych pól operacyjnych, takich jak wewnętrzne referencje raportów, pełne ścieżki skanerów albo szczegóły infrastruktury. Operator może widzieć pełniejsze metadane potrzebne do triage.

## AuditLog

AuditLog musi być tworzony dla:

- zakończenia czystego skanu,
- skanu blokującego deployment,
- override decyzji skanera,
- deploymentu odrzuconego przez politykę skanowania.

Metadata audytu nie może zawierać sekretów, pełnych tokenów, zmiennych środowiskowych ani prywatnych danych innego tenanta.

## Integracja z Deployment Pipeline

Static deployment:

1. Upload ZIP.
2. Walidacja MIME, rozmiaru i struktury.
3. Bezpieczne rozpakowanie.
4. Utworzenie `BuildJob` i `Deployment`.
5. Skan ZIP.
6. Blokada albo kontynuacja uploadu do storage.
7. Atomowe przełączenie aktywnego deploymentu.

Container deployment:

1. Upload contextu.
2. Walidacja contextu i `.dockerignore`.
3. Build w izolowanym środowisku.
4. Push obrazu do prywatnego registry.
5. Skan obrazu.
6. Blokada albo deployment do namespace projektu.

## Wymagania Testowe

Minimalne testy regresyjne:

- czysty artefakt tworzy wynik `clean`,
- zainfekowany ZIP blokuje static deployment,
- krytyczna podatność obrazu blokuje container deployment,
- operator z 2FA może wykonać override z powodem,
- zwykły użytkownik i operator bez 2FA nie mogą wykonać override,
- użytkownik organizacji A nie widzi wyników skanowania organizacji B.
