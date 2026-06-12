# Data Protection

## Cel

Ten dokument definiuje zasady ochrony danych dla platformy SaaS hostującej strony i aplikacje klientów. Obejmuje klasyfikację danych, retencję, usuwanie, eksport, szyfrowanie, dostęp operatorów oraz procedury obsługi żądań użytkowników i właścicieli organizacji. Dokument jest podstawą do późniejszej implementacji funkcji wspierających RODO/GDPR i audyt bezpieczeństwa.

## Klasyfikacja Danych

| Klasa | Opis | Przykłady | Wymagania |
| --- | --- | --- | --- |
| Public | Dane celowo publiczne. | publiczne strony klientów, publiczne rekordy DNS | integralność, ochrona przed takeover |
| Internal | Dane operacyjne platformy bez danych osobowych. | statusy deploymentów, statusy certyfikatów, konfiguracja runtime | kontrola dostępu, retencja |
| Confidential | Dane tenantów i dane biznesowe. | projekty, domeny, metadane buildów, faktury, usage | RBAC, tenant isolation, audit |
| Personal Data | Dane osobowe. | e-mail, imię, nazwisko, IP, user agent, logi aktywności | minimalizacja, RODO, retencja, eksport/usunięcie |
| Secret | Sekrety i dane uwierzytelniające. | hashe haseł, API keys, recovery codes, secret env vars, klucze szyfrujące | szyfrowanie, hashing, brak logowania, rotacja |
| Restricted | Dane o wysokim ryzyku prawnym lub bezpieczeństwa. | dane billingowe, identyfikatory Stripe, backupy, audit logs | least privilege, silna retencja, monitoring dostępu |

## Kategorie Danych

### Dane Użytkowników

- E-mail, imię i nazwisko, status aktywności, daty rejestracji i logowania.
- Hasła przechowywane wyłącznie jako hash.
- Dane 2FA: sekrety TOTP szyfrowane, recovery codes jako hash.
- Sesje przechowywane po stronie serwera; tokeny sesji nie mogą trafiać do `localStorage`.

### Dane Organizacji

- Nazwa organizacji, slug, billing email, członkowie, role, uprawnienia.
- Relacje ownershipu muszą być filtrowane przez `organization_id`.
- Usunięcie organizacji powinno być soft delete do czasu zakończenia retencji i rozliczeń.

### Dane Billingowe

- Lokalnie przechowujemy minimalne dane: Stripe customer id, subscription id, invoice id, statusy, plan, kwoty i waluty wymagane operacyjnie.
- Pełne dane kart płatniczych nie są przechowywane w platformie.
- Stripe pozostaje procesorem danych płatniczych; lokalne dane billingowe są `Restricted`.

### Dane Projektów

- Projekty, środowiska, deploymenty, domeny, certyfikaty, runtime metadata, usage.
- Sekrety projektów są szyfrowane przed zapisem i nigdy nie są zwracane przez API po utworzeniu.
- Artefakty deploymentów muszą być przypisane do organizacji, projektu i deploymentu.

### Logi

- Logi techniczne i audytowe mogą zawierać dane osobowe: IP, user agent, e-mail, actor id.
- Logi nie mogą zawierać haseł, pełnych API keys, tokenów resetu hasła, kodów 2FA, prywatnych kluczy ani wartości sekretów.
- AuditLog jest append-only na poziomie aplikacji i ma osobne zasady retencji.

### Adresy IP

- Adres IP traktujemy jako dane osobowe.
- IP jest zapisywany w logach bezpieczeństwa, AuditLog i rate limiting tylko, gdy jest to uzasadnione bezpieczeństwem, audytem lub przeciwdziałaniem nadużyciom.
- Dostęp do IP powinien być ograniczony do ról operator/security/support z uzasadnieniem.

### Dane Techniczne

- Request id, correlation id, statusy jobów, metryki, usage, identyfikatory namespace, image digest, SBOM.
- Dane techniczne bez bezpośrednich danych osobowych są `Internal`, ale mogą stać się `Confidential`, jeśli pozwalają wnioskować o aktywności klienta.

