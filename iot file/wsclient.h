// ============================================================
// wsclient.h — WebSocket command channel
//
// Replaces the old 10-second HTTP command poll. One socket stays open and
// commands arrive the moment the backend queues them, so caregiver actions
// (unlock gate, take-now, start fill) are sub-second instead of a poll away.
//
// Requires: "WebSockets" by Markus Sattler (Links2004) — Arduino Library Manager.
//
// Auth is the device api_key as a query param: ESP32 WebSocket clients cannot
// set custom headers during the handshake, so X-Device-Key is not an option.
//
// Delivery is at-least-once — the backend keeps a command PENDING until acked,
// so the same command_id can arrive twice. Dedup is handled by the caller.
// ============================================================
#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>
#include <WebSocketsClient.h>
#include "config.h"

WebSocketsClient wsClient;
bool wsConnected = false;

// Defined in the .ino — shared with the HTTP safety-net poll so both paths
// run identical command handling.
void handleDeviceCommand(const char* type, const char* commandId, JsonObject payload);

bool ws_isConnected() { return wsConnected; }

void ws_sendAck(const char* commandId) {
  if (!wsConnected || !commandId || !strlen(commandId)) return;

  StaticJsonDocument<128> msg;
  msg["type"]       = "ack";
  msg["command_id"] = commandId;

  String out;
  serializeJson(msg, out);
  wsClient.sendTXT(out);
}

void ws_sendPing() {
  if (!wsConnected) return;
  wsClient.sendTXT("{\"type\":\"ping\"}");
}

static void ws_onMessage(uint8_t* payload, size_t length) {
  StaticJsonDocument<2048> doc;
  DeserializationError err = deserializeJson(doc, payload, length);
  if (err) {
    Serial.printf("[WS] Bad JSON: %s\n", err.c_str());
    return;
  }

  const char* msgType = doc["type"] | "";

  if (strcmp(msgType, "command") == 0) {
    const char* cmdType = doc["command_type"] | "";
    const char* cmdId   = doc["command_id"]   | "";
    Serial.printf("[WS] Command: %s\n", cmdType);

    handleDeviceCommand(cmdType, cmdId, doc["payload"].as<JsonObject>());
    ws_sendAck(cmdId);

  } else if (strcmp(msgType, "pong") == 0) {
    // Server clock rides along on every pong — cheap drift check.
    long ts = doc["server_unix_time"] | 0L;
    if (ts > 0) Serial.printf("[WS] pong (server time %ld)\n", ts);
  }
}

static void ws_onEvent(WStype_t type, uint8_t* payload, size_t length) {
  switch (type) {
    case WStype_CONNECTED:
      wsConnected = true;
      Serial.println("[WS] Command channel connected");
      break;

    case WStype_DISCONNECTED:
      wsConnected = false;
      Serial.println("[WS] Disconnected — will retry");
      break;

    case WStype_TEXT:
      ws_onMessage(payload, length);
      break;

    case WStype_ERROR:
      Serial.println("[WS] Socket error");
      break;

    default:
      break;
  }
}

void ws_begin() {
  wsClient.begin(BACKEND_HOST, BACKEND_PORT, WS_PATH);
  wsClient.onEvent(ws_onEvent);
  wsClient.setReconnectInterval(WS_RECONNECT_MS);
  // Heartbeat: ping every 30 s, expect a pong within 10 s, drop after 2 misses.
  // Without this a half-open socket looks alive and commands vanish.
  wsClient.enableHeartbeat(30000, 10000, 2);
  Serial.printf("[WS] Connecting to ws://%s:%d\n", BACKEND_HOST, BACKEND_PORT);
}

/** Must be called frequently (every ~10 ms) from the network task. */
void ws_loop() {
  wsClient.loop();
}
