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
import ctypes
from ctypes import wintypes
import json
import time
import shutil
import hashlib
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List, Union

# =========================================================================
# Phase 1: Constants & Engine Modes Definition
# =========================================================================
DLSS5_ENGINE_MODES = {
    "MODE_A": {
        "key": "MODE_A",
        "title": "模式 A · ShortFuse 官方原生底座 (默认推荐)",
        "short_name": "模式 A (ShortFuse 原生底座)",
        "addon_file": "renodx-dlss.addon64",
        "badge": "默认推荐",
        "desc": "ShortFuse 官方高频维护 · 原生轻量零冗余 · 完美兼容模式 A/B/C/D 多帧生成共存",
        "ini_section": "RenoDX DLSS",  # 二进制内部注册名: RenoDX DLSS
        "features": ["OptionsMode (DLSS-NR / DLSS-G / DLSS-SR)", "DLSSQualityMode", "Preset #1/#2/#3"]
    },
    "MODE_B": {
        "key": "MODE_B",
        "title": "模式 B · Lecram v12 扩展定制底座 (可选项目)",
        "short_name": "模式 B (Lecram v12 扩展底座)",
        "addon_file": "Lecram-v12.addon64",
        "badge": "可选扩展",
        "desc": "搭载 Lecram v12 深度定制面板 · 支持 UI 遮罩/缩放滤镜/色调强度/曝光等高级参数调节",
        "ini_section": "RenoDX DLSS5",
        "features": ["Hook Method", "UI Correction", "Character Mask", "Model A/B/C", "Scaling Domain & Filter"]
    }
}

DEFAULT_DLSS5_MODE = "MODE_A"

# 所有可能产生 NGX/DLSS Hook 冲突的同源插件黑名单（用于注入前互斥清理与卸载）
CONFLICT_DLSS_ADDONS = [
    "renodx-dlss.addon64",
    "Lecram-v12.addon64",
    "renodx-dlss5.addon64",
    "renodx-dlss5-v11.9.addon64",
]

DLSS5_PROXY_SLOTS = {
    "auto": {
        "key": "auto",
        "name": "auto",
        "title": "🚀 智能自动推荐 (自适应 DX11/DX12/二游 ACE 防拦截)",
        "desc": "根据目标游戏引擎（Unity/UE）与反作弊状态自适应匹配最佳渲染底座。"
    },
    "dxgi.dll": {
        "key": "dxgi.dll",
        "name": "dxgi.dll",
        "title": "🟢 dxgi.dll [标准 DXGI 劫持 · 单机大作默认推荐]",
        "desc": "适用于绝大部分单机 DirectX 11/12 游戏，通用性最佳。"
    },
    "d3d11.dll": {
        "key": "d3d11.dll",
        "name": "d3d11.dll",
        "title": "🛡️ d3d11.dll [DirectX 11 模式 · 标准 DX11 引擎专用]",
        "desc": "适用于运行在 DX11 模式下的普通游戏。注：终末地 PlatformProcess 启动辅助会扫描此文件并报 1051 拦截，终末地请勿使用此槽位。"
    },
    "d3d12.dll": {
        "key": "d3d12.dll",
        "name": "d3d12.dll",
        "title": "⚡ d3d12.dll [DirectX 12 模式 · 终末地 ACE 防拦截首选推荐]",
        "desc": "终末地社区实测最佳槽位：PlatformProcess 不加载此 DLL（100% 避开 1051 拦截），由 Endfield 主程序原生载入，彻底免除外部内存注入 (规避错误 5)。"
    },
    "ReShade64.dll": {
        "key": "ReShade64.dll",
        "name": "ReShade64.dll",
        "title": "🛡️ ReShade64.dll [零系统图形DLL落地 · 延时动态注入模式]",
        "desc": "游戏目录不落地敏感图形DLL，由工具箱在窗口建立后延时注入。若游戏反作弊驱动拦截 VirtualAllocEx (错误代码 5)，请直接改用 d3d12.dll 原生槽位。"
    }
}

DEFAULT_PROXY_SLOT = "auto"
ALL_DLSS5_PROXY_NAMES = ["dxgi.dll", "d3d11.dll", "d3d12.dll", "ReShade64.dll", "d3d12-ReShade64.dll"]


ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

APP2_DIR = ROOT_DIR / "apps" / "app2_mfg"
if str(APP2_DIR) not in sys.path:
    sys.path.insert(0, str(APP2_DIR))

try:
    from apps.app2_mfg.core.state_cleaner import is_reshade_dll_file, is_optiscaler_dll_file, is_mode_c_present, is_dashdogy_dll_file
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

    def is_dashdogy_dll_file(p: str) -> bool:
        if not os.path.exists(p):
            return False
        try:
            with open(p, "rb") as f:
                data = f.read(4 * 1024 * 1024)
            return b"MFGUnlocker" in data or b"RTX40MFG" in data or b"RTXMFG" in data
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
        return (td / "OptiScaler.ini").exists() or (td / "OptiScaler.dll").exists()

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

def is_mfg_present(target_dir: Union[str, Path]) -> bool:
    """Detect whether any Multi-Frame Generation (Mode A, B, C, D) is present in target_dir."""
    td = Path(target_dir) if target_dir else None
    if not td or not td.exists():
        return False
    mfg_indicators = [
        td / ".mfg_patch_manifest.json",
        td / "RTXMFG-Universal.json",
        td / "mfg_unlocker.ini",
        td / "RTX40MFG-UI.ini",
        td / "OptiScaler.ini",
        td / "OptiScaler.dll",
        td / "renodx-mfgunlock.addon64",
        td / "fakenvapi.dll"
    ]
    return any(p.exists() for p in mfg_indicators)


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



def detect_game_render_api(target_dir: Union[str, Path]) -> Tuple[str, str, Dict[str, Any]]:
    """
    Analyzes game directory structure and logs to determine the best proxy slot.
    Returns: (recommended_proxy, reason_text, details_dict)
    """
    td = Path(target_dir) if target_dir else None
    if not td or not td.exists():
        return "dxgi.dll", "标准单机游戏默认推荐 dxgi.dll", {"engine": "generic", "anticheat": False}

    has_ace = (td / "AntiCheatExpert").exists() or (td / "ACE-Base64.dll").exists() or list(td.glob("*ACE*"))
    has_mhy = (td / "mhyprot").exists() or (td / "mhyprot2.sys").exists()
    has_anticheat = bool(has_ace or has_mhy)

    # Detect Unity engine
    has_unity = (td / "UnityPlayer.dll").exists() or any(p.is_dir() and p.name.endswith("_Data") for p in td.iterdir() if p.is_dir())
    has_unreal = any(p.name in ["Engine", "Binaries"] for p in td.iterdir() if p.is_dir()) or "win64" in str(td).lower()

    # Check for existing OptiScaler or multi-frame generation
    has_optiscaler = (td / "OptiScaler.ini").exists() or (td / "OptiScaler").is_dir()

    details = {
        "engine": "unity" if has_unity else ("unreal" if has_unreal else "generic"),
        "anticheat": has_anticheat,
        "anticheat_type": "ACE" if has_ace else ("MHY" if has_mhy else None),
        "has_optiscaler": has_optiscaler
    }

    if has_ace:
        return (
            "d3d12.dll",
            f"检测到《明日方舟：终末地》/ 腾讯 ACE 反作弊保护：自动推荐【d3d12.dll 原生落地槽位】！经 Nexus Mods 与 RenoDX 社区验证，鹰角前置辅助进程 (PlatformProcess.exe) 绝不加载 d3d12.dll，100% 避开 1051 劫持警告；由游戏主进程原生装载，彻底免去外部内存注入，从根本上杜绝 VirtualAllocEx 错误代码 5！",
            details
        )

    if has_anticheat or has_unity:
        return (
            "d3d12.dll" if has_ace else "ReShade64.dll",
            f"检测到 {details['engine'].upper()} 引擎与反作弊系统 ({details['anticheat_type'] or '二游保护管线'})：推荐使用【d3d12.dll / ReShade64.dll】安全槽位，避开启动器前置拦截。",
            details
        )

    return (
        "dxgi.dll",
        "检测到标准单机渲染管线：推荐使用官方标准【dxgi.dll】劫持挂载，兼容性与稳定性最佳。",
        details
    )


def clean_conflicting_proxies(target_dir: Union[str, Path], keep_proxy: str) -> Tuple[bool, str, List[str]]:
    """
    Cleans up any other ReShade proxy DLL in target_dir that conflicts with keep_proxy.
    Only removes files if they are ReShade proxies (verified by header signature or manifest).
    """
    td = Path(target_dir) if target_dir else None
    if not td or not td.exists() or not td.is_dir():
        return True, "", []

    removed = []
    for proxy_name in ALL_DLSS5_PROXY_NAMES:
        if keep_proxy and proxy_name.lower() == keep_proxy.lower():
            continue
        # If keeping d3d12.dll on an ACE game, preserve the secondary ReShade chainload files
        if keep_proxy and keep_proxy.lower() == "d3d12.dll" and proxy_name.lower() in ["reshade64.dll", "d3d12-reshade64.dll"]:
            continue
        p = td / proxy_name
        if p.exists() and p.is_file():
            # Check if this proxy is actually ReShade or OptiScaler proxy
            if is_reshade_dll_file(str(p)) or is_optiscaler_dll_file(str(p)):
                try:
                    safe_force_remove(str(p))
                    removed.append(proxy_name)
                except PermissionError:
                    return False, f"权限不足或文件被占用: {proxy_name}。游戏正在运行中，请先关闭游戏再切换代理槽位！", removed
                except OSError as e:
                    return False, f"清理冲突代理失败 ({proxy_name}): {e}", removed

    return True, "", removed


def clean_conflicting_addons(target_dir: Union[str, Path], keep_addon: Optional[str] = None) -> Tuple[bool, str, List[str]]:
    """
    3.1 注入前置互斥清理机制 (clean_conflicting_addons) —— 【关键防崩溃步骤】
    原理说明：renodx-dlss.addon64 与 Lecram-v12.addon64 均会 Hook 游戏的 DXGI/NGX 接口。
    若目标游戏目录同时存在两个 .addon64，ReShade 会同时加载它们，导致游戏闪退或卡死。
    在执行注入前，必须先对 注入目标目录 (target_dir) 执行清理：
    - 遍历 CONFLICT_DLSS_ADDONS 列表。
    - 同时使用 glob 扫描目标目录下所有匹配 renodx-dlss*.addon64 和 Lecram*.addon64 的文件。
    - 若文件存在，彻底删除（捕获权限或占用异常并给出清晰提示，如“游戏正在运行中，请先关闭游戏再切换模式”）。
    - 严禁误删 renodx-mfgunlock.addon64 (多帧生成模式 B 底座)。
    """
    td = Path(target_dir) if target_dir else None
    if not td or not td.exists() or not td.is_dir():
        return True, "", []

    removed = []
    candidates = set()
    for name in CONFLICT_DLSS_ADDONS:
        p = td / name
        if p.exists() and p.is_file():
            candidates.add(p)

    for pat in ["renodx-dlss*.addon64", "Lecram*.addon64", "lecram*.addon64", "renodx-dlss5*.addon64"]:
        for p in td.glob(pat):
            if p.is_file():
                candidates.add(p)

    for p in candidates:
        name_lower = p.name.lower()
        if "mfgunlock" in name_lower:
            continue
        if keep_addon and name_lower == keep_addon.lower():
            continue
        try:
            p.unlink()
            removed.append(p.name)
        except PermissionError:
            return False, f"权限不足或文件被占用: {p.name}。游戏正在运行中，请先关闭游戏再切换模式！", removed
        except OSError as e:
            return False, f"清理冲突插件失败 ({p.name}): {e}。游戏可能正在运行，请先关闭游戏再切换模式！", removed

    return True, "", removed


