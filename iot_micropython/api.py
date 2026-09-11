"""
api.py - Backend HTTP client + event emission with offline durability.

Dependency: urequests
    mpremote mip install urequests

Har event mein do cheezein hoti hain:
  event_uuid  - delivery idempotent banata hai, retry safe hai
  occurred_at - RTC ka wall clock jab event HUA, upload ke waqt ka nahi

occurred_at hi wo cheez hai jisse WiFi outage ke dauraan hua dose baad mein
sahi timestamp ke saath verify hota hai.

NOTE: urequests blocking hai. Isliye har call ke beech await karte hain aur
timeouts chhote rakhe hain. Dose ke beech (hand detect -> gate open) koi HTTP
call nahi hoti, sirf boundaries par hoti hai.
"""
import os

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

try:
    import ujson as json
except ImportError:
    import json

import config
import rtc
import storage

_HEADERS = {
    "Content-Type": "application/json",
    "X-Device-Key": config.DEVICE_API_KEY,
}

_BATCH_MAX = 8
_TIMEOUT = 8


def uuid4():
    """RFC4122 v4 UUID - backend idempotency isi par chalti hai."""
    raw = bytearray(os.urandom(16))
    raw[6] = (raw[6] & 0x0F) | 0x40      # version 4
    raw[8] = (raw[8] & 0x3F) | 0x80      # variant
    hexed = "".join("%02x" % b for b in raw)
    return "%s-%s-%s-%s-%s" % (hexed[0:8], hexed[8:12], hexed[12:16],
                               hexed[16:20], hexed[20:32])


def _request(method, endpoint, payload=None):
    """
    (status_code, parsed_body) return karta hai.
    Network fail par (-1, None) - exception upar nahi jaata, kyunki offline
    hona normal hai, error nahi.
    """
    try:
        import urequests
    except ImportError:
        print("[API] urequests install nahi hai")
        return (-1, None)

    url = config.BACKEND_URL + endpoint
    response = None
    try:
        if method == "GET":
            response = urequests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        else:
            body = json.dumps(payload or {})
            response = urequests.post(url, data=body, headers=_HEADERS, timeout=_TIMEOUT)

        status = response.status_code
        parsed = None
        if status in (200, 201):
            try:
                parsed = response.json()
            except ValueError:
                parsed = None
        return (status, parsed)

    except Exception as exc:
        print("[API] %s %s failed: %s" % (method, endpoint, exc))
        return (-1, None)
    finally:
        if response is not None:
            try:
                response.close()
            except Exception:
                pass


# ── Config bundle ───────────────────────────────────────────
def fetch_config():
    """
    Poora schedule bundle lao aur cache karo. Sirf tab call hota hai jab
    heartbeat `config_stale` bole - isliye koi periodic schedule poll nahi.
    """
    status, body = _request("GET", config.API_CONFIG)
    print("[API] Config fetch -> HTTP", status)
    if status != 200 or not body:
        return None

    data = body.get("data")
    if not data:
        return None

    storage.save_bundle_from_backend(data)
    return data


# ── Events ──────────────────────────────────────────────────
def build_event(event_type, extra=None):
    event = {
        "event_uuid": uuid4(),
        "event_type": event_type,
        "firmware_version": config.FIRMWARE_VERSION,
    }
    occurred = rtc.get_iso()
    if occurred:
        event["occurred_at"] = occurred
    if extra:
        event.update(extra)
    return event


def emit(event_type, extra=None):
    """
    Fire-and-forget event. POST fail hua to flash queue mein chala jaata hai -
    kabhi chup-chaap gum nahi hota.
    """
    event = build_event(event_type, extra)
    status, _ = _request("POST", config.API_EVENTS, event)

    if status in (200, 201):
        print("[EV] %s sent" % event_type)
        return True

    print("[EV] %s failed (HTTP %s) - queued" % (event_type, status))
    storage.queue_event(event)
    return False


def emit_sync(event_type, extra=None):
    """
    Event bhejo aur backend ka jawab wapas do.
    After-dose weight ke liye - jawab mein dose_status aata hai.
    Returns (status_code, data_dict_or_None).
    """
    event = build_event(event_type, extra)
    status, body = _request("POST", config.API_EVENTS, event)

    if status not in (200, 201):
        print("[EV] %s failed (HTTP %s) - replay ke liye queued" % (event_type, status))
        storage.queue_event(event)
        return (status, None)

    return (status, (body or {}).get("data"))


