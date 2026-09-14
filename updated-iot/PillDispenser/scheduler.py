from rtc import rtc

from storage import get_schedules


# ============================================================
# CURRENT TIME
# ============================================================

def get_current_datetime():

    return rtc.now()


# ============================================================
# CHECK SCHEDULES
# ============================================================

def get_due_schedules():

    now = rtc.now()


    current_date = (
        now[0],
        now[1],
        now[2]
    )


    current_time = "{:02d}:{:02d}".format(
        now[3],
        now[4]
    )


    schedules = get_schedules()


    due = []


    for schedule in schedules:

        if not schedule.get(
            "enabled",
            True
        ):

            continue


        scheduled_time = schedule.get(
            "time"
        )


        if scheduled_time != current_time:

            continue


        # Optional date filtering
        start_date = schedule.get(
            "start_date"
        )

        end_date = schedule.get(
            "end_date"
        )


        today_string = "{:04d}-{:02d}-{:02d}".format(
            now[0],
            now[1],
            now[2]
        )


        if start_date:

            if today_string < start_date:

                continue


        if end_date:

            if today_string > end_date:

                continue


        due.append(schedule)


    return due