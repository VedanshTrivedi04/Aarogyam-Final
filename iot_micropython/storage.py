"""
storage.py - schedules.json load/save/add/update/delete/read, plus offline
event queue aur per-day dispense locks.

Teen files:
  schedules.json     - backend ka config bundle (cached). Isi se device
                       offline bhi dose de sakta hai.
  event_queue.json   - WiFi down hone par events yahan jama hote hain
  device_state.json  - aaj kaunse compartments dispense ho chuke

Har write ATOMIC hai (tmp file -> rename). Flash write ke beech power chala
jaaye to aadha-likha JSON bachta hai, aur boot par schedule parse fail hone ka
matlab hai us din dawai na milna. Rename atomic hai, isliye ya poorana bundle
milega ya naya - beech ka kuch nahi.
"""
import os

try:
    import ujson as json
except ImportError:
    import json

import config


# ── Atomic file helpers ─────────────────────────────────────
def _read_json(path, default):
    try:
        with open(path, "r") as handle:
            return json.load(handle)
    except (OSError, ValueError) as exc:
        print("[STORAGE] %s padha nahi ja saka (%s) - default use kar rahe hain"
              % (path, exc))
        return default


def _write_json(path, data):
    tmp = path + ".tmp"
    try:
        with open(tmp, "w") as handle:
            json.dump(data, handle)
        try:
            os.remove(path)
        except OSError:
            pass                      # pehli baar likh rahe hain
        os.rename(tmp, path)
        return True
    except OSError as exc:
        print("[STORAGE] %s likha nahi ja saka: %s" % (path, exc))
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False


# ── Schedule bundle ─────────────────────────────────────────
_EMPTY_BUNDLE = {
    "schedule_version": 0,
    "compartments": [],
    "policy": {
        "dose_window_minutes": config.DEFAULT_DOSE_WINDOW_MIN,
        "catchup_window_minutes": config.DEFAULT_CATCHUP_WINDOW_MIN,
        "max_gate_opens": config.MAX_GATE_OPENS,
        "weight_settle_ms": config.WEIGHT_SETTLE_MS,
        "hand_detect_cm": config.HAND_DETECT_DIST_CM,
    },
    "total_weight_grams": 0.0,
    "is_gate_locked": False,
}


def load_schedule():
    """Cached bundle. File na ho to khaali bundle."""
    bundle = _read_json(config.SCHEDULES_FILE, None)
    if not isinstance(bundle, dict) or "compartments" not in bundle:
        return dict(_EMPTY_BUNDLE)

    # Purane bundle mein policy keys missing ho sakti hain
    policy = dict(_EMPTY_BUNDLE["policy"])
    policy.update(bundle.get("policy") or {})
    bundle["policy"] = policy
    return bundle


def save_schedule(bundle):
    ok = _write_json(config.SCHEDULES_FILE, bundle)
    if ok:
        print("[STORAGE] Bundle v%s saved (%d compartments)"
              % (bundle.get("schedule_version"), len(bundle.get("compartments", []))))
    return ok


def save_bundle_from_backend(data):
    """
    GET /iot/devices/{id}/config/ ka `data` seedha save karta hai.
    Khaali compartment list aaye to purana bundle rakhte hain - warna ek
    kharab response poore din ka schedule mita dega.
    """
    if not isinstance(data, dict) or not data.get("compartments"):
        print("[STORAGE] Bundle mein compartments nahi - cache rakh rahe hain")
        return False
    return save_schedule(data)


def get_compartments():
    return load_schedule().get("compartments", [])


def get_compartment(compartment_number):
    for comp in get_compartments():
        if comp.get("compartment_number") == compartment_number:
            return comp
    return None


def get_policy():
    return load_schedule()["policy"]


# ── Manual schedule editing (backend ke bina testing ke liye) ──
def add_compartment(compartment_number, time_hhmm, display_text="",
                    expected_dose_reduction_grams=0.0, time_slot="", enabled=True):
    """
    Manually ek compartment add/replace karo. Sirf bench testing ke liye -
    normal operation mein backend bundle bhejta hai aur agla sync isko
    overwrite kar dega.
    """
    bundle = load_schedule()
    comps = [c for c in bundle.get("compartments", [])
             if c.get("compartment_number") != compartment_number]

    comps.append({
        "compartment_number": compartment_number,
        "enabled": enabled,
        "time": time_hhmm,
        "time_slot": time_slot,
        "display_text": display_text,
        "audio_track": config.AUDIO_DOSE_REMINDER,
        "content_weight_grams": 0.0,
        "expected_dose_reduction_grams": expected_dose_reduction_grams,
        "medicines": [],
    })
    comps.sort(key=lambda c: c["compartment_number"])
    bundle["compartments"] = comps
    return save_schedule(bundle)


