"""Minimal CS2 PPCS client (relay mode) and the iBOX live-stream protocol on top of it.

Reverse-engineered from libPPCS_API.so and the syncdrive SDK; see PROJECT_STATUS.md.
Blocking sockets, meant to run in its own thread.
"""
from __future__ import annotations

import json
import logging
import queue
import socket
import struct
import threading
import time
from collections.abc import Callable

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

_LOGGER = logging.getLogger(__name__)

# PPPP_DecodeString lookup table (bettse/pppp_decodestring)
_INIT_TABLE = bytes.fromhex(
    "4959433db5bf6da347534f6165e371e9677f02030badb3892b2f35c16b8b959711e5a70deff1050783fb9d3bc5c713171d1f2529d3df"
)
# P2P_Proprietary_Encrypt shuffle table (magicus/pppp-dissector)
_XOR_TABLE = bytes.fromhex(
    "7c9ce84a13dedcb22f2123e4307b3d8cbc0b270c3cf79ae7087196009785efc1"
    "1fc4dba1c2ebd901faba3b05b81587832872d18b5ad6da9358feaacc6e1bf0a3"
    "88ab43c00db545384f502266207f075b14981d9ba72ab9a8cbf1fc4947063eb1"
    "0e043a945eee541134dd4df9ecc7c9e3781a6f706ba4bda95dd5f8e5bb26af42"
    "37d8e1020aae5f1cc573094e6924906d12b319ad748a2940f52dbea559e0f479"
    "d24bce8982488425c6912ba2fb8fe9a6b09e3f65f603312eac0f952c5ced39b7"
    "336c567eb4a0fd7a815351868d9f77ff6a80dfe2bf10d775645776f355cdd0c8"
    "18e6364162cf99f2324c67606192cad3ea637d16b68ed46835c3529d46441e17"
)

MSG_LIST_REQ1, MSG_LIST_REQ_ACK = 0x67, 0x69
MSG_RLY_HELLO, MSG_RLY_HELLO_ACK, MSG_RLY_PORT, MSG_RLY_PORT_ACK = 0x70, 0x71, 0x72, 0x73
MSG_RLY_REQ, MSG_RLY_TO, MSG_RLY_PKT, MSG_RLY_RDY = 0x80, 0x82, 0x83, 0x84
MSG_DRW, MSG_DRW_ACK, MSG_ALIVE, MSG_ALIVE_ACK, MSG_CLOSE = 0xD0, 0xD1, 0xE0, 0xE1, 0xF0

# iBOX commands (PpcsIotType)
IOT_AUTH, IOT_STREAM_START, IOT_STREAM_STOP = 4096, 4098, 4100
IOT_SET_STREAM_INFO, IOT_GET_FRAME = 4110, 4120
IOT_PLAYBACK_START, IOT_SET_VIDEOSPEED, IOT_SET_PLAYBACK_CH = 4112, 4118, 4130

CODEC_H264, CODEC_H265, CODEC_AAC = 78, 80, 136

QUALITY_720P, QUALITY_360P = 1, 2  # channel 0 ("FullHD" in the SDK) answers "bad param"
CAMERA_FRONT, CAMERA_REAR = 1, 2


class PpcsError(Exception):
    """Connection or protocol failure."""


