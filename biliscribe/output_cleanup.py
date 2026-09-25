"""Remove job artifacts only after all final text files have been written."""
from pathlib import Path
import os
import shutil
from .config import safe_name, source_key

FINAL_FILES = frozenset({"transcript_zh.txt", "transcript_zh.srt", "doi_chieu_zh.txt"})

def _checked_tree(path, boundary, protected):
    resolved = path.resolve()
    if not resolved.is_relative_to(boundary) or resolved == boundary:
        raise OSError("Từ chối dọn dữ liệu ngoài thư mục công việc.")
    if path.is_symlink() or path.is_junction():
        raise OSError("Không tự dọn thư mục có liên kết đến vị trí khác.")
    if any(p == resolved or p.is_relative_to(resolved) for p in protected):
        raise OSError("Không xóa file nguồn hoặc thư mục mô hình đã chọn.")
    if path.is_dir():
        for parent, dirs, files in os.walk(path, followlinks=False):
            for name in dirs + files:
                child = Path(parent) / name
                if child.is_symlink() or child.is_junction() or not child.resolve().is_relative_to(boundary):
                    raise OSError("Không tự dọn dữ liệu có liên kết ra ngoài.")

def _remove(path):
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)

def cleanup_result(item, cfg):
    root = Path(cfg.output_dir).resolve()
    folder = Path(item["folder"])
    expected = root / f"{safe_name(item['title'])} [{source_key(item['source'])[:8]}]"
    if folder.resolve() != expected or folder.is_symlink() or folder.is_junction():
        raise OSError("Thư mục kết quả không khớp với công việc; chưa xóa dữ liệu tạm.")
    if not all((folder / name).is_file() for name in FINAL_FILES):
        raise OSError("Chưa đủ ba file kết quả; giữ dữ liệu để chạy tiếp.")
    protected = [Path(cfg.cache_dir).resolve()]
    if Path(item["source"]).is_file():
        protected.append(Path(item["source"]).resolve())
    targets = [p for p in folder.iterdir() if p.name not in FINAL_FILES]
    # Validate every target before deleting any. Checkpoints are removed last.
    for path in targets:
        _checked_tree(path, root, protected)
    for path in sorted(targets, key=lambda p: p.name.startswith("checkpoint_")):
        _remove(path)

def cleanup_cache(item, cfg):
    root = Path(cfg.output_dir).resolve()
    work = Path(item["work"])
    expected = root / ".biliscribe-cache" / source_key(item["source"])
    if work.resolve() != expected:
        raise OSError("Bộ nhớ đệm không khớp với công việc; chưa xóa dữ liệu tạm.")
    if not work.exists():
        return
    protected = [Path(cfg.cache_dir).resolve()]
    if Path(item["source"]).is_file():
        protected.append(Path(item["source"]).resolve())
    _checked_tree(work, root, protected)
    _remove(work)
    try:
        work.parent.rmdir()  # Only remove the shared cache when it is empty.
    except OSError:
        pass
