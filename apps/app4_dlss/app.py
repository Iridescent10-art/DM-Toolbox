# -*- coding: utf-8 -*-
"""
App 4: 全架构超分与多帧生成 HUD 指示器 (DLSS / XeSS / FSR / MFG) - v1.2.6
========================================================================
提供全能跨架构超分辨率与多帧生成水印/OSD指示器：
1. NVIDIA DLSS 官方底层超分与 DLSS-G 帧生成水印 (ShowDlssIndicator=1024)
2. OptiScaler v0.9.4 性能叠加：超分引擎 / 渲染→输出分辨率 / FPS ([Menu] ShowFps)
3. 帧生成 Full 叠加：实时/插帧后双 FPS 与 FG 管线 (FpsOverlayType=4)
4. ReShade 帧率监控 ([OVERLAY] ShowFps / ShowFrameTime)

所有 INI 开关只写入「真实游戏目录」（来自模式 C 修补记录 / 游戏库缓存），
绝不再写入工具箱自带的模板，避免“开关显示已开启但游戏内毫无变化”。

UI 规范：
- 严格继承 DMBaseWindow (DM Design System Core SDK)
- Windows DWM 硬件级无锯齿圆角抗锯齿合成 (DWMWCP_ROUND=2)
- 统一右下角双斜线 // 缩放手柄 (DMSizeGrip)
- 包含总控开关与 4 个独立分项控制卡片
- 包含超分比例与插帧倍率-显示器刷新率匹配速查表
"""

import os
import sys
import json
import time
import winreg
import ctypes
from ctypes import wintypes
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QIcon, QFont, QPixmap, QColor
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QMessageBox, QGridLayout,
    QSizePolicy
)

# Root dir resolution
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dm_ui_core import (
    DMBaseWindow, DMCardFrame, DMFooterBar, DMSizeGrip, DMThemeManager,
    apply_dm_window_frame, get_global_theme, set_global_theme,
    SCROLLBAR_LIGHT_QSS, SCROLLBAR_DARK_QSS
)
from common.ui_theme import ModernProgressDialog
from common.config_manager import init_app_config, get_app_config_path

APP_NAME = "app4_dlss"
REG_KEY = r"SOFTWARE\NVIDIA Corporation\Global\NGXCore"
REG_VAL = "ShowDlssIndicator"


# =========================================================================
# Windows UAC Elevation Helper
# =========================================================================
class SHELLEXECUTEINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("fMask", wintypes.ULONG),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", wintypes.LPVOID),
        ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", wintypes.HKEY),
        ("dwHotKey", wintypes.DWORD),
        ("hIconOrMonitor", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
    ]


# =========================================================================
# INI File Discovery and Parsing Utilities
# =========================================================================
# =========================================================================
# Game Config Discovery (real games only - bundled templates are never touched)
# =========================================================================
def _is_inside_toolbox(path: Path) -> bool:
    """True when the path lives inside the toolbox folder (templates / defaults / dist)."""
    try:
        path.resolve().relative_to(ROOT_DIR.resolve())
        return True
    except Exception:
        return False


_GAME_DIRS_TTL = 5.0
_GAME_DIRS_CACHE: Dict[str, Any] = {"ts": 0.0, "dirs": []}
_RESHADE_BASE_CACHE: Dict[str, Tuple[float, bool]] = {}


def get_known_game_dirs(force_refresh: bool = False) -> List[Path]:
    """
    Resolve real game executable folders from the shared app2 game cache.
    The last selected game is returned first; bundled templates inside the toolbox
    folder are filtered out so shipped assets can never be modified again.
    """
    now = time.time()
    if (not force_refresh and _GAME_DIRS_CACHE["dirs"]
            and now - _GAME_DIRS_CACHE["ts"] < _GAME_DIRS_TTL):
        return list(_GAME_DIRS_CACHE["dirs"])

    dirs: List[Path] = []
    seen = set()

    def add_dir(value) -> None:
        if not value:
            return
        try:
            p = Path(value)
        except Exception:
            return
        key = str(p).lower()
        if key in seen or _is_inside_toolbox(p) or not p.exists():
            return
        seen.add(key)
        dirs.append(p)

    try:
        from apps.app2_mfg.core.game_cache import GameCacheManager
        games, last_exe = GameCacheManager.get_cached_games()
    except Exception:
        games, last_exe = [], None

    if last_exe:
        add_dir(Path(last_exe).parent)
    for game in games:
        add_dir(getattr(game, "target_dir", "") or "")
        exe = getattr(game, "exe_path", "") or ""
        if exe:
            add_dir(Path(exe).parent)

    _GAME_DIRS_CACHE["ts"] = now
    _GAME_DIRS_CACHE["dirs"] = list(dirs)
    return dirs


def get_game_display_name(game_dir: Path) -> str:
    """Human-readable game name for a target directory (falls back to folder name)."""
    try:
        from apps.app2_mfg.core.game_cache import GameCacheManager
        games, _ = GameCacheManager.get_cached_games()
        target = str(game_dir).lower()
        for game in games:
            td = str(getattr(game, "target_dir", "") or "").lower()
            if td and td == target:
                name = getattr(game, "name", "") or ""
                if name:
                    return name
    except Exception:
        pass
    return game_dir.name


def find_all_optiscaler_inis() -> List[Path]:
    """Real game OptiScaler.ini files only (never bundled template copies)."""
    inis: List[Path] = []
    seen = set()
    for game_dir in get_known_game_dirs():
        candidate = game_dir / "OptiScaler.ini"
        if not candidate.exists():
            continue
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        inis.append(candidate)
    return inis


def _has_reshade_base(game_dir: Path) -> bool:
    """Detect an installed ReShade proxy next to the game executable (cached 30s).

    ReShade 6.8 stores its signature around offset ~4.3 MB, so reading only the
    first 4 MB missed `dxgi.dll` and left this indicator permanently disabled.
    """
    key = str(game_dir).lower()
    now = time.time()
    cached = _RESHADE_BASE_CACHE.get(key)
    if cached and now - cached[0] < 30:
        return cached[1]

    found = False
    for dll_name in ("ReShade64.dll", "dxgi.dll", "d3d9.dll", "opengl32.dll"):
        dll = game_dir / dll_name
        if not dll.exists():
            continue
        try:
            with open(dll, "rb") as f:
                data = f.read(16 * 1024 * 1024)
            if b"ReShade" in data or b"reshade" in data or b"crosire" in data.lower():
                found = True
                break
        except Exception:
            continue
    _RESHADE_BASE_CACHE[key] = (now, found)
    return found


