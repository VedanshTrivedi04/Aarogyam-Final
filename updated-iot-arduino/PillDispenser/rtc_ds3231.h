#ifndef RTC_DS3231_H
#define RTC_DS3231_H

#include <Arduino.h>
#include <Wire.h>
#include "config.h"

// ============================================================
// DS3231 REAL TIME CLOCK (I2C WIRE IMPLEMENTATION)
// ============================================================
// Direct I2C communication on pins 23/22 matching rtc.py exactly
// without requiring third-party library installations.

struct DateTime {
    int year;
    int month;
    int day;
    int hour;
    int minute;
    int second;
};

inline uint8_t bcdToDec(uint8_t val) {
    return ((val >> 4) * 10) + (val & 0x0F);
}

inline uint8_t decToBcd(uint8_t val) {
    return ((val / 10) << 4) | (val % 10);
}

inline bool initRTC() {
    Wire.begin(RTC_SDA, RTC_SCL, 100000);

    Wire.beginTransmission(RTC_ADDRESS);
    if (Wire.endTransmission() != 0) {
        Serial.println("RTC NOT FOUND on I2C bus!");
        return false;
    }
    return true;
}

inline DateTime readRTC() {
    DateTime dt = {2026, 1, 1, 0, 0, 0};

    Wire.beginTransmission(RTC_ADDRESS);
    Wire.write(0x00); // Start at register 0
    if (Wire.endTransmission() != 0) {
        return dt;
    }

    Wire.requestFrom((uint8_t)RTC_ADDRESS, (uint8_t)7);
    if (Wire.available() >= 7) {
        dt.second = bcdToDec(Wire.read() & 0x7F);
        dt.minute = bcdToDec(Wire.read() & 0x7F);
        dt.hour   = bcdToDec(Wire.read() & 0x3F);
        Wire.read(); // day of week (ignored)
        dt.day    = bcdToDec(Wire.read() & 0x3F);
        dt.month  = bcdToDec(Wire.read() & 0x1F);
        dt.year   = 2000 + bcdToDec(Wire.read());
    }

    return dt;
}

inline void setRTC(int year, int month, int day, int hour, int minute, int second) {
    Wire.beginTransmission(RTC_ADDRESS);
    Wire.write(0x00); // Register pointer

    Wire.write(decToBcd(second));
    Wire.write(decToBcd(minute));
    Wire.write(decToBcd(hour));
    Wire.write(decToBcd(1)); // Day of week (1)
    Wire.write(decToBcd(day));
    Wire.write(decToBcd(month));
    Wire.write(decToBcd(year >= 2000 ? year - 2000 : year));

    Wire.endTransmission();

    Serial.printf("[RTC] Time set to: %04d-%02d-%02d %02d:%02d:%02d\n",
                  year, month, day, hour, minute, second);
}

inline String getRTCISOString() {
    DateTime dt = readRTC();
    char buf[25];
    snprintf(buf, sizeof(buf), "%04d-%02d-%02dT%02d:%02d:%02d",
             dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second);
    return String(buf);
}

inline bool checkRTC() {
    if (!initRTC()) {
        return false;
    }

    DateTime now = readRTC();
    Serial.printf("RTC Date: %02d/%02d/%04d\n", now.day, now.month, now.year);
    Serial.printf("RTC Time: %02d:%02d:%02d\n", now.hour, now.minute, now.second);
    return true;
}

#endif // RTC_DS3231_H
