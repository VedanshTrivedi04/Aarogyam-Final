import time

from config import (
    HAND_DISTANCE,
    DISPENSING_WINDOW_MINUTES
)

from stepper import rotate_to_compartment

from servo import (
    open_servo,
    close_servo
)

from ultrasonic import get_distance


# ============================================================
# DISPENSING
# ============================================================

def dispense(
    compartment,
    medicine,
    dose=1
):

    print()
    print("================================")
    print("DISPENSING STARTED")
    print("================================")

    print("Medicine:", medicine)

    print("Dose:", dose)

    print(
        "Compartment:",
        compartment
    )


    # ========================================================
    # STEP 1 - MOVE TO COMPARTMENT
    # ========================================================

    success = rotate_to_compartment(
        compartment
    )


    if not success:

        print("Stepper movement failed.")

        return "ERROR"


    # ========================================================
    # DISPENSING WINDOW
    # ========================================================

    print()
    print(
        "Dispensing window active for",
        DISPENSING_WINDOW_MINUTES,
        "minutes."
    )

    start_time = time.ticks_ms()

    window_ms = (
        DISPENSING_WINDOW_MINUTES
        *
        60
        *
        1000
    )

    dose_taken = False


    # ========================================================
    # HAND DETECTION LOOP
    # ========================================================

    while (
        time.ticks_diff(
            time.ticks_ms(),
            start_time
        )
        <= window_ms
    ):

        distance = get_distance()

        if distance is None:

            print("NO ECHO")

            time.sleep_ms(300)

            continue

        print(
            "Distance:",
            round(distance, 2),
            "cm"
        )


        # ====================================================
        # HAND DETECTED
        # ====================================================

        if distance <= HAND_DISTANCE:

            print("HAND DETECTED")

            open_servo()


            # ----------------------------------------------
            # Keep lid open while hand is present
            # ----------------------------------------------

            while True:

                # Check whether window expired
                if (
                    time.ticks_diff(
                        time.ticks_ms(),
                        start_time
                    )
                    > window_ms
                ):

                    break

                distance = get_distance()

                if distance is None:

                    time.sleep_ms(200)

                    continue

                if distance > HAND_DISTANCE:

                    print("HAND REMOVED")

                    break

                time.sleep_ms(200)


            # ----------------------------------------------
            # Close lid
            # ----------------------------------------------

            close_servo()

            dose_taken = True
            break

        time.sleep_ms(200)


    # ========================================================
    # WINDOW END
    # ========================================================

    close_servo()

    print()
    print("================================")
    print("DISPENSING WINDOW CLOSED")
    print("ULTRASONIC OFF")
    print("LID LOCKED/CLOSED")
    print("================================")

    if dose_taken:
        print("[DISPENSER] Dose successfully taken by patient!")
        return "TAKEN"
    else:
        print("[DISPENSER] Window expired. Dose MISSED by patient.")
        return "MISSED"