def find_all_reshade_inis() -> List[Path]:
    """Real game ReShade.ini files whose folder actually has a ReShade base installed."""
    inis: List[Path] = []
    seen = set()
    for game_dir in get_known_game_dirs():
        candidate = game_dir / "ReShade.ini"
        if not candidate.exists() or not _has_reshade_base(game_dir):
            continue
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        inis.append(candidate)
    return inis


def read_simple_ini(file_path: Path) -> Dict[str, Dict[str, str]]:
    """Simple parser returning {SECTION_UPPER: {KEY_UPPER: value}}."""
    result: Dict[str, Dict[str, str]] = {}
    if not file_path.exists():
        return result
    try:
        current_sec = ""
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith(";") or s.startswith("#"):
                    continue
                if s.startswith("[") and "]" in s:
                    current_sec = s[1:s.index("]")].strip().upper()
                    if current_sec not in result:
                        result[current_sec] = {}
                    continue
                if "=" in s and current_sec:
                    k, v = s.split("=", 1)
                    result[current_sec][k.strip().upper()] = v.strip()
    except Exception:
        pass
    return result


def write_ini_key_values(file_path: Path, section_name: str, key_values: Dict[str, Any]) -> bool:
    """Safely updates or injects keys in the given section while preserving formatting."""
    path = Path(file_path)
    lines: List[str] = []
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception:
            lines = []

    sec_header = f"[{section_name.strip()}]".lower()
    in_target_sec = False
    sec_found = False
    written_keys = set()
    new_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and "]" in stripped:
            if in_target_sec:
                for k, v in key_values.items():
                    if k.upper() not in written_keys:
                        new_lines.append(f"{k}={v}\n")
                        written_keys.add(k.upper())
                in_target_sec = False
            cur_sec = stripped[0:stripped.find("]") + 1].lower()
            if cur_sec == sec_header:
                in_target_sec = True
                sec_found = True
            new_lines.append(line)
            continue

        if in_target_sec and "=" in line and not stripped.startswith(";") and not stripped.startswith("#"):
            k_part, _ = line.split("=", 1)
            k_clean = k_part.strip().upper()
            matched_k = None
            for key_to_write in key_values:
                if key_to_write.upper() == k_clean:
                    matched_k = key_to_write
                    break
            if matched_k:
                new_lines.append(f"{matched_k}={key_values[matched_k]}\n")
                written_keys.add(matched_k.upper())
                continue

        new_lines.append(line)

    if in_target_sec:
        for k, v in key_values.items():
            if k.upper() not in written_keys:
                new_lines.append(f"{k}={v}\n")
                written_keys.add(k.upper())
    elif not sec_found:
        new_lines.append(f"\n[{section_name.strip()}]\n")
        for k, v in key_values.items():
            new_lines.append(f"{k}={v}\n")

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", errors="ignore") as f:
            f.writelines(new_lines)
        return True
    except Exception:
        return False


# =========================================================================
# App Config Helpers
# =========================================================================
DEFAULT_CONFIG = {
    "dlss_watermark": False,
    "xess_fsr_osd": False,
    "mfg_ratio_hud": False,
    "reshade_overlay": False
}


def load_app_settings() -> Dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    try:
        cfg_path = init_app_config(APP_NAME, "settings.json", default_dict=DEFAULT_CONFIG)
        if cfg_path.exists():
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                cfg.update(data)
    except Exception:
        pass
    return cfg


def save_app_settings(cfg: Dict[str, Any]):
    try:
        cfg_path = get_app_config_path(APP_NAME, "settings.json")
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
    except Exception:
        pass


# =========================================================================
# Dimension A: NVIDIA DLSS 官方底层超分水印
# =========================================================================
def get_dlss_indicator_status() -> bool:
    """Reads ShowDlssIndicator from HKLM registry with 64-bit and standard views."""
    for access in (winreg.KEY_READ | winreg.KEY_WOW64_64KEY, winreg.KEY_READ):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REG_KEY, 0, access) as key:
                val, _ = winreg.QueryValueEx(key, REG_VAL)
                return int(val) == 1024 or int(val) == 1
        except Exception:
            continue
    return False


def set_dlss_indicator_status(enable: bool) -> Tuple[bool, str]:
    """Sets ShowDlssIndicator in HKLM registry with synchronous UAC elevation if needed."""
    target_val = 1024 if enable else 0

    # 1. Try direct write to 64-bit registry
    try:
        with winreg.CreateKeyEx(
            winreg.HKEY_LOCAL_MACHINE, REG_KEY, 0, winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY
        ) as key:
            winreg.SetValueEx(key, REG_VAL, 0, winreg.REG_DWORD, target_val)
        cfg = load_app_settings()
        cfg["dlss_watermark"] = enable
        save_app_settings(cfg)
        return True, "已成功写入 NVIDIA 注册表！"
    except PermissionError:
        pass
    except Exception:
        pass

    # 2. Try direct write to standard registry view
    try:
        with winreg.CreateKeyEx(
            winreg.HKEY_LOCAL_MACHINE, REG_KEY, 0, winreg.KEY_WRITE
        ) as key:
            winreg.SetValueEx(key, REG_VAL, 0, winreg.REG_DWORD, target_val)
        cfg = load_app_settings()
        cfg["dlss_watermark"] = enable
        save_app_settings(cfg)
        return True, "已成功写入 NVIDIA 注册表！"
    except PermissionError:
        pass
    except Exception:
        pass

    # 3. Synchronous elevation via reg.exe with WaitForSingleObject
    try:
        params = f'add "HKLM\\{REG_KEY}" /v {REG_VAL} /t REG_DWORD /d {target_val} /f /reg:64'
        sei = SHELLEXECUTEINFO()
        sei.cbSize = ctypes.sizeof(SHELLEXECUTEINFO)
        sei.fMask = 0x00000040  # SEE_MASK_NOCLOSEPROCESS
        sei.hwnd = None
        sei.lpVerb = "runas"
        sei.lpFile = "reg.exe"
        sei.lpParameters = params
        sei.nShow = 0  # SW_HIDE

        ok = ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(sei))
        if ok and sei.hProcess:
            ctypes.windll.kernel32.WaitForSingleObject(sei.hProcess, 10000)
            ctypes.windll.kernel32.CloseHandle(sei.hProcess)
            cfg = load_app_settings()
            cfg["dlss_watermark"] = enable
            save_app_settings(cfg)
            return True, "已通过管理员授权成功更新注册表！"
        else:
            ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", "reg.exe", params, None, 0)
            if ret > 32:
                time.sleep(0.6)
                cfg = load_app_settings()
                cfg["dlss_watermark"] = enable
                save_app_settings(cfg)
                return True, "已请求管理员权限更新注册表"
            else:
                return False, "用户取消了管理员权限请求"
    except Exception as e:
        return False, f"提权执行失败: {e}"


