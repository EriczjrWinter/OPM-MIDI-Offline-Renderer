# -*- coding: utf-8 -*-
"""标准 MIDI 文件（SMF type 0/1/2）解析 —— 只取播放需要的部分。"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class Event:
    t: float
    kind: str
    ch: int = 0
    d1: int = 0
    d2: int = 0


def _read_vlq(buf: bytes, i: int, end: int) -> Tuple[int, int]:
    v = 0
    for _ in range(4):
        if i >= end:
            raise ValueError(f"VLQ 越界: i={i} end={end}")
        b = buf[i]
        i += 1
        v = (v << 7) | (b & 0x7F)
        if not (b & 0x80):
            return v, i
    raise ValueError("VLQ 超过 4 字节")


def parse_smf(data: bytes, debug: bool = False) -> Tuple[List[Event], int, int]:
    if data[:4] != b"MThd":
        raise ValueError("不是 SMF 文件")
    hdr_len, fmt, ntrk, division = struct.unpack_from(">IHHH", data, 4)
    if division & 0x8000:
        raise ValueError("SMPTE 时间格式暂不支持")
    tpq = division or 480

    if debug:
        print(f"[SMF] format={fmt} ntrk={ntrk} division={tpq} file={len(data)}B")

    pos = 8 + hdr_len
    tempo_map: List[Tuple[int, int]] = []
    raw_events: List[Tuple[int, int, int, int, int]] = []
    max_abs_tick = 0  # 【修复 1】用于记录整个文件的绝对最大 Tick（包含结尾空白）

    for track_i in range(ntrk):
        if pos + 8 > len(data) or data[pos:pos + 4] != b"MTrk":
            if debug:
                print(f"[SMF] !!! track {track_i} 提前退出: "
                      f"pos={pos:#x} tag={data[pos:pos+4]!r} "
                      f"剩余={len(data) - pos}B")
            break
        tlen = struct.unpack_from(">I", data, pos + 4)[0]
        i = pos + 8
        end = i + tlen
        if end > len(data):
            raise ValueError(f"track {track_i} 越界: end={end:#x} > file={len(data):#x}")

        tick = 0
        running_status = 0
        n_on = n_off = n_prog = n_cc = n_bend = n_meta = 0

        while i < end:
            delta, i = _read_vlq(data, i, end)
            tick += delta
            if i >= end:
                break
            b = data[i]

            if b & 0x80:
                if b < 0xF0:
                    running_status = b
                status = b
                i += 1
            else:
                status = running_status
                if status == 0:
                    raise ValueError(f"track {track_i} @ {i:#x}: 无 running status 时收到数据字节 {b:#x}")

            # ---- 元事件 ----
            if status == 0xFF:
                if i >= end:
                    break
                meta = data[i]
                i += 1
                ln, i = _read_vlq(data, i, end)
                if i + ln > end:
                    raise ValueError(f"track {track_i}: 元事件 payload 越界")
                
                # 【修复 2】兼容 FF 51 04，并加入合理性检查
                if meta == 0x51 and ln >= 3:
                    payload = data[i:i + 3]
                    usec = (payload[0] << 16) | (payload[1] << 8) | payload[2]
                    # 合法 BPM 限制 (20 ~ 500 BPM)
                    if 120000 <= usec <= 3000000:
                        tempo_map.append((tick, usec))
                    else:
                        if debug:
                            print(f"[SMF] ⚠️ 忽略异常 Tempo: {payload.hex()}")
                
                i += ln
                n_meta += 1
                continue

            if status in (0xF0, 0xF7):
                ln, i = _read_vlq(data, i, end)
                i += ln
                continue
            if status >= 0xF8:
                continue
            if status == 0xF1 or status == 0xF3:
                i += 1
                continue
            if status == 0xF2:
                i += 2
                continue
            if status == 0xF6:
                continue

            # ---- MIDI 通道消息 ----
            kind = status & 0xF0
            ch = status & 0x0F
            if kind in (0xC0, 0xD0):
                d1 = data[i]
                i += 1
                d2 = 0
            else:
                d1 = data[i]
                d2 = data[i + 1]
                i += 2

            if kind in (0x80, 0x90, 0xB0, 0xC0, 0xE0):
                raw_events.append((tick, kind, ch, d1, d2))
                if kind == 0x90 and d2 > 0: n_on += 1
                elif kind == 0x80 or (kind == 0x90 and d2 == 0): n_off += 1
                elif kind == 0xC0: n_prog += 1
                elif kind == 0xB0: n_cc += 1
                elif kind == 0xE0: n_bend += 1

        # 【修复 3】记录该轨道的绝对结尾 Tick（不管有没有音符）
        if tick > max_abs_tick:
            max_abs_tick = tick

        if debug:
            tail = data[max(0, end - 4):end].hex()
            print(f"[SMF] track {track_i}: len={tlen:#x} end={end:#x} tail={tail} "
                  f"on={n_on} off={n_off} prog={n_prog} cc={n_cc} "
                  f"bend={n_bend} meta={n_meta}")
        pos = end

    if not tempo_map:
        tempo_map = [(0, 500000)]
    tempo_map.sort()
    if tempo_map[0][0] > 0:
        tempo_map.insert(0, (0, 500000))

    def tick_to_sec(t: int) -> float:
        sec = 0.0
        last_tick, last_tempo = tempo_map[0]
        for idx in range(1, len(tempo_map)):
            mt, mtempo = tempo_map[idx]
            if mt >= t:
                break
            sec += (mt - last_tick) * last_tempo / 1e6 / tpq
            last_tick, last_tempo = mt, mtempo
        sec += (t - last_tick) * last_tempo / 1e6 / tpq
        return sec

    events: List[Event] = []
    name_map = {0x80: "off", 0x90: "on", 0xB0: "cc",
                0xC0: "prog", 0xE0: "bend"}
    for tick, kind, ch, d1, d2 in raw_events:
        events.append(Event(tick_to_sec(tick), name_map[kind], ch, d1, d2))
    events.sort(key=lambda e: e.t)

    # 【修复 4】总时长优先以轨道的绝对物理末端为准，防止吃掉尾部留白
    if max_abs_tick > 0:
        total = tick_to_sec(max_abs_tick)
    else:
        total = max((e.t for e in events), default=0.0)

    if debug:
        print(f"[SMF] 总计: events={len(events)} tempo_marks={len(tempo_map)} "
              f"total={total:.2f}s")

    return events, tpq, total