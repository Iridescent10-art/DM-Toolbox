"""
Universal MFG Patcher - High-DPI Modern Frameless Qt UI with Light/Dark Themes.
Updated:
- RHI (ReShade HDR Installer) Full Integration
- Beautiful Themed Secondary Dialogs (ModernDialog, no native Windows popups)
- Fixed QTableWidget black corners and empty area artifacts
- Clear Target Game status and manifest details in Restore/Backup page
- High-res Multi-Frame Generation Icons across window, taskbar, and UI badges
- Support for Domestic Games (燕云十六声, 鹰角终末地, 黑神话, WeGame, etc.)
"""

import sys
import os
import ctypes
import json
import threading
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any

# Windows Taskbar Icon AppUserModelID
if sys.platform == "win32":
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("UniversalMFG.Patcher.1.0")
    except Exception:
        pass

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, Signal, QObject, QPoint, QTimer, QEvent, QFileSystemWatcher, QSize
from PySide6.QtGui import QIcon, QPixmap, QColor, QFont, QGuiApplication, QCursor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QFrame, QFileDialog, QDialog,
    QGridLayout, QStackedWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QLineEdit, QScrollArea, QSizePolicy,
    QTextBrowser, QTabWidget, QCheckBox, QSlider, QButtonGroup
)
from ctypes import wintypes

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

# Toolbox common config & theme
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common.config_manager import get_global_theme, set_global_theme
from common.ui_theme import CaptionButton, CaptionButtonType, ModernProgressDialog, ProgressSignalBridge, theme_toggle_icon
from common.dm_ui_core import DMSizeGrip, apply_dm_window_frame

# Core modules
from core.models import BackendType, QualificationStatus, GameInfo
from core.scanner import GameScanner
from core.game_cache import GameCacheManager
from core.updater import ComponentUpdater, DEFAULT_MIRRORS
from core.patcher import PatchEngine
from core.rollback import RollbackEngine
from core.rhi_installer import RHIInstaller
from core.utils import get_system_gpu_name, is_rtx_40_or_newer
from core.ini_sync import IniConfigManager
from core.optiscaler_config import (
    load_optiscaler_preset, save_optiscaler_preset,
    get_preset_summary, DEFAULT_OPTISCALER_PRESET,
    load_reshade_preset, save_reshade_preset,
    get_reshade_preset_summary, DEFAULT_RESHADE_PRESET,
    load_mode_a_preset, save_mode_a_preset,
    get_mode_a_preset_summary, DEFAULT_MODE_A_PRESET
)

class WorkerSignals(QObject):
    scan_finished = Signal(list)
    update_finished = Signal(list)
    rhi_finished = Signal(bool, str)
    status_updated = Signal(str)
    progress_updated = Signal(int, str, str)  # val (0-100), text, detail

