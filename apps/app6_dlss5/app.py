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

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QIcon, QFont, QPixmap, QColor, QCursor, QGuiApplication
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QComboBox, QLineEdit,
    QFileDialog, QRadioButton, QButtonGroup, QSizePolicy,
    QSpacerItem
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
    scan_plugin_source_assets, get_plugin_source_dir
)
from common.config_manager import get_real_gpu_info


def _soft_wrap_path(text: str) -> str:
    """
    Insert zero-width spaces after path separators so a long Windows path can
    wrap inside a QLabel instead of forcing the whole window wider.
    """
    return text.replace("\\", "\\\u200b")


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

        # Shared backend helpers from App 2
        self.rhi = RHIInstaller()
        self.scanner = GameScanner()
        self.gpu_info = get_real_gpu_info()

        self.games_list: List[GameInfo] = []
        self.selected_game: Optional[GameInfo] = None
        self.active_source_dir: Path = get_plugin_source_dir()

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

    def _init_ui(self):
        # Create a smooth scroll area inside body_layout
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        is_dark = get_global_theme() == "dark"
        scroll.setStyleSheet(SCROLLBAR_DARK_QSS if is_dark else SCROLLBAR_LIGHT_QSS)

        container = QWidget()
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

        lbl_sub = QLabel("搭载 RenoDX DLSS 5 v11.9 旗舰版 (renodx-dlss5-v11.9.addon64) · 共用二号软件游戏库与 RHI 底座 · 自动兼容模式 A/B/C/D 多帧生成共存")
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
            "💡 提示：本一键注入包已内置 ReShade 6.8 完整 Add-on 底座 (dxgi.dll)，通常直接点击下方【一键注入 DLSS 5】即可；"
            "若游戏需要其他渲染 API (如 Vulkan) 或想手动管理着色器，可通过 RHI 程序为游戏安装 ReShade 底座。"
        )
        lbl_rhi_desc.setFont(QFont("Microsoft YaHei UI", 9))
        lbl_rhi_desc.setWordWrap(True)
        lbl_rhi_desc.setStyleSheet("color: gray;")
        card_rhi_layout.addWidget(lbl_rhi_desc)

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
        self.content_layout.addWidget(self.card_plugin)

        # -------------------------------------------------------------
        # Card 4: 📊 当前游戏 DLSS 5 注入状态
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
        for lbl in [self.lbl_stat_reshade, self.lbl_stat_addon, self.lbl_stat_runtime]:
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

    def _refresh_plugin_assets(self):
        """Scans plugin source directory and updates UI."""
        assets = scan_plugin_source_assets(self.active_source_dir)
        is_local = "app6_dlss5" in str(assets["source_dir"]) or "整合包" in str(assets["source_dir"])
        tag = "  [📦 整合包内置便携资产 · 全机免配置]" if is_local else ""
        self.edit_src_dir.setText(f"{assets['source_dir']}{tag}")

        details = []
        if assets["dxgi_path"]:
            details.append(f"• 渲染底座: dxgi.dll ({assets['dxgi_size_mb']} MB · ReShade 6.8 64-bit)")
        else:
            details.append("• 渲染底座: ❌ 缺失 dxgi.dll")

        if assets["addon_path"]:
            is_v119 = "11.9" in assets["addon_name"].lower()
            tag = " · v11.9 旗舰版 默认" if is_v119 else ""
            details.append(f"• 扩展插件: {assets['addon_name']} ({assets['addon_size_mb']} MB{tag})")
        else:
            details.append("• 扩展插件: ❌ 缺失 *.addon64")

        if assets["nr_50_path"]:
            details.append(f"• RTX 50 模型: nvngx_dlssnr.dll ({assets['nr_50_size_mb']} MB)")
        else:
            details.append("• RTX 50 模型: ❌ 未检测到")

        if assets["nr_20_30_40_path"]:
            details.append(f"• RTX 20/30/40 模型: nvngx_dlssnr.dll ({assets['nr_20_30_40_size_mb']} MB)")
        else:
            details.append("• RTX 20/30/40 模型: ❌ 未检测到")

        self.lbl_src_details.setText("\n".join(details))

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
            return

        stat = check_game_dlss5_status(self.selected_game.target_dir)

        if stat["is_injected"]:
            self.lbl_main_status_badge.setText("🟢 已注入 DLSS 5")
            self.lbl_main_status_badge.setStyleSheet("color: #10b981; font-weight: bold;")
        else:
            self.lbl_main_status_badge.setText("⚪ 未注入")
            self.lbl_main_status_badge.setStyleSheet("color: #64748b;")

        if stat["has_reshade"]:
            self.lbl_stat_reshade.setText("• ReShade 渲染底座: 🟢 已就绪 (dxgi.dll)")
            self.lbl_stat_reshade.setStyleSheet("color: #10b981;")
        else:
            self.lbl_stat_reshade.setText("• ReShade 渲染底座: ⚪ 未检测到")
            self.lbl_stat_reshade.setStyleSheet("color: #64748b;")

        if stat["has_addon"]:
            names = ", ".join(stat["addon_names"])
            self.lbl_stat_addon.setText(f"• DLSS 5 扩展插件: 🟢 已就绪 ({names})")
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

    def _update_all_states(self):
        self._update_rhi_status()
        self._update_status_card()

    # -----------------------------------------------------------------
    # Primary Actions: Inject & Restore
    # -----------------------------------------------------------------
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

        self.set_status("正在将 DLSS 5 插件及模型部署至游戏目录...")
        QApplication.processEvents()

        ok, msg = DLSS5Injector.inject(
            target_dir=self.selected_game.target_dir,
            source_dir=str(self.active_source_dir),
            arch_choice=arch_choice
        )

        self._update_status_card()
        self.set_status("注入完成" if ok else "注入失败")

        if ok:
            ModernDialog.success(self, "注入成功", msg)
        else:
            ModernDialog.error(self, "注入遇到问题", msg)

    def _restore_action(self):
        """Executes DLSS 5 one-click restore/uninstall."""
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
        self._update_status_card()
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

        if hasattr(self, "card_game"):
            self.card_game.apply_theme(is_dark)
        if hasattr(self, "card_rhi"):
            self.card_rhi.apply_theme(is_dark)
        if hasattr(self, "card_plugin"):
            self.card_plugin.apply_theme(is_dark)
        if hasattr(self, "card_status"):
            self.card_status.apply_theme(is_dark)

        bg = "#18181b" if is_dark else "#f4f6f9"
        card_bg = "#27272a" if is_dark else "#ffffff"
        text_color = "#f4f4f5" if is_dark else "#1e293b"
        border_color = "#3f3f46" if is_dark else "#cbd5e1"
        sub_text_color = "#a1a1aa" if is_dark else "#64748b"

        if hasattr(self, "game_info_frame"):
            self.game_info_frame.setStyleSheet(f"""
                QFrame {{
                    background: {'rgba(255, 255, 255, 0.05)' if is_dark else 'rgba(0, 0, 0, 0.04)'};
                    border: 1px solid {border_color};
                    border-radius: 8px;
                }}
            """)

        self.central_widget.setStyleSheet(f"""
            QWidget#RootContainer {{
                background-color: {bg};
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
