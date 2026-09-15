#include <Arduino.h>
#include <WiFi.h>

#include "config.h"
#include "rtc_ds3231.h"
#include "stepper.h"
#include "hall_sensor.h"
#include "servo_gate.h"
#include "ultrasonic.h"
#include "api_client.h"
#include "mqtt_handler.h"
#include "dispenser.h"

// ============================================================
// STATE TRACKING
// ============================================================
static int lastReportedMinute = -1;
static int lastExecutedMinute = -1;
static unsigned long lastHeartbeatTime = 0;
static unsigned long lastConfigSyncTime = 0;

// ============================================================
// MQTT REMOTE COMMAND HANDLER
// ============================================================
void handleRemoteCommand(const char* topic, const char* payload) {
    String msg = String(payload);

    Serial.println();
    Serial.println("==========================================");
    Serial.println(">>> MQTT REMOTE COMMAND RECEIVED <<<");
    Serial.println("==========================================");

    if (msg.indexOf("DISPENSE_NOW") >= 0 || msg.indexOf("TAKE_MEDICINE_NOW") >= 0 || msg.indexOf("OPEN_GATE") >= 0) {
        int comp = 1;
        // Check if compartment specified in JSON
        int cIdx = msg.indexOf("\"compartment\":");
        if (cIdx >= 0) {
            comp = msg.substring(cIdx + 14, cIdx + 16).toInt();
            if (comp < 1 || comp > TOTAL_COMPARTMENTS) comp = 1;
        }

        Serial.printf("[MQTT] Triggering remote dispense for Compartment %d...\n", comp);
        publishEvent("DOSE_STARTED", comp, "Remote Dose", 1);

        String result = dispense(comp, "Remote Dose", 1);

        if (result == "TAKEN") {
            publishEvent("DOSE_TAKEN", comp, "Remote Dose", 1);
        } else if (result == "MISSED") {
            publishEvent("DOSE_MISSED", comp, "Remote Dose", 1);
        }
    }
    else if (msg.indexOf("SYNC_CONFIG") >= 0 || msg.indexOf("SYNC_SCHEDULE") >= 0) {
        Serial.println("[MQTT] Refreshing schedules from backend...");
        fetchSchedulesFromBackend();
    }
    else {
        Serial.println("[MQTT] Command received and acknowledged.");
    }
}

// ============================================================
// SYSTEM SETUP
// ============================================================
void setup() {
    Serial.begin(115200);
    delay(1000);

    Serial.println();
    Serial.println("==========================================");
    Serial.println("       SMART PILL DISPENSER (ARDUINO)");
    Serial.println("       HARDWARE + MQTT INTEGRATION");
    Serial.println("==========================================");

    // 1. Initialize Hardware Pins
    initStepper();
    initHallSensor();
    initServo();
    initUltrasonic();

    // 2. Check RTC DS3231
    Serial.println();
    Serial.println("Checking RTC...");
    if (!checkRTC()) {
        Serial.println("RTC FAILED! System halting.");
        while (true) {
            delay(1000);
        }
    }

    // 3. Connect to WiFi
    Serial.println();
    Serial.print("[WIFI] Connecting to: ");
    Serial.println(WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    unsigned long wifiStart = millis();
    while (WiFi.status() != WL_CONNECTED && (millis() - wifiStart < WIFI_TIMEOUT_MS)) {
        delay(500);
        Serial.print(".");
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.println();
        Serial.println("[WIFI] Connected successfully!");
        Serial.print("[WIFI] IP Address: ");
        Serial.println(WiFi.localIP());

        // Sync Time from Backend (IST)
        syncTimeFromBackend();

        // Download doctor/caregiver schedules from Backend
        fetchSchedulesFromBackend();

        // Connect to MQTT Broker
        initMQTT();
        connectMQTT();

        // Report DEVICE_BOOT
        publishEvent("DEVICE_BOOT", 1);
    } else {
        Serial.println();
        Serial.println("[WIFI] Connection timeout. Running in OFFLINE mode using RTC & local schedules.");
    }

    // 4. Calibrate Home Position using Hall Sensor
    Serial.println();
    Serial.println("Finding HOME...");
    findHome();

    // 5. Initial Servo Gate State
    closeServo();

    // 6. System Ready Summary
    Serial.println();
    Serial.println("==========================================");
    Serial.println("SYSTEM READY");
    Serial.println("==========================================");
    Serial.println("RTC        : READY");
    Serial.println("Hall       : READY");
    Serial.println("Stepper    : READY");
    Serial.println("Servo      : READY");
    Serial.println("Ultrasonic : STANDBY");
    Serial.printf("WiFi       : %s\n", (WiFi.status() == WL_CONNECTED) ? "CONNECTED" : "OFFLINE");
    Serial.printf("MQTT       : %s\n", isMQTTConnected() ? "CONNECTED" : "OFFLINE");
    Serial.println("Backend    : ONLINE");
    Serial.println("==========================================");
}

// ============================================================
// MAIN LOOP
// ============================================================
void loop() {
    // 1. Process incoming MQTT messages (non-blocking)
    loopMQTT();

    // 2. Read Current Time from DS3231 RTC
    DateTime now = readRTC();

    // Print time at the start of each new minute
    if (now.minute != lastReportedMinute) {
        lastReportedMinute = now.minute;
        Serial.printf("\nRTC: %04d-%02d-%02d %02d:%02d:%02d\n",
                      now.year, now.month, now.day, now.hour, now.minute, now.second);
    }

    // 3. Format current time as "HH:MM"
    char currentTimeStr[6];
    snprintf(currentTimeStr, sizeof(currentTimeStr), "%02d:%02d", now.hour, now.minute);

    // 4. Check for Due Schedules
    if (now.minute != lastExecutedMinute) {
        for (int i = 0; i < TOTAL_COMPARTMENTS; i++) {
            if (schedules[i].enabled && strcmp(schedules[i].timeStr, currentTimeStr) == 0) {
                lastExecutedMinute = now.minute;

                int comp = schedules[i].compartment;
                const char* med = schedules[i].medicine;
                int dose = schedules[i].dose;

                Serial.println();
                Serial.println("==========================================");
                Serial.printf(">>> SCHEDULE DUE FOR COMPARTMENT %d <<<\n", comp);
                Serial.printf("Medicine: %s | Dose: %d\n", med, dose);
                Serial.println("==========================================");

                // Publish DOSE_STARTED
                publishEvent("DOSE_STARTED", comp, med, dose);

                // Execute physical dispensing (preserves original sensor sequence)
                String outcome = dispense(comp, med, dose);

                // Publish outcome
                if (outcome == "TAKEN") {
                    publishEvent("DOSE_TAKEN", comp, med, dose);
                } else if (outcome == "MISSED") {
                    publishEvent("DOSE_MISSED", comp, med, dose);
                }
                break; // One compartment per minute
            }
        }
    }

    // 5. Periodic Heartbeat (Every 5 minutes)
    if (millis() - lastHeartbeatTime >= HEARTBEAT_INTERVAL_MS) {
        lastHeartbeatTime = millis();
        publishHeartbeat("ok", "ok", "ok");
    }

    // 6. Periodic Schedule Refresh (Every 30 minutes)
    if (millis() - lastConfigSyncTime >= CONFIG_SYNC_INTERVAL_MS) {
        lastConfigSyncTime = millis();
        if (WiFi.status() == WL_CONNECTED) {
            fetchSchedulesFromBackend();
        }
    }

    delay(100);
}
