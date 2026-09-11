"""
loadcell.py - HX711 (1 kg load cell) driver.

IMPORTANT: ek hi load cell POORE carousel ke neeche hai. Har reading TOTAL
weight hai, kisi ek compartment ki nahi. Per-compartment weight backend
nikalta hai - running reference se subtract karke. Device sirf number bhejta
hai, koi interpretation nahi karta.

Timing note: HX711 ka SCK pulse 60 us se lamba ho jaaye to chip power-down
mode mein chala jaata hai. MicroPython mein GC ya interrupt beech mein aa
sakta hai, isliye 25 pulses ke dauraan interrupts band karte hain.
"""
try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

import machine
from machine import Pin

import config

_dout = None
_sck = None

_offset = 0          # tare
_scale = config.LOADCELL_SCALE
last_grams = 0.0
available = False


def init():
    global _dout, _sck, available
    # GPIO 35 input-only hai - DOUT hi yahan lag sakta hai, SCK nahi
    _dout = Pin(config.LOADCELL_DOUT, Pin.IN)
    _sck = Pin(config.LOADCELL_SCK, Pin.OUT)
    _sck.value(0)

    available = is_ready(timeout_ms=1000)
    if available:
        print("[HX711] Ready")
        tare()
    else:
        print("[HX711] NOT READY - wiring check karo (DOUT=%d, SCK=%d)"
              % (config.LOADCELL_DOUT, config.LOADCELL_SCK))
    return available


def is_ready(timeout_ms=0):
    """DOUT LOW matlab naya sample taiyar hai."""
    if _dout is None:
        return False
    if timeout_ms <= 0:
        return _dout.value() == 0

    import time
    deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        if _dout.value() == 0:
            return True
        time.sleep_ms(10)
    return False


def _read_raw():
    """Ek 24-bit signed sample. None agar chip taiyar nahi."""
    if not is_ready(timeout_ms=200):
        return None

    irq_state = machine.disable_irq()
    try:
        value = 0
        for _ in range(24):
            _sck.value(1)
            value = (value << 1) | _dout.value()
            _sck.value(0)
        # 25th pulse -> channel A, gain 128
        _sck.value(1)
        _sck.value(0)
    finally:
        machine.enable_irq(irq_state)

    # 24-bit two's complement -> signed
    if value & 0x800000:
        value -= 0x1000000
    return value


def read_average(samples=5):
    """`samples` raw readings ka average. None agar ek bhi na mile."""
    total = 0
    count = 0
    for _ in range(samples):
        raw = _read_raw()
        if raw is not None:
            total += raw
            count += 1
    if count == 0:
        return None
    return total / count


def tare(samples=10):
    """Abhi ka weight zero maan lo (khaali carousel)."""
    global _offset
    average = read_average(samples)
    if average is None:
        print("[HX711] Tare fail - chip ready nahi")
        return False
    _offset = average
    print("[HX711] Tared (offset=%d)" % _offset)
    return True


def get_weight_grams(samples=5):
    """Grams mein weight. Chip na mile to last known value."""
    global last_grams
    average = read_average(samples)
    if average is None:
        print("[HX711] Ready nahi - last value return kar rahe hain")
        return last_grams

    grams = (average - _offset) / _scale
    if grams < 0:
        grams = 0.0          # zero ke aas-paas ka drift clamp
    last_grams = grams
    return grams


async def get_stable_weight_grams():
    """
    5 readings ka MEDIAN.

    Poora dose decision inhi grams par tika hai, aur stepper rukne ke turant
    baad carousel thoda hilta rehta hai. Median un spikes ko phenk deta hai;
    average unhe apne andar mila leta hai.
    """
    readings = []
    for _ in range(5):
        readings.append(get_weight_grams(samples=3))
        await asyncio.sleep_ms(120)

    readings.sort()
    median = readings[len(readings) // 2]
    print("[HX711] Stable weight: %.2f g" % median)
    return median
