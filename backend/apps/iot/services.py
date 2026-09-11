"""
apps/iot/services.py — Device event processing, schedule building, compartment management.
Phase 3: Priority Scheduler + Meal-Triggered Dispensing.
"""
import logging
import secrets
from datetime import timedelta
from django.db.models import F, Q
from django.utils import timezone

from .models import Device, DeviceCommand, DeviceEvent, DeviceHeartbeat, DeviceCompartmentMapping

logger = logging.getLogger(__name__)


def parse_device_timestamp(value):
    """
    Convert an `occurred_at` from the device into an aware datetime.

    The ESP32 sends DS3231 local wall-clock (e.g. "2026-09-12T18:15:02") with
    no offset, so it is interpreted in the device timezone. Returns None for
    anything unparseable — a missing RTC stamp must never reject an event.
    """
    if not value:
        return None

    import datetime as dt

    import pytz

    from .config_service import DEVICE_TIMEZONE

    try:
        parsed = dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return None

    if parsed.tzinfo is None:
        parsed = pytz.timezone(DEVICE_TIMEZONE).localize(parsed)
    return parsed


# ─────────────────────────────────────────────────────────────
# Schedule builder (shared by views + tasks)
# ─────────────────────────────────────────────────────────────

def get_device_schedule(device: Device) -> list:
    """
    Build today's full dispensing schedule for a device.
    Phase 3: Includes priority, meal_dependency, medication_name for smart firmware logic.
    HIGH priority slots are sorted first within the same time bucket.
    """
    mappings = DeviceCompartmentMapping.objects.filter(
        device=device,
        is_filled=True,                           # Only filled compartments
    ).select_related('prescription__medication')

    schedule = []
    now = timezone.localtime()
    for mapping in mappings:
        # Resolve medication name (use stored override or fall back to prescription)
        try:
            med = mapping.prescription.medication
            med_name = mapping.medication_name or med.name
            dosage = f"{mapping.prescription.dosage_value}{mapping.prescription.dosage_unit}"
        except Exception:
            med_name = mapping.medication_name or 'Unknown'
            dosage = ''

        # Skip meal-dependent meds from time-based schedule (they get queued by meal trigger)
        if mapping.meal_dependency != 'NONE':
            continue

        for time_str in mapping.scheduled_times:
            try:
                h, m = map(int, time_str.split(':'))
            except ValueError:
                continue
            scheduled_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
            schedule.append({
                'compartment': mapping.compartment_number,
                'medication_name': med_name,
                'dosage': dosage,
                'scheduled_at': scheduled_dt.isoformat(),
                'prescription_id': str(mapping.prescription_id),
                'priority': mapping.priority,
                'meal_dependency': mapping.meal_dependency,
                'pills_remaining': mapping.pills_remaining,
                'display_text': f"{med_name}\n{dosage}\n{time_str}",
            })

    # Sort: same-time HIGH priority slots come before NORMAL
    return sorted(
        schedule,
        key=lambda x: (x['scheduled_at'], 0 if x['priority'] == 'HIGH' else 1)
    )


def check_firmware_update(device: Device) -> bool:
    """Placeholder — compare device.firmware_version against latest."""
    return False


def check_schedule_updated(device: Device) -> bool:
    """
    Returns True if any compartment's prescription was updated
    more recently than the device's last heartbeat.
    """
    if not device.last_seen_at:
        return True
    return DeviceCompartmentMapping.objects.filter(
        device=device,
        prescription__updated_at__gt=device.last_seen_at,
    ).exists()


# ─────────────────────────────────────────────────────────────
# Event handlers (one per event_type)
# ─────────────────────────────────────────────────────────────

def handle_device_boot(device: Device, event: DeviceEvent, payload: dict) -> dict:
    """Return today's schedule + server time so the device can sync."""
    return {
        'today_schedule': get_device_schedule(device),
        'server_time': timezone.now().isoformat(),
        'firmware_update_available': check_firmware_update(device),
    }