### Backupy

- Backupy są `Restricted`.
- Muszą być szyfrowane przed zapisem.
- Dostęp do backupów wymaga oddzielnych uprawnień least privilege.
- Backupy mogą zawierać dane osobowe, dane tenantów, AuditLog i metadane billingowe.

## Retencja Danych

Retencja musi być konfigurowalna i udokumentowana per kategoria:

- Dane konta użytkownika: przez czas istnienia konta, potem okres retencji prawnej/operacyjnej.
- Dane organizacji i projektów: przez czas aktywnej usługi, potem okres grace/retencji po usunięciu.
- Dane billingowe: zgodnie z wymaganiami księgowymi i podatkowymi.
- AuditLog i SecurityEvent: minimalnie na potrzeby audytu i incident response; dłużej dla zdarzeń wysokiego ryzyka.
- Logi aplikacyjne: krótsza retencja niż AuditLog, chyba że są częścią incydentu.
- Backupy: domyślnie 30 dni w MVP, docelowo polityka zależna od planu i wymagań compliance.

Retencja nie może być realizowana przez ręczne kasowanie w bazie bez audytu. Usunięcia muszą być rejestrowane i możliwe do wykazania.

## Usuwanie Danych

Usuwanie danych powinno rozróżniać:

- Soft delete: natychmiastowe ukrycie zasobu w aplikacji i API.
- Hard delete: fizyczne usunięcie po zakończeniu retencji, rozliczeń i okresów prawnych.
- Anonimizacja: usunięcie lub nieodwracalne zastąpienie danych osobowych przy zachowaniu minimalnych danych audytowych.

Nie wolno usuwać danych w sposób naruszający integralność billing, audytu bezpieczeństwa lub obowiązki prawne. Jeśli danych nie można usunąć natychmiast, użytkownik lub właściciel organizacji musi otrzymać informację o podstawie i terminie retencji.

## Eksport Danych

Eksport powinien obejmować dane osobowe i dane tenantowe w formacie maszynowo czytelnym:

- użytkownik: profil, membershipy, aktywność audytowa dotycząca użytkownika, API keys metadata bez sekretów;
- organizacja: członkowie, projekty, domeny, deployment metadata, usage, billing metadata, audit events dotyczące organizacji;
- projekty: konfiguracja, środowiska, sekrety tylko jako nazwy/metadane, bez wartości sekretów.

Eksport musi być autoryzowany, audytowany i dostępny tylko dla właściwego subjecta albo ownera organizacji.

## Szyfrowanie

### W Spoczynku

- Baza danych: szyfrowanie dysków/storage zarządzane przez infrastrukturę.
- Sekrety aplikacji klientów: szyfrowanie aplikacyjne przed zapisem.
- Backupy: szyfrowane przed zapisem do storage backupowego.
- Object storage: szyfrowanie server-side lub client-side zależnie od środowiska.
- Klucze szyfrujące: przechowywane poza repozytorium, docelowo w KMS/secrets managerze.

### W Transmisji

- TLS wymagany dla dashboardu, API, webhooków i paneli operatorskich.
- Połączenia do PostgreSQL, Redis/RabbitMQ, MinIO/S3 i Stripe muszą używać TLS w production, jeśli komponent to wspiera.
- Webhooki Stripe wymagają weryfikacji podpisu, niezależnie od TLS.

## Dostęp Operatorów

- Operatorzy platformy mają dostęp wyłącznie zgodnie z least privilege.
- Dostęp operatora do danych tenantów wymaga uzasadnienia, audytu i możliwie krótkiego czasu trwania.
- Dostęp break-glass musi być osobno oznaczony, monitorowany i przeglądany po użyciu.
- Operatorzy nie powinni mieć dostępu do wartości sekretów klientów; system powinien umożliwiać tylko reset/rotację.

## Minimalizacja Danych

