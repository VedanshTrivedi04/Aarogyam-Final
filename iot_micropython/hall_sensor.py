"""
hall_sensor.py - HOME position search aur verification.

Ye C++ firmware mein nahi tha, aur wahan ek asli problem thi: boot par wo maan
leta tha ki carousel compartment 1 par hai. Agar rotation ke beech power chala
jaaye, to position galat ho jaati thi aur device GALAT COMPARTMENT se dawai
de deta - silently, kisi ko pata bhi nahi chalta.

Hall sensor se boot par HOME dhoondh lete hain, to position hamesha pakki hai.

Magnet compartment 1 ke neeche lagana hai. A3144 jaisa open-collector sensor
magnet ke paas LOW jaata hai, isliye internal pull-up chahiye (config mein
GPIO 19 isliye chuna - 34/36/39 input-only hain, unmein pull-up nahi hota).
"""
try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

from machine import Pin

import config
import stepper

_pin = None


def init():
    global _pin
    pull = Pin.PULL_UP if config.HALL_ACTIVE_LOW else None
    _pin = Pin(config.HALL_PIN, Pin.IN, pull)
    print("[HALL] Sensor GPIO %d par ready (detected=%s)" % (config.HALL_PIN, is_at_home()))


def is_at_home():
    """True agar magnet abhi sensor ke saamne hai."""
    if _pin is None:
        return False
    value = _pin.value()
    return (value == 0) if config.HALL_ACTIVE_LOW else (value == 1)


async def find_home():
    """
    Carousel ko dheere-dheere ghumao jab tak magnet na mile.

    Milne par compartment 1 set ho jaata hai aur position_known=True.
    Poora ek revolution ghoomne ke baad bhi na mile to False - us case mein
    scheduler ko dose fire nahi karna chahiye, warna galat compartment khulega.
    """
    print("[HALL] HOME dhoondh rahe hain...")

    if is_at_home():
        stepper.set_position(1, known=True)
        print("[HALL] Pehle se HOME par hai - compartment 1")
        return True

    steps_taken = 0
    # Chhote chunks mein ghumao taaki har chunk ke baad sensor check kar sakein
    chunk = 8

    while steps_taken < config.HALL_SEARCH_MAX_STEPS:
        await stepper.step(chunk, clockwise=True)
        steps_taken += chunk

        if is_at_home():
            stepper.set_position(1, known=True)
            print("[HALL] HOME mil gaya (%d steps) - compartment 1" % steps_taken)
            return True

    print("[HALL] HOME NAHI MILA %d steps ke baad - magnet/wiring check karo" % steps_taken)
    stepper.set_position(1, known=False)
    return False


async def verify_home():
    """
    Sanity check: agar device sochta hai ki wo compartment 1 par hai, to
    magnet dikhna chahiye. Mismatch matlab position drift ho gaya - phir se
    home karo.

    Compartment 1 ke alawa kahin hai to kuch bhi conclude nahi kar sakte
    (magnet sirf ek jagah hai), isliye True return karte hain.
    """
    if stepper.current_compartment != 1:
        return True

    if is_at_home():
        return True

    print("[HALL] Position drift mila - dobara home kar rahe hain")
    return await find_home()