def handle_heartbeat(device: Device, event: DeviceEvent, payload: dict) -> dict:
    """Update device health, check for low battery, return schedule flag."""
    battery = payload.get('battery_level', device.battery_level or 100)

    Device.objects.filter(id=device.id).update(
        last_seen_at=timezone.now(),
        battery_level=battery,
        firmware_version=payload.get('firmware_version', device.firmware_version),
        stepper_status=payload.get('stepper_status', device.stepper_status),
        servo_status=payload.get('servo_status', device.servo_status),
        ultrasonic_status=payload.get('ultrasonic_status', device.ultrasonic_status),
    )
    device.refresh_from_db()

    DeviceHeartbeat.objects.create(
        device=device,
        battery_level=battery,
        firmware_version=payload.get('firmware_version', ''),
        wifi_strength=payload.get('wifi_strength'),
        uptime_seconds=payload.get('uptime_seconds', 0),
        stepper_status=payload.get('stepper_status', 'ok'),
        servo_status=payload.get('servo_status', 'ok'),
        ultrasonic_status=payload.get('ultrasonic_status', 'ok'),
    )

    # Low battery check
    if battery < 15:
        try:
            from agenthandover import AgentOrchestrator, AgentName, AgentEvent, HandoverPayload
            orchestrator = AgentOrchestrator()
            orchestrator.broadcast(
                AgentName.IOT,
                AgentEvent.DEVICE_LOW_BATTERY,
                HandoverPayload(
                    user_id=str(device.user_id),
                    device_id=str(device.id),
                    data={'battery_level': battery, 'device_name': device.device_name},
                )
            )
        except Exception:
            logger.warning("AgentOrchestrator not available for low battery broadcast")

    # ── Config reconciliation ────────────────────────────────────
    # The device reports the schedule_version it has cached in NVS. If it
    # differs from ours, it re-fetches the bundle once. This is what replaces
    # the old 60-second schedule poll.
    device_version = payload.get('schedule_version')
    config_stale = (
        device_version is None or int(device_version) != device.schedule_version
    )

    pending_commands = DeviceCommand.objects.filter(
        device=device, status='PENDING', expires_at__gt=timezone.now(),
    ).count()

    now = timezone.now()
    result: dict = {
        'server_time': now.isoformat(),
        'server_unix_time': int(now.timestamp()),
        'schedule_version': device.schedule_version,
        'config_stale': config_stale,
        'pending_commands': pending_commands,
        'gate_locked': device.is_gate_locked,
        'firmware_update_available': check_firmware_update(device),
    }

    # RTC drift — device sends its own clock so we can tell it to resync.
    rtc_time = payload.get('rtc_time')
    if rtc_time:
        result['rtc_drift_seconds'] = _rtc_drift_seconds(rtc_time)

    # Legacy fields for firmware that predates config bundles.
    schedule_updated = check_schedule_updated(device)
    result['schedule_updated'] = schedule_updated
    if schedule_updated:
        result['updated_schedule'] = get_device_schedule(device)
    return result


def _rtc_drift_seconds(rtc_time: str):
    """
    Seconds the device's RTC is behind/ahead of server time.
    The device sends local wall-clock ISO8601 without an offset.
    """
    import datetime as dt

    import pytz

    from .config_service import DEVICE_TIMEZONE

    try:
        naive = dt.datetime.fromisoformat(rtc_time.replace('Z', ''))
        if naive.tzinfo is None:
            naive = pytz.timezone(DEVICE_TIMEZONE).localize(naive)
        return int((timezone.now() - naive).total_seconds())
    except (ValueError, TypeError):
        return None


def handle_compartment_rotated(device: Device, event: DeviceEvent, payload: dict) -> dict:
    """Mark event as processed."""
    DeviceEvent.objects.filter(id=event.id).update(processed=True)
    return {}


def handle_hand_detected(device: Device, event: DeviceEvent, payload: dict) -> dict:
    """Log only — frontend will receive via websocket."""
    return {}


