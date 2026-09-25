from __future__ import annotations

import json
import os
import sys
import threading


def configure_runtime():
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "20")
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "60")
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def worker(path):
    from pathlib import Path
    from biliscribe.config import Settings
    from biliscribe.media import Cancelled
    from biliscribe.pipeline import process_batch
    from biliscribe.worker_control import listen_cancel
    cancel = threading.Event()
    lock = threading.Lock()
    def emit(event, **data):
        with lock:
            print(json.dumps({"event": event, **data}, ensure_ascii=False), flush=True)
    # Blocking sys.stdin reads can deadlock NumPy initialization on Windows.
    # Keep the pipe protocol while reading only bytes already available via Win32.
    threading.Thread(target=listen_cancel, args=(cancel,), daemon=True).start()
    try:
        request = json.loads(Path(path).read_text("utf-8"))
        if request.get("action") == "gpu":
            from biliscribe.gpu import install_gpu
            return install_gpu(emit, cancel)
        if request.get("action") == "probe":
            from biliscribe.hardware import hardware_dict
            emit("hardware", **hardware_dict())
            return 0
        cfg = Settings.from_dict(request["settings"])
        return process_batch(request["sources"], cfg, emit, cancel)
    except Cancelled as exc:
        emit("cancelled", message=str(exc))
        return 2
    except Exception as exc:
        message = str(exc)
        if "http" in message.lower() or "token" in message.lower():
            message = "Không thể tải dữ liệu. Kiểm tra mạng và thử lại."
        emit("fatal", message=message[:1500])
        return 1


def main():
    configure_runtime()
    if "--worker" in sys.argv:
        return worker(sys.argv[sys.argv.index("--worker") + 1])
    if "--self-test" in sys.argv:
        from biliscribe.diagnostics import self_test
        return self_test(sys.argv[-1])
    from biliscribe.ui import run_gui
    return run_gui()


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    raise SystemExit(main())
