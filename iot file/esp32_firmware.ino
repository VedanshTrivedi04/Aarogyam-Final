// ============================================================
// esp32_firmware.ino — MedAdhere Smart Pill Dispenser v3.0
//
// Hardware:
//   28BYJ-48 stepper  + ULN2003
//   1 kg HX711 load cell (single cell under the whole carousel)
//   DFPlayer Mini MP3 (5 audio tracks)
//   SG90 servo gate
//   HC-SR04 ultrasonic hand sensor
//   SSD1306 OLED
//   DS3231 RTC
//
// ── What changed from v2.1 ───────────────────────────────────
// The DEVICE now owns timing. v2.1 asked the backend "is a dose due?" every
// 60 s and waited for commands every 10 s (~10,400 requests/day). Now the
// backend pushes a versioned schedule bundle once, the DS3231 fires doses
// locally, and commands arrive over a WebSocket. Steady state is ~200
// requests/day, and the dispenser keeps working with WiFi down.
//
// RTOS Architecture (FreeRTOS):
//   Core 0 — taskNetwork   : WebSocket pump, heartbeat, queue flush
//   Core 1 — taskScheduler : RTC slot matching (the dose trigger)
//   Core 1 — taskMotor     : stepper rotation (queue-driven)
//   Core 1 — taskSensor    : ultrasonic, gate, weight, dose session
//
// Dose flow (no network needed to reach the patient):
//   RTC hits a slot -> mint session UUID -> rotate -> settle -> baseline weight
//   -> DOSE_STARTED -> reminder audio
//   Hand detected -> gate opens -> LID_OPENED
//   Hand withdraws -> gate closes -> LID_CLOSED -> settle -> after weight
//   -> WEIGHT_READING returns dose_status -> track 3 (taken) / 4 (missed)
//   Offline: every event is queued in flash with its RTC timestamp and
//   replayed later; the patient still gets the medicine.
// ============================================================
#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <time.h>

#include "config.h"
#include "hardware.h"
#include "api.h"
#include "eventqueue.h"
#include "events.h"
#include "schedule.h"
#include "wsclient.h"

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"

// ─────────────────────────────────────────────────────────────
// State Machine
// ─────────────────────────────────────────────────────────────
enum State {
  STATE_BOOT,
  STATE_IDLE,
  STATE_FILL_MODE,
  STATE_DOSE_PREPARE,  // Rotating / reading baseline weight
  STATE_DISPENSING,    // At the compartment, waiting for the patient's hand
  STATE_GATE_OPEN,     // Gate open, waiting for the hand to withdraw
  STATE_WEIGHT_CHECK,  // Gate closed, reading the after-dose weight
  STATE_GATE_LOCKED,   // Locked — caregiver must unlock remotely
};

// ─────────────────────────────────────────────────────────────
// Shared State
// ─────────────────────────────────────────────────────────────
volatile State deviceState       = STATE_BOOT;
volatile int   activeCompartment = -1;
volatile int   activeSlotIndex   = -1;
volatile bool  gateLocked        = false;
volatile int   gateOpenCount     = 0;
volatile bool  alarmActive       = false;
volatile bool  motorBusy         = false;

char  activeSessionId[40] = "";
float baselineWeight      = 0.0f;

// Fill mode
char fillMedName[64]     = "";
char fillMedicineId[40]  = "";
int  fillModeCompartment = -1;

// Deferred load cell reads, so the WebSocket pump never blocks on the scale
volatile bool fillReadPending   = false;
volatile bool weightReadPending = false;
char weightReadPhase[20] = "before_dose";

// Timestamps
unsigned long dispenseStartMs = 0;
unsigned long gateClosedAtMs  = 0;
unsigned long alarmStartMs    = 0;

// ─────────────────────────────────────────────────────────────
// RTOS Primitives
// ─────────────────────────────────────────────────────────────
SemaphoreHandle_t xStateMutex;
SemaphoreHandle_t xMotorMutex;   // held while rotating or reading the scale
QueueHandle_t     xMotorCmdQueue;

struct MotorCommand {
  int  targetCompartment;
  bool openLidAfter;   // true in fill mode
  char medName[64];
};

