# -*- coding: utf-8 -*-
"""
Toolbox Launcher - 游戏与硬件大师工具箱首页主程序
Implements the 4 core module integration requirements:
1. 2-column shortcut grid for the 5 sub-software (JXR HDR Converter included).
2. Non-blocking asynchronous process management with anti-multi-instance window raising.
3. Unified C-drive data storage in C:/ToolboxData/.
4. One-click factory reset and cache cleanup.
"""

# Clean modern Qt 6 imports
import os
import sys
import time
import json
import ctypes
from ctypes import wintypes
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QIcon, QPixmap, QFont, QColor
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QGridLayout,
    QSizePolicy
)

# Ensure root dir is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common.ui_theme import (
    BaseWindow, LIGHT_STYLE_SHEET, DARK_STYLE_SHEET,
    ModernProgressDialog, ModernConfirmDialog, ModernDialog,
    get_global_theme
)
from common.config_manager import (
    TOOLBOX_ROOT, CACHE_ROOT, CONFIG_ROOT,
    get_total_cache_size_mb, reset_all_data,
    get_app_cache_dir, get_app_config_dir
)

# Win32 Helpers for Anti-Multi-Instance Window Raising
user32 = ctypes.windll.user32


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def get_hwnds_for_pid(target_pid: int) -> list[int]:
    """Finds all top-level visible window handles for a given process ID."""
    hwnds = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def enum_cb(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == target_pid:
                # Filter out tool windows with 0 title length
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    hwnds.append(hwnd)
        return True

    user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
    return hwnds


kernel32 = ctypes.windll.kernel32


def get_process_name_by_pid(pid: int) -> str:
    """Returns the lowercased executable basename for a given process ID."""
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h_proc:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value).lower()
    finally:
        kernel32.CloseHandle(h_proc)
    return ""


# Official, exact window titles for the 5 sub-software of DM-Toolbox
APP_EXACT_TITLES = {
    "app1_hardware": "DM工具箱 - 硬件系统配置大师",
    "app2_mfg": "DM工具箱 - DLSS多帧生成补丁",
    "app3_autohdr": "DM工具箱 - Windows Auto HDR 管理器",
    "app4_dlss": "DM工具箱 - 全架构超分与插帧水印指示器 (DLSS / XeSS / FSR / MFG)",
    "app5_jxr": "JXR HDR 转换器 - 转 Ultra HDR / PNG",
}

ALLOWED_SUBPROCESS_EXECUTABLES = {"python.exe", "pythonw.exe", "dmbox.exe", "jxrconverter.exe"}


def find_window_by_app_id(app_id: str) -> tuple[int, int]:
    """
    Finds first visible top-level window strictly belonging to the official sub-app.
    Guarantees that browser tabs (Chrome, Edge), file explorers, or editors NEVER falsely match.
    """
    target_title = APP_EXACT_TITLES.get(app_id, "")
    if not target_title:
        return (0, 0)

    result = (0, 0)
    current_pid = os.getpid()
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def enum_cb(hwnd, lparam):
        nonlocal result
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value
                # Match exact sub-app title or starting with official title (excluding main launcher itself)
                if (title == target_title or title.startswith(target_title)) and title != "DM工具箱":
                    pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    if pid.value != current_pid and pid.value != 0:
                        proc_name = get_process_name_by_pid(pid.value)
                        # Must be python, pythonw, or dmbox - never chrome, msedge, explorer, etc.!
                        if proc_name in ALLOWED_SUBPROCESS_EXECUTABLES or "python" in proc_name:
                            result = (hwnd, pid.value)
                            return False
        return True

    user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
    return result


def activate_window_by_hwnd(hwnd: int):
    """Restores and brings a window to the foreground."""
    # SW_RESTORE = 9, SW_SHOW = 5
    user32.ShowWindow(hwnd, 9)
    # Simulate Alt key to bypass Windows focus stealing restrictions
    user32.keybd_event(0x12, 0, 0, 0)
    user32.SetForegroundWindow(hwnd)
    user32.keybd_event(0x12, 0, 2, 0)