def handle_lid_opened(device: Device, event: DeviceEvent, payload: dict) -> dict:
    """
    Create a pending DoseSession when lid is opened if one doesn't exist.
    This makes the backend ready to accept a subsequent weight reading
    that will finalize the session as taken/partial/missed.
    """
    try:
        compartment_num = payload.get('compartment') or payload.get('compartment_num')
        if not compartment_num:
            return {'error': 'compartment_required'}

        from .models import PhysicalCompartment, DoseSession
        from .weight_service import calculate_dose_expected_reduction

        comp = PhysicalCompartment.objects.filter(device=device, compartment_number=compartment_num).prefetch_related('sub_compartments').first()
        if not comp:
            return {'error': 'compartment_not_found'}

        # If there's already a pending session, return it
        existing = (
            DoseSession.objects.filter(compartment=comp, dose_status='pending')
            .order_by('-created_at')
            .first()
        )
        if existing:
            return {'session_id': str(existing.id), 'created': False}

        # Create new session using current balance and expected reduction
        subs = list(comp.sub_compartments.filter(is_active=True))
        expected_reduction = calculate_dose_expected_reduction(subs)

        session = DoseSession.objects.create(
            compartment=comp,
            scheduled_time=timezone.now(),
            expected_weight_before=comp.current_balance_weight_grams,
            weight_reduction_expected=expected_reduction,
            dose_status='pending',
        )

        return {'session_id': str(session.id), 'created': True}
    except Exception as exc:
        logger.exception("handle_lid_opened error: %s", exc)
        return {'error': 'internal'}


def handle_lid_closed(device: Device, event: DeviceEvent, payload: dict) -> dict:
    """Dose confirmation window would start here (30s timer on firmware side)."""
    # No-op for now; weight reading endpoint will finalize DoseSession.
    return {}


def handle_dose_taken(device: Device, event: DeviceEvent, payload: dict) -> dict:
    """
    Critical path: resolve compartment → create AdherenceEvent via AgentOrchestrator.
    """
    from datetime import datetime
    compartment_num = payload.get('compartment') or payload.get('compartment_num')
    if not compartment_num:
        return {'error': 'compartment_required'}

    mapping = DeviceCompartmentMapping.objects.filter(
        device=device,
        compartment_number=compartment_num,
    ).select_related('prescription').first()

    if not mapping:
        logger.error("No compartment mapping: device=%s compartment=%s", device.id, compartment_num)
        return {'error': 'no_mapping'}

    taken_at_raw = payload.get('taken_at', timezone.now().isoformat())
    scheduled_at_raw = payload.get('scheduled_at')

    try:
        taken_at = datetime.fromisoformat(taken_at_raw)
    except (ValueError, TypeError):
        taken_at = timezone.now()

    adherence_event = None
    try:
        from agenthandover import AgentOrchestrator, AgentName, AgentEvent, HandoverPayload
        orchestrator = AgentOrchestrator()
        hp = HandoverPayload(
            patient_id=str(device.linked_patient_id) if device.linked_patient_id else None,
            prescription_id=str(mapping.prescription_id),
            device_id=str(device.id),
            data={
                'taken_at': taken_at.isoformat(),
                'scheduled_at': scheduled_at_raw,
                'source': 'IOT_PILLBOX',
                'compartment': compartment_num,
                'status': 'TAKEN',
            }
        )
        result = orchestrator.broadcast(AgentName.IOT, AgentEvent.DOSE_LOGGED, hp)
        adherence_event_id = getattr(result, 'adherence_event_id', None)
    except Exception as exc:
        logger.warning("Orchestrator unavailable for DOSE_TAKEN: %s", exc)
        adherence_event_id = None

    # Link adherence event to the device event & update dose counter
    DeviceEvent.objects.filter(id=event.id).update(processed=True)
    Device.objects.filter(id=device.id).update(
        total_doses_dispensed=F('total_doses_dispensed') + 1
    )

    return {'adherence_event_id': adherence_event_id}


