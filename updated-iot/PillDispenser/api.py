import os
import time
import json

from config import (
    BACKEND_URL,
    DEVICE_ID,
    DEVICE_API_KEY,
    API_EVENTS,
    API_HEARTBEAT,
    API_SYNC_TIME,
    API_CONFIG,
    FIRMWARE_VERSION
)

from rtc import rtc
import storage
from wifi import is_connected
import mqtt_client


HEADERS = {
    "Content-Type": "application/json",
    "X-Device-Key": DEVICE_API_KEY
}

REQUEST_TIMEOUT = 10


def generate_uuid():
    """Generates a pseudo RFC4122 v4 UUID for MicroPython."""
    try:
        raw = bytearray(os.urandom(16))
        raw[6] = (raw[6] & 0x0F) | 0x40
        raw[8] = (raw[8] & 0x3F) | 0x80
        hexed = "".join("%02x" % b for b in raw)
        return "%s-%s-%s-%s-%s" % (
            hexed[0:8], hexed[8:12], hexed[12:16], hexed[16:20], hexed[20:32]
        )
    except Exception:
        return "evt-%d" % time.time()


def _request(method, endpoint, payload=None):
    """
    HTTP request helper using urequests.
    Returns (status_code, response_json_or_dict).
    """
    if not is_connected():
        return (-1, None)

    try:
        import urequests
    except ImportError:
        print("[API ERROR] 'urequests' module not found on ESP32!")
        return (-1, None)

    url = BACKEND_URL + endpoint
    response = None

    try:
        if method == "GET":
            response = urequests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        elif method == "POST":
            data_str = json.dumps(payload or {})
            response = urequests.post(url, data=data_str, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        else:
            return (-1, None)

        status = response.status_code
        data = None
        if status in (200, 201):
            try:
                data = response.json()
            except Exception:
                data = None

        return (status, data)

    except Exception as e:
        print("[API] Request failed (%s %s): %s" % (method, endpoint, e))
        return (-1, None)

    finally:
        if response is not None:
            try:
                response.close()
            except Exception:
                pass


# ============================================================
# SYNC RTC TIME FROM BACKEND
# ============================================================

def sync_time_from_backend():
    """
    Fetches the server time and sets the DS3231 RTC.
    Prefers config bundle's server_time_local (IST wall clock).
    """
    print("[API] Syncing time from backend...")
    iso_str = None

    # 1. Check config bundle first for device-local IST wall clock
    status, res = _request("GET", API_CONFIG)
    if status == 200 and res:
        data = res.get("data", {})
        iso_str = data.get("server_time_local")

    # 2. Fallback to /sync/time/
    if not iso_str:
        status, res = _request("GET", API_SYNC_TIME)
        if status == 200 and res:
            data = res.get("data", {})
            iso_str = data.get("iso_time")

    if iso_str:
        try:
            # Format: 2026-09-14T21:05:30.123456+05:30 or 2026-09-14T21:05:30
            date_part, time_part = iso_str.split("T")
            y, m, d = [int(x) for x in date_part.split("-")]

            clean_time = time_part.split(".")[0].split("+")[0].split("Z")[0]
            h, mn, s = [int(x) for x in clean_time.split(":")[:3]]

            rtc.set_time(y, m, d, h, mn, s)
            print("[API] RTC time successfully set to: %04d-%02d-%02d %02d:%02d:%02d" % (y, m, d, h, mn, s))
            return True
        except Exception as e:
            print("[API] Failed to parse server time:", e)

    print("[API] Time sync failed. Retaining current RTC time.")
    return False


# ============================================================
# FETCH SCHEDULES BUNDLE FROM BACKEND
# ============================================================

def fetch_schedules_from_backend():
    """
    Fetches the device configuration bundle containing all compartment schedules.
    """
    print("[API] Fetching schedules bundle from backend...")
    status, res = _request("GET", API_CONFIG)

    if status == 200 and res:
        data = res.get("data")
        if data:
            success = storage.save_bundle_from_backend(data)
            return success

    print("[API] Failed to fetch backend schedules. Using local schedules.json.")
    return False


# ============================================================
# SEND LIVE EVENT (MQTT FIRST, HTTP FALLBACK, OFFLINE QUEUE)
# ============================================================

def send_event(event_type, compartment=None, extra=None):
    """
    Sends an event to backend via MQTT (primary) with HTTP fallback and offline queue.
    """
    payload = {
        "event_uuid": generate_uuid(),
        "event_type": event_type,
        "device_id": DEVICE_ID,
        "compartment": compartment,
        "compartment_num": compartment,
        "occurred_at": rtc.get_iso(),
        "firmware_version": FIRMWARE_VERSION
    }

    if extra and isinstance(extra, dict):
        payload.update(extra)

    print("[EVENT] Emitting event:", event_type, "Compartment:", compartment)

    # 1. Try MQTT Publish (Primary)
    if mqtt_client.is_mqtt_connected():
        ok = mqtt_client.publish_event(payload)
        if ok:
            print("[EVENT] Sent via MQTT successfully:", event_type)
            return True

    # 2. Fallback to HTTP POST
    print("[EVENT] MQTT unavailable. Attempting HTTP POST fallback...")
    status, res = _request("POST", API_EVENTS, payload)
    if status in (200, 201):
        print("[EVENT] Sent via HTTP fallback successfully:", event_type)
        return True

    # 3. Offline Queue
    print("[EVENT] Both MQTT & HTTP unreachable. Saving event to offline queue.")
    storage.queue_event(payload)
    return False


# ============================================================
# SEND HEARTBEAT (MQTT FIRST, HTTP FALLBACK)
# ============================================================

def send_heartbeat(stepper_status="ok", servo_status="ok", ultrasonic_status="ok"):
    """
    Sends periodic heartbeat via MQTT (primary) or HTTP fallback.
    """
    payload = {
        "device_id": DEVICE_ID,
        "battery_level": 100,
        "firmware_version": FIRMWARE_VERSION,
        "stepper_status": stepper_status,
        "servo_status": servo_status,
        "ultrasonic_status": ultrasonic_status,
        "rtc_time": rtc.get_iso(),
        "timestamp": time.time()
    }

    # 1. Try MQTT
    if mqtt_client.is_mqtt_connected():
        ok = mqtt_client.publish_heartbeat(payload)
        if ok:
            print("[HEARTBEAT] Sent via MQTT successfully.")
            return True

    # 2. Try HTTP
    status, res = _request("POST", API_HEARTBEAT, payload)
    if status == 200:
        print("[HEARTBEAT] Sent via HTTP fallback.")
        data = res.get("data", {}) if res else {}
        if data.get("config_stale"):
            print("[API] Backend indicates config is stale. Refreshing bundle...")
            fetch_schedules_from_backend()
        return True

    return False


# ============================================================
# FLUSH OFFLINE QUEUE
# ============================================================

def flush_offline_events():
    """
    Flushes queued offline events once network is available.
    """
    events = storage.get_queued_events()
    if not events:
        return True

    print("[OFFLINE] Attempting to flush %d queued events..." % len(events))

    # Try MQTT first
    if mqtt_client.is_mqtt_connected():
        flushed_count = 0
        for ev in events:
            if mqtt_client.publish_event(ev):
                flushed_count += 1
        if flushed_count == len(events):
            print("[OFFLINE] All queued events flushed via MQTT!")
            storage.clear_queued_events()
            return True

    # Fallback to HTTP Batch
    if is_connected():
        batch_url = "/api/v1/iot/events/batch/"
        status, res = _request("POST", batch_url, {"events": events})
        if status in (200, 201):
            print("[OFFLINE] All queued events flushed via HTTP Batch!")
            storage.clear_queued_events()
            return True

    return False
