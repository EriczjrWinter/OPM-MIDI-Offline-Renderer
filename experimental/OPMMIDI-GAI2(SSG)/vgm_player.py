# vgm_player.py
# -*- coding: utf-8 -*-
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

def export_vgm(path: str, opm_log: list, ssg_log: list, total_sec: float):
    print(f"正在打包双芯片 VGM，OPM 事件: {len(opm_log)}，SSG 事件: {len(ssg_log)}...")
    total_samples = int(total_sec * 44100)
    
    with open(path, 'wb') as f:
        f.write(b'Vgm ')
        f.write(struct.pack('<I', 0))            
        f.write(struct.pack('<I', 0x151))        
        f.write(struct.pack('<I', 0))            
        f.write(struct.pack('<I', 0))            
        f.write(struct.pack('<I', 0))            
        f.write(struct.pack('<I', total_samples))
        f.write(struct.pack('<I', 0))            
        f.write(struct.pack('<I', 0))            
        f.write(struct.pack('<I', 0))            
        f.write(b'\x00' * 8)                     
        f.write(struct.pack('<I', 3579545))      # 0x30: YM2151 Clock
        
        # 【核心修复】：数据偏移量指向 0x80（0x80 - 0x34 = 0x4C）
        f.write(struct.pack('<I', 0x4C))         # 0x34: Data Offset
        f.write(b'\x00' * (0x74 - 0x38))         # 0x38 ~ 0x73: 填充
        f.write(struct.pack('<I', 1789772))      # 0x74: YM2149 Clock
        f.write(b'\x01')                         # 0x78: Chip Type 设为 YM2149
        f.write(b'\x00' * (0x80 - 0x79))         # 0x79 ~ 0x7F: 填充      

        all_events = []
        for t, reg, val in opm_log:
            all_events.append((t, 'opm', reg, val))
        for t, reg, val in ssg_log:
            all_events.append((t, 'ssg', reg, val))
        all_events.sort(key=lambda x: x[0])

        data_buf = bytearray()
        last_sample = 0
        
        for t, ev_type, arg1, arg2 in all_events:
            current_sample = int(t * 44100)
            wait = current_sample - last_sample
            while wait > 0:
                chunk = min(wait, 65535)
                data_buf.extend(b'\x61' + struct.pack('<H', chunk))
                wait -= chunk
            last_sample = current_sample
            
            if ev_type == 'opm':
                data_buf.extend(b'\x54' + bytes([arg1, arg2]))
            elif ev_type == 'ssg':
                data_buf.extend(b'\xA0' + bytes([arg1, arg2]))
            
        data_buf.extend(b'\x66')
        f.write(data_buf)
        
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
        return 2
        
    voices = load_opm_text(args.bank)
    data = open(args.midi, "rb").read()
    events, tpq, total_sec = parse_smf(data)
    
    print(f"音色库: {len(voices)} 条 | MIDI: {len(events)} 事件 | 时长: {total_sec:.2f}s")

    core = NullCore()
    system = OpmSystem(core)
    system.load_bank(voices)
    system.trace_vgm = True

    sr = core.sample_rate()
    total_frames = int(total_sec * sr)
    frames = 0
    ei = 0
    chunk_cap = 1024

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
        core.generate(n)
        system.advance_time(n / sr)
        frames += n

    system.trace_vgm = False
    export_vgm(args.out, system.vgm_log, system.vgm_ssg_log, total_sec)
    system.ssg.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())