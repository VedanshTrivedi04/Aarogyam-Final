"""
apps/iot/weight_service.py — Weight calculation, dose verification, gate event logic.
Backend is the SOLE source of truth for all weight math.
ESP32 only sends raw weight numbers — never interprets them.
"""
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)

DOSE_TOLERANCE = 0.90   # 10% tolerance — actual >= expected * 0.90 → TAKEN
MAX_GATE_OPENS = 4       # lock gate after this many opens per dose session


# ── Weight math helpers ──────────────────────────────────────────────────────

def calculate_sub_compartment_weight(pill_weight_grams: float, quantity_per_dose: int, duration_days: int) -> float:
    """Total weight loaded into one sub-compartment (medicine slot) when filled."""
    return pill_weight_grams * quantity_per_dose * duration_days


def calculate_compartment_expected_weight(sub_compartments) -> float:
    """Sum of all active sub-compartment total weights → total expected load."""
    return sum(s.total_weight_grams for s in sub_compartments if s.is_active)


def calculate_dose_expected_reduction(sub_compartments) -> float:
    """Expected weight reduction for one single dose (pill_weight × qty for each medicine)."""
    return sum(
        s.pill_weight_grams * s.quantity_per_dose
        for s in sub_compartments
        if s.is_active
    )


def verify_dose(actual_reduction: float, expected_reduction: float) -> str:
    """
    Compare actual vs expected weight reduction.
    Returns: 'taken' | 'partial' | 'missed'
    """
    if expected_reduction <= 0:
        return 'taken'  # compartment empty or no medicines — treat as taken

    ratio = actual_reduction / expected_reduction
    if ratio >= DOSE_TOLERANCE:
        return 'taken'
    elif ratio > 0.10:   # some medicine removed but not enough
        return 'partial'
    else:
        return 'missed'


def identify_missed_medicines(sub_compartments, weight_deficit: float) -> list:
    """
    Heuristic: identify which sub-compartments were likely NOT taken.
    Sorts medicines by dose weight (largest first) and matches against deficit.
    Returns list of dicts with medicine_name and expected_weight.
    """
    missed = []
    remaining = weight_deficit

    sorted_subs = sorted(
        [s for s in sub_compartments if s.is_active],
        key=lambda s: s.pill_weight_grams * s.quantity_per_dose,
        reverse=True,
    )

    for sub in sorted_subs:
        dose_w = sub.pill_weight_grams * sub.quantity_per_dose
        if remaining >= dose_w * DOSE_TOLERANCE:
            missed.append({
                'medicine_name': sub.medicine_name,
                'expected_dose_weight_grams': round(dose_w, 3),
            })
            remaining -= dose_w
            if remaining <= 0:
                break

    return missed


# ── Main weight processing pipeline ─────────────────────────────────────────

def find_dose_session(compartment, session_uuid: str = None):
    """
    Resolve the session a weight reading belongs to.

    Prefer the device-minted UUID: an event replayed from the ESP32's offline
    queue must land on the session it was produced for, not on whatever is
    pending now. Falls back to the newest pending session for the compartment
    (older firmware, or a reading triggered outside a dose).
    """
    from .models import DoseSession

    if session_uuid:
        session = DoseSession.objects.filter(device_session_uuid=session_uuid).first()
        if session:
            return session

    return (
        DoseSession.objects.filter(compartment=compartment, dose_status='pending')
        .order_by('-created_at')
        .first()
    )


