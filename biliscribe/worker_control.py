"""Cancellation transport that never blocks Windows CRT stdin during DLL loading."""
from __future__ import annotations

import os
import sys


def listen_cancel(cancel, stream=None):
    stream = sys.stdin if stream is None else stream
    if stream is None:
        return
    if os.name != 'nt':
        for line in stream:
            if line.strip() == 'cancel':
                cancel.set()
                return
        return
    import ctypes
    import msvcrt
    from ctypes import wintypes
    try:
        handle = wintypes.HANDLE(msvcrt.get_osfhandle(stream.fileno()))
    except (OSError, ValueError):
        return
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    peek = kernel.PeekNamedPipe
    peek.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                     ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD)]
    peek.restype = wintypes.BOOL
    read = kernel.ReadFile
    read.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
    read.restype = wintypes.BOOL
    pending = b''
    while not cancel.is_set():
        available = wintypes.DWORD()
        if not peek(handle, None, 0, None, ctypes.byref(available), None):
            return  # EOF / console / closed parent, rather than a blocking CRT read.
        if not available.value:
            cancel.wait(0.1)
            continue
        size = min(4096, available.value)
        buffer = ctypes.create_string_buffer(size)
        received = wintypes.DWORD()
        if not read(handle, buffer, size, ctypes.byref(received), None) or not received.value:
            return
        pending += buffer.raw[:received.value]
        lines = pending.split(b'\n')
        pending = lines.pop()
        for line in lines:
            if line.strip() == b'cancel':
                cancel.set()
                return
        if len(pending) > 4096:
            pending = b''
