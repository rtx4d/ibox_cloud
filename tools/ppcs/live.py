"""Step 4: relay session + DRW + iBOX auth + live stream -> raw H.264/H.265 file.

Usage: live.py <seconds> <out_file> [quality 0=FullHD 1=HD 2=SD]
"""
import json
import os
import socket
import struct
import sys
import threading
import time

import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
from nacl import bindings as nb

sys.path.insert(0, ".")
import cs2crypt
from initstring import decode

SECONDS = float(sys.argv[1]) if len(sys.argv) > 1 else 15
OUT = sys.argv[2] if len(sys.argv) > 2 else "live.bin"
QUALITY = int(sys.argv[3]) if len(sys.argv) > 3 else 2

info = json.load(open("../junan_p2pinfo.json"))
creds = json.load(open("../junan_creds.json", encoding="utf-8"))
DID_STR = os.environ["IBOX_DID"]  # cloud did, e.g. d.ib.0.<serial>
enc, KEY = info["initStringApp"].split(":")
servers = [s for s in decode(enc).decode().split(",") if s]
prefix, serial, check = info["p2pId"].split("-")
DID = prefix.encode().ljust(8, b"\0") + struct.pack(">I", int(serial)) + check.encode().ljust(8, b"\0")


def msg(t, payload=b""):
    return cs2crypt.encrypt(KEY, bytes([0xF1, t]) + struct.pack(">H", len(payload)) + payload)


def sockaddr(ip, port):
    return b"\x00\x02" + struct.pack("<H", port) + bytes(reversed(socket.inet_aton(ip))) + bytes(8)


def parse_sockaddr(b):
    return socket.inet_ntoa(bytes(reversed(b[4:8]))), struct.unpack("<H", b[2:4])[0]


def log(*a):
    print(f"{time.time() - T0:6.2f}s", *a, flush=True)


T0 = time.time()


class Session:
    """CS2 relay session with a reliable, ordered DRW byte stream per channel."""

    def __init__(self):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.s.bind(("0.0.0.0", 0))
        self.s.settimeout(0.2)
        self.peer = None
        self.tx_idx = [0] * 8
        self.unacked = {}  # (ch, idx) -> (packet, last_sent)
        self.rx_next = [0] * 8
        self.rx_pending = [dict() for _ in range(8)]
        self.rx = [bytearray() for _ in range(8)]
        self.cv = threading.Condition()
        self.alive = True
        self.bytes_in = 0

    # --- relay setup -------------------------------------------------------
    def connect(self, timeout=10):
        for srv in servers:
            self.s.sendto(msg(0x67, DID), (srv, 32100))
        relay = mark = None
        t_end = time.time() + timeout
        while time.time() < t_end and not self.peer:
            try:
                raw, addr = self.s.recvfrom(4096)
            except socket.timeout:
                continue
            m = cs2crypt.decrypt(KEY, raw)
            t, ln = m[1], struct.unpack(">H", m[2:4])[0]
            pl = m[4:4 + ln]
            if t == 0x69:
                for i in range(pl[0]):
                    self.s.sendto(msg(0x70), parse_sockaddr(pl[4 + 16 * i:20 + 16 * i]))
            elif t == 0x82:
                rip, rport = parse_sockaddr(pl[:16])
                ticket = struct.unpack(">I", pl[16:20])[0]
                pkt = msg(0x83, struct.pack(">I", ticket) + DID + bytes(4))
                for _ in range(4):
                    self.s.sendto(pkt, (rip, rport))
            elif t == 0x71 and relay is None:
                relay = addr
                self.s.sendto(msg(0x72), addr)
            elif t == 0x73 and mark is None:
                mark, port = struct.unpack(">IH", pl[:6])
                relay = (relay[0], port)
                for srv in servers:
                    self.s.sendto(msg(0x80, DID + sockaddr(*relay) + struct.pack(">I", mark)), (srv, 32100))
            elif t == 0x84:
                self.peer = addr
        if not self.peer:
            raise RuntimeError("relay not ready")
        log("relay ready", self.peer)
        threading.Thread(target=self._rx_loop, daemon=True).start()
        threading.Thread(target=self._tx_loop, daemon=True).start()

    # --- DRW ---------------------------------------------------------------
    def write(self, ch, data):
        for off in range(0, len(data), 1024):
            chunk = data[off:off + 1024]
            idx = self.tx_idx[ch]
            self.tx_idx[ch] = (idx + 1) & 0xFFFF
            pkt = msg(0xD0, bytes([0xD1, ch]) + struct.pack(">H", idx) + chunk)
            with self.cv:
                self.unacked[(ch, idx)] = [pkt, time.time()]
            self.s.sendto(pkt, self.peer)

    def read(self, ch, n, timeout=10):
        t_end = time.time() + timeout
        with self.cv:
            while len(self.rx[ch]) < n:
                left = t_end - time.time()
                if left <= 0 or not self.alive:
                    return None
                self.cv.wait(left)
            out = bytes(self.rx[ch][:n])
            del self.rx[ch][:n]
            return out

    def _tx_loop(self):
        last_alive = 0
        while self.alive:
            now = time.time()
            with self.cv:
                for k, v in self.unacked.items():
                    if now - v[1] > 0.4:
                        self.s.sendto(v[0], self.peer)
                        v[1] = now
            if now - last_alive > 1:
                self.s.sendto(msg(0xE0), self.peer)
                last_alive = now
            time.sleep(0.05)

    def _rx_loop(self):
        while self.alive:
            try:
                raw, addr = self.s.recvfrom(4096)
            except socket.timeout:
                continue
            m = cs2crypt.decrypt(KEY, raw)
            if m[0] != 0xF1:
                continue
            t, ln = m[1], struct.unpack(">H", m[2:4])[0]
            pl = m[4:4 + ln]
            if t == 0xD0:
                ch, idx = pl[1], struct.unpack(">H", pl[2:4])[0]
                self.s.sendto(msg(0xD1, bytes([0xD1, ch]) + struct.pack(">HH", 1, idx)), addr)
                self.bytes_in += len(pl) - 4
                with self.cv:
                    if ((idx - self.rx_next[ch]) & 0xFFFF) < 0x8000:
                        self.rx_pending[ch][idx] = pl[4:]
                    while self.rx_next[ch] in self.rx_pending[ch]:
                        self.rx[ch] += self.rx_pending[ch].pop(self.rx_next[ch])
                        self.rx_next[ch] = (self.rx_next[ch] + 1) & 0xFFFF
                    self.cv.notify_all()
            elif t == 0xD1:
                ch, cnt = pl[1], struct.unpack(">H", pl[2:4])[0]
                with self.cv:
                    for i in range(cnt):
                        self.unacked.pop((ch, struct.unpack(">H", pl[4 + 2 * i:6 + 2 * i])[0]), None)
            elif t == 0xE0:
                self.s.sendto(msg(0xE1), addr)
            elif t == 0xF0:
                log("peer closed")
                self.alive = False
                with self.cv:
                    self.cv.notify_all()

    def close(self):
        if self.peer:
            for _ in range(3):
                self.s.sendto(msg(0xF0), self.peer)
        self.alive = False


