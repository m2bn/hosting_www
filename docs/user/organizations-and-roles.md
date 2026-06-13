# Organizacje, członkowie i role

## Czym jest organizacja

Organizacja grupuje projekty, członków zespołu, billing, domeny i ustawienia dostępu. Jedno konto użytkownika może należeć do wielu organizacji.

## Utworzenie organizacji

1. Po zalogowaniu przejdź do widoku organizacji.
2. Wybierz utworzenie nowej organizacji.
3. Podaj nazwę organizacji.
4. Zatwierdź formularz.

Osoba tworząca organizację zostaje jej właścicielem.

## Zaproszenie albo dodanie członka

1. Otwórz organizację.
2. Przejdź do sekcji członków.
3. Podaj adres e-mail osoby, którą chcesz dodać.
4. Wybierz rolę.
5. Zatwierdź zaproszenie.

Nadawaj tylko taki poziom dostępu, jaki jest potrzebny do pracy danej osoby.

## Role w organizacji

### Owner

Właściciel organizacji. Może zarządzać organizacją, członkami, projektami, billingiem, domenami, sekretami i deploymentami. Owner może usuwać organizację oraz zmieniać role innych użytkowników.

### Admin

Administrator organizacji. Może zarządzać członkami, projektami, domenami, sekretami i deploymentami. Zwykle nie zarządza billingiem, chyba że polityka organizacji mówi inaczej.

### Developer

Developer może tworzyć i aktualizować projekty, wykonywać deploymenty, zarządzać sekretami projektu i czytać logi. Nie powinien zarządzać billingiem ani członkami organizacji.

### Billing

Osoba odpowiedzialna za płatności. Może widzieć billing, faktury i zużycie oraz rozpoczynać proces płatności. Nie może wykonywać deploymentów.

### Viewer

Rola tylko do odczytu. Viewer może przeglądać dozwolone zasoby, ale nie może ich modyfikować.

## Dobre praktyki dostępu

- Nie używaj jednego współdzielonego konta dla całego zespołu.
- Regularnie przeglądaj listę członków.
- Usuwaj dostęp osobom, które nie pracują już przy projekcie.
- Dla ownerów i adminów zawsze używaj 2FA.
