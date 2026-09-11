"""
Pins the exact HTTP response shapes the ESP32 firmware parses.

These are the contracts that broke silently before: the firmware read
`data.response_data.dose_status` while the endpoint returned `data.dose_status`,
so dose verification never completed. A field rename here must fail a test,
not a patient's dose.
"""
import json
import uuid

from django.test import Client, TestCase

from apps.identity.models import User
from apps.iot.models import Device, PhysicalCompartment, SubCompartment
from apps.iot.weight_service import process_fill_measurement


class FirmwareContractTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='fw@example.com', password='x', full_name='FW',
        )
        self.device = Device.objects.create(
            user=self.user, device_name='FW Dispenser', api_key='fwkey' * 6,
        )
        self.client = Client(headers={'x-device-key': self.device.api_key})

        slots = ['morning_before', 'morning_after', 'night_before', 'night_after']
        times = ['08:00', '09:00', '20:00', '21:00']
        self.comps = []
        for i, (slot, t) in enumerate(zip(slots, times), start=1):
            comp = PhysicalCompartment.objects.create(
                device=self.device, compartment_number=i, time_slot=slot,
                scheduled_time=t,
            )
            SubCompartment.objects.create(
                compartment=comp, medicine_name=f'Med{i}',
                quantity_per_dose=1, duration_days=10, total_pills=10,
            )
            self.comps.append(comp)

        # 100g in compartment 1 over 10 pills -> a 10g dose
        process_fill_measurement(
            self.device, self.comps[0], 100.0,
            medicine_id=str(self.comps[0].sub_compartments.first().id),
        )
        self.device.refresh_from_db()

    def _post(self, url, payload):
        return self.client.post(url, data=json.dumps(payload),
                                content_type='application/json')

    # ── GET /config/ — sched_parseBundle() in schedule.h ────────────────────
    def test_config_bundle_contract(self):
        res = self.client.get(f'/api/v1/iot/devices/{self.device.id}/config/')
        self.assertEqual(res.status_code, 200)
        data = res.json()['data']

        # Keys sched_parseBundle reads off data
        for key in ('schedule_version', 'policy', 'compartments',
                    'total_weight_grams', 'is_gate_locked'):
            self.assertIn(key, data, f'config bundle missing "{key}"')

        for key in ('dose_window_minutes', 'catchup_window_minutes',
                    'max_gate_opens', 'weight_settle_ms', 'hand_detect_cm'):
            self.assertIn(key, data['policy'], f'policy missing "{key}"')

        comp = data['compartments'][0]
        for key in ('compartment_number', 'enabled', 'time', 'time_slot',
                    'display_text', 'audio_track', 'content_weight_grams',
                    'expected_dose_reduction_grams'):
            self.assertIn(key, comp, f'compartment missing "{key}"')

        # "HH:MM" is what sscanf("%d:%d") expects
        self.assertRegex(comp['time'], r'^\d{2}:\d{2}$')
        self.assertTrue(comp['enabled'])

    def test_config_rejects_a_foreign_device_key(self):
        other = Device.objects.create(
            user=self.user, device_name='Other', api_key='otherkey' * 4,
        )
        res = self.client.get(f'/api/v1/iot/devices/{other.id}/config/')
        self.assertEqual(res.status_code, 403)

    # ── POST /events/ — dose_status path read in taskSensor ─────────────────
    def test_weight_reading_dose_status_path(self):
        session_uuid = str(uuid.uuid4())

        started = self._post('/api/v1/iot/events/', {
            'event_uuid': str(uuid.uuid4()),
            'event_type': 'DOSE_STARTED',
            'compartment_num': 1,
            'session_uuid': session_uuid,
            'weight_before': 100.0,
            'occurred_at': '2026-09-12T08:00:05',
        })
        self.assertEqual(started.status_code, 200)
        self.assertIn('session_id', started.json()['data'])

        after = self._post('/api/v1/iot/events/', {
            'event_uuid': str(uuid.uuid4()),
            'event_type': 'WEIGHT_READING',
            'compartment_num': 1,
            'weight_grams': 90.0,          # full 10g dose removed
            'phase': 'after_dose',
            'session_uuid': session_uuid,
            'occurred_at': '2026-09-12T08:02:00',
        })
        self.assertEqual(after.status_code, 200)
        data = after.json()['data']

        # THE contract: dose_status sits directly on data, not nested under
        # a "response_data" object. firmware reads data["dose_status"].
        self.assertIn('dose_status', data,
                      'dose_status must be a top-level key of data')
        self.assertEqual(data['dose_status'], 'taken')
        self.assertNotIn('response_data', data)

    def test_partial_dose_status(self):
        session_uuid = str(uuid.uuid4())
        self._post('/api/v1/iot/events/', {
            'event_uuid': str(uuid.uuid4()), 'event_type': 'DOSE_STARTED',
            'compartment_num': 1, 'session_uuid': session_uuid,
            'weight_before': 100.0,
        })
        res = self._post('/api/v1/iot/events/', {
            'event_uuid': str(uuid.uuid4()), 'event_type': 'WEIGHT_READING',
            'compartment_num': 1, 'weight_grams': 96.0,   # only 4g of 10g
            'phase': 'after_dose', 'session_uuid': session_uuid,
        })
        self.assertEqual(res.json()['data']['dose_status'], 'partial')

    # ── POST /events/batch/ — ev_flush() in events.h ────────────────────────
    def test_event_batch_contract(self):
        session_uuid = str(uuid.uuid4())
        res = self._post('/api/v1/iot/events/batch/', {
            'events': [
                {'event_uuid': str(uuid.uuid4()), 'event_type': 'DOSE_STARTED',
                 'compartment_num': 1, 'session_uuid': session_uuid,
                 'weight_before': 100.0, 'occurred_at': '2026-09-12T08:00:05'},
                {'event_uuid': str(uuid.uuid4()), 'event_type': 'LID_OPENED',
                 'compartment_num': 1, 'session_uuid': session_uuid,
                 'occurred_at': '2026-09-12T08:01:00'},
                {'event_uuid': str(uuid.uuid4()), 'event_type': 'WEIGHT_READING',
                 'compartment_num': 1, 'weight_grams': 90.0, 'phase': 'after_dose',
                 'session_uuid': session_uuid, 'occurred_at': '2026-09-12T08:02:00'},
            ]
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()['data']
        self.assertEqual(data['received'], 3)
        self.assertEqual(data['accepted'], 3)

        # An offline dose must verify identically once replayed.
        weight_result = data['results'][2]['response_data']
        self.assertEqual(weight_result['dose_status'], 'taken')

        # occurred_at is honoured rather than arrival time
        from apps.iot.models import DeviceEvent
        ev = DeviceEvent.objects.get(event_type='LID_OPENED')
        self.assertIsNotNone(ev.occurred_at)
        self.assertEqual(ev.occurred_at.astimezone().strftime('%H:%M'), '08:01')

    def test_batch_replay_is_idempotent(self):
        shared = str(uuid.uuid4())
        payload = {'events': [{
            'event_uuid': shared, 'event_type': 'LID_CLOSED',
            'compartment_num': 1, 'occurred_at': '2026-09-12T08:02:00',
        }]}

        first = self._post('/api/v1/iot/events/batch/', payload)
        second = self._post('/api/v1/iot/events/batch/', payload)

        self.assertEqual(first.json()['data']['results'][0]['status'], 'accepted')
        self.assertEqual(second.json()['data']['results'][0]['status'],
                         'duplicate_ignored')

    # ── POST /fill/measure/ — postFillMeasure() in api.h ────────────────────
    def test_fill_measure_contract(self):
        sub = self.comps[1].sub_compartments.first()
        res = self._post(
            f'/api/v1/iot/devices/{self.device.id}/fill/measure/',
            {'compartment_number': 2, 'total_weight_grams': 250.0,
             'medicine_id': str(sub.id)},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()['data']

        # Keys the firmware logs / displays after a fill step
        self.assertIn('derived_weight_grams', data)
        self.assertIn('pill_weight_grams', data)
        self.assertIn('schedule_version', data)

        # 250 total - 100 already in compartment 1 = 150g of new medicine
        self.assertAlmostEqual(data['derived_weight_grams'], 150.0, places=2)
        self.assertAlmostEqual(data['pill_weight_grams'], 15.0, places=2)

    # ── POST /heartbeat/ — taskNetwork() reconciliation ─────────────────────
    def test_heartbeat_contract(self):
        res = self._post('/api/v1/iot/heartbeat/', {
            'battery_level': 85,
            'firmware_version': '3.0.0',
            'wifi_strength': -52,
            'uptime_seconds': 3600,
            'schedule_version': self.device.schedule_version,
            'rtc_time': '2026-09-12T08:15:02',
            'queued_events': 0,
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()['data']

        for key in ('config_stale', 'pending_commands', 'schedule_version',
                    'server_unix_time', 'gate_locked', 'rtc_drift_seconds'):
            self.assertIn(key, data, f'heartbeat response missing "{key}"')

        self.assertIsInstance(data['config_stale'], bool)
        self.assertIsInstance(data['pending_commands'], int)

    def test_heartbeat_without_version_is_stale(self):
        """Firmware with no cached bundle must be told to fetch one."""
        res = self._post('/api/v1/iot/heartbeat/', {'battery_level': 85})
        self.assertTrue(res.json()['data']['config_stale'])
