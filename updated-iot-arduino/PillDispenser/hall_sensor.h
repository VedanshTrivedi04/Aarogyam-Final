#ifndef HALL_SENSOR_H
#define HALL_SENSOR_H

#include <Arduino.h>
#include "config.h"
#include "stepper.h"

// ============================================================
// HALL SENSOR (HOME POSITION)
// ============================================================

inline void initHallSensor() {
    pinMode(HALL_PIN, INPUT_PULLUP);
}

inline bool isHome() {
    // A3144 Hall sensor goes LOW when magnet is detected
    return digitalRead(HALL_PIN) == LOW;
}

inline bool findHome() {
    Serial.println();
    Serial.println("Searching HOME...");

    // Step motor forward until magnet detected (Pin 33 == LOW)
    while (digitalRead(HALL_PIN) == HIGH) {
        stepMotor(1);
    }

    stopMotor();
    delay(300);

    resetStepIndex();
    resetCompartment();

    Serial.println("HOME FOUND");
    Serial.println("Current Compartment = 1");

    return true;
}

#endif // HALL_SENSOR_H
