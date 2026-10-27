# pcm_core.py (完整版)
import os
import wave
import array

class PcmVoice:
    __slots__ = ('data', 'pos', 'step', 'volume', 'done')
    def __init__(self, data, step, volume):
        self.data = data
        self.pos = 0.0
        self.step = step
        self.volume = volume
        self.done = False

class PcmCore:
    def __init__(self, sample_rate=55930):
        self.sr = sample_rate
        self.samples = {}
        self.active_voices = []
        self.tune = 1.0
        self.gain = 2.0  # 【新增】：全局音量增益，2.0 等于翻倍

    def load_sample(self, name: str, path: str):
        """加载 RHY 采样，并预重采样到 OPM 的目标采样率"""
        if not os.path.exists(path):
            print(f"[PcmCore] 找不到采样: {path}")
            return
            
        with wave.open(path, 'rb') as w:
            n_frames = w.getnframes()
            w_sr = w.getframerate()
            n_ch = w.getnchannels()
            raw = w.readframes(n_frames)
            
            data = array.array('h')
            data.frombytes(raw)
            
            # 如果是立体声，降混为单声道
            if n_ch == 2:
                mono = array.array('h')
                for i in range(0, len(data), 2):
                    mono.append((data[i] + data[i+1]) // 2)
                data = mono
                
            # 线性重采样 (例如 44100Hz -> 55930Hz)
            step = w_sr / self.sr
            if step != 1.0:
                new_len = int(len(data) / step)
                resampled = array.array('h')
                for i in range(new_len):
                    pos = i * step
                    p1, p2 = int(pos), int(pos) + 1
                    if p2 >= len(data): p2 = len(data) - 1
                    frac = pos - p1
                    val = int(data[p1] * (1 - frac) + data[p2] * frac)
                    resampled.append(val)
                data = resampled
                
            self.samples[name] = data
            print(f"[PcmCore] 已加载采样: {name} ({len(data)} frames)")

    def play_drum(self, name: str, velocity: int):
        if name not in self.samples: return
        smp = self.samples[name]
        # 【修改】：乘上全局增益，并且把力度曲线改得稍微平缓一点
        vol = ((velocity / 127.0) ** 1.0) * self.gain 
        voice = PcmVoice(smp['data'], 1.0, vol)
        self.active_voices.append(voice)

    def play(self, name: str, velocity: int):
        """触发指定名称的鼓声"""
        if name not in self.samples:
            return
            
        vol = (velocity / 127.0) ** 1.5
        voice = PcmVoice(self.samples[name], 1.0, vol)
        self.active_voices.append(voice)

    def generate(self, nframes: int) -> array.array:
        out = array.array('i', [0] * nframes)
        alive_voices = []
        
        for v in self.active_voices:
            if v.done: continue
            for i in range(nframes):
                p1 = int(v.pos)
                if p1 >= len(v.data) - 1:
                    v.done = True
                    break
                p2 = p1 + 1
                frac = v.pos - p1
                val = int(v.data[p1] * (1 - frac) + v.data[p2] * frac)
                out[i] += int(val * v.volume)
                v.pos += v.step
            if not v.done:
                alive_voices.append(v)
                
        self.active_voices = alive_voices
        
        final_out = array.array('h')
        for val in out:
            final_out.append(max(-32768, min(32767, val)))
            
        return final_out