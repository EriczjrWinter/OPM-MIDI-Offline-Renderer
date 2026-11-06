import re
import sys

def parse_txt(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # 寻找 Ch 0（mid2vgm 通常把鼓放在 CH0 或 CH7，请根据你的 txt 替换）
    target_ch = "Ch 7"  # 如果是 Ch 0，就改成 "Ch 0"
    
    ops = {0: {}, 1: {}, 2: {}, 3: {}}
    alg = 0
    fb = 0

    for line in lines:
        if target_ch not in line:
            continue
            
        # 提取 算法和反馈
        if "Stereo:" in line and "Connection:" in line:
            m_conn = re.search(r'Connection:\s*(\d+)', line)
            m_fb = re.search(r'Feedback:\s*(\d+)', line)
            if m_conn: alg = int(m_conn.group(1))
            if m_fb: fb = int(m_fb.group(1))

        # 提取算子参数
        for op_idx in range(4):
            # 匹配例如 "Ch 7 Op 0 Detune 1: X, Multiply: Y"
            if f"Op {op_idx}" in line:
                # DT1 / MUL
                m_dt1 = re.search(r'Detune 1:\s*(\d+)', line)
                m_mul = re.search(r'Multiply:\s*(\d+)', line)
                if m_dt1: ops[op_idx]['dt1'] = int(m_dt1.group(1))
                if m_mul: ops[op_idx]['mul'] = int(m_mul.group(1))
                
                # TL
                m_tl = re.search(r'Total Level:\s*0x([0-9A-Fa-f]+)', line)
                if m_tl: ops[op_idx]['tl'] = int(m_tl.group(1), 16)
                
                # KS / AR
                m_ks = re.search(r'Key Scale:\s*0x([0-9A-Fa-f]+)', line)
                m_ar = re.search(r'Attack Rate:\s*0x([0-9A-Fa-f]+)', line)
                if m_ks: ops[op_idx]['ks'] = int(m_ks.group(1), 16)
                if m_ar: ops[op_idx]['ar'] = int(m_ar.group(1), 16)

                # DR
                m_dr = re.search(r'Decay Rate 1:\s*0x([0-9A-Fa-f]+)', line)
                if m_dr: ops[op_idx]['dr'] = int(m_dr.group(1), 16)

                # SR / DT2
                m_sr = re.search(r'Decay Rate 2:\s*0x([0-9A-Fa-f]+)', line)
                m_dt2 = re.search(r'Detune 2:\s*(\d+)', line)
                if m_sr: ops[op_idx]['sr'] = int(m_sr.group(1), 16)
                if m_dt2: ops[op_idx]['dt2'] = int(m_dt2.group(1))

                # SL / RR
                m_sl = re.search(r'D1L:\s*0x([0-9A-Fa-f]+)', line)
                m_rr = re.search(r'Release Rate:\s*0x([0-9A-Fa-f]+)', line)
                if m_sl: ops[op_idx]['sl'] = int(m_sl.group(1), 16)
                if m_rr: ops[op_idx]['rr'] = int(m_rr.group(1), 16)

    # 打印成可以直接抄的 Python 代码
    print("\n" + "="*40)
    print(f" 提取结果 (Ch: {target_ch.split()[1]})")
    print("="*40)
    print(f"'alg': {alg}, 'fb': {fb},")
    print("'operators': [")
    for i in range(4):
        op = ops[i]
        # 防报错，给个默认值
        print(f"    {{'dt1': {op.get('dt1', 0)}, 'mul': {op.get('mul', 1)}, 'tl': {op.get('tl', 0)}, "
              f"'ks': {op.get('ks', 0)}, 'ar': {op.get('ar', 31)}, 'dr': {op.get('dr', 0)}, "
              f"'sr': {op.get('sr', 0)}, 'sl': {op.get('sl', 0)}, 'rr': {op.get('rr', 0)}}},")
    print("]")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python parse_vgm_txt.py <vgm2txt的输出.txt>")
    else:
        parse_txt(sys.argv[1])