# --- iBOX command layer ("PPPP" + type + id + len, little-endian) ------------
CMD_ID = [1]


def command(sess, typ, body=None, timeout=10):
    data = (body or "").encode()
    cid = CMD_ID[0]
    CMD_ID[0] += 1
    sess.write(0, b"PPPP" + struct.pack("<III", typ, cid, len(data)) + data)
    while True:
        hdr = sess.read(0, 16, timeout)
        if hdr is None:
            raise TimeoutError(f"no reply to {typ}")
        rtyp, rid, rlen = struct.unpack("<III", hdr[4:16])
        rbody = sess.read(0, rlen, timeout) if rlen else b""
        log(f"cmd reply type={rtyp} id={rid} body={rbody[:300]!r}")
        if rid == cid:
            return rtyp, rbody


def chacha_xor(key, nonce8, data):
    c = Cipher(algorithms.ChaCha20(key, bytes(8) + nonce8), mode=None).encryptor()
    return c.update(data)


def decrypt_video(buf: bytearray, key: bytes) -> bytes:
    """AVDecryptUtil.decryptVideo: 8-byte nonce, N (offset,len) pairs, 16-byte blocks every 0x80 from +32."""
    nonce = bytes(buf[:8])
    n = buf[8]
    table = buf[9:9 + 8 * n]
    base = 9 + 8 * n
    for i in range(n):
        off, ln = struct.unpack("<II", table[8 * i:8 * i + 8])
        p = 32
        while p + 16 < ln:
            a = base + off + p
            buf[a:a + 16] = chacha_xor(key, nonce, bytes(buf[a:a + 16]))
            p += 0xA0
    return bytes(buf[base:])


def main():
    # 1) server-side signature of our ephemeral key
    app_pk, app_sk = nb.crypto_box_keypair()
    h = {"userId": creds["junan_id"], "token": creds["token"], "lang": "en"}
    r = requests.post("https://app.iot.yigtech.com/v1.0/iot/p2p/sign", headers=h, timeout=30,
                      json={"did": DID_STR, "devPwd": "", "p2pAppPublicKey": app_pk.hex()}).json()
    sign = r.get("result") or {}
    log("sign:", r.get("code"), r.get("message"), sorted(sign))
    share = nb.crypto_box_beforenm(bytes.fromhex(sign["p2pDevPublicKey"]), app_sk)

    sess = Session()
    sess.connect()
    try:
        auth = json.dumps({"app_public_key": app_pk.hex(), "timestamp": str(sign["time"]), "app_sign": sign["sign"]},
                          separators=(",", ":"))
        command(sess, 4096, auth)
        if QUALITY >= 0:
            command(sess, 4110, json.dumps({"channel": QUALITY}))
        command(sess, 4098, json.dumps({"camera": 1}))
        command(sess, 4120, None)
        out = open(OUT, "wb")
        frames = codecs = 0
        seen = {}
        t_end = time.time() + SECONDS
        while time.time() < t_end:
            hdr = sess.read(1, 32, 10)
            if hdr is None:
                log("no frame header")
                break
            codec, flags = struct.unpack("<HB", hdr[:3])
            ln = struct.unpack("<I", hdr[28:32])[0]
            w, hgt = struct.unpack("<II", hdr[16:24])
            body = sess.read(1, ln, 10)
            if body is None:
                break
            seen[codec] = seen.get(codec, 0) + 1
            if seen[codec] <= 2:
                log(f"hdr codec={codec} {hdr.hex()} len={ln} per-ch-bytes={[len(b) for b in sess.rx]} next={sess.rx_next}")
            if codec in (78, 80):
                out.write(decrypt_video(bytearray(body), share))
                frames += 1
                if frames == 1:
                    log(f"first video frame codec={codec} {w}x{hgt} flags={flags} len={ln}")
        out.close()
        log(f"video frames={frames} codecs={seen} bytes_in={sess.bytes_in}")
        try:
            command(sess, 4100, None, timeout=3)
        except TimeoutError:
            pass
    finally:
        sess.close()


main()
