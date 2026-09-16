"""
stepper.py - Direct port of stepper.h (28BYJ-48 half-step sequence).
"""
import time
from machine import Pin

import config

# ============================================================
# 8-STEP HALF STEP SEQUENCE (28BYJ-48)
# ============================================================
HALF_STEP_SEQUENCE = [
    [1, 0, 0, 0],
    [1, 1, 0, 0],
    [0, 1, 0, 0],
    [0, 1, 1, 0],
    [0, 0, 1, 0],
    [0, 0, 1, 1],
    [0, 0, 0, 1],
    [1, 0, 0, 1],
]

_step_index = 0
_current_compartment = 1

_in1 = Pin(config.STEPPER_IN1, Pin.OUT)
_in2 = Pin(config.STEPPER_IN2, Pin.OUT)
_in3 = Pin(config.STEPPER_IN3, Pin.OUT)
_in4 = Pin(config.STEPPER_IN4, Pin.OUT)


def init_stepper():
    _in1.value(0)
    _in2.value(0)
    _in3.value(0)
    _in4.value(0)


def _set_coils(a, b, c, d):
    _in1.value(1 if a else 0)
    _in2.value(1 if b else 0)
    _in3.value(1 if c else 0)
    _in4.value(1 if d else 0)


def stop_motor():
    _set_coils(0, 0, 0, 0)


def step_motor(direction):
    global _step_index
    _step_index += direction
    if _step_index >= 8:
        _step_index = 0
    if _step_index < 0:
        _step_index = 7

    coils = HALF_STEP_SEQUENCE[_step_index]
    _set_coils(coils[0], coils[1], coils[2], coils[3])

    time.sleep_ms(config.STEP_DELAY_MS)


def reset_step_index():
    global _step_index
    _step_index = 0


def reset_compartment():
    global _current_compartment
    _current_compartment = 1


def get_current_compartment():
    return _current_compartment


def rotate_to_compartment(target):
    global _current_compartment

    if target < 1 or target > config.TOTAL_COMPARTMENTS:
        print("INVALID COMPARTMENT")
        return False

    difference = target - _current_compartment
    if difference < 0:
        difference += config.TOTAL_COMPARTMENTS

    steps = difference * config.STEPS_PER_COMPARTMENT

    print()
    print("Stepper Movement")
    print("Current:", _current_compartment)
    print("Target:", target)
    print("Compartments to advance:", difference)
    print("Steps:", steps)

    for _ in range(steps):
        step_motor(1)

    stop_motor()
    _current_compartment = target

    print("Reached Compartment:", _current_compartment)

    return True