def handle_dose_timeout(device: Device, event: DeviceEvent, payload: dict) -> dict:
    """MISSED dose: log + escalation via orchestrator."""
    compartment_num = payload.get('compartment') or payload.get('compartment_num')
    mapping = DeviceCompartmentMapping.objects.filter(
        device=device, compartment_number=compartment_num
    ).first()

    if not mapping:
        return {'error': 'no_mapping'}

    try:
        from agenthandover import AgentOrchestrator, AgentName, AgentEvent, HandoverPayload
        orchestrator = AgentOrchestrator()
        hp = HandoverPayload(
            patient_id=str(device.linked_patient_id) if device.linked_patient_id else None,
            prescription_id=str(mapping.prescription_id),
            device_id=str(device.id),
            data={
                'scheduled_at': payload.get('scheduled_at'),
                'source': 'IOT_PILLBOX',
                'status': 'MISSED',
            }
        )
        orchestrator.broadcast(AgentName.IOT, AgentEvent.DOSE_MISSED, hp)
    except Exception as exc:
        logger.warning("Orchestrator unavailable for DOSE_TIMEOUT: %s", exc)

    return {}


def handle_dose_skipped(device: Device, event: DeviceEvent, payload: dict) -> dict:
    compartment_num = payload.get('compartment') or payload.get('compartment_num')
    mapping = DeviceCompartmentMapping.objects.filter(
        device=device, compartment_number=compartment_num
    ).first()

    if not mapping:
        return {'error': 'no_mapping'}

    try:
        from agenthandover import AgentOrchestrator, AgentName, AgentEvent, HandoverPayload
        orchestrator = AgentOrchestrator()
        hp = HandoverPayload(
            patient_id=str(device.linked_patient_id) if device.linked_patient_id else None,
            prescription_id=str(mapping.prescription_id),
            device_id=str(device.id),
            data={
                'scheduled_at': payload.get('scheduled_at'),
                'source': 'IOT_PILLBOX',
                'status': 'SKIPPED',
            }
        )
        orchestrator.broadcast(AgentName.IOT, AgentEvent.DOSE_SKIPPED, hp)
    except Exception as exc:
        logger.warning("Orchestrator unavailable for DOSE_SKIPPED: %s", exc)

    return {}


def handle_command_acknowledged(device: Device, event: DeviceEvent, payload: dict) -> dict:
    command_id = payload.get('command_id')
    if command_id:
        DeviceCommand.objects.filter(id=command_id, device=device).update(
            status='ACKNOWLEDGED',
            acknowledged_at=timezone.now(),
        )
    return {}


def handle_dose_duplicate_blocked(device: Device, event: DeviceEvent, payload: dict) -> dict:
    """Phase 2: Log duplicate dispense attempt — already blocked by firmware."""
    compartment_num = payload.get('compartment_num') or payload.get('compartment')
    logger.warning("Duplicate dispense attempt blocked: device=%s compartment=%s",
                   device.id, compartment_num)
    return {'status': 'duplicate_blocked'}


# Dispatch table — event_type → handler function
def _resolve_compartment(device: Device, payload: dict):
    from .models import PhysicalCompartment

    compartment_num = payload.get('compartment_num') or payload.get('compartment')
    if not compartment_num:
        return None
    return (
        PhysicalCompartment.objects
        .filter(device=device, compartment_number=int(compartment_num))
        .prefetch_related('sub_compartments')
        .first()
    )


def handle_dose_started(device: Device, event: DeviceEvent, payload: dict) -> dict:
    """
    The device's RTC fired a slot and it has read its baseline weight.

    The session UUID is minted on the ESP32, so this is idempotent: an event
    replayed from the offline queue resolves to the session it created the
    first time instead of opening a second one.
    """
    from .models import DoseSession
    from .weight_service import calculate_dose_expected_reduction

    comp = _resolve_compartment(device, payload)
    if not comp:
        return {'error': 'compartment_not_found'}

    session_uuid = payload.get('session_uuid') or payload.get('session_id')
    if not session_uuid:
        return {'error': 'session_uuid_required'}

    weight_before = payload.get('weight_before') or payload.get('weight_grams') or 0.0
    active_subs = [s for s in comp.sub_compartments.all() if s.is_active]
    expected_reduction = calculate_dose_expected_reduction(active_subs)

    occurred = event.occurred_at or timezone.now()
    session, created = DoseSession.objects.get_or_create(
        device_session_uuid=session_uuid,
        defaults={
            'compartment': comp,
            'slot_date': timezone.localtime(occurred).date(),
            'scheduled_time': occurred,
            'expected_weight_before': float(weight_before),
            'weight_reduction_expected': expected_reduction,
        },
    )

    # The device's own baseline reading is the freshest device-wide total.
    if created and weight_before:
        device.total_weight_grams = float(weight_before)
        device.save(update_fields=['total_weight_grams'])

    return {
        'session_id': str(session.id),
        'created': created,
        'expected_reduction_grams': round(expected_reduction, 3),
    }


