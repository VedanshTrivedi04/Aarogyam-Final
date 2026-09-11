"""
apps/iot/signals.py — Push queued commands to the device over WebSocket.

Hooking post_save means every existing place that creates a DeviceCommand
(fill mode, caregiver unlock, gate lock, config bump, ...) becomes push-enabled
without touching those call sites.

Delivery is at-least-once by design: the row stays PENDING until the device
acks it, so a command is never lost to a dropped socket. The firmware must
therefore ignore a command_id it has already handled.
"""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .consumers import device_group_name
from .models import DeviceCommand

logger = logging.getLogger(__name__)


@receiver(post_save, sender=DeviceCommand, dispatch_uid='iot_push_command')
def push_command_to_device(sender, instance: DeviceCommand, created: bool, **kwargs):
    if not created or instance.status != 'PENDING':
        return

    frame = {
        'type': 'command',
        'command_id': str(instance.id),
        'command_type': instance.command_type,
        'payload': instance.payload,
    }
    device_id = instance.device_id

    def _send():
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        try:
            async_to_sync(channel_layer.group_send)(
                device_group_name(device_id),
                {'type': 'device_command', 'command': frame},
            )
        except Exception as exc:
            # An offline device is the normal case, not an error — the row stays
            # PENDING and is drained on reconnect or by the safety-net poll.
            logger.debug("Could not push %s to device %s: %s",
                         instance.command_type, device_id, exc)

    transaction.on_commit(_send)
