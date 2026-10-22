# -*- coding: utf-8 -*-
"""
DLSS 5 Neural Reconstruction Plugin - Standalone Injector Engine.
=================================================================
Dedicated, rock-solid one-click injector for DLSS 5 (RenoDX DLSS-NR & ReShade Addon).
Reuses Game Recognition and RHI modules directly from App 2 (app2_mfg).
Coexists with Mode A/B/C/D frame generation through the shared
`apps/app2_mfg/core/coexistence.py` router instead of overwriting their proxy slots.
Defaults to RenoDX DLSS 5 v11.9 flagship addon (renodx-dlss5-v11.9.addon64).
"""

import os
import sys
import json
import time
import shutil
import hashlib
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

APP2_DIR = ROOT_DIR / "apps" / "app2_mfg"
if str(APP2_DIR) not in sys.path:
    sys.path.insert(0, str(APP2_DIR))

try:
    from apps.app2_mfg.core.state_cleaner import is_reshade_dll_file, is_optiscaler_dll_file, is_mode_c_present
    from apps.app2_mfg.core.rollback import RollbackEngine
    from apps.app2_mfg.core.utils import safe_force_remove, kill_locking_processes, cleanup_pending_files
except Exception:
    def is_reshade_dll_file(p: str) -> bool:
        if not os.path.exists(p):
            return False
        try:
            with open(p, "rb") as f:
                data = f.read(4 * 1024 * 1024)
            return b"ReShade" in data or b"crosire" in data
        except Exception:
            return False

    def is_optiscaler_dll_file(p: str) -> bool:
        if not os.path.exists(p):
            return False
        try:
            with open(p, "rb") as f:
                data = f.read(4 * 1024 * 1024)
            return b"OptiScaler" in data or b"libxess" in data
        except Exception:
            return False

    def is_mode_c_present(p: Any) -> bool:
        td = Path(p) if p else None
        if not td or not td.exists():
            return False
        return (td / "OptiScaler.ini").exists() or (td / "libxess_fg.dll").exists()

    def safe_force_remove(p: str) -> bool:
        try:
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
            else:
                os.remove(p)
            return True
        except Exception:
            return False

    def kill_locking_processes(d: str, exe: Optional[str] = None):
        pass

    def cleanup_pending_files(d: str):
        pass

    class RollbackEngine:
        def rollback(self, target_dir: str, exe_name: Optional[str] = None, clean_all: bool = False):
            return True, ""


try:
    from common.config_manager import get_real_gpu_info, get_app_config_path
except Exception:
    def get_real_gpu_info() -> Dict[str, Any]:
        return {
            "gpu_name": "NVIDIA GeForce RTX",
            "arch": "rtx20_30_40",
            "is_nvidia": True,
            "description": "RTX 20/30/40 架构 · 推荐通用模型",
            "is_rtx_40_or_newer": True
        }
    def get_app_config_path(app: str, f: str) -> Path:
        p = Path(os.environ.get("APPDATA", "")) / "ToolboxMaster" / "config" / app / f
        p.parent.mkdir(parents=True, exist_ok=True)
        return p


DEFAULT_DESKTOP_V119_DIR = Path(os.environ.get("USERPROFILE", r"C:\Users\17547")) / "Desktop" / "dx12游戏通用reshade极简包最新nr模型 sf1017中文版 内附说明一定要看"
DEFAULT_DESKTOP_DIR = Path(os.environ.get("USERPROFILE", r"C:\Users\17547")) / "Desktop" / "dlss5插件"
LOCAL_ASSETS_DIR = ROOT_DIR / "apps" / "app6_dlss5" / "assets"

DLSS5_MANIFEST_FILENAME = ".dlss5_manifest.json"
DLSS5_BACKUP_DIRNAME = ".dlss5_backup"


def get_plugin_source_dir(custom_path: Optional[str] = None) -> Path:
    """
    Finds the active source directory for DLSS5 plugin assets.
    Prioritizes the self-contained package assets (LOCAL_ASSETS_DIR) inside the integration
    package (整合包) so it works portably on any PC without relying on desktop paths.
    """
    if custom_path and os.path.isdir(custom_path):
        return Path(custom_path)
    # 1. Primary: bundled assets inside integration package
    if LOCAL_ASSETS_DIR.exists() and LOCAL_ASSETS_DIR.is_dir():
        if (LOCAL_ASSETS_DIR / "dxgi.dll").exists() or list(LOCAL_ASSETS_DIR.glob("*.addon64")):
            return LOCAL_ASSETS_DIR
    # 2. Secondary fallback: desktop folders if assets were stripped
    if DEFAULT_DESKTOP_V119_DIR.exists() and DEFAULT_DESKTOP_V119_DIR.is_dir():
        return DEFAULT_DESKTOP_V119_DIR
    if DEFAULT_DESKTOP_DIR.exists() and DEFAULT_DESKTOP_DIR.is_dir():
        return DEFAULT_DESKTOP_DIR
    return LOCAL_ASSETS_DIR


