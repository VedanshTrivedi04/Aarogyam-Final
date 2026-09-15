#ifndef DISPENSER_H
#define DISPENSER_H

#include <Arduino.h>
#include "config.h"
#include "stepper.h"
#include "servo_gate.h"
#include "ultrasonic.h"

// ============================================================
// CORE DISPENSING EXECUTION (PRESERVING EXACT SENSOR LOGIC)
// ============================================================

inline String dispense(int compartment, const char* medicine, int dose = 1) {
    Serial.println();
    Serial.println("================================");
    Serial.println("DISPENSING STARTED");
    Serial.println("================================");
    Serial.print("Medicine: "); Serial.println(medicine);
    Serial.print("Dose: "); Serial.println(dose);
    Serial.print("Compartment: "); Serial.println(compartment);

    // STEP 1 - MOVE STEPPER TO COMPARTMENT
    bool success = rotateToCompartment(compartment);
    if (!success) {
        Serial.println("Stepper movement failed.");
        return "ERROR";
    }

    // STEP 2 - DISPENSING WINDOW
    Serial.println();
    Serial.print("Dispensing window active for ");
    Serial.print(DISPENSING_WINDOW_MINUTES);
    Serial.println(" minutes.");

    unsigned long startTime = millis();
    unsigned long windowMs = (unsigned long)DISPENSING_WINDOW_MINUTES * 60UL * 1000UL;
    bool doseTaken = false;

    // HAND DETECTION LOOP
    while ((millis() - startTime) <= windowMs) {
        float distance = getDistance();

        if (distance < 0) {
            Serial.println("NO ECHO");
            delay(300);
            continue;
        }

        Serial.print("Distance: ");
        Serial.print(distance, 2);
        Serial.println(" cm");

        // HAND DETECTED
        if (distance <= HAND_DISTANCE_CM) {
            Serial.println("HAND DETECTED");
            openServo();

            // Keep lid open while hand is present
            while (true) {
                if ((millis() - startTime) > windowMs) {
                    break;
                }

                distance = getDistance();
                if (distance < 0) {
                    delay(200);
                    continue;
                }

                if (distance > HAND_DISTANCE_CM) {
                    Serial.println("HAND REMOVED");
                    break;
                }

                delay(200);
            }

            // Close lid
            closeServo();
            doseTaken = true;
            break;
        }

        delay(200);
    }

    // WINDOW END
    closeServo();

    Serial.println();
    Serial.println("================================");
    Serial.println("DISPENSING WINDOW CLOSED");
    Serial.println("ULTRASONIC OFF");
    Serial.println("LID LOCKED/CLOSED");
    Serial.println("================================");

    if (doseTaken) {
        Serial.println("[DISPENSER] Dose successfully taken by patient!");
        return "TAKEN";
    } else {
        Serial.println("[DISPENSER] Window expired. Dose MISSED by patient.");
        return "MISSED";
    }
}

#endif // DISPENSER_H
