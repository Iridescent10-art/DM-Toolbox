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
    QComboBox, QLineEdit, QFileDialog, QSizePolicy, QRadioButton,
    QButtonGroup, QCheckBox, QSlider, QStackedWidget
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
from apps.app6_dlss5.engine.injector import (
    DLSS5Injector, check_dlss5_status, detect_frame_generation,
    find_rhi_setup_exe, get_dlss5_addon_path, find_reshade_framework_dll
)
from apps.app6_dlss5.engine.config_sync import ConfigSyncService
from apps.app2_mfg.core.optiscaler_config import (
    load_mode_a_preset, save_mode_a_preset,
    load_reshade_preset, save_reshade_preset,
    load_optiscaler_preset, save_optiscaler_preset
)
from apps.app2_mfg.core.ini_sync import IniConfigManager

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



class MultiFrameGenPanel(QFrame):
    """
    内嵌于 DLSS 5 注入器主界面的【多帧生成联动控制台】。
    支持在单个面板内直接切换 模式 A / 模式 B / 模式 C 并动态调配参数，
    实现与目标游戏目录配置文件及 App 2 高级预设窗口的双向数据同步。
    """
    config_applied = Signal(str)

    def __init__(self, parent_window=None):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.setProperty("class", "GridCard")
        self.setObjectName("MultiFrameGenPanel")
        self.current_game_info: Optional[Dict[str, Any]] = None
        self.active_mode = "A"  # "A", "B", "C"
        self._is_loading = False

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        # 1. Header
        header = QHBoxLayout()
        header.setSpacing(10)

        self.lbl_title = QLabel("⚡ 多帧生成 (插帧) 联动控制台")
        self.lbl_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        header.addWidget(self.lbl_title)

        self.badge_mode = QLabel("A/B/C 三模式统一调控")
        self.badge_mode.setStyleSheet("""
            background-color: #8B5CF6;
            color: #FFFFFF;
            font-size: 11px;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 6px;
        """)
        header.addWidget(self.badge_mode)
        header.addStretch()

        self.btn_open_advanced = QPushButton("⚙️ 高级预设面板...")
        self.btn_open_advanced.setObjectName("BtnOpenAdvanced")
        self.btn_open_advanced.setMinimumHeight(30)
        self.btn_open_advanced.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_advanced.setToolTip("打开完整的模式 A/B/C 详细预设双向同步弹窗")
        self.btn_open_advanced.clicked.connect(self._open_advanced_dialog)
        header.addWidget(self.btn_open_advanced)

        layout.addLayout(header)

        # 2. Mode Selector
        mode_box = QHBoxLayout()
        mode_box.setSpacing(16)

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)

        self.radio_mode_a = QRadioButton("模式 A: dashdogy 独立代理")
        self.radio_mode_b = QRadioButton("模式 B: RenoDX 插件优化")
        self.radio_mode_c = QRadioButton("模式 C: OptiScaler 跨卡转译")

        for idx, rb in enumerate([self.radio_mode_a, self.radio_mode_b, self.radio_mode_c]):
            rb.setCursor(Qt.CursorShape.PointingHandCursor)
            rb.setStyleSheet("font-size: 13px; font-weight: 600;")
            self.mode_group.addButton(rb, idx)
            mode_box.addWidget(rb)

        self.radio_mode_a.setChecked(True)
        self.mode_group.idClicked.connect(self._on_mode_radio_clicked)
        layout.addLayout(mode_box)

        # 3. Common Parameters Card/Box
        self.common_frame = QFrame()
        self.common_frame.setObjectName("CommonParamsFrame")
        c_layout = QGridLayout(self.common_frame)
        c_layout.setContentsMargins(14, 10, 14, 10)
        c_layout.setHorizontalSpacing(16)
        c_layout.setVerticalSpacing(8)

        # Multiplier
        self.lbl_mul = QLabel("强制插帧倍率:")
        self.combo_multiplier = QComboBox()
        self.combo_multiplier.addItems(["2X (插入1帧)", "3X (插入2帧)", "4X (插入3帧)", "6X (插入5帧)"])
        self.combo_multiplier.setCurrentIndex(1)  # 3X
        self.combo_multiplier.currentIndexChanged.connect(self._on_param_changed)
        c_layout.addWidget(self.lbl_mul, 0, 0)
        c_layout.addWidget(self.combo_multiplier, 0, 1)

        # DLSS Preset
        self.lbl_preset = QLabel("DLSS 超分预设:")
        self.combo_dlss_preset = QComboBox()
        self.combo_dlss_preset.addItems([
            "Default (原生直通·不篡改)",
            "Preset J (Transformer 10)",
            "Preset K (Transformer 11)",
            "Preset M (CNN 13)"
        ])
        self.combo_dlss_preset.setCurrentIndex(0)  # Default
        self.combo_dlss_preset.currentIndexChanged.connect(self._on_param_changed)
        c_layout.addWidget(self.lbl_preset, 0, 2)
        c_layout.addWidget(self.combo_dlss_preset, 0, 3)

        # Hotkey
        self.lbl_key = QLabel("游戏内菜单热键:")
        self.combo_hotkey = QComboBox()
        self.combo_hotkey.addItems(["Backspace", "Insert", "Home", "F11", "End"])
        self.combo_hotkey.currentIndexChanged.connect(self._on_param_changed)
        c_layout.addWidget(self.lbl_key, 1, 0)
        c_layout.addWidget(self.combo_hotkey, 1, 1)

        # Coexistence Hint
        self.lbl_mode_summary = QLabel("🟢 当前模式：模式 A 独立代理")
        self.lbl_mode_summary.setStyleSheet("font-size: 11px; font-weight: 600;")
        c_layout.addWidget(self.lbl_mode_summary, 1, 2, 1, 2)

        layout.addWidget(self.common_frame)

        # 4. Mode-Specific Dynamic Stack
        self.stack = QStackedWidget()

        # Page A: Mode A (dashdogy)
        self.page_a = QWidget()
        pa_layout = QVBoxLayout(self.page_a)
        pa_layout.setContentsMargins(6, 6, 6, 6)
        pa_layout.setSpacing(6)

        self.chk_bink = QCheckBox("启用 Bink2 链式劫持 (bink2w64.dll -> bink2w64Hooked.dll，适用于防篡改/自校验游戏)")
        self.chk_bink.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_bink.stateChanged.connect(self._on_param_changed)
        pa_layout.addWidget(self.chk_bink)

        self.lbl_note_a = QLabel(
            "💡 <b>模式 A 架构保障</b>：严格使用 <code>version.dll</code> 注入，DLSS 5 作为 <code>dxgi.dll</code> 加载；"
            "选择 Default 时严禁覆写为 D 模型，选择 Preset J/K 时自动在 <code>ReShade.ini</code> 与 <code>RTXMFG-Universal.json</code> 锁定模型。"
        )
        self.lbl_note_a.setWordWrap(True)
        pa_layout.addWidget(self.lbl_note_a)
        self.stack.addWidget(self.page_a)

        # Page B: Mode B (RenoDX)
        self.page_b = QWidget()
        pb_layout = QVBoxLayout(self.page_b)
        pb_layout.setContentsMargins(6, 6, 6, 6)
        pb_layout.setSpacing(8)

        grid_b = QGridLayout()
        grid_b.setHorizontalSpacing(16)
        grid_b.setVerticalSpacing(6)

        self.chk_blackwell = QCheckBox("Blackwell 优化内核")
        self.chk_isr = QCheckBox("ISR 细微几何重建")
        self.chk_vwb = QCheckBox("VWB 动态视窗插值")
        self.chk_bam = QCheckBox("BAM 边缘自适应")
        self.chk_hdr = QCheckBox("HDR UI 防撕裂 (Recomp)")
        self.chk_dynamic = QCheckBox("DynamicMFG 动态多帧")
        self.chk_temporal = QCheckBox("TemporalFix 时域修复")

        for chk in [self.chk_blackwell, self.chk_isr, self.chk_vwb, self.chk_bam,
                    self.chk_hdr, self.chk_dynamic, self.chk_temporal]:
            chk.setChecked(True)
            chk.setCursor(Qt.CursorShape.PointingHandCursor)
            chk.stateChanged.connect(self._on_param_changed)
        self.chk_dynamic.setChecked(False)

        grid_b.addWidget(self.chk_blackwell, 0, 0)
        grid_b.addWidget(self.chk_isr, 0, 1)
        grid_b.addWidget(self.chk_vwb, 0, 2)
        grid_b.addWidget(self.chk_bam, 1, 0)
        grid_b.addWidget(self.chk_hdr, 1, 1)
        grid_b.addWidget(self.chk_dynamic, 1, 2)
        grid_b.addWidget(self.chk_temporal, 2, 0)
        pb_layout.addLayout(grid_b)

        self.lbl_note_b = QLabel(
            "💡 <b>模式 B 闪退防护</b>：单宿主 <code>dxgi.dll</code> 同时托管双 Addon；自动写入 <code>[RenoDX.DLSS5] EnableHooks=2</code> "
            "跳过重复 Inline Hook，并在勾选 HDR UI 时自动启用 <code>DeferredInit=1</code> 延时初始化，消除 Access Violation 闪退。"
        )
        self.lbl_note_b.setWordWrap(True)
        pb_layout.addWidget(self.lbl_note_b)
        self.stack.addWidget(self.page_b)

        # Page C: Mode C (OptiScaler)
        self.page_c = QWidget()
        pc_layout = QVBoxLayout(self.page_c)
        pc_layout.setContentsMargins(6, 6, 6, 6)
        pc_layout.setSpacing(8)

        grid_c = QGridLayout()
        grid_c.setHorizontalSpacing(16)
        grid_c.setVerticalSpacing(8)

        self.lbl_fg_out = QLabel("插帧输出引擎:")
        self.combo_fg_out = QComboBox()
        self.combo_fg_out.addItems(["xefg (Intel XeSS 2.0 FG - 推荐)", "fsrfg (AMD FSR 3.1 FG)"])
        self.combo_fg_out.currentIndexChanged.connect(self._on_param_changed)
        grid_c.addWidget(self.lbl_fg_out, 0, 0)
        grid_c.addWidget(self.combo_fg_out, 0, 1)

        self.lbl_fg_in = QLabel("插帧输入通道:")
        self.combo_fg_in = QComboBox()
        self.combo_fg_in.addItems(["dlssg (Streamline 原生通道 - 推荐)", "fsr3 (FSR 接口)"])
        self.combo_fg_in.currentIndexChanged.connect(self._on_param_changed)
        grid_c.addWidget(self.lbl_fg_in, 0, 2)
        grid_c.addWidget(self.combo_fg_in, 0, 3)

        self.chk_rcas = QCheckBox("启用 AMD RCAS 锐化")
        self.chk_rcas.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_rcas.stateChanged.connect(self._on_param_changed)
        self.slider_rcas = QSlider(Qt.Orientation.Horizontal)
        self.slider_rcas.setRange(0, 100)
        self.slider_rcas.setValue(20)
        self.lbl_rcas_val = QLabel("0.20")
        self.lbl_rcas_val.setFixedWidth(36)
        self.slider_rcas.valueChanged.connect(self._on_slider_rcas_changed)

        rcas_row = QHBoxLayout()
        rcas_row.addWidget(self.chk_rcas)
        rcas_row.addWidget(self.slider_rcas, 1)
        rcas_row.addWidget(self.lbl_rcas_val)
        grid_c.addLayout(rcas_row, 1, 0, 1, 4)

        pc_layout.addLayout(grid_c)

        self.lbl_note_c = QLabel(
            "💡 <b>模式 C 修复说明</b>：OptiScaler 部署为 <code>dxgi.dll</code>，链式加载 <code>ReShade64.dll</code>；"
            "关闭 <code>Dxgi=false</code> 显卡欺骗使 DLSS 选项常驻，<code>Dx12Upscaler=dlss</code> 直通 DLSS 5，确保 XeFG 满血生效。"
        )
        self.lbl_note_c.setWordWrap(True)
        pc_layout.addWidget(self.lbl_note_c)
        self.stack.addWidget(self.page_c)

        layout.addWidget(self.stack)

        # 5. Buttons Row
        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)

        self.btn_sync_config = QPushButton("💾 保存多帧生成配置 (同步写入游戏)")
        self.btn_sync_config.setObjectName("BtnSyncConfig")
        self.btn_sync_config.setMinimumHeight(38)
        self.btn_sync_config.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_sync_config.clicked.connect(self.on_save_config_clicked)
        btn_box.addWidget(self.btn_sync_config, 1)

        self.btn_apply_all = QPushButton("⚡ 一键全套部署 (多帧生成 + DLSS 5 联动)")
        self.btn_apply_all.setObjectName("BtnApplyAll")
        self.btn_apply_all.setMinimumHeight(38)
        self.btn_apply_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_apply_all.clicked.connect(self.on_apply_all_clicked)
        btn_box.addWidget(self.btn_apply_all, 1)

        layout.addLayout(btn_box)

    def _on_mode_radio_clicked(self, btn_id: int):
        modes = ["A", "B", "C"]
        if 0 <= btn_id < len(modes):
            self.active_mode = modes[btn_id]
            self.stack.setCurrentIndex(btn_id)
            mode_desc = {
                "A": "🟢 当前模式：模式 A dashdogy 独立代理 (version.dll)",
                "B": "🟢 当前模式：模式 B RenoDX 插件优化 (单宿主双 Addon)",
                "C": "🟢 当前模式：模式 C OptiScaler 跨卡转译 (dxgi + ReShade64 链式)"
            }
            self.lbl_mode_summary.setText(mode_desc.get(self.active_mode, ""))
            if self.active_mode == "A":
                self.combo_hotkey.setCurrentText("Backspace")
            elif self.active_mode == "B":
                self.combo_hotkey.setCurrentText("Home")
            elif self.active_mode == "C":
                self.combo_hotkey.setCurrentText("Insert")
            self.load_config()

    def _on_param_changed(self):
        pass

    def _on_slider_rcas_changed(self, v: int):
        self.lbl_rcas_val.setText(f"{v / 100.0:.2f}")

    def set_game(self, game_info: Optional[Dict[str, Any]]):
        self.current_game_info = game_info
        if not game_info or not game_info.get("target_dir"):
            self.setEnabled(False)
            return

        self.setEnabled(True)
        td = game_info.get("target_dir", "")
        detected_mode = ConfigSyncService.detect_active_mode(td)
        if detected_mode in ["A", "B", "C"]:
            self.active_mode = detected_mode
            rb = [self.radio_mode_a, self.radio_mode_b, self.radio_mode_c][["A", "B", "C"].index(detected_mode)]
            rb.blockSignals(True)
            rb.setChecked(True)
            rb.blockSignals(False)
            self.stack.setCurrentIndex(["A", "B", "C"].index(detected_mode))
            mode_desc = {
                "A": "🟢 已检测到已安装：模式 A 独立代理",
                "B": "🟢 已检测到已安装：模式 B RenoDX 插件优化",
                "C": "🟢 已检测到已安装：模式 C OptiScaler 跨卡转译"
            }
            self.lbl_mode_summary.setText(mode_desc.get(detected_mode, ""))

        self.load_config()

    def load_config(self):
        self._is_loading = True
        td = self.current_game_info.get("target_dir", "") if self.current_game_info else ""
        cfg = ConfigSyncService.load_mode_config(td, self.active_mode)

        # Multiplier
        mul = int(cfg.get("multiplier", cfg.get("force_multiplier", cfg.get("interpolation_count", 2) + 1 if "interpolation_count" in cfg else 3)))
        mul_map = {2: 0, 3: 1, 4: 2, 6: 3}
        self.combo_multiplier.setCurrentIndex(mul_map.get(mul, 1))

        # DLSS Preset
        p_str = str(cfg.get("dlss_preset", "Default")).upper()
        if "J" in p_str or "10" in p_str:
            self.combo_dlss_preset.setCurrentIndex(1)
        elif "K" in p_str or "11" in p_str:
            self.combo_dlss_preset.setCurrentIndex(2)
        elif "M" in p_str or "13" in p_str:
            self.combo_dlss_preset.setCurrentIndex(3)
        else:
            self.combo_dlss_preset.setCurrentIndex(0)

        # Hotkey
        hotkey = str(cfg.get("menu_key", ""))
        if hotkey and self.combo_hotkey.findText(hotkey, Qt.MatchFlag.MatchContains) >= 0:
            self.combo_hotkey.setCurrentText(hotkey)

        # Mode A specifics
        if self.active_mode == "A":
            self.chk_bink.setChecked(bool(cfg.get("bink_hook", False)))

        # Mode B specifics
        elif self.active_mode == "B":
            self.chk_blackwell.setChecked(bool(cfg.get("blackwell_kernels", 1)))
            self.chk_isr.setChecked(bool(cfg.get("thin_geometry_isr", 1)))
            self.chk_vwb.setChecked(bool(cfg.get("thin_geometry_vwb", 1)))
            self.chk_bam.setChecked(bool(cfg.get("thin_geometry_bam", 1)))
            self.chk_hdr.setChecked(bool(cfg.get("hdr_ui_recomposition", 1)))
            self.chk_dynamic.setChecked(bool(cfg.get("dynamic_mfg", 0)))
            self.chk_temporal.setChecked(bool(cfg.get("temporal_fix", 1)))

        # Mode C specifics
        elif self.active_mode == "C":
            fg_out = str(cfg.get("fg_output", "xefg")).lower()
            self.combo_fg_out.setCurrentIndex(1 if "fsr" in fg_out else 0)

            fg_in = str(cfg.get("fg_input", "dlssg")).lower()
            self.combo_fg_in.setCurrentIndex(1 if "fsr" in fg_in else 0)

            self.chk_rcas.setChecked(bool(cfg.get("rcas_enabled", False)))
            rcas_val = float(cfg.get("rcas_sharpness", 0.20))
            self.slider_rcas.setValue(int(rcas_val * 100))
            self.lbl_rcas_val.setText(f"{rcas_val:.2f}")

        self._is_loading = False

    def get_params(self) -> Dict[str, Any]:
        mul_vals = [2, 3, 4, 6]
        mul = mul_vals[self.combo_multiplier.currentIndex()]

        preset_vals = ["Default", "Preset J", "Preset K", "Preset M"]
        dlss_preset = preset_vals[self.combo_dlss_preset.currentIndex()]

        hotkey = self.combo_hotkey.currentText()

        params = {
            "multiplier": mul,
            "dlss_preset": dlss_preset,
            "menu_key": hotkey,
            "bink_hook": self.chk_bink.isChecked(),
            "blackwell_kernels": 1 if self.chk_blackwell.isChecked() else 0,
            "thin_geometry_isr": 1 if self.chk_isr.isChecked() else 0,
            "thin_geometry_vwb": 1 if self.chk_vwb.isChecked() else 0,
            "thin_geometry_bam": 1 if self.chk_bam.isChecked() else 0,
            "hdr_ui_recomposition": 1 if self.chk_hdr.isChecked() else 0,
            "dynamic_mfg": 1 if self.chk_dynamic.isChecked() else 0,
            "temporal_fix": 1 if self.chk_temporal.isChecked() else 0,
            "fg_output": "xefg" if self.combo_fg_out.currentIndex() == 0 else "fsrfg",
            "fg_input": "dlssg" if self.combo_fg_in.currentIndex() == 0 else "fsr3",
            "rcas_enabled": self.chk_rcas.isChecked(),
            "rcas_sharpness": self.slider_rcas.value() / 100.0,
            "dx12_upscaler": "dlss"
        }
        return params

    def on_save_config_clicked(self):
        if not self.current_game_info or not self.current_game_info.get("target_dir"):
            QMessageBox.warning(self, "提示", "请先选择目标游戏！")
            return

        td = Path(self.current_game_info["target_dir"])
        game_name = self.current_game_info.get("name", "当前游戏")
        game_exe = self.current_game_info.get("exe", "game.exe")
        params = self.get_params()

        # Update global presets and disk configs
        if self.active_mode == "A":
            preset_a = load_mode_a_preset()
            preset_a["multiplier"] = params["multiplier"]
            preset_a["dlss_preset"] = params["dlss_preset"]
            preset_a["menu_key"] = params["menu_key"]
            preset_a["bink_hook"] = params["bink_hook"]
            save_mode_a_preset(preset_a)
            if td.exists():
                IniConfigManager.sync_mode_a_forward(td, preset_a)

        elif self.active_mode == "B":
            preset_b = load_reshade_preset()
            preset_b["force_multiplier"] = params["multiplier"]
            preset_b["blackwell_kernels"] = params["blackwell_kernels"]
            preset_b["thin_geometry_isr"] = params["thin_geometry_isr"]
            preset_b["thin_geometry_vwb"] = params["thin_geometry_vwb"]
            preset_b["thin_geometry_bam"] = params["thin_geometry_bam"]
            preset_b["hdr_ui_recomposition"] = params["hdr_ui_recomposition"]
            preset_b["dynamic_mfg"] = params["dynamic_mfg"]
            preset_b["temporal_fix"] = params["temporal_fix"]
            save_reshade_preset(preset_b)
            if td.exists():
                IniConfigManager.sync_mode_b_forward(td, preset_b)

        elif self.active_mode == "C":
            preset_c = load_optiscaler_preset()
            preset_c["interpolation_count"] = max(1, params["multiplier"] - 1)
            preset_c["dlss_preset"] = "K" if "K" in params["dlss_preset"] else ("J" if "J" in params["dlss_preset"] else "Default")
            preset_c["menu_key"] = params["menu_key"]
            preset_c["fg_output"] = params["fg_output"]
            preset_c["fg_input"] = params["fg_input"]
            preset_c["dx12_upscaler"] = "dlss"
            preset_c["rcas_enabled"] = params["rcas_enabled"]
            preset_c["rcas_sharpness"] = params["rcas_sharpness"]
            save_optiscaler_preset(preset_c)
            if td.exists():
                IniConfigManager.sync_mode_c_forward(td, preset_c, exe_name=game_exe)

        QMessageBox.information(
            self,
            "保存成功",
            f"✅ 已成功将【模式 {self.active_mode}】插帧配置写入游戏【{game_name}】目录！\n\n"
            f"• 插帧倍率：{params['multiplier']}X\n"
            f"• 超分预设：{params['dlss_preset']}\n"
            f"• 呼出热键：{params['menu_key']}"
        )
        if self.parent_window and hasattr(self.parent_window, "refresh_current_game_status"):
            self.parent_window.refresh_current_game_status()

    def on_apply_all_clicked(self):
        if not self.current_game_info or not self.current_game_info.get("target_dir"):
            QMessageBox.warning(self, "提示", "请先选择目标游戏！")
            return

        td = self.current_game_info["target_dir"]
        game_exe = self.current_game_info.get("exe", "")
        params = self.get_params()

        ok, msg = ConfigSyncService.apply_unified_configuration(td, game_exe, self.active_mode, params)
        if ok:
            QMessageBox.information(self, "部署成功", msg)
        else:
            QMessageBox.critical(self, "部署失败", msg)

        if self.parent_window and hasattr(self.parent_window, "refresh_current_game_status"):
            self.parent_window.refresh_current_game_status()

    def _open_advanced_dialog(self):
        try:
            from apps.app2_mfg.gui_qt import OptiScalerPresetDialog
            g_obj = self.current_game_info.get("game_obj") if self.current_game_info else None
            is_dark = getattr(self.parent_window, "is_dark_mode", False) if self.parent_window else False
            dlg = OptiScalerPresetDialog(
                parent=self.parent_window or self,
                is_dark=is_dark,
                game=g_obj,
                initial_mode=self.active_mode
            )
            if dlg.exec():
                self.load_config()
                if self.parent_window and hasattr(self.parent_window, "refresh_current_game_status"):
                    self.parent_window.refresh_current_game_status()
        except Exception as e:
            QMessageBox.warning(self, "打开高级预设", f"打开高级预设面板异常: {e}")

    def apply_theme(self, is_dark: bool):
        card_bg = "#222325" if is_dark else "#F8FAFC"
        border = "#383A3C" if is_dark else "#E2E8F0"
        text_c = "#E8E8E8" if is_dark else "#1A1A1A"
        sub_c = "#94A3B8" if is_dark else "#64748B"
        btn_green = "#10B981" if is_dark else "#16A34A"
        btn_green_hover = "#059669" if is_dark else "#15803D"
        btn_sec_bg = "#334155" if is_dark else "#F1F5F9"
        btn_sec_border = "#475569" if is_dark else "#CBD5E1"
        btn_sec_hover = "#475569" if is_dark else "#E2E8F0"
        btn_sec_text = "#F8FAFC" if is_dark else "#1E293B"

        self.lbl_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {text_c};")
        self.lbl_mul.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {text_c};")
        self.lbl_preset.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {text_c};")
        self.lbl_key.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {text_c};")
        self.lbl_mode_summary.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {'#34D399' if is_dark else '#059669'};")
        self.lbl_note_a.setStyleSheet(f"font-size: 11px; color: {sub_c}; line-height: 140%;")
        self.lbl_note_b.setStyleSheet(f"font-size: 11px; color: {sub_c}; line-height: 140%;")
        self.lbl_note_c.setStyleSheet(f"font-size: 11px; color: {sub_c}; line-height: 140%;")

        self.common_frame.setStyleSheet(f"""
            QFrame#CommonParamsFrame {{
                background-color: {card_bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
        """)

        self.btn_open_advanced.setStyleSheet(f"""
            QPushButton#BtnOpenAdvanced {{
                background-color: transparent;
                color: {'#38BDF8' if is_dark else '#0284C7'};
                font-size: 12px;
                font-weight: 600;
                border: 1px solid {'#38BDF8' if is_dark else '#0284C7'};
                border-radius: 6px;
                padding: 4px 10px;
            }}
            QPushButton#BtnOpenAdvanced:hover {{
                background-color: {'#38BDF8' if is_dark else '#0284C7'};
                color: #FFFFFF;
            }}
        """)

        self.btn_sync_config.setStyleSheet(f"""
            QPushButton#BtnSyncConfig {{
                background-color: {btn_sec_bg};
                color: {btn_sec_text};
                font-size: 13px;
                font-weight: 600;
                border: 1px solid {btn_sec_border};
                border-radius: 8px;
                padding: 6px 14px;
            }}
            QPushButton#BtnSyncConfig:hover {{
                background-color: {btn_sec_hover};
            }}
        """)

        self.btn_apply_all.setStyleSheet(f"""
            QPushButton#BtnApplyAll {{
                background-color: {btn_green};
                color: #FFFFFF;
                font-size: 13px;
                font-weight: 700;
                border: none;
                border-radius: 8px;
                padding: 6px 14px;
            }}
            QPushButton#BtnApplyAll:hover {{
                background-color: {btn_green_hover};
            }}
        """)


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

        self.badge_ver = QLabel("v1.0.0 · 智能共存版")
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
            "为支持 DLSS 的游戏注入下一代神经网络画质引擎，内建 ReShade/RHI 运行底座，并与多帧生成补丁 (RHI / OptiScaler) 智能避让与链式共存。"
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

        # ------------------ 2.5 MULTI-FRAME GENERATION LINKAGE PANEL ------------------
        self.mfg_panel = MultiFrameGenPanel(self)
        vbox.addWidget(self.mfg_panel)

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
            "<b>2. 多帧生成 (插帧) 避让与共存机制</b>：<br>"
            "• <b>RHI 插帧 (RenoDX) 避让机制</b>：若目标游戏已注入 RHI 插帧 (RenoDX Add-on)，其底层本身已是 ReShade 64-bit 宿主。本工具严格遵循<b>【RHI 插帧免重装避让】</b>准则，绝不覆盖或重复安装底座，仅将 DLSS 5 并联挂载至现有 <code>ReShade.ini</code>，两套插件零冲突协同运行。<br>"
            "• <b>OptiScaler 插帧共存机制</b>：若目标游戏已注入 OptiScaler 跨卡插帧，本工具采用<b>【链式协同共存】</b>方案：在游戏根目录部署 <code>ReShade64.dll</code> 并在 <code>OptiScaler.ini</code> 中开启 <code>LoadReshade = true</code>，使 OptiScaler 自动链式唤起 ReShade 与 DLSS 5 插件，达成<b>【OptiScaler 多倍插帧 + DLSS 5 神经重构】</b>双引擎完美共存！<br>"
            "• <b>无损还原保护</b>：卸载还原时智能识别模组归属，仅移除 DLSS 5 插件，完整保留任何已存在的多帧生成环境与配置文件。<br><br>"
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

        if hasattr(self, "mfg_panel"):
            self.mfg_panel.set_game(self.current_game_info)

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
            self.update_alert_box("default", "未选择游戏")
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
            if status.get("host_ready", False):
                self.block_dlss5.set_status("🟢 已注入生效", c_green, "DLSS 5 插件与 ReShade 底座就绪")
                self.btn_inject.setText("⚡ 重新覆盖注入 DLSS 5")
            else:
                self.block_dlss5.set_status("⚠️ 宿主底座未就绪", c_yellow, "缺少有效 ReShade 宿主，点击修复")
                self.btn_inject.setText("🛠️ 一键修复底座并启动 DLSS 5")
            self.btn_restore.setEnabled(True)
        else:
            self.block_dlss5.set_status("⚪ 未注入", c_gray, "点击下方按钮一键注入")
            self.btn_inject.setText("⚡ 一键注入 DLSS 5")
            self.btn_restore.setEnabled(False)

        self.btn_inject.setEnabled(True)
        self.btn_inject_base.setEnabled(True)

        # 2. Frame Generation Block
        if fg_info["is_rhi_fg"]:
            self.block_fg.set_status("🟢 RHI RenoDX 插帧", c_green, "ReShade Addon (免重装底座)")
            self.btn_inject_base.setText("🛡️ ReShade 底座已由 RHI 插帧提供 (免重装)")
            self.btn_inject_base.setToolTip("当前游戏已由 RHI RenoDX 插帧提供 ReShade 核心底座，无需重复安装")
        elif fg_info["is_optiscaler_fg"]:
            self.block_fg.set_status("🟢 OptiScaler 跨卡插帧", c_green, "FSR 3.1 FG (支持链式共存)")
            if status["has_reshade64"] and status.get("opti_reshade_enabled"):
                self.btn_inject_base.setText("🟢 ReShade64 链式底座已就绪 (与 OptiScaler 共存)")
                self.btn_inject_base.setToolTip("已成功部署 ReShade64.dll 且 OptiScaler.ini 已开启 LoadReshade=true")
            else:
                self.btn_inject_base.setText("🔗 部署 ReShade64 链式底座 (与 OptiScaler 共存)")
                self.btn_inject_base.setToolTip("为当前 OptiScaler 游戏部署 ReShade64.dll 并开启 OptiScaler.ini 链式唤起")
        elif fg_info["is_dashdog_fg"]:
            self.block_fg.set_status("🟢 Dashdog 独立插帧", c_green, "独立代理 (无冲突共存)")
            self.btn_inject_base.setText("🛠️ 一键物理注入 ReShade / RHI 底座")
            self.btn_inject_base.setToolTip("直接为游戏物理注入 ReShade 6.8 核心底座 (dxgi.dll) 与基础配置")
        else:
            self.block_fg.set_status("⚪ 未检测到插帧", c_gray, "标准模式")
            self.btn_inject_base.setText("🛠️ 一键物理注入 ReShade / RHI 底座")
            self.btn_inject_base.setToolTip("直接为游戏物理注入 ReShade 6.8 核心底座 (dxgi.dll) 与基础配置")

        # 3. ReShade / RHI Block
        if fg_info["is_optiscaler_fg"]:
            if status["has_reshade64"] and status.get("opti_reshade_enabled"):
                self.block_reshade.set_status("🟢 ReShade64 链式就绪", c_green, "OptiScaler LoadReshade=true")
            elif status["has_reshade64"]:
                self.block_reshade.set_status("🟡 链式开关待激活", c_yellow, "需在 OptiScaler.ini 开启 LoadReshade")
            else:
                self.block_reshade.set_status("⚪ 待部署 ReShade64", c_gray, "点击下方按钮或一键注入即可部署")
        elif fg_info["is_rhi_fg"]:
            self.block_reshade.set_status("🟢 RHI 底座托管中", c_green, "ReShade 64-bit Full Addon (免重装)")
        elif status["is_addon_supported"]:
            self.block_reshade.set_status("🟢 底座就绪", c_green, "ReShade 64-bit Full Addon")
        elif status["is_reshade"]:
            self.block_reshade.set_status("🟡 标准 ReShade 底座", c_yellow, "无插件扩展，注入时将补齐")
        elif status.get("is_dxgi_optiscaler"):
            self.block_reshade.set_status("⚠️ 孤立 OptiScaler", c_yellow, "检测到孤立 OptiScaler，注入时自动修复为 ReShade")
        elif status["has_dxgi"]:
            self.block_reshade.set_status("🔵 第三方 dxgi.dll", c_blue, "已存在其他代理 DLL")
        else:
            self.block_reshade.set_status("⚪ 缺失底座", c_gray, "注入 DLSS 5 时全自动补全")

        # 4. Avoidance / Coexistence Block
        if fg_info["is_rhi_fg"]:
            self.block_avoidance.set_status("🛡️ RHI 避让生效", c_blue, "共用现有 ReShade 底座，免重复安装")
            self.update_alert_box(
                "rhi",
                "【RHI 插帧底座避让生效】：检测到游戏已注入 RHI (RenoDX) 插帧。ReShade 底座已由 RHI 完备提供，"
                "程序已自动跳过底座安装，直接将 DLSS 5 并联挂载，免重复安装且两套模组零冲突并存！"
            )
        elif fg_info["is_optiscaler_fg"]:
            self.block_avoidance.set_status("🟢 链式共存模式", c_green, "OptiScaler 插帧 + DLSS 5 协同运行")
            self.update_alert_box(
                "optiscaler",
                "【OptiScaler 链式共存模式】：检测到游戏已注入 OptiScaler 跨卡插帧。本工具通过部署 ReShade64.dll 并配置 "
                "OptiScaler 链式唤起，实现【OptiScaler 多倍插帧 + DLSS 5 神经重构】双引擎协同共存！"
            )
        elif fg_info["is_dashdog_fg"]:
            self.block_avoidance.set_status("🟢 独立共存模式", c_green, "Dashdog 插帧 + DLSS 5 协同运行")
            self.update_alert_box(
                "dashdog",
                "【Dashdog 独立共存模式】：检测到当前游戏已注入 Dashdog 多帧生成补丁，支持与 ReShade/DLSS 5 协同并存运行。"
            )
        else:
            self.block_avoidance.set_status("⚪ 独立底座模式", c_gray, "独占 ReShade 6.8 底座")
            self.update_alert_box(
                "default",
                "【标准独立底座模式】：当前游戏未注入多帧生成补丁，注入 DLSS 5 时将自动部署 ReShade 6.8 核心宿主底座与默认配置文件。"
            )

    def update_alert_box(self, mode: str, text: str):
        is_dark = getattr(self, "is_dark_mode", False)
        self.lbl_alert_text.setText(text)
        if mode in ["rhi", "shield"]:
            self.lbl_alert_icon.setText("🛡️")
            bg = "#1B2A32" if is_dark else "#F0F9FF"
            border = "#0284C7" if is_dark else "#BAE6FD"
            txt_color = "#38BDF8" if is_dark else "#0369A1"
        elif mode in ["optiscaler", "green"]:
            self.lbl_alert_icon.setText("🟢")
            bg = "#14291E" if is_dark else "#F0FDF4"
            border = "#10B981" if is_dark else "#BBF7D0"
            txt_color = "#4ADE80" if is_dark else "#15803D"
        elif mode in ["dashdog"]:
            self.lbl_alert_icon.setText("🚀")
            bg = "#231B32" if is_dark else "#FAF5FF"
            border = "#8B5CF6" if is_dark else "#DDD6FE"
            txt_color = "#A78BFA" if is_dark else "#6D28D9"
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
        """Performs one-click injection with Frame Generation collision avoidance and unified config sync."""
        if not self.current_game_info or not self.current_game_info.get("target_dir"):
            QMessageBox.warning(self, "提示", "请先选择目标游戏！")
            return

        target_dir = self.current_game_info["target_dir"]
        game_name = self.current_game_info.get("name", "选中游戏")
        game_exe = self.current_game_info.get("exe", "")

        # If MultiFrameGenPanel is available, perform transactional unified deployment
        if hasattr(self, "mfg_panel") and self.mfg_panel and self.mfg_panel.isEnabled():
            params = self.mfg_panel.get_params()
            mode = self.mfg_panel.active_mode
            ok, msg = ConfigSyncService.apply_unified_configuration(target_dir, game_exe, mode, params)
        else:
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
        for card_name in ["banner_card", "game_card", "mfg_panel", "action_card", "guide_card"]:
            if hasattr(self, card_name):
                getattr(self, card_name).setStyleSheet(card_style)

        if hasattr(self, "mfg_panel"):
            self.mfg_panel.apply_theme(is_dark)

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
