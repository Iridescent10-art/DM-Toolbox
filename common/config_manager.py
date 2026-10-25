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
        for app in ["app1_hardware", "app2_mfg", "app3_autohdr", "app4_dlss", "app5_jxr", "app6_dlss5"]:
            (CACHE_ROOT / app).mkdir(parents=True, exist_ok=True)
            (CONFIG_ROOT / app).mkdir(parents=True, exist_ok=True)
        (CACHE_ROOT / "wallpapers").mkdir(parents=True, exist_ok=True)

        theme_file = CONFIG_ROOT / "theme.json"
        if not theme_file.exists():
            try:
                theme_file.write_text(json.dumps({"theme": "dark"}, indent=2), encoding="utf-8")
            except Exception:
                pass

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
    """Reads global theme from C:/ToolboxData/config/theme.json, defaults to 'dark'."""
    if THEME_CONFIG_FILE.exists():
        try:
            with open(THEME_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("theme", "dark")
        except Exception:
            pass
    return "dark"


def set_global_theme(theme_name: str):
    """Sets and broadcasts global theme to C:/ToolboxData/config/theme.json and subapps."""
    try:
        import time
        ensure_toolbox_root()
        data = {"theme": theme_name, "updated_at": time.time()}
        with open(THEME_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

    try:
        jxr_settings = Path(__file__).resolve().parent.parent / "apps" / "app5_jxr" / "settings.json"
        if jxr_settings.exists():
            s = json.loads(jxr_settings.read_text(encoding="utf-8"))
            s["Theme"] = "dark" if theme_name == "dark" else "light"
            jxr_settings.write_text(json.dumps(s, indent=2), encoding="utf-8")
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
        for app in ["app1_hardware", "app2_mfg", "app3_autohdr", "app4_dlss", "app5_jxr", "app6_dlss5"]:
            (CACHE_ROOT / app).mkdir(parents=True, exist_ok=True)
            (CONFIG_ROOT / app).mkdir(parents=True, exist_ok=True)
        (CACHE_ROOT / "wallpapers").mkdir(parents=True, exist_ok=True)

        # Restore from defaults/
        if defaults_base_dir and Path(defaults_base_dir).exists():
            for item in Path(defaults_base_dir).iterdir():
                if item.is_file():
                    # Root configuration files like theme.json, wallpaper_config.json
                    try:
                        shutil.copy2(item, CONFIG_ROOT / item.name)
                    except Exception:
                        pass
                elif item.is_dir():
                    app_name = item.name
                    if app_name == "wallpapers":
                        target_wallpapers_cache = CACHE_ROOT / "wallpapers"
                        target_wallpapers_cache.mkdir(parents=True, exist_ok=True)
                        for wp in item.iterdir():
                            if wp.is_file():
                                try:
                                    shutil.copy2(wp, target_wallpapers_cache / wp.name)
                                except Exception:
                                    pass
                    else:
                        target_app_config = get_app_config_dir(app_name)
                        target_app_cache = get_app_cache_dir(app_name)
                        for sub_item in item.iterdir():
                            if sub_item.is_file():
                                shutil.copy2(sub_item, target_app_config / sub_item.name)
                            elif sub_item.name == "embedded_components" and sub_item.is_dir():
                                for ec_item in sub_item.iterdir():
                                    if ec_item.is_dir():
                                        shutil.copytree(ec_item, target_app_cache / ec_item.name, dirs_exist_ok=True)
                                    elif ec_item.is_file():
                                        shutil.copy2(ec_item, target_app_cache / ec_item.name)

        return True, f"已成功清空 AppData 缓存并还原初始配置！释放空间: {freed_mb:.2f} MB", freed_mb
    except Exception as e:
        return False, f"重置数据时发生异常: {e}", 0.0


# ---------------------------------------------------------------------------
# True Physical Hardware Detection via App 1 (CPU/GPU配置管理工具)
# ---------------------------------------------------------------------------

def get_real_gpu_model() -> str:
    """
    Retrieve the TRUE underlying physical GPU model.
    Prioritizes reading physical DXGI / Windows hardware devices directly,
    ensuring mobile/laptop dual-GPU setups (AMD/Intel iGPU + NVIDIA RTX dGPU)
    correctly prioritize the discrete NVIDIA gaming GPU.
    """
    import ctypes
    from ctypes import wintypes

    # 1. Direct DXGI Hardware Enumeration (kernel driver level, prioritizes discrete gaming GPU)
    try:
        dxgi = ctypes.windll.dxgi
        class GUID(ctypes.Structure):
            _fields_ = [('Data1', wintypes.DWORD), ('Data2', wintypes.WORD), ('Data3', wintypes.WORD), ('Data4', ctypes.c_byte * 8)]
        class LUID(ctypes.Structure):
            _fields_ = [('LowPart', wintypes.DWORD), ('HighPart', wintypes.LONG)]
        class DXGI_ADAPTER_DESC1(ctypes.Structure):
            _fields_ = [
                ('Description', wintypes.WCHAR * 128),
                ('VendorId', wintypes.UINT),
                ('DeviceId', wintypes.UINT),
                ('SubSysId', wintypes.UINT),
                ('Revision', wintypes.UINT),
                ('DedicatedVideoMemory', ctypes.c_size_t),
                ('DedicatedSystemMemory', ctypes.c_size_t),
                ('SharedSystemMemory', ctypes.c_size_t),
                ('AdapterLuid', LUID),
                ('Flags', wintypes.UINT),
            ]
        IID_IDXGIFactory1 = GUID(0x770aae78, 0xf26f, 0x4dba, (ctypes.c_byte * 8)(0xa8, 0x29, 0x25, 0x3c, 0x83, 0xd1, 0xb3, 0x87))
        pFactory = ctypes.c_void_p()
        if dxgi.CreateDXGIFactory1(ctypes.byref(IID_IDXGIFactory1), ctypes.byref(pFactory)) == 0:
            vtable = ctypes.cast(ctypes.cast(pFactory, ctypes.POINTER(ctypes.c_void_p)).contents, ctypes.POINTER(ctypes.c_void_p))
            EnumAdapters1 = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p))(vtable[12])
            GetDesc1_proto = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(DXGI_ADAPTER_DESC1))
            Release = ctypes.WINFUNCTYPE(wintypes.ULONG, ctypes.c_void_p)(vtable[2])

            adapters = []
            i = 0
            while True:
                pAdapter = ctypes.c_void_p()
                if EnumAdapters1(pFactory, i, ctypes.byref(pAdapter)) != 0:
                    break
                avtable = ctypes.cast(ctypes.cast(pAdapter, ctypes.POINTER(ctypes.c_void_p)).contents, ctypes.POINTER(ctypes.c_void_p))
                desc = DXGI_ADAPTER_DESC1()
                GetDesc1_proto(avtable[10])(pAdapter, ctypes.byref(desc))
                Release(pAdapter)
                i += 1
                if desc.Flags & 2:  # DXGI_ADAPTER_FLAG_SOFTWARE
                    continue
                d_str = desc.Description.strip()
                if d_str:
                    adapters.append({
                        'desc': d_str,
                        'vendor': desc.VendorId,
                        'vram': desc.DedicatedVideoMemory
                    })
            Release(pFactory)

            if adapters:
                # On laptops with dual GPUs (e.g. AMD Radeon iGPU + NVIDIA RTX 3060 Laptop GPU),
                # always prioritize the discrete NVIDIA RTX / GeForce graphics processor:
                nvidia_adapters = [a for a in adapters if a['vendor'] == 0x10DE or any(k in a['desc'].upper() for k in ['NVIDIA', 'GEFORCE', 'RTX'])]
                if nvidia_adapters:
                    best = max(nvidia_adapters, key=lambda a: a['vram'])
                    return best['desc']
                best = max(adapters, key=lambda a: a['vram'])
                return best['desc']
    except Exception:
        pass

    # 2. Registry Display Class (prioritizing NVIDIA discrete GPU over integrated graphics)
    try:
        import winreg
        path = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
            candidates = []
            for i in range(16):
                try:
                    sub = winreg.EnumKey(key, i)
                    with winreg.OpenKey(key, sub) as sk:
                        name, _ = winreg.QueryValueEx(sk, "DriverDesc")
                        s = str(name).strip()
                        if s:
                            candidates.append(s)
                except Exception:
                    pass
            # Prioritize discrete RTX GPUs (including Laptop / Mobile)
            for c in candidates:
                if "RTX" in c.upper():
                    return c
            for c in candidates:
                if any(k in c.upper() for k in ["NVIDIA", "GEFORCE"]):
                    return c
            if candidates:
                return candidates[0]
    except Exception:
        pass

    # 3. Check Windows Hardware Enum PCI directly for NVIDIA Device
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

    # 4. Check App 1 cache backup file if real physical hardware was persisted
    try:
        app1_cache = get_app_cache_dir("app1_hardware")
        primary_backup = app1_cache / "GPU_Backup.cfg"
        if primary_backup.exists():
            val = primary_backup.read_text(encoding="utf-8", errors="ignore").strip()
            if val and len(val) > 2 and "unknown" not in val.lower():
                return val
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
    name_upper = name.upper()
    is_50 = bool(re.search(r"RTX\s*50\d0", name_upper)) or "BLACKWELL" in name_upper
    is_40 = bool(re.search(r"RTX\s*40\d0", name_upper)) or "ADA GENERATION" in name_upper
    is_30 = bool(re.search(r"RTX\s*30\d0", name_upper)) or bool(re.search(r"30\d0\s*(LAPTOP|MOBILE|MAX-Q|TI|SUPER)", name_upper))
    is_20 = bool(re.search(r"RTX\s*20\d0", name_upper)) or bool(re.search(r"20\d0\s*(LAPTOP|MOBILE|MAX-Q|TI|SUPER)", name_upper))

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
        "is_nvidia": any(k in name_upper for k in ["NVIDIA", "GEFORCE", "RTX"]),
        "description": arch_desc,
        "is_rtx_40_or_newer": is_50 or is_40
    }