def update_compartment(compartment_number, **fields):
    bundle = load_schedule()
    for comp in bundle.get("compartments", []):
        if comp.get("compartment_number") == compartment_number:
            comp.update(fields)
            return save_schedule(bundle)
    print("[STORAGE] Compartment %s nahi mila" % compartment_number)
    return False


def delete_compartment(compartment_number):
    bundle = load_schedule()
    before = len(bundle.get("compartments", []))
    bundle["compartments"] = [c for c in bundle.get("compartments", [])
                              if c.get("compartment_number") != compartment_number]
    if len(bundle["compartments"]) == before:
        return False
    return save_schedule(bundle)


# ── Per-day dispense locks ──────────────────────────────────
def load_state():
    state = _read_json(config.STATE_FILE, None)
    if not isinstance(state, dict):
        state = {}
    return {
        "dispensed_day": state.get("dispensed_day", 0),
        "dispensed": state.get("dispensed", []),
        "gate_locked": state.get("gate_locked", False),
    }


def save_state(state):
    return _write_json(config.STATE_FILE, state)


def is_dispensed(compartment_number):
    return compartment_number in load_state()["dispensed"]


def mark_dispensed(compartment_number):
    """
    Dose dene se PEHLE call hota hai. Reboot ya doosra scheduler tick us dose
    ko dobara fire na kar de - double dose se missed dose behtar hai.
    """
    state = load_state()
    if compartment_number not in state["dispensed"]:
        state["dispensed"].append(compartment_number)
        save_state(state)


def reset_day(yyyymmdd):
    state = load_state()
    state["dispensed_day"] = yyyymmdd
    state["dispensed"] = []
    save_state(state)
    print("[STORAGE] Naya din %s - dispense locks clear" % yyyymmdd)


def rollover_if_new_day(yyyymmdd):
    """
    RTC ki date badalne par locks clear. yyyymmdd == 0 matlab clock padha hi
    nahi gaya - us case mein locks ko haath mat lagao, warna ek RTC glitch
    poore din ke doses dobara fire kar dega.
    """
    if not yyyymmdd:
        return False
    state = load_state()
    if state["dispensed_day"] != yyyymmdd:
        reset_day(yyyymmdd)
        return True
    return False


def set_gate_locked(locked):
    state = load_state()
    state["gate_locked"] = bool(locked)
    save_state(state)


def is_gate_locked():
    return load_state()["gate_locked"]


# ── Offline event queue ─────────────────────────────────────
def _load_queue():
    queue = _read_json(config.EVENT_QUEUE_FILE, None)
    return queue if isinstance(queue, list) else []


def queue_event(event):
    """
    Event ko flash mein daalo. Queue bhar jaaye to SABSE PURANA hataate hain -
    haal ka dose record purane heartbeat se zyada important hai.
    """
    queue = _load_queue()
    queue.append(event)

    dropped = 0
    while len(queue) > config.EVENT_QUEUE_CAPACITY:
        queue.pop(0)
        dropped += 1
    if dropped:
        print("[STORAGE] Queue full - %d purane event(s) drop" % dropped)

    _write_json(config.EVENT_QUEUE_FILE, queue)
    print("[STORAGE] Event queued (%d queue mein)" % len(queue))
    return True


def queue_count():
    return len(_load_queue())


def peek_batch(max_events):
    """Sabse purane `max_events` - abhi queue se hatate nahi."""
    return _load_queue()[:max_events]


def pop_front(count):
    """
    Utne hi events hatao jitne backend ne ACCEPT kiye. Partial failure par
    baaki queue mein rehte hain aur agli baar retry hote hain.
    """
    if count <= 0:
        return
    queue = _load_queue()
    remaining = queue[count:]
    _write_json(config.EVENT_QUEUE_FILE, remaining)
    print("[STORAGE] %d event(s) flushed, %d baaki" % (count, len(remaining)))


def clear_queue():
    _write_json(config.EVENT_QUEUE_FILE, [])
