// ============================================================
// hardware.h — MedAdhere ESP32 Hardware Abstraction v2.1
// Stepper : 28BYJ-48 + ULN2003 (4-wire half-step)
// Load cell: 1 kg HX711  (real sensor — NO stub)
// Speaker  : DFPlayer Mini MP3 module
// Gate     : SG90 Servo
// Sensor   : HC-SR04 Ultrasonic
// Display  : SSD1306 OLED
// RTC      : DS3231
//
// Required libraries (install via Arduino Library Manager):
//   • ESP32Servo
//   • Adafruit SSD1306 + Adafruit GFX
//   • RTClib (Adafruit)
//   • HX711 by bogde
//   • DFRobotDFPlayerMini
// ============================================================
#pragma once
#include <Arduino.h>
#include <ESP32Servo.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <RTClib.h>
#include <HX711.h>
#include <DFRobotDFPlayerMini.h>
#include "config.h"

// ── Peripheral Objects ───────────────────────────────────────
Adafruit_SSD1306 oled(OLED_WIDTH, OLED_HEIGHT, &Wire, -1);
RTC_DS3231        rtc;
Servo             lidServo;
HX711             loadCell;

// DFPlayer uses Serial2 (dedicated UART — no conflict with debug Serial)
HardwareSerial    dfSerial(2);
DFRobotDFPlayerMini dfPlayer;

// ── Runtime State ────────────────────────────────────────────
bool  rtcAvailable    = false;
bool  lidIsOpen       = false;
bool  dfPlayerReady   = false;
float lastWeightGrams = 0.0f;

// ── 28BYJ-48 Half-Step Sequence ──────────────────────────────
const int STEPPER_PINS[4] = {
  STEPPER_IN1, STEPPER_IN2, STEPPER_IN3, STEPPER_IN4
};
const int HALF_STEP[8][4] = {
  {1, 0, 0, 0}, {1, 1, 0, 0}, {0, 1, 0, 0}, {0, 1, 1, 0},
  {0, 0, 1, 0}, {0, 0, 1, 1}, {0, 0, 0, 1}, {1, 0, 0, 1},
};
int stepIndex          = 0;
int currentCompartment = 1;

// ─────────────────────────────────────────────────────────────
// Stepper
// ─────────────────────────────────────────────────────────────
void hw_stepperStep(int numSteps, bool clockwise = true) {
  for (int i = 0; i < numSteps; i++) {
    for (int pin = 0; pin < 4; pin++) {
      digitalWrite(STEPPER_PINS[pin], HALF_STEP[stepIndex][pin]);
    }
    stepIndex = clockwise ? (stepIndex + 1) % 8 : (stepIndex + 7) % 8;
    vTaskDelay(pdMS_TO_TICKS(2));  // 2 ms per half-step (precise RTOS timing)
  }
  // Power off coils after move — prevents overheating
  for (int pin = 0; pin < 4; pin++) {
    digitalWrite(STEPPER_PINS[pin], LOW);
  }
}

void hw_rotateTo(int targetCompartment) {
  if (targetCompartment == currentCompartment) return;

  int diff = targetCompartment - currentCompartment;
  if (diff < 0) diff += TOTAL_COMPARTMENTS;

  int steps = diff * STEPS_PER_SLOT;
  hw_stepperStep(steps, true);
  currentCompartment = targetCompartment;

  Serial.printf("[HW] Rotated to compartment %d (%d steps)\n",
                currentCompartment, steps);
}

// ─────────────────────────────────────────────────────────────
// Servo — Lid Gate
// ─────────────────────────────────────────────────────────────
void hw_openLid() {
  lidServo.write(SERVO_OPEN_DEG);
  lidIsOpen = true;
  Serial.println("[HW] Lid OPENED");
}

void hw_closeLid() {
  lidServo.write(SERVO_CLOSE_DEG);
  lidIsOpen = false;
  Serial.println("[HW] Lid CLOSED");
}

