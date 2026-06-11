# Custom Domains Security

## Zasady

- Każda domena należy do `Organization`, `Project` i `Environment`.
- Wszystkie zapytania do domen muszą być filtrowane przez kontekst organizacji, projektu i środowiska.
- `hostname` jest globalnie unikalny dla aktywnych rekordów, aby jedna domena nie mogła być przypisana do dwóch tenantów.
- Domeny systemowe platformy oraz domeny z zarezerwowanych suffixów są blokowane.
- Weryfikacja właścicielstwa odbywa się przez rekord TXT.
- Surowy token weryfikacyjny jest zwracany tylko raz w instrukcji DNS; w bazie przechowywany jest wyłącznie hash.
- Certyfikat może być żądany dopiero po poprawnej weryfikacji TXT.

## Rekord DNS

Backend generuje instrukcję:

```text
type: TXT
name: _platform-verify.<hostname>
value: <one-time-token>
```

Okresowy checker DNS pobiera rekordy TXT i porównuje ich wartości z hashem zapisanym w `Domain.verification_token_hash`.

## RBAC

- `owner` i `admin` mają `domain.manage`.
- `developer` nie ma domyślnie `domain.manage`.
- `viewer` nie może tworzyć, weryfikować ani wyłączać domen.
- Użytkownik spoza organizacji nie może zobaczyć ani zmodyfikować domeny.

## Ochrona Przed Takeoverem

- Nie wolno dodać domeny przypisanej do innej organizacji.
- Nie wolno dodać domeny platformowej lub domeny pod zarezerwowanym suffixem.
- Nie wolno aktywować domeny bez `verified_at`.
- Cert-manager/provisioner działa tylko dla domen zweryfikowanych.

## AuditLog

Logowane są:

- `domain.added`,
- `domain.verified`,
- `domain.verification_failed`,
- `domain.activated`,
- `domain.disabled`.

Metadata nie zawiera surowego tokenu weryfikacyjnego.
