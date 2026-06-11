from .base import *  # noqa: F403
from .env import env, env_list


DEBUG = True
SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-only-secret-key-for-local-development")
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1", "[::1]", "testserver"])

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

AUTH_RETURN_DEBUG_TOKENS = True
