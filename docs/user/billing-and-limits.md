# Limity planów, billing i faktury

## Plan organizacji

Plan określa dostępne funkcje i limity organizacji. Limity mogą obejmować:

- liczbę projektów,
- storage,
- transfer,
- deploymenty kontenerowe,
- domeny własne,
- CPU i RAM runtime.

Aktualny plan zobaczysz w sekcji billingowej organizacji.

## Zużycie

Panel pokazuje aktualne zużycie zasobów, na przykład storage, transfer, CPU i RAM. Platforma może wyświetlać ostrzeżenia po osiągnięciu 80%, 90% i 100% limitu.

Po przekroczeniu limitu niektóre działania mogą zostać zablokowane, na przykład utworzenie nowego projektu albo deployment.

## Billing

Osoby z rolą owner albo billing mogą zarządzać płatnościami.

1. Otwórz organizację.
2. Przejdź do sekcji billing.
3. Sprawdź aktualny plan i status subskrypcji.
4. Wybierz zmianę planu albo rozpoczęcie płatności.
5. Zostaniesz przekierowany do Stripe Checkout.

Platforma nie pozwala wybrać dowolnej ceny po stronie przeglądarki. Cena jest wybierana po stronie backendu na podstawie planu.

## Status subskrypcji

- `trialing`: trwa okres próbny.
- `active`: subskrypcja jest aktywna.
- `past_due`: płatność nie powiodła się, ale może obowiązywać okres karencji.
- `canceled`: subskrypcja została anulowana.
- `unpaid`: subskrypcja jest nieopłacona.

Status `canceled` albo `unpaid` może blokować tworzenie nowych zasobów i deploymenty.

## Faktury

Faktury są dostępne w sekcji billingowej. Możesz zobaczyć historię faktur, status płatności i odnośniki do dokumentów udostępnionych przez operatora płatności.

Jeśli płatność się nie powiedzie, panel pokaże komunikat payment failed. Sprawdź metodę płatności albo skontaktuj się z osobą odpowiedzialną za billing.
