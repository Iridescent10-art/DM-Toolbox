# -*- coding: utf-8 -*-
"""小黑盒桌面版 helper 运行时拦截（IFEO + C# shim）。

小黑盒 2.x 的扩展包有内容哈希校验，改 hardware.mjs 会被重新下载；
这里不改任何安装文件，而是给 hardware-windows-helper.exe 注册 IFEO Debugger：
  小黑盒启动 helper 时，Windows 先运行我们的 HeyboxHelperShim.exe
  （参数为原 helper 路径 + 原参数），shim 再运行复制出来的 helper_real.exe，
  拿到 stdout JSON 后按 ToolboxMaster 配置改写硬件字段，再输出给小黑盒。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import winreg
from pathlib import Path
from typing import List, Optional

HELPER_NAME = "hardware-windows-helper.exe"
SHIM_EXE = "HeyboxHelperShim.exe"
IFEO_KEY = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\hardware-windows-helper.exe"
SHIM_ROOT = Path(os.environ.get("PUBLIC", r"C:\Users\Public")) / "DMBOX" / "heybox-helper"


def _desktop_dirs() -> List[Path]:
    try:
        from heybox_desktop_patch import find_desktop_dirs
        return find_desktop_dirs()
    except Exception:
        return []


def find_helper_packages() -> List[Path]:
    """返回包含 native/x64/hardware-windows-helper.exe 的扩展包目录（优先当前部署目录）。"""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return []
    root = Path(appdata) / "HeyboxDesktop" / "desktop" / "extension-artifacts" / "v1" / "packages"
    if not root.is_dir():
        return []

    # 先从部署状态里找出当前硬件扩展目录
    active_names: List[str] = []
    try:
        state = Path(appdata) / "HeyboxDesktop" / "desktop" / "extension-deployments" / "v1" / "state.json"
        if state.exists():
            data = json.loads(state.read_text(encoding="utf-8"))
            for dep in (data.get("deployments") or {}).values():
                if not isinstance(dep, dict):
                    continue
                if dep.get("packageId") != "ai-desktop.hardware-detect":
                    continue
                for rev in dep.get("revisions") or []:
                    if rev.get("revisionId"):
                        active_names.append(str(rev["revisionId"]).split(":")[-1])
    except Exception:
        pass

    def sort_key(p: Path):
        name = p.name
        active = any(name.startswith(n) for n in active_names)
        return (0 if active else 1, -p.stat().st_mtime)

    found = [p for p in root.iterdir() if p.is_dir() and (p / "native" / "x64" / HELPER_NAME).exists()]
    found.sort(key=sort_key)
    return found


def _shim_source() -> Optional[Path]:
    here = Path(__file__).resolve().parent
    cand = here / SHIM_EXE
    return cand if cand.exists() else None


def _copy_tree(src: Path, dst: Path):
    if dst.exists():
        shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(src, dst)


def install_ifEO() -> str:
    """安装/刷新 IFEO 拦截，返回状态描述。调用者需要管理员权限。"""
    pkgs = find_helper_packages()
    if not pkgs:
        return "未找到小黑盒硬件扩展（请先打开一次小黑盒桌面版）"
    src = _shim_source()
    if not src:
        return f"缺少 {SHIM_EXE}，安装包可能不完整"

    pkg = pkgs[0]
    try:
        _copy_tree(pkg, SHIM_ROOT)
    except Exception as e:
        return f"复制 shim 目录失败: {e}"

    native = SHIM_ROOT / "native" / "x64"
    real_helper = native / "helper_real.exe"
    try:
        shutil.copy2(native / HELPER_NAME, real_helper)
        shutil.copy2(src, native / SHIM_EXE)
    except Exception as e:
        return f"准备 shim 文件失败: {e}"

    try:
        with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, IFEO_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, "Debugger", 0, winreg.REG_SZ, str(native / SHIM_EXE))
        return f"已启用运行时拦截: {native / SHIM_EXE}"
    except PermissionError:
        return "没有管理员权限，无法写入 IFEO（请以管理员身份运行工具箱）"
    except Exception as e:
        return f"写入 IFEO 失败: {e}"


def remove_ifEO() -> str:
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, IFEO_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, "Debugger")
    except FileNotFoundError:
        pass
    except PermissionError:
        return "没有管理员权限，无法移除 IFEO"
    except Exception:
        pass
    try:
        winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, IFEO_KEY)
    except Exception:
        pass
    try:
        if SHIM_ROOT.exists():
            shutil.rmtree(SHIM_ROOT, ignore_errors=True)
    except Exception:
        pass
    return "已关闭小黑盒运行时拦截"


def ifEO_status() -> str:
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, IFEO_KEY, 0, winreg.KEY_READ) as k:
            val, _ = winreg.QueryValueEx(k, "Debugger")
            return f"运行中: {val}"
    except Exception:
        return "未启用"
