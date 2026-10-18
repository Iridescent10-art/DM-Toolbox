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
