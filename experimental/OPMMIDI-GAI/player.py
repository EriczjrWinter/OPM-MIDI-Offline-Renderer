# player.py
# -*- coding: utf-8 -*-
"""OPM MIDI 合成器 CLI —— MIDI -> WAV。"""
from __future__ import annotations

import argparse
import os
import struct
import sys
import wave
import math
import glob
from array import array

from core import NullCore, OpmCore
from driver import OpmSystem
from smf import parse_smf
from voice import load_opm_text

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BANK = os.path.join(HERE, "NECOPN_GM.opm")

# ==========================================
# 🎛️ 软削波处理函数 (放在最外层，防止缩进报错)
# ==========================================
def apply_soft_clip(x):
    THRESHOLD = 0.5  # 超过 50% 音量就开始温柔地“磨圆”
    if x > THRESHOLD:
        return THRESHOLD + (1.0 - THRESHOLD) * math.tanh((x - THRESHOLD) / (1.0 - THRESHOLD))
    elif x < -THRESHOLD:
        return -THRESHOLD - (1.0 - THRESHOLD) * math.tanh((-x - THRESHOLD) / (1.0 - THRESHOLD))
    return x


def render(system: OpmSystem, core, events, total_sec: float,
           sr: int, tail: float = 1.0, chunk_cap: int = 512) -> bytes:
    total_frames = int((total_sec + tail) * sr)
    out = bytearray()
    frames = 0
    ei = 0

    # ==========================================
    # 🎛️ PCM 复古滤镜与混音参数区
    # ==========================================
    BITMASK = 0xFFF0  # 12-bit 降比特
    LPF_ALPHA = 0.45  # 低通滤波
    pcm_lpf_state = 0.0
    
    duck_env = 0.0
    DUCK_AMOUNT = 0.75  # 极端侧链闪避：鼓一响，FM 瞬间让路 75%
    DUCK_DECAY = 0.008
    
    # 压低基础音量，为软削波留出空间
    OPM_VOL = 0.45
    PCM_VOL = 0.55  
    # ==========================================

    while frames < total_frames:
        now = frames / sr
        
        # 1. 处理 MIDI 事件
        while ei < len(events) and events[ei].t <= now:
            e = events[ei]
            system.time = e.t
            if   e.kind == "on":   
                system.note_on(e.ch, e.d1, e.d2)
                if e.ch == 9:
                    duck_env = 1.0 # 鼓声触发侧链闪避
            elif e.kind == "off":  system.note_off(e.ch, e.d1)
            elif e.kind == "cc":   system.control_change(e.ch, e.d1, e.d2)
            elif e.kind == "prog": system.program_change(e.ch, e.d1)
            elif e.kind == "bend": system.pitch_bend(e.ch, e.d1, e.d2)
            ei += 1

        # 2. 计算当前块需要生成的帧数
        n = min(chunk_cap, total_frames - frames)
        
        # 3. 获取 OPM 和 PCM 数据
        raw_opm = core.generate(n)
        opm_array = array('h')
        opm_array.frombytes(raw_opm)
        
        pcm_array = system.pcm.generate(n)
        
        scaled = array('h')
        
        # 4. 逐个采样点混音
        for i in range(n):
            l = opm_array[i * 2]
            r = opm_array[i * 2 + 1]
            pcm_val = pcm_array[i]

            # 降比特处理 (处理 Python 负数坑)
            crushed_pcm = pcm_val & BITMASK
            if crushed_pcm > 32767:
                crushed_pcm -= 65536

            # 低通滤波
            pcm_lpf_state = pcm_lpf_state + LPF_ALPHA * (crushed_pcm - pcm_lpf_state)
            filtered_pcm = int(pcm_lpf_state)

            # 计算当前的 OPM 音量（侧链闪避）
            current_opm_vol = OPM_VOL * (1.0 - (duck_env * DUCK_AMOUNT))

            # 浮点混音 (除法转成 -1.0 ~ 1.0 的浮点数)
            f_opm_l = (l / 32768.0) * current_opm_vol
            f_opm_r = (r / 32768.0) * current_opm_vol
            f_pcm   = (filtered_pcm / 32768.0) * PCM_VOL
            
            mix_l = f_opm_l + f_pcm
            mix_r = f_opm_r + f_pcm
            
            # 软削波代替硬限幅
            mix_l = apply_soft_clip(mix_l)
            mix_r = apply_soft_clip(mix_r)
            
            # 转回 16-bit 整数
            final_l = int(mix_l * 32767.0)
            final_r = int(mix_r * 32767.0)
            
            scaled.append(final_l)
            scaled.append(final_r)
            
            # 衰减包络
            if duck_env > 0:
                duck_env -= DUCK_DECAY
                if duck_env < 0: duck_env = 0.0
            
        out += scaled.tobytes()
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
    ap = argparse.ArgumentParser(description="OPM MIDI 合成器 GAI版")
    ap.add_argument("midi", help="标准 MIDI 文件")
    ap.add_argument("-o", "--out", required=True, help="输出 WAV")
    ap.add_argument("--bank", default=DEFAULT_BANK, help=".opm 音色库路径")
    ap.add_argument("--core", default="opm", choices=["opm", "null"])
    ap.add_argument("--clock", type=int, default=3_579_545)
    ap.add_argument("--tail", type=float, default=1.0, help="尾部余响秒数")
    ap.add_argument("-r", "--raw", action="store_true", 
                    help="关闭翻译，保留原始 OPN 到 OPM 的物理偏移与畸变")

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

    # ==========================================
    # 📥 自动加载 Korg M1 鼓组
    # ==========================================
    drum_dir = os.path.join(HERE, "drum_samples", "lofi")
    if not os.path.exists(drum_dir):
        drum_dir = os.path.join(HERE, "drum_samples")
        
    # 完整的 Korg M1 鼓组映射 (覆盖 GM 标准鼓 35~81)
    KORG_KEYWORD_MAP = {
        # --- 底鼓 ---
        35: "Kick 1",
        36: "Kick 2",      # 如果曲子用到 36，用 Kick 2 代替
        # --- 军鼓 / 拍手 ---
        38: "Snare 1",
        40: "Snare 2",
        39: "Claps",       # 拍手
        # --- 踩镲 ---
        42: "Closed HH",
        44: "Closed HH 2", # 踏板踩镲（如果没有专门的 Pedal，用闭镲代替）
        46: "Open HH",
        # --- 桶鼓 (Tom) ---
        41: "Tom 2",       # 落地桶鼓
        43: "E.Tom",       # 电子桶鼓
        45: "Tom 1",       # 中桶鼓
        47: "E.Tom",       # 中低桶鼓 (可用电鼓代替)
        48: "Tom 1",       # 中高桶鼓
        50: "Tom 2",       # 高桶鼓
        # --- 镲片 ---
        49: "Crash",       # 强音镲 1
        52: "Crash",       # 中国镲（用普通强音镲代替）
        55: "Crash",       # 水镲（用普通强音镲代替）
        57: "Crash",       # 强音镲 2
        51: "Ride",        # 叮叮镲 1
        59: "Ride",        # 叮叮镲 2
        53: "Bell Ring",   # 镲帽（Ride Bell）
        # --- 拉丁/民族打击乐 ---
        60: "Conga 1",     # 高音康加鼓
        61: "Conga 2",     # 低音康加鼓
        62: "Conga 1",     # 闷音康加
        63: "Conga 1",     # 开音康加
        64: "Conga 2",     # 低音康加
        65: "Timbales 1",  # 高音天巴鼓
        66: "Timbales 2",  # 低音天巴鼓
        # --- 杂项打击乐 ---
        54: "Tambourine",  # 铃鼓
        56: "Cowbell",     # 牛铃
        58: "Vibe Hit",    # 颤音器（Vibraslap）
        69: "Shaker",      # 卡巴萨（用沙锤代替）
        70: "Shaker",      # 沙锤
        75: "Block",       # 击木（Claves）
        76: "Block",       # 高音木鱼
        77: "Block",       # 低音木鱼
        80: "Tubular",     # 闷音三角铁（用管钟代替）
        81: "Tubular",     # 开音三角铁
        82: "Whip",        # 鞭击（如果曲子用到）
    }
    loaded_count = 0
    if os.path.exists(drum_dir):
        for wav_path in glob.glob(os.path.join(drum_dir, "*.wav")):
            filename = os.path.basename(wav_path)
            for note, keyword in KORG_KEYWORD_MAP.items():
                if keyword in filename:
                    system.pcm.load_sample(str(note), wav_path)
                    loaded_count += 1
                    break
    if loaded_count > 0:
        print(f"🥁 成功加载并映射了 {loaded_count} 个 Korg 鼓采样！")
    else:
        print("⚠️ 未找到 Korg 鼓采样，将回退到 FM 鼓组。")

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