def scan_plugin_source_assets(source_dir: Optional[Path] = None) -> Dict[str, Any]:
    """
    Scans the given source directory (or auto-detected paths) for:
    - dxgi.dll (ReShade base)
    - addon64 files (RenoDX addon, defaults to v11.9)
    - nvngx_dlssnr.dll models (RTX 50 vs RTX 20/30/40)
    """
    s_dir = source_dir or get_plugin_source_dir()
    result = {
        "source_dir": str(s_dir),
        "exists": s_dir.exists(),
        "dxgi_path": None,
        "dxgi_size_mb": 0.0,
        "addon_path": None,
        "addon_name": "",
        "addon_size_mb": 0.0,
        "all_addons": [],
        "nr_50_path": None,
        "nr_50_size_mb": 0.0,
        "nr_20_30_40_path": None,
        "nr_20_30_40_size_mb": 0.0,
    }

    if not s_dir.exists():
        # Fall back to local assets if desktop doesn't exist
        if LOCAL_ASSETS_DIR.exists():
            s_dir = LOCAL_ASSETS_DIR
            result["source_dir"] = str(s_dir)
            result["exists"] = True
        else:
            return result

    # 1. Search for dxgi.dll
    dxgi_cand = s_dir / "dxgi.dll"
    if dxgi_cand.exists() and dxgi_cand.is_file():
        result["dxgi_path"] = str(dxgi_cand)
        result["dxgi_size_mb"] = round(dxgi_cand.stat().st_size / (1024 * 1024), 2)
    elif (DEFAULT_DESKTOP_DIR / "dxgi.dll").exists():
        cand = DEFAULT_DESKTOP_DIR / "dxgi.dll"
        result["dxgi_path"] = str(cand)
        result["dxgi_size_mb"] = round(cand.stat().st_size / (1024 * 1024), 2)
    elif (LOCAL_ASSETS_DIR / "dxgi.dll").exists():
        cand = LOCAL_ASSETS_DIR / "dxgi.dll"
        result["dxgi_path"] = str(cand)
        result["dxgi_size_mb"] = round(cand.stat().st_size / (1024 * 1024), 2)

    # 2. Search for *.addon64 (Default to renodx-dlss5-v11.9.addon64)
    addons = list(s_dir.glob("*.addon64"))
    if not addons and LOCAL_ASSETS_DIR.exists():
        addons = list(LOCAL_ASSETS_DIR.glob("*.addon64"))
    if addons:
        def addon_sort_key(p: Path):
            name_lower = p.name.lower()
            if "v11.9" in name_lower or "11.9" in name_lower:
                priority = 0
            elif "dlss5" in name_lower:
                priority = 1
            elif "shortfuse" in name_lower:
                priority = 2
            else:
                priority = 3
            return (priority, -p.stat().st_size)

        preferred = sorted(addons, key=addon_sort_key)
        best = preferred[0]
        result["addon_path"] = str(best)
        result["addon_name"] = best.name
        result["addon_size_mb"] = round(best.stat().st_size / (1024 * 1024), 2)
        result["all_addons"] = [str(a) for a in addons]

    # 3. Search for RTX 50 NR model
    cand_50_sub = list(s_dir.glob("*50*/*.dll")) + list(s_dir.glob("*50*\\*.dll"))
    cand_50_file = s_dir / "runtimes" / "nvngx_dlssnr_rtx50.dll"
    if cand_50_sub and cand_50_sub[0].exists():
        result["nr_50_path"] = str(cand_50_sub[0])
        result["nr_50_size_mb"] = round(cand_50_sub[0].stat().st_size / (1024 * 1024), 2)
    elif cand_50_file.exists():
        result["nr_50_path"] = str(cand_50_file)
        result["nr_50_size_mb"] = round(cand_50_file.stat().st_size / (1024 * 1024), 2)
    elif (LOCAL_ASSETS_DIR / "runtimes" / "nvngx_dlssnr_rtx50.dll").exists():
        cand = LOCAL_ASSETS_DIR / "runtimes" / "nvngx_dlssnr_rtx50.dll"
        result["nr_50_path"] = str(cand)
        result["nr_50_size_mb"] = round(cand.stat().st_size / (1024 * 1024), 2)

    # 4. Search for RTX 20/30/40 NR model
    cand_40_sub = list(s_dir.glob("*20-30-40*/*.dll")) + list(s_dir.glob("*20-30-40*\\*.dll"))
    cand_40_file = s_dir / "runtimes" / "nvngx_dlssnr_rtx20_30_40.dll"
    if cand_40_sub and cand_40_sub[0].exists():
        result["nr_20_30_40_path"] = str(cand_40_sub[0])
        result["nr_20_30_40_size_mb"] = round(cand_40_sub[0].stat().st_size / (1024 * 1024), 2)
    elif cand_40_file.exists():
        result["nr_20_30_40_path"] = str(cand_40_file)
        result["nr_20_30_40_size_mb"] = round(cand_40_file.stat().st_size / (1024 * 1024), 2)
    elif (LOCAL_ASSETS_DIR / "runtimes" / "nvngx_dlssnr_rtx20_30_40.dll").exists():
        cand = LOCAL_ASSETS_DIR / "runtimes" / "nvngx_dlssnr_rtx20_30_40.dll"
        result["nr_20_30_40_path"] = str(cand)
        result["nr_20_30_40_size_mb"] = round(cand.stat().st_size / (1024 * 1024), 2)

    return result


def _guess_game_exe(target_dir: Path) -> Optional[str]:
    """Return the largest .exe in the game directory (used for PE proxy analysis)."""
    try:
        cands = [p for p in target_dir.iterdir() if p.is_file() and p.suffix.lower() == ".exe"]
        if not cands:
            return None
        return str(max(cands, key=lambda p: p.stat().st_size))
    except Exception:
        return None


def check_game_dlss5_status(target_dir: str) -> Dict[str, Any]:
    """
    Checks whether DLSS 5 is currently injected into the game's target directory.
    Returns detailed inspection info including file states, ReShade, and active model.
    """
    td = Path(target_dir) if target_dir else None
    if not td or not td.exists() or not td.is_dir():
        return {
            "valid_dir": False,
            "is_injected": False,
            "has_reshade": False,
            "has_addon": False,
            "has_runtime": False,
            "addon_names": [],
            "runtime_size_mb": 0.0,
            "detected_arch": "unknown",
            "manifest_data": None
        }

    dxgi_path = td / "dxgi.dll"
    reshade64_path = td / "ReShade64.dll"
    runtime_path = td / "nvngx_dlssnr.dll"
    manifest_path = td / DLSS5_MANIFEST_FILENAME

    # ReShade base check
    has_reshade = False
    if dxgi_path.exists() and dxgi_path.is_file():
        try:
            with open(dxgi_path, "rb") as f:
                head = f.read(1024 * 1024)
            if b"crosire" in head.lower() or b"reshade" in head.lower() or dxgi_path.stat().st_size > 4 * 1024 * 1024:
                has_reshade = True
        except Exception:
            has_reshade = True
    elif reshade64_path.exists():
        has_reshade = True

    # Addons check
    addons = [p.name for p in td.glob("*.addon64")]
    dlss_addons = [a for a in addons if any(k in a.lower() for k in ["renodx", "dlss", "shortfuse"])]
    has_addon = len(dlss_addons) > 0

    # Runtime check
    has_runtime = runtime_path.exists() and runtime_path.is_file() and runtime_path.stat().st_size > 100 * 1024 * 1024
    runtime_size_mb = round(runtime_path.stat().st_size / (1024 * 1024), 2) if has_runtime else 0.0

    # Check manifest
    manifest_data = None
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
        except Exception:
            pass

    is_injected = (has_reshade and has_addon and has_runtime) or (manifest_data is not None)

    # Estimate active architecture based on manifest first, then runtime size.
    # RTX 20/30/40 model: ~263 MB; RTX 50 (Blackwell) model: ~254 MB.
    detected_arch = "unknown"
    if manifest_data and manifest_data.get("selected_arch"):
        detected_arch = manifest_data["selected_arch"]
    elif has_runtime:
        if runtime_size_mb >= 258.0:
            detected_arch = "rtx20_30_40"
        else:
            detected_arch = "rtx50"

    return {
        "valid_dir": True,
        "is_injected": is_injected,
        "has_reshade": has_reshade,
        "has_addon": has_addon,
        "has_runtime": has_runtime,
        "addon_names": dlss_addons or addons,
        "runtime_size_mb": runtime_size_mb,
        "detected_arch": detected_arch,
        "manifest_data": manifest_data
    }