# =========================================================================
# Dimension B: OptiScaler 性能叠加 (超分引擎 / 渲染分辨率 / FPS)
#
# OptiScaler v0.9.4 removed the old ShowOsd/ShowHud/ShowFrameGen OSD keys
# (they are absent from OptiScaler.dll and only linger in a stale template).
# The supported HUD is [Menu] ShowFps + FpsOverlayType:
#   0 Just FPS | 1 Simple | 2 Detailed | 3 Detailed+Graph
#   4 Full     | 5 Full+Graph | 6 Reflex timings
# =========================================================================
OVERLAY_TYPE_DETAILED = "2"   # upscaler + render->output resolution + FPS
OVERLAY_TYPE_FULL = "4"       # adds generated FPS / FG pipeline / Reflex timings


def _read_menu_section(ini: Path) -> Dict[str, str]:
    return read_simple_ini(ini).get("MENU", {})


def get_xess_fsr_status() -> bool:
    """Performance overlay active = [Menu] ShowFps=true in a real game OptiScaler.ini."""
    for ini in find_all_optiscaler_inis():
        if _read_menu_section(ini).get("SHOWFPS", "").lower() in ("true", "1"):
            return True
    return False


def set_xess_fsr_status(enable: bool) -> Tuple[bool, str]:
    """Toggles OptiScaler's real v0.9.4 performance overlay for upscaler/resolution/FPS."""
    if not find_all_optiscaler_inis():
        return False, "未检测到已部署 OptiScaler 的游戏目录，请先在【模式 C】修补游戏后再开启。"
    if enable:
        _write_optiscaler_overlay(True, get_mfg_hud_status())
        hint = "\n(提示: 若游戏内看不到叠加，请确认游戏已用【模式 C】修补且 OptiScaler 已成功注入)"
        return True, f"已开启 OptiScaler 性能叠加（超分引擎 / 分辨率 / FPS）。{hint}"
    _write_optiscaler_overlay(False, False)
    return True, "已关闭 OptiScaler 性能叠加与帧生成叠加。"


# =========================================================================
# Dimension C: 帧生成 Full 叠加 (实时 / 插帧后双 FPS，可判断 2X/3X/4X)
# =========================================================================
def get_mfg_hud_status() -> bool:
    """Full overlay active = ShowFps=true and FpsOverlayType in Full modes."""
    for ini in find_all_optiscaler_inis():
        menu = _read_menu_section(ini)
        if menu.get("SHOWFPS", "").lower() in ("true", "1") and menu.get("FPSOVERLAYTYPE", "").strip() in ("4", "5", "6"):
            return True
    return False


def set_mfg_hud_status(enable: bool) -> Tuple[bool, str]:
    """Upgrades / downgrades the OptiScaler overlay to the Full (frame generation) mode."""
    if not find_all_optiscaler_inis():
        return False, "未检测到已部署 OptiScaler 的游戏目录，请先在【模式 C】修补游戏后再开启。"
    if enable:
        # Full mode implies the base overlay, so both badges light up.
        _write_optiscaler_overlay(True, True)
        return True, "已开启帧生成 Full 叠加（实时 / 插帧后双 FPS、FG 管线与 Reflex 延迟）。"
    _write_optiscaler_overlay(get_xess_fsr_status(), False)
    return True, "已切换回普通性能叠加（帧生成 Full 叠加关闭）。"


def _write_optiscaler_overlay(xess_on: bool, mfg_on: bool) -> int:
    """Write the resolved overlay profile into every real game OptiScaler.ini."""
    inis = find_all_optiscaler_inis()
    for ini in inis:
        write_ini_key_values(ini, "Menu", {
            "ShowFps": "true" if (xess_on or mfg_on) else "false",
            "FpsOverlayType": OVERLAY_TYPE_FULL if mfg_on else (OVERLAY_TYPE_DETAILED if xess_on else "0"),
            "FpsOverlayPos": "0",          # 0 = Top Left
            "FpsOverlayHorizontal": "true",
            "FpsScale": "1.0",
        })
    return len(inis)


# =========================================================================
# Dimension D: ReShade 实时帧率与延迟监控 (FPS & FrameTime)
# =========================================================================
def get_reshade_overlay_status() -> bool:
    """Reads ReShade [OVERLAY] ShowFps from real game ReShade.ini files."""
    for ini in find_all_reshade_inis():
        ov_sec = read_simple_ini(ini).get("OVERLAY", {})
        if ov_sec.get("SHOWFPS", "0").lower() in ("1", "true"):
            return True
    return False


def _remove_legacy_reshade_fps_keys(path: Path) -> None:
    """Remove the wrong-case `ShowFps` keys written by older builds.

    ReShade 6.8's real key is `ShowFPS` (capital FPS); an INI with `ShowFps` is
    parsed as unknown, which is why only the frame-time line appeared.
    """
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines(keepends=True)
    except Exception:
        return
    in_overlay = False
    out = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and "]" in stripped:
            in_overlay = stripped[1:stripped.index("]")].strip().upper() == "OVERLAY"
            out.append(line)
            continue
        if in_overlay and "=" in stripped and not stripped.startswith(";"):
            key = stripped.split("=", 1)[0].strip()
            if key == "ShowFps":  # wrong casing only; keep canonical ShowFPS
                continue
        out.append(line)
    try:
        path.write_text("".join(out), encoding="utf-8")
    except Exception:
        pass


