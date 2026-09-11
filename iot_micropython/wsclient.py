"""
wsclient.py - Minimal RFC6455 WebSocket client (commands ke liye).

MicroPython mein koi bharosemand WebSocket client built-in nahi hai, isliye
handshake aur framing yahan khud likha hai. Sirf utna hi implement kiya hai
jitna is command channel ko chahiye:
  - text frames (opcode 0x1)
  - ping/pong (0x9 / 0xA) - server heartbeat ka jawab
  - close (0x8)
  - continuation/fragmented frames NAHI - backend hamesha ek hi frame bhejta hai

Auth: device_key query param mein jaata hai, kyunki WebSocket handshake mein
custom header (X-Device-Key) bhejna browser/ESP32 dono par reliable nahi.

Delivery at-least-once hai: backend command ko PENDING rakhta hai jab tak ack
na mile, to wahi command_id dobara aa sakta hai. Dedup caller ka kaam hai.
"""
import os

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

try:
    import ujson as json
except ImportError:
    import json

import ubinascii

import config

_reader = None
_writer = None
connected = False

_OP_TEXT = 0x1
_OP_CLOSE = 0x8
_OP_PING = 0x9
_OP_PONG = 0xA


def is_connected():
    return connected


async def _send_frame(opcode, payload=b""):
    """Client frames ko MASK karna RFC mein zaroori hai - warna server drop kar dega."""
    global connected

    if _writer is None:
        return False

    length = len(payload)
    header = bytearray()
    header.append(0x80 | opcode)              # FIN + opcode

    if length < 126:
        header.append(0x80 | length)          # mask bit + length
    elif length < 65536:
        header.append(0x80 | 126)
        header.append((length >> 8) & 0xFF)
        header.append(length & 0xFF)
    else:
        header.append(0x80 | 127)
        header.extend(b"\x00" * 4)            # 64-bit length ka upper half
        header.append((length >> 24) & 0xFF)
        header.append((length >> 16) & 0xFF)
        header.append((length >> 8) & 0xFF)
        header.append(length & 0xFF)

    mask = os.urandom(4)
    header.extend(mask)

    masked = bytearray(length)
    for i in range(length):
        masked[i] = payload[i] ^ mask[i % 4]

    try:
        _writer.write(bytes(header) + bytes(masked))
        await _writer.drain()
        return True
    except Exception as exc:
        print("[WS] Send failed:", exc)
        connected = False
        return False


async def _read_exactly(count):
    """Poore `count` bytes padho. None agar socket band ho gaya."""
    chunks = b""
    while len(chunks) < count:
        chunk = await _reader.read(count - len(chunks))
        if not chunk:
            return None
        chunks += chunk
    return chunks


async def _read_frame():
    """(opcode, payload_bytes) ya (None, None) agar socket band."""
    header = await _read_exactly(2)
    if header is None:
        return (None, None)

    opcode = header[0] & 0x0F
    masked = bool(header[1] & 0x80)
    length = header[1] & 0x7F

    if length == 126:
        extended = await _read_exactly(2)
        if extended is None:
            return (None, None)
        length = (extended[0] << 8) | extended[1]
    elif length == 127:
        extended = await _read_exactly(8)
        if extended is None:
            return (None, None)
        length = 0
        for byte in extended:
            length = (length << 8) | byte

    mask_key = None
    if masked:                                  # server normally mask nahi karta
        mask_key = await _read_exactly(4)
        if mask_key is None:
            return (None, None)

    payload = b""
    if length:
        payload = await _read_exactly(length)
        if payload is None:
            return (None, None)
        if mask_key:
            payload = bytes(payload[i] ^ mask_key[i % 4] for i in range(length))

    return (opcode, payload)


async def connect():
    """HTTP upgrade handshake. True agar socket khul gaya."""
    global _reader, _writer, connected

    await disconnect()

    try:
        _reader, _writer = await asyncio.open_connection(
            config.BACKEND_HOST, config.BACKEND_PORT
        )
    except Exception as exc:
        print("[WS] Connect failed:", exc)
        return False

    key = ubinascii.b2a_base64(os.urandom(16)).decode().strip()
    request = (
        "GET %s HTTP/1.1\r\n"
        "Host: %s:%d\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        "Sec-WebSocket-Key: %s\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "\r\n"
    ) % (config.WS_PATH, config.BACKEND_HOST, config.BACKEND_PORT, key)

    try:
        _writer.write(request.encode())
        await _writer.drain()

        status_line = await _reader.readline()
        if b"101" not in status_line:
            # 403 aam baat hai: galat device_key, ya URL ka device id match nahi
            print("[WS] Handshake reject:", status_line)
            await disconnect()
            return False

        # Baaki headers skip karo
        while True:
            line = await _reader.readline()
            if not line or line == b"\r\n":
                break

        connected = True
        print("[WS] Command channel connected")
        return True

    except Exception as exc:
        print("[WS] Handshake failed:", exc)
        await disconnect()
        return False


async def disconnect():
    global _reader, _writer, connected
    connected = False
    if _writer is not None:
        try:
            await _send_frame(_OP_CLOSE)
        except Exception:
            pass
        try:
            _writer.close()
            await _writer.wait_closed()
        except Exception:
            pass
    _reader = None
    _writer = None


async def send_ack(command_id):
    if not connected or not command_id:
        return
    payload = json.dumps({"type": "ack", "command_id": command_id})
    await _send_frame(_OP_TEXT, payload.encode())


async def send_ping():
    if connected:
        await _send_frame(_OP_TEXT, b'{"type":"ping"}')


async def listen(on_command):
    """
    Frames padhte raho jab tak socket zinda hai.

    on_command(command_type, command_id, payload_dict) - har command par call.
    Socket band hone par return - caller reconnect karega.
    """
    global connected

    while connected:
        try:
            opcode, payload = await _read_frame()
        except Exception as exc:
            print("[WS] Read error:", exc)
            break

        if opcode is None or opcode == _OP_CLOSE:
            print("[WS] Server ne socket band kar diya")
            break

        if opcode == _OP_PING:
            await _send_frame(_OP_PONG, payload or b"")
            continue

        if opcode == _OP_PONG:
            continue

        if opcode != _OP_TEXT:
            continue

        try:
            message = json.loads(payload.decode())
        except Exception as exc:
            print("[WS] Bad JSON:", exc)
            continue

        message_type = message.get("type")

        if message_type == "command":
            command_type = message.get("command_type", "")
            command_id = message.get("command_id", "")
            print("[WS] Command:", command_type)
            try:
                await on_command(command_type, command_id, message.get("payload") or {})
            except Exception as exc:
                print("[WS] Command handler error:", exc)
            await send_ack(command_id)

        elif message_type == "pong":
            pass

    connected = False
    await disconnect()
