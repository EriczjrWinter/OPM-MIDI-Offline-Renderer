# vgm_player.py
# -*- coding: utf-8 -*-
"""将 MIDI 转换为纯正的 YM2151 VGM 格式"""
from __future__ import annotations
import argparse
import os
import struct
import sys

from core import NullCore
from driver import OpmSystem
from smf import parse_smf
from voice import load_opm_text

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BANK = os.path.join(HERE, "NECOPN_GM.opm")


def export_vgm(path: str, log: list[tuple[float, int, int]], total_sec: float):
    print(f"正在打包 VGM，共计 {len(log)} 个寄存器事件...")
    
    total_samples = int(total_sec * 44100)
    
    with open(path, 'wb') as f:
        # --- VGM 文件头 (0x40 字节) ---
        f.write(b'Vgm ')
        f.write(struct.pack('<I', 0))            # 0x04: EOF offset
        f.write(struct.pack('<I', 0x150))        # 0x08: Version 1.50
        f.write(struct.pack('<I', 0))            # 0x0C: SN76489 clock
        f.write(struct.pack('<I', 0))            # 0x10: YM2413 clock
        f.write(struct.pack('<I', 0))            # 0x14: GD3 offset
        f.write(struct.pack('<I', total_samples)) # 0x18: Total # samples ✅
        f.write(struct.pack('<I', 0))            # 0x1C: Loop offset ✅ (修正)
        f.write(struct.pack('<I', 0))            # 0x20: Loop # samples
        f.write(struct.pack('<I', 0))            # 0x24: Rate
        f.write(b'\x00' * (0x30 - 0x28))         # 0x28 ~ 0x2F: 填充
        f.write(struct.pack('<I', 3579545))      # 0x30: YM2151 clock ✅ (修正)
        f.write(struct.pack('<I', 0x0C))         # 0x34: VGM data offset (0x40 - 0x34 = 0x0C)
        f.write(b'\x00' * (0x40 - 0x38))         # 0x38 ~ 0x3F: 填充

        # --- 数据区 ---
        data_buf = bytearray()
        last_sample = 0
        
        for t, reg, val in log:
            current_sample = int(t * 44100)
            wait = current_sample - last_sample
            while wait > 0:
                chunk = min(wait, 65535)
                data_buf.extend(b'\x61' + struct.pack('<H', chunk))
                wait -= chunk
            last_sample = current_sample
            # YM2151 写寄存器：0x54 后跟 (寄存器地址, 数据) 两个字节
            data_buf.extend(b'\x54' + bytes([reg, val]))
            
        data_buf.extend(b'\x66')  # End of sound data
        f.write(data_buf)
        
        # 回填 EOF offset
        file_size = f.tell()
        f.seek(4)
        f.write(struct.pack('<I', file_size - 4))
        
    print(f"VGM 导出成功: {path} ({(file_size/1024):.1f} KB)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="OPM MIDI -> VGM 导出器")
    ap.add_argument("midi", help="标准 MIDI 文件")
    ap.add_argument("-o", "--out", required=True, help="输出 VGM 文件")
    ap.add_argument("--bank", default=DEFAULT_BANK, help=".opm 音色库路径")
    args = ap.parse_args(argv)

    if not os.path.exists(args.bank):
        print(f"找不到音色库: {args.bank}", file=sys.stderr)
        return 2
        
    voices = load_opm_text(args.bank)
    data = open(args.midi, "rb").read()
    events, tpq, total_sec = parse_smf(data)
    
    print(f"音色库: {len(voices)} 条 | MIDI: {len(events)} 事件 | 时长: {total_sec:.2f}s")

    # 【核心】使用 NullCore，不生成实际声音，全速跑完事件
    core = NullCore()
    system = OpmSystem(core)
    system.load_bank(voices)
    system.trace_vgm = True # 开启录制

    # 因为我们不需要真实音频，所以可以用极大的步长（比如 1024 帧）来极速空跑
    # 这样几秒钟就能跑完一首 4 分钟的曲子
    sr = core.sample_rate()
    total_frames = int(total_sec * sr)
    frames = 0
    ei = 0
    chunk_cap = 1024

    print("正在模拟 MIDI 事件流...")
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
        # 这里的 generate 在 NullCore 里只返回空字节，瞬间完成
        core.generate(n)
        system.advance_time(n / sr)
        frames += n

    system.trace_vgm = False
    export_vgm(args.out, system.vgm_log, total_sec)
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())