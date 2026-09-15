#ifndef MQTT_HANDLER_H
#define MQTT_HANDLER_H

#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include "config.h"
#include "rtc_ds3231.h"
#include "api_client.h"

// Forward declaration for dispense callback
void handleRemoteCommand(const char* topic, const char* payload);

static WiFiClient espClient;
static PubSubClient mqttClient(espClient);
static unsigned long lastHeartbeatMs = 0;

inline void mqttCallback(char* topic, byte* payload, unsigned int length) {
    char message[256];
    if (length >= sizeof(message)) length = sizeof(message) - 1;
    memcpy(message, payload, length);
    message[length] = '\0';

    Serial.println();
    Serial.print("[MQTT] Message arrived on topic: ");
    Serial.println(topic);
    Serial.print("[MQTT] Content: ");
    Serial.println(message);

    handleRemoteCommand(topic, message);
}

inline bool initMQTT() {
    mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
    mqttClient.setCallback(mqttCallback);
    return true;
}

inline bool connectMQTT() {
    if (WiFi.status() != WL_CONNECTED) {
        return false;
    }

    if (mqttClient.connected()) {
        return true;
    }

    Serial.printf("[MQTT] Connecting to broker: %s:%d...\n", MQTT_BROKER, MQTT_PORT);

    bool ok = false;
    if (strlen(MQTT_USER) > 0) {
        ok = mqttClient.connect(MQTT_CLIENT_ID, MQTT_USER, MQTT_PASSWORD);
    } else {
        ok = mqttClient.connect(MQTT_CLIENT_ID);
    }

    if (ok) {
        Serial.println("[MQTT] Connected to broker successfully!");
        mqttClient.subscribe(MQTT_TOPIC_COMMANDS);
        Serial.printf("[MQTT] Subscribed to command topic: %s\n", MQTT_TOPIC_COMMANDS);
        return true;
    } else {
        Serial.printf("[MQTT] Connect failed, state: %d\n", mqttClient.state());
        return false;
    }
}

inline bool isMQTTConnected() {
    return mqttClient.connected();
}

inline void loopMQTT() {
    if (WiFi.status() == WL_CONNECTED) {
        if (!mqttClient.connected()) {
            static unsigned long lastReconnect = 0;
            if (millis() - lastReconnect > 10000) {
                lastReconnect = millis();
                connectMQTT();
            }
        } else {
            mqttClient.loop();
        }
    }
}

inline bool publishEvent(const char* eventType, int compartment, const char* medicine = "Unknown", int dose = 1) {
    char payload[300];
    snprintf(payload, sizeof(payload),
             "{\"event_type\":\"%s\",\"compartment\":%d,\"compartment_num\":%d,\"medicine\":\"%s\",\"dose\":%d,\"occurred_at\":\"%s\",\"device_id\":\"%s\",\"firmware_version\":\"%s\"}",
             eventType, compartment, compartment, medicine, dose, getRTCISOString().c_str(), DEVICE_ID, FIRMWARE_VERSION);

    Serial.printf("[EVENT] Emitting: %s (Comp %d)\n", eventType, compartment);

    if (mqttClient.connected()) {
        if (mqttClient.publish(MQTT_TOPIC_EVENTS, payload)) {
            Serial.printf("[MQTT] Event published: %s\n", eventType);
            return true;
        }
    }

    // Fallback to HTTP POST
    Serial.println("[EVENT] MQTT unavailable. Trying HTTP fallback...");
    return httpSendEvent(eventType, compartment);
}

inline bool publishHeartbeat(const char* stepperStatus = "ok", const char* servoStatus = "ok", const char* ultrasonicStatus = "ok") {
    char payload[256];
    snprintf(payload, sizeof(payload),
             "{\"device_id\":\"%s\",\"battery_level\":100,\"firmware_version\":\"%s\",\"stepper_status\":\"%s\",\"servo_status\":\"%s\",\"ultrasonic_status\":\"%s\",\"rtc_time\":\"%s\"}",
             DEVICE_ID, FIRMWARE_VERSION, stepperStatus, servoStatus, ultrasonicStatus, getRTCISOString().c_str());

    if (mqttClient.connected()) {
        if (mqttClient.publish(MQTT_TOPIC_HEARTBEAT, payload)) {
            Serial.println("[MQTT] Heartbeat published successfully.");
            return true;
        }
    }

    // Fallback to HTTP POST
    if (WiFi.status() == WL_CONNECTED) {
        HTTPClient http;
        String url = String(BACKEND_URL) + API_HEARTBEAT;
        http.begin(url);
        http.addHeader("Content-Type", "application/json");
        http.addHeader("X-Device-Key", DEVICE_API_KEY);
        int code = http.POST(payload);
        http.end();
        if (code == 200) {
            Serial.println("[HTTP] Heartbeat sent via HTTP.");
            return true;
        }
    }
    return false;
}

#endif // MQTT_HANDLER_H
