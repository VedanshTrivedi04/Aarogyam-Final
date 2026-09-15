#ifndef API_CLIENT_H
#define API_CLIENT_H

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include "config.h"
#include "rtc_ds3231.h"

// ============================================================
// SCHEDULE STRUCTURE
// ============================================================
struct SlotSchedule {
    int compartment;
    char medicine[32];
    char timeStr[6]; // "HH:MM"
    int dose;
    bool enabled;
};

// Default fallback schedules (matching schedules.json)
static SlotSchedule schedules[TOTAL_COMPARTMENTS] = {
    {1, "Paracetamol", "17:49", 1, true},
    {2, "Vitamin_C",   "17:54", 1, true},
    {3, "Calcium",     "17:59", 1, true},
    {4, "Multivitamin","18:04", 1, true}
};

inline bool syncTimeFromBackend() {
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("[API] WiFi not connected. Cannot sync time.");
        return false;
    }

    HTTPClient http;
    // Try config bundle first for exact device-local time (IST)
    String url = String(BACKEND_URL) + API_CONFIG;
    http.begin(url);
    http.addHeader("X-Device-Key", DEVICE_API_KEY);
    http.setTimeout(8000);

    int httpCode = http.GET();
    String payload = "";

    if (httpCode == 200) {
        payload = http.getString();
    } else {
        http.end();
        // Fallback to /sync/time/
        url = String(BACKEND_URL) + API_SYNC_TIME;
        http.begin(url);
        http.addHeader("X-Device-Key", DEVICE_API_KEY);
        httpCode = http.GET();
        if (httpCode == 200) {
            payload = http.getString();
        }
    }
    http.end();

    if (httpCode != 200 || payload.length() == 0) {
        Serial.printf("[API] Time sync failed. HTTP Code: %d\n", httpCode);
        return false;
    }

    // Extract ISO time from server_time_local or iso_time
    int idx = payload.indexOf("\"server_time_local\":\"");
    if (idx < 0) {
        idx = payload.indexOf("\"iso_time\":\"");
    }

    if (idx >= 0) {
        int start = payload.indexOf("\"", idx + 18) - 1;
        // Search start of timestamp
        int tIdx = payload.indexOf("T", idx);
        if (tIdx > 0) {
            String datePart = payload.substring(tIdx - 10, tIdx);
            String timePart = payload.substring(tIdx + 1, tIdx + 9);

            int y = datePart.substring(0, 4).toInt();
            int m = datePart.substring(5, 7).toInt();
            int d = datePart.substring(8, 10).toInt();

            int h = timePart.substring(0, 2).toInt();
            int mn = timePart.substring(3, 5).toInt();
            int s = timePart.substring(6, 8).toInt();

            setRTC(y, m, d, h, mn, s);
            Serial.printf("[API] RTC time synced: %04d-%02d-%02d %02d:%02d:%02d\n",
                          y, m, d, h, mn, s);
            return true;
        }
    }

    Serial.println("[API] Could not parse server time.");
    return false;
}

inline bool fetchSchedulesFromBackend() {
    if (WiFi.status() != WL_CONNECTED) {
        return false;
    }

    HTTPClient http;
    String url = String(BACKEND_URL) + API_CONFIG;
    http.begin(url);
    http.addHeader("X-Device-Key", DEVICE_API_KEY);
    http.setTimeout(8000);

    int httpCode = http.GET();
    if (httpCode != 200) {
        http.end();
        Serial.printf("[API] Config bundle fetch failed: %d\n", httpCode);
        return false;
    }

    String payload = http.getString();
    http.end();

    // Parse compartments from payload
    // Search for compartment_number and time
    int searchIdx = 0;
    int syncedCount = 0;

    while (searchIdx < payload.length()) {
        int compIdx = payload.indexOf("\"compartment_number\":", searchIdx);
        if (compIdx < 0) break;

        int compNum = payload.substring(compIdx + 21, compIdx + 23).toInt();

        int timeIdx = payload.indexOf("\"time\":\"", compIdx);
        if (timeIdx > 0 && timeIdx < compIdx + 200) {
            String slotTime = payload.substring(timeIdx + 8, timeIdx + 13);

            if (compNum >= 1 && compNum <= TOTAL_COMPARTMENTS) {
                schedules[compNum - 1].compartment = compNum;
                strncpy(schedules[compNum - 1].timeStr, slotTime.c_str(), sizeof(schedules[compNum - 1].timeStr));

                // Extract medicine name if present
                int medIdx = payload.indexOf("\"name\":\"", compIdx);
                if (medIdx > 0 && medIdx < compIdx + 400) {
                    int medEnd = payload.indexOf("\"", medIdx + 8);
                    String medName = payload.substring(medIdx + 8, medEnd);
                    strncpy(schedules[compNum - 1].medicine, medName.c_str(), sizeof(schedules[compNum - 1].medicine));
                }

                syncedCount++;
            }
        }

        searchIdx = compIdx + 25;
    }

    if (syncedCount > 0) {
        Serial.printf("[API] Synced %d compartment schedules from backend!\n", syncedCount);
        return true;
    }

    return false;
}

inline bool httpSendEvent(const char* eventType, int compartment, const char* extraJson = nullptr) {
    if (WiFi.status() != WL_CONNECTED) {
        return false;
    }

    HTTPClient http;
    String url = String(BACKEND_URL) + API_EVENTS;
    http.begin(url);
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-Device-Key", DEVICE_API_KEY);

    char payload[256];
    snprintf(payload, sizeof(payload),
             "{\"event_type\":\"%s\",\"compartment\":%d,\"compartment_num\":%d,\"occurred_at\":\"%s\",\"firmware_version\":\"%s\"}",
             eventType, compartment, compartment, getRTCISOString().c_str(), FIRMWARE_VERSION);

    int httpCode = http.POST(payload);
    http.end();

    if (httpCode == 200 || httpCode == 201) {
        Serial.printf("[HTTP] Event sent: %s\n", eventType);
        return true;
    }
    return false;
}

#endif // API_CLIENT_H
