"""
main.py - poore system ka main loop; RTC, scheduler aur dispensing ko
coordinate karta hai.

Boot order zaroori hai: hardware -> cached schedule/queue (WiFi se PEHLE, taaki
WiFi na milne par bhi RTC + cache se dose chal sake) -> homing -> WiFi ->
config fetch -> WebSocket -> async tasks.

Teen background tasks (C++ firmware ke RTOS tasks ke barabar, yahan
uasyncio coroutines):
  _scheduler_task - RTC slot matching (dose trigger)
  _dispenser_task - dispenser.tick() - gate/weight/timeout
  _network_task   - WebSocket listen, heartbeat, offline queue flush
"""
try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

import time

import network

import api
import audio
import config
import dispenser
import display
import hall_sensor
import loadcell
import rtc
import scheduler
import servo
import stepper
import storage
import ultrasonic
import wsclient

wlan = network.WLAN(network.STA_IF)

# Command_id dedup - WebSocket aur safety-net poll dono se wahi command
# dobara aa sakta hai (at-least-once delivery).
_recent_command_ids = []
_CMD_HISTORY = 8


def _already_handled(command_id):
    return bool(command_id) and command_id in _recent_command_ids


def _remember(command_id):
    if not command_id:
        return
    _recent_command_ids.append(command_id)
    if len(_recent_command_ids) > _CMD_HISTORY:
        _recent_command_ids.pop(0)


# ── WiFi ─────────────────────────────────────────────────────
def connect_wifi():
    display.message("Connecting WiFi", config.WIFI_SSID)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
        for _ in range(config.WIFI_CONNECT_TIMEOUT_S * 2):
            if wlan.isconnected():
                break
            time.sleep_ms(500)
            print(".", end="")

    if wlan.isconnected():
        ip = wlan.ifconfig()[0]
        print("\n[WiFi] Connected:", ip)
        display.message("WiFi OK", ip)
        audio.beep(2)
        return True

    print("\n[WiFi] FAILED - RTC + cached schedule se offline chalega")
    display.message("WiFi FAILED", "Offline mode")
    return False


def sync_time():
    """NTP se system time set karke DS3231 mein bhi likh do."""
    try:
        import ntptime
        ntptime.settime()                    # UTC set karta hai
        ist_seconds = time.time() + 19800    # IST = UTC + 5:30
        t = time.localtime(ist_seconds)
        rtc.write_datetime(t[0], t[1], t[2], t[3], t[4], t[5], t[6] + 1)
        print("[TIME] NTP synced:", rtc.get_time_string())
        api.sync_time_with_backend()
    except Exception as exc:
        print("[TIME] NTP fail (%s) - RTC use karenge" % exc)


