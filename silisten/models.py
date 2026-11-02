import shutil
from pathlib import Path

from . import config

SPEECH = {
    "large-v3": {
        "repo": "openai/whisper-large-v3",
        "size_gb": 3.1,
        "label": "Whisper large-v3",
        "note": "most accurate, needs ~6 GB VRAM",
    },
    "large-v3-turbo": {
        "repo": "openai/whisper-large-v3-turbo",
        "size_gb": 1.6,
        "label": "Whisper large-v3-turbo",
        "note": "about twice as fast, slightly less accurate",
    },
    "medium": {
        "repo": "openai/whisper-medium",
        "size_gb": 1.5,
        "label": "Whisper medium",
        "note": "runs on smaller GPUs",
    },
    "small": {
        "repo": "openai/whisper-small",
        "size_gb": 0.5,
        "label": "Whisper small",
        "note": "CPU friendly",
    },
}

ROMANIAN = {
    "fra-piz-turbo": {
        "repo": "FraPiz/whisper-large-v3-turbo-moldovan-romanian",
        "size_gb": 1.6,
        "label": "Romanian turbo fine-tune",
        "note": "used only when the language is Romanian",
    },
}

VAD = {
    "silero": {
        "url": "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx",
        "file": "silero_vad.onnx",
        "size_gb": 0.002,
        "label": "Silero VAD",
        "note": "stops invented text during silence",
    },
}

DIARIZATION = {
    "pyannote-campplus": {
        "files": [
            (
                "https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-segmentation-models/"
                "sherpa-onnx-pyannote-segmentation-3-0.tar.bz2",
                "segmentation.tar.bz2",
                True,
            ),
            (
                "https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/"
                "wespeaker_en_voxceleb_CAM++.onnx",
                "emb.onnx",
                False,
            ),
        ],
        "size_gb": 0.04,
        "label": "Speaker diarization",
        "note": "labels who said what",
    },
}

PROFILES = {
    "best": {"speech": "large-v3", "romanian": "fra-piz-turbo", "vad": "silero", "diarization": "pyannote-campplus"},
    "balanced": {
        "speech": "large-v3-turbo",
        "romanian": "fra-piz-turbo",
        "vad": "silero",
        "diarization": "pyannote-campplus",
    },
    "fast": {"speech": "small", "romanian": "fra-piz-turbo", "vad": "silero", "diarization": "pyannote-campplus"},
    "minimal": {"speech": "small", "romanian": None, "vad": "silero", "diarization": None},
}


def root() -> Path:
    return config.models_dir()


def speech_dir(name: str) -> Path:
    return root() / "speech" / name


def speech_repo(cfg) -> dict:
    name = cfg.get("speech_model") or "large-v3"
    if name in SPEECH:
        return {"name": name, **SPEECH[name]}
    return {"name": name, "repo": name, "label": name, "size_gb": 0, "note": "custom model"}


def romanian_repo(cfg):
    name = cfg.get("romanian_model")
    if not name:
        return None
    if name in ROMANIAN:
        return {"name": name, **ROMANIAN[name]}
    return {"name": name, "repo": name, "label": name, "size_gb": 0, "note": "custom model"}


def _in_hub_cache(repo: str) -> bool:
    try:
        from huggingface_hub import snapshot_download

        snapshot_download(repo_id=repo, local_files_only=True)
        return True
    except Exception:
        return False


def is_installed(kind: str, name: str) -> bool:
    base = root()
    if kind == "speech":
        if (base / "speech" / name / "config.json").is_file():
            return True
        entry = SPEECH.get(name)
        return _in_hub_cache(entry["repo"] if entry else name)
    if kind == "romanian":
        if (base / "romanian" / name / "config.json").is_file():
            return True
        entry = ROMANIAN.get(name)
        return _in_hub_cache(entry["repo"] if entry else name)
    if kind == "vad":
        return (base / VAD[name]["file"]).is_file()
    if kind == "diarization":
        return (base / "sherpa-onnx-pyannote-segmentation-3-0" / "model.onnx").is_file() and (
            base / "emb.onnx"
        ).is_file()
    return False


def local_path(kind: str, name: str):
    if kind == "speech":
        path = root() / "speech" / name
    elif kind == "romanian":
        path = root() / "romanian" / name
    else:
        return None
    return path if (path / "config.json").is_file() else None


def download_speech(kind: str, name: str, log=print) -> bool:
    registry = SPEECH if kind == "speech" else ROMANIAN
    entry = registry.get(name) or {"repo": name, "label": name}
    target = root() / ("speech" if kind == "speech" else "romanian") / name
    if (target / "config.json").is_file():
        log(f"{entry['label']} already installed")
        return True
    target.mkdir(parents=True, exist_ok=True)
    log(f"downloading {entry['label']} (~{entry['size_gb']} GB)")
    from huggingface_hub import snapshot_download

    snapshot_download(
        repo_id=entry["repo"],
        local_dir=str(target),
        allow_patterns=["*.json", "*.txt", "*.safetensors", "*.model"],
    )
    return (target / "config.json").is_file()


def download_file(url: str, target: Path, unpack: bool, log=print) -> bool:
    import subprocess
    import urllib.request

    if target.is_file():
        return True
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    with urllib.request.urlopen(url, timeout=120) as response, open(partial, "wb") as handle:
        shutil.copyfileobj(response, handle)
    partial.replace(target)
    if unpack:
        subprocess.run(["tar", "xjf", str(target), "-C", str(target.parent)], check=True)
        target.unlink()
    return True


def install(kind: str, name: str, log=print) -> bool:
    if kind in ("speech", "romanian"):
        return download_speech(kind, name, log)
    if kind == "vad":
        entry = VAD[name]
        return download_file(entry["url"], root() / entry["file"], False, log)
    if kind == "diarization":
        for url, filename, unpack in DIARIZATION[name]["files"]:
            download_file(url, root() / filename, unpack, log)
        return True
    log(f"unknown model kind {kind}")
    return False


def status(cfg=None) -> dict:
    cfg = cfg or config.load()
    return {
        "speech": [
            {"name": name, "installed": is_installed("speech", name), **meta}
            for name, meta in SPEECH.items()
        ],
        "romanian": [
            {"name": name, "installed": is_installed("romanian", name), **meta}
            for name, meta in ROMANIAN.items()
        ],
        "vad": [{"name": name, "installed": is_installed("vad", name), **meta} for name, meta in VAD.items()],
        "diarization": [
            {"name": name, "installed": is_installed("diarization", name), **meta}
            for name, meta in DIARIZATION.items()
        ],
        "current": {
            "speech": cfg.get("speech_model"),
            "romanian": cfg.get("romanian_model"),
            "diarization": cfg.get("diarization"),
        },
        "dir": str(root()),
    }


def apply_profile(cfg, profile: str) -> dict:
    chosen = PROFILES.get(profile)
    if not chosen:
        raise ValueError(f"unknown profile {profile}")
    cfg["speech_model"] = chosen["speech"]
    cfg["romanian_model"] = chosen["romanian"]
    cfg["diarization"] = chosen["diarization"]
    cfg["vad_model"] = chosen["vad"]
    return cfg


def install_profile(cfg, profile: str, log=print) -> bool:
    chosen = PROFILES[profile]
    ok = install("speech", chosen["speech"], log)
    if chosen["romanian"]:
        ok = install("romanian", chosen["romanian"], log) and ok
    if chosen["vad"]:
        ok = install("vad", chosen["vad"], log) and ok
    if chosen["diarization"]:
        ok = install("diarization", chosen["diarization"], log) and ok
    apply_profile(cfg, profile)
    return ok