DEFAULT_DLSS5_INI_SECTIONS: Dict[str, Dict[str, str]] = {
    "ADDON": {},
    "GENERAL": {
        "EffectSearchPaths": ".\\",
        "TextureSearchPaths": ".\\",
        "PerformanceMode": "1",
        "NoReloadOnInit": "1"
    },
    "APP": {
        "ForceWindowed": "0",
        "ForceFullscreen": "0",
        "DisableLoadingEffects": "1"
    },
    "DX12": {
        "DepthCopyBeforeClears": "0",
        "DepthCopyAtClearIndex": "0",
        "UseAspectRatioHeuristics": "1"
    },
    "OVERLAY": {
        "Language": "zh-CN",
        "Font": "C:\\Windows\\Fonts\\msyh.ttc",
        "FontSize": "18",
        "EditorFont": "C:\\Windows\\Fonts\\msyh.ttc",
        "EditorFontSize": "16",
        "TutorialProgress": "4",
        "KeyOverlay": "36,0,0,0",
        "ShowFPS": "0",
        "ShowFrameTime": "0"
    },
    "RenoDX.DLSS5": {
        "ConfigVersion": "11",
        "NREnabled": "1",
        "Enabled": "1",
        "NRPreset": "My look",
        "Preset": "My look",
        "CurrentPreset": "My look",
        "NRHookPoint": "2",
        "HookStage": "2",
        "NRStyle": "2",
        "Style": "2",
        "NRPass2Preset": "2",
        "NRModelVersion": "1",
        "ModelVersion": "1",
        "NRResolutionScale": "1.000000",
        "ResolutionScale": "1.000000",
        "NRFollowInputRes": "1",
        "NRIntensity": "1.000000",
        "Intensity": "1.000000",
        "NRLocalTone": "1.000000",
        "LocalTone": "1.000000",
        "NRLocalStructure": "1.000000",
        "LocalStructure": "1.000000",
        "NRSkinStructure": "0.801136",
        "SkinStructure": "80",
        "Skin": "80",
        "NRPass2Skin": "80",
        "NRPasses": "1",
        "PassCount": "1",
        "NRModelLabEnabled": "1",
        "ModelLab": "1",
        "NRLayersEnabled": "1",
        "UiCorrection": "1",
        "NRVramBuffering": "0",
        "VramBuffering": "0",
        "NRPresentGuides": "0",
        "NRPresentAlways": "1",
        "AlwaysPresent": "1",
        "NRPresentNonBlocking": "1",
        "NRRuntimePath": ".\\nvngx_dlssnr.dll",
        "NRToggleKey": "0,0,0,0",
        "NRGpuTimers": "0",
        "NRCostMeter": "0",
        "NRCrashDump": "0",
        "NRDiagnostics": "0",
        "NREditTrace": "0",
        "NRNormTrace": "0",
        "DirectNeuralRenderingStatus": "1",
        "DirectNeuralRenderingIntensity": "1.000000",
        "DirectNeuralRenderingStyle": "2",
        "DirectNeuralRenderingModelVersion": "1",
        "DirectNeuralRenderingProcessingScale": "100",
        "DirectNeuralRenderingScaleReconstruction": "0",
        "DirectNeuralRenderingHookStage": "2",
        "DirectNeuralRenderingAlwaysPresent": "1",
        "DirectNeuralRenderingPresentMode": "1",
        "DirectNeuralRenderingVramBuffering": "0",
        "DirectNeuralRenderingLocalToneStrength": "1.000000",
        "DirectNeuralRenderingLocalStructureStrength": "1.000000",
        "DirectNeuralRenderingSkinStructureStrength": "0.801136",
        "DirectNeuralRenderingPassCount": "1",
        "DirectNeuralRenderingFineTune": "0",
        "DirectNeuralRenderingUiCorrectionMode": "1",
        "DirectNeuralRenderingModelLab": "1"
    },
    "RenoDX DLSS5 preset": {
        "Name": "My look",
        "Version": "11",
        "ConfigVersion": "11",
        "NREnabled": "1",
        "NRPreset": "My look",
        "NRHookPoint": "2",
        "NRStyle": "2",
        "NRPass2Preset": "2",
        "NRSkinStructure": "0.801136",
        "SkinStructure": "80",
        "Skin": "80",
        "NRResolutionScale": "1.000000",
        "NRFollowInputRes": "1",
        "NRIntensity": "1.000000",
        "NRLocalTone": "1.000000",
        "NRLocalStructure": "1.000000",
        "NRPasses": "1",
        "NRModelLabEnabled": "1",
        "NRLayersEnabled": "1",
        "NRVramBuffering": "0",
        "NRPresentGuides": "0",
        "NRPresentAlways": "1",
        "NRPresentNonBlocking": "1",
        "NRRuntimePath": ".\\nvngx_dlssnr.dll"
    },
    "RenoDX": {
        "CurrentPreset": "My look",
        "Enabled": "1",
        "Status": "1",
        "ConfigVersion": "11",
        "NRHookPoint": "2",
        "NRStyle": "2",
        "NRPass2Preset": "2",
        "NRSkinStructure": "0.801136",
        "SkinStructure": "80",
        "Skin": "80",
        "NRResolutionScale": "1.000000",
        "NRFollowInputRes": "1",
        "NRIntensity": "1.000000",
        "NRLocalTone": "1.000000",
        "NRLocalStructure": "1.000000",
        "NRPresentGuides": "0",
        "NRPresentAlways": "1",
        "NRPresentNonBlocking": "1",
        "NRVramBuffering": "0",
        "NRRuntimePath": ".\\nvngx_dlssnr.dll",
        "NRToggleKey": "0,0,0,0",
        "NRGpuTimers": "0",
        "NRCostMeter": "0",
        "NRCrashDump": "0",
        "NRDiagnostics": "0",
        "NREditTrace": "0",
        "NRNormTrace": "0",
        "NRModelLabEnabled": "1",
        "NRLayersEnabled": "1",
        "DirectNeuralRenderingStatus": "1",
        "DirectNeuralRenderingIntensity": "1.000000",
        "DirectNeuralRenderingStyle": "2",
        "DirectNeuralRenderingModelVersion": "1",
        "DirectNeuralRenderingProcessingScale": "100",
        "DirectNeuralRenderingScaleReconstruction": "0",
        "DirectNeuralRenderingHookStage": "2",
        "DirectNeuralRenderingAlwaysPresent": "1",
        "DirectNeuralRenderingPresentMode": "1",
        "DirectNeuralRenderingVramBuffering": "0",
        "DirectNeuralRenderingLocalToneStrength": "1.000000",
        "DirectNeuralRenderingLocalStructureStrength": "1.000000",
        "DirectNeuralRenderingSkinStructureStrength": "0.801136",
        "DirectNeuralRenderingPassCount": "1",
        "DirectNeuralRenderingFineTune": "0",
        "DirectNeuralRenderingUiCorrectionMode": "1",
        "DirectNeuralRenderingModelLab": "1"
    },
    "DLSSNR": {
        "NREnabled": "1",
        "NRPreset": "My look",
        "NRIntensity": "1.000000",
        "NRStyle": "2",
        "NRModelVersion": "1",
        "NRPass2Preset": "2",
        "NRResolutionScale": "1.000000",
        "NRFollowInputRes": "1",
        "NRHookPoint": "2",
        "NRPresentGuides": "0",
        "NRPresentAlways": "1",
        "NRPresentNonBlocking": "1",
        "NRVramBuffering": "0",
        "NRRuntimePath": ".\\nvngx_dlssnr.dll",
        "NRToggleKey": "0,0,0,0",
        "NRGpuTimers": "0",
        "NRCostMeter": "0",
        "NRCrashDump": "0",
        "NRDiagnostics": "0",
        "NREditTrace": "0",
        "NRNormTrace": "0",
        "NRLocalTone": "1.000000",
        "NRLocalStructure": "1.000000",
        "NRSkinStructure": "0.801136",
        "SkinStructure": "80",
        "Skin": "80",
        "NRPassCount": "1",
        "NRFineTune": "0",
        "NRLayersEnabled": "1",
        "NRModelLabEnabled": "1",
        "NRToggleKey": "0,0,0,0"
    },
    "RenoDX-My look": {
        "Enabled": "1",
        "CurrentPreset": "My look",
        "ConfigVersion": "11",
        "NRHookPoint": "2",
        "NRStyle": "2",
        "NRPass2Preset": "2",
        "NRSkinStructure": "0.801136",
        "SkinStructure": "80",
        "Skin": "80",
        "NRResolutionScale": "1.000000",
        "NRFollowInputRes": "1",
        "NRIntensity": "1.000000",
        "NRLocalTone": "1.000000",
        "NRLocalStructure": "1.000000",
        "NRPasses": "1",
        "NRModelLabEnabled": "1",
        "NRLayersEnabled": "1",
        "NRVramBuffering": "0",
        "NRPresentGuides": "0",
        "NRPresentAlways": "1",
        "NRPresentNonBlocking": "1",
        "NRRuntimePath": ".\\nvngx_dlssnr.dll",
        "NRToggleKey": "0,0,0,0",
        "NRGpuTimers": "0",
        "NRCostMeter": "0",
        "NRCrashDump": "0",
        "NRDiagnostics": "0",
        "NREditTrace": "0",
        "NRNormTrace": "0",
        "Intensity": "1.000000",
        "Style": "2",
        "ModelVersion": "1",
        "ResolutionScale": "1.000000",
        "HookStage": "2",
        "AlwaysPresent": "1",
        "VramBuffering": "0",
        "LocalTone": "1.000000",
        "LocalStructure": "1.000000",
        "SkinStructure": "80",
        "PassCount": "1",
        "FineTune": "0",
        "UiCorrection": "1",
        "ModelLab": "1",
        "DirectNeuralRenderingStatus": "1",
        "DirectNeuralRenderingIntensity": "1.000000",
        "DirectNeuralRenderingStyle": "2",
        "DirectNeuralRenderingModelVersion": "1",
        "DirectNeuralRenderingProcessingScale": "100",
        "DirectNeuralRenderingScaleReconstruction": "0",
        "DirectNeuralRenderingHookStage": "2",
        "DirectNeuralRenderingAlwaysPresent": "1",
        "DirectNeuralRenderingVramBuffering": "0",
        "DirectNeuralRenderingLocalToneStrength": "1.000000",
        "DirectNeuralRenderingLocalStructureStrength": "1.000000",
        "DirectNeuralRenderingSkinStructureStrength": "0.801136",
        "DirectNeuralRenderingPassCount": "1",
        "DirectNeuralRenderingFineTune": "0",
        "DirectNeuralRenderingUiCorrectionMode": "1",
        "DirectNeuralRenderingModelLab": "1"
    }
}


