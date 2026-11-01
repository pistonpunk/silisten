import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np

from . import audio, config
from .engine import Engine, attach_speakers, compose


class App:
    def __init__(self, cfg):
        self.cfg = cfg
        self.tok = config.token()
        self.engine = Engine(cfg)
        self.lock = threading.RLock()
        self.recorder = None
        self.status = "idle"
        self.text = ""
        self.segments = []
        self.partial = ""
        self.error = None
        self.progress = None
        self.phase = ""
        self.reveal = 0
        self.append = False
        self.duration = 0.0
        self._last_partial_bytes = -1
        self._partial_busy = False

    def boot(self):
        self.engine.warm()

    def toggle(self):
        if self.status == "listening":
            self.stop_recording()
        elif self.status in ("thinking", "idle", "done", "error"):
            self.start_recording(append=False)

    def start_recording(self, append=False):
        with self.lock:
            if self.status in ("listening", "thinking"):
                return
            self.error = None
            self.progress = None
            self.phase = ""
            self.append = bool(append)
            if not append:
                self.text = ""
                self.segments = []
            self.partial = ""
            self.duration = 0.0
            self.status = "listening"
            self.reveal += 1
            self._last_partial_bytes = -1
        recorder = audio.Recorder(self.cfg.get("input_device") or "default")
        self.recorder = recorder
        recorder.start()
        threading.Thread(target=self._partial_loop, args=(recorder,), daemon=True).start()

    def stop_recording(self):
        recorder = self.recorder
        with self.lock:
            if self.status != "listening":
                return
            self.status = "thinking"
            self.phase = "transcribing"
            self.partial = ""
        data = recorder.stop() if recorder else np.zeros(0, dtype=np.float32)
        self.duration = data.size / audio.RATE
        threading.Thread(target=self._finish_listening, args=(data,), daemon=True).start()

    def _partial_loop(self, recorder):
        while not self._stop_partials(recorder):
            time.sleep(1.1)
            if self._stop_partials(recorder) or self._partial_busy:
                continue
            if recorder.duration < 0.8 or recorder.duration > 28:
                continue
            if recorder.nbytes == self._last_partial_bytes:
                continue
            self._last_partial_bytes = recorder.nbytes
            data = recorder.audio()
            self._partial_busy = True
            try:
                result = self.engine.transcribe(data, language=self.cfg.get("language"))
                with self.lock:
                    if self.status == "listening":
                        self.partial = result["text"]
                        self.duration = recorder.duration
            except Exception:
                pass
            finally:
                self._partial_busy = False

    def _stop_partials(self, recorder):
        return self.status != "listening" or self.recorder is not recorder

    def _finish_listening(self, data):
        try:
            if data.size < audio.RATE * 0.25:
                with self.lock:
                    self.status = "done"
                    self.phase = ""
                    self.reveal += 1
                return
            spans = self.engine.speech_spans(data)
            if spans is not None:
                if not spans:
                    self.commit([])
                    return
                start = max(0, spans[0][0] - int(0.15 * audio.RATE))
                end = min(data.size, spans[-1][1] + int(0.15 * audio.RATE))
                data = data[start:end]
            else:
                data = audio.trim_silence(data)
            result = self.engine.transcribe(
                data, language=self.cfg.get("language"), long_form=data.size > 29 * audio.RATE
            )
            segments = result["segments"]
            if self.cfg.get("diarize") and self.engine.diar.state == "ready":
                self.set_phase("identifying speakers")
                turns = self.engine.diar.turns(data)
                attach_speakers(segments, turns)
            self.commit(segments)
        except Exception as e:
            with self.lock:
                self.status = "error"
                self.phase = ""
                self.error = str(e)[:400]
                self.reveal += 1

    def commit(self, segments):
        with self.lock:
            offset = max((s["end"] for s in self.segments), default=0.0) if self.append else 0.0
            fresh = [{**s, "start": s["start"] + offset, "end": s["end"] + offset} for s in segments]
            self.segments = (self.segments if self.append else []) + fresh
            self.text = compose(self.segments)
            self.status = "done"
            self.phase = ""
            self.progress = None
            self.error = None
            self.reveal += 1

    def upload(self, path, append=False):
        with self.lock:
            if self.status in ("listening", "thinking"):
                return False
            self.status = "thinking"
            self.phase = "decoding"
            self.progress = 0.0
            self.error = None
            self.append = bool(append)
            if not append:
                self.text = ""
                self.segments = []
            self.partial = ""
            self.reveal += 1
        threading.Thread(target=self._file_job, args=(path,), daemon=True).start()
        return True

    def _file_job(self, path):
        try:
            data = audio.decode_file(path)
            if data.size == 0:
                raise RuntimeError("no audio track in that file")
            self.duration = data.size / audio.RATE
            self.set_phase("transcribing")
            segments = self.engine.transcribe_file(
                data, language=self.cfg.get("language"), progress=self.set_progress
            )
            if self.cfg.get("diarize") and self.engine.diar.state == "ready":
                self.set_phase("identifying speakers")
                with self.lock:
                    self.progress = None
                turns = self.engine.diar.turns(data)
                attach_speakers(segments, turns)
            self.commit(segments)
        except Exception as e:
            with self.lock:
                self.status = "error"
                self.phase = ""
                self.progress = None
                self.error = str(e)[:400]
                self.reveal += 1

    def set_phase(self, phase):
        with self.lock:
            self.phase = phase

    def set_progress(self, value):
        with self.lock:
            self.progress = value

    def clear(self):
        with self.lock:
            self.status = "idle"
            self.text = ""
            self.segments = []
            self.partial = ""
            self.error = None
            self.progress = None
            self.phase = ""
            self.duration = 0.0

    def update_config(self, patch):
        allowed = {"shortcut", "language", "diarize", "input_device", "diarization_threshold", "diarization_dir", "model"}
        changed = {k: v for k, v in patch.items() if k in allowed}
        if "language" in changed and changed["language"] in ("", "auto"):
            changed["language"] = None
        if "diarize" in changed:
            changed["diarize"] = bool(changed["diarize"])
        self.cfg.update(changed)
        config.save(self.cfg)
        if "diarization_threshold" in changed or "diarization_dir" in changed:
            threading.Thread(target=self.engine.diar.load, daemon=True).start()
        return None

    def snapshot(self):
        with self.lock:
            recorder = self.recorder
            return {
                "status": self.status,
                "text": self.text,
                "segments": self.segments,
                "partial": self.partial,
                "error": self.error,
                "progress": self.progress,
                "phase": self.phase,
                "duration": recorder.duration if recorder and self.status == "listening" else self.duration,
                "level": recorder.level if recorder and self.status == "listening" else 0.0,
                "reveal": self.reveal,
                "append": self.append,
                "shortcut": self.cfg["shortcut"],
                "engine": {
                    "state": self.engine.state,
                    "device": self.engine.device,
                    "gpu": self.engine.using_gpu,
                    "error": self.engine.error,
                },
                "diarizer": {"state": self.engine.diar.state, "error": self.engine.diar.error},
                "config": {
                    "language": self.cfg.get("language"),
                    "diarize": self.cfg.get("diarize"),
                    "input_device": self.cfg.get("input_device"),
                },
            }