def handle_weight_reading(device: Device, event: DeviceEvent, payload: dict) -> dict:
    """
    Load cell reading from the device.

    phase='before_dose' records a baseline; phase='after_dose' runs the full
    verification and returns dose_status, which the firmware reads out of
    response_data to pick its audio track and OLED message.
    """
    from .weight_service import process_weight_reading

    comp = _resolve_compartment(device, payload)
    if not comp:
        return {'error': 'compartment_not_found'}

    try:
        weight = float(payload.get('weight_grams'))
    except (TypeError, ValueError):
        return {'error': 'weight_grams_invalid'}

    phase = payload.get('phase', 'after_dose')
    session_uuid = payload.get('session_uuid') or payload.get('session_id')

    if phase == 'before_dose':
        from .weight_service import find_dose_session

        session = find_dose_session(comp, session_uuid)
        if session and session.dose_status == 'pending':
            session.expected_weight_before = weight
            session.save(update_fields=['expected_weight_before'])

        device.total_weight_grams = weight
        device.save(update_fields=['total_weight_grams'])
        return {'phase': 'before_dose', 'baseline_grams': weight,
                'session_id': str(session.id) if session else None}

    return process_weight_reading(
        comp, weight, session_uuid=session_uuid, occurred_at=event.occurred_at
    )


EVENT_HANDLERS = {
    'DEVICE_BOOT':              handle_device_boot,
    'HEARTBEAT':                handle_heartbeat,
    'COMPARTMENT_ROTATED':      handle_compartment_rotated,
    'HAND_DETECTED':            handle_hand_detected,
    'LID_OPENED':               handle_lid_opened,
    'LID_CLOSED':               handle_lid_closed,
    'DOSE_STARTED':             handle_dose_started,
    'WEIGHT_READING':           handle_weight_reading,
    'DOSE_TAKEN':               handle_dose_taken,
    'DOSE_TIMEOUT':             handle_dose_timeout,
    'DOSE_SKIPPED':             handle_dose_skipped,
    'DOSE_DUPLICATE_BLOCKED':   handle_dose_duplicate_blocked,
    'COMMAND_ACKNOWLEDGED':     handle_command_acknowledged,
}


# ─────────────────────────────────────────────────────────────
# DeviceService — CRUD helpers used by views
# ─────────────────────────────────────────────────────────────

