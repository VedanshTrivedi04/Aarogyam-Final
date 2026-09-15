from .base import *
import os

DEBUG = False

# Reverse proxy SSL header (Critical for Render to prevent 301 HTTPS redirect loops)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Allowed Hosts: allow custom comma-separated list, or default to all on Render
_hosts = [h.strip() for h in os.environ.get('ALLOWED_HOSTS', '').split(',') if h.strip()]
ALLOWED_HOSTS = _hosts if _hosts else ['*']

# CORS settings: Support Vercel frontend deployments and custom origins
_cors = [o.strip() for o in os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',') if o.strip()]
CORS_ALLOWED_ORIGINS = _cors
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://.*\.vercel\.app$",
]
if os.environ.get('CORS_ALLOW_ALL_ORIGINS', 'True').lower() == 'true':
    CORS_ALLOW_ALL_ORIGINS = True

# CSRF Trusted Origins (Required in Django 4+ for cross-origin POST requests)
_csrf = [o.strip() for o in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',') if o.strip()]
CSRF_TRUSTED_ORIGINS = _csrf if _csrf else [
    'https://*.onrender.com',
    'https://*.vercel.app',
]
for origin in CORS_ALLOWED_ORIGINS:
    if origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(origin)

# Redis & Celery Configuration
if os.environ.get('REDIS_URL'):
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                'hosts': [os.environ['REDIS_URL']],
            },
        },
    }
    CELERY_BROKER_URL = os.environ['REDIS_URL']
    CELERY_TASK_ALWAYS_EAGER = os.environ.get('CELERY_TASK_ALWAYS_EAGER', 'False').lower() == 'true'
else:
    CELERY_TASK_ALWAYS_EAGER = True

# HTTPS & Cookie Security
SECURE_SSL_REDIRECT             = os.environ.get('SECURE_SSL_REDIRECT', 'True').lower() == 'true'
SECURE_HSTS_SECONDS             = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS  = True
SECURE_HSTS_PRELOAD             = True
SESSION_COOKIE_SECURE           = True
CSRF_COOKIE_SECURE              = True

# Email Backend (Inherits Brevo / Resend / SendGrid Anymail HTTP backend if configured in base.py)
if not (os.environ.get('BREVO_API_KEY') or os.environ.get('RESEND_API_KEY') or os.environ.get('SENDGRID_API_KEY') or os.environ.get('MAILGUN_API_KEY')):
    EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')


# Sentry error monitoring (optional)
sentry_dsn = os.environ.get('SENTRY_DSN')
if sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration

    sentry_sdk.init(
        dsn=sentry_dsn,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=0.2,
        send_default_pii=False,
    )
