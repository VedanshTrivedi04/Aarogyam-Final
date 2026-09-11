"""
audio.py - DFPlayer Mini voice prompts + buzzer/LED alerts.

Patient zyadatar budzurg hain - chhoti OLED screen padhna mushkil hai, isliye
Hindi voice prompt hi asli feedback hai. DFPlayer na mile to buzzer fallback
rehta hai.

DFPlayer serial protocol: 10-byte frame
    7E FF 06 <CMD> <FEEDBACK> <PARAM_HI> <PARAM_LO> <CKSUM_HI> <CKSUM_LO> EF
"""
import time

from machine import Pin, UART

import config

_uart = None
_busy_pin = None
_buzzer = None
_led = None
dfplayer_ready = False

_CMD_PLAY_TRACK = 0x03
_CMD_SET_VOLUME = 0x06
_CMD_RESET = 0x0C


def init():
    global _uart, _busy_pin, _buzzer, _led, dfplayer_ready

    _buzzer = Pin(config.BUZZER_PIN, Pin.OUT)
    _led = Pin(config.LED_PIN, Pin.OUT)
    _buzzer.value(0)
    _led.value(0)

    try:
        _uart = UART(config.DFPLAYER_UART, baudrate=9600,
                     tx=config.DFPLAYER_TX, rx=config.DFPLAYER_RX)
        _busy_pin = Pin(config.DFPLAYER_BUSY, Pin.IN, Pin.PULL_UP)

        time.sleep_ms(1000)          # DFPlayer ko boot hone do
        _send(_CMD_RESET, 0)
        time.sleep_ms(1500)          # reset ke baad ~1.5 s
        _send(_CMD_SET_VOLUME, config.DFPLAYER_VOLUME)
        dfplayer_ready = True
        print("[DFPlayer] Ready - volume", config.DFPLAYER_VOLUME)
    except Exception as exc:
        dfplayer_ready = False
        print("[DFPlayer] Init failed:", exc, "- buzzer hi chalega")

    return dfplayer_ready


def _send(command, param):
    if _uart is None:
        return
    param_hi = (param >> 8) & 0xFF
    param_lo = param & 0xFF
    # Checksum = 0 - sum(bytes 1..6), 16-bit two's complement
    checksum = -(0xFF + 0x06 + command + 0x00 + param_hi + param_lo) & 0xFFFF
    frame = bytes([
        0x7E, 0xFF, 0x06, command, 0x00, param_hi, param_lo,
        (checksum >> 8) & 0xFF, checksum & 0xFF, 0xEF,
    ])
    _uart.write(frame)


def play(track):
    """SD card se track number bajao (0001.mp3 = track 1)."""
    if not dfplayer_ready:
        print("[DFPlayer] Ready nahi - track %d skip" % track)
        beep(2, 120)
        return
    _send(_CMD_PLAY_TRACK, track)
    print("[DFPlayer] Playing track", track)


def is_busy():
    """BUSY pin LOW matlab abhi baj raha hai."""
    if _busy_pin is None:
        return False
    return _busy_pin.value() == 0


def beep(times=1, duration_ms=100):
    if _buzzer is None:
        return
    for _ in range(times):
        _buzzer.value(1)
        time.sleep_ms(duration_ms)
        _buzzer.value(0)
        time.sleep_ms(60)


def alert():
    """Buzzer + LED - missed dose / gate lock ke liye."""
    if _buzzer is None:
        return
    for _ in range(3):
        _buzzer.value(1)
        _led.value(1)
        time.sleep_ms(300)
        _buzzer.value(0)
        _led.value(0)
        time.sleep_ms(200)


def led(on):
    if _led is not None:
        _led.value(1 if on else 0)
