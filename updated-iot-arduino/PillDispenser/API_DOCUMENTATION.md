# Smart Pill Dispenser — Firmware API & Communication Guide

This document is a local reference for the Arduino / ESP32 C++ firmware in this folder.

For the full system-wide technical documentation including sequence diagrams and companion caregiver APIs, see [IOT_DEVICE_API_DOCUMENTATION.md](../../IOT_DEVICE_API_DOCUMENTATION.md).

---

## 1. Quick API Endpoints Reference

Base URL: `https://aarogyam-backend-ptty.onrender.com` (or local `http://10.98.188.253:8000`)  
Header Required: `X-Device-Key: <DEVICE_API_KEY>`

| Endpoint | Method | Purpose in Firmware |
|---|---|---|
| `/api/v1/iot/sync/time/` | `GET` | Calibrate DS3231 RTC clock with server Unix epoch & ISO time. |
| `/api/v1/iot/devices/{device_id}/config/` | `GET` | Fetch complete 4-compartment schedule, alarm times, policies, and expected weights. |
| `/api/v1/iot/heartbeat/` | `POST` | Report device health (battery %, stepper, servo, ultrasonic status, RTC drift). |
| `/api/v1/iot/events/` | `POST` | Publish live events (`DEVICE_BOOT`, `DOSE_STARTED`, `DOSE_TAKEN`, `DOSE_MISSED`). |
| `/api/v1/iot/events/batch/` | `POST` | Flush events queued to flash during network outages when WiFi reconnects. |
| `/api/v1/iot/devices/{device_id}/commands/` | `GET` | Poll pending remote commands issued by caregivers. |
| `/api/v1/iot/devices/{device_id}/dispenser/schedule/current/` | `GET` | Check if current IST minute has an active scheduled dose or manual trigger. |
| `/api/v1/iot/events/weight-reading/` | `POST` | Send load cell weight after lid close to verify dose intake. |
| `/api/v1/iot/devices/{device_id}/fill/measure/` | `POST` | Report total carousel weight during pill refill calibration. |
| `/api/v1/iot/events/gate-event/` | `POST` | Report gate open / close transitions for anti-tamper security. |

---

## 2. Real-Time WebSocket Channel

* **URL**: `ws://<HOST>:<PORT>/ws/iot/device/<DEVICE_ID>/?device_key=<DEVICE_API_KEY>`
* **Ping**: Send `{"type":"ping"}` every 30 seconds.
* **Ack**: Send `{"type":"ack", "command_id":"<ID>"}` after handling incoming command.

---

## 3. Remote Commands Handled by Firmware

| Command Type | What Hardware Does |
|---|---|
| `DISPENSE_NOW` / `TRIGGER_DOSE` | Rotates stepper to compartment, buzzes alarm, opens servo when hand is detected. |
| `START_FILL_MODE` | Rotates to specified compartment, opens servo lid, enters refill mode. |
| `NEXT_COMPARTMENT` | Closes servo lid, rotates to next compartment, reopens lid. |
| `END_FILL_MODE` | Closes lid, sounds completion beep, re-fetches schedule config. |
| `READ_FILL_WEIGHT` | Settles 3s, reads HX711 load cell, posts weight to backend. |
| `GATE_LOCK` | Closes servo lid, plays missed dose audio, blocks manual opening. |
| `GATE_UNLOCK` | Plays caregiver unlock prompt, clears locked flag, allows dispensing. |
| `SYNC_CONFIG` / `SYNC_SCHEDULE` | Calls config API and updates in-memory slot schedules. |
| `SYNC_TIME` | Calls sync time API and adjusts DS3231 RTC clock. |