def process_weight_reading(compartment, actual_weight: float,
                           session_uuid: str = None, occurred_at=None) -> dict:
    """
    Called when the ESP32 reports the load cell total after the gate closes.

    The cell sits under the whole carousel, so `actual_weight` is a DEVICE-WIDE
    total, not this compartment's contents. The drop is attributed to this
    compartment because its gate was the one open.

    A reading with no matching session cannot be attributed to anything, so it
    is recorded as TAMPER and no balance is touched.
    """
    from .models import DoseSession, WeightHistory

    device = compartment.device

    WeightHistory.objects.create(
        device=device,
        compartment_number=compartment.compartment_number,
        weight_grams=actual_weight,
    )

    sub_compartments = list(compartment.sub_compartments.filter(is_active=True))
    active_session = find_dose_session(compartment, session_uuid)

    if not active_session:
        return _record_tamper(device, compartment, actual_weight, occurred_at)

    if active_session.dose_status != 'pending':
        # Duplicate flush of an already-verified session — replay the verdict
        # instead of double-counting the weight drop.
        return {
            'dose_status': active_session.dose_status,
            'actual_reduction_grams': active_session.weight_reduction_actual,
            'expected_reduction_grams': active_session.weight_reduction_expected,
            'current_balance_grams': active_session.actual_weight_after,
            'missed_medicines': [],
            'session_id': str(active_session.id),
            'duplicate': True,
        }

    # Baseline measured by the device at dose start is the most trustworthy
    # reference; the stored device total is the fallback.
    reference = active_session.expected_weight_before or device.total_weight_grams
    actual_reduction = max(reference - actual_weight, 0.0)
    expected_reduction = (
        active_session.weight_reduction_expected
        or calculate_dose_expected_reduction(sub_compartments)
    )

    dose_status = verify_dose(actual_reduction, expected_reduction)

    missed_medicines = []
    if dose_status in ('partial', 'missed'):
        deficit = max(expected_reduction - actual_reduction, 0)
        if deficit > 0:
            missed_medicines = identify_missed_medicines(sub_compartments, deficit)

    active_session.actual_weight_after = actual_weight
    active_session.weight_reduction_actual = round(actual_reduction, 3)
    active_session.weight_reduction_expected = round(expected_reduction, 3)
    active_session.dose_status = dose_status
    active_session.completed_at = occurred_at or timezone.now()
    active_session.save()

    # Only this compartment lost weight, so only its content drops. The
    # device-wide running reference becomes the reading we just took.
    compartment.current_balance_weight_grams = max(
        compartment.current_balance_weight_grams - actual_reduction, 0.0
    )
    compartment.save(update_fields=['current_balance_weight_grams'])

    device.total_weight_grams = actual_weight
    device.save(update_fields=['total_weight_grams'])

    if dose_status in ('partial', 'missed'):
        _notify_partial_or_missed(device, compartment.compartment_number,
                                  dose_status, actual_reduction, expected_reduction,
                                  missed_medicines)

    return {
        'dose_status': dose_status,
        'actual_reduction_grams': round(actual_reduction, 3),
        'expected_reduction_grams': round(expected_reduction, 3),
        'compartment_balance_grams': round(compartment.current_balance_weight_grams, 3),
        'device_total_grams': round(actual_weight, 3),
        'missed_medicines': missed_medicines,
        'session_id': str(active_session.id),
    }


def _record_tamper(device, compartment, actual_weight: float, occurred_at=None) -> dict:
    """
    Weight moved with no dose session open. Could be a refill, a knock, or pills
    removed off-schedule — all indistinguishable with one shared load cell.
    Log and alert, but leave balances alone so the dose math stays trustworthy.
    """
    import uuid as _uuid

    from .models import DeviceEvent

    delta = round(device.total_weight_grams - actual_weight, 3)

    DeviceEvent.objects.create(
        device=device,
        event_uuid=f'tamper-{_uuid.uuid4()}',
        event_type='TAMPER',
        compartment_num=compartment.compartment_number,
        occurred_at=occurred_at,
        raw_payload={
            'reason': 'weight_change_without_active_session',
            'reference_grams': round(device.total_weight_grams, 3),
            'reading_grams': round(actual_weight, 3),
            'delta_grams': delta,
        },
    )

    logger.warning(
        "TAMPER on device %s compartment %s: %sg change with no active session",
        device.id, compartment.compartment_number, delta,
    )
    _notify_tamper(device, compartment.compartment_number, delta)

    return {
        'dose_status': 'tamper_suspected',
        'error': 'no_active_session',
        'delta_grams': delta,
        'reading_grams': round(actual_weight, 3),
        'balances_adjusted': False,
    }


# ── Fill mode — device-wide cumulative subtraction ──────────────────────────