def set_reshade_overlay_status(enable: bool) -> Tuple[bool, str]:
    """Updates ReShade FPS and FrameTime overlay setting (canonical `ShowFPS` key)."""
    inis = find_all_reshade_inis()
    if not inis:
        return False, "未检测到已安装 ReShade 底座的游戏，请先用【模式 B】完成 ReShade 安装。"
    val_num = "1" if enable else "0"
    for ini in inis:
        _remove_legacy_reshade_fps_keys(ini)
        write_ini_key_values(ini, "OVERLAY", {
            "ShowFPS": val_num,
            "ShowFrameTime": val_num
        })
    return True, f"已{'开启' if enable else '关闭'} ReShade 实时帧率与延迟监控！"


# =========================================================================
# 主窗口：全架构超分与插帧水印指示器 (DLSSIndicatorWindow)
# =========================================================================
class DLSSIndicatorWindow(DMBaseWindow):
    """
    全架构超分与插帧水印指示器主窗口。
    - 继承自标准 DMBaseWindow
    - 完美适配 Windows DWM 硬件圆角与日/夜主题无缝切换
    - 底部状态栏自带标准 DMSizeGrip (//) 缩放手柄
    - 提供总控开关与 4 大独立控制卡片
    """
    def __init__(self):
        super().__init__(
            title="DM工具箱 - 全架构超分与插帧水印指示器 (DLSS / XeSS / FSR / MFG)",
            width=920,
            height=680,
            icon_filename="dlss_icon.png"
        )
        self.setMinimumSize(860, 580)
        self.resize(920, 680)
        self.init_content()
        self.apply_theme()
        self.refresh_all_statuses()

        # Background timer to automatically refresh and synchronize status (1200ms)
        self.status_timer = QTimer(self)
        self.status_timer.setInterval(1200)
        self.status_timer.timeout.connect(self.auto_refresh_check)
        self.status_timer.start()

    def init_content(self):
        # 核心滚动区
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.viewport().setAutoFillBackground(False)

        container = QWidget()
        container.setObjectName("ScrollContainer")
        container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.container = container
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(24, 16, 24, 20)
        vbox.setSpacing(14)

        # 1. 头部说明横幅 (图1风格)
        banner = QFrame()
        banner.setObjectName("BannerCard")
        b_layout = QHBoxLayout(banner)
        b_layout.setContentsMargins(18, 14, 18, 14)
        b_layout.setSpacing(16)

        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(54, 54)
        self.icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_path = ROOT_DIR / "common" / "assets" / "dlss_icon.png"
        if icon_path.exists():
            pix = QPixmap(str(icon_path)).scaled(54, 54, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.icon_lbl.setPixmap(pix)
        else:
            self.icon_lbl.setText("⚡")
            self.icon_lbl.setStyleSheet("font-size: 28px; color: #2F8F5B;")
        b_layout.addWidget(self.icon_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        info_box = QVBoxLayout()
        info_box.setSpacing(4)
        self.t_lbl = QLabel("全架构超分与多帧生成 HUD 指示器 (DLSS / XeSS / FSR / MFG)")
        self.t_lbl.setStyleSheet("font-size: 15px; font-weight: 700;")
        self.t_lbl.setWordWrap(True)
        self.t_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.d_lbl = QLabel("支持 NVIDIA DLSS 官方底层超分水印、OptiScaler 性能叠加（超分引擎 / 分辨率 / FPS）、帧生成 Full 双 FPS 叠加，以及 ReShade 帧率监控。开关只作用于真实游戏目录。")
        self.d_lbl.setStyleSheet("font-size: 12px; color: #64748B;")
        self.d_lbl.setWordWrap(True)
        self.d_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        info_box.addWidget(self.t_lbl)
        info_box.addWidget(self.d_lbl)
        b_layout.addLayout(info_box, 1)
        vbox.addWidget(banner)

        # 2. 主总控卡片
        master_card = QFrame()
        master_card.setObjectName("MasterCard")
        m_layout = QVBoxLayout(master_card)
        m_layout.setContentsMargins(20, 16, 20, 16)
        m_layout.setSpacing(12)

        status_row = QHBoxLayout()
        status_row.setSpacing(12)
        self.master_status_title = QLabel("全架构屏幕水印总控：")
        self.master_status_title.setStyleSheet("font-size: 14px; font-weight: 700;")
        self.master_status_title.setWordWrap(True)
        status_row.addWidget(self.master_status_title)

        self.badge_status = QLabel("⚪ 检测中...")
        self.badge_status.setStyleSheet("padding: 4px 14px; border-radius: 8px; font-size: 12px; font-weight: 700;")
        status_row.addWidget(self.badge_status)
        status_row.addStretch()

        self.btn_refresh = QPushButton("🔄 刷新检测")
        self.btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh.clicked.connect(self.refresh_all_statuses)
        status_row.addWidget(self.btn_refresh)
        m_layout.addLayout(status_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("CardSep")
        m_layout.addWidget(sep)

        batch_row = QHBoxLayout()
        batch_row.setSpacing(10)

        self.btn_enable_all = QPushButton("⚡ 一键全部开启")
        self.btn_enable_all.setObjectName("BtnEnableAll")
        self.btn_enable_all.setMinimumHeight(44)
        self.btn_enable_all.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_enable_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_enable_all.setToolTip("一次性开启全部 4 项水印 / HUD 指示器")
        self.btn_enable_all.setStyleSheet("""
            QPushButton#BtnEnableAll {
                background-color: #2F8F5B;
                color: #FFFFFF;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 700;
            }
            QPushButton#BtnEnableAll:hover { background-color: #26784C; }
        """)
        self.btn_enable_all.clicked.connect(lambda: self.apply_all(True))
        batch_row.addWidget(self.btn_enable_all)

        self.btn_disable_all = QPushButton("🛑 一键全部关闭")
        self.btn_disable_all.setObjectName("BtnDisableAll")
        self.btn_disable_all.setMinimumHeight(44)
        self.btn_disable_all.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_disable_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_disable_all.setToolTip("一次性关闭全部 4 项水印 / HUD 指示器")
        self.btn_disable_all.setStyleSheet("""
            QPushButton#BtnDisableAll {
                background-color: #DC2626;
                color: #FFFFFF;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 700;
            }
            QPushButton#BtnDisableAll:hover { background-color: #B91C1C; }
        """)
        self.btn_disable_all.clicked.connect(lambda: self.apply_all(False))
        batch_row.addWidget(self.btn_disable_all)

        m_layout.addLayout(batch_row)

        self.lbl_targets = QLabel("")
        self.lbl_targets.setStyleSheet("font-size: 11px; color: #64748B;")
        self.lbl_targets.setWordWrap(True)
        m_layout.addWidget(self.lbl_targets)

        vbox.addWidget(master_card)

        # 3. 4 个独立分项开关卡片 (2x2 网格)
        grid_cards = QGridLayout()
        grid_cards.setHorizontalSpacing(14)
        grid_cards.setVerticalSpacing(14)
        grid_cards.setColumnStretch(0, 1)
        grid_cards.setColumnStretch(1, 1)
        self.grid_cards = grid_cards

        # Card 1: NVIDIA DLSS
        self.card_dlss, self.badge_dlss, self.btn_toggle_dlss, self.lbl_reason_dlss = self._create_feature_card(
            title="🟢 NVIDIA DLSS 官方超分水印",
            desc="注册表级 1024 · 左下角显示 DLSS 版本、渲染分辨率与 Preset K/M/E 档位",
            on_click=self.toggle_dlss_indicator
        )
        grid_cards.addWidget(self.card_dlss, 0, 0)

        # Card 2: OptiScaler 性能叠加 (超分引擎 / 分辨率 / FPS)
        self.card_xess, self.badge_xess, self.btn_toggle_xess, self.lbl_reason_xess = self._create_feature_card(
            title="🔵 OptiScaler 性能叠加（超分引擎 / 分辨率 / FPS）",
            desc="写入游戏 OptiScaler.ini 的 [Menu] ShowFps，屏幕左上角显示当前超分引擎、渲染→输出分辨率与实时帧率",
            on_click=self.toggle_xess_indicator
        )
        grid_cards.addWidget(self.card_xess, 0, 1)

        # Card 3: 帧生成 Full 叠加 (实时 / 插帧后双 FPS)
        self.card_mfg, self.badge_mfg, self.btn_toggle_mfg, self.lbl_reason_mfg = self._create_feature_card(
            title="⚡ 帧生成 Full 叠加（判断 2X / 3X / 4X）",
            desc="把叠加升级为 Full 模式：显示实时/插帧后双 FPS、FG 管线与 Reflex 延迟，用双 FPS 比值即可确认当前倍率",
            on_click=self.toggle_mfg_indicator
        )
        grid_cards.addWidget(self.card_mfg, 1, 0)

        # Card 4: ReShade 监控
        self.card_reshade, self.badge_reshade, self.btn_toggle_reshade, self.lbl_reason_reshade = self._create_feature_card(
            title="📊 ReShade 帧率监控（需已安装 ReShade 底座）",
            desc="写入游戏 ReShade.ini 的 [OVERLAY] ShowFPS / ShowFrameTime，屏幕顶角显示 FPS 与帧时间",
            on_click=self.toggle_reshade_indicator
        )
        grid_cards.addWidget(self.card_reshade, 1, 1)

        vbox.addLayout(grid_cards)

        # 4. 底部速查卡片 (包含 DLSS 模式 + 插帧刷新率匹配)
        ref_card = QFrame()
        ref_card.setObjectName("RefCard")
        self.ref_card = ref_card
        r_layout = QVBoxLayout(ref_card)
        r_layout.setContentsMargins(20, 16, 20, 16)
        r_layout.setSpacing(12)

        ref_title = QLabel("💡 全架构超分模式与插帧刷新率匹配速查")
        ref_title.setStyleSheet("font-size: 14px; font-weight: 700;")
        r_layout.addWidget(ref_title)

        grid_ref = QGridLayout()
        grid_ref.setHorizontalSpacing(16)
        grid_ref.setVerticalSpacing(8)

        modes = [
            ("DLAA (深度学习抗锯齿)", "100%", "原生物理分辨率，仅应用神经网络抗锯齿"),
            ("Quality (质量模式)", "66.7%", "画质极高，接近或超越原生画质"),
            ("Balanced (平衡模式)", "58.0%", "画质与帧率平衡，适合 2K/4K 分辨率"),
            ("Performance (性能模式)", "50.0%", "显著提升帧率，适合高刷新率竞技或 4K"),
            ("Ultra Performance (超高性能)", "33.3%", "8K 分辨率或追求极致帧率使用")
        ]

        self.ref_desc_labels = []
        for i, (m_name, m_ratio, m_desc) in enumerate(modes):
            l1 = QLabel(f"● {m_name}")
            l1.setStyleSheet("font-weight: 700; color: #2F8F5B; font-size: 12px;")
            l2 = QLabel(f"渲染比: {m_ratio}")
            l2.setStyleSheet("font-weight: 600; color: #059669; font-size: 12px;")
            l3 = QLabel(m_desc)
            l3.setStyleSheet("font-size: 12px; color: #64748B;")
            l3.setWordWrap(True)
            l3.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            self.ref_desc_labels.append(l3)
            grid_ref.addWidget(l1, i, 0)
            grid_ref.addWidget(l2, i, 1)
            grid_ref.addWidget(l3, i, 2)
        grid_ref.setColumnStretch(0, 0)
        grid_ref.setColumnStretch(1, 0)
        grid_ref.setColumnStretch(2, 1)

        r_layout.addLayout(grid_ref)

        sep_mfg = QFrame()
        sep_mfg.setFrameShape(QFrame.Shape.HLine)
        sep_mfg.setObjectName("CardSep")
        r_layout.addWidget(sep_mfg)

        # 插帧倍率与刷新率匹配指引
        fg_guide_title = QLabel("⚡ 插帧倍率与显示刷新率匹配速查（防撕裂与帧平滑最佳实践）")
        fg_guide_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #D97706;")
        r_layout.addWidget(fg_guide_title)

        grid_fg = QGridLayout()
        grid_fg.setHorizontalSpacing(16)
        grid_fg.setVerticalSpacing(6)

        fg_modes = [
            ("2X 双倍插帧", "推荐 120Hz ~ 144Hz 显示器", "基础 60 FPS -> 最终 120 FPS，手感输入延迟与流畅度最佳平衡"),
            ("3X 三倍插帧", "推荐 165Hz ~ 180Hz 显示器", "基础 60 FPS -> 最终 180 FPS，突破 144Hz 瓶颈，推荐 3A 大作高画质"),
            ("4X~6X 极致插帧", "推荐 240Hz ~ 360Hz 电竞屏", "基础 60 FPS -> 最终 240~360 FPS，极速丝滑体验，电竞高刷首选")
        ]
        for i, (f_name, f_rate, f_desc) in enumerate(fg_modes):
            fl1 = QLabel(f"● {f_name}")
            fl1.setStyleSheet("font-weight: 700; color: #7C3AED; font-size: 12px;")
            fl2 = QLabel(f_rate)
            fl2.setStyleSheet("font-weight: 600; color: #D97706; font-size: 12px;")
            fl3 = QLabel(f_desc)
            fl3.setStyleSheet("font-size: 12px; color: #64748B;")
            fl3.setWordWrap(True)
            fl3.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            self.ref_desc_labels.append(fl3)
            grid_fg.addWidget(fl1, i, 0)
            grid_fg.addWidget(fl2, i, 1)
            grid_fg.addWidget(fl3, i, 2)
        grid_fg.setColumnStretch(0, 0)
        grid_fg.setColumnStretch(1, 0)
        grid_fg.setColumnStretch(2, 1)

        r_layout.addLayout(grid_fg)
        vbox.addWidget(ref_card)

        vbox.addStretch()
        self.scroll_area.setWidget(container)
        self.body_layout.addWidget(self.scroll_area)

    def _create_feature_card(self, title: str, desc: str, on_click) -> Tuple[QFrame, QLabel, QPushButton, QLabel]:
        card = QFrame()
        card.setObjectName("FeatureCard")
        card.setMinimumWidth(280)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        # Header: Title + Badge
        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        lbl_title = QLabel(title)
        lbl_title.setObjectName("FeatureTitle")
        lbl_title.setStyleSheet("font-size: 13px; font-weight: 700;")
        lbl_title.setWordWrap(True)
        lbl_title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        top_row.addWidget(lbl_title, 1)

        badge = QLabel("⚪ 检测中")
        badge.setStyleSheet("padding: 2px 10px; border-radius: 6px; font-size: 11px; font-weight: 700;")
        badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        top_row.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(top_row)

        # Description
        lbl_desc = QLabel(desc)
        lbl_desc.setObjectName("FeatureDesc")
        lbl_desc.setStyleSheet("font-size: 11px; color: #64748B;")
        lbl_desc.setWordWrap(True)
        lbl_desc.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(lbl_desc)

        # Availability / "why it does not work" hint
        lbl_reason = QLabel("")
        lbl_reason.setObjectName("FeatureReason")
        lbl_reason.setStyleSheet("font-size: 10px; color: #D97706;")
        lbl_reason.setWordWrap(True)
        layout.addWidget(lbl_reason)

        # Action Toggle Button
        btn_toggle = QPushButton("切换开关")
        btn_toggle.setObjectName("FeatureBtn")
        btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_toggle.setFixedHeight(34)
        btn_toggle.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn_toggle.clicked.connect(on_click)
        layout.addWidget(btn_toggle)

        return card, badge, btn_toggle, lbl_reason

    def apply_theme(self):
        super().apply_theme()
        if not hasattr(self, "scroll_area"):
            return
        is_dark = self.is_dark_mode

        card_bg = "#2A2B2C" if is_dark else "#FFFFFF"
        card_border = "#3A3A3A" if is_dark else "#E5E5E5"
        card_hover = "#4A4A4A" if is_dark else "#D4D4D4"
        text_primary = "#E8E8E8" if is_dark else "#1A1A1A"
        text_secondary = "#A0A0A0" if is_dark else "#8A8A8A"
        sep_color = "#3A3A3A" if is_dark else "#E5E5E5"
        btn_outline_bg = "#303132" if is_dark else "#EFEFEF"
        btn_outline_fg = "#D4D4D4" if is_dark else "#4A4A4A"

        scrollbar_qss = SCROLLBAR_DARK_QSS if is_dark else SCROLLBAR_LIGHT_QSS
        card_qss = f"""
            QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget, QWidget#ScrollContainer {{
                background: transparent;
                background-color: transparent;
                border: none;
            }}
            {scrollbar_qss}
            QFrame#BannerCard, QFrame#MasterCard, QFrame#FeatureCard, QFrame#RefCard {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 14px;
            }}
            QFrame#BannerCard:hover, QFrame#MasterCard:hover, QFrame#FeatureCard:hover, QFrame#RefCard:hover {{
                border: 1px solid {card_hover};
            }}
            QFrame#CardSep {{
                color: {sep_color};
                background-color: {sep_color};
                max-height: 1px;
                border: none;
            }}
            QPushButton {{
                border-radius: 8px;
                font-size: 12px;
                font-weight: 600;
                padding: 6px 14px;
            }}
        """
        self.scroll_area.setStyleSheet(card_qss)
        self.scroll_area.verticalScrollBar().setStyleSheet(scrollbar_qss)
        if self.scroll_area.viewport():
            self.scroll_area.viewport().setStyleSheet("background: transparent;")

        if hasattr(self, "t_lbl"):
            self.t_lbl.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {text_primary};")
        if hasattr(self, "d_lbl"):
            self.d_lbl.setStyleSheet(f"font-size: 12px; color: {text_secondary};")
        if hasattr(self, "master_status_title"):
            self.master_status_title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {text_primary};")
        if hasattr(self, "btn_refresh"):
            self.btn_refresh.setStyleSheet(f"""
                QPushButton {{
                    background-color: {btn_outline_bg};
                    color: {btn_outline_fg};
                    border: 1px solid {card_border};
                    border-radius: 8px;
                    padding: 5px 12px;
                    font-size: 12px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: {'#3A3A3A' if is_dark else '#E5E5E5'};
                    color: {text_primary};
                }}
            """)
        if hasattr(self, "ref_desc_labels"):
            for lbl in self.ref_desc_labels:
                lbl.setStyleSheet(f"font-size: 12px; color: {text_secondary};")
        if hasattr(self, "lbl_targets"):
            self.lbl_targets.setStyleSheet(f"font-size: 11px; color: {text_secondary};")

        self.refresh_all_statuses()

    def auto_refresh_check(self):
        """Silently verifies state and updates UI if state changed externally."""
        self.refresh_all_statuses(silent=True)

    def refresh_all_statuses(self, silent: bool = False):
        """Refreshes all 4 features and updates UI."""
        is_dark = self.is_dark_mode
        on_bg = "#064E3B" if is_dark else "#DCFCE7"
        on_fg = "#34D399" if is_dark else "#16A34A"
        on_border = "#059669" if is_dark else "#86EFAC"

        off_bg = "#2A2B2C" if is_dark else "#EFEFEF"
        off_fg = "#94A3B8" if is_dark else "#64748B"
        off_border = "#3A3A3A" if is_dark else "#D4D4D4"

        def apply_badge(lbl: QLabel, is_on: bool, on_text: str, off_text: str):
            if is_on:
                lbl.setText(on_text)
                lbl.setStyleSheet(f"padding: 3px 10px; border-radius: 6px; font-size: 11px; font-weight: 700; background-color: {on_bg}; color: {on_fg}; border: 1px solid {on_border};")
            else:
                lbl.setText(off_text)
                lbl.setStyleSheet(f"padding: 3px 10px; border-radius: 6px; font-size: 11px; font-weight: 700; background-color: {off_bg}; color: {off_fg}; border: 1px solid {off_border};")

        def apply_btn(btn: QPushButton, is_on: bool):
            if is_dark:
                if is_on:
                    btn.setText("🛑 关闭该指示")
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #303132;
                            color: #F87171;
                            border: 1px solid #4A4A4A;
                            border-radius: 8px;
                            font-weight: 700;
                        }
                        QPushButton:hover { background-color: #3A3A3A; color: #FCA5A5; }
                    """)
                else:
                    btn.setText("🚀 开启该指示")
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #303132;
                            color: #E8E8E8;
                            border: 1px solid #4A4A4A;
                            border-radius: 8px;
                            font-weight: 700;
                        }
                        QPushButton:hover { background-color: #6FD398; color: #FFFFFF; border-color: #6FD398; }
                    """)
            else:
                if is_on:
                    btn.setText("🛑 关闭该指示")
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #F5F5F5;
                            color: #B91C1C;
                            border: 1px solid #E5E5E5;
                            border-radius: 8px;
                            font-weight: 700;
                        }
                        QPushButton:hover { background-color: #FEE2E2; border-color: #FCA5A5; }
                    """)
                else:
                    btn.setText("🚀 开启该指示")
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #E8E8E8;
                            color: #1A1A1A;
                            border: 1px solid #D4D4D4;
                            border-radius: 8px;
                            font-weight: 700;
                        }
                        QPushButton:hover { background-color: #2F8F5B; color: #FFFFFF; border-color: #2F8F5B; }
                    """)

        # 0. Show exactly which real game folders will be modified
        opti_inis = find_all_optiscaler_inis()
        reshade_inis = find_all_reshade_inis()
        game_dirs = get_known_game_dirs()
        active_dir = game_dirs[0] if game_dirs else None
        if hasattr(self, "lbl_targets"):
            parts = []
            if opti_inis:
                names = "、".join(get_game_display_name(p.parent) for p in opti_inis[:3])
                tail = f" 等 {len(opti_inis)} 个" if len(opti_inis) > 3 else ""
                parts.append(f"OptiScaler → {names}{tail}")
            if reshade_inis:
                names = "、".join(get_game_display_name(p.parent) for p in reshade_inis[:3])
                tail = f" 等 {len(reshade_inis)} 个" if len(reshade_inis) > 3 else ""
                parts.append(f"ReShade → {names}{tail}")

            if parts:
                text = "🎯 写入目标（真实游戏目录）：" + "；".join(parts)
                if active_dir and not (active_dir / "OptiScaler.ini").exists():
                    text += f"（当前游戏「{get_game_display_name(active_dir)}」未部署模式 C，OptiScaler 叠加不会显示）"
                self.lbl_targets.setText(text)
            else:
                self.lbl_targets.setText("⚠️ 未检测到已部署 OptiScaler / ReShade 的游戏目录：请先用【模式 B/C】修补游戏")

        # 1. DLSS
        s_dlss = get_dlss_indicator_status()
        apply_badge(self.badge_dlss, s_dlss, "🟢 已开启 (1024)", "⚪ 已关闭 (0)")
        apply_btn(self.btn_toggle_dlss, s_dlss)

        # 2. OptiScaler performance overlay
        s_xess = get_xess_fsr_status()
        apply_badge(self.badge_xess, s_xess, "🟢 已开启 (ShowFps)", "⚪ 已关闭")
        apply_btn(self.btn_toggle_xess, s_xess)

        # 3. Frame generation Full overlay
        s_mfg = get_mfg_hud_status()
        apply_badge(self.badge_mfg, s_mfg, "🟢 已开启 (Full)", "⚪ 已关闭")
        apply_btn(self.btn_toggle_mfg, s_mfg)

        # 4. ReShade
        s_reshade = get_reshade_overlay_status()
        apply_badge(self.badge_reshade, s_reshade, "🟢 已开启 (FPS)", "⚪ 已关闭")
        apply_btn(self.btn_toggle_reshade, s_reshade)

        # Batch controls share the same neutral styling as the per-card toggles
        if hasattr(self, "btn_enable_all"):
            apply_btn(self.btn_enable_all, False)
            self.btn_enable_all.setText("⚡ 一键全部开启")
        if hasattr(self, "btn_disable_all"):
            apply_btn(self.btn_disable_all, True)
            self.btn_disable_all.setText("⛔ 一键全部关闭")

        # 5. Per-card "is it actually usable?" hints
        reason_ok = "#34D399" if is_dark else "#059669"
        reason_warn = "#FBBF24" if is_dark else "#D97706"

        def set_reason(lbl, text: str, ok: bool):
            lbl.setText(text)
            lbl.setStyleSheet(f"font-size: 10px; color: {reason_ok if ok else reason_warn};")

        active_has_c = bool(active_dir and (active_dir / "OptiScaler.ini").exists())

        set_reason(self.lbl_reason_dlss, "✅ 可用：注册表级水印，对所有游戏生效", True)

        if active_has_c:
            set_reason(self.lbl_reason_xess, "✅ 当前游戏已部署模式 C，可正常显示", True)
        elif opti_inis:
            set_reason(
                self.lbl_reason_xess,
                f"⚠️ 未生效：已检测到 {len(opti_inis)} 个模式 C 游戏，但当前游戏未部署（请用模式 C 修补）",
                False
            )
        else:
            set_reason(self.lbl_reason_xess, "⚠️ 未生效：未检测到模式 C 游戏（请用模式 C 修补）", False)

        if active_has_c:
            set_reason(self.lbl_reason_mfg, "✅ 依赖性能叠加，当前游戏可正常显示", True)
        else:
            set_reason(self.lbl_reason_mfg, "⚠️ 未生效：需当前游戏部署模式 C，并先开启性能叠加", False)

        if reshade_inis:
            set_reason(self.lbl_reason_reshade, f"✅ 已检测到 {len(reshade_inis)} 个 ReShade 底座", True)
        else:
            set_reason(self.lbl_reason_reshade, "⚠️ 未生效：未检测到 ReShade 底座（请用模式 B / RHI 安装）", False)

        # Master Summary
        active_count = sum([1 for s in (s_dlss, s_xess, s_mfg, s_reshade) if s])
        all_on = (active_count == 4)
        none_on = (active_count == 0)

        if all_on:
            self.badge_status.setText("🟢 全部已开启 (4/4 运行中)")
            self.badge_status.setStyleSheet(f"padding: 4px 14px; border-radius: 8px; font-size: 12px; font-weight: 700; background-color: {on_bg}; color: {on_fg}; border: 1px solid {on_border};")
            if not silent:
                self.set_status("全部 4 项水印与 HUD 指示器已开启，进游戏即可看到超分与插帧状态。")
        elif none_on:
            self.badge_status.setText("⚪ 已全部关闭 (0/4 未激活)")
            self.badge_status.setStyleSheet(f"padding: 4px 14px; border-radius: 8px; font-size: 12px; font-weight: 700; background-color: {off_bg}; color: {off_fg}; border: 1px solid {off_border};")
            if not silent:
                self.set_status("所有屏幕水印与 HUD 指示器当前处于【未开启】状态。")
        else:
            self.badge_status.setText(f"🟡 部分开启 ({active_count}/4 运行中)")
            part_bg = "#78350F" if is_dark else "#F5F5F5"
            part_fg = "#FBBF24" if is_dark else "#D97706"
            part_bd = "#D97706" if is_dark else "#E5E5E5"
            self.badge_status.setStyleSheet(f"padding: 4px 14px; border-radius: 8px; font-size: 12px; font-weight: 700; background-color: {part_bg}; color: {part_fg}; border: 1px solid {part_bd};")
            if not silent:
                self.set_status(f"当前有 {active_count} 项指示器处于启用状态。")

    # ---------------------------------------------------------------------
    # Individual Feature Toggles
    # ---------------------------------------------------------------------
    def toggle_dlss_indicator(self):
        cur = get_dlss_indicator_status()
        new_state = not cur
        ok, msg = set_dlss_indicator_status(new_state)
        self.refresh_all_statuses()
        self.set_status(f"DLSS 水印: {'已开启' if new_state else '已关闭'}")

    def toggle_xess_indicator(self):
        new_state = not get_xess_fsr_status()
        ok, msg = set_xess_fsr_status(new_state)
        self.refresh_all_statuses()
        self.set_status(msg)

    def toggle_mfg_indicator(self):
        new_state = not get_mfg_hud_status()
        ok, msg = set_mfg_hud_status(new_state)
        self.refresh_all_statuses()
        self.set_status(msg)

    def toggle_reshade_indicator(self):
        new_state = not get_reshade_overlay_status()
        ok, msg = set_reshade_overlay_status(new_state)
        self.refresh_all_statuses()
        self.set_status(msg)

    def apply_all(self, enabled: bool):
        """Enable or disable all 4 indicators in one pass (explicit on/off buttons)."""
        target_state = bool(enabled)

        progress_dlg = ModernProgressDialog(
            self,
            title="应用全架构屏幕水印与 HUD 设置",
            description=f"正在{'一键全部开启' if target_state else '一键全部关闭'}水印与 HUD 指示器...",
            is_dark=self.is_dark_mode
        )
        progress_dlg.show()

        results: List[Tuple[bool, str]] = []

        progress_dlg.set_progress(20, "正在更新 NVIDIA 驱动层注册表 DLSS 水印...", "HKLM\\SOFTWARE\\NVIDIA Corporation\\Global\\NGXCore")
        QApplication.processEvents()
        results.append(set_dlss_indicator_status(target_state))

        progress_dlg.set_progress(45, "正在配置 OptiScaler 性能叠加...", "OptiScaler.ini [Menu] ShowFps")
        QApplication.processEvents()
        results.append(set_xess_fsr_status(target_state))

        progress_dlg.set_progress(70, "正在切换帧生成 Full 叠加...", "OptiScaler.ini [Menu] FpsOverlayType=4")
        QApplication.processEvents()
        results.append(set_mfg_hud_status(target_state))

        progress_dlg.set_progress(90, "正在更新 ReShade 实时帧率与延迟叠加...", "ReShade.ini [OVERLAY]")
        QApplication.processEvents()
        results.append(set_reshade_overlay_status(target_state))

        self.refresh_all_statuses()
        failed = [msg for ok_, msg in results if not ok_]
        if failed:
            progress_dlg.finish(
                True,
                f"已{'开启' if target_state else '关闭'}可用指示器（{len(results) - len(failed)}/{len(results)}）",
                "；".join(failed),
                auto_close_delay_ms=1800
            )
        else:
            progress_dlg.finish(
                True,
                f"已成功{'开启' if target_state else '关闭'}全部水印与 HUD 指示器！",
                "配置已即时生效",
                auto_close_delay_ms=800
            )

    def toggle_master_all(self):
        """Backward-compatible alias: flip everything based on the current state."""
        active = sum(
            [get_dlss_indicator_status(), get_xess_fsr_status(),
             get_mfg_hud_status(), get_reshade_overlay_status()]
        )
        self.apply_all(active != 4)


def main():
    app = QApplication(sys.argv)
    from common.ui_theme import install_combo_arrows
    install_combo_arrows(app)
    window = DLSSIndicatorWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
