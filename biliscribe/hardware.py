from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import Settings, data_dir

_dll_handles = []


@dataclass
class Hardware:
    ram_gb: float
    available_gb: float
    physical_cores: int
    gpu_name: str = ""
    vram_gb: float = 0
    cuda_ready: bool = False
    gpu_index: int = 0


@dataclass
class Plan:
    model: str
    device: str
    compute_type: str
    threads: int
    batch_size: int
    beam_size: int
    gpu_index: int = 0


def register_gpu_dlls():
    if os.name != "nt":
        return
    folder = data_dir() / "gpu"
    if folder.exists():
        os.environ["PATH"] = str(folder) + os.pathsep + os.environ.get("PATH", "")
        _dll_handles.append(os.add_dll_directory(str(folder)))


def detect_hardware() -> Hardware:
    import psutil
    memory = psutil.virtual_memory()
    hw = Hardware(round(memory.total / 2**30, 1), round(memory.available / 2**30, 1), psutil.cpu_count(logical=False) or 2)
    register_gpu_dlls()
    smi = shutil.which("nvidia-smi")
    if not smi:
        candidate = Path(os.environ.get("WINDIR", "C:/Windows")) / "System32/nvidia-smi.exe"
        if candidate.exists():
            smi = str(candidate)
    if smi:
        try:
            result = subprocess.run([smi, "--query-gpu=index,name,memory.free", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=6, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            devices = [line.split(",") for line in result.stdout.splitlines() if line.count(",") >= 2]
            if devices:
                item = max(devices, key=lambda x: float(x[-1]))
                hw.gpu_index, hw.gpu_name, hw.vram_gb = int(item[0]), item[1].strip(), float(item[-1]) / 1024
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
    if hw.gpu_name:
        try:
            if os.name == "nt":
                # Check before CTranslate2 inference: a missing cuDNN DLL can abort the process.
                for name in ("cublas64_12.dll", "cudnn64_9.dll", "cudnn_ops64_9.dll", "cudnn_cnn64_9.dll"):
                    _dll_handles.append(ctypes.WinDLL(name))
            import ctranslate2
            hw.cuda_ready = ctranslate2.get_cuda_device_count() > hw.gpu_index
        except (OSError, RuntimeError, ImportError):
            pass
    return hw


def choose_plan(cfg: Settings, hw: Hardware) -> Plan:
    device = "cuda" if cfg.device != "cpu" and hw.cuda_ready and hw.vram_gb >= 2 else "cpu"
    if cfg.model != "auto":
        model = cfg.model
    elif cfg.profile == "quality":
        model = "large-v3"
    elif cfg.profile == "balanced":
        model = "large-v3-turbo"
    elif cfg.profile == "fast":
        model = "sensevoice-small"
    elif device == "cuda":
        model = "large-v3" if hw.vram_gb >= 5 else "large-v3-turbo"
    else:
        model = "sensevoice-small"
    if cfg.english and model in {"sensevoice-small", "large-v3-turbo"}:
        model = "large-v3"
    if model == "sensevoice-small":
        return Plan(model, "cpu", "int8", max(1, min(4, hw.physical_cores - 1)), 1, 1, hw.gpu_index)
    batch = 1
    if device == "cuda" and cfg.profile != "quality" and cfg.vad:
        batch = 8 if hw.vram_gb >= 10 else 4 if hw.vram_gb >= 6 else 1
    # The full large model on a small GPU is safer with int8 weights and no batching.
    compute = "int8_float16" if device == "cuda" else "int8"
    if device == "cuda" and hw.vram_gb < 4 and model == "large-v3":
        device, compute, batch = "cpu", "int8", 1
    return Plan(model, device, compute, max(1, min(8, hw.physical_cores - 1)), batch, 3 if cfg.profile == "fast" else 5, hw.gpu_index)


def hardware_dict():
    return asdict(detect_hardware())
