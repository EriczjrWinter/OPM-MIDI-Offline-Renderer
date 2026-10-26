# driver.py
from __future__ import annotations
import math
from dataclasses import dataclass
from core import ChipCore
from voice import OpmVoice

# 文件行顺序 M1,C1,M2,C2 → 物理 slot 0,2,1,3
VOPM_OP_REG = [0, 2, 1, 3]

# 正确的 OPM 硬件音阶表
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

# 硬编码的 FM 硬件鼓音色 (GM 映射)
# 格式: (KC, FL_CON, MUL_DT1, TL, AR_KS, DR, SR_DT2, SL_RR, 是否开启噪声, 噪声频率)
FM_DRUMS = {
    # 35/36 底鼓 (Kick): 不需要噪声，纯 M1 低频发威
    # M1_TL=0 (最响), C2_TL=127 (静音), FL_CON=0x3F (算法7,反馈满), M1_MUL=0 (0.5倍频产生极低频)
    35: (0x00, 0x7F, 0x3F, 0x00, 0x1F, 0x14, 0x00, 0x0F, False, 0),
    36: (0x00, 0x7F, 0x3F, 0x00, 0x1F, 0x14, 0x00, 0x0F, False, 0),

    # 38/40 军鼓 (Snare): M1 提供军鼓的“腔体震动”，C2 提供响弦的“沙沙声”
    # M1_TL=8, C2_TL=12 (两者混合), M1_MUL=5 (增加音调金属感), C2 开启噪声
    38: (0x08, 0x0C, 0x07, 0x05, 0x1F, 0x14, 0x10, 0x1F, True, 0x18),
    40: (0x08, 0x0C, 0x07, 0x05, 0x1F, 0x14, 0x10, 0x1F, True, 0x18),

    # 42/46 踩镲 (Hi-Hat): 几乎纯噪声，极快衰减
    # M1_TL=127 (静音), C2_TL=0 (最响), C2_DR=0x1F (极速衰减)
    42: (0x7F, 0x00, 0x07, 0x01, 0x1F, 0x00, 0x1F, 0x0F, True, 0x1F),
    46: (0x7F, 0x00, 0x07, 0x01, 0x1F, 0x00, 0x1F, 0x0F, True, 0x1F),

    # 49/51 吊镲 (Cymbal): 纯噪声，但需要更长一点的衰减余音
    # C2_DR=0x12 (稍慢衰减), SL_RR=0x1F (释放也快)
    49: (0x7F, 0x00, 0x07, 0x01, 0x1F, 0x00, 0x12, 0x1F, True, 0x1C),
    51: (0x7F, 0x00, 0x07, 0x01, 0x1F, 0x00, 0x12, 0x1F, True, 0x1C),
}



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
        self.ch_brightness = [64] * 16 
        
        # 专属鼓通道（物理通道 7）
        self.drum_ch = self.n_ch - 1
        
        self.serial = 0
        self.time = 0.0
        self.vgm_log = []      # 新增：记录 VGM 日志
        self.trace_vgm = False # 新增：录制开关
        self._init_hardware()

    def _w(self, reg: int, val: int) -> None:
        self.core.write(reg, val)
        
        if self.trace_vgm:
            # 【关键修改】：给 VGM 导出的 TL（音量）寄存器加一个安全偏置
            out_val = val & 0xFF
            if 0x60 <= (reg & 0xFF) <= 0x7F:
                # 强制增加 8（相当于衰减 6dB），防止 VGM 播放器爆音
                out_val = min(127, out_val + 8)
            self.vgm_log.append((self.time, reg & 0xFF, out_val))

    def _init_hardware(self):
        for ch in range(self.n_ch):
            self._w(0x08, ch)
        self._w(0x0F, 0x00) # 关闭 Noise

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

        bright = self.ch_brightness[midi_ch] 
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
        # 严格限制普通音符只能在 0 ~ 6 通道发声
        max_slots = self.drum_ch

        for i in range(max_slots):
            s = self.slots[i]
            if not s.active and not s.pending_off and s.midi_ch == midi_ch:
                return i

        found = -1
        for i in range(max_slots):
            s = self.slots[i]
            if not s.active and not s.pending_off:
                found = i
                break
                
        if found < 0:
            for i in range(max_slots):
                s = self.slots[i]
                if not s.active and not s.pending_off and s.midi_ch != midi_ch:
                    found = i
                    break

        if found < 0:
            best_midi = -1
            best_serial = 2**31
            for i in range(max_slots):
                s = self.slots[i]
                if s.midi_ch > best_midi:
                    best_midi = s.midi_ch
                    found = i
                    best_serial = s.serial
                elif s.midi_ch == best_midi and s.serial < best_serial:
                    found = i
                    best_serial = s.serial
                    
            if found < 0:
                return -1
            if self.slots[found].midi_ch < midi_ch:
                return -1

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

    def _play_drum(self, note: int, velocity: int) -> None:
        """完全利用噪声与 FM 混合的打击乐发声逻辑"""
        if note not in FM_DRUMS:
            return
            
        ch = self.drum_ch
        (m1_tl, c2_tl, fl_con, m1_mul, ar, m1_dr, c2_dr, sl_rr, use_noise, noise_freq) = FM_DRUMS[note]
        
        # 力度映射：力度越小，TL 越大（越安静）
        vel_atten = (127 - velocity) >> 1
        
        # 最终音量 = 基础音量 + 力度衰减
        final_m1_tl = min(127, m1_tl + vel_atten)
        final_c2_tl = min(127, c2_tl + vel_atten)
        
        # 1. 设置全局噪声参数
        if use_noise:
            self._w(0x0F, 0x80 | (noise_freq & 0x1F))
        else:
            self._w(0x0F, 0x00)
            
        # 2. 停止通道 7 当前声音
        self._w(0x08, ch)
        
        # 3. 写入通道基本参数 (算法与反馈)
        self._w(0x20 + ch, fl_con)
        
        # 4. 为 4 个算子分配参数
        for i in range(4):
            base = VOPM_OP_REG[i] * 8 + ch
            
            # 我们只用 M1 (i=0) 和 C2 (i=3)，其他两个算子强制静音
            if i == 0:
                tl = final_m1_tl
                mul = m1_mul
                dr = m1_dr
            elif i == 3:
                tl = final_c2_tl
                mul = 0x01 # C2 倍频对噪声无效，随便给个 1
                dr = c2_dr
            else:
                tl = 0x7F # C1, M2 强制静音
                mul = 0x01
                dr = 0x00
                
            self._w(0x40 + base, mul)
            self._w(0x60 + base, tl & 0x7F)
            self._w(0x80 + base, ar)        # 起音极快
            self._w(0xA0 + base, dr)        # 各自的衰减率
            self._w(0xC0 + base, 0x00)      # D2R 设为 0
            self._w(0xE0 + base, sl_rr)     # 维持与释放
            
        # 5. 设置音高 (KC) 并触发 Key-On
        # 对于底鼓，KC 越低越好。对于军鼓，KC 决定了“哒”的音高。
        kc = 0x10 if note in (35, 36) else 0x20 # 这里可以细化音高映射
        self._w(0x28 + ch, kc)
        self._w(0x30 + ch, 0x00)
        
        # 【核心】同时唤醒 M1 (物理 slot 0) 和 C2 (物理 slot 3)
        # 所以 mask 是 0x08 | 0x01 = 0x09
        self._w(0x08, 0x09 | ch) 
        
        s = self.slots[ch]
        s.midi_ch, s.note, s.velocity = 9, note, velocity
        s.active, s.released, s.pending_off = True, False, False
        s.start_time = self.time

    def note_on(self, midi_ch: int, note: int, velocity: int) -> None:
        midi_ch &= 0x0F
        
        # 拦截 MIDI 通道 10 的鼓点
        if midi_ch == 9:
            if velocity > 0:
                self._play_drum(note, velocity)
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

        self._w(0x08, 0x78 | ch)

    def note_off(self, midi_ch: int, note: int) -> None:
        midi_ch &= 0x0F
        
        # 鼓通常不需要 Note Off（硬件自身极速衰减），直接忽略通道 10 的 Note Off
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
        if midi_ch == 9:
            return
        self.bend14[midi_ch] = ((msb & 0x7F) << 7) | (lsb & 0x7F)
        for i, s in enumerate(self.slots):
            if s.active and s.midi_ch == midi_ch and i != self.drum_ch:
                self._set_pitch(i, self._pitch_with_bend(midi_ch, s.note))

    def control_change(self, midi_ch: int, cc: int, value: int) -> None:
        midi_ch &= 0x0F
        if midi_ch == 9:
            return
        
        if cc == 0x07:
            self.ch_vol[midi_ch] = value
            self._refresh_channel_tl(midi_ch)
        elif cc == 0x0B:
            self.ch_expr[midi_ch] = value
            self._refresh_channel_tl(midi_ch)
        elif cc == 0x4A:
            self.ch_brightness[midi_ch] = min(64, value)
            self._refresh_channel_tl(midi_ch)
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
            if s.active and s.midi_ch == midi_ch and i != self.drum_ch:
                v = self.voices[s.program % max(1, len(self.voices))]
                self._update_tl(i, v, s.velocity)

    def advance_time(self, seconds: float) -> None:
        self.time += seconds