State getState() {
  xSemaphoreTake(xStateMutex, portMAX_DELAY);
  State s = deviceState;
  xSemaphoreGive(xStateMutex);
  return s;
}

void setState(State s) {
  xSemaphoreTake(xStateMutex, portMAX_DELAY);
  deviceState = s;
  xSemaphoreGive(xStateMutex);
}

unsigned long doseWindowMs() {
  return (unsigned long)schedule.dose_window_minutes * 60000UL;
}

// ─────────────────────────────────────────────────────────────
// Command de-duplication
// Commands are delivered at-least-once (the backend keeps them PENDING until
// acked), so the same command_id can arrive over both the socket and the
// safety-net poll. Acting on it twice could double-trigger a dose.
// ─────────────────────────────────────────────────────────────
#define CMD_HISTORY 8
char recentCmdIds[CMD_HISTORY][40] = {};
int  recentCmdSlot = 0;

bool cmdAlreadyHandled(const char* commandId) {
  if (!commandId || !strlen(commandId)) return false;
  for (int i = 0; i < CMD_HISTORY; i++) {
    if (strcmp(recentCmdIds[i], commandId) == 0) return true;
  }
  return false;
}

void cmdRemember(const char* commandId) {
  if (!commandId || !strlen(commandId)) return;
  strlcpy(recentCmdIds[recentCmdSlot], commandId, 40);
  recentCmdSlot = (recentCmdSlot + 1) % CMD_HISTORY;
}

// ─────────────────────────────────────────────────────────────
// WiFi + Time
// ─────────────────────────────────────────────────────────────
void connectWiFi() {
  hw_displayMessage("Connecting WiFi", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 30) {
    vTaskDelay(pdMS_TO_TICKS(500));
    Serial.print(".");
    tries++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n[WiFi] Connected: %s\n", WiFi.localIP().toString().c_str());
    hw_displayMessage("WiFi OK", WiFi.localIP().toString());
    hw_beep(2);
  } else {
    Serial.println("\n[WiFi] FAILED — running offline from RTC + cached schedule");
    hw_displayMessage("WiFi FAILED", "Offline mode");
  }
}

void syncTime() {
  configTime(19800, 0, "pool.ntp.org", "time.google.com");  // IST = UTC+5:30
  struct tm t;
  if (getLocalTime(&t, 5000)) {
    char buf[20]; strftime(buf, sizeof(buf), "%H:%M:%S", &t);
    Serial.printf("[TIME] NTP synced: %s\n", buf);
    hw_rtcSyncFromNTP();
    syncTimeWithBackend();
  } else {
    Serial.println("[TIME] NTP failed — using RTC");
  }
}

// ─────────────────────────────────────────────────────────────
// Config bundle
// ─────────────────────────────────────────────────────────────
bool refreshConfig() {
  StaticJsonDocument<4096> resp;
  if (fetchConfig(resp) != 200) return false;

  if (!sched_parseBundle(resp)) return false;

  gateLocked = schedule.gate_locked;
  if (gateLocked && getState() == STATE_IDLE) {
    setState(STATE_GATE_LOCKED);
    hw_displayGateLocked();
  }
  return true;
}

// ─────────────────────────────────────────────────────────────
// Dose start — called by the scheduler (RTC) or TRIGGER_DOSE (caregiver)
// ─────────────────────────────────────────────────────────────
bool startDose(int slotIndex, bool manual) {
  if (slotIndex < 0 || slotIndex >= schedule.compartment_count) return false;

  if (gateLocked) {
    Serial.println("[DOSE] Gate locked — refusing to start");
    hw_displayGateLocked();
    return false;
  }
  if (getState() != STATE_IDLE) {
    Serial.println("[DOSE] Busy — dose start ignored");
    return false;
  }

  CompartmentSchedule& cs = schedule.comps[slotIndex];

  activeSlotIndex   = slotIndex;
  activeCompartment = cs.compartment_number;
  gateOpenCount     = 0;
  baselineWeight    = 0.0f;
  strlcpy(activeSessionId, generateUUID().c_str(), sizeof(activeSessionId));

  // Lock the slot for today BEFORE dispensing. A reboot or a second
  // scheduler tick must not re-fire a dose the patient already received.
  // Manual triggers are deliberately exempt so they don't cancel the
  // compartment's real scheduled dose later in the day.
  if (!manual) sched_markDispensed(cs.compartment_number);

  motorBusy = true;
  MotorCommand mc;
  mc.targetCompartment = cs.compartment_number;
  mc.openLidAfter      = false;
  strlcpy(mc.medName, cs.display_text, sizeof(mc.medName));
  xQueueSend(xMotorCmdQueue, &mc, 0);

  setState(STATE_DOSE_PREPARE);
  dispenseStartMs = millis();
  alarmActive     = true;
  alarmStartMs    = millis();
  hw_beep(3, 200);

  Serial.printf("[DOSE] Starting %s dose: compartment %d (session %s)\n",
                manual ? "manual" : "scheduled", activeCompartment, activeSessionId);
  return true;
}

