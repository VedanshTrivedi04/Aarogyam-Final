#ifndef STEPPER_H
#define STEPPER_H

#include <Arduino.h>
#include "config.h"

// ============================================================
// 8-STEP HALF STEP SEQUENCE (28BYJ-48)
// ============================================================
static const uint8_t halfStepSequence[8][4] = {
    {1, 0, 0, 0},
    {1, 1, 0, 0},
    {0, 1, 0, 0},
    {0, 1, 1, 0},
    {0, 0, 1, 0},
    {0, 0, 1, 1},
    {0, 0, 0, 1},
    {1, 0, 0, 1}
};

static int stepIndex = 0;
static int currentCompartment = 1;

inline void initStepper() {
    pinMode(STEPPER_IN1, OUTPUT);
    pinMode(STEPPER_IN2, OUTPUT);
    pinMode(STEPPER_IN3, OUTPUT);
    pinMode(STEPPER_IN4, OUTPUT);

    digitalWrite(STEPPER_IN1, LOW);
    digitalWrite(STEPPER_IN2, LOW);
    digitalWrite(STEPPER_IN3, LOW);
    digitalWrite(STEPPER_IN4, LOW);
}

inline void setCoils(uint8_t a, uint8_t b, uint8_t c, uint8_t d) {
    digitalWrite(STEPPER_IN1, a ? HIGH : LOW);
    digitalWrite(STEPPER_IN2, b ? HIGH : LOW);
    digitalWrite(STEPPER_IN3, c ? HIGH : LOW);
    digitalWrite(STEPPER_IN4, d ? HIGH : LOW);
}

inline void stopMotor() {
    setCoils(0, 0, 0, 0);
}

inline void stepMotor(int direction) {
    stepIndex += direction;
    if (stepIndex >= 8) {
        stepIndex = 0;
    }
    if (stepIndex < 0) {
        stepIndex = 7;
    }

    setCoils(
        halfStepSequence[stepIndex][0],
        halfStepSequence[stepIndex][1],
        halfStepSequence[stepIndex][2],
        halfStepSequence[stepIndex][3]
    );

    delay(STEP_DELAY_MS);
}

inline void resetStepIndex() {
    stepIndex = 0;
}

inline void resetCompartment() {
    currentCompartment = 1;
}

inline int getCurrentCompartment() {
    return currentCompartment;
}

inline bool rotateToCompartment(int target) {
    if (target < 1 || target > TOTAL_COMPARTMENTS) {
        Serial.println("INVALID COMPARTMENT");
        return false;
    }

    int difference = target - currentCompartment;
    if (difference < 0) {
        difference += TOTAL_COMPARTMENTS;
    }

    int steps = difference * STEPS_PER_COMPARTMENT;

    Serial.println();
    Serial.println("Stepper Movement");
    Serial.print("Current: "); Serial.println(currentCompartment);
    Serial.print("Target: "); Serial.println(target);
    Serial.print("Compartments to advance: "); Serial.println(difference);
    Serial.print("Steps: "); Serial.println(steps);

    for (int i = 0; i < steps; i++) {
        stepMotor(1);
    }

    stopMotor();
    currentCompartment = target;

    Serial.print("Reached Compartment: ");
    Serial.println(currentCompartment);

    return true;
}

#endif // STEPPER_H
