"""
Configuration Manager - Pre-set Chinese Frame Generation & Upscaler Parameters
Supports Mode C (OptiScaler / XeSS 2.0 / FSR 3.1) and Mode B (RenoDX ReShade Addon).
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional

try:
    from core.ini_sync import IniConfigManager
except (ModuleNotFoundError, ImportError):
    try:
        from apps.app2_mfg.core.ini_sync import IniConfigManager
    except (ModuleNotFoundError, ImportError):
        from .ini_sync import IniConfigManager

DEFAULT_MODE_A_PRESET: Dict[str, Any] = {
    "multiplier": 3,              # 2=2X, 3=3X, 4=4X, 5=5X, 6=6X (默认 3X 三倍插帧)
    "dlss_preset": "K",           # 默认采用 DLSS 4 Transformer 模型 Preset K
    "dlssg_preset": "C",          # 默认采用 Model C (FG Lite 极速多帧 · 推荐跟随 nvapp)
    "menu_key": "Backspace",      # "Backspace", "F11", "Insert", "Home", "End"
    "bink_hook": False
}

DEFAULT_OPTISCALER_PRESET: Dict[str, Any] = {
    "fg_output": "xefg",          # "xefg", "fsrfg", "nukems"
    "fg_input": "dlssg",         # "dlssg", "nukems", "auto"
    "interpolation_count": 2,    # 1=2X, 2=3X, 3=4X, 4=5X, 5=6X (XeFG 默认 3X 三倍插帧)
    "dx12_upscaler": "auto",     # "auto", "xess", "dlss", "fsr31"
    "rcas_enabled": False,
    "rcas_sharpness": 0.0,
    "dlss_preset": "K",          # 默认采用 DLSS 4 Transformer 模型 Preset K (杜绝 D 模型)
    "menu_key": "Insert",        # "Insert", "Backspace", "Home", "F11", "End"
    "menu_scale": 2.0,           # In-game ImGui menu scale: 1.0 / 1.5 / 2.0 (4K default)
    "unlock_mfg": True           # Deploy dashdogy MFGUnlocker.asi so XeFG can reach 3X/4X
                                 # (libxess_fg alone caps non-Arc GPUs at 2X). Disable if the
                                 # ASI conflicts with the DLSS 5 addon on startup.
}

DEFAULT_RESHADE_PRESET: Dict[str, Any] = {
    "force_multiplier": 3,       # 0=Game controlled, 2, 3, 4, 5, 6
    "dlss_preset": "K",          # 默认采用 DLSS 4 Transformer 模型 Preset K
    "blackwell_kernels": 1,      # 1=Enabled, 0=Disabled
    "thin_geometry_isr": 1,      # ThinGeometryIntermediateScatter
    "thin_geometry_vwb": 1,      # ThinGeometryPreviousScatter
    "thin_geometry_bam": 1,      # ThinGeometryValidatedWarpBlend
    "hdr_ui_recomposition": 1,   # HDRUIRecomposition
    "dynamic_mfg": 0,            # DynamicMFG
    "temporal_fix": 1,           # TemporalFix
    "hdr_compatibility": 0       # HDRCompatibilityMode
}

def get_preset_config_file(filename: str = "optiscaler_preset.json") -> Path:
    """Resolve persistent path to configuration file in AppData."""
    try:
        from common.config_manager import get_app_config_path
        return get_app_config_path("app2_mfg", filename)
    except Exception:
        appdata = os.environ.get("APPDATA", str(Path.home()))
        fallback = Path(appdata) / "ToolboxMaster" / "config" / "app2_mfg" / filename
        fallback.parent.mkdir(parents=True, exist_ok=True)
        return fallback

# ----------------- Mode A / dashdogy Standalone Preset -----------------

def load_mode_a_preset() -> Dict[str, Any]:
    """Load user's saved Mode A preset, or return defaults if absent."""
    cfg_file = get_preset_config_file("mode_a_preset.json")
    preset = dict(DEFAULT_MODE_A_PRESET)
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    preset.update(data)
        except Exception:
            pass


        # 默认 DLSS 预设升级至 DLSS 4 Transformer 模型 Preset K
    if preset.get("dlss_preset") in ("Default", "0", "", None) and not preset.get("user_customized_dlss_preset", False):
        preset["dlss_preset"] = "K"
        try:
            cfg_file.parent.mkdir(parents=True, exist_ok=True)
            with open(cfg_file, "w", encoding="utf-8") as f:
                json.dump(preset, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    return preset

def save_mode_a_preset(preset: Dict[str, Any]) -> bool:
    """Save user's Mode A preset to persistent storage."""
    cfg_file = get_preset_config_file("mode_a_preset.json")
    try:
        cfg_file.parent.mkdir(parents=True, exist_ok=True)
        merged = dict(DEFAULT_MODE_A_PRESET)
        merged.update(preset)
        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False

def get_mode_a_preset_summary(config: Optional[Dict[str, Any]] = None) -> str:
    """Format a human-readable one-line summary of Mode A preset in Chinese."""
    if config is None:
        config = load_mode_a_preset()

    mult = int(config.get("multiplier", 3))
    preset = config.get("dlss_preset", "Default")
    dlssg_p = config.get("dlssg_preset", "C")
    key = config.get("menu_key", "Backspace")
    bink = " + Bink2链式" if config.get("bink_hook") else ""
    return f"dashdogy [{mult}X 倍率] | DLSS {preset} 档 | FG {dlssg_p} 模型 | 快捷键: {key}{bink}"

# ----------------- Mode C / OptiScaler Preset -----------------

def load_optiscaler_preset() -> Dict[str, Any]:
    """Load user's saved OptiScaler preset, or return defaults if absent."""
    cfg_file = get_preset_config_file("optiscaler_preset.json")
    preset = dict(DEFAULT_OPTISCALER_PRESET)
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    preset.update(data)
        except Exception:
            pass

    # v1.3.8 一次性迁移：新出厂默认 = 开启 MFG-Unlocker 多帧解锁 + 3X XeFG。
    # 旧版本保存的配置里没有 preset_schema_version，会残留“未解锁 / 2X”的旧默认，
    # 这里统一升级一次；面板手动保存后会写入 version=2，之后不再覆盖用户选择。
    if int(preset.get("preset_schema_version", 0) or 0) < 2:
        preset["unlock_mfg"] = True
        if not preset.get("user_customized_interpolation"):
            preset["interpolation_count"] = 2
        preset["preset_schema_version"] = 2
        try:
            cfg_file.parent.mkdir(parents=True, exist_ok=True)
            with open(cfg_file, "w", encoding="utf-8") as f:
                json.dump(preset, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    # 兼容性修复与默认超分保护：
    # 若配置中 dx12_upscaler 为旧版本残留的默认值 "xess"，且未被用户显式主动修改，
    # 强制重置为官方规范默认值 "auto" (自动继承游戏内超分)，防止首次打开/安装时错误回退到 XeSS
    if preset.get("dx12_upscaler") in ("xess", "dlss") and not preset.get("user_customized_upscaler", False):
        preset["dx12_upscaler"] = "auto"
        try:
            cfg_file.parent.mkdir(parents=True, exist_ok=True)
            with open(cfg_file, "w", encoding="utf-8") as f:
                json.dump(preset, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    # 兼容性修复与默认锐化保护：
    # 若配置中 rcas_enabled 为旧版默认值 True (0.40) 且未被用户显式主动勾选，
    # 强制重置为最新官方规范默认值 False / 0.0，防止首次打开或重置时默认强开锐化
    if not preset.get("user_customized_rcas", False) and preset.get("rcas_enabled") is True and round(float(preset.get("rcas_sharpness", 0.0)), 2) == 0.40:
        preset["rcas_enabled"] = False
        preset["rcas_sharpness"] = 0.0
        try:
            cfg_file.parent.mkdir(parents=True, exist_ok=True)
            with open(cfg_file, "w", encoding="utf-8") as f:
                json.dump(preset, f, indent=2, ensure_ascii=False)
        except Exception:
            pass



        # 默认 DLSS 预设升级至 DLSS 4 Transformer 模型 Preset K (杜绝 D 模型)
    if preset.get("dlss_preset") in ("Default", "0", "", None) and not preset.get("user_customized_dlss_preset", False):
        preset["dlss_preset"] = "K"
        try:
            cfg_file.parent.mkdir(parents=True, exist_ok=True)
            with open(cfg_file, "w", encoding="utf-8") as f:
                json.dump(preset, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    # XeSS (XeFG) 默认升级为 3X 三倍帧生成 (interpolation_count = 2)
    if preset.get("interpolation_count") in (1, None) and not preset.get("user_customized_interpolation", False):
        preset["interpolation_count"] = 2
        try:
            cfg_file.parent.mkdir(parents=True, exist_ok=True)
            with open(cfg_file, "w", encoding="utf-8") as f:
                json.dump(preset, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    return preset

def save_optiscaler_preset(preset: Dict[str, Any]) -> bool:
    """Save user's OptiScaler preset to persistent storage."""
    cfg_file = get_preset_config_file("optiscaler_preset.json")
    try:
        cfg_file.parent.mkdir(parents=True, exist_ok=True)
        merged = dict(DEFAULT_OPTISCALER_PRESET)
        merged.update(preset)
        # Mark the profile as migrated so load_optiscaler_preset() never overrides
        # the user's explicit choices (e.g. unlocking turned off) again.
        merged["preset_schema_version"] = 2
        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False

def get_preset_summary(preset: Optional[Dict[str, Any]] = None) -> str:
    """Format a human-readable one-line summary of current preset in Chinese."""
    if preset is None:
        preset = load_optiscaler_preset()

    fg_out = preset.get("fg_output", "xefg")
    fg_map = {
        "xefg": "Intel XeFG 官方插帧",
        "fsrfg": "AMD FSR 3.1 FG",
        "nukems": "Nukem9 桥接插帧"
    }
    fg_text = fg_map.get(fg_out, fg_out)

    if fg_out == "xefg":
        count = int(preset.get("interpolation_count", 1))
        count_map = {1: "2X 双倍", 2: "3X 三倍", 3: "4X 四倍", 4: "5X 五倍", 5: "6X 六倍"}
        mult_text = count_map.get(count, f"{count+1}X")
    else:
        mult_text = "2X 固定"

    upscaler = preset.get("dx12_upscaler", "auto")
    up_map = {
        "auto": "自动继承游戏内超分",
        "xess": "XeSS 2.0 AI 超分",
        "dlss": "NVIDIA DLSS 超分",
        "fsr31": "AMD FSR 3.1 超分"
    }
    up_text = up_map.get(upscaler, "自动继承游戏内超分")

    rcas_str = ""
    if preset.get("rcas_enabled", False):
        sharp = float(preset.get("rcas_sharpness", 0.0))
        rcas_str = f" | RCAS 锐化 {sharp:.2f}"

    dlss_p = str(preset.get("dlss_preset", "Default")).strip()
    dlss_str = f" | DLSS {dlss_p}" if dlss_p.lower() not in ["default", "0", "none", ""] else ""
    key = str(preset.get("menu_key", "Insert")).strip()
    try:
        scale = float(preset.get("menu_scale", 2.0))
    except (TypeError, ValueError):
        scale = 2.0
    scale_str = f" | 菜单 {scale:.1f}x"

    return f"{fg_text} [{mult_text}] | {up_text}{dlss_str}{rcas_str}{scale_str} | 快捷键: {key}"

# ----------------- Mode B / RenoDX ReShade Preset -----------------

def load_reshade_preset() -> Dict[str, Any]:
    """Load user's saved RenoDX ReShade preset, or return defaults if absent."""
    cfg_file = get_preset_config_file("reshade_mfg_preset.json")
    preset = dict(DEFAULT_RESHADE_PRESET)
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    preset.update(data)
        except Exception:
            pass
    # 兼容性修复与默认 DLSS 预设升级：
    # 默认采用稳定锐利且杜绝重影抖动的 DLSS 4 Transformer 模型 Preset K
    if preset.get("dlss_preset") in ("Default", "0", "", None) and not preset.get("user_customized_dlss_preset", False):
        preset["dlss_preset"] = "K"
        try:
            cfg_file.parent.mkdir(parents=True, exist_ok=True)
            with open(cfg_file, "w", encoding="utf-8") as f:
                json.dump(preset, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    return preset

def save_reshade_preset(preset: Dict[str, Any]) -> bool:
    """Save user's RenoDX ReShade preset to persistent storage."""
    cfg_file = get_preset_config_file("reshade_mfg_preset.json")
    try:
        cfg_file.parent.mkdir(parents=True, exist_ok=True)
        merged = dict(DEFAULT_RESHADE_PRESET)
        merged.update(preset)
        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False

def get_reshade_preset_summary(config: Optional[Dict[str, Any]] = None) -> str:
    """Format a human-readable one-line summary of Mode B preset in Chinese."""
    if config is None:
        config = load_reshade_preset()

    mult = int(config.get("force_multiplier", 3))
    mult_str = "游戏控制" if mult == 0 else f"{mult}X 倍率"

    features = []
    if config.get("blackwell_kernels", 1):
        features.append("Blackwell内核")
    if config.get("thin_geometry_bam", 1):
        features.append("BAM抗伪影")
    if config.get("hdr_ui_recomposition", 1):
        features.append("HDR UI重构")
    if config.get("dynamic_mfg", 0):
        features.append("动态MFG")

    feat_str = " + ".join(features) if features else "标准模式"
    return f"RenoDX MFG [{mult_str}] | {feat_str}"

def apply_preset_to_ini(ini_path: str, preset: Optional[Dict[str, Any]] = None) -> bool:
    """
    Safely inject preset parameters into OptiScaler.ini (the only v0.9.4 config file)
    while preserving comments and structure. Legacy nvngx.ini is removed by the sync.
    """
    p = Path(ini_path)
    if not p.exists():
        return False

    if preset is None:
        preset = load_optiscaler_preset()

    target_dir = p.parent
    return IniConfigManager.sync_mode_c_forward(target_dir, preset)


# ----------------- Mode D / DLSSG for SM86/SM75 Native DLSS-G Preset -----------------

DEFAULT_DLSSG_SM86_PRESET: Dict[str, Any] = {
    "enabled": 1,                      # 1=开启插帧, 0=关闭
    "engine": "DLSS",                  # "DLSS" (默认 NVIDIA 原生模型) / "XeSS" (Intel XeSS-FG 引擎)
    "max_generated_frames": 2,         # 1=最多2X, 2=最多3X(出厂默认推荐), 3=最多4X, 5=最多6X
    "optimized": 2,                    # 0=原厂内核, 1=逐位一致加速, 2=有损轻量加速(默认), 3=极速加速
    "dlssg_preset": "Auto",            # "Auto"(默认), "A", "B", "C"(FG Lite 轻量插帧)
    "super_resolution_mode": "On",      # "Off"(默认), "On"(RTX 20/30 INT8 超分加速)
    "proxy_dll": "version.dll",        # "version.dll"(默认), "winmm.dll", "dbghelp.dll", "dinput8.dll", "dxgi.dll", "d3d12.dll"
    "logging_level": 1                 # 0=关闭, 1=错误, 2=配置, 3=全量
}

def load_dlssg_sm86_preset() -> Dict[str, Any]:
    """Load user's saved DLSSG SM86 preset, or return defaults if absent."""
    cfg_file = get_preset_config_file("dlssg_sm86_preset.json")
    preset = dict(DEFAULT_DLSSG_SM86_PRESET)
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    preset.update(data)
        except Exception:
            pass
    return preset

def save_dlssg_sm86_preset(preset: Dict[str, Any]) -> bool:
    """Save user's DLSSG SM86 preset to persistent storage."""
    cfg_file = get_preset_config_file("dlssg_sm86_preset.json")
    try:
        cfg_file.parent.mkdir(parents=True, exist_ok=True)
        merged = dict(DEFAULT_DLSSG_SM86_PRESET)
        merged.update(preset)
        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False

def get_dlssg_sm86_preset_summary(config: Optional[Dict[str, Any]] = None) -> str:
    """Format a human-readable one-line summary of Mode D preset in Chinese."""
    if config is None:
        config = load_dlssg_sm86_preset()

    eng = config.get("engine", "DLSS")
    max_f = int(config.get("max_generated_frames", 3))
    mult_map = {1: "2X", 2: "3X (推荐)", 3: "4X", 5: "6X (DLSS 4.5)"}
    mult_str = mult_map.get(max_f, f"{max_f+1}X")

    opt = int(config.get("optimized", 2))
    opt_map = {0: "原厂内核", 1: "逐位一致", 2: "轻量加速(默认)", 3: "极速加速"}
    opt_str = opt_map.get(opt, f"档位{opt}")

    preset = config.get("dlssg_preset", "Auto")
    sr_mode = config.get("super_resolution_mode", "On")
    sr_str = " | INT8超分加速" if sr_mode == "On" else ""

    proxy = config.get("proxy_dll", "version.dll")

    return f"DLSSG-SM86 [{eng} 原生插帧 {mult_str}] | {opt_str} | 预设 {preset}{sr_str} | 代理: {proxy}"