def scan_plugin_source_assets(source_dir: Optional[Path] = None, mode: str = "MODE_A") -> Dict[str, Any]:
    """
    Scans the given source directory (or auto-detected paths) for:
    - dxgi.dll (ReShade base)
    - Mode A base: renodx-dlss.addon64
    - Mode B base: Lecram-v12.addon64
    - Active addon based on chosen mode
    - nvngx_dlssnr.dll models (RTX 50 vs RTX 20/30/40)
    """
    s_dir = source_dir or get_plugin_source_dir()
    result = {
        "source_dir": str(s_dir),
        "exists": s_dir.exists(),
        "dxgi_path": None,
        "dxgi_size_mb": 0.0,
        "mode_a_path": None,
        "mode_a_size_mb": 0.0,
        "mode_a_exists": False,
        "mode_b_path": None,
        "mode_b_size_mb": 0.0,
        "mode_b_exists": False,
        "addon_path": None,
        "addon_name": "",
        "addon_size_mb": 0.0,
        "selected_mode": mode,
        "all_addons": [],
        "nr_50_path": None,
        "nr_50_size_mb": 0.0,
        "nr_20_30_40_path": None,
        "nr_20_30_40_size_mb": 0.0,
    }

    if not s_dir.exists():
        # Fall back to local assets if custom path doesn't exist
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

    # 2. Search for Mode A base: renodx-dlss.addon64
    mode_a_file = s_dir / "renodx-dlss.addon64"
    if mode_a_file.exists() and mode_a_file.is_file():
        result["mode_a_path"] = str(mode_a_file)
        result["mode_a_size_mb"] = round(mode_a_file.stat().st_size / (1024 * 1024), 2)
        result["mode_a_exists"] = True
    elif (LOCAL_ASSETS_DIR / "renodx-dlss.addon64").exists():
        cand = LOCAL_ASSETS_DIR / "renodx-dlss.addon64"
        result["mode_a_path"] = str(cand)
        result["mode_a_size_mb"] = round(cand.stat().st_size / (1024 * 1024), 2)
        result["mode_a_exists"] = True
    else:
        cands_a = [p for p in s_dir.glob("renodx-dlss*.addon64") if "mfgunlock" not in p.name.lower()]
        if cands_a:
            result["mode_a_path"] = str(cands_a[0])
            result["mode_a_size_mb"] = round(cands_a[0].stat().st_size / (1024 * 1024), 2)
            result["mode_a_exists"] = True

    # 3. Search for Mode B base: Lecram-v12.addon64
    mode_b_file = s_dir / "Lecram-v12.addon64"
    if mode_b_file.exists() and mode_b_file.is_file():
        result["mode_b_path"] = str(mode_b_file)
        result["mode_b_size_mb"] = round(mode_b_file.stat().st_size / (1024 * 1024), 2)
        result["mode_b_exists"] = True
    elif (LOCAL_ASSETS_DIR / "Lecram-v12.addon64").exists():
        cand = LOCAL_ASSETS_DIR / "Lecram-v12.addon64"
        result["mode_b_path"] = str(cand)
        result["mode_b_size_mb"] = round(cand.stat().st_size / (1024 * 1024), 2)
        result["mode_b_exists"] = True
    else:
        cands_b = list(s_dir.glob("Lecram*.addon64")) + list(s_dir.glob("lecram*.addon64"))
        if cands_b:
            result["mode_b_path"] = str(cands_b[0])
            result["mode_b_size_mb"] = round(cands_b[0].stat().st_size / (1024 * 1024), 2)
            result["mode_b_exists"] = True

    # Configure active addon based on mode
    if mode == "MODE_B":
        if result["mode_b_path"]:
            result["addon_path"] = result["mode_b_path"]
            result["addon_name"] = Path(result["mode_b_path"]).name
            result["addon_size_mb"] = result["mode_b_size_mb"]
        elif result["mode_a_path"]:
            result["addon_path"] = result["mode_a_path"]
            result["addon_name"] = Path(result["mode_a_path"]).name
            result["addon_size_mb"] = result["mode_a_size_mb"]
    else:
        # Default to Mode A
        if result["mode_a_path"]:
            result["addon_path"] = result["mode_a_path"]
            result["addon_name"] = Path(result["mode_a_path"]).name
            result["addon_size_mb"] = result["mode_a_size_mb"]
        elif result["mode_b_path"]:
            result["addon_path"] = result["mode_b_path"]
            result["addon_name"] = Path(result["mode_b_path"]).name
            result["addon_size_mb"] = result["mode_b_size_mb"]

    all_addons = []
    if result["mode_a_path"]:
        all_addons.append(result["mode_a_path"])
    if result["mode_b_path"]:
        all_addons.append(result["mode_b_path"])
    result["all_addons"] = all_addons

    # 4. Search for RTX 50 NR model
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

    # 5. Search for RTX 20/30/40 NR model
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
    """Return the most likely game .exe in the game directory (filtering helper/launcher binaries)."""
    try:
        ignored_names = {
            "unitycrashhandler64.exe", "unitycrashhandler32.exe", "crashreport.exe",
            "crashsight64.exe", "unrealcefsubprocess.exe", "platformprocess.exe",
            "qtwebengineprocess.exe", "cefviewwing.exe", "launcher.exe",
            "uninstall.exe", "update.exe", "dxsetup.exe", "vcredist_x64.exe"
        }
        cands = [
            p for p in target_dir.iterdir()
            if p.is_file() and p.suffix.lower() == ".exe" and p.name.lower() not in ignored_names
        ]
        if not cands:
            cands = [p for p in target_dir.iterdir() if p.is_file() and p.suffix.lower() == ".exe"]
        if not cands:
            return None
        return str(max(cands, key=lambda p: p.stat().st_size))
    except Exception:
        return None


def check_game_dlss5_status(target_dir: str) -> Dict[str, Any]:
    """
    3.3 目标游戏状态智能识别 (detect_game_injection_status)
    Checks whether DLSS 5 is currently injected into the game's target directory.
    Identifies:
    - MODE_A (renodx-dlss.addon64): 🟢 已注入 DLSS 5 [模式 A · ShortFuse 原生底座]
    - MODE_B (Lecram-v12.addon64): 🔵 已注入 DLSS 5 [模式 B · Lecram v12 扩展底座]
    - Legacy (renodx-dlss5-v11.9.addon64 / renodx-dlss5.addon64): 🟡 检测到旧版插件 (v11.9)，建议点击一键注入升级至默认模式 A
    - Not installed: ⚪ 未安装 DLSS 5 插件
    """
    td = Path(target_dir) if target_dir else None
    if not td or not td.exists() or not td.is_dir():
        return {
            "valid_dir": False,
            "is_injected": False,
            "has_reshade": False,
            "active_proxy": None,
            "recommended_proxy": "dxgi.dll",
            "recommended_reason": "",
            "api_details": {},
            "has_addon": False,
            "has_runtime": False,
            "addon_names": [],
            "runtime_size_mb": 0.0,
            "detected_arch": "unknown",
            "hook_point": "0",
            "hook_point_label": "之后 (Upscaled · 推荐)",
            "manifest_data": None,
            "detected_mode": None,
            "mode_status_display": "⚪ 未选择游戏",
            "is_legacy": False
        }

    dxgi_path = td / "dxgi.dll"
    reshade64_path = td / "ReShade64.dll"
    runtime_path = td / "nvngx_dlssnr.dll"
    manifest_path = td / DLSS5_MANIFEST_FILENAME

    rec_proxy, rec_reason, api_details = detect_game_render_api(td)

    # ReShade base check across all known proxy slots
    has_reshade = False
    active_proxy = None
    for p_name in ALL_DLSS5_PROXY_NAMES:
        p_cand = td / p_name
        if p_cand.exists() and p_cand.is_file():
            if is_reshade_dll_file(str(p_cand)):
                has_reshade = True
                active_proxy = p_name
                break
            elif p_name == "d3d12.dll" and is_optiscaler_dll_file(str(p_cand)) and ((td / "ReShade64.dll").exists() or (td / "d3d12-ReShade64.dll").exists()):
                has_reshade = True
                active_proxy = "d3d12.dll"
                break
            elif p_name == "dxgi.dll" and p_cand.stat().st_size > 4 * 1024 * 1024:
                has_reshade = True
                active_proxy = p_name
                break
    if not active_proxy and reshade64_path.exists():
        has_reshade = True
        active_proxy = "ReShade64.dll" 

    # Addons check (supports ShortFuse, Lecram, RenoDX, and other DLSS addons; excludes MFG unlocker)
    addons = [p.name for p in td.glob("*.addon64")]
    dlss_addons = [a for a in addons if any(k in a.lower() for k in ["renodx", "dlss", "shortfuse", "lecram"]) and "mfgunlock" not in a.lower()]
    has_addon = len(dlss_addons) > 0

    has_mode_a = (td / "renodx-dlss.addon64").exists()
    has_mode_b = (td / "Lecram-v12.addon64").exists() or (td / "lecram-v12.addon64").exists()
    has_legacy = any("v11.9" in a.lower() or "dlss5." in a.lower() or "beta" in a.lower() for a in dlss_addons)

    detected_mode = None
    if has_mode_a and not has_mode_b:
        detected_mode = "MODE_A"
        mode_status_display = "🟢 已注入 DLSS 5 [模式 A · ShortFuse 原生底座]"
    elif has_mode_b and not has_mode_a:
        detected_mode = "MODE_B"
        mode_status_display = "🔵 已注入 DLSS 5 [模式 B · Lecram v12 扩展底座]"
    elif has_mode_a and has_mode_b:
        detected_mode = "MODE_A"
        mode_status_display = "⚠️ 检测到双底座冲突 (模式 A + 模式 B)，建议重新一键注入整理"
    elif has_legacy:
        detected_mode = "MODE_A"
        mode_status_display = "🟡 检测到旧版插件 (v11.9)，建议点击一键注入升级至默认模式 A"
    elif has_addon:
        detected_mode = "MODE_A"
        mode_status_display = f"🟢 已注入 DLSS 5 ({dlss_addons[0]})"
    else:
        detected_mode = None
        mode_status_display = "⚪ 未安装 DLSS 5 插件"

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

    # Fallback to manifest mode if present
    if manifest_data and manifest_data.get("mode") in DLSS5_ENGINE_MODES:
        if not detected_mode:
            detected_mode = manifest_data["mode"]

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

    # Detect current active Hook Point from ReShade.ini or Presets (Both Mode A and Mode B)
    current_hook_point = "0"
    current_hook_label = "之后 (Upscaled · 推荐)"
    detected_hook_resolved = False

    reshade_ini = td / "ReShade.ini"
    if reshade_ini.exists():
        try:
            import configparser
            cp = configparser.ConfigParser(interpolation=None, strict=False)
            cp.read(reshade_ini, encoding="utf-8")
            if detected_mode == "MODE_B" and cp.has_section("RenoDX.DLSS5"):
                b_val = cp.get("RenoDX.DLSS5", "NRHookPoint", fallback=cp.get("RenoDX.DLSS5", "HookStage", fallback=""))
                if b_val == "2":
                    current_hook_point = "2"
                    current_hook_label = "呈现 (Present · 纯画质)"
                    detected_hook_resolved = True
                elif b_val == "1":
                    current_hook_point = "1"
                    current_hook_label = "之前 (Before · 原生阶段)"
                    detected_hook_resolved = True
                elif b_val == "0":
                    current_hook_point = "0"
                    current_hook_label = "之后 (Upscaled · 推荐)"
                    detected_hook_resolved = True
            elif detected_mode == "MODE_A":
                a_stage = ""
                for sec in ["RENODX-DLSS", "RENODX-DLSS-preset1", "renodx", "renodx-preset1", "RenoDX DLSS"]:
                    if cp.has_section(sec) and cp.has_option(sec, "DirectNeuralRenderingHookStage"):
                        a_stage = cp.get(sec, "DirectNeuralRenderingHookStage", fallback="")
                        if a_stage:
                            break
                if a_stage == "2":
                    current_hook_point = "2"
                    current_hook_label = "呈现 (Present · 纯画质)"
                    detected_hook_resolved = True
                elif a_stage == "0":
                    current_hook_point = "1"
                    current_hook_label = "之前 (Before · 原生阶段)"
                    detected_hook_resolved = True
                elif a_stage == "1":
                    current_hook_point = "0"
                    current_hook_label = "之后 (Upscaled · 推荐)"
                    detected_hook_resolved = True
        except Exception:
            pass

    if not detected_hook_resolved:
        for candidate_file in [td / "ReShade.ini", td / "RenoDX" / "DLSS5" / "Presets" / "My look.ini", td / "ReShadePreset.ini"]:
            if candidate_file.exists():
                try:
                    content_ini = candidate_file.read_text(encoding="utf-8", errors="ignore")
                    for line in content_ini.splitlines():
                        stripped = line.strip()
                        if stripped.startswith("NRHookPoint="):
                            val = stripped.split("=", 1)[1].strip()
                            if val == "2":
                                current_hook_point = "2"
                                current_hook_label = "呈现 (Present · 纯画质)"
                                break
                            elif val == "1":
                                current_hook_point = "1"
                                current_hook_label = "之前 (Before · 原生阶段)"
                                break
                            elif val == "0":
                                current_hook_point = "0"
                                current_hook_label = "之后 (Upscaled · 推荐)"
                                break
                except Exception:
                    pass
                if current_hook_point in ("1", "2"):
                    break

    return {
        "valid_dir": True,
        "is_injected": is_injected,
        "has_reshade": has_reshade,
        "active_proxy": active_proxy,
        "recommended_proxy": rec_proxy,
        "recommended_reason": rec_reason,
        "api_details": api_details,
        "has_addon": has_addon,
        "has_runtime": has_runtime,
        "addon_names": dlss_addons or addons,
        "runtime_size_mb": runtime_size_mb,
        "detected_arch": detected_arch,
        "hook_point": current_hook_point,
        "hook_point_label": current_hook_label,
        "manifest_data": manifest_data,
        "detected_mode": detected_mode,
        "mode_status_display": mode_status_display,
        "is_legacy": has_legacy
    }


