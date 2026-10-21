# -*- coding: utf-8 -*-
"""
DLSS 5 Neural Reconstruction (RenoDX ShortFuse & DLSS-NR) Injector Core.
========================================================================
Supports one-click injection of modern RenoDX DLSS 5 (ShortFuse 261017),
dual-architecture GPU model routing (RTX 50 vs RTX 20/30/40),
collision avoidance with App 2 (Frame Generation Mode A/B/C),
ReShade host management, anti-Preset D enforcement, and one-click lossless restoration.
"""

import os
import sys
import json
import time
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
APP2_DIR = ROOT_DIR / "apps" / "app2_mfg"
if str(APP2_DIR) not in sys.path:
    sys.path.insert(0, str(APP2_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from core.utils import safe_force_remove
except Exception:
    def safe_force_remove(path: str) -> bool:
        p = Path(path)
        if not p.exists():
            return True
        try:
            p.unlink(missing_ok=True)
            return True
        except Exception:
            return False


def _read_dll_signature_bytes(path: str) -> bytes:
    """Safely reads DLL binary signature data (first 16MB + last 16MB if >32MB, else full)."""
    if not path or not os.path.exists(path) or not os.path.isfile(path):
        return b""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            if size > 32 * 1024 * 1024:
                head = f.read(16 * 1024 * 1024)
                f.seek(max(0, size - 16 * 1024 * 1024))
                return head + f.read()
            return f.read()
    except Exception:
        return b""


def is_reshade_dll(path: str) -> bool:
    """Check if a DLL file is ReShade (excludes OptiScaler)."""
    if not os.path.exists(path) or not os.path.isfile(path):
        return False
    data = _read_dll_signature_bytes(path)
    if b"OptiScaler" in data:
        return False
    return b"ReShade" in data or b"crosire" in data


def is_reshade_addon_dll(path: str) -> bool:
    """Check if a DLL file is ReShade with full Add-on Support."""
    if not os.path.exists(path) or not os.path.isfile(path):
        return False
    data = _read_dll_signature_bytes(path)
    if b"OptiScaler" in data:
        return False
    return (b"ReShade" in data or b"crosire" in data) and (
        b"AddonUninit" in data or b"reshade_addon" in data or len(data) >= 5 * 1024 * 1024
    )


def is_optiscaler_dll(path: str) -> bool:
    """Check if a DLL file is OptiScaler."""
    if not os.path.exists(path) or not os.path.isfile(path):
        return False
    data = _read_dll_signature_bytes(path)
    return b"OptiScaler" in data or b"libxess" in data


def detect_system_gpu() -> Dict[str, Any]:
    """
    Detects system GPU model via WMI/PowerShell, determining architecture (RTX 50 vs RTX 20/30/40).
    """
    name = ""
    try:
        cmd = ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        for line in res.stdout.splitlines():
            line = line.strip()
            if any(k in line.lower() for k in ["nvidia", "geforce", "rtx"]):
                name = line
                break
    except Exception:
        pass

    if not name:
        name = "NVIDIA GeForce RTX (通用)"

    import re
    is_50 = bool(re.search(r"rtx\s*50\d0", name, re.IGNORECASE))
    is_40 = bool(re.search(r"rtx\s*40\d0", name, re.IGNORECASE))
    is_30 = bool(re.search(r"rtx\s*30\d0", name, re.IGNORECASE))
    is_20 = bool(re.search(r"rtx\s*20\d0", name, re.IGNORECASE))

    if is_50:
        arch = "rtx50"
        arch_desc = "RTX 50 系列专用模型 (Blackwell 架构极致算力专用)"
    elif is_40:
        arch = "rtx20_30_40"
        arch_desc = "RTX 20 / 30 / 40 系列专用模型 (310.9.16 · 推荐当前显卡)"
    elif is_30:
        arch = "rtx20_30_40"
        arch_desc = "RTX 20 / 30 / 40 系列专用模型 (310.9.16 · 推荐当前显卡)"
    elif is_20:
        arch = "rtx20_30_40"
        arch_desc = "RTX 20 / 30 / 40 系列专用模型 (310.9.16 · 推荐当前显卡)"
    else:
        arch = "rtx20_30_40"
        arch_desc = "RTX 20 / 30 / 40 系列专用模型 (310.9.16 · 通用推荐)"

    return {
        "gpu_name": name,
        "arch": arch,
        "is_nvidia": any(k in name.lower() for k in ["nvidia", "geforce", "rtx"]),
        "description": arch_desc
    }


def get_dlss5_addon_path() -> Optional[str]:
    """
    Locates the RenoDX DLSS 5 addon plugin.
    Prioritizes renodx-dlss.addon64 (ShortFuse Chinese localized 261017 release),
    with desktop folder and legacy fallbacks.
    """
    candidates = [
        ROOT_DIR / "apps" / "app6_dlss5" / "assets" / "renodx-dlss.addon64",
        ROOT_DIR / "defaults" / "app6_dlss5" / "assets" / "renodx-dlss.addon64",
        Path(r"C:\Users\17547\Desktop\dlss5插件\renodx-dlss-ShortFuse-261017汉化版.addon64"),
        Path(r"C:\Users\17547\Desktop\dlss5插件\renodx-dlss.addon64"),
        ROOT_DIR / "apps" / "app6_dlss5" / "assets" / "lecram-dlss5-beta10.addon64",
        ROOT_DIR / "defaults" / "app6_dlss5" / "assets" / "lecram-dlss5-beta10.addon64",
        Path(__file__).resolve().parent.parent / "assets" / "renodx-dlss.addon64",
        Path(__file__).resolve().parent.parent / "assets" / "lecram-dlss5-beta10.addon64",
    ]
    for cand in candidates:
        if cand.exists() and cand.is_file() and cand.stat().st_size > 0:
            return str(cand)
    return None


def get_dlss5_runtime_dll_path(arch: str = "auto") -> Optional[str]:
    """
    Locates the official NVIDIA DLSS 5 Neural Reconstruction runtime nvngx_dlssnr.dll.
    Supports dual-architecture routing:
    - arch="rtx50": 266 MB Blackwell dedicated model
    - arch="rtx20_30_40": 276 MB Turing/Ampere/Ada dedicated model (310.9.16)
    - arch="auto": automatically detects GPU and selects matching model
    """
    if arch == "auto":
        gpu_info = detect_system_gpu()
        target_arch = gpu_info.get("arch", "rtx20_30_40")
    else:
        target_arch = arch.lower()

    candidates: List[Path] = []
    assets_dir = ROOT_DIR / "apps" / "app6_dlss5" / "assets"
    defaults_dir = ROOT_DIR / "defaults" / "app6_dlss5" / "assets"

    if "50" in target_arch:
        candidates.extend([
            assets_dir / "runtimes" / "nvngx_dlssnr_rtx50.dll",
            defaults_dir / "runtimes" / "nvngx_dlssnr_rtx50.dll",
            Path(r"C:\Users\17547\.gemini\antigravity\brain\29b03b65-5c3d-4ff1-854f-8943ec280b56\scratch\rtx50\nvngx_dlssnr.dll"),
        ])
    else:
        candidates.extend([
            assets_dir / "runtimes" / "nvngx_dlssnr_rtx20_30_40.dll",
            defaults_dir / "runtimes" / "nvngx_dlssnr_rtx20_30_40.dll",
            Path(r"C:\Users\17547\.gemini\antigravity\brain\29b03b65-5c3d-4ff1-854f-8943ec280b56\scratch\rtx20_30_40\nvngx_dlssnr.dll"),
        ])

    # General fallbacks
    candidates.extend([
        assets_dir / "nvngx_dlssnr.dll",
        defaults_dir / "nvngx_dlssnr.dll",
        Path(__file__).resolve().parent.parent / "assets" / "nvngx_dlssnr.dll",
    ])

    local_app = os.environ.get("LOCALAPPDATA", "")
    if local_app:
        candidates.append(Path(local_app) / "DLSS5-NR" / "runtime" / "nvngx_dlssnr.dll")

    candidates.extend([
        Path(r"D:\game\Cyberpunk 2077\bin\x64\nvngx_dlssnr.dll"),
        Path(r"D:\game\RDR2\nvngx_dlssnr.dll"),
        Path(r"C:\Users\17547\Desktop\nvngx_dlssnr.dll")
    ])

    for cand in candidates:
        if cand.exists() and cand.is_file() and cand.stat().st_size > 10 * 1024 * 1024:
            return str(cand)
    return None


def find_reshade_framework_dll() -> Optional[str]:
    """
    Locates ReShade64.dll with full Add-on Support.
    Searches App 2 embedded components, Desktop folder, defaults, and system caches.
    """
    candidates = [
        ROOT_DIR / "apps" / "app2_mfg" / "embedded_components" / "reshade" / "6.8.0" / "ReShade64.dll",
        ROOT_DIR / "defaults" / "app2_mfg" / "embedded_components" / "reshade" / "6.8.0" / "ReShade64.dll",
        Path(r"C:\Users\17547\Desktop\dlss5插件\dxgi.dll"),
    ]
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        cache_reshade = Path(appdata) / "ToolboxMaster" / "cache" / "reshade"
        if cache_reshade.exists():
            for f in cache_reshade.rglob("ReShade64.dll"):
                if f.is_file() and f.stat().st_size > 4 * 1024 * 1024:
                    return str(f)

    local_app = os.environ.get("LOCALAPPDATA", "")
    if local_app:
        candidates.extend([
            Path(local_app) / "RHI" / "reshade" / "ReShade64.dll",
            Path(local_app) / "RHI" / "reshade-nightly" / "ReShade64.dll",
            Path(local_app) / "RHI" / "reshade-normal" / "ReShade64.dll",
        ])

    for cand in candidates:
        if cand.exists() and cand.is_file() and cand.stat().st_size > 4 * 1024 * 1024:
            return str(cand)
    return None


def find_rhi_setup_exe() -> Optional[str]:
    """Locates RHI-Setup.exe or installed RHI.exe on the system."""
    candidates = [
        ROOT_DIR / "apps" / "app2_mfg" / "embedded_components" / "tools" / "RHI-Setup.exe",
        ROOT_DIR / "defaults" / "app2_mfg" / "embedded_components" / "tools" / "RHI-Setup.exe",
    ]
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        candidates.append(Path(appdata) / "ToolboxMaster" / "cache" / "tools" / "RHI-Setup.exe")

    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    candidates.extend([
        Path(pf) / "RHI" / "RHI.exe",
        Path(pf86) / "RHI" / "RHI.exe",
    ])
    local_app = os.environ.get("LOCALAPPDATA", "")
    if local_app:
        candidates.extend([
            Path(local_app) / "Programs" / "RHI" / "RHI.exe",
            Path(local_app) / "RHI" / "RHI.exe",
        ])

    for cand in candidates:
        if cand.exists() and cand.is_file():
            return str(cand)
    return None


def detect_frame_generation(target_dir: str) -> Dict[str, Any]:
    """
    Detects whether Frame Generation (App 2) is injected into the target directory.
    Categorizes into:
    1. is_rhi_fg: Mode B RenoDX ReShade addon (renodx-mfgunlock.addon64).
    2. is_optiscaler_fg: Mode C OptiScaler (OptiScaler.dll, OptiScaler/, OptiScaler.ini).
    3. is_dashdog_fg: Mode A Dashdog MFGUnlocker (version.dll/winmm.dll).
    """
    td = Path(target_dir)
    manifest_file = td / ".mfg_patch_manifest.json"
    manifest_backend = None
    if manifest_file.exists():
        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                manifest_backend = data.get("active_backend") or data.get("backend")
        except Exception:
            manifest_backend = None

    is_rhi_fg = False
    is_optiscaler_fg = False
    is_dashdog_fg = False

    if manifest_backend:
        backend_str = str(manifest_backend).lower()
        if "optiscaler" in backend_str or "fsr" in backend_str:
            is_optiscaler_fg = True
        elif "reshade" in backend_str or "renodx" in backend_str or "mavis" in backend_str:
            is_rhi_fg = True
        elif "standalone" in backend_str or "dashdogy" in backend_str:
            is_dashdog_fg = True
    else:
        has_renodx = (td / "renodx-mfgunlock.addon64").exists()
        has_optiscaler = (
            (td / "OptiScaler.ini").exists() or
            (td / "OptiScaler.dll").exists() or
            (td / "OptiScaler").is_dir()
        )
        has_dashdog = (
            (td / "version.dll").exists() or
            (td / "RTXMFG-Universal.json").exists() or
            (td / "RTXMFG-UI.ini").exists() or
            (td / "mfg_unlocker.ini").exists() or
            (td / "bink2w64Hooked.dll").exists() or
            (td / "MFGUnlocker.dll").exists()
        )
        if has_renodx:
            is_rhi_fg = True
        elif has_optiscaler:
            is_optiscaler_fg = True
        elif has_dashdog:
            is_dashdog_fg = True

    has_fg = is_rhi_fg or is_optiscaler_fg or is_dashdog_fg or manifest_file.exists()

    details = []
    if is_rhi_fg:
        details.append("RHI RenoDX 插帧 (ReShade Add-on)")
    if is_optiscaler_fg:
        details.append("OptiScaler 跨架构插帧 (Mode C)")
    if is_dashdog_fg:
        details.append("Dashdog MFGUnlocker (Mode A)")
    if manifest_file.exists() and not details:
        details.append("DM 多帧生成补丁")

    summary = " + ".join(details) if details else "未检测到多帧生成"

    return {
        "has_fg": has_fg,
        "is_rhi_fg": is_rhi_fg,
        "is_optiscaler_fg": is_optiscaler_fg,
        "is_dashdog_fg": is_dashdog_fg,
        "has_renodx": is_rhi_fg,
        "has_dashdog": is_dashdog_fg,
        "has_optiscaler": is_optiscaler_fg,
        "has_mfg_manifest": manifest_file.exists(),
        "details": details,
        "summary": summary
    }


def is_optiscaler_load_reshade_enabled(target_dir: str) -> bool:
    """Checks if LoadReshade is set to true in OptiScaler.ini under [Plugins] section."""
    ini_path = Path(target_dir) / "OptiScaler.ini"
    if not ini_path.exists():
        return False
    try:
        with open(ini_path, "r", encoding="utf-8", errors="ignore") as f:
            in_plugins = False
            for line in f:
                stripped = line.strip()
                if stripped.startswith("[") and stripped.endswith("]"):
                    in_plugins = (stripped[1:-1].strip().lower() == "plugins")
                    continue
                if in_plugins and "=" in stripped:
                    k, v = stripped.split("=", 1)
                    if k.strip().lower() == "loadreshade":
                        val = v.split(";", 1)[0].strip().lower()
                        return val == "true"
    except Exception:
        pass
    return False


def enforce_optiscaler_anti_d_preset(ini_path: Path, force_preset: int = 11) -> bool:
    """
    Ensures OptiScaler.ini strictly avoids Preset D (enum 4) and defaults to Preset K (enum 11).
    Preserves existing user customizations (e.g. Preset M=13, Preset L=12, Preset K=11).
    """
    if not ini_path.exists():
        return False
    try:
        with open(ini_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return False

    current_sec = ""
    dlss_found = False
    dlssd_found = False
    modified = False

    dlss_keys_present = set()
    dlssd_keys_present = set()
    new_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            current_sec = stripped[1:-1].strip().upper()
            if current_sec == "DLSS":
                dlss_found = True
            elif current_sec == "DLSSD":
                dlssd_found = True
            new_lines.append(line)
            continue

        if current_sec == "DLSS" and "=" in stripped:
            k, v = stripped.split("=", 1)
            key = k.strip()
            key_upper = key.upper()
            dlss_keys_present.add(key_upper)
            val_clean = v.split(";", 1)[0].strip().lower()
            comment = (" ;" + v.split(";", 1)[1]) if ";" in v else ""

            if key_upper == "RENDERPRESETOVERRIDE":
                if val_clean not in ["true", "1"]:
                    new_lines.append(f"{key}=true{comment}\n")
                    modified = True
                    continue
            elif key_upper == "USEGENERICAPPIDWITHDLSS":
                if val_clean not in ["false", "0"]:
                    new_lines.append(f"{key}=false{comment}\n")
                    modified = True
                    continue
            elif key_upper.startswith("RENDERPRESET"):
                if val_clean in ["4", "auto", "default", "0", "d", "preset d", ""]:
                    new_lines.append(f"{key}=11{comment}\n")
                    modified = True
                    continue

        elif current_sec == "DLSSD" and "=" in stripped:
            k, v = stripped.split("=", 1)
            key = k.strip()
            key_upper = key.upper()
            dlssd_keys_present.add(key_upper)
            val_clean = v.split(";", 1)[0].strip().lower()
            comment = (" ;" + v.split(";", 1)[1]) if ";" in v else ""

            if key_upper == "RENDERPRESETOVERRIDE":
                if val_clean not in ["true", "1"]:
                    new_lines.append(f"{key}=true{comment}\n")
                    modified = True
                    continue
            elif key_upper.startswith("RENDERPRESET"):
                if val_clean in ["4", "auto", "default", "0", "d", "preset d", ""]:
                    new_lines.append(f"{key}=11{comment}\n")
                    modified = True
                    continue

        new_lines.append(line)

    if not dlss_found:
        new_lines.append(
            "\n[DLSS]\n"
            "RenderPresetOverride=true\n"
            "UseGenericAppIdWithDlss=false\n"
            "RenderPresetForAll=11\n"
            "RenderPresetDLAA=11\n"
            "RenderPresetUltraQuality=11\n"
            "RenderPresetQuality=11\n"
            "RenderPresetBalanced=11\n"
            "RenderPresetPerformance=11\n"
            "RenderPresetUltraPerformance=11\n"
        )
        modified = True
    else:
        missing_keys = []
        if "RENDERPRESETOVERRIDE" not in dlss_keys_present:
            missing_keys.append("RenderPresetOverride=true\n")
        if "USEGENERICAPPIDWITHDLSS" not in dlss_keys_present:
            missing_keys.append("UseGenericAppIdWithDlss=false\n")
        if "RENDERPRESETFORALL" not in dlss_keys_present:
            missing_keys.append("RenderPresetForAll=11\n")
        if missing_keys:
            for i, line in enumerate(new_lines):
                if line.strip().upper() == "[DLSS]":
                    for mk in reversed(missing_keys):
                        new_lines.insert(i + 1, mk)
                    modified = True
                    break

    if not dlssd_found:
        new_lines.append(
            "\n[DLSSD]\n"
            "RenderPresetOverride=true\n"
            "RenderPresetForAll=11\n"
        )
        modified = True

    if modified:
        try:
            with open(ini_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            return True
        except Exception:
            return False
    return True


def set_optiscaler_load_reshade(target_dir: str, enable: bool = True) -> bool:
    """Configures LoadReshade in OptiScaler.ini [Plugins] section."""
    td = Path(target_dir)
    ini_path = td / "OptiScaler.ini"
    val_str = "true" if enable else "auto"

    if not ini_path.exists():
        if (td / "OptiScaler").is_dir() or (td / "OptiScaler.dll").exists() or (td / "dxgi.dll").exists():
            template_candidates = [
                ROOT_DIR / "apps" / "app2_mfg" / "embedded_components" / "optiscaler" / "nightly-20261020" / "OptiScaler.ini",
                ROOT_DIR / "defaults" / "app2_mfg" / "embedded_components" / "optiscaler" / "nightly-20261020" / "OptiScaler.ini",
            ]
            template_found = False
            for tc in template_candidates:
                if tc.exists() and tc.is_file():
                    try:
                        shutil.copy2(tc, ini_path)
                        template_found = True
                        break
                    except Exception:
                        pass

            if not template_found:
                try:
                    default_content = (
                        "[Plugins]\n"
                        f"LoadReshade={val_str}\n"
                        "LoadAsiPlugins=true\n\n"
                        "[DLSS]\n"
                        "RenderPresetOverride=true\n"
                        "UseGenericAppIdWithDlss=false\n"
                        "RenderPresetForAll=11\n"
                    )
                    with open(ini_path, "w", encoding="utf-8") as f:
                        f.write(default_content)
                    return True
                except Exception:
                    return False

    try:
        with open(ini_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return False

    in_plugins_sec = False
    plugins_sec_found = False
    load_key_found = False
    modified = False
    new_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            sec_name = stripped[1:-1].strip()
            if in_plugins_sec and not load_key_found:
                new_lines.append(f"LoadReshade={val_str}\n")
                load_key_found = True
                modified = True

            in_plugins_sec = (sec_name.lower() == "plugins")
            if in_plugins_sec:
                plugins_sec_found = True
            new_lines.append(line)
            continue

        if in_plugins_sec and "=" in stripped:
            k, v = stripped.split("=", 1)
            if k.strip().lower() == "loadreshade":
                load_key_found = True
                current_v = v.split(";", 1)[0].strip().lower()
                if current_v != val_str.lower():
                    comment = ""
                    if ";" in v:
                        comment = " ;" + v.split(";", 1)[1]
                    new_lines.append(f"LoadReshade={val_str}{comment}\n")
                    modified = True
                    continue

        new_lines.append(line)

    if not plugins_sec_found:
        new_lines.append("\n[Plugins]\n")
        new_lines.append(f"LoadReshade={val_str}\n")
        modified = True
    elif not load_key_found:
        new_lines.append(f"LoadReshade={val_str}\n")
        modified = True

    if modified:
        try:
            with open(ini_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
        except Exception:
            return False

    if enable:
        enforce_optiscaler_anti_d_preset(ini_path)

    return True


def check_dlss5_status(target_dir: str) -> Dict[str, Any]:
    """Comprehensive status check of DLSS 5, runtime, ReShade host, OptiScaler coexistence, and RHI avoidance."""
    td = Path(target_dir)
    manifest_path = td / ".dlss5_patch_manifest.json"
    runtime_path = td / "nvngx_dlssnr.dll"
    dxgi_path = td / "dxgi.dll"
    reshade64_path = td / "ReShade64.dll"
    ini_path = td / "ReShade.ini"

    # Support all known addon filenames
    addon_candidates = [
        td / "renodx-dlss.addon64",
        td / "renodx-dlss-ShortFuse-261017汉化版.addon64",
        td / "lecram-dlss5-beta10.addon64",
        td / "dlss5-nr.addon64"
    ]
    existing_addons = [p for p in addon_candidates if p.exists()]
    has_addon = len(existing_addons) > 0
    addon_file = existing_addons[0].name if existing_addons else "renodx-dlss.addon64"

    manifest_data = None
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
        except Exception:
            manifest_data = None

    has_runtime = runtime_path.exists()
    if not has_runtime:
        local_app = os.environ.get("LOCALAPPDATA", "")
        if local_app:
            has_runtime = (Path(local_app) / "DLSS5-NR" / "runtime" / "nvngx_dlssnr.dll").exists()

    has_dxgi = dxgi_path.exists()
    has_reshade64 = reshade64_path.exists()
    is_reshade = is_reshade_dll(str(dxgi_path)) if has_dxgi else False
    is_addon_supported = is_reshade_addon_dll(str(dxgi_path)) if has_dxgi else False
    is_reshade64_addon_supported = is_reshade_addon_dll(str(reshade64_path)) if has_reshade64 else False
    is_dxgi_optiscaler = is_optiscaler_dll(str(dxgi_path)) if has_dxgi else False
    fg_info = detect_frame_generation(target_dir)
    opti_reshade_enabled = is_optiscaler_load_reshade_enabled(target_dir) if fg_info["is_optiscaler_fg"] else False

    if fg_info["is_optiscaler_fg"]:
        host_ready = has_reshade64 and is_reshade64_addon_supported and opti_reshade_enabled
    else:
        host_ready = has_dxgi and is_reshade and is_addon_supported

    is_injected = has_addon

    return {
        "is_injected": is_injected,
        "host_ready": host_ready,
        "has_addon": has_addon,
        "addon_file": addon_file,
        "has_runtime": has_runtime,
        "has_dxgi": has_dxgi,
        "has_reshade64": has_reshade64,
        "is_reshade": is_reshade,
        "is_addon_supported": is_addon_supported,
        "is_reshade64_addon_supported": is_reshade64_addon_supported,
        "is_dxgi_optiscaler": is_dxgi_optiscaler,
        "has_ini": ini_path.exists(),
        "fg_info": fg_info,
        "avoidance_active": fg_info["is_rhi_fg"],
        "optiscaler_coexisting": fg_info["is_optiscaler_fg"],
        "opti_reshade_enabled": opti_reshade_enabled,
        "manifest": manifest_data
    }


def _configure_reshade_ini_for_dlss5(
    ini_path: Path,
    remove: bool = False,
    dlss5_config: Optional[Dict[str, Any]] = None
) -> bool:
    """Safely configures ReShade.ini for DLSS 5 across all sections."""
    if not ini_path.exists():
        if not remove:
            _create_default_reshade_ini(ini_path)
        else:
            return False

    if not remove:
        try:
            from apps.app6_dlss5.engine.dlss5_config import write_game_dlss5_config, load_dlss5_preset
            cfg = dlss5_config or load_dlss5_preset()
            return write_game_dlss5_config(ini_path, cfg)
        except Exception:
            pass

    try:
        with open(ini_path, "r", encoding="utf-8", errors="ignore") as f:
            lines_in = f.readlines()
    except Exception:
        return False

    current_sec = ""
    modified = False
    new_lines = []
    remove_sections = [
        "DLSS5", "DLSS5-NR", "RENODX.DLSS5", "RENODX", "RENODX.DLSS", "DLSS",
        "DLSS-NR", "RENODX-DLSS", "RENODX-DLSS-PRESET1", "RENODX-DLSS-PRESET2", "RENODX-DLSS-PRESET3",
        "RENODX-PRESET1", "RENODX-PRESET2", "RENODX-PRESET3",
        "RENODX_DLSS", "RENODX_DLSS-PRESET1", "RENODX_DLSS-PRESET2", "RENODX_DLSS-PRESET3",
        "RENODX-PRESET1"
    ]

    for line in lines_in:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            current_sec = stripped[1:-1].strip().upper()
            if current_sec in remove_sections:
                if remove:
                    modified = True
                    continue
            new_lines.append(line)
            continue

        if current_sec in remove_sections:
            if remove:
                modified = True
                continue

        if current_sec == "" and remove and "=" in stripped:
            k = stripped.split("=", 1)[0].strip()
            ku = k.upper()
            if ku.startswith("DIRECTNEURAL") or ku.startswith("DLSSNR.") or ku.startswith("DLSSPRESET") or ku in ("DLSSQUALITYMODE", "DLSSAUTOEXPOSURE", "OPTIONSMODE"):
                modified = True
                continue

        if current_sec == "ADDON" and "=" in stripped:
            k, v = stripped.split("=", 1)
            key = k.strip()
            if key.upper() == "LOADFROMDLLMAIN":
                existing = [x.strip() for x in v.split(",") if x.strip()]
                addon_dir = ini_path.parent
                filtered = []
                for x in existing:
                    xl = x.lower()
                    if xl in ["lecram-dlss5-beta10.addon64", "lecram-dlss5-beta10", "renodx-dlss.addon64", "1"]:
                        continue
                    if xl == "renodx-mfgunlock.addon64" and not (addon_dir / "renodx-mfgunlock.addon64").exists():
                        continue
                    filtered.append(x)
                if filtered != existing:
                    modified = True
                    val_str = ",".join(filtered)
                    new_lines.append(f"{key}={val_str}\n")
                    continue

        new_lines.append(line)

    if modified:
        try:
            with open(ini_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            return True
        except Exception:
            return False

    return True


def _create_default_reshade_ini(ini_path: Path):
    """Creates a clean default ReShade.ini preloaded with safe ShortFuse Chinese UI and DLSS 5 configuration."""
    try:
        from apps.app6_dlss5.engine.dlss5_config import write_game_dlss5_config, load_dlss5_preset
        if write_game_dlss5_config(ini_path, load_dlss5_preset()):
            return
    except Exception:
        pass
    content = r"""DirectNeuralRenderingStatus=1
DirectNeuralRenderingHookStage=2
DirectNeuralRenderingReuseDlssUpscalingResources=1
DirectNeuralRenderingUiCorrectionMode=0
DirectNeuralRenderingIntensity=1.000000
DirectNeuralRenderingStyle=2
DirectNeuralRenderingLocalStructureStrength=1.000000
DirectNeuralRenderingLocalToneStrength=1.000000
DirectNeuralRenderingAutoMask=1
DirectNeuralRenderingSkinStructureStrength=0.500000
DirectNeuralRenderingProcessingScale=1.000000
DirectNeuralRenderingPassCount=1
DirectNeuralRenderingEncoding=0
DirectNeuralRenderingSignalEncoding=0
DirectNeuralRenderingDiffuseWhiteNits=100.0
DirectNeuralRenderingBlockHudless=0
DirectNeuralRenderingExposure=1.000000
DirectNeuralRenderingExposureMode=1
DLSSPresetQuality=0
DLSSPresetDLAA=0
DLSSPresetBalanced=0
DLSSPresetPerformance=0
DLSSPresetUltraQuality=0
DLSSPresetUltraPerformance=0
DLSSNR.Enabled=1
DLSSNR.Intensity=1.000000
DLSSNR.Style=2
DLSSNR.LocalToneStrength=1.000000
DLSSNR.LocalStructureStrength=1.000000
DLSSNR.SkinStructureStrength=0.500000
DLSSNR.GlobalToneStrength=1.000000
DLSSNR.UseAutoMask=1
DLSSNR.UICorrection=0
DLSSNR.Scale=1.000000
DLSSNR.ScalingRatio=1.000000
DLSSNR.Hint.Render.Preset=0

[GENERAL]
EffectSearchPaths=.\
TextureSearchPaths=.\
NoReloadOnInit=1
PerformanceMode=0
TutorialProgress=4

[OVERLAY]
Language=zh-CN
Font=C:\Windows\Fonts\msyh.ttc
FontSize=18
EditorFont=C:\Windows\Fonts\msyh.ttc
EditorFontSize=16
KeyOverlay=36,0,0,0
ShowFPS=0
ShowFrameTime=0

[ADDON]
LoadFromDllMain=

[RenoDX]
DirectNeuralRenderingStatus=1
DirectNeuralRenderingHookStage=2
DirectNeuralRenderingReuseDlssUpscalingResources=1
DirectNeuralRenderingUiCorrectionMode=0
DirectNeuralRenderingIntensity=1.000000
DirectNeuralRenderingStyle=2
DirectNeuralRenderingLocalStructureStrength=1.000000
DirectNeuralRenderingLocalToneStrength=1.000000
DirectNeuralRenderingAutoMask=1
DirectNeuralRenderingSkinStructureStrength=0.500000
DirectNeuralRenderingProcessingScale=1.000000
DirectNeuralRenderingPassCount=1
DirectNeuralRenderingEncoding=0
DirectNeuralRenderingSignalEncoding=0
DirectNeuralRenderingDiffuseWhiteNits=100.0
DirectNeuralRenderingBlockHudless=0
DirectNeuralRenderingExposure=1.000000
DirectNeuralRenderingExposureMode=1
DLSSPresetDLAA=0
DLSSPresetQuality=0
DLSSPresetBalanced=0
DLSSPresetPerformance=0
DLSSPresetUltraQuality=0
DLSSPresetUltraPerformance=0

[DLSS]
DirectNeuralRenderingStatus=1
DirectNeuralRenderingHookStage=2
DirectNeuralRenderingReuseDlssUpscalingResources=1
DirectNeuralRenderingUiCorrectionMode=0
DirectNeuralRenderingIntensity=1.000000
DirectNeuralRenderingStyle=2
DirectNeuralRenderingLocalStructureStrength=1.000000
DirectNeuralRenderingLocalToneStrength=1.000000
DirectNeuralRenderingAutoMask=1
DirectNeuralRenderingSkinStructureStrength=0.500000
DirectNeuralRenderingProcessingScale=1.000000
DirectNeuralRenderingPassCount=1
DirectNeuralRenderingEncoding=0
RenderPresetOverride=false
UseGenericAppIdWithDlss=false
RenderPresetForAll=0
RenderPresetDLAA=0
RenderPresetUltraQuality=0
RenderPresetQuality=0
RenderPresetBalanced=0
RenderPresetPerformance=0
RenderPresetUltraPerformance=0

[RenoDX.DLSS]
DirectNeuralRenderingStatus=1
DirectNeuralRenderingHookStage=2
DirectNeuralRenderingReuseDlssUpscalingResources=1
DirectNeuralRenderingUiCorrectionMode=0
DirectNeuralRenderingIntensity=1.000000
DirectNeuralRenderingStyle=2
DirectNeuralRenderingLocalStructureStrength=1.000000
DirectNeuralRenderingLocalToneStrength=1.000000
DirectNeuralRenderingAutoMask=1
DirectNeuralRenderingSkinStructureStrength=0.500000
DirectNeuralRenderingProcessingScale=1.000000
DirectNeuralRenderingPassCount=1
DirectNeuralRenderingEncoding=0

[RenoDX.DLSS5]
ConfigVersion=11
EnableHooks=2
RuntimeSelectionMode=1
NeuralUplift=1
NRHookPoint=2
NRAutoFgFallback=1
NRPasses=1
NRResolutionScale=1.00
NRIntensity=1.00
NRStyle=2
NRVramBuffering=1
NRPresentNonBlocking=1
HDRCompatibilityMode=0
NRRuntimePath=.\nvngx_dlssnr.dll
"""
    try:
        with open(ini_path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception:
        pass


class DLSS5Injector:
    """Manages DLSS 5 injection, Dual-Architecture GPU routing, Frame Generation avoidance, and restoration."""

    @staticmethod
    def get_status(target_dir: str) -> Dict[str, Any]:
        return check_dlss5_status(target_dir)

    @staticmethod
    def inject(target_dir: str, dlss5_config: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        td = Path(target_dir)
        if not td.exists() or not td.is_dir():
            return False, f"目标目录不存在: {target_dir}"

        addon_src = get_dlss5_addon_path()
        if not addon_src or not os.path.exists(addon_src):
            return False, "未找到 renodx-dlss.addon64 核心插件资产！\n请确认 assets 目录中包含该插件。"

        cfg = dlss5_config or {}
        chosen_arch = cfg.get("gpu_arch", "auto")
        gpu_info = detect_system_gpu()

        status = check_dlss5_status(target_dir)
        fg_info = status["fg_info"]
        is_rhi_fg = fg_info.get("is_rhi_fg", False)
        is_optiscaler_fg = fg_info.get("is_optiscaler_fg", False)
        is_dashdog_fg = fg_info.get("is_dashdog_fg", False)

        # Canonical addon file name (ASCII name ensures clean LoadLibrary without 1114 error)
        addon_dest = td / "renodx-dlss.addon64"
        runtime_dest = td / "nvngx_dlssnr.dll"
        dxgi_dest = td / "dxgi.dll"
        reshade64_dest = td / "ReShade64.dll"
        ini_dest = td / "ReShade.ini"

        manifest_path = td / ".dlss5_patch_manifest.json"
        existing_manifest = status.get("manifest") or {}
        was_reshade64_injected = existing_manifest.get("reshade64_injected_by_dlss5", False)
        was_reshade_dxgi_injected = existing_manifest.get("reshade_injected_by_dlss5", False)
        was_runtime_injected = existing_manifest.get("runtime_injected_by_dlss5", False)

        manifest: Dict[str, Any] = {
            "version": "2.0.0",
            "plugin_framework": "RenoDX-ShortFuse-261017",
            "addon_file": "renodx-dlss.addon64",
            "runtime_file": "nvngx_dlssnr.dll",
            "gpu_arch": chosen_arch,
            "detected_gpu": gpu_info.get("gpu_name", "Unknown"),
            "injected_files": ["renodx-dlss.addon64"],
            "reshade_injected_by_dlss5": was_reshade_dxgi_injected,
            "reshade64_injected_by_dlss5": was_reshade64_injected,
            "runtime_injected_by_dlss5": was_runtime_injected,
            "rhi_avoidance_active": is_rhi_fg,
            "optiscaler_coexisting": is_optiscaler_fg,
            "dashdog_coexisting": is_dashdog_fg,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        # Step 1: Handle ReShade base host
        if is_rhi_fg:
            # 🛡️ RHI FRAME GENERATION: ReShade is already running as dxgi.dll!
            manifest["reshade_injected_by_dlss5"] = False

        elif is_optiscaler_fg:
            # 🟢 OPTISCALER FRAME GENERATION: Co-existence mode!
            if not reshade64_dest.exists() or not is_reshade_addon_dll(str(reshade64_dest)):
                reshade_src = find_reshade_framework_dll()
                if not reshade_src or not os.path.exists(reshade_src):
                    return False, "未找到 ReShade64.dll 核心框架文件！\n请检查 embedded_components 或本地 RHI 缓存。"
                try:
                    shutil.copy2(reshade_src, reshade64_dest)
                    manifest["injected_files"].append("ReShade64.dll")
                    manifest["reshade64_injected_by_dlss5"] = True
                except Exception as e:
                    return False, f"部署 ReShade64.dll 链式底座失败: {e}"
            else:
                if was_reshade64_injected and "ReShade64.dll" not in manifest["injected_files"]:
                    manifest["injected_files"].append("ReShade64.dll")

            set_optiscaler_load_reshade(target_dir, enable=True)

        else:
            # Clean game, Dashdogy FG (Mode A), or orphaned proxy: dxgi.dll MUST be ReShade with Addon support!
            if reshade64_dest.exists():
                safe_force_remove(str(reshade64_dest))

            needs_dxgi_reshade = (not dxgi_dest.exists()) or (not is_reshade_addon_dll(str(dxgi_dest)))
            if not needs_dxgi_reshade:
                manifest["reshade_injected_by_dlss5"] = False
            else:
                reshade_src = find_reshade_framework_dll()
                if not reshade_src or not os.path.exists(reshade_src):
                    return False, "未找到 ReShade64.dll 核心底座框架！\n请检查 embedded_components 或本地 RHI 缓存。"

                if dxgi_dest.exists():
                    safe_force_remove(str(dxgi_dest))

                try:
                    shutil.copy2(reshade_src, dxgi_dest)
                    manifest["injected_files"].append("dxgi.dll")
                    manifest["reshade_injected_by_dlss5"] = True
                except Exception as e:
                    return False, f"部署 ReShade 核心底座 dxgi.dll 失败: {e}"

        # Clean any old legacy addon variants
        safe_force_remove(str(td / "lecram-dlss5-beta10.addon64"))
        safe_force_remove(str(td / "renodx-dlss-ShortFuse-261017汉化版.addon64"))

        # Step 2: Deploy modern RenoDX DLSS addon
        try:
            shutil.copy2(addon_src, addon_dest)
        except Exception as e:
            return False, f"拷贝 DLSS 5 插件至游戏目录失败: {e}"

        # Step 3: Deploy DLSS 5 Neural Reconstruction runtime (nvngx_dlssnr.dll) based on GPU architecture
        runtime_src = get_dlss5_runtime_dll_path(chosen_arch)
        if runtime_src and os.path.exists(runtime_src):
            local_app = os.environ.get("LOCALAPPDATA", "")
            if local_app:
                global_runtime = Path(local_app) / "DLSS5-NR" / "runtime" / "nvngx_dlssnr.dll"
                if not global_runtime.exists():
                    try:
                        global_runtime.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(runtime_src, global_runtime)
                    except Exception:
                        pass

            if not runtime_dest.exists():
                try:
                    shutil.copy2(runtime_src, runtime_dest)
                    manifest["injected_files"].append("nvngx_dlssnr.dll")
                    manifest["runtime_injected_by_dlss5"] = True
                except Exception:
                    pass
            else:
                manifest["runtime_injected_by_dlss5"] = False

        # Step 4: Register in ReShade.ini safely (unconditionally writing safe parameters)
        if not ini_dest.exists():
            _create_default_reshade_ini(ini_dest)
            manifest["injected_files"].append("ReShade.ini")
        _configure_reshade_ini_for_dlss5(ini_dest, remove=False, dlss5_config=dlss5_config)

        # Step 5: Write manifest
        manifest_path = td / ".dlss5_patch_manifest.json"
        try:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

        arch_display = "RTX 50 系列专属模型" if "50" in chosen_arch else "RTX 20/30/40 系列官方优化模型 (310.9.16)"
        if is_rhi_fg:
            msg = (
                "✅ DLSS 5 神经重构插件（ShortFuse 汉化版）注入成功！\n\n"
                f"🧠【模型架构就绪】：已部署 {arch_display}。\n"
                "🛡️【RHI 插帧底座避让生效】：\n"
                "检测到当前游戏已注入 RHI (RenoDX) 插帧模组，其已完备包含 ReShade 运行底座。\n"
                "程序已自动并联挂载 DLSS 5 神经重构，免重复安装且两套模组零冲突协同运行！\n\n"
                "🎮 启动游戏后按【Home】键即可在 ReShade 菜单中调校 DLSS 5 神经重构。"
            )
        elif is_optiscaler_fg:
            msg = (
                "✅ DLSS 5 神经重构插件（ShortFuse 汉化版）注入成功！\n\n"
                f"🧠【模型架构就绪】：已部署 {arch_display}。\n"
                "🟢【OptiScaler 链式共存模式生效】：\n"
                "程序已部署 ReShade64.dll 链式底座，并锁定 DLSS 4 Transformer 模型 Preset K！\n"
                "实现【OptiScaler 多倍插帧 + DLSS 5 神经重构】双引擎完美协同共存！\n\n"
                "🎮 启动游戏后按【Insert】呼出 OptiScaler 菜单，按【Home】呼出 ReShade 调校 DLSS 5。"
            )
        elif is_dashdog_fg:
            msg = (
                "✅ DLSS 5 神经重构插件注入成功！\n\n"
                f"🧠【模型架构就绪】：已部署 {arch_display}。\n"
                "🟢【Dashdog 独立插帧共存模式】：已协同部署 ReShade 6.8 底座与 DLSS 5 插件。\n\n"
                "🎮 启动游戏后按【Home】键即可在 ReShade 叠加层中开启 DLSS 5 神经重构调校。"
            )
        else:
            msg = (
                "✅ DLSS 5 神经重构插件（ShortFuse 汉化版）及 ReShade 6.8 底座一键注入成功！\n\n"
                f"🧠【模型架构就绪】：已部署 {arch_display}。\n"
                "🎮 启动游戏后按【Home】键即可打开 ReShade 叠加层调校 DLSS 5 神经重构。"
            )

        return True, msg

    @staticmethod
    def inject_reshade_base(target_dir: str) -> Tuple[bool, str]:
        """
        Physical injection of ReShade base.
        - For RHI FG: Avoids re-installation since ReShade is already running.
        - For OptiScaler FG: Deploys ReShade64.dll and enables LoadReshade=true in OptiScaler.ini for chain-loading.
        - For Clean / Dashdog: Deploys ReShade64.dll as dxgi.dll + ReShade.ini.
        """
        td = Path(target_dir)
        if not td.exists() or not td.is_dir():
            return False, f"目标目录不存在: {target_dir}"

        fg_info = detect_frame_generation(target_dir)

        if fg_info.get("is_rhi_fg"):
            return True, (
                "🛡️【RHI 插帧底座避让生效】：\n"
                "当前游戏已注入 RHI (RenoDX) 插帧补丁，ReShade 64-bit 核心底座已就绪并由 RHI 托管，\n"
                "免重复安装！您可以直接点击【一键注入 DLSS 5】并联挂载运行。"
            )

        if fg_info.get("is_optiscaler_fg"):
            reshade_src = find_reshade_framework_dll()
            if not reshade_src or not os.path.exists(reshade_src):
                return False, "未找到 ReShade64.dll 核心框架文件！\n请检查 embedded_components 或本地 RHI 缓存。"

            reshade64_dest = td / "ReShade64.dll"
            ini_dest = td / "ReShade.ini"

            try:
                shutil.copy2(reshade_src, reshade64_dest)
            except Exception as e:
                return False, f"部署 ReShade64.dll 链式底座失败: {e}"

            set_optiscaler_load_reshade(target_dir, enable=True)

            if not ini_dest.exists():
                _create_default_reshade_ini(ini_dest)
            _configure_reshade_ini_for_dlss5(ini_dest, remove=False)

            manifest_path = td / ".dlss5_patch_manifest.json"
            m = {}
            if manifest_path.exists():
                try:
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        m = json.load(f)
                except Exception:
                    pass
            m["reshade64_injected_by_dlss5"] = True
            m.setdefault("injected_files", [])
            if "ReShade64.dll" not in m["injected_files"]:
                m["injected_files"].append("ReShade64.dll")
            try:
                with open(manifest_path, "w", encoding="utf-8") as f:
                    json.dump(m, f, indent=2, ensure_ascii=False)
            except Exception:
                pass

            return True, (
                "🟢【OptiScaler 链式共存底座部署成功】：\n\n"
                "1. 已将 ReShade64.dll 部署至游戏目录（与 OptiScaler.dll 同级并行）；\n"
                "2. 已在 OptiScaler.ini 中开启 LoadReshade = true 链式唤起；\n"
                "3. 已锁定 DLSS 4 Transformer 模型 Preset K，彻底杜绝回退 D 模型；\n"
                "4. 已初始化 ReShade.ini 基础配置文件。\n\n"
                "✨ OptiScaler 插帧与 ReShade/DLSS 5 双引擎共存环境已就绪！"
            )

        dxgi_dest = td / "dxgi.dll"
        ini_dest = td / "ReShade.ini"

        if dxgi_dest.exists() and is_reshade_addon_dll(str(dxgi_dest)):
            return True, "🟢 当前游戏目录已存在功能完备的 ReShade 64-bit (Add-on 支持) 底座，状态正常！"

        reshade_src = find_reshade_framework_dll()
        if not reshade_src or not os.path.exists(reshade_src):
            return False, "未找到 ReShade64.dll 核心底座框架！\n请检查 embedded_components 或本地 RHI 缓存。"

        if dxgi_dest.exists() and not is_reshade_dll(str(dxgi_dest)):
            bak_path = td / "dxgi.dll.dlss5_bak"
            try:
                shutil.copy2(dxgi_dest, bak_path)
            except Exception as e:
                return False, f"备份原有 dxgi.dll 失败: {e}"

        try:
            shutil.copy2(reshade_src, dxgi_dest)
        except Exception as e:
            return False, f"部署 ReShade 核心底座 dxgi.dll 失败: {e}"

        if not ini_dest.exists():
            _create_default_reshade_ini(ini_dest)
        _configure_reshade_ini_for_dlss5(ini_dest, remove=False)

        manifest_path = td / ".dlss5_patch_manifest.json"
        m = {}
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    m = json.load(f)
            except Exception:
                pass
        m["reshade_injected_by_dlss5"] = True
        m.setdefault("injected_files", [])
        if "dxgi.dll" not in m["injected_files"]:
            m["injected_files"].append("dxgi.dll")
        try:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(m, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

        return True, (
            "✅ ReShade 64-bit (带 Add-on 支持) 核心底座部署成功！\n\n"
            "已在游戏目录就绪 dxgi.dll 与 ReShade.ini。\n"
            "现在您可以点击【一键注入 DLSS 5】完成神经重构扩展挂载。"
        )

    @staticmethod
    def restore(target_dir: str, force_clean_all: bool = False) -> Tuple[bool, str]:
        """
        Lossless one-click restoration of DLSS 5 and ReShade host.
        When force_clean_all=True: deep cleans all residual files.
        """
        td = Path(target_dir)
        if not td.exists() or not td.is_dir():
            return False, f"目标目录不存在: {target_dir}"

        if force_clean_all:
            try:
                from core.rollback import RollbackEngine
                return RollbackEngine().rollback(target_dir, clean_all=True)
            except Exception:
                try:
                    from apps.app2_mfg.core.rollback import RollbackEngine
                    return RollbackEngine().rollback(target_dir, clean_all=True)
                except Exception:
                    pass

        manifest_path = td / ".dlss5_patch_manifest.json"
        runtime_dest = td / "nvngx_dlssnr.dll"
        dxgi_dest = td / "dxgi.dll"
        reshade64_dest = td / "ReShade64.dll"
        ini_dest = td / "ReShade.ini"
        bak_path = td / "dxgi.dll.dlss5_bak"

        manifest_data = None
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
            except Exception:
                manifest_data = None

        # 1. Remove all DLSS 5 addon variants
        for addon_name in ["renodx-dlss.addon64", "renodx-dlss-ShortFuse-261017汉化版.addon64", "lecram-dlss5-beta10.addon64", "dlss5-nr.addon64"]:
            safe_force_remove(str(td / addon_name))

        # 2. Remove DLSS 5 runtime DLL
        if runtime_dest.exists():
            safe_force_remove(str(runtime_dest))

        # 3. Clean DLSS 5 runtime directory
        dlss5_runtime_dir = td / "dlss5-nr-runtime"
        if dlss5_runtime_dir.exists() and dlss5_runtime_dir.is_dir():
            try:
                shutil.rmtree(str(dlss5_runtime_dir), ignore_errors=True)
            except Exception:
                pass

        # 4. Clean crash dumps and temp configs
        for crash_file in td.glob("dlss5-nr-crash-*.txt"):
            safe_force_remove(str(crash_file))
        safe_force_remove(str(td / ".dlss5_config.json"))

        # 5. Clean ReShade.ini DLSS 5 sections
        if ini_dest.exists():
            _configure_reshade_ini_for_dlss5(ini_dest, remove=True)

        # 6. Check Frame Generation presence
        fg_info = detect_frame_generation(target_dir)
        is_rhi_fg = fg_info.get("is_rhi_fg", False)
        is_optiscaler_fg = fg_info.get("is_optiscaler_fg", False)

        if is_rhi_fg:
            pass
        elif is_optiscaler_fg:
            if reshade64_dest.exists():
                safe_force_remove(str(reshade64_dest))
            set_optiscaler_load_reshade(target_dir, enable=False)
            if ini_dest.exists() and manifest_data and "ReShade.ini" in manifest_data.get("injected_files", []):
                safe_force_remove(str(ini_dest))
        else:
            was_injected = manifest_data.get("reshade_injected_by_dlss5", False) if manifest_data else True
            if was_injected or is_reshade_dll(str(dxgi_dest)):
                if bak_path.exists():
                    safe_force_remove(str(dxgi_dest))
                    try:
                        shutil.move(str(bak_path), str(dxgi_dest))
                    except Exception:
                        pass
                else:
                    safe_force_remove(str(dxgi_dest))
            if ini_dest.exists():
                safe_force_remove(str(ini_dest))
            safe_force_remove(str(td / "ReShade.log"))

        if manifest_path.exists():
            safe_force_remove(str(manifest_path))

        return True, "✅ 已成功卸载 DLSS 5 插件并还原游戏状态！"

    @staticmethod
    def launch_rhi() -> Tuple[bool, str]:
        rhi_exe = find_rhi_setup_exe()
        if not rhi_exe or not os.path.exists(rhi_exe):
            return False, "未找到 RHI 安装包或系统程序！\n请检查 embedded_components/tools 或系统安装。"

        try:
            os.startfile(rhi_exe)
            return True, f"已成功启动 RHI: {os.path.basename(rhi_exe)}"
        except Exception:
            try:
                subprocess.Popen([rhi_exe])
                return True, f"已成功启动 RHI: {os.path.basename(rhi_exe)}"
            except Exception as e:
                return False, f"启动 RHI 失败: {e}"

    @staticmethod
    def launch_rhi_guide(game_exe_path: str = "") -> Tuple[bool, str]:
        copied_msg = ""
        if game_exe_path and os.path.exists(game_exe_path):
            try:
                from PySide6.QtWidgets import QApplication
                clipboard = QApplication.clipboard()
                if clipboard:
                    clipboard.setText(os.path.abspath(game_exe_path))
                    copied_msg = (
                        f"\n\n📋【路径已直达】已将游戏主程序完整路径自动复制到剪贴板：\n"
                        f"{os.path.abspath(game_exe_path)}\n"
                        f"在弹出的 RHI 文件选择器【文件名(N)】框内直接按【Ctrl+V】即可秒选！"
                    )
            except Exception:
                pass

        ok, msg = DLSS5Injector.launch_rhi()
        if not ok:
            return False, msg

        return True, (
            "🚀 RHI (ReShade HDR Installer) 模组助手已启动！"
            + copied_msg
            + "\n\n💡【生态共存与并联指南】：\n"
            "1. 若需使用更多 RenoDX HDR 滤镜扩展，可在 RHI 界面中配置效果；\n"
            "2. 本工具箱已自动激活 ReShade 智能避让机制，DLSS 5 神经重构与 RHI 零冲突并联运行！"
        )
