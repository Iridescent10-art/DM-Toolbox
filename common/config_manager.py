# -*- coding: utf-8 -*-
"""
Common Configuration and Cache Manager for Toolbox.
Enforces unified C-drive data storage in C:/ToolboxData:
- C:/ToolboxData/cache/{app_name}/
- C:/ToolboxData/config/{app_name}/
Decouples program files from persistent data and provides self-healing default configurations.
"""

import os
import sys
import shutil
import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

# Primary storage directory in %APPDATA%/ToolboxMaster
def resolve_toolbox_root() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        base = Path(appdata) / "ToolboxMaster"
    else:
        base = Path.home() / "AppData" / "Roaming" / "ToolboxMaster"
    return base


TOOLBOX_ROOT = resolve_toolbox_root()
CACHE_ROOT = TOOLBOX_ROOT / "cache"
CONFIG_ROOT = TOOLBOX_ROOT / "config"


def ensure_toolbox_root():
    """Ensure the top-level directory structure exists in AppData with dedicated subfolders."""
    global TOOLBOX_ROOT, CACHE_ROOT, CONFIG_ROOT
    try:
        CACHE_ROOT.mkdir(parents=True, exist_ok=True)
        CONFIG_ROOT.mkdir(parents=True, exist_ok=True)

        # Auto-create app dedicated subdirectories in both cache and config
        for app in ["app1_hardware", "app2_mfg", "app3_autohdr", "app4_dlss", "app5_jxr"]:
            (CACHE_ROOT / app).mkdir(parents=True, exist_ok=True)
            (CONFIG_ROOT / app).mkdir(parents=True, exist_ok=True)

        # Seamlessly migrate data from legacy C:/ToolboxData if it exists
        legacy = Path("C:/ToolboxData")
        if legacy.exists():
            legacy_config = legacy / "config"
            if legacy_config.exists():
                for item in legacy_config.glob("*"):
                    dest = CONFIG_ROOT / item.name
                    if not dest.exists():
                        try:
                            if item.is_dir():
                                shutil.copytree(item, dest)
                            else:
                                shutil.copy2(item, dest)
                        except Exception:
                            pass
            legacy_cache = legacy / "cache"
            if legacy_cache.exists():
                for item in legacy_cache.glob("*"):
                    dest = CACHE_ROOT / item.name
                    if not dest.exists():
                        try:
                            if item.is_dir():
                                shutil.copytree(item, dest)
                            else:
                                shutil.copy2(item, dest)
                        except Exception:
                            pass
    except Exception:
        pass


ensure_toolbox_root()


def get_app_cache_dir(app_name: str) -> Path:
    """Returns the dedicated cache directory for the given app, auto-creating if needed."""
    p = CACHE_ROOT / app_name
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_app_config_dir(app_name: str) -> Path:
    """Returns the dedicated config directory for the given app, auto-creating if needed."""
    p = CONFIG_ROOT / app_name
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_app_config_path(app_name: str, filename: str) -> Path:
    """Returns the full path to a specific config file for the given app."""
    return get_app_config_dir(app_name) / filename


THEME_CONFIG_FILE = CONFIG_ROOT / "theme.json"


