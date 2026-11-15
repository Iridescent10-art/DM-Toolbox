# -*- coding: utf-8 -*-
"""
枚举当前运行中的游戏进程（任务管理器式），供「从进程添加游戏」使用。

只依赖 ctypes（psapi / kernel32 / user32），不需要第三方库。
"""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from pathlib import Path

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

# 这些进程即使有窗口也不是游戏，直接排除
_BLOCKED_NAMES = {
    "explorer.exe", "steam.exe", "steamwebhelper.exe", "epicgameslauncher.exe",
    "wegame.exe", "rockstar*.exe", "socialclubhelper.exe", "battle.net.exe",
    "galaxyclient.exe", "eadesktop.exe", "ubisoftconnect.exe", "upc.exe",
    "python.exe", "pythonw.exe", "dm-box.exe", "dm-toolbox.exe", "dmbox.exe",
    "conhost.exe", "cmd.exe", "powershell.exe", "pwsh.exe", "windowsterminal.exe",
    "notepad.exe", "code.exe", "chrome.exe", "msedge.exe", "firefox.exe",
    "discord.exe", "qq.exe", "wechat.exe", "weixin.exe", "cloudmusic.exe",
    "nvidia app.exe", "nvcontainer.exe", "msi afterburner.exe", "rtss.exe",
}

_SYSTEM_DIRS = (
    os.environ.get("SystemRoot", r"C:\Windows").lower(),
    os.environ.get("ProgramFiles", r"C:\Program Files").lower() + r"\windowsapps",
)


def _is_candidate(name: str, path: str) -> bool:
    """判断某个进程是否值得作为「游戏」候选（纯函数，便于测试）。"""
    if not name or not path:
        return False
    lower_name = name.lower()
    lower_path = path.lower().replace("/", "\\")
    if not lower_name.endswith(".exe"):
        return False
    if lower_name in _BLOCKED_NAMES:
        return False
    # 带通配的拦截项（如 rockstar*.exe）
    for blocked in _BLOCKED_NAMES:
        if "*" in blocked:
            import fnmatch
            if fnmatch.fnmatch(lower_name, blocked):
                return False
    if lower_path.startswith(_SYSTEM_DIRS[0] + "\\") and "\\games\\" not in lower_path:
        return False
    if lower_path.startswith(_SYSTEM_DIRS[1]):
        return False
    # 排除常见的安装器 / 更新器 / 崩溃报告
    for bad in ("unins", "setup", "installer", "crash", "updater", "helper"):
        if bad in lower_name:
            return False
    return True


def _visible_window_pids() -> set[int]:
    """返回拥有可见顶层窗口的 PID 集合（用于把真正的游戏排前面）。"""
    pids: set[int] = set()
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def _cb(hwnd, _lparam):
            try:
                if user32.IsWindowVisible(hwnd):
                    pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    if pid.value:
                        pids.add(int(pid.value))
            except Exception:
                pass
            return True

        user32.EnumWindows(EnumWindowsProc(_cb), 0)
    except Exception:
        pass
    return pids


def _process_image_path(pid: int) -> str:
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(buf))
            if not kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return ""
            return buf.value
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return ""


def list_running_processes() -> list[dict]:
    """
    返回当前进程列表：
      [{"pid": int, "name": str, "path": str, "has_window": bool}, ...]
    有可见窗口的排前面，其次按名字排序。
    """
    results: dict[str, dict] = {}
    try:
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        arr = (wintypes.DWORD * 4096)()
        needed = wintypes.DWORD()
        if not psapi.EnumProcesses(ctypes.byref(arr), ctypes.sizeof(arr), ctypes.byref(needed)):
            return []
        count = needed.value // ctypes.sizeof(wintypes.DWORD)
        pids = [int(arr[i]) for i in range(count)]
    except Exception:
        return []

    window_pids = _visible_window_pids()
    for pid in pids:
        if pid <= 0:
            continue
        path = _process_image_path(pid)
        if not path:
            continue
        name = Path(path).name
        key = path.lower()
        if key in results:
            # 同一程序多开：保留有窗口的那个
            if pid in window_pids:
                results[key]["has_window"] = True
            continue
        if not _is_candidate(name, path):
            continue
        results[key] = {
            "pid": pid,
            "name": name,
            "path": path,
            "has_window": pid in window_pids,
        }

    return sorted(
        results.values(),
        key=lambda item: (not item["has_window"], item["name"].lower()),
    )
