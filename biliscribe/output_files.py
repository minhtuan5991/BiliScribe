"""Final display filenames; internal ASR/checkpoint names remain unchanged."""
import re
import unicodedata
from pathlib import Path


def ascii_title(title):
    text = str(title).replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^A-Za-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip() or "Video"


def rename_transcripts(folder, title):
    folder = Path(folder)
    if folder.is_symlink() or folder.is_junction():
        raise OSError("Không đổi tên file trong thư mục liên kết.")
    # Keep full Windows path below 250 chars, including the longest extension.
    limit = min(120, 248 - len(str(folder.resolve())) - 1 - len("_zh.srt"))
    if limit < 5:
        raise OSError("Đường dẫn quá dài để đặt tên file.")
    stem = ascii_title(title)[:limit].rstrip() + "_zh"
    pairs = [(folder / ("transcript_zh" + ext), folder / (stem + ext)) for ext in (".txt", ".srt")]
    for source, target in pairs:
        if source.is_symlink() or not source.is_file() or (target != source and target.exists()):
            raise OSError("Không thể đổi tên transcript an toàn.")
    moved = []
    try:
        for source, target in pairs:
            if source != target:
                source.rename(target)
                moved.append((source, target))
    except OSError:
        for source, target in reversed(moved):
            target.rename(source)
        raise
    return {"txt_file": pairs[0][1].name, "srt_file": pairs[1][1].name}


def transcript_file(folder, suffix):
    """Open both old releases and completed title-based outputs, never review TXT."""
    folder = Path(folder)
    if suffix not in {".txt", ".srt"}:
        return None
    legacy = folder / ("transcript_zh" + suffix)
    if legacy.is_file():
        return legacy
    candidates = [p for p in folder.glob("*_zh" + suffix)
                  if p.is_file() and p.name != "doi_chieu_zh.txt"]
    return candidates[0] if len(candidates) == 1 else None
