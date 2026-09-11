"""
dispenser.py - target compartment movement, dispensing window, ultrasonic
hand detection aur servo control.

Poore dose lifecycle ka state machine yahan hai:

    RTC slot match -> rotate -> baseline weight -> DOSE_STARTED -> reminder
    -> haath aaya -> gate open -> HAND_DETECTED + LID_OPENED
    -> haath hataya -> gate close -> LID_CLOSED -> settle -> after weight
    -> WEIGHT_READING -> dose_status (taken/partial/missed)

WiFi na ho to bhi ye poora flow chalta hai - RTC aur local schedule kaafi
hain. Sirf backend ko events queue mein jama karne padte hain.
"""
try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

import api
import audio
import config
import display
import scheduler
import servo
import stepper
import storage
import ultrasonic

STATE_IDLE = "idle"
STATE_FILL_MODE = "fill_mode"
STATE_DOSE_PREPARE = "dose_prepare"
STATE_DISPENSING = "dispensing"
STATE_GATE_OPEN = "gate_open"
STATE_WEIGHT_CHECK = "weight_check"
STATE_GATE_LOCKED = "gate_locked"

state = STATE_IDLE
active_compartment = None
active_session_id = None
baseline_weight = 0.0
gate_open_count = 0
dispense_start_ms = 0

_load_cell = None    # loadcell module ya None (hardware na ho to)
_hall = None          # hall_sensor module ya None


def init(load_cell_module=None, hall_module=None):
    """
    load_cell_module/hall_module optional hain - jinke bina bhi dispenser
    chal sake (weight verification aur homing skip ho jaayenge, warning ke
    saath).
    """
    global _load_cell, _hall, state
    _load_cell = load_cell_module
    _hall = hall_module
    state = STATE_GATE_LOCKED if storage.is_gate_locked() else STATE_IDLE


async def home():
    """Boot par carousel ki asli position pata karo."""
    if _hall is None:
        print("[DISP] Hall sensor nahi hai - compartment 1 maan rahe hain")
        stepper.set_position(1, known=False)
        return False
    return await _hall.find_home()


def _read_weight_sync_or_stub():
    """_load_cell na ho to 0.0 - dose verification backend side par bhi
    "no_baseline" ban jaayega, dosing rukega nahi."""
    if _load_cell is None:
        return 0.0
    return _load_cell.get_weight_grams()


async def _read_weight_stable():
    if _load_cell is None:
        return 0.0
    return await _load_cell.get_stable_weight_grams()


def is_gate_locked():
    return state == STATE_GATE_LOCKED


def lock_gate(reason=""):
    global state
    storage.set_gate_locked(True)
    state = STATE_GATE_LOCKED
    display.gate_locked()
    audio.alert()
    print("[DISP] Gate LOCKED:", reason)


def unlock_gate():
    global state
    storage.set_gate_locked(False)
    audio.play(config.AUDIO_CAREGIVER_UNLOCK)
    display.message("Unlocked!", "Caregiver ne khola", "Dawai le lo")
    audio.beep(2, 200)
    if active_compartment is not None:
        state = STATE_DISPENSING     # ruka hua dose resume
    else:
        state = STATE_IDLE
    print("[DISP] Gate UNLOCKED")


async def start_dose(compartment_dict, manual=False):
    """
    Dose shuru karo - scheduler (RTC match) ya TRIGGER_DOSE command dono se
    aata hai.

    Manual triggers aaj ke liye compartment ko LOCK nahi karte, taaki uska
    asli scheduled dose baad mein bhi fire ho sake.
    """
    global state, active_compartment, active_session_id, baseline_weight
    global gate_open_count, dispense_start_ms

    if is_gate_locked():
        print("[DISP] Gate locked hai - dose start nahi hoga")
        display.gate_locked()
        return False
    if state != STATE_IDLE:
        print("[DISP] Busy hai - dose start ignore")
        return False

    number = compartment_dict["compartment_number"]

    active_compartment = compartment_dict
    active_session_id = api.uuid4()
    gate_open_count = 0
    baseline_weight = 0.0

    if not manual:
        storage.mark_dispensed(number)

    state = STATE_DOSE_PREPARE
    dispense_start_ms = _now_ms()
    audio.beep(3, 200)

    print("[DISP] %s dose shuru: compartment %d (session %s)"
          % ("Manual" if manual else "Scheduled", number, active_session_id))

    await stepper.rotate_to(number)
    api.emit_compartment_rotated(number)

    await asyncio.sleep_ms(config.WEIGHT_SETTLE_MS)
    baseline_weight = await _read_weight_stable()
    api.emit_dose_started(number, active_session_id, baseline_weight)

    audio.play(compartment_dict.get("audio_track", config.AUDIO_DOSE_REMINDER))
    print("[DISP] Baseline %.2fg - haath ka intezaar" % baseline_weight)

    state = STATE_DISPENSING
    return True


def _now_ms():
    import time
    return time.ticks_ms()


def _elapsed_ms(since):
    import time
    return time.ticks_diff(time.ticks_ms(), since)


def _end_session():
    global state, active_compartment, active_session_id, gate_open_count, baseline_weight
    active_compartment = None
    active_session_id = None
    gate_open_count = 0
    baseline_weight = 0.0
    state = STATE_GATE_LOCKED if is_gate_locked() else STATE_IDLE


