"""RFUND base settings.

All environments (development / test / production) share this module.
Only environment variables differ. See docs/DEPLOYMENT.md.

Security posture (spec §59, §167, §173):
  - secrets only from environment
  - production boot validation rejects DEBUG and placeholder secrets
  - never hard-code provider keys
"""

from datetime import timedelta
from pathlib import Path

from config.env import EnvError, env_bool, env_int, env_str, parse_database_url

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# Environment selection
# ---------------------------------------------------------------------------
DJANGO_ENV = env_str("DJANGO_ENV", "development")
if DJANGO_ENV not in {"development", "test", "production"}:
    raise EnvError(f"DJANGO_ENV must be development|test|production, got {DJANGO_ENV!r}")

SECRET_KEY = env_str("DJANGO_SECRET_KEY", "")
DEBUG = env_bool("DEBUG", DJANGO_ENV == "development")
ALLOWED_HOSTS = [
    h.strip()
    for h in (env_str("ALLOWED_HOSTS", "") or "").split(",")
    if h.strip()
]

# ---------------------------------------------------------------------------
# Production safety validation (spec §173)
# ---------------------------------------------------------------------------
if DJANGO_ENV == "production":
    if DEBUG:
        raise EnvError("DEBUG=True is not allowed in production")
    if not SECRET_KEY or "change-me" in SECRET_KEY.lower():
        raise EnvError("A real DJANGO_SECRET_KEY is required in production")
    if not ALLOWED_HOSTS:
        raise EnvError("ALLOWED_HOSTS is required in production")

if not SECRET_KEY:  # development/test fallback only
    SECRET_KEY = "dev-only-insecure-key-change-me"

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS: list[str] = []

