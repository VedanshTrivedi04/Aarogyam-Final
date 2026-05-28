"""
Django base settings for MedAdhere backend.
"""
import os
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me-in-production')

INSTALLED_APPS = [
    'daphne',                          # Must be FIRST for ASGI/WebSocket support
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'channels',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
    'anymail', # added for HTTP email sending
    'django_celery_beat',
    'django_celery_results',

    # Internal apps
    'apps.core',
    'apps.identity',
    'apps.clinical',
    'apps.scheduling',
    'apps.telemetry',
    'apps.iot',
    'apps.subscriptions',
    'apps.store',
    'apps.notifications',
    'apps.communications',             # Phase: Real-time Chat & Call
    'apps.audit',
    'apps.admin_panel',
    'apps.analytics',
    'apps.ai_engine',
    'shared',

    # ── Extension Apps (Phases 13–28) ────────────────────────────────
    'apps.pharmacy',           # Phase 13: Auto-Refill
    'apps.doctor_portal',      # Phase 14: Doctor Portal
    'apps.whatsapp_bot',       # Phase 15: WhatsApp Bot
    'apps.family',             # Phase 17: Family Multi-Patient
    'apps.fhir_integration',   # Phase 18: FHIR / HL7 EHR
    'apps.vitals',             # Phase 19: Vital Signs
    'apps.gamification',       # Phase 20: Gamification
    'apps.pharmacovigilance',  # Phase 21: Pharmacovigilance
    'apps.insurance_reports',  # Phase 24: Insurance Reports
    'apps.geofence',           # Phase 26: Geofence
    'apps.abha',               # Phase 27: ABHA / ABDM
    'apps.tenants',            # Phase 28: Multi-Tenant
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'shared.middleware.RequestLogMiddleware',
    'apps.family.middleware.FamilyContextMiddleware',  # X-Patient-Context header
    'apps.tenants.middleware.TenantMiddleware',         # Multi-tenant context
]

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

AUTH_USER_MODEL = 'identity.User'

# ─── Database ────────────────────────────────────────────────────────────────
# MedAdhere is designed for PostgreSQL; use the env-backed Postgres database.
DATABASES = {
    'default': {
       'ENGINE':       os.environ.get('DB_ENGINE', 'django.db.backends.postgresql'),
        'NAME':         os.environ.get('DB_NAME', 'medadhere'),
        'USER':         os.environ.get('DB_USER', 'postgres'),
        'PASSWORD':     os.environ.get('DB_PASSWORD', 'root'),
        'HOST':         os.environ.get('DB_HOST', '127.0.0.1'),  # IP avoids reverse-DNS lookup
        'PORT':         os.environ.get('DB_PORT', '5432'),
        'CONN_MAX_AGE': 600,   # Reuse connections for 10 min — critical for cloud DBs like Neon
        'CONN_HEALTH_CHECKS': True,
        'OPTIONS': {
            'connect_timeout': 10,
            'sslmode': 'require',  # Neon requires SSL; explicit here prevents per-request TLS negotiation
        },
    }
}

# ─── Cache / Redis ───────────────────────────────────────────────────────────
REDIS_URL = os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0')

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
    }
}

# ─── Django Channels ─────────────────────────────────────────────────────────
# Use InMemoryChannelLayer by default (works without Redis).
# Override to RedisChannelLayer in production settings for multi-process support.
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}

# ─── Celery ──────────────────────────────────────────────────────────────────
CELERY_BROKER_URL          = REDIS_URL
CELERY_RESULT_BACKEND      = 'django-db'
CELERY_ACCEPT_CONTENT      = ['json']
CELERY_TASK_SERIALIZER     = 'json'
CELERY_RESULT_SERIALIZER   = 'json'
CELERY_TIMEZONE            = 'UTC'
CELERY_BEAT_SCHEDULER      = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_TASK_TRACK_STARTED  = True
CELERY_TASK_TIME_LIMIT     = 300   # 5 min hard limit per task

# ─── REST Framework ──────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'apps.identity.authentication.MedAdhereJWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'shared.pagination.StandardResultsPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'shared.exceptions.custom_exception_handler',
}

