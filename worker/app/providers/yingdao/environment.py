import ctypes
import os
from pathlib import Path


REQUIRED_YINGDAO_VERSION = "6.3.6"


class _VSFixedFileInfo(ctypes.Structure):
    _fields_ = [
        ("signature", ctypes.c_uint32), ("structure_version", ctypes.c_uint32),
        ("file_version_ms", ctypes.c_uint32), ("file_version_ls", ctypes.c_uint32),
        ("product_version_ms", ctypes.c_uint32), ("product_version_ls", ctypes.c_uint32),
        ("file_flags_mask", ctypes.c_uint32), ("file_flags", ctypes.c_uint32),
        ("file_os", ctypes.c_uint32), ("file_type", ctypes.c_uint32),
        ("file_subtype", ctypes.c_uint32), ("file_date_ms", ctypes.c_uint32),
        ("file_date_ls", ctypes.c_uint32),
    ]


def read_windows_file_version(path: Path) -> str:
    if os.name != "nt":
        raise OSError("Windows file version metadata is unavailable")
    version_api = ctypes.WinDLL("version", use_last_error=True)
    size = version_api.GetFileVersionInfoSizeW(str(path), None)
    if size == 0:
        raise OSError(ctypes.get_last_error(), "File version metadata is unavailable")
    buffer = ctypes.create_string_buffer(size)
    if not version_api.GetFileVersionInfoW(str(path), 0, size, buffer):
        raise OSError(ctypes.get_last_error(), "File version metadata is unreadable")
    pointer = ctypes.c_void_p()
    length = ctypes.c_uint()
    if not version_api.VerQueryValueW(buffer, "\\", ctypes.byref(pointer), ctypes.byref(length)):
        raise OSError(ctypes.get_last_error(), "File version metadata is invalid")
    info = ctypes.cast(pointer, ctypes.POINTER(_VSFixedFileInfo)).contents
    parts = [info.file_version_ms >> 16, info.file_version_ms & 0xFFFF,
             info.file_version_ls >> 16, info.file_version_ls & 0xFFFF]
    if parts[-1] == 0:
        parts.pop()
    return ".".join(str(value) for value in parts)
