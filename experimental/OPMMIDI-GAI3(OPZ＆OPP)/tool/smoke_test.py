# smoke_test.py
import ctypes, struct, wave
from core import OpmCore, note_to_kc

core = OpmCore()
print("handle:", core._h)
print("has opm_generate:", hasattr(core._dll, "opm_generate"))
print("status:", core.read_status())

def _advance(n=1):
    buf = (ctypes.c_int16 * (2 * n))()
    core._dll.opm_generate(core._h, buf, n)

def w(reg, val):
    core.write(reg, val)   # 内部已经处理 2 + 34 clock                                 # 数据锁存

# 全通道 key off
for ch in range(8):
    w(0x08, ch)

ch = 0
w(0x20 + ch, 0xC7)   # RL=11, FB=0, CON=7（全并联，最不容易出错）

# op 偏移: M1=0, C1=2, M2=4, C2=6
# CON=7 时四个 operator 都是载波，全部 TL=0 一起发声
for op_off in (0, 2, 4, 6):
    base = ch * 8 + op_off
    w(0x40 + base, 0x01)   # DT1=0, MUL=1
    w(0x60 + base, 0x00)   # TL=0（最大音量）
    w(0x80 + base, 0x1F)   # KS=0, AR=31
    w(0xA0 + base, 0x00)   # AMS-EN=0, D1R=0
    w(0xC0 + base, 0x00)   # DT2=0, D2R=0
    w(0xE0 + base, 0x0F)   # D1L=0（不衰减）, RR=15

w(0x28 + ch, note_to_kc(69))   # KC: A4
w(0x30 + ch, 0x00)              # KF
w(0x38 + ch, 0x00)              # PMS/AMS=0

w(0x08, 0x78 | ch)              # key on

sr = core.sample_rate()
pcm = core.generate(int(sr * 1.0))

w(0x08, ch)                     # key off
pcm += core.generate(int(sr * 0.3))

peak = max(abs(v) for v in struct.unpack('<%dh' % (len(pcm)//2), pcm))
print(f"sr={sr}  frames={len(pcm)//4}  peak={peak}")

with wave.open("smoke.wav", "wb") as f:
    f.setnchannels(2); f.setsampwidth(2); f.setframerate(sr)
    f.writeframes(pcm)

core.close()
print("-> smoke.wav")