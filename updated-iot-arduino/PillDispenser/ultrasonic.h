#ifndef ULTRASONIC_H
#define ULTRASONIC_H

#include <Arduino.h>
#include "config.h"

// ============================================================
// HC-SR04 ULTRASONIC SENSOR
// ============================================================

inline void initUltrasonic() {
    pinMode(ULTRASONIC_TRIG, OUTPUT);
    pinMode(ULTRASONIC_ECHO, INPUT);
    digitalWrite(ULTRASONIC_TRIG, LOW);
}

inline float getDistance() {
    // Clean trigger pulse
    digitalWrite(ULTRASONIC_TRIG, LOW);
    delayMicroseconds(2);

    // 10 microsecond HIGH pulse
    digitalWrite(ULTRASONIC_TRIG, HIGH);
    delayMicroseconds(10);
    digitalWrite(ULTRASONIC_TRIG, LOW);

    // 30,000 microsecond timeout (approx 5 meters max)
    unsigned long duration = pulseIn(ULTRASONIC_ECHO, HIGH, 30000);

    if (duration == 0) {
        return -1.0f; // No echo / timeout
    }

    // Distance calculation: (duration * 0.0343 cm/us) / 2
    float distance = (duration * 0.0343f) / 2.0f;
    return distance;
}

#endif // ULTRASONIC_H
