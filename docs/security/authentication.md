# Authentication dla dashboardu i API

## 1. Założenia

Dashboard i API używają sesji Django opartych o bezpieczne cookies. Nie używamy JWT w `localStorage` dla dashboardu, ponieważ zwiększa to ryzyko kradzieży tokenów przez XSS.

Wymagania bazowe:

- sesja jest utrzymywana przez cookie `sessionid`;
- cookie sesji jest `HttpOnly`;
- w produkcji cookie sesji i CSRF muszą mieć `Secure`;
- `SameSite` ma być ustawione na `Lax` albo `Strict`;
- mutujące endpointy sesyjne wymagają CSRF;
- hasła, tokeny resetu, tokeny weryfikacji e-mail, kody TOTP i recovery codes nie mogą być logowane;
- recovery codes są przechowywane wyłącznie jako hash;
- TOTP secret jest przechowywany w bazie jako zaszyfrowana wartość;
- zmiana hasła unieważnia bieżącą sesję.

## 2. Endpointy

Endpointy authentication:

- `GET /api/auth/csrf/`: ustawia cookie CSRF dla dashboardu.
- `POST /api/auth/register/`: rejestruje użytkownika i tworzy token weryfikacji e-mail.
- `POST /api/auth/login/`: loguje użytkownika do sesji cookie.
- `POST /api/auth/logout/`: kończy sesję.
- `GET /api/auth/me/`: zwraca aktualnie zalogowanego użytkownika.
- `POST /api/auth/password/reset/`: inicjuje reset hasła bez ujawniania, czy konto istnieje.
- `POST /api/auth/password/reset/confirm/`: ustawia nowe hasło na podstawie tokenu resetu.
- `POST /api/auth/password/change/`: zmienia hasło zalogowanego użytkownika i wylogowuje sesję.
- `POST /api/auth/email/verify/`: weryfikuje adres e-mail.
- `POST /api/auth/2fa/setup/`: generuje TOTP secret dla zalogowanego użytkownika.
- `POST /api/auth/2fa/enable/`: włącza 2FA po poprawnym kodzie TOTP i generuje recovery codes.
- `POST /api/auth/2fa/disable/`: wyłącza 2FA po potwierdzeniu hasłem.

## 3. Sesje i CSRF

Dashboard powinien najpierw wywołać `GET /api/auth/csrf/`, a następnie przekazywać token CSRF w nagłówku `X-CSRFToken` dla mutujących requestów.

Wymagane ustawienia:

```python
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"  # albo "Strict"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Lax"  # albo "Strict"
```

W środowisku developerskim `Secure` może być wyłączone, jeśli lokalny ruch nie używa HTTPS. Produkcja musi używać HTTPS i `Secure`.

## 4. Rate limiting i brute force

Logowanie jest chronione limitem prób per e-mail i adres IP. Po przekroczeniu limitu endpoint zwraca `429`.

Zasady:

- odpowiedź na błędne hasło jest generyczna;
- błędne TOTP i błędny recovery code liczą się jako nieudane próby logowania;
- udane logowanie czyści licznik błędnych prób;
- zdarzenia rate limitingu są audytowane.

## 5. Reset hasła

Endpoint resetu hasła zawsze zwraca tę samą odpowiedź niezależnie od tego, czy konto istnieje.

Token resetu:

- jest losowy;
- jest przechowywany jako hash;
- ma krótki TTL;
- jest jednorazowy;
- nie jest logowany.

## 6. Weryfikacja e-mail

Token weryfikacji e-mail jest losowy, jednorazowy i przechowywany jako hash. W środowisku testowym/developerskim token może być zwrócony w odpowiedzi tylko wtedy, gdy jawnie włączono `AUTH_RETURN_DEBUG_TOKENS`. W produkcji to ustawienie musi być wyłączone, a token ma być wysyłany kanałem e-mail.

## 7. 2FA TOTP

2FA jest wymagane dla:

- ownerów organizacji;
- adminów organizacji;
- operatorów platformy.

Jeżeli użytkownik ma rolę wymagającą 2FA, logowanie bez skonfigurowanego 2FA jest odrzucane. Jeżeli 2FA jest włączone, logowanie wymaga poprawnego kodu TOTP albo jednorazowego recovery code.

Recovery codes:

- są generowane przy włączeniu 2FA;
- są pokazywane użytkownikowi tylko raz;
- są przechowywane jako hash;
- po użyciu są oznaczane jako wykorzystane;
- użycie recovery code jest audytowane.

## 8. Audit log

Audit log obejmuje:

- `auth.registered`
- `auth.login.succeeded`
- `auth.login.failed`
- `auth.login.rate_limited`
- `auth.logout`
- `auth.password_reset.requested`
- `auth.password_reset.completed`
- `auth.password_changed`
- `auth.email_verified`
- `auth.2fa.enabled`
- `auth.2fa.disabled`
- `auth.2fa.recovery_code_used`

Audit log nie może zawierać haseł, tokenów, kodów TOTP ani recovery codes. Adres IP i user agent są hashowane przed zapisem.

## 9. Czego nie wolno robić

- Nie wolno zapisywać tokenów sesyjnych w `localStorage`.
- Nie wolno zwracać różnych komunikatów resetu hasła dla istniejących i nieistniejących kont.
- Nie wolno logować haseł, tokenów ani kodów 2FA.
- Nie wolno przechowywać recovery codes jako plaintext.
- Nie wolno wyłączać CSRF dla endpointów sesyjnych.
- Nie wolno włączać `AUTH_RETURN_DEBUG_TOKENS` w produkcji.
- Nie wolno traktować samego hasła jako wystarczającego dla ownerów, adminów i operatorów platformy.

## 10. Testy bezpieczeństwa

Minimalny zestaw testów:

- poprawne logowanie tworzy sesję cookie;
- błędne logowanie nie tworzy sesji i emituje audit log;
- brute force rate limit blokuje kolejne próby;
- mutujące endpointy sesyjne wymagają CSRF;
- reset hasła nie ujawnia istnienia konta;
- owner/admin/operator wymagają 2FA;
- recovery codes są hashowane;
- TOTP secret nie jest przechowywany jako plaintext;
- zmiana hasła unieważnia sesję;
- cookie sesji ma `HttpOnly`, `Secure` i właściwe `SameSite` w konfiguracji produkcyjnej.
