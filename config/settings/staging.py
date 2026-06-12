from django.core.exceptions import ImproperlyConfigured

from .production import *  # noqa: F403
from .env import env, env_bool, env_list


ENVIRONMENT = "staging"
DEBUG = False

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must contain staging hosts.")

CORS_ALLOWED_ORIGINS = env_list("DJANGO_CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", "")
STRIPE_TEST_MODE = env_bool("STRIPE_TEST_MODE", True)
if not STRIPE_TEST_MODE:
    raise ImproperlyConfigured("Staging must use Stripe test mode.")

if STRIPE_SECRET_KEY.startswith("sk_live_"):
    raise ImproperlyConfigured("Staging must not use a Stripe live secret key.")

STATIC_DEPLOYMENT_S3_BUCKET = env("STATIC_DEPLOYMENT_S3_BUCKET", "hosting-staging-deployments")
CUSTOM_DOMAIN_SYSTEM_HOSTNAMES = {
    hostname.strip().lower()
    for hostname in env(
        "CUSTOM_DOMAIN_SYSTEM_HOSTNAMES",
        "staging.example.com,api.staging.example.com,app.staging.example.com",
    ).split(",")
    if hostname.strip()
}
CUSTOM_DOMAIN_SYSTEM_SUFFIXES = {
    suffix.strip().lower().lstrip(".")
    for suffix in env("CUSTOM_DOMAIN_SYSTEM_SUFFIXES", "staging.example.com,apps.staging.example.com").split(",")
    if suffix.strip()
}

AUTH_RETURN_DEBUG_TOKENS = False
