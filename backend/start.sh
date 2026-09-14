#!/usr/bin/env bash
set -o errexit

echo "================================================="
echo " Starting Aarogyam / MedAdhere Backend Service   "
echo "================================================="

# Start background Celery worker and beat if REDIS_URL is provided
if [ -n "$REDIS_URL" ]; then
    echo "==> [CELERY] Starting Celery Worker & Beat scheduler in background (solo pool for minimal RAM)..."
    celery -A config worker --beat -l info -P solo \
        --scheduler django_celery_beat.schedulers:DatabaseScheduler \
        --pidfile=/tmp/celerybeat.pid &
    CELERY_PID=$!
    echo "==> [CELERY] Worker & Beat started with PID: $CELERY_PID"
else
    echo "==> [CELERY] Notice: REDIS_URL not set. Running in Eager mode (no background worker)."
fi

# Start background MQTT bridge if MQTT_BROKER is provided
if [ -n "$MQTT_BROKER" ]; then
    echo "==> [MQTT] Starting MQTT Bridge daemon in background ($MQTT_BROKER)..."
    python scripts/mqtt_bridge.py &
    MQTT_PID=$!
    echo "==> [MQTT] Bridge daemon started with PID: $MQTT_PID"
else
    echo "==> [MQTT] Notice: MQTT_BROKER not set. Skipping MQTT bridge."
fi

# Start Daphne ASGI server in foreground to serve HTTP & WebSockets on $PORT
# --proxy-headers ensures Daphne trusts Render's X-Forwarded-Proto: https
echo "==> [DAPHNE] Starting Daphne ASGI server on port ${PORT:-8000}..."
exec daphne -b 0.0.0.0 -p "${PORT:-8000}" --proxy-headers config.asgi:application
