// ============================================================
// api.h — HTTP transport for the MedAdhere backend (v3)
//
// Transport only. Event *emission* (with offline queueing) lives in events.h;
// command delivery is pushed over the WebSocket in wsclient.h.
//
// Device → backend over HTTP:
//   POST /api/v1/iot/events/            one event, response needed
//   POST /api/v1/iot/events/batch/      flush of the offline queue
//   POST /api/v1/iot/heartbeat/         health + config reconciliation
//   POST /api/v1/iot/devices/{id}/fill/measure/
//   GET  /api/v1/iot/devices/{id}/config/    versioned schedule bundle
//   GET  /api/v1/iot/devices/{id}/commands/  safety net only
// ============================================================
#pragma once
#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "config.h"

// ─────────────────────────────────────────────────────────────
// UUID v4 Generator (ESP32 hardware RNG)
// ─────────────────────────────────────────────────────────────
String generateUUID() {
  char uuid[37];
  const char* hex = "0123456789abcdef";
  uint8_t buf[16];
  esp_fill_random(buf, 16);
  // Set version 4 and variant bits
  buf[6] = (buf[6] & 0x0f) | 0x40;
  buf[8] = (buf[8] & 0x3f) | 0x80;
  int i = 0, j = 0;
  for (; i < 16; i++) {
    if (i == 4 || i == 6 || i == 8 || i == 10) uuid[j++] = '-';
    uuid[j++] = hex[(buf[i] >> 4) & 0xf];
    uuid[j++] = hex[buf[i] & 0xf];
  }
  uuid[36] = '\0';
  return String(uuid);
}

// ─────────────────────────────────────────────────────────────
// HTTP Helpers
// ─────────────────────────────────────────────────────────────
int apiPostRaw(const char* endpoint, const char* payload, JsonDocument& responseDoc) {
  if (WiFi.status() != WL_CONNECTED) return -1;

  HTTPClient http;
  String url = String(BACKEND_URL) + endpoint;
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Key", DEVICE_API_KEY);
  http.setTimeout(8000);

  int code = http.POST((uint8_t*)payload, strlen(payload));
  if (code == 200 || code == 201) {
    deserializeJson(responseDoc, http.getString());
  }
  http.end();
  return code;
}

int apiPost(const char* endpoint, JsonDocument& body, JsonDocument& responseDoc) {
  String payload;
  serializeJson(body, payload);
  return apiPostRaw(endpoint, payload.c_str(), responseDoc);
}

int apiGet(const char* endpoint, JsonDocument& responseDoc) {
  if (WiFi.status() != WL_CONNECTED) return -1;

  HTTPClient http;
  String url = String(BACKEND_URL) + endpoint;
  http.begin(url);
  http.addHeader("X-Device-Key", DEVICE_API_KEY);
  http.setTimeout(8000);

  int code = http.GET();
  if (code == 200) {
    deserializeJson(responseDoc, http.getString());
  }
  http.end();
  return code;
}

// ─────────────────────────────────────────────────────────────
// Config bundle — the device's whole schedule, fetched only when stale
// ─────────────────────────────────────────────────────────────
int fetchConfig(JsonDocument& responseDoc) {
  int code = apiGet(API_CONFIG, responseDoc);
  Serial.printf("[API] Config fetch → HTTP %d\n", code);
  return code;
}

// ─────────────────────────────────────────────────────────────
// Offline queue flush
// ─────────────────────────────────────────────────────────────
int sendEventBatch(const char* batchJson, JsonDocument& responseDoc) {
  int code = apiPostRaw(API_EVENT_BATCH, batchJson, responseDoc);
  Serial.printf("[API] Event batch → HTTP %d\n", code);
  return code;
}

// ─────────────────────────────────────────────────────────────
// Fill mode — one step of the guided sequence.
// The backend subtracts the running device-wide reference itself; the device
// only reports what the load cell reads for the whole carousel.
// ─────────────────────────────────────────────────────────────
int postFillMeasure(int compartmentNumber, float totalWeightGrams,
                    const char* medicineId, JsonDocument& responseDoc) {
  StaticJsonDocument<256> body;
  body["compartment_number"] = compartmentNumber;
  body["total_weight_grams"] = totalWeightGrams;
  if (medicineId && strlen(medicineId) > 0) body["medicine_id"] = medicineId;

  int code = apiPost(API_FILL_MEASURE, body, responseDoc);
  if (code == 200 || code == 201) {
    float pillWeight = responseDoc["data"]["pill_weight_grams"]   | 0.0f;
    float derived    = responseDoc["data"]["derived_weight_grams"] | 0.0f;
    Serial.printf("[API] Fill measure: +%.2fg, %.4fg per pill\n", derived, pillWeight);
  }
  return code;
}

// ─────────────────────────────────────────────────────────────
// Time Sync
// ─────────────────────────────────────────────────────────────
int syncTimeWithBackend() {
  StaticJsonDocument<256> resp;
  int code = apiGet(API_SYNC_TIME, resp);
  if (code == 200) {
    long ts = resp["data"]["unix_timestamp"] | 0L;
    if (ts > 0) {
      struct timeval tv;
      tv.tv_sec  = (time_t)ts;
      tv.tv_usec = 0;
      settimeofday(&tv, nullptr);
      Serial.printf("[API] Time synced from backend: %ld\n", ts);
    }
  }
  return code;
}
