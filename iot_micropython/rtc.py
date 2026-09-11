"""
rtc.py - DS3231 se date/time READ karta hai.

DS3231 aur OLED dono GPIO 21/22 share karte hain (addresses alag: 0x68 / 0x3C).
SoftI2C use kiya hai kyunki wo bit-banged hai - dono modules apna instance bana
sakte hain bina ek doosre ko disturb kiye.

TIME CONTRACT: yahan se jo bhi time aata hai wo DEVICE-LOCAL wall clock hai
(IST). Backend bhi schedule times local HH:MM mein bhejta hai. Device par
kabhi UTC conversion mat karna - dono taraf same wall clock compare hota hai.
"""
import time

from machine import Pin, SoftI2C

import config

_i2c = None

# DS3231 register map: 0x00 sec, 0x01 min, 0x02 hour,
#                      0x03 weekday, 0x04 date, 0x05 month, 0x06 year
_REG_TIME = 0x00
_REG_STATUS = 0x0F
_OSF_BIT = 0x80          # Oscillator Stop Flag - power loss hua tha

available = False


def _bus():
    global _i2c
    if _i2c is None:
        _i2c = SoftI2C(scl=Pin(config.OLED_SCL), sda=Pin(config.OLED_SDA), freq=400000)
    return _i2c


def _bcd2dec(value):
    return (value >> 4) * 10 + (value & 0x0F)


def _dec2bcd(value):
    return ((value // 10) << 4) | (value % 10)


def init():
    """RTC detect karo. False matlab DS3231 nahi mila."""
    global available
    try:
        available = config.RTC_ADDR in _bus().scan()
    except Exception as exc:
        print("[RTC] I2C error:", exc)
        available = False

    if available:
        if lost_power():
            print("[RTC] DS3231 ne power kho diya tha - NTP sync ka intezaar")
        else:
            print("[RTC] DS3231 OK:", get_time_string())
    else:
        print("[RTC] DS3231 NOT FOUND - sirf system time par chalega")
    return available


def lost_power():
    """True agar oscillator ruk gaya tha - matlab time bharosemand nahi."""
    if not available:
        return True
    try:
        status = _bus().readfrom_mem(config.RTC_ADDR, _REG_STATUS, 1)[0]
        return bool(status & _OSF_BIT)
    except Exception:
        return True


def _clear_osf():
    try:
        bus = _bus()
        status = bus.readfrom_mem(config.RTC_ADDR, _REG_STATUS, 1)[0]
        bus.writeto_mem(config.RTC_ADDR, _REG_STATUS, bytes([status & ~_OSF_BIT]))
    except Exception as exc:
        print("[RTC] OSF clear failed:", exc)


def read_datetime():
    """
    (year, month, day, hour, minute, second) return karta hai.
    DS3231 na mile to ESP32 ke internal RTC par fallback.
    """
    if available:
        try:
            raw = _bus().readfrom_mem(config.RTC_ADDR, _REG_TIME, 7)
            second = _bcd2dec(raw[0] & 0x7F)
            minute = _bcd2dec(raw[1] & 0x7F)
            hour = _bcd2dec(raw[2] & 0x3F)      # 24-hour mode
            day = _bcd2dec(raw[4] & 0x3F)
            month = _bcd2dec(raw[5] & 0x1F)
            year = _bcd2dec(raw[6]) + 2000
            return (year, month, day, hour, minute, second)
        except Exception as exc:
            print("[RTC] Read failed:", exc)

    t = time.localtime()
    return (t[0], t[1], t[2], t[3], t[4], t[5])


def write_datetime(year, month, day, hour, minute, second, weekday=1):
    """DS3231 par time SET karta hai. rtc_set.py aur NTP sync use karte hain."""
    if not available:
        print("[RTC] DS3231 nahi hai - set nahi kar sakte")
        return False
    try:
        payload = bytes([
            _dec2bcd(second),
            _dec2bcd(minute),
            _dec2bcd(hour),          # bit6 = 0 -> 24-hour mode
            _dec2bcd(weekday),
            _dec2bcd(day),
            _dec2bcd(month),
            _dec2bcd(year - 2000),
        ])
        _bus().writeto_mem(config.RTC_ADDR, _REG_TIME, payload)
        _clear_osf()
        return True
    except Exception as exc:
        print("[RTC] Write failed:", exc)
        return False


def is_valid():
    """
    Clock bharosemand hai ya nahi. Scheduler ISKE bina dose fire NAHI karega -
    galat time par dawai dene se behtar hai na dena.
    """
    year = read_datetime()[0]
    return year >= 2024


def get_hour_minute():
    """(hour, minute) ya (None, None) agar clock bharosemand nahi."""
    year, _, _, hour, minute, _ = read_datetime()
    if year < 2024:
        return (None, None)
    return (hour, minute)


def get_yyyymmdd():
    """Din ka number jaise 20260912. Day rollover detect karne ke liye.
    0 matlab clock invalid - locks clear NAHI karne chahiye."""
    year, month, day, _, _, _ = read_datetime()
    if year < 2024:
        return 0
    return year * 10000 + month * 100 + day


def get_time_string():
    """OLED ke liye "HH:MM"."""
    _, _, _, hour, minute, _ = read_datetime()
    return "%02d:%02d" % (hour, minute)


def get_iso():
    """
    Events ka occurred_at - device-local wall clock, bina timezone offset ke.
    Backend isko device timezone (Asia/Kolkata) maan kar parse karta hai.
    """
    year, month, day, hour, minute, second = read_datetime()
    if year < 2024:
        return ""
    return "%04d-%02d-%02dT%02d:%02d:%02d" % (year, month, day, hour, minute, second)


def sync_from_system():
    """
    NTP se ESP32 ka system time set hone ke baad usko DS3231 mein likh do,
    taaki WiFi jaane par bhi time bacha rahe.
    """
    t = time.localtime()
    if t[0] < 2024:
        print("[RTC] System time abhi valid nahi - sync skip")
        return False
    ok = write_datetime(t[0], t[1], t[2], t[3], t[4], t[5], t[6] + 1)
    if ok:
        print("[RTC] NTP se sync ho gaya:", get_time_string())
    return ok
