import json


SCHEDULE_FILE = "schedules.json"
EVENT_QUEUE_FILE = "event_queue.json"


# ============================================================
# LOAD SCHEDULES
# ============================================================

def load_schedules():

    try:

        with open(
            SCHEDULE_FILE,
            "r"
        ) as file:

            data = json.load(file)

            if isinstance(data, list):

                return data

    except Exception:

        pass

    return []


# ============================================================
# SAVE SCHEDULES
# ============================================================

def save_schedules(schedules):

    with open(
        SCHEDULE_FILE,
        "w"
    ) as file:

        json.dump(
            schedules,
            file
        )


# ============================================================
# ADD SCHEDULE
# ============================================================

def add_schedule(schedule):

    schedules = load_schedules()

    schedules.append(schedule)

    save_schedules(schedules)

    return True


# ============================================================
# UPDATE SCHEDULE
# ============================================================

def update_schedule(
    schedule_id,
    new_data
):

    schedules = load_schedules()

    for schedule in schedules:

        if schedule.get(
            "schedule_id"
        ) == schedule_id:

            schedule.update(
                new_data
            )

            save_schedules(
                schedules
            )

            return True

    return False


# ============================================================
# DELETE SCHEDULE
# ============================================================

def delete_schedule(schedule_id):

    schedules = load_schedules()

    new_list = [
        s for s in schedules
        if s.get(
            "schedule_id"
        ) != schedule_id
    ]

    if len(new_list) == len(schedules):

        return False

    save_schedules(new_list)

    return True


# ============================================================
# GET SCHEDULES
# ============================================================

def get_schedules():

    return load_schedules()


# ============================================================
# SYNC BACKEND BUNDLE INTO LOCAL SCHEDULES
# ============================================================

def save_bundle_from_backend(bundle):
    """
    Translates the backend /config/ bundle into the local schedules format
    and updates schedules.json.
    """
    if not isinstance(bundle, dict):
        return False

    compartments = bundle.get("compartments", [])
    if not compartments:
        return False

    new_schedules = []
    for comp in compartments:
        comp_num = comp.get("compartment_number")
        slot_time = comp.get("time")  # "HH:MM"
        enabled = comp.get("enabled", True)

        medicines = comp.get("medicines", [])
        med_name = "Medicine"
        dose = 1
        if medicines:
            med_name = medicines[0].get("name", "Medicine")
            dose = medicines[0].get("qty_per_dose", 1)

        if comp_num and slot_time:
            new_schedules.append({
                "schedule_id": "BACKEND_C%d_%s" % (comp_num, slot_time.replace(":", "")),
                "medicine": med_name,
                "compartment": comp_num,
                "time": slot_time,
                "dose": dose,
                "enabled": enabled
            })

    if new_schedules:
        save_schedules(new_schedules)
        print("[STORAGE] Synced %d schedules from backend bundle." % len(new_schedules))
        return True

    return False


# ============================================================
# OFFLINE EVENT QUEUE
# ============================================================

def queue_event(event):
    """Save an event locally when device is offline."""
    events = get_queued_events()
    events.append(event)
    try:
        with open(EVENT_QUEUE_FILE, "w") as f:
            json.dump(events, f)
        print("[STORAGE] Event queued offline. Total queued:", len(events))
        return True
    except Exception as e:
        print("[STORAGE] Error saving offline event:", e)
        return False


def get_queued_events():
    try:
        with open(EVENT_QUEUE_FILE, "r") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def clear_queued_events():
    try:
        with open(EVENT_QUEUE_FILE, "w") as f:
            json.dump([], f)
        return True
    except Exception:
        return False