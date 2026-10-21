# -*- coding: utf-8 -*-
"""
DLSS 5 Neural Reconstruction Configuration Service
==================================================
Manages DLSS 5 (lecram / RenoDX NR Addon) parameter presets,
reading and writing configuration to ReShade.ini across all supported section headers
([RenoDX.DLSS5], [DLSS5], and [DLSS5-NR]).
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Union, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
DEFAULTS_FILE = ROOT_DIR / "defaults" / "app6_dlss5" / "dlss5_preset.json"

DEFAULT_DLSS5_CONFIG: Dict[str, Any] = {
    "uplift": 1,
    "hook_point": 2,          # 2 = Present (呈现阶段 · 最稳防闪退 · 推荐预设)
    "passes": 1,              # 1 Pass (标准极速 · 旗舰推荐)
    "res_scale": 0.67,        # 0.67 (重构分辨率缩放)
    "intensity": 1.00,        # 1.00 (重构强度权重)
    "style": 2,               # 2 = 电影感柔和 (Cinematic Soft · 柔化抑噪)
    "vram": "Reduced",        # Reduced (精简缓冲 · 消除显存竞争与防崩溃 · 推荐)
    "non_blocking": 1,        # 1 = 启用 Present 非阻塞呈现队列 (杜绝 D3D12 死锁与 TDR 崩溃)
    "hdr": 0,                 # 0 = 自动 / 原生 HDR (推荐)
    "runtime_path": r".\nvngx_dlssnr.dll"
}


def load_dlss5_preset() -> Dict[str, Any]:
    """Loads default DLSS 5 preset from defaults folder or fallback."""
    if DEFAULTS_FILE.exists():
        try:
            with open(DEFAULTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                res = DEFAULT_DLSS5_CONFIG.copy()
                res.update(data)
                return res
        except Exception:
            pass
    return DEFAULT_DLSS5_CONFIG.copy()


def save_dlss5_preset(preset: Dict[str, Any]) -> bool:
    """Saves user-adjusted DLSS 5 preset to defaults folder."""
    try:
        DEFAULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(DEFAULTS_FILE, "w", encoding="utf-8") as f:
            json.dump(preset, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def read_game_dlss5_config(target_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Reads existing DLSS 5 configuration from target_path (directory or ini file).
    Inspects [RenoDX.DLSS5], [DLSS5], and [DLSS5-NR] in order.
    Returns merged dictionary with default fallbacks.
    """
    config = load_dlss5_preset()
    tp = Path(target_path)
    target_dir = tp if tp.is_dir() else tp.parent
    game_cfg_file = target_dir / ".dlss5_config.json"
    if game_cfg_file.exists():
        try:
            with open(game_cfg_file, "r", encoding="utf-8") as f:
                saved_cfg = json.load(f)
                config.update(saved_cfg)
        except Exception:
            pass

    reshade_ini = tp if tp.is_file() or tp.suffix.lower() == ".ini" else (tp / "ReShade.ini")
    if not reshade_ini.exists():
        return config

    try:
        from apps.app2_mfg.core.ini_sync import IniConfigManager
        sections = IniConfigManager.read_ini_sections(reshade_ini)
    except Exception:
        return config

    sec = sections.get("RenoDX.DLSS5") or sections.get("DLSS5") or sections.get("DLSS5-NR") or {}
    if not sec:
        return config

    # Neural Uplift
    if "NeuralUplift" in sec:
        try:
            config["uplift"] = int(sec["NeuralUplift"])
        except Exception:
            pass

    # NRHookPoint
    if "NRHookPoint" in sec:
        try:
            config["hook_point"] = int(sec["NRHookPoint"])
        except Exception:
            pass

    # NRPasses
    if "NRPasses" in sec:
        try:
            config["passes"] = int(sec["NRPasses"])
        except Exception:
            pass

    # NRResolutionScale
    if "NRResolutionScale" in sec:
        try:
            config["res_scale"] = float(sec["NRResolutionScale"])
        except Exception:
            pass

    # NRIntensity
    if "NRIntensity" in sec:
        try:
            config["intensity"] = float(sec["NRIntensity"])
        except Exception:
            pass

    # NRStyle
    if "NRStyle" in sec:
        try:
            config["style"] = int(sec["NRStyle"])
        except Exception:
            pass

    # NRVramBuffering
    if "NRVramBuffering" in sec:
        val = sec["NRVramBuffering"].strip()
        if val in ["0", "Full", "full"]:
            config["vram"] = "Full"
        elif val in ["1", "Reduced", "reduced"]:
            config["vram"] = "Reduced"
        elif val in ["2", "Minimal", "minimal"]:
            config["vram"] = "Minimal"
        else:
            config["vram"] = val

    # NRPresentNonBlocking
    if "NRPresentNonBlocking" in sec:
        try:
            config["non_blocking"] = int(sec["NRPresentNonBlocking"])
        except Exception:
            pass

    # HDRCompatibilityMode
    if "HDRCompatibilityMode" in sec:
        try:
            config["hdr"] = int(sec["HDRCompatibilityMode"])
        except Exception:
            pass

    return config


