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
- **Optimized Performance**: Uses pure integer operations (`v >> 1`) for volume scaling, avoiding floating-point bottlenecks and digital clipping.
- **Custom OPM Patches**: Optimized for dynamic snapshot `.opm` presets extracted from the `NECOPN.DRV`.

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

Disclaimer & Feedback
This is a lightweight, hobbyist project. Due to the simplified implementation and the immense complexity of various MIDI files, you may experience imperfect synthesis results (e.g., aggressive voice stealing, patch discrepancies) or encounter unknown bugs.

If you find any issues or have suggestions for improvement, please feel free to submit an Issue. Pull Requests are also highly appreciated!

Credits & Sound Bank
Sound Bank (OPM Presets): The .opm patches provided in this repo are dynamically extracted from the reverse-engineered NECOPN.DRV.
Check out the extraction project here: https://github.com/EriczjrWinter/necopn-drv-reverse

Emulation Core: https://github.com/nukeykt/Nuked-OPM by Nuke.YKT.

