# Domeny własne, DNS i SSL

## Dodanie domeny własnej

1. Otwórz projekt.
2. Przejdź do sekcji domen.
3. Wybierz dodanie domeny.
4. Wpisz nazwę domeny, na przykład `www.example.com`.
5. Zatwierdź formularz.

Domena nie może być już przypisana do innej organizacji. Platforma może też blokować domeny systemowe i domeny zastrzeżone.

## Weryfikacja domeny

Aby potwierdzić, że kontrolujesz domenę, platforma poprosi o dodanie rekordu TXT w DNS.

1. Skopiuj nazwę rekordu TXT z panelu.
2. Skopiuj wartość rekordu TXT z panelu.
3. Dodaj rekord w panelu DNS swojego dostawcy domeny.
4. Poczekaj na propagację DNS.
5. Wróć do platformy i odśwież status weryfikacji.

Propagacja DNS może potrwać od kilku minut do kilku godzin.

## Konfiguracja DNS dla ruchu

Po weryfikacji domeny skonfiguruj rekord kierujący ruch do platformy. Najczęściej będzie to rekord `CNAME` dla subdomeny, na przykład:

```text
www.example.com -> cname.platform.example
```

Dokładną wartość rekordu zobaczysz w panelu projektu.

## Statusy domeny

- `pending_verification`: domena czeka na weryfikację DNS.
- `verified`: domena została potwierdzona.
- `active`: domena obsługuje ruch.
- `failed`: wystąpił problem z konfiguracją.
- `disabled`: domena została wyłączona.

## SSL

Po poprawnej weryfikacji domeny platforma automatycznie rozpoczyna wydawanie certyfikatu SSL. Nie musisz ręcznie przesyłać kluczy prywatnych ani certyfikatów.

Status certyfikatu może być:

- `pending`: żądanie certyfikatu czeka na rozpoczęcie.
- `issuing`: certyfikat jest wydawany.
- `active`: certyfikat działa.
- `renewal_pending`: certyfikat czeka na odnowienie.
- `failed`: wystąpił błąd DNS albo ACME.
- `expired`: certyfikat wygasł.

Jeśli certyfikat ma status `failed`, sprawdź rekordy DNS i spróbuj ponownie odświeżyć status.
