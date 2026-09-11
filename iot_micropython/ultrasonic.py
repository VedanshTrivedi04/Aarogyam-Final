"""
ultrasonic.py - HC-SR04 distance aur hand detection.

Gate isi sensor se khulta hai, to false positive ka matlab hai dawai bina
maange khul jaana. Isliye hand_detected() ek single reading par bharosa nahi
karta - 3 mein se 2 readings threshold ke andar honi chahiye.
"""
try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

from machine import Pin, time_pulse_us

import config

_trig = None
_echo = None

# 30 ms timeout ~ 5 m range. Isse aage kuch bhi ho, humein matlab nahi.
_TIMEOUT_US = 30000


def init():
    global _trig, _echo
    _trig = Pin(config.ULTRASONIC_TRIG, Pin.OUT)
    _echo = Pin(config.ULTRASONIC_ECHO, Pin.IN)
    _trig.value(0)


def read_distance_cm():
    """
    Distance cm mein. -1 matlab koi echo nahi mila (timeout) - us case ko
    "koi haath nahi" samjho, "0 cm par haath hai" nahi.
    """
    if _trig is None:
        return -1

    _trig.value(0)
    time_pulse_us(_echo, 0, 1)      # settle
    _trig.value(1)
    # 10 us trigger pulse
    for _ in range(3):
        pass
    _trig.value(0)

    try:
        duration = time_pulse_us(_echo, 1, _TIMEOUT_US)
    except OSError:
        return -1                    # echo timeout

    if duration < 0:
        return -1

    # Sound: 340 m/s -> 0.034 cm/us, aur echo do taraf jaata hai
    return (duration * 0.034) / 2


def hand_detected():
    """
    True agar haath dispensing window mein hai.

    3 readings, 2 agree karein to hi haan. Ek spike se gate nahi khulna
    chahiye - sensor noise ya guzarta hua kapda gate open kar de to dose
    count galat ho jaayega.
    """
    hits = 0
    for _ in range(3):
        distance = read_distance_cm()
        if 0 < distance <= config.HAND_DETECT_DIST_CM:
            hits += 1
    return hits >= 2


async def wait_until_clear(timeout_ms=5000):
    """
    Haath hatne ka intezaar. True matlab window saaf ho gaya,
    False matlab timeout - caller ko gate waise bhi band kar dena chahiye.
    """
    elapsed = 0
    while elapsed < timeout_ms:
        if not hand_detected():
            return True
        await asyncio.sleep_ms(200)
        elapsed += 200
    return False
