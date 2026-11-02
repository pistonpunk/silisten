# Silisten

Push-to-talk transcription for Linux. You hit a shortcut, talk, press Done, and the text appears in a small notch at the bottom of the screen. Copy it and carry on.

Everything runs on your own machine. No account, no API key, nothing leaves the computer.

![Silisten](docs/demo.gif)

I wrote it because I wanted dictation that stays out of the way. The notch is small on purpose, it disappears when you are done with it, and it does not need a browser window or a subscription to work.

## Using it

`Ctrl+Delete` opens the notch and starts recording. Say what you need to say, then press `Done`. The text appears, and the copy button puts all of it on the clipboard.

If you think of something else before copying, press `Talk more` and the next recording gets appended to the same text instead of replacing it.

There is a file button too, and you can drag an audio or video file onto the notch. It will transcribe that and label the speakers.

## Installing

### AppImage

Grab `Silisten-*-x86_64.AppImage` from [releases](../../releases).

```sh
chmod +x Silisten-*-x86_64.AppImage
./Silisten-*-x86_64.AppImage
```

First run is slow. It builds a Python environment under `~/.local/share/silisten/venv`, installs the speech backend, then downloads whichever model you pick. Give it a few minutes and a few GB of disk.

### From source

```sh
git clone https://github.com/pistonpunk/silisten
cd silisten
./install.sh
```

The script asks which model profile you want, downloads just those, builds the Qt front end, drops a `silisten` command on your PATH, and adds a desktop shortcut.

You will need these (Debian/Ubuntu names):

```
python3-venv ffmpeg alsa-utils cmake g++
qt6-base-dev qt6-declarative-dev qt6-wayland liblayershellqtinterface-dev
```

## Models

Nothing is bundled. You choose what gets downloaded, either during install or later.

```sh
silisten models                 # what is installed and what is in use
silisten models install speech large-v3-turbo
silisten models profile fast    # switch the whole set at once
```

| Model | Size | Notes |
| --- | --- | --- |
| `large-v3` | 3.1 GB | Most accurate. Wants around 6 GB of VRAM. |
| `large-v3-turbo` | 1.6 GB | About twice as fast, a little less accurate. |
| `medium` | 1.5 GB | For smaller cards. |
| `small` | 0.5 GB | Fine on CPU. |

There is also a Romanian fine-tune that gets used when you set the language to Romanian. It is much better at Romanian than the stock model and about three times faster. If its output does not look like Romanian at all, Silisten falls back to the main model, so a wrong language setting cannot leave you with garbage.

The same choice is in the app settings if you would rather click than type. Anything not downloaded yet gets fetched the first time it is needed.

## Settings

Config lives in `~/.config/silisten/config.json`. You can edit the file, or use `silisten config --set key=value`.

| Key | Default | What it does |
| --- | --- | --- |
| `shortcut` | `Ctrl+Delete` | Shortcut registered with your desktop |
| `language` | `null` | Recognition language. `null` means auto-detect |
| `input_device` | `default` | Microphone, by the name in the picker |
| `speech_model` | `large-v3` | One of the names above |
| `romanian_model` | `fra-piz-turbo` | Set to `null` to turn the Romanian model off |
| `diarization` | `pyannote-campplus` | Speaker labels. `null` turns them off |
| `diarization_threshold` | `0.7` | Higher merges similar voices, lower splits them |
| `vad_threshold` | `0.5` | Higher is stricter about what counts as speech |
| `auto_stop` | `false` | Stop by itself after a pause |
| `auto_stop_seconds` | `1.6` | How long that pause has to be |
| `auto_download` | `true` | Fetch missing models automatically |
| `models_dir` | `~/.local/share/silisten/models` | Where models are kept |
| `port` | `8756` | Local backend port |

## What you need

Linux with a PipeWire or ALSA microphone, Python 3.11 or newer, and 4 GB of RAM plus whatever your model needs.

A GPU is optional. On AMD it runs through ROCm; NVIDIA works through the same PyTorch path. On CPU it works too, just slowly, so pick a small model.

About the window: Silisten checks the compositor at startup. On KDE Plasma, Hyprland, sway, river, labwc and Wayfire it uses a layer-shell surface, which is a real overlay pinned to the bottom edge. GNOME does not support that protocol, so there it falls back to a frameless always-on-top window in the same place. It looks the same, but other windows can still be focused over it in a few corner cases.

## When something goes wrong

**Shortcut does nothing.** Check `silisten config` and make sure the binding there matches what your desktop has registered. On GNOME you can rebind under Settings, Keyboard.

**It is bound but nothing opens.** Run `silisten start` in a terminal. The error will be right there instead of swallowed.

**Transcription takes forever.** You are probably on CPU. `silisten models profile fast` fixes most of that.

**Everything comes back in English.** Set the language by hand. Auto-detect is not reliable on short clips.

**No speaker labels.** The two small ONNX models are missing. `silisten models install diarization pyannote-campplus` gets them, they are only about 40 MB.

**It types out words when I said nothing.** Raise `vad_threshold`, and check the right microphone is selected in the notch.

## Building it

```sh
cmake -S ui-qt -B ui-qt/build -DCMAKE_BUILD_TYPE=Release
cmake --build ui-qt/build -j"$(nproc)"
```

Push a tag and GitHub Actions builds the AppImage plus source archives and attaches them to the release. The workflow runs inside a clean Ubuntu container so the Qt version does not drift between machines.

## License

MIT. Do what you like with it.