void endDoseSession() {
  activeCompartment = -1;
  activeSlotIndex   = -1;
  gateOpenCount     = 0;
  alarmActive       = false;
  baselineWeight    = 0.0f;
  memset(activeSessionId, 0, sizeof(activeSessionId));
  setState(gateLocked ? STATE_GATE_LOCKED : STATE_IDLE);
}

// ─────────────────────────────────────────────────────────────
// Command handling — shared by the WebSocket and the safety-net poll
// ─────────────────────────────────────────────────────────────
/** First present key wins. Avoids chaining ArduinoJson's `|` across variants. */
static int payloadInt(JsonObject p, const char* k1, const char* k2, int fallback) {
  if (!p.isNull()) {
    if (p[k1].is<int>()) return p[k1].as<int>();
    if (k2 && p[k2].is<int>()) return p[k2].as<int>();
  }
  return fallback;
}

static const char* payloadStr(JsonObject p, const char* k1, const char* k2,
                              const char* fallback) {
  if (!p.isNull()) {
    if (p[k1].is<const char*>()) return p[k1].as<const char*>();
    if (k2 && p[k2].is<const char*>()) return p[k2].as<const char*>();
  }
  return fallback;
}

void handleDeviceCommand(const char* type, const char* commandId, JsonObject payload) {
  if (cmdAlreadyHandled(commandId)) {
    Serial.printf("[CMD] %s already handled — ignoring duplicate\n", type);
    return;
  }
  cmdRemember(commandId);

  Serial.printf("[CMD] %s\n", type);

  // ── Config sync ────────────────────────────────────────────
  // SYNC_SCHEDULE is the legacy name still queued by the clinical app;
  // both mean "your cached bundle is stale".
  if (strcmp(type, "SYNC_CONFIG") == 0 || strcmp(type, "SYNC_SCHEDULE") == 0) {
    refreshConfig();
  }

  // ── Caregiver "take medicine now" ──────────────────────────
  else if (strcmp(type, "TRIGGER_DOSE") == 0) {
    int comp = payloadInt(payload, "compartment", "compartment_number", -1);
    int idx  = sched_indexOfCompartment(comp);
    if (idx >= 0) {
      startDose(idx, /*manual=*/true);
    } else {
      Serial.printf("[CMD] TRIGGER_DOSE for unknown compartment %d\n", comp);
    }
  }

  // ── Gate control ───────────────────────────────────────────
  else if (strcmp(type, "GATE_LOCK") == 0) {
    gateLocked = true;
    hw_closeLid();
    setState(STATE_GATE_LOCKED);
    hw_displayGateLocked();
    hw_alertAlarm();
    hw_playTrack(AUDIO_DOSE_MISSED);
  }

  else if (strcmp(type, "GATE_UNLOCK") == 0) {
    gateLocked    = false;
    gateOpenCount = 0;
    hw_playTrack(AUDIO_CAREGIVER_UNLOCK);
    hw_displayMessage("Unlocked!", "Caregiver ne khola", "Dawai le lo");
    hw_beep(2, 200);
    if (activeCompartment > 0) {
      setState(STATE_DISPENSING);      // resume the interrupted dose
      dispenseStartMs = millis();
      alarmActive     = true;
      alarmStartMs    = millis();
    } else {
      setState(STATE_IDLE);
    }
  }

  else if (strcmp(type, "OPEN_GATE") == 0) {
    if (!gateLocked) {
      hw_openLid();
      evLidOpened(activeCompartment, activeSessionId);
      setState(STATE_GATE_OPEN);
    } else {
      hw_displayMessage("Gate LOCKED", "Cannot open", "");
    }
  }

  // ── Fill mode ──────────────────────────────────────────────
  else if (strcmp(type, "START_FILL_MODE") == 0 ||
           strcmp(type, "NEXT_COMPARTMENT") == 0) {
    int comp = payloadInt(payload, "compartment", "compartment_number",
                          fillModeCompartment + 1);
    const char* medName = payloadStr(payload, "medication_name", "medicine_name",
                                     "Medicine");

    strlcpy(fillMedName, medName, sizeof(fillMedName));
    fillModeCompartment = comp;

    motorBusy = true;
    MotorCommand mc;
    mc.targetCompartment = comp;
    mc.openLidAfter      = true;
    strlcpy(mc.medName, medName, sizeof(mc.medName));
    xQueueSend(xMotorCmdQueue, &mc, 0);

    setState(STATE_FILL_MODE);
  }

  else if (strcmp(type, "END_FILL_MODE") == 0) {
    hw_closeLid();
    fillModeCompartment = -1;
    setState(STATE_IDLE);
    hw_displayMessage("Fill Complete!", "All stocked", "");
    hw_beep(3, 100);
    refreshConfig();   // expected weights changed
  }

  // ── Deferred load cell reads (handled in taskSensor) ───────
  else if (strcmp(type, "READ_FILL_WEIGHT") == 0) {
    fillModeCompartment = payloadInt(payload, "compartment_number", "compartment",
                                     fillModeCompartment);
    strlcpy(fillMedicineId, payloadStr(payload, "medicine_id", nullptr, ""),
            sizeof(fillMedicineId));
    strlcpy(fillMedName, payloadStr(payload, "medicine_name", nullptr, fillMedName),
            sizeof(fillMedName));
    fillReadPending = true;
  }

  else if (strcmp(type, "READ_WEIGHT") == 0) {
    strlcpy(weightReadPhase, payloadStr(payload, "phase", nullptr, "before_dose"),
            sizeof(weightReadPhase));
    int comp = payloadInt(payload, "compartment", "compartment_number",
                          activeCompartment);
    if (comp > 0) activeCompartment = comp;
    weightReadPending = true;
  }

  // ── Utility ────────────────────────────────────────────────
  else if (strcmp(type, "SYNC_TIME") == 0) {
    syncTime();
  }

  else if (strcmp(type, "RESET_FLAGS") == 0) {
    sched_resetDay(hw_rtcGetYYYYMMDD());
    gateLocked = false;
    endDoseSession();
    hw_displayMessage("Day Reset!", "New day, fresh", "");
  }

  else {
    Serial.printf("[CMD] Unhandled command type: %s\n", type);
  }

  // Acked over the socket by ws_onMessage; this covers the HTTP poll path.
  if (!ws_isConnected()) evCommandAck(commandId);
}

