// ============================================================
// events.h — Event emission with offline durability
//
// Every event carries:
//   event_uuid  — makes delivery idempotent, so a retried flush is harmless
//   occurred_at — RTC wall clock at the moment it happened, NOT at upload
//
// occurred_at is what lets the backend verify a dose that physically happened
// during a WiFi outage: the event is queued in flash and replayed later, and
// the server timestamps it correctly instead of using arrival time.
//
// ev_emit()     fire-and-forget; queues to flash if the POST fails
// ev_emitSync() needs the response body (dose_status) — queues on failure
// ev_flush()    drains the flash queue in batches
// ============================================================
#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>
#include "api.h"
#include "eventqueue.h"
#include "hardware.h"

#define EV_BATCH_MAX      8
#define EV_BATCH_BUF   3072

/** Serialise an event into `out`, merging any extra fields. */
static void ev_build(char* out, size_t outLen,
                     const char* eventType, JsonDocument& extra) {
  StaticJsonDocument<512> body;
  body["event_uuid"]       = generateUUID();
  body["event_type"]       = eventType;
  body["firmware_version"] = FIRMWARE_VERSION;

  String occurred = hw_rtcGetISO();
  if (occurred.length() > 0) body["occurred_at"] = occurred;

  for (JsonPair kv : extra.as<JsonObject>()) {
    body[kv.key()] = kv.value();
  }
  serializeJson(body, out, outLen);
}

/**
 * Emit an event. If the network is down or the POST fails, the event is
 * persisted to flash and retried by ev_flush() — it is never silently lost.
 */
void ev_emit(const char* eventType, JsonDocument& extra) {
  char json[EVQ_MAX_LEN];
  ev_build(json, sizeof(json), eventType, extra);

  StaticJsonDocument<512> resp;
  int code = apiPostRaw(API_EVENTS, json, resp);

  if (code == 200 || code == 201) {
    Serial.printf("[EV] %s sent\n", eventType);
  } else {
    Serial.printf("[EV] %s failed (HTTP %d) — queued\n", eventType, code);
    evq_push(json);
  }
}

/**
 * Emit and return the backend's response. Used for the after-dose weight,
 * where the reply carries dose_status for the audio/OLED feedback.
 * Returns the HTTP code; queues the event if it could not be delivered.
 */
int ev_emitSync(const char* eventType, JsonDocument& extra, JsonDocument& responseDoc) {
  char json[EVQ_MAX_LEN];
  ev_build(json, sizeof(json), eventType, extra);

  int code = apiPostRaw(API_EVENTS, json, responseDoc);
  if (code != 200 && code != 201) {
    Serial.printf("[EV] %s failed (HTTP %d) — queued for replay\n", eventType, code);
    evq_push(json);
  }
  return code;
}

/**
 * Drain the flash queue. Only pops entries the backend actually accepted, so
 * a partial failure leaves the rest queued for the next attempt.
 */
void ev_flush() {
  if (evq_isEmpty() || WiFi.status() != WL_CONNECTED) return;

  static char batch[EV_BATCH_BUF];
  int packed = evq_buildBatch(batch, sizeof(batch), EV_BATCH_MAX);
  if (packed == 0) return;

  StaticJsonDocument<2048> resp;
  int code = sendEventBatch(batch, resp);

  if (code == 200 || code == 201) {
    evq_popFront(packed);
  } else {
    Serial.printf("[EV] Flush failed (HTTP %d) — %d event(s) still queued\n",
                  code, evq_count());
  }
}

// ─────────────────────────────────────────────────────────────
// Typed emitters
// ─────────────────────────────────────────────────────────────

void evDoseStarted(int compartment, const char* sessionId, float weightBefore) {
  StaticJsonDocument<192> extra;
  extra["compartment_num"] = compartment;
  extra["session_uuid"]    = sessionId;
  extra["weight_before"]   = weightBefore;
  ev_emit("DOSE_STARTED", extra);
}

void evCompartmentRotated(int compartment) {
  StaticJsonDocument<64> extra;
  extra["compartment_num"] = compartment;
  ev_emit("COMPARTMENT_ROTATED", extra);
}

void evHandDetected(int compartment, const char* sessionId) {
  StaticJsonDocument<128> extra;
  extra["compartment_num"] = compartment;
  if (strlen(sessionId)) extra["session_uuid"] = sessionId;
  ev_emit("HAND_DETECTED", extra);
}

void evLidOpened(int compartment, const char* sessionId) {
  StaticJsonDocument<128> extra;
  extra["compartment_num"] = compartment;
  if (strlen(sessionId)) extra["session_uuid"] = sessionId;
  ev_emit("LID_OPENED", extra);
}

void evLidClosed(int compartment, const char* sessionId) {
  StaticJsonDocument<128> extra;
  extra["compartment_num"] = compartment;
  if (strlen(sessionId)) extra["session_uuid"] = sessionId;
  ev_emit("LID_CLOSED", extra);
}

/** After-dose weight. Read the verdict at responseDoc["data"]["dose_status"]. */
int evWeightReading(int compartment, float grams, const char* phase,
                    const char* sessionId, JsonDocument& responseDoc) {
  StaticJsonDocument<192> extra;
  extra["compartment_num"] = compartment;
  extra["weight_grams"]    = grams;
  extra["phase"]           = phase;
  if (strlen(sessionId)) extra["session_uuid"] = sessionId;
  return ev_emitSync("WEIGHT_READING", extra, responseDoc);
}

void evDoseTimeout(int compartment, const char* sessionId) {
  StaticJsonDocument<128> extra;
  extra["compartment_num"] = compartment;
  if (strlen(sessionId)) extra["session_uuid"] = sessionId;
  ev_emit("DOSE_TIMEOUT", extra);
}

void evLowBattery(int batteryPct) {
  StaticJsonDocument<64> extra;
  extra["battery_level"] = batteryPct;
  ev_emit("LOW_BATTERY", extra);
}

void evCommandAck(const char* commandId) {
  StaticJsonDocument<128> extra;
  extra["command_id"] = commandId;
  ev_emit("COMMAND_ACKNOWLEDGED", extra);
}
