from __future__ import annotations

import gc
import json
import math
import os
import re
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from .config import MODELS, Settings, atomic_text
from .hardware import Plan
from .media import check_cancel, extract_chunk


@dataclass
class Segment:
    start: float
    end: float
    text: str
    avg_logprob: float | None = None
    no_speech_prob: float | None = None
    review: bool = False


def clean_zh(text: str) -> str:
    text = re.sub(r"\s+", " ", text.strip())
    text = re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", text)
    text = re.sub(r"\s+([，。！？；：、）》】」』])", r"\1", text)
    return re.sub(r"([（《【「『])\s+", r"\1", text)


def timestamp(value: float, sep=","):
    ms = max(0, round(value * 1000))
    hours, ms = divmod(ms, 3600000)
    minutes, ms = divmod(ms, 60000)
    seconds, ms = divmod(ms, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02}{sep}{ms:03}"


def paragraphs(segments: list[Segment]) -> str:
    result, buffer = [], ""
    last_end = 0
    for seg in segments:
        if buffer and (seg.start - last_end > 1.8 or len(buffer) >= 180):
            result.append(buffer)
            buffer = ""
        if buffer and buffer[-1:].isascii() and seg.text[:1].isascii() and buffer[-1:].isalnum():
            buffer += " "
        buffer += seg.text
        last_end = seg.end
    if buffer:
        result.append(buffer)
    return "\n\n".join(result) + "\n"


def subtitle_cues(segments: list[Segment]):
    """Split long Chinese cues at punctuation, preserving every recognized character."""
    for seg in segments:
        text = seg.text.strip()
        pieces = []
        while len(text) > 42:
            cut = max(text.rfind(p, 16, 42) for p in "，。！？；、 ")
            cut = cut + 1 if cut >= 16 else 36
            pieces.append(text[:cut])
            text = text[cut:]
        if text:
            pieces.append(text)
        count = max(1, sum(len(p) for p in pieces))
        cursor = seg.start
        for i, piece in enumerate(pieces):
            end = seg.end if i == len(pieces) - 1 else cursor + (seg.end - seg.start) * len(piece) / count
            yield cursor, max(cursor + 0.001, end), piece.strip()
            cursor = end


def write_outputs(folder: Path, segments: list[Segment], metadata: dict, language="zh"):
    prefix = "transcript_" + language
    atomic_text(folder / (prefix + ".txt"), paragraphs(segments), "utf-8-sig")
    cues = list(subtitle_cues(segments))
    srt = "\n".join(f"{i}\n{timestamp(start)} --> {timestamp(end)}\n{text}\n" for i, (start, end, text) in enumerate(cues, 1))
    atomic_text(folder / (prefix + ".srt"), srt, "utf-8-sig")
    report = {**metadata, "language": language, "segments": [asdict(s) for s in segments]}
    atomic_text(folder / (prefix + ".json"), json.dumps(report, ensure_ascii=False, indent=2))
    flagged = [s for s in segments if s.review]
    review = "Các đoạn nên nghe lại (chỉ là chỉ báo từ mô hình, không phải xác suất đúng):\n\n"
    if segments and all(s.avg_logprob is None for s in segments):
        review += "SenseVoice không cung cấp điểm độ tin cậy. Cần nghe lại tên riêng và thuật ngữ.\n\n"
    review += "\n".join(f"{timestamp(s.start)} — {timestamp(s.end)}  {s.text}" for s in flagged)
    if not flagged:
        review += "Không có đoạn bị gắn cờ. Điều này không bảo đảm transcript chính xác tuyệt đối.\n"
    atomic_text(folder / (prefix + "_review.txt"), review, "utf-8-sig")


