// ============================================================
// schedule.h — Local schedule store + RTC scheduler (v3)
//
// Architecture change from v2: the DEVICE owns timing. The backend pushes a
// versioned config bundle which is cached in NVS; the DS3231 then fires doses
// locally with no network round-trip. This is what removes the old 60-second
// schedule poll and lets the dispenser work with WiFi down.
//
// Time contract: `hour`/`minute` are DEVICE-LOCAL wall clock, exactly as the
// backend emits them. Never convert — compare straight against the RTC.
// ============================================================
#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include "config.h"

// ── One compartment's schedule + weight expectations ────────
struct CompartmentSchedule {
  int   compartment_number;
  bool  enabled;
  int   hour;
  int   minute;
  float expected_dose_reduction_grams;
  float content_weight_grams;
  int   audio_track;
  char  time_slot[20];
  char  display_text[128];
};

// ── Everything the device needs to run a day unattended ─────
struct ScheduleBundle {
  uint32_t schedule_version;
  int      compartment_count;
  CompartmentSchedule comps[TOTAL_COMPARTMENTS];

  // policy (from the bundle, with compile-time fallbacks)
  uint32_t dose_window_minutes;
  uint32_t catchup_window_minutes;
  uint32_t max_gate_opens;
  uint32_t weight_settle_ms;
  uint32_t hand_detect_cm;

  float    device_total_weight_grams;
  bool     gate_locked;
};

ScheduleBundle schedule = {
  0, 0, {},
  DEFAULT_DOSE_WINDOW_MIN, DEFAULT_CATCHUP_WINDOW_MIN,
  MAX_GATE_OPENS, WEIGHT_SETTLE_MS, HAND_DETECT_DIST_CM,
  0.0f, false,
};

// ── Per-day dispense locks ──────────────────────────────────
// Bit i = compartment i+1 already dispensed today. Persisted so a reboot
// mid-day cannot re-fire a dose the patient already took.
uint32_t dispensedMask = 0;
uint32_t dispensedDay  = 0;   // YYYYMMDD

Preferences schedPrefs;

static const char* SCHED_NS = "sched";

// ─────────────────────────────────────────────────────────────
// Persistence
// ─────────────────────────────────────────────────────────────
void sched_save() {
  schedPrefs.begin(SCHED_NS, false);
  schedPrefs.putBytes("bundle", &schedule, sizeof(schedule));
  schedPrefs.putUInt("mask", dispensedMask);
  schedPrefs.putUInt("day", dispensedDay);
  schedPrefs.end();
}

void sched_load() {
  schedPrefs.begin(SCHED_NS, true);
  size_t stored = schedPrefs.getBytesLength("bundle");
  if (stored == sizeof(schedule)) {
    schedPrefs.getBytes("bundle", &schedule, sizeof(schedule));
    Serial.printf("[SCHED] Restored bundle v%u (%d compartments)\n",
                  schedule.schedule_version, schedule.compartment_count);
  } else if (stored > 0) {
    // Struct layout changed across a firmware update — discard rather than
    // reinterpret stale bytes as a schedule.
    Serial.println("[SCHED] Cached bundle size mismatch — ignoring");
  }
  dispensedMask = schedPrefs.getUInt("mask", 0);
  dispensedDay  = schedPrefs.getUInt("day", 0);
  schedPrefs.end();
}

