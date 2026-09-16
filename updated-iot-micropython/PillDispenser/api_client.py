"""
api_client.py - Direct port of api_client.h. Same manual substring parsing
as the Arduino version (no JSON library assumptions about backend schema),
same HTTP endpoints/payload shapes, same command-poll algorithm.

Requires the `urequests` library (not built into MicroPython by default):
    import mip; mip.install("urequests")
or copy urequests.py onto the device manually.
"""
import time
import network
import urequests as requests

import config
import rtc_ds3231 as rtc

# Set by main.py after it defines handle_remote_command, to avoid a
# circular import (main.py also imports this module).
handle_remote_command = None

_wlan = network.WLAN(network.STA_IF)

# ============================================================
# SCHEDULE STRUCTURE
# ============================================================
# Default fallback schedules (matching schedules.json)
schedules = [
    {"compartment": 1, "medicine": "Paracetamol", "time": "17:49", "dose": 1, "enabled": True},
    {"compartment": 2, "medicine": "Vitamin_C", "time": "17:54", "dose": 1, "enabled": True},
    {"compartment": 3, "medicine": "Calcium", "time": "17:59", "dose": 1, "enabled": True},
    {"compartment": 4, "medicine": "Multivitamin", "time": "18:04", "dose": 1, "enabled": True},
]


def wifi_is_connected():
    return _wlan.isconnected()


def to_int(s):
    """Mimics Arduino String.toInt(): parse leading digits, 0 if none."""
    s = s.strip()
    num = ""
    for ch in s:
        if ch.isdigit() or (ch == "-" and num == ""):
            num += ch
        else:
            break
    if num in ("", "-"):
        return 0
    return int(num)


def _http_get(url):
    try:
        resp = requests.get(url, headers={"X-Device-Key": config.DEVICE_API_KEY})
        text = resp.text if resp.status_code == 200 else None
        resp.close()
        return text
    except Exception as exc:
        print("[API] HTTP GET failed:", exc)
        return None


def _http_post(url, body):
    try:
        resp = requests.post(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Device-Key": config.DEVICE_API_KEY,
            },
        )
        code = resp.status_code
        resp.close()
        return code
    except Exception as exc:
        print("[API] HTTP POST failed:", exc)
        return -1


def sync_time_from_backend():
    if not wifi_is_connected():
        print("[API] WiFi not connected. Cannot sync time.")
        return False

    # Try config bundle first for exact device-local time (IST)
    payload = _http_get(config.BACKEND_URL + config.API_CONFIG)
    if payload is None:
        # Fallback to /sync/time/
        payload = _http_get(config.BACKEND_URL + config.API_SYNC_TIME)

    if not payload:
        print("[API] Time sync failed.")
        return False

    # Extract ISO time from server_time_local or iso_time
    idx = payload.find('"server_time_local":"')
    if idx < 0:
        idx = payload.find('"iso_time":"')

    if idx >= 0:
        t_idx = payload.find("T", idx)
        if t_idx > 0:
            date_part = payload[t_idx - 10:t_idx]
            time_part = payload[t_idx + 1:t_idx + 9]

            y = to_int(date_part[0:4])
            m = to_int(date_part[5:7])
            d = to_int(date_part[8:10])

            h = to_int(time_part[0:2])
            mn = to_int(time_part[3:5])
            s = to_int(time_part[6:8])

            rtc.set_rtc(y, m, d, h, mn, s)
            print("[API] RTC time synced: {:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
                y, m, d, h, mn, s))
            return True

    print("[API] Could not parse server time.")
    return False


def fetch_schedules_from_backend():
    if not wifi_is_connected():
        return False

    payload = _http_get(config.BACKEND_URL + config.API_CONFIG)
    if payload is None:
        print("[API] Config bundle fetch failed.")
        return False

    # Parse compartments from payload
    # Search for compartment_number and time
    search_idx = 0
    synced_count = 0

    while search_idx < len(payload):
        comp_idx = payload.find('"compartment_number":', search_idx)
        if comp_idx < 0:
            break

        comp_num = to_int(payload[comp_idx + 21:comp_idx + 23])

        time_idx = payload.find('"time":"', comp_idx)
        if 0 < time_idx < comp_idx + 200:
            slot_time = payload[time_idx + 8:time_idx + 13]

            if 1 <= comp_num <= config.TOTAL_COMPARTMENTS:
                entry = schedules[comp_num - 1]
                entry["compartment"] = comp_num
                entry["time"] = slot_time

                # Extract medicine name if present
                med_idx = payload.find('"name":"', comp_idx)
                if 0 < med_idx < comp_idx + 400:
                    med_end = payload.find('"', med_idx + 8)
                    if med_end > 0:
                        entry["medicine"] = payload[med_idx + 8:med_end]

                synced_count += 1

        search_idx = comp_idx + 25

    if synced_count > 0:
        print("[API] Synced {} compartment schedules from backend!".format(synced_count))
        return True

    return False


