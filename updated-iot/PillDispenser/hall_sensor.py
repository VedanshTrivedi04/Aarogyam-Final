from machine import Pin
import time

from config import HALL_PIN

from stepper import (
    step_motor,
    stop_motor,
    reset_step_index,
    reset_compartment
)


# ============================================================
# HALL SENSOR
# ============================================================

hall = Pin(
    HALL_PIN,
    Pin.IN,
    Pin.PULL_UP
)


# ============================================================
# CHECK HOME
# ============================================================

def is_home():

    return hall.value() == 0


# ============================================================
# FIND HOME
# ============================================================

def find_home():

    print()
    print("Searching HOME...")


    while hall.value() == 1:

        step_motor(1)


    stop_motor()

    time.sleep_ms(300)


    reset_step_index()

    reset_compartment()


    print("HOME FOUND")

    print("Current Compartment = 1")


    return True