class DeviceService:
    @staticmethod
    def generate_api_key() -> str:
        return secrets.token_urlsafe(48)

    @staticmethod
    def link_device(user, patient, device_name: str, device_type: str = 'CIRCULAR_PILL_DISPENSER') -> Device:
        """Link a new IoT device to a user/patient. Premium gate checked in view."""
        api_key = DeviceService.generate_api_key()
        return Device.objects.create(
            user=user,
            linked_patient=patient,
            device_name=device_name,
            device_type=device_type,
            api_key=api_key,
        )

    @staticmethod
    def ingest_event(device: Device, payload: dict):
        """Idempotent event ingestion. Returns (event, created)."""
        event_uuid = str(payload.get('event_uuid', ''))
        event_type = payload.get('event_type', '')
        if not event_uuid or not event_type:
            raise ValueError("event_uuid and event_type are required")

        event, created = DeviceEvent.objects.get_or_create(
            event_uuid=event_uuid,
            defaults={
                'device': device,
                'event_type': event_type,
                'compartment_num': payload.get('compartment_num') or payload.get('compartment'),
                'raw_payload': payload,
                'occurred_at': parse_device_timestamp(payload.get('occurred_at')),
            }
        )

        response_data: dict = {}
        if created:
            handler = EVENT_HANDLERS.get(event_type)
            if handler:
                try:
                    response_data = handler(device, event, payload) or {}
                except Exception as exc:
                    logger.exception("Handler error for %s: %s", event_type, exc)

        return event, created, response_data

    @staticmethod
    def record_heartbeat(device: Device, payload: dict) -> dict:
        return handle_heartbeat(device, None, payload)  # type: ignore[arg-type]

    @staticmethod
    def update_compartments(device: Device, mappings: list):
        """
        Phase 3 upgrade: saves all smart fields alongside prescription.
        mappings = [{
            'compartment_number': 1, 'prescription_id': '<uuid>',
            'scheduled_times': ['08:00'],
            'priority': 'HIGH',                    # optional
            'meal_dependency': 'AFTER_BREAKFAST',  # optional
            'medication_name': 'Aspirin 75mg',     # optional OLED override
            'total_pills': 30,                     # optional
        }]
        """
        from apps.clinical.models import Prescription
        for m in mappings:
            prescription_id = m.get('prescription_id') or m.get('prescription')
            prescription = Prescription.objects.get(id=prescription_id)
            total_pills = int(m.get('total_pills', 0))
            defaults = {
                'prescription': prescription,
                'scheduled_times': m.get('scheduled_times', []),
                'priority': m.get('priority', 'NORMAL'),
                'meal_dependency': m.get('meal_dependency', 'NONE'),
                'medication_name': m.get('medication_name', prescription.medication.name
                                        if hasattr(prescription, 'medication') else ''),
                'total_pills': total_pills,
            }
            obj, created = DeviceCompartmentMapping.objects.update_or_create(
                device=device,
                compartment_number=m['compartment_number'],
                defaults=defaults,
            )
            # Only reset pills_remaining on fresh create (not on update)
            if created and total_pills > 0:
                obj.pills_remaining = total_pills
                obj.save(update_fields=['pills_remaining'])


# ─────────────────────────────────────────────────────────────
# Phase 3: Priority Scheduler
# ─────────────────────────────────────────────────────────────

class PriorityScheduler:
    """
    Checks if any HIGH priority compartment has a pending dose.
    If yes, queues it BEFORE any normal doses.
    Called from: periodic Celery task (every 2 min) + after DOSE_TAKEN.
    """

    @staticmethod
    def check_and_queue_high_priority(device: Device):
        """Scan HIGH priority compartments and queue if dose is overdue."""
        now = timezone.localtime()
        current_time = now.strftime('%H:%M')

        high_prio = DeviceCompartmentMapping.objects.filter(
            device=device,
            priority='HIGH',
            is_filled=True,
            meal_dependency='NONE',
        )

        for mapping in high_prio:
            for time_str in mapping.scheduled_times:
                try:
                    h, m_val = map(int, time_str.split(':'))
                except ValueError:
                    continue
                slot_time = now.replace(hour=h, minute=m_val, second=0, microsecond=0)
                # Within ±5 minute window
                diff_secs = (now - slot_time).total_seconds()
                if 0 <= diff_secs <= 300:
                    # Check if already queued
                    already_queued = DeviceCommand.objects.filter(
                        device=device,
                        command_type='PREPARE_COMPARTMENT',
                        status__in=['PENDING', 'SENT'],
                        payload__compartment=mapping.compartment_number,
                        expires_at__gt=timezone.now(),
                    ).exists()
                    if not already_queued:
                        DeviceCommand.objects.create(
                            device=device,
                            command_type='PREPARE_COMPARTMENT',
                            payload={
                                'compartment': mapping.compartment_number,
                                'medication_name': mapping.medication_name,
                                'priority': 'HIGH',
                                'reason': 'HIGH_PRIORITY_SCHEDULE',
                            },
                            expires_at=timezone.now() + timedelta(minutes=30),
                        )
                        logger.info(
                            "[PriorityScheduler] Queued HIGH priority: device=%s compartment=%s",
                            device.id, mapping.compartment_number
                        )

    @staticmethod
    def run_for_all_devices():
        """Called by Celery Beat every 2 minutes."""
        devices = Device.objects.filter(is_active=True)
        for device in devices:
            try:
                PriorityScheduler.check_and_queue_high_priority(device)
            except Exception as exc:
                logger.error("PriorityScheduler error device=%s: %s", device.id, exc)