async def flush_queue():
    """
    Flash queue ko batches mein bhejo. Sirf utne events pop karte hain jitne
    backend ne accept kiye - partial failure par baaki queue mein rehte hain.
    """
    if storage.queue_count() == 0:
        return

    batch = storage.peek_batch(_BATCH_MAX)
    if not batch:
        return

    status, body = _request("POST", config.API_EVENT_BATCH, {"events": batch})

    if status in (200, 201) and body:
        accepted = len(batch)
        storage.pop_front(accepted)
        print("[EV] %d event(s) flushed" % accepted)
    else:
        print("[EV] Flush failed (HTTP %s) - %d queue mein"
              % (status, storage.queue_count()))

    await asyncio.sleep_ms(50)


# ── Typed emitters ──────────────────────────────────────────
def emit_dose_started(compartment, session_uuid, weight_before):
    return emit("DOSE_STARTED", {
        "compartment_num": compartment,
        "session_uuid": session_uuid,
        "weight_before": weight_before,
    })


def emit_compartment_rotated(compartment):
    return emit("COMPARTMENT_ROTATED", {"compartment_num": compartment})


def emit_hand_detected(compartment, session_uuid):
    return emit("HAND_DETECTED", {
        "compartment_num": compartment, "session_uuid": session_uuid,
    })


def emit_lid_opened(compartment, session_uuid):
    return emit("LID_OPENED", {
        "compartment_num": compartment, "session_uuid": session_uuid,
    })


def emit_lid_closed(compartment, session_uuid):
    return emit("LID_CLOSED", {
        "compartment_num": compartment, "session_uuid": session_uuid,
    })


def emit_weight_reading(compartment, grams, phase, session_uuid):
    """
    (status, data) return karta hai. dose_status seedha data par hota hai -
    `data["response_data"]` ke andar NAHI (wo sirf /events/batch/ mein hai).
    """
    return emit_sync("WEIGHT_READING", {
        "compartment_num": compartment,
        "weight_grams": grams,
        "phase": phase,
        "session_uuid": session_uuid,
    })


def emit_dose_timeout(compartment, session_uuid):
    return emit("DOSE_TIMEOUT", {
        "compartment_num": compartment, "session_uuid": session_uuid,
    })


def emit_low_battery(percent):
    return emit("LOW_BATTERY", {"battery_level": percent})


def emit_command_ack(command_id):
    if command_id:
        return emit("COMMAND_ACKNOWLEDGED", {"command_id": command_id})


# ── Heartbeat ───────────────────────────────────────────────
def heartbeat(battery, rssi, uptime_s, schedule_version, state_name, compartment):
    """
    Heartbeat hi config reconciliation channel hai.
    Jawab mein: config_stale, pending_commands, rtc_drift_seconds, gate_locked.
    """
    payload = {
        "battery_level": battery,
        "firmware_version": config.FIRMWARE_VERSION,
        "wifi_strength": rssi,
        "uptime_seconds": uptime_s,
        "schedule_version": schedule_version,
        "rtc_time": rtc.get_iso(),
        "current_compartment": compartment,
        "queued_events": storage.queue_count(),
        "state": state_name,
    }
    status, body = _request("POST", config.API_HEARTBEAT, payload)
    if status in (200, 201) and body:
        return body.get("data")
    return None


# ── Fill mode ───────────────────────────────────────────────
def post_fill_measure(compartment_number, total_weight_grams, medicine_id=None):
    """
    Guided fill ka ek step. Device sirf poore carousel ka total bhejta hai;
    running reference se subtract karna backend ka kaam hai.
    """
    payload = {
        "compartment_number": compartment_number,
        "total_weight_grams": total_weight_grams,
    }
    if medicine_id:
        payload["medicine_id"] = medicine_id

    status, body = _request("POST", config.API_FILL_MEASURE, payload)
    if status in (200, 201) and body:
        data = body.get("data") or {}
        print("[API] Fill measure: +%.2fg, %.4fg per pill"
              % (data.get("derived_weight_grams", 0.0),
                 data.get("pill_weight_grams", 0.0)))
        return data
    print("[API] Fill measure failed -> HTTP", status)
    return None


# ── Commands (safety net - normally WebSocket se aate hain) ──
def poll_commands():
    status, body = _request("GET", config.API_COMMANDS)
    if status != 200 or not body:
        return []
    return ((body.get("data") or {}).get("commands")) or []


# ── Time sync ───────────────────────────────────────────────
def sync_time_with_backend():
    status, body = _request("GET", config.API_SYNC_TIME)
    if status == 200 and body:
        return (body.get("data") or {}).get("unix_timestamp")
    return None