def get_global_theme() -> str:
    """Reads global theme from C:/ToolboxData/config/theme.json, defaults to 'light'."""
    if THEME_CONFIG_FILE.exists():
        try:
            with open(THEME_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("theme", "light")
        except Exception:
            pass
    return "light"


def set_global_theme(theme_name: str):
    """Sets and broadcasts global theme to C:/ToolboxData/config/theme.json."""
    try:
        import time
        ensure_toolbox_root()
        data = {"theme": theme_name, "updated_at": time.time()}
        with open(THEME_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def init_app_config(
    app_name: str,
    config_filename: str,
    default_template_path: Optional[Path] = None,
    default_dict: Optional[Dict[str, Any]] = None
) -> Path:
    """
    Self-healing configuration initialization.
    If the target config does not exist in C:/ToolboxData/config/{app_name}/:
    1. Copies from default_template_path if provided and exists.
    2. Otherwise writes default_dict as JSON if provided.
    Returns the Path to the active config file.
    """
    target = get_app_config_path(app_name, config_filename)
    if not target.exists():
        if default_template_path and Path(default_template_path).exists():
            try:
                shutil.copy2(default_template_path, target)
                return target
            except Exception:
                pass

        if default_dict is not None:
            try:
                with open(target, "w", encoding="utf-8") as f:
                    json.dump(default_dict, f, indent=2, ensure_ascii=False)
                return target
            except Exception:
                pass

    return target


def get_dir_size_bytes(directory: Path) -> int:
    """Recursively computes total size of a directory in bytes."""
    if not directory.exists():
        return 0
    total = 0
    for root, _, files in os.walk(directory):
        for f in files:
            fp = Path(root) / f
            try:
                total += fp.stat().st_size
            except Exception:
                pass
    return total


def get_total_cache_size_bytes() -> int:
    """Returns total size of C:/ToolboxData in bytes."""
    return get_dir_size_bytes(TOOLBOX_ROOT)


def get_total_cache_size_mb() -> float:
    """Returns total size of %APPDATA%/ToolboxMaster in megabytes."""
    return round(get_total_cache_size_bytes() / (1024 * 1024), 2)


def reset_all_data(defaults_base_dir: Optional[Path] = None) -> Tuple[bool, str, float]:
    """
    Executes complete factory reset of %APPDATA%/ToolboxMaster:
    1. Calculates current total size before deletion.
    2. Clears cache and config trees recursively.
    3. Recreates clean cache and config directories with subfolders.
    4. Copies default templates from defaults_base_dir into config/{app_name}/.
    5. Returns (success, message, freed_mb).
    """
    freed_mb = get_total_cache_size_mb()

    try:
        # Clear Cache
        if CACHE_ROOT.exists():
            shutil.rmtree(CACHE_ROOT, ignore_errors=True)
        CACHE_ROOT.mkdir(parents=True, exist_ok=True)

        # Clear Config
        if CONFIG_ROOT.exists():
            shutil.rmtree(CONFIG_ROOT, ignore_errors=True)
        CONFIG_ROOT.mkdir(parents=True, exist_ok=True)

        # Re-create subdirectories
        for app in ["app1_hardware", "app2_mfg", "app3_autohdr", "app4_dlss", "app5_jxr"]:
            (CACHE_ROOT / app).mkdir(parents=True, exist_ok=True)
            (CONFIG_ROOT / app).mkdir(parents=True, exist_ok=True)

        # Restore from defaults/
        if defaults_base_dir and Path(defaults_base_dir).exists():
            for app_dir in Path(defaults_base_dir).iterdir():
                if app_dir.is_dir():
                    app_name = app_dir.name
                    target_app_config = get_app_config_dir(app_name)
                    target_app_cache = get_app_cache_dir(app_name)
                    for item in app_dir.iterdir():
                        if item.is_file():
                            shutil.copy2(item, target_app_config / item.name)
                        elif item.name == "embedded_components" and item.is_dir():
                            for sub_item in item.iterdir():
                                if sub_item.is_dir():
                                    shutil.copytree(sub_item, target_app_cache / sub_item.name, dirs_exist_ok=True)
                                elif sub_item.is_file():
                                    shutil.copy2(sub_item, target_app_cache / sub_item.name)

        return True, f"已成功清空 AppData 缓存并还原初始配置！释放空间: {freed_mb:.2f} MB", freed_mb
    except Exception as e:
        return False, f"重置数据时发生异常: {e}", 0.0


# ---------------------------------------------------------------------------
# True Physical Hardware Detection via App 1 (CPU/GPU配置管理工具)
# ---------------------------------------------------------------------------

def get_real_gpu_model() -> str:
    """
    Retrieve the TRUE underlying physical GPU model.
    Prioritizes reading from App 1 (CPU/GPU配置管理工具) 出厂真实硬件数据与备份快照，
    防止因注册表/WMI中已被修改伪装（如伪装成 RTX 5090/4090 等）导致 DLSS 5 或插帧补丁识别为错误架构。
    """
    # 1. Check App 1 cache backup file: GPU_Backup.cfg
    try:
        app1_cache = get_app_cache_dir("app1_hardware")
        primary_backup = app1_cache / "GPU_Backup.cfg"
        if primary_backup.exists():
            val = primary_backup.read_text(encoding="utf-8", errors="ignore").strip()
            if val and len(val) > 2 and "unknown" not in val.lower():
                return val
    except Exception:
        pass

    backup_candidates = [
        Path(os.environ.get("APPDATA", "")) / "ToolboxMaster" / "cache" / "app1_hardware" / "GPU_Backup.cfg",
        Path("C:/ToolboxData/cache/app1_hardware/GPU_Backup.cfg"),
        Path("C:/GPU_Backup.cfg"),
    ]
    for p_candidate in backup_candidates:
        if p_candidate.exists():
            try:
                val = p_candidate.read_text(encoding="utf-8", errors="ignore").strip()
                if val and len(val) > 2 and "unknown" not in val.lower():
                    return val
            except Exception:
                pass

    # 2. Check App 1 config.json -> current_hardware.detected_gpu
    config_candidates = [
        get_app_config_path("app1_hardware", "config.json"),
        Path(os.environ.get("APPDATA", "")) / "ToolboxMaster" / "config" / "app1_hardware" / "config.json",
        Path("C:/ToolboxData/config/app1_hardware/config.json"),
        Path("C:/Users/Public/Hardware_Config.json"),
    ]
    try:
        root_dir = Path(__file__).resolve().parent.parent
        config_candidates.extend([
            root_dir / "apps" / "app1_hardware" / "config.json",
            root_dir / "defaults" / "app1_hardware" / "config.json",
            Path(r"C:\Program Files\DMBOX\apps\app1_hardware\config.json"),
            Path(r"D:\AI\整合包\apps\app1_hardware\config.json"),
        ])
    except Exception:
        pass

    for p_cfg in config_candidates:
        if p_cfg.exists():
            try:
                with open(p_cfg, "r", encoding="utf-8", errors="ignore") as f:
                    data = json.load(f)
                det = data.get("current_hardware", {}).get("detected_gpu", "").strip()
                if det and len(det) > 2 and "unknown" not in det.lower():
                    return det
            except Exception:
                pass

    # 3. Check Windows Hardware Enum PCI directly (Protected by Windows Kernel, unaffected by DriverDesc modifications)
    try:
        import winreg
        enum_pci = r"SYSTEM\CurrentControlSet\Enum\PCI"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, enum_pci) as k:
            num_subkeys = winreg.QueryInfoKey(k)[0]
            for i in range(num_subkeys):
                sub = winreg.EnumKey(k, i)
                if "VEN_10DE" in sub.upper():  # NVIDIA Device
                    with winreg.OpenKey(k, sub) as dev_k:
                        for j in range(winreg.QueryInfoKey(dev_k)[0]):
                            inst = winreg.EnumKey(dev_k, j)
                            with winreg.OpenKey(dev_k, inst) as inst_k:
                                try:
                                    cls_guid, _ = winreg.QueryValueEx(inst_k, "ClassGUID")
                                    if cls_guid.lower() == "{4d36e968-e325-11ce-bfc1-08002be10318}":
                                        desc, _ = winreg.QueryValueEx(inst_k, "DeviceDesc")
                                        if desc:
                                            clean_desc = desc.split(";")[-1].strip()
                                            if clean_desc and "NVIDIA" in clean_desc.upper():
                                                return clean_desc
                                except Exception:
                                    pass
    except Exception:
        pass

    # 4. Fallback: Registry DriverDesc (if App 1 data not found and not spoofed)
    try:
        import winreg
        path = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
            for i in range(12):
                try:
                    sub = winreg.EnumKey(key, i)
                    with winreg.OpenKey(key, sub) as sk:
                        name, _ = winreg.QueryValueEx(sk, "DriverDesc")
                        s = str(name).strip()
                        if any(k in s.upper() for k in ["NVIDIA", "GEFORCE", "RTX", "GTX", "RADEON", "INTEL ARC"]):
                            return s
                except Exception:
                    pass
    except Exception:
        pass

    return "NVIDIA GeForce RTX (通用)"


def get_real_gpu_info() -> Dict[str, Any]:
    """
    Returns full GPU architecture & identification based on TRUE physical hardware.
    Determines architecture (RTX 50 vs RTX 20/30/40) for DLSS 5 and Multi-Frame Generation.
    """
    import re
    name = get_real_gpu_model()
    is_50 = bool(re.search(r"rtx\s*50\d0", name, re.IGNORECASE))
    is_40 = bool(re.search(r"rtx\s*40\d0", name, re.IGNORECASE))
    is_30 = bool(re.search(r"rtx\s*30\d0", name, re.IGNORECASE))
    is_20 = bool(re.search(r"rtx\s*20\d0", name, re.IGNORECASE))

    if is_50:
        arch = "rtx50"
        arch_desc = "RTX 50 系列专用模型 (Blackwell 架构极致算力专用)"
    elif is_40 or is_30 or is_20:
        arch = "rtx20_30_40"
        arch_desc = f"{name} (RTX 20/30/40 架构 · 推荐当前显卡)"
    else:
        arch = "rtx20_30_40"
        arch_desc = f"{name} (通用推荐模型)"

    return {
        "gpu_name": name,
        "arch": arch,
        "is_nvidia": any(k in name.upper() for k in ["NVIDIA", "GEFORCE", "RTX"]),
        "description": arch_desc,
        "is_rtx_40_or_newer": is_50 or is_40
    }
