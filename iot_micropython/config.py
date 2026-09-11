"""
config.py - GPIO pins aur hardware settings.

Pin map C++ firmware (iot file/config.h) se exactly match karta hai, sirf
HALL_PIN naya hai.

Timing contract: device apna dose khud RTC se fire karta hai. Backend sirf
schedule bundle bhejta hai, "abhi dose hai kya" nahi poocha jaata.
"""

# ── WiFi ────────────────────────────────────────────────────
WIFI_SSID = "YOUR_WIFI_NAME"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"
WIFI_RECONNECT_MS = 15000
WIFI_CONNECT_TIMEOUT_S = 15

# ── Backend ─────────────────────────────────────────────────
# WebSocket ko host aur port alag chahiye, isliye BACKEND_URL inhi se banta hai.
BACKEND_HOST = "10.98.188.253"
BACKEND_PORT = 8000
BACKEND_URL = "http://%s:%d" % (BACKEND_HOST, BACKEND_PORT)

DEVICE_ID = "e214a30b-c919-4d23-b3f1-80557b756cdd"
DEVICE_API_KEY = "GBfHHm3ZSwEo1MkzZSBTGrgWzXZeudFH7p2h4kbmhferTrfflRCdxyftuEF_nPvr"

# ── API Endpoints ───────────────────────────────────────────
API_EVENTS = "/api/v1/iot/events/"
API_EVENT_BATCH = "/api/v1/iot/events/batch/"
API_HEARTBEAT = "/api/v1/iot/heartbeat/"
API_COMMANDS = "/api/v1/iot/devices/%s/commands/" % DEVICE_ID
API_SYNC_TIME = "/api/v1/iot/sync/time/"
API_CONFIG = "/api/v1/iot/devices/%s/config/" % DEVICE_ID
API_FILL_MEASURE = "/api/v1/iot/devices/%s/fill/measure/" % DEVICE_ID

# WebSocket command channel. ESP32 handshake mein custom header nahi bhej
# sakta, isliye device_key query param mein jaata hai.
WS_PATH = "/ws/iot/device/%s/?device_key=%s" % (DEVICE_ID, DEVICE_API_KEY)
WS_RECONNECT_MS = 10000
WS_PING_MS = 30000

# ── Timing ──────────────────────────────────────────────────
HEARTBEAT_INTERVAL_MS = 600000   # 10 min
COMMAND_POLL_MS = 300000         # 5 min - sirf safety net, socket down ho tab
EVENT_FLUSH_MS = 60000           # offline queue retry
SCHEDULER_TICK_MS = 1000         # RTC slot check
GATE_CLOSE_CONFIRM_MS = 3000     # lid band hone ke baad settle
WEIGHT_SETTLE_MS = 1500          # rotation ke baad baseline read se pehle
HAND_DETECT_DIST_CM = 15

# ── Scheduling policy defaults ──────────────────────────────
# Backend bundle ke `policy` block se override ho jaate hain.
DEFAULT_DOSE_WINDOW_MIN = 60      # gate itni der available rehta hai
DEFAULT_CATCHUP_WINDOW_MIN = 30   # power off ke dauraan chhoota slot itni der tak fire hoga
MAX_GATE_OPENS = 4

# ── 28BYJ-48 Stepper (ULN2003) ──────────────────────────────
STEPPER_IN1 = 13
STEPPER_IN2 = 12
STEPPER_IN3 = 14
STEPPER_IN4 = 27
STEP_DELAY_MS = 2

# ── Servo (SG90) - Gate ─────────────────────────────────────
SERVO_PIN = 25
SERVO_OPEN_DEG = 90
SERVO_CLOSE_DEG = 0

# ── HC-SR04 Ultrasonic ──────────────────────────────────────
ULTRASONIC_TRIG = 26
ULTRASONIC_ECHO = 33

# ── HX711 Load Cell (1 kg) ──────────────────────────────────
# Ek hi load cell poore carousel ke neeche hai, isliye reading hamesha TOTAL
# weight hai - kisi ek compartment ki nahi. Backend running reference se
# subtract karke per-compartment weight nikalta hai.
LOADCELL_DOUT = 35   # GPIO35 input-only - DOUT hi yahan lagega
LOADCELL_SCK = 18
LOADCELL_SCALE = 2280.0   # known weight rakhkar calibrate karo

# ── Hall Effect Sensor - HOME position ──────────────────────
# Naya (C++ firmware mein nahi tha). Boot par HOME dhoondhne se power cut ke
# baad position drift theek ho jaata hai.
# GPIO 19 chuna kyunki internal pull-up support karta hai - GPIO 34/36/39
# input-only hain aur unmein pull-up nahi hota, jo open-collector hall sensor
# (A3144) ke liye zaroori hai.
HALL_PIN = 19
HALL_ACTIVE_LOW = True     # A3144 magnet ke paas LOW jaata hai
HALL_SEARCH_MAX_STEPS = 4200   # ek poore revolution se thoda zyada

# ── DFPlayer Mini MP3 ───────────────────────────────────────
DFPLAYER_UART = 2
DFPLAYER_RX = 16     # ESP32 receives from DFPlayer TX
DFPLAYER_TX = 17     # ESP32 transmits to DFPlayer RX
DFPLAYER_BUSY = 15   # LOW = playing
DFPLAYER_VOLUME = 25

# SD card par MP3 files ka naam:
#   0001.mp3 - "Dawai lene ka waqt ho gaya"
#   0002.mp3 - "Apni dawai nikaalo"
#   0003.mp3 - "Shukriya, dawai le li gayi"
#   0004.mp3 - "Dawai nahi li, caregiver ko alert kiya"
#   0005.mp3 - "Dispenser unlock ho gaya"
AUDIO_DOSE_REMINDER = 1
AUDIO_TAKE_MEDICINE = 2
AUDIO_DOSE_TAKEN = 3
AUDIO_DOSE_MISSED = 4
AUDIO_CAREGIVER_UNLOCK = 5

# ── SSD1306 OLED (I2C) ──────────────────────────────────────
OLED_SDA = 21
OLED_SCL = 22
OLED_WIDTH = 128
OLED_HEIGHT = 64
OLED_ADDR = 0x3C

# ── DS3231 RTC (I2C, OLED ke saath bus share karta hai) ─────
RTC_ADDR = 0x68

# ── Buzzer, LED, Battery ────────────────────────────────────
BUZZER_PIN = 32
LED_PIN = 2
BATTERY_PIN = 34
BATTERY_RAW_MIN = 1800
BATTERY_RAW_MAX = 4095

# ── Dispenser ───────────────────────────────────────────────
TOTAL_COMPARTMENTS = 4
STEPS_PER_SLOT = 1024     # 28BYJ-48: 4096 half-steps/rev / 4 slots

# ── Storage files ───────────────────────────────────────────
SCHEDULES_FILE = "schedules.json"    # backend bundle ka local cache
EVENT_QUEUE_FILE = "event_queue.json"
STATE_FILE = "device_state.json"
EVENT_QUEUE_CAPACITY = 24

FIRMWARE_VERSION = "3.0.0-mpy"
