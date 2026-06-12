import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]

USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
ROOT_URLCONF = "config.urls"
AUTH_USER_MODEL = "api.User"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "rest_framework",
    "apps.api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "config.request_id.RequestIdMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "config.security_headers.SecurityHeadersMiddleware",
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "auth-rate-limit",
    }
}

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

PERMISSIONS_POLICY = "accelerometer=(), camera=(), geolocation=(), gyroscope=(), microphone=(), payment=(), usb=()"
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "base-uri 'self'; "
    "object-src 'none'; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; "
    "connect-src 'self'"
)
CORS_ALLOWED_ORIGINS = []

AUTH_LOGIN_RATE_LIMIT_ATTEMPTS = 5
AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS = 300
AUTH_RETURN_DEBUG_TOKENS = False
ENTITLEMENTS_NO_SUBSCRIPTION_POLICY = "free"
ENTITLEMENTS_PAST_DUE_GRACE_DAYS = 7
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_CHECKOUT_SUCCESS_URL = os.environ.get("STRIPE_CHECKOUT_SUCCESS_URL", "http://localhost:3000/billing/success")
STRIPE_CHECKOUT_CANCEL_URL = os.environ.get("STRIPE_CHECKOUT_CANCEL_URL", "http://localhost:3000/billing/cancel")
STRIPE_TEST_MODE = os.environ.get("STRIPE_TEST_MODE", "true").lower() in {"1", "true", "yes"}
API_KEY_RATE_LIMIT_ATTEMPTS = int(os.environ.get("API_KEY_RATE_LIMIT_ATTEMPTS", "120"))
API_KEY_RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("API_KEY_RATE_LIMIT_WINDOW_SECONDS", "60"))
STATIC_DEPLOYMENT_MAX_ZIP_BYTES = int(os.environ.get("STATIC_DEPLOYMENT_MAX_ZIP_BYTES", str(50 * 1024 * 1024)))
STATIC_DEPLOYMENT_MAX_FILES = int(os.environ.get("STATIC_DEPLOYMENT_MAX_FILES", "2000"))
STATIC_DEPLOYMENT_MAX_UNPACKED_BYTES = int(os.environ.get("STATIC_DEPLOYMENT_MAX_UNPACKED_BYTES", str(500 * 1024 * 1024)))
STATIC_DEPLOYMENT_ALLOWED_EXTENSIONS = set(
    os.environ.get(
        "STATIC_DEPLOYMENT_ALLOWED_EXTENSIONS",
        ".html,.htm,.css,.js,.mjs,.json,.txt,.xml,.svg,.png,.jpg,.jpeg,.gif,.webp,.ico,.wasm,.map,.woff,.woff2",
    ).split(",")
)
STATIC_DEPLOYMENT_STORAGE_BACKEND = os.environ.get("STATIC_DEPLOYMENT_STORAGE_BACKEND", "local")
STATIC_DEPLOYMENT_LOCAL_ROOT = os.environ.get("STATIC_DEPLOYMENT_LOCAL_ROOT", str(BASE_DIR / "outputs" / "static-deployments"))
STATIC_DEPLOYMENT_S3_BUCKET = os.environ.get("STATIC_DEPLOYMENT_S3_BUCKET", "")
STATIC_DEPLOYMENT_S3_ENDPOINT_URL = os.environ.get("STATIC_DEPLOYMENT_S3_ENDPOINT_URL", "")
STATIC_DEPLOYMENT_S3_REGION = os.environ.get("STATIC_DEPLOYMENT_S3_REGION", "us-east-1")

CONTAINER_DEPLOYMENT_MAX_CONTEXT_ZIP_BYTES = int(os.environ.get("CONTAINER_DEPLOYMENT_MAX_CONTEXT_ZIP_BYTES", str(100 * 1024 * 1024)))
CONTAINER_DEPLOYMENT_MAX_CONTEXT_BYTES = int(os.environ.get("CONTAINER_DEPLOYMENT_MAX_CONTEXT_BYTES", str(512 * 1024 * 1024)))
CONTAINER_DEPLOYMENT_BUILD_TIMEOUT_SECONDS = int(os.environ.get("CONTAINER_DEPLOYMENT_BUILD_TIMEOUT_SECONDS", "1200"))
CONTAINER_DEPLOYMENT_REGISTRY = os.environ.get("CONTAINER_DEPLOYMENT_REGISTRY", "registry.example.com/private")
CONTAINER_DEPLOYMENT_BUILD_CPU_LIMIT = os.environ.get("CONTAINER_DEPLOYMENT_BUILD_CPU_LIMIT", "2")
CONTAINER_DEPLOYMENT_BUILD_MEMORY_LIMIT = os.environ.get("CONTAINER_DEPLOYMENT_BUILD_MEMORY_LIMIT", "4Gi")
CONTAINER_DEPLOYMENT_RUNTIME_CPU_LIMIT = os.environ.get("CONTAINER_DEPLOYMENT_RUNTIME_CPU_LIMIT", "1")
CONTAINER_DEPLOYMENT_RUNTIME_MEMORY_LIMIT = os.environ.get("CONTAINER_DEPLOYMENT_RUNTIME_MEMORY_LIMIT", "512Mi")
CONTAINER_DEPLOYMENT_DEFAULT_PORT = int(os.environ.get("CONTAINER_DEPLOYMENT_DEFAULT_PORT", "8080"))

