# translator.py
import math

def midi_to_opm_pitch(pitch, clock=3579545, base_freq=440.0):
    """
    支持浮点数的 OPM 音高翻译。
    pitch 可以是 60.5，代表 C4 往上升半个半音。
    """
    # 限制范围，防止溢出
    pitch = max(0.0, min(127.99, pitch))
    
    # 计算标准频率
    pitch_freq = base_freq * (2.0 ** ((pitch - 69) / 12.0))
    
    # 计算 OPM 对应的绝对浮点值
    # (3584 是 8 个八度的基准偏移量，64 是一个八度内的刻度数，12 是半音数)
    kf_float = 3584 + 64 * 12 * math.log2(pitch_freq * clock / 3579545.0 / base_freq)
    
    # 为了防止浮点误差导致半音跳动，加上极小偏移并四舍五入
    kf_float += 0.000001
    
    # 计算八度
    octave = int(kf_float // (64 * 12))
    octave = max(0, min(7, octave))
    
    # 计算当前八度内的相对值
    remainder = kf_float - (octave * 64 * 12)
    
    # 计算音名索引 (0 代表 C#)
    key_index = int(remainder // 64)
    opm_notes = [0, 1, 2, 4, 5, 6, 8, 9, 10, 12, 13, 14]
    kc_low = opm_notes[key_index]
    
    # 计算微调 (KF寄存器)
    # 保留 remainder 的小数部分，映射到 0~63 的整数
    kf_rem = remainder % 64
    kf_val = int(round(kf_rem)) & 0x3F
    
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