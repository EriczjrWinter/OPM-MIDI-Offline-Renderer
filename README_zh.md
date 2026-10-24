OPM MIDI 离线渲染合成器

项目简介
这是一个基于 Nuked OPM（逐周期精确仿真的 YM2151 芯片核心）构建的轻量级、高性能 MIDI 离线渲染合成器。

本项目致敬并复现了经典 PC-98 平台 NECOPN.DRV 驱动的“动态丢音”（Voice Stealing / 大逃杀）机制。由于 YM2151 硬件只有 8 个物理通道，当 MIDI 音轨数超过硬件限制时，系统会执行优先级抢占策略——优先保障主旋律，无情切断老旧或低优先级的音符，完美还原 90 年代 FM 街机音源的复古听感。

核心特性
硬件级精确渲染：底层调用 C 语言的 Nuked OPM 核心，实现精确到 64 clock 的芯片级仿真。

动态丢音机制：完美复刻 NECOPN 的通道分配逻辑，在 8 通道满载时执行残酷的“大逃杀”抢音。

极致性能优化：音频增益采用纯整数位运算（v >> 1），摒弃浮点运算与软削波，渲染速度极快且彻底杜绝爆音。

CC74 亮度辅助：参考 Wohlstand (libOPNMIDI) 的实现思路，支持 CC74 (Brightness) 控制器，通过动态调整 FM 调制器（Modulator）的电平，模拟出低通滤波器的明暗变化。

专属音色库：内置由 NECOPN.DRV 动态快照提取生成的 .opm 预设。

环境依赖
Python 3.8+

Nuked OPM 核心 (opm.dll / opm.so)：请确保编译好的 C 语言动态链接库文件存在于项目根目录。注意：Nuked OPM 是逐周期仿真，对单核 CPU 性能有一定要求，但 Python 端的封装已经过极致的性能优化。

使用方法
将标准 MIDI 文件渲染为 WAV：

bash
python player.py "你的文件.mid" --bank "NECOPN_GM.opm" -o "输出.wav"
命令行参数：

midi: 输入的 MIDI 文件路径。

--bank: .opm 音色库路径（默认：NECOPN_GM.opm）。

-o, --out: 输出的 .wav 文件路径。

--tail: 渲染尾部多保留的余响秒数（默认 1.0）。

--clock: OPM 芯片主时钟频率（默认 3,579,545 Hz）。

免责声明与核心替换指南
硬件固有瑕疵：由于本项目使用的是 Nuked OPM 核心，它输出的是没有任何现代 DSP 平滑处理、也没有内置低通滤波（LPF）的“裸数字信号”。因此，在 MIDI 事件极其密集，或使用高反馈（FL）音色时，可能会产生刺耳的“锯齿毛刺”或高频混叠。这是真实硬件物理特性的忠实呈现，而非 BUG。

如何更换核心：如果你更偏好 VST 那种平滑、柔和的声音，你可以自行替换核心。请参考 core.py 中的封装逻辑，实现 ChipCore 抽象基类（编写你自己的接口），并传入 driver.py 即可无缝切换（例如移植 fmgen）。

音色库与致谢
音色库 (OPM 预设)：仓库中提供的 .opm 预设源自 NECOPN.DRV 的逆向提取工程。
提取工具与逆向工程请访问：https://github.com/EriczjrWinter/necopn-drv-reverse

核心仿真器：感谢 Nuke.YKT 开发的 https://github.com/nukeykt/Nuked-OPM