from machine import Pin
import time

from config import (
    ULTRASONIC_TRIG,
    ULTRASONIC_ECHO
)


# ============================================================
# ULTRASONIC
# ============================================================

trig = Pin(
    ULTRASONIC_TRIG,
    Pin.OUT
)

echo = Pin(
    ULTRASONIC_ECHO,
    Pin.IN
)


# ============================================================
# DISTANCE
# ============================================================

def get_distance():

    trig.value(0)

    time.sleep_us(2)


    trig.value(1)

    time.sleep_us(10)


    trig.value(0)


    timeout = 30000


    start = time.ticks_us()


    while echo.value() == 0:

        if time.ticks_diff(
            time.ticks_us(),
            start
        ) > timeout:

            return None


    pulse_start = time.ticks_us()


    while echo.value() == 1:

        if time.ticks_diff(
            time.ticks_us(),
            pulse_start
        ) > timeout:

            return None


    pulse_end = time.ticks_us()


    duration = time.ticks_diff(
        pulse_end,
        pulse_start
    )


    distance = (
        duration * 0.0343
    ) / 2


    return distance