# Sub-software Definitions
APPS_METADATA = [
    {
        "id": "app1_hardware",
        "name": "全硬件配置大师",
        "tag": "硬件修改 · 驱动模拟",
        "desc": "CPU / GPU / 显存 / 主板 / 内存 / 硬盘 自定义硬件，支持游戏客户端检测。",
        "icon": "app_icon.png",
        "script_rel": "apps/app1_hardware/app.py",
        "work_dir": "apps/app1_hardware",
        "require_admin": True
    },
    {
        "id": "app2_mfg",
        "name": "DLSS多帧生成补丁",
        "tag": "通用补丁 · 帧率翻倍",
        "desc": "全游戏通用 DLSS-G / FSR3 / XeSS 多帧生成注入补丁，集成 ReShade HDR 安装器与热更新组件，支持一键无损还原。",
        "icon": "mfg_icon.png",
        "script_rel": "apps/app2_mfg/app.py",
        "work_dir": "apps/app2_mfg"
    },
    {
        "id": "app3_autohdr",
        "name": "Windows Auto HDR 管理器",
        "tag": "画面增强 · 动态HDR",
        "desc": "智能检测已生效游戏，一键强制为任意 DirectX 11/12 游戏开启 Windows 10-bit / 8-bit Auto HDR 超高动态范围画面增强。",
        "icon": "autohdr_icon.png",
        "script_rel": "apps/app3_autohdr/app.py",
        "work_dir": "apps/app3_autohdr"
    },
    {
        "id": "app4_dlss",
        "name": "全架构超分与插帧指示器",
        "tag": "全架构超分 · 水印开关",
        "desc": "支持 NVIDIA DLSS、Intel XeSS 2.0、AMD FSR 3.1 跨卡超分与 2X~6X 多帧生成倍率实时屏幕 HUD 水印指示。",
        "icon": "dlss_icon.png",
        "script_rel": "apps/app4_dlss/app.py",
        "work_dir": "apps/app4_dlss",
        "require_admin": True
    },
    {
        "id": "app5_jxr",
        "name": "JXR HDR 转换器",
        "tag": "HDR 截图 · Ultra HDR",
        "desc": "把 Windows HDR 截图 (JPEG XR / .jxr) 批量转换为 Ultra HDR JPEG 或 SDR PNG，支持三种 Tone Mapping、峰值亮度与 EXIF/XMP 元数据透传。",
        "icon": "jxr_icon.png",
        "exe_rel": "apps/app5_jxr/JxrConverter.exe",
        "work_dir": "apps/app5_jxr"
    }
]