class Handler(BaseHTTPRequestHandler):
    app = None

    def log_message(self, *args):
        pass

    def _send(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self):
        return self.headers.get("X-Silisten-Token") == self.app.tok

    def do_GET(self):
        if not self._authorized():
            return self._send({"error": "unauthorized"}, 401)
        if self.path == "/state":
            return self._send(self.app.snapshot())
        if self.path == "/config":
            return self._send(self.app.cfg)
        if self.path == "/sources":
            return self._send(audio.list_sources())
        if self.path == "/quit":
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return self._send({"ok": True})
        self._send({"error": "not found"}, 404)

    def do_POST(self):
        if not self._authorized():
            return self._send({"error": "unauthorized"}, 401)
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self._send({"error": "bad json"}, 400)
        if self.path == "/toggle":
            self.app.toggle()
        elif self.path == "/record/start":
            self.app.start_recording(bool(body.get("append")))
        elif self.path == "/record/stop":
            self.app.stop_recording()
        elif self.path == "/clear":
            self.app.clear()
        elif self.path == "/upload":
            path = body.get("path")
            if not path:
                return self._send({"error": "missing path"}, 400)
            if not self.app.upload(path, bool(body.get("append"))):
                return self._send({"error": "busy"}, 409)
        elif self.path == "/config":
            problem = self.app.update_config(body)
            if problem:
                return self._send({"error": problem}, 400)
        else:
            return self._send({"error": "not found"}, 404)
        self._send(self.app.snapshot())


def create_app(cfg=None):
    cfg = cfg or config.load()
    app = App(cfg)
    handler = type("BoundHandler", (Handler,), {"app": app})
    httpd = ThreadingHTTPServer(("127.0.0.1", int(cfg.get("port") or 8756)), handler)
    httpd.daemon_threads = True
    return app, httpd
