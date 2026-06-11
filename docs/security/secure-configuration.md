# Secure configuration Django

## 1. Cel

Ten dokument opisuje bezpieczne ustawienia Django dla środowisk `development`, `test` i `production`.

Konfiguracja znajduje się w:

- `config/settings/development.py`
- `config/settings/test.py`
- `config/settings/production.py`

Domyślny `manage.py` używa `config.settings.development`. Produkcja musi jawnie ustawić:

```bash
DJANGO_SETTINGS_MODULE=config.settings.production
```

albo:

```bash
DJANGO_ENV=production
DJANGO_SETTINGS_MODULE=config.settings
```

## 2. Wymagane zmienne produkcyjne

Produkcja nie startuje bez:

- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`

Przykład znajduje się w `.env.example`. Plik `.env.example` nie zawiera prawdziwych sekretów.

## 3. Production defaults

W produkcji obowiązuje:

- `DEBUG = False`
- `SECRET_KEY` tylko ze zmiennej środowiskowej
- `ALLOWED_HOSTS` tylko ze zmiennej środowiskowej
- `SECURE_SSL_REDIRECT = True`
- `SESSION_COOKIE_SECURE = True`
- `SESSION_COOKIE_HTTPONLY = True`
- `CSRF_COOKIE_SECURE = True`
- `SESSION_COOKIE_SAMESITE = "Lax"` albo `"Strict"`
- `CSRF_COOKIE_SAMESITE = "Lax"` albo `"Strict"`
- `SECURE_HSTS_SECONDS = 31536000`
- `SECURE_HSTS_INCLUDE_SUBDOMAINS = True`
- `SECURE_HSTS_PRELOAD = True`
- `SECURE_CONTENT_TYPE_NOSNIFF = True`
- `X_FRAME_OPTIONS = "DENY"`
- `SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"`

## 4. Security headers

`config.security_headers.SecurityHeadersMiddleware` ustawia:

- `Content-Security-Policy`
- `Permissions-Policy`
- `Referrer-Policy`

Baseline CSP:

```text
default-src 'self';
base-uri 'self';
object-src 'none';
frame-ancestors 'none';
form-action 'self';
img-src 'self' data:;
font-src 'self';
style-src 'self' 'unsafe-inline';
script-src 'self';
connect-src 'self'
```

Jeżeli dashboard wymaga zewnętrznych domen, należy rozszerzyć CSP świadomie i z testami.

## 5. CORS

CORS jest domyślnie zamknięty. Odpowiedzi CORS są dodawane tylko wtedy, gdy `Origin` znajduje się w `DJANGO_CORS_ALLOWED_ORIGINS`.

Nie wolno używać:

```python
CORS_ALLOW_ALL_ORIGINS = True
```

Ani odpowiednika wildcard `*` dla endpointów sesyjnych z cookies.

## 6. Logi i sekrety

Konfiguracja logowania używa `config.logging_filters.RedactSecretsFilter`, który redaguje typowe pola sekretów:

- `password`
- `token`
- `secret`
- `api_key`
- `authorization`
- `recovery_code`
- `totp`

Nie wolno logować pełnych payloadów requestów authentication, billing, webhooków ani konfiguracji sekretów.

## 7. Development i test

Development:

- może mieć `DEBUG = True`;
- może używać lokalnego `SECRET_KEY`;
- może zwracać debug tokeny auth przez `AUTH_RETURN_DEBUG_TOKENS = True`;
- nie musi wymuszać `Secure` cookies, jeśli działa lokalnie bez HTTPS.

Test:

- używa osobnych ustawień;
- ma deterministyczny testowy `SECRET_KEY`;
- nie jest konfiguracją produkcyjną.

## 8. Weryfikacja

Przed wdrożeniem produkcyjnym uruchom:

```bash
DJANGO_SETTINGS_MODULE=config.settings.production python manage.py check --deploy
python manage.py test
```

Komenda produkcyjna wymaga ustawionych zmiennych `DJANGO_SECRET_KEY` i `DJANGO_ALLOWED_HOSTS`.
