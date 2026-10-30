"""CS2 "P2P_Proprietary_Encrypt": XOR keystream from a 256-byte table and a 4-byte key hash
(port of magicus/pppp-dissector)."""

TABLE = bytes.fromhex("7c9ce84a13dedcb22f2123e4307b3d8cbc0b270c3cf79ae7087196009785efc11fc4dba1c2ebd901faba3b05b81587832872d18b5ad6da9358feaacc6e1bf0a388ab43c00db545384f502266207f075b14981d9ba72ab9a8cbf1fc4947063eb10e043a945eee541134dd4df9ecc7c9e3781a6f706ba4bda95dd5f8e5bb26af4237d8e1020aae5f1cc573094e6924906d12b319ad748a2940f52dbea559e0f479d24bce8982488425c6912ba2fb8fe9a6b09e3f65f603312eac0f952c5ced39b7336c567eb4a0fd7a815351868d9f77ff6a80dfe2bf10d775645776f355cdd0c818e6364162cf99f2324c67606192cad3ea637d16b68ed46835c3529d46441e17")


def key_hash(key: str) -> list[int]:
    h = [0, 0, 0, 0]
    for b in key.encode():
        h[0] = (h[0] + b) & 255
        h[1] = (h[1] - b) & 255
        h[2] = (h[2] + b // 3) & 255
        h[3] = h[3] ^ b
    return h


def _lookup(h: list[int], prev: int) -> int:
    return TABLE[(h[prev & 3] + prev) & 255]


def encrypt(key: str, data: bytes) -> bytes:
    h, out, prev = key_hash(key), bytearray(), 0
    for b in data:
        prev = b ^ _lookup(h, prev)
        out.append(prev)
    return bytes(out)


def decrypt(key: str, data: bytes) -> bytes:
    h, out, prev = key_hash(key), bytearray(), 0
    for b in data:
        out.append(b ^ _lookup(h, prev))
        prev = b
    return bytes(out)
