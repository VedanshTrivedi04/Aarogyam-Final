# ============================================================
# SMART PILL DISPENSER - CONFIGURATION (MICROPYTHON)
# Direct port of config.h - same values, same pins.
# ============================================================

# ============================================================
# WIFI CONFIGURATION
# ============================================================
WIFI_SSID = "YOUR_WIFI_NAME"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"
WIFI_TIMEOUT_MS = 15000

# ============================================================
# BACKEND & DEVICE CREDENTIALS
# ============================================================
BACKEND_HOST = "aarogyam-backend-ptty.onrender.com"
BACKEND_PORT = 443
BACKEND_URL = "https://aarogyam-backend-ptty.onrender.com"

DEVICE_ID = "e214a30b-c919-4d23-b3f1-80557b756cdd"
DEVICE_API_KEY = "GBfHHm3ZSwEo1MkzZSBTGrgWzXZeudFH7p2h4kbmhferTrfflRCdxyftuEF_nPvr"

API_EVENTS = "/api/v1/iot/events/"
API_HEARTBEAT = "/api/v1/iot/heartbeat/"
API_SYNC_TIME = "/api/v1/iot/sync/time/"
API_CONFIG = "/api/v1/iot/devices/e214a30b-c919-4d23-b3f1-80557b756cdd/config/"
API_COMMANDS = "/api/v1/iot/devices/e214a30b-c919-4d23-b3f1-80557b756cdd/commands/"

FIRMWARE_VERSION = "3.2.0-mpy"
HEARTBEAT_INTERVAL_MS = 300000        # 5 minutes
CONFIG_SYNC_INTERVAL_MS = 1800000     # 30 minutes
COMMAND_POLL_INTERVAL_MS = 15000      # 15 seconds - HTTP poll for remote commands

# ============================================================
# RTC - DS3231 (I2C)
# ============================================================
RTC_SDA = 23
RTC_SCL = 22
RTC_ADDRESS = 0x68

# ============================================================
# HALL EFFECT SENSOR (HOME POSITION)
# ============================================================
HALL_PIN = 33

# ============================================================
# STEPPER MOTOR - 28BYJ-48 (ULN2003)
# ============================================================
STEPPER_IN1 = 13
STEPPER_IN2 = 14
STEPPER_IN3 = 27
STEPPER_IN4 = 26

TOTAL_COMPARTMENTS = 4
STEPS_PER_COMPARTMENT = 1024   # 90 degrees rotation
STEP_DELAY_MS = 3

# ============================================================
# SERVO - SG90 (DISPENSER LID)
# ============================================================
SERVO_PIN = 25
SERVO_CLOSED_ANGLE = 0
SERVO_OPEN_ANGLE = 90

# ============================================================
# ULTRASONIC SENSOR - HC-SR04
# ============================================================
ULTRASONIC_TRIG = 19
ULTRASONIC_ECHO = 18
HAND_DISTANCE_CM = 15     # Hand detection distance

# ============================================================
# DISPENSING WINDOW
# ============================================================
DISPENSING_WINDOW_MINUTES = 3
