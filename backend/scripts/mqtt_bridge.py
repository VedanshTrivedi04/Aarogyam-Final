"""
backend/scripts/mqtt_bridge.py - Bridge service connecting MQTT Broker to Django Backend.

This daemon connects to your MQTT broker, listens to real-time events & heartbeats
from the ESP32 Pill Dispenser, and feeds them into the Django database & adherence engine.

Usage:
    pip install paho-mqtt
    python scripts/mqtt_bridge.py
"""

import os
import sys
import json
import logging

# Initialize Django setup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

import django
django.setup()

from apps.iot.models import Device, DeviceCommand
from apps.iot.services import DeviceService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("MQTT_BRIDGE")

try:
    import paho.mqtt.client as mqtt
except ImportError:
    logger.error("paho-mqtt is not installed! Run: pip install paho-mqtt")
    sys.exit(1)


# ============================================================
# CONFIGURATION
# ============================================================
MQTT_BROKER = os.getenv("MQTT_BROKER", "broker.hivemq.com")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER", None)
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", None)

TOPIC_EVENTS = "medadhere/+/events"
TOPIC_HEARTBEAT = "medadhere/+/heartbeat"


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("Connected to MQTT Broker (%s:%d)", MQTT_BROKER, MQTT_PORT)
        client.subscribe(TOPIC_EVENTS)
        client.subscribe(TOPIC_HEARTBEAT)
        logger.info("Subscribed to: %s and %s", TOPIC_EVENTS, TOPIC_HEARTBEAT)
    else:
        logger.error("Failed to connect to MQTT broker, return code: %d", rc)


def on_message(client, userdata, msg):
    topic = msg.topic
    payload_str = msg.payload.decode("utf-8")

    try:
        data = json.loads(payload_str)
    except Exception as e:
        logger.warning("Received invalid JSON on %s: %s", topic, e)
        return

    # Topic format: medadhere/<device_id>/events or medadhere/<device_id>/heartbeat
    parts = topic.split("/")
    if len(parts) < 3:
        return

    device_id = parts[1]
    channel_type = parts[2]

    try:
        device = Device.objects.filter(id=device_id, is_active=True).first()
        if not device:
            logger.warning("Device %s not found or inactive in database", device_id)
            return

        if channel_type == "events":
            logger.info("Ingesting MQTT Event from Device %s: %s", device_id, data.get("event_type"))
            event, created, resp = DeviceService.ingest_event(device, data)
            logger.info("Event processed: created=%s, response=%s", created, resp)

        elif channel_type == "heartbeat":
            logger.info("Recording MQTT Heartbeat for Device %s", device_id)
            resp = DeviceService.record_heartbeat(device, data)
            logger.debug("Heartbeat result: %s", resp)

    except Exception as e:
        logger.exception("Error processing MQTT message on %s: %s", topic, e)


def publish_command(client, device_id, command_type, payload=None):
    """
    Helper to send a real-time command to a specific device via MQTT.
    """
    topic = f"medadhere/{device_id}/commands"
    message = {
        "command_type": command_type,
        "payload": payload or {}
    }
    client.publish(topic, json.dumps(message))
    logger.info("Sent remote command %s to %s", command_type, topic)


def main():
    client = mqtt.Client()

    if MQTT_USER and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

    client.on_connect = on_connect
    client.on_message = on_message

    logger.info("Starting MQTT Bridge worker...")
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_forever()
    except KeyboardInterrupt:
        logger.info("MQTT Bridge stopped by user.")
    except Exception as e:
        logger.error("MQTT Bridge crashed: %s", e)


if __name__ == "__main__":
    main()
