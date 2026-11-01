import subprocess
import threading

import numpy as np

RATE = 16000
CHUNK = RATE // 10


class Recorder:
    def __init__(self, device="default"):
        self.device = device
        self._pcm = bytearray()
        self._level = 0.0
        self._stop = threading.Event()
        self._proc = None
        self._thread = None
        self.error = None

    def start(self):
        self._pcm = bytearray()
        self._level = 0.0
        self.error = None
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        proc = self._proc
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
        if self._thread:
            self._thread.join(timeout=2)
        return self.audio()

    def audio(self):
        if not self._pcm:
            return np.zeros(0, dtype=np.float32)
        return np.frombuffer(bytes(self._pcm), dtype=np.int16).astype(np.float32) / 32768.0

    @property
    def duration(self):
        return len(self._pcm) / 2 / RATE

    @property
    def nbytes(self):
        return len(self._pcm)

    @property
    def level(self):
        return self._level

    @property
    def running(self):
        return bool(self._thread and self._thread.is_alive())

    @staticmethod
    def _arecord(device):
        return ["arecord", "-q", "-D", device, "-f", "S16_LE", "-r", str(RATE), "-c", "1", "-t", "raw"]

    @staticmethod
    def _pw_record():
        return ["pw-record", "--rate", str(RATE), "--channels", "1", "--format", "s16", "-"]

    def _spawn(self):
        proc = subprocess.Popen(self._arecord(self.device), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            proc.wait(timeout=0.6)
        except subprocess.TimeoutExpired:
            return proc
        for cmd in (self._pw_record(), self._arecord("default")):
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            try:
                proc.wait(timeout=0.6)
            except subprocess.TimeoutExpired:
                return proc
        raise RuntimeError("no working microphone recorder (arecord / pw-record)")

    def _run(self):
        try:
            self._proc = self._spawn()
        except Exception as e:
            self.error = str(e)
            return
        buf = b""
        while not self._stop.is_set():
            data = self._proc.stdout.read(CHUNK * 2)
            if not data:
                break
            self._pcm += data
            buf = (buf + data)[-(CHUNK * 2):]
            samples = np.frombuffer(buf, dtype=np.int16).astype(np.float32) / 32768.0
            if samples.size:
                rms = float(np.sqrt(np.mean(samples**2)))
                self._level = min(1.0, max(0.0, (rms - 0.008) * 9.0))
        if self._proc and self._proc.poll() not in (None, 0, -15):
            self.error = "recorder exited unexpectedly"


def decode_file(path):
    cmd = ["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(RATE), "-"]
    try:
        out = subprocess.run(cmd, capture_output=True, check=False)
    except OSError as e:
        raise RuntimeError(f"ffmpeg not available: {e}") from e
    if out.returncode != 0:
        raise RuntimeError(out.stderr.decode(errors="replace").strip() or "ffmpeg failed to decode the file")
    return np.frombuffer(out.stdout, dtype=np.float32).copy()


def trim_silence(x, threshold=0.004):
    if x.size == 0:
        return x
    loud = np.flatnonzero(np.abs(x) > threshold)
    if loud.size == 0:
        return x[:0]
    return x[max(0, loud[0] - RATE // 10): min(x.size, loud[-1] + RATE // 10)]