def decode_init_string(encoded: str) -> list[str]:
    out = bytearray(len(encoded) // 2)
    for i in range(len(out)):
        b = 57
        for prev in out[:i]:
            b ^= prev
        val = 16 * (ord(encoded[2 * i]) - 65) + (ord(encoded[2 * i + 1]) - 65)
        out[i] = (b ^ _INIT_TABLE[i % len(_INIT_TABLE)] ^ val) & 0xFF
    return [s for s in out.decode(errors="ignore").split(",") if s]


class _Crypt:
    def __init__(self, key: str) -> None:
        h = [0, 0, 0, 0]
        for b in key.encode():
            h[0] = (h[0] + b) & 255
            h[1] = (h[1] - b) & 255
            h[2] = (h[2] + b // 3) & 255
            h[3] = h[3] ^ b
        # keystream byte depends only on the previous ciphertext byte
        self._ks = bytes(_XOR_TABLE[(h[p & 3] + p) & 255] for p in range(256))

    def encrypt(self, data: bytes) -> bytes:
        out, prev, ks = bytearray(len(data)), 0, self._ks
        for i, b in enumerate(data):
            prev = b ^ ks[prev]
            out[i] = prev
        return bytes(out)

    def decrypt(self, data: bytes) -> bytes:
        out, prev, ks = bytearray(len(data)), 0, self._ks
        for i, b in enumerate(data):
            out[i] = b ^ ks[prev]
            prev = b
        return bytes(out)


def _sockaddr(ip: str, port: int) -> bytes:
    return b"\x00\x02" + struct.pack("<H", port) + bytes(reversed(socket.inet_aton(ip))) + bytes(8)


def _parse_sockaddr(b: bytes) -> tuple[str, int]:
    return socket.inet_ntoa(bytes(reversed(b[4:8]))), struct.unpack("<H", b[2:4])[0]


def _did_bytes(p2p_id: str) -> bytes:
    prefix, serial, check = p2p_id.split("-")
    return prefix.encode().ljust(8, b"\0") + struct.pack(">I", int(serial)) + check.encode().ljust(8, b"\0")


def decrypt_video(buf: bytearray, share_key: bytes) -> bytes:
    """AVDecryptUtil.decryptVideo: returns the clear Annex-B payload."""
    nonce = bytes(buf[:8])
    n = buf[8]
    base = 9 + 8 * n
    # every block is XORed with the first 16 keystream bytes (fixed nonce, counter 0)
    ks = Cipher(algorithms.ChaCha20(share_key, bytes(8) + nonce), mode=None).encryptor().update(bytes(16))
    for i in range(n):
        off, ln = struct.unpack_from("<II", buf, 9 + 8 * i)
        p = 32
        while p + 16 < ln:
            a = base + off + p
            buf[a:a + 16] = bytes(x ^ y for x, y in zip(buf[a:a + 16], ks))
            p += 0xA0
    return bytes(buf[base:])


def decrypt_audio(data: bytes, share_key: bytes) -> bytes:
    """AVDecryptUtil.decryptAudio: 8-byte nonce, then the whole ADTS frame is chacha20-encrypted."""
    return Cipher(algorithms.ChaCha20(share_key, bytes(8) + data[:8]), mode=None).encryptor().update(data[8:])


class RelaySession:
    """CS2 session through a relay server, with a reliable ordered byte stream per DRW channel."""

    def __init__(self, p2p_id: str, init_string: str) -> None:
        encoded, _, key = init_string.partition(":")
        self._servers = decode_init_string(encoded)
        self._crypt = _Crypt(key)
        self._did = _did_bytes(p2p_id)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind(("0.0.0.0", 0))
        self._sock.settimeout(0.2)
        self._peer: tuple[str, int] | None = None
        self._tx_idx = [0] * 8
        self._unacked: dict[tuple[int, int], list] = {}
        self._rx_next = [0] * 8
        self._rx_pending: list[dict[int, bytes]] = [{} for _ in range(8)]
        self._rx = [bytearray() for _ in range(8)]
        self._cv = threading.Condition()
        self.alive = False

    def _msg(self, t: int, payload: bytes = b"") -> bytes:
        return self._crypt.encrypt(bytes([0xF1, t]) + struct.pack(">H", len(payload)) + payload)

    def _send(self, data: bytes, addr) -> None:
        try:
            self._sock.sendto(data, addr)
        except OSError as err:
            _LOGGER.debug("send to %s failed: %s", addr, err)

    def _recv(self) -> tuple[int, bytes, tuple[str, int]] | None:
        try:
            raw, addr = self._sock.recvfrom(4096)
        except (socket.timeout, OSError):
            return None
        m = self._crypt.decrypt(raw)
        if len(m) < 4 or m[0] != 0xF1:
            return None
        ln = struct.unpack(">H", m[2:4])[0]
        return m[1], m[4:4 + ln], addr

    def connect(self, timeout: float = 12) -> None:
        for srv in self._servers:
            self._send(self._msg(MSG_LIST_REQ1, self._did), (srv, 32100))
        relay = mark = None
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and not self._peer:
            got = self._recv()
            if not got:
                continue
            t, pl, addr = got
            if t == MSG_LIST_REQ_ACK and pl:
                for i in range(pl[0]):
                    self._send(self._msg(MSG_RLY_HELLO), _parse_sockaddr(pl[4 + 16 * i:20 + 16 * i]))
            elif t == MSG_RLY_TO and len(pl) >= 20:
                target = _parse_sockaddr(pl[:16])
                ticket = struct.unpack(">I", pl[16:20])[0]
                pkt = self._msg(MSG_RLY_PKT, struct.pack(">I", ticket) + self._did + bytes(4))
                for _ in range(4):
                    self._send(pkt, target)
            elif t == MSG_RLY_HELLO_ACK and relay is None:
                relay = addr
                self._send(self._msg(MSG_RLY_PORT), addr)
            elif t == MSG_RLY_PORT_ACK and mark is None and relay and len(pl) >= 6:
                mark, port = struct.unpack(">IH", pl[:6])
                relay = (relay[0], port)
                req = self._did + _sockaddr(*relay) + struct.pack(">I", mark)
                for srv in self._servers:
                    self._send(self._msg(MSG_RLY_REQ, req), (srv, 32100))
            elif t == MSG_RLY_RDY:
                self._peer = addr
        if not self._peer:
            self._sock.close()
            raise PpcsError("dashcam did not come to the relay (offline?)")
        self.alive = True
        threading.Thread(target=self._rx_loop, name="ibox-ppcs-rx", daemon=True).start()
        threading.Thread(target=self._tx_loop, name="ibox-ppcs-tx", daemon=True).start()

    def write(self, ch: int, data: bytes) -> None:
        for off in range(0, len(data), 1024):
            idx = self._tx_idx[ch]
            self._tx_idx[ch] = (idx + 1) & 0xFFFF
            pkt = self._msg(MSG_DRW, bytes([0xD1, ch]) + struct.pack(">H", idx) + data[off:off + 1024])
            with self._cv:
                self._unacked[(ch, idx)] = [pkt, time.monotonic()]
            self._send(pkt, self._peer)

    def read(self, ch: int, n: int, timeout: float = 10) -> bytes:
        deadline = time.monotonic() + timeout
        with self._cv:
            while len(self._rx[ch]) < n:
                left = deadline - time.monotonic()
                if not self.alive:
                    raise PpcsError("session closed")
                if left <= 0:
                    raise TimeoutError(f"channel {ch} read timeout")
                self._cv.wait(left)
            out = bytes(self._rx[ch][:n])
            del self._rx[ch][:n]
            return out

    def _tx_loop(self) -> None:
        last_alive = 0.0
        while self.alive:
            now = time.monotonic()
            with self._cv:
                pending = [v for v in self._unacked.values() if now - v[1] > 0.4]
                for v in pending:
                    v[1] = now
            for v in pending:
                self._send(v[0], self._peer)
            if now - last_alive > 1:
                self._send(self._msg(MSG_ALIVE), self._peer)
                last_alive = now
            time.sleep(0.05)

    def _rx_loop(self) -> None:
        last_seen = time.monotonic()
        while self.alive:
            got = self._recv()
            if not got:
                if time.monotonic() - last_seen > 15:
                    _LOGGER.debug("iBOX P2P: peer silent, closing")
                    self._mark_dead()
                continue
            t, pl, addr = got
            last_seen = time.monotonic()
            if t == MSG_DRW and len(pl) >= 4:
                ch, idx = pl[1], struct.unpack(">H", pl[2:4])[0]
                self._send(self._msg(MSG_DRW_ACK, bytes([0xD1, ch]) + struct.pack(">HH", 1, idx)), addr)
                with self._cv:
                    if ((idx - self._rx_next[ch]) & 0xFFFF) < 0x8000:
                        self._rx_pending[ch][idx] = pl[4:]
                    while self._rx_next[ch] in self._rx_pending[ch]:
                        self._rx[ch] += self._rx_pending[ch].pop(self._rx_next[ch])
                        self._rx_next[ch] = (self._rx_next[ch] + 1) & 0xFFFF
                    self._cv.notify_all()
            elif t == MSG_DRW_ACK and len(pl) >= 4:
                ch, cnt = pl[1], struct.unpack(">H", pl[2:4])[0]
                with self._cv:
                    for i in range(cnt):
                        self._unacked.pop((ch, struct.unpack_from(">H", pl, 4 + 2 * i)[0]), None)
            elif t == MSG_ALIVE:
                self._send(self._msg(MSG_ALIVE_ACK), addr)
            elif t == MSG_CLOSE:
                self._mark_dead()

    def _mark_dead(self) -> None:
        self.alive = False
        with self._cv:
            self._cv.notify_all()

    def close(self) -> None:
        if self._peer:
            for _ in range(3):
                self._send(self._msg(MSG_CLOSE), self._peer)
        self._mark_dead()
        self._sock.close()


class IboxLiveClient:
    """iBOX command layer: auth, stream start/stop and frame reading."""

    def __init__(self, session: RelaySession, share_key: bytes) -> None:
        self._s = session
        self._key = share_key
        self._cmd_id = 1

    def command(self, typ: int, body: dict | None = None, timeout: float = 10) -> bytes:
        data = json.dumps(body, separators=(",", ":")).encode() if body is not None else b""
        cid = self._cmd_id
        self._cmd_id += 1
        self._s.write(0, b"PPPP" + struct.pack("<III", typ, cid, len(data)) + data)
        while True:
            hdr = self._s.read(0, 16, timeout)
            _rtyp, rid, rlen = struct.unpack("<III", hdr[4:16])
            rbody = self._s.read(0, rlen, timeout) if rlen else b""
            if rid == cid:
                return rbody

    def authenticate(self, auth: dict) -> None:
        reply = self.command(IOT_AUTH, auth)
        if b'"code":0' not in reply.replace(b" ", b""):
            raise PpcsError(f"auth rejected: {reply[:100]!r}")

    def start_live(self, quality: int | None, camera: int) -> None:
        self.command(IOT_STREAM_START, {"camera": camera})
        # switching quality before the stream starts leaves the dashcam sending audio only
        if quality is not None:
            self.command(IOT_SET_STREAM_INFO, {"channel": quality})
        # without an explicit frame request no video arrives
        self.command(IOT_GET_FRAME)

    def start_playback(self, path_name: str, file_name: str) -> None:
        # start_time is not a seek position: anything but 0 plays only the file's last GOP
        reply = self.command(IOT_PLAYBACK_START, {"start_time": 0, "pathName": path_name, "fileName": file_name})
        if b'"code":0' not in reply.replace(b" ", b""):
            raise PpcsError(f"playback rejected: {reply[:100]!r}")

    def stop_live(self) -> None:
        try:
            self.command(IOT_STREAM_STOP, timeout=3)
        except (TimeoutError, PpcsError):
            pass

    def read_frame(self, timeout: float = 10) -> tuple[int, bool, int, bytes]:
        """(codec, keyframe, pts in ms, payload) — video is decrypted to Annex-B, audio to ADTS."""
        hdr = self._s.read(1, 32, timeout)
        codec, flags = struct.unpack_from("<HB", hdr)
        ms, sec = struct.unpack_from("<II", hdr, 8)
        ln = struct.unpack_from("<I", hdr, 28)[0]
        body = self._s.read(1, ln)
        if codec in (CODEC_H264, CODEC_H265):
            body = decrypt_video(bytearray(body), self._key)
        elif codec == CODEC_AAC and len(body) >= 24:
            body = decrypt_audio(body, self._key)
        return codec, bool(flags & 1), sec * 1000 + ms, body


def run_session(
    p2p_info: dict,
    auth: dict,
    share_key: bytes,
    request: dict,
    on_frame: Callable[[int, bool, int, bytes], None],
    stop: threading.Event,
    controls: queue.Queue | None = None,
    on_ready: Callable[[], None] | None = None,
) -> None:
    """Blocking: connect, start live or playback, feed frames to `on_frame` until `stop`.

    request: {"mode": "live", "quality", "camera"} or {"mode": "playback", "path", "file"}.
    controls: commands sent while streaming, e.g. {"speed": 2} or {"quality": 1}.
    Ends normally when a recording runs out (no frames for a while).
    """
    session = RelaySession(p2p_info["p2pId"], p2p_info["initStringApp"])
    session.connect()
    client = IboxLiveClient(session, share_key)
    live = request["mode"] == "live"
    try:
        client.authenticate(auth)
        if live:
            client.start_live(request.get("quality"), request.get("camera", CAMERA_FRONT))
        else:
            client.start_playback(request["path"], request["file"])
        if on_ready:
            on_ready()
        silent_since = time.monotonic()
        while not stop.is_set() and session.alive:
            while controls is not None and not controls.empty():
                ctl = controls.get_nowait()
                if "speed" in ctl:
                    client.command(IOT_SET_VIDEOSPEED, {"speed": int(ctl["speed"])})
                if "quality" in ctl:
                    client.command(IOT_SET_STREAM_INFO if live else IOT_SET_PLAYBACK_CH, {"channel": int(ctl["quality"])})
                    client.command(IOT_GET_FRAME)
            try:
                frame = client.read_frame(timeout=1)
            except TimeoutError:
                if time.monotonic() - silent_since > (10 if live else 6):
                    if live:
                        raise
                    break  # end of the recording
                continue
            silent_since = time.monotonic()
            on_frame(*frame)
    finally:
        if session.alive and live:
            client.stop_live()
        session.close()
