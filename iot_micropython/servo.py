"""
servo.py - Lid OPEN / CLOSE.

SG90: 50 Hz PWM, ~0.5 ms (0 deg) se ~2.5 ms (180 deg) pulse.
MicroPython duty_u16 use karta hai, to 20 ms period ka fraction nikalte hain.

Movement ke baad PWM band kar dete hain - SG90 position hold karte waqt
buzz karta hai aur current kheenchta hai. Gate mechanically apni jagah rehta
hai, isliye hold karne ki zaroorat nahi.
"""
try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

from machine import Pin, PWM

import config

_pwm = None
is_open = False

_FREQ = 50
_MIN_US = 500       # 0 deg
_MAX_US = 2500      # 180 deg


def init():
    global _pwm
    _pwm = PWM(Pin(config.SERVO_PIN), freq=_FREQ)
    close()


def _write_angle(degrees):
    if _pwm is None:
        return
    degrees = max(0, min(180, degrees))
    pulse_us = _MIN_US + (_MAX_US - _MIN_US) * degrees // 180
    # duty_u16: 65535 = 100% of the 20 ms period
    duty = pulse_us * 65535 // 20000
    _pwm.duty_u16(duty)


async def _move_to(degrees):
    _write_angle(degrees)
    await asyncio.sleep_ms(400)      # servo ko pahunchne do
    _pwm.duty_u16(0)                 # phir PWM band - buzz/current band


async def open_lid():
    global is_open
    await _move_to(config.SERVO_OPEN_DEG)
    is_open = True
    print("[SERVO] Lid OPEN")


async def close_lid():
    global is_open
    await _move_to(config.SERVO_CLOSE_DEG)
    is_open = False
    print("[SERVO] Lid CLOSED")


def close():
    """Blocking close - sirf boot ke waqt, jab event loop nahi chal raha."""
    global is_open
    import time
    _write_angle(config.SERVO_CLOSE_DEG)
    time.sleep_ms(400)
    if _pwm:
        _pwm.duty_u16(0)
    is_open = False