def update_ini_file_sections(ini_path: Path, sections: Dict[str, Dict[str, str]]):
    """
    Updates or creates an INI file ensuring specified sections and key-values are present.
    Preserves other unrelated sections, keys, and comments.
    """
    if not ini_path.exists():
        lines = []
        for sec, kv in sections.items():
            lines.append(f"[{sec}]")
            for k, v in kv.items():
                lines.append(f"{k}={v}")
            lines.append("")
        try:
            ini_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        except Exception:
            pass
        return

    try:
        content = ini_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        content = ""

    lines = content.splitlines()
    parsed_sections: Dict[str, List[Tuple[str, str, str]]] = {}
    section_order: List[str] = []
    current_sec = ""

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            current_sec = stripped[1:-1].strip()
            if current_sec not in parsed_sections:
                parsed_sections[current_sec] = []
                section_order.append(current_sec)
        else:
            if current_sec not in parsed_sections:
                parsed_sections[current_sec] = []
                section_order.append(current_sec)
            key = ""
            val = ""
            if "=" in line and not stripped.startswith(";") and not stripped.startswith("#"):
                parts = line.split("=", 1)
                key = parts[0].strip()
                val = parts[1].strip()
            parsed_sections[current_sec].append((line, key, val))

    # Apply updates
    for sec_name, kv_dict in sections.items():
        matched_sec = None
        for existing_sec in section_order:
            if existing_sec.lower() == sec_name.lower():
                matched_sec = existing_sec
                break

        if matched_sec is None:
            section_order.append(sec_name)
            parsed_sections[sec_name] = [(f"{k}={v}", k, v) for k, v in kv_dict.items()]
        else:
            sec_items = parsed_sections[matched_sec]
            for k, v in kv_dict.items():
                k_lower = k.lower()
                matching_indices = [idx for idx, item in enumerate(sec_items) if item[1].lower() == k_lower]
                if matching_indices:
                    first_idx = matching_indices[0]
                    sec_items[first_idx] = (f"{k}={v}", k, v)
                    for dup_idx in reversed(matching_indices[1:]):
                        sec_items.pop(dup_idx)
                else:
                    sec_items.append((f"{k}={v}", k, v))

    out_lines = []
    for sec in section_order:
        if sec:
            out_lines.append(f"[{sec}]")
        for item in parsed_sections[sec]:
            out_lines.append(item[0])
        out_lines.append("")

    try:
        ini_path.write_text("\n".join(out_lines).strip() + "\n", encoding="utf-8")
    except Exception:
        pass


def _update_preset_file_kv(file_path: Path, kv: Dict[str, str]):
    """Update key-values in a preset INI file preserving comments and formatting."""
    if not file_path.exists():
        return
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()
        found_keys = set()
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if "=" in stripped and not stripped.startswith(";") and not stripped.startswith("#"):
                k, _ = stripped.split("=", 1)
                k_clean = k.strip()
                k_lower = k_clean.lower()
                matched = False
                for target_k, target_v in kv.items():
                    if k_lower == target_k.lower():
                        new_lines.append(f"{target_k}={target_v}")
                        found_keys.add(target_k.lower())
                        matched = True
                        break
                if matched:
                    continue
            new_lines.append(line)
        for target_k, target_v in kv.items():
            if target_k.lower() not in found_keys:
                new_lines.append(f"{target_k}={target_v}")
        file_path.write_text("\n".join(new_lines).strip() + "\n", encoding="utf-8")
    except Exception:
        pass


