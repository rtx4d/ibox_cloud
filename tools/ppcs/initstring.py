"""PPPP_DecodeString (CS2 init string) — port of bettse/pppp_decodestring."""
DEFAULT_TABLE = bytes.fromhex(
    "4959433db5bf6da347534f6165e371e9677f02030badb3892b2f35c16b8b959711e5a70deff1050783fb9d3bc5c713171d1f2529d3df"
)

def decode(encoded: str, table: bytes = DEFAULT_TABLE) -> bytes:
    out = bytearray(len(encoded) // 2)
    for i in range(len(out)):
        b = 57
        for prev in out[:i]:
            b ^= prev
        val = 16 * (ord(encoded[2 * i]) - 65) + (ord(encoded[2 * i + 1]) - 65)
        out[i] = (b ^ table[i % len(table)] ^ val) & 0xFF
    return bytes(out)
