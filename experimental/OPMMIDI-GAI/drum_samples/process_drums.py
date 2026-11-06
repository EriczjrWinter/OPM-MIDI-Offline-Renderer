# drum_samples/process_drums.py
import os
import subprocess
import sys

def process_all_wavs():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    lofi_dir = os.path.join(current_dir, "lofi")
    
    # 创建输出文件夹
    if not os.path.exists(lofi_dir):
        os.makedirs(lofi_dir)
        
    wav_files = [f for f in os.listdir(current_dir) if f.lower().endswith(".wav")]
    
    if not wav_files:
        print("当前文件夹里没有找到 WAV 文件！请先把你下载的 Korg 鼓声放进来。")
        return

    print(f"找到 {len(wav_files)} 个文件，开始进行降维（22kHz + 8-bit 颗粒感）处理...")
    
    for wav in wav_files:
        input_path = os.path.join(current_dir, wav)
        output_path = os.path.join(lofi_dir, wav)
        
        # 调用 FFmpeg：降采样到 22050，砍掉 4.5kHz 以上的高频，加上 8-bit 颗粒感
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-ar", "22050",
            "-af", "lowpass=f=4500, acrusher=bits=8:mode=log:aa=1",
            "-c:a", "pcm_s16le",
            output_path
        ]
        
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            print(f"  [OK] {wav}")
        except FileNotFoundError:
            print("❌ 错误: 系统中未找到 ffmpeg，请先安装并配置环境变量。")
            sys.exit(1)
        except subprocess.CalledProcessError:
            print(f"  [失败] {wav}")

    print("\n全部处理完成！你可以去 'lofi' 文件夹里看看生成的文件。")

if __name__ == "__main__":
    process_all_wavs()