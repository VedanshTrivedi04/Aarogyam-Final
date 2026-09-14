from machine import Pin, I2C
import time

from config import (
    RTC_SDA,
    RTC_SCL,
    RTC_ADDRESS
)


# ============================================================
# I2C
# ============================================================

i2c = I2C(
    0,
    scl=Pin(RTC_SCL),
    sda=Pin(RTC_SDA),
    freq=100000
)


# ============================================================
# BCD CONVERSION
# ============================================================

def dec_to_bcd(value):
    return ((value // 10) << 4) | (value % 10)


def bcd_to_dec(value):
    return ((value >> 4) * 10) + (value & 0x0F)


# ============================================================
# AM / PM → 24 HOUR CONVERSION
# ============================================================

def convert_to_24_hour(hour, am_pm):

    am_pm = am_pm.upper()

    if am_pm == "AM":

        if hour == 12:
            return 0

        return hour

    elif am_pm == "PM":

        if hour == 12:
            return 12

        return hour + 12

    else:

        raise ValueError("AM_PM must be AM or PM")


# ============================================================
# SET RTC
# ============================================================

def set_rtc(year, month, day, hour, minute, second):

    data = bytes([
        dec_to_bcd(second),
        dec_to_bcd(minute),
        dec_to_bcd(hour),
        dec_to_bcd(1),       # Day of week
        dec_to_bcd(day),
        dec_to_bcd(month),
        dec_to_bcd(year - 2000)
    ])

    i2c.writeto_mem(
        RTC_ADDRESS,
        0x00,
        data
    )

    print("RTC TIME SET SUCCESSFULLY")


# ============================================================
# READ RTC
# ============================================================

def read_rtc():

    data = i2c.readfrom_mem(
        RTC_ADDRESS,
        0x00,
        7
    )

    second = bcd_to_dec(data[0] & 0x7F)
    minute = bcd_to_dec(data[1] & 0x7F)
    hour = bcd_to_dec(data[2] & 0x3F)

    day = bcd_to_dec(data[4] & 0x3F)
    month = bcd_to_dec(data[5] & 0x1F)
    year = 2000 + bcd_to_dec(data[6])

    # Convert 24-hour → 12-hour
    if hour == 0:
        display_hour = 12
        am_pm = "AM"

    elif hour < 12:
        display_hour = hour
        am_pm = "AM"

    elif hour == 12:
        display_hour = 12
        am_pm = "PM"

    else:
        display_hour = hour - 12
        am_pm = "PM"

    print()
    print("RTC DATE: {:02d}/{:02d}/{}".format(
        day, month, year
    ))

    print("RTC TIME: {:02d}:{:02d}:{:02d} {}".format(
        display_hour,
        minute,
        second,
        am_pm
    ))


# ============================================================
# SET YOUR DATE & TIME HERE
# ============================================================

YEAR = 2026
MONTH = 9
DAY = 30

HOUR = 8
MINUTE = 28
SECOND = 0

AM_PM = "PM"


# ============================================================
# CONVERT AM/PM TO 24-HOUR
# ============================================================

HOUR_24 = convert_to_24_hour(
    HOUR,
    AM_PM
)


# ============================================================
# RUN ONCE
# ============================================================

print("Setting RTC...")

print(
    "Setting Date: {:02d}/{:02d}/{}".format(
        DAY,
        MONTH,
        YEAR
    )
)

print(
    "Setting Time: {:02d}:{:02d}:{:02d} {}".format(
        HOUR,
        MINUTE,
        SECOND,
        AM_PM
    )
)


set_rtc(
    YEAR,
    MONTH,
    DAY,
    HOUR_24,
    MINUTE,
    SECOND
)

time.sleep(1)

read_rtc()

print()
print("RTC SET COMPLETE")