# ----------------- CUSTOM THEMED MODAL DIALOG -----------------
class ModernDialog(QDialog):
    """Clean modern modal dialog with rounded corners and light/dark theme matching."""
    def __init__(self, parent, title: str, message: str, dialog_type: str = "info", is_dark: bool = False):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(460)

        bg_color = "#2A2B2C" if is_dark else "#ffffff"
        border_color = "#3A3A3A" if is_dark else "#D4D4D4"
        text_color = "#F5F5F5" if is_dark else "#292929"
        msg_color = "#94a3b8" if is_dark else "#4A4A4A"

        type_map = {
            "info": ("ℹ", "#E8E8E8", "#26784C"),
            "success": ("✓", "#dcfce7", "#16a34a"),
            "warning": ("⚠", "#F5F5F5", "#d97706"),
            "error": ("✕", "#fee2e2", "#dc2626"),
            "question": ("?", "#ede9fe", "#7c3aed")
        }
        icon_char, b_bg, b_fg = type_map.get(dialog_type, ("ℹ", "#E8E8E8", "#26784C"))

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        card = QFrame()
        card.setStyleSheet(f"""
            background-color: {bg_color};
            border: 1px solid {border_color};
            border-radius: 14px;
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 20, 22, 20)
        card_layout.setSpacing(14)

        # Header
        header = QHBoxLayout()
        header.setSpacing(12)

        badge = QLabel(icon_char)
        badge.setFixedSize(36, 36)
        badge.setStyleSheet(f"""
            background-color: {b_bg};
            color: {b_fg};
            border-radius: 10px;
            font-size: 18px;
            font-weight: bold;
            qproperty-alignment: AlignCenter;
            border: none;
        """)
        header.addWidget(badge)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {text_color}; border: none;")
        header.addWidget(lbl_title)
        header.addStretch()

        btn_x = QPushButton("✕")
        btn_x.setFixedSize(28, 28)
        btn_x.setStyleSheet(f"background: transparent; color: {msg_color}; border: none; font-size: 14px; font-weight: bold;")
        btn_x.clicked.connect(self.reject)
        header.addWidget(btn_x)

        card_layout.addLayout(header)

        # Body Message
        lbl_msg = QLabel(message)
        lbl_msg.setStyleSheet(f"font-size: 13px; color: {msg_color}; line-height: 1.4; border: none;")
        lbl_msg.setWordWrap(True)
        card_layout.addWidget(lbl_msg)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        if dialog_type == "question":
            btn_cancel = QPushButton("取消")
            btn_cancel.setStyleSheet("""
                background-color: #E5E5E5;
                color: #3A3A3A;
                border: none;
                border-radius: 8px;
                padding: 8px 20px;
                font-weight: 600;
                font-size: 13px;
            """)
            btn_cancel.clicked.connect(self.reject)
            btn_row.addWidget(btn_cancel)

            btn_ok = QPushButton("确认执行")
            btn_ok.setStyleSheet("""
                background-color: #2F8F5B;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 8px 22px;
                font-weight: bold;
                font-size: 13px;
            """)
            btn_ok.clicked.connect(self.accept)
            btn_row.addWidget(btn_ok)
        else:
            btn_ok = QPushButton("我知道了")
            btn_ok.setStyleSheet("""
                background-color: #2F8F5B;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 8px 24px;
                font-weight: bold;
                font-size: 13px;
            """)
            btn_ok.clicked.connect(self.accept)
            btn_row.addWidget(btn_ok)

        card_layout.addLayout(btn_row)
        main_layout.addWidget(card)

    @classmethod
    def info(cls, parent, title: str, message: str, is_dark: bool = False):
        dlg = cls(parent, title, message, "info", is_dark)
        return dlg.exec()

    @classmethod
    def success(cls, parent, title: str, message: str, is_dark: bool = False):
        dlg = cls(parent, title, message, "success", is_dark)
        return dlg.exec()

    @classmethod
    def warning(cls, parent, title: str, message: str, is_dark: bool = False):
        dlg = cls(parent, title, message, "warning", is_dark)
        return dlg.exec()

    @classmethod
    def error(cls, parent, title: str, message: str, is_dark: bool = False):
        dlg = cls(parent, title, message, "error", is_dark)
        return dlg.exec()

    @classmethod
    def confirm(cls, parent, title: str, message: str, is_dark: bool = False) -> bool:
        dlg = cls(parent, title, message, "question", is_dark)
        return dlg.exec() == QDialog.DialogCode.Accepted


class ModernTranslationGuideDialog(QDialog):
    """
    Rich interactive guide & English-Chinese translation modal
    for all Frame Generation backends (Mode A, Mode B, Mode C / OptiScaler).
    """
    def __init__(self, parent=None, is_dark: bool = False, initial_tab: int = 0):
        super().__init__(parent)
        self.is_dark = is_dark
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # Responsive screen adaptation
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            dlg_w = max(860, min(1000, int(avail.width() * 0.78)))
            dlg_h = max(600, min(760, int(avail.height() * 0.82)))
            self.resize(dlg_w, dlg_h)
            self.move(
                avail.left() + max(0, (avail.width() - dlg_w) // 2),
                avail.top() + max(0, (avail.height() - dlg_h) // 2)
            )
        else:
            self.resize(880, 650)

        bg_color = "#2A2B2C" if is_dark else "#ffffff"
        border_color = "#3A3A3A" if is_dark else "#D4D4D4"
        text_color = "#F5F5F5" if is_dark else "#292929"

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)

        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 14px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(14)

        # Header
        header = QHBoxLayout()
        header.setSpacing(12)

        badge = QLabel("📖")
        badge.setFixedSize(36, 36)
        badge.setStyleSheet(f"""
            background-color: {'#1e3a8a' if is_dark else '#E8E8E8'};
            color: {'#7ED9A2' if is_dark else '#26784C'};
            border-radius: 10px;
            font-size: 18px;
            qproperty-alignment: AlignCenter;
            border: none;
        """)
        header.addWidget(badge)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        lbl_title = QLabel("三大插帧模式使用指南与游戏内中英文对照速查")
        lbl_title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {text_color}; border: none;")
        title_box.addWidget(lbl_title)
        lbl_sub = QLabel("全插帧方案保姆级教程、按键说明与 OptiScaler 游戏内悬浮菜单逐项中文释义")
        lbl_sub.setStyleSheet(f"font-size: 11px; color: {'#94a3b8' if is_dark else '#64748b'}; border: none;")
        title_box.addWidget(lbl_sub)
        header.addLayout(title_box)
        header.addStretch()

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(28, 28)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {'#94a3b8' if is_dark else '#64748b'};
                border: none;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background: {'#3A3A3A' if is_dark else '#EFEFEF'};
                color: {'#ef4444' if is_dark else '#dc2626'};
            }}
        """)
        btn_close.clicked.connect(self.accept)
        header.addWidget(btn_close)
        card_layout.addLayout(header)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {border_color};
                background: {bg_color};
                border-radius: 10px;
                padding: 6px;
            }}
            QTabBar::tab {{
                background: {'#3A3A3A' if is_dark else '#E5E5E5'};
                color: {'#D4D4D4' if is_dark else '#4A4A4A'};
                border-radius: 8px;
                padding: 8px 16px;
                margin-right: 6px;
                margin-bottom: 6px;
                font-weight: 600;
                font-size: 12px;
            }}
            QTabBar::tab:selected {{
                background: #2F8F5B;
                color: #ffffff;
            }}
            QTabBar::tab:hover:!selected {{
                background: {'#4A4A4A' if is_dark else '#D4D4D4'};
                color: {'#F5F5F5' if is_dark else '#292929'};
            }}
            QTabBar::scroller {{
                width: 38px;
            }}
            QTabBar QToolButton {{
                background-color: #2F8F5B;
                color: #ffffff;
                border: 1px solid #26784C;
                border-radius: 6px;
                margin: 1px;
                padding: 2px;
                font-weight: bold;
                min-width: 22px;
                min-height: 22px;
            }}
            QTabBar QToolButton:hover {{
                background-color: #26784C;
            }}
            QTabBar QToolButton:pressed {{
                background-color: #1e40af;
            }}
            QTabBar QToolButton:disabled {{
                background-color: {'#3A3A3A' if is_dark else '#E5E5E5'};
                border-color: {'#4A4A4A' if is_dark else '#D4D4D4'};
                color: {'#64748b' if is_dark else '#94a3b8'};
            }}
        """)

        # Tabs are ordered A -> B -> C so the guide always reads in the same order as the
        # rest of the toolbox (no more C/B/A zig-zag).
        self.tabs.addTab(self._create_standalone_tab(is_dark), "📦 模式 A · dashdogy 独立代理 (Backspace)")
        self.tabs.addTab(self._create_reshade_tab(is_dark), "🎨 模式 B · RenoDX ReShade 插件 (Home)")
        self.tabs.addTab(self._create_optiscaler_tab(is_dark), "🚀 模式 C · OptiScaler 跨卡转译 (Insert)")

        self.tabs.setCurrentIndex(initial_tab)
        card_layout.addWidget(self.tabs, 1)

        # Footer Button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_ok = QPushButton("我知道了")
        btn_ok.setStyleSheet("""
            background-color: #2F8F5B;
            color: #ffffff;
            border: none;
            border-radius: 8px;
            padding: 8px 26px;
            font-weight: bold;
            font-size: 13px;
        """)
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_ok)
        card_layout.addLayout(btn_row)

        main_layout.addWidget(card)

    def _create_browser(self, html_content: str, is_dark: bool) -> QTextBrowser:
        tb = QTextBrowser()
        tb.setOpenExternalLinks(True)
        tb.setStyleSheet(f"""
            QTextBrowser {{
                background-color: {'#292929' if is_dark else '#F5F5F5'};
                color: {'#E5E5E5' if is_dark else '#2A2B2C'};
                border: 1px solid {'#3A3A3A' if is_dark else '#E5E5E5'};
                border-radius: 8px;
                padding: 12px;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
            }}
        """)
        tb.setHtml(html_content)
        return tb

    def _create_optiscaler_tab(self, is_dark: bool) -> QWidget:
        th_bg = '#2A2B2C' if is_dark else '#E5E5E5'
        td_border = '#3A3A3A' if is_dark else '#D4D4D4'
        badge_blue = '<span style="background-color: #2F8F5B; color: #ffffff; padding: 2px 6px; border-radius: 4px; font-weight: bold;">【Insert】键</span>'
        html = f"""
        <div style="line-height: 1.6; font-size: 13px;">
            <h3 style="color: #3E9E69; margin-top: 0;">🚀 模式 C · OptiScaler 跨卡转译（Insert）</h3>
            <p><b>适用显卡</b>：全架构通用 —— NVIDIA RTX 20/30/40/50 系列、GTX 系列、AMD Radeon、Intel Arc。</p>
            <p><b>核心使用方法</b>：修补完成后进入游戏，在游戏的<b>【画质 / 图像设置】</b>中直接开启原本被禁用的<b>【DLSS 帧生成 (Frame Generation)】</b>开关。OptiScaler 会在底层接管并转译为 <b>Intel XeFG</b>（默认，2X）或 <b>AMD FSR 3.1 FG</b> 运行，游戏帧率即刻翻倍。</p>
            <p><b>游戏内控制台呼出快捷键</b>：进入游戏随时按下键盘 {badge_blue}，即可呼出或隐藏悬浮控制台。若觉得 4K 下菜单过小，请在【模式 C 预设面板 → 游戏内菜单界面大小】选择 <code>2.0x</code>。</p>
            <hr style="border: 0; border-top: 1px solid {td_border}; margin: 12px 0;">
            <h4 style="color: #8FE3B0; margin: 8px 0;">📋 游戏内悬浮菜单中英文对照表（逐项中文释义）</h4>
            <table border="1" cellpadding="6" cellspacing="0" style="width: 100%; border-collapse: collapse; border-color: {td_border}; font-size: 12px;">
                <tr style="background-color: {th_bg}; font-weight: bold;">
                    <th style="width: 28%; text-align: left;">英文原版名称</th>
                    <th style="width: 28%; text-align: left;">中文功能释义</th>
                    <th style="text-align: left;">推荐设置与操作说明</th>
                </tr>
                <tr>
                    <td><b>Upscalers</b></td>
                    <td>超分辨率算法引擎</td>
                    <td>当前默认使用 DLSS 超分（可点击 Change Upscaler 自由切换为 FSR 2/3 或 XeSS）。</td>
                </tr>
                <tr>
                    <td><b>Frame Generation</b></td>
                    <td>帧生成 / 插帧模块</td>
                    <td><b>核心转译区域</b>：<br>• <b>FG Input</b>：插帧劫持接口（默认 <code>DLSSG</code> / Streamline）<br>• <b>FG Output</b>：最终生成算法（默认 <code>XeFG</code> · Intel XeSS 2.0 官方插帧；也可切到 <code>FSR FG</code>）<br>⚠️ 若修改此处，需点击底部 <b>Save Settings</b> 并重启游戏生效。</td>
                </tr>
                <tr>
                    <td><b>Framerate</b></td>
                    <td>帧率与延迟控制</td>
                    <td>• <b>Current method: Reflex</b>：当前开启 NVIDIA Reflex 低延迟<br>• <b>FPS Limit</b>：最大帧率限制（输入 0 表示不锁帧）。</td>
                </tr>
                <tr>
                    <td><b>VRR Frame Cap Calculator</b></td>
                    <td>防撕裂锁帧计算器</td>
                    <td>在 <b>Refresh Rate</b> 输入您的显示器刷新率（如 160Hz），点击 <b>Set as FPS Limit</b>，会自动锁定在 152.7 FPS（为 G-Sync / FreeSync 预留缓冲区，彻底防止画面撕裂）。</td>
                </tr>
                <tr>
                    <td><b>Sharpness</b></td>
                    <td>画质清晰度与锐化</td>
                    <td>• <b>Enable RCAS/DA</b>：勾选开启 AMD 对比度自适应锐化<br>• <b>Sharpness 滑块</b>：调节锐化强度（推荐 <code>0.300 ~ 0.500</code> 之间最自然清晰）。</td>
                </tr>
                <tr>
                    <td><b>Menu Scale</b></td>
                    <td>菜单界面缩放</td>
                    <td>4K (3840×2160) 建议 <code>2.0</code>，2K 建议 <code>1.5</code>。可直接在工具箱【模式 C 预设面板 → 游戏内菜单界面大小】设置，自动写入 <code>[Menu] Scale</code>，无需手改 INI。</td>
                </tr>
                <tr>
                    <td><b>Save Settings (底部)</b></td>
                    <td>保存当前配置</td>
                    <td>点击将当前窗口所有参数永久保存到游戏根目录的 <code>OptiScaler.ini</code>（v0.9.4 唯一合法配置，旧 <code>nvngx.ini</code> 会被自动清除）。</td>
                </tr>
                <tr>
                    <td><b>Close (底部)</b></td>
                    <td>关闭悬浮菜单</td>
                    <td>关闭当前控制面板（与键盘 【Insert】 键功能相同）。</td>
                </tr>
            </table>
        </div>
        """
        return self._create_browser(html, is_dark)

    def _create_reshade_tab(self, is_dark: bool) -> QWidget:
        td_border = '#3A3A3A' if is_dark else '#D4D4D4'
        badge_home = '<span style="background-color: #16a34a; color: #ffffff; padding: 2px 6px; border-radius: 4px; font-weight: bold;">【Home】键</span>'
        html = f"""
        <div style="line-height: 1.6; font-size: 13px;">
            <h3 style="color: #10b981; margin-top: 0;">🎨 模式 B · RenoDX ReShade 插件（Home）</h3>
            <div style="background-color: {'#3b1812' if is_dark else '#fff7ed'}; border-left: 4px solid #ea580c; padding: 10px 14px; border-radius: 4px; margin-bottom: 12px;">
                <b>❓ 为什么安装了模式 B 进入游戏却没有显示？</b><br>
                <b>原因</b>：模式 B 是一个 <b>ReShade Addon 插件</b> (<code>renodx-mfgunlock.addon64</code>)，它必须依赖游戏本身安装了 <b>带 Addon 支持的 ReShade 底座</b> (即 <code>dxgi.dll</code>) 才能被载入。如果游戏未安装底座，进入游戏时游戏根本不会执行插件，按 Home 键也不会有任何面板出现！
            </div>
            <h4 style="color: #34d399; margin: 8px 0;">🚀 模式 B 正确安装三部曲（一步到位）：</h4>
            <ol style="padding-left: 20px;">
                <li><b>一键启动 RHI 为游戏安装底座</b>：<br>
                在本工具箱主界面点击【🚀 一键启动 RHI 为当前游戏安装 ReShade 底座】（软件会自动将游戏 exe 路径复制到剪贴板）。</li>
                <li><b>在 RHI 中选择游戏并完成安装</b>：<br>
                在打开的 RHI 窗口中点击选择游戏（文件对话框按 <code>Ctrl+V</code> 直接粘贴路径直达），渲染 API 勾选 <b>DirectX 11/12</b>，并务必勾选 <b>【ReShade with full add-on support】</b> 完成安装。</li>
                <li><b>进入游戏开启插帧</b>：<br>
                启动游戏后，屏幕顶部会出现 ReShade 灰色横幅，按下键盘 {badge_home} 呼出面板，在【Add-ons】选项卡中可以看到 <code>RenoDX MFG Unlock</code> 已正常挂载生效！此时在游戏设置中打开【DLSS 帧生成】即可！</li>
            </ol>
        </div>
        """
        return self._create_browser(html, is_dark)

    def _create_standalone_tab(self, is_dark: bool) -> QWidget:
        badge_bs = '<span style="background-color: #2F8F5B; color: #ffffff; padding: 2px 6px; border-radius: 4px; font-weight: bold;">【Backspace】(退格键)</span>'
        html = f"""
        <div style="line-height: 1.6; font-size: 13px;">
            <h3 style="color: #3E9E69; margin-top: 0;">📦 模式 A · dashdogy 独立代理（Backspace）</h3>
            <p><b>适用显卡</b>：NVIDIA GeForce RTX 40 / 50 系列。</p>
            <p><b>核心优势</b>：零外部依赖，使用微软系统级代理 DLL (<code>version.dll</code> 或 <code>winmm.dll</code>) 劫持注入，完全原生兼容，性能损耗为 0。</p>
            <p><b>游戏内快捷键</b>：进入游戏按下键盘 {badge_bs} 可呼出内置设置菜单。</p>
            <p><b>开启方式</b>：进入游戏系统的【画质设置】/【图像设置】，将【DLSS 帧生成】开关直接打开即可享受流畅多帧生成！</p>
        </div>
        """
        return self._create_browser(html, is_dark)


class ModernRHIGuideDialog(QDialog):
    """
    Dedicated RHI Launch & Path Navigation Assistant.
    Solves the common user problem where pasting an .exe path into Windows File Dialog's
    top address bar fails, by providing distinct copy buttons for:
    1. Full Executable Path (for bottom 'File name' input box)
    2. Folder Directory Path (for top 'Address Bar' breadcrumb navigation)
    3. Direct explorer directory opening.
    """
    def __init__(self, parent=None, game_info: Optional[GameInfo] = None, rhi_installer: Optional[RHIInstaller] = None, is_dark: bool = False):
        super().__init__(parent)
        self.game = game_info
        self.rhi = rhi_installer
        self.is_dark = is_dark

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # Responsive screen adaptation
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            dlg_w = max(740, min(880, int(avail.width() * 0.72)))
            dlg_h = max(580, min(700, int(avail.height() * 0.78)))
            self.resize(dlg_w, dlg_h)
            self.move(
                avail.left() + max(0, (avail.width() - dlg_w) // 2),
                avail.top() + max(0, (avail.height() - dlg_h) // 2)
            )
        else:
            self.resize(760, 600)

        bg_color = "#2A2B2C" if is_dark else "#ffffff"
        border_color = "#3A3A3A" if is_dark else "#D4D4D4"
        text_color = "#F5F5F5" if is_dark else "#292929"

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)

        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 14px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        header.setSpacing(12)

        badge = QLabel("🛠️")
        badge.setFixedSize(36, 36)
        badge.setStyleSheet(f"""
            background-color: {'#064e3b' if is_dark else '#d1fae5'};
            color: {'#34d399' if is_dark else '#059669'};
            border-radius: 10px;
            font-size: 18px;
            qproperty-alignment: AlignCenter;
            border: none;
        """)
        header.addWidget(badge)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        lbl_title = QLabel("ReShade / RHI 模组底座安装与路径直达助手")
        lbl_title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {text_color}; border: none;")
        title_box.addWidget(lbl_title)
        lbl_sub = QLabel("一键秒速定位游戏主程序，解决 Windows 文件选择框地址栏无法直接跳转 .exe 的问题")
        lbl_sub.setStyleSheet(f"font-size: 11px; color: {'#94a3b8' if is_dark else '#64748b'}; border: none;")
        title_box.addWidget(lbl_sub)
        header.addLayout(title_box)
        header.addStretch()

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(28, 28)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {'#94a3b8' if is_dark else '#64748b'};
                border: none;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background: {'#3A3A3A' if is_dark else '#EFEFEF'};
                color: {'#ef4444' if is_dark else '#dc2626'};
            }}
        """)
        btn_close.clicked.connect(self.accept)
        header.addWidget(btn_close)
        card_layout.addLayout(header)

        # Game Info Box
        game_name = self.game.name if self.game else "未选择游戏"
        exe_path = self.game.exe_path if self.game else ""
        target_dir = self.game.target_dir if self.game else ""

        info_box = QFrame()
        info_box.setStyleSheet(f"""
            QFrame {{
                background-color: {'#292929' if is_dark else '#F5F5F5'};
                border: 1px solid {'#3A3A3A' if is_dark else '#E5E5E5'};
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        ib_layout = QVBoxLayout(info_box)
        ib_layout.setSpacing(6)

        lbl_gname = QLabel(f"🎮 当前目标游戏: <b>{game_name}</b>")
        lbl_gname.setStyleSheet(f"font-size: 13px; color: {text_color}; border: none;")
        ib_layout.addWidget(lbl_gname)

        lbl_gpath = QLabel(f"📁 主程序路径: <code style='color: {'#7ED9A2' if is_dark else '#2F8F5B'};'>{exe_path}</code>")
        lbl_gpath.setWordWrap(True)
        lbl_gpath.setStyleSheet(f"font-size: 11px; color: {'#94a3b8' if is_dark else '#64748b'}; border: none;")
        ib_layout.addWidget(lbl_gpath)

        card_layout.addWidget(info_box)

        # Quick Copy Buttons Row
        btn_row_copy = QHBoxLayout()
        btn_row_copy.setSpacing(10)

        self.btn_copy_file = QPushButton("📋 复制主程序完整路径 (推荐)")
        self.btn_copy_file.setStyleSheet("""
            QPushButton {
                background-color: #2F8F5B;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 8px 14px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #26784C;
            }
        """)
        self.btn_copy_file.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy_file.clicked.connect(self._copy_exe_path)
        btn_row_copy.addWidget(self.btn_copy_file)

        self.btn_copy_dir = QPushButton("📁 复制所在文件夹路径")
        self.btn_copy_dir.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 8px 14px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #047857;
            }
        """)
        self.btn_copy_dir.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy_dir.clicked.connect(self._copy_dir_path)
        btn_row_copy.addWidget(self.btn_copy_dir)

        self.btn_open_folder = QPushButton("📂 在资源管理器中打开")
        self.btn_open_folder.setStyleSheet(f"""
            QPushButton {{
                background-color: {'#3A3A3A' if is_dark else '#E5E5E5'};
                color: {'#E5E5E5' if is_dark else '#3A3A3A'};
                border: none;
                border-radius: 8px;
                padding: 8px 14px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {'#4A4A4A' if is_dark else '#D4D4D4'};
            }}
        """)
        self.btn_open_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_folder.clicked.connect(self._open_in_explorer)
        btn_row_copy.addWidget(self.btn_open_folder)

        card_layout.addLayout(btn_row_copy)

        # Explanatory Guide Box (HTML)
        guide_browser = QTextBrowser()
        guide_browser.setOpenExternalLinks(True)
        guide_browser.setStyleSheet(f"""
            QTextBrowser {{
                background-color: {'#292929' if is_dark else '#F5F5F5'};
                border: 1px solid {'#3A3A3A' if is_dark else '#E5E5E5'};
                border-radius: 10px;
                color: {text_color};
                padding: 10px;
            }}
        """)

        html = f"""
        <div style="line-height: 1.6; font-size: 12px; color: {text_color};">
            <div style="background-color: {'#422006' if is_dark else '#F5F5F5'}; border-left: 4px solid #f59e0b; padding: 8px 12px; border-radius: 4px; margin-bottom: 10px;">
                <b style="color: {'#fbbf24' if is_dark else '#b45309'}; font-size: 13px;">⚠️ 为什么在文件选择窗口顶部的地址栏粘贴会无法跳转？</b><br>
                在 Windows 文件选择窗口中，<b>最顶部的地址栏只接受“文件夹路径”</b>。如果您把 <code>...\\yysls.exe</code> 这类包含主程序文件名的路径粘贴在顶部，Windows 会将其误当作文件夹查找而导致无法跳转或报错。
            </div>
            
            <b style="color: {'#8FE3B0' if is_dark else '#0284c7'}; font-size: 13px;">✨ 正确跳转方法（两种方法 100% 成功，任选一种）：</b><br>
            <ol style="margin-top: 4px; padding-left: 20px;">
                <li><b>方法 1（最简单秒选·强烈推荐）：</b><br>
                点击上方【📋 复制主程序完整路径】，在 RHI 弹出的文件选择器<b>最下方【文件名(N)】框内</b>按 <code>Ctrl + V</code> 粘贴，然后直接按回车或点击【打开(O)】，即可瞬间精确选中！</li>
                <li><b>方法 2（地址栏跳转法）：</b><br>
                点击上方【📁 复制所在文件夹路径】，粘贴到<b>窗口最顶部的【地址栏】</b>按回车进入文件夹，就能直接在列表中看到 <code>yysls.exe</code>，双击它即可！</li>
            </ol>

            <div style="background-color: {'#064e3b' if is_dark else '#ecfdf5'}; border-left: 4px solid #10b981; padding: 8px 12px; border-radius: 4px; margin-top: 8px;">
                <b style="color: {'#34d399' if is_dark else '#047857'}; font-size: 13px;">💡 RHI 安装关键注意：</b><br>
                在 RHI 界面中选中游戏后，渲染 API 请根据游戏选择 <b>DirectX 11/12</b>，并且<b>务必勾选【ReShade with full add-on support】</b>完成安装！安装完毕后进入游戏，按键盘 <b>【Home】键</b> 即可看到 RenoDX 插帧插件已完美激活！
            </div>
        </div>
        """
        guide_browser.setHtml(html)
        card_layout.addWidget(guide_browser, 1)

        # Footer Actions
        footer = QHBoxLayout()
        footer.setSpacing(12)
        footer.addStretch()

        btn_launch = QPushButton("🚀 立即拉起 RHI 程序")
        btn_launch.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 9px 24px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #047857;
            }
        """)
        btn_launch.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_launch.clicked.connect(self._launch_rhi_action)
        footer.addWidget(btn_launch)

        btn_ok = QPushButton("我知道了")
        btn_ok.setStyleSheet(f"""
            QPushButton {{
                background-color: {'#3A3A3A' if is_dark else '#E5E5E5'};
                color: {'#E5E5E5' if is_dark else '#3A3A3A'};
                border: none;
                border-radius: 8px;
                padding: 9px 20px;
                font-weight: 600;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {'#4A4A4A' if is_dark else '#D4D4D4'};
            }}
        """)
        btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_ok.clicked.connect(self.accept)
        footer.addWidget(btn_ok)

        card_layout.addLayout(footer)
        main_layout.addWidget(card)

    def _copy_exe_path(self):
        if self.game and self.game.exe_path:
            QApplication.clipboard().setText(self.game.exe_path)
            self.btn_copy_file.setText("✓ 已复制主程序路径 (去底部【文件名】框粘贴)")
            QTimer.singleShot(2500, lambda: self.btn_copy_file.setText("📋 复制主程序完整路径 (推荐)"))

    def _copy_dir_path(self):
        if self.game and self.game.target_dir:
            QApplication.clipboard().setText(self.game.target_dir)
            self.btn_copy_dir.setText("✓ 已复制文件夹路径 (去顶部【地址栏】粘贴)")
            QTimer.singleShot(2500, lambda: self.btn_copy_dir.setText("📁 复制所在文件夹路径"))

    def _open_in_explorer(self):
        if self.game and self.game.exe_path and os.path.exists(self.game.exe_path):
            try:
                subprocess.Popen(f'explorer.exe /select,"{os.path.normpath(self.game.exe_path)}"')
            except Exception:
                try:
                    os.startfile(self.game.target_dir)
                except Exception:
                    pass
        elif self.game and self.game.target_dir and os.path.exists(self.game.target_dir):
            try:
                os.startfile(self.game.target_dir)
            except Exception:
                pass

    def _launch_rhi_action(self):
        self._copy_exe_path()
        if self.rhi:
            ok, msg = self.rhi.launch_rhi()
            if not ok:
                ModernDialog.error(self, "启动 RHI 失败", msg, self.is_dark)


# ----------------- CUSTOM MULTI-FRAME GENERATION PRESET DIALOG -----------------
class OptiScalerPresetDialog(QDialog):
    """
    Modern modal dialog for pre-configuring Mode A (dashdogy MFG-Unlocker),
    Mode B (RenoDX ReShade Addon), and Mode C (OptiScaler / XeSS 2.0 / FSR 3.1)
    parameters with real-time bi-directional INI synchronization.
    """
    def __init__(
        self,
        parent=None,
        is_dark: bool = False,
        game: Optional[GameInfo] = None,
        initial_mode: Optional[str] = None,
        *args,
        current_mode: Optional[str] = None,
        mode: Optional[str] = None,
        active_mode: Optional[str] = None,
        **kwargs
    ):
        # Handle string passed as first argument (e.g. OptiScalerPresetDialog("A"))
        if isinstance(parent, str):
            initial_mode = parent
            parent = None

        super().__init__(parent)
        self.is_dark = is_dark
        self.game = game or (parent.selected_game if hasattr(parent, "selected_game") else None)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        dlg_w = 1080
        self.setMinimumWidth(1060)

        # Responsive placement
        screen = QGuiApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            dlg_w = max(1080, min(1160, int(avail.width() * 0.7))) if avail.width() >= 1080 else 1080
            dlg_h = min(int(avail.height() * 0.94), 780)
            self.setMinimumHeight(min(680, dlg_h))
            self.resize(dlg_w, dlg_h)
            self.move(
                avail.left() + max(0, (avail.width() - dlg_w) // 2),
                avail.top() + max(0, (avail.height() - dlg_h) // 2)
            )
        else:
            self.setMinimumHeight(680)
            self.resize(1080, 760)

        # Windows 11 DWM rounded corners
        try:
            hwnd = int(self.winId())
            corner_val = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(corner_val), ctypes.sizeof(corner_val))
            dark_val = ctypes.c_int(1 if is_dark else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark_val), ctypes.sizeof(dark_val))
        except Exception:
            pass

        # Load presets: merge in-game INI values if the target game folder already has configs
        self.preset_a = load_mode_a_preset()
        self.preset_b = load_reshade_preset()
        self.preset_c = load_optiscaler_preset()
        if self.game and self.game.target_dir:
            disk_a = IniConfigManager.read_mode_a_reverse(self.game.target_dir)
            if disk_a:
                self.preset_a.update(disk_a)
            disk_b = IniConfigManager.read_mode_b_reverse(self.game.target_dir)
            if disk_b:
                self.preset_b.update(disk_b)
            disk_c = IniConfigManager.read_mode_c_reverse(self.game.target_dir)
            if disk_c:
                if disk_c.get("dx12_upscaler") in ("xess", "dlss") and not self.preset_c.get("user_customized_upscaler", False):
                    disk_c["dx12_upscaler"] = "auto"
                self.preset_c.update(disk_c)
            else:
                # 目标游戏未安装过 OptiScaler (第一次安装/打补丁)
                # 默认超分必须 100% 确保为 auto (自动继承游戏内设定)
                self.preset_c["dx12_upscaler"] = "auto"
        else:
            self.preset_c["dx12_upscaler"] = "auto"

        if not self.preset_c.get("user_customized_upscaler", False):
            self.preset_c["dx12_upscaler"] = "auto"

        self._drag_pos = QPoint()
        self._is_dragging = False

        # Resolve mode
        raw_mode = initial_mode or current_mode or mode or active_mode
        for arg in args:
            if isinstance(arg, str):
                raw_mode = arg
                break

        if not raw_mode and parent and hasattr(parent, "combo_backend") and parent.combo_backend:
            cb_data = parent.combo_backend.currentData()
            cb_str = str(cb_data.value if hasattr(cb_data, "value") else cb_data).lower()
            if "standalone" in cb_str or "dashdogy" in cb_str:
                raw_mode = "A"
            elif "reshade" in cb_str or "mavis" in cb_str:
                raw_mode = "B"
            elif "optiscaler" in cb_str or "fsr" in cb_str:
                raw_mode = "C"

        if not raw_mode and self.game:
            if self.game.patched_backend:
                pb = str(self.game.patched_backend).lower()
                if "standalone" in pb or "dashdogy" in pb:
                    raw_mode = "A"
                elif "reshade" in pb or "mavis" in pb:
                    raw_mode = "B"
                elif "optiscaler" in pb:
                    raw_mode = "C"
            elif self.game.target_dir:
                td = Path(self.game.target_dir)
                if (td / "OptiScaler.ini").exists() or (td / "nvngx.ini").exists():
                    raw_mode = "C"
                elif (td / "renodx-mfgunlock.addon64").exists() or (td / "ReShade.ini").exists():
                    raw_mode = "B"
                elif (td / "RTXMFG-UI.ini").exists() or (td / "mfg_unlocker.ini").exists():
                    raw_mode = "A"

        mode_upper = str(raw_mode or "A").upper().strip()
        if "B" in mode_upper or "RESHADE" in mode_upper or "MAVIS" in mode_upper:
            target_idx = 1
        elif "C" in mode_upper or "OPTISCALER" in mode_upper or "XESS" in mode_upper or "FSR" in mode_upper:
            target_idx = 2
        else:
            target_idx = 0

        self.initial_tab_index = target_idx

        self._build_ui()

    def showEvent(self, event):
        super().showEvent(event)
        # 强制在首次显示时立即重算所有子控件与布局尺寸，彻底消除“需要拖动一下才正常”的Bug
        if self.layout():
            self.layout().activate()
        for i in range(self.stacked_widget.count()):
            page = self.stacked_widget.widget(i)
            if page and page.layout():
                page.layout().activate()
            if page:
                page.updateGeometry()
        self.updateGeometry()
        QTimer.singleShot(0, self._force_initial_relayout)

    def _force_initial_relayout(self):
        # 微调 1px 再还原，强制触发 Qt 底层的 resizeEvent 重排管线
        w, h = self.width(), self.height()
        self.resize(w + 1, h)
        self.resize(w, h)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._is_dragging and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._is_dragging = False

    def _build_ui(self):
        is_dark = self.is_dark
        bg_color = "#2A2B2C" if is_dark else "#ffffff"
        border_color = "#3A3A3A" if is_dark else "#D4D4D4"
        text_color = "#F5F5F5" if is_dark else "#292929"
        sub_text = "#94a3b8" if is_dark else "#64748b"
        card_bg = "#292929" if is_dark else "#F5F5F5"
        card_border = "#3A3A3A" if is_dark else "#E5E5E5"
        combo_bg = "#2A2B2C" if is_dark else "#ffffff"
        combo_border = "#4A4A4A" if is_dark else "#D4D4D4"

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)

        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 16px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 18, 22, 18)
        card_layout.setSpacing(12)

        # 1. Header
        header = QHBoxLayout()
        header.setSpacing(12)

        badge = QLabel("⚡")
        badge.setFixedSize(38, 38)
        badge.setStyleSheet(f"""
            background-color: {'#1e3a8a' if is_dark else '#E8E8E8'};
            color: {'#7ED9A2' if is_dark else '#26784C'};
            border-radius: 10px;
            font-size: 20px;
            qproperty-alignment: AlignCenter;
            border: none;
        """)
        header.addWidget(badge)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        lbl_title = QLabel("多帧生成预设与游戏内外双向同步配置")
        lbl_title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {text_color}; border: none;")
        title_box.addWidget(lbl_title)
        lbl_sub = QLabel("在此提前调定各插帧引擎参数，保存即自动写入游戏配置文件，游戏内修改实时回显")
        lbl_sub.setStyleSheet(f"font-size: 11px; color: {sub_text}; border: none;")
        title_box.addWidget(lbl_sub)
        header.addLayout(title_box)
        header.addStretch()

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(28, 28)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {sub_text};
                border: none;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background: {'#3A3A3A' if is_dark else '#EFEFEF'};
                color: {'#ef4444' if is_dark else '#dc2626'};
            }}
        """)
        btn_close.clicked.connect(self.reject)
        header.addWidget(btn_close)
        card_layout.addLayout(header)

        # 2. Real-Time Bi-Directional Synchronization Status Banner
        sync_banner = QFrame()
        sync_bg = "#064e3b33" if is_dark else "#ecfdf5"
        sync_border = "#059669"
        sync_banner.setStyleSheet(f"""
            QFrame {{
                background-color: {sync_bg};
                border-left: 4px solid {sync_border};
                border-radius: 6px;
                padding: 6px 12px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        sb_layout = QHBoxLayout(sync_banner)
        sb_layout.setContentsMargins(8, 6, 8, 6)
        sb_layout.setSpacing(8)

        if self.game:
            sync_text = f"🟢 <b>实时双向同步已绑定：</b> 目标游戏 <b>[{self.game.name}]</b> (修改后即刻更新游戏目录 INI 配置；游戏内按快捷键调参自动反向回显)"
        else:
            sync_text = "🟢 <b>全局默认预设：</b> 保存后将作为所有支持游戏的基础配置，修补时全自动注入游戏目录"

        lbl_sync = QLabel(sync_text)
        lbl_sync.setStyleSheet(f"font-size: 11px; color: {'#34d399' if is_dark else '#047857'};")
        lbl_sync.setWordWrap(True)
        sb_layout.addWidget(lbl_sync, 1)
        card_layout.addWidget(sync_banner)

        # 3. Tab Bar with Independent Mutually-Exclusive Button Group
        self.tab_bar_frame = QFrame()
        self.tab_bar_frame.setObjectName("TabBarFrame")
        self.tab_bar_frame.setStyleSheet("background: transparent; border: none;")
        tb_layout = QHBoxLayout(self.tab_bar_frame)
        tb_layout.setContentsMargins(0, 0, 0, 0)
        tb_layout.setSpacing(8)

        self.btn_group = QButtonGroup(self)
        self.tab_button_group = self.btn_group
        self.btn_group.setExclusive(True)

        text_a = "📦 模式 A: dashdogy 独立代理"
        text_b = "🎨 模式 B: RenoDX 插件优化"
        text_c = "🚀 模式 C: OptiScaler 跨卡转译"

        self.tab_btn_a = QPushButton(text_a)
        self.tab_btn_b = QPushButton(text_b)
        self.tab_btn_c = QPushButton(text_c)

        tooltips = [
            "模式 A: dashdogy 独立代理 (MFG-Unlocker 多倍插帧)",
            "模式 B: RenoDX 插件优化 (高品质光流/HDR)",
            "模式 C: OptiScaler 跨卡转译 (Intel XeSS 2.0 / FSR 3.1 / DLSS)"
        ]
        if 0 <= self.initial_tab_index < 3:
            tooltips[self.initial_tab_index] += " · 当前正在使用该模式"

        self.tab_buttons = [self.tab_btn_a, self.tab_btn_b, self.tab_btn_c]

        tab_font = QFont("Microsoft YaHei UI")
        tab_font.setPixelSize(13)
        tab_font.setWeight(QFont.Weight.DemiBold)

        for idx, btn in enumerate(self.tab_buttons):
            btn.setFont(tab_font)
            btn.setToolTip(tooltips[idx])
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(40)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.btn_group.addButton(btn, idx)
            btn.clicked.connect(lambda checked=False, i=idx: self.switch_preset_tab(i))
            tb_layout.addWidget(btn)

        self.btn_group.idClicked.connect(self.switch_preset_tab)
        card_layout.addWidget(self.tab_bar_frame)

        # 4. QStackedWidget for Mode A, Mode B, Mode C Pages
        self.stacked_widget = QStackedWidget()
        self.tab_widget = self.stacked_widget  # Alias for backward compatibility
        self.tab_widget.tabText = lambda i: self.tab_buttons[i].text()
        border_col = '#3A3A3A' if is_dark else '#D4D4D4'
        self.stacked_widget.setStyleSheet(f"""
            QStackedWidget {{
                background-color: {'#292929' if is_dark else '#ffffff'};
                border: 1px solid {border_col};
                border-radius: 10px;
            }}
        """)

        # Add Tab 0: Mode A
        tab_mode_a = self._build_mode_a_tab(is_dark, text_color, sub_text, card_bg, card_border, combo_bg, combo_border)
        self.stacked_widget.addWidget(tab_mode_a)

        # Add Tab 1: Mode B
        tab_mode_b = self._build_mode_b_tab(is_dark, text_color, sub_text, card_bg, card_border, combo_bg, combo_border)
        self.stacked_widget.addWidget(tab_mode_b)

        # Add Tab 2: Mode C
        tab_mode_c = self._build_mode_c_tab(is_dark, text_color, sub_text, card_bg, card_border, combo_bg, combo_border)
        self.stacked_widget.addWidget(tab_mode_c)

        card_layout.addWidget(self.stacked_widget, 1)

        # 4. Explanatory Guide Box
        guide_box = QFrame()
        guide_box.setStyleSheet(f"""
            QFrame {{
                background-color: {'#1e3a8a33' if is_dark else '#F5F5F5'};
                border-left: 4px solid #3E9E69;
                border-radius: 6px;
                padding: 8px 12px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        gb_layout = QVBoxLayout(guide_box)
        gb_layout.setContentsMargins(8, 6, 8, 6)
        gb_layout.setSpacing(2)
        lbl_tip_title = QLabel("💡 运行时热重载与生效说明：")
        lbl_tip_title.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {'#7ED9A2' if is_dark else '#26784C'};")
        gb_layout.addWidget(lbl_tip_title)

        lbl_tip_desc = QLabel(
            "• <b>游戏未运行时</b>：点击保存即可直接生效，下次启动游戏直接畅玩。<br>"
            "• <b>游戏运行中修改</b>：配置已实时写入游戏文件。部分底层 DLL 仅在启动时读取一次 ini，若游戏内未即时刷新，在游戏内按【Insert】/【Home】重新加载或重启游戏即可！"
        )
        lbl_tip_desc.setStyleSheet(f"font-size: 11px; color: {text_color}; line-height: 1.3;")
        lbl_tip_desc.setWordWrap(True)
        gb_layout.addWidget(lbl_tip_desc)
        card_layout.addWidget(guide_box)

        # 5. Footer Buttons
        footer = QHBoxLayout()
        footer.setSpacing(12)

        btn_reset = QPushButton("🔄 恢复默认推荐")
        btn_reset.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {sub_text};
                border: 1px solid {border_color};
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {'#3A3A3A' if is_dark else '#EFEFEF'};
                color: {text_color};
            }}
        """)
        btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reset.clicked.connect(self._reset_to_defaults)
        footer.addWidget(btn_reset)

        footer.addStretch()

        btn_cancel = QPushButton("取消")
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: {'#3A3A3A' if is_dark else '#E5E5E5'};
                color: {'#E5E5E5' if is_dark else '#3A3A3A'};
                border: none;
                border-radius: 8px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {'#4A4A4A' if is_dark else '#D4D4D4'};
            }}
        """)
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        footer.addWidget(btn_cancel)

        btn_save = QPushButton("💾 保存配置并同步至游戏")
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #2F8F5B;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 8px 24px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #26784C;
            }
        """)
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.clicked.connect(self._save_and_accept)
        footer.addWidget(btn_save)

        card_layout.addLayout(footer)
        main_layout.addWidget(card)

        # Hook events & populate values
        self.combo_fg_out.currentIndexChanged.connect(self._on_fg_out_changed)
        self._sync_values_to_ui()

        # Switch to initial target tab
        self.switch_preset_tab(self.initial_tab_index)

    def switch_preset_tab(self, index: int):
        """Switch active stacked widget page and update tab button active styles."""
        if not (0 <= index < self.stacked_widget.count()):
            return
        self.stacked_widget.setCurrentIndex(index)
        for i, btn in enumerate(self.tab_buttons):
            is_active = (i == index)
            btn.setChecked(is_active)
            self._update_tab_button_style(btn, is_active)
        cur = self.stacked_widget.currentWidget()
        if cur:
            cur.show()
            if cur.layout():
                cur.layout().activate()
            cur.updateGeometry()

    def _update_tab_button_style(self, btn: QPushButton, is_active: bool):
        is_dark = self.is_dark
        text_color = "#F5F5F5" if is_dark else "#292929"
        if is_active:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2F8F5B;
                    color: #ffffff;
                    border: 1px solid #26784C;
                    border-radius: 8px;
                    padding: 8px 10px;
                    font-size: 13px;
                    font-weight: 600;
                    min-height: 40px;
                }
                QPushButton:hover {
                    background-color: #26784C;
                }
            """)
        else:
            bg = "#2A2B2C" if is_dark else "#EFEFEF"
            border = "#3A3A3A" if is_dark else "#D4D4D4"
            col = "#94a3b8" if is_dark else "#64748b"
            hover_bg = "#3A3A3A" if is_dark else "#E5E5E5"
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg};
                    color: {col};
                    border: 1px solid {border};
                    border-radius: 8px;
                    padding: 8px 10px;
                    font-size: 13px;
                    font-weight: 600;
                    min-height: 40px;
                }}
                QPushButton:hover {{
                    background-color: {hover_bg};
                    color: {text_color};
                }}
            """)

    def _build_mode_a_tab(self, is_dark, text_color, sub_text, card_bg, card_border, combo_bg, combo_border) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # Section 1: Mode A Core Settings
        mfg_card = QFrame()
        mfg_card.setStyleSheet(f"""
            QFrame {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 10px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        mc_layout = QVBoxLayout(mfg_card)
        mc_layout.setContentsMargins(14, 12, 14, 12)
        mc_layout.setSpacing(10)

        lbl_sec1 = QLabel("📦 独立代理多帧生成 (dashdogy / MFG-Unlocker) 核心设定")
        lbl_sec1.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {'#7ED9A2' if is_dark else '#2F8F5B'};")
        mc_layout.addWidget(lbl_sec1)

        # Row 1: Multiplier
        h_mult = QHBoxLayout()
        h_mult.setContentsMargins(0, 0, 0, 0)
        lbl_mult = QLabel("强制插帧倍率设定:")
        lbl_mult.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {text_color};")
        lbl_mult.setFixedWidth(150)
        h_mult.addWidget(lbl_mult)

        self.combo_a_mult = QComboBox()
        self.combo_a_mult.setMinimumHeight(36)
        self.combo_a_mult.setMinimumWidth(280)
        self.combo_a_mult.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.combo_a_mult.addItem("2X 双倍帧率 (标准平滑 · 推荐 60Hz~144Hz)", 2)
        self.combo_a_mult.addItem("3X 三倍帧率 (高刷电竞推荐 · 推荐 165Hz~240Hz) [推荐]", 3)
        self.combo_a_mult.addItem("4X 四倍帧率 (超高刷极速 · 推荐 240Hz+)", 4)
        self.combo_a_mult.setStyleSheet(self._combo_qss(combo_bg, combo_border, text_color))
        self.combo_a_mult.view().setTextElideMode(Qt.TextElideMode.ElideNone)
        h_mult.addWidget(self.combo_a_mult, 1)
        mc_layout.addLayout(h_mult)

        # Row 2: DLSS Preset
        h_preset = QHBoxLayout()
        h_preset.setContentsMargins(0, 0, 0, 0)
        lbl_preset = QLabel("DLSS 超分预设档位:")
        lbl_preset.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {text_color};")
        lbl_preset.setFixedWidth(150)
        h_preset.addWidget(lbl_preset)

        self.combo_a_preset = QComboBox()
        self.combo_a_preset.setMinimumHeight(36)
        self.combo_a_preset.setMinimumWidth(280)
        self.combo_a_preset.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.combo_a_preset.addItem("Default (直通 · 不覆盖游戏或驱动模型)", "Default")
        self.combo_a_preset.addItem("Preset M (DLSS 4.5 第二代 Transformer · 极致画质与抗鬼影) [最新旗舰]", "M")
        self.combo_a_preset.addItem("Preset L (DLSS 4.5 第二代 Transformer · 专为高倍超分与 4K 优化)", "L")
        self.combo_a_preset.addItem("Preset K (DLSS 4 第一代 Transformer · 画面极度锐利稳定 · 推荐)", "K")
        self.combo_a_preset.addItem("Preset J (DLSS 4 第一代 Transformer · 植被与铁丝网细节强化)", "J")
        self.combo_a_preset.addItem("Preset E (DLSS 3.7 改进型 CNN · 动态与静态平衡最佳)", "E")
        self.combo_a_preset.addItem("Preset C (传统 CNN 模型 · 适合高速移动射击游戏)", "C")
        self.combo_a_preset.addItem("Preset F (传统 CNN 模型 · 适用于 DLAA 与超性能模式)", "F")
        self.combo_a_preset.setStyleSheet(self._combo_qss(combo_bg, combo_border, text_color))
        self.combo_a_preset.view().setTextElideMode(Qt.TextElideMode.ElideNone)
        h_preset.addWidget(self.combo_a_preset, 1)
        mc_layout.addLayout(h_preset)

        # Row 3: Hotkey
        h_key = QHBoxLayout()
        h_key.setContentsMargins(0, 0, 0, 0)
        lbl_key = QLabel("游戏内菜单呼出快捷键:")
        lbl_key.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {text_color};")
        lbl_key.setFixedWidth(150)
        h_key.addWidget(lbl_key)

        self.combo_a_key = QComboBox()
        self.combo_a_key.setMinimumHeight(36)
        self.combo_a_key.setMinimumWidth(280)
        self.combo_a_key.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.combo_a_key.addItem("Backspace (退格键 · 默认呼出 ImGui 菜单) [推荐]", "Backspace")
        self.combo_a_key.addItem("F11 (F11 功能快捷键)", "F11")
        self.combo_a_key.addItem("Insert (Insert 键)", "Insert")
        self.combo_a_key.addItem("Home (Home 键)", "Home")
        self.combo_a_key.addItem("End (End 键)", "End")
        self.combo_a_key.setStyleSheet(self._combo_qss(combo_bg, combo_border, text_color))
        self.combo_a_key.view().setTextElideMode(Qt.TextElideMode.ElideNone)
        h_key.addWidget(self.combo_a_key, 1)
        mc_layout.addLayout(h_key)

        layout.addWidget(mfg_card)

        # Section 2: Security & Hook Settings
        sec_card = QFrame()
        sec_card.setStyleSheet(f"""
            QFrame {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 10px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        sc_layout = QVBoxLayout(sec_card)
        sc_layout.setContentsMargins(14, 12, 14, 12)
        sc_layout.setSpacing(10)

        lbl_sec2 = QLabel("🛡️ 运行注入与防反作弊屏蔽")
        lbl_sec2.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {'#34d399' if is_dark else '#059669'};")
        sc_layout.addWidget(lbl_sec2)

        self.chk_a_bink = QCheckBox("⚙️ 启用 Bink2 链式劫持 (bink2w64Hooked.dll · 防反篡改与安全屏蔽)")
        self.chk_a_bink.setStyleSheet(f"color: {text_color}; font-size: 12px; font-weight: 600; border: none;")
        sc_layout.addWidget(self.chk_a_bink)

        lbl_hint = QLabel("💡 模式 A 通过本地代理 DLL (version/winmm) 自动劫持 Streamline，进游戏后按上述快捷键即可直接在屏幕上呼出 dashdogy 实时调参面板。")
        lbl_hint.setStyleSheet(f"font-size: 11px; color: {sub_text};")
        lbl_hint.setWordWrap(True)
        sc_layout.addWidget(lbl_hint)

        layout.addWidget(sec_card)
        layout.addStretch()
        return tab

    def _build_mode_c_tab(self, is_dark, text_color, sub_text, card_bg, card_border, combo_bg, combo_border) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # Section: Frame Generation & Multipliers
        fg_card = QFrame()
        fg_card.setStyleSheet(f"""
            QFrame {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 10px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        fg_layout = QVBoxLayout(fg_card)
        fg_layout.setContentsMargins(14, 12, 14, 12)
        fg_layout.setSpacing(10)

        lbl_fg_sec = QLabel("⚡ 多帧生成 (Frame Generation) 核心设定")
        lbl_fg_sec.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {'#8FE3B0' if is_dark else '#0284c7'};")
        fg_layout.addWidget(lbl_fg_sec)

        # Row: FG Output
        h_fg_out = QHBoxLayout()
        lbl_fg_out = QLabel("插帧输出引擎:")
        lbl_fg_out.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {text_color};")
        lbl_fg_out.setFixedWidth(145)
        h_fg_out.addWidget(lbl_fg_out)

        self.combo_fg_out = QComboBox()
        self.combo_fg_out.setMinimumHeight(36)
        self.combo_fg_out.setMinimumWidth(280)
        self.combo_fg_out.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.combo_fg_out.addItem("Intel XeFG (XeSS 2.0 官方插帧 · 支持 2X/3X/4X) [推荐]", "xefg")
        self.combo_fg_out.addItem("AMD FSR 3.1 FG (全架构通用插帧 · 固定 2X 双倍)", "fsrfg")
        self.combo_fg_out.addItem("Nukem9 DLSSG-to-FSR3 (经典转译通道 · 固定 2X 双倍)", "nukems")
        self.combo_fg_out.setStyleSheet(self._combo_qss(combo_bg, combo_border, text_color))
        self.combo_fg_out.view().setTextElideMode(Qt.TextElideMode.ElideNone)
        h_fg_out.addWidget(self.combo_fg_out, 1)
        fg_layout.addLayout(h_fg_out)

        # Row: Multiplier
        h_mult = QHBoxLayout()
        lbl_mult = QLabel("插帧倍率设定:")
        lbl_mult.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {text_color};")
        lbl_mult.setFixedWidth(145)
        h_mult.addWidget(lbl_mult)

        self.combo_mult = QComboBox()
        self.combo_mult.setMinimumHeight(36)
        self.combo_mult.setMinimumWidth(280)
        self.combo_mult.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.combo_mult.addItem("2X 双倍帧率 (标准平滑 · 推荐 60Hz~144Hz 显示器)", 1)
        self.combo_mult.addItem("3X 三倍帧率 (XeFG 高刷电竞 · 推荐 165Hz~240Hz) [默认推荐]", 2)
        self.combo_mult.addItem("4X 四倍帧率 (XeFG 极速流体 · 推荐 240Hz+ 超高刷)", 3)
        self.combo_mult.setStyleSheet(self._combo_qss(combo_bg, combo_border, text_color))
        self.combo_mult.view().setTextElideMode(Qt.TextElideMode.ElideNone)
        h_mult.addWidget(self.combo_mult, 1)
        fg_layout.addLayout(h_mult)

        # Dynamic Multiplier Hint
        self.lbl_mult_hint = QLabel("✨ 当前选用 Intel XeSS 2.0 官方插帧，已完整解锁 2X / 3X / 4X 多倍帧生成！")
        self.lbl_mult_hint.setStyleSheet(f"font-size: 11px; color: {'#34d399' if is_dark else '#059669'};")
        self.lbl_mult_hint.setWordWrap(True)
        fg_layout.addWidget(self.lbl_mult_hint)

        # Row: FG Input
        h_fg_in = QHBoxLayout()
        lbl_fg_in = QLabel("插帧输入通道:")
        lbl_fg_in.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {text_color};")
        lbl_fg_in.setFixedWidth(145)
        h_fg_in.addWidget(lbl_fg_in)

        self.combo_fg_in = QComboBox()
        self.combo_fg_in.setMinimumHeight(36)
        self.combo_fg_in.setMinimumWidth(280)
        self.combo_fg_in.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.combo_fg_in.addItem("DLSSG via Streamline (官方原生及全显卡通用通道 · 推荐)", "dlssg")
        self.combo_fg_in.addItem("Nukem's DLSSG (20/30 系列显卡桥接通道)", "nukems")
        self.combo_fg_in.addItem("Auto (根据游戏渲染流自动匹配)", "auto")
        self.combo_fg_in.setStyleSheet(self._combo_qss(combo_bg, combo_border, text_color))
        self.combo_fg_in.view().setTextElideMode(Qt.TextElideMode.ElideNone)
        h_fg_in.addWidget(self.combo_fg_in, 1)
        fg_layout.addLayout(h_fg_in)

        # Row: Hotkey
        h_c_key = QHBoxLayout()
        lbl_c_key = QLabel("游戏内菜单呼出快捷键:")
        lbl_c_key.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {text_color};")
        lbl_c_key.setFixedWidth(145)
        h_c_key.addWidget(lbl_c_key)

        self.combo_c_key = QComboBox()
        self.combo_c_key.setMinimumHeight(36)
        self.combo_c_key.setMinimumWidth(280)
        self.combo_c_key.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.combo_c_key.addItem("Insert (Insert 键 · 官方默认呼出 ImGui 菜单) [推荐]", "Insert")
        self.combo_c_key.addItem("Backspace (退格键 · 适合 60%/75% 紧凑配列键盘)", "Backspace")
        self.combo_c_key.addItem("Home (Home 键 · 经典备用呼出键)", "Home")
        self.combo_c_key.addItem("F11 (F11 功能快捷键)", "F11")
        self.combo_c_key.addItem("End (End 键)", "End")
        self.combo_c_key.setStyleSheet(self._combo_qss(combo_bg, combo_border, text_color))
        self.combo_c_key.view().setTextElideMode(Qt.TextElideMode.ElideNone)
        h_c_key.addWidget(self.combo_c_key, 1)
        fg_layout.addLayout(h_c_key)

        # Row: In-game ImGui menu scale (OptiScaler.ini [Menu] Scale, 0.5 - 2.0)
        h_c_scale = QHBoxLayout()
        lbl_c_scale = QLabel("游戏内菜单界面大小:")
        lbl_c_scale.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {text_color};")
        lbl_c_scale.setFixedWidth(145)
        lbl_c_scale.setToolTip("OptiScaler.ini → [Menu] Scale，合法范围 0.5 - 2.0")
        h_c_scale.addWidget(lbl_c_scale)

        self.combo_menu_scale = QComboBox()
        self.combo_menu_scale.setMinimumHeight(36)
        self.combo_menu_scale.setMinimumWidth(280)
        self.combo_menu_scale.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.combo_menu_scale.addItem("1.0x (1080P 标准 · 原始大小)", 1.0)
        self.combo_menu_scale.addItem("1.5x (2K / 1440P 放大推荐)", 1.5)
        self.combo_menu_scale.addItem("2.0x (4K 超清大字 · 3840×2160 推荐) [默认]", 2.0)
        self.combo_menu_scale.setToolTip(
            "对应 OptiScaler.ini 的 [Menu] Scale。4K 屏幕默认 1.0 会让菜单极小、文字难辨，\n"
            "这里默认 2.0；保存后即写入游戏目录，下次呼出菜单立即变大。"
        )
        self.combo_menu_scale.setStyleSheet(self._combo_qss(combo_bg, combo_border, text_color))
        self.combo_menu_scale.view().setTextElideMode(Qt.TextElideMode.ElideNone)
        h_c_scale.addWidget(self.combo_menu_scale, 1)
        fg_layout.addLayout(h_c_scale)

        self.lbl_menu_scale_hint = QLabel(
            "💡 4K (3840×2160) 下 OptiScaler 默认 Menu Scale 仅 1.0，菜单与字体过小；"
            "此处选择 2.0 即可获得清晰大字菜单（2K 屏幕推荐 1.5）。"
        )
        self.lbl_menu_scale_hint.setStyleSheet(f"font-size: 11px; color: {sub_text};")
        self.lbl_menu_scale_hint.setWordWrap(True)
        fg_layout.addWidget(self.lbl_menu_scale_hint)

        layout.addWidget(fg_card)

        # Section: Upscaler & Sharpness
        up_card = QFrame()
        up_card.setStyleSheet(f"""
            QFrame {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 10px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        up_layout = QVBoxLayout(up_card)
        up_layout.setContentsMargins(14, 12, 14, 12)
        up_layout.setSpacing(10)

        lbl_up_sec = QLabel("🎨 超分辨率与画质增强设定")
        lbl_up_sec.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {'#a78bfa' if is_dark else '#7c3aed'};")
        up_layout.addWidget(lbl_up_sec)

        # Row: Upscaler
        h_up = QHBoxLayout()
        lbl_up = QLabel("DirectX 12 超分:")
        lbl_up.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {text_color};")
        lbl_up.setFixedWidth(145)
        h_up.addWidget(lbl_up)

        self.combo_upscaler = QComboBox()
        self.combo_upscaler.setMinimumHeight(36)
        self.combo_upscaler.setMinimumWidth(280)
        self.combo_upscaler.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.combo_upscaler.addItem("Auto (自动继承游戏内设定) [推荐 / 默认]", "auto")
        self.combo_upscaler.addItem("Intel XeSS 2.0 (AI 神经网络深度超分 · 细腻抗鬼影)", "xess")
        self.combo_upscaler.addItem("NVIDIA DLSS (RTX 原生 Tensor Core 超分辨率)", "dlss")
        self.combo_upscaler.addItem("AMD FSR 3.1 (全平台通用超分辨率)", "fsr31")
        self.combo_upscaler.setStyleSheet(self._combo_qss(combo_bg, combo_border, text_color))
        self.combo_upscaler.view().setTextElideMode(Qt.TextElideMode.ElideNone)
        h_up.addWidget(self.combo_upscaler, 1)
        up_layout.addLayout(h_up)

        # Row: DLSS Preset
        h_c_preset = QHBoxLayout()
        lbl_c_preset = QLabel("DLSS 超分预设档位:")
        lbl_c_preset.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {text_color};")
        lbl_c_preset.setFixedWidth(145)
        h_c_preset.addWidget(lbl_c_preset)

        self.combo_c_preset = QComboBox()
        self.combo_c_preset.setMinimumHeight(36)
        self.combo_c_preset.setMinimumWidth(280)
        self.combo_c_preset.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.combo_c_preset.addItem("Default (直通 · 不覆盖游戏或驱动模型)", "Default")
        self.combo_c_preset.addItem("Preset M (DLSS 4.5 第二代 Transformer · 极致画质与抗鬼影) [最新旗舰]", "M")
        self.combo_c_preset.addItem("Preset L (DLSS 4.5 第二代 Transformer · 专为高倍超分与 4K 优化)", "L")
        self.combo_c_preset.addItem("Preset K (DLSS 4 第一代 Transformer · 画面极度锐利稳定) [默认推荐]", "K")
        self.combo_c_preset.addItem("Preset J (DLSS 4 第一代 Transformer · 植被与铁丝网细节强化)", "J")
        self.combo_c_preset.addItem("Preset E (DLSS 3.7 改进型 CNN · 动态与静态平衡最佳)", "E")
        self.combo_c_preset.addItem("Preset C (传统 CNN 模型 · 适合高速移动射击游戏)", "C")
        self.combo_c_preset.addItem("Preset F (传统 CNN 模型 · 适用于 DLAA 与超性能模式)", "F")
        self.combo_c_preset.setStyleSheet(self._combo_qss(combo_bg, combo_border, text_color))
        self.combo_c_preset.view().setTextElideMode(Qt.TextElideMode.ElideNone)
        h_c_preset.addWidget(self.combo_c_preset, 1)
        up_layout.addLayout(h_c_preset)

        # Sharpness Row
        h_sharp = QHBoxLayout()
        self.chk_rcas = QCheckBox("启用 AMD RCAS 对比度自适应锐化 (防止抗锯齿模糊)")
        self.chk_rcas.setStyleSheet(f"color: {text_color}; font-size: 12px; font-weight: 600; border: none;")
        h_sharp.addWidget(self.chk_rcas)
        h_sharp.addStretch()

        self.lbl_sharp_val = QLabel("0.00")
        self.lbl_sharp_val.setStyleSheet(f"color: {'#8FE3B0' if is_dark else '#0284c7'}; font-weight: bold; font-size: 13px;")
        h_sharp.addWidget(self.lbl_sharp_val)
        up_layout.addLayout(h_sharp)

        # Slider Row
        h_slider = QHBoxLayout()
        lbl_sl_min = QLabel("平滑 0.0")
        lbl_sl_min.setStyleSheet(f"font-size: 11px; color: {sub_text};")
        h_slider.addWidget(lbl_sl_min)

        self.slider_sharp = QSlider(Qt.Orientation.Horizontal)
        self.slider_sharp.setRange(0, 100)
        self.slider_sharp.setSingleStep(5)
        self.slider_sharp.valueChanged.connect(self._on_slider_changed)
        self.slider_sharp.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                border: none;
                height: 6px;
                background: {'#3A3A3A' if is_dark else '#E5E5E5'};
                border-radius: 3px;
            }}
            QSlider::sub-page:horizontal {{
                background: #2F8F5B;
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: #ffffff;
                border: 2px solid #2F8F5B;
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }}
        """)
        h_slider.addWidget(self.slider_sharp, 1)

        lbl_sl_max = QLabel("锐利 1.0")
        lbl_sl_max.setStyleSheet(f"font-size: 11px; color: {sub_text};")
        h_slider.addWidget(lbl_sl_max)
        up_layout.addLayout(h_slider)

        layout.addWidget(up_card)
        layout.addStretch()
        return tab

    def _build_mode_b_tab(self, is_dark, text_color, sub_text, card_bg, card_border, combo_bg, combo_border) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # Section 1: Multiplier
        mult_card = QFrame()
        mult_card.setStyleSheet(f"""
            QFrame {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 10px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        mc_layout = QVBoxLayout(mult_card)
        mc_layout.setContentsMargins(14, 12, 14, 12)
        mc_layout.setSpacing(10)

        lbl_mfg_sec = QLabel("🎨 强制插帧倍率 (Force Multiplier · 2X~6X)")
        lbl_mfg_sec.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {'#34d399' if is_dark else '#059669'};")
        mc_layout.addWidget(lbl_mfg_sec)

        h_b_mult = QHBoxLayout()
        lbl_b_mult = QLabel("插帧倍率设定:")
        lbl_b_mult.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {text_color};")
        lbl_b_mult.setFixedWidth(140)
        h_b_mult.addWidget(lbl_b_mult)

        self.combo_b_mult = QComboBox()
        self.combo_b_mult.setMinimumHeight(36)
        self.combo_b_mult.setMinimumWidth(280)
        self.combo_b_mult.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.combo_b_mult.addItem("0: 游戏原生控制 (保持游戏内画质菜单设定)", 0)
        self.combo_b_mult.addItem("2: 2X 双倍帧率 (标准平滑 · 推荐 60Hz~144Hz)", 2)
        self.combo_b_mult.addItem("3: 3X 三倍帧率 (高刷电竞推荐 · 推荐 165Hz~240Hz) [推荐]", 3)
        self.combo_b_mult.addItem("4: 4X 四倍帧率 (超高刷极速 · 推荐 240Hz+)", 4)
        self.combo_b_mult.addItem("5: 5X 五倍帧率 (高倍插帧探索)", 5)
        self.combo_b_mult.addItem("6: 6X 六倍帧率 (极限多帧生成)", 6)
        self.combo_b_mult.setStyleSheet(self._combo_qss(combo_bg, combo_border, text_color))
        self.combo_b_mult.view().setTextElideMode(Qt.TextElideMode.ElideNone)
        h_b_mult.addWidget(self.combo_b_mult, 1)
        mc_layout.addLayout(h_b_mult)

        lbl_b_note = QLabel("✨ 采用 RenoDX 深度光流调度，直接解除 DLSS 3 原生 2X 倍率限制，最高可达 6 倍丝滑插帧！")
        lbl_b_note.setStyleSheet(f"font-size: 11px; color: {'#34d399' if is_dark else '#059669'};")
        lbl_b_note.setWordWrap(True)
        mc_layout.addWidget(lbl_b_note)
        layout.addWidget(mult_card)

        # Section 2: Blackwell Kernels & Artifact Mitigation
        opt_card = QFrame()
        opt_card.setStyleSheet(f"""
            QFrame {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 10px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        oc_layout = QVBoxLayout(opt_card)
        oc_layout.setContentsMargins(14, 12, 14, 12)
        oc_layout.setSpacing(8)

        lbl_opt_sec = QLabel("🛡️ Blackwell 架构优化内核与薄几何体抗伪影")
        lbl_opt_sec.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {'#8FE3B0' if is_dark else '#0284c7'};")
        oc_layout.addWidget(lbl_opt_sec)

        self.chk_b_blackwell = QCheckBox("🌟 启用 Blackwell 架构优化内核 (BlackwellFrameworkKernels · 全光流运动矢量平滑)")
        self.chk_b_blackwell.setStyleSheet(f"color: {text_color}; font-size: 12px; font-weight: 600; border: none;")
        oc_layout.addWidget(self.chk_b_blackwell)

        self.chk_b_isr = QCheckBox("🌿 细微几何体中间散射保留 (ISR · 消除草木、电线、细小物体插帧断裂)")
        self.chk_b_isr.setStyleSheet(f"color: {text_color}; font-size: 12px; border: none;")
        oc_layout.addWidget(self.chk_b_isr)

        self.chk_b_vwb = QCheckBox("🌊 前帧散射融合优化 (VWB · 增强多方向复杂运动前后帧平滑过渡)")
        self.chk_b_vwb.setStyleSheet(f"color: {text_color}; font-size: 12px; border: none;")
        oc_layout.addWidget(self.chk_b_vwb)

        self.chk_b_bam = QCheckBox("✨ 边界验证几何扭曲融合 (BAM · 彻底消除动态角色模型边缘撕裂与鬼影)")
        self.chk_b_bam.setStyleSheet(f"color: {text_color}; font-size: 12px; border: none;")
        oc_layout.addWidget(self.chk_b_bam)

        self.chk_b_hdr = QCheckBox("🌈 HDR UI 防撕裂重构 (HDRUIRecomposition · 修复 HDR 模式下准星与 HUD 闪烁)")
        self.chk_b_hdr.setStyleSheet(f"color: {text_color}; font-size: 12px; border: none;")
        oc_layout.addWidget(self.chk_b_hdr)

        self.chk_b_dynamic = QCheckBox("⚡ NVIDIA Dynamic MFG 动态插帧 (DynamicMFG · 驱动层智能自适应负载)")
        self.chk_b_dynamic.setStyleSheet(f"color: {text_color}; font-size: 12px; border: none;")
        oc_layout.addWidget(self.chk_b_dynamic)

        self.chk_b_temporal = QCheckBox("⏱️ 时间中点平滑修复 (TemporalFix · 解决部分虚幻引擎游戏插帧偶发卡顿)")
        self.chk_b_temporal.setStyleSheet(f"color: {text_color}; font-size: 12px; border: none;")
        oc_layout.addWidget(self.chk_b_temporal)

        layout.addWidget(opt_card)
        layout.addStretch()
        return tab

    def _combo_qss(self, bg: str, border: str, text: str) -> str:
        arrow_color = '#94a3b8' if self.is_dark else '#64748b'
        try:
            from common.ui_theme import get_combo_arrow_url
            arrow_url = get_combo_arrow_url(self.is_dark)
        except Exception:
            arrow_url = ""
        disabled_bg = '#3A3A3A' if self.is_dark else '#EFEFEF'
        disabled_text = '#64748b' if self.is_dark else '#94a3b8'
        disabled_border = '#4A4A4A' if self.is_dark else '#E5E5E5'
        item_hover_bg = '#3A3A3A' if self.is_dark else '#E5E5E5'
        item_hover_text = '#F5F5F5' if self.is_dark else '#292929'
        return f"""
            QComboBox {{
                background-color: {bg};
                color: {text};
                border: 1px solid {border};
                border-radius: 8px;
                padding: 4px 10px;
                min-height: 36px;
                min-width: 280px;
                font-size: 12px;
            }}
            QComboBox:disabled {{
                background-color: {disabled_bg};
                color: {disabled_text};
                border-color: {disabled_border};
            }}
            /* Integrated chevron image (CSS-border triangles are unsupported by Qt). */
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 30px;
                border: none;
                background: transparent;
            }}
            QComboBox::down-arrow {{
                image: url("{arrow_url}");
                width: 12px;
                height: 8px;
                margin-right: 9px;
            }}
            QComboBox QAbstractItemView,
            QComboBox QListView {{
                background-color: {bg};
                color: {text};
                selection-background-color: #2F8F5B;
                selection-color: #ffffff;
                border: 1px solid {border};
                border-radius: 6px;
                padding: 4px;
                outline: none;
            }}
            QComboBox QAbstractItemView::item,
            QComboBox QListView::item {{
                min-height: 30px;
                padding: 4px 10px;
                color: {text};
            }}
            QComboBox QAbstractItemView::item:hover,
            QComboBox QListView::item:hover {{
                background-color: {item_hover_bg};
                color: {item_hover_text};
            }}
            QComboBox QAbstractItemView::item:selected,
            QComboBox QListView::item:selected {{
                background-color: #2F8F5B;
                color: #ffffff;
            }}
        """

    def _sync_values_to_ui(self):
        # 0. Mode A
        a_mult = int(self.preset_a.get("multiplier", 3))
        idx_am = self.combo_a_mult.findData(a_mult)
        if idx_am >= 0:
            self.combo_a_mult.setCurrentIndex(idx_am)

        a_preset = str(self.preset_a.get("dlss_preset", "K"))
        if str(a_preset).strip() in ("0", "", "none", "None"):
            a_preset = "K"
        idx_ap = self.combo_a_preset.findData(a_preset)
        if idx_ap >= 0:
            self.combo_a_preset.setCurrentIndex(idx_ap)
        else:
            idx_k = self.combo_a_preset.findData("K")
            self.combo_a_preset.setCurrentIndex(idx_k if idx_k >= 0 else 0)

        a_key = str(self.preset_a.get("menu_key", "Backspace"))
        idx_ak = self.combo_a_key.findData(a_key)
        if idx_ak >= 0:
            self.combo_a_key.setCurrentIndex(idx_ak)

        self.chk_a_bink.setChecked(bool(self.preset_a.get("bink_hook", True)))

        # 1. Mode B
        b_mult = int(self.preset_b.get("force_multiplier", 3))
        idx_bm = self.combo_b_mult.findData(b_mult)
        if idx_bm >= 0:
            self.combo_b_mult.setCurrentIndex(idx_bm)

        self.chk_b_blackwell.setChecked(bool(self.preset_b.get("blackwell_kernels", 1)))
        self.chk_b_isr.setChecked(bool(self.preset_b.get("thin_geometry_isr", 1)))
        self.chk_b_vwb.setChecked(bool(self.preset_b.get("thin_geometry_vwb", 1)))
        self.chk_b_bam.setChecked(bool(self.preset_b.get("thin_geometry_bam", 1)))
        self.chk_b_hdr.setChecked(bool(self.preset_b.get("hdr_ui_recomposition", 1)))
        self.chk_b_dynamic.setChecked(bool(self.preset_b.get("dynamic_mfg", 0)))
        self.chk_b_temporal.setChecked(bool(self.preset_b.get("temporal_fix", 1)))

        # 2. Mode C
        fg_out = self.preset_c.get("fg_output", "xefg")
        idx = self.combo_fg_out.findData(fg_out)
        if idx >= 0:
            self.combo_fg_out.setCurrentIndex(idx)

        mult = int(self.preset_c.get("interpolation_count", 2))
        idx_m = self.combo_mult.findData(mult)
        if idx_m >= 0:
            self.combo_mult.setCurrentIndex(idx_m)

        fg_in = self.preset_c.get("fg_input", "dlssg")
        idx_in = self.combo_fg_in.findData(fg_in)
        if idx_in >= 0:
            self.combo_fg_in.setCurrentIndex(idx_in)

        up = self.preset_c.get("dx12_upscaler", "auto")
        idx_up = self.combo_upscaler.findData(up)
        if idx_up >= 0:
            self.combo_upscaler.setCurrentIndex(idx_up)
        else:
            self.combo_upscaler.setCurrentIndex(0)

        c_preset = str(self.preset_c.get("dlss_preset", "K"))
        if str(c_preset).strip() in ("0", "", "none", "None"):
            c_preset = "K"
        idx_cp = self.combo_c_preset.findData(c_preset)
        if idx_cp >= 0:
            self.combo_c_preset.setCurrentIndex(idx_cp)
        else:
            idx_k = self.combo_c_preset.findData("K")
            self.combo_c_preset.setCurrentIndex(idx_k if idx_k >= 0 else 0)

        c_key = str(self.preset_c.get("menu_key", "Insert"))
        idx_ck = self.combo_c_key.findData(c_key)
        if idx_ck >= 0:
            self.combo_c_key.setCurrentIndex(idx_ck)
        else:
            self.combo_c_key.setCurrentIndex(0)

        # In-game menu scale (1.0 / 1.5 / 2.0); unknown stored values are clamped
        try:
            scale_val = float(self.preset_c.get("menu_scale", 2.0))
        except (TypeError, ValueError):
            scale_val = 2.0
        scale_val = max(1.0, min(2.0, scale_val))
        idx_scale = self.combo_menu_scale.findData(scale_val)
        if idx_scale >= 0:
            self.combo_menu_scale.setCurrentIndex(idx_scale)
        else:
            self.combo_menu_scale.setCurrentIndex(self.combo_menu_scale.count() - 1)

        self.chk_rcas.setChecked(bool(self.preset_c.get("rcas_enabled", False)))
        val = int(round(float(self.preset_c.get("rcas_sharpness", 0.0)) * 100))
        self.slider_sharp.setValue(val)
        self.lbl_sharp_val.setText(f"{val/100.0:.2f}")

        self._on_fg_out_changed()

    def _on_fg_out_changed(self):
        cur_out = self.combo_fg_out.currentData()
        xefg_max = None
        if self.game and getattr(self.game, "target_dir", None):
            try:
                xefg_max = IniConfigManager.detect_xefg_max_interpolations(self.game.target_dir)
            except Exception:
                xefg_max = None

        if cur_out == "xefg":
            self.combo_mult.setEnabled(True)
            if xefg_max is not None and xefg_max <= 1:
                self.lbl_mult_hint.setText(
                    "⚠️ 实机日志检测到本机 XeFG 上限为 2X（libxess_fg: Max supported interpolations = 1）："
                    "请选 2X，否则 OptiScaler 会一直提示 Restart the game to apply correct XeFG settings!。"
                    "需要 3X/4X 原生多帧请改用模式 A (dashdogy) 或模式 B (RenoDX MFGUnlock)。"
                )
                self.lbl_mult_hint.setStyleSheet(
                    f"font-size: 11px; color: {'#f59e0b' if self.is_dark else '#b45309'};"
                )
            elif xefg_max is not None and xefg_max >= 2:
                self.lbl_mult_hint.setText(
                    f"✨ 实机日志检测到本机 XeFG 最高支持 {xefg_max + 1}X 插帧，"
                    f"已可选择到 {xefg_max + 1}X（保存时会自动写入合法的 InterpolationCount）。"
                )
                self.lbl_mult_hint.setStyleSheet(
                    f"font-size: 11px; color: {'#34d399' if self.is_dark else '#059669'};"
                )
            else:
                self.lbl_mult_hint.setText(
                    "✨ XeFG 支持 2X / 3X / 4X，实际上限由 libxess_fg 决定；"
                    "保存时会按实机能力自动写入合法的 InterpolationCount，避免二次重启提示。"
                )
                self.lbl_mult_hint.setStyleSheet(
                    f"font-size: 11px; color: {'#34d399' if self.is_dark else '#059669'};"
                )
        else:
            self.combo_mult.setCurrentIndex(0)  # 2X
            self.combo_mult.setEnabled(False)
            self.lbl_mult_hint.setText("⚠️ FSR 3.1 / Nukem9 通道固定为 2X 双倍插帧，不支持 3X/4X 多倍率 (已自动锁定为 2X)。")
            self.lbl_mult_hint.setStyleSheet(f"font-size: 11px; color: {'#f59e0b' if self.is_dark else '#d97706'};")

    def _on_slider_changed(self, val: int):
        self.lbl_sharp_val.setText(f"{val/100.0:.2f}")

    def _reset_to_defaults(self):
        self.preset_a = dict(DEFAULT_MODE_A_PRESET)
        self.preset_b = dict(DEFAULT_RESHADE_PRESET)
        self.preset_c = dict(DEFAULT_OPTISCALER_PRESET)
        self._sync_values_to_ui()

    def _save_and_accept(self):
        # 0. Update Mode A dictionary & save to persistent storage
        self.preset_a["multiplier"] = self.combo_a_mult.currentData()
        self.preset_a["dlss_preset"] = self.combo_a_preset.currentData()
        self.preset_a["menu_key"] = self.combo_a_key.currentData()
        self.preset_a["bink_hook"] = self.chk_a_bink.isChecked()
        save_mode_a_preset(self.preset_a)

        # 1. Update Mode B dictionary & save to persistent storage
        self.preset_b["force_multiplier"] = self.combo_b_mult.currentData()
        self.preset_b["blackwell_kernels"] = 1 if self.chk_b_blackwell.isChecked() else 0
        self.preset_b["thin_geometry_isr"] = 1 if self.chk_b_isr.isChecked() else 0
        self.preset_b["thin_geometry_vwb"] = 1 if self.chk_b_vwb.isChecked() else 0
        self.preset_b["thin_geometry_bam"] = 1 if self.chk_b_bam.isChecked() else 0
        self.preset_b["hdr_ui_recomposition"] = 1 if self.chk_b_hdr.isChecked() else 0
        self.preset_b["dynamic_mfg"] = 1 if self.chk_b_dynamic.isChecked() else 0
        self.preset_b["temporal_fix"] = 1 if self.chk_b_temporal.isChecked() else 0
        save_reshade_preset(self.preset_b)

        # 2. Update Mode C dictionary & save to persistent storage
        self.preset_c["fg_output"] = self.combo_fg_out.currentData()
        self.preset_c["interpolation_count"] = self.combo_mult.currentData()
        self.preset_c["fg_input"] = self.combo_fg_in.currentData()
        self.preset_c["dx12_upscaler"] = self.combo_upscaler.currentData()
        self.preset_c["user_customized_upscaler"] = (self.combo_upscaler.currentData() != "auto")
        self.preset_c["dlss_preset"] = self.combo_c_preset.currentData()
        self.preset_c["menu_key"] = self.combo_c_key.currentData()
        self.preset_c["menu_scale"] = float(self.combo_menu_scale.currentData())
        self.preset_c["rcas_enabled"] = self.chk_rcas.isChecked()
        self.preset_c["rcas_sharpness"] = round(self.slider_sharp.value() / 100.0, 2)
        save_optiscaler_preset(self.preset_c)

        # 3. Forward synchronization to target game directory
        if self.game and self.game.target_dir:
            IniConfigManager.sync_mode_a_forward(self.game.target_dir, self.preset_a)
            IniConfigManager.sync_mode_b_forward(self.game.target_dir, self.preset_b)
            IniConfigManager.sync_mode_c_forward(self.game.target_dir, self.preset_c, exe_name=self.game.exe_name)

        self.accept()


# ----------------- QSS THEMES -----------------
LIGHT_THEME = """
    QMainWindow {
        background: transparent;
    }
    QWidget#CentralWidget {
        background-color: #F5F5F5;
        border: none;
    border-radius: 8px;
    }
    QWidget#Sidebar {
        background-color: #FFFFFF;
        border-top-left-radius: 0px;
        border-bottom-left-radius: 16px;
        border-right: 1px solid #E5E5E5;
    }
    QWidget#TitleBar {
        background-color: #FFFFFF;
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
        border-bottom: 1px solid #E5E5E5;
    }
    QLabel {
        color: #2A2B2C;
    }
    
    /* 图2右上角标题栏按钮 */
    QPushButton.title-btn {
        background-color: transparent;
        color: #64748B;
        border: none;
        border-radius: 6px;
        font-size: 14px;
        font-weight: 600;
        min-width: 34px;
        max-width: 34px;
        min-height: 28px;
        max-height: 28px;
    }
    QPushButton#TitleBtnMax, QPushButton.TitleBtnMax {
        font-size: 17px;
        font-weight: 700;
    }
    QPushButton.title-btn:hover {
        background-color: #E5E5E5;
        color: #292929;
    }
    QPushButton.title-close-btn:hover {
        background-color: #EF4444;
        color: #FFFFFF;
    }
    QPushButton.theme-toggle-btn, QPushButton#ThemeToggleBtn { 
    background-color: transparent;
    color: #3A3A3A;
    border: none;
    border-radius: 10px;
    padding: 4px 6px;
    min-height: 24px;
}
    QPushButton.theme-toggle-btn:hover, QPushButton#ThemeToggleBtn:hover { background-color: #EFEFEF; border: none; }

    /* 图1优化：现代化极简 6px 细致圆角滑动条 (全软件统一) */
    QScrollBar:vertical {
        border: none;
        background: transparent;
        width: 6px;
        margin: 0px;
        border-radius: 3px;
    }
    QScrollBar::handle:vertical {
        background: #D4D4D4;
        min-height: 24px;
        border-radius: 3px;
    }
    QScrollBar::handle:vertical:hover {
        background: #94A3B8;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
        width: 0px;
        background: transparent;
        border: none;
    }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: transparent;
    }
    QScrollBar:horizontal {
        border: none;
        background: transparent;
        height: 0px;
        width: 0px;
        margin: 0px;
    }
    QScrollBar::handle:horizontal {
        background: transparent;
        min-width: 0px;
        height: 0px;
    }
    QScrollBar::handle:horizontal:hover {
        background: transparent;
    }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        width: 0px;
        height: 0px;
        background: transparent;
        border: none;
    }
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
        background: transparent;
    }

    /* Sidebar Navigation */
    QPushButton.nav-btn {
        background-color: transparent;
        color: #64748B;
        border: none;
        border-radius: 12px;
        padding: 10px 16px;
        text-align: left;
        font-size: 13px;
        font-weight: 600;
    }
    QPushButton.nav-btn:hover {
        background-color: #EFEFEF;
        color: #2A2B2C;
    }
    QPushButton.nav-btn-active {
        background-color: #E8E8E8;
        color: #1A1A1A;
        font-weight: bold;
        border-radius: 12px;
        padding: 10px 16px;
        text-align: left;
        font-size: 13px;
    }

    /* Cards */
    QFrame.card {
        background-color: #FFFFFF;
        border: 1px solid #E5E5E5;
        border-radius: 16px;
    }
    QFrame.card:hover {
        border-color: #A7F3D0;
    }

    /* Dropdowns */
    QComboBox {
        background-color: #ffffff;
        border: 1px solid #D4D4D4;
        border-radius: 8px;
        padding: 7px 12px;
        font-size: 13px;
        color: #292929;
    }
    QComboBox:hover {
        border: 1px solid #94a3b8;
    }
    /* Native chevron (see the combo helper above). */
    QComboBox QAbstractItemView,
    QComboBox QListView,
    QComboBoxPrivateContainer,
    QListView#combo_popup {
        background-color: #ffffff;
        color: #292929;
        selection-background-color: #F5F5F5;
        selection-color: #2F8F5B;
        border: 1px solid #D4D4D4;
        border-radius: 8px;
        padding: 4px;
        outline: none;
    }
    QComboBox QAbstractItemView::item,
    QComboBox QListView::item {
        min-height: 30px;
        padding: 4px 10px;
        color: #292929;
        background-color: #ffffff;
    }
    QComboBox QAbstractItemView::item:hover,
    QComboBox QListView::item:hover {
        background-color: #EFEFEF;
        color: #2F8F5B;
    }
    QComboBox QAbstractItemView::item:selected,
    QComboBox QListView::item:selected {
        background-color: #F5F5F5;
        color: #2F8F5B;
    }

    /* Buttons */
    QPushButton.card-action-btn {
        background-color: transparent;
        color: #2F8F5B;
        border: none;
        font-size: 13px;
        font-weight: bold;
        text-align: left;
    }
    QPushButton.card-action-btn:hover {
        color: #26784C;
    }
    QPushButton.primary-btn {
        background-color: #8FE3B0;
        color: #10231A;
        border: none;
        border-radius: 10px;
        padding: 11px 24px;
        font-size: 14px;
        font-weight: bold;
    }
    QPushButton.primary-btn:hover {
        background-color: #7ED9A2;
    }
    QPushButton.secondary-btn {
        background-color: #E5E5E5;
        color: #3A3A3A;
        border: none;
        border-radius: 10px;
        padding: 11px 22px;
        font-size: 13px;
        font-weight: 600;
    }
    QPushButton.secondary-btn:hover {
        background-color: #D4D4D4;
        color: #292929;
    }
    QPushButton.warning-btn {
        background-color: #fee2e2;
        color: #b91c1c;
        border: 1px solid #fca5a5;
        border-radius: 10px;
        padding: 11px 22px;
        font-size: 13px;
        font-weight: bold;
    }
    QPushButton.warning-btn:hover {
        background-color: #fecaca;
    }
    QFrame#BottomActionBar {
        background-color: #ffffff;
        border-top: 1px solid #E5E5E5;
        border-bottom-right-radius: 16px;
    }
    QStackedWidget {
        border-bottom-right-radius: 16px;
    }

    /* Table & Header - Eliminate dark corner blocks! */
    QTableWidget {
        background-color: #ffffff;
        alternate-background-color: #F5F5F5;
        border: 1px solid #E5E5E5;
        border-radius: 12px;
        gridline-color: #EFEFEF;
        color: #292929;
    }
    QHeaderView {
        background-color: #F5F5F5;
        border: none;
    }
    QHeaderView::section {
        background-color: #F5F5F5;
        color: #4A4A4A;
        font-weight: bold;
        border: none;
        border-bottom: 1px solid #E5E5E5;
        padding: 8px 10px;
    }
    QTableCornerButton::section {
        background-color: #F5F5F5;
        border: none;
    }
    QLineEdit {
        background-color: #ffffff;
        border: 1px solid #D4D4D4;
        border-radius: 8px;
        padding: 6px 12px;
        color: #292929;
    }
    QTabBar::scroller {
        width: 38px;
    }
    QTabBar QToolButton {
        background-color: #2F8F5B;
        color: #ffffff;
        border: 1px solid #26784C;
        border-radius: 6px;
        margin: 1px;
        padding: 2px;
        font-weight: bold;
        min-width: 22px;
        min-height: 22px;
    }
    QTabBar QToolButton:hover {
        background-color: #26784C;
    }
    QTabBar QToolButton:disabled {
        background-color: #E5E5E5;
        border-color: #D4D4D4;
        color: #94a3b8;
    }
"""

DARK_THEME = """
    QMainWindow {
        background: transparent;
    }
    QWidget#CentralWidget {
        background-color: #292929;
        border: none;
    border-radius: 8px;
    }
    QWidget#Sidebar {
        background-color: #2A2B2C;
        border-top-left-radius: 0px;
        border-bottom-left-radius: 16px;
        border-right: 1px solid #3A3A3A;
    }
    QWidget#TitleBar {
        background-color: #292929;
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
        border-bottom: 1px solid #3A3A3A;
    }
    QLabel {
        color: #E8E8E8;
    }
    
    /* 图2右上角标题栏按钮 */
    QPushButton.title-btn {
        background-color: transparent;
        color: #A0A0A0;
        border: none;
        border-radius: 6px;
        font-size: 14px;
        font-weight: 600;
        min-width: 34px;
        max-width: 34px;
        min-height: 28px;
        max-height: 28px;
    }
    QPushButton#TitleBtnMax, QPushButton.TitleBtnMax {
        font-size: 17px;
        font-weight: 700;
    }
    QPushButton.title-btn:hover {
        background-color: #3A3A3A;
        color: #FFFFFF;
    }
    QPushButton.title-close-btn:hover {
        background-color: #EF4444;
        color: #FFFFFF;
    }
    QPushButton.theme-toggle-btn, QPushButton#ThemeToggleBtn { 
    background-color: transparent;
    color: #E8E8E8;
    border: none;
    border-radius: 10px;
    padding: 4px 6px;
    min-height: 24px;
}
    QPushButton.theme-toggle-btn:hover, QPushButton#ThemeToggleBtn:hover { background-color: #3A3A3A; border: none; }

    /* 图1优化：现代化暗色极简 6px 细致圆角滑动条 (全软件统一) */
    QScrollBar:vertical {
        border: none;
        background: transparent;
        width: 6px;
        margin: 0px;
        border-radius: 3px;
    }
    QScrollBar::handle:vertical {
        background: #3A3A3A;
        min-height: 24px;
        border-radius: 3px;
    }
    QScrollBar::handle:vertical:hover {
        background: #4A4A4A;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
        width: 0px;
        background: transparent;
        border: none;
    }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: transparent;
    }
    QScrollBar:horizontal {
        border: none;
        background: transparent;
        height: 0px;
        width: 0px;
        margin: 0px;
    }
    QScrollBar::handle:horizontal {
        background: transparent;
        min-width: 0px;
        height: 0px;
    }
    QScrollBar::handle:horizontal:hover {
        background: transparent;
    }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        width: 0px;
        height: 0px;
        background: transparent;
        border: none;
    }
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
        background: transparent;
    }

    /* Sidebar Navigation */
    QPushButton.nav-btn {
        background-color: transparent;
        color: #A0A0A0;
        border: none;
        border-radius: 10px;
        padding: 10px 14px;
        text-align: left;
        font-size: 13px;
        font-weight: 600;
    }
    QPushButton.nav-btn:hover {
        background-color: #3A3A3A;
        color: #ffffff;
    }
    QPushButton.nav-btn-active {
        background-color: #303132;
        color: #FFFFFF;
        font-weight: bold;
        border-radius: 10px;
        padding: 10px 14px;
        text-align: left;
        font-size: 13px;
    }

    /* Cards */
    QFrame.card {
        background-color: #2A2B2C;
        border: 1px solid #3A3A3A;
        border-radius: 14px;
    }
    QFrame.card:hover {
        border: 1px solid #4A4A4A;
    }

    /* Dropdowns */
    QComboBox {
        background-color: #292929;
        border: 1px solid #4A4A4A;
        border-radius: 8px;
        padding: 7px 12px;
        font-size: 13px;
        color: #E8E8E8;
    }
    QComboBox:hover {
        border: 1px solid #8A8A8A;
    }
    /* Native chevron (see the combo helper above). */
    QComboBox QAbstractItemView,
    QComboBox QListView,
    QComboBoxPrivateContainer,
    QListView#combo_popup {
        background-color: #2A2B2C;
        color: #E8E8E8;
        selection-background-color: #1e3a8a;
        selection-color: #A7F3D0;
        border: 1px solid #4A4A4A;
        border-radius: 8px;
        padding: 4px;
        outline: none;
    }
    QComboBox QAbstractItemView::item,
    QComboBox QListView::item {
        min-height: 30px;
        padding: 4px 10px;
        color: #E8E8E8;
        background-color: #2A2B2C;
    }
    QComboBox QAbstractItemView::item:hover,
    QComboBox QListView::item:hover {
        background-color: #3A3A3A;
        color: #A7F3D0;
    }
    QComboBox QAbstractItemView::item:selected,
    QComboBox QListView::item:selected {
        background-color: #1e3a8a;
        color: #A7F3D0;
    }

    /* Buttons */
    QPushButton.card-action-btn {
        background-color: transparent;
        color: #A7F3D0;
        border: none;
        font-size: 13px;
        font-weight: bold;
        text-align: left;
    }
    QPushButton.card-action-btn:hover {
        color: #A7F3D0;
    }
    QPushButton.primary-btn {
        background-color: #8FE3B0;
        color: #10231A;
        border: none;
        border-radius: 10px;
        padding: 11px 24px;
        font-size: 14px;
        font-weight: bold;
    }
    QPushButton.primary-btn:hover {
        background-color: #7ED9A2;
    }
    QPushButton.secondary-btn {
        background-color: #3A3A3A;
        color: #DDDDDD;
        border: none;
        border-radius: 10px;
        padding: 11px 22px;
        font-size: 13px;
        font-weight: 600;
    }
    QPushButton.secondary-btn:hover {
        background-color: #4A4A4A;
        color: #ffffff;
    }
    QPushButton.warning-btn {
        background-color: #7f1d1d;
        color: #fecaca;
        border: 1px solid #b91c1c;
        border-radius: 10px;
        padding: 11px 22px;
        font-size: 13px;
        font-weight: bold;
    }
    QPushButton.warning-btn:hover {
        background-color: #991b1b;
    }
    QFrame#BottomActionBar {
        background-color: #292929;
        border-top: 1px solid #3A3A3A;
        border-bottom-right-radius: 16px;
    }
    QStackedWidget {
        border-bottom-right-radius: 16px;
    }

    /* Table & Header - Eliminate dark corner blocks! */
    QTableWidget {
        background-color: #2A2B2C;
        alternate-background-color: #292929;
        border: 1px solid #3A3A3A;
        border-radius: 12px;
        gridline-color: #3A3A3A;
        color: #E8E8E8;
    }
    QHeaderView {
        background-color: #292929;
        border: none;
    }
    QHeaderView::section {
        background-color: #292929;
        color: #A0A0A0;
        font-weight: bold;
        border: none;
        border-bottom: 1px solid #3A3A3A;
        padding: 8px 10px;
    }
    QTableCornerButton::section {
        background-color: #292929;
        border: none;
    }
    QLineEdit {
        background-color: #292929;
        border: 1px solid #4A4A4A;
        border-radius: 8px;
        padding: 6px 12px;
        color: #E8E8E8;
    }
    QTabBar::scroller {
        width: 38px;
    }
    QTabBar QToolButton {
        background-color: #6FD398;
        color: #ffffff;
        border: 1px solid #6FD398;
        border-radius: 6px;
        margin: 1px;
        padding: 2px;
        font-weight: bold;
        min-width: 22px;
        min-height: 22px;
    }
    QTabBar QToolButton:hover {
        background-color: #6FD398;
    }
    QTabBar QToolButton:disabled {
        background-color: #3A3A3A;
        border-color: #4A4A4A;
        color: #8A8A8A;
    }
"""

class ModernMFGGUI(QMainWindow):
    BORDER_SIZE = 6

    def __init__(self):
        super().__init__()
        from common.ui_theme import install_combo_arrows
        install_combo_arrows(QApplication.instance())
        self.setWindowTitle("DM工具箱 - DLSS多帧生成补丁")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window | Qt.WindowType.WindowMinMaxButtonsHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.BORDER_SIZE = 7
        self.CORNER_SIZE = 20

        # Enable Windows 11 DWM native smooth rounded corners & immersive titlebar
        try:
            import ctypes
            hwnd = int(self.winId())
            corner_val = ctypes.c_int(2)  # DWMWCP_ROUND = 2
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(corner_val), ctypes.sizeof(corner_val))
            dark_val = ctypes.c_int(1 if (get_global_theme() == "dark") else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark_val), ctypes.sizeof(dark_val))
        except Exception:
            pass

        # Responsive screen adaptation
        screen = QGuiApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            target_w = min(int(avail.width() * 0.92), max(960, min(1200, int(avail.width() * 0.78))))
            target_h = min(int(avail.height() * 0.88), max(640, min(800, int(avail.height() * 0.80))))
            self.resize(target_w, target_h)
            min_w = min(820, max(600, int(avail.width() * 0.65)))
            min_h = min(540, max(420, int(avail.height() * 0.60)))
            self.setMinimumSize(min_w, min_h)
        else:
            self.resize(1120, 750)
            self.setMinimumSize(820, 540)

        # Drag & Resize tracking
        self._is_dragging = False
        self._drag_pos = QPoint()
        self._resize_edge = 0
        self._resize_start_pos = QPoint()
        self._resize_start_geom = self.geometry()
        self._edge_cursor_active = False

        qApp = QApplication.instance()
        if qApp:
            qApp.installEventFilter(self)

        # Base directory for persistent cache (beside .exe when frozen)
        if getattr(sys, 'frozen', False):
            self.base_dir = os.path.dirname(sys.executable)
        else:
            self.base_dir = str(Path(__file__).parent)

        # Set Window and Taskbar Icon
        icon_path = self.get_asset_path("mfg_icon.png")
        if os.path.exists(icon_path):
            app_icon = QIcon(icon_path)
            self.setWindowIcon(app_icon)
            QApplication.setWindowIcon(app_icon)

        # High-DPI font setup
        font = QtGui.QFont("Microsoft YaHei UI", 10)
        font.setStyleStrategy(QtGui.QFont.StyleStrategy.PreferAntialias)
        self.setFont(font)

        # Core logic
        self.updater = ComponentUpdater(legacy_root_dir=self.base_dir)
        self.scanner = GameScanner()
        self.patcher = PatchEngine(self.updater)
        self.rollback = RollbackEngine()
        self.rhi = RHIInstaller(cache_dir=str(self.updater.cache_dir))

        self.signals = WorkerSignals()
        self.signals.scan_finished.connect(self._on_scan_finished)
        self.signals.update_finished.connect(self._on_update_finished)
        self.signals.rhi_finished.connect(self._on_rhi_finished)
        self.signals.status_updated.connect(self._on_status_updated)
        self.signals.progress_updated.connect(self._on_progress_updated)

        self._active_progress_dlg: Optional[ModernProgressDialog] = None
        self.games: List[GameInfo] = []
        self.selected_game: Optional[GameInfo] = None
        self.use_bink: bool = False
        self.is_dark_mode: bool = (get_global_theme() == "dark")
        self.drag_position = QPoint()

        # Bi-directional INI synchronization engine (Stage 4)
        self._ini_watcher = QFileSystemWatcher(self)
        self._ini_watcher.fileChanged.connect(self._on_ini_file_changed)
        self._ini_watcher.directoryChanged.connect(self._on_ini_dir_changed)
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(400)
        self._debounce_timer.timeout.connect(self._on_ini_debounce_timeout)
        self._suppress_sync = False

        self._build_ui()
        self._apply_theme()
        self.center_on_screen()
        self._load_cache_status()
        self._load_cached_games_instant()
        self.trigger_background_scan()

        # 实时监听全局主题切换，实现全软件毫秒级无感同步
        self.theme_sync_timer = QTimer(self)
        self.theme_sync_timer.setInterval(500)
        self.theme_sync_timer.timeout.connect(self.check_external_theme_change)
        self.theme_sync_timer.start()

    def check_external_theme_change(self):
        """检查全局主题文件是否被其他子软件或主程序切换"""
        global_mode = get_global_theme()
        should_be_dark = (global_mode == "dark")
        if self.is_dark_mode != should_be_dark:
            self.is_dark_mode = should_be_dark
            self._apply_theme()

    def get_asset_path(self, filename: str) -> str:
        """Resolve asset path, checking PyInstaller _MEIPASS first, then local assets."""
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            p = os.path.join(sys._MEIPASS, "assets", filename)
            if os.path.exists(p):
                return p
        candidates = [
            os.path.join(self.base_dir, "assets", filename),
            os.path.join(str(Path(__file__).parent), "assets", filename)
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return candidates[0]

    def _apply_theme(self):
        theme_str = DARK_THEME if self.is_dark_mode else LIGHT_THEME
        app = QApplication.instance()
        if app:
            from common.ui_theme import combo_arrow_qss
            app.setStyleSheet(theme_str + combo_arrow_qss(self.is_dark_mode))
            # Synchronize application palette to prevent OS dark palette bleedthrough
            pal = QtGui.QPalette()
            if self.is_dark_mode:
                pal.setColor(QtGui.QPalette.ColorRole.Window, QColor("#292929"))
                pal.setColor(QtGui.QPalette.ColorRole.WindowText, QColor("#F5F5F5"))
                pal.setColor(QtGui.QPalette.ColorRole.Base, QColor("#2A2B2C"))
                pal.setColor(QtGui.QPalette.ColorRole.AlternateBase, QColor("#292929"))
                pal.setColor(QtGui.QPalette.ColorRole.Text, QColor("#F5F5F5"))
                pal.setColor(QtGui.QPalette.ColorRole.Button, QColor("#2A2B2C"))
                pal.setColor(QtGui.QPalette.ColorRole.ButtonText, QColor("#F5F5F5"))
                pal.setColor(QtGui.QPalette.ColorRole.Highlight, QColor("#3E9E69"))
                pal.setColor(QtGui.QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
            else:
                pal.setColor(QtGui.QPalette.ColorRole.Window, QColor("#F5F5F5"))
                pal.setColor(QtGui.QPalette.ColorRole.WindowText, QColor("#292929"))
                pal.setColor(QtGui.QPalette.ColorRole.Base, QColor("#ffffff"))
                pal.setColor(QtGui.QPalette.ColorRole.AlternateBase, QColor("#EFEFEF"))
                pal.setColor(QtGui.QPalette.ColorRole.Text, QColor("#292929"))
                pal.setColor(QtGui.QPalette.ColorRole.Button, QColor("#ffffff"))
                pal.setColor(QtGui.QPalette.ColorRole.ButtonText, QColor("#292929"))
                pal.setColor(QtGui.QPalette.ColorRole.Highlight, QColor("#2F8F5B"))
                pal.setColor(QtGui.QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
            app.setPalette(pal)
        self.setStyleSheet(theme_str)
        if self.centralWidget():
            self.centralWidget().setStyleSheet(theme_str)
        if hasattr(self, "btn_theme_toggle"):
            self.btn_theme_toggle.setText("")
            self.btn_theme_toggle.setIcon(theme_toggle_icon(self.is_dark_mode))
            self.btn_theme_toggle.setIconSize(QSize(16, 16))
            self.btn_theme_toggle.setToolTip("切换为浅色白天模式" if self.is_dark_mode else "切换为暗色黑夜模式")
        if hasattr(self, "btn_min"):
            self.btn_min.set_dark_mode(self.is_dark_mode)
        if hasattr(self, "btn_max"):
            self.btn_max.set_dark_mode(self.is_dark_mode)
            self.btn_max.set_maximized_state(self.isMaximized())
        if hasattr(self, "btn_close"):
            self.btn_close.set_dark_mode(self.is_dark_mode)
        if hasattr(self, "table_lib") and self.games:
            self._populate_library_table()

        # Top alert bar dynamic styling
        if hasattr(self, "top_alert"):
            if self.is_dark_mode:
                self.top_alert.setStyleSheet("""
                    background-color: #2A2B2C;
                    color: #34D399;
                    border: 1px solid #3A3A3A;
                    border-radius: 10px;
                    padding: 8px 16px;
                    font-size: 13px;
                    font-weight: 600;
                """)
            else:
                self.top_alert.setStyleSheet("""
                    background-color: #F5F5F5;
                    color: #059669;
                    border: 1px solid #E5E5E5;
                    border-radius: 10px;
                    padding: 8px 16px;
                """)

        if hasattr(self, "card_bink"):
            self._update_entry_cards_style()

        if hasattr(self, "size_grip") and self.size_grip:
            self.size_grip.set_dark_mode(self.is_dark_mode)

        # Apply DWM hardware rounded corners and theme border
        apply_dm_window_frame(self, self.is_dark_mode)

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        set_global_theme("dark" if self.is_dark_mode else "light")
        self._apply_theme()

    def _build_ui(self):
        central_widget = QWidget()
        central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(central_widget)

        root_vbox = QVBoxLayout(central_widget)
        root_vbox.setContentsMargins(0, 0, 0, 0)
        root_vbox.setSpacing(0)

        # 1. Custom Frameless Title Bar
        self.title_bar = QWidget()
        self.title_bar.setObjectName("TitleBar")
        self.title_bar.setFixedHeight(46)
        tb_layout = QHBoxLayout(self.title_bar)
        tb_layout.setContentsMargins(16, 0, 10, 0)
        tb_layout.setSpacing(10)

        # App brand logo
        icon_path = os.path.join(self.base_dir, "assets", "mfg_icon.png")
        if os.path.exists(icon_path):
            pix = QPixmap(icon_path).scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            tb_img = QLabel()
            tb_img.setPixmap(pix)
            tb_layout.addWidget(tb_img)
        else:
            tb_icon = QLabel("⚡")
            tb_icon.setStyleSheet("color: #2F8F5B; font-size: 16px; font-weight: bold;")
            tb_layout.addWidget(tb_icon)

        tb_title = QLabel("DM工具箱 - DLSS多帧生成补丁")
        tb_title.setStyleSheet("font-size: 13px; font-weight: bold;")
        tb_layout.addWidget(tb_title)
        tb_layout.addStretch()

        # Theme switch button (图2样式)
        self.btn_theme_toggle = QPushButton("")
        self.btn_theme_toggle.setFixedSize(30, 30)
        self.btn_theme_toggle.setIcon(theme_toggle_icon(self.is_dark_mode))
        self.btn_theme_toggle.setIconSize(QSize(16, 16))
        self.btn_theme_toggle.setObjectName("ThemeToggleBtn")
        self.btn_theme_toggle.setProperty("class", "theme-toggle-btn")
        self.btn_theme_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_theme_toggle.setToolTip("切换日间 / 夜间模式 (将同步切换所有打开的软件)")
        self.btn_theme_toggle.clicked.connect(self.toggle_theme)
        tb_layout.addWidget(self.btn_theme_toggle)

        # Window controls (图1高精度居中对齐)
        self.btn_min = CaptionButton(CaptionButtonType.MINIMIZE, self)
        self.btn_min.setToolTip("最小化")
        self.btn_min.clicked.connect(self.showMinimized)
        tb_layout.addWidget(self.btn_min)

        self.btn_max = CaptionButton(CaptionButtonType.MAXIMIZE, self)
        self.btn_max.setToolTip("最大化 / 还原")
        self.btn_max.clicked.connect(self._toggle_maximize)
        tb_layout.addWidget(self.btn_max)

        self.btn_close = CaptionButton(CaptionButtonType.CLOSE, self)
        self.btn_close.setToolTip("关闭")
        self.btn_close.clicked.connect(self.close)
        tb_layout.addWidget(self.btn_close)

        root_vbox.addWidget(self.title_bar)

        # 2. Main Body (Sidebar + QStackedWidget)
        body_widget = QWidget()
        body_layout = QHBoxLayout(body_widget)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # ------------------ SIDEBAR ------------------
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(14, 18, 14, 18)
        sidebar_layout.setSpacing(8)

        # Logo and Title
        logo_box = QLabel()
        if os.path.exists(icon_path):
            pix_large = QPixmap(icon_path).scaled(38, 38, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_box.setPixmap(pix_large)
        else:
            logo_box.setText("⚡")
            logo_box.setStyleSheet("background-color: #2F8F5B; color: white; border-radius: 8px; font-size: 18px; qproperty-alignment: AlignCenter;")
        logo_box.setFixedSize(38, 38)

        brand_vbox = QVBoxLayout()
        brand_vbox.setSpacing(1)
        lbl_b1 = QLabel("MFG Master")
        lbl_b1.setStyleSheet("font-size: 15px; font-weight: bold;")
        lbl_b2 = QLabel("插帧双引擎管理器")
        lbl_b2.setStyleSheet("font-size: 11px; color: #64748b;")
        brand_vbox.addWidget(lbl_b1)
        brand_vbox.addWidget(lbl_b2)

        logo_row = QHBoxLayout()
        logo_row.addWidget(logo_box)
        logo_row.addLayout(brand_vbox)
        sidebar_layout.addLayout(logo_row)
        sidebar_layout.addSpacing(14)

        # Navigation Buttons
        self.nav_buttons: List[QPushButton] = []
        nav_items = [
            ("🏠 首页概览", 0),
            ("🎮 游戏库管理", 1),
            ("⚡ 插帧引擎定制", 2),
            ("🛠️ RHI 模组生态", 3),
            ("☁️ 组件版本同步", 4),
            ("🛡️ 系统事务与还原", 5)
        ]

        for text, page_idx in nav_items:
            btn = QPushButton(text)
            btn.setProperty("class", "nav-btn-active" if page_idx == 0 else "nav-btn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, idx=page_idx: self.switch_page(idx))
            self.nav_buttons.append(btn)
            sidebar_layout.addWidget(btn)

        sidebar_layout.addStretch()

        # Sidebar Bottom Version Badge
        v_card = QFrame()
        v_card.setStyleSheet("border: 1px solid #D4D4D4; border-radius: 10px; padding: 10px;")
        v_layout = QVBoxLayout(v_card)
        v_layout.setContentsMargins(4, 4, 4, 4)
        v_layout.setSpacing(3)
        self.lbl_side_ver = QLabel("当前版本: v1.5.0 Pro")
        self.lbl_side_ver.setStyleSheet("font-size: 11px; color: #64748b;")
        self.lbl_side_hook = QLabel("● 核心拦截器就绪")
        self.lbl_side_hook.setStyleSheet("font-size: 12px; color: #16a34a; font-weight: bold;")
        v_layout.addWidget(self.lbl_side_ver)
        v_layout.addWidget(self.lbl_side_hook)
        sidebar_layout.addWidget(v_card)

        body_layout.addWidget(sidebar)

        # ------------------ STACKED MAIN CONTENT ------------------
        self.stacked_widget = QStackedWidget()

        # Page 0: 首页概览 (Dashboard)
        self.stacked_widget.addWidget(self._build_dashboard_page())

        # Page 1: 游戏库管理 (Library Table)
        self.stacked_widget.addWidget(self._build_library_page())

        # Page 2: 插帧双引擎定制
        self.stacked_widget.addWidget(self._build_engine_page())

        # Page 3: RHI 模组生态
        self.stacked_widget.addWidget(self._build_rhi_page())

        # Page 4: 组件版本同步
        self.stacked_widget.addWidget(self._build_updater_page())

        # Page 5: 系统事务与一键还原
        self.stacked_widget.addWidget(self._build_backup_page())

        body_layout.addWidget(self.stacked_widget)
        root_vbox.addWidget(body_widget)

    def _wrap_scroll(self, content_widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; } QScrollArea > QWidget > QWidget { background: transparent; }")
        scroll.setWidget(content_widget)
        return scroll

    # ------------------ PAGE BUILDERS ------------------
    def _build_dashboard_page(self) -> QWidget:
        page_container = QWidget()
        page_container_layout = QVBoxLayout(page_container)
        page_container_layout.setContentsMargins(0, 0, 0, 0)
        page_container_layout.setSpacing(0)

        # Scrollable upper cards container
        cards_widget = QWidget()
        layout = QVBoxLayout(cards_widget)
        layout.setContentsMargins(28, 18, 28, 14)
        layout.setSpacing(14)

        # Top Alert Pill
        self.top_alert = QLabel("● 实时多帧生成环境就绪 | Streamline 拦截通道与 Ada/Blackwell 补丁已激活")
        self.top_alert.setWordWrap(True)
        self.top_alert.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.top_alert)

        # Header
        hero_layout = QHBoxLayout()
        hero_text = QVBoxLayout()
        hero_text.setSpacing(2)
        lbl_h1 = QLabel("MFG Multi-Frame Master")
        lbl_h1.setStyleSheet("font-size: 24px; font-weight: 800;")
        lbl_h2 = QLabel("高效、稳定、易用的 DLSS-G 多帧生成双引擎一键修补与还原工具 (兼容国产独立大作)")
        lbl_h2.setStyleSheet("font-size: 13px; color: #64748b;")
        lbl_h2.setWordWrap(True)
        lbl_h2.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        hero_text.addWidget(lbl_h1)
        hero_text.addWidget(lbl_h2)
        hero_layout.addLayout(hero_text, 1)

        self.badge_mfg = QLabel("RTX 40 / 30 系列\nDLSS 3x~6x / XeSS")
        self.badge_mfg.setStyleSheet("""
            background-color: #E8E8E8;
            color: #2F8F5B;
            font-size: 12px;
            font-weight: bold;
            border-radius: 12px;
            padding: 8px 16px;
            qproperty-alignment: AlignCenter;
        """)
        hero_layout.addWidget(self.badge_mfg)
        layout.addLayout(hero_layout)

        # 2x2 Grid Cards
        grid = QGridLayout()
        grid.setSpacing(14)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        # Card 1: 目标游戏定制与选择 (Game Target Selection & Info Box)
        card1 = QFrame()
        card1.setProperty("class", "card")
        c1 = QVBoxLayout(card1)
        c1.setContentsMargins(18, 16, 18, 16)
        c1.setSpacing(10)

        # 1. Header (40x40 Icon Badge + Title/Refresh Row + Subtitle)
        header1 = QHBoxLayout()
        header1.setSpacing(12)

        self.badge_game = QLabel("🎯")
        self.badge_game.setFixedSize(40, 40)
        self.badge_game.setStyleSheet(f"""
            background-color: {'#1e3a8a' if self.is_dark_mode else '#E8E8E8'};
            color: {'#7ED9A2' if self.is_dark_mode else '#26784C'};
            border-radius: 10px;
            font-size: 18px;
            font-weight: 800;
            qproperty-alignment: AlignCenter;
            border: none;
        """)
        header1.addWidget(self.badge_game)

        text_vbox1 = QVBoxLayout()
        text_vbox1.setSpacing(2)

        title_row1 = QHBoxLayout()
        title_row1.setSpacing(8)
        lbl_title1 = QLabel("目标游戏定制与选择")
        lbl_title1.setStyleSheet("font-size: 14px; font-weight: bold;")
        lbl_title1.setWordWrap(False)
        title_row1.addWidget(lbl_title1)
        title_row1.addStretch()

        self.btn_rescan_header = QPushButton("🔄 刷新库")
        self.btn_rescan_header.setObjectName("BtnRescanHeader")
        self.btn_rescan_header.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_rescan_header.setFixedHeight(26)
        self.btn_rescan_header.clicked.connect(self.trigger_background_scan)
        title_row1.addWidget(self.btn_rescan_header)
        text_vbox1.addLayout(title_row1)

        lbl_desc1 = QLabel("自动扫描 Steam / Epic / GOG / WeGame 等主流平台及本地游戏库")
        lbl_desc1.setStyleSheet("font-size: 11px; color: #64748b;")
        lbl_desc1.setWordWrap(True)
        text_vbox1.addWidget(lbl_desc1)

        header1.addLayout(text_vbox1, 1)
        c1.addLayout(header1)

        # 2. Game Selection Dropdown
        self.combo_games = QComboBox()
        self.combo_games.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.combo_games.setMinimumContentsLength(8)
        self.combo_games.setMinimumHeight(38)
        self.combo_games.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.combo_games.currentIndexChanged.connect(self._on_game_dropdown_changed)
        c1.addWidget(self.combo_games)

        # 3. Current Game Info Frame (CardGameInfo)
        self.card_game_info = QFrame()
        self.card_game_info.setObjectName("CardGameInfo")
        info_layout = QVBoxLayout(self.card_game_info)
        info_layout.setContentsMargins(12, 10, 12, 10)
        info_layout.setSpacing(6)

        # Row 1: Executable Path
        path_row = QHBoxLayout()
        path_row.setSpacing(6)
        lbl_p_title = QLabel("📍 路径:")
        lbl_p_title.setObjectName("InfoRowTitle")
        lbl_p_title.setStyleSheet("font-size: 11px; font-weight: 700;")
        lbl_p_title.setFixedWidth(46)
        path_row.addWidget(lbl_p_title)

        self.lbl_game_path = QLabel("正在检索游戏库...")
        self.lbl_game_path.setStyleSheet("font-size: 11px; line-height: 1.3;")
        self.lbl_game_path.setWordWrap(True)
        path_row.addWidget(self.lbl_game_path, 1)

        self.btn_open_game_dir = QPushButton("📂")
        self.btn_open_game_dir.setToolTip("在文件资源管理器中直接打开游戏所在文件夹")
        self.btn_open_game_dir.setFixedSize(26, 26)
        self.btn_open_game_dir.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_game_dir.clicked.connect(self._on_open_selected_game_dir)
        path_row.addWidget(self.btn_open_game_dir)
        info_layout.addLayout(path_row)

        # Row 2: Architecture / Engine
        arch_row = QHBoxLayout()
        arch_row.setSpacing(6)
        lbl_a_title = QLabel("🎮 架构:")
        lbl_a_title.setObjectName("InfoRowTitle")
        lbl_a_title.setStyleSheet("font-size: 11px; font-weight: 700;")
        lbl_a_title.setFixedWidth(46)
        arch_row.addWidget(lbl_a_title)

        self.lbl_info_arch = QLabel("检测中...")
        self.lbl_info_arch.setStyleSheet("font-size: 11px; color: #2F8F5B; font-weight: 600;")
        self.lbl_info_arch.setWordWrap(True)
        arch_row.addWidget(self.lbl_info_arch, 1)
        info_layout.addLayout(arch_row)

        # Row 3: Patch Status
        patch_row = QHBoxLayout()
        patch_row.setSpacing(6)
        lbl_s_title = QLabel("🛡️ 状态:")
        lbl_s_title.setObjectName("InfoRowTitle")
        lbl_s_title.setStyleSheet("font-size: 11px; font-weight: 700;")
        lbl_s_title.setFixedWidth(46)
        patch_row.addWidget(lbl_s_title)

        self.lbl_info_patch = QLabel("未修补")
        self.lbl_info_patch.setStyleSheet("font-size: 11px; font-weight: 600;")
        self.lbl_info_patch.setWordWrap(True)
        patch_row.addWidget(self.lbl_info_patch, 1)
        info_layout.addLayout(patch_row)

        c1.addWidget(self.card_game_info)

        # 4. Secondary Action Pick Buttons
        pick_row = QHBoxLayout()
        pick_row.setSpacing(8)

        self.btn_pick_exe = QPushButton("📁 手动选择主程序 (.exe)")
        self.btn_pick_exe.setObjectName("BtnPickExe")
        self.btn_pick_exe.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pick_exe.setMinimumHeight(34)
        self.btn_pick_exe.clicked.connect(self.on_pick_exe_manually)
        pick_row.addWidget(self.btn_pick_exe, 1)

        self.btn_pick_dir = QPushButton("📂 手动选择游戏文件夹")
        self.btn_pick_dir.setObjectName("BtnPickDir")
        self.btn_pick_dir.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pick_dir.setMinimumHeight(34)
        self.btn_pick_dir.clicked.connect(self.on_pick_dir_manually)
        pick_row.addWidget(self.btn_pick_dir, 1)

        c1.addLayout(pick_row)
        c1.addStretch()

        grid.addWidget(card1, 0, 0)

        # Card 2: 插帧引擎模式
        card2 = self._create_card("⚙️", "#F5F5F5", "#7e22ce", "插帧引擎后端定制", "dashdogy (独立) / mavismmg (ReShade) / OptiScaler (FSR 3.1 跨卡)")
        c2 = card2.layout()
        self.combo_backend = QComboBox()
        self.combo_backend.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.combo_backend.setMinimumContentsLength(8)
        self.combo_backend.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.combo_backend.addItem("🤖 智能推荐 (架构与环境自适应)", BackendType.SMART_AUTO)
        self.combo_backend.addItem("📦 模式 A: 独立代理 (version/winmm)", BackendType.STANDALONE)
        self.combo_backend.addItem("🎨 模式 B: ReShade 插件 (renodx-mfgunlock)", BackendType.RESHADE_ADDON)
        self.combo_backend.addItem("🚀 模式 C: OptiScaler / XeSS 2.0 / FSR 3.1 (全显卡 2X~4X 多倍插帧)", BackendType.OPTISCALER_FSR)
        self.combo_backend.currentIndexChanged.connect(self._on_backend_dropdown_changed)
        c2.addWidget(self.combo_backend)

        self.lbl_backend_desc = QLabel("推荐机制: 目标目录存在 ReShade 则优先 Addon，否则使用独立代理")
        self.lbl_backend_desc.setStyleSheet("font-size: 11px; color: #64748b; line-height: 1.3;")
        self.lbl_backend_desc.setWordWrap(True)
        c2.addWidget(self.lbl_backend_desc)

        # 1. Bink2 Chain Hook Card Container
        self.card_bink = QFrame()
        self.card_bink.setObjectName("CardBink")
        self.card_bink.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.card_bink.setCursor(Qt.CursorShape.PointingHandCursor)
        self.card_bink.setMinimumHeight(42)
        cb_layout = QVBoxLayout(self.card_bink)
        cb_layout.setContentsMargins(10, 4, 10, 4)
        cb_layout.setSpacing(0)

        self.btn_bink_toggle = QPushButton(f"⚙️ Bink2 链式劫持: {'【已启用】' if self.use_bink else '【已禁用】'} →")
        self.btn_bink_toggle.setProperty("class", "card-action-btn")
        self.btn_bink_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_bink_toggle.setMinimumHeight(34)
        self.btn_bink_toggle.clicked.connect(self._toggle_bink)
        cb_layout.addWidget(self.btn_bink_toggle)
        c2.addWidget(self.card_bink)

        # 2. Frame Generation Guide Card Container
        self.card_guide = QFrame()
        self.card_guide.setObjectName("CardGuide")
        self.card_guide.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.card_guide.setCursor(Qt.CursorShape.PointingHandCursor)
        self.card_guide.setMinimumHeight(42)
        cg_layout = QVBoxLayout(self.card_guide)
        cg_layout.setContentsMargins(10, 4, 10, 4)
        cg_layout.setSpacing(0)

        self.btn_show_guide = QPushButton("📖 各插帧模式使用指南与英文对照 →")
        self.btn_show_guide.setProperty("class", "card-action-btn")
        self.btn_show_guide.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_show_guide.setMinimumHeight(34)
        self.btn_show_guide.clicked.connect(self.on_show_guide_click)
        cg_layout.addWidget(self.btn_show_guide)
        c2.addWidget(self.card_guide)

        # 3. Preset Multiplier Configuration Card Container
        self.card_preset = QFrame()
        self.card_preset.setObjectName("CardPreset")
        self.card_preset.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.card_preset.setCursor(Qt.CursorShape.PointingHandCursor)
        self.card_preset.setMinimumHeight(54)
        cp_layout = QVBoxLayout(self.card_preset)
        cp_layout.setContentsMargins(10, 6, 10, 6)
        cp_layout.setSpacing(2)

        self.btn_preset_cfg = QPushButton("⚡ 预设多帧生成参数与倍率 (中文面板) →")
        self.btn_preset_cfg.setProperty("class", "card-action-btn")
        self.btn_preset_cfg.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_preset_cfg.setMinimumHeight(32)
        self.btn_preset_cfg.clicked.connect(self.on_open_preset_config_dialog)
        cp_layout.addWidget(self.btn_preset_cfg)

        self.lbl_preset_summary = QLabel()
        self.lbl_preset_summary.setStyleSheet("font-size: 11px; line-height: 1.3;")
        self.lbl_preset_summary.setWordWrap(True)
        self._update_preset_summary()
        cp_layout.addWidget(self.lbl_preset_summary)
        c2.addWidget(self.card_preset)
        self._update_entry_cards_style()

        # 明显且高度醒目的 RHI 快捷启动横幅 (响应用户“打开RHI那个选项要明显一点”需求)
        self.rhi_banner = QFrame()
        self.rhi_banner.setObjectName("RHIBanner")
        self.rhi_banner.setStyleSheet("""
            QFrame#RHIBanner {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #047857);
                border: 1px solid #10b981;
                border-radius: 10px;
            }
        """)
        rb_layout = QVBoxLayout(self.rhi_banner)
        rb_layout.setContentsMargins(12, 10, 12, 10)
        rb_layout.setSpacing(6)

        # Row 1: Title + Icon
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        lbl_rhi_icon = QLabel("🛠️")
        lbl_rhi_icon.setStyleSheet("font-size: 16px; font-family: 'Segoe UI Emoji', 'Microsoft YaHei UI'; background: transparent; border: none;")
        top_row.addWidget(lbl_rhi_icon)

        self.lbl_rhi_t = QLabel("ReShade / RHI 模组底座")
        self.lbl_rhi_t.setStyleSheet("font-size: 13px; font-weight: bold; color: #E8E8E8; background: transparent; border: none;")
        top_row.addWidget(self.lbl_rhi_t)
        top_row.addStretch()
        rb_layout.addLayout(top_row)

        # Row 2: Wrapped hint
        self.lbl_rhi_desc_hint = QLabel("模式 B 必需组件 · 解决游戏内按键无显示 · 内置主程序路径直达助手")
        self.lbl_rhi_desc_hint.setStyleSheet("font-size: 11px; color: #a7f3d0; background: transparent; border: none; line-height: 1.3;")
        self.lbl_rhi_desc_hint.setWordWrap(True)
        rb_layout.addWidget(self.lbl_rhi_desc_hint)

        # Row 3: Prominent Full-Width Launch Button
        self.btn_launch_rhi_quick = QPushButton("🚀 立即打开 RHI 安装器 →")
        self.btn_launch_rhi_quick.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_launch_rhi_quick.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #065f46;
                border: 1px solid #a7f3d0;
                border-radius: 6px;
                padding: 7px 14px;
                font-size: 12px;
                font-weight: 800;
            }
            QPushButton:hover {
                background-color: #ecfdf5;
                color: #047857;
            }
        """)
        self.btn_launch_rhi_quick.clicked.connect(self.on_quick_launch_rhi_for_game)
        rb_layout.addWidget(self.btn_launch_rhi_quick)

        c2.addWidget(self.rhi_banner)
        card2.setMinimumHeight(480)
        grid.addWidget(card2, 0, 1)

        # Card 3: 架构与环境检测
        card3 = self._create_card("⚡", "#ffedd5", "#c2410c", "Streamline 与 DLSS-G 状态", "NVIDIA Streamline 运行时、DLSS-G 310.x 资格与运行锁")
        c3 = card3.layout()
        self.lbl_streamline_stat = QLabel("Streamline: 待检测 | nvngx_dlssg: 待检测")
        self.lbl_streamline_stat.setStyleSheet("font-size: 13px; font-weight: 600;")
        self.lbl_streamline_stat.setWordWrap(True)
        c3.addWidget(self.lbl_streamline_stat)

        self.lbl_lock_stat = QLabel("运行状态: 未运行 (就绪)")
        self.lbl_lock_stat.setStyleSheet("font-size: 11px; color: #16a34a;")
        self.lbl_lock_stat.setWordWrap(True)
        c3.addWidget(self.lbl_lock_stat)

        btn_rescan = QPushButton("🔄 重新扫描本地游戏库 →")
        btn_rescan.setProperty("class", "card-action-btn")
        btn_rescan.setStyleSheet("color: #c2410c; font-weight: bold;")
        btn_rescan.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_rescan.clicked.connect(self.trigger_background_scan)
        c3.addWidget(btn_rescan)
        grid.addWidget(card3, 1, 0)

        # Card 4: 云端组件同步与加速
        card4 = self._create_card("☁️", "#ccfbf1", "#0f766e", "云端组件库与热更新", "GitHub 资产热更新、镜像加速与本地离线版本缓存")
        c4 = card4.layout()
        h_mirror = QHBoxLayout()
        lbl_mirror = QLabel("加速节点:")
        h_mirror.addWidget(lbl_mirror)
        self.combo_mirror = QComboBox()
        self.combo_mirror.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.combo_mirror.setMinimumContentsLength(8)
        self.combo_mirror.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        for m in DEFAULT_MIRRORS.keys():
            self.combo_mirror.addItem(m)
        self.combo_mirror.setCurrentText("GHProxy")
        h_mirror.addWidget(self.combo_mirror)
        c4.addLayout(h_mirror)

        h_channel = QHBoxLayout()
        lbl_channel = QLabel("Opti通道:")
        h_channel.addWidget(lbl_channel)
        self.combo_opti_channel = QComboBox()
        self.combo_opti_channel.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.combo_opti_channel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.combo_opti_channel.addItem("🔥 Nightly 预览版 (推荐 · Opti 10 / XeMFG多帧)", "nightly")
        self.combo_opti_channel.addItem("🛡️ Stable 稳定版 (官方传统 v0.9.4)", "stable")
        h_channel.addWidget(self.combo_opti_channel)
        c4.addLayout(h_channel)

        self.lbl_cache_summary = QLabel("本地缓存: 正在读取...")
        self.lbl_cache_summary.setStyleSheet("font-size: 11px; color: #64748b;")
        self.lbl_cache_summary.setWordWrap(True)
        c4.addWidget(self.lbl_cache_summary)

        sync_btn_row = QHBoxLayout()
        sync_btn_row.setSpacing(10)

        btn_sync = QPushButton("☁️ 检查并同步最新版本 →")
        btn_sync.setProperty("class", "card-action-btn")
        btn_sync.setStyleSheet("color: #0f766e; font-weight: bold;")
        btn_sync.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_sync.clicked.connect(self.on_sync_updates_click)
        sync_btn_row.addWidget(btn_sync)

        btn_clear_quick = QPushButton("🗑️ 删除缓存")
        btn_clear_quick.setProperty("class", "card-action-btn")
        btn_clear_quick.setStyleSheet("color: #dc2626; font-weight: bold;")
        btn_clear_quick.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear_quick.clicked.connect(self.on_clear_cache_click)
        sync_btn_row.addWidget(btn_clear_quick)
        sync_btn_row.addStretch()

        c4.addLayout(sync_btn_row)
        grid.addWidget(card4, 1, 1)

        layout.addLayout(grid)
        layout.addStretch()

        scroll_area = self._wrap_scroll(cards_widget)
        page_container_layout.addWidget(scroll_area, 1)

        # Bottom Action Bar (Fixed at bottom so it's always accessible without scrolling)
        bottom_bar_frame = QFrame()
        bottom_bar_frame.setObjectName("BottomActionBar")
        bottom_bar = QHBoxLayout(bottom_bar_frame)
        bottom_bar.setContentsMargins(28, 12, 28, 12)
        bottom_bar.setSpacing(14)

        self.lbl_status = QLabel("● 状态: 就绪 | 补丁状态: 未修补")
        self.lbl_status.setStyleSheet("font-size: 13px; font-weight: 500;")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        bottom_bar.addWidget(self.lbl_status, 1)

        btn_restore = QPushButton("一键还原官方真实文件")
        btn_restore.setProperty("class", "secondary-btn")
        btn_restore.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_restore.clicked.connect(self.on_restore_click)
        bottom_bar.addWidget(btn_restore)

        btn_patch = QPushButton("立即应用全套自定义配置 →")
        btn_patch.setProperty("class", "primary-btn")
        btn_patch.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_patch.clicked.connect(self.on_patch_click)
        bottom_bar.addWidget(btn_patch)

        self.size_grip = DMSizeGrip(self)
        self.size_grip.set_dark_mode(self.is_dark_mode)
        bottom_bar.addWidget(self.size_grip, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)

        page_container_layout.addWidget(bottom_bar_frame, 0)
        return page_container

    def _build_library_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(14)

        # Header
        h_row = QHBoxLayout()
        h_row.setSpacing(14)

        title_box = QVBoxLayout()
        title_box.setSpacing(3)
        title = QLabel("已检索游戏库管理")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        title_box.addWidget(title)

        self.lbl_lib_count = QLabel("智能扫描并检索已安装的本地游戏与启动程序")
        self.lbl_lib_count.setStyleSheet("font-size: 12px; color: #64748B;")
        title_box.addWidget(self.lbl_lib_count)
        h_row.addLayout(title_box)
        h_row.addStretch()

        self.lib_search = QLineEdit()
        self.lib_search.setPlaceholderText("🔍 快速搜索游戏名称...")
        self.lib_search.setFixedWidth(240)
        self.lib_search.setMinimumHeight(36)
        self.lib_search.textChanged.connect(self._filter_library_table)
        h_row.addWidget(self.lib_search)

        btn_add_lib = QPushButton("➕ 手动添加游戏")
        btn_add_lib.setProperty("class", "primary-btn")
        btn_add_lib.setMinimumHeight(36)
        btn_add_lib.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add_lib.clicked.connect(self.on_pick_exe_manually)
        h_row.addWidget(btn_add_lib)

        layout.addLayout(h_row)

        # Table in Card frame
        card_table = QFrame()
        card_table.setProperty("class", "card")
        card_layout = QVBoxLayout(card_table)
        card_layout.setContentsMargins(8, 8, 8, 8)
        card_layout.setSpacing(0)

        self.table_lib = QTableWidget()
        self.table_lib.setColumnCount(5)
        self.table_lib.setHorizontalHeaderLabels(["游戏名称", "平台", "DLSS-G 资格", "补丁状态", "真实主程序路径"])
        self.table_lib.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table_lib.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table_lib.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table_lib.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table_lib.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table_lib.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table_lib.setColumnWidth(0, 240)
        self.table_lib.setColumnWidth(1, 90)
        self.table_lib.setColumnWidth(2, 130)
        self.table_lib.setColumnWidth(3, 130)
        self.table_lib.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_lib.verticalHeader().setVisible(False)
        self.table_lib.verticalHeader().setDefaultSectionSize(44)
        self.table_lib.cellClicked.connect(self._on_table_cell_clicked)
        self.table_lib.cellDoubleClicked.connect(self._on_table_cell_double_clicked)
        card_layout.addWidget(self.table_lib)

        layout.addWidget(card_table, 1)

        return page

    def _build_engine_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(16)

        title = QLabel("插帧双引擎深度定制与高级参数")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        card_standalone = self._create_card("A", "#E8E8E8", "#26784C", "模式 A: dashdogy/MFG-Unlocker 代理参数", "适用于 RTX 40 & RTX 30 系列，支持 Preset C 及 XeSS 插帧")
        cs_layout = card_standalone.layout()
        cs_layout.addWidget(QLabel("• 注入方式: Proxy DLL 劫持 (优先级: version.dll > winmm.dll > dinput8.dll)"))
        cs_layout.addWidget(QLabel("• 交互菜单: 游戏内默认按 【Backspace】 呼出 ImGui 菜单"))
        cs_layout.addWidget(QLabel("• Bink 链式劫持: 将原有 bink2w64.dll 重命名为 bink2w64Hooked.dll，防反篡改屏蔽"))
        layout.addWidget(card_standalone)

        card_addon = self._create_card("B", "#F5F5F5", "#7e22ce", "模式 B: mavismmg/MFGAdaUnlock-RenoDx 插件参数", "依赖 ReShade with Addon Support，集成 Blackwell 内核与抗伪影技术")
        ca_layout = card_addon.layout()
        ca_layout.addWidget(QLabel("• 注入方式: ReShade.ini [ADDON] LoadFromDllMain 极早加载"))
        ca_layout.addWidget(QLabel("• 交互菜单: 游戏内按 【Home】 键在 ReShade 面板中调校"))
        ca_layout.addWidget(QLabel("• 专属黑科技: 薄几何体插值优化 (ISR & VWB)、边缘抗伪影 (BAM)、HDR UI 防撕裂"))
        layout.addWidget(card_addon)

        card_optiscaler = self._create_card("C", "#ffedd5", "#c2410c", "模式 C: OptiScaler / XeSS 2.0 / FSR 3.1 跨架构转译 (全显卡 2X~4X 多倍插帧)", "专为非 40 系显卡及 40 系尝鲜设计，将原生 DLSS 3 转译为 XeFG / FSR 3.1 帧生成")
        co_layout = card_optiscaler.layout()
        co_layout.addWidget(QLabel("• 核心原理: fakenvapi 伪装开启游戏内 DLSS 3 帧生成开关，按预设桥接至 Intel XeFG 或 AMD FSR 3.1 算力管线"))
        co_layout.addWidget(QLabel("• 多倍率支持: 原生支持 Intel XeSS 2.0 官方插帧 (2X/3X/4X) 与 FSR 3.1 (2X) 双重内核自由切换"))
        co_layout.addWidget(QLabel("• 注入方式: Proxy DLL 劫持 (优先级: dxgi.dll > version.dll > winmm.dll)"))
        co_layout.addWidget(QLabel("• 免调参防闪退: 工具箱全自动托管参数，已默认禁用易引发 DX12 崩溃的 ImGui 菜单，进游戏开启【DLSS 帧生成】即直接生效"))

        btn_page2_preset = QPushButton("⚙️ 打开模式 C / OptiScaler 中文预设与倍率参数面板 →")
        btn_page2_preset.setProperty("class", "card-action-btn")
        btn_page2_preset.setStyleSheet("color: #c2410c; font-weight: bold; font-size: 13px; margin-top: 6px;")
        btn_page2_preset.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_page2_preset.clicked.connect(self.on_open_preset_config_dialog)
        co_layout.addWidget(btn_page2_preset)
        layout.addWidget(card_optiscaler)

        layout.addStretch()
        return self._wrap_scroll(page)

    def _build_rhi_page(self) -> QWidget:
        """New RHI (ReShade HDR Installer) page."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(16)

        title = QLabel("🛠️ RHI (ReShade HDR Installer) 模组生态集成")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        card_rhi = self._create_card("🛠️", "#E8E8E8", "#2F8F5B", "RankFTW/RHI 全能图形与 HDR 模组安装器", "一键安装 ReShade (Addon 版)、RenoDX、OptiScaler 跨架构插帧及 DLSS 核心库")
        c_layout = card_rhi.layout()
        c_layout.addWidget(QLabel("• 项目开源地址: https://github.com/RankFTW/RHI"))
        c_layout.addWidget(QLabel("• 核心功能: 自动化为任意游戏部署 ReShade with Addon Support、配置 RenoDX HDR 以及 DLSS/FSR 模组。"))

        # Manual path & current path selection box
        path_box = QVBoxLayout()
        path_box.setSpacing(8)

        lbl_path_title = QLabel("RHI 可执行文件路径:")
        lbl_path_title.setStyleSheet("font-weight: 600; font-size: 12px;")
        path_box.addWidget(lbl_path_title)

        h_path = QHBoxLayout()
        h_path.setSpacing(10)

        self.line_rhi_path = QLineEdit()
        self.line_rhi_path.setReadOnly(True)
        self.line_rhi_path.setPlaceholderText("自动检测或手动指定 RHI 路径 (RHI.exe / RHI-Setup.exe)...")
        h_path.addWidget(self.line_rhi_path, 1)

        self.btn_browse_rhi = QPushButton("📁 手动指定路径 (.exe)")
        self.btn_browse_rhi.setProperty("class", "secondary-btn")
        self.btn_browse_rhi.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_browse_rhi.clicked.connect(self.on_browse_rhi_click)
        h_path.addWidget(self.btn_browse_rhi)

        self.btn_reset_rhi = QPushButton("🔄 重置为自动检测")
        self.btn_reset_rhi.setProperty("class", "secondary-btn")
        self.btn_reset_rhi.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset_rhi.clicked.connect(self.on_reset_rhi_click)
        h_path.addWidget(self.btn_reset_rhi)

        path_box.addLayout(h_path)
        c_layout.addLayout(path_box)

        self.lbl_rhi_status = QLabel("本地状态: 正在检测 RHI...")
        self.lbl_rhi_status.setStyleSheet("font-size: 13px; font-weight: bold; color: #16a34a;")
        c_layout.addWidget(self.lbl_rhi_status)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.btn_launch_rhi = QPushButton("🚀 启动 / 运行 RHI 工具")
        self.btn_launch_rhi.setProperty("class", "primary-btn")
        self.btn_launch_rhi.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_launch_rhi.clicked.connect(self.on_launch_rhi_click)
        btn_row.addWidget(self.btn_launch_rhi)

        self.btn_download_rhi = QPushButton("☁️ 下载最新 RHI-Setup.exe (使用加速镜像)")
        self.btn_download_rhi.setProperty("class", "secondary-btn")
        self.btn_download_rhi.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_download_rhi.clicked.connect(self.on_download_rhi_click)
        btn_row.addWidget(self.btn_download_rhi)

        btn_row.addStretch()
        c_layout.addLayout(btn_row)
        layout.addWidget(card_rhi)

        # Real-time ReShade & Addon Ecosystem Status Card for Current Game
        card_eco = self._create_card("🎮", "#ede9fe", "#7c3aed", "当前选中游戏模组生态实时检测 (ReShade / RenoDX / HDR)", "实时感知目标游戏目录的 ReShade 宿主与已部署的全部 .addon64 模组")
        ce_layout = card_eco.layout()
        self.lbl_rhi_eco_status = QLabel("正在读取当前选定游戏模组状态...")
        self.lbl_rhi_eco_status.setStyleSheet("font-size: 13px; line-height: 1.6;")
        self.lbl_rhi_eco_status.setWordWrap(True)
        ce_layout.addWidget(self.lbl_rhi_eco_status)
        layout.addWidget(card_eco)

        self._refresh_rhi_display()
        layout.addStretch()
        return self._wrap_scroll(page)

    def _build_updater_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(16)

        title = QLabel("云端组件版本同步与离线缓存管理")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        self.card_cache_info = self._create_card("🗄️", "#ccfbf1", "#0f766e", "本地组件资产库与存储管理", "独立存储于 AppData 目录，避免污染软件根目录")
        c_layout = self.card_cache_info.layout()
        self.lbl_cache_detailed = QLabel("正在读取版本缓存索引...")
        self.lbl_cache_detailed.setStyleSheet("font-size: 13px; line-height: 1.6;")
        self.lbl_cache_detailed.setWordWrap(True)
        c_layout.addWidget(self.lbl_cache_detailed)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        btn_sync_now = QPushButton("☁️ 立即同步最新组件 (异步下载)")
        btn_sync_now.setProperty("class", "primary-btn")
        btn_sync_now.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_sync_now.clicked.connect(self.on_sync_updates_click)
        btn_row.addWidget(btn_sync_now)

        self.btn_clear_cache = QPushButton("🗑️ 删除/清空本地缓存")
        self.btn_clear_cache.setProperty("class", "warning-btn")
        self.btn_clear_cache.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear_cache.clicked.connect(self.on_clear_cache_click)
        btn_row.addWidget(self.btn_clear_cache)

        btn_open_folder = QPushButton("📁 打开缓存所在文件夹")
        btn_open_folder.setProperty("class", "secondary-btn")
        btn_open_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open_folder.clicked.connect(self.on_open_cache_dir_click)
        btn_row.addWidget(btn_open_folder)

        btn_row.addStretch()
        c_layout.addLayout(btn_row)
        layout.addWidget(self.card_cache_info)

        layout.addStretch()
        return self._wrap_scroll(page)

    def _build_backup_page(self) -> QWidget:
        """Enhanced Backup & Rollback Page with Clear Game Selection and Manifest Viewer."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(16)

        title = QLabel("系统清单事务与一键无损还原")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        # Card 1: Target Game Selector for Rollback
        card_target = self._create_card("🎯", "#E8E8E8", "#26784C", "选择还原目标游戏", "明确查看当前选中的游戏、补丁状态及事务清单详情")
        ct_layout = card_target.layout()

        self.combo_backup_game = QComboBox()
        self.combo_backup_game.currentIndexChanged.connect(self._on_backup_game_changed)
        ct_layout.addWidget(self.combo_backup_game)

        self.lbl_backup_detail = QLabel("请在上方选择需要检查或还原的游戏...")
        self.lbl_backup_detail.setStyleSheet("font-size: 13px; line-height: 1.5;")
        self.lbl_backup_detail.setWordWrap(True)
        ct_layout.addWidget(self.lbl_backup_detail)

        layout.addWidget(card_target)

        # Card 2: Rollback Action
        card_action = self._create_card("🛡️", "#fee2e2", "#dc2626", "一键安全纯净回滚", "基于 .mfg_patch_manifest.json 事务清单精准还原原始文件，绝不误删游戏自带内容")
        ca_layout = card_action.layout()

        self.lbl_manifest_summary = QLabel("清单状态: 未检测到修补快照")
        self.lbl_manifest_summary.setStyleSheet("font-size: 12px; color: #64748b;")
        ca_layout.addWidget(self.lbl_manifest_summary)

        self.btn_execute_restore = QPushButton("🔄 还原当前选中游戏: 【未选择】 到官方纯净原版")
        self.btn_execute_restore.setProperty("class", "warning-btn")
        self.btn_execute_restore.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_execute_restore.clicked.connect(self.on_restore_click)
        ca_layout.addWidget(self.btn_execute_restore)

        layout.addWidget(card_action)
        layout.addStretch()
        return self._wrap_scroll(page)

    def _create_card(self, badge_char: str, badge_color: str, badge_text_color: str, title: str, desc: str) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(10)

        badge = QLabel(badge_char)
        badge.setFixedSize(36, 36)
        badge.setStyleSheet(f"""
            background-color: {badge_color};
            color: {badge_text_color};
            border-radius: 10px;
            font-size: 16px;
            font-weight: 800;
            qproperty-alignment: AlignCenter;
            border: none;
        """)
        header.addWidget(badge)

        text_vbox = QVBoxLayout()
        text_vbox.setSpacing(2)
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        lbl_title.setWordWrap(True)
        lbl_desc = QLabel(desc)
        lbl_desc.setStyleSheet("font-size: 11px; color: #64748b;")
        lbl_desc.setWordWrap(True)
        text_vbox.addWidget(lbl_title)
        text_vbox.addWidget(lbl_desc)
        header.addLayout(text_vbox, 1)

        layout.addLayout(header)
        return card

    # ------------------ EVENT HANDLERS & LOGIC ------------------
    def switch_page(self, index: int):
        self.stacked_widget.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            if i == index:
                btn.setProperty("class", "nav-btn-active")
                btn.setStyleSheet("background-color: #2F8F5B; color: #ffffff; font-weight: bold; border-radius: 10px;")
            else:
                btn.setProperty("class", "nav-btn")
                btn.setStyleSheet("background-color: transparent; border-radius: 10px;")

        # Update backup page selector if switching there
        if index == 5:
            self._update_backup_page_dropdown()

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        if hasattr(self, "btn_max"):
            self.btn_max.set_maximized_state(self.isMaximized())

    def changeEvent(self, event):
        if event.type() == event.Type.WindowStateChange:
            if hasattr(self, "btn_max"):
                self.btn_max.set_maximized_state(self.isMaximized())
        super().changeEvent(event)

    def _toggle_bink(self):
        self.use_bink = not self.use_bink
        self.btn_bink_toggle.setText(f"⚙️ Bink2 链式劫持: {'【已启用】' if self.use_bink else '【已禁用】'} →")

    def _on_backend_dropdown_changed(self, index: int = 0):
        data = self.combo_backend.currentData()
        backend_str = data.value if hasattr(data, "value") else str(data)
        has_reshade = bool(self.selected_game and self.selected_game.has_reshade)

        if backend_str in [BackendType.STANDALONE.value, "dashdogy"]:
            self.lbl_backend_desc.setText("模式 A (dashdogy): 零外部依赖，使用 version.dll / winmm.dll 代理注入，按 Backspace 呼出菜单")
            self.lbl_backend_desc.setStyleSheet("font-size: 11px; color: #2F8F5B;")
            if hasattr(self, "lbl_rhi_desc_hint"):
                self.lbl_rhi_desc_hint.setText("当前为模式 A (无需底座) · 可在此打开 RHI 安装画质滤镜或管理模组")
        elif backend_str in [BackendType.RESHADE_ADDON.value, "mavismmg"]:
            if self.selected_game and self.selected_game.target_dir:
                v_ok, v_msg, v_stat = self.patcher.verify_mode_b_integrity(self.selected_game.target_dir)
                if v_ok:
                    self.lbl_backend_desc.setText("模式 B (mavismmg): 🟢 已就绪 (ReShade 框架 + 插件双就绪 · 按 Home 键呼出)")
                    self.lbl_backend_desc.setStyleSheet("font-size: 11px; color: #16a34a; font-weight: bold;")
                elif v_stat.get("has_addon") and not v_stat.get("has_dxgi"):
                    self.lbl_backend_desc.setText("模式 B (mavismmg): ⚠️ 缺失 dxgi.dll 底座，点击【应用】将自动为您补齐注入！")
                    self.lbl_backend_desc.setStyleSheet("font-size: 11px; color: #d97706; font-weight: bold;")
                else:
                    self.lbl_backend_desc.setText("模式 B (mavismmg): 内置完整 ReShade 6.8 框架 + RenoDX 插件，点击应用一键自动注入 (无需手动安装)")
                    self.lbl_backend_desc.setStyleSheet("font-size: 11px; color: #7e22ce; font-weight: 600;")
            else:
                self.lbl_backend_desc.setText("模式 B (mavismmg): 内置完整 ReShade 6.8 框架 + RenoDX 插件，点击应用一键自动注入 (按 Home 调校)")
                self.lbl_backend_desc.setStyleSheet("font-size: 11px; color: #7e22ce; font-weight: 600;")

            if hasattr(self, "lbl_rhi_desc_hint"):
                self.lbl_rhi_desc_hint.setText("⚡ 模式 B 已内置全套框架与插件 · 可在此打开 RHI 安装其他 HDR 画面滤镜")
        elif backend_str in [BackendType.OPTISCALER_FSR.value, "optiscaler"]:
            self.lbl_backend_desc.setText("模式 C (OptiScaler / FSR 3.1): 专为 RTX 20/30 系及全显卡设计，将 DLSS 3 转译为 FSR 3.1 帧生成，参数由工具箱全自动托管")
            self.lbl_backend_desc.setStyleSheet("font-size: 11px; color: #ea580c; font-weight: 600;")
            if hasattr(self, "lbl_rhi_desc_hint"):
                self.lbl_rhi_desc_hint.setText("当前为模式 C 跨卡转译 · 可使用 RHI 管理 HDR 与高级着色器生态")
        else:
            gpu_name = get_system_gpu_name()
            if not is_rtx_40_or_newer(gpu_name):
                self.lbl_backend_desc.setText(f"智能推荐 ({gpu_name}): 检测为 RTX 20/30 系或非 40/50 显卡，将自动应用模式 C (OptiScaler/FSR 3.1)")
                self.lbl_backend_desc.setStyleSheet("font-size: 11px; color: #ea580c;")
                if hasattr(self, "lbl_rhi_desc_hint"):
                    self.lbl_rhi_desc_hint.setText("智能模式推荐 C · 可点击右侧打开 RHI 模组生态助手")
            else:
                self.lbl_backend_desc.setText(f"智能推荐 ({gpu_name}): 发现 40/50 系显卡，将自动应用高画质模式 B (ReShade 6.8 + RenoDX 一键完整注入)")
                self.lbl_backend_desc.setStyleSheet("font-size: 11px; color: #16a34a;")
                if hasattr(self, "lbl_rhi_desc_hint"):
                    self.lbl_rhi_desc_hint.setText("✅ 智能模式匹配高画质模式 B · 内置完整 ReShade 框架与 RenoDX 插件")

    def on_show_guide_click(self):
        backend = self.combo_backend.currentData()
        backend_str = backend.value if hasattr(backend, "value") else str(backend)
        initial_tab = 0  # default: Mode A
        if backend_str in [BackendType.OPTISCALER_FSR.value, "optiscaler"]:
            initial_tab = 2
        elif backend_str in [BackendType.RESHADE_ADDON.value, "mavismmg"]:
            initial_tab = 1
        elif backend_str in [BackendType.STANDALONE.value, "dashdogy"]:
            initial_tab = 0
        dlg = ModernTranslationGuideDialog(self, is_dark=self.is_dark_mode, initial_tab=initial_tab)
        dlg.exec()

    def _update_preset_summary(self):
        try:
            summary_a = get_mode_a_preset_summary()
            summary_b = get_reshade_preset_summary()
            summary_c = get_preset_summary()
            if hasattr(self, "lbl_preset_summary"):
                self.lbl_preset_summary.setText(f"📦 模式A: {summary_a} | 🎨 模式B: {summary_b}\n⚡ 模式C: {summary_c}")
        except Exception:
            pass

    def _update_entry_cards_style(self):
        is_dark = self.is_dark_mode
        if is_dark:
            bink_qss = """
                QFrame#CardBink {
                    background-color: #2A2B2C;
                    border: 1px solid #3A3A3A;
                    border-radius: 11px;
                    min-height: 42px;
                }
                QFrame#CardBink:hover {
                    background-color: #343434;
                    border: 1px solid #4A4A4A;
                }
            """
            guide_qss = """
                QFrame#CardGuide {
                    background-color: #2A2B2C;
                    border: 1px solid #3A3A3A;
                    border-radius: 11px;
                    min-height: 42px;
                }
                QFrame#CardGuide:hover {
                    background-color: #343434;
                    border: 1px solid #4A4A4A;
                }
            """
            preset_qss = """
                QFrame#CardPreset {
                    background-color: #2A2B2C;
                    border: 1px solid #3A3A3A;
                    border-radius: 11px;
                    min-height: 52px;
                }
                QFrame#CardPreset:hover {
                    background-color: #343434;
                    border: 1px solid #4A4A4A;
                }
            """
            btn_bink_qss = "QPushButton { background: transparent; color: #A0A0A0; border: none; font-size: 12px; font-weight: bold; text-align: left; padding: 6px 8px; border-radius: 8px; } QPushButton:hover { background-color: #3A3A3A; color: #E8E8E8; } QPushButton:pressed { background-color: #444444; }"
            btn_guide_qss = "QPushButton { background: transparent; color: #A0A0A0; border: none; font-size: 12px; font-weight: bold; text-align: left; padding: 6px 8px; border-radius: 8px; } QPushButton:hover { background-color: #3A3A3A; color: #E8E8E8; } QPushButton:pressed { background-color: #444444; }"
            btn_preset_qss = "QPushButton { background: transparent; color: #A0A0A0; border: none; font-size: 12px; font-weight: bold; text-align: left; padding: 6px 8px; border-radius: 8px; } QPushButton:hover { background-color: #3A3A3A; color: #E8E8E8; } QPushButton:pressed { background-color: #444444; }"
            lbl_summary_col = "#A0A0A0"
            info_qss = """
                QFrame#CardGameInfo {
                    background-color: #2A2B2C;
                    border: 1px solid #3A3A3A;
                    border-radius: 10px;
                }
            """
            btn_pick_qss = """
                QPushButton#BtnPickExe, QPushButton#BtnPickDir {
                    background-color: #2A2B2C;
                    color: #A7F3D0;
                    border: 1px solid #3A3A3A;
                    border-radius: 8px;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 6px 10px;
                }
                QPushButton#BtnPickExe:hover, QPushButton#BtnPickDir:hover {
                    background-color: #2F8F5B;
                    color: #ffffff;
                    border: 1px solid #3E9E69;
                }
            """
            btn_rescan_qss = """
                QPushButton#BtnRescanHeader {
                    background-color: #2A2B2C;
                    color: #7ED9A2;
                    border: 1px solid #3A3A3A;
                    border-radius: 6px;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 2px 10px;
                }
                QPushButton#BtnRescanHeader:hover {
                    background-color: #2F8F5B;
                    color: #ffffff;
                    border: 1px solid #3E9E69;
                }
            """
            btn_open_dir_qss = """
                QPushButton {
                    background-color: #3A3A3A;
                    color: #D4D4D4;
                    border: 1px solid #4A4A4A;
                    border-radius: 5px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #4A4A4A;
                    color: #ffffff;
                }
            """
            badge_game_qss = """
                background-color: #303132;
                color: #8AB4F8;
                border-radius: 10px;
                font-size: 18px;
                font-weight: 800;
                qproperty-alignment: AlignCenter;
                border: 1px solid #3A3A3A;
            """
            path_lbl_color = "#E8E8E8"
            title_lbl_color = "#A0A0A0"
        else:
            bink_qss = """
                QFrame#CardBink {
                    background-color: #FFFFFF;
                    border: 1px solid #E5E5E5;
                    border-radius: 11px;
                    min-height: 42px;
                }
                QFrame#CardBink:hover {
                    background-color: #EFEFEF;
                    border: 1px solid #D4D4D4;
                }
            """
            guide_qss = """
                QFrame#CardGuide {
                    background-color: #FFFFFF;
                    border: 1px solid #E5E5E5;
                    border-radius: 11px;
                    min-height: 42px;
                }
                QFrame#CardGuide:hover {
                    background-color: #EFEFEF;
                    border: 1px solid #D4D4D4;
                }
            """
            preset_qss = """
                QFrame#CardPreset {
                    background-color: #FFFFFF;
                    border: 1px solid #E5E5E5;
                    border-radius: 11px;
                    min-height: 52px;
                }
                QFrame#CardPreset:hover {
                    background-color: #EFEFEF;
                    border: 1px solid #D4D4D4;
                }
            """
            btn_bink_qss = "QPushButton { background: transparent; color: #5A5A5A; border: none; font-size: 12px; font-weight: bold; text-align: left; padding: 6px 8px; border-radius: 8px; } QPushButton:hover { background-color: #E8E8E8; color: #1A1A1A; } QPushButton:pressed { background-color: #DCDCDC; }"
            btn_guide_qss = "QPushButton { background: transparent; color: #5A5A5A; border: none; font-size: 12px; font-weight: bold; text-align: left; padding: 6px 8px; border-radius: 8px; } QPushButton:hover { background-color: #E8E8E8; color: #1A1A1A; } QPushButton:pressed { background-color: #DCDCDC; }"
            btn_preset_qss = "QPushButton { background: transparent; color: #5A5A5A; border: none; font-size: 12px; font-weight: bold; text-align: left; padding: 6px 8px; border-radius: 8px; } QPushButton:hover { background-color: #E8E8E8; color: #1A1A1A; } QPushButton:pressed { background-color: #DCDCDC; }"
            lbl_summary_col = "#5A5A5A"
            info_qss = """
                QFrame#CardGameInfo {
                    background-color: #F5F5F5;
                    border: 1px solid #E5E5E5;
                    border-radius: 10px;
                }
            """
            btn_pick_qss = """
                QPushButton#BtnPickExe, QPushButton#BtnPickDir {
                    background-color: #EFEFEF;
                    color: #26784C;
                    border: 1px solid #D4D4D4;
                    border-radius: 8px;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 6px 10px;
                }
                QPushButton#BtnPickExe:hover, QPushButton#BtnPickDir:hover {
                    background-color: #E8E8E8;
                    color: #1e40af;
                    border: 1px solid #A7F3D0;
                }
            """
            btn_rescan_qss = """
                QPushButton#BtnRescanHeader {
                    background-color: #F5F5F5;
                    color: #26784C;
                    border: 1px solid #D4D4D4;
                    border-radius: 6px;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 2px 10px;
                }
                QPushButton#BtnRescanHeader:hover {
                    background-color: #E8E8E8;
                    color: #1e40af;
                    border: 1px solid #3E9E69;
                }
            """
            btn_open_dir_qss = """
                QPushButton {
                    background-color: #E5E5E5;
                    color: #3A3A3A;
                    border: 1px solid #D4D4D4;
                    border-radius: 5px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #D4D4D4;
                    color: #292929;
                }
            """
            badge_game_qss = """
                background-color: #EFEFEF;
                color: #2F8F5B;
                border-radius: 10px;
                font-size: 18px;
                font-weight: 800;
                qproperty-alignment: AlignCenter;
                border: 1px solid #E5E5E5;
            """
            path_lbl_color = "#3A3A3A"
            title_lbl_color = "#8A8A8A"

        if hasattr(self, "card_bink"):
            self.card_bink.setStyleSheet(bink_qss)
        if hasattr(self, "card_guide"):
            self.card_guide.setStyleSheet(guide_qss)
        if hasattr(self, "card_preset"):
            self.card_preset.setStyleSheet(preset_qss)
        if hasattr(self, "btn_bink_toggle"):
            self.btn_bink_toggle.setStyleSheet(btn_bink_qss)
        if hasattr(self, "btn_show_guide"):
            self.btn_show_guide.setStyleSheet(btn_guide_qss)
        if hasattr(self, "btn_preset_cfg"):
            self.btn_preset_cfg.setStyleSheet(btn_preset_qss)
        if hasattr(self, "lbl_preset_summary"):
            self.lbl_preset_summary.setStyleSheet(f"font-size: 11px; color: {lbl_summary_col}; line-height: 1.3;")

        if hasattr(self, "card_game_info"):
            self.card_game_info.setStyleSheet(info_qss)
        if hasattr(self, "btn_pick_exe"):
            self.btn_pick_exe.setStyleSheet(btn_pick_qss)
        if hasattr(self, "btn_pick_dir"):
            self.btn_pick_dir.setStyleSheet(btn_pick_qss)
        if hasattr(self, "btn_rescan_header"):
            self.btn_rescan_header.setStyleSheet(btn_rescan_qss)
        if hasattr(self, "btn_open_game_dir"):
            self.btn_open_game_dir.setStyleSheet(btn_open_dir_qss)
        if hasattr(self, "badge_game"):
            self.badge_game.setStyleSheet(badge_game_qss)
        if hasattr(self, "lbl_game_path"):
            self.lbl_game_path.setStyleSheet(f"font-size: 11px; color: {path_lbl_color}; line-height: 1.3;")
        if hasattr(self, "card_game_info"):
            for title_lbl in self.card_game_info.findChildren(QLabel, "InfoRowTitle"):
                title_lbl.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {title_lbl_color};")
        if hasattr(self, "selected_game") and self.selected_game and hasattr(self, "lbl_info_patch"):
            patch_text, patch_color = self._format_game_patch_status(self.selected_game)
            self.lbl_info_patch.setText(patch_text)
            self.lbl_info_patch.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {patch_color};")

        # Neutral DM-style RHI banner + GPU badge (no rainbow gradients)
        if hasattr(self, "rhi_banner") and hasattr(self, "lbl_rhi_t"):
            if is_dark:
                self.rhi_banner.setStyleSheet(
                    "QFrame#RHIBanner { background-color: #2A2B2C; border: 1px solid #3A3A3A; border-radius: 10px; }"
                )
                self.lbl_rhi_t.setStyleSheet("font-size: 13px; font-weight: bold; color: #E8E8E8; background: transparent; border: none;")
                self.lbl_rhi_desc_hint.setStyleSheet("font-size: 11px; color: #A0A0A0; background: transparent; border: none;")
                self.btn_launch_rhi_quick.setStyleSheet(
                    "QPushButton { background-color: #8FE3B0; color: #10231A; border: none; border-radius: 6px; padding: 7px 14px; font-size: 12px; font-weight: 800; }"
                    "QPushButton:hover { background-color: #7ED9A2; }"
                )
            else:
                self.rhi_banner.setStyleSheet(
                    "QFrame#RHIBanner { background-color: #FFFFFF; border: 1px solid #E5E5E5; border-radius: 10px; }"
                )
                self.lbl_rhi_t.setStyleSheet("font-size: 13px; font-weight: bold; color: #1A1A1A; background: transparent; border: none;")
                self.lbl_rhi_desc_hint.setStyleSheet("font-size: 11px; color: #8A8A8A; background: transparent; border: none;")
                self.btn_launch_rhi_quick.setStyleSheet(
                    "QPushButton { background-color: #8FE3B0; color: #10231A; border: none; border-radius: 6px; padding: 7px 14px; font-size: 12px; font-weight: 800; }"
                    "QPushButton:hover { background-color: #7ED9A2; }"
                )
        if hasattr(self, "badge_mfg"):
            if is_dark:
                self.badge_mfg.setStyleSheet(
                    "background-color: #303132; color: #8FE3B0; font-size: 12px; font-weight: bold;"
                    " border-radius: 12px; padding: 8px 16px; qproperty-alignment: AlignCenter; border: 1px solid #3A3A3A;"
                )
            else:
                self.badge_mfg.setStyleSheet(
                    "background-color: #EFEFEF; color: #2F8F5B; font-size: 12px; font-weight: bold;"
                    " border-radius: 12px; padding: 8px 16px; qproperty-alignment: AlignCenter; border: 1px solid #E5E5E5;"
                )

    def _update_ini_watcher_target(self):
        """Update file system watcher to track the selected game's directory and INI files."""
        try:
            watched_files = self._ini_watcher.files()
            if watched_files:
                self._ini_watcher.removePaths(watched_files)
            watched_dirs = self._ini_watcher.directories()
            if watched_dirs:
                self._ini_watcher.removePaths(watched_dirs)
        except Exception:
            pass

        if not self.selected_game or not self.selected_game.target_dir:
            return

        target_dir = Path(self.selected_game.target_dir)
        if not target_dir.exists():
            return

        # Watch the directory itself (to detect new INI creation by game)
        try:
            self._ini_watcher.addPath(str(target_dir))
        except Exception:
            pass

        # Watch target INI files if they exist
        ini_candidates = [
            "OptiScaler.ini",
            "nvngx.ini",
            "ReShade.ini",
            "RTXMFG-UI.ini",
            "mfg_unlocker.ini"
        ]
        for name in ini_candidates:
            ini_p = target_dir / name
            if ini_p.exists():
                try:
                    self._ini_watcher.addPath(str(ini_p))
                except Exception:
                    pass

    def _on_ini_file_changed(self, path: str):
        if self._suppress_sync:
            return
        self._debounce_timer.start(400)

    def _on_ini_dir_changed(self, path: str):
        if self._suppress_sync:
            return
        self._update_ini_watcher_target()
        self._debounce_timer.start(400)

    def _on_ini_debounce_timeout(self):
        self._check_and_sync_from_game_ini(silent=False)

    def _check_and_sync_from_game_ini(self, silent: bool = False):
        if self._suppress_sync or not self.selected_game or not self.selected_game.target_dir:
            return

        target_dir = Path(self.selected_game.target_dir)
        if not target_dir.exists():
            return

        changed_any = False
        feedback_messages = []

        # 0. Reverse sync Mode A (RTXMFG-UI.ini / mfg_unlocker.ini)
        mode_a_data = IniConfigManager.read_mode_a_reverse(target_dir)
        if mode_a_data:
            cur_a = load_mode_a_preset()
            diff_a = {k: v for k, v in mode_a_data.items() if cur_a.get(k) != v}
            if diff_a:
                cur_a.update(diff_a)
                save_mode_a_preset(cur_a)
                changed_any = True
                feedback_messages.append(f"dashdogy [{get_mode_a_preset_summary(cur_a)}]")

        # 1. Reverse sync Mode C (OptiScaler.ini / nvngx.ini)
        mode_c_data = IniConfigManager.read_mode_c_reverse(target_dir)
        if mode_c_data:
            cur_preset = load_optiscaler_preset()
            diff_c = {k: v for k, v in mode_c_data.items() if cur_preset.get(k) != v}
            # 防止单个旧游戏的局部反向同步将全局默认超分错误污染为 "xess"
            if "dx12_upscaler" in diff_c and diff_c["dx12_upscaler"] in ("xess", "dlss") and not cur_preset.get("user_customized_upscaler", False):
                diff_c.pop("dx12_upscaler", None)
            if diff_c:
                cur_preset.update(diff_c)
                save_optiscaler_preset(cur_preset)
                changed_any = True
                feedback_messages.append(f"OptiScaler [{get_preset_summary(cur_preset)}]")

        # 2. Reverse sync Mode B (ReShade.ini)
        mode_b_data = IniConfigManager.read_mode_b_reverse(target_dir)
        if mode_b_data:
            cur_b = load_reshade_preset()
            diff_b = {k: v for k, v in mode_b_data.items() if cur_b.get(k) != v}
            if diff_b:
                cur_b.update(diff_b)
                save_reshade_preset(cur_b)
                changed_any = True
                feedback_messages.append(f"RenoDX [{get_reshade_preset_summary(cur_b)}]")

        if changed_any:
            self._update_preset_summary()
            details = " · ".join(feedback_messages)
            if not silent:
                if hasattr(self, "top_alert"):
                    self.top_alert.setText(f"🔄 检测到游戏内配置已变更，工具箱已实时自动同步！({details})")
                if hasattr(self, "lbl_status"):
                    self.lbl_status.setText(f"● 双向同步: 已自动同步游戏内改动 ({details})")

    def on_open_preset_config_dialog(self):
        dlg = OptiScalerPresetDialog(self, is_dark=self.is_dark_mode, game=self.selected_game)
        if dlg.exec():
            # Temporarily suppress reverse sync while forward sync writes settle
            self._suppress_sync = True
            QTimer.singleShot(800, lambda: setattr(self, "_suppress_sync", False))

            self._update_preset_summary()
            self._update_ini_watcher_target()

            game_sync_note = ""
            if self.selected_game:
                game_sync_note = f"\n\n【双向同步执行成功】\n✅ 已直接同步更新目标游戏目录: {self.selected_game.name}\n({self.selected_game.target_dir})"

            ModernDialog.info(
                self,
                "多帧生成配置已保存并同步",
                f"预设参数已成功更新！\n\n【模式 A (dashdogy 独立代理)】\n{get_mode_a_preset_summary()}\n\n【模式 B (RenoDX ReShade)】\n{get_reshade_preset_summary()}\n\n【模式 C (OptiScaler/XeSS)】\n{get_preset_summary()}{game_sync_note}\n\n【运行时生效说明】\n• 游戏未运行时：进游戏开启【DLSS 帧生成】即直接生效。\n• 游戏运行中修改：部分底层图形 DLL 仅在启动时读取一次 ini，若游戏内未自动刷新，可在游戏内按 Insert/Home 重载或重启游戏即可生效！",
                self.is_dark_mode
            )

    def on_quick_launch_rhi_for_game(self):
        dlg = ModernRHIGuideDialog(
            self,
            game_info=self.selected_game,
            rhi_installer=self.rhi,
            is_dark=self.is_dark_mode
        )
        dlg.exec()

    def _load_cache_status(self):
        reg = self.updater.load_registry()
        dash_tag = reg.get(BackendType.STANDALONE.value, {}).get("latest_tag", "未下载")
        mavis_tag = reg.get(BackendType.RESHADE_ADDON.value, {}).get("latest_tag", "未下载")
        opti_tag = reg.get(BackendType.OPTISCALER_FSR.value, {}).get("latest_tag", "未下载")
        size_mb = self.updater.get_cache_size_bytes() / (1024 * 1024)

        self.lbl_cache_summary.setText(f"本地缓存: dashdogy [{dash_tag}] | mavismmg [{mavis_tag}] | OptiScaler [{opti_tag}] (占用: {size_mb:.2f} MB)")
        self.lbl_side_ver.setText(f"当前版本: {dash_tag}")

        rhi_found, rhi_path = self.rhi.is_installed_or_cached()
        rhi_str = f"已就绪 ({os.path.basename(rhi_path)})" if rhi_found else "未下载"

        cache_dir_display = str(self.updater.cache_dir)
        self.lbl_cache_detailed.setText(
            f"📁 缓存存储路径: {cache_dir_display}\n"
            f"💾 缓存占用空间: {size_mb:.2f} MB （安全存放于系统 AppData，不在软件根目录）\n\n"
            f"• dashdogy/MFG-Unlocker (Standalone): {dash_tag}\n"
            f"• mavismmg/MFGAdaUnlock-RenoDx (Addon): {mavis_tag}\n"
            f"• optiscaler/OptiScaler (FSR 3.1 Bridge): {opti_tag}\n"
            f"• RankFTW/RHI 模组工具: {rhi_str}"
        )

    def on_open_cache_dir_click(self):
        cache_dir = str(self.updater.cache_dir)
        if os.path.exists(cache_dir):
            try:
                os.startfile(cache_dir)
            except Exception as e:
                ModernDialog.error(self, "打开文件夹失败", str(e), self.is_dark_mode)
        else:
            ModernDialog.warning(self, "提示", "缓存目录尚不存在！", self.is_dark_mode)

    def on_clear_cache_click(self):
        size_mb = self.updater.get_cache_size_bytes() / (1024 * 1024)
        confirm = ModernDialog.confirm(
            self,
            "清空/删除缓存确认",
            f"确定要彻底删除本地下载的全部组件缓存吗？\n\n"
            f"• 缓存目录: {self.updater.cache_dir}\n"
            f"• 将释放空间: 约 {size_mb:.2f} MB\n\n"
            f"清空后软件将恢复初始无缓存状态。后续修补前可随时点击【检查并同步最新版本】重新下载。",
            self.is_dark_mode
        )
        if not confirm:
            return

        ok, msg, freed = self.updater.clear_cache()
        if ok:
            ModernDialog.success(self, "清空缓存成功", msg, self.is_dark_mode)
            self._load_cache_status()
            self._refresh_rhi_display()
        else:
            ModernDialog.error(self, "清空缓存失败", msg, self.is_dark_mode)

    def _refresh_rhi_display(self):
        found, path = self.rhi.is_installed_or_cached()
        is_manual = self.rhi.is_manual_path()
        if hasattr(self, "btn_reset_rhi"):
            self.btn_reset_rhi.setEnabled(is_manual)

        if found:
            if hasattr(self, "line_rhi_path"):
                self.line_rhi_path.setText(path)

            if is_manual:
                self.lbl_rhi_status.setText(f"● 已配置手动指定 RHI 路径: {path}")
                self.lbl_rhi_status.setStyleSheet("font-size: 13px; font-weight: bold; color: #2F8F5B;")
            else:
                is_setup = "setup" in os.path.basename(path).lower()
                tag_name = "安装包" if is_setup else "已安装主程序"
                self.lbl_rhi_status.setText(f"● 系统自动检测就绪 ({tag_name}): {path}")
                self.lbl_rhi_status.setStyleSheet("font-size: 13px; font-weight: bold; color: #16a34a;")

            self.btn_launch_rhi.setEnabled(True)
            self.btn_download_rhi.setText("☁️ 重新下载 / 更新安装包")
        else:
            if hasattr(self, "line_rhi_path"):
                self.line_rhi_path.setText("")
            self.lbl_rhi_status.setText("● 未检测到 RHI (可点击上方手动指定路径，或点击下方自动下载)")
            self.lbl_rhi_status.setStyleSheet("font-size: 13px; font-weight: bold; color: #d97706;")
            self.btn_launch_rhi.setEnabled(False)
            self.btn_download_rhi.setText("☁️ 下载最新 RHI 安装包 (带 Addon 支持)")

        if hasattr(self, "lbl_rhi_eco_status"):
            if not self.selected_game:
                self.lbl_rhi_eco_status.setText("请在主界面或游戏库中选择一款目标游戏，以查看其 ReShade 框架与 Addon 模组状态。")
            else:
                g = self.selected_game
                target_dir = g.target_dir
                dxgi_p = os.path.join(target_dir, "dxgi.dll") if target_dir else ""
                has_dxgi = os.path.exists(dxgi_p)
                is_reshade = self.patcher._is_reshade_addon_dll(dxgi_p) if has_dxgi else False

                addons_found = []
                if target_dir and os.path.exists(target_dir):
                    try:
                        for f in os.listdir(target_dir):
                            lf = f.lower()
                            if lf.endswith(".addon64") or lf.endswith(".addon"):
                                addons_found.append(f)
                    except Exception:
                        pass

                if is_reshade:
                    reshade_stat_str = "<span style='color: #16a34a; font-weight: bold;'>✅ 已安装 (ReShade64 with Full Add-on Support)</span>"
                elif has_dxgi:
                    reshade_stat_str = "<span style='color: #d97706; font-weight: bold;'>⚠️ 已存在 dxgi.dll (非官方 Addon 版或被占用)</span>"
                else:
                    reshade_stat_str = "<span style='color: #64748b;'>❌ 未安装 (可在本工具箱启用【模式 B】自动注入，或通过 RHI 部署)</span>"

                if addons_found:
                    formatted_addons = []
                    for a in addons_found:
                        if a.lower() == "renodx-mfgunlock.addon64":
                            formatted_addons.append(f"<span style='color: #7e22ce; font-weight: bold;'>{a} (多帧生成核心插件)</span>")
                        elif "hdr" in a.lower() or "renodx" in a.lower():
                            formatted_addons.append(f"<span style='color: #2F8F5B; font-weight: bold;'>{a} (HDR 画面模组)</span>")
                        else:
                            formatted_addons.append(f"<span>{a}</span>")
                    addons_str = ", ".join(formatted_addons)
                else:
                    addons_str = "<span style='color: #64748b;'>未检测到任何 .addon64 模组</span>"

                coexist_tip = (
                    "🛡️ <b>智能模组共存保护机制：</b><br>"
                    "• 本工具箱与 RHI 模组生态完全兼容无冲突。<br>"
                    "• 启用【模式 B】时，会自动同时注入 ReShade 6.8 框架与插帧插件。<br>"
                    "• 卸载【模式 B】时，若检测到您还安装了其他 Addon（如 HDR 模组），将<b>严格保留 ReShade 框架</b>，绝不破坏您的其他模组！"
                )

                self.lbl_rhi_eco_status.setText(
                    f"🎮 <b>目标游戏：</b> <b>{g.name}</b> ({g.source})<br>"
                    f"📁 <b>程序目录：</b> <code>{target_dir}</code><br>"
                    f"🔌 <b>ReShade 框架：</b> {reshade_stat_str}<br>"
                    f"📦 <b>已安装插件 ({len(addons_found)} 个)：</b> {addons_str}<br><br>"
                    f"{coexist_tip}"
                )

    def on_browse_rhi_click(self):
        """Allow user to manually locate and select RHI.exe or RHI-Setup.exe."""
        from PySide6.QtWidgets import QFileDialog
        curr_path = self.line_rhi_path.text() if hasattr(self, "line_rhi_path") else ""
        initial_dir = os.path.dirname(curr_path) if curr_path and os.path.exists(curr_path) else r"C:\Program Files"
        if not os.path.exists(initial_dir):
            initial_dir = ""

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "手动选择 RHI 可执行程序",
            initial_dir,
            "RHI 可执行文件 (*.exe);;所有文件 (*.*)"
        )
        if file_path and os.path.exists(file_path):
            self.rhi.set_manual_path(file_path)
            self._refresh_rhi_display()
            ModernDialog.success(
                self,
                "指定成功",
                f"已成功将 RHI 目标程序手动指定为:\n{file_path}\n\n该配置已保存至本地配置，后续启动将优先使用此路径。",
                self.is_dark_mode
            )

    def on_reset_rhi_click(self):
        """Reset manual override back to automatic system detection."""
        self.rhi.clear_manual_path()
        self._refresh_rhi_display()
        ModernDialog.info(
            self,
            "重置成功",
            "已清除手动指定的 RHI 路径，已恢复为 Windows 系统与注册表自动侦测模式。",
            self.is_dark_mode
        )

    def on_download_rhi_click(self):
        mirror = self.combo_mirror.currentText()
        mirror_prefix = DEFAULT_MIRRORS.get(mirror, "")
        self.lbl_status.setText("● 正在下载 RHI-Setup.exe...")

        progress_dlg = ModernProgressDialog(
            self,
            title="下载 RHI 运行时工具包",
            description="正在连接 GitHub 与云端镜像节点...",
            is_dark=self.is_dark_mode,
            cancelable=True
        )
        progress_dlg.set_indeterminate("正在解析 RHI 最新版本资产...", f"镜像节点: {mirror}")
        self._active_progress_dlg = progress_dlg

        def dl_progress(downloaded, total):
            if total > 0:
                pct = int(min(100, (downloaded / total) * 100))
                detail = f"{downloaded / 1024 / 1024:.2f} MB / {total / 1024 / 1024:.2f} MB ({pct}%)"
            else:
                pct = 50
                detail = f"已下载: {downloaded / 1024 / 1024:.2f} MB"
            self.signals.progress_updated.emit(pct, "正在下载 RHI-Setup.exe...", detail)

        def dl_thread():
            ok, msg = self.rhi.download_rhi(mirror_prefix, progress_cb=dl_progress)
            self.signals.rhi_finished.emit(ok, msg)

        threading.Thread(target=dl_thread, daemon=True).start()
        progress_dlg.show()

    def _on_rhi_finished(self, ok: bool, msg: str):
        self._refresh_rhi_display()
        self.lbl_status.setText("● 就绪")
        if self._active_progress_dlg:
            self._active_progress_dlg.finish(
                ok,
                "RHI 工具包下载成功！" if ok else "RHI 下载遇到问题",
                msg,
                auto_close_delay_ms=0
            )
            self._active_progress_dlg = None
        else:
            if ok:
                ModernDialog.success(self, "RHI 下载成功", msg, self.is_dark_mode)
            else:
                ModernDialog.error(self, "RHI 下载失败", msg, self.is_dark_mode)

    def on_launch_rhi_click(self):
        ok, msg = self.rhi.launch_rhi()
        if ok:
            ModernDialog.info(self, "启动 RHI", msg, self.is_dark_mode)
        else:
            ModernDialog.error(self, "启动失败", msg, self.is_dark_mode)

    def _load_cached_games_instant(self):
        """Cache-First Instant Startup: Restore games and last selected game from local cache in 0ms."""
        try:
            cached_games, last_exe = GameCacheManager.get_cached_games()
            if cached_games:
                self.games = cached_games
                self.combo_games.blockSignals(True)
                self.combo_games.clear()
                target_idx = 0
                for idx, g in enumerate(self.games):
                    prefix = "✅ " if g.qualification == QualificationStatus.QUALIFIED else (
                        "⚠️ " if g.qualification == QualificationStatus.MISSING_DLSSG else "❌ "
                    )
                    patch_tag = f" [已修补-{g.patched_backend}]" if g.is_patched else ""
                    self.combo_games.addItem(f"{prefix}{g.name} ({g.source}){patch_tag}", g)
                    if last_exe and g.exe_path.lower() == last_exe.lower():
                        target_idx = idx

                self.combo_games.blockSignals(False)
                if self.games:
                    self.combo_games.setCurrentIndex(target_idx)
                    self._on_game_dropdown_changed(target_idx)

                self._populate_library_table()
                self._update_backup_page_dropdown()
                self.lbl_status.setText(f"● 缓存就绪: 已秒开载入 {len(self.games)} 款游戏历史 (正在后台静默检查更新...)")
            else:
                self.combo_games.blockSignals(True)
                self.combo_games.clear()
                self.combo_games.addItem("🔍 正在扫描本地游戏库...", None)
                self.combo_games.blockSignals(False)
                if hasattr(self, "lbl_game_path"):
                    self.lbl_game_path.setText("正在检索系统游戏库...")
                if hasattr(self, "lbl_info_arch"):
                    self.lbl_info_arch.setText("检测中...")
                if hasattr(self, "lbl_info_patch"):
                    self.lbl_info_patch.setText("检测中...")
        except Exception:
            pass

    def trigger_background_scan(self):
        if hasattr(self, "btn_rescan_header"):
            self.btn_rescan_header.setText("⏳ 正在刷新...")
            self.btn_rescan_header.setEnabled(False)
        self.lbl_status.setText("● 正在检索系统游戏库 (Steam, Epic, GOG, WeGame 及本地游戏)...")

        def scan_thread():
            games = self.scanner.scan_all_libraries()
            self.signals.scan_finished.emit(games)
        threading.Thread(target=scan_thread, daemon=True).start()

    def _on_scan_finished(self, games: List[GameInfo]):
        if hasattr(self, "btn_rescan_header"):
            self.btn_rescan_header.setText("🔄 刷新库")
            self.btn_rescan_header.setEnabled(True)

        # 1. Retrieve custom games from cache
        cache = GameCacheManager.load_cache()
        custom_games_raw = cache.get("custom_added_games", [])
        custom_games = []
        seen_paths = set()
        for item in custom_games_raw:
            try:
                cg = GameInfo.from_dict(item)
                norm = cg.exe_path.lower()
                if norm not in seen_paths:
                    seen_paths.add(norm)
                    custom_games.append(cg)
            except Exception:
                pass

        # Also preserve any custom games in self.games not yet persisted
        for g in self.games:
            if g.source in ["手动自定义", "Custom"] and g.exe_path.lower() not in seen_paths:
                seen_paths.add(g.exe_path.lower())
                custom_games.append(g)

        # Refresh volatile fields of custom entries from the freshly scanned copy.
        # Without this a custom game kept its old "已修补-optiscaler" flag forever.
        scanned_by_exe = {sg.exe_path.lower(): sg for sg in games if sg.exe_path}
        for cg in custom_games:
            sg = scanned_by_exe.get(cg.exe_path.lower())
            if not sg:
                continue
            cg.qualification = sg.qualification
            cg.streamline_ver = sg.streamline_ver
            cg.dlssg_ver = sg.dlssg_ver
            cg.has_reshade = sg.has_reshade
            cg.is_patched = sg.is_patched
            cg.patched_backend = sg.patched_backend
            cg.installed_version = sg.installed_version

        # 2. Merge custom games and scanned games
        merged_games: List[GameInfo] = list(custom_games)
        for sg in games:
            norm = sg.exe_path.lower()
            if norm not in seen_paths:
                seen_paths.add(norm)
                merged_games.append(sg)

        # 3. Save merged list to persistent cache
        curr_exe = self.selected_game.exe_path if self.selected_game else None
        if not curr_exe and merged_games:
            curr_exe = merged_games[0].exe_path

        GameCacheManager.save_cache(
            last_selected_exe=curr_exe,
            custom_games=custom_games,
            scanned_games=games
        )

        self.games = merged_games

        # 4. Update dropdown preserving current selected game
        self.combo_games.blockSignals(True)
        self.combo_games.clear()
        target_idx = 0
        qualified_count = 0

        for idx, g in enumerate(self.games):
            prefix = "✅ " if g.qualification == QualificationStatus.QUALIFIED else (
                "⚠️ " if g.qualification == QualificationStatus.MISSING_DLSSG else "❌ "
            )
            patch_tag = f" [已修补-{g.patched_backend}]" if g.is_patched else ""
            self.combo_games.addItem(f"{prefix}{g.name} ({g.source}){patch_tag}", g)
            if curr_exe and g.exe_path.lower() == curr_exe.lower():
                target_idx = idx
            if g.qualification == QualificationStatus.QUALIFIED:
                qualified_count += 1

        self.combo_games.blockSignals(False)
        self.lbl_status.setText(f"● 扫描完成: 发现 {len(self.games)} 款游戏 ({qualified_count} 款支持 DLSS-G)")

        if self.games:
            self.combo_games.setCurrentIndex(target_idx)
            self._on_game_dropdown_changed(target_idx)

        self._populate_library_table()
        self._update_backup_page_dropdown()

    def _create_cell_badge(self, text: str, bg_light: str, text_light: str, border_light: str,
                           bg_dark: str, text_dark: str, border_dark: str) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        c_layout = QHBoxLayout(container)
        c_layout.setContentsMargins(4, 2, 4, 2)
        c_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        bg = bg_dark if self.is_dark_mode else bg_light
        tc = text_dark if self.is_dark_mode else text_light
        bc = border_dark if self.is_dark_mode else border_light

        lbl = QLabel(text)
        lbl.setStyleSheet(f"""
            background-color: {bg};
            color: {tc};
            border: 1px solid {bc};
            border-radius: 6px;
            padding: 3px 8px;
            font-size: 11px;
            font-weight: 700;
        """)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_layout.addWidget(lbl)
        return container

    def _populate_library_table(self):
        if not hasattr(self, "table_lib"):
            return
        self.table_lib.setRowCount(len(self.games))
        if hasattr(self, "lbl_lib_count"):
            qual_count = sum(1 for g in self.games if g.qualification == QualificationStatus.QUALIFIED)
            self.lbl_lib_count.setText(f"共发现 {len(self.games)} 款游戏 · 其中 {qual_count} 款支持 DLSS-G 帧生成 (双击直接选中调校)")

        for row, g in enumerate(self.games):
            # 0. 游戏名称
            name_item = QTableWidgetItem(g.name)
            name_item.setFont(QFont("Microsoft YaHei UI", 10, QFont.Weight.Bold))
            name_item.setToolTip(f"游戏名称: {g.name}\n双击直接开启配置")
            self.table_lib.setItem(row, 0, name_item)

            # 1. 平台
            src_str = g.source
            if src_str.lower() == "steam":
                w_src = self._create_cell_badge("Steam", "#F5F5F5", "#26784C", "#E8E8E8", "#2A2B2C", "#7ED9A2", "#3A3A3A")
            elif "epic" in src_str.lower():
                w_src = self._create_cell_badge("Epic", "#F3F4F6", "#374151", "#E5E7EB", "#2A2B2C", "#94A3B8", "#3A3A3A")
            else:
                w_src = self._create_cell_badge(src_str, "#F5F5F5", "#92400E", "#E5E5E5", "#78350F", "#FCD34D", "#B45309")
            self.table_lib.setCellWidget(row, 1, w_src)

            # 2. DLSS-G 资格
            if g.qualification == QualificationStatus.QUALIFIED:
                w_qual = self._create_cell_badge("✅ 原生支持", "#DEF7EC", "#03543F", "#BCF0DA", "#064E3B", "#6EE7B7", "#059669")
            elif g.qualification == QualificationStatus.MISSING_DLSSG:
                w_qual = self._create_cell_badge("⚠️ 仅Streamline", "#FEF08A", "#854D0E", "#FDE047", "#713F12", "#FDE047", "#854D0E")
            else:
                w_qual = self._create_cell_badge("❌ 不支持", "#FDE8E8", "#9B1C1C", "#FBD5D5", "#7F1D1D", "#FCA5A5", "#991B1B")
            self.table_lib.setCellWidget(row, 2, w_qual)

            # 3. 补丁状态
            if g.is_patched:
                patch_str = f"已修补 [{g.patched_backend}]"
                w_patch = self._create_cell_badge(patch_str, "#E8E8E8", "#26784C", "#D4D4D4", "#1E3A8A", "#A7F3D0", "#2F8F5B")
            else:
                w_patch = self._create_cell_badge("未修补", "#EFEFEF", "#64748B", "#E5E5E5", "#2A2B2C", "#94A3B8", "#3A3A3A")
            self.table_lib.setCellWidget(row, 3, w_patch)

            # 4. 真实主程序路径
            path_item = QTableWidgetItem(g.exe_path)
            path_item.setForeground(QColor("#64748B" if not self.is_dark_mode else "#94A3B8"))
            path_item.setToolTip(f"主程序绝对路径:\n{g.exe_path}")
            self.table_lib.setItem(row, 4, path_item)

    def _filter_library_table(self, query: str):
        q = query.strip().lower()
        for row in range(self.table_lib.rowCount()):
            name_item = self.table_lib.item(row, 0)
            if not name_item:
                continue
            match = q in name_item.text().lower()
            self.table_lib.setRowHidden(row, not match)

    def _on_table_cell_clicked(self, row: int, col: int):
        if 0 <= row < len(self.games):
            self.combo_games.setCurrentIndex(row)

    def _on_table_cell_double_clicked(self, row: int, col: int):
        if 0 <= row < len(self.games):
            self.combo_games.setCurrentIndex(row)
            self.switch_page(0)

    def _on_table_row_double_clicked(self, item: QTableWidgetItem):
        if item:
            self._on_table_cell_double_clicked(item.row(), item.column())

    def _format_game_arch_text(self, game: GameInfo) -> str:
        """Format architecture and detected engine/frameworks for display."""
        parts = ["DirectX 12 (64-bit)"]
        if game.qualification == QualificationStatus.QUALIFIED:
            fw = []
            if game.streamline_ver:
                fw.append(f"Streamline {game.streamline_ver}")
            else:
                fw.append("Streamline 框架")
            if game.dlssg_ver:
                fw.append(f"DLSS-G {game.dlssg_ver}")
            else:
                fw.append("DLSS-G 动态库")
            parts.append(f"原生支持 DLSS-G ({' + '.join(fw)})")
        elif game.qualification == QualificationStatus.MISSING_DLSSG:
            parts.append("含 Streamline 框架 (缺少 nvngx_dlssg.dll)")
        else:
            parts.append("通用架构 (未检测到 Streamline 框架)")

        if game.has_reshade:
            parts.append("已载入 ReShade")

        return " | ".join(parts)

    def _format_game_patch_status(self, game: GameInfo) -> Tuple[str, str]:
        """Format patch status text and color."""
        if game.is_patched:
            backend_str = str(game.patched_backend or "")
            b_lower = backend_str.lower()
            ver = f" (版本: {game.installed_version})" if game.installed_version else ""
            if "mavis" in b_lower or "reshade" in b_lower:
                mode_name = "模式 B: RenoDX + ReShade"
            elif "optiscaler" in b_lower or "fsr" in b_lower:
                mode_name = "模式 C: OptiScaler / FSR 3.1"
            elif "standalone" in b_lower or "dashdogy" in b_lower:
                mode_name = "模式 A: 独立代理 DLL"
            else:
                mode_name = backend_str or "自定义补丁"
            color = "#16a34a" if not self.is_dark_mode else "#4ade80"
            return f"🟢 【{mode_name} (已注入)】{ver}", color
        else:
            color = "#64748b" if not self.is_dark_mode else "#94a3b8"
            return "⚪ 官方纯净原版 (未安装补丁)", color

    def _on_open_selected_game_dir(self):
        """Open selected game directory in Windows Explorer."""
        if not hasattr(self, "selected_game") or not self.selected_game:
            ModernDialog.warning(self, "提示", "请先在下拉列表中选择一款游戏！", self.is_dark_mode)
            return
        td = self.selected_game.target_dir or os.path.dirname(self.selected_game.exe_path)
        if td and os.path.exists(td):
            try:
                os.startfile(td)
            except Exception as e:
                ModernDialog.warning(self, "打开失败", f"无法打开游戏目录: {td}\n错误: {e}", self.is_dark_mode)
        else:
            ModernDialog.warning(self, "目录不存在", f"目标游戏所在路径不存在或已被移动:\n{td}", self.is_dark_mode)

    def _on_game_dropdown_changed(self, index: int):
        if index < 0 or index >= self.combo_games.count():
            return
        game: GameInfo = self.combo_games.itemData(index)
        if not game:
            return

        self.selected_game = game
        if hasattr(self, "lbl_game_path"):
            self.lbl_game_path.setText(game.exe_path)
        if hasattr(self, "lbl_info_arch"):
            self.lbl_info_arch.setText(self._format_game_arch_text(game))
        if hasattr(self, "lbl_info_patch"):
            patch_text, patch_color = self._format_game_patch_status(game)
            self.lbl_info_patch.setText(patch_text)
            self.lbl_info_patch.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {patch_color};")

        # Persist selection immediately to cache
        GameCacheManager.save_last_selected(game.exe_path)

        self._on_backend_dropdown_changed(self.combo_backend.currentIndex())

        sl_str = game.streamline_ver or "未检测到"
        dlssg_str = game.dlssg_ver or "未检测到"
        self.lbl_streamline_stat.setText(f"Streamline: {sl_str} | nvngx_dlssg: {dlssg_str}")

        if game.is_running:
            self.lbl_lock_stat.setText("运行状态: ⚠️ 游戏正在运行中！请先关闭后再执行修补")
            self.lbl_lock_stat.setStyleSheet("font-size: 11px; color: #dc2626; font-weight: bold;")
        else:
            self.lbl_lock_stat.setText("运行状态: ✅ 未运行 (可安全执行修补与还原)")
            self.lbl_lock_stat.setStyleSheet("font-size: 11px; color: #16a34a;")

        # Check Mode B integrity & auto-heal if needed
        if game.target_dir and os.path.exists(game.target_dir):
            addon_f = os.path.join(game.target_dir, "renodx-mfgunlock.addon64")
            if os.path.exists(addon_f):
                self.patcher.auto_heal_mode_b(game.target_dir)
                game.has_reshade = True

        if game.is_patched:
            if "mavismmg" in str(game.patched_backend).lower() or "reshade" in str(game.patched_backend).lower():
                v_ok, v_msg, v_stat = self.patcher.verify_mode_b_integrity(game.target_dir)
                if v_ok:
                    self.lbl_status.setText(f"● 状态: 就绪 | 补丁状态: 【已修补】后端: {game.patched_backend} 🟢 (框架+插件双就绪)")
                    self.top_alert.setText(f"● 游戏 '{game.name}' 已激活模式 B 插帧 (ReShade 框架与 RenoDX 插件完整就绪)")
                else:
                    self.lbl_status.setText(f"● 状态: 就绪 | 补丁状态: 【已修补】后端: {game.patched_backend} (正在自动校准框架)")
                    self.top_alert.setText(f"● 游戏 '{game.name}' 已激活多帧生成修补 ({game.patched_backend})")
            else:
                self.lbl_status.setText(f"● 状态: 就绪 | 补丁状态: 【已修补】后端: {game.patched_backend}")
                self.top_alert.setText(f"● 游戏 '{game.name}' 已激活多帧生成修补 ({game.patched_backend})")
        else:
            self.lbl_status.setText("● 状态: 就绪 | 补丁状态: 未修补")
            self.top_alert.setText(f"● 目标: {game.name} | 环境已就绪，可随时应用修补")

        # Update bi-directional file watcher to target this game and perform initial reverse sync
        self._update_ini_watcher_target()
        self._check_and_sync_from_game_ini(silent=True)
        self._refresh_rhi_display()
        self._update_preset_summary()

    def _update_backup_page_dropdown(self):
        """Update the dropdown and manifest preview in the Backup/Restore page."""
        self.combo_backup_game.blockSignals(True)
        self.combo_backup_game.clear()

        selected_idx = 0
        for i, g in enumerate(self.games):
            status_text = f" [已修补-{g.patched_backend}]" if g.is_patched else " [未修补]"
            self.combo_backup_game.addItem(f"{g.name}{status_text}", g)
            if self.selected_game and g.exe_path == self.selected_game.exe_path:
                selected_idx = i

        self.combo_backup_game.blockSignals(False)
        if self.games:
            self.combo_backup_game.setCurrentIndex(selected_idx)
            self._on_backup_game_changed(selected_idx)

    def _on_backup_game_changed(self, index: int):
        if index < 0 or index >= self.combo_backup_game.count():
            return
        g: GameInfo = self.combo_backup_game.itemData(index)
        if not g:
            return

        self.selected_game = g
        # Synchronize dashboard combo
        self.combo_games.setCurrentIndex(index)

        # Read manifest if exists
        manifest_path = os.path.join(g.target_dir, ".mfg_patch_manifest.json")
        has_manifest = os.path.exists(manifest_path)

        manifest_info = ""
        if has_manifest:
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    m = json.load(f)
                created = ", ".join(m.get("created_files", [])) or "无"
                backups = ", ".join([f"{b.get('original')}->{b.get('backup')}" for b in m.get("renamed_backups", [])]) or "无"
                manifest_info = f"\n• 注入文件: {created}\n• 备份重命名: {backups}\n• 修补时间: {m.get('patch_timestamp', '-')}"
            except Exception:
                manifest_info = "\n• 清单已存在"

        status_str = f"【已修补】后端: {g.patched_backend} (版本: {g.installed_version or '最新'})" if g.is_patched else "【官方纯净原版】未安装补丁"
        self.lbl_backup_detail.setText(
            f"🎮 目标游戏: {g.name} ({g.source})\n"
            f"📁 主程序: {g.exe_path}\n"
            f"⚡ 补丁状态: {status_str}"
            f"{manifest_info}"
        )

        if g.is_patched:
            self.lbl_manifest_summary.setText(f"清单状态: 已记录修补快照 ({g.patched_backend})，可随时一键安全无损撤销。")
            self.btn_execute_restore.setText(f"🔄 立即还原 【{g.name}】 到官方纯净原版")
            self.btn_execute_restore.setEnabled(True)
        else:
            self.lbl_manifest_summary.setText("清单状态: 当前游戏未安装补丁，处于官方原始纯净状态。")
            self.btn_execute_restore.setText(f"✅ 当前游戏已是官方纯净原版 (无需还原)")
            self.btn_execute_restore.setEnabled(False)

    def on_pick_exe_manually(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择游戏主可执行程序", "C:\\", "可执行文件 (*.exe)"
        )
        if not file_path:
            return
        self._process_manual_selection(file_path, is_file=True)

    def on_pick_dir_manually(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择游戏安装根目录", "C:\\")
        if not dir_path:
            return
        self._process_manual_selection(dir_path, is_file=False)

    def _process_manual_selection(self, path: str, is_file: bool):
        target_dir = os.path.dirname(path) if is_file else path
        game_name = os.path.splitext(os.path.basename(path))[0] if is_file else os.path.basename(path)

        info = self.scanner.analyze_game_directory(game_name, "手动自定义", target_dir)
        if not info:
            ModernDialog.warning(self, "检测提示", "所选路径中未发现有效游戏主程序！", self.is_dark_mode)
            return

        # Persist custom game into local cache so it survives rescans & restarts
        GameCacheManager.add_custom_game(info)

        self.games.insert(0, info)
        prefix = "✅ " if info.qualification == QualificationStatus.QUALIFIED else "❌ "
        self.combo_games.insertItem(0, f"{prefix}{info.name} (手动自定义)", info)
        self.combo_games.setCurrentIndex(0)
        self._populate_library_table()
        self._update_backup_page_dropdown()
        self.switch_page(0)
        ModernDialog.success(self, "添加成功", f"已成功载入游戏: {info.name}\n主程序: {info.exe_path}", self.is_dark_mode)

    def _on_progress_updated(self, val: int, text: str, detail: str):
        if self._active_progress_dlg:
            self._active_progress_dlg.set_progress(val, text, detail)

    def on_sync_updates_click(self):
        mirror = self.combo_mirror.currentText()
        mirror_prefix = DEFAULT_MIRRORS.get(mirror, "")
        self.lbl_status.setText("● 正在云端同步最新组件版本...")

        progress_dlg = ModernProgressDialog(
            self,
            title="检查与下载云端组件更新",
            description="正在连接云端发布源与镜像...",
            is_dark=self.is_dark_mode,
            cancelable=True
        )
        progress_dlg.set_indeterminate("正在向云端检查最新组件发布...", f"镜像节点: {mirror}")
        self._active_progress_dlg = progress_dlg

        def update_thread():
            results = []
            backends = [
                (BackendType.STANDALONE, "Standalone (MFGUnlocker)", 0, 33),
                (BackendType.RESHADE_ADDON, "ReShade Addon (mavismmg)", 33, 66),
                (BackendType.OPTISCALER_FSR, "OptiScaler / FSR 3.1", 66, 100)
            ]
            opti_channel = self.combo_opti_channel.currentData() if hasattr(self, "combo_opti_channel") else "nightly"
            for b, name, base_pct, end_pct in backends:
                self.signals.progress_updated.emit(
                    base_pct,
                    f"正在检查 {name} 最新版本...",
                    "查询云端 Release 资产"
                )
                channel_arg = opti_channel if b == BackendType.OPTISCALER_FSR else None
                ok, rel, err = self.updater.fetch_latest_release_info(b, mirror_prefix, channel=channel_arg)
                if ok:
                    tag = rel.get("tag_name", "最新版")
                    def item_dl_progress(downloaded, total, b_pct=base_pct, e_pct=end_pct, b_name=name):
                        if total > 0:
                            frac = min(1.0, downloaded / total)
                            pct = int(b_pct + frac * (e_pct - b_pct))
                            detail = f"已下载: {downloaded / 1024 / 1024:.2f} MB / {total / 1024 / 1024:.2f} MB ({int(frac*100)}%)"
                        else:
                            pct = int((b_pct + e_pct) / 2)
                            detail = f"已下载: {downloaded / 1024 / 1024:.2f} MB"
                        self.signals.progress_updated.emit(pct, f"正在下载 {b_name} ({tag})...", detail)

                    d_ok, d_msg = self.updater.download_and_cache(b, rel, mirror_prefix, progress_cb=item_dl_progress)
                    results.append(f"{b.value}: {tag} -> {'缓存成功' if d_ok else d_msg}")
                    self.signals.progress_updated.emit(end_pct, f"已完成 {name} 同步", tag)
                else:
                    results.append(f"{b.value}: 检查失败 ({err})")
                    self.signals.progress_updated.emit(end_pct, f"{name} 检查未通过: {err}", "保持现有本地组件")

            self.signals.progress_updated.emit(100, "组件同步流程已全部执行完成！", "正在刷新本地组件状态")
            self.signals.update_finished.emit(results)

        threading.Thread(target=update_thread, daemon=True).start()
        progress_dlg.show()

    def _on_update_finished(self, results: List[str]):
        self._load_cache_status()
        self.lbl_status.setText("● 组件同步完成。")
        if self._active_progress_dlg:
            self._active_progress_dlg.finish(
                True,
                "云端组件同步完成！",
                f"已检查并同步 {len(results)} 个核心组件",
                auto_close_delay_ms=0
            )
            self._active_progress_dlg = None
        ModernDialog.info(self, "云端组件同步结果", "\n".join(results), self.is_dark_mode)

    def on_patch_click(self):
        if not self.selected_game:
            ModernDialog.warning(self, "提示", "请先选择需要修补的游戏！", self.is_dark_mode)
            return

        backend = self.combo_backend.currentData()
        backend_str = backend.value if hasattr(backend, "value") else str(backend)
        backend_name_map = {
            "dashdogy": "dashdogy Standalone 独立代理",
            "mavismmg": "mavismmg ReShade 插件",
            "optiscaler": "OptiScaler / FSR 3.1 跨卡桥接",
            "smart_auto": "智能推荐自适应模式"
        }
        friendly_backend = backend_name_map.get(backend_str, backend_str)

        self.lbl_status.setText(f"● 正在修补游戏 '{self.selected_game.name}'...")

        progress_dlg = ModernProgressDialog(
            self,
            title="应用多帧生成补丁设置",
            description=f"正在为 '{self.selected_game.name}' 部署补丁...",
            is_dark=self.is_dark_mode
        )
        progress_dlg.show()
        self._active_progress_dlg = progress_dlg

        try:
            progress_dlg.set_progress(20, "正在检验游戏可执行文件与架构...", f"目录: {self.selected_game.target_dir}")
            QApplication.processEvents()

            progress_dlg.set_progress(50, f"正在准备 {friendly_backend} 核心生成组件...", "读取本地缓存与最新预设")
            QApplication.processEvents()

            progress_dlg.set_progress(80, "正在注入补丁文件并写入版本清单...", "执行文件部署与安全备份")
            QApplication.processEvents()

            ok, msg = self.patcher.patch_game(self.selected_game, backend, prefer_bink_hook=self.use_bink)

            if ok:
                # The requested backend can be SMART_AUTO; the manifest holds what was
                # actually deployed. Always show/persist the real backend.
                actual_backend = backend_str
                try:
                    with open(os.path.join(self.selected_game.target_dir, ".mfg_patch_manifest.json"), "r", encoding="utf-8") as f:
                        actual_backend = json.load(f).get("active_backend") or backend_str
                except Exception:
                    pass

                progress_dlg.finish(True, "补丁应用成功！", msg, auto_close_delay_ms=0)
                self.selected_game.is_patched = True
                self.selected_game.patched_backend = actual_backend
                GameCacheManager.update_patch_state(
                    self.selected_game.exe_path, True, actual_backend, self.selected_game.installed_version
                )
                curr_idx = self.combo_games.currentIndex()
                if 0 <= curr_idx < self.combo_games.count():
                    prefix = "✅ " if self.selected_game.qualification == QualificationStatus.QUALIFIED else "⚠️ "
                    self.combo_games.setItemText(curr_idx, f"{prefix}{self.selected_game.name} ({self.selected_game.source}) [已修补-{actual_backend}]")
                self._on_game_dropdown_changed(curr_idx)
                self._populate_library_table()
                self._update_backup_page_dropdown()

                # Mode B automatically injects ReShade64.dll as dxgi.dll, no manual RHI step needed!
                if actual_backend in ["mavismmg", BackendType.RESHADE_ADDON.value]:
                    self.selected_game.has_reshade = True
            else:
                progress_dlg.finish(False, "补丁应用失败", msg, auto_close_delay_ms=0)
        except Exception as e:
            progress_dlg.finish(False, "补丁应用遇到异常", f"执行异常: {e}", auto_close_delay_ms=0)
        finally:
            self._active_progress_dlg = None

    def _prompt_reshade_install_after_patch(self):
        """Deprecated: ReShade framework is now automatically deployed by the patcher."""
        pass

    def on_restore_click(self):
        if not self.selected_game:
            ModernDialog.warning(self, "提示", "请先选择需要还原的游戏！", self.is_dark_mode)
            return

        confirm = ModernDialog.confirm(
            self, "一键还原确认",
            f"确定要无损还原游戏 '{self.selected_game.name}' 吗？\n将安全删除注入的 DLL/Addon 并恢复原始备份。",
            self.is_dark_mode
        )
        if not confirm:
            return

        self.lbl_status.setText(f"● 正在还原游戏 '{self.selected_game.name}'...")

        progress_dlg = ModernProgressDialog(
            self,
            title="还原游戏原始配置",
            description=f"正在还原 '{self.selected_game.name}'...",
            is_dark=self.is_dark_mode
        )
        progress_dlg.show()
        self._active_progress_dlg = progress_dlg

        try:
            # Release any file handles held by the QFileSystemWatcher before rollback
            if hasattr(self, "_ini_watcher"):
                watched_f = self._ini_watcher.files()
                if watched_f:
                    self._ini_watcher.removePaths(watched_f)
                watched_d = self._ini_watcher.directories()
                if watched_d:
                    self._ini_watcher.removePaths(watched_d)

            progress_dlg.set_progress(30, "正在扫描已注入补丁与配置文件...", "定位 DLL 注入与 Addon 挂载")
            QApplication.processEvents()

            progress_dlg.set_progress(70, "正在清理注入文件并还原原版备份...", "恢复原始系统依赖与清单")
            QApplication.processEvents()

            ok, msg = self.rollback.rollback(self.selected_game.target_dir, self.selected_game.exe_name)
            if not ok and "未找到修补清单" in msg:
                # Already clean (manifest removed manually / by a previous restore): clear state.
                ok = True
                msg = "目标目录已无修补清单，补丁状态已重置为【未修补】。"

            if ok:
                progress_dlg.finish(True, "还原完成！", msg, auto_close_delay_ms=0)
                self.selected_game.is_patched = False
                self.selected_game.patched_backend = None
                self.selected_game.installed_version = None
                GameCacheManager.update_patch_state(self.selected_game.exe_path, False)
                curr_idx = self.combo_games.currentIndex()
                if 0 <= curr_idx < self.combo_games.count():
                    prefix = "✅ " if self.selected_game.qualification == QualificationStatus.QUALIFIED else "⚠️ "
                    self.combo_games.setItemText(curr_idx, f"{prefix}{self.selected_game.name} ({self.selected_game.source})")
                self._on_game_dropdown_changed(curr_idx)
                self._populate_library_table()
                self._update_backup_page_dropdown()
            else:
                progress_dlg.finish(False, "还原失败", msg, auto_close_delay_ms=0)
        except Exception as e:
            progress_dlg.finish(False, "还原遇到异常", f"执行异常: {e}", auto_close_delay_ms=0)
        finally:
            self._active_progress_dlg = None
            if hasattr(self, "_update_ini_watcher_target"):
                self._update_ini_watcher_target()

    def _on_status_updated(self, text: str):
        self.lbl_status.setText(f"● {text}")

    # -------------------------------------------------------------
    # Native Windows WM_NCHITTEST & Edge Drag Resizing (拖动放大缩小)
    # -------------------------------------------------------------
    def nativeEvent(self, eventType, message):
        return super().nativeEvent(eventType, message)

    def center_on_screen(self):
        screen = self.screen() or QGuiApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            new_x = avail.left() + max(0, (avail.width() - self.width()) // 2)
            new_y = avail.top() + max(0, (avail.height() - self.height()) // 2)
            self.move(new_x, new_y)

    def moveEvent(self, event):
        super().moveEvent(event)

    def _get_resize_edge(self, pos: QPoint) -> int:
        b = self.BORDER_SIZE
        c = getattr(self, "CORNER_SIZE", 20)
        w = self.width()
        h = self.height()

        # 4 corners first with generous hit zone (20x20px)
        if pos.x() <= c and pos.y() <= c:
            return 1 | 4  # Top-Left
        if pos.x() >= w - c and pos.y() <= c:
            return 2 | 4  # Top-Right
        if pos.x() <= c and pos.y() >= h - c:
            return 1 | 8  # Bottom-Left
        if pos.x() >= w - c and pos.y() >= h - c:
            return 2 | 8  # Bottom-Right

        edge = 0
        if pos.x() <= b: edge |= 1       # Left
        if pos.x() >= w - b: edge |= 2   # Right
        if pos.y() <= b: edge |= 4       # Top
        if pos.y() >= h - b: edge |= 8   # Bottom
        return edge

    def _update_cursor_for_edge(self, edge: int):
        if edge in (1 | 4, 2 | 8):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif edge in (2 | 4, 1 | 8):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif edge in (1, 2):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif edge in (4, 8):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.unsetCursor()

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            if not self.isMaximized():
                edge = self._get_resize_edge(pos)
                if edge != 0:
                    self._resize_edge = edge
                    self._resize_start_pos = event.globalPosition().toPoint()
                    self._resize_start_geom = self.geometry()
                    event.accept()
                    return
            if pos.y() <= 46:
                child = self.childAt(pos)
                is_btn = False
                p = child
                while p and p is not self:
                    if isinstance(p, QPushButton):
                        is_btn = True
                        break
                    p = p.parent()
                if not is_btn:
                    self._is_dragging = True
                    self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                    event.accept()
                    return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        pos = event.position().toPoint()
        if not self.isMaximized():
            if self._resize_edge != 0 and (event.buttons() & Qt.MouseButton.LeftButton):
                delta = event.globalPosition().toPoint() - self._resize_start_pos
                rect = self._resize_start_geom
                x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
                min_w = self.minimumWidth()
                min_h = self.minimumHeight()

                if self._resize_edge & 1: # Left
                    new_w = max(min_w, w - delta.x())
                    x = rect.right() - new_w + 1
                    w = new_w
                elif self._resize_edge & 2: # Right
                    w = max(min_w, w + delta.x())

                if self._resize_edge & 4: # Top
                    new_h = max(min_h, h - delta.y())
                    y = rect.bottom() - new_h + 1
                    h = new_h
                elif self._resize_edge & 8: # Bottom
                    h = max(min_h, h + delta.y())

                self.setGeometry(x, y, w, h)
                event.accept()
                return
            elif not (event.buttons() & Qt.MouseButton.LeftButton):
                edge = self._get_resize_edge(pos)
                self._update_cursor_for_edge(edge)

        if self._is_dragging and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        self._is_dragging = False
        self._resize_edge = 0
        self.unsetCursor()
        super().mouseReleaseEvent(event)

    def eventFilter(self, watched, event):
        if not self.isVisible() or self.isMinimized():
            return super().eventFilter(watched, event)

        et = event.type()
        if self._resize_edge != 0:
            if et == QEvent.Type.MouseMove:
                delta = event.globalPosition().toPoint() - self._resize_start_pos
                rect = self._resize_start_geom
                x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
                min_w = self.minimumWidth()
                min_h = self.minimumHeight()

                if self._resize_edge & 1: # Left
                    new_w = max(min_w, w - delta.x())
                    x = rect.right() - new_w + 1
                    w = new_w
                elif self._resize_edge & 2: # Right
                    w = max(min_w, w + delta.x())

                if self._resize_edge & 4: # Top
                    new_h = max(min_h, h - delta.y())
                    y = rect.bottom() - new_h + 1
                    h = new_h
                elif self._resize_edge & 8: # Bottom
                    h = max(min_h, h + delta.y())

                self.setGeometry(x, y, w, h)
                return True

            elif et == QEvent.Type.MouseButtonRelease:
                self._resize_edge = 0
                self.unsetCursor()
                self._edge_cursor_active = False
                return True

        if not self.isMaximized() and isinstance(watched, QWidget):
            try:
                if watched.window() is self:
                    if et == QEvent.Type.MouseMove:
                        local_pos = self.mapFromGlobal(event.globalPosition().toPoint())
                        edge = self._get_resize_edge(local_pos)
                        if edge != 0:
                            self._update_cursor_for_edge(edge)
                            self._edge_cursor_active = True
                        elif getattr(self, "_edge_cursor_active", False):
                            self.unsetCursor()
                            self._edge_cursor_active = False

                    elif et == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                        local_pos = self.mapFromGlobal(event.globalPosition().toPoint())
                        edge = self._get_resize_edge(local_pos)
                        if edge != 0:
                            self._resize_edge = edge
                            self._resize_start_pos = event.globalPosition().toPoint()
                            self._resize_start_geom = self.geometry()
                            return True
            except Exception:
                pass

        return super().eventFilter(watched, event)

    def closeEvent(self, event):
        qApp = QApplication.instance()
        if qApp:
            try:
                qApp.removeEventFilter(self)
            except Exception:
                pass
        super().closeEvent(event)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() <= 46:
            child = self.childAt(event.position().toPoint())
            is_btn = False
            p = child
            while p and p is not self:
                if isinstance(p, QPushButton):
                    is_btn = True
                    break
                p = p.parent()
            if not is_btn:
                self._toggle_maximize()
                event.accept()
                return
        super().mouseDoubleClickEvent(event)


# Backwards compatibility alias
MainWindow = ModernMFGGUI


def main():
    app = QApplication(sys.argv)
    from common.ui_theme import install_combo_arrows
    install_combo_arrows(app)

    font = QtGui.QFont("Microsoft YaHei UI", 10)
    font.setStyleStrategy(QtGui.QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)

    window = ModernMFGGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

