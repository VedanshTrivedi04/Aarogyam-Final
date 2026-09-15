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
_last_ping_time = 0
PING_INTERVAL_SECONDS = 30  # must stay well under the 60s keepalive passed to MQTTClient


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


_last_reconnect_attempt = 0
RECONNECT_DELAY_SECONDS = 15


def connect_mqtt():
    """Connect to the MQTT broker and subscribe to commands topic."""
    global _client, _connected, _last_ping_time
    import gc
    gc.collect()

    if not is_connected():
        print("[MQTT] WiFi not connected. Cannot connect to MQTT broker.")
        _connected = False
        return False

    try:
        print("[MQTT] Connecting to broker: %s:%d..." % (MQTT_BROKER, MQTT_PORT))
        is_ssl = (MQTT_PORT == 8883)
        ssl_params = {"server_hostname": MQTT_BROKER} if is_ssl else {}

        _client = MQTTClient(
            client_id=MQTT_CLIENT_ID,
            server=MQTT_BROKER,
            port=MQTT_PORT,
            user=MQTT_USER,
            password=MQTT_PASSWORD,
            keepalive=60,
            ssl=is_ssl,
            ssl_params=ssl_params
        )
        _client.set_callback(_on_message)
        _client.connect()
        _connected = True
        _last_ping_time = time.time()
        print("[MQTT] Connected to broker successfully!")

        # Subscribe to device command topic
        try:
            _client.subscribe(MQTT_TOPIC_COMMANDS)
            print("[MQTT] Subscribed to command topic:", MQTT_TOPIC_COMMANDS)
        except Exception as sub_err:
            print("[MQTT] Subscribe warning (publishing still active):", sub_err)
        return True

    except Exception as e:
        print("[MQTT] Connection failed:", e)
        _connected = False
        _client = None
        return False


def is_mqtt_connected():
    return _connected and _client is not None


def check_messages():
    """Non-blocking poll for incoming MQTT messages, keepalive ping, and auto-reconnect."""
    global _client, _connected, _last_ping_time, _last_reconnect_attempt

    # If disconnected, auto-reconnect every 15 seconds
    if not _connected or _client is None:
        now = time.time()
        if now - _last_reconnect_attempt >= RECONNECT_DELAY_SECONDS:
            _last_reconnect_attempt = now
            if is_connected():
                connect_mqtt()
        return

    try:
        _client.check_msg()

        now = time.time()
        if now - _last_ping_time >= PING_INTERVAL_SECONDS:
            _last_ping_time = now
            _client.ping()
    except OSError as e:
        _connected = False
        _client = None
    except Exception as e:
        _connected = False
        _client = None


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
