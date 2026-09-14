import time
import network

from config import (
    WIFI_SSID,
    WIFI_PASSWORD,
    WIFI_TIMEOUT_SECONDS
)


# ============================================================
# WIFI INTERFACE
# ============================================================

wlan = network.WLAN(network.STA_IF)


def is_connected():
    return wlan.isconnected()


def connect_wifi():
    """
    Connect to configured WiFi network with timeout.
    Returns True if connected, False if failed.
    """
    if wlan.isconnected():
        print("[WIFI] Already connected. IP:", wlan.ifconfig()[0])
        return True

    print()
    print("[WIFI] Connecting to:", WIFI_SSID)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)

    start = time.time()
    while not wlan.isconnected():
        if time.time() - start > WIFI_TIMEOUT_SECONDS:
            print("[WIFI] Connection timeout! Running in offline mode.")
            return False
        time.sleep(0.5)
        print(".", end="")

    print()
    print("[WIFI] Connected successfully!")
    print("[WIFI] IP Address:", wlan.ifconfig()[0])
    return True


def disconnect_wifi():
    if wlan.isconnected():
        wlan.disconnect()
        wlan.active(False)
        print("[WIFI] Disconnected.")