# ---------------------------------------------------------------------------
# VRAM spoof detection (App 1 hardware disguise)
# ---------------------------------------------------------------------------
# Nominal board memory per physical GPU model. Used to tell whether App 1 has
# raised the *reported* VRAM far above what the card really has: games size
# their texture streaming pools from the DXGI/DirectX memory budget, so a fake
# 32 GB on a 12 GB board makes them over-commit until the driver hangs
# (DXGI_ERROR_DEVICE_HUNG / nvlddmkm event 153). Longest keys first so that
# "RTX 4070 TI" wins over "RTX 4070".
_GPU_NOMINAL_VRAM_GB: Dict[str, int] = {
    "RTX 5090": 32, "RTX 5080": 16, "RTX 5070 TI": 16, "RTX 5070": 12,
    "RTX 4090": 24, "RTX 4080": 16, "RTX 4070 TI": 12, "RTX 4070": 12,
    "RTX 4060 TI": 8, "RTX 4060": 8,
    "RTX 3090 TI": 24, "RTX 3090": 24, "RTX 3080 TI": 12, "RTX 3080": 10,
    "RTX 3070 TI": 8, "RTX 3070": 8, "RTX 3060 TI": 8, "RTX 3060": 12,
    "RTX 2080 TI": 11, "RTX 2080": 8, "RTX 2070": 8, "RTX 2060": 6,
    "GTX 1660 TI": 6, "GTX 1660": 6, "GTX 1650": 4,
    "GTX 1080 TI": 11, "GTX 1080": 8, "GTX 1070": 8, "GTX 1060": 6,
    "ARC B580": 12, "ARC B570": 10, "ARC A770": 16, "ARC A750": 8,
    "RX 7900 XTX": 24, "RX 7900 XT": 20, "RX 7800 XT": 16, "RX 7700 XT": 12,
    "RX 7600": 8, "RX 6900 XT": 16, "RX 6800 XT": 16, "RX 6800": 16,
    "RX 6700 XT": 12, "RX 6600 XT": 8,
}


