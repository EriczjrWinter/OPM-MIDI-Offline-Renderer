# translator.py
import math

def midi_to_opm_pitch(note, clock=3579545, base_freq=440.0):
    """音高翻译：将 MIDI 音符精确转换为 OPM 的 KC/KF（解决物理偏移）"""
    pitch_freq = base_freq * (2.0 ** ((note - 69) / 12.0))
    # 根据 OPM 的时钟频率和分频计算
    kf_float = 3584 + 64 * 12 * math.log2(pitch_freq * clock / 3579545.0 / base_freq)
    
    octave = int(kf_float / 64 / 12)
    k = int(kf_float / 64) % 12
    opm_notes = [0, 1, 2, 4, 5, 6, 8, 9, 10, 12, 13, 14]
    
    octave = max(0, min(7, octave)) # 限制在 0-7 八度
    kc_val = (octave << 4) | opm_notes[k]
    kf_val = int(kf_float % 64) << 2
    return kc_val & 0x7F, kf_val & 0xFF

def translate_opn_envelope_to_opm(dr, sr, rr):
    """包络翻译：修正 OPN 包络在 OPM 上过快的衰减，防止塑料放屁音"""
    # OPN 的 31 在 OPM 上会瞬间掉底，我们乘以 0.7 作为经验缩放
    safe_dr = int(dr * 0.7) if dr > 0 else 0
    safe_sr = int(sr * 0.7) if sr > 0 else 0
    safe_rr = int(rr * 0.8) if rr > 0 else 0
    
    # 设定 OPM 的安全上限，防止出现高频爆音
    return min(safe_dr, 22), min(safe_sr, 22), min(safe_rr, 14)

def translate_fb(fb):
    """反馈翻译：OPN 的高反馈在 OPM 上会引发严重的波形畸变"""
    return min(fb, 5) # 强行限制最大反馈，防止崩溃