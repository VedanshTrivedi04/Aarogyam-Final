# MedAdhere ESP32 Firmware v3.0 — Setup & Connection Guide

## Kya badla hai (v2.1 → v3.0)

Pehle **backend decide karta tha** ki dose ka time aaya ya nahi. ESP32 har 60
second `schedule/current/` poll karta tha aur har 10 second commands poll karta
tha — roughly **10,400 requests/day**, aur WiFi jaane par dispenser bekaar.

Ab **device khud time owner hai**:

- Backend ek baar **versioned config bundle** bhejta hai → ESP32 NVS flash mein cache karta hai
- **DS3231 RTC** locally dose fire karta hai — koi network round-trip nahi
- Commands **WebSocket** se push hote hain (10-second poll khatam)
- WiFi down ho to bhi dose milta hai; events flash mein queue hote hain aur baad mein sync

Steady state: **~200 requests/day**, aur command latency sub-second.

---

## 📦 Required Libraries (Arduino IDE mein install karo)

| Library | Install Name | Version |
|---------|-------------|---------|
| ArduinoJson | `ArduinoJson` by bblanchon | v7.x |
| ESP32Servo | `ESP32Servo` by Kevin Harrington | latest |
| Adafruit SSD1306 | `Adafruit SSD1306` | latest |
| Adafruit GFX | `Adafruit GFX Library` | latest |
| RTClib | `RTClib` by Adafruit | v2.x |
| HX711 | `HX711` by bogde | latest |
| DFPlayer Mini | `DFRobotDFPlayerMini` | latest |
| **WebSockets** | `WebSockets` by **Markus Sattler** | **v2.4+** ← NEW in v3.0 |

> ⚠️ WebSocket library ke bahut clones hain. **Markus Sattler (Links2004)** wala
> hi install karo — baaki ke saath `WebSocketsClient.h` compile nahi hoga.

**Install:** Arduino IDE → Tools → Manage Libraries → naam likhke install karo

---

## ⚙️ Arduino IDE Settings

```
Board:     ESP32 Dev Module
Port:      COM3 (ya jo bhi dikhaye)
Upload Speed: 921600
Flash Size: 4MB (32Mb)
Partition Scheme: Default 4MB with spiffs
```

---

## 🔌 Hardware Wiring

```
ESP32 Pin    →   Component
─────────────────────────────────────────
─ 28BYJ-48 Stepper (ULN2003) ────────────────────
GPIO 13      →   ULN2003 IN1
GPIO 12      →   ULN2003 IN2
GPIO 14      →   ULN2003 IN3
GPIO 27      →   ULN2003 IN4
─ Servo (Gate) ───────────────────────────────
GPIO 25      →   Servo Signal
─ HC-SR04 Ultrasonic ──────────────────────────
GPIO 26      →   HC-SR04 TRIG
GPIO 33      →   HC-SR04 ECHO
─ HX711 Load Cell (1 kg) ──────────────────────
GPIO 35      →   HX711 DOUT   (input-only pin)
GPIO 18      →   HX711 SCK
─ DFPlayer Mini MP3 ───────────────────────────
GPIO 16      →   DFPlayer TX  (ESP32 RX2)
GPIO 17      →   DFPlayer RX  (1kΩ resistor ke through)
GPIO 15      →   DFPlayer BUSY (optional, LOW = playing)
─ I2C Bus (shared: OLED + DS3231 RTC) ─────────────
GPIO 21      →   SDA (OLED + DS3231 — wired together)
GPIO 22      →   SCL (OLED + DS3231 — wired together)
─ Misc ────────────────────────────────────────
GPIO 32      →   Buzzer (+)
GPIO  2      →   LED (built-in)
GPIO 34      →   Battery voltage divider (ADC)
3.3V         →   OLED VCC, DS3231 VCC
GND          →   All GND
```

> ⚠️ **I2C:** DS3231 aur OLED dono GPIO 21/22 share karte hain.
> Addresses alag hain (OLED=0x3C, DS3231=0x68) — conflict nahi hoga.