class AppCard(QFrame):
    """Reusable Fluent Card representing one sub-software shortcut."""
    def __init__(self, meta: dict, parent_launcher):
        super().__init__()
        self.meta = meta
        self.parent_launcher = parent_launcher
        self.app_id = meta["id"]
        self.setProperty("class", "GridCard")
        self.setCursor(Qt.PointingHandCursor)
        self.is_running = False
        self.current_pid = 0
        self.init_ui()
        self.apply_theme(self.parent_launcher.is_dark_mode)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Top Row: Icon + Title + Tag
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        # Icon (40x40)
        self.lbl_icon = QLabel()
        self.lbl_icon.setFixedSize(40, 40)
        icon_path = ROOT_DIR / "common" / "assets" / self.meta["icon"]
        if icon_path.exists():
            pix = QPixmap(str(icon_path)).scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.lbl_icon.setPixmap(pix)
        top_row.addWidget(self.lbl_icon)

        # Title & Tag
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        self.lbl_title = QLabel(self.meta["name"])
        self.lbl_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        title_box.addWidget(self.lbl_title)

        self.lbl_tag = QLabel(self.meta["tag"])
        self.lbl_tag.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        title_box.addWidget(self.lbl_tag)

        top_row.addLayout(title_box)
        top_row.addStretch()

        # Running status indicator badge
        self.badge_status = QLabel("⚪ 未启动")
        top_row.addWidget(self.badge_status, 0, Qt.AlignTop)

        layout.addLayout(top_row)

        # Description (Word Wrap)
        self.lbl_desc = QLabel(self.meta["desc"])
        self.lbl_desc.setWordWrap(True)
        self.lbl_desc.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        layout.addWidget(self.lbl_desc)

        layout.addStretch()

        # Bottom Action Bar
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        self.btn_action = QPushButton("🚀 打开软件")
        self.btn_action.setProperty("class", "PrimaryBtn")
        self.btn_action.setMinimumHeight(35)
        self.btn_action.setCursor(Qt.PointingHandCursor)
        self.btn_action.clicked.connect(self.on_action_clicked)
        bottom_row.addWidget(self.btn_action)

        layout.addLayout(bottom_row)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.on_action_clicked()
        super().mousePressEvent(event)

    def on_action_clicked(self):
        self.parent_launcher.launch_or_activate_app(self.app_id)

    def apply_theme(self, is_dark: bool):
        if is_dark:
            self.lbl_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #F5F5F5;")
            self.lbl_tag.setStyleSheet("""
                color: #A0A0A0;
                font-size: 11px;
                font-weight: 700;
                background-color: #303132;
                padding: 2px 7px;
                border-radius: 5px;
            """)
            self.lbl_desc.setStyleSheet("color: #94A3B8; font-size: 12px; line-height: 1.45;")
        else:
            self.lbl_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #292929;")
            self.lbl_tag.setStyleSheet("""
                color: #5A5A5A;
                font-size: 11px;
                font-weight: 700;
                background-color: #F0F0F0;
                padding: 2px 7px;
                border-radius: 5px;
            """)
            self.lbl_desc.setStyleSheet("color: #4A4A4A; font-size: 12px; line-height: 1.45;")

        self._render_status(is_dark)

    def _render_status(self, is_dark: bool):
        if self.is_running:
            self.badge_status.setText(f"🟢 运行中 ({self.current_pid})")
            if is_dark:
                self.badge_status.setStyleSheet("""
                    color: #4ADE80;
                    font-size: 11px;
                    font-weight: 700;
                    background-color: #064E3B;
                    padding: 3px 9px;
                    border-radius: 8px;
                """)
            else:
                self.badge_status.setStyleSheet("""
                    color: #16A34A;
                    font-size: 11px;
                    font-weight: 700;
                    background-color: #DCFCE7;
                    padding: 3px 9px;
                    border-radius: 8px;
                """)
            self.btn_action.setText("🚀 置顶 / 重新打开")
            self.btn_action.setStyleSheet("""
                background-color: #8FE3B0;
                color: #10231A;
                border: none;
                border-radius: 9px;
                padding: 7px 14px;
                font-size: 13px;
                font-weight: 700;
            """)
        else:
            self.badge_status.setText("⚪ 未启动")
            if is_dark:
                self.badge_status.setStyleSheet("""
                    color: #94A3B8;
                    font-size: 11px;
                    font-weight: 600;
                    background-color: #3A3A3A;
                    padding: 3px 9px;
                    border-radius: 8px;
                """)
            else:
                self.badge_status.setStyleSheet("""
                    color: #64748B;
                    font-size: 11px;
                    font-weight: 600;
                    background-color: #EFEFEF;
                    padding: 3px 9px;
                    border-radius: 8px;
                """)
            self.btn_action.setText("🚀 打开软件")
            self.btn_action.setStyleSheet("""
                background-color: #8FE3B0;
                color: #10231A;
                border: none;
                border-radius: 9px;
                padding: 7px 14px;
                font-size: 13px;
                font-weight: 700;
            """)

    def update_status(self, is_running: bool, pid: int = 0):
        self.is_running = is_running
        self.current_pid = pid
        self._render_status(self.parent_launcher.is_dark_mode)


