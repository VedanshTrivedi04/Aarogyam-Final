"""
main.py - Direct MicroPython port of PillDispenser.ino.
Same pins, same fill-mode/dispense logic, same HTTP backend contract.
Runs automatically on boot (MicroPython convention).
"""
import time
import network

import config
import rtc_ds3231 as rtc
import stepper
import hall_sensor
import servo_gate as servo
import ultrasonic
import api_client as api
from dispenser import dispense

# ============================================================
# STATE TRACKING
# ============================================================
last_reported_minute = -1
last_executed_minute = -1
last_heartbeat_time = 0
last_config_sync_time = 0
last_command_poll_time = 0
fill_mode_active = False


# ============================================================
# REMOTE COMMAND HANDLER (commands arrive via HTTP polling)
# ============================================================
def handle_remote_command(cmd_type, payload_json):
    global fill_mode_active

    cmd = cmd_type or ""
    pj = payload_json or ""

    comp = 1
    # Check if compartment specified in the command payload.
    # The caregiver app's fill-mode UI sends "compartment_number" (PREPARE_COMPARTMENT),
    # while dispense-trigger commands send "compartment" - check both.
    cn_idx = pj.find('"compartment_number":')
    if cn_idx >= 0:
        comp = api.to_int(pj[cn_idx + 21:cn_idx + 23])
    else:
        c_idx = pj.find('"compartment":')
        if c_idx >= 0:
            comp = api.to_int(pj[c_idx + 14:c_idx + 16])
    if comp < 1 or comp > config.TOTAL_COMPARTMENTS:
        comp = 1

    if "START_FILL_MODE" in cmd or "NEXT_COMPARTMENT" in cmd or "PREPARE_COMPARTMENT" in cmd:
        # Caregiver app sends PREPARE_COMPARTMENT for both the first slot and
        # every subsequent one, so always close-rotate-open: harmless if the
        # lid is already closed, and correct whichever step this is.
        print("[FILL] Preparing Compartment {} for filling...".format(comp))
        fill_mode_active = True
        servo.close_servo()
        time.sleep_ms(500)  # let the gate physically settle before rotating
        stepper.rotate_to_compartment(comp)
        servo.open_servo()

    elif "END_FILL_MODE" in cmd:
        print("[FILL] Fill mode ended. Closing lid, resuming normal schedule...")
        servo.close_servo()
        fill_mode_active = False

    elif ("DISPENSE_NOW" in cmd or "TAKE_MEDICINE_NOW" in cmd or "OPEN_GATE" in cmd
          or "TRIGGER_DOSE" in cmd or "FORCE_OPEN_LID" in cmd):
        if fill_mode_active:
            print("[CMD] Ignored - fill mode is active.")
            return

        print("[CMD] Triggering remote dispense for Compartment {}...".format(comp))
        api.publish_event("DOSE_STARTED", comp, "Remote Dose", 1)

        result = dispense(comp, "Remote Dose", 1)

        if result == "TAKEN":
            api.publish_event("DOSE_TAKEN", comp, "Remote Dose", 1)
        elif result == "MISSED":
            api.publish_event("DOSE_MISSED", comp, "Remote Dose", 1)

    elif "SYNC_CONFIG" in cmd or "SYNC_SCHEDULE" in cmd:
        print("[CMD] Refreshing schedules from backend...")
        api.fetch_schedules_from_backend()

    else:
        print("[CMD] Command received and acknowledged.")


api.handle_remote_command = handle_remote_command


