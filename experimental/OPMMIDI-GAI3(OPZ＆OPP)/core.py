# core.py
from __future__ import annotations
import ctypes
import os
import struct
from abc import ABC, abstractmethod

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DLL = os.path.join(HERE, "opm.dll")


class ChipCore(ABC):
    @abstractmethod
    def write(self, reg: int, val: int) -> None: ...
    @abstractmethod
    def read_status(self) -> int: ...
    @abstractmethod
    def sample_rate(self) -> int: ...
    @abstractmethod
    def generate(self, nframes: int) -> bytes: ...
    def reset(self) -> None: ...


class NullCore(ChipCore):
    name = "null"
    def __init__(self, clock: int = 3_579_545):
        self.clock = clock
        self.writes: list[tuple[int, int]] = []
    def write(self, reg, val): self.writes.append((reg & 0xFF, val & 0xFF))
    def read_status(self): return 0
    def sample_rate(self): return self.clock // 64
    def generate(self, nframes): return b"\x00" * (4 * nframes)


class OpmCore(ChipCore):
    name = "nuked-opm"
    _dll = None

    @classmethod
    def load(cls, path: str = DEFAULT_DLL) -> ctypes.CDLL:
        if cls._dll is None:
            if not os.path.exists(path):
                raise FileNotFoundError(f"找不到 {path}")
            d = ctypes.CDLL(path)
            d.opm_create.restype = ctypes.c_void_p
            d.opm_create.argtypes = [ctypes.c_uint32]
            d.opm_destroy.argtypes = [ctypes.c_void_p]
            d.opm_write.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint8]
            d.opm_read.restype = ctypes.c_uint8
            d.opm_read.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            d.opm_generate.argtypes = [ctypes.c_void_p,
                                       ctypes.POINTER(ctypes.c_int16),
                                       ctypes.c_uint32]
            cls._dll = d
        return cls._dll

    def __init__(self, clock: int = 3_579_545, flags: int = 0, dll_path: str = DEFAULT_DLL):
        self.clock = clock
        self._sr = clock // 64
        self._dll = self.load(dll_path)
        self._h = self._dll.opm_create(flags)
        if not self._h:
            raise RuntimeError("opm_create 失败")

    def write(self, reg: int, val: int) -> None:
        # 新的 DLL wrapper 内部已经推进了时钟，直接写即可
        self._dll.opm_write(self._h, 0, reg & 0xFF)
        self._dll.opm_write(self._h, 1, val & 0xFF)

    def read_status(self) -> int:
        return self._dll.opm_read(self._h, 1)

    def sample_rate(self) -> int:
        return self._sr

    def generate(self, nframes: int) -> bytes:
        buf = (ctypes.c_int16 * (2 * nframes))()
        self._dll.opm_generate(self._h, buf, nframes)
        return bytes(buf)

    def close(self) -> None:
        if self._h:
            self._dll.opm_destroy(self._h)
            self._h = None