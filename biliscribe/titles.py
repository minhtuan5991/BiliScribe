"""Clean video titles, translate only the title, and name completed output folders."""
from __future__ import annotations

import hashlib
import json
import queue
import re
import threading
import time
import unicodedata
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from filelock import FileLock

from .config import atomic_text, data_dir, safe_name, source_key
from .media import check_cancel
from .output_cleanup import FINAL_FILES

_CJK = re.compile(r"[\u3400-\u9fff]")
_TAGS = {"完结", "完结短剧", "短剧", "已完结", "全集", "完整版", "高清", "1080p", "4k",
         "恐怖怪谈", "恐怖故事", "悬疑", "小说推文", "小说推荐", "一口气看完", "一口气听完"}


def clean_title(title: str) -> str:
    title = unicodedata.normalize("NFC", str(title))
    title = "".join(c for c in title if unicodedata.category(c)[0] != "C"
                    and unicodedata.category(c) != "So" and c not in "\ufe0e\ufe0f")
    title = re.sub(r"https?://\S+", " ", title)
    title = re.sub(r"\s*#[^\s#]+", " ", title)
    title = re.sub(r"\s*[\[【(（]\s*(?:BV[a-zA-Z0-9]{10}|[a-fA-F0-9]{8,16})\s*[\]】)）]\s*$", "", title)

    def bracket(match):
        inner = match.group(1).strip()
        return " " if inner.casefold() in _TAGS else inner

    title = re.sub(r"[\[【（(《「『]([^\[\]【】（）()《》「」『』]+)[\]】）)》」』]", bracket, title)
    # Only remove known promotional phrases when separated from the actual title.
    tags = "|".join(re.escape(t) for t in sorted(_TAGS, key=len, reverse=True))
    title = re.sub(rf"^(?:{tags})\s*[:：|丨—-]+\s*", "", title, flags=re.I)
    title = re.sub(rf"\s*[|丨—-]+\s*(?:{tags})\s*$", "", title, flags=re.I)
    title = re.sub(r'[<>:"/\\|?*]', " ", title)
    title = re.sub(r"[★☆◆◇●◎※=~～]+", " ", title)
    return re.sub(r"\s+", " ", title).strip(" .-_!！,，。:：;；丨—") or "Video"


def _request_translation(title: str) -> str:
    # Public Google Translate web endpoint, best effort (not the paid Cloud API).
    url = "https://translate.googleapis.com/translate_a/single?" + urlencode(
        {"client": "gtx", "sl": "zh-CN", "tl": "vi", "dt": "t", "q": title})
    with urlopen(Request(url, headers={"User-Agent": "BiliScribe"}), timeout=4) as response:
        raw = response.read(65537)
    if len(raw) > 65536:
        raise ValueError("Translation response too large")
    rows = json.loads(raw)[0]
    value = clean_title("".join(row[0] for row in rows if isinstance(row, list) and isinstance(row[0], str)))
    if not value or value == "Video" or _CJK.search(value):
        raise ValueError("No Vietnamese title returned")
    return value


def vietnamese_title(title, cancel, emit):
    if not _CJK.search(title):
        return ""
    # Preferred translation supplied by the user; also works without Internet.
    if title == "规则怪谈":
        return "Những câu chuyện kỳ lạ về luật lệ"
    cache = data_dir() / "title-translations" / (hashlib.sha256(title.encode()).hexdigest() + ".json")
    try:
        saved = json.loads(cache.read_text("utf-8"))
        if saved["zh"] == title and isinstance(saved["vi"], str) and saved["vi"]:
            return clean_title(saved["vi"])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    results = queue.Queue(maxsize=1)
    def request():
        try:
            results.put(_request_translation(title[:500]))
        except Exception:
            results.put("")
    threading.Thread(target=request, daemon=True, name="title-translation").start()
    until = time.monotonic() + 5
    value = ""
    while time.monotonic() < until:
        check_cancel(cancel)
        try:
            value = results.get(timeout=.1)
            break
        except queue.Empty:
            pass
    check_cancel(cancel)
    if value:
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            atomic_text(cache, json.dumps({"zh": title, "vi": value}, ensure_ascii=False))
        except OSError:
            pass
    else:
        emit("log", message="Chưa dịch được tên video (mạng/dịch vụ dịch). Kết quả vẫn được lưu với tên Trung đã làm sạch.")
    return value


def output_name(title, translated, root, file_space=30):
    # Leave room for filenames and collision suffix on non-long-path Windows setups.
    available = 235 - len(str(Path(root).resolve()))
    budget = min(180, available - min(file_space, max(30, available // 2)))
    if budget < 24:
        raise OSError("Đường dẫn kết quả quá dài; hãy chọn thư mục ngắn hơn.")
    if translated:
        zh_budget = min(len(title), max(10, budget // 3))
        vi = translated[:budget - zh_budget - 3].rstrip(" .")
        return safe_name(vi + " - " + title[:zh_budget].rstrip(" ."), budget)
    return safe_name(title, budget)


def rename_completed(item, cfg, name):
    root = Path(cfg.output_dir).resolve()
    folder = Path(item["folder"])
    expected = root / f"{safe_name(item['title'])} [{source_key(item['source'])[:8]}]"
    if folder.is_symlink() or folder.is_junction() or folder.resolve() != expected:
        raise OSError("Thư mục không khớp công việc; không đổi tên.")
    if name != Path(name).name or name in {".", "..", ""}:
        raise OSError("Tên thư mục không hợp lệ.")
    if {p.name for p in folder.iterdir()} != FINAL_FILES:
        raise OSError("Chỉ đổi tên sau khi hoàn tất ba file kết quả.")
    if any(p.is_symlink() or not p.is_file() for p in folder.iterdir()):
        raise OSError("Không đổi tên kết quả có liên kết.")
    with FileLock(str(data_dir() / "output-names.lock"), timeout=5):
        for number in range(1, 10000):
            target = root / (name if number == 1 else f"{name} ({number})")
            if target.exists() or target.is_symlink():
                continue
            try:
                folder.rename(target)  # Windows refuses an existing destination.
            except FileExistsError:
                continue
            item["folder"] = target
            return target
    raise OSError("Có quá nhiều thư mục trùng tên.")
