# ssg_core.py
import ctypes
import os
from array import array # 【新增】

class SsgCore:
    def __init__(self):
        dll_path = os.path.join(os.path.dirname(__file__), "ssg.dll")
        self.dll = ctypes.CDLL(dll_path)
        
        self.dll.ssg_create.restype = ctypes.c_void_p
        self.dll.ssg_write.argtypes = [ctypes.c_void_p, ctypes.c_uint8, ctypes.c_uint8]
        self.dll.ssg_generate.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int16), ctypes.c_int]
        self.dll.ssg_destroy.argtypes = [ctypes.c_void_p]
        
        self.handle = self.dll.ssg_create()
        self.write(0x07, 0x3F)

    def write(self, reg: int, val: int):
        self.dll.ssg_write(self.handle, reg, val)

    def generate(self, nframes: int) -> array:
        buf = (ctypes.c_int16 * nframes)()
        self.dll.ssg_generate(self.handle, buf, nframes)
        # 【修复】：直接把 C 的内存块转成 array，零对象开销
        arr = array('h')
        arr.frombytes(bytes(buf))
        return arr

    def close(self):
        if self.handle:
            self.dll.ssg_destroy(self.handle)
            self.handle = None