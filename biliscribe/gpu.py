"""Optional user-requested NVIDIA runtime, installed privately without pip or admin."""
import hashlib
import json
import os
import urllib.request
import zipfile
from pathlib import Path

from .config import atomic_text, data_dir
from .media import check_cancel

PACKAGES = (("nvidia-cuda-runtime-cu12", "12.4.127"), ("nvidia-cublas-cu12", "12.4.5.8"), ("nvidia-cudnn-cu12", "9.1.0.70"))


def install_gpu(emit, cancel):
    import certifi
    import ssl
    context = ssl.create_default_context(cafile=certifi.where())
    target = data_dir() / "gpu"
    target.mkdir(parents=True, exist_ok=True)
    for number, (package, version) in enumerate(PACKAGES):
        check_cancel(cancel)
        marker = target / f"{package}-{version}.json"
        if marker.exists():
            continue
        emit("model", message=f"Đọc gói NVIDIA {package} {version}", progress=-1)
        with urllib.request.urlopen(f"https://pypi.org/pypi/{package}/{version}/json", timeout=30, context=context) as response:
            manifest = json.load(response)
        entry = next((e for e in manifest["urls"] if e["filename"].endswith("win_amd64.whl")), None)
        if not entry or not entry["url"].startswith("https://files.pythonhosted.org/"):
            raise RuntimeError("Không tìm thấy gói NVIDIA Windows chính thức.")
        wheel = target / entry["filename"]
        hasher = hashlib.sha256()
        with urllib.request.urlopen(entry["url"], timeout=45, context=context) as response, wheel.open("wb") as output:
            done = 0
            while chunk := response.read(2**20):
                check_cancel(cancel)
                output.write(chunk)
                hasher.update(chunk)
                done += len(chunk)
                emit("model", message=f"Tải thư viện GPU {number + 1}/3: {done / 2**20:.0f}/{entry['size'] / 2**20:.0f} MB", progress=100 * done / max(1, entry["size"]))
        if hasher.hexdigest() != entry["digests"]["sha256"]:
            wheel.unlink(missing_ok=True)
            raise RuntimeError("Gói GPU có checksum không khớp. Hãy tải lại.")
        with zipfile.ZipFile(wheel) as archive:
            for member in archive.infolist():
                check_cancel(cancel)
                if member.filename.lower().endswith(".dll"):
                    dest = target / Path(member.filename).name
                elif "license" in member.filename.lower():
                    dest = target / (package + "-" + Path(member.filename).name)
                else:
                    continue
                atomic = dest.with_suffix(dest.suffix + ".tmp")
                with archive.open(member) as inp, atomic.open("wb") as out:
                    import shutil
                    shutil.copyfileobj(inp, out)
                os.replace(atomic, dest)
        wheel.unlink(missing_ok=True)
        atomic_text(marker, json.dumps({"sha256": hasher.hexdigest(), "source": entry["url"]}))
    emit("done", completed=1, failed=0, elapsed=0, message="Thư viện GPU đã sẵn sàng. Lượt xử lý tiếp theo sẽ tự kiểm tra GPU.")
    return 0
