"""
ultrasonic.py - Direct port of ultrasonic.h (HC-SR04).
"""
import time
from machine import Pin, time_pulse_us

import config

_trig = Pin(config.ULTRASONIC_TRIG, Pin.OUT)
_echo = Pin(config.ULTRASONIC_ECHO, Pin.IN)


def init_ultrasonic():
    _trig.value(0)


def get_distance():
    # Clean trigger pulse
    _trig.value(0)
    time.sleep_us(2)

    # 10 microsecond HIGH pulse
    _trig.value(1)
    time.sleep_us(10)
    _trig.value(0)

    # 30,000 microsecond timeout (approx 5 meters max)
    duration = time_pulse_us(_echo, 1, 30000)

    if duration < 0:
        return -1.0  # No echo / timeout

    # Distance calculation: (duration * 0.0343 cm/us) / 2
    distance = (duration * 0.0343) / 2.0
    return distance
