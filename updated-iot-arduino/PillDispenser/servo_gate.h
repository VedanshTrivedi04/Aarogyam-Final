#ifndef SERVO_GATE_H
#define SERVO_GATE_H

#include <Arduino.h>
#include "config.h"

// ============================================================
// SG90 SERVO GATE CONTROL (50Hz PWM)
// ============================================================
// Uses ESP32 hardware PWM (LEDC) with 16-bit resolution to match
// MicroPython's duty_u16 formula exactly without external libraries.

#define SERVO_LEDC_CHANNEL   0
#define SERVO_LEDC_FREQ      50
#define SERVO_LEDC_RES       16

inline void initServo() {
    #if ESP_IDF_VERSION_MAJOR >= 5
    ledcAttach(SERVO_PIN, SERVO_LEDC_FREQ, SERVO_LEDC_RES);
    #else
    ledcSetup(SERVO_LEDC_CHANNEL, SERVO_LEDC_FREQ, SERVO_LEDC_RES);
    ledcAttachPin(SERVO_PIN, SERVO_LEDC_CHANNEL);
    #endif
}

inline void setServoAngle(int angle) {
    if (angle < 0) angle = 0;
    if (angle > 180) angle = 180;

    // Exact formula matching MicroPython: duty = 1638 + (angle / 180) * (8192 - 1638)
    uint32_t duty = (uint32_t)(1638 + ((float)angle / 180.0f) * (8192 - 1638));

    #if ESP_IDF_VERSION_MAJOR >= 5
    ledcWrite(SERVO_PIN, duty);
    #else
    ledcWrite(SERVO_LEDC_CHANNEL, duty);
    #endif
}

inline void openServo() {
    setServoAngle(SERVO_OPEN_ANGLE);
    Serial.println("LID OPEN");
}

inline void closeServo() {
    setServoAngle(SERVO_CLOSED_ANGLE);
    Serial.println("LID CLOSED");
}

#endif // SERVO_GATE_H
