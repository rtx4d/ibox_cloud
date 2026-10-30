"""Step 3: CS2 relay. LIST_REQ1 -> LIST_REQ_ACK(relays) -> RLY_HELLO -> RLY_PORT -> RLY_PORT_ACK
-> RLY_REQ to P2P servers -> wait RLY_RDY from relay. Logs everything, closes politely."""
import json, socket, struct, sys, time
sys.path.insert(0, ".")
from initstring import decode
import cs2crypt

NAMES = {0x01: "HELLO_ACK", 0x21: "P2P_REQ_ACK", 0x40: "PUNCH_TO", 0x41: "PUNCH_PKT", 0x42: "P2P_RDY",
         0x69: "LIST_REQ_ACK", 0x71: "RLY_HELLO_ACK", 0x73: "RLY_PORT_ACK", 0x81: "RLY_REQ_ACK",
         0x82: "RLY_TO", 0x83: "RLY_PKT", 0x84: "RLY_RDY", 0xE0: "ALIVE", 0xE1: "ALIVE_ACK",
         0xF0: "CLOSE", 0xD0: "DRW", 0xD1: "DRW_ACK"}
d = json.load(open("../junan_p2pinfo.json"))
enc, KEY = d["initStringApp"].split(":")
servers = [s for s in decode(enc).decode().split(",") if s]
prefix, serial, check = d["p2pId"].split("-")
DID = prefix.encode().ljust(8, b"\0") + struct.pack(">I", int(serial)) + check.encode().ljust(8, b"\0")

def msg(t, payload=b""):
    return cs2crypt.encrypt(KEY, bytes([0xF1, t]) + struct.pack(">H", len(payload)) + payload)
def sockaddr(ip, port):
    return b"\x00\x02" + struct.pack("<H", port) + bytes(reversed(socket.inet_aton(ip))) + b"\0" * 8
def parse_sockaddr(b):
    return socket.inet_ntoa(bytes(reversed(b[4:8]))), struct.unpack("<H", b[2:4])[0]

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(("0.0.0.0", 0)); s.settimeout(0.3)
for srv in servers:
    s.sendto(msg(0x67, DID), (srv, 32100))

tickets = []; relay = None; mark = None; rdy = None; t0 = time.time(); last_req = 0
duration = float(sys.argv[1]) if len(sys.argv) > 1 else 25
while time.time() - t0 < duration:
    try:
        raw, addr = s.recvfrom(4096)
    except socket.timeout:
        if relay and mark is not None and not rdy and time.time() - last_req > 2:
            for srv in servers:
                s.sendto(msg(0x80, DID + sockaddr(*relay) + struct.pack(">I", mark)), (srv, 32100))
            last_req = time.time()
        if rdy:
            s.sendto(msg(0xE0), rdy)
        continue
    m = cs2crypt.decrypt(KEY, raw)
    if m[0] != 0xF1:
        print("undecodable", addr, raw[:16].hex()); continue
    t, ln = m[1], struct.unpack(">H", m[2:4])[0]; pl = m[4:4 + ln]
    info = ""
    if t == 0x69:
        n = pl[0]; addrs = [parse_sockaddr(pl[4 + 16 * i: 20 + 16 * i]) for i in range(n)]
        info = f" relays={addrs}"
        for a in addrs:
            s.sendto(msg(0x70), a)
    elif t == 0x82:
        rip, rport = parse_sockaddr(pl[:16]); ticket = struct.unpack(">I", pl[16:20])[0]
        info = f" relay={rip}:{rport} ticket={ticket:#x} -> RLY_PKT x4"
        pkt = msg(0x83, struct.pack(">I", ticket) + DID + bytes(4))
        for _ in range(4):
            s.sendto(pkt, (rip, rport))
        tickets.append(((rip, rport), ticket))
    elif t == 0x71 and relay is None:
        relay = addr; s.sendto(msg(0x72), addr); info = " -> RLY_PORT"
    elif t == 0x73 and mark is None:
        mark, port = struct.unpack(">IH", pl[:6]); relay = (relay[0], port)
        info = f" mark={mark:#x} port={port}"
        for srv in servers:
            s.sendto(msg(0x80, DID + sockaddr(*relay) + struct.pack(">I", mark)), (srv, 32100))
        last_req = time.time()
    elif t == 0x84:
        rdy = addr; info = "  *** RELAY READY ***"
    elif t == 0xE0:
        s.sendto(msg(0xE1), addr)
    print(f"{time.time()-t0:5.1f}s {addr[0]}:{addr[1]} {NAMES.get(t, hex(t))} len={ln} {pl[:40].hex()}{info}")
for a in {rdy, relay} - {None}:
    s.sendto(msg(0xF0), a)
print("relay:", relay, "mark:", mark, "ready:", rdy)
