# SOFTWARE REQUIREMENTS SPECIFICATION (SRS)
## Aarogyam (MedAdhere v2.1) — Intelligent Medication Adherence Monitoring & Autonomous Intervention System

**Document Identifier**: `SRS-AAROGYAM-2026-V2.1`  
**Version**: 2.1.0  
**Classification**: Technical Product Specification  
**Status**: Production Baseline  
**Date**: September 2026  
**Standard Compliance**: IEEE Std 830-1998 / ISO/IEC/IEEE 29148:2018  

---

## 1. Introduction

### 1.1 Purpose
This Software Requirements Specification (SRS) provides an exhaustive, authoritative description of the **Aarogyam (MedAdhere v2.1)** platform. It defines all functional and non-functional requirements, external interfaces, hardware-firmware integration parameters, autonomous agent behaviors, data models, and architectural boundaries. 

This document serves as the foundational reference for software engineers, firmware developers, AI/ML engineers, clinical auditors, and hardware designers collaborating on the Aarogyam ecosystem.

### 1.2 Scope of the System
**Aarogyam** is an intelligent, cyber-physical healthcare platform designed to combat the chronic disease medication non-adherence crisis in India and emerging economies. The platform integrates:
1. **IoT Edge Hardware**: An ESP32 dual-core smart pill dispenser equipped with stepper motor carousel rotation, differential gravimetric verification (load cell), optical/ultrasonic hand detection, physical servo-locking gates, bilingual OLED display, DS3231 RTC, and audio guidance.
2. **Central Cloud Backend**: A high-throughput Django 5.x / Daphne ASGI distributed service orchestrating 27 domain apps, WebSockets via Django Channels, Celery Beat task scheduling, and Redis caching.
3. **Agent Handover Orchestrator**: An asynchronous, event-driven service mesh coordinating 16 core agents and 12 extension agents with typed handover contracts.
4. **Predictive AI Engine**: Machine learning pipeline featuring XGBoost risk scoring, SHAP TreeExplainer feature attribution, and predictive refill consumption forecasting.
5. **Autonomous Agent Runtime**: An LLM-powered (Groq / Llama-3 / Mixtral) observe-reason-plan-act-evaluate loop executing high-risk clinical interventions and automated pharmacy replenishment with human-in-the-loop safeguards.
6. **Multi-Role Web Portals**: Five dedicated web dashboards (Patient, Caregiver, Doctor, Hospital Tenant Admin, and Super-Admin) developed in React 19, TailwindCSS, and TanStack Query.
7. **Omnichannel Tele-Intervention**: Push notifications (FCM), Telegram interactive bot, SMS/Voice (Twilio), Email (SendGrid), and WebSocket push alerts.
8. **Healthcare Interoperability**: Indian National Digital Health Mission (ABDM / ABHA M1/M2/M3), HL7 FHIR R4 export, OpenFDA pharmacovigilance, and HIPAA/DISHA-compliant audit trails.

### 1.3 Real-World Problem Statement
According to the World Health Organization (WHO), adherence to long-term therapy for chronic illnesses in developing nations averages only 50%. In India, where hypertension, diabetes, and cardiovascular diseases affect over 250 million citizens:
- Patients miss doses due to forgetfulness, cognitive decline, complex multi-drug schedules, and asymptomatic conditions.
- Caregivers and family members suffer from "alert blindness" and lack physical proof of ingestion.
- Doctors have zero visibility into actual patient compliance between quarterly visits, leading to incorrect dosage escalation (pseudo-resistance).
- Pharmacies face irregular refill patterns, resulting in stockouts and therapy discontinuation.

Aarogyam resolves this by bridging the cyber-physical gap: physically locking medicine, validating dose extraction via precision weight deltas, proactively predicting non-adherence through machine learning, and mobilizing caregivers and autonomous agents before health emergencies manifest.