# ── Command handling (WebSocket aur safety-net poll dono se) ──
async def handle_command(command_type, command_id, payload):
    if _already_handled(command_id):
        print("[CMD] %s duplicate - ignore" % command_type)
        return
    _remember(command_id)
    print("[CMD]", command_type)

    if command_type in ("SYNC_CONFIG", "SYNC_SCHEDULE"):
        api.fetch_config()

    elif command_type == "TRIGGER_DOSE":
        number = payload.get("compartment") or payload.get("compartment_number")
        comp = storage.get_compartment(number) if number else None
        if comp:
            await dispenser.start_dose(comp, manual=True)
        else:
            print("[CMD] TRIGGER_DOSE: compartment %s nahi mila" % number)

    elif command_type == "GATE_LOCK":
        dispenser.lock_gate(payload.get("reason", "backend"))
        await servo.close_lid()
        audio.play(config.AUDIO_DOSE_MISSED)

    elif command_type == "GATE_UNLOCK":
        dispenser.unlock_gate()

    elif command_type == "OPEN_GATE":
        if not dispenser.is_gate_locked():
            await servo.open_lid()
            if dispenser.active_compartment:
                api.emit_lid_opened(dispenser.active_compartment["compartment_number"],
                                    dispenser.active_session_id)
        else:
            display.message("Gate LOCKED", "Cannot open", "")

    elif command_type in ("START_FILL_MODE", "NEXT_COMPARTMENT"):
        number = payload.get("compartment") or payload.get("compartment_number")
        med_name = payload.get("medication_name") or payload.get("medicine_name", "Medicine")
        if number:
            await dispenser.start_fill_mode(number, med_name)

    elif command_type == "END_FILL_MODE":
        await dispenser.end_fill_mode()
        api.fetch_config()          # expected weights badal gaye

    elif command_type == "READ_FILL_WEIGHT":
        number = payload.get("compartment_number") or payload.get("compartment")
        medicine_id = payload.get("medicine_id", "")
        med_name = payload.get("medicine_name", "")
        if number:
            await dispenser.read_fill_weight(number, medicine_id, med_name)

    elif command_type == "SYNC_TIME":
        sync_time()

    elif command_type == "RESET_FLAGS":
        storage.reset_day(rtc.get_yyyymmdd())
        storage.set_gate_locked(False)
        display.message("Day Reset!", "New day, fresh", "")

    else:
        print("[CMD] Unhandled:", command_type)

    if not wsclient.is_connected():
        api.emit_command_ack(command_id)


# ── Background tasks ─────────────────────────────────────────
async def _scheduler_task():
    """RTC ka dose trigger. Network se bilkul independent hai."""
    while True:
        if scheduler.check_day_rollover():
            pass   # storage ne already print kar diya

        if dispenser.state == dispenser.STATE_IDLE and not dispenser.is_gate_locked():
            comp = scheduler.due_compartment()
            if comp is not None:
                print("[SCHED] Compartment %d ka time ho gaya" % comp["compartment_number"])
                await dispenser.start_dose(comp, manual=False)

        await asyncio.sleep_ms(config.SCHEDULER_TICK_MS)


async def _dispenser_task():
    """Gate/weight/timeout state machine + idle display."""
    last_idle_update = 0
    while True:
        await dispenser.tick()

        if dispenser.state == dispenser.STATE_IDLE:
            now = time.ticks_ms()
            if time.ticks_diff(now, last_idle_update) > 10000:
                last_idle_update = now
                queued = storage.queue_count()
                status = ("Sync pending: %d" % queued) if queued else (
                    "Online" if wsclient.is_connected() else "Offline")
                display.idle(rtc.get_time_string(), status)
        elif dispenser.state == dispenser.STATE_GATE_LOCKED:
            display.gate_locked()

        await asyncio.sleep_ms(100)


async def _ws_supervisor():
    """WebSocket connect/listen/reconnect loop - command channel ki jaan."""
    while True:
        if wlan.isconnected():
            if await wsclient.connect():
                await wsclient.listen(handle_command)
                print("[WS] Disconnected - %dms mein retry" % config.WS_RECONNECT_MS)
        await asyncio.sleep_ms(config.WS_RECONNECT_MS)


async def _ws_ping_task():
    while True:
        await asyncio.sleep_ms(config.WS_PING_MS)
        await wsclient.send_ping()