> ⚠️ **Load cell placement:** Ek hi load cell **poore carousel ke neeche** hai,
> isliye reading हमेशा **total weight** hoti hai — kisi single compartment ki
> nahi. Backend running reference se subtract karke per-compartment weight
> nikalta hai. Cell ko center mein mount karo warna rotation par reading shift hogi.

---

## 🚀 Backend Se Connect Karna

### Step 1 — Backend chalu karo (ASGI, WebSocket ke liye zaroori)

```bash
cd backend
docker compose up -d
```

> ⚠️ WebSocket ke liye **Daphne/ASGI** chahiye. `manage.py runserver` se
> WebSocket kaam nahi karega — `daphne config.asgi:application` use karo.

### Step 2 — Device register karo

```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@medadhere.com","password":"admin123"}'

# Response se JWT token lo, phir:
curl -X POST http://localhost:8000/api/v1/iot/devices/link/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"device_name":"My Pill Dispenser","device_type":"CIRCULAR_PILL_DISPENSER"}'
```

### Step 3 — Response se copy karo

```json
{
  "data": {
    "id":      "PASTE_IN_config.h → DEVICE_ID",
    "api_key": "PASTE_IN_config.h → DEVICE_API_KEY"
  }
}
```

### Step 4 — config.h update karo

```cpp
#define WIFI_SSID      "YourWiFiName"
#define WIFI_PASSWORD  "YourWiFiPassword"
#define BACKEND_HOST   "192.168.1.100"   // apne PC ka IP (NO http://, NO port)
#define BACKEND_PORT   8000
#define DEVICE_API_KEY "copy from step 3"
#define DEVICE_ID      "copy from step 3"
```

> ⚠️ v3.0 mein `BACKEND_HOST` aur `BACKEND_PORT` **alag** hain (WebSocket ko
> host/port separately chahiye). `BACKEND_URL` inhi se ban jaata hai.

### Step 5 — Compartments setup + medicines fill karo

Dashboard se ya API se: compartments banao, medicine add karo, phir guided fill
chalao. Har compartment fill karne ke baad load cell measure karta hai. Iske
bina `enabled: false` rahega aur **dose fire nahi hoga** (jaan-boojh kar —
bina measured weight ke verification impossible hai).

### Step 6 — Flash karo

Arduino IDE mein `esp32_firmware.ino` kholo → **Upload**

---

## 🔄 Communication Flow

```
ESP32 Boot
  ├─ HW init: OLED + DS3231 + HX711 + DFPlayer
  ├─ NVS se cached schedule + queued events restore   ← WiFi se PEHLE
  ├─ WiFi connect → NTP sync → RTC update
  ├─ WebSocket connect (command channel)
  └─ GET /iot/devices/{id}/config/  → bundle NVS mein save

Every 10 min — POST /iot/heartbeat/
  ├─ bhejta hai: battery, RSSI, schedule_version, rtc_time, queued_events
  └─ wapas aata hai: config_stale, pending_commands, rtc_drift_seconds
       └─ config_stale=true → sirf tab bundle dobara fetch karta hai

Commands (WebSocket push, sub-second)
  SYNC_CONFIG / SYNC_SCHEDULE, TRIGGER_DOSE, GATE_LOCK, GATE_UNLOCK,
  OPEN_GATE, START_FILL_MODE, NEXT_COMPARTMENT, END_FILL_MODE,
  READ_FILL_WEIGHT, READ_WEIGHT, SYNC_TIME, RESET_FLAGS
  └─ Socket down ho to 5-min HTTP poll safety net

Dose Time (RTC-driven — network ki zaroorat nahi)
  ├─ RTC slot match → session UUID banta hai → slot aaj ke liye lock
  ├─ Stepper rotate → COMPARTMENT_ROTATED
  ├─ Settle → baseline weight → DOSE_STARTED
  ├─ Reminder audio + OLED + buzzer
  ├─ Haath detect → gate open → HAND_DETECTED + LID_OPENED
  ├─ Haath hataya → gate close → LID_CLOSED
  └─ 3 s settle → after weight → WEIGHT_READING
       └─ response mein dose_status → track 3 (taken) / 4 (missed)

Offline Mode (WiFi gaya)
  ├─ RTC + NVS cache se dose chalta rehta hai — patient ko dawai milti hai
  ├─ Events flash queue mein jaate hain (RTC ka occurred_at ke saath)
  ├─ OLED "Dose recorded / will sync" dikhata hai — taken/missed claim nahi
  └─ WiFi wapas → POST /iot/events/batch/ → backend wahi weight math chalata hai

Midnight (RTC date badalte hi)
  └─ Per-day dispense locks clear (NVS mein persisted, reboot-safe)
```

