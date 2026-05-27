# 🏥 Aarogyam — Intelligent Medication Adherence Monitoring System

> **MedAdhere v2.1** — An end-to-end smart healthcare platform combining an IoT-powered smart pill dispenser, an AI-driven adherence engine, a multi-role web dashboard, and real-time communication infrastructure to ensure patients never miss a dose.

---

## 📖 Table of Contents

- [Overview](#-overview)
- [Architecture at a Glance](#-architecture-at-a-glance)
- [Hardware — Smart Pill Dispenser](#-hardware--smart-pill-dispenser)
  - [Components List](#components-list)
  - [GPIO Pin Mapping](#gpio-pin-mapping)
  - [Wiring Diagram Summary](#wiring-diagram-summary)
  - [Firmware Architecture (FreeRTOS)](#firmware-architecture-freertos)
  - [Dose Flow State Machine](#dose-flow-state-machine)
  - [Audio Tracks](#audio-tracks)
- [Software — Backend (Django)](#-software--backend-django)
  - [Backend App Modules](#backend-app-modules)
  - [Tech Stack](#tech-stack)
  - [Key API Groups](#key-api-groups)
  - [Real-Time via Django Channels](#real-time-via-django-channels)
  - [AI Engine](#ai-engine)
  - [Background Tasks (Celery)](#background-tasks-celery)
- [Software — Frontend (React)](#-software--frontend-react)
  - [Frontend Tech Stack](#frontend-tech-stack)
  - [Portal Dashboards](#portal-dashboards)
- [Infrastructure & DevOps](#-infrastructure--devops)
  - [Docker Services](#docker-services)
  - [Environment Variables](#environment-variables)
- [Getting Started](#-getting-started)
  - [Prerequisites](#prerequisites)
  - [1. Clone & Configure Backend](#1-clone--configure-backend)
  - [2. Run with Docker Compose](#2-run-with-docker-compose)
  - [3. Seed the Database](#3-seed-the-database)
  - [4. Run the Frontend Locally](#4-run-the-frontend-locally)
  - [5. Flash the ESP32 Firmware](#5-flash-the-esp32-firmware)
- [IoT Device Registration & Linking](#-iot-device-registration--linking)
- [Test Accounts](#-test-accounts)
- [API Reference Quick Start](#-api-reference-quick-start)
- [Project Structure](#-project-structure)
- [Feature Highlights](#-feature-highlights)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🌟 Overview

**Aarogyam** (meaning *"health"* in Sanskrit) is a hackathon-born, production-grade medication adherence system targeting India's chronic disease crisis. It goes beyond simple reminders — a physical smart dispenser physically controls access to medication, weight sensors verify if medicine was taken, and an AI engine predicts future non-adherence before it happens.

### Who it's for

| Role | What they get |
|---|---|
| **Patient** | Smart dispenser physically dispenses medicine at the right time; voice prompts in Hindi |
| **Caregiver** | Real-time alerts, remote lock/unlock of the dispenser, adherence dashboard |
| **Doctor** | Prescription management, adherence analytics, clinical reports |
| **Pharmacist** | Inventory sync, auto-refill triggers |
| **Tenant Admin** | Multi-tenant hospital/clinic management |
| **Super Admin** | Platform-wide oversight, audit trails |

---

## 🏗️ Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────────┐
│                        PATIENT'S HOME                           │
│                                                                 │
│   ┌──────────────────────────────────────────────────────┐     │
│   │          ESP32 Smart Pill Dispenser (Firmware v2.1)  │     │
│   │                                                      │     │
│   │  Core 0 (Network Task)   Core 1 (Motor + Sensor)    │     │
│   │  ├── WiFi / Heartbeat    ├── 28BYJ-48 Stepper       │     │
│   │  ├── Schedule Poll       ├── HC-SR04 Ultrasonic      │     │
│   │  └── Command Poll        ├── HX711 Load Cell         │     │
│   │                          ├── SG90 Servo Gate         │     │
│   │                          ├── DFPlayer Mini (Audio)   │     │
│   │                          ├── SSD1306 OLED            │     │
│   │                          └── DS3231 RTC              │     │
│   └──────────────────┬───────────────────────────────────┘     │
│                      │ HTTP REST (polling)                      │
└──────────────────────┼──────────────────────────────────────────┘
                       │
          ┌────────────▼──────────────┐
          │   Django / Daphne (ASGI)  │   Port 8000
          │   REST API + WebSockets   │
          ├───────────────────────────┤
          │  Celery Worker            │   Async tasks
          │  Celery Beat              │   Scheduled tasks
          ├───────────────────────────┤
          │  Redis 7                  │   Cache + broker
          ├───────────────────────────┤
          │  PostgreSQL (Neon / local)│   Persistent store
          └────────────┬──────────────┘
                       │
          ┌────────────▼──────────────┐
          │  React + Vite Frontend    │   Port 5173
          │  Patient / Caregiver /    │
          │  Doctor / Admin Portals   │
          └───────────────────────────┘
```

---

## 🔧 Hardware — Smart Pill Dispenser

### Components List

| Component | Model / Spec | Purpose |
|---|---|---|
| **Microcontroller** | ESP32 Dev Module | Wi-Fi, BLE, dual-core RTOS |
| **Stepper Motor** | 28BYJ-48 5V + ULN2003 Driver | Rotates the 4-compartment pill carousel |
| **Load Cell** | 1 kg HX711 | Weighs medication before & after dose to verify intake |
| **Servo Motor** | SG90 / MG90S | Opens and closes the dispensing gate |
| **Ultrasonic Sensor** | HC-SR04 | Detects patient's hand (≤15 cm) to trigger gate open |
| **OLED Display** | SSD1306 128×64 (I2C) | Shows medication name, time, dose status |
| **Real-Time Clock** | DS3231 (I2C) | Accurate timekeeping even when offline; shares I2C bus with OLED |
| **MP3 Module** | DFPlayer Mini | Plays Hindi voice prompts via speaker |
| **Speaker** | 8 Ω / 3 W | Audio output for voice guidance |
| **Buzzer** | Active buzzer | Alert beeps |
| **LED** | Built-in GPIO 2 | Visual alert indicator |
| **Battery ADC** | Voltage divider on GPIO 34 | Monitors battery level and sends low-battery alerts |

### GPIO Pin Mapping

```
ESP32 GPIO  │  Connected To
────────────┼──────────────────────────────────────
GPIO 13     │  ULN2003 IN1  (28BYJ-48 stepper coil 1)
GPIO 12     │  ULN2003 IN2  (stepper coil 2)
GPIO 14     │  ULN2003 IN3  (stepper coil 3)
GPIO 27     │  ULN2003 IN4  (stepper coil 4)
GPIO 25     │  SG90 Servo Signal (gate)
GPIO 26     │  HC-SR04 TRIG
GPIO 33     │  HC-SR04 ECHO
GPIO 35     │  HX711 DOUT   (load cell, input-only)
GPIO 18     │  HX711 SCK
GPIO 16     │  DFPlayer TX → ESP32 RX2 (Serial2)
GPIO 17     │  ESP32 TX2  → DFPlayer RX (via 1 kΩ resistor)
GPIO 15     │  DFPlayer BUSY pin (optional, LOW = playing)
GPIO 21     │  I2C SDA  (shared: OLED 0x3C + DS3231 0x68)
GPIO 22     │  I2C SCL  (shared: OLED + DS3231)
GPIO 32     │  Buzzer (+)
GPIO  2     │  Built-in LED
GPIO 34     │  Battery ADC (input-only)
3.3 V / GND │  All peripheral VCC / GND rails
```

> ⚠️ **I2C sharing**: OLED and DS3231 share GPIO 21/22. Their I2C addresses are different (0x3C vs 0x68), so there is no conflict.

### Wiring Diagram Summary

```
Power:
  5V  ──► 28BYJ-48 stepper motor (via ULN2003)
  5V  ──► DFPlayer Mini VCC
  3.3V ──► OLED VCC, DS3231 VCC, HC-SR04 VCC, HX711 VCC
  GND ──► All component grounds (common ground with ESP32)

Stepper Driver (ULN2003):
  IN1–IN4 ──► GPIO 13, 12, 14, 27
  OUT ──► 28BYJ-48 coils (4-wire, half-step mode)

Servo Gate:
  Signal ──► GPIO 25 (PWM)
  Open = 90°, Closed = 0°

Load Cell HX711:
  DOUT ──► GPIO 35, SCK ──► GPIO 18
  Scale calibration: LOADCELL_SCALE = 2280.0

DFPlayer Mini:
  TX ──► GPIO 16 (ESP32 RX2)
  RX ──► GPIO 17 (ESP32 TX2) via 1 kΩ resistor
  BUSY ──► GPIO 15 (optional)
  Speaker+ / Speaker- ──► 8 Ω / 3 W speaker
```

### Firmware Architecture (FreeRTOS)

The firmware runs three concurrent RTOS tasks:

```
Core 0
└── taskNetwork (priority 1, 8 KB stack)
    ├── WiFi watchdog & auto-reconnect (every 15 s)
    ├── NTP time sync → DS3231 RTC update
    ├── Heartbeat POST every 5 min (battery, RSSI, uptime)
    ├── Schedule poll GET every 60 s (triggers motor command)
    └── Command poll GET every 10 s (ROTATE, PLAY_VOICE_NOTE,
        LOCK_LID, UNLOCK_LID, FILL_MODE, SYNC_TIME, RESET_FLAGS)

Core 1
├── taskMotor (priority 3 [highest], 4 KB stack)
│   ├── Blocks on xMotorCmdQueue
│   ├── Holds xMotorMutex during rotation (28BYJ-48 half-step)
│   └── Signals COMPARTMENT_ROTATED event after rotation
│
└── taskSensor (priority 2, 6 KB stack)
    ├── STATE_IDLE         → displays clock on OLED
    ├── STATE_DISPENSING   → polls HC-SR04; opens gate on hand detected
    ├── STATE_GATE_OPEN    → waits for hand withdrawal, then closes gate
    ├── STATE_WEIGHT_CHECK → reads HX711 after-dose weight, sends to backend
    ├── STATE_GATE_LOCKED  → beeps every 30 s, shows locked screen
    └── STATE_FILL_MODE    → blinks fill instructions on OLED
```

### Dose Flow State Machine

```
                        Backend sends schedule
                               │
                          [ROTATE_TO_COMPARTMENT]
                               │
                     ┌─────────▼──────────┐
                     │  STATE_DISPENSING   │◄──── (1-hour timeout → DOSE_TIMEOUT)
                     │  OLED: dose info    │
                     └─────────┬──────────┘
                               │ Hand detected (HC-SR04 ≤15 cm)
                     ┌─────────▼──────────┐
                     │  STATE_GATE_OPEN    │
                     │  Servo: 90° open    │
                     │  Audio: Track 2     │
                     └─────────┬──────────┘
                               │ Hand withdrawn (debounced 500 ms)
                     ┌─────────▼──────────┐
                     │  STATE_WEIGHT_CHECK │
                     │  Settle 3 s         │
                     │  HX711 → backend   │
                     └─────────┬──────────┘
                    ┌──────────┴──────────┐
               dose_status=taken      partial / unknown
                    │                     │
               Audio: Track 3         Back to DISPENSING
               STATE_IDLE
```

**Lock/Unlock Flow (missed dose → caregiver intervention):**
```
1-hour timeout fires
  └── POST DOSE_TIMEOUT → backend sends LOCK_LID command
  └── STATE_GATE_LOCKED: plays Track 4, beeps, shows locked screen
      └── Caregiver approves on portal
          └── Backend sends UNLOCK_LID command
              └── Plays Track 5, re-enters STATE_DISPENSING
```

### Audio Tracks

Save these files to the DFPlayer Mini's SD card as `0001.mp3` → `0005.mp3`:

| Track | File | Hindi Prompt | Trigger |
|---|---|---|---|
| 1 | `0001.mp3` | "Dawai lene ka waqt ho gaya" | Dose reminder |
| 2 | `0002.mp3` | "Apni dawai nikaalo" | Gate opened / take medicine |
| 3 | `0003.mp3` | "Shukriya, dawai le li gayi" | Dose confirmed taken |
| 4 | `0004.mp3` | "Dawai nahi li, caregiver ko alert kiya" | Dose missed / gate locked |
| 5 | `0005.mp3` | "Dispenser unlock ho gaya" | Caregiver unlocked remotely |

---

## ⚙️ Software — Backend (Django)

### Backend App Modules

The backend is a Django monorepo with 27 feature apps under `backend/apps/`:

| App | Purpose |
|---|---|
| `core` | Base models, shared utilities, middleware |
| `identity` | User accounts, JWT auth, MFA (TOTP), sessions |
| `scheduling` | Prescription schedules, reminder generation, dose logging |
| `iot` | Device registration, event ingestion, command dispatch, fill mode |
| `telemetry` | IoT telemetry ingest & device health dashboards |
| `ai_engine` | XGBoost adherence risk prediction, SHAP explainability, refill forecasting |
| `notifications` | Push (FCM), SMS (Twilio), Email (SendGrid), WhatsApp bot |
| `communications` | WebSocket consumers (Django Channels), real-time alerts |
| `analytics` | Adherence summaries, timelines, medication-level reports |
| `caregiver` | Caregiver-patient linking, permission levels, alert routing |
| `doctor_portal` | Doctor profiles, doctor-patient links, clinical prescribing |
| `family` | Family group management |
| `vitals` | Blood pressure, glucose, weight readings & targets |
| `gamification` | Streaks, badges, adherence score |
| `pharmacy` | Pharmacy partner integrations, auto-refill orders |
| `store` | Hardware product catalog, orders |
| `subscriptions` | Subscription plans, Razorpay/Stripe webhooks, invoices |
| `tenants` | Multi-tenant (hospital/clinic) isolation |
| `admin_panel` | Super-admin capabilities |
| `audit` | Immutable audit log for HIPAA-style compliance |
| `geofence` | Location-based reminders |
| `fhir_integration` | HL7 FHIR R4 patient record export/import |
| `abha` | ABHA / ABDM (India's national health ID) integration |
| `clinical` | ICD-10 condition codes, clinical notes |
| `insurance_reports` | Insurance claim report generation |
| `pharmacovigilance` | Drug interaction checks (OpenFDA), adverse event reporting |
| `whatsapp_bot` | Twilio WhatsApp "taken / missed / snooze" chatbot |

### Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Framework | Django 5.0.4 + Django REST Framework 3.15.1 |
| Auth | JWT (SimpleJWT), TOTP MFA (pyotp), Google OAuth |
| Real-Time | Django Channels 4.1, channels-redis, Daphne ASGI server |
| Task Queue | Celery 5.3.6 + Redis 7 broker (django-celery-beat + results) |
| Database | PostgreSQL (Neon cloud DB or local Postgres) |
| Cache / Broker | Redis 7 |
| AI/ML | XGBoost, scikit-learn, SHAP, pandas, numpy |
| Notifications | Twilio (SMS + WhatsApp), SendGrid (Email), FCM (Push) |
| Payments | Razorpay (primary), Stripe (fallback) |
| Storage | AWS S3 via boto3 (media files) |
| API Docs | drf-spectacular (OpenAPI 3.0 schema) |
| Encryption | Fernet field-level encryption (cryptography) |
| Rate Limiting | django-ratelimit |
| Reports | xhtml2pdf |
| Monitoring | Sentry SDK |

### Key API Groups

| Group | Base Path | Auth Method |
|---|---|---|
| Auth (register, login, MFA, refresh) | `/api/v1/auth/` | None / Bearer JWT |
| User profile & sessions | `/api/v1/users/me/` | Bearer JWT |
| Patient profile & prescriptions | `/api/v1/patients/me/` | Bearer JWT |
| Caregiver portal | `/api/v1/caregivers/` | Bearer JWT |
| Reminders & adherence | `/api/v1/reminders/`, `/api/v1/adherence/` | Bearer JWT |
| IoT device management (user-facing) | `/api/v1/iot/devices/` | Bearer JWT |
| **IoT firmware communication** | `/api/v1/iot/events/`, `/api/v1/iot/heartbeat/`, `/api/v1/iot/devices/{id}/commands/` | `X-Device-Key` header |
| Telemetry | `/api/v1/iot-telemetry/` | Bearer JWT |
| Notifications | `/api/v1/notifications/` | Bearer JWT |
| Subscriptions & billing | `/api/v1/subscriptions/` | Bearer JWT |
| Vitals | `/api/v1/vitals/` | Bearer JWT |
| Gamification | `/api/v1/gamification/` | Bearer JWT |
| Pharmacy & refills | `/api/v1/pharmacy/` | Bearer JWT |
| Store (hardware orders) | `/api/v1/store/` | Bearer JWT |
| Doctor portal | `/api/v1/doctor/` | Bearer JWT |
| WhatsApp webhook | `/api/v1/whatsapp/webhook/` | Twilio signature |
| Admin panel | `/api/v1/admin/` | Bearer JWT (super admin) |

Full guide: [`backend/POSTMAN_API_GUIDE.md`](./backend/POSTMAN_API_GUIDE.md)

### Real-Time via Django Channels

- **WebSocket endpoint**: `ws://host:8000/ws/notifications/`
- Powered by Django Channels 4.1 with Redis channel layer
- Used for: live dose alerts, caregiver notifications, IoT status updates
- JWT token passed as query parameter for WebSocket authentication

### AI Engine

Located in `backend/apps/ai_engine/`. Provides:

| Feature | Method |
|---|---|
| Adherence risk score (0–100) | XGBoost classifier trained on dose history, time-of-day, day-of-week, streak data |
| Feature importance | SHAP values — tells patient *why* they're at risk |
| Refill forecast | Predicts when medication will run out based on actual consumption |
| Personalized reminder timing | Learns the patient's best response window |

### Background Tasks (Celery)

| Task | Schedule | Purpose |
|---|---|---|
| Generate daily reminders | Daily (midnight) | Creates reminder objects from active schedules |
| Send reminder notifications | Per-reminder trigger | Push / SMS / WhatsApp / Email |
| Adherence analytics aggregation | Hourly | Rolls up logs into summary tables |
| Low stock alerts | Every 6 hrs | Checks remaining_quantity and triggers refill |
| Subscription expiry | Daily | Checks and expires overdue subscriptions |
| Device heartbeat timeout | Every 5 min | Marks devices offline if no heartbeat in 10 min |

---

## 💻 Software — Frontend (React)

### Frontend Tech Stack

| Technology | Version | Purpose |
|---|---|---|
| React | 19.x | Core UI framework |
| Vite | 8.x | Build tool & dev server |
| React Router DOM | 7.x | Client-side routing |
| TailwindCSS | 4.x | Utility-first styling |
| Framer Motion | 12.x | Animations & transitions |
| GSAP | 3.x | Advanced scroll/timeline animations |
| Zustand | 5.x | Global state management |
| TanStack React Query | 5.x | Server state, caching, invalidation |
| React Hook Form + Zod | 7.x + 4.x | Type-safe forms with validation |
| Recharts | 3.x | Adherence charts & analytics graphs |
| Lucide React + React Icons | Latest | Icon library |
| Axios | 1.x | HTTP client |
| @react-oauth/google | 0.12 | Google OAuth login |
| vite-plugin-pwa | 1.x | Progressive Web App support |

### Portal Dashboards

The frontend serves **5 role-based portals**, each under its own route namespace:

```
/auth/*         — Login, Register, MFA, Forgot Password
/patient/*      — Dashboard, My Medicines, Adherence History, Vitals, IoT Dispenser, Gamification
/caregiver/*    — Patient List, Adherence Alerts, Remote Lock/Unlock, Caregiver Dashboard
/doctor/*       — Patient Management, Prescriptions, Clinical Reports
/admin/*        — Tenant Management, Subscription Plans, Audit Logs
/public/*       — Landing, Pricing, About
```

---

## 🐳 Infrastructure & DevOps

### Docker Services

Defined in [`docker-compose.yml`](./docker-compose.yml):

| Service | Image / Build | Port | Role |
|---|---|---|---|
| `redis` | `redis:7-alpine` | — | Message broker + cache |
| `backend` | `./backend/Dockerfile` | `8000` | Daphne ASGI (Django + Channels) |
| `celery-worker` | same image | — | Async task worker |
| `celery-beat` | same image | — | Periodic task scheduler |
| `frontend` | `./frontend/Dockerfile` | `5173` | Vite dev server |

**Live development** is supported via Docker Compose `develop.watch` — code changes sync instantly without rebuilding (except `requirements.txt` which triggers a rebuild).

### Environment Variables

Copy `backend/.env.example` → `backend/.env` and fill in:

```env
# Django
SECRET_KEY=<generate a long random key>
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (Neon or local Postgres)
DB_NAME=medadhere
DB_USER=postgres
DB_PASSWORD=root
DB_HOST=localhost
DB_PORT=5432

# Redis
REDIS_URL=redis://localhost:6379/0

# Field-level encryption
FIELD_ENCRYPTION_KEY=<generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">

# Twilio (SMS + WhatsApp)
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM_NUMBER=

# FCM Push Notifications
FCM_SERVER_KEY=

# SendGrid Email
SENDGRID_API_KEY=
DEFAULT_FROM_EMAIL=noreply@medadhere.com

# Google OAuth
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# Sentry
SENTRY_DSN=

# Frontend URL (for CORS and redirect links)
FRONTEND_URL=http://localhost:5173
```

For the frontend, copy `frontend/.env.example` → `frontend/.env`:
```env
VITE_API_URL=http://localhost:8000
VITE_GOOGLE_CLIENT_ID=<your_google_client_id>
```

---

## 🚀 Getting Started

### Prerequisites

| Tool | Required Version |
|---|---|
| Docker & Docker Compose | Docker 24+ |
| Python | 3.12+ (if running locally without Docker) |
| Node.js | 20+ (if running frontend without Docker) |
| Arduino IDE | 2.x (for ESP32 firmware) |
| ESP32 board package | via Arduino Board Manager |
| PostgreSQL | 15+ (or use Neon cloud) |

### 1. Clone & Configure Backend

```bash
git clone <repo-url>
cd "Intelligent-Medication-Adherence-Monitoring-System-vedansh"

# Copy and edit backend env
cp backend/.env.example backend/.env
# Fill in DB credentials, Redis URL, and secret key
```

### 2. Run with Docker Compose

```bash
# From the project root
docker compose up -d

# To watch logs
docker compose logs -f backend

# To stop
docker compose down
```

The backend will be available at `http://localhost:8000`.
The frontend dev server will be at `http://localhost:5173`.

### 3. Seed the Database

Run migrations and seed initial data:

```bash
# Migrations (run automatically on container start, or manually)
docker compose exec backend python manage.py migrate

# Seed subscription plans
docker compose exec backend python manage.py seed_subscription_plans

# Seed medication database
docker compose exec backend python manage.py seed_medications_db

# Seed ICD-10 codes
docker compose exec backend python manage.py seed_icd10_codes

# Create a super admin user
docker compose exec backend python manage.py create_superadmin

# Create a sample tenant
docker compose exec backend python manage.py create_tenant \
  --name "Apollo Indore" \
  --subdomain apollo-indore \
  --plan HOSPITAL \
  --admin-email admin@apollo.com

# Generate IoT device IDs
docker compose exec backend python manage.py generate_device_ids \
  --product-id <product-uuid> \
  --batch-size 100
```

### 4. Run the Frontend Locally

```bash
cd frontend
npm install
npm run dev
# Opens at http://localhost:5173
```

### 5. Flash the ESP32 Firmware

#### Install Arduino Libraries (via Library Manager)

| Library | Manager Search Name |
|---|---|
| ArduinoJson | `ArduinoJson` by bblanchon (v7.x) |
| ESP32Servo | `ESP32Servo` by Kevin Harrington |
| Adafruit SSD1306 | `Adafruit SSD1306` |
| Adafruit GFX | `Adafruit GFX Library` |
| RTClib | `RTClib` by Adafruit (v2.x) |
| HX711 | `HX711` by bogde |
| DFRobotDFPlayerMini | `DFRobotDFPlayerMini` |

#### Arduino IDE Settings

```
Board:            ESP32 Dev Module
Port:             COM3 (or whichever appears)
Upload Speed:     921600
Flash Size:       4MB (32Mb)
Partition Scheme: Default 4MB with spiffs
```

#### Configure `iot file/config.h`

```cpp
#define WIFI_SSID      "YourWiFiName"
#define WIFI_PASSWORD  "YourWiFiPassword"
#define BACKEND_URL    "http://192.168.X.X:8000"  // Your PC's local IP
#define DEVICE_API_KEY "paste-from-registration-step"
#define DEVICE_ID      "paste-from-registration-step"
```

To find your PC's local IP (Windows):
```powershell
ipconfig | findstr IPv4
```

> ⚠️ The ESP32 and your PC **must be on the same WiFi network**.

Then open `iot file/esp32_firmware.ino` in Arduino IDE and click **Upload**.

#### Verify in Serial Monitor (115200 baud)

```
[BOOT] MedAdhere Pill Dispenser v2.1.0
[HW] All hardware initialized
[RTC] DS3231 OK: 16:30:00
[WiFi] Connected: 192.168.1.105
[TIME] NTP synced: 16:30:01
[RTC] Synced from NTP
[RTOS] Network task started on Core 0
[RTOS] Motor task started on Core 1
[RTOS] Sensor task started on Core 1
[BOOT] All RTOS tasks launched
```

---

## 🔗 IoT Device Registration & Linking

1. **Register the device** (one time per device):
```bash
# Login as a patient user
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"patient@example.com","password":"password123"}'

# Link device to the patient account
curl -X POST http://localhost:8000/api/v1/iot/devices/link/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"device_name":"My Pill Dispenser","device_type":"CIRCULAR_PILL_DISPENSER"}'
```

2. **Copy from response**:
```json
{
  "data": {
    "id":      "← paste as DEVICE_ID in config.h",
    "api_key": "← paste as DEVICE_API_KEY in config.h"
  }
}
```

3. **Re-flash** the firmware with the updated `config.h`.

---

## 🔑 Test Accounts

Use these seeded accounts for development and testing:

| Email | Password | Role |
|---|---|---|
| `patient+apollo-indore@medadhere.test` | `Patient@12345` | PATIENT |
| `owner+apollo-indore@medadhere.test` | `Owner@12345` | TENANT_ADMIN |
| `patient+clinic-demo@medadhere.test` | `Patient@12345` | PATIENT |
| `owner+clinic-demo@medadhere.test` | `Owner@12345` | TENANT_ADMIN |
| `caregiver@medadhere.test` | `Caregiver@123` | CAREGIVER |
| `pharmacist@medadhere.test` | `Pharma@123` | PHARMACIST |
| `nurse@medadhere.test` | `Nurse@123` | NURSE |

---

## 📡 API Reference Quick Start

### Authentication

```http
POST /api/v1/auth/login/
Content-Type: application/json

{
  "email": "patient+apollo-indore@medadhere.test",
  "password": "Patient@12345"
}
```

Response:
```json
{
  "access": "<15-min JWT>",
  "refresh": "<30-day refresh token>"
}
```

Use `Authorization: Bearer <access>` on all protected endpoints.
Refresh with `POST /api/v1/auth/refresh/` using `{"refresh": "<token>"}`.

### IoT Firmware Communication

The ESP32 does **not** use JWT. It uses:
```http
X-Device-Key: <DEVICE_API_KEY from config.h>
```

Key firmware endpoints:
```
POST /api/v1/iot/events/                              ← Send device events
POST /api/v1/iot/heartbeat/                           ← Heartbeat (every 5 min)
GET  /api/v1/iot/devices/{device_id}/commands/        ← Poll for commands (every 10 s)
GET  /api/v1/iot/devices/{device_id}/dispenser/schedule/current/  ← Active dose schedule
```

Full API documentation: [`backend/POSTMAN_API_GUIDE.md`](./backend/POSTMAN_API_GUIDE.md)
Auto-generated OpenAPI schema: `http://localhost:8000/api/schema/`
Swagger UI: `http://localhost:8000/api/docs/`

---

## 📁 Project Structure

```
Intelligent-Medication-Adherence-Monitoring-System-vedansh/
│
├── backend/                        # Django backend
│   ├── apps/                       # 27 feature apps
│   │   ├── ai_engine/              # XGBoost + SHAP adherence AI
│   │   ├── communications/         # Django Channels WebSocket consumers
│   │   ├── iot/                    # ESP32 device management
│   │   ├── scheduling/             # Prescription schedules & reminders
│   │   ├── notifications/          # Multi-channel notification dispatch
│   │   └── ...                     # (22 more apps)
│   ├── config/                     # Django settings (dev/prod/docker)
│   ├── medadhere_backend/          # Project-level URL routing
│   ├── requirements.txt            # Python dependencies
│   ├── Dockerfile                  # Backend container image
│   ├── .env.example                # Environment variable template
│   └── POSTMAN_API_GUIDE.md        # Complete API reference
│
├── frontend/                       # React + Vite frontend
│   ├── src/
│   │   ├── pages/
│   │   │   ├── patient/            # Patient portal
│   │   │   ├── caregiver/          # Caregiver portal
│   │   │   ├── doctor/             # Doctor portal
│   │   │   ├── admin/              # Admin panel
│   │   │   ├── auth/               # Login, register, MFA
│   │   │   └── public/             # Landing pages
│   │   ├── components/             # Reusable UI components
│   │   ├── stores/                 # Zustand state stores
│   │   ├── hooks/                  # Custom React hooks
│   │   ├── lib/                    # API client, utilities
│   │   └── routes/                 # Route definitions
│   ├── package.json                # Node.js dependencies
│   ├── vite.config.js              # Vite + PWA config
│   └── Dockerfile                  # Frontend container image
│
├── iot file/                       # ESP32 firmware (Arduino C++)
│   ├── esp32_firmware.ino          # Main firmware (FreeRTOS tasks)
│   ├── hardware.h                  # Hardware abstraction layer
│   ├── config.h                    # WiFi, device ID, pin definitions
│   ├── api.h                       # HTTP API helper functions
│   ├── schedule.h                  # Schedule parsing & NVS caching
│   └── README.md                   # ESP32 setup & wiring guide
│
├── docker-compose.yml              # Full-stack Docker Compose
├── credential.md                   # Seed commands & secret reference
└── README.md                       # ← You are here
```

---

## ✨ Feature Highlights

### 🤖 AI-Powered Risk Prediction
- XGBoost model predicts non-adherence risk (0–100%) per patient per day
- SHAP explainability tells the patient *exactly* which factors contribute to their risk
- Proactive caregiver alerts before a missed dose pattern develops

### ⚖️ Weight-Based Dose Verification
- HX711 load cell reads baseline weight **before** and **after** each dose
- Backend classifies as `taken` (full), `partial`, or `missed` automatically
- Eliminates self-reporting bias — verification is physical, not manual

### 🗣️ Hindi Voice Guidance
- DFPlayer Mini plays contextual Hindi audio prompts at every step
- Works completely offline (no internet needed for audio playback)

### 📴 Offline Resilience
- DS3231 RTC maintains accurate time during WiFi outages
- NVS flash cache saves the active schedule across power cycles
- Dispensing continues correctly even without network connectivity

### 👨‍👩‍👧 Caregiver Remote Control
- Caregivers can lock/unlock the dispenser gate remotely from the web portal
- Real-time WebSocket notifications on dose events
- Full adherence history with timeline charts

### 🏥 Multi-Tenant Support
- Full hospital/clinic isolation via tenant system
- Each tenant has its own admin, patients, and branding
- Subscription tiers: FREE → BASIC → PRO → HOSPITAL → ENTERPRISE

### 🌐 Standards Compliance
- HL7 FHIR R4 patient record export/import
- ABHA (India's national health ID) integration
- ICD-10 diagnosis code support
- CDSCO pharmacovigilance report export
- Immutable audit log for compliance

### 🎮 Gamification
- Streak tracking, adherence badges, and score leaderboards
- Encourages habit formation through positive reinforcement

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Follow the existing app structure for new Django apps
4. Write tests in `backend/tests/`
5. Ensure `docker compose up` builds and all existing tests pass
6. Submit a pull request with a clear description

---

## 📄 License

This project was built for a hackathon. All code is original work by the team. Contact the repository owner for licensing terms before commercial use.

---

<div align="center">
  <b>Built with ❤️ for patients who deserve better than forgetting their medicine.</b>
  <br>
  <i>Aarogyam — आरोग्यम् — "May you be healthy."</i>
</div>