// ─────────────────────────────────────────────────────────────
// Bundle parsing — GET /api/v1/iot/devices/{id}/config/
// ─────────────────────────────────────────────────────────────
bool sched_parseBundle(JsonDocument& doc) {
  JsonObject data = doc["data"];
  if (data.isNull()) return false;

  ScheduleBundle next = {};
  next.schedule_version = data["schedule_version"] | 0;

  JsonObject policy = data["policy"];
  next.dose_window_minutes    = policy["dose_window_minutes"]    | DEFAULT_DOSE_WINDOW_MIN;
  next.catchup_window_minutes = policy["catchup_window_minutes"] | DEFAULT_CATCHUP_WINDOW_MIN;
  next.max_gate_opens         = policy["max_gate_opens"]         | MAX_GATE_OPENS;
  next.weight_settle_ms       = policy["weight_settle_ms"]       | GATE_CLOSE_CONFIRM_MS;
  next.hand_detect_cm         = policy["hand_detect_cm"]         | HAND_DETECT_DIST_CM;

  next.device_total_weight_grams = data["total_weight_grams"] | 0.0f;
  next.gate_locked               = data["is_gate_locked"]     | false;

  JsonArray comps = data["compartments"].as<JsonArray>();
  int i = 0;
  for (JsonObject c : comps) {
    if (i >= TOTAL_COMPARTMENTS) break;
    CompartmentSchedule& cs = next.comps[i];

    cs.compartment_number = c["compartment_number"] | (i + 1);
    cs.enabled            = c["enabled"]            | false;
    cs.expected_dose_reduction_grams = c["expected_dose_reduction_grams"] | 0.0f;
    cs.content_weight_grams          = c["content_weight_grams"]          | 0.0f;
    cs.audio_track                   = c["audio_track"]                   | AUDIO_DOSE_REMINDER;

    // "HH:MM" in device-local time
    const char* t = c["time"] | "";
    cs.hour = cs.minute = -1;
    if (strlen(t) >= 4) {
      int h, m;
      if (sscanf(t, "%d:%d", &h, &m) == 2 &&
          h >= 0 && h <= 23 && m >= 0 && m <= 59) {
        cs.hour = h;
        cs.minute = m;
      }
    }
    if (cs.hour < 0) {
      Serial.printf("[SCHED] Compartment %d has a bad time '%s' — disabling\n",
                    cs.compartment_number, t);
      cs.enabled = false;
    }

    strlcpy(cs.time_slot,    c["time_slot"]    | "", sizeof(cs.time_slot));
    strlcpy(cs.display_text, c["display_text"] | "", sizeof(cs.display_text));
    i++;
  }
  next.compartment_count = i;

  if (i == 0) {
    Serial.println("[SCHED] Bundle contained no compartments — keeping cache");
    return false;
  }

  schedule = next;
  sched_save();

  Serial.printf("[SCHED] Bundle v%u loaded — %d compartments\n",
                schedule.schedule_version, schedule.compartment_count);
  for (int j = 0; j < schedule.compartment_count; j++) {
    CompartmentSchedule& cs = schedule.comps[j];
    Serial.printf("[SCHED]   c%d %02d:%02d %s dose=%.2fg\n",
                  cs.compartment_number, cs.hour, cs.minute,
                  cs.enabled ? "ON " : "OFF", cs.expected_dose_reduction_grams);
  }
  return true;
}

// ─────────────────────────────────────────────────────────────
// Per-day locks
// ─────────────────────────────────────────────────────────────
bool sched_isDispensed(int compartmentNumber) {
  return dispensedMask & (1UL << (compartmentNumber - 1));
}

void sched_markDispensed(int compartmentNumber) {
  dispensedMask |= (1UL << (compartmentNumber - 1));
  sched_save();
}

void sched_resetDay(uint32_t yyyymmdd) {
  dispensedMask = 0;
  dispensedDay  = yyyymmdd;
  sched_save();
  Serial.printf("[SCHED] New day %u — dispense locks cleared\n", yyyymmdd);
}

/** Clears locks when the RTC date rolls over. Safe to call every tick. */
void sched_rolloverIfNewDay(uint32_t yyyymmdd) {
  if (yyyymmdd != 0 && yyyymmdd != dispensedDay) {
    sched_resetDay(yyyymmdd);
  }
}

// ─────────────────────────────────────────────────────────────
// The scheduler itself
// ─────────────────────────────────────────────────────────────
/**
 * Index into schedule.comps of a dose due right now, or -1.
 *
 * A slot fires from its scheduled minute until catchup_window_minutes past
 * it, so a dispenser that was powered off over the slot still delivers when
 * it comes back — but never hours later.
 */
int sched_dueSlot(int nowHour, int nowMinute) {
  int nowMins = nowHour * 60 + nowMinute;

  for (int i = 0; i < schedule.compartment_count; i++) {
    CompartmentSchedule& cs = schedule.comps[i];
    if (!cs.enabled) continue;
    if (sched_isDispensed(cs.compartment_number)) continue;

    int slotMins = cs.hour * 60 + cs.minute;
    int delta    = nowMins - slotMins;

    if (delta >= 0 && delta <= (int)schedule.catchup_window_minutes) {
      return i;
    }
  }
  return -1;
}

int sched_indexOfCompartment(int compartmentNumber) {
  for (int i = 0; i < schedule.compartment_count; i++) {
    if (schedule.comps[i].compartment_number == compartmentNumber) return i;
  }
  return -1;
}
