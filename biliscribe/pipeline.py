from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from pathlib import Path

from . import __version__
from .config import Settings, atomic_text, source_key
from .history import record_history
from .hardware import choose_plan, detect_hardware, Plan
from .media import Cancelled, check_cancel, prepare_source
from .transcribe import Transcriber, write_outputs
from .sensevoice import SenseVoiceTranscriber
from .comparison import compare_transcripts
from .output_cleanup import cleanup_result, cleanup_cache
from .titles import clean_title, vietnamese_title, output_name, rename_completed
from .output_files import ascii_title, rename_transcripts


def process_batch(sources, cfg: Settings, emit, cancel):
    cfg = replace(cfg, english=False, keep_source=False)
    start = time.monotonic()
    api = cfg.profile == "pixazo"
    if api:
        from .pixazo import PixazoTranscriber
        hw = None
        plan = Plan("qwen3-asr-flash-realtime", "api", "PCM 16 kHz", cfg.pixazo_workers, cfg.pixazo_workers, 0)
    else:
        hw = detect_hardware()
        plan = choose_plan(cfg, hw)
        emit("hardware", **asdict(hw))
    emit("plan", **asdict(plan))
    if hw and hw.gpu_name and not hw.cuda_ready and cfg.device != "cpu" and plan.model != "sensevoice-small":
        emit("log", message="Có GPU NVIDIA nhưng chưa đủ thư viện CUDA. Dùng CPU; có thể bấm Chuẩn bị GPU trong Nâng cao.")
    if not api and cfg.device == "cuda" and plan.device != "cuda" and plan.model != "sensevoice-small":
        emit("log", message="GPU chưa sẵn sàng hoặc thiếu VRAM. Tự động dùng CPU INT8.")
    dual = cfg.profile == "quality" and plan.model == "large-v3"
    def primary_event(kind, **data):
        if dual and kind == "item" and data.get("active"):
            data["progress"] = 25 + 55 * max(0, min(1, (data.get("progress", 25) - 25) / 70))
        emit(kind, **data)
    engine_class = PixazoTranscriber if api else SenseVoiceTranscriber if plan.model == "sensevoice-small" else Transcriber
    recognizer = engine_class(cfg, plan, primary_event, cancel)
    results, errors = [], []
    completed_cache = {}
    pending = {}
    unfinished_keys = set()
    # Only two inputs are prefetched; never enqueue an entire playlist or load multiple ASR models.
    try:
        with ThreadPoolExecutor(max_workers=cfg.download_workers, thread_name_prefix="audio") as pool:
            pending = {}
            next_submit = 0
            def submit_next():
                nonlocal next_submit
                if next_submit < len(sources) and not cancel.is_set():
                    i = next_submit
                    pending[i] = pool.submit(prepare_source, sources[i], cfg, emit, cancel, i)
                    next_submit += 1
            for _ in range(min(cfg.download_workers, len(sources))):
                submit_next()
            for i, source in enumerate(sources):
                if cancel.is_set():
                    for future in pending.values():
                        future.cancel()
                    raise Cancelled("Đã dừng. Có thể chạy lại để tiếp tục.")
                try:
                    completed_cache.pop(source, None)
                    item = pending.pop(i).result()
                    check_cancel(cancel)
                    metadata = {"app": f"BiliScribe {__version__}", "source": source, "title": item["title"], "source_duration_seconds": item["duration"], "settings": {"profile": cfg.profile, "script": cfg.script, "vad": cfg.vad}, "engine": asdict(plan), "subtitle_timing": "Long cues split proportionally; timestamps are approximate."}
                    zh, duration = recognizer.transcribe(item, i)
                    metadata["duration_seconds"] = duration
                    metadata["engine"] = asdict(recognizer.plan)
                    metadata["preview_only"] = bool(cfg.preview_seconds)
                    write_outputs(item["folder"], zh, metadata)
                    comparison_count = None
                    if dual:
                        # Release the large model before loading the CPU verifier on low-RAM PCs.
                        recognizer.close()
                        compare_cfg = replace(cfg, model="sensevoice-small", device="cpu", english=False, glossary="")
                        compare_plan = choose_plan(compare_cfg, hw)
                        def compare_event(kind, **data):
                            if kind == "preview":
                                return
                            if kind == "item":
                                data["stage"] = "Đối chiếu tiếng Trung"
                                data["progress"] = 80 + 15 * max(0, min(1, (data.get("progress", 25) - 25) / 70))
                            emit(kind, **data)
                        checker = SenseVoiceTranscriber(compare_cfg, compare_plan, compare_event, cancel)
                        comparison_folder = item["folder"] / "doi-chieu"
                        comparison_folder.mkdir(exist_ok=True)
                        comparison_item = {**item, "folder": comparison_folder}
                        try:
                            alternative, _ = checker.transcribe(comparison_item, i)
                            alternative_metadata = {**metadata, "engine": asdict(compare_plan), "role": "Independent comparison; not an automatic correction."}
                            write_outputs(comparison_folder, alternative, alternative_metadata)
                            comparison_count = compare_transcripts(zh, alternative, item["folder"])
                            metadata["comparison"] = {"model": "sensevoice-small", "differences": comparison_count,
                                                      "note": "Disagreement is not proof of error; primary text is unchanged."}
                            write_outputs(item["folder"], zh, metadata)
                            (comparison_folder / "transcript_zh.partial.txt").unlink(missing_ok=True)
                        finally:
                            checker.close()
                    if api:
                        atomic_text(item["folder"] / "doi_chieu_zh.txt",
                                    "Nhận dạng tiếng Trung bằng Pixazo Qwen ASR Realtime.\n"
                                    "Chưa chạy đối chiếu với mô hình thứ hai. Không có điểm độ tin cậy.\n"
                                    "Mốc phụ đề lấy từ sự kiện lời nói; có thể là thời gian ước lượng.\n"
                                    "Kiểm tra tên riêng và thuật ngữ bằng video / file nguồn.\n", "utf-8-sig")
                    elif not dual:
                        review = (item["folder"] / "transcript_zh_review.txt").read_text("utf-8-sig")
                        atomic_text(item["folder"] / "doi_chieu_zh.txt",
                                    "Chưa chạy đối chiếu hai mô hình trong chế độ này.\n"
                                    "Chọn Ưu tiên độ sát + Large v3 để đối chiếu.\n\n" + review, "utf-8-sig")
                    check_cancel(cancel)
                    for language in ("zh", "en"):
                        (item["folder"] / f"transcript_{language}.partial.txt").unlink(missing_ok=True)
                    status = "Hoàn tất" if zh else "Không phát hiện lời nói"
                    emit("item", index=i, stage="Đặt tên thư mục kết quả", progress=98)
                    title_zh = clean_title(item["title"])
                    title_vi = vietnamese_title(title_zh, cancel, emit)
                    file_title = title_vi or title_zh
                    final_name = output_name(title_zh, title_vi, cfg.output_dir,
                                             file_space=min(128, len(ascii_title(file_title)) + 8))
                    check_cancel(cancel)
                    summary = {"title": item["title"], "folder": str(item["folder"]), "segments": len(zh), "review": sum(s.review for s in zh), "status": status, "source": source, "completed_at": time.strftime("%Y-%m-%d %H:%M:%S"), "duration": duration, "model": recognizer.plan.model, "comparison_differences": comparison_count}
                    atomic_text(item["folder"] / "result.json", json.dumps(summary, ensure_ascii=False, indent=2))
                    cleanup_result(item, cfg)
                    try:
                        rename_completed(item, cfg, final_name)
                    except (OSError, TimeoutError):
                        emit("log", message="Đã lưu đủ ba file nhưng chưa đổi tên được thư mục. Hãy đóng chương trình đang giữ thư mục kết quả.")
                    summary.update(folder=str(item["folder"]), title_zh=title_zh, title_vi=title_vi)
                    try:
                        summary.update(rename_transcripts(item["folder"], file_title))
                    except OSError:
                        emit("log", message="Đã lưu transcript nhưng chưa đổi tên được file. Hãy đóng ứng dụng đang mở các file kết quả.")
                    completed_cache[source] = item
                    results.append(summary)
                    try:
                        record_history(summary)
                    except (OSError, TimeoutError):
                        emit("log", message="Kết quả đã được lưu nhưng chưa cập nhật được lịch sử. Bạn vẫn có thể mở thư mục kết quả.")
                    emit("result", index=i, **summary)
                    emit("item", index=i, stage=status, progress=100)

                except Cancelled:
                    unfinished_keys.add(source_key(source))
                    cancel.set()
                    raise
                except Exception as exc:
                    unfinished_keys.add(source_key(source))
                    check_cancel(cancel)
                    text = str(exc)
                    if "http" in text.lower() or "token" in text.lower():
                        text = "Không tải được mô hình / dữ liệu. Kiểm tra mạng và dung lượng trống rồi chạy lại."
                    if "memory" in text.lower() or "alloc" in text.lower():
                        text = "Không đủ RAM cho mô hình hiện tại. Chọn Máy nhẹ / nhanh hoặc đóng bớt ứng dụng."
                    errors.append({"source": source, "message": text[:1500]})
                    emit("item", index=i, stage="Lỗi", progress=0, detail=text[:1500])
                    emit("log", message=f"Mục {i + 1}: {text[:1500]}")
                finally:
                    submit_next()
    finally:
        # Wait for prefetch workers to close files before deleting successful caches.
        unfinished_keys.update(source_key(sources[i]) for i in pending)
        for item in completed_cache.values():
            if source_key(item["source"]) in unfinished_keys:
                continue
            try:
                cleanup_cache(item, cfg)
            except OSError as exc:
                errors.append({"source": item["source"], "message": str(exc)})
                emit("log", message=f"Đã lưu ba file kết quả nhưng chưa dọn được bộ nhớ đệm: {exc}")
        recognizer.close()
    emit("done", completed=len(results), failed=len(errors), elapsed=round(time.monotonic() - start, 1), errors=errors)
    return 0 if not errors else 1
