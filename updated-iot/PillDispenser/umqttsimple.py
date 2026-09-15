# MicroPython umqtt.simple client (Standard implementation with IPv4 auto-resolution)
import usocket as socket
import ustruct as struct
from ubinascii import hexlify


class MQTTException(Exception):
    pass


def _encode_len(pkt, sz):
    i = 1
    while sz > 0x7F:
        pkt[i] = (sz & 0x7F) | 0x80
        sz >>= 7
        i += 1
    pkt[i] = sz
    return i


class MQTTClient:

    def __init__(
        self,
        client_id,
        server,
        port=0,
        user=None,
        password=None,
        keepalive=0,
        ssl=False,
        ssl_params={},
        socket_timeout=10,
    ):
        if port == 0:
            port = 8883 if ssl else 1883
        self.client_id = client_id
        self.sock = None
        self.server = server
        self.port = port
        self.ssl = ssl
        self.ssl_params = ssl_params
        self.pid = 0
        self.cb = None
        self.user = user
        self.pswd = password
        self.keepalive = keepalive
        self.socket_timeout = socket_timeout
        self.lw_topic = None
        self.lw_msg = None
        self.lw_qos = 0
        self.lw_retain = False

    def _send_str(self, s):
        if isinstance(s, str):
            s = s.encode("utf-8")
        self.sock.write(struct.pack("!H", len(s)))
        self.sock.write(s)

    def _recv_len(self):
        n = 0
        sh = 0
        while 1:
            res = self.sock.read(1)
            b = res[0]
            n |= (b & 0x7F) << sh
            if not b & 0x80:
                return n
            sh += 7

    def set_callback(self, f):
        self.cb = f

    def set_last_will(self, topic, msg, retain=False, qos=0):
        assert 0 <= qos <= 2
        assert topic
        self.lw_topic = topic
        self.lw_msg = msg
        self.lw_qos = qos
        self.lw_retain = retain

    def connect(self, clean_session=True):
        self.sock = socket.socket()
        # Bound the connect + CONNACK handshake so a stalled/unreachable
        # broker can't hang the whole device forever; later reads use
        # setblocking() explicitly and are unaffected by this timeout.
        self.sock.settimeout(self.socket_timeout)
        addr = None
        for res in socket.getaddrinfo(self.server, self.port):
            if len(res[-1]) == 2:  # IPv4
                addr = res[-1]
                break
        if addr is None:
            addr = socket.getaddrinfo(self.server, self.port)[0][-1]
        self.sock.connect(addr)

        if self.ssl:
            import ussl
            self.sock = ussl.wrap_socket(self.sock, **self.ssl_params)

        # NOTE: premsg is intentionally 6 bytes (not 5). The extra
        # trailing zero byte is written out as part of the fixed
        # header (see `i + 2` below) and supplies the high byte of
        # MQTT's 2-byte protocol-name length field. Without it the
        # CONNECT packet is 1 byte short of its declared remaining
        # length, so the broker waits for a byte that never arrives
        # and silently closes the connection instead of replying
        # with a CONNACK.
        premsg = bytearray(b"\x10\0\0\0\0\0")
        msg = bytearray(b"\x04MQTT\x04\x02\0\0")

        cid = self.client_id
        if isinstance(cid, str):
            cid = cid.encode("utf-8")

        sz = 10 + 2 + len(cid)
        msg[6] = clean_session << 1
        if self.user is not None:
            sz += 2 + len(self.user) + 2 + len(self.pswd)
            msg[6] |= 0xC0
        if self.keepalive:
            assert self.keepalive < 65536
            msg[7] |= self.keepalive >> 8
            msg[8] |= self.keepalive & 0x00FF
        if self.lw_topic:
            sz += 2 + len(self.lw_topic) + 2 + len(self.lw_msg)
            msg[6] |= 0x4 | (self.lw_qos << 3) | (self.lw_retain << 5)

        i = _encode_len(premsg, sz)
        self.sock.write(premsg, i + 2)
        self.sock.write(msg)
        self._send_str(cid)
        if self.lw_topic:
            self._send_str(self.lw_topic)
            self._send_str(self.lw_msg)
        if self.user is not None:
            self._send_str(self.user)
            self._send_str(self.pswd)
        resp = self.sock.read(4)
        if not resp or len(resp) < 4:
            raise MQTTException(
                "No CONNACK received from broker (connection closed during handshake)"
            )
        if resp[0] != 0x20 or resp[1] != 0x02:
            raise MQTTException("Malformed CONNACK from broker: %r" % resp)
        if resp[3] != 0:
            raise MQTTException(resp[3])
        return resp[2] & 1

    def disconnect(self):
        try:
            self.sock.write(b"\xe0\0")
            self.sock.close()
        except Exception:
            pass

    def ping(self):
        self.sock.write(b"\xc0\0")

    def publish(self, topic, msg, retain=False, qos=0):
        if isinstance(topic, str):
            topic = topic.encode("utf-8")
        if isinstance(msg, str):
            msg = msg.encode("utf-8")

        pkt = bytearray(b"\x30\0\0\0")
        pkt[0] |= qos << 1 | retain
        sz = 2 + len(topic) + len(msg)
        if qos > 0:
            sz += 2
        assert sz < 2097152

        i = _encode_len(pkt, sz)
        self.sock.write(pkt, i + 1)
        self._send_str(topic)
        if qos > 0:
            self.pid += 1
            struct.pack_into("!H", pkt, 0, self.pid)
            self.sock.write(pkt, 2)
        self.sock.write(msg)
        if qos == 1:
            while 1:
                op = self.wait_msg()
                if op == 0x40:
                    sz = self.sock.read(1)
                    assert sz == b"\x02"
                    rcv_pid = self.sock.read(2)
                    rcv_pid = rcv_pid[0] << 8 | rcv_pid[1]
                    if self.pid == rcv_pid:
                        return
        elif qos == 2:
            assert 0

    def _send_subunsub(self, topic, typ, ack_op, ack_n, qos=0):
        if isinstance(topic, str):
            topic = topic.encode("utf-8")
        pkt = bytearray(4)
        pkt[0] = typ
        self.pid += 1
        pid = self.pid
        i = _encode_len(pkt, 4 + len(topic) + (ack_n > 3))
        self.sock.write(pkt, i + 1)
        struct.pack_into("!H", pkt, 0, pid)
        self.sock.write(pkt, 2)
        self._send_str(topic)
        if ack_n > 3:
            self.sock.write(bytes((qos,)))
        while 1:
            op = self.wait_msg()
            if op == ack_op:
                resp = self.sock.read(ack_n)
                assert resp[1] == (pid >> 8) and resp[2] == (pid & 0xFF)
                if resp[3] == 0x80:
                    raise MQTTException(resp[3])
                return

    def subscribe(self, topic, qos=0):
        assert self.cb is not None, "Subscribe callback is not set"
        self._send_subunsub(topic, 0x82, 0x90, 4, qos)

    def wait_msg(self):
        res = self.sock.read(1)
        self.sock.setblocking(True)
        if res is None:
            return None
        if res == b"":
            raise OSError(-1)
        if res == b"\xd0":  # PINGRESP
            sz = self.sock.read(1)[0]
            assert sz == 0
            return None
        op = res[0]
        if op & 0xF0 != 0x30:
            return op
        sz = self._recv_len()
        topic_len = self.sock.read(2)
        topic_len = (topic_len[0] << 8) | topic_len[1]
        topic = self.sock.read(topic_len)
        sz -= topic_len + 2
        if op & 6:
            pid = self.sock.read(2)
            pid = pid[0] << 8 | pid[1]
            sz -= 2
        msg = self.sock.read(sz)
        self.cb(topic, msg)
        if op & 6 == 2:
            pkt = bytearray(b"\x40\x02\0\0")
            struct.pack_into("!H", pkt, 2, pid)
            self.sock.write(pkt)
        elif op & 6 == 4:
            assert 0
        return op

    def check_msg(self):
        self.sock.setblocking(False)
        return self.wait_msg()