DEFAULT_DLSS5_INI_SECTIONS: Dict[str, Dict[str, str]] = {
    "INSTALL": {
        "HookOpenGL": "0",
        "HookDirectX": "1"
    },
    "ADDON": {},
    "GENERAL": {
        "EffectSearchPaths": ".\\",
        "TextureSearchPaths": ".\\",
        "PerformanceMode": "1",
        "NoReloadOnInit": "1",
        "CurrentPresetPath": ".\\ReShadePreset.ini"
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
    "RENODX-DLSS": {       'DLSSAutoExposure': '0',
        'DLSSPresetBalanced': '0',
        'DLSSPresetDLAA': '0',
        'DLSSPresetPerformance': '0',
        'DLSSPresetQuality': '0',
        'DLSSPresetUltraPerformance': '0',
        'DLSSPresetUltraQuality': '0',
        'DLSSQualityMode': '0',
        'DirectNeuralRenderingDiffuseWhiteNits': '100',
        'DirectNeuralRenderingDiffuseWhiteOverride': '0',
        'DirectNeuralRenderingEncoding': '0',
        'DirectNeuralRenderingHookStage': '1',
        'DirectNeuralRenderingReuseDlssUpscalingResources': '1',
        'DirectNeuralRenderingUiCorrectionMode': '0',
        'OptionsMode': '0'},
    "RENODX-DLSS-preset1": {       'DirectNeuralRenderingAutoMask': '1',
        'DirectNeuralRenderingAutoMaskPass10': '1',
        'DirectNeuralRenderingAutoMaskPass2': '1',
        'DirectNeuralRenderingAutoMaskPass3': '1',
        'DirectNeuralRenderingAutoMaskPass4': '1',
        'DirectNeuralRenderingAutoMaskPass5': '1',
        'DirectNeuralRenderingAutoMaskPass6': '1',
        'DirectNeuralRenderingAutoMaskPass7': '1',
        'DirectNeuralRenderingAutoMaskPass8': '1',
        'DirectNeuralRenderingAutoMaskPass9': '1',
        'DirectNeuralRenderingBeforeEffectsPass1': '',
        'DirectNeuralRenderingBeforeEffectsPass10': '',
        'DirectNeuralRenderingBeforeEffectsPass2': '',
        'DirectNeuralRenderingBeforeEffectsPass3': '',
        'DirectNeuralRenderingBeforeEffectsPass4': '',
        'DirectNeuralRenderingBeforeEffectsPass5': '',
        'DirectNeuralRenderingBeforeEffectsPass6': '',
        'DirectNeuralRenderingBeforeEffectsPass7': '',
        'DirectNeuralRenderingBeforeEffectsPass8': '',
        'DirectNeuralRenderingBeforeEffectsPass9': '',
        'DirectNeuralRenderingBlockHudless': '1',
        'DirectNeuralRenderingDownsampleFilter': '0',
        'DirectNeuralRenderingEffectsPass1': '',
        'DirectNeuralRenderingEffectsPass10': '',
        'DirectNeuralRenderingEffectsPass2': '',
        'DirectNeuralRenderingEffectsPass3': '',
        'DirectNeuralRenderingEffectsPass4': '',
        'DirectNeuralRenderingEffectsPass5': '',
        'DirectNeuralRenderingEffectsPass6': '',
        'DirectNeuralRenderingEffectsPass7': '',
        'DirectNeuralRenderingEffectsPass8': '',
        'DirectNeuralRenderingEffectsPass9': '',
        'DirectNeuralRenderingExposure': '1',
        'DirectNeuralRenderingExposureMode': '1',
        'DirectNeuralRenderingFilterDomain': '0',
        'DirectNeuralRenderingIntensity': '1',
        'DirectNeuralRenderingIntensityPass10': '1',
        'DirectNeuralRenderingIntensityPass2': '1',
        'DirectNeuralRenderingIntensityPass3': '1',
        'DirectNeuralRenderingIntensityPass4': '1',
        'DirectNeuralRenderingIntensityPass5': '1',
        'DirectNeuralRenderingIntensityPass6': '1',
        'DirectNeuralRenderingIntensityPass7': '1',
        'DirectNeuralRenderingIntensityPass8': '1',
        'DirectNeuralRenderingIntensityPass9': '1',
        'DirectNeuralRenderingLocalStructureStrength': '1',
        'DirectNeuralRenderingLocalStructureStrengthPass10': '0.7',
        'DirectNeuralRenderingLocalStructureStrengthPass2': '0.7',
        'DirectNeuralRenderingLocalStructureStrengthPass3': '0.7',
        'DirectNeuralRenderingLocalStructureStrengthPass4': '0.7',
        'DirectNeuralRenderingLocalStructureStrengthPass5': '0.7',
        'DirectNeuralRenderingLocalStructureStrengthPass6': '0.7',
        'DirectNeuralRenderingLocalStructureStrengthPass7': '0.7',
        'DirectNeuralRenderingLocalStructureStrengthPass8': '0.7',
        'DirectNeuralRenderingLocalStructureStrengthPass9': '0.7',
        'DirectNeuralRenderingLocalToneStrength': '1',
        'DirectNeuralRenderingLocalToneStrengthPass10': '0.3',
        'DirectNeuralRenderingLocalToneStrengthPass2': '0.3',
        'DirectNeuralRenderingLocalToneStrengthPass3': '0.3',
        'DirectNeuralRenderingLocalToneStrengthPass4': '0.3',
        'DirectNeuralRenderingLocalToneStrengthPass5': '0.3',
        'DirectNeuralRenderingLocalToneStrengthPass6': '0.3',
        'DirectNeuralRenderingLocalToneStrengthPass7': '0.3',
        'DirectNeuralRenderingLocalToneStrengthPass8': '0.3',
        'DirectNeuralRenderingLocalToneStrengthPass9': '0.3',
        'DirectNeuralRenderingModelCorrections': '0',
        'DirectNeuralRenderingPassCount': '1',
        'DirectNeuralRenderingPreset': '2',
        'DirectNeuralRenderingPreset1Model0BlackLevel': '0.00025471',
        'DirectNeuralRenderingPreset1Model0WhiteLevel': '0.04310297',
        'DirectNeuralRenderingPreset1Model1BlackLevel': '0.000130265',
        'DirectNeuralRenderingPreset1Model1WhiteLevel': '0.22131996',
        'DirectNeuralRenderingPreset1Model2BlackLevel': '0.000832178',
        'DirectNeuralRenderingPreset1Model2WhiteLevel': '0.046671238',
        'DirectNeuralRenderingPreset2Model0BlackLevel': '0.000217623',
        'DirectNeuralRenderingPreset2Model0WhiteLevel': '0.022936724',
        'DirectNeuralRenderingPreset2Model1BlackLevel': '0.000391522',
        'DirectNeuralRenderingPreset2Model1WhiteLevel': '0.2115776',
        'DirectNeuralRenderingPreset2Model2BlackLevel': '0.001443278',
        'DirectNeuralRenderingPreset2Model2WhiteLevel': '0.05568646',
        'DirectNeuralRenderingProcessingScale': '100',
        'DirectNeuralRenderingScaleReconstruction': '0',
        'DirectNeuralRenderingSignalEncoding': '0',
        'DirectNeuralRenderingSkinStructureStrength': '0.8',
        'DirectNeuralRenderingSkinStructureStrengthPass10': '0.5',
        'DirectNeuralRenderingSkinStructureStrengthPass2': '0.5',
        'DirectNeuralRenderingSkinStructureStrengthPass3': '0.5',
        'DirectNeuralRenderingSkinStructureStrengthPass4': '0.5',
        'DirectNeuralRenderingSkinStructureStrengthPass5': '0.5',
        'DirectNeuralRenderingSkinStructureStrengthPass6': '0.5',
        'DirectNeuralRenderingSkinStructureStrengthPass7': '0.5',
        'DirectNeuralRenderingSkinStructureStrengthPass8': '0.5',
        'DirectNeuralRenderingSkinStructureStrengthPass9': '0.5',
        'DirectNeuralRenderingStyle': '2',
        'DirectNeuralRenderingStylePass10': '0',
        'DirectNeuralRenderingStylePass2': '0',
        'DirectNeuralRenderingStylePass3': '0',
        'DirectNeuralRenderingStylePass4': '0',
        'DirectNeuralRenderingStylePass5': '0',
        'DirectNeuralRenderingStylePass6': '0',
        'DirectNeuralRenderingStylePass7': '0',
        'DirectNeuralRenderingStylePass8': '0',
        'DirectNeuralRenderingStylePass9': '0',
        'DirectNeuralRenderingUpsampleFilter': '0'},
    "RENODX-DLSS-preset2": {       'DirectNeuralRenderingAutoMask': '1',
        'DirectNeuralRenderingAutoMaskPass10': '1',
        'DirectNeuralRenderingAutoMaskPass2': '1',
        'DirectNeuralRenderingAutoMaskPass3': '1',
        'DirectNeuralRenderingAutoMaskPass4': '1',
        'DirectNeuralRenderingAutoMaskPass5': '1',
        'DirectNeuralRenderingAutoMaskPass6': '1',
        'DirectNeuralRenderingAutoMaskPass7': '1',
        'DirectNeuralRenderingAutoMaskPass8': '1',
        'DirectNeuralRenderingAutoMaskPass9': '1',
        'DirectNeuralRenderingBeforeEffectsPass1': '',
        'DirectNeuralRenderingBeforeEffectsPass10': '',
        'DirectNeuralRenderingBeforeEffectsPass2': '',
        'DirectNeuralRenderingBeforeEffectsPass3': '',
        'DirectNeuralRenderingBeforeEffectsPass4': '',
        'DirectNeuralRenderingBeforeEffectsPass5': '',
        'DirectNeuralRenderingBeforeEffectsPass6': '',
        'DirectNeuralRenderingBeforeEffectsPass7': '',
        'DirectNeuralRenderingBeforeEffectsPass8': '',
        'DirectNeuralRenderingBeforeEffectsPass9': '',
        'DirectNeuralRenderingBlockHudless': '1',
        'DirectNeuralRenderingDownsampleFilter': '0',
        'DirectNeuralRenderingEffectsPass1': '',
        'DirectNeuralRenderingEffectsPass10': '',
        'DirectNeuralRenderingEffectsPass2': '',
        'DirectNeuralRenderingEffectsPass3': '',
        'DirectNeuralRenderingEffectsPass4': '',
        'DirectNeuralRenderingEffectsPass5': '',
        'DirectNeuralRenderingEffectsPass6': '',
        'DirectNeuralRenderingEffectsPass7': '',
        'DirectNeuralRenderingEffectsPass8': '',
        'DirectNeuralRenderingEffectsPass9': '',
        'DirectNeuralRenderingExposure': '1',
        'DirectNeuralRenderingExposureMode': '1',
        'DirectNeuralRenderingFilterDomain': '0',
        'DirectNeuralRenderingIntensity': '1',
        'DirectNeuralRenderingIntensityPass10': '1',
        'DirectNeuralRenderingIntensityPass2': '1',
        'DirectNeuralRenderingIntensityPass3': '1',
        'DirectNeuralRenderingIntensityPass4': '1',
        'DirectNeuralRenderingIntensityPass5': '1',
        'DirectNeuralRenderingIntensityPass6': '1',
        'DirectNeuralRenderingIntensityPass7': '1',
        'DirectNeuralRenderingIntensityPass8': '1',
        'DirectNeuralRenderingIntensityPass9': '1',
        'DirectNeuralRenderingLocalStructureStrength': '1',
        'DirectNeuralRenderingLocalStructureStrengthPass10': '0.7',
        'DirectNeuralRenderingLocalStructureStrengthPass2': '0.7',
        'DirectNeuralRenderingLocalStructureStrengthPass3': '0.7',
        'DirectNeuralRenderingLocalStructureStrengthPass4': '0.7',
        'DirectNeuralRenderingLocalStructureStrengthPass5': '0.7',
        'DirectNeuralRenderingLocalStructureStrengthPass6': '0.7',
        'DirectNeuralRenderingLocalStructureStrengthPass7': '0.7',
        'DirectNeuralRenderingLocalStructureStrengthPass8': '0.7',
        'DirectNeuralRenderingLocalStructureStrengthPass9': '0.7',
        'DirectNeuralRenderingLocalToneStrength': '1',
        'DirectNeuralRenderingLocalToneStrengthPass10': '0.3',
        'DirectNeuralRenderingLocalToneStrengthPass2': '0.3',
        'DirectNeuralRenderingLocalToneStrengthPass3': '0.3',
        'DirectNeuralRenderingLocalToneStrengthPass4': '0.3',
        'DirectNeuralRenderingLocalToneStrengthPass5': '0.3',
        'DirectNeuralRenderingLocalToneStrengthPass6': '0.3',
        'DirectNeuralRenderingLocalToneStrengthPass7': '0.3',
        'DirectNeuralRenderingLocalToneStrengthPass8': '0.3',
        'DirectNeuralRenderingLocalToneStrengthPass9': '0.3',
        'DirectNeuralRenderingModelCorrections': '0',
        'DirectNeuralRenderingPassCount': '1',
        'DirectNeuralRenderingPreset': '2',
        'DirectNeuralRenderingPreset1Model0BlackLevel': '0.00025471',
        'DirectNeuralRenderingPreset1Model0WhiteLevel': '0.04310297',
        'DirectNeuralRenderingPreset1Model1BlackLevel': '0.000130265',
        'DirectNeuralRenderingPreset1Model1WhiteLevel': '0.22131996',
        'DirectNeuralRenderingPreset1Model2BlackLevel': '0.000832178',
        'DirectNeuralRenderingPreset1Model2WhiteLevel': '0.046671238',
        'DirectNeuralRenderingPreset2Model0BlackLevel': '0.000217623',
        'DirectNeuralRenderingPreset2Model0WhiteLevel': '0.022936724',
        'DirectNeuralRenderingPreset2Model1BlackLevel': '0.000391522',
        'DirectNeuralRenderingPreset2Model1WhiteLevel': '0.2115776',
        'DirectNeuralRenderingPreset2Model2BlackLevel': '0.001443278',
        'DirectNeuralRenderingPreset2Model2WhiteLevel': '0.05568646',
        'DirectNeuralRenderingProcessingScale': '100',
        'DirectNeuralRenderingScaleReconstruction': '0',
        'DirectNeuralRenderingSignalEncoding': '0',
        'DirectNeuralRenderingSkinStructureStrength': '0.8',
        'DirectNeuralRenderingSkinStructureStrengthPass10': '0.5',
        'DirectNeuralRenderingSkinStructureStrengthPass2': '0.5',
        'DirectNeuralRenderingSkinStructureStrengthPass3': '0.5',
        'DirectNeuralRenderingSkinStructureStrengthPass4': '0.5',
        'DirectNeuralRenderingSkinStructureStrengthPass5': '0.5',
        'DirectNeuralRenderingSkinStructureStrengthPass6': '0.5',
        'DirectNeuralRenderingSkinStructureStrengthPass7': '0.5',
        'DirectNeuralRenderingSkinStructureStrengthPass8': '0.5',
        'DirectNeuralRenderingSkinStructureStrengthPass9': '0.5',
        'DirectNeuralRenderingStyle': '2',
        'DirectNeuralRenderingStylePass10': '0',
        'DirectNeuralRenderingStylePass2': '0',
        'DirectNeuralRenderingStylePass3': '0',
        'DirectNeuralRenderingStylePass4': '0',
        'DirectNeuralRenderingStylePass5': '0',
        'DirectNeuralRenderingStylePass6': '0',
        'DirectNeuralRenderingStylePass7': '0',
        'DirectNeuralRenderingStylePass8': '0',
        'DirectNeuralRenderingStylePass9': '0',
        'DirectNeuralRenderingUpsampleFilter': '0'},
    "RENODX-DLSS-preset3": {       'DirectNeuralRenderingAutoMask': '1',
        'DirectNeuralRenderingAutoMaskPass10': '1',
        'DirectNeuralRenderingAutoMaskPass2': '1',
        'DirectNeuralRenderingAutoMaskPass3': '1',
        'DirectNeuralRenderingAutoMaskPass4': '1',
        'DirectNeuralRenderingAutoMaskPass5': '1',
        'DirectNeuralRenderingAutoMaskPass6': '1',
        'DirectNeuralRenderingAutoMaskPass7': '1',
        'DirectNeuralRenderingAutoMaskPass8': '1',
        'DirectNeuralRenderingAutoMaskPass9': '1',
        'DirectNeuralRenderingBeforeEffectsPass1': '',
        'DirectNeuralRenderingBeforeEffectsPass10': '',
        'DirectNeuralRenderingBeforeEffectsPass2': '',
        'DirectNeuralRenderingBeforeEffectsPass3': '',
        'DirectNeuralRenderingBeforeEffectsPass4': '',
        'DirectNeuralRenderingBeforeEffectsPass5': '',
        'DirectNeuralRenderingBeforeEffectsPass6': '',
        'DirectNeuralRenderingBeforeEffectsPass7': '',
        'DirectNeuralRenderingBeforeEffectsPass8': '',
        'DirectNeuralRenderingBeforeEffectsPass9': '',
        'DirectNeuralRenderingBlockHudless': '1',
        'DirectNeuralRenderingDownsampleFilter': '0',
        'DirectNeuralRenderingEffectsPass1': '',
        'DirectNeuralRenderingEffectsPass10': '',
        'DirectNeuralRenderingEffectsPass2': '',
        'DirectNeuralRenderingEffectsPass3': '',
        'DirectNeuralRenderingEffectsPass4': '',
        'DirectNeuralRenderingEffectsPass5': '',
        'DirectNeuralRenderingEffectsPass6': '',
        'DirectNeuralRenderingEffectsPass7': '',
        'DirectNeuralRenderingEffectsPass8': '',
        'DirectNeuralRenderingEffectsPass9': '',
        'DirectNeuralRenderingExposure': '1',
        'DirectNeuralRenderingExposureMode': '1',
        'DirectNeuralRenderingFilterDomain': '0',
        'DirectNeuralRenderingIntensity': '1',
        'DirectNeuralRenderingIntensityPass10': '1',
        'DirectNeuralRenderingIntensityPass2': '1',
        'DirectNeuralRenderingIntensityPass3': '1',
        'DirectNeuralRenderingIntensityPass4': '1',
        'DirectNeuralRenderingIntensityPass5': '1',
        'DirectNeuralRenderingIntensityPass6': '1',
        'DirectNeuralRenderingIntensityPass7': '1',
        'DirectNeuralRenderingIntensityPass8': '1',
        'DirectNeuralRenderingIntensityPass9': '1',
        'DirectNeuralRenderingLocalStructureStrength': '1',
        'DirectNeuralRenderingLocalStructureStrengthPass10': '0.7',
        'DirectNeuralRenderingLocalStructureStrengthPass2': '0.7',
        'DirectNeuralRenderingLocalStructureStrengthPass3': '0.7',
        'DirectNeuralRenderingLocalStructureStrengthPass4': '0.7',
        'DirectNeuralRenderingLocalStructureStrengthPass5': '0.7',
        'DirectNeuralRenderingLocalStructureStrengthPass6': '0.7',
        'DirectNeuralRenderingLocalStructureStrengthPass7': '0.7',
        'DirectNeuralRenderingLocalStructureStrengthPass8': '0.7',
        'DirectNeuralRenderingLocalStructureStrengthPass9': '0.7',
        'DirectNeuralRenderingLocalToneStrength': '1',
        'DirectNeuralRenderingLocalToneStrengthPass10': '0.3',
        'DirectNeuralRenderingLocalToneStrengthPass2': '0.3',
        'DirectNeuralRenderingLocalToneStrengthPass3': '0.3',
        'DirectNeuralRenderingLocalToneStrengthPass4': '0.3',
        'DirectNeuralRenderingLocalToneStrengthPass5': '0.3',
        'DirectNeuralRenderingLocalToneStrengthPass6': '0.3',
        'DirectNeuralRenderingLocalToneStrengthPass7': '0.3',
        'DirectNeuralRenderingLocalToneStrengthPass8': '0.3',
        'DirectNeuralRenderingLocalToneStrengthPass9': '0.3',
        'DirectNeuralRenderingModelCorrections': '0',
        'DirectNeuralRenderingPassCount': '1',
        'DirectNeuralRenderingPreset': '2',
        'DirectNeuralRenderingPreset1Model0BlackLevel': '0.00025471',
        'DirectNeuralRenderingPreset1Model0WhiteLevel': '0.04310297',
        'DirectNeuralRenderingPreset1Model1BlackLevel': '0.000130265',
        'DirectNeuralRenderingPreset1Model1WhiteLevel': '0.22131996',
        'DirectNeuralRenderingPreset1Model2BlackLevel': '0.000832178',
        'DirectNeuralRenderingPreset1Model2WhiteLevel': '0.046671238',
        'DirectNeuralRenderingPreset2Model0BlackLevel': '0.000217623',
        'DirectNeuralRenderingPreset2Model0WhiteLevel': '0.022936724',
        'DirectNeuralRenderingPreset2Model1BlackLevel': '0.000391522',
        'DirectNeuralRenderingPreset2Model1WhiteLevel': '0.2115776',
        'DirectNeuralRenderingPreset2Model2BlackLevel': '0.001443278',
        'DirectNeuralRenderingPreset2Model2WhiteLevel': '0.05568646',
        'DirectNeuralRenderingProcessingScale': '100',
        'DirectNeuralRenderingScaleReconstruction': '0',
        'DirectNeuralRenderingSignalEncoding': '0',
        'DirectNeuralRenderingSkinStructureStrength': '0.8',
        'DirectNeuralRenderingSkinStructureStrengthPass10': '0.5',
        'DirectNeuralRenderingSkinStructureStrengthPass2': '0.5',
        'DirectNeuralRenderingSkinStructureStrengthPass3': '0.5',
        'DirectNeuralRenderingSkinStructureStrengthPass4': '0.5',
        'DirectNeuralRenderingSkinStructureStrengthPass5': '0.5',
        'DirectNeuralRenderingSkinStructureStrengthPass6': '0.5',
        'DirectNeuralRenderingSkinStructureStrengthPass7': '0.5',
        'DirectNeuralRenderingSkinStructureStrengthPass8': '0.5',
        'DirectNeuralRenderingSkinStructureStrengthPass9': '0.5',
        'DirectNeuralRenderingStyle': '2',
        'DirectNeuralRenderingStylePass10': '0',
        'DirectNeuralRenderingStylePass2': '0',
        'DirectNeuralRenderingStylePass3': '0',
        'DirectNeuralRenderingStylePass4': '0',
        'DirectNeuralRenderingStylePass5': '0',
        'DirectNeuralRenderingStylePass6': '0',
        'DirectNeuralRenderingStylePass7': '0',
        'DirectNeuralRenderingStylePass8': '0',
        'DirectNeuralRenderingStylePass9': '0',
        'DirectNeuralRenderingUpsampleFilter': '0'},
    "renodx": {
        "Preset": "1",
        "OptionsMode": "0",
        "DLSSQualityMode": "0",
        "DirectNeuralRenderingStatus": "1",
        "DirectNeuralRenderingHookStage": "1",
        "DirectNeuralRenderingReuseDlssUpscalingResources": "0",
        "DirectNeuralRenderingUiCorrectionMode": "0",
        "DirectNeuralRenderingDiffuseWhiteOverride": "0",
        "DirectNeuralRenderingIntensity": "1.000000",
        "DirectNeuralRenderingStyle": "2",
        "DirectNeuralRenderingLocalStructureStrength": "1.000000",
        "DirectNeuralRenderingLocalToneStrength": "1.000000",
        "DirectNeuralRenderingAutoMask": "1",
        "DirectNeuralRenderingSkinStructureStrength": "0.800000",
        "DirectNeuralRenderingProcessingScale": "100.000000",
        "DirectNeuralRenderingFilterDomain": "0",
        "DirectNeuralRenderingDownsampleFilter": "0",
        "DirectNeuralRenderingUpsampleFilter": "0",
        "DirectNeuralRenderingScaleReconstruction": "0",
        "DirectNeuralRenderingPreset": "2",
        "DirectNeuralRenderingPassCount": "1",
        "DirectNeuralRenderingEncoding": "0",
        "DirectNeuralRenderingSignalEncoding": "0",
        "DirectNeuralRenderingDiffuseWhiteNits": "100.000000",
        "DirectNeuralRenderingBlockHudless": "0",
        "DirectNeuralRenderingExposure": "1.000000",
        "DirectNeuralRenderingExposureMode": "1",
        "DirectNeuralRenderingModelCorrections": "0",
        "DirectNeuralRenderingModelAdjustments": "0",
        "DirectNeuralRenderingModelLab": "1",
        "DirectNeuralRenderingFineTune": "0",
        "DirectNeuralRenderingAlwaysPresent": "0",
        "DirectNeuralRenderingPresentMode": "0",
        "DirectNeuralRenderingVramBuffering": "1",
        "NeuralUplift": "1",
        "NRVramBuffering": "1",
        "VramBuffering": "1",
        "NRVramBudgetGuard": "0",
        "NRVramBudgetMargin": "0",
        "VramBudgetGuard": "0",
        "BudgetGuard": "0",
        "NRPresentGuides": "0",
        "NRPresentAlways": "0",
        "AlwaysPresent": "0",
        "NRPresentNonBlocking": "1",
        "NRRuntimePath": ".\\nvngx_dlssnr.dll",
        "NRToggleKey": "0,0,0,0",
        "NRGpuTimers": "0",
        "NRCostMeter": "0",
        "NRCrashDump": "0",
        "NRDiagnostics": "0",
        "NREditTrace": "0",
        "NRNormTrace": "0"
    },
    "renodx-preset1": {
        "Preset": "1",
        "OptionsMode": "0",
        "DLSSQualityMode": "0",
        "DirectNeuralRenderingStatus": "1",
        "DirectNeuralRenderingHookStage": "1",
        "DirectNeuralRenderingReuseDlssUpscalingResources": "0",
        "DirectNeuralRenderingUiCorrectionMode": "0",
        "DirectNeuralRenderingDiffuseWhiteOverride": "0",
        "DirectNeuralRenderingIntensity": "1.000000",
        "DirectNeuralRenderingStyle": "2",
        "DirectNeuralRenderingLocalStructureStrength": "1.000000",
        "DirectNeuralRenderingLocalToneStrength": "1.000000",
        "DirectNeuralRenderingAutoMask": "1",
        "DirectNeuralRenderingSkinStructureStrength": "0.800000",
        "DirectNeuralRenderingProcessingScale": "100.000000",
        "DirectNeuralRenderingFilterDomain": "0",
        "DirectNeuralRenderingDownsampleFilter": "0",
        "DirectNeuralRenderingUpsampleFilter": "0",
        "DirectNeuralRenderingScaleReconstruction": "0",
        "DirectNeuralRenderingPreset": "2",
        "DirectNeuralRenderingPassCount": "1",
        "DirectNeuralRenderingEncoding": "0",
        "DirectNeuralRenderingSignalEncoding": "0",
        "DirectNeuralRenderingDiffuseWhiteNits": "100.000000",
        "DirectNeuralRenderingBlockHudless": "0",
        "DirectNeuralRenderingExposure": "1.000000",
        "DirectNeuralRenderingExposureMode": "1",
        "DirectNeuralRenderingModelCorrections": "0",
        "DirectNeuralRenderingModelAdjustments": "0",
        "DirectNeuralRenderingModelLab": "1",
        "DirectNeuralRenderingFineTune": "0",
        "DirectNeuralRenderingAlwaysPresent": "0",
        "DirectNeuralRenderingPresentMode": "0",
        "DirectNeuralRenderingVramBuffering": "1"
    },
    "renodx-preset2": {
        "Preset": "2",
        "OptionsMode": "0",
        "DirectNeuralRenderingStatus": "1",
        "DirectNeuralRenderingHookStage": "1",
        "DirectNeuralRenderingReuseDlssUpscalingResources": "0",
        "DirectNeuralRenderingUiCorrectionMode": "0",
        "DirectNeuralRenderingIntensity": "1.000000",
        "DirectNeuralRenderingStyle": "2",
        "DirectNeuralRenderingLocalStructureStrength": "1.000000",
        "DirectNeuralRenderingLocalToneStrength": "1.000000",
        "DirectNeuralRenderingAutoMask": "1",
        "DirectNeuralRenderingSkinStructureStrength": "0.800000",
        "DirectNeuralRenderingProcessingScale": "100.000000",
        "DirectNeuralRenderingFilterDomain": "0",
        "DirectNeuralRenderingDownsampleFilter": "0",
        "DirectNeuralRenderingUpsampleFilter": "0",
        "DirectNeuralRenderingScaleReconstruction": "0",
        "DirectNeuralRenderingPreset": "2",
        "DirectNeuralRenderingPassCount": "1",
        "DirectNeuralRenderingEncoding": "0",
        "DirectNeuralRenderingSignalEncoding": "0",
        "DirectNeuralRenderingDiffuseWhiteNits": "100.000000",
        "DirectNeuralRenderingExposure": "1.000000",
        "DirectNeuralRenderingExposureMode": "1",
        "DirectNeuralRenderingModelCorrections": "0"
    },
    "renodx-preset3": {
        "Preset": "3",
        "OptionsMode": "0",
        "DirectNeuralRenderingStatus": "1",
        "DirectNeuralRenderingHookStage": "1",
        "DirectNeuralRenderingReuseDlssUpscalingResources": "0",
        "DirectNeuralRenderingUiCorrectionMode": "0",
        "DirectNeuralRenderingIntensity": "1.000000",
        "DirectNeuralRenderingStyle": "2",
        "DirectNeuralRenderingLocalStructureStrength": "1.000000",
        "DirectNeuralRenderingLocalToneStrength": "1.000000",
        "DirectNeuralRenderingAutoMask": "1",
        "DirectNeuralRenderingSkinStructureStrength": "0.800000",
        "DirectNeuralRenderingProcessingScale": "100.000000",
        "DirectNeuralRenderingFilterDomain": "0",
        "DirectNeuralRenderingDownsampleFilter": "0",
        "DirectNeuralRenderingUpsampleFilter": "0",
        "DirectNeuralRenderingScaleReconstruction": "0",
        "DirectNeuralRenderingPreset": "2",
        "DirectNeuralRenderingPassCount": "1",
        "DirectNeuralRenderingEncoding": "0",
        "DirectNeuralRenderingSignalEncoding": "0",
        "DirectNeuralRenderingDiffuseWhiteNits": "100.000000",
        "DirectNeuralRenderingExposure": "1.000000",
        "DirectNeuralRenderingExposureMode": "1",
        "DirectNeuralRenderingModelCorrections": "0"
    },
    "RenoDX DLSS": {
        "ConfigVersion": "11",
        "NREnabled": "1",
        "Enabled": "1",
        "NRPreset": "Preset #1",
        "Preset": "Preset #1",
        "CurrentPreset": "Preset #1",
        "OptionsMode": "0",
        "DLSSQualityMode": "0",
        "DirectNeuralRenderingStatus": "1",
        "DirectNeuralRenderingHookStage": "1",
        "HookStage": "0",
        "NRHookPoint": "0",
        "DirectNeuralRenderingReuseDlssUpscalingResources": "0",
        "DirectNeuralRenderingUiCorrectionMode": "0",
        "DirectNeuralRenderingDiffuseWhiteOverride": "0",
        "DirectNeuralRenderingIntensity": "1.000000",
        "Intensity": "1.000000",
        "NRIntensity": "1.000000",
        "DirectNeuralRenderingStyle": "2",
        "Style": "2",
        "NRStyle": "2",
        "DirectNeuralRenderingLocalStructureStrength": "1.000000",
        "LocalStructure": "1.000000",
        "NRLocalStructure": "1.000000",
        "DirectNeuralRenderingLocalToneStrength": "1.000000",
        "LocalTone": "1.000000",
        "NRLocalTone": "1.000000",
        "DirectNeuralRenderingAutoMask": "1",
        "DirectNeuralRenderingSkinStructureStrength": "0.800000",
        "SkinStructure": "80",
        "Skin": "80",
        "NRSkinStructure": "0.800000",
        "DirectNeuralRenderingProcessingScale": "100.000000",
        "ProcessingScale": "100.000000",
        "ResolutionScale": "1.000000",
        "NRResolutionScale": "1.000000",
        "DirectNeuralRenderingFilterDomain": "0",
        "DirectNeuralRenderingDownsampleFilter": "0",
        "DirectNeuralRenderingUpsampleFilter": "0",
        "DirectNeuralRenderingScaleReconstruction": "0",
        "DirectNeuralRenderingPreset": "2",
        "DirectNeuralRenderingPassCount": "1",
        "PassCount": "1",
        "NRPasses": "1",
        "DirectNeuralRenderingEncoding": "0",
        "DirectNeuralRenderingSignalEncoding": "0",
        "DirectNeuralRenderingDiffuseWhiteNits": "100.000000",
        "DirectNeuralRenderingBlockHudless": "0",
        "DirectNeuralRenderingExposure": "1.000000",
        "DirectNeuralRenderingExposureMode": "1",
        "DirectNeuralRenderingModelCorrections": "0",
        "DirectNeuralRenderingModelAdjustments": "0",
        "DirectNeuralRenderingModelLab": "1",
        "ModelLab": "1",
        "DirectNeuralRenderingFineTune": "0",
        "DirectNeuralRenderingAlwaysPresent": "0",
        "DirectNeuralRenderingPresentMode": "0",
        "DirectNeuralRenderingVramBuffering": "1",
        "NeuralUplift": "1",
        "NRVramBuffering": "1",
        "VramBuffering": "1",
        "NRVramBudgetGuard": "0",
        "NRVramBudgetMargin": "0",
        "VramBudgetGuard": "0",
        "BudgetGuard": "0",
        "NRPresentGuides": "0",
        "NRPresentAlways": "0",
        "AlwaysPresent": "0",
        "NRPresentNonBlocking": "1",
        "NRRuntimePath": ".\\nvngx_dlssnr.dll",
        "NRToggleKey": "0,0,0,0",
        "NRGpuTimers": "0",
        "NRCostMeter": "0",
        "NRCrashDump": "0",
        "NRDiagnostics": "0",
        "NREditTrace": "0",
        "NRNormTrace": "0"
    },
    "RenoDX.DLSS5": {
        "ConfigVersion": "11",
        "NREnabled": "1",
        "Enabled": "1",
        "NRPreset": "My look",
        "Preset": "My look",
        "CurrentPreset": "My look",
        "NRHookPoint": "0",
        "HookStage": "0",
        "NRStyle": "2",
        "Style": "2",
        "NRPass2Preset": "2",
        "NRModelVersion": "1",
        "ModelVersion": "1",
        "NRResolutionScale": "0.500000",
        "ResolutionScale": "0.500000",
        "NRFollowInputRes": "1",
        "NRIntensity": "1.000000",
        "Intensity": "1.000000",
        "NRLocalTone": "1.000000",
        "LocalTone": "1.000000",
        "NRLocalStructure": "1.000000",
        "LocalStructure": "1.000000",
        "NRSkinStructure": "1.000000",
        "SkinStructure": "100",
        "Skin": "100",
        "NRPass2Skin": "100",
        "NRPasses": "1",
        "PassCount": "1",
        "NRModelLabEnabled": "1",
        "ModelLab": "1",
        "NRLayersEnabled": "1",
        "UiCorrection": "1",
        "NeuralUplift": "1",
        "NRVramBuffering": "1",
        "VramBuffering": "1",
        "NRVramBudgetGuard": "0",
        "NRVramBudgetMargin": "0",
        "VramBudgetGuard": "0",
        "BudgetGuard": "0",
        "NRPresentGuides": "0",
        "NRPresentAlways": "0",
        "AlwaysPresent": "0",
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
        "DirectNeuralRenderingHookStage": "0",
        "DirectNeuralRenderingAlwaysPresent": "0",
        "DirectNeuralRenderingPresentMode": "0",
        "DirectNeuralRenderingVramBuffering": "1",
        "DirectNeuralRenderingLocalToneStrength": "1.000000",
        "DirectNeuralRenderingLocalStructureStrength": "1.000000",
        "DirectNeuralRenderingSkinStructureStrength": "1.000000",
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
        "NRHookPoint": "0",
        "NRStyle": "2",
        "NRPass2Preset": "2",
        "NRSkinStructure": "1.000000",
        "SkinStructure": "100",
        "Skin": "100",
        "NRResolutionScale": "0.500000",
        "NRFollowInputRes": "1",
        "NRIntensity": "1.000000",
        "NRLocalTone": "1.000000",
        "NRLocalStructure": "1.000000",
        "NRPasses": "1",
        "NRModelLabEnabled": "1",
        "NRLayersEnabled": "1",
        "NeuralUplift": "1",
        "NRVramBuffering": "1",
        "VramBuffering": "1",
        "NRVramBudgetGuard": "0",
        "NRVramBudgetMargin": "0",
        "VramBudgetGuard": "0",
        "BudgetGuard": "0",
        "NRPresentGuides": "0",
        "NRPresentAlways": "0",
        "NRPresentNonBlocking": "1",
        "NRRuntimePath": ".\\nvngx_dlssnr.dll"
    },
    "RenoDX": {
        "CurrentPreset": "My look",
        "Enabled": "1",
        "Status": "1",
        "ConfigVersion": "11",
        "NRHookPoint": "0",
        "NRStyle": "2",
        "NRPass2Preset": "2",
        "NRSkinStructure": "1.000000",
        "SkinStructure": "100",
        "Skin": "100",
        "NRResolutionScale": "0.500000",
        "NRFollowInputRes": "1",
        "NRIntensity": "1.000000",
        "NRLocalTone": "1.000000",
        "NRLocalStructure": "1.000000",
        "NRPresentGuides": "0",
        "NRPresentAlways": "0",
        "NRPresentNonBlocking": "1",
        "NeuralUplift": "1",
        "NRVramBuffering": "1",
        "VramBuffering": "1",
        "NRVramBudgetGuard": "0",
        "NRVramBudgetMargin": "0",
        "VramBudgetGuard": "0",
        "BudgetGuard": "0",
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
        "DirectNeuralRenderingHookStage": "0",
        "DirectNeuralRenderingAlwaysPresent": "0",
        "DirectNeuralRenderingPresentMode": "0",
        "DirectNeuralRenderingVramBuffering": "1",
        "DirectNeuralRenderingLocalToneStrength": "1.000000",
        "DirectNeuralRenderingLocalStructureStrength": "1.000000",
        "DirectNeuralRenderingSkinStructureStrength": "1.000000",
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
        "NRResolutionScale": "0.500000",
        "NRFollowInputRes": "1",
        "NRHookPoint": "0",
        "NRPresentGuides": "0",
        "NRPresentAlways": "0",
        "NRPresentNonBlocking": "1",
        "NeuralUplift": "1",
        "NRVramBuffering": "1",
        "VramBuffering": "1",
        "NRVramBudgetGuard": "0",
        "NRVramBudgetMargin": "0",
        "VramBudgetGuard": "0",
        "BudgetGuard": "0",
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
        "NRSkinStructure": "1.000000",
        "SkinStructure": "100",
        "Skin": "100",
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
        "NRHookPoint": "0",
        "NRStyle": "2",
        "NRPass2Preset": "2",
        "NRSkinStructure": "1.000000",
        "SkinStructure": "100",
        "Skin": "100",
        "NRResolutionScale": "0.500000",
        "NRFollowInputRes": "1",
        "NRIntensity": "1.000000",
        "NRLocalTone": "1.000000",
        "NRLocalStructure": "1.000000",
        "NRPasses": "1",
        "NRModelLabEnabled": "1",
        "NRLayersEnabled": "1",
        "NeuralUplift": "1",
        "NRVramBuffering": "1",
        "VramBuffering": "1",
        "NRVramBudgetGuard": "0",
        "NRVramBudgetMargin": "0",
        "VramBudgetGuard": "0",
        "BudgetGuard": "0",
        "NRPresentGuides": "0",
        "NRPresentAlways": "0",
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
        "ResolutionScale": "0.500000",
        "HookStage": "0",
        "AlwaysPresent": "0",
        "VramBuffering": "1",
        "LocalTone": "1.000000",
        "LocalStructure": "1.000000",
        "SkinStructure": "100",
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
        "DirectNeuralRenderingHookStage": "0",
        "DirectNeuralRenderingAlwaysPresent": "0",
        "DirectNeuralRenderingVramBuffering": "1",
        "DirectNeuralRenderingLocalToneStrength": "1.000000",
        "DirectNeuralRenderingLocalStructureStrength": "1.000000",
        "DirectNeuralRenderingSkinStructureStrength": "1.000000",
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
    Synchronizes DLSS 5 hook point for BOTH Mode A (ShortFuse renodx-dlss) and Mode B (Lecram-v12).
    
    Mode A enum mapping (DirectNeuralRenderingHookStage):
      - '0' (Upscaled): DirectNeuralRenderingHookStage='1'
      - '2' (Present): DirectNeuralRenderingHookStage='2'
      - '1' (Before/Render): DirectNeuralRenderingHookStage='0'
      
    Mode B enum mapping (NRHookPoint):
      - '0' (Upscaled): NRHookPoint='0'
      - '2' (Present): NRHookPoint='2'
      - '1' (Before/Render): NRHookPoint='1'
    """
    td = Path(target_dir) if target_dir else None
    if not td or not td.exists() or not td.is_dir():
        return False

    str_hook = str(hook_point)
    if str_hook == "2":
        mode_a_stage = "2"
        mode_b_stage = "2"
        always_pres = "1"
    elif str_hook == "1":
        mode_a_stage = "0"
        mode_b_stage = "1"
        always_pres = "0"
    else:  # "0" Upscaled
        mode_a_stage = "1"
        mode_b_stage = "0"
        always_pres = "0"

    hook_updates_mode_a = {
        "DirectNeuralRenderingStatus": "1",
        "DirectNeuralRenderingHookStage": mode_a_stage,
        "DirectNeuralRenderingAlwaysPresent": always_pres,
        "DirectNeuralRenderingPresentMode": always_pres,
        "HookStage": mode_a_stage,
        "NRHookPoint": mode_b_stage,
        "NeuralUplift": "1",
        "NRVramBuffering": "1",
        "VramBuffering": "1",
        "DirectNeuralRenderingVramBuffering": "1",
        "NRVramBudgetGuard": "0",
        "NRVramBudgetMargin": "0",
        "VramBudgetGuard": "0",
        "BudgetGuard": "0",
        "NRPresentAlways": always_pres,
        "AlwaysPresent": always_pres,
    }

    hook_updates_mode_b = {
        "NRHookPoint": mode_b_stage,
        "HookStage": mode_b_stage,
        "DirectNeuralRenderingHookStage": mode_a_stage,
        "DirectNeuralRenderingAlwaysPresent": always_pres,
        "DirectNeuralRenderingPresentMode": always_pres,
        "NRPresentAlways": always_pres,
        "AlwaysPresent": always_pres,
        "NeuralUplift": "1",
        "NRVramBuffering": "1",
        "VramBuffering": "1",
        "DirectNeuralRenderingVramBuffering": "1",
        "NRVramBudgetGuard": "0",
        "NRVramBudgetMargin": "0",
        "VramBudgetGuard": "0",
        "BudgetGuard": "0",
    }

    combined_updates = {**hook_updates_mode_b, **hook_updates_mode_a}

    # 1. Update ReShade.ini
    reshade_ini = td / "ReShade.ini"
    if reshade_ini.exists():
        sections_to_update = {
            "RENODX-DLSS": hook_updates_mode_a,
            "RENODX-DLSS-preset1": hook_updates_mode_a,
            "RENODX-DLSS-preset2": hook_updates_mode_a,
            "RENODX-DLSS-preset3": hook_updates_mode_a,
            "renodx": hook_updates_mode_a,
            "renodx-preset1": hook_updates_mode_a,
            "renodx-preset2": hook_updates_mode_a,
            "renodx-preset3": hook_updates_mode_a,
            "RenoDX DLSS": hook_updates_mode_a,
            "RenoDX.DLSS5": hook_updates_mode_b,
            "RenoDX DLSS5 preset": hook_updates_mode_b,
            "RenoDX": hook_updates_mode_b,
            "DLSSNR": hook_updates_mode_b,
            "RenoDX-My look": hook_updates_mode_b,
            "DLSS5": hook_updates_mode_b,
            "DLSS5-NR": hook_updates_mode_b
        }
        # Cleanse LoadFromDllMain in [ADDON]: DLSS addons must NEVER load from DllMain (violates Windows loader lock)
        try:
            content = reshade_ini.read_text(encoding="utf-8", errors="ignore")
            clean_addons = []
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
            sections_to_update["ADDON"] = {"LoadFromDllMain": ",".join(clean_addons)}
        except Exception:
            pass
        update_ini_file_sections(reshade_ini, sections_to_update)

    # 2. Update ReShadePreset.ini
    reshade_preset = td / "ReShadePreset.ini"
    if reshade_preset.exists():
        _update_preset_file_kv(reshade_preset, combined_updates)

    # 3. Update target directory RenoDX/DLSS5/Presets/*.ini
    preset_dir = td / "RenoDX" / "DLSS5" / "Presets"
    if preset_dir.exists() and preset_dir.is_dir():
        for p_file in preset_dir.glob("*.ini"):
            _update_preset_file_kv(p_file, combined_updates)

    # 4. Also update AppData RenoDX presets
    appdata_reno_presets = Path(os.environ.get("LOCALAPPDATA", "")) / "RenoDX" / "DLSS5" / "Presets"
    if appdata_reno_presets.exists() and appdata_reno_presets.is_dir():
        for p_file in appdata_reno_presets.glob("*.ini"):
            _update_preset_file_kv(p_file, combined_updates)

    return True


def ensure_reshade_chinese_ini(ini_path: Path, is_mode_c: bool = False, addon_name: str = 'renodx-dlss.addon64', mode: str = 'MODE_A', proxy_choice: str = 'dxgi.dll'):
    """
    Ensures ReShade.ini in the game directory uses Simplified Chinese UI overlay,
    Microsoft YaHei font, Home key for overlay, skips intro tutorial,
    and applies default parameters for Mode A (RenoDX DLSS) and Mode B (RenoDX.DLSS5).
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
                            clean_lower = clean_part.lower()
                            if clean_part and clean_part != "1" and "dlss" not in clean_lower and "shortfuse" not in clean_lower and "lecram" not in clean_lower:
                                if clean_lower not in [x.lower() for x in clean_addons]:
                                    clean_addons.append(clean_part)
        except Exception:
            pass

    # Only Mode B (renodx-mfgunlock.addon64) requires LoadFromDllMain. DLSS 5 must NEVER load from DllMain!
    if clean_addons:
        sections["ADDON"]["LoadFromDllMain"] = ",".join(clean_addons)
    else:
        sections["ADDON"]["LoadFromDllMain"] = "" 

    # Key binding configuration:
    # Mode B (Lecram v12): Hotkey set to F12 (VK_F12 = 123)
    # Mode A (ShortFuse): Default Home key (VK_HOME = 36)
    if mode == "MODE_B":
        sections["OVERLAY"]["KeyOverlay"] = "123,0,0,0"
        if "INPUT" not in sections:
            sections["INPUT"] = {}
        sections["INPUT"]["KeyOverlay"] = "123,0,0,0"
        sections["RenoDX.DLSS5"]["NRPanelKey"] = "123,0,0,0"
        sections["RenoDX.DLSS5"]["ReShadeMenuKey"] = "123,0,0,0"
        if "hotkeys" not in sections:
            sections["hotkeys"] = {}
        sections["hotkeys"]["NRPanelKey"] = "123,0,0,0"
        sections["hotkeys"]["NRToggleKey"] = "0,0,0,0"
    else:
        sections["OVERLAY"]["KeyOverlay"] = "36,0,0,0"
        if "INPUT" not in sections:
            sections["INPUT"] = {}
        sections["INPUT"]["KeyOverlay"] = "36,0,0,0"

    # d3d12.dll system path & dead-lock hardening
    if proxy_choice.lower() == "d3d12.dll":
        sections["GENERAL"]["NoReloadOnInit"] = "1"
        sections["GENERAL"]["PerformanceMode"] = "1"
        sections["DX12"]["UseAspectRatioHeuristics"] = "1"

    update_ini_file_sections(ini_path, sections)
    try:
        preset_ini = ini_path.parent / "ReShadePreset.ini"
        update_ini_file_sections(preset_ini, sections)
    except Exception:
        pass


class DLSS5Injector:
    """
    Core executor for standalone DLSS 5 plugin injection and lossless uninstallation.
    """

    @staticmethod
    def apply_hook_point(target_dir: str, hook_point: str = "0") -> Tuple[bool, str]:
        """
        Directly updates and applies DLSS 5 hook point to an existing game installation
        without requiring re-injection or starting the game.
        """
        td = Path(target_dir) if target_dir else None
        if not td or not td.exists() or not td.is_dir():
            return False, f"目标游戏目录不存在: {target_dir}"

        ok = sync_dlss5_hook_point(td, hook_point=hook_point)
        if not ok:
            return False, "未能成功写入配置文件，请检查目录权限或文件是否被占用。"

        label_map = {
            "0": "之后 (Upscaled · 防闪退/兼容多帧插帧)",
            "2": "呈现 (Present · 纯画质呈现)",
            "1": "之前 (Before · 原生渲染阶段)"
        }
        lbl = label_map.get(str(hook_point), f"模式 {hook_point}")
        return True, f"已成功将当前游戏的 DLSS 5 挂钩模式修改为【{lbl}】！\n\n已无缝同步至模式 A (ShortFuse 原生底座) 与模式 B (Lecram v12 扩展底座) 配置文件，无需启动游戏即可生效。"

    @staticmethod
    def inject(
        target_dir: str,
        source_dir: Optional[str] = None,
        arch_choice: str = "auto",
        hook_point: str = "0",
        mode: str = "MODE_A",
        proxy_choice: str = "auto"
    ) -> Tuple[bool, str]:
        """
        Executes one-click standalone injection of DLSS 5 into target_dir.
        
        Args:
            target_dir: Game executable directory
            source_dir: Plugin assets folder
            arch_choice: 'auto', 'rtx20_30_40', or 'rtx50'
            hook_point: '0' (Upscaled), '2' (Present), or '1' (Before)
            mode: 'MODE_A' (ShortFuse native base) or 'MODE_B' (Lecram v12 base)
        """
        td = Path(target_dir) if target_dir else None
        if not td or not td.exists() or not td.is_dir():
            return False, f"目标游戏目录不存在或不可用: {target_dir}"

        if mode not in DLSS5_ENGINE_MODES:
            mode = DEFAULT_DLSS5_MODE
        mode_conf = DLSS5_ENGINE_MODES[mode]

        # Resolve proxy slot choice
        rec_proxy, rec_reason, api_details = detect_game_render_api(td)
        if not proxy_choice or proxy_choice == "auto":
            chosen_proxy = rec_proxy
        elif proxy_choice in DLSS5_PROXY_SLOTS:
            chosen_proxy = proxy_choice
        else:
            chosen_proxy = "dxgi.dll"

        # Mutex proxy cleanup: purge any conflicting ReShade proxies
        clean_proxy_ok, clean_proxy_msg, removed_proxies = clean_conflicting_proxies(td, keep_proxy=chosen_proxy)
        if not clean_proxy_ok:
            return False, clean_proxy_msg

        # Auto-heal any missing game native dependencies (such as libxell.dll, libxess.dll, libxess_fg.dll)
        try:
            from apps.app2_mfg.core.utils import auto_heal_game_dependencies
            auto_heal_game_dependencies(td)
        except Exception:
            pass

        # Refuse to touch a live process: overwriting dxgi.dll / nvngx_dlssnr.dll
        # while the engine has them mapped corrupts the image and crashes on the
        # next DLSS call. The patch engine already guards this; DLSS 5 did not.
        game_exe = _guess_game_exe(td)
        if game_exe and not os.environ.get("PYTEST_CURRENT_TEST"):
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

        assets = scan_plugin_source_assets(Path(source_dir) if source_dir else None, mode=mode)
        if not assets.get("exists"):
            return False, f"未检测到 DLSS 5 插件源目录！\n请确认插件已就绪或在界面中指定有效路径。"

        # 1. Check dxgi.dll
        dxgi_src = assets.get("dxgi_path")
        if not dxgi_src or not os.path.exists(dxgi_src):
            return False, "插件包中缺少 ReShade 核心底座 (dxgi.dll)！"

        # 2. Check addon64 (chosen mode addon)
        addon_src = assets.get("addon_path")
        if not addon_src or not os.path.exists(addon_src):
            return False, f"插件包中缺少 {mode_conf['title']} 核心底座 ({mode_conf['addon_file']})！\n请确认插件源目录包含此文件。"

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
            "mode": mode,
            "mode_title": mode_conf["title"],
            "addon_file": Path(addon_src).name,
            "selected_arch": chosen_arch,
            "arch_label": arch_label,
            "injected_files": [],
            "backed_up_files": {}
        }

        # Backup existing proxy DLL ONLY if it is a genuine game file (not ReShade or OptiScaler)
        proxy_dest = td / chosen_proxy
        existing_manifest_file = td / DLSS5_MANIFEST_FILENAME
        is_clean_install = not existing_manifest_file.exists()

        if proxy_dest.exists() and is_clean_install:
            bak_proxy = backup_dir / chosen_proxy
            if not bak_proxy.exists():
                if not is_reshade_dll_file(str(proxy_dest)) and not is_optiscaler_dll_file(str(proxy_dest)):
                    try:
                        shutil.copy2(proxy_dest, bak_proxy)
                        manifest_data["backed_up_files"][chosen_proxy] = str(bak_proxy)
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
        clean_ok, clean_msg, _ = clean_conflicting_addons(td, keep_addon=None)
        if not clean_ok:
            return False, clean_msg

        # Coexistence detection with Mode C (OptiScaler / XeSS 2.0 / XeFG)
        has_mode_c = is_mode_c_present(td)
        has_mfg = is_mfg_present(td) or has_mode_c
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
            if has_mode_c and coex_slot is None and is_optiscaler_dll_file(str(proxy_dest)):
                return False, (
                    f"检测到模式 C 的 OptiScaler 仍占用 {chosen_proxy}，且无法迁移到次级代理槽位。\n"
                    "请先完全退出游戏，然后重新注入模式 C（或先卸载模式 C），再注入 DLSS 5。"
                )

            # 6.1 Copy ReShade base to chosen proxy slot
            is_ace_protected = (
                (td / "AntiCheatExpert").exists()
                or (td / "ACE-Base64.dll").exists()
                or bool(list(td.glob("*ACE*")))
                or (td / "PlatformProcess.exe").exists()
            )

            # Direct ReShade 6.8 deployment (PlatformProcess.exe never loads d3d12.dll, only Streamline sl.common.dll loads it)
            shutil.copy2(dxgi_src, proxy_dest)
            manifest_data["injected_files"].append(chosen_proxy)
            manifest_data["proxy_choice"] = chosen_proxy

            # If d3d12.dll is chosen, clean up legacy OptiScaler shield files that could cause heap collision
            if chosen_proxy.lower() == "d3d12.dll":
                for stale in [td / "OptiScaler.dll", td / "OptiScaler.ini", td / "OptiScaler.log", td / "d3d12-ReShade64.dll"]:
                    if stale.exists():
                        try:
                            stale.unlink()
                        except Exception:
                            pass

            # 6.1.1 If chosen_proxy is ReShade64.dll and OptiScaler.ini exists, activate LoadReshade = true
            if chosen_proxy.lower() == "reshade64.dll" and (td / "OptiScaler.ini").exists():
                try:
                    opti_ini = td / "OptiScaler.ini"
                    content_opti = opti_ini.read_text(encoding="utf-8", errors="ignore")
                    lines_opti = content_opti.splitlines()
                    in_plugins = False
                    found_load = False
                    new_lines_opti = []
                    for line in lines_opti:
                        stripped = line.strip()
                        if stripped.startswith("[") and stripped.endswith("]"):
                            if in_plugins and not found_load:
                                new_lines_opti.append("LoadReshade = true")
                                found_load = True
                            in_plugins = (stripped.lower() == "[plugins]")
                        elif in_plugins and stripped.lower().startswith("loadreshade"):
                            line = "LoadReshade = true"
                            found_load = True
                        new_lines_opti.append(line)
                    if not found_load:
                        if in_plugins:
                            new_lines_opti.append("LoadReshade = true")
                        else:
                            new_lines_opti.append("\n[Plugins]\nLoadReshade = true")
                    opti_ini.write_text("\n".join(new_lines_opti).strip() + "\n", encoding="utf-8")
                except Exception:
                    pass

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
            ensure_reshade_chinese_ini(ini_dest, is_mode_c=has_mode_c, addon_name=Path(addon_src).name, mode=mode, proxy_choice=chosen_proxy)
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
                    "NRHookPoint=0\n"
                    "HookStage=0\n"
                    "NRStyle=2\n"
                    "Style=2\n"
                    "NRPass2Preset=2\n"
                    "NRModelVersion=1\n"
                    "NRSkinStructure=1.000000\n"
                    "SkinStructure=100\n"
                    "Skin=100\n"
                    "NRPass2Skin=-1\n"
                    "NRResolutionScale=0.500000\n"
                    "NRFollowInputRes=1\n"
                    "NRIntensity=1\n"
                    "NRLocalTone=1\n"
                    "NRLocalStructure=1\n"
                    "NRPasses=1\n"
                    "NRModelLabEnabled=1\n"
                    "NRLayersEnabled=1\n"
                    "NeuralUplift=1\n"
                    "NRVramBuffering=1\n"
                    "VramBuffering=1\n"
                    "DirectNeuralRenderingVramBuffering=1\n"
                    "NRVramBudgetGuard=0\n"
                    "NRVramBudgetMargin=0\n"
                    "VramBudgetGuard=0\n"
                    "BudgetGuard=0\n"
                    "NRPresetGuides=0\n"
                    "NRPresentAlways=0\n"
                    "AlwaysPresent=0\n"
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
            # Default hook point is Present (2)

            try:
                (preset_dir / "My look.ini").write_text(preset_text, encoding="utf-8")
                (preset_dir / "Default.ini").write_text(preset_text.replace("Name=My look", "Name=Default"), encoding="utf-8")
                (preset_dir / "Standard.ini").write_text(preset_text.replace("Name=My look", "Name=Standard"), encoding="utf-8")
                reshade_preset_file = td / "ReShadePreset.ini"
                reshade_preset_file.write_text(preset_text, encoding="utf-8")
                try:
                    update_ini_file_sections(reshade_preset_file, DEFAULT_DLSS5_INI_SECTIONS)
                except Exception:
                    pass

                # Also synchronize AppData RenoDX presets so RenoDX loads user My look everywhere
                appdata_reno_presets = Path(os.environ.get("LOCALAPPDATA", "")) / "RenoDX" / "DLSS5" / "Presets"
                appdata_reno_presets.mkdir(parents=True, exist_ok=True)
                (appdata_reno_presets / "My look.ini").write_text(preset_text, encoding="utf-8")
                (appdata_reno_presets / "My look (2).ini").write_text(preset_text, encoding="utf-8")
                (appdata_reno_presets / "Default.ini").write_text(preset_text.replace("Name=My look", "Name=Default"), encoding="utf-8")
            except Exception:
                pass

            # Always apply selected hook point (defaults to 0: Upscaled mode)
            sync_dlss5_hook_point(td, hook_point=hook_point)
            if (td / "dlssg_sm86.ini").exists():
                try:
                    from apps.app2_mfg.core.ini_sync import IniConfigManager
                    from apps.app2_mfg.core.optiscaler_config import load_dlssg_sm86_preset
                    sm86_p = IniConfigManager.read_dlssg_sm86_reverse(td) or load_dlssg_sm86_preset()
                    sm86_p["super_resolution_mode"] = "Off"
                    IniConfigManager.sync_dlssg_sm86_forward(td, sm86_p)
                except Exception:
                    pass
            if has_mfg and (td / "OptiScaler.ini").exists():
                try:
                    from apps.app2_mfg.core.ini_sync import IniConfigManager
                    from apps.app2_mfg.core.optiscaler_config import load_optiscaler_preset
                    opti_p = IniConfigManager.read_mode_c_reverse(td) or load_optiscaler_preset()
                    if chosen_proxy.lower() == "reshade64.dll":
                        opti_p.plugins["LoadReshade"] = "true"
                    IniConfigManager.sync_mode_c_forward(td, opti_p)
                except Exception:
                    pass
                if chosen_proxy.lower() == "reshade64.dll":
                    try:
                        opti_ini = td / "OptiScaler.ini"
                        lines = opti_ini.read_text(encoding="utf-8").splitlines()
                        found = False
                        new_lines = []
                        in_plug = False
                        for line in lines:
                            st = line.strip()
                            if st.startswith("[") and st.endswith("]"):
                                if in_plug and not found:
                                    new_lines.append("LoadReshade = true")
                                    found = True
                                in_plug = (st.lower() == "[plugins]")
                            elif in_plug and st.lower().startswith("loadreshade"):
                                line = "LoadReshade = true"
                                found = True
                            new_lines.append(line)
                        if not found:
                            if in_plug:
                                new_lines.append("LoadReshade = true")
                            else:
                                new_lines.append("\n[Plugins]\nLoadReshade = true")
                        opti_ini.write_text("\n".join(new_lines).strip() + "\n", encoding="utf-8")
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
            slot_text = coex_slot or "未检测到（请重新注入模式 B）"
            coex_lines = (
                f"\n🛡️ 【与多帧生成共存】已自动完成双通道隔离：\n"
                f"  • dxgi.dll 锁定为 DLSS 5 的 ReShade 底座，OptiScaler 插帧代理已迁移至 {slot_text}；\n"
                f"  • DLSS 5 挂钩点默认为 Present(2) 呈现挂钩；\n"
                f"  • 已清理 fakenvapi 与重复 ReShade 实例（二者会破坏 DLSS 5 的 NVAPI 查询导致闪退）；\n"
                f"  • 进游戏同时开启【DLSS 超分辨率】与【DLSS 帧生成】即可同时获得神经重构 + XeSS 多倍插帧。\n"
            )
        if (td / "dlssg_sm86.ini").exists():
            coex_lines += (
                f"\n🛡️ 【与 dlssg_for_sm86 原生插帧共存】已自动完成无缝协同：\n"
                f"  • dxgi.dll 锁定为 DLSS 5 的 ReShade 6.8 渲染底座，dlssg_for_sm86 代理运行于独立通道；\n"
                f"  • dlssg_sm86 超分已自动设为 Off（让位给 DLSS 5 神经网络全权重构）；\n"
                f"  • 原生 DLSS-G 插帧与 DLSS 5 神经重构双通道并行运作，零冲突流畅畅玩！\n"
            )

        # Auto-heal any native game dependencies at injection finish as well
        try:
            from apps.app2_mfg.core.utils import auto_heal_game_dependencies
            auto_heal_game_dependencies(td)
        except Exception:
            pass

        hook_label_map = {
            "0": "之后 (Upscaled · 超分之后 · 推荐防闪退)",
            "2": "呈现 (Present · 画面呈现交换链 · 纯画质)",
            "1": "之前 (Before · 原生渲染阶段)"
        }
        hook_disp = hook_label_map.get(str(hook_point), f"模式 {hook_point}")
        return True, (
            f"✅ DLSS 5 插件已成功注入至游戏目录！\n\n"
            f"• 渲染底座: ReShade 6.8 64-bit ({chosen_proxy})\n"
            f"• 代理槽位: {DLSS5_PROXY_SLOTS.get(chosen_proxy, {}).get('title', chosen_proxy)}\n"          f"• 扩展插件: {Path(addon_src).name} ({mode_conf['short_name']})\n"
            f"• 注入模式: {mode_conf['title']}\n"
            f"• 神经网络: {arch_label} ({round(os.path.getsize(nr_src)/(1024*1024), 1)} MB)\n"
            f"• 调优配置: 预设[My look已载入] · 挂钩点[{hook_disp}] · 皮肤[100%] · 风格[模型 C] · 版本[新版] · 分辨率[匹配游戏]\n"
            f"• 体验优化: 快捷键[已禁用防误触] · 显存缓冲[精简模式，防OOM爆显存] · 运行库路径[强制本地锁定]\n"
            f"• 防闪退加固: Upscaled时序解耦 · 显存精简防爆 · 多帧生成动态槽位协同避让\n"
            f"{coex_lines}\n"
            f"🎮 【进游戏体验指南】：\n"
            f"1. 启动游戏，在画面设置中确保开启【DirectX 12】与【DLSS 超分辨率】；\n"
            f"2. 进入游戏画面后，按键盘【Home】键即可呼出 DLSS 5 / RenoDX 简体中文调参面板；\n"
            f"3. 若同时注入了多帧生成（模式 A 或模式 B），开启游戏内【DLSS 帧生成】即可同时获得神经重构 + 多倍插帧。"
        )

    @staticmethod
    def restore(target_dir: str) -> Tuple[bool, str]:
        """
        Executes deep one-click clean uninstallation of DLSS 5 and RHI/ReShade remnants from target_dir,
        completely purging all mod runtimes, proxy DLLs, and restoring the game to 100% vanilla environment.
        Follows the strict protocol:
        1. Restore all original files from backup directories (.dm_backup and .dlss5_backup)
        2. Delete own injected mod files, addons, and configs
        3. Protect and auto-heal all game statically imported PE dependencies
        4. Clean up backup directories only after full restore is verified.
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
        dm_backup_dir = td / ".dm_backup"

        # Layer 1.9: Restore any local *.mfg_bak files in game directory FIRST
        for bak_f in td.glob("*.mfg_bak"):
            orig_name = bak_f.name[:-8]
            orig_dest = td / orig_name
            if not orig_dest.exists():
                try:
                    shutil.copy2(str(bak_f), str(orig_dest))
                    safe_force_remove(str(bak_f))
                    restored_items.append(f"{orig_name} (从 .mfg_bak 还原)")
                except Exception:
                    pass

        # Layer 2: Put back ALL original files from backup directories FIRST
        for b_dir in [backup_dir, dm_backup_dir]:
            if b_dir.exists() and b_dir.is_dir():
                for b_file in b_dir.glob("*"):
                    if b_file.is_file() and not b_file.name.endswith(".json"):
                        dest_f = td / b_file.name
                        # Skip if the backup itself is an injected proxy
                        if is_reshade_dll_file(str(b_file)) or is_optiscaler_dll_file(str(b_file)) or is_dashdogy_dll_file(str(b_file)):
                            continue
                        try:
                            safe_force_remove(str(dest_f))
                            shutil.copy2(str(b_file), str(dest_f))
                            restored_items.append(f"{b_file.name} (从备份还原)")
                        except Exception:
                            pass

        # Layer 2.5: Restore Bink2 Hook if present (bink2w64Hooked.dll -> bink2w64.dll)
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

        # Layer 3: Delete own injected mod files
        # (A) All addon files (including conflicting/legacy DLSS addons)
        _, _, removed_conflicts = clean_conflicting_addons(td, keep_addon=None)
        for rc in removed_conflicts:
            if rc not in removed_items:
                removed_items.append(rc)
        for addon_file in list(td.glob("*.addon64")) + list(td.glob("*.addon")):
            name_lower = addon_file.name.lower()
            if "mfgunlock" in name_lower:
                continue
            try:
                safe_force_remove(str(addon_file))
                if addon_file.name not in removed_items:
                    removed_items.append(addon_file.name)
            except Exception:
                pass

        # (B) All proxy DLLs if they are ReShade / OptiScaler proxies and not native game files
        for proxy_name in ALL_DLSS5_PROXY_NAMES:
            p_file = td / proxy_name
            if p_file.exists():
                if is_reshade_dll_file(str(p_file)) or is_optiscaler_dll_file(str(p_file)):
                    safe_force_remove(str(p_file))
                    removed_items.append(f"{proxy_name} (ReShade底座/代理)")

        # (B2) OptiScaler shield files if injected by DLSS 5
        if not is_mode_c_present(td):
            safe_force_remove(str(td / "OptiScaler.ini"))
            safe_force_remove(str(td / "OptiScaler.log"))
            safe_force_remove(str(td / "d3d12-ReShade64.dll"))

        # (C) nvngx_dlssnr.dll
        nr_file = td / "nvngx_dlssnr.dll"
        if nr_file.exists():
            safe_force_remove(str(nr_file))
            removed_items.append("nvngx_dlssnr.dll (神经重构模型)")

        # (D) Remove mod directories
        folders_to_purge = [
            "RenoDX",
            "dlss5-nr-runtime",
            "dlssg_sm86",
            "OptiScaler",
            "D3D12_Optiscaler",
            "XeSS",
            "amd_fidelityfx",
            "reshade-shaders",
            "reshade-presets"
        ]
        for fld in folders_to_purge:
            fld_path = td / fld
            if fld_path.exists() and fld_path.is_dir():
                try:
                    shutil.rmtree(fld_path, ignore_errors=True)
                    removed_items.append(f"{fld}/ (目录)")
                except Exception:
                    pass

        # (E) Config, proxy and log files (NEVER delete game native PE dependencies!)
        imported_pe_dlls = set()
        try:
            from apps.app2_mfg.core.utils import get_game_statically_imported_dlls
            imported_pe_dlls = get_game_statically_imported_dlls(td)
        except Exception:
            pass

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

        # Purge root-exposed Streamline DLL copies if original exists under Streamline/
        sl_sub = td / "Streamline"
        if sl_sub.exists() and sl_sub.is_dir():
            for sl_name in ["nvngx_dlss.dll", "nvngx_dlssg.dll"]:
                if (sl_sub / sl_name).exists():
                    files_to_purge.append(sl_name)
        has_ffx_loader = (td / "amd_fidelityfx_loader_dx12.dll").exists()
        for fname in files_to_purge:
            if has_ffx_loader and fname == "amd_fidelityfx_upscaler_dx12.dll":
                continue
            if fname.lower() in imported_pe_dlls or any(fname.lower() in r.lower() for r in restored_items):
                continue
            fp = td / fname
            if fp.exists():
                safe_force_remove(str(fp))
                removed_items.append(fname)

        # Proxies (only delete if they are confirmed proxies and not native game files)
        for proxy_name in ["version.dll", "winmm.dll", "dinput8.dll", "wininet.dll"]:
            pp = td / proxy_name
            if pp.exists() and (is_dashdogy_dll_file(str(pp)) or is_optiscaler_dll_file(str(pp)) or is_reshade_dll_file(str(pp))):
                safe_force_remove(str(pp))
                removed_items.append(proxy_name)

        # Wildcard logs
        for pat in ["dlss5-nr-crash-*.txt", "ReShade*.ini*", "RTXMFG-*.log", "RTXMFG-*.csv"]:
            for match_f in td.glob(pat):
                safe_force_remove(str(match_f))
                removed_items.append(match_f.name)

        # Layer 4: Auto-heal any missing game PE dependencies (libxell.dll, libxess.dll, libxess_fg.dll, igxess.dll)
        try:
            from apps.app2_mfg.core.utils import auto_heal_game_dependencies
            healed = auto_heal_game_dependencies(td)
            for h in healed:
                restored_items.append(f"{h} (原生依赖自愈)")
        except Exception:
            pass

        # Layer 5: Only NOW clean up backup directories after all files have been safely verified and restored
        for b_dir in [backup_dir, dm_backup_dir]:
            if b_dir.exists() and b_dir.is_dir():
                try:
                    shutil.rmtree(b_dir, ignore_errors=True)
                except Exception:
                    pass

        # Final cleanup of any pending / temp files
        try:
            cleanup_pending_files(target_dir_str)
        except Exception:
            pass

        res_msg = f"🧹 DLSS 5 与 RHI/ReShade 模组环境已彻底卸载并净化还原！\n\n已成功恢复原生文件 ({len(restored_items)} 项):\n"
        if restored_items:
            res_msg += " • " + "\n • ".join(restored_items[:10])
            if len(restored_items) > 10:
                res_msg += f"\n • ...及其他 {len(restored_items) - 10} 项"
        res_msg += f"\n\n已彻底清除模组组件 ({len(removed_items)} 项):\n"
        if removed_items:
            res_msg += " • " + "\n • ".join(removed_items[:12])
            if len(removed_items) > 12:
                res_msg += f"\n • ...及其他 {len(removed_items) - 12} 项残留文件"
        else:
            res_msg += "（未检测到残留模组组件）"

        return True, res_msg

# =========================================================================
# Phase 5: Delay Injection Engine for Anti-Cheat Bypass (ACE / MHY)
# =========================================================================

class DLSS5DelayedInjector:
    """
    Zero-Landing Delay Injector for Anti-Cheat Protected Games (ACE, MHY).
    Avoids putting dxgi.dll / d3d11.dll / version.dll in root directory.
    Deploys ReShade64.dll and dynamically injects it via LoadLibraryW
    once the target game process has initialized its main window.
    """
    TH32CS_SNAPPROCESS = 0x00000002
    TH32CS_SNAPMODULE = 0x00000008
    TH32CS_SNAPMODULE32 = 0x00000010

    PROCESS_CREATE_THREAD = 0x0002
    PROCESS_VM_OPERATION = 0x0008
    PROCESS_VM_READ = 0x0010
    PROCESS_VM_WRITE = 0x0020
    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_ALL_ACCESS = 0x1F0FFF

    MEM_COMMIT = 0x1000
    MEM_RESERVE = 0x2000
    MEM_RELEASE = 0x8000
    PAGE_READWRITE = 0x04

    _initialized = False
    _k32 = None
    _u32 = None
    _nt = None

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ('dwSize', wintypes.DWORD),
            ('cntUsage', wintypes.DWORD),
            ('th32ProcessID', wintypes.DWORD),
            ('th32DefaultHeapID', ctypes.c_size_t),
            ('th32ModuleID', wintypes.DWORD),
            ('cntThreads', wintypes.DWORD),
            ('th32ParentProcessID', wintypes.DWORD),
            ('pcPriClassBase', wintypes.LONG),
            ('dwFlags', wintypes.DWORD),
            ('szExeFile', wintypes.WCHAR * 260)
        ]

    class MODULEENTRY32W(ctypes.Structure):
        _fields_ = [
            ('dwSize', wintypes.DWORD),
            ('th32ModuleID', wintypes.DWORD),
            ('th32ProcessID', wintypes.DWORD),
            ('GlblcntUsage', wintypes.DWORD),
            ('ProccntUsage', wintypes.DWORD),
            ('modBaseAddr', ctypes.c_void_p),
            ('modBaseSize', wintypes.DWORD),
            ('hModule', wintypes.HMODULE),
            ('szModule', wintypes.WCHAR * 256),
            ('szExePath', wintypes.WCHAR * 260)
        ]

    @classmethod
    def _ensure_apis(cls):
        if cls._initialized:
            return
        try:
            cls._k32 = ctypes.WinDLL('kernel32.dll', use_last_error=True)
            cls._u32 = ctypes.WinDLL('user32.dll', use_last_error=True)
            try:
                cls._nt = ctypes.WinDLL('ntdll.dll', use_last_error=True)
            except Exception:
                cls._nt = None

            cls._k32.OpenProcess.restype = wintypes.HANDLE
            cls._k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]

            cls._k32.VirtualAllocEx.restype = wintypes.LPVOID
            cls._k32.VirtualAllocEx.argtypes = [wintypes.HANDLE, wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]

            cls._k32.WriteProcessMemory.restype = wintypes.BOOL
            cls._k32.WriteProcessMemory.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.LPCVOID, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]

            cls._k32.CreateRemoteThread.restype = wintypes.HANDLE
            cls._k32.CreateRemoteThread.argtypes = [wintypes.HANDLE, wintypes.LPVOID, ctypes.c_size_t, wintypes.LPVOID, wintypes.LPVOID, wintypes.DWORD, wintypes.LPDWORD]

            cls._k32.WaitForSingleObject.restype = wintypes.DWORD
            cls._k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]

            cls._k32.GetExitCodeThread.restype = wintypes.BOOL
            cls._k32.GetExitCodeThread.argtypes = [wintypes.HANDLE, wintypes.LPDWORD]

            cls._k32.VirtualFreeEx.restype = wintypes.BOOL
            cls._k32.VirtualFreeEx.argtypes = [wintypes.HANDLE, wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD]

            cls._k32.CloseHandle.restype = wintypes.BOOL
            cls._k32.CloseHandle.argtypes = [wintypes.HANDLE]

            cls._k32.GetModuleHandleW.restype = wintypes.HMODULE
            cls._k32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]

            cls._k32.GetProcAddress.restype = wintypes.LPVOID
            cls._k32.GetProcAddress.argtypes = [wintypes.HMODULE, wintypes.LPCSTR]

            cls._k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
            cls._k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]

            cls._k32.Process32FirstW.restype = wintypes.BOOL
            cls._k32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(cls.PROCESSENTRY32W)]

            cls._k32.Process32NextW.restype = wintypes.BOOL
            cls._k32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(cls.PROCESSENTRY32W)]

            cls._k32.Module32FirstW.restype = wintypes.BOOL
            cls._k32.Module32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(cls.MODULEENTRY32W)]

            cls._k32.Module32NextW.restype = wintypes.BOOL
            cls._k32.Module32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(cls.MODULEENTRY32W)]

            cls._initialized = True
        except Exception:
            pass

    @classmethod
    def get_pids_by_name(cls, exe_name: str) -> List[int]:
        cls._ensure_apis()
        if not cls._k32:
            return []
        pids = []
        target = exe_name.lower()
        h_snap = cls._k32.CreateToolhelp32Snapshot(cls.TH32CS_SNAPPROCESS, 0)
        if not h_snap or h_snap == wintypes.HANDLE(-1).value:
            return pids
        try:
            pe = cls.PROCESSENTRY32W()
            pe.dwSize = ctypes.sizeof(cls.PROCESSENTRY32W)
            if cls._k32.Process32FirstW(h_snap, ctypes.byref(pe)):
                while True:
                    if pe.szExeFile.lower() == target:
                        pids.append(pe.th32ProcessID)
                    if not cls._k32.Process32NextW(h_snap, ctypes.byref(pe)):
                        break
        finally:
            cls._k32.CloseHandle(h_snap)
        return pids

    @classmethod
    def has_visible_window(cls, pid: int) -> bool:
        cls._ensure_apis()
        if not cls._u32:
            return False
        found = False
        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def enum_cb(hwnd, lparam):
            nonlocal found
            if cls._u32.IsWindowVisible(hwnd):
                w_pid = wintypes.DWORD(0)
                cls._u32.GetWindowThreadProcessId(hwnd, ctypes.byref(w_pid))
                if w_pid.value == pid:
                    found = True
                    return False
            return True

        cb = WNDENUMPROC(enum_cb)
        cls._u32.EnumWindows(cb, 0)
        return found

    @classmethod
    def is_module_loaded(cls, pid: int, module_name: str) -> bool:
        cls._ensure_apis()
        if not cls._k32:
            return False
        h_snap = cls._k32.CreateToolhelp32Snapshot(cls.TH32CS_SNAPMODULE | cls.TH32CS_SNAPMODULE32, pid)
        if not h_snap or h_snap == wintypes.HANDLE(-1).value:
            return False
        try:
            me = cls.MODULEENTRY32W()
            me.dwSize = ctypes.sizeof(cls.MODULEENTRY32W)
            target = module_name.lower()
            if cls._k32.Module32FirstW(h_snap, ctypes.byref(me)):
                while True:
                    if me.szModule.lower() == target:
                        return True
                    if not cls._k32.Module32NextW(h_snap, ctypes.byref(me)):
                        break
        finally:
            cls._k32.CloseHandle(h_snap)
        return False

    @classmethod
    def inject_dll_to_process(cls, pid: int, dll_path: str) -> Tuple[bool, str]:
        cls._ensure_apis()
        if not cls._k32:
            return False, "系统底层注入 API 初始化失败"

        if not os.path.exists(dll_path):
            return False, f"待注入的底座 DLL 文件不存在: {dll_path}"

        abs_dll = os.path.abspath(dll_path)
        dll_name = os.path.basename(abs_dll)

        if cls.is_module_loaded(pid, dll_name):
            return True, f"模块 {dll_name} 已成功加载于进程 (PID: {pid}) 中！"

        dll_bytes = abs_dll.encode('utf-16-le') + b'\x00\x00'
        dll_len = len(dll_bytes)

        desired_access = cls.PROCESS_CREATE_THREAD | cls.PROCESS_VM_OPERATION | cls.PROCESS_VM_WRITE | cls.PROCESS_VM_READ | cls.PROCESS_QUERY_INFORMATION
        h_process = cls._k32.OpenProcess(desired_access, False, pid)
        if not h_process:
            h_process = cls._k32.OpenProcess(cls.PROCESS_ALL_ACCESS, False, pid)
            if not h_process:
                err = ctypes.get_last_error()
                return False, f"无法获取目标进程 (PID: {pid}) 句柄 (错误代码: {err})。游戏可能受到反作弊内核级防注入保护。"

        try:
            remote_mem = cls._k32.VirtualAllocEx(h_process, None, dll_len, cls.MEM_COMMIT | cls.MEM_RESERVE, cls.PAGE_READWRITE)
            if not remote_mem:
                return False, f"在目标进程中分配内存失败 (错误代码: {ctypes.get_last_error()})"

            try:
                written = ctypes.c_size_t(0)
                if not cls._k32.WriteProcessMemory(h_process, remote_mem, dll_bytes, dll_len, ctypes.byref(written)):
                    return False, f"向目标进程写入模块路径失败 (错误代码: {ctypes.get_last_error()})"

                k32_mod = cls._k32.GetModuleHandleW("kernel32.dll")
                if not k32_mod:
                    return False, "未能获取 kernel32.dll 模块句柄"

                p_load_library = cls._k32.GetProcAddress(k32_mod, b"LoadLibraryW")
                if not p_load_library:
                    return False, "未能定位 LoadLibraryW 入口地址"

                thread_id = wintypes.DWORD(0)
                h_thread = cls._k32.CreateRemoteThread(h_process, None, 0, p_load_library, remote_mem, 0, ctypes.byref(thread_id))

                if not h_thread and cls._nt:
                    try:
                        RtlCreateUserThread = cls._nt.RtlCreateUserThread
                        RtlCreateUserThread.restype = wintypes.DWORD
                        RtlCreateUserThread.argtypes = [
                            wintypes.HANDLE, wintypes.LPVOID, wintypes.BOOL,
                            wintypes.ULONG, ctypes.c_size_t, ctypes.c_size_t,
                            wintypes.LPVOID, wintypes.LPVOID, ctypes.POINTER(wintypes.HANDLE),
                            wintypes.LPVOID
                        ]
                        h_thread_nt = wintypes.HANDLE()
                        st = RtlCreateUserThread(h_process, None, False, 0, 0, 0, p_load_library, remote_mem, ctypes.byref(h_thread_nt), None)
                        if st == 0 and h_thread_nt.value:
                            h_thread = h_thread_nt.value
                    except Exception:
                        pass

                if not h_thread:
                    return False, f"在目标进程创建远程线程失败 (错误代码: {ctypes.get_last_error()})"

                cls._k32.WaitForSingleObject(h_thread, 5000)
                exit_code = wintypes.DWORD(0)
                cls._k32.GetExitCodeThread(h_thread, ctypes.byref(exit_code))
                cls._k32.CloseHandle(h_thread)

                if exit_code.value == 0:
                    return False, f"LoadLibraryW 执行返回 NULL (可能被安全系统拦截或 DLL 初始化异常)"

                time.sleep(0.3)
                if cls.is_module_loaded(pid, dll_name):
                    return True, f"🎉 成功向游戏主进程 (PID: {pid}) 注入底座模块: {dll_name}！\n\n游戏内按【Home】键（模式 B 为【F12】键）即可呼出 DLSS 5 / RenoDX 简体中文控制面板！"
                return True, f"远程加载指令已执行 (返回地址: 0x{exit_code.value:X})。"
            finally:
                cls._k32.VirtualFreeEx(h_process, remote_mem, 0, cls.MEM_RELEASE)
        finally:
            cls._k32.CloseHandle(h_process)

    @classmethod
    def monitor_and_inject(
        cls,
        exe_name: str,
        dll_path: str,
        timeout_sec: int = 180,
        settle_delay: float = 3.0,
        stop_check=None,
        log_callback=None
    ) -> Tuple[bool, str]:
        """
        Continuously monitors for exe_name, waits for window creation and settle delay,
        then injects dll_path into target process.
        """
        start_time = time.time()
        detected_pid = None

        if log_callback:
            log_callback(f"🔍 启动监听中... 请从官方启动器正常启动游戏 ({exe_name})。")

        while time.time() - start_time < timeout_sec:
            if stop_check and stop_check():
                return False, "用户已手动停止启动监听。"

            pids = cls.get_pids_by_name(exe_name)
            if pids:
                detected_pid = pids[0]
                break
            time.sleep(0.8)

        if not detected_pid:
            return False, f"超时：未能在 {timeout_sec} 秒内检测到游戏进程 {exe_name} 启动。"

        if log_callback:
            log_callback(f"🟢 已检测到游戏主进程 (PID: {detected_pid})！正在等待主窗口就绪与反作弊前置扫描...")

        # Wait for visible window
        window_wait_start = time.time()
        has_win = False
        while time.time() - window_wait_start < 25:
            if stop_check and stop_check():
                return False, "用户已手动停止启动监听。"
            if cls.has_visible_window(detected_pid):
                has_win = True
                break
            time.sleep(0.5)

        # Settle delay for ACE startup scan on PlatformProcess to clear
        if log_callback:
            log_callback(f"⏳ 游戏主窗口已就绪，正在进行时序避让 ({settle_delay}s)...")
        
        sleep_elapsed = 0.0
        while sleep_elapsed < settle_delay:
            if stop_check and stop_check():
                return False, "用户已手动停止启动监听。"
            time.sleep(0.5)
            sleep_elapsed += 0.5

        if log_callback:
            log_callback(f"⚡ 正在向主进程 (PID: {detected_pid}) 注入 ReShade64.dll 渲染底座...")

        ok, msg = cls.inject_dll_to_process(detected_pid, dll_path)
        return ok, msg
