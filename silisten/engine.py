import re
import threading
from pathlib import Path

import numpy as np
import torch

from . import config

RATE = 16000


SEGMENTATION_FILE = "sherpa-onnx-pyannote-segmentation-3-0/model.onnx"
EMBEDDING_FILE = "emb.onnx"
VAD_FILE = "silero_vad.onnx"

GAP = 0.4
MIN_SPEECH = 0.25


class Diarizer:
    def __init__(self, cfg):
        self.cfg = cfg
        self.pipe = None
        self.state = "idle"
        self.error = None
        self._lock = threading.Lock()

    def model_dir(self):
        return Path(self.cfg.get("diarization_dir") or config.MODELS_DIR)

    def load(self):
        base = self.model_dir()
        segmentation = base / SEGMENTATION_FILE
        embedding = base / EMBEDDING_FILE
        missing = [p.name for p in (segmentation, embedding) if not p.is_file()]
        if missing:
            self.state = "unavailable"
            self.error = f"missing local models in {base}: {', '.join(missing)} - run: silisten setup"
            return
        try:
            import sherpa_onnx

            segmentation_config = sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
                pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(model=str(segmentation)),
                num_threads=4,
            )
            embedding_config = sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(embedding), num_threads=4)
            clustering = sherpa_onnx.FastClusteringConfig(
                num_clusters=-1, threshold=float(self.cfg.get("diarization_threshold", 0.7))
            )
            self.pipe = sherpa_onnx.OfflineSpeakerDiarization(
                sherpa_onnx.OfflineSpeakerDiarizationConfig(
                    segmentation=segmentation_config, embedding=embedding_config, clustering=clustering
                )
            )
            self.state = "ready"
            self.error = None
        except Exception as e:
            self.state = "error"
            self.error = str(e).splitlines()[0][:300]

    def turns(self, waveform):
        if not self.pipe or waveform.size < RATE:
            return []
        audio = np.ascontiguousarray(waveform, dtype=np.float32)
        with self._lock:
            result = self.pipe.process(audio)
        return [(float(s.start), float(s.end), str(s.speaker)) for s in result.sort_by_start_time()]


ROMANIAN_MODEL = "FraPiz/whisper-large-v3-turbo-moldovan-romanian"
_runs = threading.Lock()


def _make_pipe(name, gpu):
    from transformers import pipeline

    dtype = torch.float16 if gpu else torch.float32
    kwargs = dict(model=name, device="cuda" if gpu else "cpu")
    try:
        return pipeline("automatic-speech-recognition", dtype=dtype, **kwargs)
    except TypeError:
        return pipeline("automatic-speech-recognition", torch_dtype=dtype, **kwargs)


def _run(pipe, waveform, kwargs):
    with _runs, torch.inference_mode():
        return pipe(waveform, **kwargs)


RO_CHARS = set("ăâîșțĂÂÎȘȚ")
RO_WORDS = {"și", "să", "nu", "este", "sunt", "care", "pentru", "dar", "din", "pe", "cu", "la", "un", "o", "eu", "tu", "el", "ea", "noi", "voi", "ei", "sau", "mai", "foarte", "acest", "aceasta", "că", "să", "am", "ai", "are", "avem"}


def _looks_romanian(text):
    if any(ch in RO_CHARS for ch in text):
        return True
    words = [w.strip(".,!?;:\"'").lower() for w in text.split()]
    words = [w for w in words if w]
    if not words:
        return True
    hits = sum(1 for w in words if w in RO_WORDS)
    return hits / len(words) >= 0.2 or hits >= 3


def _degenerate(text):
    if len(text) < 24:
        return False
    words = [w for w in text.split() if w]
    if words:
        head, tail = words[:-1], words[1:]
        if head and sum(1 for a, b in zip(head, tail) if a == b) / len(head) > 0.6:
            return True
        if len(set(map(str.lower, words))) / len(words) < 0.15:
            return True
    compact = text.replace(" ", "").lower()
    if len(set(compact)) / len(compact) < 0.08:
        return True
    if re.search(r"(..+?)\1{4,}", compact):
        return True


def _load_vad(cfg):
    path = Path(cfg.get("diarization_dir") or config.MODELS_DIR) / VAD_FILE
    if not path.is_file():
        return None
    try:
        import sherpa_onnx

        vad_config = sherpa_onnx.VadModelConfig()
        vad_config.silero_vad.model = str(path)
        vad_config.silero_vad.threshold = float(cfg.get("vad_threshold", 0.5))
        vad_config.silero_vad.min_silence_duration = 0.35
        vad_config.silero_vad.min_speech_duration = MIN_SPEECH
        vad_config.silero_vad.max_speech_duration = 30
        vad_config.sample_rate = RATE
        vad_config.num_threads = 2
        return sherpa_onnx.VadModel.create(vad_config)
    except Exception:
        return None


