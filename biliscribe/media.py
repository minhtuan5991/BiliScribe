from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

from .config import Settings, atomic_text, normalize_url, resource_path, safe_name, source_key


class Cancelled(Exception):
    pass


def check_cancel(cancel: threading.Event):
    if cancel.is_set():
        raise Cancelled("Đã dừng theo yêu cầu.")


def binary(name: str) -> str:
    path = resource_path("vendor/" + name + (".exe" if os.name == "nt" else ""))
    found = str(path) if path.is_file() else shutil.which(name)
    if not found:
        raise RuntimeError(f"Thiếu {name}. Hãy cài lại BiliScribe bằng bộ cài đầy đủ.")
    return found


def run_media(args: list[str], cancel: threading.Event, timeout=7200):
    check_cancel(cancel)
    # stderr is a file so a long FFmpeg error never fills a pipe and deadlocks.
    import tempfile
    with tempfile.TemporaryFile() as errors:
        proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=errors, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        start = time.monotonic()
        try:
            while proc.poll() is None:
                check_cancel(cancel)
                if time.monotonic() - start > timeout:
                    raise TimeoutError("FFmpeg xử lý quá thời gian cho phép.")
                cancel.wait(0.15)
            if proc.returncode:
                errors.seek(0)
                raise RuntimeError("FFmpeg: " + errors.read().decode("utf-8", "replace")[-1500:])
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)