/** Safety net for a dropped socket — NOT the primary command path. */
void pollCommandsHttp() {
  StaticJsonDocument<2048> resp;
  if (apiGet(API_COMMANDS, resp) != 200) return;

  for (JsonObject cmd : resp["data"]["commands"].as<JsonArray>()) {
    handleDeviceCommand(cmd["type"] | "", cmd["command_id"] | "",
                        cmd["payload"].as<JsonObject>());
  }
}

// ─────────────────────────────────────────────────────────────
// TASK 1 — Network (Core 0)
// WebSocket pump, heartbeat/config reconciliation, offline queue flush.
// ─────────────────────────────────────────────────────────────
void taskNetwork(void* pvParam) {
  Serial.println("[RTOS] Network task started on Core 0");

  StaticJsonDocument<256> bootExtra;
  bootExtra["battery_level"]    = hw_getBatteryLevel();
  bootExtra["firmware_version"] = FIRMWARE_VERSION;
  bootExtra["stepper_status"]   = hw_getStatus();
  ev_emit("DEVICE_BOOT", bootExtra);

  if (WiFi.status() == WL_CONNECTED) refreshConfig();
  if (getState() == STATE_BOOT) setState(STATE_IDLE);

  unsigned long lastHeartbeat   = 0;
  unsigned long lastCommandPoll = 0;
  unsigned long lastFlush       = 0;
  unsigned long lastWifiRetry   = 0;
  unsigned long lastLowBatAlert = 0;

  for (;;) {
    unsigned long now = millis();

    if (WiFi.status() != WL_CONNECTED) {
      if (now - lastWifiRetry >= WIFI_RECONNECT_MS) {
        lastWifiRetry = now;
        Serial.println("[WiFi] Lost — retrying (dosing continues from RTC)");
        WiFi.reconnect();
      }
      vTaskDelay(pdMS_TO_TICKS(1000));
      continue;
    }

    // ── WebSocket pump — must run often ─────────────────────
    ws_loop();

    // ── Heartbeat + config reconciliation (every 10 min) ────
    if (now - lastHeartbeat >= HEARTBEAT_INTERVAL_MS) {
      lastHeartbeat = now;
      int bat = hw_getBatteryLevel();

      StaticJsonDocument<384> hbBody;
      hbBody["battery_level"]     = bat;
      hbBody["firmware_version"]  = FIRMWARE_VERSION;
      hbBody["wifi_strength"]     = WiFi.RSSI();
      hbBody["uptime_seconds"]    = millis() / 1000;
      hbBody["schedule_version"]  = schedule.schedule_version;
      hbBody["rtc_time"]          = hw_rtcGetISO();
      hbBody["current_compartment"] = currentCompartment;
      hbBody["queued_events"]     = evq_count();
      hbBody["state"]             = (int)getState();

      StaticJsonDocument<512> hbResp;
      int code = apiPost(API_HEARTBEAT, hbBody, hbResp);

      if (code == 200 || code == 201) {
        JsonObject data = hbResp["data"];

        // This is what replaces the old 60-second schedule poll.
        if (data["config_stale"] | false) {
          Serial.println("[HB] Config stale — fetching bundle");
          refreshConfig();
        }
        // Socket may be down; pull anything waiting.
        if ((data["pending_commands"] | 0) > 0 && !ws_isConnected()) {
          pollCommandsHttp();
        }
        long drift = data["rtc_drift_seconds"] | 0L;
        if (drift > 30 || drift < -30) {
          Serial.printf("[HB] RTC drift %lds — resyncing\n", drift);
          syncTime();
        }
        gateLocked = data["gate_locked"] | gateLocked;
      }

      Serial.printf("[HB] battery=%d%% queued=%d ws=%d\n",
                    bat, evq_count(), ws_isConnected() ? 1 : 0);

      if (bat < 15 && now - lastLowBatAlert >= 3600000UL) {
        lastLowBatAlert = now;
        evLowBattery(bat);
      }
    }

    // ── Safety-net command poll (every 5 min, only if socket down) ──
    if (now - lastCommandPoll >= COMMAND_POLL_MS) {
      lastCommandPoll = now;
      if (!ws_isConnected()) {
        Serial.println("[CMD] Socket down — falling back to HTTP poll");
        pollCommandsHttp();
      }
    }

    // ── Replay anything produced while offline ──────────────
    if (now - lastFlush >= EVENT_FLUSH_MS) {
      lastFlush = now;
      ev_flush();
    }

    vTaskDelay(pdMS_TO_TICKS(10));   // keep the WebSocket responsive
  }
}

