# Smart Pill Dispenser - Arduino / C++ Firmware

This folder contains the complete, native Arduino C++ (`.ino`) implementation of the Smart Pill Dispenser firmware, converted from `updated-iot/PillDispenser` with **100% identical sensor and actuator logic**.

---

## 📁 File Structure

```
updated-iot-arduino/PillDispenser/
├── PillDispenser.ino   # Master Arduino sketch (setup & loop)
├── config.h            # Hardware pins, WiFi, Backend URL & MQTT topics
├── stepper.h           # 28BYJ-48 8-step half-step sequence & compartment rotation
├── hall_sensor.h       # Pin 33 magnet detection & findHome() calibration
├── servo_gate.h        # SG90 50Hz PWM gate open (90°) & close (0°)
├── ultrasonic.h        # HC-SR04 10µs pulse timing & distance calculation
├── rtc_ds3231.h        # Direct I2C Wire protocol for DS3231 (Pins 23/22)
├── api_client.h        # HTTPClient for server time sync & prescription schedules
├── mqtt_handler.h      # PubSubClient MQTT integration & remote command subscriber
└── dispenser.h         # Dispensing window with hand detection loop
```

---

## 🔌 Exact Hardware Pin Configuration

| Component | Physical Model | ESP32 GPIO Pins | Function |
| :--- | :--- | :--- | :--- |
| **RTC Module** | DS3231 (I2C 0x68) | SDA: `23`, SCL: `22` | Wall-clock timekeeper (IST) |
| **Hall Sensor** | A3144 | GPIO `33` (Input Pull-up) | Homing to Compartment 1 |
| **Stepper Motor** | 28BYJ-48 + ULN2003 | IN1: `13`, IN2: `14`, IN3: `27`, IN4: `26` | 4-Compartment rotary carousel |
| **Servo Gate** | SG90 Micro Servo | GPIO `25` (50Hz PWM) | Lid open (90°) & close (0°) |
| **Ultrasonic** | HC-SR04 | TRIG: `19`, ECHO: `18` | Patient hand detection (≤ 15 cm) |

---

## ⚙️ Arduino IDE Setup

1. **Board Selection**:
   - In Arduino IDE, go to `Tools` -> `Board` -> `esp32` -> **`ESP32 Dev Module`**.
2. **Library Installation**:
   - Go to `Tools` -> `Manage Libraries...`
   - Search for **`PubSubClient`** by *Nick O'Leary* and click **Install**.
   *(All other modules like `Wire`, `WiFi`, `HTTPClient`, and hardware PWM use standard ESP32 Core libraries with zero extra dependencies!)*
3. **Configuration**:
   - Open `config.h`.
   - Update `WIFI_SSID` and `WIFI_PASSWORD` with your home/hotspot network.
   - Set `BACKEND_URL` and `MQTT_BROKER` to your backend PC IP (e.g. `10.98.188.253`) or `broker.hivemq.com`.
4. **Upload**:
   - Connect ESP32 via USB.
   - Select the correct COM port.
   - Click **Upload**.
   - Open Serial Monitor at **`115200`** baud rate.
