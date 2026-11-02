import os
import shutil
import subprocess
import urllib.request
from pathlib import Path

from . import config

ROOT = Path(__file__).resolve().parent.parent
SEGMENTATION_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-segmentation-models/"
    "sherpa-onnx-pyannote-segmentation-3-0.tar.bz2"
)
EMBEDDING_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/"
    "wespeaker_en_voxceleb_CAM++.onnx"
)
VAD_URL = "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"

GBINDINGS = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings"
SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
KEYBINDING_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"


def gsettings_get(schema, key):
    try:
        return subprocess.run(["gsettings", "get", schema, key], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def gsettings_set(schema, key, value):
    subprocess.run(["gsettings", "set", schema, key, value], check=False)


def install_command():
    source = ROOT / "bin" / "silisten"
    source.chmod(0o755)
    target = Path.home() / ".local" / "bin" / "silisten"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink() or target.exists():
            target.unlink()
        target.symlink_to(source)
    except OSError:
        print("  command: could not link, use ./bin/silisten")
        return False
    print(f"  command: {target}")
    if str(target.parent) not in os.environ.get("PATH", "").split(":"):
        print(f"  add ~/.local/bin to PATH, or run {target} directly")
    return True


def gnome_shortcut(shortcut):
    if not shutil.which("gsettings"):
        print("  shortcut: gsettings not found (not GNOME?)")
        return False

    path = f"{GBINDINGS}/silisten/"
    current = gsettings_get(SCHEMA, "custom-keybindings") or "@as []"
    if path not in current:
        inner = current.strip()[1:-1].strip()
        entries = [e.strip() for e in inner.split(",") if e.strip()] if inner else []
        entries.append(f"'{path}'")
        gsettings_set(SCHEMA, "custom-keybindings", "[" + ", ".join(entries) + "]")

    gsettings_set(f"{KEYBINDING_SCHEMA}:{path}", "name", "Silisten")
    gsettings_set(f"{KEYBINDING_SCHEMA}:{path}", "command", "silisten toggle")
    gsettings_set(f"{KEYBINDING_SCHEMA}:{path}", "binding", shortcut)
    print(f"  GNOME shortcut: {shortcut} -> silisten toggle")
    return True


def desktop_entry():
    entry = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Silisten\n"
        "Comment=Speak, transcribe, copy\n"
        "Exec=silisten start\n"
        "Icon=audio-input-microphone\n"
        "Terminal=false\n"
        "Categories=Utility;AudioVideo;\n"
        "StartupNotify=false\n"
    )
    applications = Path.home() / ".local" / "share" / "applications"
    applications.mkdir(parents=True, exist_ok=True)
    target = applications / "silisten.desktop"
    target.write_text(entry)
    print(f"  app menu: {target}")


def download(url, target):
    if target.is_file() and target.stat().st_size > 0:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    with urllib.request.urlopen(url, timeout=120) as response, open(partial, "wb") as handle:
        shutil.copyfileobj(response, handle)
    partial.replace(target)


def install_diarization_models():
    base = config.models_dir()
    print(f"  diarization models: {base}")
    try:
        archive = base / "segmentation.tar.bz2"
        download(SEGMENTATION_URL, archive)
        if archive.is_file():
            subprocess.run(["tar", "xjf", str(archive), "-C", str(base)], check=True)
            archive.unlink()
        download(EMBEDDING_URL, base / "emb.onnx")
        download(VAD_URL, base / "silero_vad.onnx")
    except Exception as e:
        print(f"  diarization models: failed ({e})")
        return False
    from .engine import EMBEDDING_FILE, SEGMENTATION_FILE, VAD_FILE

    ok = all((base / name).is_file() for name in (SEGMENTATION_FILE, EMBEDDING_FILE, VAD_FILE))
    print(f"  diarization models: {'ok' if ok else 'incomplete'}")
    return ok


def prefetch(cfg):
    from .engine import Engine

    engine = Engine(cfg)
    engine.load()
    print(f"  speech model: {engine.state} on {engine.device} ({engine.error or 'ok'})")
    if cfg.get("diarization"):
        engine.diar.load()
        print(f"  speakers: {engine.diar.state} ({engine.diar.error or 'ok'})")


def check_commands():
    missing = [c for c in ("ffmpeg", "arecord", "cmake", "g++") if not shutil.which(c)]
    if missing:
        print(f"  missing commands: {', '.join(missing)}")
        print("  sudo apt install ffmpeg alsa-utils cmake g++ qt6-base-dev qt6-declarative-dev qt6-wayland liblayershellqtinterface-dev")
        return False
    print("  system commands: ok")
    return True


PROFILE_HELP = {
    "best": "large-v3, most accurate, ~6 GB VRAM",
    "balanced": "large-v3-turbo, about twice as fast",
    "fast": "small, runs on modest hardware",
    "minimal": "small, no speaker labels",
}


def choose_profile(args):
    from . import models

    profile = getattr(args, "profile", None)
    if profile:
        if profile not in models.PROFILES:
            raise SystemExit(f"unknown profile '{profile}' - choose from {', '.join(models.PROFILES)}")
        return profile
    if getattr(args, "yes", False):
        return "balanced"
    if not sys.stdin.isatty():
        return "balanced"
    print("\n  Which models do you want? Only the chosen ones are downloaded.\n")
    for index, (name, blurb) in enumerate(PROFILE_HELP.items(), 1):
        print(f"    {index}) {name:<9} {blurb}")
    choice = input("\n  Choice [2]: ").strip() or "2"
    names = list(PROFILE_HELP)
    if choice.isdigit() and 1 <= int(choice) <= len(names):
        return names[int(choice) - 1]
    return choice if choice in models.PROFILES else "balanced"


def install_models(cfg, profile):
    from . import models

    print(f"  models: {profile} profile")
    ok = models.install_profile(cfg, profile)
    config.save(cfg)
    print(f"  models: {'ok' if ok else 'incomplete'}")
    return ok


def run(args):
    cfg = config.load()
    print("silisten setup")
    check_commands()
    install_command()
    desktop_entry()
    gnome_shortcut(cfg["shortcut"])
    profile = choose_profile(args)
    install_models(cfg, profile)
    if not args.no_prefetch:
        prefetch(cfg)
    print(f"\n  config: {config.PATH}")
    print("  start: silisten start   (or launch Silisten from your app menu)")
    return 0