async def tick():
    """
    Har loop iteration call hota hai. taskSensor ke barabar - ultrasonic,
    gate, weight, timeout sab yahan handle hote hain.
    """
    global state, gate_open_count

    if state == STATE_IDLE:
        return

    if state == STATE_DISPENSING:
        await _tick_dispensing()
    elif state == STATE_GATE_OPEN:
        await _tick_gate_open()
    elif state == STATE_WEIGHT_CHECK:
        await _tick_weight_check()
    elif state == STATE_GATE_LOCKED:
        pass   # display.gate_locked() ko main loop periodic call karega


async def _tick_dispensing():
    global state, gate_open_count

    number = active_compartment["compartment_number"]
    window_ms = scheduler.dose_window_ms()

    if _elapsed_ms(dispense_start_ms) >= window_ms:
        await servo.close_lid()
        api.emit_dose_timeout(number, active_session_id)
        audio.play(config.AUDIO_DOSE_MISSED)
        audio.alert()
        display.message("DOSE TIMEOUT", "Alerting caregiver", "")
        _end_session()
        return

    if is_gate_locked():
        return

    if ultrasonic.hand_detected():
        gate_open_count += 1

        # Backend GATE_LOCK bhejne se pehle hi self-enforce karo - agar
        # socket down hai to command time par nahi pahunchega.
        if gate_open_count > scheduler.max_gate_opens():
            lock_gate("gate open limit (%d) exceeded" % scheduler.max_gate_opens())
            return

        api.emit_hand_detected(number, active_session_id)
        await servo.open_lid()
        audio.play(config.AUDIO_TAKE_MEDICINE)
        api.emit_lid_opened(number, active_session_id)
        state = STATE_GATE_OPEN
        audio.beep(1, 100)
        print("[DISP] Lid opened (count=%d)" % gate_open_count)


_gate_close_at = 0


async def _tick_gate_open():
    global state, _gate_close_at

    number = active_compartment["compartment_number"]

    if not ultrasonic.hand_detected():
        await asyncio.sleep_ms(500)
        if not ultrasonic.hand_detected():        # debounced
            await servo.close_lid()
            _gate_close_at = _now_ms()
            api.emit_lid_closed(number, active_session_id)
            print("[DISP] Lid closed - weight check")
            state = STATE_WEIGHT_CHECK
            return

    if _elapsed_ms(dispense_start_ms) >= scheduler.dose_window_ms():
        await servo.close_lid()
        _gate_close_at = _now_ms()
        api.emit_lid_closed(number, active_session_id)
        state = STATE_WEIGHT_CHECK


async def _tick_weight_check():
    global state

    if _elapsed_ms(_gate_close_at) < config.GATE_CLOSE_CONFIRM_MS:
        return

    number = active_compartment["compartment_number"]
    weight = await _read_weight_stable()
    print("[DISP] After-dose weight: %.2fg (baseline %.2fg)" % (weight, baseline_weight))

    status_code, data = api.emit_weight_reading(number, weight, "after_dose", active_session_id)

    if status_code in (200, 201) and data:
        dose_status = data.get("dose_status", "unknown")
        print("[DISP] dose_status:", dose_status)
        display.dose_result(dose_status)

        if dose_status == "taken":
            audio.play(config.AUDIO_DOSE_TAKEN)
            audio.beep(3, 100)
            await asyncio.sleep_ms(3000)
            _end_session()
        elif dose_status == "partial":
            audio.beep(2, 300)
            state = STATE_DISPENSING       # session khula rehta hai
        else:
            audio.beep(1, 500)
            state = STATE_DISPENSING
    else:
        # Offline: event queue mein hai, baad mein verify hoga. Yahan
        # "taken" ya "missed" claim NAHI karte.
        print("[DISP] Offline - weight baad ke liye queued")
        display.dose_result("pending_sync")
        audio.beep(2, 150)
        await asyncio.sleep_ms(3000)
        _end_session()


# ── Fill mode ────────────────────────────────────────────────
async def start_fill_mode(compartment_number, medicine_name=""):
    global state
    await stepper.rotate_to(compartment_number)
    await servo.open_lid()
    display.fill_mode(compartment_number, medicine_name)
    audio.beep(2, 150)
    state = STATE_FILL_MODE


async def end_fill_mode():
    global state
    await servo.close_lid()
    display.message("Fill Complete!", "All stocked", "")
    audio.beep(3, 100)
    state = STATE_IDLE


async def read_fill_weight(compartment_number, medicine_id, medicine_name=""):
    display.message("Measuring...", medicine_name, "Keep still!")
    await asyncio.sleep_ms(scheduler.weight_settle_ms())
    weight = await _read_weight_stable()

    result = api.post_fill_measure(compartment_number, weight, medicine_id)
    if result:
        pill_weight = result.get("pill_weight_grams", 0.0)
        display.message("Weight OK!", "%.1fg" % weight, "%.3fg/pill" % pill_weight)
        audio.beep(2, 100)
    else:
        display.message("Measure FAILED", "", "")
        audio.beep(1, 600)
    return result