# ─── SimpleJWT ───────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':      timedelta(days=1),
    'REFRESH_TOKEN_LIFETIME':     timedelta(days=30),
    'ROTATE_REFRESH_TOKENS':      True,
    'BLACKLIST_AFTER_ROTATION':   True,
    'UPDATE_LAST_LOGIN':          True,
    'ALGORITHM':                  'HS256',
    'SIGNING_KEY':                SECRET_KEY,
    'AUTH_HEADER_TYPES':          ('Bearer',),
    'USER_ID_FIELD':              'id',
    'USER_ID_CLAIM':              'user_id',
    'AUTH_TOKEN_CLASSES':         ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM':           'token_type',
    'JTI_CLAIM':                  'jti',
}

# ─── DRF Spectacular (OpenAPI) ────────────────────────────────────────────────
SPECTACULAR_SETTINGS = {
    'TITLE': 'MedAdhere API',
    'DESCRIPTION': 'Medication Adherence Platform — Backend API',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
}

# ─── Encryption ──────────────────────────────────────────────────────────────
FIELD_ENCRYPTION_KEY = os.environ.get('FIELD_ENCRYPTION_KEY', '')

# ─── Auth / Social ────────────────────────────────────────────────────────────
GOOGLE_CLIENT_ID     = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
FRONTEND_URL         = os.environ.get('FRONTEND_URL', 'http://localhost:3000')

# ─── Payment / Razorpay ──────────────────────────────────────────────────────
RAZORPAY_KEY_ID       = os.environ.get('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET   = os.environ.get('RAZORPAY_KEY_SECRET', '')
RAZORPAY_WEBHOOK_SECRET = os.environ.get('RAZORPAY_WEBHOOK_SECRET', '')

# ─── Notification Providers ───────────────────────────────────────────────────
TWILIO_ACCOUNT_SID  = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN   = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_FROM_NUMBER  = os.environ.get('TWILIO_FROM_NUMBER', '')
TWILIO_MESSAGING_SERVICE_SID = os.environ.get('TWILIO_MESSAGING_SERVICE_SID', '')
FCM_SERVER_KEY      = os.environ.get('FCM_SERVER_KEY', '')
SENDGRID_API_KEY    = os.environ.get('SENDGRID_API_KEY', '')
GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', 'AIzaSyAaHAE2MVl1Lrf48O0KJ7-L7MtXWkNgojY')
DEFAULT_FROM_EMAIL  = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@medadhere.com')

# SMTP / HTTP Email Settings
EMAIL_BACKEND       = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST          = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT          = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS       = os.environ.get('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_HOST_USER     = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_TIMEOUT       = 8   # prevents SMTP from hanging HTTP requests if Gmail is slow

# Bypass SMTP on Hugging Face / Vercel using Anymail HTTP API
ANYMAIL = {}
if SENDGRID_API_KEY:
    EMAIL_BACKEND = "anymail.backends.sendgrid.EmailBackend"
    ANYMAIL["SENDGRID_API_KEY"] = SENDGRID_API_KEY
elif os.environ.get('RESEND_API_KEY'):
    EMAIL_BACKEND = "anymail.backends.resend.EmailBackend"
    ANYMAIL["RESEND_API_KEY"] = os.environ.get('RESEND_API_KEY')
elif os.environ.get('MAILGUN_API_KEY'):
    EMAIL_BACKEND = "anymail.backends.mailgun.EmailBackend"
    ANYMAIL["MAILGUN_API_KEY"] = os.environ.get('MAILGUN_API_KEY')
    ANYMAIL["MAILGUN_SENDER_DOMAIN"] = os.environ.get('MAILGUN_SENDER_DOMAIN', '')

# ─── Static / Media ──────────────────────────────────────────────────────────
STATIC_URL  = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL   = '/media/'
MEDIA_ROOT  = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LANGUAGE_CODE = 'en-us'
TIME_ZONE     = 'UTC'
USE_I18N      = True
USE_TZ        = True

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# ─── Logging ─────────────────────────────────────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'verbose'},
    },
    'root': {'handlers': ['console'], 'level': 'INFO'},
    'loggers': {
        'medadhere': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': False},
        'medadhere.agents': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'medadhere.ai_engine': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}

# ─── AI Engine ───────────────────────────────────────────────────────────────
AI_MODEL_DIR = BASE_DIR / 'apps/ai_engine/models/artifacts'
AI_DATA_DIR = BASE_DIR / 'apps/ai_engine/datasets/raw'