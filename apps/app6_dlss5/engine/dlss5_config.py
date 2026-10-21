# -*- coding: utf-8 -*-
"""
DLSS 5 Neural Reconstruction Configuration Service (RenoDX ShortFuse 261017 & Legacy Mirror)
==========================================================================================
Manages DLSS 5 Direct Neural Reconstruction (DNR / NR Addon) parameter presets,
reading and writing configuration to ReShade.ini across all supported section headers:
- Modern ShortFuse RenoDX: [RenoDX], [DLSS], [RenoDX.DLSS]
- Backward Compatibility: [RenoDX.DLSS5], [DLSS5], [DLSS5-NR]
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Union, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
DEFAULTS_FILE = ROOT_DIR / "defaults" / "app6_dlss5" / "dlss5_preset.json"

DEFAULT_DLSS5_CONFIG: Dict[str, Any] = {
    # GPU Model Architecture ("auto", "rtx20_30_40", "rtx50")
    "gpu_arch": "auto",

    # RenoDX Direct Neural Rendering (ShortFuse Official)
    "status": 1,               # 1: 启用神经重构 (DirectNeuralRenderingStatus)
    "hook_stage": 2,           # 2: Present 呈现阶段 · 最稳防闪退 (DirectNeuralRenderingHookStage)
    "reuse_upscaling": 1,      # 1: 可选复用 DLSS 超分运动向量与深度 (DirectNeuralRenderingReuseDlssUpscalingResources)
    "ui_correction": 0,        # 0: 自动 UI 校正 (DirectNeuralRenderingUiCorrectionMode)
    "intensity": 1.00,         # 整体重构强度 1.00 (DirectNeuralRenderingIntensity)
    "style": 2,                # 模型样式: 0=模型A(原生), 1=模型B(锐度), 2=模型C(电影柔和·抑噪)
    "local_structure": 1.00,   # 结构强度 (DirectNeuralRenderingLocalStructureStrength)
    "local_tone": 1.00,        # 局部色调 (DirectNeuralRenderingLocalToneStrength)
    "auto_mask": 1,            # 角色蒙版 (DirectNeuralRenderingAutoMask · 默认开启保护角色与UI)
    "skin_structure": 1.00,    # 皮肤结构 (DirectNeuralRenderingSkinStructureStrength)
    "processing_scale": 0.67,  # 重构分辨率缩放 (DirectNeuralRenderingProcessingScale)
    "pass_count": 1,           # 推理遍数 1 Pass (DirectNeuralRenderingPassCount)
    "encoding": 0,             # 色彩编码 0: 自动 (DirectNeuralRenderingEncoding)
    "signal_encoding": 0,      # NR 信号编码 0: 自动 (DirectNeuralRenderingSignalEncoding)
    "diffuse_white": 203.0,    # 参考白场亮度 203.0 nits (DirectNeuralRenderingDiffuseWhiteNits)
    "block_hudless": 0,        # 屏蔽 HUD 源 (DirectNeuralRenderingBlockHudless)
    "exposure_mode": 0,        # 曝光模式: 0 正常 (DirectNeuralRenderingExposureMode)
    "exposure": 1.00,          # 曝光乘数 1.00x (DirectNeuralRenderingExposure)

    # DLSS Quality & Render Preset Overrides (Anti-Preset D -> Preset K)
    "dlss_preset": 11,         # 11: Preset K (DLSSPresetDLAA, Quality, Balanced, Performance, UltraPerformance)
    "dlss_quality_mode": 0,    # 0: 游戏默认 (DLSSQualityMode)
    "dlss_auto_exposure": 0,   # 0: 游戏默认 (DLSSAutoExposure)

    # Legacy Compatibility Keys (for older addon / test suite compatibility)
    "uplift": 1,
    "hook_point": 2,
    "passes": 1,
    "res_scale": 0.67,
    "vram": "Reduced",
    "non_blocking": 1,
    "hdr": 0,
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
    Inspects [RenoDX], [DLSS], [RenoDX.DLSS] first, then legacy [RenoDX.DLSS5], [DLSS5], [DLSS5-NR].
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

    # Check root section (ReShade nullptr section) and modern RenoDX / DLSS sections
    root_sec = sections.get("", {})
    mod_sec = dict(sections.get("RenoDX") or sections.get("DLSS") or sections.get("RenoDX.DLSS") or {})
    # Prioritize root_sec values as ReShade gets/sets them at root
    mod_sec.update(root_sec)
    legacy_sec = sections.get("RenoDX.DLSS5") or sections.get("DLSS5") or sections.get("DLSS5-NR") or {}

    # Modern RenoDX Keys
    if "DirectNeuralRenderingStatus" in mod_sec:
        try:
            config["status"] = int(mod_sec["DirectNeuralRenderingStatus"])
            config["uplift"] = config["status"]
        except Exception:
            pass

    if "DirectNeuralRenderingHookStage" in mod_sec:
        try:
            config["hook_stage"] = int(mod_sec["DirectNeuralRenderingHookStage"])
            config["hook_point"] = config["hook_stage"]
        except Exception:
            pass

    if "DirectNeuralRenderingReuseDlssUpscalingResources" in mod_sec:
        try:
            config["reuse_upscaling"] = int(mod_sec["DirectNeuralRenderingReuseDlssUpscalingResources"])
        except Exception:
            pass

    if "DirectNeuralRenderingUiCorrectionMode" in mod_sec:
        try:
            config["ui_correction"] = int(mod_sec["DirectNeuralRenderingUiCorrectionMode"])
        except Exception:
            pass

    if "DirectNeuralRenderingIntensity" in mod_sec:
        try:
            config["intensity"] = float(mod_sec["DirectNeuralRenderingIntensity"])
        except Exception:
            pass

    if "DirectNeuralRenderingStyle" in mod_sec:
        try:
            config["style"] = int(mod_sec["DirectNeuralRenderingStyle"])
        except Exception:
            pass

    if "DirectNeuralRenderingLocalStructureStrength" in mod_sec:
        try:
            config["local_structure"] = float(mod_sec["DirectNeuralRenderingLocalStructureStrength"])
        except Exception:
            pass

    if "DirectNeuralRenderingLocalToneStrength" in mod_sec:
        try:
            config["local_tone"] = float(mod_sec["DirectNeuralRenderingLocalToneStrength"])
        except Exception:
            pass

    if "DirectNeuralRenderingAutoMask" in mod_sec:
        try:
            config["auto_mask"] = int(mod_sec["DirectNeuralRenderingAutoMask"])
        except Exception:
            pass

    if "DirectNeuralRenderingSkinStructureStrength" in mod_sec:
        try:
            config["skin_structure"] = float(mod_sec["DirectNeuralRenderingSkinStructureStrength"])
        except Exception:
            pass

    if "DirectNeuralRenderingProcessingScale" in mod_sec:
        try:
            config["processing_scale"] = float(mod_sec["DirectNeuralRenderingProcessingScale"])
            config["res_scale"] = config["processing_scale"]
        except Exception:
            pass

    if "DirectNeuralRenderingPassCount" in mod_sec:
        try:
            config["pass_count"] = int(mod_sec["DirectNeuralRenderingPassCount"])
            config["passes"] = config["pass_count"]
        except Exception:
            pass

    if "DirectNeuralRenderingEncoding" in mod_sec:
        try:
            config["encoding"] = int(mod_sec["DirectNeuralRenderingEncoding"])
            config["hdr"] = config["encoding"]
        except Exception:
            pass

    if "DLSSPresetQuality" in mod_sec:
        try:
            config["dlss_preset"] = int(mod_sec["DLSSPresetQuality"])
        except Exception:
            pass

    # Legacy Fallback Parsing
    if "NeuralUplift" in legacy_sec and "DirectNeuralRenderingStatus" not in mod_sec:
        try:
            config["uplift"] = int(legacy_sec["NeuralUplift"])
            config["status"] = config["uplift"]
        except Exception:
            pass

    if "NRHookPoint" in legacy_sec and "DirectNeuralRenderingHookStage" not in mod_sec:
        try:
            config["hook_point"] = int(legacy_sec["NRHookPoint"])
            config["hook_stage"] = config["hook_point"]
        except Exception:
            pass

    if "NRPasses" in legacy_sec and "DirectNeuralRenderingPassCount" not in mod_sec:
        try:
            config["passes"] = int(legacy_sec["NRPasses"])
            config["pass_count"] = config["passes"]
        except Exception:
            pass

    if "NRResolutionScale" in legacy_sec and "DirectNeuralRenderingProcessingScale" not in mod_sec:
        try:
            config["res_scale"] = float(legacy_sec["NRResolutionScale"])
            config["processing_scale"] = config["res_scale"]
        except Exception:
            pass

    if "NRIntensity" in legacy_sec and "DirectNeuralRenderingIntensity" not in mod_sec:
        try:
            config["intensity"] = float(legacy_sec["NRIntensity"])
        except Exception:
            pass

    if "NRStyle" in legacy_sec and "DirectNeuralRenderingStyle" not in mod_sec:
        try:
            config["style"] = int(legacy_sec["NRStyle"])
        except Exception:
            pass

    if "NRVramBuffering" in legacy_sec:
        val = legacy_sec["NRVramBuffering"].strip()
        if val in ["0", "Full", "full"]:
            config["vram"] = "Full"
        elif val in ["1", "Reduced", "reduced"]:
            config["vram"] = "Reduced"
        elif val in ["2", "Minimal", "minimal"]:
            config["vram"] = "Minimal"
        else:
            config["vram"] = val

    if "NRPresentNonBlocking" in legacy_sec:
        try:
            config["non_blocking"] = int(legacy_sec["NRPresentNonBlocking"])
        except Exception:
            pass

    return config


def write_game_dlss5_config(target_path: Union[str, Path], config: Dict[str, Any]) -> bool:
    """
    Writes DLSS 5 configuration into target_path (directory or ini file).
    Populates:
    1. Modern ShortFuse RenoDX sections: [RenoDX], [DLSS], [RenoDX.DLSS]
    2. Backward-compatible sections: [RenoDX.DLSS5], [DLSS5], [DLSS5-NR]
    3. Safely cleans [ADDON] LoadFromDllMain to prevent loader lock deadlock.
    Enforces Present hook stage (2) and Reduced VRAM buffering when Multi-Frame Generation is present.
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

    raw_stage = config.get("hook_stage", config.get("hook_point", 2))
    try:
        hook_val = int(raw_stage)
    except Exception:
        hook_val = 2

    # Under Multi-Frame Generation (dashdogy / renodx / OptiScaler), DLSS 5 cannot
    # capture directly on the direct command list at 'After Upscaling' (0 or 1) due to command list
    # collision with optical flow generation (list_refused=direct).
    # Hook point 2 (Present) is strictly enforced under MFG to prevent
    # 0x887A0006 DXGI_ERROR_DEVICE_HUNG TDR crashes.
    if has_mfg and hook_val in (0, 1):
        effective_hp = 2
    else:
        effective_hp = hook_val

    vram_val = str(config.get("vram", "Reduced"))
    if has_mfg and (vram_val.lower() in ["full", "0"]):
        vram_int_str = "1"
    elif vram_val.lower() in ["reduced", "1"]:
        vram_int_str = "1"
    elif vram_val.lower() in ["minimal", "2"]:
        vram_int_str = "2"
    else:
        vram_int_str = "0"

    status_val = int(config.get("status", config.get("uplift", 1)))
    intensity_val = float(config.get("intensity", 1.0))
    style_val = int(config.get("style", 2))
    proc_scale_val = float(config.get("processing_scale", config.get("res_scale", 0.67)))
    pass_cnt_val = int(config.get("pass_count", config.get("passes", 1)))
    encoding_val = int(config.get("encoding", config.get("hdr", 0)))
    dlss_preset_val = int(config.get("dlss_preset", 11))
    local_struct_val = float(config.get("local_structure", 1.0))
    local_tone_val = float(config.get("local_tone", 1.0))
    auto_mask_val = int(config.get("auto_mask", 0))
    skin_struct_val = float(config.get("skin_structure", 1.0))
    reuse_up_val = int(config.get("reuse_upscaling", 1))
    ui_corr_val = int(config.get("ui_correction", 0))
    block_hud_val = int(config.get("block_hudless", 0))
    exp_mode_val = int(config.get("exposure_mode", 0))
    exp_val = float(config.get("exposure", 1.0))
    white_nits_val = float(config.get("diffuse_white", 203.0))

    # 1. Modern RenoDX / ShortFuse direct dictionary
    renodx_dict = {
        "DirectNeuralRenderingStatus": str(status_val),
        "DirectNeuralRenderingHookStage": str(effective_hp),
        "DirectNeuralRenderingReuseDlssUpscalingResources": str(reuse_up_val),
        "DirectNeuralRenderingUiCorrectionMode": str(ui_corr_val),
        "DirectNeuralRenderingIntensity": f"{intensity_val:.6f}",
        "DirectNeuralRenderingStyle": str(style_val),
        "DirectNeuralRenderingLocalStructureStrength": f"{local_struct_val:.6f}",
        "DirectNeuralRenderingLocalToneStrength": f"{local_tone_val:.6f}",
        "DirectNeuralRenderingAutoMask": str(auto_mask_val),
        "DirectNeuralRenderingSkinStructureStrength": f"{skin_struct_val:.6f}",
        "DirectNeuralRenderingProcessingScale": f"{proc_scale_val:.6f}",
        "DirectNeuralRenderingPassCount": str(pass_cnt_val),
        "DirectNeuralRenderingEncoding": str(encoding_val),
        "DirectNeuralRenderingSignalEncoding": str(config.get("signal_encoding", 0)),
        "DirectNeuralRenderingDiffuseWhiteNits": f"{white_nits_val:.1f}",
        "DirectNeuralRenderingBlockHudless": str(block_hud_val),
        "DirectNeuralRenderingExposure": f"{exp_val:.6f}",
        "DirectNeuralRenderingExposureMode": str(exp_mode_val),
        "DLSSQualityMode": str(config.get("dlss_quality_mode", 0)),
        "DLSSAutoExposure": str(config.get("dlss_auto_exposure", 0)),
        "DLSSPresetDLAA": str(dlss_preset_val),
        "DLSSPresetQuality": str(dlss_preset_val),
        "DLSSPresetBalanced": str(dlss_preset_val),
        "DLSSPresetPerformance": str(dlss_preset_val),
        "DLSSPresetUltraQuality": str(dlss_preset_val),
        "DLSSPresetUltraPerformance": str(dlss_preset_val),
        # Internal evaluator and runtime keys (DLSSNR.*)
        "DLSSNR.Enabled": str(status_val),
        "DLSSNR.Intensity": f"{intensity_val:.6f}",
        "DLSSNR.Style": str(style_val),
        "DLSSNR.LocalToneStrength": f"{local_tone_val:.6f}",
        "DLSSNR.LocalStructureStrength": f"{local_struct_val:.6f}",
        "DLSSNR.SkinStructureStrength": f"{skin_struct_val:.6f}",
        "DLSSNR.GlobalToneStrength": f"{local_tone_val:.6f}",
        "DLSSNR.UseAutoMask": str(auto_mask_val),
        "DLSSNR.UICorrection": str(ui_corr_val),
        "DLSSNR.Scale": f"{proc_scale_val:.6f}",
        "DLSSNR.ScalingRatio": f"{proc_scale_val:.6f}",
        "DLSSNR.Hint.Render.Preset": str(dlss_preset_val),
    }

    # 2. [DLSS] section dictionary (includes OptiScaler / ReShade standard keys)
    dlss_section_dict = dict(renodx_dict)
    dlss_section_dict.update({
        "RenderPresetOverride": "true",
        "UseGenericAppIdWithDlss": "false",
        "RenderPresetForAll": str(dlss_preset_val),
    })

    # 3. Legacy compatibility dictionary
    legacy_dlss5_dict = {
        "ConfigVersion": "11",
        "EnableHooks": "2",
        "RuntimeSelectionMode": "1",
        "NeuralUplift": str(status_val),
        "NRHookPoint": str(effective_hp),
        "NRAutoFgFallback": "1",
        "NRPasses": str(pass_cnt_val),
        "NRResolutionScale": f"{proc_scale_val:.2f}",
        "NRIntensity": f"{intensity_val:.2f}",
        "NRStyle": str(style_val),
        "NRVramBuffering": vram_int_str,
        "NRPresentNonBlocking": str(config.get("non_blocking", 1)),
        "HDRCompatibilityMode": str(encoding_val),
        "NRRuntimePath": r".\nvngx_dlssnr.dll"
    }

    updates: Dict[str, Dict[str, Any]] = {
        "": renodx_dict,  # Root / global section (ReShade nullptr section, 100% in-game effective)
        "RenoDX": renodx_dict,
        "DLSS": dlss_section_dict,
        "RenoDX.DLSS": renodx_dict,
        "RenoDX.DLSS5": legacy_dlss5_dict,
        "DLSS5": legacy_dlss5_dict,
        "DLSS5-NR": legacy_dlss5_dict,
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
                if "lecram" not in x.lower() and "renodx-dlss" not in x.lower() and x != "1"
            ]
            updates["ADDON"] = {"LoadFromDllMain": ",".join(filtered)}

    ok = IniConfigManager.write_ini_sections(reshade_ini, updates)

    # Persist per-game settings cache
    if target_dir.exists():
        game_cfg_file = target_dir / ".dlss5_config.json"
        try:
            with open(game_cfg_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    return ok