// ─────────────────────────────────────────────────────────────
// TASK 2 — Scheduler (Core 1)
// The dose trigger. Reads the DS3231 and matches it against the cached
// bundle — no network involved, so this works during an outage.
// ─────────────────────────────────────────────────────────────
void taskScheduler(void* pvParam) {
  Serial.println("[RTOS] Scheduler task started on Core 1");

  for (;;) {
    int hour, minute;
    if (hw_rtcGetHourMinute(hour, minute)) {
      sched_rolloverIfNewDay(hw_rtcGetYYYYMMDD());

      if (getState() == STATE_IDLE && !gateLocked) {
        int slot = sched_dueSlot(hour, minute);
        if (slot >= 0) {
          Serial.printf("[SCHED] %02d:%02d matched compartment %d\n",
                        hour, minute, schedule.comps[slot].compartment_number);
          startDose(slot, /*manual=*/false);
        }
      }
    }
    vTaskDelay(pdMS_TO_TICKS(SCHEDULER_TICK_MS));
  }
}

// ─────────────────────────────────────────────────────────────
// TASK 3 — Motor (Core 1)
// Holds xMotorMutex while rotating so weight reads can't overlap motion.
// ─────────────────────────────────────────────────────────────
void taskMotor(void* pvParam) {
  Serial.println("[RTOS] Motor task started on Core 1");
  MotorCommand cmd;

  for (;;) {
    if (xQueueReceive(xMotorCmdQueue, &cmd, portMAX_DELAY) == pdTRUE) {
      xSemaphoreTake(xMotorMutex, portMAX_DELAY);

      Serial.printf("[MOTOR] Rotating to compartment %d\n", cmd.targetCompartment);
      hw_rotateTo(cmd.targetCompartment);

      if (cmd.openLidAfter) {
        vTaskDelay(pdMS_TO_TICKS(300));
        hw_openLid();
        hw_displayFillMode(cmd.targetCompartment, cmd.medName);
        hw_beep(2, 150);
      } else {
        evCompartmentRotated(cmd.targetCompartment);
      }

      xSemaphoreGive(xMotorMutex);
      motorBusy = false;
    }
  }
}

