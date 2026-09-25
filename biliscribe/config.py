from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, urlunsplit

APP_NAME = "BiliScribe"
MODELS = {
    "sensevoice-small": ("csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17", "có sẵn · ~239 MB"),
    "tiny": ("Systran/faster-whisper-tiny", "~75 MB"),
    "base": ("Systran/faster-whisper-base", "~145 MB"),
    "small": ("Systran/faster-whisper-small", "~465 MB"),
    "medium": ("Systran/faster-whisper-medium", "~1,5 GB"),
    "large-v3-turbo": ("mobiuslabsgmbh/faster-whisper-large-v3-turbo", "~1,6 GB"),
    "large-v3": ("Systran/faster-whisper-large-v3", "~3,1 GB"),
}
PROFILES = {
    "auto": "Tự động theo cấu hình máy",
    "quality": "Ưu tiên độ sát · Large v3 + đối chiếu",
    "balanced": "Cân bằng · Large v3 Turbo",
    "fast": "Máy nhẹ / nhanh · SenseVoice",
    "pixazo": "Pixazo API · Qwen tiếng Trung",
}


def data_dir() -> Path:
    value = os.environ.get("BILISCRIBE_DATA_DIR")
    path = Path(value) if value else Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def resource_path(name: str) -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / name


def atomic_text(path: Path, text: str, encoding="utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix="." + path.name + "-", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding=encoding, newline="") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def normalize_url(raw: str) -> str:
    raw = raw.strip()
    if re.fullmatch(r"BV[0-9A-Za-z]{10}", raw):
        raw = "https://www.bilibili.com/video/" + raw
    match = re.search(r"https?://[^\s<>\[\]]+", raw)
    if match:
        raw = match.group().rstrip("）),。；;")
    parsed = urlsplit(raw)
    if parsed.scheme not in ("http", "https") or parsed.username or parsed.password:
        raise ValueError("Hãy dán link https://www.bilibili.com/video/BV… hoặc https://b23.tv/…")
    host = (parsed.hostname or "").lower()
    if host not in {"bilibili.com", "www.bilibili.com", "m.bilibili.com", "b23.tv"} or parsed.port:
        raise ValueError("Chỉ hỗ trợ link video Bilibili và link rút gọn b23.tv.")
    if host == "b23.tv":
        if not re.fullmatch(r"/[A-Za-z0-9]+/?", parsed.path):
            raise ValueError("Link b23.tv không hợp lệ.")
        return urlunsplit(("https", host, parsed.path, "", ""))
    if not re.fullmatch(r"/video/(?:BV[0-9A-Za-z]{10}|av[0-9]+)/?", parsed.path, re.I):
        raise ValueError("Cần link của một video cụ thể: bilibili.com/video/BV…")
    page = parse_qs(parsed.query).get("p", ["1"])[0]
    if not page.isdigit() or not 1 <= int(page) <= 10000:
        raise ValueError("Số phần p trong link không hợp lệ.")
    return urlunsplit(("https", "www.bilibili.com", parsed.path.rstrip("/") + "/", f"p={int(page)}", ""))


def safe_name(title: str, limit=75) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", title).strip(" .")[:limit].rstrip(" .")
    if not value or value.upper().split(".")[0] in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
        value = "video_" + value
    return value


def source_key(source: str) -> str:
    path = Path(source)
    if path.is_file():
        stat = path.stat()
        source = f"{path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


@dataclass
class Settings:
    output_dir: str = ""
    profile: str = "auto"
    device: str = "auto"
    model: str = "auto"
    script: str = "simplified"
    glossary: str = ""
    cookies: str = "none"
    cookie_file: str = ""
    vad: bool = True
    english: bool = False
    keep_source: bool = False
    pixazo_workers: int = 3
    download_workers: int = 2
    fragments: int = 4
    force: bool = False
    cache_dir: str = ""
    preview_seconds: int = 0

    @classmethod
    def from_dict(cls, values):
        cfg = cls(**{k: v for k, v in values.items() if k in cls.__dataclass_fields__})
        if cfg.profile not in PROFILES or cfg.device not in {"auto", "cpu", "cuda"}:
            raise ValueError("Cấu hình chế độ / thiết bị không hợp lệ.")
        if cfg.model != "auto" and cfg.model not in MODELS:
            raise ValueError("Mô hình không được hỗ trợ.")
        if cfg.script not in {"simplified", "traditional", "original"}:
            raise ValueError("Kiểu chữ không hợp lệ.")
        if cfg.cookies not in {"none", "file", "chrome", "edge", "firefox"}:
            raise ValueError("Tùy chọn cookie không hợp lệ.")
        cfg.pixazo_workers = max(1, min(4, int(cfg.pixazo_workers)))
        cfg.download_workers = max(1, min(2, int(cfg.download_workers)))
        cfg.fragments = max(1, min(8, int(cfg.fragments)))
        cfg.preview_seconds = max(0, min(600, int(cfg.preview_seconds)))
        cfg.glossary = cfg.glossary.strip()[:600]
        if not cfg.output_dir:
            cfg.output_dir = str(Path.home() / "Downloads" / APP_NAME)
        if not cfg.cache_dir:
            cfg.cache_dir = str(data_dir() / "models")
        return cfg

    def recognition_key(self):
        data = asdict(self)
        keys = ("profile", "device", "model", "script", "glossary", "vad", "english", "preview_seconds")
        return hashlib.sha256(json.dumps({k: data[k] for k in keys}, sort_keys=True).encode()).hexdigest()


def load_settings() -> Settings:
    try:
        return Settings.from_dict(json.loads((data_dir() / "settings.json").read_text("utf-8")))
    except (OSError, ValueError, TypeError):
        return Settings.from_dict({})


def save_settings(cfg: Settings):
    atomic_text(data_dir() / "settings.json", json.dumps(asdict(cfg), ensure_ascii=False, indent=2))
