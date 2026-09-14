"""
config/asgi.py — ASGI entrypoint for HTTP + WebSocket (Django Channels).
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from config.ws_routing import websocket_urlpatterns
from apps.communications.middleware import JWTAuthMiddleware
from apps.iot.ws_auth import DeviceKeyAuthMiddleware

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    # Both auth layers run: DeviceKey sets scope['device'] for firmware,
    # JWT sets scope['user'] for browser clients. Each consumer checks its own.
    'websocket': DeviceKeyAuthMiddleware(
        JWTAuthMiddleware(
            URLRouter(websocket_urlpatterns)
        )
    ),
})
