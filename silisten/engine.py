import threading
from pathlib import Path

import numpy as np
import torch

from . import config

RATE = 16000


SEGMENTATION_FILE = "sherpa-onnx-pyannote-segmentation-3-0/model.onnx"
EMBEDDING_FILE = "emb.onnx"


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


class Engine:
    def __init__(self, cfg):
        self.cfg = cfg
        self.state = "loading"
        self.error = None
        self.device = None
        self.using_gpu = False
        self._pipe = None
        self._lock = threading.Lock()
        self._load_lock = threading.Lock()
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

    def ensure_ready(self):
        if self._pipe is not None:
            return
        with self._load_lock:
            if self._pipe is None:
                self.load()
        if self._pipe is None:
            raise RuntimeError(self.error or "speech model failed to load")

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
        with self._lock, torch.inference_mode():
            out = self._pipe(waveform, **kwargs)
        duration = waveform.size / RATE
        return {"text": out.get("text", "").strip(), "segments": _to_segments(out, duration)}

    def transcribe_file(self, waveform, language=None, progress=None):
        window = 300 * RATE
        total = max(1, (waveform.size + window - 1) // window)
        segments = []
        for i in range(total):
            part = waveform[i * window:(i + 1) * window]
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
