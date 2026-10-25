# OPM MIDI 离线渲染器

> **Language**: [[English](README.md) | 简体中文]

本项目是一个轻量级、高性能的离线 MIDI 转 WAV 合成器，基于 **Nuked OPM**（周期精确的 YM2151 模拟器）构建。受经典 PC-98 `NECOPN.DRV` 驱动器的动态声部抢占（丢音）机制启发，本渲染器严格将播放限制在 8 个硬件通道（YM2151 的物理上限）内，并还原 90 年代 FM 音效芯片真实而怀旧的听感。

> **🎯 状态**: 离线渲染器功能完整，包含硬件级精确的 YM2151 模拟、NECOPN 风格声部抢占、硬件 FM 鼓合成以及 CC74 亮度控制。WOPN 银行互操作性已通过验证。
> 
> **📦 开箱即用**: 已内置默认 `NECOPN_GM.opm` 音色银行（从逆向工程还原的 `NECOPN.DRV` 中动态提取）。无需准备外部银行即可直接渲染。

## 🏗️ 架构与核心要点

**1. 周期精确的 YM2151 模拟**
由 C 语言编写的 Nuked OPM 核心驱动，每个采样模拟 64 个时钟周期。这是一个 CPU 密集型模拟器，但 Python 封装层已高度优化。

**2. 动态声部抢占（NECOPN 风格）**
渲染器严格限制在 8 个硬件通道内。当复音数超过硬件上限时，"大逃杀"声部抢占算法会优先保留主旋律，并激进地切断较旧或较低优先级的音符——模拟原始 `NECOPN.DRV` 驱动器的真实丢音行为。

**3. 硬件 FM 鼓合成**
由于 YM2151 不支持 ADPCM/采样播放，GM 标准鼓组（通道 10）通过纯 FM 硬件噪声和超快包络合成。一个物理通道（Ch 7）专供打击乐使用，完全豁免于声部抢占算法。

**4. CC74 亮度控制**
按照 Wohlstand 的方案（libOPNMIDI）实现 CC74（亮度）：动态调整调制器 TL，以模拟 FM 音色上的低通滤波效果。

## 📦 必需资源

1. **Python 3.8+**
   * 运行 Python 引擎所需。
2. **Nuked OPM 核心（`opm.dll` / `opm.so`）**
   * 编译好的 C 核心必须放置在根目录中。请注意，Nuked OPM 是 CPU 密集型的周期精确模拟器，渲染速度取决于你的 CPU。
3. **音色银行（`.opm`）**
   * 默认的 `NECOPN_GM.opm` 已内置，从逆向工程还原的 `NECOPN.DRV` 中动态提取。
   * *（可选）* 也可以使用任何有效的 `.opm` 银行，包括由 WOPN 转换而来的银行（见下文）。

## 🚀 快速开始

### 将 MIDI 文件渲染为 WAV
bash
python player.py "path/to/your.mid" --bank "NECOPN_GM.opm" -o "output.wav"

命令行参数
参数	默认值	说明
midi	—	输入 MIDI 文件的路径。
--bank	NECOPN_GM.opm	.opm 音色银行的路径。
-o, --out	—	输出 .wav 文件的路径。
--tail	1.0	结尾额外渲染的音频秒数。
--clock	3579545	OPM 芯片的主时钟（Hz）。

### 🎛️ 命令行参数
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `midi` | — | 输入 MIDI 文件的路径。 |
| `--bank` | `NECOPN_GM.opm` | `.opm` 音色银行的路径。 |
| `-o, --out` | — | 输出 `.wav` 文件的路径。 |
| `--tail` | `1.0` | 结尾额外渲染的音频秒数。 |
| `--clock` | `3579545` | OPM 芯片的主时钟（Hz）。 |

### 🔄 与 WOPN 音色库的互操作性
本引擎不仅限于从 `NECOPN.DRV` 中提取的 `.opm` 预设。为 `libOPNMIDI` 设计的有效 **`.wopn`（WOPN2-B2NK）** 银行在转换为 `.opm` 格式后，也可以被本引擎完美使用。

1. **获取 WOPN 银行**：可在 [libOPNMIDI 仓库](https://github.com/Wohlstand/libOPNMIDI) 中找到各种乐器库。
2. **获取 OPN2-BE**：下载 [OPN2BankEditor](https://github.com/Wohlstand/OPN2BankEditor) 的 **DEV（开发）版本**，以确保获得最新的 WOPN 解析和 OPM 导出支持。
3. **转换为 OPM**：在 OPN2-BE 中打开 `.wopn` 文件，并导出为 `.opm` 预设音色库。
4. **渲染**：运行 Python 引擎，并通过 `--bank` 指定转换后的 `.opm` 文件。

###
- **硬件特性与不可控伪影：** 由于本项目使用 Nuked OPM，它模拟的是 YM2151 芯片的原始数字输出，没有现代 DSP 平滑或内置低通滤波器。因此，密集的 MIDI 事件或高反馈音色可能产生刺耳的"拉链噪声"或高频混叠。这是硬件的真实特性，而非 bug。
- **替换核心：** 如果你偏好更平滑、VST 般的听感，本项目的模块化设计允许你替换核心。参考 `core.py` 中的封装逻辑，实现 `ChipCore` 抽象类以包装其他模拟器（如 `fmgen`），然后传递给 `driver.py`。

### 🔬 技术细节
- **周期精确核心：** Nuked OPM 每个采样模拟 64 个时钟周期的 YM2151。
- **声部抢占：** 8 通道硬限制，基于优先级的丢音策略，与 `NECOPN.DRV` 行为一致。
- **鼓通道保留：** 物理通道 7 专供 FM 打击乐使用，不参与声部抢占。
- **CC74 亮度：** 按照 libOPNMIDI 的实现调整调制器 TL。

### 🙏 致谢与免责声明
- 感谢 **Wohlstand** 与 **JP Cimalando** 在 OPN2-BE 中实现基础的 OPM 库导出支持，使 WOPN→OPM 跨芯片工作流成为可能。
- **音色银行（OPM 预设）：** 本仓库提供的 `.opm` 音色从逆向工程还原的 `NECOPN.DRV` 中动态提取。提取项目地址：https://github.com/EriczjrWinter/necopn-drv-reverse
- **模拟核心：** [Nuked-OPM](https://github.com/nukeykt/Nuked-OPM)，作者 Nuke.YKT。
- 本项目仅供个人学习、复古技术研究与交流，所有权利归各自所有者所有。
