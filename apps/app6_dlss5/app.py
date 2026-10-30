# -*- coding: utf-8 -*-
"""
DLSS 5 Neural Reconstruction Plugin - Standalone One-Click Injector UI.
========================================================================
Implements the user requirements:
1. One-click injection of DLSS 5 plugin from Desktop (or local assets).
2. Shared Game Recognition (GameCacheManager & GameScanner) from App 2 (app2_mfg).
3. Shared ReShade / RHI installer & guide modal from App 2 (app2_mfg).
4. DLSS 5 injection with automatic coexistence hand-off for Mode A/B/C/D frame generation
   (see apps/app2_mfg/core/coexistence.py); the injector never steals another mode's proxy slot.
5. Fluent Modern Qt 6 UI with full DM Design System alignment (DWM round corners, dark/light theme).
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any

from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QIcon, QFont, QPixmap, QColor, QCursor, QGuiApplication
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QComboBox, QLineEdit,
    QFileDialog, QRadioButton, QButtonGroup, QSizePolicy,
    QCheckBox, QSpacerItem
)

# Root directory resolution
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

APP2_DIR = ROOT_DIR / "apps" / "app2_mfg"
if str(APP2_DIR) not in sys.path:
    sys.path.insert(0, str(APP2_DIR))

# Import Design System Core SDK
from dm_ui_core import (
    DMBaseWindow, DMCardFrame, DMFooterBar, DMSizeGrip,
    DMThemeManager, ModernDialog, apply_dm_window_frame,
    get_global_theme, set_global_theme,
    SCROLLBAR_LIGHT_QSS, SCROLLBAR_DARK_QSS
)

# Import Shared Game Recognition and RHI from App 2
from apps.app2_mfg.core.game_cache import GameCacheManager
from apps.app2_mfg.core.scanner import GameScanner
from apps.app2_mfg.core.models import GameInfo, QualificationStatus
from apps.app2_mfg.core.rhi_installer import RHIInstaller
from apps.app2_mfg.gui_qt import ModernRHIGuideDialog

# Import DLSS 5 Injector Engine
from apps.app6_dlss5.engine.injector import (
    DLSS5Injector, check_game_dlss5_status,
    scan_plugin_source_assets, get_plugin_source_dir,
    DLSS5_PROXY_SLOTS, DEFAULT_PROXY_SLOT,
    detect_game_render_api, ALL_DLSS5_PROXY_NAMES,
    DLSS5DelayedInjector
)
from common.config_manager import get_real_gpu_info


def _soft_wrap_path(text: str) -> str:
    """
    Insert zero-width spaces after path separators so a long Windows path can
    wrap inside a QLabel instead of forcing the whole window wider.
    """
    return text.replace("\\", "\\\u200b")



class DLSS5MonitorWorker(QThread):
    sig_status = Signal(str, str)
    sig_finished = Signal(bool, str)

    def __init__(self, exe_name: str, dll_path: str, parent=None):
        super().__init__(parent)
        self.exe_name = exe_name
        self.dll_path = dll_path
        self._stop_requested = False

    def stop(self):
        self._stop_requested = True

    def run(self):
        def log_cb(msg):
            self.sig_status.emit(msg, "#0284c7")

        ok, msg = DLSS5DelayedInjector.monitor_and_inject(
            exe_name=self.exe_name,
            dll_path=self.dll_path,
            timeout_sec=300,
            settle_delay=3.5,
            stop_check=lambda: self._stop_requested,
            log_callback=log_cb
        )
        self.sig_finished.emit(ok, msg)


class DLSS5MainWindow(DMBaseWindow):

    """
    Main Application Window for DLSS 5 Standalone One-Click Injection.
    """

    def __init__(self):
        super().__init__(
            title="DM工具箱 - DLSS 5 插件一键注入",
            width=1120,
            height=820,
            icon_filename="dlss5_icon.ico"
        )
        self.subapp_id = "app6_dlss5" 

        # Shared backend helpers from App 2
        self.rhi = RHIInstaller()
        self.scanner = GameScanner()
        self.gpu_info = get_real_gpu_info()

        self.games_list: List[GameInfo] = []
        self.selected_game: Optional[GameInfo] = None
        self.active_source_dir: Path = get_plugin_source_dir()
        self.monitor_worker: Optional[DLSS5MonitorWorker] = None

        # Build UI layout
        self._init_ui()

        # Initial data loading
        self._load_cached_games()
        self._refresh_plugin_assets()
        self._update_all_states()

        # Real-time game sync timer (syncs with App 2 mfg_game_cache.json every 1.2s)
        self.game_sync_timer = QTimer(self)
        self.game_sync_timer.setInterval(1200)
        self.game_sync_timer.timeout.connect(self._sync_selected_game_from_cache)
        self.game_sync_timer.start()

    def changeEvent(self, event):
        if event.type() == event.Type.ActivationChange and self.isActiveWindow():
            self._sync_selected_game_from_cache()
        super().changeEvent(event)

    def _sync_selected_game_from_cache(self):
        """Silently syncs currently selected game from GameCacheManager if changed externally (e.g. by App 2)."""
        try:
            cache = GameCacheManager.load_cache()
            last_exe = cache.get("last_selected_exe")
            if not last_exe:
                return

            if self.selected_game and hasattr(self.selected_game, "exe_path") and self.selected_game.exe_path.lower() == last_exe.lower():
                return

            for i in range(self.combo_games.count()):
                item = self.combo_games.itemData(i)
                if item and hasattr(item, "exe_path") and item.exe_path.lower() == last_exe.lower():
                    if self.combo_games.currentIndex() != i:
                        self.combo_games.blockSignals(True)
                        self.combo_games.setCurrentIndex(i)
                        self.selected_game = item
                        self._update_selected_game_display()
                        self._update_status_card()
                        self.combo_games.blockSignals(False)
                    return

            self._load_cached_games()
        except Exception:
            pass

    def apply_theme(self):
        super().apply_theme()
        if hasattr(self, "card_game"):
            self._apply_theme_styles(self.is_dark_mode)
        try:
            from common.ui_theme import apply_glass_controls, apply_page_surface
            card_op = max(0.50, float(getattr(self, "wallpaper_config", {}).get("card_opacity", 0.86)))
            apply_page_surface(self.scroll.widget(), self.is_dark_mode, card_op)
            apply_glass_controls(self, self.is_dark_mode)
        except Exception:
            pass

    def _init_ui(self):
        # Create a smooth scroll area inside body_layout
        scroll = QScrollArea(self)
        scroll.setObjectName("DLSS5ScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        is_dark = get_global_theme() == "dark"
        scroll.setStyleSheet(SCROLLBAR_DARK_QSS if is_dark else SCROLLBAR_LIGHT_QSS)
        scroll.viewport().setAutoFillBackground(False)
        scroll.viewport().setStyleSheet("background: transparent;")
        self.scroll = scroll

        container = QWidget()
        container.setObjectName("DLSS5ScrollContainer")
        container.setAutoFillBackground(False)
        container.setStyleSheet("background: transparent;")
        self.container = container
        self.content_layout = QVBoxLayout(container)
        self.content_layout.setContentsMargins(6, 4, 16, 12)
        self.content_layout.setSpacing(14)
        scroll.setWidget(container)

        self.body_layout.addWidget(scroll, 1)

        # Top banner with DLSS 5 logo and GPU badge
        banner_layout = QHBoxLayout()
        banner_layout.setContentsMargins(4, 0, 4, 4)
        banner_layout.setSpacing(14)

        icon_lbl = QLabel()
        icon_path = ROOT_DIR / "common" / "assets" / "dlss5_icon.png"
        if not icon_path.exists():
            icon_path = ROOT_DIR / "common" / "assets" / "dlss_icon.png"
        if icon_path.exists():
            pix = QPixmap(str(icon_path)).scaled(42, 42, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            icon_lbl.setPixmap(pix)
        banner_layout.addWidget(icon_lbl)

        title_col = QVBoxLayout()
        title_col.setSpacing(3)
        lbl_head = QLabel("DLSS 5 插件一键注入 (神经网络渲染与画质重构)")
        lbl_head.setObjectName("dlss5_head_title")
        lbl_head.setFont(QFont("Microsoft YaHei UI", 13, QFont.Weight.Bold))
        lbl_head.setWordWrap(True)

        lbl_sub = QLabel("搭载 ShortFuse 原生底座 (模式 A 默认) / Lecram v12 扩展底座 (模式 B 可选) / GITC Uplift 全 API 底座 (模式 C) · 共用二号软件游戏库与 RHI 底座 · 自动兼容多帧生成共存")
        lbl_sub.setObjectName("dlss5_sub_title")
        lbl_sub.setFont(QFont("Microsoft YaHei UI", 9))
        lbl_sub.setWordWrap(True)
        lbl_sub.setMinimumWidth(0)
        title_col.addWidget(lbl_head)
        title_col.addWidget(lbl_sub)
        banner_layout.addLayout(title_col, 1)

        # GPU badge
        self.lbl_gpu_badge = QLabel()
        self.lbl_gpu_badge.setFont(QFont("Microsoft YaHei UI", 9, QFont.Weight.Bold))
        self.lbl_gpu_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gpu_name = self.gpu_info.get("gpu_name", "NVIDIA RTX")
        short_gpu = gpu_name.replace("NVIDIA GeForce ", "").replace("NVIDIA ", "")
        self.lbl_gpu_badge.setText(f"🖥️ {short_gpu}")
        self.lbl_gpu_badge.setToolTip(f"物理显卡: {gpu_name}")
        self.lbl_gpu_badge.setMaximumWidth(260)
        self.lbl_gpu_badge.setFixedHeight(34)
        self.lbl_gpu_badge.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.lbl_gpu_badge.setStyleSheet("""
            QLabel {
                background: rgba(143, 227, 176, 0.15);
                color: #2e7d32;
                border: 1px solid rgba(143, 227, 176, 0.5);
                border-radius: 8px;
                padding: 6px 14px;
            }
        """)
        banner_layout.addWidget(self.lbl_gpu_badge, 0, Qt.AlignmentFlag.AlignVCenter)

        self.content_layout.addLayout(banner_layout)

        # -------------------------------------------------------------
        # Card 1: 🎮 游戏选择与识别 (共用二号软件多帧生成)
        # -------------------------------------------------------------
        self.card_game = DMCardFrame()
        card_game_layout = self.card_game.card_layout
        card_game_layout.setContentsMargins(18, 16, 18, 16)
        card_game_layout.setSpacing(12)

        card_game_header = QHBoxLayout()
        lbl_g_title = QLabel("🎮 目标游戏选择 (多帧生成实时同步)")
        lbl_g_title.setFont(QFont("Microsoft YaHei UI", 11, QFont.Weight.Bold))
        card_game_header.addWidget(lbl_g_title)
        card_game_header.addStretch(1)

        self.btn_rescan = QPushButton("🔄 重新扫描游戏")
        self.btn_rescan.setFixedHeight(28)
        self.btn_rescan.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_rescan.clicked.connect(self._rescan_games_action)
        card_game_header.addWidget(self.btn_rescan)

        self.btn_add_custom = QPushButton("🔍 手动添加游戏 (.exe)")
        self.btn_add_custom.setFixedHeight(28)
        self.btn_add_custom.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add_custom.clicked.connect(self._add_custom_game_action)
        card_game_header.addWidget(self.btn_add_custom)

        card_game_layout.addLayout(card_game_header)

        # Game combo box
        self.combo_games = QComboBox()
        self.combo_games.setFixedHeight(36)
        self.combo_games.setFont(QFont("Microsoft YaHei UI", 10))
        self.combo_games.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.combo_games.setMinimumContentsLength(18)
        self.combo_games.setMinimumWidth(200)
        self.combo_games.currentIndexChanged.connect(self._on_game_selected_changed)
        card_game_layout.addWidget(self.combo_games)

        # Game detail info box
        self.game_info_frame = QFrame()
        self.game_info_frame.setStyleSheet("""
            QFrame {
                background: rgba(125, 125, 125, 0.08);
                border-radius: 8px;
                padding: 6px 10px;
            }
        """)
        info_box_layout = QVBoxLayout(self.game_info_frame)
        info_box_layout.setContentsMargins(10, 8, 10, 8)
        info_box_layout.setSpacing(6)

        self.lbl_game_path = QLabel("游戏主程序: (未选择)")
        self.lbl_game_path.setFont(QFont("Microsoft YaHei UI", 9))
        self.lbl_game_path.setWordWrap(True)
        self.lbl_game_path.setMinimumWidth(0)
        self.lbl_game_path.setTextFormat(Qt.TextFormat.PlainText)

        self.lbl_target_dir = QLabel("注入目标目录: (未选择)")
        self.lbl_target_dir.setFont(QFont("Microsoft YaHei UI", 9))
        self.lbl_target_dir.setWordWrap(True)
        self.lbl_target_dir.setMinimumWidth(0)
        self.lbl_target_dir.setTextFormat(Qt.TextFormat.PlainText)

        info_box_layout.addWidget(self.lbl_game_path)
        info_box_layout.addWidget(self.lbl_target_dir)

        # Quick action row for selected game
        game_btn_row = QHBoxLayout()
        game_btn_row.setSpacing(10)

        self.btn_open_game_dir = QPushButton("📁 打开游戏目录")
        self.btn_open_game_dir.setFixedHeight(28)
        self.btn_open_game_dir.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_game_dir.clicked.connect(self._open_game_dir_action)
        game_btn_row.addWidget(self.btn_open_game_dir)

        self.btn_copy_exe = QPushButton("📋 复制主程序完整路径")
        self.btn_copy_exe.setFixedHeight(28)
        self.btn_copy_exe.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy_exe.clicked.connect(self._copy_exe_action)
        game_btn_row.addWidget(self.btn_copy_exe)

        game_btn_row.addStretch(1)
        info_box_layout.addLayout(game_btn_row)

        card_game_layout.addWidget(self.game_info_frame)
        self.content_layout.addWidget(self.card_game)

        # -------------------------------------------------------------
        # Card 2: 🛠️ ReShade / RHI 模组底座助手 (共用二号软件 RHI)
        # -------------------------------------------------------------
        self.card_rhi = DMCardFrame()
        card_rhi_layout = self.card_rhi.card_layout
        card_rhi_layout.setContentsMargins(18, 14, 18, 14)
        card_rhi_layout.setSpacing(10)

        rhi_head = QHBoxLayout()
        lbl_rhi_title = QLabel("🛠️ ReShade / RHI 模组底座助手")
        lbl_rhi_title.setFont(QFont("Microsoft YaHei UI", 11, QFont.Weight.Bold))
        rhi_head.addWidget(lbl_rhi_title)
        rhi_head.addStretch(1)

        self.lbl_rhi_status = QLabel("检测中...")
        self.lbl_rhi_status.setFont(QFont("Microsoft YaHei UI", 9))
        rhi_head.addWidget(self.lbl_rhi_status)

        self.btn_launch_rhi = QPushButton("🚀 启动 RHI 模组底座助手")
        self.btn_launch_rhi.setFixedHeight(28)
        self.btn_launch_rhi.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_launch_rhi.clicked.connect(self._launch_rhi_action)
        rhi_head.addWidget(self.btn_launch_rhi)

        card_rhi_layout.addLayout(rhi_head)

        lbl_rhi_desc = QLabel(
            "💡 提示：本一键注入包内置 ReShade 6.8 完整 Add-on 底座，通常点击【一键注入 DLSS 5】即可；"
            "若游戏需要其他渲染 API (如 Vulkan) 或想手动管理着色器，可通过 RHI 程序为游戏安装 ReShade 底座。"
        )
        lbl_rhi_desc.setFont(QFont("Microsoft YaHei UI", 9))
        lbl_rhi_desc.setWordWrap(True)
        lbl_rhi_desc.setStyleSheet("color: gray;")
        card_rhi_layout.addWidget(lbl_rhi_desc)

        # -------------------------------------------------------------
        # Proxy Slot & Anti-Cheat Bypass Selector Row
        # -------------------------------------------------------------
        lbl_proxy_title = QLabel("🛡️ 渲染底座代理槽位与防拦截模式 (自适应 / 终末地 ACE 防封):")
        lbl_proxy_title.setFont(QFont("Microsoft YaHei UI", 9, QFont.Weight.Bold))
        card_rhi_layout.addWidget(lbl_proxy_title)

        self.combo_proxy_slot = QComboBox()
        self.combo_proxy_slot.setFixedHeight(34)
        self.combo_proxy_slot.setFont(QFont("Microsoft YaHei UI", 9))
        for key, info in DLSS5_PROXY_SLOTS.items():
            self.combo_proxy_slot.addItem(info["title"], key)
        self.combo_proxy_slot.setCurrentIndex(0)
        self.combo_proxy_slot.currentIndexChanged.connect(self._on_proxy_selection_changed)
        card_rhi_layout.addWidget(self.combo_proxy_slot)

        self.lbl_proxy_hint = QLabel()
        self.lbl_proxy_hint.setFont(QFont("Microsoft YaHei UI", 8))
        self.lbl_proxy_hint.setWordWrap(True)
        self._update_proxy_hint("auto")
        card_rhi_layout.addWidget(self.lbl_proxy_hint)

        self.content_layout.addWidget(self.card_rhi)

        # -------------------------------------------------------------
        # Card 3: 🧩 DLSS 5 插件包与模型选择 (来自桌面 dlss5 插件包)
        # -------------------------------------------------------------
        self.card_plugin = DMCardFrame()
        card_plugin_layout = self.card_plugin.card_layout
        card_plugin_layout.setContentsMargins(18, 16, 18, 16)
        card_plugin_layout.setSpacing(12)

        lbl_p_title = QLabel("🧩 DLSS 5 插件包与神经网络重构模型")
        lbl_p_title.setFont(QFont("Microsoft YaHei UI", 11, QFont.Weight.Bold))
        card_plugin_layout.addWidget(lbl_p_title)

        # Plugin source directory row
        src_row = QHBoxLayout()
        src_row.setSpacing(10)
        lbl_src_tag = QLabel("插件源目录:")
        lbl_src_tag.setFont(QFont("Microsoft YaHei UI", 9, QFont.Weight.Bold))
        src_row.addWidget(lbl_src_tag)

        self.edit_src_dir = QLineEdit(str(self.active_source_dir))
        self.edit_src_dir.setFixedHeight(30)
        self.edit_src_dir.setReadOnly(True)
        src_row.addWidget(self.edit_src_dir, 1)

        self.btn_browse_src = QPushButton("📁 浏览更换...")
        self.btn_browse_src.setFixedHeight(30)
        self.btn_browse_src.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_browse_src.clicked.connect(self._browse_source_dir_action)
        src_row.addWidget(self.btn_browse_src)

        card_plugin_layout.addLayout(src_row)

        # Detected components in plugin source
        self.lbl_src_details = QLabel("正在扫描插件资产...")
        self.lbl_src_details.setFont(QFont("Microsoft YaHei UI", 9))
        self.lbl_src_details.setWordWrap(True)
        card_plugin_layout.addWidget(self.lbl_src_details)

        lbl_portable_hint = QLabel(
            "✨ 资产自包含保障：插件包与神经网络模型已完整封装于整合包内部 (apps/app6_dlss5/assets)，"
            "复制整合包至任意其他电脑即可全机免配置即开即用！"
        )
        lbl_portable_hint.setFont(QFont("Microsoft YaHei UI", 8))
        lbl_portable_hint.setStyleSheet("color: #059669;")
        lbl_portable_hint.setWordWrap(True)
        card_plugin_layout.addWidget(lbl_portable_hint)

        # -------------------------------------------------------------
        # 2.2 DLSS 5 注入底座模式选择 (模式 A / 模式 B)
        # -------------------------------------------------------------
        lbl_mode_block_title = QLabel("🛠️ DLSS 5 扩展插件底座模式 (模式 A / 模式 B):")
        lbl_mode_block_title.setFont(QFont("Microsoft YaHei UI", 9, QFont.Weight.Bold))
        card_plugin_layout.addWidget(lbl_mode_block_title)

        self.combo_dlss5_mode = QComboBox()
        self.combo_dlss5_mode.setFixedHeight(36)
        self.combo_dlss5_mode.setFont(QFont("Microsoft YaHei UI", 9))
        self.combo_dlss5_mode.addItem(
            "🚀 模式 A (默认推荐) — renodx-dlss.addon64 [ShortFuse 官方原生底座 · 极速稳定]",
            "MODE_A"
        )
        self.combo_dlss5_mode.addItem(
            "⚡ 模式 B (可选项目) — Lecram v12 / v12.5 [Lecram 旗舰扩展底座 · 深度参数定制 · 快捷键 F12]",
            "MODE_B"
        )
        self.combo_dlss5_mode.addItem(
            "🧪 模式 C (全 API 通用) — gitc-uplift.addon64 [GITC Uplift 1.7.0 · DX9/10/11/12/Vulkan/OpenGL · 自带显存检查与中文界面]",
            "MODE_C"
        )
        self.combo_dlss5_mode.setCurrentIndex(0)
        self.combo_dlss5_mode.currentIndexChanged.connect(self._on_mode_selection_changed)
        card_plugin_layout.addWidget(self.combo_dlss5_mode)

        # 模式 B 底座版本（仅模式 B 时显示）
        self.combo_mode_b_variant = QComboBox()
        self.combo_mode_b_variant.setFixedHeight(32)
        self.combo_mode_b_variant.setFont(QFont("Microsoft YaHei UI", 9))
        self.combo_mode_b_variant.addItem(
            "🔧 模式 B · Lecram v12（默认）— 9.0 MB · 稳定版", "v12"
        )
        self.combo_mode_b_variant.addItem(
            "🧪 模式 B · Lecram v12.5（新版）— 10.0 MB · 可选升级", "v12.5"
        )
        self.combo_mode_b_variant.setToolTip(
            "Lecram v12.5 是较新的扩展底座版本，面板与参数项更多；\n"
            "若 v12.5 出现兼容问题，可随时切回 v12。"
        )
        self.combo_mode_b_variant.setCurrentIndex(1)  # 默认 Lecram v12.5
        self.combo_mode_b_variant.setVisible(False)
        card_plugin_layout.addWidget(self.combo_mode_b_variant)

        self.lbl_mode_hint = QLabel()
        self.lbl_mode_hint.setFont(QFont("Microsoft YaHei UI", 8))
        self.lbl_mode_hint.setWordWrap(True)
        self._update_mode_hint("MODE_A")
        card_plugin_layout.addWidget(self.lbl_mode_hint)

        # Architecture model selection radios
        lbl_model_tag = QLabel("⚡ 神经重构模型版本 (nvngx_dlssnr.dll):")
        lbl_model_tag.setFont(QFont("Microsoft YaHei UI", 9, QFont.Weight.Bold))
        card_plugin_layout.addWidget(lbl_model_tag)

        self.radio_group_arch = QButtonGroup(self)
        arch_row = QVBoxLayout()
        arch_row.setSpacing(8)

        # Auto option with true GPU name
        is_50 = self.gpu_info.get("arch") == "rtx50"
        rec_model_name = "RTX 50 系列专用模型" if is_50 else "RTX 20/30/40 系列专用模型 (310.9.16 新版)"

        self.rb_auto = QRadioButton("🔘 智能推荐（自动匹配）")
        self.rb_auto.setToolTip(f"检测到物理硬件: {gpu_name}\n自动选择: {rec_model_name}")
        self.rb_auto.setChecked(True)
        self.radio_group_arch.addButton(self.rb_auto, 0)
        arch_row.addWidget(self.rb_auto)

        self.rb_40 = QRadioButton("🔘 RTX 20/30/40 系列模型")
        self.rb_40.setToolTip("文件: nvngx_dlssnr_310.9.16__rtx20-30-40 系列显卡专用（263.37 MB）")
        self.radio_group_arch.addButton(self.rb_40, 1)
        arch_row.addWidget(self.rb_40)

        self.rb_50 = QRadioButton("🔘 RTX 50 系列模型")
        self.rb_50.setToolTip("文件: nvngx_dlssnr-1017 新 NR 50 显卡专用（254.08 MB）")
        self.radio_group_arch.addButton(self.rb_50, 2)
        arch_row.addWidget(self.rb_50)

        card_plugin_layout.addLayout(arch_row)

        # ---- NR VRAM budget guard (防 4K + 多帧生成打爆显存导致 TDR 闪退) ----
        vram_row = QHBoxLayout()
        vram_row.setSpacing(10)
        self.chk_nr_vram_guard = QCheckBox("🛡️ 启用 NR 显存预算守卫（显存不足时自动降档，防 TDR 闪退）")
        self.chk_nr_vram_guard.setToolTip(
            "NR 神经重构会额外占用显存（模型 + 中间缓冲）。\n"
            "开启后 RenoDX 在分配前检查剩余显存，不足时自动降低 NR 负载，\n"
            "而不是把显存吃满触发驱动超时（0x141 TDR）。\n"
            "4K + 多帧生成同时开启时强烈建议打开。"
        )
        vram_row.addWidget(self.chk_nr_vram_guard, 1)

        lbl_margin = QLabel("预留余量:")
        vram_row.addWidget(lbl_margin)
        self.combo_nr_vram_margin = QComboBox()
        for _label, _val in [("0% (不预留)", 0), ("5% (推荐)", 5), ("10%", 10), ("15%", 15), ("20% (保守)", 20)]:
            self.combo_nr_vram_margin.addItem(_label, _val)
        self.combo_nr_vram_margin.setMinimumWidth(130)
        vram_row.addWidget(self.combo_nr_vram_margin)
        card_plugin_layout.addLayout(vram_row)

        self._load_nr_vram_settings()

        card_plugin_layout.addLayout(arch_row) if False else None
        self.content_layout.addWidget(self.card_plugin)

        # -------------------------------------------------------------
        # Card 4: ⚙️ DLSS 5 挂钩阶段模式配置 (防启动闪退 / 多帧插帧协同)
        # -------------------------------------------------------------
        self.card_hook = DMCardFrame()
        card_hook_layout = self.card_hook.card_layout
        card_hook_layout.setContentsMargins(18, 16, 18, 16)
        card_hook_layout.setSpacing(12)

        hook_header = QHBoxLayout()
        lbl_h_title = QLabel("⚙️ DLSS 5 挂钩阶段模式配置 (防启动闪退 / 多帧插帧协同)")
        lbl_h_title.setFont(QFont("Microsoft YaHei UI", 11, QFont.Weight.Bold))
        hook_header.addWidget(lbl_h_title)
        hook_header.addStretch(1)

        self.btn_apply_hook = QPushButton("⚡ 立即应用/修改挂钩模式 (无需启动游戏)")
        self.btn_apply_hook.setFixedHeight(30)
        self.btn_apply_hook.setFont(QFont("Microsoft YaHei UI", 9, QFont.Weight.Bold))
        self.btn_apply_hook.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_apply_hook.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
            QPushButton:pressed {
                background-color: #075985;
            }
            QPushButton:disabled {
                background-color: rgba(148, 163, 184, 0.2);
                color: #94a3b8;
            }
        """)
        self.btn_apply_hook.clicked.connect(self._apply_hook_mode_action)
        hook_header.addWidget(self.btn_apply_hook)

        card_hook_layout.addLayout(hook_header)

        # Hook mode selection row
        hook_row = QHBoxLayout()
        hook_row.setSpacing(12)
        lbl_hook_tag = QLabel("挂钩阶段模式 (Hook Point):")
        lbl_hook_tag.setFont(QFont("Microsoft YaHei UI", 9, QFont.Weight.Bold))
        hook_row.addWidget(lbl_hook_tag)

        self.combo_hook_point = QComboBox()
        self.combo_hook_point.setFixedHeight(34)
        self.combo_hook_point.setFont(QFont("Microsoft YaHei UI", 9))
        self.combo_hook_point.addItem("之后 (Upscaled) · 【推荐 · 防闪退 · 兼容 4X/多帧插帧与低显存】", "0")
        self.combo_hook_point.addItem("呈现 (Present) · 【纯画质呈现 · 适合原生单卡无插帧高显存环境】", "2")
        self.combo_hook_point.addItem("之前 (Before) · 【超分前原生阶段 · 原生画质处理】", "1")
        self.combo_hook_point.setCurrentIndex(0)
        hook_row.addWidget(self.combo_hook_point, 1)

        card_hook_layout.addLayout(hook_row)

        lbl_hook_explain = QLabel(
            "💡 【模式特性说明与防闪退保障】\n"
            "• 之后 (Upscaled · 推荐)：DLSS 5 在 DLSS 超分之后、帧生成之前介入。具备完整深度与运动矢量缓冲，"
            "显存占用极小 (~600MB)，彻底根治 2077、巫师 3 开启 4X 插帧或高分辨率时的 0xc0000005 启动秒退！\n"
            "• 呈现 (Present)：在最终画面呈现交换链介入。对 4K 全分辨率二次重构，显存占用较高 (~2.5GB)，且严禁与 4X 插帧同时开启。\n"
            "• 离线修改保障：若游戏因配置冲突无法启动，直接在上方下拉框选择【之后 (Upscaled)】并点击右侧【立即应用/修改挂钩模式】，"
            "本软件将直接写入游戏配置文件，免启动游戏即可彻底修复闪退！"
        )
        lbl_hook_explain.setFont(QFont("Microsoft YaHei UI", 8))
        lbl_hook_explain.setWordWrap(True)
        lbl_hook_explain.setStyleSheet("color: #0369a1; background: rgba(3, 105, 161, 0.08); border-radius: 6px; padding: 8px;")
        card_hook_layout.addWidget(lbl_hook_explain)

        self.content_layout.addWidget(self.card_hook)

        # -------------------------------------------------------------
        # Card 5: 📊 当前游戏 DLSS 5 注入状态
        # -------------------------------------------------------------
        self.card_status = DMCardFrame()
        card_status_layout = self.card_status.card_layout
        card_status_layout.setContentsMargins(18, 16, 18, 16)
        card_status_layout.setSpacing(10)

        status_header = QHBoxLayout()
        lbl_stat_title = QLabel("📊 当前游戏 DLSS 5 注入状态")
        lbl_stat_title.setFont(QFont("Microsoft YaHei UI", 11, QFont.Weight.Bold))
        status_header.addWidget(lbl_stat_title)
        status_header.addStretch(1)

        self.lbl_main_status_badge = QLabel("⚪ 未注入")
        self.lbl_main_status_badge.setFont(QFont("Microsoft YaHei UI", 10, QFont.Weight.Bold))
        status_header.addWidget(self.lbl_main_status_badge)

        card_status_layout.addLayout(status_header)

        # Status details items
        self.lbl_stat_reshade = QLabel("• ReShade 渲染底座: ⚪ 未就绪")
        self.lbl_stat_addon = QLabel("• DLSS 5 扩展插件: ⚪ 未就绪")
        self.lbl_stat_runtime = QLabel("• 神经重构模型: ⚪ 未就绪")
        self.lbl_stat_hook = QLabel("• 运行挂钩阶段: ⚪ 未就绪")
        for lbl in [self.lbl_stat_reshade, self.lbl_stat_addon, self.lbl_stat_runtime, self.lbl_stat_hook]:
            lbl.setFont(QFont("Microsoft YaHei UI", 9))
            card_status_layout.addWidget(lbl)

        # Guidance text
        lbl_guide = QLabel(
            "📌 【默认设置与还原保障】\n"
            "1. 默认调优预设：注入已自动配置实机调优参数（风格[模型 C] · 版本[新版] · 分辨率[匹配游戏] · 挂钩[之后/Upscaled · 超分之后 · 防闪退防卡死] · 显存缓冲[最小/Minimal · 极致节省显存] · 预设[My look]）；\n"
            "2. 启动游戏：请在游戏图形设置中开启【DirectX 12】与【DLSS 超分辨率】；\n"
            "3. 游戏内呼出：按键盘【Home】键呼出中文面板，按【F6】键可实时开关 DLSS 5 神经重构；\n"
            "4. 彻底还原：点击【一键卸载与彻底还原】将深度净化 RHI/ReShade/DLSS 5/runtime 全套残留，100% 恢复游戏原生纯净环境。"
        )
        lbl_guide.setFont(QFont("Microsoft YaHei UI", 9))
        lbl_guide.setWordWrap(True)
        lbl_guide.setMinimumWidth(0)
        lbl_guide.setStyleSheet("color: #0284c7; background: rgba(2, 132, 199, 0.08); border-radius: 6px; padding: 8px;")
        card_status_layout.addWidget(lbl_guide)

        self.content_layout.addWidget(self.card_status)

        # -------------------------------------------------------------
        # Action Buttons in Footer Bar
        # -------------------------------------------------------------
        self.btn_inject = QPushButton("🚀 一键注入 DLSS 5 插件")
        self.btn_inject.setFixedHeight(34)
        self.btn_inject.setFont(QFont("Microsoft YaHei UI", 10, QFont.Weight.Bold))
        self.btn_inject.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_inject.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 0 24px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
            QPushButton:pressed {
                background-color: #047857;
            }
        """)
        self.btn_inject.clicked.connect(self._inject_action)
        self.footer_bar.add_action_widget(self.btn_inject)

        self.btn_restore = QPushButton("🧹 一键卸载与彻底还原")
        self.btn_restore.setFixedHeight(34)
        self.btn_restore.setFont(QFont("Microsoft YaHei UI", 10))
        self.btn_restore.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_restore.setStyleSheet("""
            QPushButton {
                background-color: rgba(239, 68, 68, 0.12);
                color: #dc2626;
                border: 1px solid rgba(239, 68, 68, 0.3);
                border-radius: 8px;
                padding: 0 18px;
            }
            QPushButton:hover {
                background-color: rgba(239, 68, 68, 0.22);
            }
            QPushButton:pressed {
                background-color: rgba(239, 68, 68, 0.32);
            }
        """)
        self.btn_restore.clicked.connect(self._restore_action)
        self.footer_bar.add_action_widget(self.btn_restore)

        # Apply styles
        self._apply_theme_styles(get_global_theme() == "dark")

    # -----------------------------------------------------------------
    # Backend Logic & Data Loading
    # -----------------------------------------------------------------
    # ---- NR VRAM budget guard ----
    def _load_nr_vram_settings(self):
        """Load the persisted NR VRAM guard preference and wire change handlers."""
        try:
            from apps.app6_dlss5.engine.injector import load_nr_vram_settings
            settings = load_nr_vram_settings()
        except Exception:
            settings = {"guard": False, "margin": 0}
        self.chk_nr_vram_guard.setChecked(bool(settings.get("guard", False)))
        idx = self.combo_nr_vram_margin.findData(int(settings.get("margin", 0) or 0))
        if idx >= 0:
            self.combo_nr_vram_margin.setCurrentIndex(idx)
        self.chk_nr_vram_guard.toggled.connect(self._on_nr_vram_changed)
        self.combo_nr_vram_margin.currentIndexChanged.connect(self._on_nr_vram_changed)

    def _nr_vram_values(self):
        guard = bool(self.chk_nr_vram_guard.isChecked())
        try:
            margin = int(self.combo_nr_vram_margin.currentData() or 0)
        except Exception:
            margin = 0
        return guard, margin

    def _on_nr_vram_changed(self, *_args):
        """Persist the choice and push it into the currently selected game."""
        guard, margin = self._nr_vram_values()
        try:
            from apps.app6_dlss5.engine.injector import (
                save_nr_vram_settings,
                sync_nr_vram_settings,
            )
            save_nr_vram_settings(guard, margin)
            game = getattr(self, "selected_game", None)
            if game is not None:
                sync_nr_vram_settings(game.target_dir, guard, margin)
                self.set_status(
                    "NR 显存预算守卫：%s（余量 %d%%）已应用到当前游戏，重启游戏生效"
                    % ("开启" if guard else "关闭", margin)
                )
        except Exception:
            pass

    def _load_cached_games(self):
        """Loads game cache shared with App 2."""
        try:
            cached_games, last_exe = GameCacheManager.get_cached_games()
            self.games_list = cached_games or []

            self.combo_games.blockSignals(True)
            self.combo_games.clear()

            target_idx = 0
            for i, g in enumerate(self.games_list):
                tag = f"[{g.source}]" if g.source else ""
                self.combo_games.addItem(f"{tag} {g.name} - {g.exe_name}", g)
                if last_exe and g.exe_path.lower() == last_exe.lower():
                    target_idx = i

            if self.games_list:
                self.combo_games.setCurrentIndex(target_idx)
                self.selected_game = self.games_list[target_idx]
            else:
                self.combo_games.addItem("暂未扫描到游戏，请点击右侧【重新扫描】或【手动添加】", None)
                self.selected_game = None

            self.combo_games.blockSignals(False)
            self._update_selected_game_display()
        except Exception as e:
            self.set_status(f"加载游戏列表遇到问题: {e}")

    def _rescan_games_action(self):
        """Triggers game scan using App 2 GameScanner and updates GameCacheManager."""
        self.set_status("正在扫描系统已安装游戏与各驱动器游戏库...")
        QApplication.processEvents()
        try:
            games = self.scanner.scan_games()
            if games:
                GameCacheManager.save_cache(
                    last_selected_exe=self.selected_game.exe_path if self.selected_game else None,
                    scanned_games=games
                )
                self._load_cached_games()
                ModernDialog.success(self, "扫描完成", f"已成功识别到 {len(games)} 款游戏！已同步至游戏列表。")
            else:
                ModernDialog.info(self, "扫描结果", "未能在标准驱动器与平台注册表中自动找到游戏，您可点击【手动添加游戏】选择游戏的 .exe 程序。")
        except Exception as e:
            ModernDialog.error(self, "扫描失败", str(e))
        finally:
            self.set_status("就绪")

    def _add_custom_game_action(self):
        """Manually picks a game exe file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择游戏主程序 (DirectX 12 / DLSS 游戏)",
            "D:\\game",
            "游戏主程序 (*.exe)"
        )
        if not file_path:
            return

        try:
            info = self.scanner.get_game_info_from_exe(file_path)
            if info:
                GameCacheManager.add_custom_game(info)
                self._load_cached_games()
                # Find and select the added game
                for i in range(self.combo_games.count()):
                    item = self.combo_games.itemData(i)
                    if item and item.exe_path.lower() == info.exe_path.lower():
                        self.combo_games.setCurrentIndex(i)
                        break
                ModernDialog.success(
                    self,
                    "添加成功",
                    f"已成功添加并识别游戏:\n{info.name}\n主程序: {info.exe_path}\n注入目标目录: {info.target_dir}"
                )
            else:
                ModernDialog.warning(self, "添加失败", "所选文件无法识别为有效游戏主程序，请检查路径。")
        except Exception as e:
            ModernDialog.error(self, "添加失败", str(e))

    def _on_game_selected_changed(self, idx: int):
        data = self.combo_games.itemData(idx)
        if data is not None and (isinstance(data, GameInfo) or hasattr(data, "exe_path")):
            self.selected_game = data
            GameCacheManager.save_last_selected(data.exe_path)
            self._update_selected_game_display()
            self._update_status_card()

    def _update_selected_game_display(self):
        if not self.selected_game:
            self.lbl_game_path.setText("游戏主程序: (未选择)")
            self.lbl_target_dir.setText("注入目标目录: (未选择)")
            self.btn_open_game_dir.setEnabled(False)
            self.btn_copy_exe.setEnabled(False)
            return

        self.btn_open_game_dir.setEnabled(True)
        self.btn_copy_exe.setEnabled(True)
        self.lbl_game_path.setText(_soft_wrap_path(f"游戏主程序: {self.selected_game.exe_path}"))
        self.lbl_target_dir.setText(_soft_wrap_path(f"注入目标目录: {self.selected_game.target_dir}"))
        self._update_inject_button_text()

    def _open_game_dir_action(self):
        if self.selected_game and os.path.exists(self.selected_game.target_dir):
            try:
                os.startfile(self.selected_game.target_dir)
            except Exception as e:
                ModernDialog.warning(self, "打开失败", str(e))

    def _copy_exe_action(self):
        if self.selected_game:
            QApplication.clipboard().setText(self.selected_game.exe_path)
            self.set_status("已复制主程序完整路径到剪贴板！")

    def _update_mode_hint(self, mode: str):
        """Updates the dynamic mode hint text and style for Mode A and Mode B."""
        if mode == "MODE_C":
            self.lbl_mode_hint.setText(
                "当前已选模式 C (全 API 通用)：使用 GITC Uplift 1.7.0，自动部署 addon + helper + "
                "GITC-Uplift\\nvngx_dlssnr.dll 与 Uplift.fx。进游戏按 Home 打开 ReShade，在 GITC Uplift 标签勾选 Enable。"
            )
            self.lbl_mode_hint.setStyleSheet("""
                QLabel {
                    color: #7c3aed;
                    background: rgba(124, 58, 237, 0.08);
                    border: 1px solid rgba(124, 58, 237, 0.25);
                    border-radius: 6px;
                    padding: 6px 10px;
                }
            """)
        elif mode == "MODE_B":
            self.lbl_mode_hint.setText("当前已选模式 B (可选)：使用 Lecram-v12.addon64，游戏内按 F12 可调 UI 遮罩、滤镜与 Model A/B/C。")
            self.lbl_mode_hint.setStyleSheet("""
                QLabel {
                    color: #0284c7;
                    background: rgba(2, 132, 199, 0.08);
                    border: 1px solid rgba(2, 132, 199, 0.25);
                    border-radius: 6px;
                    padding: 6px 10px;
                }
            """)
        else:
            self.lbl_mode_hint.setText("当前已选模式 A (默认)：使用 ShortFuse 原版 renodx-dlss.addon64，体积轻量、兼容性最佳。")
            self.lbl_mode_hint.setStyleSheet("""
                QLabel {
                    color: #059669;
                    background: rgba(16, 185, 129, 0.08);
                    border: 1px solid rgba(16, 185, 129, 0.25);
                    border-radius: 6px;
                    padding: 6px 10px;
                }
            """)

    def _on_mode_selection_changed(self, idx: int):
        """Triggered when user manually switches mode combo box."""
        mode = self.combo_dlss5_mode.itemData(idx) or "MODE_A"
        if hasattr(self, "combo_mode_b_variant"):
            self.combo_mode_b_variant.setVisible(mode == "MODE_B")
        self._update_mode_hint(mode)
        self._refresh_plugin_assets()

    def _sync_mode_selector(self, mode: str):
        """
        Synchronizes mode combo box without triggering re-entrant writes.
        Defaults to MODE_A if mode is unrecognized.
        """
        target_idx = {"MODE_A": 0, "MODE_B": 1, "MODE_C": 2}.get(mode, 0)
        if hasattr(self, "combo_dlss5_mode"):
            if self.combo_dlss5_mode.currentIndex() != target_idx:
                self.combo_dlss5_mode.blockSignals(True)
                self.combo_dlss5_mode.setCurrentIndex(target_idx)
                self.combo_dlss5_mode.blockSignals(False)
            self._update_mode_hint(mode if mode in ("MODE_A", "MODE_B") else "MODE_A")
        if hasattr(self, "combo_mode_b_variant"):
            self.combo_mode_b_variant.setVisible(target_idx == 1)
            if target_idx != 1:
                # 回到模式 A 时把 B 的版本选择复位到默认 v12.5，
                # 避免上一次模式 B 的残留选择影响下一次注入。
                default_idx = self.combo_mode_b_variant.findData("v12.5")
                if default_idx >= 0 and self.combo_mode_b_variant.currentIndex() != default_idx:
                    self.combo_mode_b_variant.blockSignals(True)
                    self.combo_mode_b_variant.setCurrentIndex(default_idx)
                    self.combo_mode_b_variant.blockSignals(False)

    def _update_proxy_hint(self, proxy_key: str):
        """Updates dynamic proxy slot hint label based on selected slot and detected game."""
        if not hasattr(self, "lbl_proxy_hint"):
            return
        rec_text = ""
        if self.selected_game and hasattr(self.selected_game, "target_dir"):
            rec_proxy, rec_reason, _ = detect_game_render_api(self.selected_game.target_dir)
            rec_text = f"\n【实机智能探测】{rec_reason}"

        if proxy_key == "auto":
            hint_msg = (
                "当前模式：🚀 智能推荐。系统将根据目标游戏引擎（Unity / Unreal / 自研）与反作弊系统自适应匹配最佳底座代理。\n"
                "• 普通单机/DX12大作 -> 自动采用 dxgi.dll；\n"
                "• Unity/ACE二游 (如终末地) -> 自动推荐 d3d12.dll，彻底免去外部注入并杜绝 1051 拦截；\n"
                "• 已装 OptiScaler 跨架构多帧生成 -> 自动链式调用 ReShade64.dll，零系统图形 DLL 落地。"
            )
            if rec_text:
                hint_msg += rec_text
            self.lbl_proxy_hint.setText(hint_msg)
            self.lbl_proxy_hint.setStyleSheet("""
                QLabel {
                    color: #059669;
                    background: rgba(16, 185, 129, 0.08);
                    border: 1px solid rgba(16, 185, 129, 0.25);
                    border-radius: 6px;
                    padding: 6px 10px;
                }
            """)
        elif proxy_key == "d3d11.dll":
            self.lbl_proxy_hint.setText(
                "🛡️ d3d11.dll：强制通过 DirectX 11 接口挂载 ReShade。适用于《明日方舟：终末地》等 Unity/ACE 反作弊二游，"
                "可完美绕过 ACE 对 dxgi.dll 的非法拦截，并彻底消除 d3d12.dll 导致的 D3D11On12 崩溃！"
            )
            self.lbl_proxy_hint.setStyleSheet("""
                QLabel {
                    color: #0284c7;
                    background: rgba(2, 132, 199, 0.08);
                    border: 1px solid rgba(2, 132, 199, 0.25);
                    border-radius: 6px;
                    padding: 6px 10px;
                }
            """)
        elif proxy_key == "d3d12.dll":
            self.lbl_proxy_hint.setText(
                "⚡ d3d12.dll [终末地 ACE 防拦截首选 · 进程隔离双擎加固]：\n"
                "• 独创【进程隔离双擎机制】：自动搭载顶层 ProcessFilter 防护，彻底忽略 PlatformProcess.exe 与 Qt 辅助进程，彻底杜绝辅助进程报错与游戏卡死闪退！\n"
                "• 游戏主程序 (Endfield.exe) 内部原生载入 ReShade64，免外部内存注入，彻底规避错误代码 5！\n"
                "• 点击【🚀 一键注入 DLSS 5】后，直接打开鹰角启动器点【开始游戏】，进入画面按 Home / F12 即可畅享 DLSS 5！"
            )
            self.lbl_proxy_hint.setStyleSheet("""
                QLabel {
                    color: #059669;
                    background: rgba(16, 185, 129, 0.08);
                    border: 1px solid rgba(16, 185, 129, 0.25);
                    border-radius: 6px;
                    padding: 6px 10px;
                }
            """)
        elif proxy_key == "ReShade64.dll":
            self.lbl_proxy_hint.setText(
                "🛡️ ReShade64.dll [零系统图形DLL落地 · 延时动态注入模式]：\n"
                "• 磁盘不落地敏感图形 DLL，由工具箱在窗口建立后延时动态注入。\n"
                "• ⚠️ 注意：因腾讯 ACE 内核驱动会拦截外部内存操作导致“分配内存失败 (错误代码: 5)”，《终末地》请直接改用上方【⚡ d3d12.dll】原生槽位！"
            )
            self.lbl_proxy_hint.setStyleSheet("""
                QLabel {
                    color: #7c3aed;
                    background: rgba(124, 58, 237, 0.08);
                    border: 1px solid rgba(124, 58, 237, 0.25);
                    border-radius: 6px;
                    padding: 6px 10px;
                }
            """)
        else:  # dxgi.dll
            self.lbl_proxy_hint.setText(
                "🟢 dxgi.dll：官方标准通用劫持挂载。适用于绝大多数单机 DirectX 11 / DirectX 12 3A 大作，兼容性最佳。"
            )
            self.lbl_proxy_hint.setStyleSheet("""
                QLabel {
                    color: #059669;
                    background: rgba(16, 185, 129, 0.08);
                    border: 1px solid rgba(16, 185, 129, 0.25);
                    border-radius: 6px;
                    padding: 6px 10px;
                }
            """)

    def _on_proxy_selection_changed(self, idx: int):
        """Triggered when user manually switches proxy slot combo box."""
        proxy_key = self.combo_proxy_slot.itemData(idx) or "auto"
        self._update_proxy_hint(proxy_key)
        self._update_inject_button_text()

    def _update_inject_button_text(self):
        """Updates the inject button text and appearance depending on monitor state and proxy slot."""
        if not hasattr(self, "btn_inject"):
            return
        if self.monitor_worker and self.monitor_worker.isRunning():
            self.btn_inject.setText("🛑 正在监听启动 (点击取消)")
            self.btn_inject.setStyleSheet("""
                QPushButton {
                    background-color: #d97706;
                    color: #ffffff;
                    border: none;
                    border-radius: 8px;
                    padding: 0 24px;
                }
                QPushButton:hover {
                    background-color: #b45309;
                }
                QPushButton:pressed {
                    background-color: #92400e;
                }
            """)
        else:
            cur_proxy = self.combo_proxy_slot.currentData() if hasattr(self, "combo_proxy_slot") else "auto"
            is_delay_mode = False
            if cur_proxy == "ReShade64.dll":
                is_delay_mode = True
            elif cur_proxy == "auto" and self.selected_game:
                rec_proxy, _, _ = detect_game_render_api(self.selected_game.target_dir)
                if rec_proxy == "ReShade64.dll":
                    is_delay_mode = True

            if is_delay_mode:
                self.btn_inject.setText("🚀 一键注入并开启启动监听")
            else:
                self.btn_inject.setText("🚀 一键注入 DLSS 5 插件")
            self.btn_inject.setStyleSheet("""
                QPushButton {
                    background-color: #10b981;
                    color: #ffffff;
                    border: none;
                    border-radius: 8px;
                    padding: 0 24px;
                }
                QPushButton:hover {
                    background-color: #059669;
                }
                QPushButton:pressed {
                    background-color: #047857;
                }
            """)

    def _sync_proxy_selector(self, proxy_key: str):
        """Synchronizes proxy selector combo box without triggering re-entrant writes."""
        if not hasattr(self, "combo_proxy_slot"):
            return
        target_idx = 0
        for i in range(self.combo_proxy_slot.count()):
            if self.combo_proxy_slot.itemData(i) == proxy_key:
                target_idx = i
                break
        if self.combo_proxy_slot.currentIndex() != target_idx:
            self.combo_proxy_slot.blockSignals(True)
            self.combo_proxy_slot.setCurrentIndex(target_idx)
            self.combo_proxy_slot.blockSignals(False)
        self._update_proxy_hint(proxy_key)

    def _refresh_plugin_assets(self):
        """
        2.3 插件源目录资产清单动态刷新 (update_assets_info)
        Scans plugin source directory and updates UI with dual-mode asset status.
        """
        cur_mode = self.combo_dlss5_mode.currentData() if hasattr(self, "combo_dlss5_mode") else "MODE_A"
        assets = scan_plugin_source_assets(self.active_source_dir, mode=cur_mode)
        is_local = "app6_dlss5" in str(assets["source_dir"]) or "整合包" in str(assets["source_dir"])
        tag = "  [📦 整合包内置便携资产 · 全机免配置]" if is_local else ""
        self.edit_src_dir.setText(f"{assets['source_dir']}{tag}")

        details = []
        if assets["dxgi_path"]:
            details.append(f"• 渲染底座: dxgi.dll ({assets['dxgi_size_mb']} MB · ReShade 6.8 64-bit)")
        else:
            details.append("• 渲染底座: <span style='color: #ef4444;'>❌ 缺失 dxgi.dll</span>")

        # Mode A addon status
        if assets.get("mode_a_path"):
            act_tag = " [当前激活]" if cur_mode == "MODE_A" else ""
            details.append(f"• 模式 A 底座: renodx-dlss.addon64 ({assets['mode_a_size_mb']} MB · ShortFuse 官方版 [默认注入]{act_tag})")
        else:
            details.append("• 模式 A 底座: <span style='color: #ef4444;'>❌ 缺失 renodx-dlss.addon64</span>")

        # Mode C addon status (GITC Uplift)
        if assets.get("mode_c_exists"):
            act_tag = " [当前激活]" if cur_mode == "MODE_C" else ""
            details.append(
                f"• 模式 C 底座: gitc-uplift.addon64 ({assets['mode_c_size_mb']} MB · "
                f"GITC Uplift 1.7.0 [全 API 通用]{act_tag})"
            )
        else:
            details.append("• 模式 C 底座: <span style='color: #ef4444;'>❌ 缺失 gitc-uplift.addon64</span>")

        # Mode B addon status (v12 / v12.5)
        if assets.get("mode_b_path"):
            act_tag = " [当前激活]" if cur_mode == "MODE_B" else ""
            v_name = Path(assets["mode_b_path"]).name
            v_label = "Lecram v12.5 扩展版" if assets.get("mode_b_variant") == "v12.5" else "Lecram v12 扩展版"
            details.append(f"• 模式 B 底座: {v_name} ({assets['mode_b_size_mb']} MB · {v_label} [可选项目]{act_tag})")
        else:
            details.append("• 模式 B 底座: <span style='color: #ef4444;'>❌ 缺失 Lecram 底座</span>")
        if assets.get("mode_b_v125_exists"):
            v125_tag = " [当前激活]" if cur_mode == "MODE_B" and assets.get("mode_b_variant") == "v12.5" else ""
            details.append(f"• 模式 B v12.5 可选包: {assets['mode_b_v125_size_mb']} MB · 已就绪{v125_tag}")

        if assets["nr_50_path"]:
            details.append(f"• RTX 50 模型: nvngx_dlssnr.dll ({assets['nr_50_size_mb']} MB)")
        else:
            details.append("• RTX 50 模型: <span style='color: #ef4444;'>❌ 未检测到</span>")

        if assets["nr_20_30_40_path"]:
            details.append(f"• RTX 20/30/40 模型: nvngx_dlssnr.dll ({assets['nr_20_30_40_size_mb']} MB)")
        else:
            details.append("• RTX 20/30/40 模型: <span style='color: #ef4444;'>❌ 未检测到</span>")

        self.lbl_src_details.setText("<br>".join(details))
        self.lbl_src_details.setTextFormat(Qt.TextFormat.RichText)

    def _browse_source_dir_action(self):
        """Allows user to select a custom plugin assets folder."""
        d = QFileDialog.getExistingDirectory(
            self,
            "选择 DLSS 5 插件包所在目录",
            str(self.active_source_dir)
        )
        if d and os.path.isdir(d):
            self.active_source_dir = Path(d)
            self._refresh_plugin_assets()

    def _update_rhi_status(self):
        """Checks RHI installation/cache status using App 2 RHIInstaller."""
        found, path = self.rhi.is_installed_or_cached()
        if found:
            self.lbl_rhi_status.setText(f"🟢 已检测到 RHI ({Path(path).name})")
            self.lbl_rhi_status.setStyleSheet("color: #10b981; font-weight: bold;")
        else:
            self.lbl_rhi_status.setText("⚪ 未检测到 RHI")
            self.lbl_rhi_status.setStyleSheet("color: #64748b;")

    def _launch_rhi_action(self):
        """Launches RHI or the ModernRHIGuideDialog from App 2."""
        if not self.selected_game:
            ModernDialog.warning(self, "请先选择游戏", "请先在上方游戏列表中选择目标游戏！")
            return

        # Ensure Simplified Chinese templates
        self.rhi.ensure_rhi_chinese_templates()

        # Copy game exe to clipboard for instant Ctrl+V
        QApplication.clipboard().setText(self.selected_game.exe_path)

        # Show ModernRHIGuideDialog from App 2
        try:
            is_dark = get_global_theme() == "dark"
            dlg = ModernRHIGuideDialog(
                parent=self,
                game_info=self.selected_game,
                rhi_installer=self.rhi,
                is_dark=is_dark
            )
            dlg.exec()
        except Exception:
            # Fallback direct launch
            ok, msg = self.rhi.launch_rhi()
            if not ok:
                ModernDialog.warning(self, "启动 RHI 提示", msg)

    def _update_status_card(self):
        """Checks DLSS 5 status in current game's target directory."""
        if not self.selected_game:
            self.lbl_main_status_badge.setText("⚪ 未选择游戏")
            self.lbl_main_status_badge.setStyleSheet("color: #64748b;")
            self.lbl_stat_reshade.setText("• ReShade 渲染底座: ⚪ 未就绪")
            self.lbl_stat_addon.setText("• DLSS 5 扩展插件: ⚪ 未就绪")
            self.lbl_stat_runtime.setText("• 神经重构模型: ⚪ 未就绪")
            self.lbl_stat_hook.setText("• 运行挂钩阶段: ⚪ 未就绪")
            if hasattr(self, "btn_apply_hook"):
                self.btn_apply_hook.setEnabled(False)
            self._sync_mode_selector("MODE_A")
            return

        stat = check_game_dlss5_status(self.selected_game.target_dir)

        # 3.3 Main status badge & sync mode selector
        badge_text = stat.get("mode_status_display", "⚪ 未安装 DLSS 5 插件")
        self.lbl_main_status_badge.setText(badge_text)

        detected_mode = stat.get("detected_mode")
        if detected_mode == "MODE_C":
            self.lbl_main_status_badge.setStyleSheet("color: #7c3aed; font-weight: bold;")
            self._sync_mode_selector("MODE_C")
        elif detected_mode == "MODE_B":
            self.lbl_main_status_badge.setStyleSheet("color: #0284c7; font-weight: bold;")
            self._sync_mode_selector("MODE_B")
            if hasattr(self, "combo_mode_b_variant"):
                want_variant = "v12.5" if stat.get("mode_b_variant") == "v12.5" else "v12"
                v_idx = self.combo_mode_b_variant.findData(want_variant)
                if v_idx >= 0:
                    self.combo_mode_b_variant.blockSignals(True)
                    self.combo_mode_b_variant.setCurrentIndex(v_idx)
                    self.combo_mode_b_variant.blockSignals(False)
                self.combo_mode_b_variant.setVisible(True)
        elif detected_mode == "MODE_A":
            if stat.get("is_legacy"):
                self.lbl_main_status_badge.setStyleSheet("color: #f59e0b; font-weight: bold;")
            else:
                self.lbl_main_status_badge.setStyleSheet("color: #10b981; font-weight: bold;")
            self._sync_mode_selector("MODE_A")
        else:
            self.lbl_main_status_badge.setStyleSheet("color: #64748b;")
            self._sync_mode_selector("MODE_A")

        if stat["has_reshade"]:
            active_p = stat.get("active_proxy") or "dxgi.dll"
            self.lbl_stat_reshade.setText(f"• ReShade 渲染底座: 🟢 已就绪 ({active_p})")
            self.lbl_stat_reshade.setStyleSheet("color: #10b981;")
        else:
            self.lbl_stat_reshade.setText("• ReShade 渲染底座: ⚪ 未检测到")
            self.lbl_stat_reshade.setStyleSheet("color: #64748b;")

        cur_proxy_sel = self.combo_proxy_slot.currentData() if hasattr(self, "combo_proxy_slot") else "auto"
        if cur_proxy_sel == "auto":
            self._update_proxy_hint("auto")

        if stat["has_addon"]:
            names = ", ".join(stat["addon_names"])
            if detected_mode == "MODE_C":
                self.lbl_stat_addon.setText(f"• DLSS 5 扩展插件: 🟣 已就绪 ({names} · 模式 C · GITC Uplift)")
                self.lbl_stat_addon.setStyleSheet("color: #7c3aed;")
            elif detected_mode == "MODE_B":
                self.lbl_stat_addon.setText(f"• DLSS 5 扩展插件: 🔵 已就绪 ({names} · 模式 B)")
                self.lbl_stat_addon.setStyleSheet("color: #0284c7;")
            else:
                self.lbl_stat_addon.setText(f"• DLSS 5 扩展插件: 🟢 已就绪 ({names} · 模式 A)")
                self.lbl_stat_addon.setStyleSheet("color: #10b981;")
        else:
            self.lbl_stat_addon.setText("• DLSS 5 扩展插件: ⚪ 未检测到")
            self.lbl_stat_addon.setStyleSheet("color: #64748b;")

        if stat["has_runtime"]:
            arch_str = f" · {stat['detected_arch']}" if stat["detected_arch"] != "unknown" else ""
            self.lbl_stat_runtime.setText(f"• 神经重构模型: 🟢 已就绪 ({stat['runtime_size_mb']} MB{arch_str})")
            self.lbl_stat_runtime.setStyleSheet("color: #10b981;")
        else:
            self.lbl_stat_runtime.setText("• 神经重构模型: ⚪ 未检测到")
            self.lbl_stat_runtime.setStyleSheet("color: #64748b;")

        # Hook Point Status & Sync
        if stat["is_injected"]:
            self.lbl_stat_hook.setText(f"• 运行挂钩阶段: 🟢 {stat.get('hook_point_label', '之后 (Upscaled)')}")
            self.lbl_stat_hook.setStyleSheet("color: #10b981;")
            if hasattr(self, "btn_apply_hook"):
                self.btn_apply_hook.setEnabled(True)
        else:
            self.lbl_stat_hook.setText("• 运行挂钩阶段: ⚪ 未就绪 (注入时将应用所选配置)")
            self.lbl_stat_hook.setStyleSheet("color: #64748b;")
            if hasattr(self, "btn_apply_hook"):
                self.btn_apply_hook.setEnabled(False)

        if hasattr(self, "combo_hook_point"):
            cur_hook = stat.get("hook_point", "0")
            self.combo_hook_point.blockSignals(True)
            idx = self.combo_hook_point.findData(cur_hook)
            if idx >= 0:
                self.combo_hook_point.setCurrentIndex(idx)
            self.combo_hook_point.blockSignals(False)

    def _update_all_states(self):
        self._update_rhi_status()
        self._update_status_card()

    # -----------------------------------------------------------------
    # Primary Actions: Inject & Restore
    # -----------------------------------------------------------------
    def _apply_hook_mode_action(self):
        """Immediately applies selected hook point to the game without launching it."""
        if not self.selected_game:
            ModernDialog.warning(self, "未选择游戏", "请先在上方游戏列表中选择目标游戏！")
            return

        stat = check_game_dlss5_status(self.selected_game.target_dir)
        if not stat["is_injected"] and not (Path(self.selected_game.target_dir) / "ReShade.ini").exists():
            ModernDialog.warning(self, "游戏尚未注入", "当前游戏尚未注入 DLSS 5，请先点击下方的【一键注入 DLSS 5 插件】！")
            return

        chosen_hook = self.combo_hook_point.currentData() if hasattr(self, "combo_hook_point") else "0"
        self.set_status("正在修改游戏 DLSS 5 挂钩阶段模式...")
        QApplication.processEvents()

        ok, msg = DLSS5Injector.apply_hook_point(self.selected_game.target_dir, chosen_hook)
        self._update_status_card()
        self.set_status("挂钩模式修改完成" if ok else "修改失败")

        if ok:
            ModernDialog.success(self, "挂钩模式已更新", msg)
        else:
            ModernDialog.error(self, "修改失败", msg)

    def _inject_action(self):
        """Executes DLSS 5 one-click injection."""
        if not self.selected_game:
            ModernDialog.warning(self, "未选择游戏", "请先在上方下拉框中选择要注入的目标游戏！")
            return

        # Architecture choice
        if self.rb_auto.isChecked():
            arch_choice = "auto"
        elif self.rb_40.isChecked():
            arch_choice = "rtx20_30_40"
        else:
            arch_choice = "rtx50"

        chosen_hook = self.combo_hook_point.currentData() if hasattr(self, "combo_hook_point") else "0"
        chosen_mode = self.combo_dlss5_mode.currentData() if hasattr(self, "combo_dlss5_mode") else "MODE_A"
        if not chosen_mode:
            chosen_mode = "MODE_A"
        chosen_proxy = self.combo_proxy_slot.currentData() if hasattr(self, "combo_proxy_slot") else "auto"
        if not chosen_proxy:
            chosen_proxy = "auto"

        self.set_status("正在将 DLSS 5 插件及模型部署至游戏目录...")
        QApplication.processEvents()

        # If already monitoring, user clicked cancel
        if self.monitor_worker and self.monitor_worker.isRunning():
            self.monitor_worker.stop()
            self.monitor_worker.wait(2000)
            self.monitor_worker = None
            self.set_status("已停止游戏启动监听。")
            self._update_inject_button_text()
            return

        nr_guard, nr_margin = self._nr_vram_values()
        ok, msg = DLSS5Injector.inject(
            target_dir=self.selected_game.target_dir,
            source_dir=str(self.active_source_dir),
            arch_choice=arch_choice,
            hook_point=chosen_hook,
            mode=chosen_mode,
            proxy_choice=chosen_proxy,
            nr_vram_guard=nr_guard,
            nr_vram_margin=nr_margin,
            mode_b_variant=(
                self.combo_mode_b_variant.currentData() or "v12.5"
                if hasattr(self, "combo_mode_b_variant") else "v12.5"
            ),
        )

        self._update_status_card()
        if not ok:
            self.set_status("注入失败")
            ModernDialog.error(self, "注入遇到问题", msg)
            return

        mode_tag = {
            "MODE_A": "模式 A: renodx-dlss.addon64",
            "MODE_B": "模式 B: Lecram v12 / v12.5",
            "MODE_C": "模式 C: GITC Uplift",
        }.get(chosen_mode, chosen_mode)

        # Check if we should activate delayed injection monitor
        stat = check_game_dlss5_status(self.selected_game.target_dir)
        actual_proxy = stat.get("active_proxy") or chosen_proxy
        is_delayed_proxy = (actual_proxy.lower() == "reshade64.dll")

        if is_delayed_proxy:
            reshade_path = str(Path(self.selected_game.target_dir) / "ReShade64.dll")
            self.monitor_worker = DLSS5MonitorWorker(self.selected_game.exe_name, reshade_path, parent=self)
            self.monitor_worker.sig_status.connect(lambda text_msg, color: self.set_status(text_msg))
            self.monitor_worker.sig_finished.connect(self._on_delayed_injection_finished)
            self.monitor_worker.start()
            self._update_inject_button_text()

            self.set_status(f"文件已就绪！正在监听 {self.selected_game.exe_name} 启动... 请从官方启动器开始游戏")
            ModernDialog.info(
                self,
                "启动监听已激活",
                f"✅ DLSS 5 底座与模型已成功部署至游戏目录！\n\n"
                f"🛡️ 【免落地延时挂载已就绪】\n"
                f"• 游戏目录未放置任何敏感系统代理 DLL，已 100% 避开启动器与 ACE 反作弊的前置扫描；\n"
                f"• 请直接打开【鹰角启动器】点击【开始游戏】！\n\n"
                f"本工具将在检测到游戏窗口初始化完成后，自动将 ReShade64.dll 延时注入进主进程，期间请保持本工具在后台运行。"
            )
        else:
            self.set_status(f"注入成功！已部署 [{mode_tag}]")
            ModernDialog.success(self, "注入成功", msg)


    def _on_delayed_injection_finished(self, ok: bool, msg: str):
        """Callback when delayed injection monitor completes or times out."""
        self.monitor_worker = None
        self._update_inject_button_text()
        self._update_status_card()
        if ok:
            self.set_status("🎉 延时注入完成！游戏内按 Home / F12 即可畅享神经重构！")
            ModernDialog.success(self, "DLSS 5 延时注入成功", msg)
        else:
            self.set_status("启动监听结束")
            ModernDialog.warning(self, "启动监听提示", msg)

    def _restore_action(self):
        """Executes DLSS 5 one-click restore/uninstall."""
        if self.monitor_worker and self.monitor_worker.isRunning():
            self.monitor_worker.stop()
            self.monitor_worker.wait(2000)
            self.monitor_worker = None
            self._update_inject_button_text()

        if not self.selected_game:
            ModernDialog.warning(self, "未选择游戏", "请先在上方下拉框中选择要还原的目标游戏！")
            return

        stat = check_game_dlss5_status(self.selected_game.target_dir)
        if not stat["is_injected"]:
            confirmed = ModernDialog.confirm(
                self,
                "清理确认",
                f"当前游戏目录未检测到 DLSS 5 注入记录，是否仍对该目录执行深度清理以清除可能的 DLL 残留？\n\n目录: {self.selected_game.target_dir}"
            )
            if not confirmed:
                return
        else:
            confirmed = ModernDialog.confirm(
                self,
                "卸载确认",
                f"确定要从当前游戏目录卸载 DLSS 5 插件并还原原始文件吗？\n\n游戏: {self.selected_game.name}\n目录: {self.selected_game.target_dir}"
            )
            if not confirmed:
                return

        self.set_status("正在卸载 DLSS 5 插件并还原游戏目录...")
        QApplication.processEvents()

        ok, msg = DLSS5Injector.restore(self.selected_game.target_dir)
        # Phase 3.4 & Phase 4: Reset mode selector to default MODE_A
        self._sync_mode_selector("MODE_A")
        if hasattr(self, "combo_mode_b_variant"):
            _v125 = self.combo_mode_b_variant.findData("v12.5")
            if _v125 >= 0:
                self.combo_mode_b_variant.blockSignals(True)
                self.combo_mode_b_variant.setCurrentIndex(_v125)
                self.combo_mode_b_variant.blockSignals(False)
            self.combo_mode_b_variant.setVisible(False)
        self._sync_proxy_selector("auto")
        self._update_status_card()
        self._refresh_plugin_assets()
        self.set_status("还原完成" if ok else "还原遇到问题")

        if ok:
            ModernDialog.info(self, "卸载与还原完成", msg)
        else:
            ModernDialog.warning(self, "还原遇到问题", msg)

    # -----------------------------------------------------------------
    # Theme Switching
    # -----------------------------------------------------------------
    def _on_theme_changed(self, theme_name: str):
        self._apply_theme_styles(theme_name == "dark")

    def _apply_theme_styles(self, is_dark: bool):
        try:
            apply_dm_window_frame(self, is_dark)
        except Exception:
            pass

        has_wp = bool(getattr(self, "wallpaper_pixmap", None) and not self.wallpaper_pixmap.isNull() and getattr(self, "wallpaper_config", {}).get("enabled", False))
        card_op = max(0.50, float(getattr(self, "wallpaper_config", {}).get("card_opacity", 0.86)))

        if hasattr(self, "card_game"):
            self.card_game.apply_theme(is_dark, wallpaper_active=has_wp, card_opacity=card_op)
        if hasattr(self, "card_rhi"):
            self.card_rhi.apply_theme(is_dark, wallpaper_active=has_wp, card_opacity=card_op)
        if hasattr(self, "card_plugin"):
            self.card_plugin.apply_theme(is_dark, wallpaper_active=has_wp, card_opacity=card_op)
        if hasattr(self, "card_hook"):
            self.card_hook.apply_theme(is_dark, wallpaper_active=has_wp, card_opacity=card_op)
        if hasattr(self, "card_status"):
            self.card_status.apply_theme(is_dark, wallpaper_active=has_wp, card_opacity=card_op)

        if hasattr(self, "scroll") and self.scroll:
            scrollbar_qss = SCROLLBAR_DARK_QSS if is_dark else SCROLLBAR_LIGHT_QSS
            if has_wp:
                self.scroll.setStyleSheet(scrollbar_qss + "\nQScrollArea, QScrollArea > QWidget { background: transparent; border: none; }")
                self.scroll.viewport().setStyleSheet("background: transparent;")
                if self.scroll.widget():
                    self.scroll.widget().setStyleSheet("background: transparent;")
            else:
                self.scroll.setStyleSheet(scrollbar_qss)

        bg = "transparent" if has_wp else ("#18181b" if is_dark else "#f4f6f9")
        card_bg = (f"rgba(26, 28, 36, {card_op:.2f})" if is_dark else f"rgba(255, 255, 255, {card_op:.2f})") if has_wp else ("#27272a" if is_dark else "#ffffff")
        text_color = "#F9FAFB" if is_dark else "#111827"
        border_color = "rgba(255, 255, 255, 0.12)" if is_dark else "rgba(0, 0, 0, 0.08)"
        sub_text_color = "#CBD5E1" if is_dark else "#374151"

        if hasattr(self, "game_info_frame"):
            self.game_info_frame.setStyleSheet(f"""
                QFrame {{
                    background: {'rgba(255, 255, 255, 0.08)' if is_dark else 'rgba(0, 0, 0, 0.04)'};
                    border: 1px solid {border_color};
                    border-radius: 8px;
                }}
            """)

        self.central_widget.setStyleSheet(f"""
            QWidget#RootContainer {{
                background-color: {bg};
            }}
            QScrollArea, QScrollArea > QWidget, QScrollArea QWidget, QWidget#DLSS5ScrollContainer {{
                background: transparent;
                background-color: transparent;
            }}
            #dlss5_head_title {{
                color: {text_color};
            }}
            #dlss5_sub_title {{
                color: {sub_text_color};
            }}
            QComboBox {{
                background-color: {card_bg};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 4px 10px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {card_bg};
                color: {text_color};
                selection-background-color: {'#3f3f46' if is_dark else '#e2e8f0'};
            }}
            QLineEdit {{
                background-color: {card_bg};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 4px 8px;
            }}
            QPushButton {{
                background-color: {card_bg};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 4px 12px;
            }}
            QPushButton:hover {{
                background-color: {'#3f3f46' if is_dark else '#f1f5f9'};
            }}
            QRadioButton {{
                color: {text_color};
                spacing: 6px;
            }}
            QLabel {{
                color: {text_color};
            }}
        """)


def main():
    app = QApplication(sys.argv)
    from common.ui_theme import install_combo_arrows
    install_combo_arrows(app)

    app_font = QFont("Microsoft YaHei UI", 10)
    app_font.setStyleStrategy(QFont.PreferAntialias | QFont.PreferQuality)
    app.setFont(app_font)

    win = DLSS5MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