def process_fill_measurement(device, compartment, total_weight: float,
                             medicine_id: str = None) -> dict:
    """
    One step of the guided fill sequence.

    The load cell reads the whole carousel, so each measurement includes
    everything loaded before it. The new content is the difference against the
    running device-wide reference, which then advances:

        derived  = total_weight - device.total_weight_grams
        reference = total_weight

    Passing `medicine_id` attributes the step to a single medicine and derives
    its per-pill weight; omitting it attributes the step to the compartment as
    a whole.
    """
    from .models import SubCompartment, WeightHistory

    reference = device.total_weight_grams
    derived = round(total_weight - reference, 3)

    if derived <= 0:
        return {
            'error': 'no_weight_added',
            'message': (
                f'Reading ({total_weight}g) is not above the running reference '
                f'({reference}g). Check that pills were actually added.'
            ),
            'reference_grams': round(reference, 3),
            'reading_grams': round(total_weight, 3),
        }

    WeightHistory.objects.create(
        device=device,
        compartment_number=compartment.compartment_number,
        weight_grams=total_weight,
    )

    result = {
        'compartment_number': compartment.compartment_number,
        'reference_before_grams': round(reference, 3),
        'reading_grams': round(total_weight, 3),
        'derived_weight_grams': derived,
    }

    if medicine_id:
        sub = SubCompartment.objects.filter(
            id=medicine_id, compartment=compartment, is_active=True
        ).first()
        if not sub:
            return {'error': 'medicine_not_found'}
        if sub.total_pills <= 0:
            return {'error': 'total_pills_not_set',
                    'message': f'{sub.medicine_name} has no total_pills to divide by.'}

        sub.pill_weight_grams = round(derived / sub.total_pills, 4)
        sub.total_weight_grams = derived
        sub.ai_analysis_data = {
            'source': 'load_cell_measured',
            'device_reference_before_grams': round(reference, 3),
            'device_reading_grams': round(total_weight, 3),
            'this_medicine_weight_grams': derived,
            'total_pills': sub.total_pills,
        }
        sub.save(update_fields=[
            'pill_weight_grams', 'total_weight_grams', 'ai_analysis_data',
        ])
        result['medicine_name'] = sub.medicine_name
        result['total_pills'] = sub.total_pills
        result['pill_weight_grams'] = sub.pill_weight_grams

    # Compartment expected weight is the sum of what has actually been measured
    # into it; balance starts equal to it until doses begin.
    measured = compartment.sub_compartments.filter(is_active=True, pill_weight_grams__gt=0)
    compartment.expected_weight_grams = round(
        sum(s.total_weight_grams for s in measured) or derived, 3
    )
    compartment.current_balance_weight_grams = compartment.expected_weight_grams
    compartment.last_filled_at = timezone.now()
    compartment.save(update_fields=[
        'expected_weight_grams', 'current_balance_weight_grams', 'last_filled_at',
    ])

    device.total_weight_grams = total_weight
    device.save(update_fields=['total_weight_grams'])

    result['compartment_expected_weight_grams'] = compartment.expected_weight_grams
    result['device_total_grams'] = round(total_weight, 3)
    return result


# ── Gate event handling ──────────────────────────────────────────────────────

