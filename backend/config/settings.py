"""Django settings for the University Portal API."""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-key-change-me-in-production-0123456789")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "django_filters",
    # Local
    "apps.core",
    "apps.accounts",
    "apps.academics",
    "apps.campus",
    "apps.finance",
    "apps.website",
    "apps.attendance",
    "apps.admissions",
    "apps.students",
    "apps.reports",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

WSGI_APPLICATION = "config.wsgi.application"

# PostgreSQL is the primary database. USE_SQLITE=1 exists only for quick
# throwaway runs (e.g. CI without a database service).
if env_bool("USE_SQLITE"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB", "university_portal"),
            "USER": os.getenv("POSTGRES_USER", "portal"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", "portal"),
            "HOST": os.getenv("POSTGRES_HOST", "localhost"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("TIME_ZONE", "Africa/Lagos")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Uploaded files. Profile photos (media/avatars/) are public; proofs of payment are never
# served directly: the API checks access first.
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", BASE_DIR / "media"))
MEDIA_URL = "/media/"
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    # Money is returned as JSON numbers rather than strings.
    "COERCE_DECIMAL_TO_STRING": False,
    # Only views that opt in (with a throttle_scope) are rate-limited.
    "DEFAULT_THROTTLE_RATES": {
        "contact": os.getenv("CONTACT_RATE", "5/hour"),
        "checkin": os.getenv("CHECKIN_RATE", "20/minute"),
        "apply": os.getenv("APPLY_SIGNUP_RATE", "10/hour"),
        "chat": os.getenv("CHAT_RATE", "60/hour"),
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
}

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")

# Needed when the admin is reached through a proxy or domain whose Origin differs
# from the Host Django sees, e.g. "https://portal.example.edu".
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

UNIVERSITY_NAME = os.getenv("UNIVERSITY_NAME", "BULACODE UNIVERSITY")
UNIVERSITY_ADDRESS = os.getenv("UNIVERSITY_ADDRESS", "Office of Student Accounts (Bursary)")
UNIVERSITY_SHORT_NAME = os.getenv("UNIVERSITY_SHORT_NAME", "BULACODE")
# Public address of the portal, used for links in emails (e.g. https://portal.bulacode.edu.ng).
PORTAL_URL = os.getenv("PORTAL_URL", "http://localhost:5173")

# SMS alerts: "console" logs them; "termii" sends through Termii.
SMS_BACKEND = os.getenv("SMS_BACKEND", "console")
TERMII_API_KEY = os.getenv("TERMII_API_KEY", "")
TERMII_SENDER_ID = os.getenv("TERMII_SENDER_ID", "")

# Attendance: QR/check-in codes rotate every ATTENDANCE_CODE_SECONDS; students below
# ATTENDANCE_MIN_PERCENT are flagged (75% is the usual requirement to sit examinations).
ATTENDANCE_CODE_SECONDS = int(os.getenv("ATTENDANCE_CODE_SECONDS", "20"))
ATTENDANCE_MIN_PERCENT = int(os.getenv("ATTENDANCE_MIN_PERCENT", "75"))

# Course registration limits (units per semester).
MIN_UNITS_PER_SEMESTER = int(os.getenv("MIN_UNITS_PER_SEMESTER", "15"))
MAX_UNITS_PER_SEMESTER = int(os.getenv("MAX_UNITS_PER_SEMESTER", "24"))

# Email: receipts are emailed to students. In development they are printed to the
# console unless SMTP settings are provided.
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", f"{UNIVERSITY_NAME} Bursary <bursary@example.edu>")
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_BACKEND = (
    "django.core.mail.backends.smtp.EmailBackend" if EMAIL_HOST else "django.core.mail.backends.console.EmailBackend"
)

# Bursary bank account shown to students paying offline (and on invoices). Leave blank to hide.
BURSARY_BANK_NAME = os.getenv("BURSARY_BANK_NAME", "")
BURSARY_ACCOUNT_NAME = os.getenv("BURSARY_ACCOUNT_NAME", "")
BURSARY_ACCOUNT_NUMBER = os.getenv("BURSARY_ACCOUNT_NUMBER", "")
# Optional address notified when a student uploads a proof of payment.
BURSARY_NOTIFY_EMAIL = os.getenv("BURSARY_NOTIFY_EMAIL", "")

# Paystack (https://dashboard.paystack.com/#/settings/developers). With no secret key,
# online payment is switched off (every online payment goes through Paystack).
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "")
PAYSTACK_BASE_URL = os.getenv("PAYSTACK_BASE_URL", "https://api.paystack.co")
# Where Paystack sends the student after checkout. Defaults to
# <the portal's own origin>/fees/paystack/callback.
PAYSTACK_CALLBACK_URL = os.getenv("PAYSTACK_CALLBACK_URL", "")

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_CONTENT_TYPE_NOSNIFF = True

# Website chatbot. With an Anthropic API key it answers with Claude; without one it uses built-in answers.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CHATBOT_MODEL = os.getenv("CHATBOT_MODEL", "claude-sonnet-5")
