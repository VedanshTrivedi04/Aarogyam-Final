"""
apps/iot/ws_auth.py — Device API-key authentication for WebSocket connections.

Firmware has no JWT, so it authenticates the same way it does over HTTP:
its api_key, passed as a query param because ESP32 WebSocket clients can't
set custom headers during the handshake.

    ws://host/ws/iot/device/<device_id>/?device_key=<api_key>

Composes with JWTAuthMiddleware rather than replacing it — this one only sets
scope['device'], leaving scope['user'] to the JWT layer, so browser consumers
are unaffected.
"""
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware


@database_sync_to_async
def get_device_from_key(api_key: str):
    from .models import Device

    return Device.objects.filter(api_key=api_key, is_active=True).first()


class DeviceKeyAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        params = parse_qs(scope.get('query_string', b'').decode())
        device_key = params.get('device_key', [None])[0]

        scope['device'] = await get_device_from_key(device_key) if device_key else None

        return await super().__call__(scope, receive, send)
