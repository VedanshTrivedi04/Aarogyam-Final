"""
display.py - SSD1306 OLED screens.

`ssd1306.py` driver device par hona chahiye:
    mpremote mip install ssd1306
Na mile to sab functions chup-chaap no-op ho jaate hain - OLED na hone se
dawai dena nahi rukna chahiye.

DS3231 ke saath GPIO 21/22 share karta hai. SoftI2C isliye ki dono modules
apna instance bana saken.
"""
from machine import Pin, SoftI2C

import config

_oled = None
available = False

_LINE_CHARS = 21        # 128 px / 6 px per char


def init():
    global _oled, available
    try:
        import ssd1306
    except ImportError:
        print("[OLED] ssd1306 driver nahi mila - display disabled")
        available = False
        return False

    try:
        i2c = SoftI2C(scl=Pin(config.OLED_SCL), sda=Pin(config.OLED_SDA), freq=400000)
        _oled = ssd1306.SSD1306_I2C(config.OLED_WIDTH, config.OLED_HEIGHT,
                                    i2c, addr=config.OLED_ADDR)
        available = True
        message("MedAdhere v" + config.FIRMWARE_VERSION, "Booting...")
        print("[OLED] Ready")
    except Exception as exc:
        print("[OLED] Init failed:", exc)
        available = False
    return available


def _lines(*rows):
    if not available:
        return
    try:
        _oled.fill(0)
        y = 0
        for row in rows:
            if row is None:
                continue
            for chunk_start in range(0, len(row), _LINE_CHARS):
                if y > 56:
                    break
                _oled.text(row[chunk_start:chunk_start + _LINE_CHARS], 0, y)
                y += 10
        _oled.show()
    except Exception as exc:
        print("[OLED] Draw failed:", exc)


def message(line1, line2="", line3=""):
    _lines(line1, line2, line3)


def idle(time_string, status_line=""):
    _lines("MedAdhere Ready", time_string, status_line)


def dose_info(compartment, display_text):
    rows = ["Compartment %d" % compartment]
    for part in str(display_text).split("\n"):
        if part:
            rows.append(part)
    _lines(*rows[:5])


def fill_mode(compartment, medicine_name):
    _lines("=== FILL MODE ===",
           "Compartment: %s" % compartment,
           "Add medicine:",
           str(medicine_name)[:_LINE_CHARS],
           "Confirm on portal ->")


def gate_locked():
    _lines("!! GATE LOCKED !!",
           "Dose window closed.",
           "Caregiver must",
           "unlock from app.")


def dose_result(status):
    if status == "taken":
        _lines("Dose OK!", "Full dose confirmed.")
    elif status == "partial":
        _lines("Partial", "Dose incomplete.")
    elif status == "pending_sync":
        _lines("Dose recorded", "Will sync when", "online")
    else:
        _lines("Missed!", "No dose detected.")


def clear():
    if available:
        try:
            _oled.fill(0)
            _oled.show()
        except Exception:
            pass
