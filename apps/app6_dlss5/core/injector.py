# -*- coding: utf-8 -*-
"""
DLSS 5 Neural Reconstruction (NR Addon) & ReShade/RHI Runtime Injector Core.
Supports one-click injection, collision avoidance with App 2 (Frame Generation),
ReShade host management, and one-click lossless restoration.
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


def is_reshade_dll(path: str) -> bool:
    """Check if a DLL file is ReShade (checks for crosire or ReShade signature in binary)."""
    if not os.path.exists(path) or not os.path.isfile(path):
        return False
    try:
        with open(path, "rb") as f:
            data = f.read(1024 * 1024 * 12)
            return b"ReShade" in data or b"crosire" in data
    except Exception:
        return False


def is_reshade_addon_dll(path: str) -> bool:
    """Check if a DLL file is ReShade with full Add-on Support."""
    if not os.path.exists(path) or not os.path.isfile(path):
        return False
    try:
        with open(path, "rb") as f:
            data = f.read(1024 * 1024 * 12)
            return (b"ReShade" in data or b"crosire" in data) and (
                b"AddonUninit" in data or b"reshade_addon" in data or len(data) >= 5 * 1024 * 1024
            )
    except Exception:
        return False


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

    has_renodx = (td / "renodx-mfgunlock.addon64").exists()
    has_optiscaler = (
        (td / "OptiScaler.dll").exists() or
        (td / "OptiScaler").is_dir() or
        (td / "OptiScaler.ini").exists() or
        (td / "nvngx.ini").exists()
    )
    has_dashdog = (
        (td / "MFGUnlocker.dll").exists() or
        (td / "RTXMFG-UI.ini").exists() or
        (td / "mfg_unlocker.ini").exists()
    )

    is_rhi_fg = has_renodx or manifest_backend in ["reshade_addon", "renodx"]
    is_optiscaler_fg = has_optiscaler or manifest_backend in ["optiscaler", "optiscaler_fsr"]
    is_dashdog_fg = has_dashdog or manifest_backend in ["standalone", "dashdogy"]

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
        "has_renodx": has_renodx,
        "has_dashdog": has_dashdog,
        "has_optiscaler": has_optiscaler,
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


def set_optiscaler_load_reshade(target_dir: str, enable: bool = True) -> bool:
    """
    Configures LoadReshade in OptiScaler.ini [Plugins] section.
    When enable=True, sets LoadReshade=true so OptiScaler chain-loads ReShade64.dll.
    When enable=False, resets LoadReshade=auto.
    """
    td = Path(target_dir)
    ini_path = td / "OptiScaler.ini"
    val_str = "true" if enable else "auto"

    if not ini_path.exists():
        if (td / "OptiScaler").is_dir() or (td / "OptiScaler.dll").exists():
            try:
                with open(ini_path, "w", encoding="utf-8") as f:
                    f.write(f"[Plugins]\nLoadReshade={val_str}\n")
                return True
            except Exception:
                return False
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
            return True
        except Exception:
            return False

    return True


def check_dlss5_status(target_dir: str) -> Dict[str, Any]:
    """Comprehensive status check of DLSS 5, ReShade host, OptiScaler coexistence, and RHI avoidance."""
    td = Path(target_dir)
    manifest_path = td / ".dlss5_patch_manifest.json"
    addon_path = td / "lecram-dlss5-beta10.addon64"
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
    has_dxgi = dxgi_path.exists()
    has_reshade64 = reshade64_path.exists()
    is_reshade = is_reshade_dll(str(dxgi_path)) if has_dxgi else False
    is_addon_supported = is_reshade_addon_dll(str(dxgi_path)) if has_dxgi else False
    is_reshade64_addon_supported = is_reshade_addon_dll(str(reshade64_path)) if has_reshade64 else False
    fg_info = detect_frame_generation(target_dir)
    opti_reshade_enabled = is_optiscaler_load_reshade_enabled(target_dir) if fg_info["is_optiscaler_fg"] else False

    is_injected = has_addon

    return {
        "is_injected": is_injected,
        "has_addon": has_addon,
        "has_dxgi": has_dxgi,
        "has_reshade64": has_reshade64,
        "is_reshade": is_reshade,
        "is_addon_supported": is_addon_supported,
        "is_reshade64_addon_supported": is_reshade64_addon_supported,
        "has_ini": ini_path.exists(),
        "fg_info": fg_info,
        "avoidance_active": fg_info["is_rhi_fg"],  # Only RHI FG avoids ReShade base install!
        "optiscaler_coexisting": fg_info["is_optiscaler_fg"],
        "opti_reshade_enabled": opti_reshade_enabled,
        "manifest": manifest_data
    }


def _ensure_addon_in_reshade_ini(ini_path: Path, addon_name: str) -> bool:
    """Safely appends addon_name to LoadFromDllMain in [ADDON] section of ReShade.ini."""
    lines = []
    if ini_path.exists():
        try:
            with open(ini_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception:
            lines = []

    in_addon_sec = False
    addon_sec_found = False
    load_key_found = False
    modified = False
    new_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            sec_name = stripped[1:-1].strip()
            if in_addon_sec and not load_key_found and addon_name:
                new_lines.append(f"LoadFromDllMain={addon_name}\n")
                load_key_found = True
                modified = True

            in_addon_sec = (sec_name.upper() == "ADDON")
            if in_addon_sec:
                addon_sec_found = True
            new_lines.append(line)
            continue

        if in_addon_sec and "=" in stripped:
            k, v = stripped.split("=", 1)
            if k.strip().upper() == "LOADFROMDLLMAIN":
                load_key_found = True
                if addon_name:
                    existing = [x.strip() for x in v.split(",") if x.strip()]
                    if addon_name.lower() not in [x.lower() for x in existing]:
                        existing.append(addon_name)
                        new_lines.append(f"{k.strip()}={','.join(existing)}\n")
                        modified = True
                        continue

        new_lines.append(line)

    if not addon_sec_found:
        new_lines.append("\n[ADDON]\n")
        if addon_name:
            new_lines.append(f"LoadFromDllMain={addon_name}\n")
        modified = True
    elif not load_key_found and addon_name:
        new_lines.append(f"LoadFromDllMain={addon_name}\n")
        modified = True

    if modified:
        try:
            with open(ini_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            return True
        except Exception:
            return False

    return False


def _remove_addon_from_reshade_ini(ini_path: Path, addon_name: str) -> bool:
    """Safely removes addon_name from LoadFromDllMain in [ADDON] section of ReShade.ini."""
    if not ini_path.exists():
        return False
    try:
        with open(ini_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return False

    in_addon_sec = False
    modified = False
    new_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            sec_name = stripped[1:-1].strip()
            in_addon_sec = (sec_name.upper() == "ADDON")
            new_lines.append(line)
            continue

        if in_addon_sec and "=" in stripped:
            k, v = stripped.split("=", 1)
            if k.strip().upper() == "LOADFROMDLLMAIN":
                existing = [x.strip() for x in v.split(",") if x.strip()]
                remaining = [x for x in existing if x.lower() != addon_name.lower() and x.lower() != addon_name.replace(".addon64", "").lower()]
                if len(remaining) != len(existing):
                    modified = True
                    if remaining:
                        new_lines.append(f"{k.strip()}={','.join(remaining)}\n")
                    else:
                        new_lines.append(f"{k.strip()}=\n")
                    continue

        new_lines.append(line)

    if modified:
        try:
            with open(ini_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            return True
        except Exception:
            return False
    return False


def _create_default_reshade_ini(ini_path: Path, addon_name: str = ""):
    """Creates a clean default ReShade.ini configured with Home key overlay and optional addon."""
    addon_line = f"LoadFromDllMain={addon_name}\n" if addon_name else "LoadFromDllMain=\n"
    content = f"""[GENERAL]
