"""Keep worker and FFmpeg processes inside an owned Windows job."""
import ctypes
import os
from ctypes import wintypes


class ProcessJob:
    def __init__(self, pid):
        self.handle = None
        if os.name != "nt":
            return
        class BASIC(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64), ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t), ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD), ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(key, ctypes.c_uint64) for key in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount", "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]
        class EXTENDED(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", BASIC), ("IoInfo", IO), ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.api.CreateJobObjectW.restype = wintypes.HANDLE
        self.api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.api.OpenProcess.restype = wintypes.HANDLE
        self.api.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        self.api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.api.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = self.api.CreateJobObjectW(None, None)
        limits = EXTENDED()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
        process = self.api.OpenProcess(0x0100 | 0x0001, False, int(pid))
        try:
            if handle and process and self.api.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)) and self.api.AssignProcessToJobObject(handle, process):
                self.handle = handle
            elif handle:
                self.api.CloseHandle(handle)
        finally:
            if process:
                self.api.CloseHandle(process)

    def terminate(self):
        if self.handle:
            self.api.TerminateJobObject(self.handle, 2)

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None
