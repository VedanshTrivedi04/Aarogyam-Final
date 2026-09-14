from storage import update_schedule


# ============================================================
# RESCHEDULE TIME
# ============================================================

def reschedule_time(
    schedule_id,
    new_time
):

    return update_schedule(
        schedule_id,
        {
            "time": new_time
        }
    )


# ============================================================
# CHANGE MEDICINE
# ============================================================

def change_medicine(
    schedule_id,
    medicine,
    compartment
):

    return update_schedule(
        schedule_id,
        {
            "medicine": medicine,
            "compartment": compartment
        }
    )


# ============================================================
# CHANGE COMPLETE SCHEDULE
# ============================================================

def reschedule(
    schedule_id,
    new_time=None,
    medicine=None,
    compartment=None,
    dose=None
):

    data = {}


    if new_time is not None:

        data["time"] = new_time


    if medicine is not None:

        data["medicine"] = medicine


    if compartment is not None:

        data["compartment"] = compartment


    if dose is not None:

        data["dose"] = dose


    if not data:

        return False


    return update_schedule(
        schedule_id,
        data
    )