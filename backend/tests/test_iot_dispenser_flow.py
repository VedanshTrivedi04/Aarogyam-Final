"""
End-to-end check of the autonomous-dispenser backend:
fill sequence math, dose verification, tamper, idempotent replay, heartbeat.
Run with the sqlite test settings so the remote DB is never touched.
"""
import uuid

from django.test import TestCase
from django.utils import timezone

from apps.identity.models import User
from apps.iot.config_service import build_config_bundle, bump_schedule_version
from apps.iot.models import (
    Device, DeviceCommand, DeviceEvent, DoseSession, PhysicalCompartment,
    SubCompartment,
)
from apps.iot.services import DeviceService
from apps.iot.weight_service import process_fill_measurement


class DispenserFlowTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='t@example.com', password='x', full_name='T',
        )
        self.device = Device.objects.create(
            user=self.user, device_name='Test Dispenser', api_key='k' * 20,
        )
        slots = ['morning_before', 'morning_after', 'night_before', 'night_after']
        times = ['08:00', '09:00', '20:00', '21:00']
        self.comps = []
        for i, (slot, t) in enumerate(zip(slots, times), start=1):
            comp = PhysicalCompartment.objects.create(
                device=self.device, compartment_number=i,
                time_slot=slot, scheduled_time=t,
            )
            SubCompartment.objects.create(
                compartment=comp, medicine_name=f'Med{i}',
                quantity_per_dose=1, duration_days=10, total_pills=10,
            )
            self.comps.append(comp)

    # ── Fill sequence: the cumulative subtraction ───────────────────────────
    def test_fill_sequence_is_device_wide_cumulative(self):
        """
        Load cell reads the whole carousel, so each step's content is the
        reading minus the running reference.
        Readings 100 / 250 / 300 / 380 -> contents 100 / 150 / 50 / 80.
        """
        readings = [100.0, 250.0, 300.0, 380.0]
        expected = [100.0, 150.0, 50.0, 80.0]

        for comp, reading, want in zip(self.comps, readings, expected):
            sub = comp.sub_compartments.first()
            result = process_fill_measurement(
                self.device, comp, reading, medicine_id=str(sub.id),
            )
            self.assertNotIn('error', result, result)
            self.assertAlmostEqual(result['derived_weight_grams'], want, places=2)
            # 10 pills per medicine
            self.assertAlmostEqual(result['pill_weight_grams'], want / 10, places=3)

        self.device.refresh_from_db()
        self.assertAlmostEqual(self.device.total_weight_grams, 380.0, places=2)

        for comp, want in zip(self.comps, expected):
            comp.refresh_from_db()
            self.assertAlmostEqual(comp.current_balance_weight_grams, want, places=2)

    def test_fill_rejects_reading_below_reference(self):
        comp = self.comps[0]
        process_fill_measurement(self.device, comp, 100.0)
        self.device.refresh_from_db()
        result = process_fill_measurement(self.device, self.comps[1], 90.0)
        self.assertEqual(result['error'], 'no_weight_added')

    # ── Dose lifecycle ──────────────────────────────────────────────────────
    def _fill_all(self):
        for comp, reading in zip(self.comps, [100.0, 250.0, 300.0, 380.0]):
            process_fill_measurement(
                self.device, comp, reading,
                medicine_id=str(comp.sub_compartments.first().id),
            )
            self.device.refresh_from_db()

    def _dose_start(self, comp, baseline, session_uuid):
        return DeviceService.ingest_event(self.device, {
            'event_uuid': str(uuid.uuid4()),
            'event_type': 'DOSE_STARTED',
            'compartment_num': comp.compartment_number,
            'session_uuid': session_uuid,
            'weight_before': baseline,
            'occurred_at': '2026-09-12T08:00:05',
        })

    def _weight_after(self, comp, weight, session_uuid, event_uuid=None):
        return DeviceService.ingest_event(self.device, {
            'event_uuid': event_uuid or str(uuid.uuid4()),
            'event_type': 'WEIGHT_READING',
            'compartment_num': comp.compartment_number,
            'weight_grams': weight,
            'phase': 'after_dose',
            'session_uuid': session_uuid,
            'occurred_at': '2026-09-12T08:02:00',
        })

    def test_full_dose_taken(self):
        """Comp 1 holds 100g / 10 pills -> one dose is 10g."""
        self._fill_all()
        comp, sid = self.comps[0], str(uuid.uuid4())

        _, _, started = self._dose_start(comp, 380.0, sid)
        self.assertTrue(started['created'])
        self.assertAlmostEqual(started['expected_reduction_grams'], 10.0, places=2)

        # Patient removes a full dose: 380 -> 370
        _, _, res = self._weight_after(comp, 370.0, sid)
        self.assertEqual(res['dose_status'], 'taken')
        self.assertAlmostEqual(res['actual_reduction_grams'], 10.0, places=2)

        comp.refresh_from_db()
        self.assertAlmostEqual(comp.current_balance_weight_grams, 90.0, places=2)
        self.device.refresh_from_db()
        self.assertAlmostEqual(self.device.total_weight_grams, 370.0, places=2)

    def test_partial_and_missed_dose(self):
        self._fill_all()

        comp, sid = self.comps[1], str(uuid.uuid4())   # 150g / 10 pills -> 15g dose
        self._dose_start(comp, 380.0, sid)
        _, _, res = self._weight_after(comp, 373.0, sid)   # only 7g removed
        self.assertEqual(res['dose_status'], 'partial')

        comp2, sid2 = self.comps[2], str(uuid.uuid4())
        self._dose_start(comp2, 373.0, sid2)
        _, _, res2 = self._weight_after(comp2, 373.0, sid2)  # nothing removed
        self.assertEqual(res2['dose_status'], 'missed')

    def test_weight_reading_without_session_is_tamper(self):
        self._fill_all()
        _, _, res = self._weight_after(self.comps[0], 350.0, str(uuid.uuid4()))
        self.assertEqual(res['dose_status'], 'tamper_suspected')
        self.assertFalse(res['balances_adjusted'])

        self.comps[0].refresh_from_db()
        self.assertAlmostEqual(self.comps[0].current_balance_weight_grams, 100.0, places=2)
        self.assertTrue(
            DeviceEvent.objects.filter(device=self.device, event_type='TAMPER').exists()
        )

    def test_offline_replay_is_idempotent(self):
        """Re-flushing the same queued events must not double-count the drop."""
        self._fill_all()
        comp, sid = self.comps[0], str(uuid.uuid4())
        self._dose_start(comp, 380.0, sid)

        shared_uuid = str(uuid.uuid4())
        _, created1, res1 = self._weight_after(comp, 370.0, sid, event_uuid=shared_uuid)
        _, created2, res2 = self._weight_after(comp, 370.0, sid, event_uuid=shared_uuid)

        self.assertTrue(created1)
        self.assertFalse(created2)           # deduped by event_uuid
        self.assertEqual(res1['dose_status'], 'taken')

        comp.refresh_from_db()
        self.assertAlmostEqual(comp.current_balance_weight_grams, 90.0, places=2)
        self.assertEqual(DoseSession.objects.filter(device_session_uuid=sid).count(), 1)

    def test_dose_started_replay_reuses_session(self):
        self._fill_all()
        comp, sid = self.comps[0], str(uuid.uuid4())
        _, _, first = self._dose_start(comp, 380.0, sid)
        _, _, second = self._dose_start(comp, 380.0, sid)
        self.assertTrue(first['created'])
        self.assertFalse(second['created'])
        self.assertEqual(first['session_id'], second['session_id'])

    # ── Config bundle + versioning ──────────────────────────────────────────
    def test_config_bundle_shape(self):
        self._fill_all()
        bundle = build_config_bundle(self.device)

        self.assertEqual(bundle['utc_offset_minutes'], 330)
        self.assertEqual(len(bundle['compartments']), 4)
        self.assertEqual(bundle['policy']['max_gate_opens'], 4)

        first = bundle['compartments'][0]
        self.assertEqual(first['time'], '08:00')
        self.assertTrue(first['enabled'])
        self.assertAlmostEqual(first['expected_dose_reduction_grams'], 10.0, places=2)
        self.assertEqual(first['medicines'][0]['name'], 'Med1')

    def test_bump_version_queues_sync_and_increments(self):
        before = self.device.schedule_version
        new_version = bump_schedule_version(self.device, reason='test')
        self.assertEqual(new_version, before + 1)
        self.assertTrue(
            DeviceCommand.objects.filter(
                device=self.device, command_type='SYNC_CONFIG', status='PENDING',
            ).exists()
        )

    def test_heartbeat_reports_stale_config_and_pending_commands(self):
        from apps.iot.services import handle_heartbeat

        bump_schedule_version(self.device, reason='test')
        self.device.refresh_from_db()

        # The DS3231 is synced to device-local time, so rtc_time is IST
        # wall-clock with no offset — exactly what the firmware sends.
        import pytz
        from apps.iot.config_service import DEVICE_TIMEZONE
        device_now = timezone.now().astimezone(pytz.timezone(DEVICE_TIMEZONE))

        stale = handle_heartbeat(self.device, None, {
            'battery_level': 80, 'schedule_version': 1,
            'rtc_time': device_now.strftime('%Y-%m-%dT%H:%M:%S'),
        })
        self.assertTrue(stale['config_stale'])
        self.assertGreaterEqual(stale['pending_commands'], 1)
        self.assertLess(abs(stale['rtc_drift_seconds']), 120)

        fresh = handle_heartbeat(self.device, None, {
            'battery_level': 80,
            'schedule_version': self.device.schedule_version,
        })
        self.assertFalse(fresh['config_stale'])

    def test_legacy_sync_schedule_marks_config_stale(self):
        """
        The clinical app queues SYNC_SCHEDULE without bumping the version.
        An outstanding sync command must still force a bundle refetch.
        """
        from datetime import timedelta

        from apps.iot.services import handle_heartbeat

        DeviceCommand.objects.create(
            device=self.device, command_type='SYNC_SCHEDULE',
            payload={'reason': 'prescription_changed'},
            expires_at=timezone.now() + timedelta(hours=1),
        )

        result = handle_heartbeat(self.device, None, {
            'battery_level': 80,
            'schedule_version': self.device.schedule_version,
        })
        self.assertTrue(result['config_stale'])