LOCAL_APPS = [
    "apps.core",
    "apps.audit",
    "apps.accounts",
    "apps.customers",
    "apps.identity",
    "apps.ledger",
    "apps.payments",
    "apps.settlements",
    "apps.savings",
    "apps.loans",
    "apps.farmers",
    "apps.agriculture",
    "apps.agents",
    "apps.organizations",
    "apps.cooperatives",
    "apps.risk",
    "apps.fraud",
    "apps.notifications",
    "apps.support",
    "apps.documents",
    "apps.reporting",
    "apps.ussd",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.RequestIDMiddleware",
    "apps.core.middleware.StructuredRequestLoggingMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

ASGI_APPLICATION = "config.asgi.application"
WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Database (spec §56: database-level constraints; §95: UTC internally)
# ---------------------------------------------------------------------------
_database_url = env_str("DATABASE_URL", "postgres://rfund:rfund@localhost:5432/rfund")
_db = parse_database_url(_database_url)
DATABASES = {
    "default": {
        "ENGINE": _db.ENGINE,
        "NAME": _db.NAME,
        "USER": _db.USER,
        "PASSWORD": _db.PASSWORD,
        "HOST": _db.HOST,
        "PORT": _db.PORT,
        "OPTIONS": _db.OPTIONS,
        "CONN": {"autocommit": True} if _db.ENGINE.endswith("postgresql") else {},
        "ATOMIC_REQUESTS": False,
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Redis / Celery (spec §153)
# ---------------------------------------------------------------------------
REDIS_URL = env_str("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = env_str("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = env_str("CELERY_RESULT_BACKEND", REDIS_URL)
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", DJANGO_ENV == "test")
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300
CELERY_TASK_SOFT_TIME_LIMIT = 240
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# ---------------------------------------------------------------------------
# Authentication (spec §60) — opaque hashed tokens, rotation, revocation
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

# Token lifetimes
ACCESS_TOKEN_TTL = timedelta(minutes=30)
REFRESH_TOKEN_TTL = timedelta(days=14)
OTP_TTL = timedelta(minutes=5)
OTP_MAX_ATTEMPTS = 5
LOGIN_MAX_FAILURES = 5
LOGIN_LOCKOUT_MINUTES = 15

# ---------------------------------------------------------------------------
# Money (spec §3.3, §3.4)
# ---------------------------------------------------------------------------
BASE_CURRENCY = env_str("BASE_CURRENCY", "NGN")
SUPPORTED_CURRENCIES = ["NGN", "USD", "EUR", "GBP"]
MONEY_MAX_DIGITS = 19
MONEY_DECIMAL_PLACES = 2

# ---------------------------------------------------------------------------
# Payments (spec §22–§27)
# ---------------------------------------------------------------------------
PAYMENT_PROVIDER = env_str("PAYMENT_PROVIDER", "paystack")
PAYSTACK_SECRET_KEY = env_str("PAYSTACK_SECRET_KEY", "")
PAYSTACK_PUBLIC_KEY = env_str("PAYSTACK_PUBLIC_KEY", "")
PAYSTACK_WEBHOOK_SECRET = env_str("PAYSTACK_WEBHOOK_SECRET", "")
PAYSTACK_BASE_URL = env_str("PAYSTACK_BASE_URL", "https://api.paystack.co")
PAYSTACK_TIMEOUT_SECONDS = env_int("PAYSTACK_TIMEOUT_SECONDS", 20)

# The deterministic local provider is for development/test ONLY.
# It can never be selected in production (spec §102: no accidental demo mode).
ALLOW_LOCAL_PAYMENT_PROVIDER = env_bool("ALLOW_LOCAL_PAYMENT_PROVIDER", False)
if DJANGO_ENV == "production":
    ALLOW_LOCAL_PAYMENT_PROVIDER = False

# ---------------------------------------------------------------------------
# Notifications / SMS (spec §47, §187)
# ---------------------------------------------------------------------------
SMS_PROVIDER = env_str("SMS_PROVIDER", "console")
SMS_PROVIDER_KEY = env_str("SMS_PROVIDER_KEY", "")
EMAIL_BACKEND = env_str(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend"
    if DJANGO_ENV != "production"
    else "django.core.mail.backends.smtp.EmailBackend",
)
DEFAULT_FROM_EMAIL = env_str("DEFAULT_FROM_EMAIL", "RFUND <no-reply@rfund.example>")

# ---------------------------------------------------------------------------
# Documents / object storage (spec §62)
# ---------------------------------------------------------------------------
STORAGE_BACKEND = env_str("STORAGE_BACKEND", "local")
MEDIA_ROOT = Path(env_str("MEDIA_ROOT", str(BASE_DIR / "media")))
MEDIA_URL = "/media/"
MAX_UPLOAD_BYTES = env_int("MAX_UPLOAD_BYTES", 5 * 1024 * 1024)
ALLOWED_UPLOAD_EXTENSIONS = ["pdf", "jpg", "jpeg", "png", "webp"]
OBJECT_STORAGE_KEY = env_str("OBJECT_STORAGE_KEY", "")
OBJECT_STORAGE_SECRET = env_str("OBJECT_STORAGE_SECRET", "")
OBJECT_STORAGE_BUCKET = env_str("OBJECT_STORAGE_BUCKET", "")
OBJECT_STORAGE_ENDPOINT = env_str("OBJECT_STORAGE_ENDPOINT", "")
SIGNED_URL_TTL_SECONDS = env_int("SIGNED_URL_TTL_SECONDS", 300)

# ---------------------------------------------------------------------------
# Observability (spec §90, §170)
# ---------------------------------------------------------------------------
SENTRY_DSN = env_str("SENTRY_DSN", "")
LOG_LEVEL = env_str("LOG_LEVEL", "INFO" if DJANGO_ENV == "production" else "DEBUG")
LOG_REQUESTS = env_bool("LOG_REQUESTS", True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {"()": "apps.core.logging.RequestIDLogFilter"},
    },
    "formatters": {
        "json": {
            "()": "apps.core.logging.StructuredFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["request_id"],
            "formatter": "json",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"level": LOG_LEVEL, "propagate": True},
        "django.server": {"level": "INFO", "propagate": True},
        "django.db.backends": {"level": "WARNING", "propagate": False},
        "rfund": {"level": LOG_LEVEL, "propagate": True},
        # Never let provider HTTP bodies leak at DEBUG in production paths.
        "httpx": {"level": "WARNING"},
    },
}

# ---------------------------------------------------------------------------
# Timezone / i18n (spec §95, §98)
# ---------------------------------------------------------------------------
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
DISPLAY_TIMEZONE = env_str("DISPLAY_TIMEZONE", "Africa/Lagos")
LANGUAGE_CODE = "en"

# ---------------------------------------------------------------------------
# GraphQL security (spec §115)
# ---------------------------------------------------------------------------
GRAPHQL_DEPTH_LIMIT = env_int("GRAPHQL_DEPTH_LIMIT", 8)
GRAPHQL_MAX_OPERATION_BYTES = env_int("GRAPHQL_MAX_OPERATION_BYTES", 100_000)
GRAPHQL_DEFAULT_PAGE_SIZE = env_int("GRAPHQL_DEFAULT_PAGE_SIZE", 20)
GRAPHQL_MAX_PAGE_SIZE = env_int("GRAPHQL_MAX_PAGE_SIZE", 100)

# Rate limits (requests/minute) by actor class (spec §164)
RATE_LIMIT_ANONYMOUS = env_int("RATE_LIMIT_ANONYMOUS", 60)
RATE_LIMIT_CUSTOMER = env_int("RATE_LIMIT_CUSTOMER", 240)
RATE_LIMIT_AGENT = env_int("RATE_LIMIT_AGENT", 480)
RATE_LIMIT_ADMIN = env_int("RATE_LIMIT_ADMIN", 600)
RATE_LIMIT_WEBHOOK = env_int("RATE_LIMIT_WEBHOOK", 600)

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------
STATIC_ROOT = Path(env_str("STATIC_ROOT", str(BASE_DIR / "staticfiles")))
STATIC_URL = "/static/"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if DJANGO_ENV == "production"
        else "django.core.files.storage.FileSystemStorage"
    },
}

# ---------------------------------------------------------------------------
# Security headers (spec §59)
# ---------------------------------------------------------------------------
if DJANGO_ENV == "production":
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 31_536_000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in (env_str("CSRF_TRUSTED_ORIGINS", "") or "").split(",") if o.strip()
]

# CORS: the Next.js BFF proxies requests server-side, so the browser talks to
# its own origin. Direct browser-to-API CORS is only enabled explicitly.
CORS_ALLOWED_ORIGINS = [
    o.strip() for o in (env_str("CORS_ALLOWED_ORIGINS", "") or "").split(",") if o.strip()
]

# ---------------------------------------------------------------------------
# Seed safety (spec §175)
# ---------------------------------------------------------------------------
ALLOW_SEED_IN_PRODUCTION = False  # hard guard; no override accepted
