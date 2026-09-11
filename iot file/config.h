// ============================================================
// config.h — MedAdhere ESP32 Configuration
// Stepper : 28BYJ-48 5V + ULN2003 Driver
// Load cell: 1 kg HX711
// Speaker  : DFPlayer Mini MP3 (5 pre-loaded audio tracks)
// Gate     : SG90 Servo
// Sensor   : HC-SR04 Ultrasonic
// Display  : SSD1306 OLED 128×64 (I2C)
// RTC      : DS3231 (I2C, shares bus with OLED)
// ============================================================
#pragma once

// ── WiFi ────────────────────────────────────────────────────
#define WIFI_SSID          "YOUR_WIFI_NAME"
#define WIFI_PASSWORD      "YOUR_WIFI_PASSWORD"
#define WIFI_RECONNECT_MS  15000

// ── Backend ─────────────────────────────────────────────────
#define BACKEND_HOST      "10.98.188.253"
#define BACKEND_PORT      8000
#define BACKEND_URL       "http://" BACKEND_HOST ":8000"
#define DEVICE_API_KEY    "GBfHHm3ZSwEo1MkzZSBTGrgWzXZeudFH7p2h4kbmhferTrfflRCdxyftuEF_nPvr"
#define DEVICE_ID         "e214a30b-c919-4d23-b3f1-80557b756cdd"

// ── API Endpoints ────────────────────────────────────────────
// All device events go through a single standard endpoint (idempotent)
#define API_EVENTS      "/api/v1/iot/events/"
#define API_EVENT_BATCH "/api/v1/iot/events/batch/"
#define API_HEARTBEAT   "/api/v1/iot/heartbeat/"
#define API_COMMANDS    "/api/v1/iot/devices/" DEVICE_ID "/commands/"
#define API_SYNC_TIME   "/api/v1/iot/sync/time/"
#define API_CONFIG      "/api/v1/iot/devices/" DEVICE_ID "/config/"
#define API_FILL_MEASURE "/api/v1/iot/devices/" DEVICE_ID "/fill/measure/"

// ── WebSocket command channel ───────────────────────────────
// Commands are pushed over this socket. The HTTP command poll below is only
// a safety net for a dropped socket — it is NOT the primary path.
#define WS_PATH  "/ws/iot/device/" DEVICE_ID "/?device_key=" DEVICE_API_KEY
#define WS_RECONNECT_MS  10000

// ── Timing ──────────────────────────────────────────────────
// The device schedules its own doses from the RTC, so there is no schedule
// poll at all. The heartbeat doubles as the config-reconciliation channel.
#define HEARTBEAT_INTERVAL_MS    600000   // 10 min
#define COMMAND_POLL_MS          300000   // 5 min — safety net only
#define EVENT_FLUSH_MS            60000   // retry the offline event queue
#define SCHEDULER_TICK_MS          1000   // RTC slot check
#define HAND_DETECT_DIST_CM          15   // cm threshold for ultrasonic
#define GATE_CLOSE_CONFIRM_MS      3000   // wait 3 s after lid close before weight read
#define WEIGHT_SETTLE_MS           1500   // wait after rotation before baseline read
#define DOSE_TIMEOUT_MS         3600000   // 1 hour — matches backend window

// ── Scheduling policy defaults ──────────────────────────────
// Overridden by the `policy` block in the backend config bundle.
#define DEFAULT_DOSE_WINDOW_MIN      60   // gate stays available this long
#define DEFAULT_CATCHUP_WINDOW_MIN   30   // fire a slot missed while powered off

// ── 28BYJ-48 Stepper (ULN2003) ──────────────────────────────
#define STEPPER_IN1   13
#define STEPPER_IN2   12
#define STEPPER_IN3   14
#define STEPPER_IN4   27

// ── Servo (SG90 / MG90S) — Gate ─────────────────────────────
#define SERVO_PIN        25
#define SERVO_OPEN_DEG   90
#define SERVO_CLOSE_DEG   0

// ── HC-SR04 Ultrasonic ───────────────────────────────────────
#define ULTRASONIC_TRIG  26
#define ULTRASONIC_ECHO  33

// ── HX711 Load Cell (1 kg) ───────────────────────────────────
#define LOADCELL_DOUT    35   // GPIO35 (input-only)
#define LOADCELL_SCK     18
// Calibration: put a known weight (e.g. 100 g) on the scale,
// then adjust LOADCELL_SCALE until hw_getWeightGrams() reads correctly.
#define LOADCELL_SCALE   2280.0f

// ── DFPlayer Mini MP3 ────────────────────────────────────────
// Connect DFPlayer TX → ESP32 GPIO16 (RX2)
//         DFPlayer RX → ESP32 GPIO17 (TX2)  via 1kΩ resistor
//         DFPlayer BUSY → ESP32 GPIO15 (optional, LOW = playing)
// Speaker: 8 Ω / 3 W recommended
#define DFPLAYER_RX      16   // ESP32 receives from DFPlayer TX
#define DFPLAYER_TX      17   // ESP32 transmits to DFPlayer RX
#define DFPLAYER_BUSY    15   // LOW when DFPlayer is playing (optional)
#define DFPLAYER_VOLUME  25   // 0 – 30

// ── Audio Track Mapping ──────────────────────────────────────
// Rename your MP3 files on the SD card to:
//   0001.mp3 — Dose reminder  : "Dawai lene ka waqt ho gaya"
//   0002.mp3 — Take medicine  : "Apni dawai nikaalo"
//   0003.mp3 — Dose taken     : "Shukriya, dawai le li gayi"
//   0004.mp3 — Missed / lock  : "Dawai nahi li, caregiver ko alert kiya"
//   0005.mp3 — Caregiver unlock: "Dispenser unlock ho gaya"
#define AUDIO_DOSE_REMINDER    1
#define AUDIO_TAKE_MEDICINE    2
#define AUDIO_DOSE_TAKEN       3
#define AUDIO_DOSE_MISSED      4
#define AUDIO_CAREGIVER_UNLOCK 5

// ── SSD1306 OLED (I2C) ──────────────────────────────────────
#define OLED_SDA    21
#define OLED_SCL    22
#define OLED_WIDTH  128
#define OLED_HEIGHT  64

// ── Buzzer & LED ─────────────────────────────────────────────
#define BUZZER_PIN  32
#define LED_PIN      2

// ── Battery ADC ──────────────────────────────────────────────
#define BATTERY_PIN 34

// ── RTC DS3231 ───────────────────────────────────────────────
#define RTC_ENABLED true
#define RTC_SDA     21
#define RTC_SCL     22

// ── Dispenser Config ─────────────────────────────────────────
// Fixed 4-compartment layout:
//   1 → Morning Before Food
//   2 → Morning After Food
//   3 → Night Before Food
//   4 → Night After Food
#define TOTAL_COMPARTMENTS   4
// 28BYJ-48: 4096 half-steps / revolution → 1024 steps per slot
#define STEPS_PER_SLOT      1024
// Max lid opens per session before backend is expected to lock
#define MAX_GATE_OPENS       4

// ── Firmware ─────────────────────────────────────────────────
#define FIRMWARE_VERSION   "2.1.0"