class Engine:
    def __init__(self, cfg):
        self.cfg = cfg
        self.state = "loading"
        self.error = None
        self.device = None
        self.using_gpu = False
        self._pipe = None
        self._ro_pipe = None
        self._ro_loaded = False
        self._lock = threading.Lock()
        self._load_lock = threading.Lock()
        self.vad = _load_vad(cfg)
        self.diar = Diarizer(cfg)

    def warm(self):
        threading.Thread(target=self.load, daemon=True).start()

    def load(self):
        try:
            from transformers import pipeline

            gpu = torch.cuda.is_available()
            device = "cuda" if gpu else "cpu"
            dtype = torch.float16 if gpu else torch.float32
            kwargs = dict(model=self.cfg["model"], device=device)
            try:
                pipe = pipeline("automatic-speech-recognition", dtype=dtype, **kwargs)
            except TypeError:
                pipe = pipeline("automatic-speech-recognition", torch_dtype=dtype, **kwargs)
            with self._lock:
                self._pipe = pipe
                self.using_gpu = gpu
                self.device = torch.cuda.get_device_name(0) if gpu else "CPU"
                self.state = "ready"
        except Exception as e:
            self.state = "error"
            self.error = str(e).splitlines()[0][:400]
        if self.cfg.get("diarize"):
            self.diar.load()

    def _language_model(self, language):
        if not language or language != "ro":
            return None
        if self.cfg.get("romanian_model_off"):
            return None
        with self._load_lock:
            if not self._ro_loaded:
                self._ro_loaded = True
                try:
                    self._ro_pipe = _make_pipe(
                        self.cfg.get("romanian_model") or ROMANIAN_MODEL, self.using_gpu
                    )
                except Exception as e:
                    self._ro_pipe = None
                    self.error = f"romanian model unavailable: {str(e).splitlines()[0][:200]}"
        return self._ro_pipe

    def ensure_ready(self):
        if self._pipe is not None:
            return
        with self._load_lock:
            if self._pipe is None:
                self.load()
        if self._pipe is None:
            raise RuntimeError(self.error or "speech model failed to load")

    def speech_spans(self, waveform):
        if self.vad is None:
            return None
        vad = self.vad
        window = vad.window_size()
        with self._lock:
            vad.reset()
            spans, start = [], None
            for offset in range(0, waveform.size - window + 1, window):
                speech = vad.is_speech(waveform[offset: offset + window])
                if speech and start is None:
                    start = offset
                elif not speech and start is not None:
                    spans.append((start, offset))
                    start = None
            if start is not None:
                spans.append((start, waveform.size))
        merged = []
        for begin, end in spans:
            if merged and begin - merged[-1][1] < GAP * RATE:
                merged[-1] = (merged[-1][0], end)
            else:
                merged.append((begin, end))
        return [(a, b) for a, b in merged if b - a >= MIN_SPEECH * RATE]

    def transcribe(self, waveform, language=None, long_form=False):
        if waveform.size == 0:
            return {"text": "", "segments": []}
        self.ensure_ready()
        kwargs = {"return_timestamps": True}
        gen = {}
        if language:
            gen["language"] = language
        if gen:
            kwargs["generate_kwargs"] = gen
        if long_form:
            kwargs["chunk_length_s"] = 30
            kwargs["batch_size"] = 8
        spans = self.speech_spans(waveform)
        if spans is not None and not spans:
            return {"text": "", "segments": [], "silent": True}
        out = None
        pipe = self._language_model(language)
        if pipe is not None:
            try:
                candidate = _run(pipe, waveform, kwargs)
                text = candidate.get("text", "")
                if not _degenerate(text) and _looks_romanian(text):
                    out = candidate
            except Exception:
                out = None
        if out is None:
            out = _run(self._pipe, waveform, kwargs)
        duration = waveform.size / RATE
        return {"text": out.get("text", "").strip(), "segments": _to_segments(out, duration)}

    def transcribe_file(self, waveform, language=None, progress=None):
        window = 300 * RATE
        total = max(1, (waveform.size + window - 1) // window)
        segments = []
        for i in range(total):
            part = waveform[i * window:(i + 1) * window]
            spans = self.speech_spans(part)
            if spans is not None:
                if not spans:
                    if progress:
                        progress((i + 1) / total)
                    continue
                part = part[max(0, spans[0][0] - int(0.15 * RATE)): min(part.size, spans[-1][1] + int(0.15 * RATE))]
            result = self.transcribe(part, language=language, long_form=True)
            offset = i * window / RATE
            for seg in result["segments"]:
                segments.append({**seg, "start": seg["start"] + offset, "end": seg["end"] + offset})
            if progress:
                progress((i + 1) / total)
        return segments


def _to_segments(out, duration):
    segments = []
    for chunk in out.get("chunks") or []:
        start, end = chunk.get("timestamp") or (0.0, None)
        text = (chunk.get("text") or "").strip()
        if text:
            segments.append(
                {
                    "start": float(start or 0.0),
                    "end": float(end if end is not None else duration),
                    "text": text,
                    "speaker": None,
                }
            )
    if not segments and out.get("text", "").strip():
        segments = [{"start": 0.0, "end": float(duration), "text": out["text"].strip(), "speaker": None}]
    return segments


def attach_speakers(segments, turns):
    if not turns:
        return segments
    names = {}
    for seg in segments:
        best, best_overlap = None, 0.0
        for start, end, label in turns:
            overlap = min(end, seg["end"]) - max(start, seg["start"])
            if overlap > best_overlap:
                best, best_overlap = label, overlap
        if best is None:
            mid = (seg["start"] + seg["end"]) / 2
            nearest, distance = None, 1.5
            for start, end, label in turns:
                gap = min(abs(mid - start), abs(mid - end))
                if gap <= distance:
                    nearest, distance = label, gap
            best = nearest
        if best is not None:
            seg["speaker"] = names.setdefault(best, len(names) + 1)
    return segments


def compose(segments):
    segments = [s for s in segments if s.get("text", "").strip()]
    if not segments:
        return ""
    speakers = {s.get("speaker") for s in segments if s.get("speaker")}
    if len(speakers) <= 1:
        return " ".join(s["text"].strip() for s in segments).strip()
    out, current = [], object()
    for seg in segments:
        speaker = seg.get("speaker")
        text = seg["text"].strip()
        if speaker != current:
            out.append(f"Speaker {speaker}: {text}" if speaker else text)
            current = speaker
        else:
            out[-1] += " " + text
    return "\n\n".join(out).strip()