### 1.4 Definitions, Acronyms, and Abbreviations
| Term | Definition |
|---|---|
| **ABHA** | Ayushman Bharat Health Account (India's national digital health identifier). |
| **ABDM** | Ayushman Bharat Digital Mission (National digital health ecosystem standards). |
| **ASGI** | Asynchronous Server Gateway Interface (enables asynchronous Python web servers). |
| **Celery Beat** | Periodic job scheduler for background task queues. |
| **DISHA** | Digital Information Security in Healthcare Act (Indian healthcare privacy standard). |
| **FHIR** | Fast Healthcare Interoperability Resources (HL7 standard for electronic healthcare records). |
| **FCM** | Firebase Cloud Messaging (Google mobile push notification infrastructure). |
| **GPIO** | General Purpose Input/Output (pins on ESP32 microcontroller). |
| **HX711** | 24-bit precision analog-to-digital converter designed for weigh scales. |
| **ICD-10** | International Statistical Classification of Diseases and Related Health Problems (10th Revision). |
| **MFA / TOTP** | Multi-Factor Authentication / Time-based One-Time Password. |
| **RBAC** | Role-Based Access Control. |
| **RTOS** | Real-Time Operating System (specifically FreeRTOS on ESP32). |
| **SHAP** | SHapley Additive exPlanations (explainable AI methodology). |
| **ULN2003** | High-voltage, high-current Darlington transistor array used to drive stepper motors. |
| **WSS** | WebSocket Secure protocol. |

### 1.5 Document Conventions
- **Requirement Tags**: `[FR-xxx]` for Functional Requirements, `[NFR-xxx]` for Non-Functional Requirements, `[HWR-xxx]` for Hardware Requirements.
- **Priority Ratings**: High (Critical path, MVP), Medium (Core operational feature), Low (Extended capability).
- **Standards Format**: Requirements are structured with Preconditions, Triggers, Inputs, Processing Logic, Outputs, and Error Handling.

---

## 2. Overall Description

### 2.1 Product Perspective & Context Architecture
The Aarogyam platform operates as an integrated multi-tier cyber-physical system:

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                           TIER 1: PHYSICAL EDGE (IoT)                          │
│  ESP32 Dual-Core (FreeRTOS) ── Stepper Carousel ── HX711 Load Cell ── Servo    │
│  HC-SR04 Sensor ── DS3231 RTC ── OLED 128x64 ── DFPlayer Audio (Hindi/English)  │
└──────────────────────────────────────┬─────────────────────────────────────────┘
                                       │ HTTPS REST / Polling (X-Device-Key)
┌──────────────────────────────────────▼─────────────────────────────────────────┐
│                      TIER 2: API & INGESTION GATEWAY                          │
│  Django 5.x / Daphne ASGI · Celery Workers & Beat · Redis 7 Broker & Cache     │
│  PostgreSQL (Relational Store with Fernet Field-Level Encryption)             │
└──────────────────────────────────────┬─────────────────────────────────────────┘
                                       │ Internal Event Dispatch
┌──────────────────────────────────────▼─────────────────────────────────────────┐
│              TIER 3: AGENT HANDOVER & AUTONOMOUS RUNTIME                      │
│  16 Core Agents + 12 Extension Agents (Event-Driven State Machine Mesh)       │
│  Autonomous LLM Pipeline (Groq / Llama-3 / Mixtral Tool Calling)               │
│  XGBoost v1.9.0 Adherence Risk Predictor + SHAP Explainer                     │
└──────────────────────────────────────┬─────────────────────────────────────────┘
                                       │ Real-Time Push / WS / Webhooks
┌──────────────────────────────────────▼─────────────────────────────────────────┐
│                 TIER 4: MULTI-CHANNEL TELE-INTERVENTION                        │
│  Firebase Push (FCM) · Telegram Bot API · Twilio SMS · SendGrid Email · WSS    │
└──────────────────────────────────────┬─────────────────────────────────────────┘
                                       │ Responsive Client Consumption
┌──────────────────────────────────────▼─────────────────────────────────────────┐
│                 TIER 5: MULTI-ROLE WEB CLIENTS (PORTALS)                       │
│  React 19 + Vite 8 SPA: Patient · Caregiver · Doctor · Pharmacy · Admin        │
└────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Hardware Subsystem Specification (ESP32 Smart Dispenser)
The physical dispenser is an intelligent medical appliance placed in the patient's residence.

#### 2.2.1 Component Specifications
1. **Processing Core**: Espressif ESP32-WROOM-32 (Tensilica Xtensa Dual-Core 32-bit LX6, 240 MHz, 520 KB SRAM, 4 MB Flash, 802.11 b/g/n Wi-Fi, Bluetooth 4.2 BLE).
2. **Carousel Actuation**: 28BYJ-48 5V Unipolar Stepper Motor driven by ULN2003 Darlington Array (64:1 reduction ratio, 4096 half-steps per 360° rotation). Drives a 4-compartment rotatable pill carousel.
3. **Gravimetric Verification**: 1 kg Aluminum Single-Point Load Cell coupled with an Avia Semiconductor HX711 24-bit ADC differential amplifier. Resolution: $\pm 0.05\text{ g}$. Scale factor calibrated to 2280.0.
4. **Dispense Gate Barrier**: TowerPro SG90 9g Micro Servo Motor (PWM controlled, $50\text{ Hz}$, $0^\circ$ closed barrier, $90^\circ$ open chute).
5. **Proximity & Hand Detection**: HC-SR04 Ultrasonic Ranging Module (Echo/Trigger cycle, operating threshold $\le 15\text{ cm}$, sample debounce $500\text{ ms}$).
6. **Local Visual Interface**: $0.96''$ I2C SSD1306 OLED Display ($128 \times 64$ monochrome pixels, I2C address `0x3C`).
7. **Offline Real-Time Clock**: Maxim Integrated DS3231 Extreme Precision I2C RTC with integrated temperature-compensated crystal oscillator (TCXO) and CR2032 coin cell backup (I2C address `0x68`).
8. **Audio Guidance Subsystem**: DFPlayer Mini MP3 Player Module driven over UART2 (`16/17`), paired with an $8\,\Omega / 3\,\text{W}$ high-fidelity miniature speaker.
9. **Power Subsystem**: $5\,\text{V} / 2\,\text{A}$ micro-USB/DC barrel input with 3.3V LDO regulator and GPIO 34 analog voltage divider for battery health telemetry.

#### 2.2.2 ESP32 Pin Mapping Table
| ESP32 Pin | Connected Subsystem | Pin Function | Electrical Interface |
|---|---|---|---|
| **GPIO 13** | ULN2003 Stepper Driver | IN1 (Phase A) | 3.3V Logic OUT |
| **GPIO 12** | ULN2003 Stepper Driver | IN2 (Phase B) | 3.3V Logic OUT |
| **GPIO 14** | ULN2003 Stepper Driver | IN3 (Phase C) | 3.3V Logic OUT |
| **GPIO 27** | ULN2003 Stepper Driver | IN4 (Phase D) | 3.3V Logic OUT |
| **GPIO 25** | SG90 Servo Motor | PWM Signal | $50\,\text{Hz}$ PWM OUT ($0^\circ - 90^\circ$) |
| **GPIO 26** | HC-SR04 Ultrasonic | Trigger | $10\,\mu\text{s}$ Pulse OUT |
| **GPIO 33** | HC-SR04 Ultrasonic | Echo | Level-Shifted Pulse IN |
| **GPIO 35** | HX711 Load Cell ADC | DOUT | Synchronous Serial Data IN (Input Only) |
| **GPIO 18** | HX711 Load Cell ADC | SCK | Serial Clock OUT ($>100\,\text{kHz}$) |
| **GPIO 16** | DFPlayer Mini MP3 | RX2 (ESP32 RX) | UART Serial IN ($9600\,\text{bps}$) |
| **GPIO 17** | DFPlayer Mini MP3 | TX2 (ESP32 TX) | UART Serial OUT ($1\,\text{k}\Omega$ protected) |
| **GPIO 15** | DFPlayer Mini MP3 | BUSY | Active LOW Detection IN |
| **GPIO 21** | Shared I2C Bus | SDA | I2C Data ($400\,\text{kHz}$ Fast Mode) |
| **GPIO 22** | Shared I2C Bus | SCL | I2C Clock ($400\,\text{kHz}$ Fast Mode) |
| **GPIO 32** | Active Buzzer | Piezo Driver | High-Drive Logic OUT |
| **GPIO 2** | Onboard Blue LED | Status Beacon | Logic OUT |
| **GPIO 34** | Battery Voltage Divider | ADC1_CH6 | Analog Input ($0-3.3\,\text{V}$, Input Only) |

#### 2.2.3 Dual-Core FreeRTOS Task Architecture
The ESP32 firmware distributes workloads across dual cores using FreeRTOS primitives:
- **Core 0 — `taskNetwork` (Priority 1, 8 KB Stack)**:
  - Wi-Fi watchdog with auto-reconnect and exponential backoff ($15\text{ s}$).
  - NTP time synchronization updating DS3231 RTC registers.
  - Heartbeat POST every $5\text{ min}$ delivering battery level, Wi-Fi RSSI, and uptime.
  - Schedule poll GET every $60\text{ s}$ retrieving upcoming dosage events.
  - Command poll GET every $10\text{ s}$ checking for `ROTATE`, `PLAY_VOICE_NOTE`, `LOCK_LID`, `UNLOCK_LID`, `FILL_MODE`, `SYNC_TIME`, and `RESET_FLAGS`.
- **Core 1 — `taskMotor` (Priority 3, Highest, 4 KB Stack)**:
  - Consumes commands from FreeRTOS `xMotorCmdQueue`.
  - Acquires `xMotorMutex` to prevent concurrent stepper rotation.
  - Executes precise 4096-half-step sequence to rotate compartment 1 through 4.
  - Publishes `COMPARTMENT_ROTATED` event flags upon completion.
- **Core 1 — `taskSensor` (Priority 2, 6 KB Stack)**:
  - Executes real-time dispenser state machine: `STATE_IDLE` $\rightarrow$ `STATE_DISPENSING` $\rightarrow$ `STATE_GATE_OPEN` $\rightarrow$ `STATE_WEIGHT_CHECK` $\rightarrow$ `STATE_GATE_LOCKED` $\rightarrow$ `STATE_FILL_MODE`.

### 2.3 Software Monorepo Structure
The backend is structured into 27 discrete Django applications managed under `backend/apps/`:
1. `core`: Abstract timestamped models, shared exceptions, UUID primary keys, and cryptography helpers.
2. `identity`: Custom `User` model, JWT token generation, role assignment, TOTP MFA, session management, and `UserDevice` push tokens.
3. `clinical`: ICD-10 disease taxonomy, patient clinical histories, contraindications, and clinical encounter notes.
4. `scheduling`: Prescription models, daily reminder rule generation, dosage calculation, and dose event logs.
5. `telemetry`: High-frequency IoT metrics ingest (RSSI, voltage, sensor jitter), and device health monitoring.
6. `iot`: Physical device registration, pairing tokens, firmware heartbeat handler, and command dispatch queues.
7. `subscriptions`: Tiered billing models (Free, Caregiver Plus, Family Pro, Hospital Enterprise) and payment gateway webhooks.
8. `store`: E-commerce catalog for hardware dispensers, replacement carousels, and order fulfillment.
9. `notifications`: Multi-channel notification pipeline (In-App, FCM Push, Telegram Bot, Twilio SMS/WhatsApp, SendGrid Email).
10. `communications`: WebRTC signaling, real-time WebSocket chat and video consultation between doctors and patients.
11. `audit`: Immutable, write-only audit trail logging all PHI access for HIPAA and DISHA compliance.
12. `admin_panel`: Platform-wide administrative oversight, system health diagnostics, and user moderation.
13. `analytics`: Adherence score aggregation, cohort analytics, adherence timelines, and CSV/PDF export.
14. `ai_engine`: Machine learning inference service hosting the XGBoost classifier, SHAP explainability, and refill consumption forecast.
15. `agent_runtime`: Autonomous agentic pipeline (observe, reason, plan, act, evaluate) utilizing Groq LLM tool calling for high-risk adherence and refill resolution.
16. `pharmacy`: Pharmacy partner registry, API bridge, auto-refill triggers, and inventory tracking.
17. `doctor_portal`: Doctor profile management, doctor-patient links, digital prescription generation, and risk alerts.
18. `telegram_bot`: Full-duplex interactive Telegram bot service replacing legacy chatbots with inline keyboard dose logging and OTP onboarding.
19. `family`: Family groups, multi-patient guardian linking, and consolidated family adherence dashboards.
20. `fhir_integration`: HL7 FHIR R4 standard serialization and patient record import/export.
21. `vitals`: Patient vital signs tracking (blood pressure, fasting/post-prandial blood glucose, pulse, SpO2, weight, body temperature).
22. `gamification`: Adherence streaks, badge awarding, and behavioral reward points.
23. `pharmacovigilance`: Automated drug-drug and drug-food interaction checks against OpenFDA APIs and adverse drug reaction reporting.
24. `insurance_reports`: Automated PDF generation of verified adherence certificates for health insurance premium discounts.
25. `geofence`: Patient geofence boundary configuration and location-triggered medication alerts.
26. `abha`: Ayushman Bharat Digital Mission (ABDM) integration (ABHA creation, verification, and consent management).
27. `tenants`: Multi-tenant hospital/clinic isolation with custom domain routing and isolated patient populations.

### 2.4 User Classes and Detailed Personas
1. **Patient (End User)**:
   - *Profile*: Elderly individuals, chronic illness patients (diabetes, cardiovascular disease, hypertension, tuberculosis) managing 2–6 daily medications.
   - *Needs*: Frictionless reminders, physical access control, voice instructions in native language (Hindi/English), visual OLED schedule indicators, zero complex device setups.
2. **Caregiver (Family Member / Guardian)**:
   - *Profile*: Son, daughter, or designated nurse living with or away from the patient.
   - *Needs*: Instant alerts when doses are missed or dispenser is tampered with; remote lid lock/unlock controls; weekly adherence trend summaries; emergency geofencing.
3. **Doctor / Healthcare Provider**:
   - *Profile*: Treating physicians, cardiologists, and endocrinologists prescribing chronic therapy.
   - *Needs*: Verifiable, tamper-proof adherence records; explainable AI risk indicators; clinical prescription builder with drug interaction checks; patient risk alerts.
4. **Pharmacist / Fulfillment Partner**:
   - *Profile*: In-house or partnered retail pharmacy dispensaries.
   - *Needs*: Predictive refill orders generated 5 days before medication exhaustion; prescription verification; order fulfillment status tracking.
5. **Hospital Tenant Administrator**:
   - *Profile*: Clinical operations manager at hospitals utilizing Aarogyam for outpatient monitoring.
   - *Needs*: Departmental patient analytics, staff doctor assignments, tenant branding, subscription billing, and compliance auditing.
6. **System Super-Administrator**:
   - *Profile*: Platform technical operators and site reliability engineers.
   - *Needs*: System health diagnostics, global audit logs, AI model performance monitoring, IoT device fleet provisioning, and API rate-limit controls.

---

## 3. External Interface Requirements

### 3.1 User Interfaces (Frontend Web Portals)
The web user interface is built as a single-page application (SPA) using React 19, Vite 8, TailwindCSS 4, and TanStack Query 5. The interface provides 5 role-based dashboards:

#### 3.1.1 Patient Portal (`/patient/*`)
- **Dashboard (`/patient/home`)**: Current medication schedule, next dose countdown, daily adherence streak counter, quick dose confirmation, and recent AI insights.
- **My Medications (`/patient/medications`)**: Active prescriptions, dosage timings, pill images, remaining tablet counts, and refill requests.
- **IoT Dispenser (`/patient/dispenser`)**: Live dispenser connection state, battery level, Wi-Fi signal strength, and compartment filling wizard.
- **Vitals Tracking (`/patient/vitals`)**: Interactive charts for blood glucose and blood pressure with target thresholds.
- **Gamification (`/patient/rewards`)**: Earned badges, current streak days, and adherence level progression.

#### 3.1.2 Caregiver Portal (`/caregiver/*`)
- **Patient Overview (`/caregiver/dashboard`)**: Multi-patient card grid displaying adherence percentage, last recorded dose, and current dispenser status.
- **Patient Detail (`/caregiver/patient/:id`)**: Comprehensive medical record, adherence calendar, missed dose timelines, and real-time alerts.
- **Remote Dispenser Controls**: One-click remote gate unlock, emergency dispense trigger, and dispenser lock override.
- **Geofencing Config (`/caregiver/patient/:id/geofence`)**: Interactive Leaflet map to establish home radius and safe travel zones.

#### 3.1.3 Doctor Portal (`/doctor/*`)
- **Clinical Dashboard (`/doctor/home`)**: High-risk patient triage queue flagged by the AI engine, pending refill requests, and patient alerts.
- **Prescription Builder (`/doctor/patient/:id/prescribe`)**: Digital prescription interface with automated OpenFDA drug interaction warnings and auto-calculated schedule generation.
- **Adherence Analytics**: Detailed dose timing variance, missed dose heatmaps, and exportable clinical PDF reports.

#### 3.1.4 Hospital Tenant Admin & Super-Admin (`/admin/*`)
- **Tenant Management (`/admin/tenants`)**: Multi-tenant clinic onboarding, domain mapping, doctor assignments, and subscription license allocation.
- **IoT Device Fleet (`/admin/devices`)**: Batch device ID generator, hardware firmware version tracking, and diagnostic telemetry viewer.
- **Audit Logs (`/admin/audit`)**: Tamper-proof, searchable audit log of all clinical actions and data access events.

### 3.2 Hardware Interfaces
The firmware running on the ESP32 interacts with hardware components using standard bus protocols:
1. **I2C Bus Protocol (Shared, $400\,\text{kHz}$ Fast Mode)**:
   - `SDA` on GPIO 21, `SCL` on GPIO 22.
   - Master: ESP32. Slaves: SSD1306 Display (`0x3C`) and DS3231 RTC (`0x68`).
2. **Synchronous Serial Interface (HX711 24-bit ADC)**:
   - Clock line `SCK` on GPIO 18 driven by ESP32; Data line `DOUT` on GPIO 35 sampled by ESP32.
   - Timing: Minimum $0.1\,\mu\text{s}$ high/low clock pulses; 25 pulses per conversion to select Channel A with 128 gain.
3. **UART Serial Protocol (DFPlayer Mini)**:
   - UART2 Hardware Serial: TX on GPIO 17, RX on GPIO 16. Baud rate: $9600\,\text{bps}$, 8 data bits, no parity, 1 stop bit.
4. **PWM Pulse Generator (SG90 Servo)**:
   - Frequency: $50\,\text{Hz}$ ($20\,\text{ms}$ period). Duty cycle: $1.0\,\text{ms}$ ($0^\circ$, gate closed) to $2.0\,\text{ms}$ ($90^\circ$, gate open).
5. **Digital Half-Step Sequence (28BYJ-48 Stepper)**:
   - 8-phase excitation cycle driving GPIOs 13, 12, 14, 27 sequentially:
     `{1,0,0,0} -> {1,1,0,0} -> {0,1,0,0} -> {0,1,1,0} -> {0,0,1,0} -> {0,0,1,1} -> {0,0,0,1} -> {1,0,0,1}`.

### 3.3 Software Interfaces & Third-Party Services
1. **PostgreSQL Database**: Primary relational datastore (PostgreSQL 15+) using `psycopg2-binary` and connection pooling via PgBouncer.
2. **Redis 7 In-Memory Store**: Dual-purpose deployment for Celery broker queues (Database 0) and Django ASGI channel layers/cache (Database 1).
3. **Groq Cloud LLM Inference**: High-speed inference endpoint supporting `llama-3.3-70b-versatile` and `mixtral-8x7b-32768` with structured OpenAI-compatible tool calling.
4. **Firebase Cloud Messaging (FCM HTTP v1)**: Push notification delivery to Android, iOS, and Web PWAs with custom payload handling.
5. **Telegram Bot API**: Full-duplex webhook interface receiving `/start`, `/verify`, and dose confirmation button callbacks.
6. **Twilio REST API**: SMS dispatch and WhatsApp messaging fallback using E.164 phone formatting.
7. **SendGrid Email API**: Transactional email delivery for onboarding, subscription invoices, and security alerts.
8. **Razorpay & Stripe**: Dual payment gateways for automated recurring billing and hardware store purchases.
9. **OpenFDA API**: National Library of Medicine drug interaction and pharmacovigilance database query interface.
10. **ABDM Sandbox Gateway**: National Health Authority (NHA) API for ABHA address creation, demographic authentication, and health record linking.

### 3.4 Communication Protocols
1. **RESTful HTTP/HTTPS API**: Standard JSON API compliant with OpenAPI 3.0 specification.
2. **WebSocket Secure (WSS)**: Asynchronous full-duplex communication over Daphne ASGI for live notifications, telemetry, and consultation signaling.
3. **IoT Polling Protocol**: Low-overhead HTTP/1.1 REST polling mechanism:
   - Schedule Poll: `GET /api/v1/iot/devices/{id}/schedule/` every 60 seconds.
   - Command Poll: `GET /api/v1/iot/devices/{id}/commands/` every 10 seconds.
   - Heartbeat: `POST /api/v1/iot/devices/{id}/heartbeat/` every 5 minutes.
   - Dose Event: `POST /api/v1/iot/events/` immediately upon sensor trigger.
4. **Device Authentication Header**: Every IoT request must carry `X-Device-Key: <secret_device_token>`. Unauthenticated requests are rejected with `HTTP 401 Unauthorized`.

---

## 4. System Features & Detailed Functional Requirements

### 4.1 Feature 1: Identity, Authentication & Role-Based Access Control (RBAC)
#### 4.1.1 Description
Provides multi-tenant identity verification, multi-factor authentication (MFA), role-based permission scoping, and session security.
#### 4.1.2 Functional Requirements
- **[FR-1.1] User Registration & Social Auth**: The system shall support user registration via email/password and Google OAuth2. Roles include: `PATIENT`, `CAREGIVER`, `DOCTOR`, `PHARMACIST`, `TENANT_ADMIN`, and `SUPER_ADMIN`.
- **[FR-1.2] JWT Token Lifecycle**: The system shall issue an HMAC-SHA256 signed JWT Access Token (lifetime: 15 minutes) and a Refresh Token (lifetime: 7 days) upon successful authentication.
- **[FR-1.3] Time-Based One-Time Password (TOTP) MFA**: The system shall provide RFC 6238 TOTP MFA for doctor and administrative accounts, generating standard QR code secrets.
- **[FR-1.4] Role-Based Route Guards**: The system shall enforce endpoint authorization via permission classes (`IsPatient`, `IsCaregiver`, `IsDoctor`, `IsTenantAdmin`, `IsSuperAdmin`).
- **[FR-1.5] Multi-Tenant Context Isolation**: The system shall resolve tenant context using subdomains (`<tenant>.aarogyam.app`) or the `X-Tenant-ID` header, filtering all database queries to the active tenant.

### 4.2 Feature 2: Smart IoT Pill Dispenser & Firmware Lifecycle
#### 4.2.1 Description
Manages physical device registration, FreeRTOS state transitions, gravimetric intake validation, and remote hardware commands.
#### 4.2.2 Functional Requirements
- **[FR-2.1] Device Pairing & Token Generation**: The system shall generate a cryptographically random 32-character pairing token for each dispenser. Scanning the device QR code via the patient portal links the hardware to the patient record.
- **[FR-2.2] FreeRTOS Dose Sequence Execution**:
  1. *Step 1 (Schedule Trigger)*: When local RTC matches schedule time, `taskSensor` enters `STATE_DISPENSING`, updates OLED with medicine name, beeps buzzer, and plays DFPlayer Track 1 ("Dawai lene ka waqt ho gaya").
  2. *Step 2 (Compartment Rotation)*: `taskMotor` acquires `xMotorMutex` and rotates stepper motor 1024 half-steps ($90^\circ$) to align the scheduled compartment with the dispensing chute.
  3. *Step 3 (Contactless Hand Detection)*: HC-SR04 ultrasonic sensor continuously samples distance. When distance $\le 15\text{ cm}$ is detected for $>500\text{ ms}$, servo actuates to $90^\circ$ (open gate) and plays Track 2 ("Apni dawai nikaalo").
  4. *Step 4 (Hand Withdrawal & Gate Closure)*: When hand distance $>15\text{ cm}$ for $>1.0\text{ s}$, servo returns to $0^\circ$ (closed gate).
  5. *Step 5 (Gravimetric Weight Verification)*: `taskSensor` enters `STATE_WEIGHT_CHECK`, settles for $3.0\text{ s}$, and averages 10 readings from HX711. Weight delta is calculated:
     $$\Delta W = W_{\text{before}} - W_{\text{after}}$$
     - If $\Delta W \ge \text{expected\_weight} \times 0.85$: Status set to `TAKEN`. Audio Track 3 plays ("Shukriya, dawai le li gayi").
     - If $0 < \Delta W < \text{expected\_weight} \times 0.85$: Status set to `PARTIAL_DOSE`.
     - If $\Delta W \le 0$: Status set to `DOSE_NOT_TAKEN`.
  6. *Step 6 (Event Transmission)*: Device posts event payload to `/api/v1/iot/events/`:
     ```json
     {
       "device_id": "ESP32-AAROGYAM-0042",
       "event_type": "DOSE_TAKEN",
       "compartment": 1,
       "weight_delta_grams": 0.45,
       "battery_level": 94,
       "timestamp": "2026-09-16T08:00:15Z"
     }
     ```
- **[FR-2.3] Missed Dose Lockdown**: If no hand is detected within 60 minutes of schedule trigger, the device enters `STATE_GATE_LOCKED`, locks the servo gate, sounds periodic alert beeps, plays Track 4 ("Dawai nahi li, caregiver ko alert kiya"), and dispatches `DOSE_TIMEOUT` to the backend.
- **[FR-2.4] Remote Gate Unlock Override**: A caregiver can issue an unlock command from the web portal. The backend queues an `UNLOCK_LID` command. Upon receipt, the dispenser plays Track 5 ("Dispenser unlock ho gaya") and re-enters `STATE_DISPENSING` for 15 minutes.
- **[FR-2.5] Compartment Refill Wizard**: Activating `FILL_MODE` rotates each compartment sequentially to the top opening, allowing the patient or caregiver to load tablets while weighing the initial compartment baseline.

### 4.3 Feature 3: Prescription & Scheduling Engine
#### 4.3.1 Description
Maintains patient medication schedules, calculates dynamic reminder times, and coordinates dosage events.
#### 4.3.2 Functional Requirements
- **[FR-3.1] Prescription Data Model**: Prescriptions must record medication name, dosage form (tablet, capsule, syrup), strength, route of administration, daily frequency, meal timing (`BEFORE_MEAL`, `AFTER_MEAL`, `WITH_MEAL`), start date, end date, total quantity, and remaining quantity.
- **[FR-3.2] Daily Reminder Generation**: A Celery Beat task running daily at 00:00 UTC evaluates all active prescriptions and instantiates daily `Reminder` records with specific target datetimes adjusted for the patient's local timezone.
- **[FR-3.3] Dose Escalation Flow**: When a scheduled reminder is unacknowledged:
  - $T + 0\text{ min}$: Primary alert dispatched to IoT dispenser and In-App notification.
  - $T + 15\text{ min}$: Mobile push notification (FCM) and Telegram bot reminder.
  - $T + 30\text{ min}$: SMS notification to patient and primary caregiver.
  - $T + 60\text{ min}$: Caregiver emergency escalation alert triggered, dispenser locked, and `HIGH_RISK_DETECTED` event fired.

### 4.4 Feature 4: AI Adherence Prediction & Explainability Engine
#### 4.4.1 Description
Predicts patient non-adherence risk over a forward-looking 7-day window and explains contributing risk factors using machine learning.
#### 4.4.2 Functional Requirements
- **[FR-4.1] Machine Learning Model Architecture**: The adherence risk model uses an XGBoost Classifier (`adherence_risk_xgb_v1.9.0.pkl`) trained on historical dose logs, feature-engineered variables, and clinical attributes.
- **[FR-4.2] Feature Vector Specification**:
  1. `adherence_rate_last_7d`: Percentage of doses taken on time in past 7 days.
  2. `adherence_rate_last_30d`: Percentage of doses taken on time in past 30 days.
  3. `current_streak_days`: Consecutive days with 100% adherence.
  4. `missed_doses_last_14d`: Total count of missed dose events in past 14 days.
  5. `timing_variance_minutes`: Standard deviation of intake times relative to scheduled times.
  6. `regimen_complexity_score`: Number of concurrent medications multiplied by daily dosing frequencies.
  7. `age`: Patient chronological age.
  8. `is_living_alone`: Boolean indicator of independent living.
- **[FR-4.3] Output Risk Classification**:
  - `Risk Score`: Normalized probability output ($0 - 100$).
  - `Risk Level`: `LOW` ($0 - 35$), `MEDIUM` ($36 - 65$), `HIGH` ($66 - 100$).
- **[FR-4.4] SHAP Explainability**: The inference engine applies `shap.TreeExplainer` to calculate local SHapley values for each inference, generating human-readable risk attribution strings (e.g., *"Risk elevated due to high dosage timing variance (+18%) and living alone (+12%)"*).
- **[FR-4.5] Predictive Refill Consumption Forecasting**: Calculates the exact projected date of medication exhaustion based on moving-average daily consumption, triggering replenishment alerts 5 days prior to stock exhaustion.

### 4.5 Feature 5: Autonomous Agentic Runtime (Groq LLM Pipeline)
#### 4.5.1 Description
An autonomous agentic reasoning pipeline built in `backend/apps/agent_runtime/` executing an Observe-Reason-Plan-Act-Evaluate loop for high-risk clinical interventions and auto-refills.
#### 4.5.2 Functional Requirements
- **[FR-5.1] Event-Triggered Enqueue**: When `HIGH_RISK_DETECTED` or `REFILL_THRESHOLD_REACHED` events fire, the system spawns asynchronous Celery tasks (`evaluate_intervention_needed` or `evaluate_refill_needed`), decoupling LLM inference from synchronous API responses.
- **[FR-5.2] Observe Phase**: The agent compiles contextual memory from the database: patient demographics, recent dose logs, SHAP risk factors, active caregiver contact preferences, and prescription history.
- **[FR-5.3] Reason & Plan Phase**: The system constructs a structured prompt for the Groq LLM API (`llama-3.3-70b-versatile`) with strict JSON tool schemas. The LLM formulates a multi-step intervention plan:
  - Step 1: Query doctor availability or patient preference.
  - Step 2: Select high-priority communication channel.
  - Step 3: Compose personalized Hindi/English intervention message.
  - Step 4: Propose dispenser schedule adjustment or pharmacy refill order.
- **[FR-5.4] Policy Engine & Safety Guardrails**: All proposed actions pass through `PolicyEngine` before execution:
  - *Rule 1*: Autonomous medication dosage changes are strictly prohibited without verified doctor approval.
  - *Rule 2*: Maximum 1 automated phone call per patient per 24-hour cycle.
  - *Rule 3*: Pharmacy refill orders exceeding ₹5,000 require explicit caregiver/patient approval.
- **[FR-5.5] Tool Execution**: Approved actions are executed via `ToolRegistry`:
  - `send_multichannel_alert`: Dispatches alerts across selected channels.
  - `schedule_doctor_consultation`: Books an emergency tele-consultation slot.
  - `create_refill_order`: Places an automated order with the preferred pharmacy partner.
  - `lock_dispenser_gate`: Secures physical medication access.
- **[FR-5.6] Outcome Monitoring**: `OutcomeMonitor` tracks patient adherence for 72 hours post-intervention, recording intervention success metrics in `AgentAuditLog`.

### 4.6 Feature 6: Multi-Channel Real-Time Alert & Notification Dispatcher
#### 4.6.1 Description
Delivers notifications across multiple communication channels based on recipient preferences and subscription plans.
#### 4.6.2 Functional Requirements
- **[FR-6.1] In-App Real-Time WebSocket Delivery**: Pushes notification payloads over Django Channels to connected frontend clients within $<200\text{ ms}$.
- **[FR-6.2] Firebase Cloud Messaging (FCM)**: Sends mobile push notifications with custom priority tags, title, body, and deep-link routing URLs.
- **[FR-6.3] Telegram Interactive Bot (`apps.telegram_bot`)**:
  - Direct account linking via phone number matching and 6-digit OTP verification.
  - Interactive reminder messages with inline buttons: `[✅ Li (Taken)]`, `[❌ Nahi Li (Missed)]`, `[⏰ 15 min Baad (Snooze)]`.
  - Inline button clicks update the `DoseLog` table and notify the IoT dispenser via WebSocket/command queue.
- **[FR-6.4] Twilio SMS & Voice Delivery**: Formats automated SMS reminders and triggers synthetic voice calls for critical high-risk alerts.
- **[FR-6.5] SendGrid Email Delivery**: Dispatches branded HTML email summaries, weekly adherence progress reports, and password reset tokens.

### 4.7 Feature 7: Caregiver Portal & Remote Tele-Intervention
#### 4.7.1 Description
Empowers designated caregivers with monitoring, remote dispenser controls, and geofenced safety alerts.
#### 4.7.2 Functional Requirements
- **[FR-7.1] Caregiver-Patient Link Management**: Supports 1-to-many and many-to-1 relationships with permission levels: `VIEW_ONLY`, `ALERTS_ONLY`, and `FULL_CONTROL`.
- **[FR-7.2] Remote Dispenser Locking & Unlocking**: Allows caregivers with `FULL_CONTROL` to remotely lock or unlock the physical dispenser gate.
- **[FR-7.3] Patient Geofence Configuration**: Caregivers can define a geographical coordinate and radius (e.g., $500\text{ m}$ around the patient's home). If the patient's mobile app leaves the boundary during a scheduled dose window, a `GEOFENCE_BREACH` alert is issued.

### 4.8 Feature 8: Doctor Clinical Portal & Adherence Auditing
#### 4.8.1 Description
Provides clinical oversight, digital prescribing, and adherence monitoring for treating physicians.
#### 4.8.2 Functional Requirements
- **[FR-8.1] Clinical Dashboard**: Displays an active patient census sorted by AI adherence risk score, highlighting non-compliant patients.
- **[FR-8.2] Digital Prescription Builder**: Enables physicians to generate structured prescriptions with dose timing, duration, and meal relations.
- **[FR-8.3] Real-Time Drug Interaction Checking**: Queries the OpenFDA database upon medication selection to alert the doctor of potential drug-drug or drug-disease contraindications.
- **[FR-8.4] Clinical PDF Report Generation**: Generates comprehensive adherence audit reports including graphs, dose timestamps, and vitals correlation using `xhtml2pdf`.

### 4.9 Feature 9: Autonomous Pharmacy Refill & Partner Integration
#### 4.9.1 Description
Automates medication replenishment by bridging inventory tracking with external pharmacy fulfillment APIs.
#### 4.9.2 Functional Requirements
- **[FR-9.1] Inventory Depletion Tracking**: Decrements `remaining_quantity` upon each verified `DOSE_TAKEN` event.
- **[FR-9.2] Refill Trigger**: When `remaining_quantity <= (dosage_per_day * refill_threshold_days)`, the system emits `REFILL_THRESHOLD_REACHED`.
- **[FR-9.3] Automated Partner Order Placement**: Generates a `RefillOrder`, calculates estimated cost, and invokes the partnered pharmacy API (`call_pharmacy_api`) with exponential backoff retries.
- **[FR-9.4] Delivery Replenishment Sync**: When the pharmacy marks the order as `DELIVERED`, the system updates `remaining_quantity` and schedules the dispenser refill wizard.

### 4.10 Feature 10: Gamification, Streaks & Behavioral Economics
#### 4.10.1 Description
Incentivizes sustained adherence using habit-forming behavioral mechanisms.
#### 4.10.2 Functional Requirements
- **[FR-10.1] Adherence Streaks**: Increments consecutive streak days when all daily scheduled doses are taken on time. Any missed dose resets the current streak to zero.
- **[FR-10.2] Milestone Badges**: Automatically awards digital achievement badges:
  - `BRONZE_STREAK_7`: 7 consecutive days of 100% adherence.
  - `SILVER_STREAK_30`: 30 consecutive days of 100% adherence.
  - `GOLD_STREAK_90`: 90 consecutive days of 100% adherence.
  - `CENTURION_100`: 100 total doses taken on time.
  - `PERFECT_MONTH`: Zero missed or delayed doses in a calendar month.
- **[FR-10.3] Adherence Score Calculation**: Computes a dynamic composite score ($0 - 1000$) incorporating streak longevity, timing punctuality, and vitals recording frequency.

### 4.11 Feature 11: Vitals Monitoring & Telemetry Aggregation
#### 4.11.1 Description
Correlates medication adherence with quantitative physiological biomarker improvements.
#### 4.11.2 Functional Requirements
- **[FR-11.1] Supported Biomarkers**: Blood Pressure (Systolic/Diastolic in mmHg), Pulse (bpm), Blood Glucose (mg/dL with fasting/post-prandial tags), Weight (kg), SpO2 (%), and Body Temperature (°F/°C).
- **[FR-11.2] Clinical Thresholds & Anomaly Alerts**: Out-of-range vitals (e.g., Systolic $>160\,\text{mmHg}$ or Glucose $<70\,\text{mg/dL}$) trigger instant alerts to caregivers and treating physicians.
- **[FR-11.3] Adherence-Vitals Correlation Visualizer**: Renders comparative trend graphs linking dose regularity with blood pressure/glucose stabilization over 30, 60, and 90-day intervals.

### 4.12 Feature 12: Healthcare Standards: ABHA (ABDM), FHIR R4 & Pharmacovigilance
#### 4.12.1 Description
Aligns with national and international health data standards.
#### 4.12.2 Functional Requirements
- **[FR-12.1] ABHA Account Integration**: Interfaces with India's ABDM Gateway to verify and link 14-digit ABHA numbers and `@abdm` health addresses.
- **[FR-12.2] HL7 FHIR R4 Serialization**: Exposes FHIR-compliant REST endpoints serializing patient adherence records as FHIR `MedicationStatement` and `MedicationAdministration` resources.
- **[FR-12.3] Pharmacovigilance & Adverse Event Logging**: Provides structured forms for patients and doctors to log adverse drug reactions (ADRs), automatically generating standard CIOMS / CDSCO-compatible pharmacovigilance reports.

### 4.13 Feature 13: Multi-Tenancy, Subscriptions, Hardware Store & Billing
#### 4.13.1 Description
Manages commercial hospital tenant isolation, recurring SaaS subscriptions, and hardware purchases.
#### 4.13.2 Functional Requirements
- **[FR-13.1] Tenant Data Isolation**: Enforces tenant scoping on all models via `TenantMiddleware`. Tenant data is inaccessible across organizational boundaries.
- **[FR-13.2] Subscription Tiers**:
  - `FREE`: 1 patient profile, basic push reminders, manual logging.
  - `CAREGIVER_PLUS`: IoT dispenser support, SMS/WhatsApp/Telegram alerts, 2 caregiver links.
  - `FAMILY_PRO`: Up to 5 patient profiles, vitals correlation, full AI risk scoring.
  - `HOSPITAL_ENTERPRISE`: Unlimited patients, multi-doctor dashboard, FHIR export, tenant branding.
- **[FR-13.3] Hardware Store & Inventory Fulfillment**: E-commerce catalog for purchasing smart dispensers and replacement carousels, with payment processing via Razorpay/Stripe.

---

## 5. Non-Functional Requirements (NFRs)

### 5.1 Performance Requirements
- **[NFR-1.1] API Response Latency**: 95% of standard HTTP REST API queries shall return responses in $<200\text{ ms}$ under a load of 1,000 concurrent requests.
- **[NFR-1.2] Real-Time Alert Delivery**: WebSocket and FCM push notifications shall be delivered to client devices in $<1.0\text{ second}$ from event trigger.
- **[NFR-1.3] IoT Edge Responsiveness**: The ESP32 FreeRTOS motor task shall initiate carousel rotation within $<100\text{ ms}$ of queue command dispatch.
- **[NFR-1.4] Weight Measurement Settling Time**: HX711 gravimetric verification shall stabilize and complete conversion within $\le 3.0\text{ seconds}$.
- **[NFR-1.5] LLM Inference Latency**: Autonomous agent Groq LLM tool planning shall complete within $<2.5\text{ seconds}$.

### 5.2 Safety & Medical Failure-Mode Protection
- **[NFR-2.1] Physical Overdose Prevention**: The dispenser gate shall physically lock immediately after dose extraction, preventing double-dosing or premature compartment access.
- **[NFR-2.2] Jam & Misalignment Detection**: If the stepper motor fails to complete carousel rotation within $3.0\text{ seconds}$, the firmware shall sound an alarm, lock the gate, and report a `MOTOR_STALL_ERROR` to the cloud.
- **[NFR-2.3] Fail-Safe Gate State**: In the event of total electrical power failure or system reset, the servo gate shall remain in the $0^\circ$ mechanically closed position.
- **[NFR-2.4] Medical Advice Disclaimers**: All AI risk predictions and agentic nudges must display mandatory clinical disclaimers: *"For adherence assistance only; does not replace medical advice."*

### 5.3 Security Requirements
- **[NFR-3.1] Field-Level PHI Encryption**: Patient identifiers, medical conditions, and phone numbers shall be encrypted at rest in PostgreSQL using AES-128/256 via Fernet symmetric keys.
- **[NFR-3.2] Transport Layer Security**: All external communications (HTTPS, WSS) must enforce TLS 1.3 encryption.
- **[NFR-3.3] Hardware Mutual Authentication**: IoT dispensers shall authenticate each request using an immutable, cryptographically generated `X-Device-Key`.
- **[NFR-3.4] Immutable Audit Trail**: All reads, writes, and modifications to Protected Health Information (PHI) must append an immutable record to the `audit_log` table, recording user ID, IP address, timestamp, and action.

### 5.4 Reliability, Fault Tolerance & Offline Operation
- **[NFR-4.1] Offline Schedule Preservation**: The ESP32 shall cache up to 7 days of medication schedules in non-volatile flash memory (NVS/EEPROM). In the event of Wi-Fi loss, the device shall execute scheduled doses autonomously using the battery-backed DS3231 RTC.
- **[NFR-4.2] Offline Event Buffering**: Doses taken while offline shall be stored in local flash memory and synchronized in chronological order immediately upon Wi-Fi reconnection.
- **[NFR-4.3] Cloud High Availability**: The backend cloud infrastructure shall maintain $\ge 99.9\%$ operational uptime.

### 5.5 Regulatory & Compliance Requirements
- **[NFR-5.1] HIPAA & DISHA Alignment**: Meets Indian Digital Information Security in Healthcare Act (DISHA) standards and US HIPAA Security Rule standards for electronic protected health information (ePHI).
- **[NFR-5.2] Digital Personal Data Protection (DPDP) Act 2023**: Implements explicit user consent collection, data principal access controls, and "Right to be Forgotten" account erasure routines.

### 5.6 Usability, Accessibility & Localization
- **[NFR-6.1] Multilingual Audio Prompting**: The physical dispenser shall provide clear audio guidance in Hindi and English with adjustable volume ($60 - 85\,\text{dB}$).
- **[NFR-6.2] Senior-Friendly UI Design**: The patient web interface shall adhere to WCAG 2.1 Level AA standards, featuring high-contrast color palettes ($>4.5:1$), minimum font sizes of 16px, and intuitive touch targets ($>48 \times 48\,\text{px}$).

---

## 6. System Architecture & Design Models

### 6.1 State Machine Diagrams

#### 6.1.1 Physical Dispenser Dose Flow State Machine
```
                       [STATE_IDLE] (OLED Clock, Wait for schedule)
                             │
                  RTC Time Matches Schedule
                             │
                             ▼
                    [STATE_DISPENSING]
               - OLED: Show Medication Info
               - Buzzer: Short Beep
               - Audio: Track 1 ("Dawai lene ka waqt ho gaya")
               - Stepper: Rotate Carousel 90°
                             │
           ┌─────────────────┴─────────────────┐
     Hand Detected                       Timeout (60 min)
   (HC-SR04 <= 15 cm)                          │
           │                                   │
           ▼                                   ▼
   [STATE_GATE_OPEN]                  [STATE_GATE_LOCKED]
   - Servo: 90° (Open)                - Servo: 0° (Locked)
   - Audio: Track 2 ("Apni dawai...") - Audio: Track 4 ("Dawai nahi li...")
           │                          - Post: DOSE_TIMEOUT to Cloud
   Hand Withdrawn (>15 cm, 1s)                 │
           │                          Caregiver Unlocks Remotely
           ▼                                   │
  [STATE_WEIGHT_CHECK]                         ▼
   - Settle 3.0 seconds               Re-enter [STATE_DISPENSING]
   - HX711: Sample Delta W            Play Track 5 ("Unlock ho gaya")
           │
  ┌────────┴────────┐
Delta W >= Expected  Delta W < Expected / <= 0
  │                   │
  ▼                   ▼
Status: TAKEN       Status: PARTIAL / MISSED
Audio: Track 3      Alert Cloud
Return to IDLE      Return to IDLE
```

### 6.2 Sequence Diagrams

#### 6.2.1 Dose Verification & Notification Sequence
```
Patient             ESP32 Dispenser            Backend (Django)         Caregiver (Web/Telegram)
   │                       │                          │                           │
   │  (Schedule Trigger)   │                          │                           │
   │◄──Audio Track 1───────┤                          │                           │
   │   OLED & Beep         │                          │                           │
   │                       │                          │                           │
   ├──Hands in Chute──────►│                          │                           │
   │◄──Servo Gate Opens────┤                          │                           │
   │   Audio Track 2       │                          │                           │
   │                       │                          │                           │
   ├──Extracts Medicine───►│                          │                           │
   │                       ├──Weighs Delta W─────────►│                           │
   │                       │  POST /api/v1/iot/events │                           │
   │                       │                          ├──Process DoseLog─────────►│ (Live WebSocket)
   │◄──Audio Track 3───────┤                          ├──Update Streaks           │ "Dose Verified!"
   │   "Shukriya..."       │                          └──Check Refill Trigger     │
```

#### 6.2.2 Missed Dose & Autonomous Agent Escalation Sequence
```
Patient             ESP32 Dispenser            Backend & AI Runtime       Caregiver / Doctor
   │                       │                          │                           │
   │ (60 min Timeout)      │                          │                           │
   │◄──Audio Track 4───────┤                          │                           │
   │   Gate Locked         ├──POST DOSE_TIMEOUT──────►│                           │
   │                       │                          ├──Dispatch Push / Telegram►│
   │                       │                          │   "Missed Dose Alert"     │
   │                       │                          │                           │
   │                       │                          ├──Emit HIGH_RISK_DETECTED  │
   │                       │                          │            │              │
   │                       │                          │   [Autonomous Agent]      │
   │                       │                          │   - Query Groq LLM        │
   │                       │                          │   - Evaluate Risk (SHAP)  │
   │                       │                          │   - Formulate Plan        │
   │                       │                          │            │              │
   │                       │                          ├──Queue Doctor Alert──────►│ "High Risk Review"
   │                       │                          └──Schedule Escalation Call │
```

### 6.3 Entity Relationship Model & Data Dictionaries

```
┌─────────────────┐       1:N       ┌────────────────────────┐
│     Tenant      ├────────────────►│          User          │
└─────────────────┘                 └───────────┬────────────┘
                                                │ 1:1
                                                ▼
┌─────────────────┐       1:N       ┌────────────────────────┐
│   Prescription  │◄────────────────┤     PatientProfile     │
└────────┬────────┘                 └───────────┬────────────┘
         │ 1:N                                  │ 1:N
         ▼                                      ▼
┌─────────────────┐                 ┌────────────────────────┐
│    Reminder     │                 │   CaregiverRelation    │
└────────┬────────┘                 └────────────────────────┘
         │ 1:N                                  │ 1:1
         ▼                                      ▼
┌─────────────────┐                 ┌────────────────────────┐
│     DoseLog     │                 │       IoTDevice        │
└─────────────────┘                 └────────────────────────┘
```

#### 6.3.1 Core Database Tables
1. **`users_user`**:
   - `id`: UUID (Primary Key).
   - `email`: VARCHAR(255), Unique.
   - `phone_number`: VARCHAR(20), Unique.
   - `role`: VARCHAR(20) (`PATIENT`, `CAREGIVER`, `DOCTOR`, `PHARMACIST`, `TENANT_ADMIN`, `SUPER_ADMIN`).
   - `is_mfa_enabled`: BOOLEAN.
   - `mfa_secret`: VARCHAR(64) (Fernet Encrypted).
2. **`iot_devices`**:
   - `id`: UUID (Primary Key).
   - `device_serial`: VARCHAR(64), Unique.
   - `device_key_hash`: VARCHAR(128).
   - `patient_id`: UUID (Foreign Key $\rightarrow$ `PatientProfile`).
   - `status`: VARCHAR(20) (`ONLINE`, `OFFLINE`, `LOCKED`, `ERROR`).
   - `firmware_version`: VARCHAR(20).
   - `battery_level`: INTEGER.
   - `wifi_rssi`: INTEGER.
   - `last_heartbeat_at`: TIMESTAMP WITH TIME ZONE.
3. **`scheduling_prescription`**:
   - `id`: UUID (Primary Key).
   - `patient_id`: UUID (Foreign Key $\rightarrow$ `PatientProfile`).
   - `doctor_id`: UUID (Foreign Key $\rightarrow$ `DoctorProfile`, Nullable).
   - `medication_name`: VARCHAR(255).
   - `dosage_form`: VARCHAR(50).
   - `strength`: VARCHAR(50).
   - `dosage_per_day`: INTEGER.
   - `total_quantity`: INTEGER.
   - `remaining_quantity`: INTEGER.
   - `refill_threshold_days`: INTEGER (Default: 5).
   - `expected_dose_weight_grams`: DECIMAL(6, 3).
   - `start_date`: DATE.
   - `end_date`: DATE.
   - `status`: VARCHAR(20) (`ACTIVE`, `COMPLETED`, `DISCONTINUED`).
4. **`scheduling_doselog`**:
   - `id`: UUID (Primary Key).
   - `prescription_id`: UUID (Foreign Key $\rightarrow$ `Prescription`).
   - `patient_id`: UUID (Foreign Key $\rightarrow$ `PatientProfile`).
   - `scheduled_time`: TIMESTAMP WITH TIME ZONE.
   - `actual_time`: TIMESTAMP WITH TIME ZONE.
   - `status`: VARCHAR(20) (`TAKEN`, `MISSED`, `PARTIAL`, `SNOOZED`).
   - `log_source`: VARCHAR(20) (`IOT_DEVICE`, `MOBILE_APP`, `TELEGRAM_BOT`, `CAREGIVER_OVERRIDE`).
   - `weight_delta_grams`: DECIMAL(6, 3).
5. **`agent_runtime_agentgoal`**:
   - `id`: UUID (Primary Key).
   - `patient_id`: UUID (Foreign Key $\rightarrow$ `PatientProfile`).
   - `goal_type`: VARCHAR(50) (`ADHERENCE_INTERVENTION`, `AUTO_REFILL`).
   - `trigger_event`: VARCHAR(50).
   - `status`: VARCHAR(20) (`OBSERVE`, `REASON`, `PLAN`, `ACT`, `EVALUATE`, `COMPLETED`, `FAILED`).
   - `reasoning_trace`: JSONB.
   - `created_at`: TIMESTAMP WITH TIME ZONE.

---

## 7. Verification, Testing & Acceptance Criteria

### 7.1 Test Strategy Matrix
| Level | Scope | Tools / Frameworks | Target Metric |
|---|---|---|---|
| **Unit Testing (Backend)** | Models, Serializers, Handover logic, Policy rules | Pytest, Django Test Runner | $>85\%$ Line Coverage |
| **Unit Testing (Frontend)** | React components, Zustand stores, hooks | Vitest, React Testing Library | $>80\%$ Component Coverage |
| **Integration Testing** | REST APIs, Django Channels WebSocket consumers | Pytest-Django, Channels LiveServer | 100% Core Endpoints Passing |
| **Hardware-in-the-Loop** | ESP32 Firmware FreeRTOS tasks, sensors, actuators | PlatformIO, Saleae Logic Analyzer | 0 Stepper Skips, Accurate $\Delta W$ |
| **End-to-End System** | Complete dose flow: Schedule $\rightarrow$ Dispense $\rightarrow$ Verify | Playwright (Web), Mock ESP32 Client | End-to-end latency $<2\text{ s}$ |

### 7.2 Hardware-in-the-Loop (HIL) Test Protocol
1. **Gravimetric Precision Test**:
   - Apply standard calibration weights ($0.25\text{ g}$, $0.50\text{ g}$, $1.00\text{ g}$, $5.00\text{ g}$) to the HX711 scale plate.
   - Measure 50 consecutive weight samples.
   - *Acceptance Criterion*: Mean error must remain within $\le \pm 0.05\text{ g}$.
2. **Carousel Rotation Endurance Test**:
   - Execute 1,000 continuous $90^\circ$ rotation cycles using the 28BYJ-48 stepper motor under nominal payload.
   - *Acceptance Criterion*: Zero mechanical stalls; compartment optical alignment variance $\le \pm 2^\circ$.
3. **Power Loss & Recovery Protocol**:
   - Interrupt electrical power during `STATE_DISPENSING`.
   - Restore power after 60 seconds.
   - *Acceptance Criterion*: Device must read DS3231 RTC, query local NVS flash schedules, restore the servo gate to $0^\circ$ (closed), and resume normal operational polling.

---

## 8. Appendices

### 8.1 Agent Handover Event Catalog
The system operates an asynchronous event bus connecting 28 specialized agents:

| Event Identifier | Source Agent | Target Agent(s) | Payload Summary |
|---|---|---|---|
| `DOSE_LOGGED` | `IoTAgent` / `TelegramBot` | `AdherenceAgent`, `AnalyticsAgent` | `patient_id`, `prescription_id`, `status`, `weight_delta` |
| `DOSE_MISSED` | `ReminderAgent` | `CaregiverAgent`, `NotificationAgent` | `patient_id`, `reminder_id`, `minutes_overdue` |
| `HIGH_RISK_DETECTED` | `AIAgent` (XGBoost) | `AgentRuntime`, `DoctorAgent`, `CaregiverAgent` | `patient_id`, `risk_score`, `shap_factors`, `trace_id` |
| `REFILL_THRESHOLD_REACHED` | `MedicationAgent` | `AgentRuntime`, `PharmacyAgent` | `prescription_id`, `remaining_quantity`, `days_left` |
| `REFILL_ORDER_PLACED` | `PharmacyAgent` | `NotificationAgent`, `StoreAgent` | `order_id`, `partner_id`, `medication_name`, `total_amount` |
| `DOCTOR_ALERT_TRIGGERED` | `DoctorAgent` | `NotificationAgent` | `doctor_id`, `patient_id`, `severity`, `clinical_reasons` |
| `GEOFENCE_BREACH` | `GeofenceAgent` | `CaregiverAgent`, `NotificationAgent` | `patient_id`, `current_lat`, `current_lon`, `distance_breached` |
| `DEVICE_TAMPER_DETECTED` | `IoTAgent` | `CaregiverAgent`, `AuditAgent` | `device_id`, `accelerometer_delta`, `timestamp` |

### 8.2 Audio Guidance Prompts Directory
| Track # | Audio File | Hindi Voice Prompt | English Equivalent | Functional Trigger |
|---|---|---|---|---|
| **01** | `0001.mp3` | *"Dawai lene ka waqt ho gaya hai"* | *"It is time to take your medicine"* | Scheduled reminder time reached |
| **02** | `0002.mp3` | *"Kripya apni dawai nikaalein"* | *"Please take out your medicine"* | Dispenser gate opened ($90^\circ$) |
| **03** | `0003.mp3` | *"Shukriya, aapki dawai le li gayi hai"* | *"Thank you, your dose is confirmed"* | Load cell verified dose extraction |
| **04** | `0004.mp3` | *"Dawai nahi li gayi, caregiver ko soochit kiya gaya hai"* | *"Dose missed, caregiver has been alerted"* | 60-minute timeout expired |
| **05** | `0005.mp3` | *"Dispenser unlock ho gaya hai"* | *"Dispenser has been unlocked"* | Remote caregiver unlock command |

---
**End of Software Requirements Specification (SRS)**
