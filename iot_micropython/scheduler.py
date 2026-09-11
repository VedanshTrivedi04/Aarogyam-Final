"""
scheduler.py - RTC ke HH:MM ko schedules.json ke time se match karta hai.

Yahi poore v3 architecture ka dil hai: device KHUD decide karta hai ki dose ka
time aaya. Backend se "abhi dose hai kya" nahi poocha jaata, isliye WiFi na ho
to bhi dawai milti hai.

Time contract: schedules.json ka `time` device-local HH:MM hai, bilkul waise
hi jaise backend bhejta hai. RTC bhi local wall clock deta hai. Dono ko seedha
compare karo - koi UTC conversion nahi.
"""
import config
import rtc
import storage


def _parse_hhmm(value):
    """'HH:MM' -> minutes-since-midnight, ya None agar format galat."""
    try:
        hour_str, minute_str = str(value).split(":")
        hour = int(hour_str)
        minute = int(minute_str)
    except (ValueError, AttributeError):
        return None

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour * 60 + minute


def due_compartment(now_hour=None, now_minute=None):
    """
    Abhi jo compartment dispense hona chahiye uska dict, warna None.

    Slot apne scheduled minute se catchup_window tak fire hota hai - device
    band tha aur thodi der baad chalu hua to dawai phir bhi mil jaati hai,
    lekin ghanton baad nahi.
    """
    if now_hour is None or now_minute is None:
        now_hour, now_minute = rtc.get_hour_minute()

    # Clock hi bharosemand nahi to kuch mat karo. Galat waqt par galat
    # compartment kholne se behtar hai dose skip karna.
    if now_hour is None:
        return None

    now_minutes = now_hour * 60 + now_minute
    bundle = storage.load_schedule()
    catchup = bundle["policy"].get("catchup_window_minutes",
                                   config.DEFAULT_CATCHUP_WINDOW_MIN)

    for comp in bundle.get("compartments", []):
        if not comp.get("enabled"):
            continue

        number = comp.get("compartment_number")
        if number is None or storage.is_dispensed(number):
            continue

        slot_minutes = _parse_hhmm(comp.get("time"))
        if slot_minutes is None:
            print("[SCHED] Compartment %s ka time galat: %r" % (number, comp.get("time")))
            continue

        delta = now_minutes - slot_minutes
        # delta < 0 -> slot abhi aaya nahi. Aadhi raat ke aas-paas wrap NAHI
        # karte: 23:59 par 00:05 ka slot fire nahi hona chahiye.
        if 0 <= delta <= catchup:
            return comp

    return None


def check_day_rollover():
    """Din badla to dispense locks clear. True agar reset hua."""
    return storage.rollover_if_new_day(rtc.get_yyyymmdd())


def dose_window_ms():
    policy = storage.get_policy()
    return policy.get("dose_window_minutes", config.DEFAULT_DOSE_WINDOW_MIN) * 60000


def max_gate_opens():
    return storage.get_policy().get("max_gate_opens", config.MAX_GATE_OPENS)


def weight_settle_ms():
    return storage.get_policy().get("weight_settle_ms", config.WEIGHT_SETTLE_MS)


def describe():
    """Debug helper - abhi ka schedule print karo."""
    bundle = storage.load_schedule()
    state = storage.load_state()
    print("[SCHED] Bundle v%s | day=%s | dispensed=%s"
          % (bundle.get("schedule_version"), state["dispensed_day"], state["dispensed"]))

    for comp in bundle.get("compartments", []):
        print("[SCHED]   c%s %s %s dose=%.2fg %s" % (
            comp.get("compartment_number"),
            comp.get("time"),
            "ON " if comp.get("enabled") else "OFF",
            comp.get("expected_dose_reduction_grams", 0.0),
            "(dispensed)" if storage.is_dispensed(comp.get("compartment_number")) else "",
        ))
