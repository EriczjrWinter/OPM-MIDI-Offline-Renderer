# player.py
# -*- coding: utf-8 -*-
"""OPM MIDI 合成器 CLI —— MIDI -> WAV。"""
from __future__ import annotations

import argparse
import os
import struct
import sys
import wave

from core import NullCore, OpmCore
from driver import OpmSystem
from smf import parse_smf
from voice import load_opm_text

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BANK = os.path.join(HERE, "NECOPN_GM.opm")


def render(system: OpmSystem, core, events, total_sec: float,
           sr: int, tail: float = 1.0, chunk_cap: int = 512) -> bytes:
    total_frames = int((total_sec + tail) * sr)
    out = bytearray()
    frames = 0
    ei = 0

    while frames < total_frames:
        now = frames / sr
        while ei < len(events) and events[ei].t <= now:
            e = events[ei]
            system.time = e.t
            if   e.kind == "on":   system.note_on(e.ch, e.d1, e.d2)
            elif e.kind == "off":  system.note_off(e.ch, e.d1)
            elif e.kind == "cc":   system.control_change(e.ch, e.d1, e.d2)
            elif e.kind == "prog": system.program_change(e.ch, e.d1)
            elif e.kind == "bend": system.pitch_bend(e.ch, e.d1, e.d2)
            ei += 1

        n = min(chunk_cap, total_frames - frames)
        raw = core.generate(n)
        
        samples = struct.unpack("<%dh" % (2 * n), raw)
        
        # 【完美音量】你原来的 v >> 3 是除以8（峰值3000）。
        # 现在我们改成 v >> 1（除以2），峰值会完美落在 12000~16000 之间！
        # 纯位运算，速度极快，且绝对不会爆音！
        scaled = [v >> 1 for v in samples]
        
        out += struct.pack("<%dh" % (2 * n), *scaled)
        
        system.advance_time(n / sr)
        frames += n

    return bytes(out)


def write_wav(path: str, pcm: bytes, sr: int) -> None:
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="OPM MIDI 合成器")
    ap.add_argument("midi", help="标准 MIDI 文件")
    ap.add_argument("-o", "--out", required=True, help="输出 WAV")
    ap.add_argument("--bank", default=DEFAULT_BANK, help=".opm 音色库路径")
    ap.add_argument("--core", default="opm", choices=["opm", "null"])
    ap.add_argument("--clock", type=int, default=3_579_545)
    ap.add_argument("--tail", type=float, default=1.0, help="尾部余响秒数")
    args = ap.parse_args(argv)

    if not os.path.exists(args.bank):
        print(f"找不到音色库: {args.bank}", file=sys.stderr)
        return 2
    voices = load_opm_text(args.bank)
    print(f"音色库: {len(voices)} 条  ({os.path.basename(args.bank)})")

    data = open(args.midi, "rb").read()
    events, tpq, total_sec = parse_smf(data)
    print(f"MIDI: {len(events)} 事件  {total_sec:.2f}s  tpq={tpq}")

    if args.core == "opm":
        core = OpmCore(clock=args.clock)
    else:
        core = NullCore(clock=args.clock)
    print(f"核心: {core.name}  sr={core.sample_rate()}")

    system = OpmSystem(core)
    system.load_bank(voices)

    sr = core.sample_rate()
    pcm = render(system, core, events, total_sec, sr, tail=args.tail)

    write_wav(args.out, pcm, sr)
    
    peak = 0
    if pcm:
        samples = struct.unpack('<%dh' % (len(pcm) // 2), pcm)
        peak = max(max(samples), abs(min(samples)))

    print(f"WAV -> {args.out}  {sr}Hz  peak={peak}/32767")

    core.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())