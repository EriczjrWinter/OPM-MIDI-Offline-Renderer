# player.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import argparse
import os
import struct
import sys
import wave
from array import array

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
        
        # 1. 获取 OPM 音频
        raw_opm = core.generate(n)
        opm_array = array('h')
        opm_array.frombytes(raw_opm)
        
        # 2. 获取 SSG 音频
        ssg_array = system.ssg.generate(n)
        
        # 3. 极速混音：利用切片的批量处理（避免逐点 for 循环）
        # opm_array[0::2] 提取左声道，opm_array[1::2] 提取右声道
        # 注意：这里我们用列表推导式，比手动 append 快得多
        left_channel = [max(-32767, min(32767, (l + s * 4) >> 1)) for l, s in zip(opm_array[0::2], ssg_array)]
        right_channel = [max(-32767, min(32767, (r + s * 4) >> 1)) for r, s in zip(opm_array[1::2], ssg_array)]
        
        # 将左右声道交错合并
        mixed = array('h')
        for l, r in zip(left_channel, right_channel):
            mixed.append(l)
            mixed.append(r)
            
        out += mixed.tobytes()
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
    ap = argparse.ArgumentParser(description="OPM MIDI 合成器 (SSG Edition)")
    ap.add_argument("midi", help="标准 MIDI 文件")
    ap.add_argument("-o", "--out", required=True, help="输出 WAV")
    ap.add_argument("--bank", default=DEFAULT_BANK, help=".opm 音色库路径")
    ap.add_argument("--core", default="opm", choices=["opm", "null"])
    ap.add_argument("--clock", type=int, default=3_579_545)
    ap.add_argument("--tail", type=float, default=1.0, help="尾部余响秒数")
    ap.add_argument("-r", "--raw", action="store_true", help="关闭翻译，保留原始偏移")
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
    system.translate_pitch = not args.raw
    system.translate_env = not args.raw

    sr = core.sample_rate()
    pcm = render(system, core, events, total_sec, sr, tail=args.tail)

    write_wav(args.out, pcm, sr)
    
    peak = 0
    if pcm:
        samples = struct.unpack('<%dh' % (len(pcm) // 2), pcm)
        peak = max(max(samples), abs(min(samples)))

    print(f"WAV -> {args.out}  {sr}Hz  peak={peak}/32767")

    core.close()
    system.ssg.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())