CUSTOM_DOMAIN_TXT_RECORD_PREFIX = os.environ.get("CUSTOM_DOMAIN_TXT_RECORD_PREFIX", "_platform-verify")
CUSTOM_DOMAIN_SYSTEM_HOSTNAMES = {
    hostname.strip().lower()
    for hostname in os.environ.get("CUSTOM_DOMAIN_SYSTEM_HOSTNAMES", "localhost,example.com,example.test").split(",")
    if hostname.strip()
}
CUSTOM_DOMAIN_SYSTEM_SUFFIXES = {
    suffix.strip().lower().lstrip(".")
    for suffix in os.environ.get("CUSTOM_DOMAIN_SYSTEM_SUFFIXES", "localhost,platform.local").split(",")
    if suffix.strip()
}
CUSTOM_DOMAIN_CERT_MANAGER_PROVIDER = os.environ.get("CUSTOM_DOMAIN_CERT_MANAGER_PROVIDER", "cert-manager")
CERTIFICATE_EXPIRY_ALERT_DAYS = int(os.environ.get("CERTIFICATE_EXPIRY_ALERT_DAYS", "14"))
USAGE_VIEWER_CAN_VIEW_USAGE = os.environ.get("USAGE_VIEWER_CAN_VIEW_USAGE", "false").lower() in {"1", "true", "yes"}
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "no-reply@example.com")
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
NOTIFICATION_BASE_URL = os.environ.get("NOTIFICATION_BASE_URL", "http://localhost:3000")
NOTIFICATION_RATE_LIMIT_ATTEMPTS = int(os.environ.get("NOTIFICATION_RATE_LIMIT_ATTEMPTS", "20"))
NOTIFICATION_RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("NOTIFICATION_RATE_LIMIT_WINDOW_SECONDS", "3600"))
NOTIFICATION_MAX_RETRY_ATTEMPTS = int(os.environ.get("NOTIFICATION_MAX_RETRY_ATTEMPTS", "3"))
BACKUP_OUTPUT_DIR = os.environ.get("BACKUP_OUTPUT_DIR", str(BASE_DIR / "outputs" / "backups"))
BACKUP_RETENTION_DAYS = int(os.environ.get("BACKUP_RETENTION_DAYS", "30"))
BACKUP_ENCRYPTION_KEY = os.environ.get("BACKUP_ENCRYPTION_KEY", "")
BACKUP_PLATFORM_CONFIG_KEYS = [
    key.strip()
    for key in os.environ.get(
        "BACKUP_PLATFORM_CONFIG_KEYS",
        "DJANGO_SETTINGS_MODULE,DJANGO_ALLOWED_HOSTS,STATIC_DEPLOYMENT_STORAGE_BACKEND,STATIC_DEPLOYMENT_S3_BUCKET,STATIC_DEPLOYMENT_S3_REGION",
    ).split(",")
    if key.strip()
]
BACKUP_SECRET_FINGERPRINT_KEYS = [
    key.strip()
    for key in os.environ.get(
        "BACKUP_SECRET_FINGERPRINT_KEYS",
        "DJANGO_SECRET_KEY,BACKUP_ENCRYPTION_KEY,PROJECT_SECRET_ENCRYPTION_KEY,STRIPE_SECRET_KEY,STRIPE_WEBHOOK_SECRET",
    ).split(",")
    if key.strip()
]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "redact_secrets": {
            "()": "config.logging_filters.RedactSecretsFilter",
        },
        "request_context": {
            "()": "config.structured_logging.RequestContextFilter",
        },
    },
    "formatters": {
        "json": {
            "()": "config.structured_logging.JsonFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["redact_secrets", "request_context"],
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}
