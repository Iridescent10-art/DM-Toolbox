# -*- coding: utf-8 -*-
"""还原被“统一改名”波及的核显/其它显卡描述。

apply_config.ps1 早期版本会把所有非虚拟显卡的 DriverDesc/DeviceDesc 都改成目标显卡名，
导致核显（AMD/Intel）也显示成 RTX 4070。这里从各显卡驱动 INF 中找回原始型号并写回。
"""

from __future__ import annotations

import re
import winreg
from pathlib import Path
from typing import Optional, Tuple

CLASS_KEY = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
ENUM_PCI = r"SYSTEM\CurrentControlSet\Enum\PCI"
DX_KEY = r"SOFTWARE\Microsoft\DirectX"
INF_DIR = Path(r"C:\Windows\INF")

WANTED_VENDORS = {0x1002: "AMD", 0x8086: "Intel"}


def _read_inf_text(path: Path) -> str:
    data = path.read_bytes()
    for enc in ("utf-16", "utf-8-sig", "mbcs", "latin-1"):
        try:
            return data.decode(enc)
        except Exception:
            continue
    return ""


def _resolve_inf_name(inf_path: Path, ven: int, dev: int) -> Optional[str]:
    if not inf_path.exists():
        return None
    text = _read_inf_text(inf_path)
    if not text:
        return None
    pattern = re.compile(rf"VEN_{ven:04X}&DEV_{dev:04X}", re.IGNORECASE)
    strings = {}
    in_strings = False
    for line in text.splitlines():
        raw = line.strip()
        if raw.startswith("["):
            in_strings = raw.lower() == "[strings]"
            continue
        if in_strings and "=" in raw:
            k, v = raw.split("=", 1)
            strings[k.strip().strip('"').lower()] = v.strip().strip('"')
    for line in text.splitlines():
        if not pattern.search(line) or "=" not in line:
            continue
        lhs = line.split("=", 1)[0].strip().strip('"')
        m = re.fullmatch(r"%([^%]+)%", lhs)
        if m:
            resolved = strings.get(m.group(1).strip().lower())
            if resolved:
                return resolved
            continue
        if lhs and not lhs.startswith("["):
            return lhs
    return None


def _set(key, name, value):
    try:
        winreg.SetValueEx(key, name, 0, winreg.REG_SZ, str(value))
    except Exception:
        pass


def repair_gpu_descriptors(dry_run: bool = False) -> list:
    """返回修复的 [(vendor, device, name)]；需要管理员权限。"""
    fixed = []
    try:
        access = winreg.KEY_READ if dry_run else (winreg.KEY_READ | winreg.KEY_SET_VALUE)
        class_root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, CLASS_KEY, 0, access)
    except PermissionError:
        return fixed
    except OSError:
        return fixed

    with class_root:
        i = 0
        while True:
            try:
                sub_name = winreg.EnumKey(class_root, i)
            except OSError:
                break
            i += 1
            if not re.fullmatch(r"\d{4}", sub_name):
                continue
            try:
                sub_access = winreg.KEY_READ if dry_run else (winreg.KEY_READ | winreg.KEY_SET_VALUE)
                sub = winreg.OpenKey(class_root, sub_name, 0, sub_access)
            except OSError:
                continue
            with sub:
                def get(name):
                    try:
                        return winreg.QueryValueEx(sub, name)[0]
                    except OSError:
                        return None

                matching = str(get("MatchingDeviceId") or "")
                provider = str(get("ProviderName") or "")
                desc = str(get("DriverDesc") or "")
                inf = get("InfPath")
                m = re.search(r"VEN_([0-9A-F]{4})&DEV_([0-9A-F]{4})", matching, re.IGNORECASE)
                if not m:
                    continue
                ven, dev = int(m.group(1), 16), int(m.group(2), 16)
                if ven not in WANTED_VENDORS:
                    continue
                # 已经是正常描述就不动
                if desc and not re.search(r"nvidia|geforce|rtx|gtx", desc, re.IGNORECASE):
                    continue
                original = None
                if inf:
                    original = _resolve_inf_name(INF_DIR / str(inf), ven, dev)
                if not original:
                    original = "AMD Radeon(TM) Graphics" if ven == 0x1002 else "Intel(R) Graphics"
                if dry_run:
                    fixed.append((ven, dev, original))
                    continue
                _set(sub, "DriverDesc", original)
                _set(sub, "HardwareInformation.ChipType", original)
                _set(sub, "HardwareInformation.AdapterString", original)
                # Enum 实例
                try:
                    enum_root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, ENUM_PCI, 0, winreg.KEY_READ)
                    with enum_root:
                        j = 0
                        while True:
                            try:
                                kname = winreg.EnumKey(enum_root, j)
                            except OSError:
                                break
                            j += 1
                            if not re.search(rf"VEN_{ven:04X}&DEV_{dev:04X}", kname, re.IGNORECASE):
                                continue
                            inst_root = winreg.OpenKey(enum_root, kname, 0, winreg.KEY_READ)
                            with inst_root:
                                try:
                                    inst = winreg.EnumKey(inst_root, 0)
                                except OSError:
                                    continue
                                try:
                                    inst_key = winreg.OpenKey(inst_root, inst, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE)
                                except OSError:
                                    continue
                                with inst_key:
                                    _set(inst_key, "DeviceDesc", original)
                                    _set(inst_key, "FriendlyName", original)
                except OSError:
                    pass
                # DirectX 适配器描述
                try:
                    dx_root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, DX_KEY, 0, winreg.KEY_READ)
                    with dx_root:
                        j = 0
                        while True:
                            try:
                                gname = winreg.EnumKey(dx_root, j)
                            except OSError:
                                break
                            j += 1
                            try:
                                gkey = winreg.OpenKey(dx_root, gname, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE)
                            except OSError:
                                continue
                            with gkey:
                                try:
                                    v_id = winreg.QueryValueEx(gkey, "VendorId")[0]
                                    d_id = winreg.QueryValueEx(gkey, "DeviceId")[0]
                                except OSError:
                                    continue
                                if int(v_id) == ven and int(d_id) == dev:
                                    _set(gkey, "Description", original)
                except OSError:
                    pass
                fixed.append((ven, dev, original))
    return fixed
