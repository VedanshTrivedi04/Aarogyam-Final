"""
apps/iot/consumers.py — WebSocket command channel for dispenser firmware.

Replaces the old 10-second HTTP command poll. The device holds one socket open
and commands arrive as they are queued (see apps/iot/signals.py). The HTTP
command poll is kept as a low-frequency safety net, so a dropped socket delays
a command but never loses it.

    ws://host/ws/iot/device/<device_id>/?device_key=<api_key>

Device → server frames:
    {"type": "ack",  "command_id": "<uuid>"}
    {"type": "ping"}
Server → device frames:
    {"type": "command", "command_id": ..., "command_type": ..., "payload": {...}}
    {"type": "pong"}
"""
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.utils import timezone

logger = logging.getLogger(__name__)


def device_group_name(device_id) -> str:
    return f'iot-device-{device_id}'


class DeviceCommandConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.device = self.scope.get('device')
        url_device_id = self.scope['url_route']['kwargs']['device_id']

        # The key must belong to the device named in the URL.
        if not self.device or str(self.device.id) != str(url_device_id):
            await self.close(code=4003)
            return

        self.group_name = device_group_name(self.device.id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self._touch_last_seen()

        logger.info("Device %s connected to command channel", self.device.id)

        # Drain anything queued while the device was offline so a reconnect
        # doesn't wait for the safety-net poll.
        for command in await self._pending_commands():
            await self.send_json(command)

    async def disconnect(self, code):
        if getattr(self, 'group_name', None):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        msg_type = content.get('type')

        if msg_type == 'ping':
            await self.send_json({'type': 'pong',
                                  'server_unix_time': int(timezone.now().timestamp())})
        elif msg_type == 'ack':
            await self._acknowledge(content.get('command_id'))

    async def device_command(self, event):
        """Fan-out target for channel_layer.group_send from signals.py."""
        await self.send_json(event['command'])

    # ── DB helpers ──────────────────────────────────────────────────────────

    @database_sync_to_async
    def _touch_last_seen(self):
        type(self.device).objects.filter(id=self.device.id).update(
            last_seen_at=timezone.now()
        )

    @database_sync_to_async
    def _pending_commands(self):
        from .models import DeviceCommand

        pending = list(
            DeviceCommand.objects.filter(
                device=self.device, status='PENDING', expires_at__gt=timezone.now()
            ).order_by('created_at')
        )
        if pending:
            DeviceCommand.objects.filter(id__in=[c.id for c in pending]).update(status='SENT')

        return [
            {
                'type': 'command',
                'command_id': str(c.id),
                'command_type': c.command_type,
                'payload': c.payload,
            }
            for c in pending
        ]

    @database_sync_to_async
    def _acknowledge(self, command_id):
        from .models import DeviceCommand

        if not command_id:
            return
        DeviceCommand.objects.filter(id=command_id, device=self.device).update(
            status='ACKNOWLEDGED', acknowledged_at=timezone.now()
        )