// ─────────────────────────────────────────────────────────────
// Ultrasonic — Hand Detection
// ─────────────────────────────────────────────────────────────
float hw_getUltrasonicCM() {
  digitalWrite(ULTRASONIC_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(ULTRASONIC_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(ULTRASONIC_TRIG, LOW);
  long dur = pulseIn(ULTRASONIC_ECHO, HIGH, 30000);
  return dur * 0.034f / 2.0f;
}

bool hw_isHandDetected() {
  float d = hw_getUltrasonicCM();
  return (d > 0 && d <= HAND_DETECT_DIST_CM);
}

// ─────────────────────────────────────────────────────────────
// HX711 — 1 kg Load Cell
// ─────────────────────────────────────────────────────────────
float hw_getWeightGrams() {
  if (!loadCell.is_ready()) {
    Serial.println("[HW] Load cell not ready — returning last value");
    return lastWeightGrams;
  }
  float w = loadCell.get_units(5);  // average of 5 readings
  if (w < 0.0f) w = 0.0f;           // clamp negative drift near zero
  lastWeightGrams = w;
  Serial.printf("[HW] Weight: %.2f g\n", w);
  return w;
}

/**
 * Median-of-5 reading. The whole dose decision rests on these grams, and a
 * single averaged sample right after the stepper moves can be skewed by
 * residual carousel wobble. A median throws out those spikes; a mean folds
 * them in.
 */
float hw_getStableWeightGrams() {
  const int N = 5;
  float samples[N];

  for (int i = 0; i < N; i++) {
    samples[i] = hw_getWeightGrams();
    vTaskDelay(pdMS_TO_TICKS(120));
  }

  for (int i = 1; i < N; i++) {              // insertion sort, N is tiny
    float key = samples[i];
    int j = i - 1;
    while (j >= 0 && samples[j] > key) {
      samples[j + 1] = samples[j];
      j--;
    }
    samples[j + 1] = key;
  }

  float median = samples[N / 2];
  Serial.printf("[HW] Stable weight: %.2f g\n", median);
  return median;
}

void hw_tareLoadCell() {
  loadCell.tare();
  Serial.println("[HW] Load cell tared");
}

// ─────────────────────────────────────────────────────────────
// DFPlayer Mini — Audio Playback
// ─────────────────────────────────────────────────────────────
void hw_playTrack(int track) {
  if (!dfPlayerReady) {
    Serial.printf("[DFPlayer] Not ready — cannot play track %d\n", track);
    return;
  }
  dfPlayer.play(track);
  Serial.printf("[DFPlayer] Playing track %d\n", track);
}

void hw_dfplayerStop() {
  if (dfPlayerReady) dfPlayer.stop();
}

bool hw_dfplayerIsBusy() {
  // BUSY pin is LOW when playing — only valid if pin is wired
  return (digitalRead(DFPLAYER_BUSY) == LOW);
}

// ─────────────────────────────────────────────────────────────
// RTC DS3231
// ─────────────────────────────────────────────────────────────
String hw_rtcGetTime() {
  if (rtcAvailable) {
    DateTime now = rtc.now();
    char buf[6];
    snprintf(buf, sizeof(buf), "%02d:%02d", now.hour(), now.minute());
    return String(buf);
  }
  struct tm t;
  if (getLocalTime(&t, 500)) {
    char buf[6]; strftime(buf, sizeof(buf), "%H:%M", &t);
    return String(buf);
  }
  return "00:00";
}

String hw_rtcGetISO() {
  if (rtcAvailable) {
    DateTime now = rtc.now();
    char buf[25];
    snprintf(buf, sizeof(buf), "%04d-%02d-%02dT%02d:%02d:%02d",
             now.year(), now.month(), now.day(),
             now.hour(), now.minute(), now.second());
    return String(buf);
  }
  struct tm t;
  if (getLocalTime(&t, 500)) {
    char buf[25]; strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%S", &t);
    return String(buf);
  }
  return "";
}

/**
 * Current local hour/minute. Returns false if no clock source is usable —
 * the scheduler must not fire doses off a garbage time.
 */
bool hw_rtcGetHourMinute(int& hour, int& minute) {
  if (rtcAvailable) {
    DateTime now = rtc.now();
    if (now.year() >= 2024) {       // sane clock (DS3231 reads 2000 unset)
      hour = now.hour();
      minute = now.minute();
      return true;
    }
  }
  struct tm t;
  if (getLocalTime(&t, 500) && (t.tm_year + 1900) >= 2024) {
    hour = t.tm_hour;
    minute = t.tm_min;
    return true;
  }
  return false;
}

/** Local date as YYYYMMDD, or 0 if no clock source. Used for day rollover. */
uint32_t hw_rtcGetYYYYMMDD() {
  if (rtcAvailable) {
    DateTime now = rtc.now();
    if (now.year() >= 2024) {
      return now.year() * 10000UL + now.month() * 100UL + now.day();
    }
  }
  struct tm t;
  if (getLocalTime(&t, 500) && (t.tm_year + 1900) >= 2024) {
    return (t.tm_year + 1900) * 10000UL + (t.tm_mon + 1) * 100UL + t.tm_mday;
  }
  return 0;
}

bool hw_rtcIsMidnight() {
  if (rtcAvailable) {
    DateTime now = rtc.now();
    return (now.hour() == 0 && now.minute() == 0 && now.second() < 10);
  }
  struct tm t;
  if (getLocalTime(&t, 500)) {
    return (t.tm_hour == 0 && t.tm_min == 0 && t.tm_sec < 10);
  }
  return false;
}

void hw_rtcSyncFromNTP() {
  if (!rtcAvailable) return;
  struct tm t;
  if (getLocalTime(&t, 5000)) {
    rtc.adjust(DateTime(t.tm_year + 1900, t.tm_mon + 1, t.tm_mday,
                        t.tm_hour, t.tm_min, t.tm_sec));
    Serial.println("[RTC] Synced from NTP");
  } else {
    Serial.println("[RTC] NTP sync failed — keeping RTC time");
  }
}

// ─────────────────────────────────────────────────────────────
// OLED Display
// ─────────────────────────────────────────────────────────────
void hw_displayMessage(String l1, String l2 = "", String l3 = "") {
  oled.clearDisplay();
  oled.setTextSize(1);
  oled.setTextColor(SSD1306_WHITE);
  oled.setCursor(0,  0); oled.println(l1);
  oled.setCursor(0, 20); oled.println(l2);
  oled.setCursor(0, 40); oled.println(l3);
  oled.display();
}

void hw_displayMedicine(String med, String dosage, String time) {
  oled.clearDisplay();
  oled.setTextSize(2);
  oled.setCursor(0, 0);  oled.println(med.substring(0, 8));
  oled.setTextSize(1);
  oled.setCursor(0, 20); oled.print("Dose: "); oled.println(dosage);
  oled.setCursor(0, 32); oled.print("Time: "); oled.println(time);
  oled.setCursor(0, 48); oled.println("Take your medicine!");
  oled.display();
}

void hw_displayDoseInfo(int compartmentNum, const char* displayText) {
  oled.clearDisplay();
  oled.setTextSize(1);
  oled.setTextColor(SSD1306_WHITE);
  oled.setCursor(0, 0);
  oled.print("Compartment "); oled.println(compartmentNum);
  int y = 12;
  String text = String(displayText);
  int start = 0;
  while (y < 64 && start < (int)text.length()) {
    int nl = text.indexOf('\n', start);
    String line = (nl < 0) ? text.substring(start) : text.substring(start, nl);
    oled.setCursor(0, y); oled.println(line.substring(0, 21));
    y += 10;
    if (nl < 0) break;
    start = nl + 1;
  }
  oled.display();
}

void hw_displayFillMode(int compartment, const char* medName) {
  oled.clearDisplay();
  oled.setTextSize(1);
  oled.setTextColor(SSD1306_WHITE);
  oled.setCursor(0,  0); oled.println("=== FILL MODE ===");
  oled.setCursor(0, 12); oled.print("Compartment: "); oled.println(compartment);
  oled.setCursor(0, 24); oled.println("Add medicine:");
  oled.setCursor(0, 36); oled.println(String(medName).substring(0, 21));
  oled.setCursor(0, 50); oled.println("Confirm on portal ->");
  oled.display();
}

void hw_displayGateLocked() {
  oled.clearDisplay();
  oled.setTextSize(1);
  oled.setTextColor(SSD1306_WHITE);
  oled.setCursor(0,  0); oled.println("!! GATE LOCKED !!");
  oled.setCursor(0, 16); oled.println("Dose window closed.");
  oled.setCursor(0, 28); oled.println("Caregiver must");
  oled.setCursor(0, 38); oled.println("unlock from app.");
  oled.display();
}

void hw_displayDoseResult(const char* status) {
  oled.clearDisplay();
  oled.setTextSize(2);
  oled.setTextColor(SSD1306_WHITE);
  oled.setCursor(0, 0);
  if (strcmp(status, "taken") == 0) {
    oled.println("Dose OK!");
    oled.setTextSize(1); oled.setCursor(0, 24); oled.println("Full dose confirmed.");
  } else if (strcmp(status, "partial") == 0) {
    oled.println("Partial");
    oled.setTextSize(1); oled.setCursor(0, 24); oled.println("Dose incomplete.");
  } else {
    oled.println("Missed!");
    oled.setTextSize(1); oled.setCursor(0, 24); oled.println("No dose detected.");
  }
  oled.display();
}

void hw_displayRTCStatus() {
  String timeStr = hw_rtcGetTime();
  oled.fillRect(0, 54, 128, 10, SSD1306_BLACK);
  oled.setCursor(0, 54);
  oled.setTextSize(1);
  oled.print(rtcAvailable ? "RTC " : "NTP ");
  oled.print(timeStr);
  oled.display();
}

// ─────────────────────────────────────────────────────────────
// Buzzer / LED
// ─────────────────────────────────────────────────────────────
void hw_beep(int times = 1, int ms = 100) {
  for (int i = 0; i < times; i++) {
    digitalWrite(BUZZER_PIN, HIGH);
    delay(ms);
    digitalWrite(BUZZER_PIN, LOW);
    delay(60);
  }
}

void hw_alertAlarm() {
  for (int i = 0; i < 3; i++) {
    digitalWrite(BUZZER_PIN, HIGH);
    digitalWrite(LED_PIN,    HIGH);
    delay(300);
    digitalWrite(BUZZER_PIN, LOW);
    digitalWrite(LED_PIN,    LOW);
    delay(200);
  }
}

// ─────────────────────────────────────────────────────────────
// Battery
// ─────────────────────────────────────────────────────────────
int hw_getBatteryLevel() {
  int raw = analogRead(BATTERY_PIN);
  int pct = map(raw, 1800, 4095, 0, 100);
  return constrain(pct, 0, 100);
}

const char* hw_getStatus() { return "ok"; }

// ─────────────────────────────────────────────────────────────
// hw_initAll — Initialize every peripheral
// ─────────────────────────────────────────────────────────────
void hw_initAll() {
  // Stepper coil pins
  for (int i = 0; i < 4; i++) {
    pinMode(STEPPER_PINS[i], OUTPUT);
    digitalWrite(STEPPER_PINS[i], LOW);
  }

  // Servo — gate closed at boot
  lidServo.attach(SERVO_PIN);
  lidServo.write(SERVO_CLOSE_DEG);

  // Ultrasonic
  pinMode(ULTRASONIC_TRIG, OUTPUT);
  pinMode(ULTRASONIC_ECHO, INPUT);

  // Buzzer & LED
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(LED_PIN,    OUTPUT);

  // DFPlayer busy pin (optional — input with pull-up)
  pinMode(DFPLAYER_BUSY, INPUT_PULLUP);

  // Battery ADC
  pinMode(BATTERY_PIN, INPUT);

  // I2C bus — shared by OLED + DS3231
  Wire.begin(OLED_SDA, OLED_SCL);

  // OLED
  if (!oled.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("[HW] OLED FAILED — check wiring");
  } else {
    oled.clearDisplay();
    oled.setTextSize(1);
    oled.setTextColor(SSD1306_WHITE);
    oled.setCursor(0, 0);  oled.println("MedAdhere v2.1");
    oled.setCursor(0, 12); oled.println("Booting...");
    oled.display();
  }

  // RTC DS3231
  if (rtc.begin()) {
    rtcAvailable = true;
    if (rtc.lostPower()) {
      Serial.println("[RTC] DS3231 lost power — awaiting NTP sync");
    } else {
      DateTime now = rtc.now();
      Serial.printf("[RTC] DS3231 OK: %02d:%02d:%02d\n",
                    now.hour(), now.minute(), now.second());
    }
  } else {
    rtcAvailable = false;
    Serial.println("[RTC] DS3231 NOT FOUND — NTP only");
  }

  // HX711 Load Cell
  loadCell.begin(LOADCELL_DOUT, LOADCELL_SCK);
  loadCell.set_scale(LOADCELL_SCALE);
  loadCell.tare();
  Serial.println("[HW] HX711 initialized and tared");

  // DFPlayer Mini
  dfSerial.begin(9600, SERIAL_8N1, DFPLAYER_RX, DFPLAYER_TX);
  delay(1000);  // DFPlayer needs ~1 s to boot after power-on
  if (dfPlayer.begin(dfSerial, /*isACK*/ true, /*doReset*/ true)) {
    dfPlayer.volume(DFPLAYER_VOLUME);
    dfPlayerReady = true;
    Serial.printf("[DFPlayer] Ready — volume %d\n", DFPLAYER_VOLUME);
  } else {
    dfPlayerReady = false;
    Serial.println("[DFPlayer] FAILED — check wiring / SD card");
  }

  Serial.println("[HW] All hardware initialized");
}
