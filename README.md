# OPM MIDI Offline Renderer

> **Language**: [English | [简体中文](README_zh.md)]

This project is a lightweight, high-performance offline MIDI-to-WAV synthesizer built on top of **Nuked OPM**, a cycle-accurate YM2151 emulator. Inspired by the dynamic voice-stealing (note-dropping) mechanism of the classic PC-98 `NECOPN.DRV` driver, it strictly limits playback to the 8 physical channels of the YM2151 and reproduces the authentic, nostalgic character of 90s FM sound chips.

> **🎯 Status**: Fully functional offline renderer with hardware-accurate YM2151 emulation, NECOPN-style voice stealing, hardware FM drum synthesis, and CC74 brightness control. WOPN bank interoperability has been verified.
> 
> **📦 Out-of-the-box**: A default `NECOPN_GM.opm` voice bank (dynamically extracted from the reverse-engineered `NECOPN.DRV`) is bundled. You can render immediately without preparing external banks.

## 🏗️ Architecture & Core Notes

**1. Cycle-Accurate YM2151 Emulation**
Powered by the C-based Nuked OPM core, which emulates the YM2151 at 64 clocks per sample. This is a CPU-intensive emulator, but the Python wrapper is highly optimized.

**2. Dynamic Voice Stealing (NECOPN Style)**
The renderer strictly limits playback to 8 hardware channels. When polyphony exceeds the hardware limit, a "battle royale" voice-stealing algorithm prioritizes the main melody and aggressively cuts off older or lower-priority notes — simulating the authentic note-dropping behavior of the original `NECOPN.DRV` driver.

**3. Hardware FM Drum Synthesis**
Since the YM2151 lacks ADPCM/sample playback, GM standard drum kits (Channel 10) are synthesized using pure FM hardware noise and ultra-fast envelopes. One physical channel (Ch 7) is exclusively reserved for percussion and is fully exempt from the voice-stealing algorithm.

**4. CC74 Brightness Control**
Implements CC74 (Brightness) following Wohlstand's approach (libOPNMIDI): the Modulator's TL is adjusted dynamically to simulate a low-pass filter effect on the FM timbre.

## Drum Kit Implementation & OPM Bank Limitations
 A fundamental limitation of the standard .opm file format is that it natively supports only 128 melodic instruments. Historically, percussion on OPM chips was entirely synthesized or handled via external hardware. Therefore, standard .opm banks physically cannot contain a GM drum kit.

To solve this and maintain authentic rhythm, this engine implements the drum kit through the following logic:

**1. WOPN Backporting**: We extracted a professionally tuned GM percussion set from a standard WOPN bank.
Hardcoded in Driver: Since .opm cannot store drums, these tuned parameters are hardcoded directly into driver.py as a dedicated dictionary (DRUM_BANK). This bypasses the .opm format limitation and prevents the performance overhead of dynamically loading patches for every drum hit.

**2. Ch7 Dedication**: To preserve the 7 melodic channels for polyphony (via the NECOPN voice-stealing algorithm), the entire drum kit is locked to Physical Channel 7. This results in a "monophonic compromise" where overlapping drum notes (e.g., kick and hi-hat simultaneously) will cut each other off, faithfully replicating the physical constraints of vintage hardware.

TIP:Legacy FM Noise Drums: The original handcrafted FM noise drum logic is retained in the code as a "legacy fallback." 

## 📦 Required Assets

1. **Python 3.8+**
   * Required to run the Python engine.
2. **Nuked OPM Core (`opm.dll` / `opm.so`)**
   * The compiled C core must be placed in the root directory. Note that Nuked OPM is a CPU-intensive cycle-accurate emulator; rendering speed depends on your CPU.
3. **Voice Bank (`.opm`)**
   * The default `NECOPN_GM.opm` is bundled and dynamically extracted from the reverse-engineered `NECOPN.DRV`.
   * *(Optional)* You may also supply any valid `.opm` bank, including ones converted from WOPN (see below).

## 🚀 Quick Start

### Render a MIDI file to WAV
bash
python player.py "path/to/your.mid" --bank "NECOPN_GM.opm" -o "output.wav"