// ─────────────────────────────────────────────────────────────
// TASK 4 — Sensor + Gate (Core 1)
// ─────────────────────────────────────────────────────────────
void taskSensor(void* pvParam) {
  Serial.println("[RTOS] Sensor task started on Core 1");

  for (;;) {
    unsigned long now = millis();
    State curState = getState();

    // ── Deferred load cell reads (kept off the network task) ──
    // The flag is cleared only once the read actually runs, so a request
    // arriving mid-rotation waits instead of being dropped.
    if (fillReadPending && !motorBusy) {
      if (xSemaphoreTake(xMotorMutex, pdMS_TO_TICKS(5000)) == pdTRUE) {
        fillReadPending = false;
        hw_displayMessage("Measuring...", fillMedName, "Keep still!");
        vTaskDelay(pdMS_TO_TICKS(schedule.weight_settle_ms));
        float w = hw_getStableWeightGrams();
        xSemaphoreGive(xMotorMutex);

        StaticJsonDocument<512> resp;
        int code = postFillMeasure(fillModeCompartment, w, fillMedicineId, resp);
        if (code == 200 || code == 201) {
          float pill = resp["data"]["pill_weight_grams"] | 0.0f;
          hw_displayMessage("Weight OK!", String(w, 1) + "g",
                            String(pill, 3) + "g/pill");
          hw_beep(2, 100);
        } else {
          const char* msg = resp["error"]["message"] | "Measure failed";
          hw_displayMessage("Measure FAILED", msg, "");
          hw_beep(1, 600);
        }
      }
    }

    if (weightReadPending && !motorBusy) {
      if (xSemaphoreTake(xMotorMutex, pdMS_TO_TICKS(5000)) == pdTRUE) {
        weightReadPending = false;
        vTaskDelay(pdMS_TO_TICKS(schedule.weight_settle_ms));
        float w = hw_getStableWeightGrams();
        xSemaphoreGive(xMotorMutex);

        StaticJsonDocument<512> resp;
        evWeightReading(activeCompartment, w, weightReadPhase, activeSessionId, resp);
        if (strcmp(weightReadPhase, "before_dose") == 0) baselineWeight = w;
      }
    }

    switch (curState) {

      // ── IDLE — show clock ───────────────────────────────────
      case STATE_IDLE: {
        static unsigned long lastIdleUpdate = 0;
        if (now - lastIdleUpdate > 10000) {
          lastIdleUpdate = now;
          String line3 = evq_count() > 0
            ? String("Sync pending: ") + evq_count()
            : (ws_isConnected() ? "Online" : "Offline");
          hw_displayMessage("MedAdhere Ready", hw_rtcGetTime(), line3);
        }
        break;
      }

      // ── DOSE_PREPARE — rotation done, take the baseline ─────
      case STATE_DOSE_PREPARE: {
        if (motorBusy) break;                       // still rotating
        if (xSemaphoreTake(xMotorMutex, pdMS_TO_TICKS(5000)) != pdTRUE) break;

        vTaskDelay(pdMS_TO_TICKS(schedule.weight_settle_ms));
        baselineWeight = hw_getStableWeightGrams();
        xSemaphoreGive(xMotorMutex);

        evDoseStarted(activeCompartment, activeSessionId, baselineWeight);

        int track = (activeSlotIndex >= 0)
          ? schedule.comps[activeSlotIndex].audio_track
          : AUDIO_DOSE_REMINDER;
        hw_playTrack(track);

        Serial.printf("[DOSE] Baseline %.2fg — waiting for hand\n", baselineWeight);
        setState(STATE_DISPENSING);
        dispenseStartMs = millis();
        break;
      }

      // ── DISPENSING — waiting for the patient's hand ─────────
      case STATE_DISPENSING: {
        static unsigned long lastDispUpdate = 0;
        if (now - lastDispUpdate > 2000) {
          lastDispUpdate = now;
          const char* text = (activeSlotIndex >= 0)
            ? schedule.comps[activeSlotIndex].display_text : "";
          hw_displayDoseInfo(activeCompartment, text);
        }

        if (now - dispenseStartMs >= doseWindowMs()) {
          hw_closeLid();
          evDoseTimeout(activeCompartment, activeSessionId);
          hw_playTrack(AUDIO_DOSE_MISSED);
          hw_alertAlarm();
          hw_displayMessage("DOSE TIMEOUT", "Alerting caregiver", "");
          endDoseSession();
          break;
        }

        if (!gateLocked && hw_isHandDetected()) {
          gateOpenCount++;

          // Self-enforce the open limit: with the socket down the backend
          // cannot send GATE_LOCK in time to stop repeated grabs.
          if ((uint32_t)gateOpenCount > schedule.max_gate_opens) {
            gateLocked = true;
            hw_closeLid();
            setState(STATE_GATE_LOCKED);
            hw_displayGateLocked();
            hw_alertAlarm();
            Serial.printf("[SENSOR] Gate open limit (%u) exceeded — locking\n",
                          schedule.max_gate_opens);
            break;
          }

          evHandDetected(activeCompartment, activeSessionId);
          hw_openLid();
          hw_playTrack(AUDIO_TAKE_MEDICINE);
          evLidOpened(activeCompartment, activeSessionId);

          setState(STATE_GATE_OPEN);
          Serial.printf("[SENSOR] Lid opened (open count=%d)\n", gateOpenCount);
          hw_beep(1, 100);
        }
        break;
      }

      // ── GATE_OPEN — wait for the hand to withdraw ───────────
      case STATE_GATE_OPEN: {
        if (!hw_isHandDetected()) {
          vTaskDelay(pdMS_TO_TICKS(500));
          if (!hw_isHandDetected()) {               // debounced
            hw_closeLid();
            gateClosedAtMs = millis();
            evLidClosed(activeCompartment, activeSessionId);
            Serial.println("[SENSOR] Lid closed — weight check");
            setState(STATE_WEIGHT_CHECK);
            break;
          }
        }

        if (now - dispenseStartMs >= doseWindowMs()) {
          hw_closeLid();
          gateClosedAtMs = millis();
          evLidClosed(activeCompartment, activeSessionId);
          setState(STATE_WEIGHT_CHECK);
        }
        break;
      }

      // ── WEIGHT_CHECK — settle, read, report, announce ───────
      case STATE_WEIGHT_CHECK: {
        if (now - gateClosedAtMs < GATE_CLOSE_CONFIRM_MS) break;

        float weightGrams;
        if (xSemaphoreTake(xMotorMutex, pdMS_TO_TICKS(5000)) == pdTRUE) {
          weightGrams = hw_getStableWeightGrams();
          xSemaphoreGive(xMotorMutex);
        } else {
          weightGrams = hw_getWeightGrams();
        }

        Serial.printf("[SENSOR] After-dose weight: %.2fg (baseline %.2fg)\n",
                      weightGrams, baselineWeight);

        StaticJsonDocument<768> weightResp;
        int wCode = evWeightReading(activeCompartment, weightGrams,
                                    "after_dose", activeSessionId, weightResp);

        if (wCode == 200 || wCode == 201) {
          // POST /events/ flattens the handler result onto `data`, so
          // dose_status is top-level here. (It IS nested under
          // results[i].response_data on /events/batch/ — different shape.)
          const char* doseStatus = weightResp["data"]["dose_status"] | "unknown";
          Serial.printf("[SENSOR] dose_status: %s\n", doseStatus);
          hw_displayDoseResult(doseStatus);

          if (strcmp(doseStatus, "taken") == 0) {
            hw_playTrack(AUDIO_DOSE_TAKEN);
            hw_beep(3, 100);
            vTaskDelay(pdMS_TO_TICKS(3000));
            endDoseSession();
          } else if (strcmp(doseStatus, "partial") == 0) {
            // Session stays open — the patient may still take the rest.
            hw_beep(2, 300);
            setState(STATE_DISPENSING);
          } else {
            hw_beep(1, 500);
            setState(STATE_DISPENSING);
          }
        } else {
          // Offline: the event is queued and verified when connectivity
          // returns, so don't claim taken or missed here.
          Serial.println("[SENSOR] Offline — weight queued for later verification");
          hw_displayMessage("Dose recorded", "Will sync when", "online");
          hw_beep(2, 150);
          vTaskDelay(pdMS_TO_TICKS(3000));
          endDoseSession();
        }
        break;
      }

      // ── GATE_LOCKED ─────────────────────────────────────────
      case STATE_GATE_LOCKED: {
        static unsigned long lastLockBeep = 0;
        if (now - lastLockBeep > 30000) {
          lastLockBeep = now;
          hw_beep(2, 300);
          hw_displayGateLocked();
        }
        if (!gateLocked) setState(STATE_IDLE);   // unlocked remotely
        break;
      }

      // ── FILL_MODE ───────────────────────────────────────────
      case STATE_FILL_MODE: {
        static unsigned long lastFillBlink = 0;
        if (now - lastFillBlink > 5000) {
          lastFillBlink = now;
          hw_displayFillMode(fillModeCompartment, fillMedName);
        }
        break;
      }

      default: break;
    }

    // Periodic alarm beep while a dose is waiting
    if (alarmActive && (now - alarmStartMs) % 10000 < 200) {
      hw_beep(1, 200);
    }

    vTaskDelay(pdMS_TO_TICKS(100));
  }
}

