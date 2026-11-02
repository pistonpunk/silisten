import json
import os
import secrets
from pathlib import Path

DIR = Path(os.environ.get("SILISTEN_CONFIG_DIR", Path.home() / ".config" / "silisten"))
PATH = DIR / "config.json"
TOKEN_PATH = DIR / "token"
MODELS_DIR = Path(
    os.environ.get("SILISTEN_MODELS_DIR", Path.home() / ".local" / "share" / "silisten" / "models")
)

DEFAULTS = {
    "shortcut": "Ctrl+Delete",
    "language": None,
    "input_device": "default",
    "speech_model": "large-v3",
    "romanian_model": "fra-piz-turbo",
    "vad_model": "silero",
    "diarization": "pyannote-campplus",
    "diarize": True,
    "auto_stop": False,
    "auto_stop_seconds": 1.6,
    "vad_threshold": 0.5,
    "diarization_threshold": 0.7,
    "models_dir": None,
    "auto_download": True,
    "port": 8756,
}

ALIASES = {
    "model": "speech_model",
    "diarization_dir": "models_dir",
}


def load():
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(PATH.read_text()))
    except (OSError, ValueError):
        pass
    return migrate(cfg)


def migrate(cfg):
    for old, new in ALIASES.items():
        if old in cfg:
            cfg.setdefault(new, cfg.pop(old))
    if cfg.get("romanian_model") and "FraPiz" in str(cfg["romanian_model"]):
        cfg["romanian_model"] = "fra-piz-turbo"
    return cfg


def save(cfg):
    DIR.mkdir(parents=True, exist_ok=True)
    tmp = PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=2) + "\n")
    tmp.chmod(0o600)
    tmp.replace(PATH)


def token():
    DIR.mkdir(parents=True, exist_ok=True)
    try:
        tok = TOKEN_PATH.read_text().strip()
        if tok:
            return tok
    except OSError:
        pass
    tok = secrets.token_hex(16)
    TOKEN_PATH.write_text(tok + "\n")
    TOKEN_PATH.chmod(0o600)
    return tok


def models_dir():
    cfg = load()
    return Path(cfg.get("models_dir") or MODELS_DIR)
