"""Optional API-key storage protected by the current Windows user's DPAPI."""
import base64
import ctypes
import os
from ctypes import wintypes
from .config import atomic_text, data_dir

class Blob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

def _crypt(raw, decrypt=False):
    if os.name != "nt":
        raise OSError("Lưu API key an toàn chỉ hỗ trợ trên Windows.")
    buffer = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
    source, target = Blob(len(raw), buffer), Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise OSError("Không thể đọc/lưu API key bằng tài khoản Windows hiện tại.")
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel.LocalFree(target.data)

def save_key(value):
    path = data_dir() / "pixazo-key.dpapi"
    if not value:
        path.unlink(missing_ok=True)
    else:
        atomic_text(path, base64.b64encode(_crypt(value.encode())).decode("ascii"))

def load_key():
    path = data_dir() / "pixazo-key.dpapi"
    if not path.exists():
        return ""
    try:
        return _crypt(base64.b64decode(path.read_text("ascii")), decrypt=True).decode("utf-8")
    except (OSError, ValueError, UnicodeError):
        return ""
