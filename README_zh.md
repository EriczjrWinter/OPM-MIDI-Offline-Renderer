OPM MIDI 离线渲染合成器

项目简介
这是一个基于 Nuked OPM（逐周期精确仿真的 YM2151 芯片核心）构建的轻量级、高性能 MIDI 离线渲染合成器。

本项目致敬并复现了经典 PC-98 平台 NECOPN.DRV 驱动的“动态丢音”（Voice Stealing / 大逃杀）机制。由于 YM2151 硬件只有 8 个物理通道，当 MIDI 音轨数超过硬件限制时，系统会执行优先级抢占策略——优先保障主旋律，无情切断老旧或低优先级的音符，完美还原 90 年代 FM 街机音源的复古听感。

核心特性
- **硬件级精确渲染**：底层调用 C 语言的 Nuked OPM 核心，实现精确到 64 clock 的芯片级仿真。
- **动态丢音机制**：完美复刻 NECOPN 的通道分配逻辑，在 8 通道满载时执行残酷的“大逃杀”抢音。
- **纯 FM 鼓组合成 (FM Drum Synthesis)**：由于 YM2151 硬件本身不具备 OPN 的 ADPCM 或板载 RHY，本项目利用芯片内置的“硬件噪声(Noise)”与极速包络，直接在寄存器层硬编码合成了一套 GM 标准鼓组。系统强制保留物理通道 7 作为专属鼓轨，该通道享受大逃杀机制的“绝对豁免权”，保证打击乐永远不被旋律抢占。
- **CC74 亮度辅助**：参考 Wohlstand (libOPNMIDI) 的实现思路，支持 CC74 (Brightness) 控制器，通过动态调整 FM 调制器（Modulator）的电平，模拟出低通滤波器的明暗变化。

### 🔄 与 WOPN 音色库的互操作性

本引擎并不局限于从 `NECOPN.DRV` 提取的内置 `.opm` 预设。经过实际测试，任何为 `libOPNMIDI` 设计的合规 **`.wopn` (WOPN2-B2NK)** 音色库，在转换为 `.opm` 格式后，同样能被本引擎完美识别并演奏。

**如何使用 WOPN 音色库：**
1. **获取 WOPN 音色库**：你可以在 [libOPNMIDI 仓库](https://github.com/Wohlstand/libOPNMIDI) 中找到各种丰富的音色库。
2. **获取 OPN2-BE**：请下载 [OPN2BankEditor](https://github.com/Wohlstand/OPN2BankEditor) 的 **DEV (开发) 版本**，以确保获得最新的 WOPN 解析和 OPM 导出支持。
3. **转换为 OPM**：使用 OPN2-BE 打开 `.wopn` 文件，并将其导出为 `.opm` 预设库。
4. **渲染**：在命令行中指定转换好的 `.opm` 文件，运行本 Python 渲染引擎即可。


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
