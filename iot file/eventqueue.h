// ============================================================
// eventqueue.h — NVS-backed offline event queue
//
// The device dispenses whether or not WiFi is up, so events produced during
// an outage must survive both the outage and a reboot. Each entry is a
// complete event JSON object carrying its own `occurred_at` from the RTC, so
// the backend can verify a dose long after it physically happened.
//
// Ring buffer over NVS keys e0..e(N-1) with a persisted head index.
// ============================================================
#pragma once
#include <Arduino.h>
#include <Preferences.h>

#define EVQ_CAPACITY   24     // ~2 days of dose events
#define EVQ_MAX_LEN   384     // bytes per event JSON

Preferences evqPrefs;
static const char* EVQ_NS = "evq";

int evqHead  = 0;   // index of the oldest entry
int evqCount = 0;

static void evq_saveMeta() {
  evqPrefs.begin(EVQ_NS, false);
  evqPrefs.putInt("head",  evqHead);
  evqPrefs.putInt("count", evqCount);
  evqPrefs.end();
}

void evq_init() {
  evqPrefs.begin(EVQ_NS, true);
  evqHead  = evqPrefs.getInt("head", 0);
  evqCount = evqPrefs.getInt("count", 0);
  evqPrefs.end();

  if (evqHead < 0 || evqHead >= EVQ_CAPACITY) evqHead = 0;
  if (evqCount < 0 || evqCount > EVQ_CAPACITY) evqCount = 0;

  if (evqCount > 0) {
    Serial.printf("[EVQ] %d queued event(s) restored from flash\n", evqCount);
  }
}

int evq_count() { return evqCount; }
bool evq_isEmpty() { return evqCount == 0; }

static void evq_key(int slot, char* out, size_t len) {
  snprintf(out, len, "e%d", slot);
}

/**
 * Append an event. When full the oldest entry is dropped — a recent dose
 * record matters more than a stale heartbeat, and dropping silently is
 * better than blocking the dose flow.
 */
bool evq_push(const char* json) {
  if (strlen(json) >= EVQ_MAX_LEN) {
    Serial.printf("[EVQ] Event too large (%d bytes) — dropped\n", strlen(json));
    return false;
  }

  int slot;
  if (evqCount == EVQ_CAPACITY) {
    slot    = evqHead;                            // overwrite oldest
    evqHead = (evqHead + 1) % EVQ_CAPACITY;
    Serial.println("[EVQ] Queue full — dropped oldest event");
  } else {
    slot = (evqHead + evqCount) % EVQ_CAPACITY;
    evqCount++;
  }

  char key[8];
  evq_key(slot, key, sizeof(key));

  evqPrefs.begin(EVQ_NS, false);
  evqPrefs.putString(key, json);
  evqPrefs.putInt("head",  evqHead);
  evqPrefs.putInt("count", evqCount);
  evqPrefs.end();

  Serial.printf("[EVQ] Queued event (%d in queue)\n", evqCount);
  return true;
}

/** Read the i-th oldest entry (0 = oldest). */
bool evq_peek(int index, char* out, size_t outLen) {
  if (index < 0 || index >= evqCount) return false;

  char key[8];
  evq_key((evqHead + index) % EVQ_CAPACITY, key, sizeof(key));

  evqPrefs.begin(EVQ_NS, true);
  String value = evqPrefs.getString(key, "");
  evqPrefs.end();

  if (value.length() == 0) return false;
  strlcpy(out, value.c_str(), outLen);
  return true;
}

/** Drop the n oldest entries — call only after the backend has accepted them. */
void evq_popFront(int n) {
  if (n <= 0) return;
  if (n > evqCount) n = evqCount;

  evqPrefs.begin(EVQ_NS, false);
  for (int i = 0; i < n; i++) {
    char key[8];
    evq_key((evqHead + i) % EVQ_CAPACITY, key, sizeof(key));
    evqPrefs.remove(key);
  }
  evqHead  = (evqHead + n) % EVQ_CAPACITY;
  evqCount -= n;
  evqPrefs.putInt("head",  evqHead);
  evqPrefs.putInt("count", evqCount);
  evqPrefs.end();

  Serial.printf("[EVQ] Flushed %d event(s), %d remaining\n", n, evqCount);
}

/**
 * Build {"events":[...]} from up to `maxEvents` of the oldest entries.
 * Returns how many were packed so the caller knows what to pop on success.
 */
int evq_buildBatch(char* out, size_t outLen, int maxEvents) {
  if (evqCount == 0) return 0;

  int limit = min(maxEvents, evqCount);
  size_t pos = 0;
  int packed = 0;

  pos += snprintf(out + pos, outLen - pos, "{\"events\":[");

  char entry[EVQ_MAX_LEN];
  for (int i = 0; i < limit; i++) {
    if (!evq_peek(i, entry, sizeof(entry))) break;

    size_t needed = strlen(entry) + (packed ? 1 : 0) + 3;  // +separator +"]}"
    if (pos + needed >= outLen) break;                     // keep it contiguous

    if (packed) out[pos++] = ',';
    pos += snprintf(out + pos, outLen - pos, "%s", entry);
    packed++;
  }

  snprintf(out + pos, outLen - pos, "]}");
  return packed;
}
