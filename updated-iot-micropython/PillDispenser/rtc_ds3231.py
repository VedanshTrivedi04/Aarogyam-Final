"""
rtc_ds3231.py - Direct port of rtc_ds3231.h (raw I2C DS3231, no library).
Same register layout / BCD conversion as the Arduino Wire implementation.
"""
from machine import I2C, Pin

import config

_i2c = I2C(0, scl=Pin(config.RTC_SCL), sda=Pin(config.RTC_SDA), freq=100000)


class DateTime:
    def __init__(self, year, month, day, hour, minute, second):
        self.year = year
        self.month = month
        self.day = day
        self.hour = hour
        self.minute = minute
        self.second = second


def _bcd_to_dec(val):
    return ((val >> 4) * 10) + (val & 0x0F)


def _dec_to_bcd(val):
    return ((val // 10) << 4) | (val % 10)


def init_rtc():
    if config.RTC_ADDRESS not in _i2c.scan():
        print("RTC NOT FOUND on I2C bus!")
        return False
    return True


def read_rtc():
    try:
        _i2c.writeto(config.RTC_ADDRESS, bytes([0x00]))  # Start at register 0
        data = _i2c.readfrom(config.RTC_ADDRESS, 7)
    except OSError:
        return DateTime(2026, 1, 1, 0, 0, 0)

    second = _bcd_to_dec(data[0] & 0x7F)
    minute = _bcd_to_dec(data[1] & 0x7F)
    hour = _bcd_to_dec(data[2] & 0x3F)
    # data[3] = day of week (ignored)
    day = _bcd_to_dec(data[4] & 0x3F)
    month = _bcd_to_dec(data[5] & 0x1F)
    year = 2000 + _bcd_to_dec(data[6])

    return DateTime(year, month, day, hour, minute, second)


def set_rtc(year, month, day, hour, minute, second):
    buf = bytes([
        0x00,  # Register pointer
        _dec_to_bcd(second),
        _dec_to_bcd(minute),
        _dec_to_bcd(hour),
        _dec_to_bcd(1),  # Day of week (1)
        _dec_to_bcd(day),
        _dec_to_bcd(month),
        _dec_to_bcd(year - 2000 if year >= 2000 else year),
    ])
    _i2c.writeto(config.RTC_ADDRESS, buf)

    print("[RTC] Time set to: {:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
        year, month, day, hour, minute, second))


def get_rtc_iso_string():
    dt = read_rtc()
    return "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}".format(
        dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)


def check_rtc():
    if not init_rtc():
        return False

    now = read_rtc()
    print("RTC Date: {:02d}/{:02d}/{:04d}".format(now.day, now.month, now.year))
    print("RTC Time: {:02d}:{:02d}:{:02d}".format(now.hour, now.minute, now.second))
    return True