- Zbieramy tylko dane potrzebne do działania usługi, bezpieczeństwa, billing i compliance.
- Nie przechowujemy pełnych numerów kart, pełnych API keys, plaintext haseł, plaintext recovery codes ani wartości sekretów po odczycie przez użytkownika.
- Dane diagnostyczne powinny używać publicznych UUID, prefixów kluczy i fingerprintów zamiast wartości sekretów.

## Procedury RODO

### Prawo Do Usunięcia Danych

Żądanie usunięcia musi przejść przez:

1. Weryfikację tożsamości użytkownika albo uprawnień ownera organizacji.
2. Ustalenie zakresu: konto użytkownika, członkostwo, organizacja, projekt, dane billingowe.
3. Sprawdzenie blokad prawnych: faktury, spory, nadużycia, incydenty bezpieczeństwa.
4. Soft delete lub anonimizację natychmiastową tam, gdzie to możliwe.
5. Hard delete po zakończeniu retencji.
6. Audyt wykonania bez zapisywania nadmiarowych danych osobowych.

### Prawo Do Eksportu Danych

Żądanie eksportu musi przejść przez:

1. Weryfikację tożsamości lub ownershipu organizacji.
2. Określenie zakresu eksportu.
3. Wygenerowanie paczki eksportowej z manifestem.
4. Szyfrowanie paczki lub udostępnienie przez krótkotrwały, autoryzowany link.
5. AuditLog zdarzenia eksportu.
6. Automatyczne usunięcie paczki eksportowej po krótkiej retencji.

### Obsługa Żądania Użytkownika

- Użytkownik może żądać eksportu lub usunięcia danych dotyczących własnego konta.
- Jeśli użytkownik jest członkiem organizacji, usunięcie konta nie może automatycznie usuwać danych organizacji.
- Dane audytowe mogą zostać zanonimizowane zamiast usunięte, jeśli są wymagane do bezpieczeństwa lub rozliczalności.

### Obsługa Żądania Właściciela Organizacji

- Owner organizacji może żądać eksportu danych organizacji.
- Usunięcie organizacji wymaga potwierdzenia ownera i sprawdzenia rozliczeń.
- System musi uniemożliwiać usunięcie danych organizacji przez użytkownika bez roli owner.
- Dane billingowe i faktury podlegają retencji prawnej.

## Wymagane Funkcje Aplikacji

Aby wspierać powyższe procedury, aplikacja musi posiadać:

- Panel eksportu danych użytkownika.
- Panel eksportu danych organizacji dla ownera.
- Job asynchroniczny generujący eksport z manifestem.
- Szyfrowane paczki eksportowe albo krótkotrwałe signed URLs.
- Workflow żądania usunięcia konta użytkownika.
- Workflow żądania usunięcia organizacji.
- Mechanizm soft delete i późniejszego hard delete zgodnie z retencją.
- Mechanizm anonimizacji danych osobowych w AuditLog/logach tam, gdzie usunięcie nie jest dopuszczalne.
- Rejestr żądań RODO z ownerem, statusem, zakresem, terminem i wynikiem.
- Automatyczne enforcement retencji dla logów, backupów, eksportów i soft-deleted zasobów.
- AuditLog dla eksportu, usunięcia, anonimizacji i dostępu operatora.
- Narzędzie operatora do zatwierdzania lub odrzucania żądań z uzasadnieniem.
- Raport danych przechowywanych dla użytkownika i organizacji.
- Mechanizm blokady usunięcia danych objętych legal hold, incydentem lub rozliczeniem.
- Rotację i zarządzanie kluczami szyfrowania.
- Testy regresyjne dla eksportu, usuwania, anonimizacji i tenant isolation.

## Zasady Kontrolne

- Każdy nowy model musi mieć przypisaną klasę danych i retencję.
- Każdy endpoint eksportu/usuwania musi mieć testy autoryzacji i IDOR.
- Każdy log zawierający dane osobowe musi mieć uzasadnienie i retencję.
- Każdy sekret musi być szyfrowany lub hashowany przed zapisem.
- Każdy dostęp operatora do danych tenantów musi być audytowany.
