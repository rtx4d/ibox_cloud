import sys
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
from elftools.elf.elffile import ELFFile
LIB = sys.argv[1]; elf = ELFFile(open(LIB, "rb")); data = open(LIB, "rb").read()
syms = {}
for sec in elf.iter_sections():
    if sec.name in (".dynsym", ".symtab"):
        for s in sec.iter_symbols():
            if s["st_info"]["type"] == "STT_FUNC" and s["st_value"]:
                syms[s.name] = (s["st_value"], s["st_size"])
def off(va):
    for seg in elf.iter_segments():
        if seg["p_type"] == "PT_LOAD" and seg["p_vaddr"] <= va < seg["p_vaddr"] + seg["p_filesz"]:
            return va - seg["p_vaddr"] + seg["p_offset"]
md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
targets = {va: n for n, (va, _) in syms.items() if any(p in n for p in sys.argv[2:])}
for name, (va, size) in syms.items():
    o = off(va)
    for ins in md.disasm(data[o:o + size], va):
        if ins.mnemonic in ("bl", "b"):
            try: t = int(ins.op_str.lstrip("#"), 16)
            except ValueError: continue
            if t in targets:
                print(f"{targets[t][:60]:60} <- {name[:90]} @ {ins.address:x}")