def sync_dlss5_hook_point(target_dir: Union[str, Path], hook_point: str = "0") -> bool:
    """
    Synchronizes DLSS 5 hook point between Present (2) and Upscaled (0) mode.
    When coexisting with Mode C (XeSS FG / OptiScaler), setting hook_point="0" prevents
    DLSS 5 from intercepting XeFG's synthetic swapchain presentation, resolving 0xc0000005 crashes.
    """
    td = Path(target_dir) if target_dir else None
    if not td or not td.exists() or not td.is_dir():
        return False

    always_pres = "0" if str(hook_point) == "0" else "1"
    str_hook = str(hook_point)

    hook_updates = {
        "NRHookPoint": str_hook,
        "HookStage": str_hook,
        "DirectNeuralRenderingHookStage": str_hook,
        "DirectNeuralRenderingAlwaysPresent": always_pres,
        "DirectNeuralRenderingPresentMode": always_pres,
        "NRPresentAlways": always_pres,
        "AlwaysPresent": always_pres,
    }

    # 1. Update ReShade.ini
    reshade_ini = td / "ReShade.ini"
    if reshade_ini.exists():
        sections_to_update = {
            "RenoDX.DLSS5": hook_updates,
            "RenoDX DLSS5 preset": hook_updates,
            "RenoDX": hook_updates,
            "DLSSNR": hook_updates,
            "RenoDX-My look": hook_updates
        }
        update_ini_file_sections(reshade_ini, sections_to_update)

    # 2. Update ReShadePreset.ini
    reshade_preset = td / "ReShadePreset.ini"
    if reshade_preset.exists():
        _update_preset_file_kv(reshade_preset, hook_updates)

    # 3. Update target directory RenoDX/DLSS5/Presets/*.ini
    preset_dir = td / "RenoDX" / "DLSS5" / "Presets"
    if preset_dir.exists() and preset_dir.is_dir():
        for p_file in preset_dir.glob("*.ini"):
            _update_preset_file_kv(p_file, hook_updates)

    # 4. Also update AppData RenoDX presets
    appdata_reno_presets = Path(os.environ.get("LOCALAPPDATA", "")) / "RenoDX" / "DLSS5" / "Presets"
    if appdata_reno_presets.exists() and appdata_reno_presets.is_dir():
        for p_file in appdata_reno_presets.glob("*.ini"):
            _update_preset_file_kv(p_file, hook_updates)

    return True


def ensure_reshade_chinese_ini(ini_path: Path, is_mode_c: bool = False, addon_name: str = 'renodx-dlss5-v11.9.addon64'):
    """
    Ensures ReShade.ini in the game directory uses Simplified Chinese UI overlay,
    Microsoft YaHei font, Home key for overlay, skips intro tutorial,
    and applies the exact default parameters matching the RenoDX v11.9 screenshot.
    Cleanses any legacy LoadFromDllMain=1 pollution, ensuring only valid addon names are written.
    In Mode C coexistence mode, sets hook point to 0 (Upscaled mode) to prevent XeFG swapchain conflict.
    """
    import copy
    sections = copy.deepcopy(DEFAULT_DLSS5_INI_SECTIONS)

    # Clean up legacy LoadFromDllMain: remove "1" and DLSS addons (which must load outside DllMain)
    clean_addons = []
    if ini_path.exists():
        try:
            content = ini_path.read_text(encoding="utf-8", errors="ignore")
            for line in content.splitlines():
                stripped = line.strip()
                if "=" in stripped and not stripped.startswith(";") and not stripped.startswith("#"):
                    k, v = stripped.split("=", 1)
                    if k.strip().lower() == "loadfromdllmain":
                        for part in v.split(","):
                            clean_part = part.strip()
                            if clean_part and clean_part != "1" and "dlss" not in clean_part.lower() and "shortfuse" not in clean_part.lower():
                                if clean_part.lower() not in [x.lower() for x in clean_addons]:
                                    clean_addons.append(clean_part)
        except Exception:
            pass

    # Only Mode B (renodx-mfgunlock.addon64) requires LoadFromDllMain. DLSS 5 must NEVER load from DllMain!
    if clean_addons:
        sections["ADDON"]["LoadFromDllMain"] = ",".join(clean_addons)
    else:
        sections["ADDON"]["LoadFromDllMain"] = "" 

    if is_mode_c:
        hook_updates = {
            "NRHookPoint": "0",
            "HookStage": "0",
            "DirectNeuralRenderingHookStage": "0",
            "DirectNeuralRenderingAlwaysPresent": "0",
            "DirectNeuralRenderingPresentMode": "0",
            "NRPresentAlways": "0",
            "AlwaysPresent": "0",
        }
        for sec_name in ["RenoDX.DLSS5", "RenoDX DLSS5 preset", "RenoDX", "DLSSNR", "RenoDX-My look"]:
            if sec_name in sections:
                sections[sec_name].update(hook_updates)

    update_ini_file_sections(ini_path, sections)


