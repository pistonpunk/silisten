# Silisten

Push-to-talk transcription for Linux. Whisper large-v3 on the GPU, speaker diarization, a black notch at the bottom of the screen.

Press a key chord anywhere, talk, press it again. The text appears in the notch; copy it or keep talking and it appends.

## Install

```bash
cd ~/Work/Silisten
./install.sh
```

`install.sh` creates the venv, installs the ROCm torch wheels and sherpa-onnx, fetches whisper-large-v3 (~3 GB) and the diarization models, builds the native GTK3 notch (`ui-native/`), links the `silisten` command, and adds the GNOME shortcut.

The UI is a single Qt 6 / QML binary (`ui-qt/`) — no Electron, no browser.

It picks its windowing backend at startup:
- **layer-shell** (KDE Plasma, Hyprland, sway, river, labwc, Wayfire) — true bottom-edge overlay with keyboard interactivity.
- **X11/XWayland** (GNOME, XFCE and anything else) — a frameless always-on-top window positioned bottom-centre.

Start it with `silisten start`, or press the shortcut. Right now it starts on demand; add the app menu entry to your GNOME autostart if you want it always running.

## Use

- **Shift+Tab+Q** — start listening, press again to stop. If the app isn't running, the shortcut starts it.
- **Copy all** — puts the whole transcript on the clipboard and hides the notch.
- **Talk more** — records again and appends to the same transcript.
- **Upload file** — pick an audio or video file. Drag and drop onto the notch works too.
- **Esc** — hide the notch.

## Changing the shortcut

The binding lives in GNOME, not in the app. Change it anywhere you like:

- GNOME Settings › Keyboard › Custom Shortcuts › **Silisten**
- or `silisten shortcut "Ctrl+Alt+Space"` from a terminal
- or via `gsettings`

It runs `silisten toggle`.

## Models — all local, no tokens, no accounts

- Speech: `openai/whisper-large-v3`, fp16 on the GPU, full precision — not quantized. Downloaded once from Hugging Face into the local cache.
- Romanian: `FraPiz/whisper-large-v3-turbo-moldovan-romanian` is used instead when the language is set to Romanian — roughly 3× faster and far more accurate on Romanian speech. If its output does not look Romanian (or it starts looping), the app falls back to large-v3 so a wrong language setting can never corrupt the text. Both are configurable: `model` and `romanian_model`.
- Speakers: sherpa-onnx running pyannote segmentation-3.0 + WeSpeaker CAM++ embeddings on CPU. Small ONNX models in `~/.local/share/silisten/models/`, married to nothing and used offline. Diarizing a minute of audio takes about a second.

`diarization_threshold` in the config controls how eagerly voices are merged into one speaker — raise it if one person splits into several, lower it if two people merge.

## Config

`~/.config/silisten/config.json`

```json
{
  "shortcut": "Ctrl+Delete",
  "language": null,
  "input_device": "default",
  "model": "openai/whisper-large-v3",
  "diarize": true,
  "auto_stop": true,
  "auto_stop_seconds": 1.6,
  "diarization_dir": null,
  "diarization_threshold": 0.7,
  "port": 8756
}
```

`language: null` auto-detects. A recording runs through `arecord` (falls back to `pw-record`), files through `ffmpeg`.

Recording stops by itself after `auto_stop_seconds` of silence, once you have actually said something. Set `auto_stop` to false to record until you press the key again.

Silero VAD gates every transcription: if nothing is detected as speech, no text is produced. That is what stops Whisper inventing phrases from silence or background noise.

## Requirements

- Linux with a PipeWire or ALSA microphone, `ffmpeg`, `arecord`
- AMD ROCm GPU (tested on RX 9070 XT / gfx1201) or CPU fallback
- Python 3.14, Qt 6 (`qt6-base-dev`, `qt6-declarative-dev`, `qt6-wayland`, `liblayershellqtinterface-dev`, `cmake`, `g++`)

The backend listens on `127.0.0.1:8756` and requires the token in `~/.config/silisten/token`, so other local pages can't drive it.

## Troubleshooting

**Shortcut does nothing** — check the binding with `gsettings get org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/silisten/ binding`. Re-apply with `silisten shortcut "Shift+Tab+Q"`.

**Model failed** — Settings shows the error. Usually missing ROCm drivers or no disk space for the weights.

**Speakers never labelled** — Settings shows the reason. If the models are missing, `./install.sh` re-downloads them. If one voice splits into many, raise `diarization_threshold`.
