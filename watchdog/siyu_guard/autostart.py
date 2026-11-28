"""Per-user login startup; requires no administrator privileges."""

import hashlib
import os
import subprocess
import sys

from siyu_guard.guard import peer_command
from siyu_guard.storage import data_root


def value_name() -> str:
    identity = hashlib.sha256(os.path.normcase(str(data_root())).encode("utf-8")).hexdigest()[:12]
    return "SiyuWatchdog-" + identity


def enable_autostart() -> None:
    if os.name != "nt" or not getattr(sys, "frozen", False):
        raise RuntimeError("请使用安装包设置自启")
    import winreg
    action = subprocess.list2cmdline(peer_command("sentinel"))
    path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0,
                        winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE) as key:
        try:
            existing, _ = winreg.QueryValueEx(key, value_name())
        except FileNotFoundError:
            existing = None
        if existing is not None and existing != action:
            raise RuntimeError("已有不同路径的自启项，请先处理旧版本")
        winreg.SetValueEx(key, value_name(), 0, winreg.REG_SZ, action)