---

## 🌐 Apna PC ka IP kaise pata kare

```bash
# Windows PowerShell
ipconfig | findstr IPv4

# Output example: 192.168.1.100
# #define BACKEND_HOST "192.168.1.100"
```

> ⚠️ ESP32 aur PC ek hi WiFi network pe hone chahiye!

---

## 🧪 Test karna (Serial Monitor se)

Arduino IDE → Tools → Serial Monitor → **115200 baud**

Healthy boot aisa dikhega:

```
[BOOT] MedAdhere Pill Dispenser v3.0.0
[HW] HX711 initialized and tared
[RTC] DS3231 OK: 08:15:30
[DFPlayer] Ready — volume 25
[HW] All hardware initialized
[SCHED] Restored bundle v42 (4 compartments)
[WiFi] Connected: 192.168.1.105
[TIME] NTP synced: 08:15:31
[WS] Connecting to ws://192.168.1.100:8000
[WS] Command channel connected
[RTOS] Network task started on Core 0
[RTOS] Motor task started on Core 1
[RTOS] Sensor task started on Core 1
[RTOS] Scheduler task started on Core 1
[API] Config fetch → HTTP 200
[SCHED] Bundle v42 loaded — 4 compartments
[SCHED]   c1 08:00 ON  dose=10.00g
[SCHED]   c2 09:00 ON  dose=15.00g
[HB] battery=85% queued=0 ws=1
```

Dose firing:

```
[SCHED] 08:00 matched compartment 1
[DOSE] Starting scheduled dose: compartment 1 (session 3f2a...)
[MOTOR] Rotating to compartment 1
[HW] Stable weight: 380.00 g
[DOSE] Baseline 380.00g — waiting for hand
[SENSOR] Lid opened (open count=1)
[SENSOR] Lid closed — weight check
[HW] Stable weight: 370.00 g
[SENSOR] After-dose weight: 370.00g (baseline 380.00g)
[SENSOR] dose_status: taken
```

### Troubleshooting

| Serial output | Matlab |
|---|---|
| `[RTC] DS3231 NOT FOUND — NTP only` | RTC wiring check karo. WiFi gaya to time drift hoga aur offline dosing bharosemand nahi rahegi. |
| `[WS] Disconnected — will retry` | Backend ASGI pe nahi chal raha (`runserver` WebSocket support nahi karta), ya BACKEND_HOST galat hai. Commands 5-min poll se aayenge. |
| `[SCHED] Cached bundle size mismatch — ignoring` | Firmware update ke baad struct layout badla. Normal — agla config fetch theek kar dega. |
| `[SCHED] c1 08:00 OFF` | Us compartment mein measured medicine nahi hai. Fill flow chalao. |
| `[EVQ] N queued event(s) restored` | Offline events pending hain, WiFi aane par flush honge. |
| `[EVQ] Queue full — dropped oldest` | 24 se zyada events queue ho gaye — device bahut der offline tha. |
| `[HW] Load cell not ready` | HX711 wiring. GPIO 35 input-only hai — DOUT hi wahan lagega, SCK nahi. |

---

## 📂 File Structure

| File | Role |
|---|---|
| `esp32_firmware.ino` | State machine + 4 RTOS tasks + command handling |
| `config.h` | Pins, WiFi, backend host/port, timing, policy defaults |
| `hardware.h` | Peripheral drivers (stepper, servo, HX711, OLED, RTC, DFPlayer) |
| `schedule.h` | Config bundle cache (NVS) + **RTC scheduler** + per-day locks |
| `eventqueue.h` | NVS ring buffer — offline event durability |
| `events.h` | Event emission; queues to flash when a POST fails |
| `api.h` | HTTP transport (config, batch, heartbeat, fill measure) |
| `wsclient.h` | WebSocket command channel + auto-reconnect |
