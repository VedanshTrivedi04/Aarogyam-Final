"""
dispenser.py - Direct port of dispenser.h (preserves exact sensor sequence).
"""
import time

import config
import stepper
import servo_gate as servo
import ultrasonic


def dispense(compartment, medicine, dose=1):
    print()
    print("================================")
    print("DISPENSING STARTED")
    print("================================")
    print("Medicine:", medicine)
    print("Dose:", dose)
    print("Compartment:", compartment)

    # STEP 1 - MOVE STEPPER TO COMPARTMENT
    success = stepper.rotate_to_compartment(compartment)
    if not success:
        print("Stepper movement failed.")
        return "ERROR"

    # STEP 2 - DISPENSING WINDOW
    print()
    print("Dispensing window active for", config.DISPENSING_WINDOW_MINUTES, "minutes.")

    start_time = time.ticks_ms()
    window_ms = config.DISPENSING_WINDOW_MINUTES * 60 * 1000
    dose_taken = False

    # HAND DETECTION LOOP
    while time.ticks_diff(time.ticks_ms(), start_time) <= window_ms:
        distance = ultrasonic.get_distance()

        if distance < 0:
            print("NO ECHO")
            time.sleep_ms(300)
            continue

        print("Distance: {:.2f} cm".format(distance))

        # HAND DETECTED
        if distance <= config.HAND_DISTANCE_CM:
            print("HAND DETECTED")
            servo.open_servo()

            # Keep lid open while hand is present
            while True:
                if time.ticks_diff(time.ticks_ms(), start_time) > window_ms:
                    break

                distance = ultrasonic.get_distance()
                if distance < 0:
                    time.sleep_ms(200)
                    continue

                if distance > config.HAND_DISTANCE_CM:
                    print("HAND REMOVED")
                    break

                time.sleep_ms(200)

            # Close lid
            servo.close_servo()
            dose_taken = True
            break

        time.sleep_ms(200)

    # WINDOW END
    servo.close_servo()

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
