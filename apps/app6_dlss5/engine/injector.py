# -*- coding: utf-8 -*-
"""
DLSS 5 Neural Reconstruction (NR Addon) & ReShade/RHI Runtime Injector Core.
Supports one-click injection, collision avoidance with App 2 (Frame Generation),
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
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


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


def get_dlss5_addon_path() -> Optional[str]:
    """Locate the packaged lecram-dlss5-beta10.addon64 plugin."""
    candidates = [
        ROOT_DIR / "apps" / "app6_dlss5" / "assets" / "lecram-dlss5-beta10.addon64",
        ROOT_DIR / "defaults" / "app6_dlss5" / "assets" / "lecram-dlss5-beta10.addon64",
        Path(__file__).resolve().parent.parent / "assets" / "lecram-dlss5-beta10.addon64",
        Path(r"c:\Users\17547\Desktop\lecram-dlss5-beta10.addon64")
    ]
    for cand in candidates:
        if cand.exists() and cand.is_file() and cand.stat().st_size > 0:
            return str(cand)
    return None


def get_dlss5_runtime_dll_path() -> Optional[str]:
    """
    Locates the official NVIDIA DLSS 5 Neural Reconstruction runtime nvngx_dlssnr.dll (165.8 MB).
    Searches app assets, defaults, local AppData cache, and system locations.
    """
    candidates = [
        ROOT_DIR / "apps" / "app6_dlss5" / "assets" / "nvngx_dlssnr.dll",
        ROOT_DIR / "defaults" / "app6_dlss5" / "assets" / "nvngx_dlssnr.dll",
        Path(__file__).resolve().parent.parent / "assets" / "nvngx_dlssnr.dll",
    ]
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
    Searches App 2 embedded components, defaults, local AppData cache, and system RHI.
    """
    candidates = [
        ROOT_DIR / "apps" / "app2_mfg" / "embedded_components" / "reshade" / "6.8.0" / "ReShade64.dll",
        ROOT_DIR / "defaults" / "app2_mfg" / "embedded_components" / "reshade" / "6.8.0" / "ReShade64.dll",
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
       -> ReShade is ALREADY installed! Strictly avoids reinstalling ReShade base.
    2. is_optiscaler_fg: Mode C OptiScaler (OptiScaler.dll, OptiScaler/, OptiScaler.ini).
       -> OptiScaler and ReShade/DLSS 5 CO-EXIST via chain loader (LoadReshade=true + ReShade64.dll).
    3. is_dashdog_fg: Mode A Dashdog MFGUnlocker.
       -> Uses version.dll/winmm.dll, co-exists with dxgi.dll ReShade.
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


def enforce_optiscaler_anti_d_preset(ini_path: Path) -> bool:
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
                # If set to 4 (Preset D), auto, default, 0, or empty: upgrade to 11 (Preset K)
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

    # If [DLSS] section was not found, append it
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
    """
    Configures LoadReshade in OptiScaler.ini [Plugins] section.
    When enable=True:
      - Sets LoadReshade=true so OptiScaler chain-loads ReShade64.dll.
      - Enforces anti-D preset (sets RenderPresetForAll=11 Preset K to strictly eliminate Preset D).
      - If OptiScaler.ini does not exist, copies from the official bundled template.
    When enable=False:
      - Resets LoadReshade=auto, leaving all other settings intact.
    """
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
                        "RenderPresetDLAA=11\n"
                        "RenderPresetUltraQuality=11\n"
                        "RenderPresetQuality=11\n"
                        "RenderPresetBalanced=11\n"
                        "RenderPresetPerformance=11\n"
                        "RenderPresetUltraPerformance=11\n\n"
                        "[DLSSD]\n"
                        "RenderPresetOverride=true\n"
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
    addon_path = td / "lecram-dlss5-beta10.addon64"
    runtime_path = td / "nvngx_dlssnr.dll"
    dxgi_path = td / "dxgi.dll"
    reshade64_path = td / "ReShade64.dll"
    ini_path = td / "ReShade.ini"

    manifest_data = None
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
        except Exception:
            manifest_data = None

    has_addon = addon_path.exists()
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

    # Check whether the host environment is actually ready to execute the addon
    if fg_info["is_optiscaler_fg"]:
        host_ready = has_reshade64 and is_reshade64_addon_supported and opti_reshade_enabled
    else:
        host_ready = has_dxgi and is_reshade and is_addon_supported

    is_injected = has_addon

    return {
        "is_injected": is_injected,
        "host_ready": host_ready,
        "has_addon": has_addon,
        "has_runtime": has_runtime,
        "has_dxgi": has_dxgi,
        "has_reshade64": has_reshade64,
        "is_reshade": is_reshade,
        "is_addon_supported": is_addon_supported,
        "is_reshade64_addon_supported": is_reshade64_addon_supported,
        "is_dxgi_optiscaler": is_dxgi_optiscaler,
        "has_ini": ini_path.exists(),
        "fg_info": fg_info,
        "avoidance_active": fg_info["is_rhi_fg"],  # Only RHI FG avoids ReShade base install!
        "optiscaler_coexisting": fg_info["is_optiscaler_fg"],
        "opti_reshade_enabled": opti_reshade_enabled,
        "manifest": manifest_data
    }


def _configure_reshade_ini_for_dlss5(
    ini_path: Path,
    remove: bool = False,
    dlss5_config: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Safely configures ReShade.ini for DLSS 5.
    1. Removes any 'lecram-dlss5-beta10.addon64', 'lecram-dlss5-beta10', or literal '1'
       from LoadFromDllMain to prevent Windows Loader Lock deadlock (error 1114).
    2. When remove=False, writes/updates [RenoDX.DLSS5], [DLSS5], and [DLSS5-NR] with
       safe non-blocking Present parameters (NRHookPoint=2, NRPresentNonBlocking=1, NRVramBuffering=Full).
    3. Cleans up all DLSS5 sections when remove=True.
    """
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

    for line in lines_in:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            current_sec = stripped[1:-1].strip().upper()
            if current_sec in ["DLSS5", "DLSS5-NR", "RENODX.DLSS5"]:
                if remove:
                    modified = True
                    continue
            new_lines.append(line)
            continue

        if current_sec in ["DLSS5", "DLSS5-NR", "RENODX.DLSS5"]:
            if remove:
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
                    if xl in ["lecram-dlss5-beta10.addon64", "lecram-dlss5-beta10", "1"]:
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
    """Creates a clean default ReShade.ini configured with Home key overlay and DLSS 5 runtime path."""
    content = """[GENERAL]
EffectSearchPaths=.\\
TextureSearchPaths=.\\
NoReloadOnInit=1
PerformanceMode=0

[OVERLAY]
KeyOverlay=36,0,0,0
ShowFPS=0
ShowFrameTime=0

[ADDON]
LoadFromDllMain=

[DLSS5]
NRRuntimePath=.\\nvngx_dlssnr.dll
"""
    try:
        with open(ini_path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception:
        pass


class DLSS5Injector:
    """Manages DLSS 5 injection, Frame Generation avoidance, RHI linkage, and restoration."""

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
            return False, "未找到 lecram-dlss5-beta10.addon64 核心插件资产！\n请确认 assets 目录中包含该插件。"

        status = check_dlss5_status(target_dir)
        fg_info = status["fg_info"]
        is_rhi_fg = fg_info.get("is_rhi_fg", False)
        is_optiscaler_fg = fg_info.get("is_optiscaler_fg", False)
        is_dashdog_fg = fg_info.get("is_dashdog_fg", False)

        addon_dest = td / "lecram-dlss5-beta10.addon64"
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
            "version": "1.0.0",
            "addon_file": "lecram-dlss5-beta10.addon64",
            "runtime_file": "nvngx_dlssnr.dll",
            "injected_files": ["lecram-dlss5-beta10.addon64"],
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
            # "RHI的插帧才不需要重新装" -> Strictly do NOT touch or replace dxgi.dll!
            manifest["reshade_injected_by_dlss5"] = False

        elif is_optiscaler_fg:
            # 🟢 OPTISCALER FRAME GENERATION: Co-existence mode!
            # "opt插帧应该和RHIdlss5共存啊" -> OptiScaler stays as dxgi.dll.
            # We deploy ReShade64.dll alongside OptiScaler and set LoadReshade=true in OptiScaler.ini!
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

            # Configure OptiScaler.ini: LoadReshade = true AND enforce anti-D preset (Preset K)
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

                # If dxgi.dll exists and is an orphaned proxy (e.g. leftover OptiScaler), safe-remove it
                if dxgi_dest.exists():
                    safe_force_remove(str(dxgi_dest))

                try:
                    shutil.copy2(reshade_src, dxgi_dest)
                    manifest["injected_files"].append("dxgi.dll")
                    manifest["reshade_injected_by_dlss5"] = True
                except Exception as e:
                    return False, f"部署 ReShade 核心底座 dxgi.dll 失败: {e}"

        # Step 2: Deploy DLSS 5 addon
        try:
            shutil.copy2(addon_src, addon_dest)
        except Exception as e:
            return False, f"拷贝 DLSS 5 插件至游戏目录失败: {e}"

        # Step 3: Deploy DLSS 5 Neural Reconstruction runtime (nvngx_dlssnr.dll)
        runtime_src = get_dlss5_runtime_dll_path()
        if runtime_src and os.path.exists(runtime_src):
            # Populate global %LOCALAPPDATA%\DLSS5-NR\runtime if possible
            local_app = os.environ.get("LOCALAPPDATA", "")
            if local_app:
                global_runtime = Path(local_app) / "DLSS5-NR" / "runtime" / "nvngx_dlssnr.dll"
                if not global_runtime.exists():
                    try:
                        global_runtime.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(runtime_src, global_runtime)
                    except Exception:
                        pass

            # Copy to target directory alongside addon
            if not runtime_dest.exists():
                try:
                    shutil.copy2(runtime_src, runtime_dest)
                    manifest["injected_files"].append("nvngx_dlssnr.dll")
                    manifest["runtime_injected_by_dlss5"] = True
                except Exception:
                    pass
            else:
                manifest["runtime_injected_by_dlss5"] = False

        # Step 4: Register in ReShade.ini safely (avoiding Loader Lock deadlock)
        if not ini_dest.exists():
            _create_default_reshade_ini(ini_dest)
            manifest["injected_files"].append("ReShade.ini")
        else:
            _configure_reshade_ini_for_dlss5(ini_dest, remove=False, dlss5_config=dlss5_config)

        # Step 5: Write manifest
        manifest_path = td / ".dlss5_patch_manifest.json"
        try:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

        if is_rhi_fg:
            msg = (
                "✅ DLSS 5 神经重构插件注入成功！\n\n"
                "🛡️【RHI 插帧底座避让生效】：\n"
                "检测到当前游戏已注入 RHI (RenoDX) 插帧模组，其已完备包含 ReShade 运行底座。\n"
                "程序已自动跳过底座安装，直接将 DLSS 5 并联挂载至现有 ReShade 环境，免重复安装且两套模组零冲突协同运行！\n\n"
                "🎮 启动游戏后按【Home】键即可在 ReShade 叠加层中开启 DLSS 5 神经重构调校。"
            )
        elif is_optiscaler_fg:
            msg = (
                "✅ DLSS 5 神经重构插件注入成功！\n\n"
                "🟢【OptiScaler 链式共存模式生效】：\n"
                "检测到当前游戏已注入 OptiScaler 跨架构插帧。\n"
                "程序已自动部署 ReShade64.dll 链式底座，并在 OptiScaler.ini 中开启 LoadReshade = true 链式唤起！\n"
                "已自动锁定 DLSS 4 Transformer 模型 Preset K，彻底规避旧版 D 模型！\n"
                "实现【OptiScaler 多倍插帧 + DLSS 5 神经重构】双引擎完美协同共存！\n\n"
                "🎮 启动游戏后按【Insert】呼出 OptiScaler 菜单，按【Home】呼出 ReShade 调校 DLSS 5。"
            )
        elif is_dashdog_fg:
            msg = (
                "✅ DLSS 5 神经重构插件注入成功！\n\n"
                "🟢【Dashdog 独立插帧共存模式】：\n"
                "检测到当前游戏已注入 Dashdog 多帧生成补丁，已协同部署 ReShade 6.8 底座与 DLSS 5 插件。\n\n"
                "🎮 启动游戏后按【Home】键即可在 ReShade 叠加层中开启 DLSS 5 神经重构调校。"
            )
        else:
            msg = (
                "✅ DLSS 5 神经重构插件及 ReShade 6.8 底座一键注入成功！\n\n"
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

        # 1. RHI RenoDX Frame Generation:
        if fg_info.get("is_rhi_fg"):
            return True, (
                "🛡️【RHI 插帧底座避让生效】：\n"
                "当前游戏已注入 RHI (RenoDX) 插帧补丁，ReShade 64-bit 核心底座已就绪并由 RHI 托管，\n"
                "免重复安装！您可以直接点击【一键注入 DLSS 5】并联挂载运行。"
            )

        # 2. OptiScaler Frame Generation:
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
            else:
                _configure_reshade_ini_for_dlss5(ini_dest, remove=False, dlss5_config=dlss5_config)

            # Record in manifest so restore knows ReShade64.dll was deployed by toolbox
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

        # 3. Clean game or Dashdogy FG:
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
        else:
            _configure_reshade_ini_for_dlss5(ini_dest, remove=False, dlss5_config=dlss5_config)

        # Record in manifest
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

        return True, "✅ 已成功为当前游戏物理注入 ReShade 6.8 (Add-on 支持) 核心底座与基础配置！"

    @staticmethod
    def restore(target_dir: str) -> Tuple[bool, str]:
        td = Path(target_dir)
        manifest_path = td / ".dlss5_patch_manifest.json"
        addon_dest = td / "lecram-dlss5-beta10.addon64"
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

        # 1. Remove DLSS 5 addon file
        if addon_dest.exists():
            try:
                addon_dest.unlink()
            except Exception as e:
                return False, f"删除 DLSS 5 插件失败: {e}"

        # 2. Remove DLSS 5 runtime DLL if deployed by DLSS 5
        if manifest_data and manifest_data.get("runtime_injected_by_dlss5", False):
            if runtime_dest.exists():
                try:
                    runtime_dest.unlink()
                except Exception:
                    pass

        # 3. Clean ReShade.ini
        if ini_dest.exists():
            _configure_reshade_ini_for_dlss5(ini_dest, remove=True)

        # 4. Check Frame Generation presence
        fg_info = detect_frame_generation(target_dir)
        is_rhi_fg = fg_info.get("is_rhi_fg", False)
        is_optiscaler_fg = fg_info.get("is_optiscaler_fg", False)

        if is_rhi_fg:
            # RHI frame generation: Strictly preserve dxgi.dll and ReShade.ini!
            pass
        elif is_optiscaler_fg:
            # OptiScaler frame generation: Keep OptiScaler intact!
            # If ReShade64.dll was deployed by DLSS 5, remove ReShade64.dll and reset LoadReshade
            if manifest_data and manifest_data.get("reshade64_injected_by_dlss5", False):
                if reshade64_dest.exists():
                    try:
                        reshade64_dest.unlink()
                    except Exception:
                        pass
                set_optiscaler_load_reshade(target_dir, enable=False)
                if ini_dest.exists() and "ReShade.ini" in manifest_data.get("injected_files", []):
                    try:
                        ini_dest.unlink()
                    except Exception:
                        pass
        else:
            # If DLSS 5 was the one who deployed ReShade as dxgi.dll, safely clean it up
            was_injected = manifest_data.get("reshade_injected_by_dlss5", False) if manifest_data else False
            if was_injected:
                if dxgi_dest.exists():
                    try:
                        dxgi_dest.unlink()
                    except Exception:
                        pass
                if bak_path.exists():
                    try:
                        shutil.move(str(bak_path), str(dxgi_dest))
                    except Exception:
                        pass
                if ini_dest.exists() and "ReShade.ini" in manifest_data.get("injected_files", []):
                    try:
                        ini_dest.unlink()
                    except Exception:
                        pass

        # 5. Remove manifest
        if manifest_path.exists():
            try:
                manifest_path.unlink()
            except Exception:
                pass

        return True, "✅ 已成功卸载 DLSS 5 插件并还原游戏状态！"

    @staticmethod
    def launch_rhi() -> Tuple[bool, str]:
        """Launch RHI (ReShade HDR Installer) setup or installed program."""
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
        """
        Launches RHI and copies game executable path to Windows clipboard for instant paste navigation.
        """
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
            f"{msg}{copied_msg}\n\n"
            "💡【RHI 关键配置提示】：\n"
            "1. 渲染 API 请选择 DirectX 11/12。\n"
            "2. 务必勾选【ReShade with full add-on support】完成安装！"
        )
