# Smart Pill Dispenser - MicroPython Firmware

Direct MicroPython port of `updated-iot-arduino/PillDispenser` — **same pins,
same sensor/actuator logic, same HTTP backend contract**. Only the language
changed (Arduino C++ → MicroPython); nothing about wiring or behaviour did.

---

## 📁 File Structure

```
updated-iot-micropython/PillDispenser/
├── main.py            # setup() + loop() + remote-command handler (== PillDispenser.ino)
├── config.py           # Hardware pins, WiFi, Backend URL & API endpoints
├── stepper.py           # 28BYJ-48 8-step half-step sequence & compartment rotation
├── hall_sensor.py       # HALL_PIN magnet detection & find_home() calibration
├── servo_gate.py        # SG90 50Hz PWM gate open (90°) & close (0°)
├── ultrasonic.py         # HC-SR04 pulse timing & distance calculation
├── rtc_ds3231.py         # Raw I2C DS3231 (no external library)
├── api_client.py         # urequests: time sync, schedules, events, heartbeat & command polling
└── dispenser.py          # Dispensing window with hand detection loop
```

---

## 🔌 Hardware Pin Configuration (identical to the Arduino version)

| Component | Physical Model | ESP32 GPIO Pins | Function |
| :--- | :--- | :--- | :--- |
| **RTC Module** | DS3231 (I2C 0x68) | SDA: `23`, SCL: `22` | Wall-clock timekeeper (IST) |
| **Hall Sensor** | A3144 | GPIO `33` (Input Pull-up) | Homing to Compartment 1 |
| **Stepper Motor** | 28BYJ-48 + ULN2003 | IN1: `13`, IN2: `14`, IN3: `27`, IN4: `26` | 4-Compartment rotary carousel |
| **Servo Gate** | SG90 Micro Servo | GPIO `25` (50Hz PWM) | Lid open (90°) & close (0°) |
| **Ultrasonic** | HC-SR04 | TRIG: `19`, ECHO: `18` | Patient hand detection (≤ 15 cm) |

### Communication (HTTP only, same as the Arduino version)

| Direction | Endpoint | Purpose |
| :--- | :--- | :--- |
| Device → Backend | `POST /api/v1/iot/events/` | Dose/boot events (also used to ACK commands) |
| Device → Backend | `POST /api/v1/iot/heartbeat/` | Heartbeat every 5 minutes |
| Device ← Backend | `GET /api/v1/iot/devices/{id}/config/` | Time sync + compartment schedules |
| Device ← Backend | `GET /api/v1/iot/devices/{id}/commands/` | Polled every 15s for remote commands (`PREPARE_COMPARTMENT`, `END_FILL_MODE`, `TRIGGER_DOSE`, `SYNC_CONFIG`, ...) |

---

## ⚙️ Setup

1. **Flash MicroPython** onto the ESP32 (via `esptool.py` or Thonny) — get the
   firmware `.bin` from https://micropython.org/download/ESP32_GENERIC/.

2. **Install `urequests`** (not built into MicroPython by default). With the
   board connected and WiFi already up in a REPL session:
   ```python
   import mip
   mip.install("urequests")
   ```
   Or manually copy `urequests.py` from
   https://github.com/micropython/micropython-lib onto the device's filesystem.

3. **Configure `config.py`**:
   - Update `WIFI_SSID` and `WIFI_PASSWORD`.
   - `BACKEND_URL` / `DEVICE_ID` / `DEVICE_API_KEY` / `API_*` are already set
     to match the deployed backend — same values as the Arduino `config.h`.

4. **Upload all files** in this folder to the board's root (`/`) using
   `mpremote`, `ampy`, Thonny, or rshell, e.g.:
   ```bash
   mpremote cp config.py stepper.py hall_sensor.py servo_gate.py ultrasonic.py rtc_ds3231.py api_client.py dispenser.py main.py :
   ```

5. **Reset the board.** MicroPython auto-runs `main.py` on boot — no manual
   "upload sketch" step like Arduino. Open a serial terminal (115200 baud,
   e.g. `mpremote` or `screen`/PuTTY) to watch the same log lines as the
   Arduino version (`[WIFI]`, `[API]`, `[EVENT]`, `[FILL]`, `[CMD]`, RTC prints).

---

## Notes on the port

- **Command polling / JSON parsing** deliberately keeps the same manual
  substring search (`find`/slicing) the Arduino version uses (`indexOf`/
  `substring`), rather than switching to `json.loads`, so the parsing
  behaviour against the real backend response is identical to the firmware
  already in use — not a guess at a JSON schema.
- **Servo duty formula** is bit-for-bit the same math as the Arduino LEDC
  16-bit config, just called via MicroPython's `duty_u16()`.
- **`FIRMWARE_VERSION`** is `"3.2.0-mpy"` instead of `"3.2.0-ino"` — the only
  intentional content difference — so the dashboard can tell which runtime a
  device is on. Everything else (pins, thresholds, endpoints, command
  handling, fill-mode flow) is unchanged.