class Transcriber:
    chunk_seconds = 300.0
    overlap = 2.0

    def close(self):
        self.model = None
        gc.collect()

    def __init__(self, cfg: Settings, plan: Plan, emit, cancel):
        self.cfg, self.plan, self.emit, self.cancel = cfg, plan, emit, cancel
        self.model = None
        self.model_path = None
        self.progress_callback = None

    def _download_model(self):
        from huggingface_hub import snapshot_download
        from tqdm.auto import tqdm
        folder = Path(self.cfg.cache_dir) / self.plan.model
        marker = folder / "biliscribe-ready.json"
        required = ("model.bin", "config.json", "tokenizer.json")
        if marker.exists() and all((folder / name).is_file() for name in required):
            return folder
        try:
            # Reuse the original TranscriptTool's standard Hugging Face cache when complete.
            existing = Path(snapshot_download(MODELS[self.plan.model][0], local_files_only=True, token=False))
            if all((existing / name).is_file() for name in required):
                self.emit("log", message=f"Dùng mô hình {self.plan.model} đã có trong bộ nhớ đệm Hugging Face.")
                return existing
        except Exception:
            pass
        emit, cancel = self.emit, self.cancel
        emit("model", message=f"Tải mô hình {self.plan.model} ({MODELS[self.plan.model][1]}), chỉ cần tải một lần.", progress=-1)
        class Progress(tqdm):
            def __init__(self, *args, **kwargs):
                kwargs["disable"] = False
                self.last_notice = 0.0
                super().__init__(*args, **kwargs)
            def display(self, *args, **kwargs):
                check_cancel(cancel)
                now = time.monotonic()
                if now - self.last_notice > 0.4:
                    self.last_notice = now
                    if self.total and self.total > 1000000:
                        emit("model", message=f"Đang tải mô hình: {self.n / 2**20:.0f} / {self.total / 2**20:.0f} MB", progress=min(99, 100 * self.n / self.total))
            def update(self, n=1):
                check_cancel(cancel)
                return super().update(n)
        # Anonymous downloads only; never use a stored Hugging Face account token.
        snapshot_download(MODELS[self.plan.model][0], local_dir=str(folder), token=False, allow_patterns=["model.bin", "config.json", "tokenizer.json", "vocabulary.*", "preprocessor_config.json"], max_workers=3, tqdm_class=Progress)
        check_cancel(self.cancel)
        if not all((folder / name).is_file() for name in required):
            raise RuntimeError("Mô hình tải chưa đủ. Hãy thử lại để tải tiếp.")
        atomic_text(marker, json.dumps({"repo": MODELS[self.plan.model][0]}))
        return folder

    def load(self):
        if self.model is not None:
            return
        from faster_whisper import WhisperModel
        if self.model_path is None:
            self.model_path = self._download_model()
        check_cancel(self.cancel)
        self.emit("model", message=f"Nạp {self.plan.model} · {self.plan.device.upper()} · {self.plan.compute_type}", progress=-1)
        self.model = WhisperModel(str(self.model_path), device=self.plan.device, device_index=self.plan.gpu_index, compute_type=self.plan.compute_type, cpu_threads=self.plan.threads, num_workers=1, local_files_only=True)
        self.emit("plan", **asdict(self.plan))

    def _fallback(self, exc):
        msg = str(exc).lower()
        resource_error = any(s in msg for s in ("memory", "cuda", "cublas", "cudnn", "alloc", "gpu", "compute type"))
        if not resource_error:
            return False
        if self.plan.batch_size > 1:
            self.plan = replace(self.plan, batch_size=1)
            self.emit("log", message="Thiếu bộ nhớ GPU: giảm batch xuống 1 và thử lại đoạn hiện tại.")
        elif self.plan.device == "cuda":
            self.model = None
            gc.collect()
            self.plan = replace(self.plan, device="cpu", compute_type="int8", batch_size=1)
            self.emit("log", message="GPU không dùng được: chuyển sang CPU INT8, giữ nguyên mô hình và nội dung.")
        else:
            return False
        return True

    def _one_chunk(self, chunk, task):
        for attempt in range(3):
            try:
                self.load()
                from faster_whisper import BatchedInferencePipeline
                kwargs = dict(language="zh", task=task, beam_size=self.plan.beam_size, temperature=[0.0, 0.2, 0.4], condition_on_previous_text=False, vad_filter=self.cfg.vad,
                              compression_ratio_threshold=2.4, log_prob_threshold=-1.0, no_speech_threshold=0.6, word_timestamps=True)
                if self.cfg.vad:
                    kwargs["vad_parameters"] = {"threshold": 0.35, "min_silence_duration_ms": 700, "speech_pad_ms": 400}
                if task == "transcribe" and self.cfg.glossary:
                    kwargs["initial_prompt"] = self.cfg.glossary
                if self.plan.batch_size > 1 and self.cfg.vad:
                    engine = BatchedInferencePipeline(self.model)
                    kwargs["batch_size"] = self.plan.batch_size
                else:
                    engine = self.model
                segments, _ = engine.transcribe(str(chunk), **kwargs)
                # Buffer only one bounded chunk. Failed retries never append duplicate segments.
                result = []
                last_notice = 0.0
                for seg in segments:
                    check_cancel(self.cancel)
                    result.append(seg)
                    now = time.monotonic()
                    if now - last_notice >= 0.3:
                        last_notice = now
                        if self.progress_callback:
                            self.progress_callback(float(seg.end))
                        else:
                            self.emit("heartbeat", seconds=float(seg.end))
                return result
            except (RuntimeError, MemoryError) as exc:
                if attempt == 2 or not self._fallback(exc):
                    raise
        raise RuntimeError("Không nhận dạng được đoạn âm thanh.")

    def transcribe(self, item, index, task="transcribe"):
        language = "zh" if task == "transcribe" else "en"
        work, folder = item["work"], item["folder"]
        duration = min(item["duration"], self.cfg.preview_seconds) if self.cfg.preview_seconds else item["duration"]
        chunk_seconds, overlap = self.chunk_seconds, self.overlap
        checkpoint = folder / f"checkpoint_{language}.json"
        key = "v2:" + self.cfg.recognition_key() + ":" + self.plan.model
        records, finished = [], 0
        if checkpoint.exists() and not self.cfg.force:
            try:
                data = json.loads(checkpoint.read_text("utf-8"))
                if data["key"] == key and data["duration"] == duration:
                    records = [Segment(**s) for s in data["segments"]]
                    finished = int(data["finished"])
                    self.emit("log", index=index, message=f"Tiếp tục từ đoạn {finished + 1}; giữ {len(records)} câu đã lưu.")
            except (KeyError, ValueError, TypeError, OSError):
                records, finished = [], 0
        converter = None
        if task == "transcribe" and self.cfg.script != "original":
            from opencc import OpenCC
            converter = OpenCC("t2s" if self.cfg.script == "simplified" else "s2t")
        count = math.ceil(duration / chunk_seconds)
        phase_count = 2 if self.cfg.english else 1
        phase = 1 if task == "translate" and self.cfg.english else 0
        stage = "Nhận dạng tiếng Trung" if language == "zh" else "Dịch tiếng Anh"
        last_progress = 25 + 70 * phase / phase_count
        def progress_at(seconds):
            nonlocal last_progress
            fraction = max(0.0, min(1.0, seconds / max(0.001, duration)))
            last_progress = max(last_progress, 25 + 70 * (phase + fraction) / phase_count)
            self.emit("item", index=index, stage=stage, active=True, progress=last_progress,
                      detail=f"{min(duration, max(0.0, seconds)) / 60:.1f}/{duration / 60:.1f} phút")
        for part in range(finished, count):
            check_cancel(self.cancel)
            left = part * chunk_seconds
            right = min(duration, left + chunk_seconds)
            start = max(0.0, left - overlap)
            stop = min(duration, right + overlap)
            chunk = work / f"chunk-{language}.wav"
            progress_at(left)
            self.progress_callback = lambda seconds, offset=start, boundary=right: progress_at(min(boundary, offset + seconds))
            extract_chunk(item["media"], chunk, start, stop - start, self.cancel)
            try:
                decoded = self._one_chunk(chunk, task)
            finally:
                chunk.unlink(missing_ok=True)
            for seg in decoded:
                words = getattr(seg, "words", None)
                if words:
                    # Trim overlap at word level to avoid repeating a whole boundary sentence.
                    selected = [w for w in words if left <= start + (w.start + w.end) / 2 < right]
                    if not selected:
                        continue
                    raw = "".join(w.word for w in selected)
                    seg_start, seg_end = selected[0].start, selected[-1].end
                else:
                    midpoint = start + (seg.start + seg.end) / 2
                    if midpoint < left or (part < count - 1 and midpoint >= right):
                        continue
                    raw, seg_start, seg_end = seg.text, seg.start, seg.end
                text = clean_zh(raw) if language == "zh" else raw.strip()
                if converter:
                    text = converter.convert(text)
                if not text:
                    continue
                begin, end = max(0.0, start + seg_start), min(duration, start + seg_end)
                if records:
                    if text == records[-1].text and begin < records[-1].end:
                        continue
                    begin = max(begin, records[-1].end)
                if end <= begin:
                    continue
                logprob = getattr(seg, "avg_logprob", None)
                silence = getattr(seg, "no_speech_prob", None)
                review = (logprob is not None and logprob < -0.8) or (silence is not None and silence > 0.8 and logprob is not None and logprob < -0.4) or getattr(seg, "compression_ratio", 0) > 2.4
                records.append(Segment(round(begin, 3), round(end, 3), text, round(logprob, 4) if logprob is not None else None, round(silence, 4) if silence is not None else None, review))
            atomic_text(checkpoint, json.dumps({"key": key, "duration": duration, "finished": part + 1, "segments": [asdict(s) for s in records]}, ensure_ascii=False))
            atomic_text(folder / f"transcript_{language}.partial.txt", paragraphs(records), "utf-8-sig")
            self.emit("preview", index=index, text=paragraphs(records)[-30000:])
            progress_at(right)
        self.progress_callback = None
        progress_at(duration)
        return records, duration