class ToolboxLauncher(BaseWindow):
    """
    Main Launcher Window for Game & Hardware Toolbox.
    """
    def __init__(self):
        super().__init__(
            title="DM工具箱",
            icon_filename="app_icon.png",
            width=960,
            height=820
        )
        self.running_processes: dict[str, subprocess.Popen] = {}
        self.proc_launch_time: dict[str, float] = {}
        self.cards: dict[str, AppCard] = {}

        self.init_launcher_ui()
        self.apply_theme()

        # Polling timer for process monitoring and cache size update
        self.monitor_timer = QTimer(self)
        self.monitor_timer.setInterval(1000)
        self.monitor_timer.timeout.connect(self.poll_processes_and_stats)
        self.monitor_timer.start()

        # Initial refresh
        self.update_cache_display()

        # Preloaded releases cache & silent background update checker
        self.preloaded_releases = []
        self.silent_updater = None
        QTimer.singleShot(2000, self.start_background_update_check)

    def init_launcher_ui(self):
        # Outer scroll area with NO horizontal scrollbar and responsive stretching
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(18, 14, 18, 16)
        vbox.setSpacing(14)

        # ------------------ TOP HERO & ACTION HEADER ------------------
        header_card = QFrame()
        header_card.setProperty("class", "GridCard")
        h_layout = QHBoxLayout(header_card)
        h_layout.setContentsMargins(18, 14, 18, 14)
        h_layout.setSpacing(14)

        # Left Info
        left_info = QVBoxLayout()
        left_info.setSpacing(4)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        self.t_lbl = QLabel("DM工具箱")
        self.t_lbl.setStyleSheet("font-size: 19px; font-weight: 800;")
        title_row.addWidget(self.t_lbl)

        from common.version import APP_VERSION
        self.lbl_ver = QLabel(f"v{APP_VERSION}")
        self.lbl_ver.setStyleSheet("""
            background-color: #8FE3B0;
            color: #10231A;
            font-size: 11px;
            font-weight: 700;
            padding: 2px 7px;
            border-radius: 6px;
        """)
        title_row.addWidget(self.lbl_ver)
        title_row.addStretch()
        left_info.addLayout(title_row)

        self.sub_lbl = QLabel("全架构硬件深度定制 · 动态 Auto HDR 增强 · DLSS 多帧生成补丁 · DLSS 实时超分指示 · JXR→Ultra HDR 转换")
        self.sub_lbl.setWordWrap(True)
        self.sub_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        left_info.addWidget(self.sub_lbl)
        h_layout.addLayout(left_info, 1)

        # Right Action Buttons
        right_actions = QHBoxLayout()
        right_actions.setSpacing(10)

        # Cache size badge
        self.lbl_cache_size = QLabel("💾 缓存占用: 计算中...")
        right_actions.addWidget(self.lbl_cache_size)

        # Check for Updates Button
        self.btn_check_update = QPushButton("🔄 检查更新")
        self.btn_check_update.setProperty("class", "SecondaryBtn")
        self.btn_check_update.setMinimumHeight(35)
        self.btn_check_update.setCursor(Qt.PointingHandCursor)
        self.btn_check_update.setToolTip("检查 GitHub 官方发布的最新版本，可自由选择在线下载升级。")
        self.btn_check_update.clicked.connect(self.on_check_update_clicked)
        right_actions.addWidget(self.btn_check_update)

        # One-click Reset & Clean Button (Compact text, full tooltip)
        self.btn_reset = QPushButton("🧹 还原与清理")
        self.btn_reset.setProperty("class", "DangerBtn")
        self.btn_reset.setMinimumHeight(35)
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.setToolTip("关闭所有正在运行的子软件，彻底清空 AppData 缓存，并将 5 个软件恢复为初始默认配置。")
        self.btn_reset.clicked.connect(self.on_reset_and_clean_clicked)
        right_actions.addWidget(self.btn_reset)

        h_layout.addLayout(right_actions)
        vbox.addWidget(header_card)

        # ------------------ 2x2 SHORTCUT GRID ------------------
        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setContentsMargins(0, 2, 0, 2)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)

        # Instantiate all sub-software cards in a 2-column grid
        for i, meta in enumerate(APPS_METADATA):
            card = AppCard(meta, self)
            self.cards[meta["id"]] = card
            row = i // 2
            col = i % 2
            grid.addWidget(card, row, col)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        vbox.addWidget(grid_widget)

        # ------------------ BOTTOM DATA CENTER TIPS ------------------
        self.tip_card = QFrame()
        tip_layout = QHBoxLayout(self.tip_card)
        tip_layout.setContentsMargins(16, 10, 16, 10)
        tip_layout.setSpacing(12)

        self.tip_lbl = QLabel(
            "📌 <b>存储规范提示</b>：全软件配置文件保存在 <code>%APPDATA%/ToolboxMaster/config/</code>（按软件独立生成子文件夹），"
            "所有临时文件与下载缓存保存在 <code>%APPDATA%/ToolboxMaster/cache/</code>。程序本体与数据彻底解耦，绿色便携无残留。"
        )
        self.tip_lbl.setWordWrap(True)
        tip_layout.addWidget(self.tip_lbl, 1)

        self.btn_open_c_dir = QPushButton("📂 打开 AppData 数据中心")
        self.btn_open_c_dir.setProperty("class", "SecondaryBtn")
        self.btn_open_c_dir.setCursor(Qt.PointingHandCursor)
        self.btn_open_c_dir.clicked.connect(self.open_toolbox_data_dir)
        tip_layout.addWidget(self.btn_open_c_dir)

        vbox.addWidget(self.tip_card)

        vbox.addStretch()
        scroll.setWidget(container)
        self.body_layout.addWidget(scroll)

    def apply_theme(self):
        super().apply_theme()
        is_dark = getattr(self, "is_dark_mode", False)
        if hasattr(self, "t_lbl"):
            self.t_lbl.setStyleSheet(f"font-size: 19px; font-weight: 800; color: {'#F5F5F5' if is_dark else '#292929'};")
        if hasattr(self, "sub_lbl"):
            self.sub_lbl.setStyleSheet(f"font-size: 12px; color: {'#94A3B8' if is_dark else '#64748B'};")
        if hasattr(self, "lbl_cache_size"):
            if is_dark:
                self.lbl_cache_size.setStyleSheet("""
                    background-color: #292929;
                    color: #94A3B8;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 6px 12px;
                    border: 1px solid #3A3A3A;
                    border-radius: 8px;
                """)
            else:
                self.lbl_cache_size.setStyleSheet("""
                    background-color: #F5F5F5;
                    color: #3A3A3A;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 6px 12px;
                    border: 1px solid #E5E5E5;
                    border-radius: 8px;
                """)
        if hasattr(self, "tip_card"):
            if is_dark:
                self.tip_card.setStyleSheet("""
                    background-color: #2A2B2C;
                    border: 1px solid #3A3A3A;
                    border-radius: 12px;
                """)
            else:
                self.tip_card.setStyleSheet("""
                    background-color: #F5F5F5;
                    border: 1px solid #E5E5E5;
                    border-radius: 12px;
                """)
        if hasattr(self, "tip_lbl"):
            self.tip_lbl.setStyleSheet(f"color: {'#94A3B8' if is_dark else '#4A4A4A'}; font-size: 12px;")

        if hasattr(self, "cards"):
            for card in self.cards.values():
                card.apply_theme(is_dark)

    def update_cache_display(self):
        try:
            mb = get_total_cache_size_mb()
            self.lbl_cache_size.setText(f"💾 缓存占用: {mb:.2f} MB")
        except Exception:
            self.lbl_cache_size.setText("💾 缓存占用: 0.00 MB")

    def poll_processes_and_stats(self):
        """Monitors all registered child processes and updates card states."""
        for app_id, card in self.cards.items():
            proc = self.running_processes.get(app_id)
            is_running = False
            running_pid = 0

            if proc is not None and proc.poll() is None:
                is_running = True
                running_pid = proc.pid
            else:
                # Fallback: check visible window by exact sub-app title and verified process
                hwnd, pid = find_window_by_app_id(app_id)
                if hwnd and pid:
                    is_running = True
                    running_pid = pid

            card.update_status(is_running, running_pid)
            if not is_running and proc is not None:
                self.running_processes.pop(app_id, None)

        # Update cache size
        self.update_cache_display()

    def set_status(self, text: str):
        if hasattr(self, "lbl_status") and self.lbl_status:
            self.lbl_status.setText(text)

    def launch_or_activate_app(self, app_id: str):
        """
        Anti-multi-instance launch handler:
        If app is already running with an active window, brings its window to front.
        If the process has no visible window (zombie or terminated), cleans it up and launches a fresh instance.
        """
        # 1. Check proc handle
        proc = self.running_processes.get(app_id)
        if proc is not None and proc.poll() is None:
            hwnds = get_hwnds_for_pid(proc.pid)
            if hwnds:
                activate_window_by_hwnd(hwnds[0])
                self.set_status(f"软件已在运行中，已将窗口唤醒并置顶！(PID: {proc.pid})")
                return
            else:
                # If launched within the last 4 seconds, the window is still initializing. Do NOT kill!
                launch_time = self.proc_launch_time.get(app_id, 0)
                if time.time() - launch_time < 4.0:
                    self.set_status("软件正在启动初始化中，请稍候...")
                    return
                try:
                    proc.terminate()
                except Exception:
                    pass
                self.running_processes.pop(app_id, None)

        # 2. Check visible window by exact title and verified process
        hwnd, pid = find_window_by_app_id(app_id)
        if hwnd and pid:
            activate_window_by_hwnd(hwnd)
            self.set_status(f"软件已在运行中，已将窗口唤醒并置顶！(PID: {pid})")
            if app_id in self.cards:
                self.cards[app_id].update_status(True, pid)
            return

        # 3. Not running - find script and launch
        meta = next((m for m in APPS_METADATA if m["id"] == app_id), None)
        if not meta:
            return

        work_dir = ROOT_DIR / meta["work_dir"]

        # External EXE app (e.g. JXR HDR Converter): launch the executable directly.
        exe_rel = meta.get("exe_rel")
        if exe_rel:
            exe_path = ROOT_DIR / exe_rel
            if not exe_path.exists():
                ModernDialog.error(self, "启动失败", f"未找到目标程序:\n{exe_path}")
                return
            try:
                if meta.get("require_admin", False) and not is_admin():
                    ret = ctypes.windll.shell32.ShellExecuteW(
                        None, "runas", str(exe_path), None, str(work_dir), 1
                    )
                    if ret > 32:
                        self.set_status(f"已请求管理员权限启动 [{meta['name']}]...")
                        self.proc_launch_time[app_id] = time.time()
                        QTimer.singleShot(800, self.poll_processes_and_stats)
                    else:
                        self.set_status(f"启动 [{meta['name']}] 需要管理员权限，用户取消了授权。")
                    return

                new_proc = subprocess.Popen(
                    [str(exe_path)],
                    cwd=str(work_dir),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self.running_processes[app_id] = new_proc
                self.proc_launch_time[app_id] = time.time()
                if app_id in self.cards:
                    self.cards[app_id].update_status(True, new_proc.pid)
                self.set_status(f"已非阻塞启动 [{meta['name']}] (PID: {new_proc.pid})")
            except Exception as e:
                ModernDialog.error(self, "启动异常", f"启动子软件失败:\n{e}")
            return

        script_path = ROOT_DIR / meta["script_rel"]

        if not script_path.exists():
            ModernDialog.error(self, "启动失败", f"未找到目标启动文件:\n{script_path}")
            return

        try:
            env = os.environ.copy()
            pythonpath = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = f"{ROOT_DIR};{pythonpath}"

            py_exe = sys.executable
            bundled_pyw = ROOT_DIR / "runtime" / "pythonw.exe"
            if bundled_pyw.exists():
                py_exe = str(bundled_pyw)
            elif py_exe.lower().endswith("python.exe"):
                candidate_pyw = Path(py_exe).parent / "pythonw.exe"
                if candidate_pyw.exists():
                    py_exe = str(candidate_pyw)

            # If the app requires administrator and the launcher is not elevated, launch via ShellExecuteW runas
            if meta.get("require_admin", False) and not is_admin():
                ret = ctypes.windll.shell32.ShellExecuteW(
                    None,
                    "runas",
                    py_exe,
                    f'"{script_path}"',
                    str(work_dir),
                    1
                )
                if ret > 32:
                    self.set_status(f"已请求管理员权限启动 [{meta['name']}]...")
                    self.proc_launch_time[app_id] = time.time()
                    QTimer.singleShot(800, self.poll_processes_and_stats)
                else:
                    self.set_status(f"启动 [{meta['name']}] 需要管理员权限，用户取消了授权。")
                return

            # Launch async child process with detached streams
            new_proc = subprocess.Popen(
                [py_exe, str(script_path)],
                cwd=str(work_dir),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.running_processes[app_id] = new_proc
            self.proc_launch_time[app_id] = time.time()
            if app_id in self.cards:
                self.cards[app_id].update_status(True, new_proc.pid)
            self.set_status(f"已非阻塞启动 [{meta['name']}] (PID: {new_proc.pid})")
        except Exception as e:
            ModernDialog.error(self, "启动异常", f"启动子软件失败:\n{e}")

    def on_reset_and_clean_clicked(self):
        """
        Feature B: 5-step robust factory reset and cache cleanup:
        1. Modern confirmation modal dialog with detailed items
        2. Safe termination of all running child processes (releasing file locks)
        3. Clear %APPDATA%/ToolboxMaster/ and C:/ToolboxData/
        4. Rebuild directories and copy defaults/ templates
        5. Completion feedback with progress bar and explicit user confirmation
        """
        confirmed = ModernDialog.confirm(
            parent=self,
            title="确认还原默认设置与清理缓存",
            message="该操作将执行系统级环境清理与出厂设置还原：",
            bullet_items=[
                "• 安全关闭当前所有正在运行的 4 个子软件（释放文件占用锁）",
                "• 彻底清空 %APPDATA%/ToolboxMaster/ 下的所有临时缓存、日志和下载",
                "• 将四个子软件的当前配置文件重置为 defaults/ 初始出厂配置"
            ],
            warning_note="⚠️ 注意：重置后所有自定义配置将丢失，此操作不可撤销！",
            confirm_text="立即清理并还原",
            cancel_text="取消",
            icon_type="danger",
            is_danger=True
        )
        if not confirmed:
            return

        progress_dlg = ModernProgressDialog(
            self,
            title="还原默认设置与清理缓存",
            description="正在启动清理流程...",
            is_dark=(get_global_theme() == "dark")
        )

        def run_cleanup_steps():
            try:
                # Step 1: 20%
                progress_dlg.set_progress(20, "正在安全终止运行中的子软件...", "向所有活动子进程发送终止信号")
                QApplication.processEvents()
                time.sleep(0.3)

                # Step 2: Terminate all running child processes
                for app_id, proc in list(self.running_processes.items()):
                    if proc.poll() is None:
                        try:
                            proc.terminate()
                        except Exception:
                            pass

                # Step 2: 45%
                progress_dlg.set_progress(45, "正在释放文件系统占用锁...", "等待子进程句柄完全释放并清理进程表")
                QApplication.processEvents()
                time.sleep(0.35)
                for app_id, proc in list(self.running_processes.items()):
                    if proc.poll() is None:
                        try:
                            proc.kill()
                        except Exception:
                            pass

                self.running_processes.clear()

                # Step 3: 70%
                progress_dlg.set_progress(70, "正在深度清空临时缓存与日志...", "清理 %APPDATA%/ToolboxMaster/ 临时数据与日志")
                QApplication.processEvents()
                time.sleep(0.3)

                # Step 3 & 4: Reset C:/ToolboxData and restore defaults
                defaults_dir = ROOT_DIR / "defaults"
                ok, msg, freed_mb = reset_all_data(defaults_dir)

                # Step 4: 90%
                progress_dlg.set_progress(90, "正在重置初始配置与刷新状态...", "恢复各组件 defaults 初始出厂配置")
                QApplication.processEvents()
                time.sleep(0.25)

                # Step 5: Refresh UI and show result
                self.poll_processes_and_stats()
                self.update_cache_display()

                if ok:
                    progress_dlg.finish(
                        True,
                        "清理与还原成功！",
                        f"已成功释放 {freed_mb:.2f} MB 空间，所有配置与缓存已重置完毕",
                        auto_close_delay_ms=0
                    )
                    self.set_status(f"完成！已还原初始默认设置并释放 {freed_mb:.2f} MB 空间。")
                else:
                    progress_dlg.finish(
                        False,
                        "清理遇到问题",
                        msg,
                        auto_close_delay_ms=0
                    )
                    self.set_status(msg)
            except Exception as e:
                progress_dlg.finish(False, "清理异常中断", str(e), auto_close_delay_ms=0)
                self.set_status(f"清理出错: {e}")

        QTimer.singleShot(100, run_cleanup_steps)
        progress_dlg.exec()


    def start_background_update_check(self):
        """Starts silent background update check if enabled in settings."""
        try:
            from common.app_updater import SilentUpdateChecker
            self.silent_updater = SilentUpdateChecker(self.on_update_found_silently)
            self.silent_updater.start_check()
        except Exception:
            pass

    def on_update_found_silently(self, latest_tag: str, releases: list):
        """Called when background worker discovers a newer release on GitHub."""
        self.preloaded_releases = releases
        self.btn_check_update.setText(f"✨ 发现新版本 {latest_tag}")
        self.btn_check_update.setToolTip(f"发现新版本 {latest_tag} 可供更新，点击立即查看更新日志并在线安装！")
        self.btn_check_update.setStyleSheet("""
            background-color: #8FE3B0;
            color: #10231A;
            border: none;
            border-radius: 9px;
            padding: 7px 14px;
            font-size: 13px;
            font-weight: 800;
        """)

    def on_check_update_clicked(self):
        """Opens the full update dialog allowing user to choose any GitHub release to update to."""
        try:
            from common.app_updater import show_update_dialog
            show_update_dialog(parent=self, preloaded_releases=self.preloaded_releases)
        except Exception as e:
            ModernDialog.warning(parent=self, title="检查更新失败", message=f"无法打开更新器窗口:\n{e}")

    def open_toolbox_data_dir(self):
        """Opens C:/ToolboxData in Windows File Explorer."""
        try:
            if not TOOLBOX_ROOT.exists():
                TOOLBOX_ROOT.mkdir(parents=True, exist_ok=True)
            subprocess.Popen(["explorer.exe", str(TOOLBOX_ROOT)])
        except Exception as e:
            ModernDialog.warning(self, "打开失败", f"无法打开目录:\n{e}")

    def closeEvent(self, event):
        """Optionally confirm if child processes are still running when launcher closes."""
        running_count = sum(1 for p in self.running_processes.values() if p.poll() is None)
        if running_count > 0:
            confirmed = ModernDialog.confirm(
                parent=self,
                title="退出提示",
                message=f"当前还有 {running_count} 个子软件正在运行中。\n\n关闭工具箱首页不会强制中断已打开的子软件。\n是否确定退出首页启动器？",
                confirm_text="退出启动器",
                cancel_text="取消",
                icon_type="question"
            )
            if not confirmed:
                event.ignore()
                return

        event.accept()


def main():
    app = QApplication(sys.argv)
    from common.ui_theme import install_combo_arrows
    install_combo_arrows(app)
    
    # Global clear font
    app_font = QFont("Microsoft YaHei UI", 10)
    app_font.setStyleStrategy(QFont.PreferAntialias | QFont.PreferQuality)
    app.setFont(app_font)

    # Windows AppID
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Toolbox.Master.Launcher.1.0")
    except Exception:
        pass

    window = ToolboxLauncher()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
