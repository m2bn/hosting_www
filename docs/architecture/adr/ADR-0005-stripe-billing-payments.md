# ADR-0005: Stripe Billing jako system płatności

## Status

Accepted

## Kontekst

Platforma wymaga subskrypcji, faktur, statusów płatności, blokowania lub odblokowywania dostępu, planów oraz w przyszłości rozliczeń usage-based. Budowanie własnego systemu płatności i fakturowania zwiększyłoby ryzyko prawne, bezpieczeństwa i operacyjne.

## Decyzja

Stripe Billing jest zewnętrznym systemem płatności, subskrypcji i fakturowania.

## Konsekwencje pozytywne

- Stripe obsługuje płatności, faktury, subskrypcje, metody płatności i wiele wymagań compliance.
- Zmniejszamy zakres danych płatniczych przetwarzanych przez platformę.
- Webhooki pozwalają utrzymywać lokalny billing state bez budowania całego systemu płatności.
- Stripe wspiera późniejsze scenariusze usage-based billing.
- Klienci dostają sprawdzone przepływy płatności i fakturowania.

## Konsekwencje negatywne

- Platforma zależy od dostępności i API Stripe.
- Webhooki mogą przychodzić z opóźnieniem, powtórzeniami lub poza kolejnością.
- Model danych Stripe musi być poprawnie mapowany na organizacje i plany platformy.
- Zmiany cennika i podatków mogą wymagać starannej synchronizacji.

## Alternatywy

- Paddle: prostsza obsługa merchant of record w niektórych krajach, ale inne ograniczenia integracyjne.
- Chargebee/Recurly: mocne platformy billingowe, ale większy koszt i dodatkowa zależność.
- Własny billing: pełna kontrola, ale zbyt duże ryzyko compliance, fraud i utrzymania.
- Manualne fakturowanie dla MVP: proste na start, ale nie pasuje do self-service SaaS.

## Wpływ na bezpieczeństwo

- Platforma nie powinna przechowywać danych kart płatniczych.
- Webhooki Stripe muszą być weryfikowane podpisem, idempotentne i odporne na replay.
- Krytyczne decyzje billingowe powinny być potwierdzane przez Stripe API albo reconciliation.
- Billing state w platformie musi być audytowany i transakcyjny.
- Klucze Stripe muszą być przechowywane w secret store/KMS, rotowane i nigdy nie logowane.