def get_physical_vram_gb() -> Optional[int]:
    """Nominal VRAM of the *physical* GPU in GB, or None when the model is unknown."""
    try:
        name = get_real_gpu_model().upper()
    except Exception:
        return None
    for model in sorted(_GPU_NOMINAL_VRAM_GB, key=len, reverse=True):
        if model in name:
            return _GPU_NOMINAL_VRAM_GB[model]
    return None


def _read_app1_config() -> Dict[str, Any]:
    candidates = [
        get_app_config_path("app1_hardware", "config.json"),
        Path(os.environ.get("APPDATA", "")) / "ToolboxMaster" / "config" / "app1_hardware" / "config.json",
    ]
    try:
        root_dir = Path(__file__).resolve().parent.parent
        candidates.append(root_dir / "apps" / "app1_hardware" / "config.json")
    except Exception:
        pass
    for p in candidates:
        try:
            if p.exists():
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            continue
    return {}


def get_spoofed_vram_gb() -> Optional[int]:
    """VRAM (GB) that App 1 currently reports to games, or None when unset."""
    data = _read_app1_config()
    target = data.get("custom_target") or {}
    try:
        val = int(target.get("gpu_vram_gb"))
    except (TypeError, ValueError):
        return None
    return val if val > 0 else None


def describe_vram_overcommit(physical_gb: Optional[int], spoofed_gb: Optional[int]) -> Optional[str]:
    """
    Build a user-facing warning when the disguised VRAM exceeds the real board.

    Pure function so it stays testable without registry or hardware access.
    """
    if not physical_gb or not spoofed_gb:
        return None
    if spoofed_gb <= physical_gb:
        return None
    return (
        f"App1 当前把显存伪装为 {spoofed_gb} GB，但显卡实际只有 {physical_gb} GB。\n"
        f"游戏会按 {spoofed_gb} GB 预分配纹理/渲染目标，超过真实显存后驱动会挂起并报 "
        f"DXGI_ERROR_DEVICE_HUNG（事件 153，俗称 TDR），表现就是“玩一会儿闪退”。\n"
        f"请到【硬件配置大师】把显存改为「{physical_gb} GB (保持原始)」，"
        f"或执行「一键还原官方真实配置」后再试。"
    )


def detect_vram_overcommit() -> Optional[str]:
    """Runtime check used by the frame-generation / DLSS 5 preflight."""
    try:
        return describe_vram_overcommit(get_physical_vram_gb(), get_spoofed_vram_gb())
    except Exception:
        return None


def get_wallpaper_cache_size_mb() -> float:
    """Returns size of %APPDATA%/ToolboxMaster/cache/wallpapers/ in MB."""
    wp_dir = CACHE_ROOT / "wallpapers"
    if not wp_dir.exists():
        return 0.0
    return round(get_dir_size_bytes(wp_dir) / (1024 * 1024), 2)
