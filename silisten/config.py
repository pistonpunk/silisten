import json
import os
import secrets
from pathlib import Path

DIR = Path(os.environ.get("SILISTEN_CONFIG_DIR", Path.home() / ".config" / "silisten"))
PATH = DIR / "config.json"
TOKEN_PATH = DIR / "token"

DEFAULTS = {
    "shortcut": "Shift+Tab+Q",
    "language": None,
    "input_device": "default",
    "model": "openai/whisper-large-v3",
    "diarization_model": "pyannote/speaker-diarization-3.1",
    "diarize": True,
    "hf_token": None,
    "port": 8756,
}


def load():
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(PATH.read_text()))
    except (OSError, ValueError):
        pass
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


def hf_token(cfg):
    return (
        cfg.get("hf_token")
        or os.environ.get("HF_TOKEN")
        or os.environ.get("HUGGING_FACE_HUB_TOKEN")
        or _cached_hf_token()
    )


def _cached_hf_token():
    try:
        return (Path.home() / ".cache" / "huggingface" / "token").read_text().strip() or None
    except OSError:
        return None
