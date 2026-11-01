import shutil
import subprocess
import sys
from pathlib import Path

from . import config

ROOT = Path(__file__).resolve().parent.parent
RULE = Path("/etc/udev/rules.d/70-silisten-input.rules")
RULE_TEXT = 'SUBSYSTEM=="input", KERNEL=="event*", TAG+="uaccess"\n'


def can_read_input():
    from .hotkey import _keyboards

    for path in _keyboards():
        try:
            with open(path, "rb"):
                return True
        except PermissionError:
            continue
    return False


def install_input_rule():
    if can_read_input():
        print("  input access: ok")
        return True
    print("  input access: installing udev rule (sudo)...")
    try:
        subprocess.run(["sudo", "tee", str(RULE)], input=RULE_TEXT.encode(), check=True,
                       stdout=subprocess.DEVNULL)
        subprocess.run(["sudo", "udevadm", "control", "--reload-rules"], check=True)
        subprocess.run(["sudo", "udevadm", "trigger", "--subsystem-match=input"], check=True)
        subprocess.run(["sudo", "udevadm", "settle"], check=False)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"  input access: FAILED ({e})")
        return False
    ok = can_read_input()
    print(f"  input access: {'ok' if ok else 'still denied - log out and back in'}")
    return ok


def install_desktop():
    launcher = ROOT / "bin" / "silisten"
    entry = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Silisten\n"
        "Comment=Speak, transcribe, copy\n"
        f"Exec={launcher} start\n"
        f"Path={ROOT}\n"
        "Icon=audio-input-microphone\n"
        "Terminal=false\n"
        "Categories=Utility;AudioVideo;\n"
        "StartupNotify=false\n"
    )
    apps = Path.home() / ".local" / "share" / "applications"
    autostart = Path.home() / ".config" / "autostart"
    apps.mkdir(parents=True, exist_ok=True)
    autostart.mkdir(parents=True, exist_ok=True)
    (apps / "silisten.desktop").write_text(entry)
    (autostart / "silisten.desktop").write_text(entry)
    print(f"  launcher: {apps / 'silisten.desktop'}")
    print(f"  autostart: {autostart / 'silisten.desktop'}")


def prefetch(cfg):
    from .engine import Engine

    print("  loading whisper-large-v3 (first run downloads ~3 GB)...")
    engine = Engine(cfg)
    engine.load()
    print(f"  engine: {engine.state} on {engine.device} ({engine.error or 'ok'})")
    if cfg.get("diarize"):
        if engine.diar.state == "ready":
            print("  diarization: ready")
        else:
            print(f"  diarization: {engine.diar.state} ({engine.diar.error})")


def diarization_help():
    print(
        "\n  Speaker diarization needs a free Hugging Face token:\n"
        "    1. Create one at https://huggingface.co/settings/tokens\n"
        "    2. Accept the terms at https://huggingface.co/pyannote/speaker-diarization-3.1\n"
        "       and https://huggingface.co/pyannote/segmentation-3.0\n"
        "    3. silisten setup --hf-token hf_xxxxxxxx\n"
    )


def check_commands():
    missing = [c for c in ("ffmpeg", "arecord", "node", "npm") if not shutil.which(c)]
    if missing:
        print(f"  missing commands: {', '.join(missing)}")
        print("  sudo apt install ffmpeg alsa-utils nodejs npm")
        return False
    print("  system commands: ok")
    return True


def run(args):
    cfg = config.load()
    if args.hf_token:
        cfg["hf_token"] = args.hf_token
        config.save(cfg)
        print("  hf token saved")
    print("silisten setup")
    check_commands()
    install_input_rule()
    install_desktop()
    if not args.no_prefetch:
        prefetch(cfg)
    if cfg.get("diarize") and not config.hf_token(cfg):
        diarization_help()
    print(f"\n  config: {config.PATH}")
    print(f"  shortcut: {cfg['shortcut']}")
    print("  start: silisten start")
    return 0
