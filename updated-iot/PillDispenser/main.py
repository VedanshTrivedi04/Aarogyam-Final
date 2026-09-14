import time

from config import (
    HEARTBEAT_INTERVAL_SECONDS,
    CONFIG_SYNC_INTERVAL_SECONDS
)

from rtc import check_rtc, rtc
from wifi import connect_wifi, is_connected
from hall_sensor import find_home
from servo import close_servo
from scheduler import get_due_schedules
from dispenser import dispense
import api
import mqtt_client


# ============================================================
# MQTT REMOTE COMMAND HANDLER
# ============================================================

def handle_remote_command(topic, payload):
    """
    Handles real-time commands received from MQTT broker.
    Example: {"command_type": "DISPENSE_NOW", "compartment": 2, "medicine": "Aspirin"}
    """
    cmd_type = payload.get("command_type") or payload.get("type")
    comp = payload.get("compartment") or payload.get("compartment_num", 1)
    med = payload.get("medicine", "Manual Remote Dose")
    dose = payload.get("dose", 1)

    print()
    print("==========================================")
    print(">>> MQTT REMOTE COMMAND RECEIVED: %s <<<" % cmd_type)
    print("==========================================")

    if cmd_type in ("DISPENSE_NOW", "TAKE_MEDICINE_NOW", "OPEN_GATE"):
        print("[MQTT] Triggering remote dispense for Compartment %s..." % comp)
        api.send_event("DOSE_STARTED", compartment=comp, extra={"source": "MQTT_REMOTE"})
        res = dispense(compartment=int(comp), medicine=med, dose=dose)

        if res == "TAKEN":
            api.send_event("DOSE_TAKEN", compartment=comp, extra={"source": "MQTT_REMOTE"})
        elif res == "MISSED":
            api.send_event("DOSE_MISSED", compartment=comp, extra={"source": "MQTT_REMOTE"})

    elif cmd_type in ("SYNC_CONFIG", "SYNC_SCHEDULE"):
        print("[MQTT] Refreshing schedules from backend...")
        api.fetch_schedules_from_backend()

    else:
        print("[MQTT] Unhandled command type:", cmd_type)


# ============================================================
# SYSTEM START
# ============================================================

print()
print("==========================================")
print("       SMART PILL DISPENSER")
print("       HARDWARE + MQTT INTEGRATION")
print("==========================================")


# ============================================================
# RTC INITIALIZATION
# ============================================================

print()
print("Checking RTC...")

if not check_rtc():
    print("RTC FAILED")
    while True:
        time.sleep(1)


# ============================================================
# WIFI & MQTT SYNC
# ============================================================

wifi_ok = connect_wifi()

if wifi_ok:
    # 1. Sync RTC from Backend Server Time (IST)
    api.sync_time_from_backend()

    # 2. Fetch latest schedules from Backend
    api.fetch_schedules_from_backend()

    # 3. Connect to MQTT Broker & Register command handler
    mqtt_client.set_command_callback(handle_remote_command)
    mqtt_client.connect_mqtt()

    # 4. Report boot event to Backend via MQTT
    api.send_event("DEVICE_BOOT")

    # 5. Flush any offline events from earlier
    api.flush_offline_events()
else:
    print("[SYSTEM] Starting in OFFLINE mode using local schedules.json and DS3231 RTC.")


# ============================================================
# HOME CALIBRATION (HALL SENSOR)
# ============================================================

print()
print("Finding HOME...")
find_home()


# ============================================================
# SERVO INITIAL STATE
# ============================================================

close_servo()


# ============================================================
# SYSTEM READY SUMMARY
# ============================================================

print()
print("==========================================")
print("SYSTEM READY")
print("==========================================")
print("RTC        : READY")
print("Hall       : READY")
print("Stepper    : READY")
print("Servo      : READY")
print("Ultrasonic : STANDBY")
print("WiFi       : %s" % ("CONNECTED" if is_connected() else "OFFLINE"))
print("MQTT       : %s" % ("CONNECTED" if mqtt_client.is_mqtt_connected() else "OFFLINE"))
print("Backend    : ONLINE")
print("==========================================")


# ============================================================
# PREVENT SAME SCHEDULE FROM REPEATING
# ============================================================

executed_today = {}
last_heartbeat_time = time.time()
last_config_sync_time = time.time()
last_minute_reported = -1


# ============================================================
# MAIN LOOP
# ============================================================

while True:

    try:
        # Check for incoming real-time MQTT commands (non-blocking)
        mqtt_client.check_messages()

        now = rtc.now()
        current_minute = now[4]

        # Only print time on new minute
        if current_minute != last_minute_reported:
            last_minute_reported = current_minute
            print()
            print("RTC: {:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
                now[0], now[1], now[2], now[3], now[4], now[5]
            ))

        # Check for due schedules
        due_schedules = get_due_schedules()

        for schedule in due_schedules:
            schedule_id = schedule.get("schedule_id")
            compartment = schedule.get("compartment")
            medicine = schedule.get("medicine", "Unknown")
            dose = schedule.get("dose", 1)

            date_key = "{}-{}-{}-{}".format(
                now[0], now[1], now[2], schedule_id
            )

            # Prevent multiple executions during the same minute
            if executed_today.get(date_key):
                continue

            executed_today[date_key] = True

            print()
            print("==========================================")
            print(">>> SCHEDULE DUE FOR COMPARTMENT %s <<<" % compartment)
            print("Medicine:", medicine, "| Dose:", dose)
            print("==========================================")

            # Report DOSE_STARTED via MQTT
            api.send_event("DOSE_STARTED", compartment=compartment, extra={
                "medicine": medicine,
                "dose": dose,
                "schedule_id": schedule_id
            })

            # Execute physical dispensing using original sensor sequence
            result = dispense(
                compartment=compartment,
                medicine=medicine,
                dose=dose
            )

            # Report outcome via MQTT
            if result == "TAKEN":
                api.send_event("DOSE_TAKEN", compartment=compartment, extra={
                    "medicine": medicine,
                    "dose": dose,
                    "schedule_id": schedule_id
                })
            elif result == "MISSED":
                api.send_event("DOSE_MISSED", compartment=compartment, extra={
                    "medicine": medicine,
                    "dose": dose,
                    "schedule_id": schedule_id
                })

        # Periodic Heartbeat
        current_time_sec = time.time()
        if current_time_sec - last_heartbeat_time >= HEARTBEAT_INTERVAL_SECONDS:
            last_heartbeat_time = current_time_sec
            if is_connected() and not mqtt_client.is_mqtt_connected():
                mqtt_client.connect_mqtt()

            api.send_heartbeat()
            api.flush_offline_events()

        # Periodic Schedule Refresh from backend
        if current_time_sec - last_config_sync_time >= CONFIG_SYNC_INTERVAL_SECONDS:
            last_config_sync_time = current_time_sec
            if is_connected():
                api.fetch_schedules_from_backend()

    except Exception as e:
        print("MAIN ERROR:", e)

    time.sleep(0.5)