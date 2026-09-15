#ifndef CONFIG_H
#define CONFIG_H

// ============================================================
// SMART PILL DISPENSER - CONFIGURATION (ARDUINO / C++)
// ============================================================

// ============================================================
// WIFI CONFIGURATION
// ============================================================
#define WIFI_SSID            "YOUR_WIFI_NAME"
#define WIFI_PASSWORD        "YOUR_WIFI_PASSWORD"
#define WIFI_TIMEOUT_MS      15000

// ============================================================
// BACKEND & DEVICE CREDENTIALS
// ============================================================
#define BACKEND_HOST         "aarogyam-backend-ptty.onrender.com"
#define BACKEND_PORT         443
#define BACKEND_URL          "https://aarogyam-backend-ptty.onrender.com"

#define DEVICE_ID            "e214a30b-c919-4d23-b3f1-80557b756cdd"
#define DEVICE_API_KEY       "GBfHHm3ZSwEo1MkzZSBTGrgWzXZeudFH7p2h4kbmhferTrfflRCdxyftuEF_nPvr"

#define API_EVENTS           "/api/v1/iot/events/"
#define API_HEARTBEAT        "/api/v1/iot/heartbeat/"
#define API_SYNC_TIME        "/api/v1/iot/sync/time/"
#define API_CONFIG           "/api/v1/iot/devices/e214a30b-c919-4d23-b3f1-80557b756cdd/config/"
#define API_COMMANDS         "/api/v1/iot/devices/e214a30b-c919-4d23-b3f1-80557b756cdd/commands/"

#define FIRMWARE_VERSION     "3.2.0-ino"
#define HEARTBEAT_INTERVAL_MS   300000  // 5 minutes
#define CONFIG_SYNC_INTERVAL_MS 1800000 // 30 minutes
#define COMMAND_POLL_INTERVAL_MS 15000  // 15 seconds - HTTP poll for remote commands

// ============================================================
// RTC - DS3231 (I2C)
// ============================================================
#define RTC_SDA              23
#define RTC_SCL              22
#define RTC_ADDRESS          0x68

// ============================================================
// HALL EFFECT SENSOR (HOME POSITION)
// ============================================================
#define HALL_PIN             33

// ============================================================
// STEPPER MOTOR - 28BYJ-48 (ULN2003)
// ============================================================
#define STEPPER_IN1          13
#define STEPPER_IN2          14
#define STEPPER_IN3          27
#define STEPPER_IN4          26

#define TOTAL_COMPARTMENTS    4
#define STEPS_PER_COMPARTMENT 1024  // 90 degrees rotation
#define STEP_DELAY_MS         3

// ============================================================
// SERVO - SG90 (DISPENSER LID)
// ============================================================
#define SERVO_PIN            25
#define SERVO_CLOSED_ANGLE   0
#define SERVO_OPEN_ANGLE     90

// ============================================================
// ULTRASONIC SENSOR - HC-SR04
// ============================================================
#define ULTRASONIC_TRIG      19
#define ULTRASONIC_ECHO      18
#define HAND_DISTANCE_CM     15     // Hand detection distance

// ============================================================
// DISPENSING WINDOW
// ============================================================
#define DISPENSING_WINDOW_MINUTES 3

#endif // CONFIG_H
