"""Disassemble named functions from libPPCS_API.so (arm64). Usage: dis.py <substr> [...]"""
import sys
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
from elftools.elf.elffile import ELFFile
LIB = sys.argv[1]
f = open(LIB, "rb"); elf = ELFFile(f); data = open(LIB, "rb").read()
syms = {}
for sec in elf.iter_sections():
    if sec.name in (".dynsym", ".symtab"):
        for s in sec.iter_symbols():
            if s["st_info"]["type"] == "STT_FUNC" and s["st_value"]:
                syms[s.name] = (s["st_value"], s["st_size"])
addr2name = {v[0]: k for k, v in syms.items()}
def off(va):
    for seg in elf.iter_segments():
        if seg["p_type"] == "PT_LOAD" and seg["p_vaddr"] <= va < seg["p_vaddr"] + seg["p_filesz"]:
            return va - seg["p_vaddr"] + seg["p_offset"]
md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
for pat in sys.argv[2:]:
    for name, (va, size) in sorted(syms.items()):
        if pat in name and (pat.startswith("=") is False):
            print(f"\n==== {name} @ {va:#x} size {size}")
            o = off(va)
            for ins in md.disasm(data[o:o + size], va):
                ops = ins.op_str
                if ins.mnemonic == "bl":
                    try:
                        t = int(ops.lstrip("#"), 16); ops += "  <" + addr2name.get(t, "?") + ">"
                    except ValueError:
                        pass
                print(f"  {ins.address:x}: {ins.mnemonic:6} {ops}")

# xrefs: "xref:<substr>" prints which functions call matching symbols
