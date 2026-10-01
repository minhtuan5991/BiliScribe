import json
import threading
import time
from pathlib import Path

import pytest

from biliscribe import titles
from biliscribe.config import Settings, safe_name, source_key
from biliscribe.media import Cancelled
from biliscribe.output_cleanup import FINAL_FILES


@pytest.mark.parametrize("raw,expected", [
    ("规则怪谈", "规则怪谈"),
    ("🔥【完结短剧】《规则怪谈》 [a052c382] #小说推荐", "规则怪谈"),
    ("【恐怖怪谈】我们发现了蜡笔！ [BV1sDLG6DED3]", "我们发现了蜡笔"),
    ("【第12集】规则怪谈 - 完整版", "第12集规则怪谈"),
    ("《规则怪谈》\u200b\ufe0f", "规则怪谈"),
    ("规则怪谈：第2集", "规则怪谈：第2集"),
])
def test_clean_title(raw, expected):
    assert titles.clean_title(raw) == expected


def test_example_offline_and_windows_name(tmp_path, monkeypatch):
    monkeypatch.setattr(titles, "_request_translation", lambda t: pytest.fail("Network unnecessary"))
    vi = titles.vietnamese_title("规则怪谈", threading.Event(), lambda *a, **k: None)
    name = titles.output_name("规则怪谈", vi, Path("D:/results"))
    assert name == "Những câu chuyện kỳ lạ về luật lệ - 规则怪谈"
    assert titles.output_name("CON", "", tmp_path).startswith("video_")
    long = titles.output_name("很长" * 100, "Tên dài " * 100, Path("D:/results"))
    assert len(long) <= 180 and " - " in long


def test_translation_cache_failure_and_cancel(tmp_path, monkeypatch):
    monkeypatch.setenv("BILISCRIBE_DATA_DIR", str(tmp_path))
    calls = []
    def request(title):
        calls.append(title)
        return "Thế giới lạnh giá"
    monkeypatch.setattr(titles, "_request_translation", request)
    cancel = threading.Event()
    for _ in range(2):
        assert titles.vietnamese_title("极寒世界", cancel, lambda *a, **k: None) == "Thế giới lạnh giá"
    assert calls == ["极寒世界"]
    monkeypatch.setattr(titles, "_request_translation", lambda _: (_ for _ in ()).throw(OSError("offline")))
    events = []
    assert titles.vietnamese_title("其他", cancel, lambda *a, **k: events.append(k)) == ""
    assert events and "Chưa dịch" in events[0]["message"]
    gate = threading.Event()
    monkeypatch.setattr(titles, "_request_translation", lambda _: gate.wait(2))
    cancel.set()
    start = time.monotonic()
    with pytest.raises(Cancelled): titles.vietnamese_title("新名称", cancel, lambda *a, **k: None)
    assert time.monotonic() - start < .3
    gate.set()


def test_translation_sends_only_title_and_validates(monkeypatch):
    from io import BytesIO
    from urllib.parse import parse_qs, urlsplit
    seen = []
    def request(req, timeout):
        seen.append(req.full_url)
        assert timeout == 4
        return BytesIO(json.dumps([[["Tên Việt", "标题", None]]]).encode())
    monkeypatch.setattr(titles, "urlopen", request)
    assert titles._request_translation("标题") == "Tên Việt"
    assert parse_qs(urlsplit(seen[0]).query)["q"] == ["标题"]
    for payload in [b"bad json", json.dumps([[["标题"]]]).encode(), b" " * 65537]:
        monkeypatch.setattr(titles, "urlopen", lambda *a, **k: BytesIO(payload))
        with pytest.raises(ValueError): titles._request_translation("标题")


def make_job(tmp_path, source="source"):
    cfg = Settings(output_dir=str(tmp_path / "out"))
    folder = Path(cfg.output_dir) / f"规则怪谈 [{source_key(source)[:8]}]"
    folder.mkdir(parents=True)
    for name in FINAL_FILES: (folder / name).write_text(source, "utf-8")
    return cfg, {"title": "规则怪谈", "source": source, "folder": folder}


def test_completed_rename_collision_and_three_files(tmp_path, monkeypatch):
    monkeypatch.setenv("BILISCRIBE_DATA_DIR", str(tmp_path / "data"))
    cfg, item = make_job(tmp_path)
    name = "Tên Việt - 规则怪谈"
    first = titles.rename_completed(item, cfg, name)
    cfg, second = make_job(tmp_path, "second")
    destination = titles.rename_completed(second, cfg, name)
    assert first.name == name and destination.name == name + " (2)"
    assert {p.name for p in destination.iterdir()} == FINAL_FILES
    assert (first / "transcript_zh.txt").read_text() == "source"
    assert (destination / "transcript_zh.txt").read_text() == "second"


def test_incomplete_or_outside_never_renamed(tmp_path, monkeypatch):
    monkeypatch.setenv("BILISCRIBE_DATA_DIR", str(tmp_path / "data"))
    cfg, item = make_job(tmp_path)
    checkpoint = item["folder"] / "checkpoint_zh.json"
    checkpoint.write_text("resume")
    with pytest.raises(OSError): titles.rename_completed(item, cfg, "Tên - 规则怪谈")
    assert checkpoint.read_text() == "resume"
    checkpoint.unlink()
    with pytest.raises(OSError): titles.rename_completed(item, cfg, "../other")
    item["folder"] = tmp_path
    with pytest.raises(OSError): titles.rename_completed(item, cfg, "Tên")
