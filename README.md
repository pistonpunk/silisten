# Silisten

Push-to-talk transcription for Linux. Whisper large-v3 on the GPU, speaker diarization, a black notch at the bottom of the screen.

Press a key chord anywhere, talk, press it again. The text appears in the notch; copy it or keep talking and it appends.

## Install

```bash
cd ~/Work/Silisten
./install.sh
```

`install.sh` creates the venv, installs the ROCm torch wheels, fetches whisper-large-v3 (~3 GB), installs Electron, adds the udev rule that lets the app read the keyboard, and registers autostart.

Start it: `bin/silisten start` (or just log out and back in — it autostarts).

## Speaker diarization (needs your token)

The weights are gated. Without a token everything else works and speakers are simply not labelled.

1. Create a read token: <https://huggingface.co/settings/tokens>
2. Accept the terms on both pages:
   - <https://huggingface.co/pyannote/speaker-diarization-3.1>
   - <https://huggingface.co/pyannote/segmentation-3.0>
3. Save it:

```bash
bin/silisten config --set hf_token=hf_xxxxxxxxxxxxxxxx
```

Restart the app. Settings → Speakers should say ready.

## Use

- **Shift+Tab+Q** — start listening, press again to stop. Change it in Settings (any chord, e.g. `Ctrl+Alt+Space`).
- **Copy all** — puts the whole transcript on the clipboard and hides the notch.
- **Talk more** — records again and appends to the same transcript.
- **Upload file** — pick an audio or video file. Drag and drop onto the notch works too.
- **Esc** — hide the notch.

## Models

- Speech: `openai/whisper-large-v3`, fp16 on the GPU, full precision — not quantized.
- Speakers: `pyannote/speaker-diarization-3.1`.

Change them in `~/.config/silisten/config.json` (`model`, `diarization_model`) or the Settings panel.

## Config

`~/.config/silisten/config.json`

```json
{
  "shortcut": "Shift+Tab+Q",
  "language": null,
  "input_device": "default",
  "model": "openai/whisper-large-v3",
  "diarization_model": "pyannote/speaker-diarization-3.1",
  "diarize": true,
  "hf_token": null,
  "port": 8756
}
```

`language: null` auto-detects. A recording runs through `arecord` (falls back to `pw-record`), files through `ffmpeg`.

## Requirements

- Linux with a PipeWire or ALSA microphone, `ffmpeg`, `arecord`
- AMD ROCm GPU (tested on RX 9070 XT / gfx1201) or CPU fallback
- Python 3.14, Node 22

The backend listens on `127.0.0.1:8756` and requires the token in `~/.config/silisten/token`, so other local pages can't drive it.

## Troubleshooting

**Shortcut does nothing** — Settings → Shortcut shows the reason. If it says access denied, `./install.sh` didn't finish or you haven't logged out since it ran.

**Model failed** — Settings shows the error. Usually missing ROCm drivers or no disk space for the weights.

**Speakers never labelled** — no token, see above.
