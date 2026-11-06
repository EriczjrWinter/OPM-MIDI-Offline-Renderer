import sys
import re

def extract_kc(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    print("=== 提取所有 Key Code (KC) 和 Key On ===")
    print("提示：如果你按顺序敲了底鼓、军鼓、踩镲，看看下面的 KC 是不是在变。\n")

    current_kc = {}
    event_count = 0

    for line in lines:
        # 提取 Key Code
        m_kc = re.search(r'Ch (\d+) Key Code: 0x([0-9A-Fa-f]+) = (\S+)', line)
        if m_kc:
            ch = int(m_kc.group(1))
            kc_val = int(m_kc.group(2), 16)
            note_name = m_kc.group(3)
            current_kc[ch] = (kc_val, note_name)

        # 提取 Key On
        if "Key On" in line:
            event_count += 1
            # 找到是哪个通道触发的
            m_ch = re.search(r'Ch (\d+)', line)
            if m_ch:
                ch = int(m_ch.group(1))
                if ch in current_kc:
                    kc_val, note_name = current_kc[ch]
                    print(f"第 {event_count:2d} 次发声 -> 通道 {ch} | KC 值: 0x{kc_val:02X} ({kc_val:3d}) | 音高: {note_name}")
                else:
                    print(f"第 {event_count:2d} 次发声 -> 通道 {ch} | 未捕获到 KC (可能未更新)")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python dump_kc.py <vgm2txt的输出.txt>")
    else:
        extract_kc(sys.argv[1])