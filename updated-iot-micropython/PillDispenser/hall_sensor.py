"""
hall_sensor.py - Direct port of hall_sensor.h (A3144 home-position detection).
"""
import time
from machine import Pin

import config
import stepper

_hall = Pin(config.HALL_PIN, Pin.IN, Pin.PULL_UP)


def init_hall_sensor():
    pass  # pin already configured as INPUT_PULLUP above


def is_home():
    # A3144 Hall sensor goes LOW when magnet is detected
    return _hall.value() == 0


def find_home():
    print()
    print("Searching HOME...")

    # Step motor forward until magnet detected (HALL_PIN == LOW)
    while _hall.value() == 1:
        stepper.step_motor(1)

    stepper.stop_motor()
    time.sleep_ms(300)

    stepper.reset_step_index()
    stepper.reset_compartment()

    print("HOME FOUND")
    print("Current Compartment = 1")

    return True