# ============================================================
# EVENT / HEARTBEAT REPORTING (plain HTTP - deployed backend)
# ============================================================
def publish_event(event_type, compartment, medicine="Unknown", dose=1):
    payload = (
        '{{"event_type":"{}","compartment":{},"compartment_num":{},'
        '"medicine":"{}","dose":{},"occurred_at":"{}","device_id":"{}",'
        '"firmware_version":"{}"}}'
    ).format(
        event_type, compartment, compartment, medicine, dose,
        rtc.get_rtc_iso_string(), config.DEVICE_ID, config.FIRMWARE_VERSION,
    )

    print("[EVENT] Emitting: {} (Comp {})".format(event_type, compartment))

    if not wifi_is_connected():
        print("[EVENT] WiFi not connected. Event dropped.")
        return False

    code = _http_post(config.BACKEND_URL + config.API_EVENTS, payload)

    if code == 200 or code == 201:
        print("[HTTP] Event sent: {}".format(event_type))
        return True

    print("[HTTP] Event send failed: {} (code {})".format(event_type, code))
    return False


def publish_heartbeat(stepper_status="ok", servo_status="ok", ultrasonic_status="ok"):
    if not wifi_is_connected():
        return False

    payload = (
        '{{"device_id":"{}","battery_level":100,"firmware_version":"{}",'
        '"stepper_status":"{}","servo_status":"{}","ultrasonic_status":"{}",'
        '"rtc_time":"{}"}}'
    ).format(
        config.DEVICE_ID, config.FIRMWARE_VERSION, stepper_status,
        servo_status, ultrasonic_status, rtc.get_rtc_iso_string(),
    )

    code = _http_post(config.BACKEND_URL + config.API_HEARTBEAT, payload)

    if code == 200:
        print("[HTTP] Heartbeat sent successfully.")
        return True

    print("[HTTP] Heartbeat send failed (code {})".format(code))
    return False


# ============================================================
# REMOTE COMMAND POLLING (HTTP poll, replaces MQTT subscription)
# ============================================================
def acknowledge_command(command_id):
    if not wifi_is_connected():
        return False

    payload = (
        '{{"event_type":"COMMAND_ACKNOWLEDGED","command_id":"{}",'
        '"occurred_at":"{}","device_id":"{}","firmware_version":"{}"}}'
    ).format(command_id, rtc.get_rtc_iso_string(), config.DEVICE_ID, config.FIRMWARE_VERSION)

    code = _http_post(config.BACKEND_URL + config.API_EVENTS, payload)
    return code == 200 or code == 201


def poll_device_commands():
    if not wifi_is_connected():
        return

    payload = _http_get(config.BACKEND_URL + config.API_COMMANDS)
    if payload is None:
        return

    # Manual parse of: {"commands":[{"command_id":"...","type":"...","payload":{...}}, ...]}
    search_idx = 0
    processed = 0

    while search_idx < len(payload) and processed < 5:
        id_idx = payload.find('"command_id":"', search_idx)
        if id_idx < 0:
            break

        id_start = id_idx + 14  # length of: "command_id":"
        id_end = payload.find('"', id_start)
        if id_end < 0:
            break
        command_id = payload[id_start:id_end]

        cmd_type = ""
        type_idx = payload.find('"type":"', id_end)
        if 0 < type_idx < id_end + 100:
            type_start = type_idx + 8  # length of: "type":"
            type_end = payload.find('"', type_start)
            if type_end > 0:
                cmd_type = payload[type_start:type_end]

        cmd_payload = "{}"
        payload_idx = payload.find('"payload":', id_end)
        if 0 < payload_idx < id_end + 150:
            brace_start = payload.find("{", payload_idx)
            brace_end = payload.find("}", brace_start)
            if brace_start > 0 and brace_end > brace_start:
                cmd_payload = payload[brace_start:brace_end + 1]

        print()
        print("==========================================")
        print(">>> REMOTE COMMAND RECEIVED (HTTP) <<<")
        print("Type: {} | Command ID: {}".format(cmd_type, command_id))
        print("==========================================")

        if handle_remote_command:
            handle_remote_command(cmd_type, cmd_payload)
        acknowledge_command(command_id)

        search_idx = id_end + 1
        processed += 1
