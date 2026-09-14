from .base import *

DEBUG = True
ALLOWED_HOSTS = ['*']

# Accept comma-separated origins via env when provided, else fall back to common dev ports.
CORS_ALLOWED_ORIGINS = [o.strip() for o in os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',') if o.strip()] or [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]
CORS_ALLOW_CREDENTIALS = True


# Use console email backend only if no SMTP credentials are configured.
# If EMAIL_HOST_USER is set in .env, use SMTP so real emails (OTP, verification) arrive.
if not os.environ.get('EMAIL_HOST_USER'):
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Run Celery tasks synchronously in development (no worker needed).
# NOTE: .delay() calls block the caller — EMAIL_TIMEOUT=8s in base.py limits SMTP hangs.
CELERY_TASK_ALWAYS_EAGER = True

# Use Redis channel layer and cache when Redis is available (e.g. Docker),
# otherwise fall back to LocMemCache and InMemoryChannelLayer for bare local dev.
redis_url = os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0')
redis_available = False
try:
    import redis
    r = redis.from_url(redis_url, socket_connect_timeout=1, socket_timeout=1)
    r.ping()
    redis_available = True
except Exception:
    redis_available = False

if redis_available:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': redis_url,
        }
    }
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                'hosts': [redis_url],
            },
        },
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        },
    }

# Allow WebSocket connections from all origins in dev (Cloudflare tunnel + localhost)
CORS_ALLOW_ALL_ORIGINS = True