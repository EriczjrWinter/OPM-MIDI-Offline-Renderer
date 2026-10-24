# OPM MIDI Offline Renderer 

> **Language**: [English | [简体中文](README_zh.md)]

---

## English

### Overview
This project is a lightweight, high-performance offline MIDI-to-WAV synthesizer built on top of the **Nuked OPM** (cycle-accurate YM2151 emulator). 

Inspired by the dynamic voice-stealing (note-dropping) mechanism of the classic PC-98 `NECOPN.DRV` driver, this renderer strictly limits playback to 8 hardware channels (the physical limit of the YM2151). When the polyphony exceeds the hardware limit, the system performs a "battle royale" (Voice Stealing) algorithm—prioritizing the main melody and aggressively cutting off older or lower-priority notes to simulate the authentic, nostalgic behavior of 90s FM sound chips.

### Features
- **Hardware-Accurate Rendering**: Powered by the C-based Nuked OPM for cycle-accurate YM2151 emulation (64 clocks per sample).
- **Dynamic Voice Stealing (NECOPN Style)**: Automatically manages the 8 physical channels, ruthlessly cutting off lower-priority tracks when polyphony is exceeded.
- **Hardware FM Drum Synthesis**: Since the YM2151 lacks ADPCM/Sample playback, this project synthesizes GM standard drum kits (Channel 10) using pure FM hardware noise and ultra-fast envelopes. One physical channel (Ch 7) is exclusively reserved for percussion, fully exempt from the voice-stealing algorithm.
- **CC74 Brightness Control**: Implements CC74 (Brightness) based on Wohlstand's approach (libOPNMIDI), dynamically adjusting the Modulator's TL to simulate a low-pass filter effect on the FM timbre.

### 🔄 Interoperability with WOPN Banks

This engine is not limited to the `.opm` presets extracted from `NECOPN.DRV`. We have tested that valid **`.wopn` (WOPN2-B2NK)** banks designed for `libOPNMIDI` can also be perfectly utilized by this engine after being converted to `.opm` format.

**How to use WOPN banks with this renderer:**
1. **Get WOPN Banks**: You can find a wide variety of instrument banks in the [libOPNMIDI repository](https://github.com/Wohlstand/libOPNMIDI).
2. **Get OPN2-BE**: Download the **DEV (Development) version** of [OPN2BankEditor](https://github.com/Wohlstand/OPN2BankEditor) to ensure you have the latest WOPN parsing and OPM export support.
3. **Convert to OPM**: Open the `.wopn` file in OPN2-BE and export it as an `.opm` preset bank.
4. **Render**: Run the Python engine and specify the converted `.opm` file via the CLI arguments.

### Requirements
- Python 3.8+
- **Nuked OPM Core (`opm.dll` / `opm.so`)**: The compiled C core must be placed in the root directory. Note that Nuked OPM is a CPU-intensive cycle-accurate emulator; rendering speed depends on your CPU, though the Python wrapper is highly optimized.

### Usage
Render a standard MIDI file to WAV:
```bash
python player.py "path/to/your.mid" --bank "NECOPN_GM.opm" -o "output.wav"
CLI Arguments:

midi: Path to the input MIDI file.

--bank: Path to the .opm voice bank (default: NECOPN_GM.opm).

-o, --out: Path to the output .wav file.

--tail: Seconds of extra audio to render at the end (default: 1.0).

--clock: Master clock for the OPM chip (default: 3,579,545 Hz).

Disclaimer & Core Replacement
Hardware Quirks & Uncontrollable Artifacts: Because this project uses Nuked OPM, it simulates the raw digital output of the YM2151 chip without any modern DSP smoothing or built-in LPF (Low-Pass Filter). Therefore, dense MIDI events or high-feedback patches may produce harsh "zipper noise" or high-frequency aliasing. This is a genuine characteristic of the hardware, not a bug.

Swapping the Core: If you prefer a smoother, VST-like sound, the project's modular design allows you to replace the core. Simply refer to the encapsulation logic in core.py and implement the ChipCore abstract class to wrap another emulator (like fmgen), then pass it to driver.py.

Credits & Sound Bank
Sound Bank (OPM Presets): The .opm patches provided in this repo are dynamically extracted from the reverse-engineered NECOPN.DRV.
Check out the extraction project here: https://github.com/EriczjrWinter/necopn-drv-reverse

Emulation Core: https://github.com/nukeykt/Nuked-OPM by Nuke.YKT.