### 🎛️ CLI Arguments
| Argument | Default | Description |
|----------|---------|-------------|
| `midi` | — | Path to the input MIDI file. |
| `--bank` | `NECOPN_GM.opm` | Path to the `.opm` voice bank. |
| `-o, --out` | — | Path to the output `.wav` file. |
| `--tail` | `1.0` | Seconds of extra audio to render at the end. |
| `--clock` | `3579545` | Master clock for the OPM chip (Hz). |

### 🔄 Interoperability with WOPN Banks
This engine is not limited to `.opm` presets extracted from `NECOPN.DRV`. Valid **`.wopn` (WOPN2-B2NK)** banks designed for `libOPNMIDI` can also be perfectly utilized by this engine after conversion to `.opm` format.

1. **Get WOPN Banks**: A wide variety of instrument banks can be found in the [libOPNMIDI repository](https://github.com/Wohlstand/libOPNMIDI).
2. **Get OPN2-BE**: Download the **DEV (Development) version** of [OPN2BankEditor](https://github.com/Wohlstand/OPN2BankEditor) to ensure the latest WOPN parsing and OPM export support.
3. **Convert to OPM**: Open the `.wopn` file in OPN2-BE and export it as an `.opm` preset bank.
4. **Render**: Run the Python engine and specify the converted `.opm` file via `--bank`.

### 🔄 VGM Export Support
In addition to rendering WAV files, this project includes a dedicated export tool, vgm_player.py, which allows you to export standard VGM (Video Game Music) files.

1. **Why export to VGM?**: VGM files contain only the raw YM2151 register commands and timestamps, resulting in an incredibly small file size (e.g., a 4-minute track may be only a few dozen KB). You can play these files using modern VGM players (like Foobar2000 with the VGM plugin or VGMPlay), or even on real hardware setups.
2. **How to use:**: Use vgm_player.py instead of player.py. The rest of the logic (voice banks, NECOPN voice-stealing, FM drums) is exactly the same as the WAV export.

python vgm_player.py "path/to/your.mid" --bank "NECOPN_GM.opm" -o "output.vgm"

###
- **Hardware Quirks & Uncontrollable Artifacts:** Because this project uses Nuked OPM, it simulates the raw digital output of the YM2151 without modern DSP smoothing or built-in LPF. Dense MIDI events or high-feedback patches may produce harsh "zipper noise" or high-frequency aliasing. This is a genuine characteristic of the hardware, not a bug.
- **Swapping the Core:** If you prefer a smoother, VST-like sound, the modular design allows you to replace the core. Refer to the encapsulation logic in `core.py` and implement the `ChipCore` abstract class to wrap another emulator (e.g., `fmgen`), then pass it to `driver.py`.

### 🔬 Technical Details
- **Cycle-Accurate Core:** Nuked OPM emulates the YM2151 at 64 clocks per sample.
- **Voice Stealing:** 8-channel hard limit with priority-based note dropping, matching `NECOPN.DRV` behavior.
- **Drum Channel Reservation:** Physical channel 7 is reserved exclusively for FM percussion and never participates in voice stealing.
- **CC74 Brightness:** Modulator TL adjustment following libOPNMIDI's implementation.

### 🙏 Credits & Disclaimer
- **Credits & Sound Bank**
OPN2-BE & WOPN Collections: Special thanks to Wohlstand and JP Cimalando for their foundational work on OPN2-BE (OPN2 Bank Editor). Their support for OPM bank exporting made the WOPN→OPM cross-chip workflow possible. More importantly, we deeply appreciate the high-quality WOPN instrument collections they curated, which made it possible to backport professionally tuned FM drums into this engine.
- **Sound Bank (OPM Presets):** The `.opm` patches provided in this repo are dynamically extracted from the reverse-engineered `NECOPN.DRV`. Check out the extraction project here: https://github.com/EriczjrWinter/necopn-drv-reverse
- **Emulation Core:** [Nuked-OPM](https://github.com/nukeykt/Nuked-OPM) by Nuke.YKT.
- This project is for educational and preservation purposes only. All rights belong to their respective owners.
