# ADR-0003: PostgreSQL jako główna baza danych

## Status

Accepted

## Kontekst

Control plane przechowuje dane silnie relacyjne: użytkowników, organizacje, role, projekty, domeny, deploymenty, billing state, API keys, audyt, konfiguracje i metadane runtime. Potrzebujemy transakcyjności, spójności, dobrego modelu migracji i możliwości budowania zapytań raportowych.

## Decyzja

PostgreSQL jest główną bazą danych control plane.

## Konsekwencje pozytywne

- PostgreSQL zapewnia transakcje ACID, integralność referencyjną i dojrzały model indeksowania.
- Dobrze pasuje do Django ORM i migracji.
- Wspiera JSONB dla wybranych elastycznych konfiguracji bez rezygnacji z relacyjnego rdzenia.
- Jest sprawdzony operacyjnie w systemach SaaS i ma bogaty ekosystem backupu, replikacji i monitoringu.
- Ułatwia egzekwowanie unikalności domen, relacji tenantowych i spójności billing state.

## Konsekwencje negatywne

- Separacja tenantów w jednej bazie wymaga konsekwentnego filtrowania i testów autoryzacji.
- Przy dużej skali logów, metryk lub eventów PostgreSQL nie powinien być jedynym storage.
- Migracje schematu mogą stać się ryzykowne bez dyscypliny release i testów.
- Wydajność zależy od dobrych indeksów, planów zapytań i kontroli N+1.

## Alternatywy

- MySQL: dojrzały wybór, ale PostgreSQL daje mocniejsze funkcje typów, indeksów i JSONB.
- CockroachDB: atrakcyjny dla rozproszonej SQL, ale większa złożoność operacyjna.
- DynamoDB/NoSQL: dobre dla wybranych workloadów, ale słabsze dopasowanie do relacyjnego modelu SaaS.
- Database per tenant: mocna izolacja, ale za wysoki koszt operacyjny dla MVP.

## Wpływ na bezpieczeństwo

- Każda tabela tenantowa musi zawierać tenant context albo mieć jawne uzasadnienie wyjątku.
- Wymagane są testy IDOR i cross-tenant dla zapytań oraz operacji asynchronicznych.
- Dostęp aplikacji do bazy musi używać minimalnych uprawnień i osobnych kont tam, gdzie to uzasadnione.
- Dane wrażliwe i sekrety nie mogą być przechowywane jako plain text.
- Backupy PostgreSQL muszą być szyfrowane, testowane przez restore i objęte audytem dostępu.
