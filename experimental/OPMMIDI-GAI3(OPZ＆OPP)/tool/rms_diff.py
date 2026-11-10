# -*- coding: utf-8 -*-
"""逐秒 RMS 对比两个 WAV，找出差异 > 阈值的秒数。
用法: py rms_diff.py real.wav py.wav [--thresh 0.3]
real.wav: NP2 里原驱动录的
py.wav:   Python 渲染的
"""
import argparse
import wave
import struct
import math

def read_mono(path):
    with wave.open(path, "rb") as w:
        sr = w.getframerate()
        n = w.getnframes()
        ch = w.getnchannels()
        data = w.readframes(n)
    s = struct.unpack("<%dh" % (len(data) // 2), data)
    if ch == 2:
        s = [(s[i] + s[i+1]) // 2 for i in range(0, len(s), 2)]
    return sr, s

def rms(seg):
    if not seg: return 0.0
    return math.sqrt(sum(x*x for x in seg) / len(seg))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("real")
    ap.add_argument("pywav")
    ap.add_argument("--thresh", type=float, default=0.3)
    args = ap.parse_args()

    sr_a, a = read_mono(args.real)
    sr_b, b = read_mono(args.pywav)
    print(f"real: {sr_a}Hz {len(a)} samples; py: {sr_b}Hz {len(b)} samples")
    if sr_a != sr_b:
        print("采样率不同，无法直接比较")
        return
    n = min(len(a), len(b))
    secs = n // sr_a
    print(f"{'time':>6} {'real RMS':>10} {'py RMS':>10} {'diff':>8}   {'sig':>3}")
    for t in range(secs):
        ra = rms(a[t*sr_a:(t+1)*sr_a])
        rb = rms(b[t*sr_a:(t+1)*sr_a])
        denom = max(ra, rb, 1)
        diff = abs(ra - rb) / denom
        sig = "**" if diff > args.thresh else ""
        print(f"{t:6d} {ra:10.0f} {rb:10.0f} {diff:7.1%}   {sig:>3}")

if __name__ == "__main__":
    main()