EffectSearchPaths=.\\
TextureSearchPaths=.\\
NoReloadOnInit=1
PerformanceMode=0

[OVERLAY]
KeyOverlay=36,0,0,0
ShowFPS=0
ShowFrameTime=0

[ADDON]
{addon_line}"""
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
    def inject(target_dir: str) -> Tuple[bool, str]:
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
        dxgi_dest = td / "dxgi.dll"
        reshade64_dest = td / "ReShade64.dll"
        ini_dest = td / "ReShade.ini"

        manifest: Dict[str, Any] = {
            "version": "1.0.0",
            "addon_file": "lecram-dlss5-beta10.addon64",
            "injected_files": ["lecram-dlss5-beta10.addon64"],
            "reshade_injected_by_dlss5": False,
            "reshade64_injected_by_dlss5": False,
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
                manifest["reshade64_injected_by_dlss5"] = False

            # Configure OptiScaler.ini: LoadReshade = true
            set_optiscaler_load_reshade(target_dir, enable=True)

        else:
            # Clean game or Dashdogy FG (Dashdogy uses version.dll/winmm.dll, dxgi.dll is free for ReShade)
            if dxgi_dest.exists() and is_reshade_addon_dll(str(dxgi_dest)):
                manifest["reshade_injected_by_dlss5"] = False
            else:
                reshade_src = find_reshade_framework_dll()
                if not reshade_src or not os.path.exists(reshade_src):
                    return False, "未找到 ReShade64.dll 核心底座框架！\n请检查 embedded_components 或本地 RHI 缓存。"

                # Backup foreign dxgi.dll if present
                if dxgi_dest.exists() and not is_reshade_dll(str(dxgi_dest)):
                    bak_path = td / "dxgi.dll.dlss5_bak"
                    try:
                        shutil.copy2(dxgi_dest, bak_path)
                        manifest["backup_file"] = "dxgi.dll.dlss5_bak"
                    except Exception as e:
                        return False, f"备份原有 dxgi.dll 失败: {e}"

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

        # Step 3: Register in ReShade.ini
        if not ini_dest.exists():
            _create_default_reshade_ini(ini_dest, "lecram-dlss5-beta10.addon64")
            manifest["injected_files"].append("ReShade.ini")
        else:
            _ensure_addon_in_reshade_ini(ini_dest, "lecram-dlss5-beta10.addon64")

        # Step 4: Write manifest
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
                _create_default_reshade_ini(ini_dest, "")

            return True, (
                "🟢【OptiScaler 链式共存底座部署成功】：\n\n"
                "1. 已将 ReShade64.dll 部署至游戏目录（与 OptiScaler.dll 同级并行）；\n"
                "2. 已在 OptiScaler.ini 中开启 LoadReshade = true 链式唤起；\n"
                "3. 已初始化 ReShade.ini 基础配置文件。\n\n"
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
            _create_default_reshade_ini(ini_dest, "")

        return True, "✅ 已成功为当前游戏物理注入 ReShade 6.8 (Add-on 支持) 核心底座与基础配置！"

    @staticmethod
    def restore(target_dir: str) -> Tuple[bool, str]:
        td = Path(target_dir)
        manifest_path = td / ".dlss5_patch_manifest.json"
        addon_dest = td / "lecram-dlss5-beta10.addon64"
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

        # 2. Clean addon from ReShade.ini
        if ini_dest.exists():
            _remove_addon_from_reshade_ini(ini_dest, "lecram-dlss5-beta10.addon64")

        # 3. Check Frame Generation presence
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

        # 4. Remove manifest
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
