# voice.py
import re
from dataclasses import dataclass, field

@dataclass
class OpmVoice:
    name: str = ""
    lfo: tuple = (0, 0, 0, 0, 0)       # LFRQ, AMD, PMD, WF, NFRQ
    ch:  tuple = (64, 0, 7, 0, 0, 120, 0)  # PAN, FL, CON, AMS, PMS, slot_mask, NE
    ops: list = field(default_factory=list)  # 4 个 dict: AR DR SR RR SL TL KS MUL DT1 DT2

    @classmethod
    def from_opm_block(cls, name: str, lines: list[str]) -> "OpmVoice":
        v = cls(name=name)
        for line in lines:
            line = line.strip()
            if line.startswith("LFO:"):
                v.lfo = tuple(int(x) for x in line[4:].split())
            elif line.startswith("CH:"):
                v.ch = tuple(int(x) for x in line[3:].split())
            elif line[:3] in ("M1:", "C1:", "M2:", "C2:"):
                vals = [int(x) for x in line[3:].split()]
                v.ops.append({
                    "ar": vals[0], "dr": vals[1], "sr": vals[2],
                    "rr": vals[3], "sl": vals[4], "tl": vals[5],
                    "ks": vals[6], "mul": vals[7], "dt1": vals[8],
                    "dt2": vals[9] if len(vals) > 9 else 0,
                })
        return v


def load_opm_text(path: str) -> list[OpmVoice]:
    voices, cur_name, cur_lines = [], None, []
    for raw in open(path, encoding="ascii", errors="ignore"):
        line = raw.rstrip("\r\n")
        if line.startswith("@:"):
            if cur_name is not None:
                voices.append(OpmVoice.from_opm_block(cur_name, cur_lines))
            cur_name = line.split(None, 1)[1] if len(line.split(None, 1)) > 1 else ""
            cur_lines = []
        elif cur_name is not None and line.strip():
            cur_lines.append(line)
    if cur_name is not None:
        voices.append(OpmVoice.from_opm_block(cur_name, cur_lines))
    return voices