def duration_seconds(path: Path):
    result = subprocess.run([binary("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)], capture_output=True, timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        duration = float(json.loads(result.stdout)["format"]["duration"])
        if duration <= 0:
            raise ValueError()
        return duration
    except (ValueError, KeyError):
        raise RuntimeError("Không đọc được thời lượng hoặc file không có âm thanh.")


def make_mp3(src: Path, target: Path, cancel):
    if target.is_file() and target.stat().st_size > 0:
        return
    temp = target.with_suffix(".partial.mp3")
    run_media([binary("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-map", "0:a:0", "-vn", "-c:a", "libmp3lame", "-q:a", "2", str(temp)], cancel)
    check_cancel(cancel)
    os.replace(temp, target)


def extract_chunk(src: Path, target: Path, start: float, length: float, cancel):
    run_media([binary("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{start:.3f}", "-i", str(src), "-t", f"{length:.3f}", "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(target)], cancel)


class DownloadLogger:
    def __init__(self, emit, index):
        self.emit, self.index = emit, index
    def debug(self, msg):
        pass
    def warning(self, msg):
        # Signed CDN URLs or cookie errors may contain credentials; keep raw diagnostics out of logs.
        if "subtitle" not in str(msg).lower():
            self.emit("log", index=self.index, message="Bilibili có cảnh báo; ứng dụng sẽ thử phương thức tải phù hợp.")
    def error(self, msg):
        pass


def friendly_download_error(exc):
    text = str(exc).lower()
    if "cookie" in text or "login" in text or "sign in" in text:
        return "Video cần đăng nhập hoặc không đọc được cookie. Chọn cookie Firefox / file cookies.txt trong Nâng cao."
    if "403" in text or "412" in text or "429" in text:
        return "Bilibili đang từ chối kết nối. Hãy thử lại sau hoặc cung cấp cookie của tài khoản có quyền xem."
    if "404" in text or "not available" in text or "removed" in text:
        return "Video không còn khả dụng hoặc tài khoản / khu vực hiện tại không xem được."
    return "Không tải được âm thanh Bilibili. Kiểm tra mạng, link video và cookie; sau đó thử lại."


def prepare_source(source: str, cfg: Settings, emit, cancel, index: int):
    check_cancel(cancel)
    key = source_key(source)
    root = Path(cfg.output_dir)
    work = root / ".biliscribe-cache" / key
    work.mkdir(parents=True, exist_ok=True)
    local = Path(source)
    title = local.stem if local.is_file() else ""
    media = local.resolve() if local.is_file() else None
    info_file = work / "download.json"
    if media is None and info_file.exists():
        try:
            data = json.loads(info_file.read_text("utf-8"))
            candidate = work / Path(data["filename"]).name
            if candidate.is_file() and candidate.stat().st_size:
                media, title = candidate, data["title"]
                emit("log", index=index, message="Dùng lại âm thanh đã tải trong bộ nhớ đệm.")
        except (OSError, KeyError, ValueError):
            pass
    if media is None:
        import yt_dlp
        from yt_dlp.utils import DownloadCancelled
        url = normalize_url(source)
        last_emit = [0.0]
        def hook(data):
            if cancel.is_set():
                raise DownloadCancelled("cancelled")
            now = time.monotonic()
            if data.get("status") == "downloading" and now - last_emit[0] > 0.3:
                last_emit[0] = now
                total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
                done = data.get("downloaded_bytes", 0)
                detail = f"{done / 2**20:.1f} MB"
                speed, eta = data.get("speed"), data.get("eta")
                if isinstance(speed, (int, float)) and speed > 0:
                    detail += f" · {speed / 1024:.0f} KB/s"
                if isinstance(eta, (int, float)) and 0 <= eta < 86400:
                    detail += f" · còn ~{int(eta) // 60}:{int(eta) % 60:02}"
                emit("item", index=index, stage="Tải âm thanh", progress=20 * done / total if total else 0, detail=detail)
        opts = {
            "format": "bestaudio/best", "noplaylist": True, "playlist_items": "1",
            "outtmpl": str(work / "source.%(ext)s"), "windowsfilenames": True,
            "continuedl": True, "retries": 4, "fragment_retries": 4, "extractor_retries": 2,
            "socket_timeout": 25, "concurrent_fragment_downloads": cfg.fragments,
            "http_headers": {"Referer": "https://www.bilibili.com/", "Accept-Language": "zh-CN,zh;q=0.9"},
            "quiet": True, "noprogress": True, "logger": DownloadLogger(emit, index),
            "progress_hooks": [hook], "ffmpeg_location": str(Path(binary("ffmpeg")).parent),
        }
        if cfg.cookies == "file":
            cookie = Path(cfg.cookie_file)
            if not cookie.is_file():
                raise ValueError("Chưa chọn file cookies.txt hợp lệ.")
            # yt-dlp saves its cookie jar on close; protect the user's original cookie file.
            cookie_copy = work / "cookies.txt"
            shutil.copyfile(cookie, cookie_copy)
            opts["cookiefile"] = str(cookie_copy)
        elif cfg.cookies != "none":
            opts["cookiesfrombrowser"] = (cfg.cookies,)
        try:
            for attempt in range(2):
                check_cancel(cancel)
                emit("item", index=index, stage="Đọc video" if attempt == 0 else "Thử lại kết nối", progress=0)
                try:
                    with yt_dlp.YoutubeDL(opts) as downloader:
                        data = downloader.extract_info(url, download=True)
                        if data and data.get("entries"):
                            data = next(iter(data["entries"]), None)
                        if not data:
                            raise RuntimeError("Không có dữ liệu video.")
                        title = str(data.get("title") or data.get("id") or "Bilibili")
                        requested = data.get("requested_downloads") or []
                        filename = requested[0].get("filepath") if requested else None
                        media = Path(filename or downloader.prepare_filename(data))
                    if not media.is_file():
                        raise RuntimeError("Không tìm thấy âm thanh sau khi tải.")
                    break
                except DownloadCancelled:
                    raise Cancelled("Đã dừng tải.")
                except Exception as exc:
                    check_cancel(cancel)
                    if attempt:
                        raise RuntimeError(friendly_download_error(exc)) from exc
                    opts.update(concurrent_fragment_downloads=1, http_chunk_size=512 * 1024)
                    emit("log", index=index, message="Làm mới địa chỉ tải và thử lại với một luồng.")
                    if cancel.wait(1):
                        check_cancel(cancel)
            atomic_text(info_file, json.dumps({"filename": media.name, "title": title}, ensure_ascii=False))
        finally:
            if cfg.cookies == "file":
                (work / "cookies.txt").unlink(missing_ok=True)
    folder = root / f"{safe_name(title)} [{key[:8]}]"
    folder.mkdir(parents=True, exist_ok=True)
    emit("item", index=index, title=title, stage="Xuất MP3", progress=21)
    mp3 = folder / "audio.mp3"
    make_mp3(media, mp3, cancel)
    duration = duration_seconds(media)
    if cfg.keep_source and not local.is_file():
        kept = folder / ("audio-original" + media.suffix)
        if not kept.exists():
            shutil.copyfile(media, kept)
    return {"source": source, "title": title, "media": media, "mp3": mp3, "folder": folder, "duration": duration, "work": work}
