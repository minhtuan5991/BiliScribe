import json
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from biliscribe.config import Settings, normalize_url, safe_name
from biliscribe.hardware import Hardware, Plan, choose_plan
from biliscribe.media import Cancelled, check_cancel
from biliscribe.transcribe import Segment, Transcriber, clean_zh, subtitle_cues, timestamp, write_outputs


@pytest.fixture(autouse=True)
def appdata(tmp_path, monkeypatch):
    monkeypatch.setenv("BILISCRIBE_DATA_DIR", str(tmp_path / "data"))


def test_urls_preserve_selected_part():
    assert normalize_url("https://www.bilibili.com/video/BV1sDLG6DED3/?p=3&spm_id=x") == "https://www.bilibili.com/video/BV1sDLG6DED3/?p=3"
    assert normalize_url("BV1sDLG6DED3").endswith("?p=1")
    assert normalize_url("【分享】 https://b23.tv/abc123 。") == "https://b23.tv/abc123"


@pytest.mark.parametrize("url", ["https://bilibili.com.evil.test/video/BV1sDLG6DED3", "https://evil.test/bilibili.com", "file:///C:/foo", "https://user:password@bilibili.com/video/BV1sDLG6DED3", "https://www.bilibili.com/video/BV1sDLG6DED3/?p=-1", "https://www.bilibili.com/"])
def test_reject_bad_urls(url):
    with pytest.raises(ValueError):
        normalize_url(url)


def test_hardware_adapts_without_silently_downgrading_quality():
    cfg = Settings.from_dict({})
    low = Hardware(4, 1.1, 2)
    assert choose_plan(cfg, low).model == "sensevoice-small"
    cfg.profile = "quality"
    plan = choose_plan(cfg, low)
    assert plan.model == "large-v3" and plan.compute_type == "int8"
    cfg.profile = "auto"
    gpu = Hardware(16, 8, 8, "NVIDIA", 5.5, True)
    assert choose_plan(cfg, gpu).device == "cuda"
    assert choose_plan(cfg, gpu).model == "large-v3"
    cfg.device = "cpu"
    assert choose_plan(cfg, gpu).device == "cpu"


def test_output_unicode_timing_and_no_added_words(tmp_path):
    text = "这是一段中文记录，保留AI和专有名词，不添加内容。" * 4
    segments = [Segment(0, 12.345, text), Segment(13.4, 14.7, "再见！", review=True)]
    write_outputs(tmp_path, segments, {"model": "test"})
    assert (tmp_path / "transcript_zh.txt").read_text("utf-8-sig").replace("\n", "") == text + "再见！"
    cues = list(subtitle_cues(segments))
    assert "".join(c[2] for c in cues) == text + "再见！"
    assert all(cues[i][1] <= cues[i+1][0] for i in range(len(cues)-1))
    assert cues[-1][1] == 14.7
    assert timestamp(59.9996) == "00:01:00,000"
    assert "再见" in (tmp_path / "transcript_zh_review.txt").read_text("utf-8-sig")


def test_cleanup_does_not_rewrite_mixed_language():
    assert clean_zh("中 文 AI GPT-4， test") == "中文 AI GPT-4， test"
    assert safe_name("CON") == "video_CON"
    assert "/" not in safe_name("测试/名称:*?")


def test_cancellation_is_distinct_from_failure():
    event = threading.Event()
    event.set()
    with pytest.raises(Cancelled):
        check_cancel(event)


def test_gpu_fallback_stages_preserve_model():
    transcriber = Transcriber(Settings.from_dict({}), Plan("large-v3", "cuda", "int8_float16", 4, 4, 5), lambda *a, **k: None, threading.Event())
    assert transcriber._fallback(RuntimeError("CUDA out of memory"))
    assert transcriber.plan.batch_size == 1 and transcriber.plan.device == "cuda"
    assert transcriber._fallback(RuntimeError("CUDA out of memory"))
    assert transcriber.plan.device == "cpu" and transcriber.plan.model == "large-v3"
    assert not transcriber._fallback(RuntimeError("Disk full"))


def test_checkpoint_reuses_finished_chunks_and_preserves_overlap_words(tmp_path, monkeypatch):
    cfg = Settings.from_dict({"output_dir": str(tmp_path), "script": "original"})
    emit = lambda *args, **kwargs: None
    recognizer = Transcriber(cfg, Plan("small", "cpu", "int8", 2, 1, 5), emit, threading.Event())
    calls = []
    def decode(path, task):
        calls.append(str(path))
        if len(calls) == 1:
            words = [SimpleNamespace(start=297, end=298, word="甲"), SimpleNamespace(start=299, end=299.8, word="乙"), SimpleNamespace(start=300.2, end=301, word="丙")]
        else:
            # Second chunk starts at 298; overlapping 乙 must be owned by the first chunk only.
            words = [SimpleNamespace(start=1, end=1.8, word="乙"), SimpleNamespace(start=2.2, end=3, word="丙"), SimpleNamespace(start=4, end=5, word="丁")]
        return [SimpleNamespace(start=words[0].start, end=words[-1].end, words=words, text="".join(w.word for w in words), avg_logprob=-0.2, no_speech_prob=0.01, compression_ratio=1)]
    recognizer._one_chunk = decode
    monkeypatch.setattr("biliscribe.transcribe.extract_chunk", lambda *a: None)
    item = {"work": tmp_path, "folder": tmp_path, "duration": 310, "media": tmp_path / "audio.m4a"}
    segments, _ = recognizer.transcribe(item, 0)
    assert "".join(s.text for s in segments) == "甲乙丙丁"
    assert len(calls) == 2
    again, _ = recognizer.transcribe(item, 0)
    assert len(calls) == 2 and again == segments
    cfg.glossary = "测试"
    recognizer.transcribe(item, 0)
    assert len(calls) == 4