def write_game_dlss5_config(target_path: Union[str, Path], config: Dict[str, Any]) -> bool:
    """
    Writes DLSS 5 configuration into target_path (directory or ini file) across all three
    section headers ([RenoDX.DLSS5], [DLSS5], [DLSS5-NR]) simultaneously.
    Also ensures [ADDON] LoadFromDllMain does not contain deadlock tokens.
    Automatically guards against D3D12 command list collisions and VRAM over-allocation
    when Multi-Frame Generation (Mode A, Mode B, Mode C) is present.
    """
    tp = Path(target_path)
    reshade_ini = tp if tp.is_file() or tp.suffix.lower() == ".ini" else (tp / "ReShade.ini")
    target_dir = reshade_ini.parent

    try:
        from apps.app2_mfg.core.ini_sync import IniConfigManager
    except Exception:
        return False

    has_mfg = False
    if target_dir.exists():
        mfg_indicators = [
            target_dir / "version.dll",
            target_dir / "RTXMFG-Universal.json",
            target_dir / "mfg_unlocker.ini",
            target_dir / "renodx-mfgunlock.addon64",
            target_dir / "OptiScaler.ini",
        ]
        has_mfg = any(p.exists() for p in mfg_indicators)

    raw_hp = config.get("hook_point", 2)
    try:
        hook_val = int(raw_hp)
    except Exception:
        hook_val = 2

    # Under Multi-Frame Generation (dashdogy / renodx / OptiScaler), DLSS 5 NR cannot
    # capture directly on the direct command list at 'After Upscaling' (0) due to command list
    # collision with optical flow generation (list_refused=direct).
    # Hook point 2 (Present) or 3 (Auto with fallback) is strictly enforced to prevent
    # 0x887A0006 DXGI_ERROR_DEVICE_HUNG TDR crashes.
    if has_mfg and hook_val in (0, 1):
        effective_hp = 2
    else:
        effective_hp = hook_val

    vram_val = str(config.get("vram", "Reduced"))
    # In full 4K UE5 titles with Nanite/Lumen, 'Full' (0) buffering keeps the 'After Upscaling'
    # safety net on the direct command list even under Present, triggering command list collisions
    # with Frame Generation (list_refused=direct) and PCIe paging thrashing (13s TDR timeouts).
    # 'Reduced' (1) disables the After Upscaling safety net under Present, running 100% clean.
    # Note: DLSS 5 addon parses NRVramBuffering as an INTEGER: 0=Full, 1=Reduced, 2=Minimal.
    if has_mfg and (vram_val.lower() in ["full", "0"]):
        vram_int_str = "1"
    elif vram_val.lower() in ["reduced", "1"]:
        vram_int_str = "1"
    elif vram_val.lower() in ["minimal", "2"]:
        vram_int_str = "2"
    else:
        vram_int_str = "0"

    dlss5_dict = {
        "ConfigVersion": "11",
        "EnableHooks": "2",
        "RuntimeSelectionMode": "1",
        "NeuralUplift": str(config.get("uplift", 1)),
        "NRHookPoint": str(effective_hp),
        "NRAutoFgFallback": "1",
        "NRPasses": str(config.get("passes", 1)),
        "NRResolutionScale": f"{float(config.get('res_scale', 0.67)):.2f}",
        "NRIntensity": f"{float(config.get('intensity', 1.0)):.2f}",
        "NRStyle": str(config.get("style", 2)),
        "NRVramBuffering": vram_int_str,
        "NRPresentNonBlocking": str(config.get("non_blocking", 1)),
        "HDRCompatibilityMode": str(config.get("hdr", 0)),
        "NRRuntimePath": r".\nvngx_dlssnr.dll"
    }

    updates: Dict[str, Dict[str, Any]] = {
        "RenoDX.DLSS5": dlss5_dict,
        "DLSS5": dlss5_dict,
        "DLSS5-NR": dlss5_dict,
    }

    # Ensure ADDON section does not dead-lock loader
    if reshade_ini.exists():
        sections = IniConfigManager.read_ini_sections(reshade_ini)
        addon_sec = sections.get("ADDON", {})
        main_dlls = addon_sec.get("LoadFromDllMain", "")
        if main_dlls:
            items = [x.strip() for x in main_dlls.split(",") if x.strip()]
            filtered = [
                x for x in items
                if "lecram" not in x.lower() and x != "1"
            ]
            updates["ADDON"] = {"LoadFromDllMain": ",".join(filtered)}

    ok = IniConfigManager.write_ini_sections(reshade_ini, updates)

    # Also persist per-game settings cache
    if target_dir.exists():
        game_cfg_file = target_dir / ".dlss5_config.json"
        try:
            with open(game_cfg_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    return ok
