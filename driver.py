# driver.py
from __future__ import annotations
import math
from dataclasses import dataclass
from core import ChipCore
from voice import OpmVoice

# 文件行顺序 M1,C1,M2,C2 → 物理 slot 0,2,1,3（与 VOPM 的 SendVo 一致）
VOPM_OP_REG = [0, 2, 1, 3]

# 正确的 OPM 硬件音阶表（跳过 3, 7, 11）
KTBL = [1, 2, 4, 5, 6, 8, 9, 10, 12, 13, 14, 15]

# 修正后的载波表（对应 ops 顺序 M1, C1, M2, C2）
CARRIER_MASK = {
    0: (0, 0, 0, 1),   # C2
    1: (0, 0, 0, 1),   # C2
    2: (0, 0, 0, 1),   # C2
    3: (0, 0, 1, 1),   # M2, C2
    4: (0, 1, 0, 1),   # C1, C2
    5: (0, 1, 1, 1),   # C1, M2, C2
    6: (0, 1, 1, 1),   # C1, M2, C2
    7: (1, 1, 1, 1),   # 全载波
}

TL_DB_PER_STEP = 0.75


def _pan_bits(pan: int) -> int:
    if pan < 32:
        return 0x40
    if pan > 96:
        return 0x80
    return 0xC0


@dataclass
class Slot:
    midi_ch: int = 0
    note: int = 0
    program: int = 0
    velocity: int = 0
    active: bool = False
    released: bool = False
    pending_off: bool = False
    start_time: float = 0.0
    release_time: float = 0.0
    serial: int = 0


