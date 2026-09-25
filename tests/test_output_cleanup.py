import threading
from pathlib import Path
import pytest
from biliscribe.config import Settings, source_key, safe_name
from biliscribe.output_cleanup import FINAL_FILES, cleanup_result, cleanup_cache
from biliscribe.transcribe import Segment
from biliscribe.hardware import Hardware
from biliscribe.media import Cancelled

def job(tmp_path, source="source", title="测试"):
    cfg = Settings.from_dict({"output_dir": str(tmp_path / "output"), "cache_dir": str(tmp_path / "models"), "profile": "fast"})
    folder = Path(cfg.output_dir) / f"{safe_name(title)} [{source_key(source)[:8]}]"
    work = Path(cfg.output_dir) / ".biliscribe-cache" / source_key(source)
    folder.mkdir(parents=True); work.mkdir(parents=True)
    item = dict(source=source, title=title, folder=folder, work=work, duration=1)
    return cfg, item

def test_only_three_files_remain_and_source_models_other_job_survive(tmp_path):
    src = tmp_path / "my-audio.mp3"; src.write_bytes(b"original")
    cfg, item = job(tmp_path, str(src))
    for name in FINAL_FILES | {"audio.mp3", "result.json", "checkpoint_zh.json", "transcript_zh.json", "transcript_en.txt"}:
        (item["folder"] / name).write_text("测试", "utf-8")
    comparison = item["folder"] / "doi-chieu"; comparison.mkdir(); (comparison / "checkpoint_zh.json").write_text("temporary")
    (item["work"] / "source.m4a").write_bytes(b"cache")
    other = item["work"].parent / "unfinished"; other.mkdir(); (other / "source.m4a").write_bytes(b"keep")
    Path(cfg.cache_dir).mkdir(); (Path(cfg.cache_dir) / "model.bin").write_bytes(b"model")
    cleanup_result(item, cfg); cleanup_cache(item, cfg)
    assert {p.name for p in item["folder"].iterdir()} == FINAL_FILES
    assert not item["work"].exists()
    assert src.read_bytes() == b"original" and (other / "source.m4a").read_bytes() == b"keep"
    assert (Path(cfg.cache_dir) / "model.bin").read_bytes() == b"model"

def test_incomplete_output_is_never_cleaned(tmp_path):
    cfg, item = job(tmp_path)
    checkpoint = item["folder"] / "checkpoint_zh.json"; checkpoint.write_text("resume")
    with pytest.raises(OSError): cleanup_result(item, cfg)
    assert checkpoint.read_text() == "resume"

def test_path_outside_expected_job_is_rejected(tmp_path):
    cfg, item = job(tmp_path)
    item["work"] = tmp_path
    with pytest.raises(OSError): cleanup_cache(item, cfg)
    item["folder"] = Path(cfg.output_dir)
    with pytest.raises(OSError): cleanup_result(item, cfg)

@pytest.mark.parametrize("outcome", ["success", "error", "cancel", "comparison_error", "dual"])
def test_pipeline_cleanup_only_on_success(tmp_path, monkeypatch, outcome):
    import biliscribe.pipeline as pipeline
    cfg, item = job(tmp_path)
    monkeypatch.setenv("BILISCRIBE_DATA_DIR", str(tmp_path / "appdata"))
    monkeypatch.setattr(pipeline, "detect_hardware", lambda: Hardware(8, 4, 4))
    monkeypatch.setattr(pipeline, "prepare_source", lambda *args: item)
    (item["work"] / "source.m4a").write_bytes(b"cache")
    (item["folder"] / "audio.mp3").write_bytes(b"audio")
    cancel = threading.Event(); events = []
    if outcome in {"comparison_error", "dual"}: cfg.profile = "quality"
    def transcribe(self, current, *args):
        checkpoint = current["folder"] / "checkpoint_zh.json"
        checkpoint.write_text("resume")
        if outcome == "cancel": raise Cancelled("stopped")
        if outcome == "error" or (outcome == "comparison_error" and current["folder"].name == "doi-chieu"):
            raise RuntimeError("recognition failed")
        return [Segment(0, 1, "你好。")], 1
    monkeypatch.setattr(pipeline.Transcriber, "transcribe", transcribe)
    monkeypatch.setattr(pipeline.SenseVoiceTranscriber, "transcribe", transcribe)
    def run(): return pipeline.process_batch(["source"], cfg, lambda k, **d: events.append((k,d)), cancel)
    if outcome == "cancel":
        with pytest.raises(Cancelled): run()
    else:
        assert run() == (0 if outcome in {"success", "dual"} else 1)
    if outcome in {"success", "dual"}:
        assert {p.name for p in item["folder"].iterdir()} == FINAL_FILES
        assert not item["work"].exists()
        report = (item["folder"] / "doi_chieu_zh.txt").read_text("utf-8-sig")
        assert ("Chưa chạy đối chiếu" in report) == (outcome == "success")
    else:
        assert (item["folder"] / "checkpoint_zh.json").read_text() == "resume"
        assert (item["folder"] / "audio.mp3").exists() and item["work"].exists()
        assert not any(k == "result" for k, _ in events)