async def _network_task():
    """
    Heartbeat + config reconciliation + offline queue flush + safety-net poll.
    Heartbeat hi batata hai ki bundle stale hai ya nahi - isliye periodic
    schedule poll bilkul nahi hai.
    """
    last_command_poll = time.ticks_ms()

    while True:
        if not wlan.isconnected():
            print("[WiFi] Lost - reconnect try kar rahe hain (dosing RTC se chalta rahega)")
            wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
            await asyncio.sleep_ms(config.WIFI_RECONNECT_MS)
            continue

        bundle = storage.load_schedule()
        battery = _battery_percent()

        data = api.heartbeat(
            battery=battery,
            rssi=wlan.status("rssi") if hasattr(wlan, "status") else 0,
            uptime_s=time.ticks_ms() // 1000,
            schedule_version=bundle.get("schedule_version", 0),
            state_name=dispenser.state,
            compartment=stepper.current_compartment,
        )

        if data:
            if data.get("config_stale"):
                print("[HB] Config stale - bundle fetch")
                api.fetch_config()

            if data.get("pending_commands", 0) > 0 and not wsclient.is_connected():
                for cmd in api.poll_commands():
                    await handle_command(cmd.get("type", ""), cmd.get("command_id", ""),
                                        cmd.get("payload") or {})

            drift = data.get("rtc_drift_seconds") or 0
            if abs(drift) > 30:
                print("[HB] RTC drift %ds - resync" % drift)
                sync_time()

            if data.get("gate_locked") and not dispenser.is_gate_locked():
                dispenser.lock_gate("backend reported locked")
            elif data.get("gate_locked") is False and dispenser.is_gate_locked():
                dispenser.unlock_gate()

        print("[HB] battery=%d%% queued=%d ws=%d" %
              (battery, storage.queue_count(), 1 if wsclient.is_connected() else 0))

        if battery < 15:
            api.emit_low_battery(battery)

        # Safety-net poll - sirf socket down hone par
        now = time.ticks_ms()
        if time.ticks_diff(now, last_command_poll) >= config.COMMAND_POLL_MS:
            last_command_poll = now
            if not wsclient.is_connected():
                for cmd in api.poll_commands():
                    await handle_command(cmd.get("type", ""), cmd.get("command_id", ""),
                                        cmd.get("payload") or {})

        await asyncio.sleep_ms(config.HEARTBEAT_INTERVAL_MS)


async def _flush_task():
    while True:
        await asyncio.sleep_ms(config.EVENT_FLUSH_MS)
        if wlan.isconnected():
            await api.flush_queue()


def _battery_percent():
    try:
        from machine import ADC, Pin
        adc = ADC(Pin(config.BATTERY_PIN))
        adc.atten(ADC.ATTN_11DB)
        raw = adc.read()
        pct = (raw - config.BATTERY_RAW_MIN) * 100 // (
            config.BATTERY_RAW_MAX - config.BATTERY_RAW_MIN)
        return max(0, min(100, pct))
    except Exception:
        return 100


# ── Boot ─────────────────────────────────────────────────────
async def _main():
    print("\n[BOOT] MedAdhere Pill Dispenser v" + config.FIRMWARE_VERSION)
    print("[BOOT] Device ID:", config.DEVICE_ID)

    rtc.init()
    display.init()
    audio.init()
    stepper.init()
    servo.init()
    ultrasonic.init()
    have_loadcell = loadcell.init()
    hall_sensor.init()   # Hall pin wired hai - dispenser isse hamesha home karega

    dispenser.init(
        load_cell_module=loadcell if have_loadcell else None,
        hall_module=hall_sensor,
    )

    # Cache PEHLE load karo - WiFi na milne par bhi RTC + cache se chal sake.
    scheduler.describe()

    await dispenser.home()

    wifi_ok = connect_wifi()
    if wifi_ok:
        sync_time()
        api.fetch_config()

    # WiFi na ho to bhi emit() event ko flash queue mein daal deta hai -
    # WiFi aane par flush ho jaayega.
    api.emit("DEVICE_BOOT", {
        "battery_level": _battery_percent(),
        "firmware_version": config.FIRMWARE_VERSION,
    })

    print("[BOOT] %d-compartment dispenser ready" % config.TOTAL_COMPARTMENTS)

    tasks = [
        asyncio.create_task(_scheduler_task()),
        asyncio.create_task(_dispenser_task()),
        asyncio.create_task(_network_task()),
        asyncio.create_task(_flush_task()),
    ]
    if wifi_ok:
        tasks.append(asyncio.create_task(_ws_supervisor()))
        tasks.append(asyncio.create_task(_ws_ping_task()))

    print("[BOOT] Saare background tasks chalu")
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        print("\n[BOOT] Rok diya gaya")
