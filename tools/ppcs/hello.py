import json, socket, sys, time
sys.path.insert(0, ".")
from initstring import decode
import cs2crypt
d = json.load(open("../junan_p2pinfo.json"))
enc, key = d["initStringApp"].split(":")
servers = [s for s in decode(enc).decode().split(",") if s]
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(1.5); s.bind(("0.0.0.0", 0))
hello = bytes([0xF1, 0x00, 0x00, 0x00])
for label, pkt in (("plain", hello), ("crypt", cs2crypt.encrypt(key, hello)), ("crypt-psk-default", cs2crypt.encrypt("SSD@cs2-network.", hello))):
    for srv in servers:
        s.sendto(pkt, (srv, 32100))
        try:
            data, addr = s.recvfrom(2048)
            dec = data if data[0] == 0xF1 else cs2crypt.decrypt(key if label == "crypt" else "SSD@cs2-network.", data)
            print(f"{label:18} {srv:16} -> {len(data)}B raw={data[:4].hex()} dec={dec.hex()}")
        except socket.timeout:
            print(f"{label:18} {srv:16} -> timeout")
