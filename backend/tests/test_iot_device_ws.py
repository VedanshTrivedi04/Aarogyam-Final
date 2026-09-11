"""
WebSocket command channel: auth, live push, reconnect drain, ack.
Uses TransactionTestCase so transaction.on_commit callbacks actually fire.
"""
from asgiref.sync import async_to_sync, sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase
from django.utils import timezone

from apps.identity.models import User
from apps.iot.models import Device, DeviceCommand
from config.asgi import application


class DeviceCommandChannelTest(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='ws@example.com', password='x', full_name='WS',
        )
        self.device = Device.objects.create(
            user=self.user, device_name='WS Dispenser', api_key='wskey' * 4,
        )
        self.url = f'/ws/iot/device/{self.device.id}/?device_key={self.device.api_key}'

    def _queue(self, command_type, payload=None):
        from datetime import timedelta
        return DeviceCommand.objects.create(
            device=self.device,
            command_type=command_type,
            payload=payload or {},
            expires_at=timezone.now() + timedelta(hours=1),
        )

    def test_rejects_bad_device_key(self):
        async def scenario():
            comm = WebsocketCommunicator(
                application, f'/ws/iot/device/{self.device.id}/?device_key=wrong'
            )
            connected, _ = await comm.connect()
            self.assertFalse(connected)

        async_to_sync(scenario)()

    def test_rejects_key_for_a_different_device(self):
        other = Device.objects.create(
            user=self.user, device_name='Other', api_key='otherkey' * 3,
        )

        async def scenario():
            # Valid key, but the URL names a device it does not own.
            comm = WebsocketCommunicator(
                application, f'/ws/iot/device/{other.id}/?device_key={self.device.api_key}'
            )
            connected, _ = await comm.connect()
            self.assertFalse(connected)

        async_to_sync(scenario)()

    def test_live_push_and_ack(self):
        async def scenario():
            comm = WebsocketCommunicator(application, self.url)
            connected, _ = await comm.connect()
            self.assertTrue(connected)
            self.assertTrue(await comm.receive_nothing())

            cmd = await sync_to_async(self._queue)(
                'GATE_UNLOCK', {'reason': 'caregiver remote unlock'}
            )

            frame = await comm.receive_json_from(timeout=3)
            self.assertEqual(frame['type'], 'command')
            self.assertEqual(frame['command_type'], 'GATE_UNLOCK')
            self.assertEqual(frame['command_id'], str(cmd.id))
            self.assertEqual(frame['payload']['reason'], 'caregiver remote unlock')

            await comm.send_json_to({'type': 'ack', 'command_id': frame['command_id']})
            await comm.receive_nothing(timeout=0.5)

            await sync_to_async(cmd.refresh_from_db)()
            self.assertEqual(cmd.status, 'ACKNOWLEDGED')
            self.assertIsNotNone(cmd.acknowledged_at)

            await comm.disconnect()

        async_to_sync(scenario)()

    def test_pending_commands_drain_on_connect(self):
        """A command queued while the device was offline arrives on reconnect."""
        cmd = self._queue('TRIGGER_DOSE', {'compartment': 2})

        async def scenario():
            comm = WebsocketCommunicator(application, self.url)
            connected, _ = await comm.connect()
            self.assertTrue(connected)

            frame = await comm.receive_json_from(timeout=3)
            self.assertEqual(frame['command_type'], 'TRIGGER_DOSE')
            self.assertEqual(frame['command_id'], str(cmd.id))

            await comm.disconnect()

        async_to_sync(scenario)()

        # Still PENDING: only an ack clears a command, so one lost to a dying
        # socket is re-delivered on the next reconnect.
        cmd.refresh_from_db()
        self.assertEqual(cmd.status, 'PENDING')

    def test_ping_pong(self):
        async def scenario():
            comm = WebsocketCommunicator(application, self.url)
            await comm.connect()
            await comm.send_json_to({'type': 'ping'})
            frame = await comm.receive_json_from(timeout=3)
            self.assertEqual(frame['type'], 'pong')
            self.assertGreater(frame['server_unix_time'], 0)
            await comm.disconnect()

        async_to_sync(scenario)()

    def test_config_bump_pushes_sync_config(self):
        """Changing a slot time must reach a connected device immediately."""
        async def scenario():
            comm = WebsocketCommunicator(application, self.url)
            await comm.connect()

            from apps.iot.config_service import bump_schedule_version
            await sync_to_async(bump_schedule_version)(self.device, 'slot_time_updated')

            frame = await comm.receive_json_from(timeout=3)
            self.assertEqual(frame['command_type'], 'SYNC_CONFIG')
            self.assertEqual(frame['payload']['reason'], 'slot_time_updated')

            await comm.disconnect()

        async_to_sync(scenario)()
