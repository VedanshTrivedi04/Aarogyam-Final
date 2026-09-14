import json
import time
from umqttsimple import MQTTClient, MQTTException
from wifi import is_connected

from config import (
    MQTT_BROKER,
    MQTT_PORT,
    MQTT_CLIENT_ID,
    MQTT_USER,
    MQTT_PASSWORD,
    MQTT_TOPIC_EVENTS,
    MQTT_TOPIC_HEARTBEAT,
    MQTT_TOPIC_COMMANDS
)


_client = None
_connected = False
_command_callback = None


def set_command_callback(cb):
    """Register custom callback for incoming MQTT commands."""
    global _command_callback
    _command_callback = cb


def _on_message(topic, msg):
    """Internal MQTT callback when message is received."""
    topic_str = topic.decode("utf-8") if isinstance(topic, bytes) else str(topic)
    msg_str = msg.decode("utf-8") if isinstance(msg, bytes) else str(msg)

    print()
    print("[MQTT] Received message on topic:", topic_str)
    print("[MQTT] Content:", msg_str)

    try:
        data = json.loads(msg_str)
    except Exception:
        data = {"raw": msg_str}

    if _command_callback:
        try:
            _command_callback(topic_str, data)
        except Exception as e:
            print("[MQTT] Error executing command callback:", e)


def connect_mqtt():
    """Connect to the MQTT broker and subscribe to commands topic."""
    global _client, _connected

    if not is_connected():
        print("[MQTT] WiFi not connected. Cannot connect to MQTT broker.")
        _connected = False
        return False

    try:
        print("[MQTT] Connecting to broker: %s:%d..." % (MQTT_BROKER, MQTT_PORT))
        _client = MQTTClient(
            client_id=MQTT_CLIENT_ID,
            server=MQTT_BROKER,
            port=MQTT_PORT,
            user=MQTT_USER,
            password=MQTT_PASSWORD,
            keepalive=60
        )
        _client.set_callback(_on_message)
        _client.connect()
        _connected = True
        print("[MQTT] Connected to broker successfully!")

        # Subscribe to device command topic
        _client.subscribe(MQTT_TOPIC_COMMANDS)
        print("[MQTT] Subscribed to command topic:", MQTT_TOPIC_COMMANDS)
        return True

    except Exception as e:
        print("[MQTT] Connection failed:", e)
        _connected = False
        _client = None
        return False


def is_mqtt_connected():
    return _connected and _client is not None


def check_messages():
    """Non-blocking poll for incoming MQTT messages."""
    global _client, _connected
    if not _connected or _client is None:
        return

    try:
        _client.check_msg()
    except OSError as e:
        print("[MQTT] Socket error during check_msg:", e)
        _connected = False
        _client = None
    except Exception as e:
        print("[MQTT] check_msg error:", e)


def publish(topic, payload):
    """Publish a JSON payload or string to an MQTT topic."""
    global _client, _connected
    if not _connected or _client is None:
        # Try reconnecting once if WiFi is alive
        if is_connected():
            connect_mqtt()

    if not _connected or _client is None:
        return False

    try:
        if isinstance(payload, (dict, list)):
            msg = json.dumps(payload)
        else:
            msg = str(payload)

        _client.publish(topic, msg)
        print("[MQTT] Published to %s: %s" % (topic, msg[:100]))
        return True
    except Exception as e:
        print("[MQTT] Publish failed:", e)
        _connected = False
        _client = None
        return False


def publish_event(payload):
    """Publish an adherence or device event to the events topic."""
    return publish(MQTT_TOPIC_EVENTS, payload)


def publish_heartbeat(payload):
    """Publish device telemetry/health to the heartbeat topic."""
    return publish(MQTT_TOPIC_HEARTBEAT, payload)
