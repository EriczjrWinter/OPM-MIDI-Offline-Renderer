# translator.py
import math

def midi_to_opm_pitch(pitch, clock=3579545, base_freq=440.0):
    """
    极简、极速、防越界的 OPM 音高翻译。
    pitch: 可以是浮点数（比如 60.5 代表弯音）。
    """
    # 1. 限制输入 MIDI 范围，防止底层 CPU 算爆
    pitch = max(0.0, min(127.99, pitch))
    
    # 2. 直接使用线性映射公式（完美支持小数弯音，且没有 math.log2 的浮点误差）
    # 64 是一个半音的刻度数，3584 是 MIDI 69 (A4) 对应的基准值
    kf_float = 64.0 * (pitch - 69.0) + 3584.0
    
    # 3. 计算八度
    octave = int(kf_float // (64 * 12))
    
    # 【核心保护】：强行截断到 0~7 八度，防止越界
    if octave < 0:
        octave = 0
        kf_float = 0.0 
    elif octave > 7:
        octave = 7
        # 截断到八度 7 的最高音（B音，音名索引 11，微调 63）
        kf_float = (7 * 64 * 12) + (11 * 64) + 63.0
        
    # 4. 计算当前八度内的余数
    remainder = kf_float - (octave * 64 * 12)
    
    # 计算音名索引 (0~11)
    key_index = int(remainder // 64)
    
    # 【双重保护】：防止浮点意外
    key_index = max(0, min(11, key_index))
    
    # OPM 的 KC 映射表
    opm_notes = [0, 1, 2, 4, 5, 6, 8, 9, 10, 12, 13, 14]
    kc_low = opm_notes[key_index]
    
    # 5. 计算微调 (KF)
    kf_val = min(63, int(round(remainder % 64)))
    
    kc_val = (octave << 4) | kc_low
    
    return kc_val & 0x7F, (kf_val << 2)

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