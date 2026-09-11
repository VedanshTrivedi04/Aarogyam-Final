"""
stepper.py - 28BYJ-48 compartment movement aur step count.

4096 half-steps = 1 revolution = 4 compartments, to 1 compartment = 1024 steps.
Carousel sirf ek hi direction (clockwise) mein ghumta hai - gear backlash se
position error na ho isliye.

Async hai: har step ke beech await karta hai taaki rotation ke dauraan
scheduler, WebSocket aur sensors bhooke na rahein.
"""
try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

from machine import Pin

import config

# Half-step sequence - full-step se smooth aur zyada torque
_HALF_STEP = (
    (1, 0, 0, 0), (1, 1, 0, 0), (0, 1, 0, 0), (0, 1, 1, 0),
    (0, 0, 1, 0), (0, 0, 1, 1), (0, 0, 0, 1), (1, 0, 0, 1),
)

_pins = []
_step_index = 0

# Kaunsa compartment abhi gate ke saamne hai. HOME milne tak bharosemand nahi.
current_compartment = 1
position_known = False


def init():
    global _pins
    _pins = [
        Pin(config.STEPPER_IN1, Pin.OUT),
        Pin(config.STEPPER_IN2, Pin.OUT),
        Pin(config.STEPPER_IN3, Pin.OUT),
        Pin(config.STEPPER_IN4, Pin.OUT),
    ]
    release()


def release():
    """
    Coils band karo. Ye zaroori hai - 28BYJ-48 ko energised chhod dene se
    driver aur motor dono garam ho jaate hain.
    """
    for pin in _pins:
        pin.value(0)


def _apply(pattern):
    for pin, value in zip(_pins, pattern):
        pin.value(value)


async def step(count, clockwise=True):
    """`count` half-steps ghumao. Beech mein await karta hai."""
    global _step_index

    for _ in range(count):
        _apply(_HALF_STEP[_step_index])
        _step_index = (_step_index + 1) % 8 if clockwise else (_step_index + 7) % 8
        await asyncio.sleep_ms(config.STEP_DELAY_MS)

    release()


async def rotate_to(target_compartment):
    """
    Target compartment tak ghumao. Hamesha aage (clockwise) jaata hai, isliye
    4 se 1 jaane ke liye 3 slots aage ghumega, peeche nahi.
    """
    global current_compartment

    if target_compartment == current_compartment:
        print("[STEPPER] Pehle se compartment %d par hai" % target_compartment)
        return 0

    diff = target_compartment - current_compartment
    if diff < 0:
        diff += config.TOTAL_COMPARTMENTS

    steps = diff * config.STEPS_PER_SLOT
    await step(steps, clockwise=True)
    current_compartment = target_compartment

    print("[STEPPER] Compartment %d par pahunch gaye (%d steps)" % (target_compartment, steps))
    return steps


def set_position(compartment, known=True):
    """HOME milne ke baad hall_sensor isko call karta hai."""
    global current_compartment, position_known
    current_compartment = compartment
    position_known = known
