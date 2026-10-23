OPM MIDI 离线渲染合成器

项目简介
这是一个基于 Nuked OPM（逐周期精确仿真的 YM2151 芯片核心）构建的轻量级、高性能 MIDI 离线渲染合成器。

本项目致敬并复现了经典 PC-98 平台 NECOPN.DRV 驱动的“动态丢音”（Voice Stealing / 大逃杀）机制。由于 YM2151 硬件只有 8 个物理通道，当 MIDI 音轨数超过硬件限制时，系统会执行优先级抢占策略——优先保障主旋律，无情切断老旧或低优先级的音符，完美还原 90 年代 FM 街机音源的复古听感。

核心特性
硬件级精确渲染：底层调用 C 语言的 Nuked OPM 核心，实现精确到 64 clock 的芯片级仿真。

动态丢音机制：完美复刻 NECOPN 的通道分配逻辑，在 8 通道满载时执行残酷的“大逃杀”抢音。

极致性能优化：音频增益采用纯整数位运算（v >> 1），摒弃浮点运算与软削波，渲染速度极快且彻底杜绝爆音。

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

免责声明与反馈
本项目属于个人兴趣驱动的简易实现。受限于底层架构的精简以及各种 MIDI 文件的复杂性，在实际测试中可能会遇到合成表现不理想的情况（例如大逃杀机制过于激进导致丢音、音色还原偏差等）或未知的 BUG。

如果在使用过程中发现任何问题，或者对项目有改进建议，非常欢迎随时 提交 Issue！同时也欢迎提交 Pull Request 共同完善这个项目。

音色库与致谢
音色库 (OPM 预设)：仓库中提供的 .opm 预设源自 NECOPN.DRV 的逆向提取工程。
提取工具与逆向工程请访问：https://github.com/EriczjrWinter/necopn-drv-reverse

核心仿真器：感谢 Nuke.YKT 开发的 https://github.com/nukeykt/Nuked-OPM