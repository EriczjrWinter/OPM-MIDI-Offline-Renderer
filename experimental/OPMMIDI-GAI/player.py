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


def render(system: OpmSystem, core, events, total_sec: float, sr: int, tail: float = 1.0, chunk_cap: int = 512) -> bytes:
    total_frames = int((total_sec + tail) * sr)
    out = bytearray()
    frames = 0
    ei = 0
    
    # 基础音量权重
    OPM_VOL = 1.0
    PCM_VOL = 1.0
    
    # 侧链闪避状态
    duck_env = 0.0  # 当前闪避包络(0.0~1.0)
    DUCK_AMOUNT = 0.5  # 鼓声最大能压掉 OPM 多少音量 (0.5 代表压低 50%)
    DUCK_DECAY = 0.005 # 闪避恢复的速度 (每帧恢复多少)

    while frames < total_frames:
        now = frames / sr
        
        # 1. 处理 MIDI 事件
        while ei < len(events) and events[ei].t <= now:
            e = events[ei]
            system.time = e.t
            if   e.kind == "on":   
                system.note_on(e.ch, e.d1, e.d2)
                # 【触发侧链】：如果是鼓（通道 9），瞬间拉满闪避包络
                if e.ch == 9:
                    duck_env = 1.0
            elif e.kind == "off":  system.note_off(e.ch, e.d1)
            elif e.kind == "cc":   system.control_change(e.ch, e.d1, e.d2)
            elif e.kind == "prog": system.program_change(e.ch, e.d1)
            elif e.kind == "bend": system.pitch_bend(e.ch, e.d1, e.d2)
            ei += 1

        n = min(chunk_cap, total_frames - frames)
        
        raw_opm = core.generate(n)
        opm_array = struct.unpack("<%dh" % (2 * n), raw_opm)
        pcm_array = system.pcm.generate(n) 
        
        scaled = []
        for i in range(n):
            # 获取原始音频
            l = opm_array[i * 2]
            r = opm_array[i * 2 + 1]
            pcm_l = pcm_array[i]
            
            # 【核心魔法】：根据闪避包络，动态缩放 OPM 的音量
            # 当 duck_env = 1.0 时，OPM 音量乘以 0.5 (压低一半)
            # 当 duck_env = 0.0 时，OPM 音量乘以 1.0 (恢复原样)
            current_opm_vol = OPM_VOL * (1.0 - (duck_env * DUCK_AMOUNT))
            
            final_l = int(l * current_opm_vol + pcm_l * PCM_VOL)
            final_r = int(r * current_opm_vol + pcm_l * PCM_VOL)
            
            # 防爆音限幅
            final_l = max(-32767, min(32767, final_l))
            final_r = max(-32767, min(32767, final_r))
            
            scaled.append(final_l)
            scaled.append(final_r)
            
            # 包络衰减（让被压低的 OPM 音量平滑恢复）
            if duck_env > 0:
                duck_env -= DUCK_DECAY
                if duck_env < 0: duck_env = 0.0
            
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