class OpmSystem:
    def __init__(self, core: ChipCore, n_ch: int = 8, bend_range: int = 2):
        self.core = core
        self.n_ch = n_ch
        self.bend_range = bend_range
        self.slots = [Slot() for _ in range(n_ch)]
        self.loaded_program = [-1] * n_ch
        self.voices: list[OpmVoice] = []
        self.programs = [0] * 16
        self.bend14 = [8192] * 16
        
        self.sustain = [False] * 16
        self.ch_vol = [127] * 16
        self.ch_expr = [127] * 16
        self.ch_brightness = [64] * 16  # 新增：CC74 亮度，默认 64（中心点）
        
        self.serial = 0
        self.time = 0.0
        self._init_hardware()

    def _w(self, reg: int, val: int) -> None:
        self.core.write(reg, val)

    def _init_hardware(self):
        for ch in range(self.n_ch):
            self._w(0x08, ch)
        self._w(0x0F, 0x00) # 关闭硬件 Noise

    def load_bank(self, voices: list[OpmVoice]) -> None:
        self.voices = list(voices)

    def _load_voice(self, ch: int, v: OpmVoice) -> None:
        lfo = list(v.lfo) + [0] * (5 - len(v.lfo))
        self._w(0x18, lfo[0] & 0xFF)
        self._w(0x19, 0x80 | (lfo[2] & 0x7F)) # PMD
        self._w(0x19, lfo[1] & 0x7F)          # AMD
        self._w(0x1B, (lfo[3] & 0x03) | ((lfo[4] & 0x1F) << 3))

        pan, fl, con, ams, pms = v.ch[0], v.ch[1], v.ch[2], v.ch[3], v.ch[4]
        self._w(0x20 + ch, _pan_bits(pan) | ((fl & 7) << 3) | (con & 7))
        self._w(0x38 + ch, ((pms & 7) << 4) | (ams & 3))

        for i, op in enumerate(v.ops):
            base = VOPM_OP_REG[i] * 8 + ch
            self._w(0x40 + base, ((op["dt1"] & 7) << 4) | (op["mul"] & 0x0F))
            self._w(0x60 + base, op["tl"] & 0x7F)
            self._w(0x80 + base, ((op["ks"] & 3) << 6) | (op["ar"] & 0x1F))
            self._w(0xA0 + base, ((op.get("ame", 0) & 1) << 7) | (op["dr"] & 0x1F))
            self._w(0xC0 + base, ((op["dt2"] & 3) << 6) | (op["sr"] & 0x1F))
            self._w(0xE0 + base, ((op["sl"] & 0x0F) << 4) | (op["rr"] & 0x0F))

    def _update_tl(self, ch: int, v: OpmVoice, velocity: int) -> None:
        midi_ch = self.slots[ch].midi_ch
        con = v.ch[2] & 7
        carriers = CARRIER_MASK.get(con, (0, 0, 0, 1))

        # 1. 计算载波（Carrier）的音量衰减：受力度、CC7、CC11 影响
        vel = max(0, min(127, velocity))
        vol = self.ch_vol[midi_ch]
        expr = self.ch_expr[midi_ch]

        total_db = 0.0
        if vel == 0:
            total_db += 96.0
        else:
            total_db += -20.0 * math.log10(vel / 127.0)
        if vol == 0 or expr == 0:
            total_db += 96.0
        else:
            total_db += -20.0 * math.log10((vol * expr) / (127.0 * 127.0))

        atten_carrier = int(round(total_db / TL_DB_PER_STEP))
        atten_carrier = max(0, min(127, atten_carrier))

        # 2. 计算调制器（Modulator）的音量衰减：受 CC74 亮度影响
        # CC74 越小（变暗），调制器被压得越小声，高频谐波越少
        bright = self.ch_brightness[midi_ch]  # 0~64
        # 最大衰减量设为 48（约 36dB），避免完全变成纯正弦波
        atten_mod = int((64 - bright) * 0.75) 

        for i, op in enumerate(v.ops):
            tl = op["tl"] & 0x7F
            if carriers[i]:
                tl = min(127, tl + atten_carrier)
            else:
                tl = min(127, tl + atten_mod)
            self._w(0x60 + VOPM_OP_REG[i] * 8 + ch, tl)

    def _set_pitch(self, ch: int, pitch: float) -> None:
        base = int(math.floor(pitch))
        frac = pitch - base
        note = max(0, min(127, base))

        octave = (note // 12) - 1
        octave = max(0, min(7, octave)) 
        key = KTBL[note % 12]
        kc = (octave << 4) | key
        
        kf = int(round(frac * 64)) & 0x3F
        self._w(0x28 + ch, kc & 0x7F)
        self._w(0x30 + ch, kf << 2)

    def _pitch_with_bend(self, midi_ch: int, note: int) -> float:
        bend = (self.bend14[midi_ch & 0x0F] - 8192) / 8192.0
        return note + bend * self.bend_range

    def _find(self, midi_ch: int, note: int) -> int:
        for i, s in enumerate(self.slots):
            if s.active and s.midi_ch == midi_ch and s.note == note:
                return i
        return -1

    def _allocate(self, midi_ch: int, note: int) -> int:
        # 1. 优先找同 MIDI 通道、空闲的槽
        for i, s in enumerate(self.slots):
            if not s.active and not s.pending_off and s.midi_ch == midi_ch:
                return i

        # 2. 找任何完全空闲的槽
        found = -1
        for i, s in enumerate(self.slots):
            if not s.active and not s.pending_off:
                found = i
                break
                
        if found < 0:
            # 3. 找其他通道完全空闲的槽
            for i, s in enumerate(self.slots):
                if not s.active and not s.pending_off and s.midi_ch != midi_ch:
                    found = i
                    break

        # 4. 所有槽都满了，开始 NECOPN 大逃杀
        if found < 0:
            best_midi = -1
            best_serial = 2**31
            for i, s in enumerate(self.slots):
                # 找 MIDI 通道号最大的（数值越大，优先级越低）
                if s.midi_ch > best_midi:
                    best_midi = s.midi_ch
                    found = i
                    best_serial = s.serial
                elif s.midi_ch == best_midi and s.serial < best_serial:
                    # 通道号相同，找最早按下的（serial 最小）
                    found = i
                    best_serial = s.serial
                    
            if found < 0:
                return -1
                
            # NECOPN 绝杀：如果被杀的槽的通道号（优先级）比当前请求的还要小，
            # 说明当前请求是最低优先级的，直接拒绝发声！
            if self.slots[found].midi_ch < midi_ch:
                return -1

        # 如果抢占的是正在发声的通道，必须先发 Key-Off 截断它
        s = self.slots[found]
        if s.active:
            self._w(0x08, found) 
            s.active = False
            
        return found

    def _real_note_off(self, ch: int) -> None:
        self._w(0x08, ch)
        s = self.slots[ch]
        s.active = False
        s.released = True
        s.pending_off = False
        s.release_time = self.time

    def note_on(self, midi_ch: int, note: int, velocity: int) -> None:
        midi_ch &= 0x0F
        if midi_ch == 9:
            return
        if velocity == 0:
            return self.note_off(midi_ch, note)
        if self._find(midi_ch, note) >= 0:
            return

        ch = self._allocate(midi_ch, note)
        if ch < 0:
            return
            
        prog = self.programs[midi_ch] % max(1, len(self.voices))
        v = self.voices[prog]

        if self.loaded_program[ch] != prog:
            self._load_voice(ch, v)
            self.loaded_program[ch] = prog

        s = self.slots[ch]
        s.midi_ch, s.note, s.program, s.velocity = midi_ch, note, prog, velocity
        s.active, s.released, s.pending_off = True, False, False
        s.start_time = self.time
        self.serial += 1
        s.serial = self.serial

        self._update_tl(ch, v, velocity)
        self._set_pitch(ch, self._pitch_with_bend(midi_ch, note))

        # key-on
        self._w(0x08, 0x78 | ch)

    def note_off(self, midi_ch: int, note: int) -> None:
        midi_ch &= 0x0F
        if midi_ch == 9:
            return
        ch = self._find(midi_ch, note)
        if ch < 0:
            return
        if self.sustain[midi_ch]:
            self.slots[ch].pending_off = True
        else:
            self._real_note_off(ch)

    def program_change(self, midi_ch: int, prog: int) -> None:
        self.programs[midi_ch & 0x0F] = prog & 0x7F

    def pitch_bend(self, midi_ch: int, lsb: int, msb: int) -> None:
        midi_ch &= 0x0F
        self.bend14[midi_ch] = ((msb & 0x7F) << 7) | (lsb & 0x7F)
        for i, s in enumerate(self.slots):
            if s.active and s.midi_ch == midi_ch:
                self._set_pitch(i, self._pitch_with_bend(midi_ch, s.note))

    def control_change(self, midi_ch: int, cc: int, value: int) -> None:
        midi_ch &= 0x0F
        
        # --- 音量与表情 ---
        if cc == 0x07:
            self.ch_vol[midi_ch] = value
            self._refresh_channel_tl(midi_ch)
        elif cc == 0x0B:
            self.ch_expr[midi_ch] = value
            self._refresh_channel_tl(midi_ch)
            
        # --- CC74 亮度控制 (XG standard) ---
        elif cc == 0x4A:
            # CC74 范围 0~127，但 XG 规范里通常只用到 0~64，64 以上视为全亮
            self.ch_brightness[midi_ch] = min(64, value)
            self._refresh_channel_tl(midi_ch)
            
        # --- 踏板与复位 ---
        elif cc == 0x40:
            if value >= 64:
                self.sustain[midi_ch] = True
            else:
                self.sustain[midi_ch] = False
                for i, s in enumerate(self.slots):
                    if s.midi_ch == midi_ch and s.pending_off:
                        self._real_note_off(i)
        elif cc == 0x78:
            for i, s in enumerate(self.slots):
                if s.active and s.midi_ch == midi_ch:
                    self._w(0x08, i)
                    s.active = s.pending_off = False
                    s.released = True
                    s.release_time = self.time
        elif cc == 0x79:
            self.bend14[midi_ch] = 8192
            self.ch_vol[midi_ch] = 127
            self.ch_expr[midi_ch] = 127
            self.ch_brightness[midi_ch] = 64
            self.sustain[midi_ch] = False
            for i, s in enumerate(self.slots):
                if s.midi_ch == midi_ch and s.pending_off:
                    self._real_note_off(i)
            self._refresh_channel_tl(midi_ch)
        elif cc == 0x7B:
            for i, s in enumerate(self.slots):
                if s.active and s.midi_ch == midi_ch:
                    self._real_note_off(i)

    def _refresh_channel_tl(self, midi_ch: int) -> None:
        for i, s in enumerate(self.slots):
            if s.active and s.midi_ch == midi_ch:
                v = self.voices[s.program % max(1, len(self.voices))]
                self._update_tl(i, v, s.velocity)

    def advance_time(self, seconds: float) -> None:
        self.time += seconds