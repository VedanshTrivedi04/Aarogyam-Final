"""
apps/iot/config_service.py — Versioned config bundle handed to the ESP32.

The device caches this bundle in NVS and drives its own dose schedule from the
DS3231 RTC, so it only re-fetches when the schedule_version it reports back on
a heartbeat differs from the one stored on the Device row.

Timezone contract: `time` is always HH:MM in DEVICE-LOCAL wall-clock time.
The firmware compares it against the RTC directly and never does UTC math.
"""
import logging

import pytz
from django.conf import settings
from django.db.models import F
from django.utils import timezone

logger = logging.getLogger(__name__)

DEVICE_TIMEZONE = getattr(settings, 'DEVICE_TIMEZONE', 'Asia/Kolkata')

# Behaviour the firmware reads out of the bundle instead of hardcoding it,
# so these can be tuned server-side without reflashing.
DEVICE_POLICY = {
    'dose_window_minutes': 60,      # how long the gate stays available after a slot fires
    'catchup_window_minutes': 30,   # fire a slot missed while powered off, within this much
    'max_gate_opens': 4,            # gate opens per session before the device locks itself
    'weight_settle_ms': 3000,       # wait after gate close before reading the load cell
    'hand_detect_cm': 15,
    'heartbeat_interval_seconds': 600,
    'command_poll_seconds': 300,    # safety net only; commands normally arrive over WebSocket
}


def _slot_audio_track(time_slot: str) -> int:
    """DFPlayer track for the dose reminder. Track 1 is the generic reminder."""
    return 1


def build_config_bundle(device) -> dict:
    """
    Full state the device needs to run autonomously for a day.
    Read-only — never mutates the device.
    """
    from .ai_service import generate_display_text, generate_voice_text
    from .weight_service import calculate_dose_expected_reduction

    tz = pytz.timezone(DEVICE_TIMEZONE)
    now_local = timezone.now().astimezone(tz)

    compartments = []
    qs = (
        device.physical_compartments
        .filter(is_active=True)
        .prefetch_related('sub_compartments')
        .order_by('compartment_number')
    )

    for comp in qs:
        active_subs = [s for s in comp.sub_compartments.all() if s.is_active]
        hour, minute = comp.get_scheduled_hour_minute()

        compartments.append({
            'compartment_number': comp.compartment_number,
            'time_slot': comp.time_slot,
            'time': f'{hour:02d}:{minute:02d}',
            # A compartment with nothing measured in it must not fire a dose.
            'enabled': bool(active_subs) and comp.expected_weight_grams > 0,
            'content_weight_grams': round(comp.current_balance_weight_grams, 3),
            'expected_dose_reduction_grams': round(
                calculate_dose_expected_reduction(active_subs), 3
            ),
            'display_text': generate_display_text(comp.time_slot, active_subs),
            'voice_text': generate_voice_text(comp.time_slot, active_subs),
            'audio_track': _slot_audio_track(comp.time_slot),
            'medicines': [
                {
                    'medicine_uuid': str(s.id),
                    'name': s.medicine_name,
                    'pill_weight_grams': round(s.pill_weight_grams, 4),
                    'qty_per_dose': s.quantity_per_dose,
                }
                for s in active_subs
            ],
        })

    return {
        'schedule_version': device.schedule_version,
        'device_id': str(device.id),
        'timezone': DEVICE_TIMEZONE,
        'utc_offset_minutes': int(now_local.utcoffset().total_seconds() // 60),
        'server_unix_time': int(timezone.now().timestamp()),
        'server_time_local': now_local.isoformat(),
        'total_weight_grams': round(device.total_weight_grams, 3),
        'tare_weight_grams': round(device.tare_weight_grams, 3),
        'is_gate_locked': device.is_gate_locked,
        'policy': DEVICE_POLICY,
        'compartments': compartments,
    }


def bump_schedule_version(device, reason: str = '') -> int:
    """
    Invalidate the device's cached bundle. Called by every view that changes
    what the device needs to know (slot times, medicines, fill completion).

    Uses an F() expression so concurrent edits can't clobber each other's bump.
    Pushes a SYNC_CONFIG command so an online device refreshes immediately
    instead of waiting for its next heartbeat.
    """
    from datetime import timedelta

    from .models import DeviceCommand

    device.__class__.objects.filter(id=device.id).update(
        schedule_version=F('schedule_version') + 1
    )
    device.refresh_from_db(fields=['schedule_version'])

    DeviceCommand.objects.create(
        device=device,
        command_type='SYNC_CONFIG',
        payload={'schedule_version': device.schedule_version, 'reason': reason},
        expires_at=timezone.now() + timedelta(hours=24),
    )

    logger.info(
        "Device %s schedule_version → %s (%s)",
        device.id, device.schedule_version, reason or 'unspecified',
    )
    return device.schedule_version
