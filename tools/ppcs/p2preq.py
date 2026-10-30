"""Step 2: MSG_P2P_REQ for the dashcam DID, log everything, answer punches, close politely."""
import json, socket, struct, sys, time
sys.path.insert(0, ".")
from initstring import decode
import cs2crypt

NAMES = {0x01: "HELLO_ACK", 0x21: "P2P_REQ_ACK", 0x40: "PUNCH_TO", 0x41: "PUNCH_PKT", 0x42: "P2P_RDY",
         0x43: "P2P_RDY_ACK", 0xE0: "ALIVE", 0xE1: "ALIVE_ACK", 0xF0: "CLOSE", 0xD0: "DRW", 0xD1: "DRW_ACK",
         0x70: "RLY_HELLO", 0x71: "RLY_HELLO_ACK", 0x72: "RLY_PORT", 0x73: "RLY_PORT_ACK", 0x80: "RLY_REQ",
         0x81: "RLY_REQ_ACK", 0x82: "RLY_TO", 0x83: "RLY_PKT", 0x84: "RLY_RDY", 0x85: "RLY_TO_ACK", 0x26: "P2P_REQ_DSK"}

d = json.load(open("../junan_p2pinfo.json"))
enc, KEY = d["initStringApp"].split(":")
servers = [s for s in decode(enc).decode().split(",") if s]
prefix, serial, check = d["p2pId"].split("-")
DID = prefix.encode().ljust(8, b"\0") + struct.pack(">I", int(serial)) + check.encode().ljust(8, b"\0")

def msg(t, payload=b""):
    return cs2crypt.encrypt(KEY, bytes([0xF1, t]) + struct.pack(">H", len(payload)) + payload)

def sockaddr(ip, port):  # family BE, port LE, ip reversed (as seen in HELLO_ACK)
    return b"\x00\x02" + struct.pack("<H", port) + bytes(reversed(socket.inet_aton(ip))) + b"\0" * 8

def parse_sockaddr(b):
    return socket.inet_ntoa(bytes(reversed(b[4:8]))), struct.unpack("<H", b[2:4])[0]

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(("0.0.0.0", 0)); s.settimeout(0.5)
local_port = s.getsockname()[1]
probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); probe.connect((servers[0], 32100)); local_ip = probe.getsockname()[0]; probe.close()
print("local", local_ip, local_port, "DID len", len(DID))

req = DID + sockaddr(local_ip, local_port)
for srv in servers:
    s.sendto(msg(0x20, req), (srv, 32100))

peers, t0, ready = set(), time.time(), False
duration = float(sys.argv[1]) if len(sys.argv) > 1 else 20
while time.time() - t0 < duration:
    try:
        raw, addr = s.recvfrom(4096)
    except socket.timeout:
        for p in list(peers):
            if not ready:
                s.sendto(msg(0x41, DID), p)
        continue
    m = cs2crypt.decrypt(KEY, raw)
    if m[0] != 0xF1:
        print(f"{time.time()-t0:5.1f}s {addr} undecodable {raw[:16].hex()}"); continue
    t = m[1]; ln = struct.unpack(">H", m[2:4])[0]; pl = m[4:4 + ln]
    src = "server" if addr[0] in servers else "peer"
    extra = ""
    if t == 0x40 and len(pl) >= 16:
        ip, port = parse_sockaddr(pl[:16]); extra = f" -> {ip}:{port}"
        peers.add((ip, port)); s.sendto(msg(0x41, DID), (ip, port))
    elif t == 0x41:
        peers.add(addr); s.sendto(msg(0x42, DID), addr)
    elif t == 0x42:
        ready = True; peers.add(addr); s.sendto(msg(0x42, DID), addr); extra = "  *** P2P READY ***"
    elif t == 0xE0:
        s.sendto(msg(0xE1), addr)
    print(f"{time.time()-t0:5.1f}s {src:6} {addr[0]}:{addr[1]} {NAMES.get(t, hex(t))} len={ln} {pl[:48].hex()}{extra}")
for p in peers:
    s.sendto(msg(0xF0), p)
print("peers:", peers, "ready:", ready)