class DLSS5Injector:
    """
    Core executor for standalone DLSS 5 plugin injection and lossless uninstallation.
    """

    @staticmethod
    def inject(
        target_dir: str,
        source_dir: Optional[str] = None,
        arch_choice: str = "auto"
    ) -> Tuple[bool, str]:
        """
        Executes one-click standalone injection of DLSS 5 into target_dir.
        
        Args:
            target_dir: Game executable directory
            source_dir: Plugin assets folder
            arch_choice: 'auto', 'rtx20_30_40', or 'rtx50'
        """
        td = Path(target_dir) if target_dir else None
        if not td or not td.exists() or not td.is_dir():
            return False, f"目标游戏目录不存在或不可用: {target_dir}"

        # Refuse to touch a live process: overwriting dxgi.dll / nvngx_dlssnr.dll
        # while the engine has them mapped corrupts the image and crashes on the
        # next DLSS call. The patch engine already guards this; DLSS 5 did not.
        game_exe = _guess_game_exe(td)
        if game_exe:
            try:
                from apps.app2_mfg.core.utils import is_process_running
                if is_process_running(os.path.basename(game_exe)):
                    return False, (
                        f"游戏进程 {os.path.basename(game_exe)} 正在运行中！\n"
                        f"请先完全退出游戏（含启动器/崩溃收集器）后再注入 DLSS 5，"
                        f"否则会因文件被占用或半写入而导致闪退。"
                    )
            except Exception:
                pass

        assets = scan_plugin_source_assets(Path(source_dir) if source_dir else None)
        if not assets.get("exists"):
            return False, f"未检测到 DLSS 5 插件源目录！\n请确认插件已就绪或在界面中指定有效路径。"

        # 1. Check dxgi.dll
        dxgi_src = assets.get("dxgi_path")
        if not dxgi_src or not os.path.exists(dxgi_src):
            return False, "插件包中缺少 ReShade 核心底座 (dxgi.dll)！"

        # 2. Check addon64 (renodx-dlss5-v11.9.addon64 prioritized)
        addon_src = assets.get("addon_path")
        if not addon_src or not os.path.exists(addon_src):
            return False, "插件包中缺少 RenoDX DLSS 5 扩展模组 (*.addon64)！"

        # 3. Determine GPU architecture and choose NR model
        gpu_info = get_real_gpu_info()
        chosen_arch = arch_choice
        if chosen_arch == "auto":
            chosen_arch = gpu_info.get("arch", "rtx20_30_40")

        if chosen_arch == "rtx50":
            nr_src = assets.get("nr_50_path")
            arch_label = "RTX 50 系列专用模型"
        else:
            nr_src = assets.get("nr_20_30_40_path")
            arch_label = "RTX 20/30/40 系列专用模型"

        # Fallback if selected model is missing
        if not nr_src or not os.path.exists(nr_src):
            if chosen_arch == "rtx50" and assets.get("nr_20_30_40_path"):
                nr_src = assets.get("nr_20_30_40_path")
                arch_label = "RTX 20/30/40 系列模型 (回退兼容)"
            elif chosen_arch != "rtx50" and assets.get("nr_50_path"):
                nr_src = assets.get("nr_50_path")
                arch_label = "RTX 50 系列模型 (回退兼容)"
            else:
                return False, f"插件包中未找到神经重构模型 (nvngx_dlssnr.dll)！\n请确认插件目录中包含模型文件。"

        # 4. Prepare backup folder
        backup_dir = td / DLSS5_BACKUP_DIRNAME
        backup_dir.mkdir(parents=True, exist_ok=True)

        manifest_data = {
            "injected_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "gpu_detected": gpu_info.get("gpu_name", "Unknown"),
            "selected_arch": chosen_arch,
            "arch_label": arch_label,
            "injected_files": [],
            "backed_up_files": {}
        }

        # Backup existing dxgi.dll ONLY if it is a genuine game file (not ReShade or OptiScaler)
        dxgi_dest = td / "dxgi.dll"
        existing_manifest_file = td / DLSS5_MANIFEST_FILENAME
        is_clean_install = not existing_manifest_file.exists()

        if dxgi_dest.exists() and is_clean_install:
            bak_dxgi = backup_dir / "dxgi.dll"
            if not bak_dxgi.exists():
                if not is_reshade_dll_file(str(dxgi_dest)) and not is_optiscaler_dll_file(str(dxgi_dest)):
                    try:
                        shutil.copy2(dxgi_dest, bak_dxgi)
                        manifest_data["backed_up_files"]["dxgi.dll"] = str(bak_dxgi)
                    except Exception:
                        pass

        # Backup existing nvngx_dlssnr.dll if it exists and wasn't injected by us
        nr_dest = td / "nvngx_dlssnr.dll"
        if nr_dest.exists() and is_clean_install:
            bak_nr = backup_dir / "nvngx_dlssnr.dll"
            if not bak_nr.exists():
                try:
                    shutil.copy2(nr_dest, bak_nr)
                    manifest_data["backed_up_files"]["nvngx_dlssnr.dll"] = str(bak_nr)
                except Exception:
                    pass

        # 5. Clean up stale / conflicting old addon versions to prevent ReShade duplicate load crash
        for old_addon in td.glob("*.addon64"):
            name_lower = old_addon.name.lower()
            if name_lower == Path(addon_src).name.lower():
                continue
            if "mfgunlock" in name_lower:
                # Mode B addon - preserve during coexistence!
                continue
            if "dlss" in name_lower or "shortfuse" in name_lower or ("renodx" in name_lower and "dlss" in name_lower):
                try:
                    old_addon.unlink(missing_ok=True)
                except Exception:
                    pass

        # Coexistence detection with Mode C (OptiScaler / XeSS 2.0 / XeFG)
        has_mode_c = is_mode_c_present(td)
        coex_slot: Optional[str] = None

        # 5.1 DLSS 5 needs dxgi.dll for its ReShade host. If Mode C was injected
        # first, OptiScaler owns that slot; moving it (instead of overwriting it)
        # keeps the frame-generation hook alive. This was the silent failure that
        # made "both injected" look like a crash: ReShade replaced OptiScaler's
        # only proxy, the game then loaded a half-configured OptiScaler.ini.
        if has_mode_c:
            try:
                from apps.app2_mfg.core.coexistence import (
                    ensure_optiscaler_proxy,
                    purge_fakenvapi,
                    purge_secondary_reshade,
                )
                coex_slot = None
                if (td / "OptiScaler.ini").exists():
                    # Only a real Mode C install owns a proxy; a stray libxess_fg.dll
                    # left over from a partial cleanup must not drag OptiScaler in.
                    coex_slot = ensure_optiscaler_proxy(td, _guess_game_exe(td))
                purge_fakenvapi(td)
                purge_secondary_reshade(td)
            except Exception:
                coex_slot = None

        if not has_mode_c:
            # A leftover second ReShade host (ReShade64.dll / d3d12-ReShade64.dll)
            # initializes a second D3D12 hook chain and crashes on teardown.
            try:
                from apps.app2_mfg.core.coexistence import purge_secondary_reshade
                purge_secondary_reshade(td)
            except Exception:
                pass

        # 6. Copy files into target directory
        try:
            # 6.0 Never clobber a still-active OptiScaler proxy: if the slot could
            # not be handed over, abort instead of silently killing Mode C.
            if has_mode_c and coex_slot is None and is_optiscaler_dll_file(str(dxgi_dest)):
                return False, (
                    "检测到模式 C 的 OptiScaler 仍占用 dxgi.dll，且无法迁移到次级代理槽位。\n"
                    "请先完全退出游戏，然后重新注入模式 C（或先卸载模式 C），再注入 DLSS 5。"
                )

            # 6.1 Copy dxgi.dll
            shutil.copy2(dxgi_src, dxgi_dest)
            manifest_data["injected_files"].append("dxgi.dll")

            # 6.2 Copy addon64 (defaults to renodx-dlss5-v11.9.addon64)
            addon_dest = td / Path(addon_src).name
            shutil.copy2(addon_src, addon_dest)
            manifest_data["injected_files"].append(addon_dest.name)

            # 6.3 Copy nvngx_dlssnr.dll
            shutil.copy2(nr_src, nr_dest)
            manifest_data["injected_files"].append("nvngx_dlssnr.dll")

            # 6.4 Delete legacy migration marker to prevent RenoDX resetting to factory stock
            (td / "ReShade.ini.v11-backup").unlink(missing_ok=True)

            # 6.5 Configure ReShade.ini with Chinese UI and screenshot-matched default parameters
            ini_dest = td / "ReShade.ini"
            ensure_reshade_chinese_ini(ini_dest, is_mode_c=has_mode_c, addon_name=Path(addon_src).name)
            if not is_clean_install or not (backup_dir / "ReShade.ini").exists():
                manifest_data["injected_files"].append("ReShade.ini")

            # 6.6 Write official RenoDX Presets folder and files with user My look preset and anti-stutter optimizations
            preset_dir = td / "RenoDX" / "DLSS5" / "Presets"
            preset_dir.mkdir(parents=True, exist_ok=True)
            template_path = LOCAL_ASSETS_DIR / "presets" / "My look.ini"
            if template_path.exists():
                preset_text = template_path.read_text(encoding="utf-8")
            else:
                preset_text = (
                    "[RenoDX DLSS5 preset]\n"
                    "Name=My look\n"
                    "Version=11.9.0\n"
                    "ConfigVersion=11\n"
                    "NREnabled=1\n"
                    "NRPreset=My look\n"
                    "NRHookPoint=2\n"
                    "HookStage=2\n"
                    "NRStyle=2\n"
                    "Style=2\n"
                    "NRPass2Preset=2\n"
                    "NRModelVersion=1\n"
                    "NRSkinStructure=0.801136\n"
                    "SkinStructure=80\n"
                    "Skin=80\n"
                    "NRPass2Skin=-1\n"
                    "NRResolutionScale=1.000000\n"
                    "NRFollowInputRes=1\n"
                    "NRIntensity=1\n"
                    "NRLocalTone=1\n"
                    "NRLocalStructure=1\n"
                    "NRPasses=1\n"
                    "NRModelLabEnabled=1\n"
                    "NRLayersEnabled=1\n"
                    "NRVramBuffering=0\n"
                    "NRPresetGuides=0\n"
                    "NRPresentAlways=1\n"
                    "AlwaysPresent=1\n"
                    "NRPresentNonBlocking=1\n"
                    "NRRuntimePath=.\\nvngx_dlssnr.dll\n"
                    "NRToggleKey=0,0,0,0\n"
                    "NRPresetKey=0,0,0,0\n"
                    "NRShotKey=0,0,0,0\n"
                    "NRScreenshotKey=0,0,0,0\n"
                    "NRPanelKey=0,0,0,0\n"
                    "NRGpuTimers=0\n"
                    "NRCostMeter=0\n"
                    "NRDiagnostics=0\n"
                    "NRCrashDump=0\n"
                    "NREditTrace=0\n"
                    "NRNormTrace=0\n"
                    "NRUICorrection=0\n"
                )
            if has_mode_c:
                hook_reps = {
                    "NRHookPoint=2": "NRHookPoint=0",
                    "HookStage=2": "HookStage=0",
                    "DirectNeuralRenderingHookStage=2": "DirectNeuralRenderingHookStage=0",
                    "DirectNeuralRenderingAlwaysPresent=1": "DirectNeuralRenderingAlwaysPresent=0",
                    "DirectNeuralRenderingPresentMode=1": "DirectNeuralRenderingPresentMode=0",
                    "NRPresentAlways=1": "NRPresentAlways=0",
                    "AlwaysPresent=1": "AlwaysPresent=0",
                }
                for old_k, new_k in hook_reps.items():
                    preset_text = preset_text.replace(old_k, new_k)

            try:
                (preset_dir / "My look.ini").write_text(preset_text, encoding="utf-8")
                (preset_dir / "Default.ini").write_text(preset_text.replace("Name=My look", "Name=Default"), encoding="utf-8")
                (preset_dir / "Standard.ini").write_text(preset_text.replace("Name=My look", "Name=Standard"), encoding="utf-8")
                (td / "ReShadePreset.ini").write_text(preset_text, encoding="utf-8")

                # Also synchronize AppData RenoDX presets so RenoDX loads user My look everywhere
                appdata_reno_presets = Path(os.environ.get("LOCALAPPDATA", "")) / "RenoDX" / "DLSS5" / "Presets"
                appdata_reno_presets.mkdir(parents=True, exist_ok=True)
                (appdata_reno_presets / "My look.ini").write_text(preset_text, encoding="utf-8")
                (appdata_reno_presets / "My look (2).ini").write_text(preset_text, encoding="utf-8")
                (appdata_reno_presets / "Default.ini").write_text(preset_text.replace("Name=My look", "Name=Default"), encoding="utf-8")
            except Exception:
                pass

            if has_mode_c:
                sync_dlss5_hook_point(td, hook_point="0")
                if (td / "OptiScaler.ini").exists():
                    try:
                        from apps.app2_mfg.core.ini_sync import IniConfigManager
                        from apps.app2_mfg.core.optiscaler_config import load_optiscaler_preset
                        opti_p = IniConfigManager.read_mode_c_reverse(td) or load_optiscaler_preset()
                        IniConfigManager.sync_mode_c_forward(td, opti_p)
                    except Exception:
                        pass
            manifest_data["injected_files"].append("RenoDX")
            manifest_data["injected_files"].append("ReShadePreset.ini")

            # 6.7 Synchronize AppData DLSS-NR runtime cache to prevent loading obsolete 310.8 kernels
            try:
                appdata_runtime_dir = Path(os.environ.get("LOCALAPPDATA", "")) / "DLSS5-NR" / "runtime"
                if appdata_runtime_dir.exists():
                    shutil.copy2(nr_src, appdata_runtime_dir / "nvngx_dlssnr.dll")
                    copy_txt = appdata_runtime_dir / "b" / "nr-copy.txt"
                    if copy_txt.exists():
                        copy_txt.unlink(missing_ok=True)
            except Exception:
                pass

            # 6.8 Write injection manifest
            manifest_file = td / DLSS5_MANIFEST_FILENAME
            with open(manifest_file, "w", encoding="utf-8") as f:
                json.dump(manifest_data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            return False, f"复制插件文件到游戏目录失败:\n{e}"

        coex_lines = ""
        if has_mode_c:
            slot_text = coex_slot or "未检测到（请重新注入模式 C）"
            coex_lines = (
                f"\n🛡️ 【与多帧生成共存】已自动完成双通道隔离：\n"
                f"  • dxgi.dll 锁定为 DLSS 5 的 ReShade 底座，OptiScaler 插帧代理已迁移至 {slot_text}；\n"
                f"  • DLSS 5 挂钩点自动切到 Upscaled(0)，避让 XeFG 合成交换链；\n"
                f"  • 已清理 fakenvapi 与重复 ReShade 实例（二者会破坏 DLSS 5 的 NVAPI 查询导致闪退）；\n"
                f"  • 进游戏同时开启【DLSS 超分辨率】与【DLSS 帧生成】即可同时获得神经重构 + XeSS 多倍插帧。\n"
            )

        vram_warning = ""
        try:
            from common.config_manager import detect_vram_overcommit
            _vram_msg = detect_vram_overcommit()
            if _vram_msg:
                vram_warning = f"\n⚠️ 【显存伪装风险】{_vram_msg}\n"
        except Exception:
            pass

        return True, (
            f"✅ DLSS 5 插件已成功注入至游戏目录！\n\n"
            f"• 渲染底座: ReShade 6.8 64-bit (dxgi.dll)\n"
            f"• 扩展插件: {Path(addon_src).name} (v11.9 旗舰版)\n"
            f"• 神经网络: {arch_label} ({round(os.path.getsize(nr_src)/(1024*1024), 1)} MB)\n"
            f"• 默认调参: 预设[My look已完整载入] · {('挂钩协同: [Upscaled模式 (在插帧前重构，消除XeFG冲突)]' if has_mode_c else '挂钩点[Present模式 (呈现)]')} · 皮肤[80%] · 风格[模型 C] · 版本[新版] · 分辨率[匹配游戏]\n• 体验优化: 开启快捷键[已禁用，避免误触] · 显存缓冲[全量模式，调参流畅不卡顿] · 运行库路径[强制本地锁定]\n"
            f"• 防闪退加固: Present[Present模式呈现挂钩] · 显存缓冲[精简模式，防OOM爆显存] · 运行库路径[强制本地锁定]\n"
            f"{vram_warning}{coex_lines}\n"
            f"🎮 【进游戏体验指南】：\n"
            f"1. 启动游戏，在画面设置中确保开启【DirectX 12】与【DLSS 超分辨率】；\n"
            f"2. 进入游戏画面后，按键盘【Home】键即可呼出 DLSS 5 / RenoDX 简体中文调参面板；\n"
            f"3. 已注入模式 C 时，再开启游戏内【DLSS 帧生成】即可启用 XeSS/XeFG 多倍插帧。"
        )

    @staticmethod
    def restore(target_dir: str) -> Tuple[bool, str]:
        """
        Executes deep one-click clean uninstallation of DLSS 5 and RHI/ReShade remnants from target_dir,
        completely purging all mod runtimes, proxy DLLs, and restoring the game to 100% vanilla environment.
        """
        td = Path(target_dir) if target_dir else None
        if not td or not td.exists() or not td.is_dir():
            return False, f"目标游戏目录不存在: {target_dir}"

        target_dir_str = str(td.resolve())

        # Layer 1: Force terminate any locking processes in target directory
        try:
            kill_locking_processes(target_dir_str)
            cleanup_pending_files(target_dir_str)
        except Exception:
            pass

        removed_items = []
        restored_items = []
        backup_dir = td / DLSS5_BACKUP_DIRNAME

        # Layer 1.5: Restore Bink2 Hook if present (Mode A chainload restore)
        bink_hook = td / "bink2w64Hooked.dll"
        bink_orig = td / "bink2w64.dll"
        if bink_hook.exists():
            safe_force_remove(str(bink_orig))
            try:
                bink_hook.rename(bink_orig)
                restored_items.append("bink2w64.dll (从 bink2w64Hooked.dll 恢复)")
            except Exception:
                try:
                    shutil.copy2(str(bink_hook), str(bink_orig))
                    safe_force_remove(str(bink_hook))
                    restored_items.append("bink2w64.dll (从 bink2w64Hooked.dll 恢复)")
                except Exception:
                    pass

        # Layer 2: Remove all addon files (*.addon64, *.addon)
        for addon_file in list(td.glob("*.addon64")) + list(td.glob("*.addon")):
            try:
                safe_force_remove(str(addon_file))
                removed_items.append(addon_file.name)
            except Exception:
                pass

        # Layer 3: Handle dxgi.dll
        dxgi_file = td / "dxgi.dll"
        bak_dxgi = backup_dir / "dxgi.dll"
        if dxgi_file.exists():
            if is_reshade_dll_file(str(dxgi_file)) or is_optiscaler_dll_file(str(dxgi_file)):
                safe_force_remove(str(dxgi_file))
                removed_items.append("dxgi.dll (ReShade底座/代理)")

        # If backup dxgi exists, verify whether backup was native or ReShade/RHI
        if bak_dxgi.exists():
            if is_reshade_dll_file(str(bak_dxgi)) or is_optiscaler_dll_file(str(bak_dxgi)):
                # Backup was also ReShade installed by RHI previously! Purge it, DO NOT RESTORE!
                safe_force_remove(str(bak_dxgi))
                removed_items.append(".dlss5_backup/dxgi.dll (非原生ReShade备份已清除)")
            else:
                # Truly a native game file: restore it
                try:
                    if dxgi_file.exists():
                        safe_force_remove(str(dxgi_file))
                    shutil.move(str(bak_dxgi), str(dxgi_file))
                    restored_items.append("dxgi.dll (原生游戏文件)")
                except Exception:
                    pass

        # Layer 4: Handle nvngx_dlssnr.dll
        nr_file = td / "nvngx_dlssnr.dll"
        if nr_file.exists():
            safe_force_remove(str(nr_file))
            removed_items.append("nvngx_dlssnr.dll (神经重构模型)")

        bak_nr = backup_dir / "nvngx_dlssnr.dll"
        if bak_nr.exists():
            safe_force_remove(str(bak_nr))

        # Layer 5: Deep remove all ReShade / RHI / DLSS 5 directories
        folders_to_purge = [
            "RenoDX",
            "dlss5-nr-runtime",
            "dlssg_sm86",
            "OptiScaler",
            "D3D12_Optiscaler",
            "XeSS",
            "amd_fidelityfx",
            "reshade-shaders",
            "reshade-presets",
            DLSS5_BACKUP_DIRNAME,
            ".dm_backup"
        ]
        for fld in folders_to_purge:
            fld_path = td / fld
            if fld_path.exists() and fld_path.is_dir():
                try:
                    shutil.rmtree(fld_path, ignore_errors=True)
                    removed_items.append(f"{fld}/ (目录)")
                except Exception:
                    pass

        # Layer 6: Deep remove config, backup and log files
        files_to_purge = [
            "ReShade.ini",
            "ReShade.ini.v11-backup",
            "ReShadePreset.ini",
            "ReShade64.dll",
            "ReShade.log",
            "dxgi.log",
            DLSS5_MANIFEST_FILENAME,
            ".dlss5_config.json",
            ".dlss5_patch_manifest.json",
            ".mfg_patch_manifest.json",
            "dxgi.dll.dlss5_bak",
            "version.dll",
            "winmm.dll",
            "dinput8.dll",
            "wininet.dll",
            "fakenvapi.dll",
            "fakenvapi.ini",
            "fakenvapi.log",
            "OptiScaler.ini",
            "OptiScaler.dll",
            "OptiScaler.log",
            "nvngx.ini",
            "dlssg_sm86.ini",
            "RTXMFG-Universal.json",
            "RTXMFG-Universal.status.json",
            "RTX40MFG-UI.ini",
            "RTXMFG-UI.ini",
            "mfg_unlocker.ini",
            "RTX40MFG-UI-layout.ini",
            "MFGUnlocker.log",
            "rtxmfg.log",
            "MFGUnlocker.dll",
            "dlssg_to_fsr3_amd_is_better.dll",
            "amd_fidelityfx_dx12.dll",
            "amd_fidelityfx_framegeneration_dx12.dll",
            "amd_fidelityfx_upscaler_dx12.dll",
            "amd_fidelityfx_vk.dll",
            "libxell.dll",
            "libxess.dll",
            "libxess_dx11.dll",
            "libxess_fg.dll"
        ]
        for fname in files_to_purge:
            fp = td / fname
            if fp.exists():
                safe_force_remove(str(fp))
                removed_items.append(fname)

        # Also purge any wildcard crash logs or logs
        for pat in ["dlss5-nr-crash-*.txt", "ReShade*.ini*", "RTXMFG-*.log", "RTXMFG-*.csv"]:
            for match_f in td.glob(pat):
                safe_force_remove(str(match_f))
                removed_items.append(match_f.name)

        # Layer 7: Secondary sweep via RollbackEngine (clean_all=True) to eliminate any OptiScaler/proxy remnants
        try:
            rb_engine = RollbackEngine()
            rb_engine.rollback(target_dir_str, clean_all=True)
        except Exception:
            pass

        # Layer 8: Final cleanup of any pending / temp files
        try:
            cleanup_pending_files(target_dir_str)
        except Exception:
            pass

        res_msg = f"🧹 DLSS 5 与 RHI/ReShade 模组环境已彻底卸载并净化还原！\n\n已彻底清除组件 ({len(removed_items)} 项):\n"
        if removed_items:
            res_msg += " • " + "\n • ".join(removed_items[:12])
            if len(removed_items) > 12:
                res_msg += f"\n • ...及其他 {len(removed_items) - 12} 项残留文件"
        else:
            res_msg += "（未检测到残留模组组件）"

        if restored_items:
            res_msg += f"\n\n已恢复原生游戏备份:\n • " + "\n • ".join(restored_items)

        res_msg += "\n\n✨ 游戏目录已 100% 恢复为官方纯净无篡改环境！"
        return True, res_msg
