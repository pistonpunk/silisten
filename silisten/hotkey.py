import glob
import os
import select
import struct
import threading
from pathlib import Path

EVENT = struct.Struct("llHHi")

FAMILY = {
    "shift": "shift",
    "ctrl": "ctrl",
    "control": "ctrl",
    "alt": "alt",
    "option": "alt",
    "super": "super",
    "meta": "super",
    "win": "super",
    "cmd": "super",
}

MODIFIERS = {
    "shift": frozenset({42, 54}),
    "ctrl": frozenset({29, 97}),
    "alt": frozenset({56, 100}),
    "super": frozenset({125, 126}),
}

KEYS = {
    "tab": 15, "space": 57, "enter": 28, "esc": 1, "escape": 1, "backspace": 14,
    "a": 30, "b": 48, "c": 46, "d": 32, "e": 18, "f": 33, "g": 34, "h": 35, "i": 23,
    "j": 36, "k": 37, "l": 38, "m": 50, "n": 49, "o": 24, "p": 25, "q": 16, "r": 19,
    "s": 31, "t": 20, "u": 22, "v": 47, "w": 17, "x": 45, "y": 21, "z": 44,
    "1": 2, "2": 3, "3": 4, "4": 5, "5": 6, "6": 7, "7": 8, "8": 9, "9": 10, "0": 11,
    "f1": 59, "f2": 60, "f3": 61, "f4": 62, "f5": 63, "f6": 64,
    "f7": 65, "f8": 66, "f9": 67, "f10": 68, "f11": 87, "f12": 88,
    "minus": 12, "equal": 13, "comma": 51, "period": 52, "slash": 53, "backslash": 43, "grave": 41,
}


def parse_chord(chord):
    parts = [p.strip().lower() for p in chord.replace(" ", "").split("+") if p.strip()]
    if not parts:
        raise ValueError("empty shortcut")
    if len(parts) > 4:
        raise ValueError("at most 4 keys in a shortcut")
    requirements = []
    for part in parts[:-1]:
        if part in FAMILY:
            requirement = MODIFIERS[FAMILY[part]]
        elif part in KEYS:
            requirement = frozenset({KEYS[part]})
        else:
            raise ValueError(f"unknown key '{part}'")
        if requirement not in requirements:
            requirements.append(requirement)
    trigger = parts[-1]
    if trigger in FAMILY:
        raise ValueError("shortcut must end with a regular key")
    if trigger not in KEYS:
        raise ValueError(f"unknown key '{trigger}'")
    return requirements, KEYS[trigger]


def _has_key(words, code):
    index = len(words) - 1 - code // 64
    return 0 <= index < len(words) and bool(words[index] >> (code % 64) & 1)


def _keyboards():
    paths = []
    for path in sorted(glob.glob("/dev/input/event*"), key=lambda p: int(p.rsplit("event", 1)[-1] or 0)):
        base = os.path.basename(path)
        try:
            words = [int(w, 16) for w in Path(f"/sys/class/input/{base}/device/capabilities/key").read_text().split()]
        except (OSError, ValueError):
            continue
        if _has_key(words, 30) or _has_key(words, 31):
            paths.append(path)
    return paths


class HotkeyListener:
    def __init__(self, chord, callback):
        self.chord = chord
        self.callback = callback
        self.requirements, self.trigger = parse_chord(chord)
        self.status = "starting"
        self.reason = ""
        self._fds = {}
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=1)
        for fd in self._fds:
            try:
                os.close(fd)
            except OSError:
                pass
        self._fds = {}

    def _run(self):
        denied = []
        for path in _keyboards():
            try:
                self._fds[os.open(path, os.O_RDONLY | os.O_NONBLOCK)] = path
            except PermissionError:
                denied.append(path)
        if self._fds:
            self.status = "ok"
            self.reason = ""
        elif denied:
            self.status = "denied"
            self.reason = "input access denied - run: silisten setup"
        else:
            self.status = "error"
            self.reason = "no keyboard found in /dev/input"

        pressed = set()
        while not self._stop.is_set() and self._fds:
            try:
                ready, _, _ = select.select(list(self._fds), [], [], 0.3)
            except (OSError, ValueError):
                break
            for fd in ready:
                try:
                    data = os.read(fd, EVENT.size * 64)
                except OSError:
                    continue
                for offset in range(0, len(data) - EVENT.size + 1, EVENT.size):
                    _, _, etype, code, value = EVENT.unpack_from(data, offset)
                    if etype != 1:
                        continue
                    if value == 0:
                        pressed.discard(code)
                    elif value == 1:
                        pressed.add(code)
                        if code == self.trigger and all(pressed & req for req in self.requirements):
                            threading.Thread(target=self.callback, daemon=True).start()
