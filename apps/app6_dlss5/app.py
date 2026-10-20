# -*- coding: utf-8 -*-
"""
App 6: DLSS 5 神经重构与画质注入器 (DLSS 5 Neural Reconstruction Injector)
========================================================================
集成最新 lecram DLSS 5 神经网络渲染插件 (DLSS 5 NR Addon)，
支持一键注入至游戏根目录，附带 ReShade / RHI 运行底座与多帧生成 (插帧) 深度联动与冲突智能避让。

联动特性：
1. 游戏库实时联动：与「应用2：DLSS多帧生成补丁」共享游戏扫描缓存 (GameCacheManager)，
   启动秒开、最近游戏跨应用同步、手动添加游戏双向互通。
2. RHI / ReShade 底座联动：
   - 支持一键物理注入 ReShade 6.8 (Add-on 支持) 核心底座（带多帧生成避让保护）
   - 支持拉起 RHI 模组生态助手，自动将主程序绝对路径复制到剪贴板，支持 Ctrl+V 秒选游戏。
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

# App 2 for GameScanner & GameCacheManager import
MFG_DIR = ROOT_DIR / "apps" / "app2_mfg"
if str(MFG_DIR) not in sys.path:
    sys.path.insert(0, str(MFG_DIR))

from dm_ui_core import (
    DMBaseWindow, DMFooterBar, DMSizeGrip, DMThemeManager,
    apply_dm_window_frame, get_global_theme, set_global_theme,
    SCROLLBAR_LIGHT_QSS, SCROLLBAR_DARK_QSS
)
from apps.app6_dlss5.core.injector import (
    DLSS5Injector, check_dlss5_status, detect_frame_generation,
    find_rhi_setup_exe, get_dlss5_addon_path, find_reshade_framework_dll
)

try:
    from apps.app2_mfg.core.game_cache import GameCacheManager
    from apps.app2_mfg.core.models import GameInfo, QualificationStatus
except Exception:
    GameCacheManager = None
    GameInfo = None

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
            if GameCacheManager:
                try:
                    GameCacheManager.save_cache(scanned_games=games)
                except Exception:
                    pass
            self.games_found.emit(games)
        except Exception:
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
        layout.addWidget(self.lbl_title)

        self.lbl_val = QLabel("⚪ 检测中...")
        self.lbl_val.setWordWrap(True)
        layout.addWidget(self.lbl_val)

        self.lbl_sub = QLabel("")
        self.lbl_sub.setWordWrap(True)
        layout.addWidget(self.lbl_sub)

    def set_status(self, val_text: str, val_color: str, sub_text: str = ""):
        self.lbl_val.setText(val_text)
        self.lbl_val.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {val_color};")
        self.lbl_sub.setText(sub_text)
        self.lbl_sub.setVisible(bool(sub_text))

    def apply_theme(self, is_dark: bool):
        bg = "#222325" if is_dark else "#F8FAFC"
        border = "#383A3C" if is_dark else "#E2E8F0"
        title_c = "#94A3B8" if is_dark else "#64748B"
        sub_c = "#8A8F98" if is_dark else "#94A3B8"
        self.setStyleSheet(f"""
            QFrame#StatusBlock {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 10px;
            }}
        """)
        self.lbl_title.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {title_c};")
        self.lbl_sub.setStyleSheet(f"font-size: 11px; color: {sub_c};")


class DLSS5Window(DMBaseWindow):
    """DLSS 5 神经重构与画质注入器主窗口。"""

    def __init__(self):
        self.games_list: List[Any] = []
        self.current_game_info: Optional[Dict[str, Any]] = None
        self.scan_worker: Optional[GameScanWorker] = None

        super().__init__(
            title="DM工具箱 - DLSS 5 神经重构与画质注入器",
            width=960,
            height=780,
            icon_filename="dlss5_icon.png"
        )
        self.setMinimumSize(880, 680)
        self.resize(960, 780)

        self.init_content()
        self.apply_theme()

        # Immediate zero-latency startup linkage from App 2 GameCacheManager
        has_cached = self.load_from_game_cache()
        if not has_cached:
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
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        container = QWidget()
        container.setObjectName("ScrollContainer")
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(20, 12, 20, 14)
        vbox.setSpacing(12)

        # ------------------ 1. BANNER CARD ------------------
        self.banner_card = QFrame()
        self.banner_card.setProperty("class", "GridCard")
        b_layout = QHBoxLayout(self.banner_card)
        b_layout.setContentsMargins(18, 12, 18, 12)
        b_layout.setSpacing(14)

        # Icon
        self.banner_icon = QLabel()
        self.banner_icon.setFixedSize(54, 54)
        icon_path = ASSETS_DIR / "dlss5_icon.png"
        if not icon_path.exists():
            icon_path = ROOT_DIR / "common" / "assets" / "dlss5_icon.png"
        if icon_path.exists():
            pix = QPixmap(str(icon_path)).scaled(54, 54, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.banner_icon.setPixmap(pix)
        b_layout.addWidget(self.banner_icon)

        # Text
        b_text_box = QVBoxLayout()
        b_text_box.setSpacing(4)

        t_row = QHBoxLayout()
        t_row.setSpacing(10)
        self.banner_title = QLabel("DLSS 5 神经重构与画质注入器")
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

        self.badge_link = QLabel("🔗 多帧生成深度联动")
        self.badge_link.setStyleSheet("""
            background-color: #0284C7;
            color: #FFFFFF;
            font-size: 11px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 6px;
        """)
        t_row.addWidget(self.badge_link)
        t_row.addStretch()
        b_text_box.addLayout(t_row)

        self.banner_desc = QLabel(
            "集成最新 lecram DLSS 5 神经网络重建插件 (DLSS 5 NR Addon)，"
            "为支持 DLSS 的游戏注入下一代神经网络画质引擎，内建 ReShade/RHI 运行底座，并与多帧生成补丁智能避让共存。"
        )
        self.banner_desc.setWordWrap(True)
        b_text_box.addWidget(self.banner_desc)

        b_layout.addLayout(b_text_box, 1)
        vbox.addWidget(self.banner_card)

        # ------------------ 2. GAME SELECTION & STATUS CARD ------------------
        self.game_card = QFrame()
        self.game_card.setProperty("class", "GridCard")
        g_layout = QVBoxLayout(self.game_card)
        g_layout.setContentsMargins(18, 12, 18, 12)
        g_layout.setSpacing(10)

        # Title row
        g_header = QHBoxLayout()
        self.lbl_g_title = QLabel("🎮 目标游戏与运行环境监测 (多帧生成联动)")
        self.lbl_g_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        g_header.addWidget(self.lbl_g_title)
        g_header.addStretch()

        self.lbl_scan_status = QLabel("正在连接多帧生成游戏库...")
        g_header.addWidget(self.lbl_scan_status)
        g_layout.addLayout(g_header)

        # Selector row
        sel_row = QHBoxLayout()
        sel_row.setSpacing(10)

        self.combo_games = QComboBox()
        self.combo_games.setMinimumHeight(38)
        self.combo_games.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.combo_games.currentIndexChanged.connect(self.on_game_selected)
        sel_row.addWidget(self.combo_games, 1)

        self.btn_browse = QPushButton("➕ 手动选择游戏 (.exe)")
        self.btn_browse.setObjectName("BtnBrowse")
        self.btn_browse.setMinimumHeight(38)
        self.btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_browse.clicked.connect(self.on_browse_game)
        sel_row.addWidget(self.btn_browse)

        self.btn_rescan = QPushButton("🔄 联动全盘扫描")
        self.btn_rescan.setObjectName("BtnRescan")
        self.btn_rescan.setMinimumHeight(38)
        self.btn_rescan.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_rescan.clicked.connect(self.start_background_scan)
        sel_row.addWidget(self.btn_rescan)

        g_layout.addLayout(sel_row)

        # Path display
        self.lbl_current_path = QLabel("📁 当前目标目录: 未选择游戏")
        self.lbl_current_path.setStyleSheet("font-size: 11px; font-family: Consolas, monospace;")
        self.lbl_current_path.setWordWrap(True)
        g_layout.addWidget(self.lbl_current_path)

        # 4-Quadrant Status Grid
        status_grid = QGridLayout()
        status_grid.setSpacing(10)

        self.block_dlss5 = StatusBlock("DLSS 5 插件状态")
        status_grid.addWidget(self.block_dlss5, 0, 0)

        self.block_fg = StatusBlock("多帧生成 (插帧) 联动状态")
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
        self.action_card = QFrame()
        self.action_card.setProperty("class", "GridCard")
        act_layout = QVBoxLayout(self.action_card)
        act_layout.setContentsMargins(18, 12, 18, 12)
        act_layout.setSpacing(10)

        self.lbl_act_title = QLabel("⚡ 一键操作中心")
        self.lbl_act_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        act_layout.addWidget(self.lbl_act_title)

        # Row 1: DLSS 5 Injection & Restore
        btn_row1 = QHBoxLayout()
        btn_row1.setSpacing(12)

        self.btn_inject = QPushButton("⚡ 一键注入 DLSS 5")
        self.btn_inject.setObjectName("BtnInject")
        self.btn_inject.setMinimumHeight(44)
        self.btn_inject.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_inject.clicked.connect(self.on_inject_dlss5)
        btn_row1.addWidget(self.btn_inject, 2)

        self.btn_restore = QPushButton("🔄 一键还原 / 卸载")
        self.btn_restore.setObjectName("BtnRestore")
        self.btn_restore.setMinimumHeight(44)
        self.btn_restore.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_restore.clicked.connect(self.on_restore_dlss5)
        btn_row1.addWidget(self.btn_restore, 1)

        self.btn_open_dir = QPushButton("📂 打开游戏目录")
        self.btn_open_dir.setObjectName("BtnOpenDir")
        self.btn_open_dir.setMinimumHeight(44)
        self.btn_open_dir.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_dir.clicked.connect(self.on_open_game_dir)
        btn_row1.addWidget(self.btn_open_dir, 1)

        act_layout.addLayout(btn_row1)

        # Row 2: RHI / ReShade Base Integration Linkage
        btn_row2 = QHBoxLayout()
        btn_row2.setSpacing(12)

        self.btn_inject_base = QPushButton("🛠️ 一键物理注入 ReShade / RHI 底座")
        self.btn_inject_base.setObjectName("BtnInjectBase")
        self.btn_inject_base.setMinimumHeight(40)
        self.btn_inject_base.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_inject_base.setToolTip("直接为游戏物理注入 ReShade 6.8 核心底座 (dxgi.dll) 与基础配置，已带多帧生成避让")
        self.btn_inject_base.clicked.connect(self.on_inject_reshade_base)
        btn_row2.addWidget(self.btn_inject_base, 1)

        self.btn_rhi = QPushButton("🚀 启动 RHI 模组生态助手 (自动复制路径)")
        self.btn_rhi.setObjectName("BtnRHI")
        self.btn_rhi.setMinimumHeight(40)
        self.btn_rhi.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_rhi.setToolTip("自动将当前游戏主程序绝对路径复制到剪贴板，并在打开的 RHI 安装器中按 Ctrl+V 即可秒选游戏")
        self.btn_rhi.clicked.connect(self.on_launch_rhi)
        btn_row2.addWidget(self.btn_rhi, 1)

        act_layout.addLayout(btn_row2)
        vbox.addWidget(self.action_card)

        # ------------------ 4. GUIDELINES & PRINCIPLE CARD ------------------
        self.guide_card = QFrame()
        self.guide_card.setProperty("class", "GridCard")
        guide_layout = QVBoxLayout(self.guide_card)
        guide_layout.setContentsMargins(20, 16, 20, 16)
        guide_layout.setSpacing(10)

        self.lbl_guide_title = QLabel("💡 DLSS 5 神经重构使用指南与技术说明")
        self.lbl_guide_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        guide_layout.addWidget(self.lbl_guide_title)

        tips_text = (
            "<b>1. 游戏内热键与调校</b>：<br>"
            "启动游戏后，在游戏画面中按键盘 <code>【Home】</code> 键即可唤出 ReShade 叠加控制台。在 <code>【Add-ons】</code> 标签页中可查看已挂载的 <b>lecram-dlss5-beta10</b> 神经重构插件及其运行状态。<br><br>"
            "<b>2. 多帧生成 (插帧) 避让共存机制</b>：<br>"
            "• DLSS 5 插件与多帧生成补丁 (RenoDX / OptiScaler) 均依托底层 <code>dxgi.dll</code> (ReShade 64-bit Add-on 宿主) 运行。<br>"
            "• 若目标游戏已通过「应用2：DLSS多帧生成补丁」完成注入，本程序会自动激活<b>【插帧避让】</b>，跳过底座部署，直接将 DLSS 5 并联挂载至现有 <code>ReShade.ini</code>，两套插件在同一进程中协同工作，零冲突、免二次安装。<br>"
            "• 还原时同样具备防误删保护：仅移除 DLSS 5 插件，完整保留多帧生成环境。<br><br>"
            "<b>3. 联动与 RHI 生态支持</b>：<br>"
            "• 本工具与「应用2：DLSS多帧生成补丁」共享游戏扫描数据与最近游戏历史，无须反复耗时全盘扫描。<br>"
            "• 支持直接一键物理部署 ReShade 6.8 底座，或拉起 RHI 安装器直达助手（自动将游戏路径写入剪贴板，秒速定位）。"
        )
        self.lbl_tips = QLabel(tips_text)
        self.lbl_tips.setWordWrap(True)
        self.lbl_tips.setTextFormat(Qt.TextFormat.RichText)
        guide_layout.addWidget(self.lbl_tips)

        vbox.addWidget(self.guide_card)

        vbox.addStretch()
        self.scroll_area.setWidget(container)
        self.body_layout.addWidget(self.scroll_area)

    def load_from_game_cache(self) -> bool:
        """Loads cached games and last selected executable from App 2 GameCacheManager."""
        if not GameCacheManager:
            return False
        try:
            games, last_exe = GameCacheManager.get_cached_games()
            if games:
                self.populate_games(games, last_selected_exe=last_exe)
                self.lbl_scan_status.setText(f"🔗 已联动【多帧生成】游戏库 (共 {len(games)} 款游戏)")
                return True
        except Exception:
            pass
        return False

    def populate_games(self, games: list, last_selected_exe: Optional[str] = None):
        """Populates game dropdown and restores last selected game."""
        self.games_list = games
        self.btn_rescan.setEnabled(True)

        self.combo_games.blockSignals(True)
        self.combo_games.clear()

        if not games:
            self.combo_games.addItem("未发现已安装游戏 (请点击右侧手动选择)", "")
            self.combo_games.blockSignals(False)
            self.refresh_current_game_status()
            return

        target_idx = 0
        for i, g in enumerate(games):
            name = getattr(g, "name", "未知游戏")
            exe = getattr(g, "exe_name", getattr(g, "primary_executable", ""))
            p_dir = getattr(g, "target_dir", getattr(g, "install_dir", ""))
            exe_full = getattr(g, "exe_path", "")
            is_patched = getattr(g, "is_patched", False)

            # Check DLSS 5 injection on disk
            addon_exists = (Path(p_dir) / "lecram-dlss5-beta10.addon64").exists() if p_dir else False

            if is_patched and addon_exists:
                tag = " [DLSS 5 + 插帧双就绪]"
            elif is_patched:
                tag = " [多帧生成已就绪]"
            elif addon_exists:
                tag = " [DLSS 5已注入]"
            else:
                tag = ""

            display_text = f"{name} ({exe}){tag}" if exe else f"{name}{tag}"
            data_dict = {
                "name": name,
                "target_dir": str(p_dir),
                "exe": str(exe),
                "exe_path": str(exe_full),
                "game_obj": g
            }
            self.combo_games.addItem(display_text, data_dict)

            if last_selected_exe and exe_full and exe_full.lower() == last_selected_exe.lower():
                target_idx = i

        self.combo_games.blockSignals(False)
        self.combo_games.setCurrentIndex(target_idx)
        self.on_game_selected(target_idx)

    def start_background_scan(self):
        """Starts background game library scan."""
        self.lbl_scan_status.setText("⏳ 正在快速扫描本地已安装游戏...")
        self.btn_rescan.setEnabled(False)

        self.scan_worker = GameScanWorker()
        self.scan_worker.games_found.connect(self.on_scan_completed)
        self.scan_worker.start()

    def on_scan_completed(self, games: list):
        """Callback when background scan finishes."""
        self.populate_games(games)
        self.lbl_scan_status.setText(f"✅ 全盘扫描完成，已同步 {len(games)} 款游戏")

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

        # Try to resolve title with scanner if available
        try:
            from apps.app2_mfg.core.scanner import GameScanner
            scanner = GameScanner()
            game_name = scanner._resolve_game_title(target_dir, exe_name)
        except Exception:
            pass

        custom_data = {
            "name": f"{game_name} (自定义添加)",
            "target_dir": str(target_dir),
            "exe": exe_name,
            "exe_path": str(p)
        }

        # Sync to App 2 GameCacheManager
        if GameCacheManager and GameInfo:
            try:
                g_info = GameInfo(
                    name=game_name,
                    source="Custom",
                    install_dir=str(target_dir),
                    target_dir=str(target_dir),
                    exe_path=str(p),
                    exe_name=exe_name,
                    qualification=QualificationStatus.QUALIFIED
                )
                GameCacheManager.add_custom_game(g_info)
            except Exception:
                pass

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
            # Synchronize last selected exe to App 2 GameCacheManager
            exe_full = data.get("exe_path", "")
            if exe_full and GameCacheManager:
                try:
                    GameCacheManager.save_last_selected(exe_full)
                except Exception:
                    pass
        else:
            self.current_game_info = None
            self.lbl_current_path.setText("📁 当前目标目录: 未选择游戏")

        self.refresh_current_game_status()

    def refresh_current_game_status(self):
        """Evaluates target directory and refreshes 4 status blocks and buttons."""
        if not hasattr(self, "btn_inject") or not hasattr(self, "block_dlss5"):
            return
        if not hasattr(self, "current_game_info") or not self.current_game_info or not self.current_game_info.get("target_dir"):
            self.block_dlss5.set_status("⚪ 未选择游戏", "#94A3B8")
            self.block_fg.set_status("⚪ 未选择游戏", "#94A3B8")
            self.block_reshade.set_status("⚪ 未选择游戏", "#94A3B8")
            self.block_avoidance.set_status("⚪ 未选择游戏", "#94A3B8")
            self.btn_inject.setEnabled(False)
            self.btn_restore.setEnabled(False)
            self.btn_inject_base.setEnabled(False)
            self.update_alert_box(False, "未选择游戏")
            return

        target_dir = self.current_game_info["target_dir"]
        if not os.path.exists(target_dir):
            self.block_dlss5.set_status("❌ 目录不存在", "#EF4444")
            self.btn_inject.setEnabled(False)
            self.btn_restore.setEnabled(False)
            self.btn_inject_base.setEnabled(False)
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
        self.btn_inject_base.setEnabled(True)

        # 2. Frame Generation Block
        if fg_info["has_fg"]:
            self.block_fg.set_status("🟢 已检测到插帧补丁", c_green, fg_info["summary"])
            self.btn_inject_base.setText("🛡️ ReShade 底座已由多帧生成托管")
        else:
            self.block_fg.set_status("⚪ 未检测到插帧", c_gray, "标准模式")
            self.btn_inject_base.setText("🛠️ 一键物理注入 ReShade / RHI 底座")

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
            bg = "#1B2A32" if is_dark else "#F0F9FF"
            border = "#0284C7" if is_dark else "#BAE6FD"
            txt_color = "#38BDF8" if is_dark else "#0369A1"
        else:
            self.lbl_alert_icon.setText("💡")
            bg = "#232426" if is_dark else "#F8FAFC"
            border = "#3A3C3E" if is_dark else "#E2E8F0"
            txt_color = "#94A3B8" if is_dark else "#475569"

        self.alert_box.setStyleSheet(f"""
            QFrame#AlertBox {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 10px;
            }}
            QLabel {{
                color: {txt_color};
                background: transparent;
                border: none;
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

    def on_inject_reshade_base(self):
        """Performs standalone physical injection of ReShade/RHI base with avoidance."""
        if not self.current_game_info or not self.current_game_info.get("target_dir"):
            QMessageBox.warning(self, "提示", "请先选择目标游戏！")
            return

        target_dir = self.current_game_info["target_dir"]
        game_name = self.current_game_info.get("name", "选中游戏")

        ok, msg = DLSS5Injector.inject_reshade_base(target_dir)
        if ok:
            QMessageBox.information(self, f"ReShade 底座就绪 - {game_name}", msg)
        else:
            QMessageBox.critical(self, "底座注入失败", msg)

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
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        ok, msg = DLSS5Injector.restore(target_dir)
        if ok:
            QMessageBox.information(self, f"还原成功 - {game_name}", msg)
        else:
            QMessageBox.critical(self, "还原失败", msg)

        self.refresh_current_game_status()

    def on_launch_rhi(self):
        """Launches RHI-Setup.exe with game path copied to Windows clipboard for instant paste."""
        game_exe_path = ""
        if self.current_game_info:
            game_exe_path = self.current_game_info.get("exe_path", "")
            if not game_exe_path and self.current_game_info.get("target_dir") and self.current_game_info.get("exe"):
                game_exe_path = str(Path(self.current_game_info["target_dir"]) / self.current_game_info["exe"])

        ok, msg = DLSS5Injector.launch_rhi_guide(game_exe_path)
        if ok:
            QMessageBox.information(self, "RHI 模组生态直达助手", msg)
        else:
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

        card_bg = "#2A2B2C" if is_dark else "#FFFFFF"
        card_border = "#3A3A3A" if is_dark else "#E5E5E5"
        hover_border = "#3E9E69" if is_dark else "#2F8F5B"
        title_color = "#E8E8E8" if is_dark else "#1A1A1A"
        sub_color = "#94A3B8" if is_dark else "#64748B"

        card_style = f"""
            QFrame[class="GridCard"] {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 14px;
            }}
            QFrame[class="GridCard"]:hover {{
                border: 1px solid {hover_border};
            }}
        """
        for card_name in ["banner_card", "game_card", "action_card", "guide_card"]:
            if hasattr(self, card_name):
                getattr(self, card_name).setStyleSheet(card_style)

        # Update Titles & Subtitles
        if hasattr(self, "banner_title"):
            self.banner_title.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {title_color};")
        if hasattr(self, "banner_desc"):
            self.banner_desc.setStyleSheet(f"font-size: 12px; color: {sub_color};")
        if hasattr(self, "lbl_g_title"):
            self.lbl_g_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {title_color};")
        if hasattr(self, "lbl_act_title"):
            self.lbl_act_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {title_color};")
        if hasattr(self, "lbl_guide_title"):
            self.lbl_guide_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {title_color};")
        if hasattr(self, "lbl_scan_status"):
            self.lbl_scan_status.setStyleSheet(f"font-size: 12px; color: {sub_color};")

        # Explicit vibrant button styles for light and dark
        btn_green = "#10B981" if is_dark else "#16A34A"
        btn_green_hover = "#059669" if is_dark else "#15803D"
        btn_sec_bg = "#334155" if is_dark else "#F1F5F9"
        btn_sec_border = "#475569" if is_dark else "#CBD5E1"
        btn_sec_hover = "#475569" if is_dark else "#E2E8F0"
        btn_sec_text = "#F8FAFC" if is_dark else "#1E293B"

        if hasattr(self, "btn_inject"):
            self.btn_inject.setStyleSheet(f"""
                QPushButton#BtnInject {{
                    background-color: {btn_green};
                    color: #FFFFFF;
                    font-size: 14px;
                    font-weight: 700;
                    border: none;
                    border-radius: 10px;
                    padding: 8px 16px;
                }}
                QPushButton#BtnInject:hover {{
                    background-color: {btn_green_hover};
                }}
                QPushButton#BtnInject:disabled {{
                    background-color: {'#374151' if is_dark else '#E2E8F0'};
                    color: {'#6B7280' if is_dark else '#94A3B8'};
                }}
            """)

        if hasattr(self, "btn_browse"):
            self.btn_browse.setStyleSheet(f"""
                QPushButton#BtnBrowse {{
                    background-color: {btn_green};
                    color: #FFFFFF;
                    font-size: 13px;
                    font-weight: 700;
                    border: none;
                    border-radius: 8px;
                    padding: 6px 14px;
                }}
                QPushButton#BtnBrowse:hover {{
                    background-color: {btn_green_hover};
                }}
            """)

        if hasattr(self, "btn_rescan"):
            rescan_c = "#38BDF8" if is_dark else "#0284C7"
            self.btn_rescan.setStyleSheet(f"""
                QPushButton#BtnRescan {{
                    background-color: transparent;
                    color: {rescan_c};
                    font-size: 13px;
                    font-weight: 600;
                    border: 1px solid {rescan_c};
                    border-radius: 8px;
                    padding: 6px 14px;
                }}
                QPushButton#BtnRescan:hover {{
                    background-color: {rescan_c};
                    color: #FFFFFF;
                }}
            """)

        if hasattr(self, "btn_restore"):
            danger_c = "#F87171" if is_dark else "#DC2626"
            self.btn_restore.setStyleSheet(f"""
                QPushButton#BtnRestore {{
                    background-color: transparent;
                    color: {danger_c};
                    font-size: 13px;
                    font-weight: 600;
                    border: 1px solid {danger_c};
                    border-radius: 10px;
                    padding: 8px 14px;
                }}
                QPushButton#BtnRestore:hover {{
                    background-color: {danger_c};
                    color: #FFFFFF;
                }}
                QPushButton#BtnRestore:disabled {{
                    border-color: {'#4B5563' if is_dark else '#CBD5E1'};
                    color: {'#6B7280' if is_dark else '#94A3B8'};
                }}
            """)

        sec_style = f"""
            QPushButton {{
                background-color: {btn_sec_bg};
                color: {btn_sec_text};
                font-size: 13px;
                font-weight: 600;
                border: 1px solid {btn_sec_border};
                border-radius: 10px;
                padding: 8px 14px;
            }}
            QPushButton:hover {{
                background-color: {btn_sec_hover};
            }}
            QPushButton:disabled {{
                background-color: {'#374151' if is_dark else '#E2E8F0'};
                color: {'#6B7280' if is_dark else '#94A3B8'};
                border-color: {'#4B5563' if is_dark else '#CBD5E1'};
            }}
        """
        if hasattr(self, "btn_inject_base"):
            self.btn_inject_base.setStyleSheet(sec_style)
        if hasattr(self, "btn_rhi"):
            self.btn_rhi.setStyleSheet(sec_style)
        if hasattr(self, "btn_open_dir"):
            self.btn_open_dir.setStyleSheet(sec_style)

        # Update Status Blocks
        if hasattr(self, "block_dlss5"):
            for b in [self.block_dlss5, self.block_fg, self.block_reshade, self.block_avoidance]:
                b.apply_theme(is_dark)

        if hasattr(self, "lbl_tips"):
            self.lbl_tips.setStyleSheet(f"font-size: 12px; color: {sub_color}; line-height: 150%;")

        if hasattr(self, "lbl_current_path"):
            self.lbl_current_path.setStyleSheet(f"font-size: 11px; color: {sub_color}; font-family: Consolas, monospace;")

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