// ─────────────────────────────────────────────────────────────
// SETUP
// ─────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n[BOOT] MedAdhere Pill Dispenser v" FIRMWARE_VERSION);
  Serial.printf("[BOOT] Device ID: %s\n", DEVICE_ID);

  hw_initAll();

  // Restore cached schedule + queued events BEFORE networking, so a boot with
  // no WiFi can still dispense from flash.
  evq_init();
  sched_load();
  gateLocked = schedule.gate_locked;

  xStateMutex    = xSemaphoreCreateMutex();
  xMotorMutex    = xSemaphoreCreateMutex();
  xMotorCmdQueue = xQueueCreate(5, sizeof(MotorCommand));

  connectWiFi();
  if (WiFi.status() == WL_CONNECTED) {
    syncTime();
    ws_begin();
  }

  // Core 0: Network (stack 12 kB — HTTP + WebSocket + JSON)
  xTaskCreatePinnedToCore(taskNetwork,   "NetworkTask",   12288, NULL, 1, NULL, 0);
  // Core 1: Motor (priority 3 — highest so rotation isn't interrupted)
  xTaskCreatePinnedToCore(taskMotor,     "MotorTask",      4096, NULL, 3, NULL, 1);
  // Core 1: Sensor (priority 2)
  xTaskCreatePinnedToCore(taskSensor,    "SensorTask",     8192, NULL, 2, NULL, 1);
  // Core 1: Scheduler (priority 1 — the dose trigger)
  xTaskCreatePinnedToCore(taskScheduler, "SchedulerTask",  4096, NULL, 1, NULL, 1);

  Serial.println("[BOOT] All RTOS tasks launched");
  Serial.printf("[BOOT] %d-compartment dispenser ready (schedule v%u)\n",
                TOTAL_COMPARTMENTS, schedule.schedule_version);
}

void loop() {
  // All work happens in the RTOS tasks
  vTaskDelay(pdMS_TO_TICKS(10000));
}
