# -*- coding: utf-8 -*-
"""
App 6: DLSS 5 神经重构与画质注入器 (DLSS 5 Neural Reconstruction Injector)
========================================================================
集成最新 lecram DLSS 5 神经网络渲染插件 (DLSS 5 NR Addon)，
支持一键注入至游戏根目录，附带 ReShade / RHI 运行底座与多帧生成 (插帧) 冲突智能避让。

UI 规范：
- 严格遵循 DMBaseWindow (DM Design System Core SDK)
- 完美契合 Windows DWM 硬件级无锯齿圆角抗锯齿合成 (DWMWCP_ROUND=2)
- 适配标准 DMSizeGrip (//) 缩放手柄与实时主题同步
- 状态四分格监测：DLSS 5 状态、插帧状态、ReShade底座、智能避让判定
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

from PySide6.QtCore import Qt, QTimer, QSize, QThread, Signal
from PySide6.QtGui import QIcon, QFont, QPixmap, QColor
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QMessageBox, QGridLayout,
    QComboBox, QLineEdit, QFileDialog, QSizePolicy
)

# Root dir resolution
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# App 2 for GameScanner import
MFG_DIR = ROOT_DIR / "apps" / "app2_mfg"
if str(MFG_DIR) not in sys.path:
    sys.path.insert(0, str(MFG_DIR))

from dm_ui_core import (
    DMBaseWindow, DMCardFrame, DMFooterBar, DMSizeGrip, DMThemeManager,
    apply_dm_window_frame, get_global_theme, set_global_theme,
    SCROLLBAR_LIGHT_QSS, SCROLLBAR_DARK_QSS
)
from common.ui_theme import ModernProgressDialog, ModernConfirmDialog
from apps.app6_dlss5.core.injector import (
    DLSS5Injector, check_dlss5_status, detect_frame_generation,
    find_rhi_setup_exe, get_dlss5_addon_path, find_reshade_framework_dll
)

APP_DIR = Path(__file__).resolve().parent
ASSETS_DIR = APP_DIR / "assets"


class GameScanWorker(QThread):
    """Background worker to scan all logical drives and registries without freezing UI."""
    games_found = Signal(list)

    def run(self):
        try:
            from apps.app2_mfg.core.scanner import GameScanner
            scanner = GameScanner()
            games = scanner.scan_all_libraries()
            self.games_found.emit(games)
        except Exception as e:
            self.games_found.emit([])


class StatusBlock(QFrame):
    """Reusable mini-card block for 4-quadrant status monitor."""
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("StatusBlock")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #64748B;")
        layout.addWidget(self.lbl_title)

        self.lbl_val = QLabel("⚪ 检测中...")
        self.lbl_val.setStyleSheet("font-size: 13px; font-weight: 600; color: #1E293B;")
        self.lbl_val.setWordWrap(True)
        layout.addWidget(self.lbl_val)

        self.lbl_sub = QLabel("")
        self.lbl_sub.setStyleSheet("font-size: 11px; color: #94A3B8;")
        self.lbl_sub.setWordWrap(True)
        layout.addWidget(self.lbl_sub)

    def set_status(self, val_text: str, val_color: str, sub_text: str = ""):
        self.lbl_val.setText(val_text)
        self.lbl_val.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {val_color};")
        self.lbl_sub.setText(sub_text)
        self.lbl_sub.setVisible(bool(sub_text))

    def apply_theme(self, is_dark: bool):
        bg = "#1E2022" if is_dark else "#F8FAFC"
        border = "#334155" if is_dark else "#E2E8F0"
        title_c = "#94A3B8" if is_dark else "#64748B"
        self.setStyleSheet(f"""
            QFrame#StatusBlock {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
        """)
        self.lbl_title.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {title_c};")


class DLSS5Window(DMBaseWindow):
    """DLSS 5 神经重构与画质注入器主窗口。"""

    def __init__(self):
        super().__init__(
            title="DM工具箱 - DLSS 5 神经重构与画质注入器",
            width=960,
            height=720,
            icon_filename="dlss5_icon.png"
        )
        self.setMinimumSize(880, 620)
        self.resize(960, 720)

        self.games_list: List[Any] = []
        self.current_game_info: Optional[Dict[str, Any]] = None
        self.scan_worker: Optional[GameScanWorker] = None

        self.init_content()
        self.apply_theme()
        QTimer.singleShot(150, self.start_background_scan)

        # Status check timer
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(2000)
        self.poll_timer.timeout.connect(self.refresh_current_game_status)
        self.poll_timer.start()

    def closeEvent(self, event):
        if hasattr(self, "poll_timer") and self.poll_timer.isActive():
            self.poll_timer.stop()
        if hasattr(self, "scan_worker") and self.scan_worker and self.scan_worker.isRunning():
            self.scan_worker.quit()
        super().closeEvent(event)

    def init_content(self):
        # Scroll area for clean layout
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content_widget = QWidget()
        vbox = QVBoxLayout(content_widget)
        vbox.setContentsMargins(24, 18, 24, 18)
        vbox.setSpacing(16)

        # ------------------ 1. BANNER CARD ------------------
        banner = DMCardFrame()
        b_layout = QHBoxLayout(banner)
        b_layout.setContentsMargins(20, 16, 20, 16)
        b_layout.setSpacing(16)

        # Icon
        self.banner_icon = QLabel()
        self.banner_icon.setFixedSize(54, 54)
        icon_path = ASSETS_DIR / "dlss5_icon.png"
        if not icon_path.exists():
            icon_path = ROOT_DIR / "common" / "assets" / "dlss5_icon.png"
        if icon_path.exists():
            pix = QPixmap(str(icon_path)).scaled(54, 54, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.banner_icon.setPixmap(pix)
        b_layout.addWidget(self.banner_icon)

        # Text
        b_text_box = QVBoxLayout()
        b_text_box.setSpacing(4)

        t_row = QHBoxLayout()
        t_row.setSpacing(10)
        self.banner_title = QLabel("DLSS 5 神经重构与画质注入器")
        self.banner_title.setProperty("class", "CardTitle")
        self.banner_title.setStyleSheet("font-size: 18px; font-weight: 800;")
        t_row.addWidget(self.banner_title)

        self.badge_ver = QLabel("v1.0.0 · 智能避让版")
        self.badge_ver.setStyleSheet("""
            background-color: #10B981;
            color: #FFFFFF;
            font-size: 11px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 6px;
        """)
        t_row.addWidget(self.badge_ver)
        t_row.addStretch()
        b_text_box.addLayout(t_row)

        self.banner_desc = QLabel(
            "集成最新 lecram DLSS 5 神经网络重建插件 (DLSS 5 NR Addon)，"
            "为支持 DLSS 的游戏注入下一代神经网络画质引擎，内建 ReShade/RHI 运行底座，并与多帧生成补丁智能避让共存。"
        )
        self.banner_desc.setStyleSheet("font-size: 12px; color: #64748B;")
        self.banner_desc.setWordWrap(True)
        b_text_box.addWidget(self.banner_desc)

        b_layout.addLayout(b_text_box, 1)
        vbox.addWidget(banner)

        # ------------------ 2. GAME SELECTION & STATUS CARD ------------------
        self.game_card = DMCardFrame()
        g_layout = QVBoxLayout(self.game_card)
        g_layout.setContentsMargins(20, 16, 20, 16)
        g_layout.setSpacing(14)

        # Title row
        g_header = QHBoxLayout()
        lbl_g_title = QLabel("🎮 目标游戏与运行环境监测")
        lbl_g_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        g_header.addWidget(lbl_g_title)
        g_header.addStretch()

        self.lbl_scan_status = QLabel("正在扫描本地游戏库...")
        self.lbl_scan_status.setStyleSheet("font-size: 12px; color: #64748B;")
        g_header.addWidget(self.lbl_scan_status)
        g_layout.addLayout(g_header)

        # Selector row
        sel_row = QHBoxLayout()
        sel_row.setSpacing(10)

        self.combo_games = QComboBox()
        self.combo_games.setMinimumHeight(38)
        self.combo_games.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.combo_games.currentIndexChanged.connect(self.on_game_selected)
        sel_row.addWidget(self.combo_games, 1)

        self.btn_browse = QPushButton("➕ 手动选择游戏 (.exe)")
        self.btn_browse.setProperty("class", "PrimaryBtn")
        self.btn_browse.setMinimumHeight(38)
        self.btn_browse.setCursor(Qt.PointingHandCursor)
        self.btn_browse.clicked.connect(self.on_browse_game)
        sel_row.addWidget(self.btn_browse)

        self.btn_rescan = QPushButton("🔄 重新扫描")
        self.btn_rescan.setProperty("class", "OutlineBtn")
        self.btn_rescan.setMinimumHeight(38)
        self.btn_rescan.setCursor(Qt.PointingHandCursor)
        self.btn_rescan.clicked.connect(self.start_background_scan)
        sel_row.addWidget(self.btn_rescan)

        g_layout.addLayout(sel_row)

        # Path display
        self.lbl_current_path = QLabel("📁 当前目标目录: 未选择游戏")
        self.lbl_current_path.setStyleSheet("font-size: 11px; color: #94A3B8; font-family: Consolas, monospace;")
        self.lbl_current_path.setWordWrap(True)
        g_layout.addWidget(self.lbl_current_path)

        # 4-Quadrant Status Grid
        status_grid = QGridLayout()
        status_grid.setSpacing(10)

        self.block_dlss5 = StatusBlock("DLSS 5 插件状态")
        status_grid.addWidget(self.block_dlss5, 0, 0)

        self.block_fg = StatusBlock("多帧生成 (插帧) 状态")
        status_grid.addWidget(self.block_fg, 0, 1)

        self.block_reshade = StatusBlock("ReShade / RHI 运行宿主")
        status_grid.addWidget(self.block_reshade, 1, 0)

        self.block_avoidance = StatusBlock("智能冲突避让判定")
        status_grid.addWidget(self.block_avoidance, 1, 1)

        g_layout.addLayout(status_grid)

        # Co-existence banner alert
        self.alert_box = QFrame()
        self.alert_box.setObjectName("AlertBox")
        alert_layout = QHBoxLayout(self.alert_box)
        alert_layout.setContentsMargins(14, 10, 14, 10)
        alert_layout.setSpacing(10)

        self.lbl_alert_icon = QLabel("🛡️")
        self.lbl_alert_icon.setStyleSheet("font-size: 18px;")
        alert_layout.addWidget(self.lbl_alert_icon)

        self.lbl_alert_text = QLabel(
            "插帧避让提示：当游戏已注入多帧生成 (RenoDX/OptiScaler) 时，DLSS 5 将自动共用现有底座，免重复注入与冲突。"
        )
        self.lbl_alert_text.setStyleSheet("font-size: 12px; font-weight: 600;")
        self.lbl_alert_text.setWordWrap(True)
        alert_layout.addWidget(self.lbl_alert_text, 1)

        g_layout.addWidget(self.alert_box)
        vbox.addWidget(self.game_card)

        # ------------------ 3. ACTION CENTER CARD ------------------
        self.action_card = DMCardFrame()
        act_layout = QVBoxLayout(self.action_card)
        act_layout.setContentsMargins(20, 16, 20, 16)
        act_layout.setSpacing(14)

        lbl_act_title = QLabel("⚡ 一键操作中心")
        lbl_act_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        act_layout.addWidget(lbl_act_title)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.btn_inject = QPushButton("⚡ 一键注入 DLSS 5")
        self.btn_inject.setProperty("class", "PrimaryBtn")
        self.btn_inject.setMinimumHeight(44)
        self.btn_inject.setCursor(Qt.PointingHandCursor)
        self.btn_inject.setStyleSheet("font-size: 14px; font-weight: 700;")
        self.btn_inject.clicked.connect(self.on_inject_dlss5)
        btn_row.addWidget(self.btn_inject, 2)

        self.btn_restore = QPushButton("🔄 一键还原 / 卸载")
        self.btn_restore.setProperty("class", "OutlineBtn")
        self.btn_restore.setMinimumHeight(44)
        self.btn_restore.setCursor(Qt.PointingHandCursor)
        self.btn_restore.setStyleSheet("font-size: 13px; font-weight: 600;")
        self.btn_restore.clicked.connect(self.on_restore_dlss5)
        btn_row.addWidget(self.btn_restore, 1)

        self.btn_rhi = QPushButton("🛠️ 启动 / 管理 RHI 底座")
        self.btn_rhi.setProperty("class", "SecondaryBtn")
        self.btn_rhi.setMinimumHeight(44)
        self.btn_rhi.setCursor(Qt.PointingHandCursor)
        self.btn_rhi.setStyleSheet("font-size: 13px; font-weight: 600;")
        self.btn_rhi.clicked.connect(self.on_launch_rhi)
        btn_row.addWidget(self.btn_rhi, 1)

        self.btn_open_dir = QPushButton("📂 打开游戏目录")
        self.btn_open_dir.setProperty("class", "SecondaryBtn")
        self.btn_open_dir.setMinimumHeight(44)
        self.btn_open_dir.setCursor(Qt.PointingHandCursor)
        self.btn_open_dir.setStyleSheet("font-size: 13px;")
        self.btn_open_dir.clicked.connect(self.on_open_game_dir)
        btn_row.addWidget(self.btn_open_dir, 1)

        act_layout.addLayout(btn_row)
        vbox.addWidget(self.action_card)

        # ------------------ 4. GUIDELINES & PRINCIPLE CARD ------------------
        self.guide_card = DMCardFrame()
        guide_layout = QVBoxLayout(self.guide_card)
        guide_layout.setContentsMargins(20, 16, 20, 16)
        guide_layout.setSpacing(10)

        lbl_guide_title = QLabel("💡 DLSS 5 神经重构使用指南与技术说明")
        lbl_guide_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        guide_layout.addWidget(lbl_guide_title)

        tips_text = (
            "<b>1. 游戏内热键与调校</b>：<br>"
            "启动游戏后，在游戏画面中按键盘 <code>【Home】</code> 键即可唤出 ReShade 叠加控制台。在 <code>【Add-ons】</code> 标签页中可查看已挂载的 <b>lecram-dlss5-beta10</b> 神经重构插件及其运行状态。<br><br>"
            "<b>2. 多帧生成 (插帧) 避让共存机制</b>：<br>"
            "• DLSS 5 插件与多帧生成补丁 (RenoDX / OptiScaler) 均依托底层 <code>dxgi.dll</code> (ReShade 64-bit Add-on 宿主) 运行。<br>"
            "• 若目标游戏已通过「应用2：DLSS多帧生成补丁」完成注入，本程序会自动激活<b>【插帧避让】</b>，跳过底座部署，直接将 DLSS 5 并联挂载至现有 <code>ReShade.ini</code>，两套插件在同一进程中协同工作，零冲突、免二次安装。<br>"
            "• 还原时同样具备防误删保护：仅移除 DLSS 5 插件，完整保留多帧生成环境。<br><br>"
            "<b>3. 硬件与环境兼容性</b>：<br>"
            "支持 NVIDIA GeForce RTX 20 / 30 / 40 / 50 全系列显卡。请确保游戏画面设置中已开启 DLSS 超分辨率技术。"
        )
        lbl_tips = QLabel(tips_text)
        lbl_tips.setStyleSheet("font-size: 12px; color: #64748B; line-height: 150%;")
        lbl_tips.setWordWrap(True)
        lbl_tips.setTextFormat(Qt.RichText)
        guide_layout.addWidget(lbl_tips)

        vbox.addWidget(self.guide_card)

        vbox.addStretch()
        self.scroll_area.setWidget(content_widget)
        self.body_layout.addWidget(self.scroll_area)

    def start_background_scan(self):
        """Starts background game library scan."""
        self.lbl_scan_status.setText("⏳ 正在快速扫描本地已安装游戏...")
        self.btn_rescan.setEnabled(False)

        self.scan_worker = GameScanWorker()
        self.scan_worker.games_found.connect(self.on_scan_completed)
        self.scan_worker.start()

    def on_scan_completed(self, games: list):
        """Populates game dropdown once scan completes."""
        self.games_list = games
        self.btn_rescan.setEnabled(True)
        self.lbl_scan_status.setText(f"✅ 扫描完成，共识别 {len(games)} 款游戏")

        self.combo_games.blockSignals(True)
        self.combo_games.clear()

        if not games:
            self.combo_games.addItem("未发现已安装游戏 (请点击右侧手动选择)", "")
        else:
            for g in games:
                name = getattr(g, "name", "未知游戏")
                exe = getattr(g, "primary_executable", "")
                p_dir = getattr(g, "target_dir", getattr(g, "install_dir", ""))
                display_text = f"{name} ({exe})" if exe else name
                self.combo_games.addItem(display_text, {
                    "name": name,
                    "target_dir": str(p_dir),
                    "exe": str(exe)
                })

        self.combo_games.blockSignals(False)

        if games:
            self.combo_games.setCurrentIndex(0)
            self.on_game_selected(0)
        else:
            self.refresh_current_game_status()

    def on_browse_game(self):
        """Opens file dialog for user to manually select a game executable."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择游戏主程序 (DirectX 11 / 12 可执行文件)",
            "",
            "游戏可执行文件 (*.exe);;所有文件 (*.*)"
        )
        if not file_path:
            return

        p = Path(file_path).resolve()
        target_dir = p.parent
        exe_name = p.name
        game_name = p.stem

        custom_data = {
            "name": f"{game_name} (自定义添加)",
            "target_dir": str(target_dir),
            "exe": exe_name
        }

        # Check if already in combo
        idx = -1
        for i in range(self.combo_games.count()):
            d = self.combo_games.itemData(i)
            if isinstance(d, dict) and d.get("target_dir", "").lower() == str(target_dir).lower():
                idx = i
                break

        if idx >= 0:
            self.combo_games.setCurrentIndex(idx)
        else:
            self.combo_games.addItem(f"📁 {game_name} ({exe_name})", custom_data)
            self.combo_games.setCurrentIndex(self.combo_games.count() - 1)

    def on_game_selected(self, index: int):
        data = self.combo_games.itemData(index)
        if isinstance(data, dict):
            self.current_game_info = data
            self.lbl_current_path.setText(f"📁 当前目标目录: {data.get('target_dir', '')}")
        else:
            self.current_game_info = None
            self.lbl_current_path.setText("📁 当前目标目录: 未选择游戏")

        self.refresh_current_game_status()

    def refresh_current_game_status(self):
        """Evaluates target directory and refreshes 4 status blocks and buttons."""
        if not self.current_game_info or not self.current_game_info.get("target_dir"):
            self.block_dlss5.set_status("⚪ 未选择游戏", "#94A3B8")
            self.block_fg.set_status("⚪ 未选择游戏", "#94A3B8")
            self.block_reshade.set_status("⚪ 未选择游戏", "#94A3B8")
            self.block_avoidance.set_status("⚪ 未选择游戏", "#94A3B8")
            self.btn_inject.setEnabled(False)
            self.btn_restore.setEnabled(False)
            self.update_alert_box(False, "未选择游戏")
            return

        target_dir = self.current_game_info["target_dir"]
        if not os.path.exists(target_dir):
            self.block_dlss5.set_status("❌ 目录不存在", "#EF4444")
            self.btn_inject.setEnabled(False)
            self.btn_restore.setEnabled(False)
            return

        status = DLSS5Injector.get_status(target_dir)
        fg_info = status["fg_info"]
        is_dark = getattr(self, "is_dark_mode", False)

        c_green = "#4ADE80" if is_dark else "#16A34A"
        c_gray = "#94A3B8" if is_dark else "#64748B"
        c_blue = "#38BDF8" if is_dark else "#0284C7"
        c_yellow = "#FACC15" if is_dark else "#D97706"

        # 1. DLSS 5 Block
        if status["is_injected"]:
            self.block_dlss5.set_status("🟢 已注入生效", c_green, "lecram-dlss5-beta10.addon64 就绪")
            self.btn_inject.setText("⚡ 重新覆盖注入 DLSS 5")
            self.btn_restore.setEnabled(True)
        else:
            self.block_dlss5.set_status("⚪ 未注入", c_gray, "点击下方按钮一键注入")
            self.btn_inject.setText("⚡ 一键注入 DLSS 5")
            self.btn_restore.setEnabled(False)

        self.btn_inject.setEnabled(True)

        # 2. Frame Generation Block
        if fg_info["has_fg"]:
            self.block_fg.set_status("🟢 已检测到插帧补丁", c_green, fg_info["summary"])
        else:
            self.block_fg.set_status("⚪ 未检测到插帧", c_gray, "标准模式")

        # 3. ReShade / RHI Block
        if status["is_addon_supported"]:
            self.block_reshade.set_status("🟢 底座就绪", c_green, "ReShade 64-bit Full Addon")
        elif status["is_reshade"]:
            self.block_reshade.set_status("🟡 标准 ReShade 底座", c_yellow, "无插件扩展，注入时将补齐")
        elif status["has_dxgi"]:
            self.block_reshade.set_status("🔵 第三方 dxgi.dll", c_blue, "已存在其他代理 DLL")
        else:
            self.block_reshade.set_status("⚪ 缺失底座", c_gray, "注入 DLSS 5 时全自动补全")

        # 4. Avoidance Block
        if fg_info["has_fg"]:
            self.block_avoidance.set_status("🛡️ 避让已激活", c_blue, "自动共用插帧底座，免冲突")
            self.update_alert_box(
                True,
                f"🛡️【多帧生成避让已激活】：检测到游戏已启用多帧生成 ({fg_info['summary']})。"
                "DLSS 5 注入时将自动复用现有宿主底座，绝不覆盖已有插帧文件，实现零冲突双插件共存！"
            )
        else:
            self.block_avoidance.set_status("⚪ 独立底座模式", c_gray, "独占 ReShade 6.8 底座")
            self.update_alert_box(
                False,
                "💡【独立底座模式】：当前游戏未注入多帧生成补丁，注入 DLSS 5 时将自动部署 ReShade 6.8 核心宿主底座与默认配置文件。"
            )

    def update_alert_box(self, is_avoidance: bool, text: str):
        is_dark = getattr(self, "is_dark_mode", False)
        self.lbl_alert_text.setText(text)
        if is_avoidance:
            self.lbl_alert_icon.setText("🛡️")
            bg = "#1E2A38" if is_dark else "#F0F9FF"
            border = "#0284C7" if is_dark else "#BAE6FD"
            txt_color = "#38BDF8" if is_dark else "#0369A1"
        else:
            self.lbl_alert_icon.setText("💡")
            bg = "#1E2229" if is_dark else "#F8FAFC"
            border = "#334155" if is_dark else "#E2E8F0"
            txt_color = "#94A3B8" if is_dark else "#475569"

        self.alert_box.setStyleSheet(f"""
            QFrame#AlertBox {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            QLabel {{
                color: {txt_color};
            }}
        """)

    def on_inject_dlss5(self):
        """Performs one-click injection with Frame Generation collision avoidance."""
        if not self.current_game_info or not self.current_game_info.get("target_dir"):
            QMessageBox.warning(self, "提示", "请先选择目标游戏！")
            return

        target_dir = self.current_game_info["target_dir"]
        game_name = self.current_game_info.get("name", "选中游戏")

        ok, msg = DLSS5Injector.inject(target_dir)
        if ok:
            QMessageBox.information(self, f"注入成功 - {game_name}", msg)
        else:
            QMessageBox.critical(self, "注入失败", msg)

        self.refresh_current_game_status()

    def on_restore_dlss5(self):
        """Restores target game cleanly without affecting Frame Generation."""
        if not self.current_game_info or not self.current_game_info.get("target_dir"):
            return

        target_dir = self.current_game_info["target_dir"]
        game_name = self.current_game_info.get("name", "选中游戏")

        reply = QMessageBox.question(
            self,
            "确认还原",
            f"确定要卸载游戏【{game_name}】中的 DLSS 5 插件并还原吗？\n\n"
            "（若当前游戏注入了多帧生成补丁，将自动保留多帧生成环境与 ReShade 底座不受任何影响）",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        ok, msg = DLSS5Injector.restore(target_dir)
        if ok:
            QMessageBox.information(self, f"还原成功 - {game_name}", msg)
        else:
            QMessageBox.critical(self, "还原失败", msg)

        self.refresh_current_game_status()

    def on_launch_rhi(self):
        """Launches RHI-Setup.exe or installed RHI utility."""
        ok, msg = DLSS5Injector.launch_rhi()
        if not ok:
            QMessageBox.warning(self, "启动 RHI", msg)

    def on_open_game_dir(self):
        """Opens game directory in Windows Explorer."""
        if not self.current_game_info or not self.current_game_info.get("target_dir"):
            return
        td = self.current_game_info["target_dir"]
        if os.path.exists(td):
            os.startfile(td)

    def apply_theme(self):
        """Synchronizes UI theme across BaseWindow and all child cards."""
        super().apply_theme()
        is_dark = getattr(self, "is_dark_mode", False)

        # Update scrollbar styling
        if hasattr(self, "scroll_area"):
            self.scroll_area.setStyleSheet(SCROLLBAR_DARK_QSS if is_dark else SCROLLBAR_LIGHT_QSS)

        # Subtitle color
        if hasattr(self, "banner_desc"):
            c_sub = "#94A3B8" if is_dark else "#64748B"
            self.banner_desc.setStyleSheet(f"font-size: 12px; color: {c_sub};")

        # Update Status Blocks
        if hasattr(self, "block_dlss5"):
            for b in [self.block_dlss5, self.block_fg, self.block_reshade, self.block_avoidance]:
                b.apply_theme(is_dark)
            self.refresh_current_game_status()


def main():
    app = QApplication.instance()
    owns_app = False
    if app is None:
        app = QApplication(sys.argv)
        owns_app = True

    win = DLSS5Window()
    win.show()

    if owns_app:
        sys.exit(app.exec())


if __name__ == "__main__":
    main()
