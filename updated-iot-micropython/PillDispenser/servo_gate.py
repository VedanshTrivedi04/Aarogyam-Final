"""
servo_gate.py - Direct port of servo_gate.h (SG90 lid, 50Hz PWM).

Same duty formula as the Arduino version's 16-bit LEDC config, just written
against MicroPython's duty_u16 (0-65535 range):
    duty = 1638 + (angle / 180) * (8192 - 1638)
1638/65535 = 0.5ms pulse (0 deg), 8192/65535 = 2.5ms pulse (180 deg) @ 50Hz.
"""
from machine import Pin, PWM

import config

_SERVO_FREQ = 50

_pwm = PWM(Pin(config.SERVO_PIN))
_pwm.freq(_SERVO_FREQ)


def init_servo():
    _pwm.freq(_SERVO_FREQ)


def set_servo_angle(angle):
    if angle < 0:
        angle = 0
    if angle > 180:
        angle = 180

    duty = int(1638 + (angle / 180.0) * (8192 - 1638))
    _pwm.duty_u16(duty)


def open_servo():
    set_servo_angle(config.SERVO_OPEN_ANGLE)
    print("LID OPEN")


def close_servo():
    set_servo_angle(config.SERVO_CLOSED_ANGLE)
    print("LID CLOSED")
