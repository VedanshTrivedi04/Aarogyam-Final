from machine import Pin
import time

from config import (
    IN1,
    IN2,
    IN3,
    IN4,
    STEP_DELAY,
    STEPS_PER_COMPARTMENT,
    TOTAL_COMPARTMENTS
)


# ============================================================
# STEPPER PINS
# ============================================================

coil1 = Pin(IN1, Pin.OUT)
coil2 = Pin(IN2, Pin.OUT)
coil3 = Pin(IN3, Pin.OUT)
coil4 = Pin(IN4, Pin.OUT)


# ============================================================
# HALF STEP SEQUENCE
# ============================================================

half_step_sequence = [

    (1, 0, 0, 0),
    (1, 1, 0, 0),
    (0, 1, 0, 0),
    (0, 1, 1, 0),
    (0, 0, 1, 0),
    (0, 0, 1, 1),
    (0, 0, 0, 1),
    (1, 0, 0, 1)

]


step_index = 0

current_compartment = 1


# ============================================================
# COIL CONTROL
# ============================================================

def set_coils(a, b, c, d):

    coil1.value(a)
    coil2.value(b)
    coil3.value(c)
    coil4.value(d)


# ============================================================
# SINGLE STEP
# ============================================================

def step_motor(direction):

    global step_index

    step_index += direction

    if step_index >= 8:

        step_index = 0

    if step_index < 0:

        step_index = 7


    pattern = half_step_sequence[
        step_index
    ]


    set_coils(
        pattern[0],
        pattern[1],
        pattern[2],
        pattern[3]
    )


    time.sleep(STEP_DELAY)


# ============================================================
# STOP
# ============================================================

def stop_motor():

    set_coils(0, 0, 0, 0)


# ============================================================
# RESET STEP INDEX
# ============================================================

def reset_step_index():

    global step_index

    step_index = 0


# ============================================================
# RESET COMPARTMENT
# ============================================================

def reset_compartment():

    global current_compartment

    current_compartment = 1


# ============================================================
# GET CURRENT COMPARTMENT
# ============================================================

def get_current_compartment():

    return current_compartment


# ============================================================
# ROTATE TO TARGET
# ============================================================

def rotate_to_compartment(target):

    global current_compartment


    if target < 1 or target > TOTAL_COMPARTMENTS:

        print("INVALID COMPARTMENT")

        return False


    difference = (
        target -
        current_compartment
    )


    if difference < 0:

        difference += TOTAL_COMPARTMENTS


    steps = (
        difference *
        STEPS_PER_COMPARTMENT
    )


    print()
    print("Stepper Movement")
    print("Current:", current_compartment)
    print("Target:", target)
    print("Compartments:", difference)
    print("Steps:", steps)


    for i in range(steps):

        step_motor(1)


    stop_motor()


    current_compartment = target


    print(
        "Reached Compartment:",
        current_compartment
    )


    return True