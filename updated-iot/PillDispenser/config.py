# ============================================================
# SMART PILL DISPENSER
# CONFIGURATION
# ============================================================


# ============================================================
# WIFI CONFIGURATION
# ============================================================

WIFI_SSID = "YOUR_WIFI_NAME"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"
WIFI_TIMEOUT_SECONDS = 15


# ============================================================
# BACKEND & DEVICE CREDENTIALS
# ============================================================

BACKEND_HOST = "10.98.188.253"
BACKEND_PORT = 8000
BACKEND_URL = "http://%s:%d" % (BACKEND_HOST, BACKEND_PORT)

DEVICE_ID = "e214a30b-c919-4d23-b3f1-80557b756cdd"
DEVICE_API_KEY = "GBfHHm3ZSwEo1MkzZSBTGrgWzXZeudFH7p2h4kbmhferTrfflRCdxyftuEF_nPvr"

API_EVENTS = "/api/v1/iot/events/"
API_HEARTBEAT = "/api/v1/iot/heartbeat/"
API_SYNC_TIME = "/api/v1/iot/sync/time/"
API_CONFIG = "/api/v1/iot/devices/%s/config/" % DEVICE_ID

FIRMWARE_VERSION = "3.2.0-mqtt"
HEARTBEAT_INTERVAL_SECONDS = 300   # 5 minutes
CONFIG_SYNC_INTERVAL_SECONDS = 1800  # 30 minutes


# ============================================================
# MQTT BROKER CONFIGURATION
# ============================================================

# Cloud Broker (HiveMQ Public - Port 1883)
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_CLIENT_ID = "esp32_dispenser_%s" % DEVICE_ID[:8]
MQTT_USER = None
MQTT_PASSWORD = None

# Pub/Sub Topics
MQTT_TOPIC_EVENTS = "medadhere/%s/events" % DEVICE_ID
MQTT_TOPIC_HEARTBEAT = "medadhere/%s/heartbeat" % DEVICE_ID
MQTT_TOPIC_COMMANDS = "medadhere/%s/commands" % DEVICE_ID


# ============================================================
# RTC - DS3231
# ============================================================

RTC_SDA = 23
RTC_SCL = 22
RTC_ADDRESS = 0x68


# ============================================================
# HALL EFFECT SENSOR
# ============================================================

HALL_PIN = 33


# ============================================================
# STEPPER MOTOR - 28BYJ-48
# ============================================================

IN1 = 13
IN2 = 14
IN3 = 27
IN4 = 26


# ============================================================
# STEPPER SETTINGS
# ============================================================

TOTAL_COMPARTMENTS = 4

# 1 compartment = intended 90°
STEPS_PER_COMPARTMENT = 1024

STEP_DELAY = 0.003


# ============================================================
# SERVO - SG90
# ============================================================

SERVO_PIN = 25

SERVO_CLOSED_ANGLE = 0
SERVO_OPEN_ANGLE = 90


# ============================================================
# ULTRASONIC
# ============================================================

ULTRASONIC_TRIG = 19
ULTRASONIC_ECHO = 18

# Hand detection distance in cm
HAND_DISTANCE = 15


# ============================================================
# DISPENSING WINDOW
# ============================================================

# After scheduled time, ultrasonic + servo
# remain active for this duration.
DISPENSING_WINDOW_MINUTES = 3