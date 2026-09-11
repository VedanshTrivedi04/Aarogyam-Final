"""
rtc_set.py - DS3231 ka date/time SET karta hai.

NORMAL OPERATION MEIN YE RUN NAHI KARNA. Sirf tab chalao jab:
  - Nayi CR2032 battery lagayi ho
  - RTC "lost power" bata raha ho aur WiFi/NTP available na ho
  - Pehli baar device setup kar rahe ho

Normal flow mein main.py khud NTP se sync kar leta hai.

Chalane ka tarika (REPL se):

    import rtc_set
    rtc_set.set_now(2026, 9, 12, 18, 15, 0)     # manual
    rtc_set.set_from_ntp()                       # WiFi chalu ho to behtar
    rtc_set.show()                               # abhi kya time hai
"""
import time

import rtc


def show():
    """Abhi DS3231 par kya time hai."""
    rtc.init()
    year, month, day, hour, minute, second = rtc.read_datetime()
    print("[RTC] %04d-%02d-%02d %02d:%02d:%02d" % (year, month, day, hour, minute, second))
    print("[RTC] Valid:", rtc.is_valid(), "| Lost power:", rtc.lost_power())
    return (year, month, day, hour, minute, second)


def set_now(year, month, day, hour, minute, second=0, weekday=1):
    """
    Manually time set karo. Hour 24-hour format mein (e.g. shaam 6:15 = 18, 15).
    weekday: 1=Monday ... 7=Sunday (DS3231 sirf store karta hai, use nahi karta).
    """
    if not (2024 <= year <= 2099):
        print("[RTC] Year 2024-2099 ke beech hona chahiye")
        return False
    if not (1 <= month <= 12 and 1 <= day <= 31):
        print("[RTC] Month/day galat hai")
        return False
    if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
        print("[RTC] Time galat hai - 24-hour format use karo")
        return False

    rtc.init()
    if rtc.write_datetime(year, month, day, hour, minute, second, weekday):
        print("[RTC] Set ho gaya ->", rtc.get_time_string())
        show()
        return True
    return False


def set_from_ntp():
    """
    WiFi se connect karke NTP se time lo aur DS3231 mein likh do.
    Sabse accurate tareeka - jab bhi WiFi available ho yahi use karo.
    """
    import network
    import ntptime

    import config

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("[RTC] WiFi connect kar rahe hain...")
        wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
        for _ in range(config.WIFI_CONNECT_TIMEOUT_S * 2):
            if wlan.isconnected():
                break
            time.sleep(0.5)

    if not wlan.isconnected():
        print("[RTC] WiFi nahi mila - set_now() se manually daal do")
        return False

    try:
        # ntptime UTC set karta hai; humein IST (UTC+5:30) chahiye.
        ntptime.settime()
        ist_seconds = time.time() + (5 * 3600) + 1800
        t = time.localtime(ist_seconds)
        rtc.init()
        ok = rtc.write_datetime(t[0], t[1], t[2], t[3], t[4], t[5], t[6] + 1)
        if ok:
            print("[RTC] NTP se set ho gaya (IST) ->", rtc.get_time_string())
            show()
        return ok
    except Exception as exc:
        print("[RTC] NTP fail:", exc)
        return False