def handle_gate_event(device, compartment_number: int, event_type: str) -> dict:
    """
    Process a gate open/close event from ESP32.
    - Records GateEvent.
    - On 'open': increments gate_open_count on active DoseSession.
    - If count exceeds MAX_GATE_OPENS: locks gate, queues GATE_LOCK command, notifies caregiver.
    Returns dict with gate_locked flag and command (if any) for ESP32 to execute.
    """
    from .models import GateEvent, DoseSession, PhysicalCompartment, DeviceCommand
    from datetime import timedelta

    compartment = PhysicalCompartment.objects.filter(
        device=device, compartment_number=compartment_number
    ).first()

    session = None
    if compartment:
        session = (
            DoseSession.objects.filter(compartment=compartment, dose_status='pending')
            .order_by('-created_at')
            .first()
        )

    GateEvent.objects.create(
        device=device,
        compartment_number=compartment_number,
        event_type=event_type,
        session=session,
    )

    gate_locked = device.is_gate_locked
    issued_command = None

    if event_type == 'open' and session and not session.is_gate_locked:
        session.gate_open_count += 1
        session.save(update_fields=['gate_open_count'])

        if session.gate_open_count > MAX_GATE_OPENS:
            session.is_gate_locked = True
            session.save(update_fields=['is_gate_locked'])

            device.is_gate_locked = True
            device.save(update_fields=['is_gate_locked'])

            gate_locked = True
            issued_command = 'GATE_LOCK'

            # Queue hardware command so ESP32 physically locks the gate
            DeviceCommand.objects.create(
                device=device,
                command_type='GATE_LOCK',
                payload={
                    'compartment': compartment_number,
                    'reason': f'Gate opened {session.gate_open_count} times (limit {MAX_GATE_OPENS})',
                },
                expires_at=timezone.now() + timedelta(hours=24),
            )

            _notify_gate_locked(device, compartment_number, session.gate_open_count)

    return {
        'gate_locked': gate_locked,
        'gate_open_count': session.gate_open_count if session else 0,
        'command': issued_command,
    }


def caregiver_unlock(device) -> dict:
    """
    Remote caregiver unlock: clear gate lock on device and latest pending session.
    Queues GATE_UNLOCK command for ESP32 to physically unlock.
    """
    from .models import DoseSession, DeviceCommand, PhysicalCompartment
    from datetime import timedelta

    device.is_gate_locked = False
    device.save(update_fields=['is_gate_locked'])

    # Unlock all pending locked sessions
    locked_sessions = DoseSession.objects.filter(
        compartment__device=device,
        is_gate_locked=True,
    )
    locked_sessions.update(is_gate_locked=False, gate_open_count=0)

    DeviceCommand.objects.create(
        device=device,
        command_type='GATE_UNLOCK',
        payload={'reason': 'Caregiver remote unlock'},
        expires_at=timezone.now() + timedelta(hours=1),
    )

    return {'unlocked': True, 'message': 'Gate unlocked. GATE_UNLOCK command queued for device.'}


# ── Private notification helpers ─────────────────────────────────────────────

def _notify_partial_or_missed(device, compartment_number, dose_status,
                               actual_reduction, expected_reduction, missed_medicines):
    try:
        from apps.iot.tasks import _send_whatsapp
        phone = device.caregiver_phone
        if not phone:
            return
        missed_names = ', '.join(m['medicine_name'] for m in missed_medicines) or 'unknown'
        msg = (
            f"{'PARTIAL DOSE' if dose_status == 'partial' else 'MISSED DOSE'} ALERT\n"
            f"Device: {device.device_name}\n"
            f"Compartment: {compartment_number}\n"
            f"Expected: {round(expected_reduction, 1)}g reduction, got: {round(actual_reduction, 1)}g\n"
            f"Likely missed: {missed_names}"
        )
        _send_whatsapp(phone, msg)
    except Exception as exc:
        logger.warning("Failed to send partial/missed dose notification: %s", exc)


def _notify_tamper(device, compartment_number, delta_grams):
    try:
        from apps.iot.tasks import _send_whatsapp
        phone = device.caregiver_phone
        if not phone:
            return
        _send_whatsapp(
            phone,
            f"UNEXPECTED WEIGHT CHANGE — {device.device_name}\n"
            f"Compartment {compartment_number} changed by {delta_grams}g "
            f"with no dose scheduled.\n"
            f"Pills may have been removed outside the schedule, or the "
            f"dispenser was moved. Please check the device."
        )
    except Exception as exc:
        logger.warning("Failed to send tamper notification: %s", exc)


def _notify_gate_locked(device, compartment_number, gate_open_count):
    try:
        from apps.iot.tasks import _send_whatsapp
        phone = device.caregiver_phone
        if not phone:
            return
        _send_whatsapp(
            phone,
            f"GATE LOCKED — {device.device_name}\n"
            f"Compartment {compartment_number} gate locked after "
            f"{gate_open_count} open attempts (limit {MAX_GATE_OPENS}).\n"
            f"Please unlock from the app."
        )
    except Exception as exc:
        logger.warning("Failed to send gate lock notification: %s", exc)