# ============================================================
# SYSTEM SETUP
# ============================================================
def setup():
    global last_heartbeat_time

    print()
    print("==========================================")
    print("       SMART PILL DISPENSER (MICROPYTHON)")
    print("       HARDWARE + HTTP INTEGRATION")
    print("==========================================")

    # 1. Initialize Hardware Pins
    stepper.init_stepper()
    hall_sensor.init_hall_sensor()
    servo.init_servo()
    ultrasonic.init_ultrasonic()

    # 2. Check RTC DS3231
    print()
    print("Checking RTC...")
    if not rtc.check_rtc():
        print("RTC FAILED! System halting.")
        while True:
            time.sleep_ms(1000)

    # 3. Connect to WiFi
    print()
    print("[WIFI] Connecting to:", config.WIFI_SSID)
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)

    wifi_start = time.ticks_ms()
    while not wlan.isconnected() and time.ticks_diff(time.ticks_ms(), wifi_start) < config.WIFI_TIMEOUT_MS:
        time.sleep_ms(500)
        print(".", end="")

    if wlan.isconnected():
        print()
        print("[WIFI] Connected successfully!")
        print("[WIFI] IP Address:", wlan.ifconfig()[0])

        # Sync Time from Backend (IST)
        api.sync_time_from_backend()

        # Download doctor/caregiver schedules from Backend
        api.fetch_schedules_from_backend()

        # Report DEVICE_BOOT
        api.publish_event("DEVICE_BOOT", 1)

        # Send an immediate heartbeat so the dashboard shows ONLINE right away
        # (last_seen_at on the backend is only updated by /heartbeat/, and the
        # periodic timer below would otherwise wait a full HEARTBEAT_INTERVAL_MS).
        api.publish_heartbeat("ok", "ok", "ok")
        last_heartbeat_time = time.ticks_ms()
    else:
        print()
        print("[WIFI] Connection timeout. Running in OFFLINE mode using RTC & local schedules.")

    # 4. Calibrate Home Position using Hall Sensor
    print()
    print("Finding HOME...")
    hall_sensor.find_home()

    # 5. Initial Servo Gate State
    servo.close_servo()

    # 6. System Ready Summary
    print()
    print("==========================================")
    print("SYSTEM READY")
    print("==========================================")
    print("RTC        : READY")
    print("Hall       : READY")
    print("Stepper    : READY")
    print("Servo      : READY")
    print("Ultrasonic : STANDBY")
    print("WiFi       :", "CONNECTED" if wlan.isconnected() else "OFFLINE")
    print("Backend    : ONLINE (HTTP)")
    print("==========================================")


# ============================================================
# MAIN LOOP
# ============================================================
def loop():
    global last_reported_minute, last_executed_minute
    global last_heartbeat_time, last_config_sync_time, last_command_poll_time

    wlan = network.WLAN(network.STA_IF)

    while True:
        # 1. Poll backend for remote commands (dispense-now, sync, etc.)
        if time.ticks_diff(time.ticks_ms(), last_command_poll_time) >= config.COMMAND_POLL_INTERVAL_MS:
            last_command_poll_time = time.ticks_ms()
            if wlan.isconnected():
                api.poll_device_commands()

        # 2. Read Current Time from DS3231 RTC
        now = rtc.read_rtc()

        # Print time at the start of each new minute
        if now.minute != last_reported_minute:
            last_reported_minute = now.minute
            print("\nRTC: {:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
                now.year, now.month, now.day, now.hour, now.minute, now.second))

        # 3. Format current time as "HH:MM"
        current_time_str = "{:02d}:{:02d}".format(now.hour, now.minute)

        # 4. Check for Due Schedules (paused while a caregiver fill session is active)
        if not fill_mode_active and now.minute != last_executed_minute:
            for entry in api.schedules:
                if entry["enabled"] and entry["time"] == current_time_str:
                    last_executed_minute = now.minute

                    comp = entry["compartment"]
                    med = entry["medicine"]
                    dose = entry["dose"]

                    print()
                    print("==========================================")
                    print(">>> SCHEDULE DUE FOR COMPARTMENT {} <<<".format(comp))
                    print("Medicine: {} | Dose: {}".format(med, dose))
                    print("==========================================")

                    # Publish DOSE_STARTED
                    api.publish_event("DOSE_STARTED", comp, med, dose)

                    # Execute physical dispensing (preserves original sensor sequence)
                    outcome = dispense(comp, med, dose)

                    # Publish outcome
                    if outcome == "TAKEN":
                        api.publish_event("DOSE_TAKEN", comp, med, dose)
                    elif outcome == "MISSED":
                        api.publish_event("DOSE_MISSED", comp, med, dose)
                    break  # One compartment per minute

        # 5. Periodic Heartbeat (Every 5 minutes)
        if time.ticks_diff(time.ticks_ms(), last_heartbeat_time) >= config.HEARTBEAT_INTERVAL_MS:
            last_heartbeat_time = time.ticks_ms()
            api.publish_heartbeat("ok", "ok", "ok")

        # 6. Periodic Schedule Refresh (Every 30 minutes)
        if time.ticks_diff(time.ticks_ms(), last_config_sync_time) >= config.CONFIG_SYNC_INTERVAL_MS:
            last_config_sync_time = time.ticks_ms()
            if wlan.isconnected():
                api.fetch_schedules_from_backend()

        time.sleep_ms(100)


setup()
loop()
