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

    # 调整 PCM 鼓的音量权重（0.0 ~ 1.0），防止鼓声完全盖住旋律
    PCM_VOL = 0.45 

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
        
        # 1. 获取 OPM 输出 (Nuked OPM 核心)
        raw_opm = core.generate(n)
        opm_array = struct.unpack("<%dh" % (2 * n), raw_opm)
        
        # 2. 获取 PCM 输出 (我们的模拟芯片)
        pcm_array = system.pcm.generate(n) # 这是一维的 array('h')，长度是 n
        
        # 3. 混合音频
        scaled = []
        for i in range(n):
            # OPM 是立体声（L, R 交错），PCM 是单声道
            l = opm_array[i * 2]
            r = opm_array[i * 2 + 1]
            
            # 把 PCM 乘以音量权重后，同时加到左右声道
            pcm_l = int(pcm_array[i] * PCM_VOL)
            
            l += pcm_l
            r += pcm_l
            
            # 4. 降增益与安全限幅 (防止混音后爆音)
            l = l >> 1
            r = r >> 1
            
            scaled.append(max(-32767, min(32767, l)))
            scaled.append(max(-32767, min(32767, r)))
            
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

    # 【加载 RHY 采样】
    # 假设这些 WAV 文件在项目根目录，或者你指定的路径下
    rhy_files = {
        'BD': '2608_BD.WAV',
        'HH': '2608_HH.WAV',
        'RIM': '2608_RIM.WAV',
        'SD': '2608_SD.WAV',
        'TOM': '2608_TOM.WAV',
        'TOP': '2608_TOP.WAV',
        # 'RYM': '2608_RYM.WAV' # 这个视情况加载，可能不是标准鼓
    }
    
    for name, filename in rhy_files.items():
        if os.path.exists(filename):
            system.pcm.load_sample(name, filename)

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