# -*- coding: utf-8 -*-
"""
App 3: Windows Auto HDR 管理器 (Auto HDR Force Manager)
Reconstructed to fully unify with DM Hardware Master (app1) Fluent Light Modern Card theme.
"""

import os
import sys
import winreg
import ctypes
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QPoint
from PySide6.QtGui import QIcon, QFont, QPixmap, QColor
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QMessageBox, QLabel, QComboBox, QFrame, QLineEdit, QScrollArea,
    QSizePolicy
)

# Ensure root dir is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common.ui_theme import BaseWindow, LIGHT_STYLE_SHEET, DARK_STYLE_SHEET, ModernProgressDialog
from common.config_manager import init_app_config, get_app_cache_dir

REG_PATH = r"SOFTWARE\Microsoft\Direct3D"
MODE_DISABLED = "⚪ 未开启 (Disabled)"
MODE_8BIT = "💎 强制 Auto HDR (8-bit)"
MODE_10BIT = "✨ 强制 Auto HDR (10-bit)"

VAL_8BIT = "BufferUpgradeOverride=1"
VAL_10BIT = "BufferUpgradeOverride=1;BufferUpgradeEnable10Bit=1"


def get_resource_path(relative_path: str) -> str:
    base = Path(__file__).resolve().parent
    p = base / relative_path
    if p.exists():
        return str(p)
    common_p = ROOT_DIR / "common" / "assets" / relative_path
    if common_p.exists():
        return str(common_p)
    return str(p)


class AutoHDRManager:
    @staticmethod
    def ensure_root_key():
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_PATH) as _:
                pass
            return True
        except Exception:
            return False

    @staticmethod
    def list_applications():
        apps = []
        AutoHDRManager.ensure_root_key()
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ) as root:
                idx = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(root, idx)
                        idx += 1
                        if subkey_name == "MostRecentApplication":
                            continue

                        sub_path = f"{REG_PATH}\\{subkey_name}"
                        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_path, 0, winreg.KEY_READ) as subkey:
                            try:
                                name_val, _ = winreg.QueryValueEx(subkey, "Name")
                            except FileNotFoundError:
                                name_val = ""

                            try:
                                behav_val, _ = winreg.QueryValueEx(subkey, "D3DBehaviors")
                            except FileNotFoundError:
                                behav_val = ""

                            apps.append({
                                "key_name": subkey_name,
                                "path": name_val,
                                "behavior": behav_val
                            })
                    except OSError:
                        break
        except Exception:
            pass
        return apps

    @staticmethod
    def find_free_subkey():
        AutoHDRManager.ensure_root_key()
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ) as root:
            idx = 0
            while True:
                name = f"Application{idx}"
                try:
                    with winreg.OpenKey(root, name, 0, winreg.KEY_READ):
                        idx += 1
                except FileNotFoundError:
                    return name

    @staticmethod
    def save_app(key_name, path, mode_str):
        AutoHDRManager.ensure_root_key()
        sub_path = f"{REG_PATH}\\{key_name}"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, sub_path) as key:
            winreg.SetValueEx(key, "Name", 0, winreg.REG_SZ, path)
            if MODE_10BIT in mode_str:
                winreg.SetValueEx(key, "D3DBehaviors", 0, winreg.REG_SZ, VAL_10BIT)
            elif MODE_8BIT in mode_str:
                winreg.SetValueEx(key, "D3DBehaviors", 0, winreg.REG_SZ, VAL_8BIT)
            else:
                try:
                    winreg.DeleteValue(key, "D3DBehaviors")
                except FileNotFoundError:
                    pass

    @staticmethod
    def delete_app(key_name):
        try:
            sub_path = f"{REG_PATH}\\{key_name}"
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sub_path)
            return True
        except Exception:
            return False


class AutoHDRWindow(BaseWindow):
    def __init__(self):
        super().__init__(
            title="DM工具箱 - Windows Auto HDR 管理器",
            icon_filename="autohdr_icon.png",
            width=960,
            height=640
        )
        self.subapp_id = "app3_autohdr"
        self.setAcceptDrops(True)
        self.all_apps = []
        self.filtered_apps = []

        # Auto init config in C:/ToolboxData/config/app3_autohdr/
        self.config_path = init_app_config(
            "app3_autohdr",
            "settings.json",
            default_dict={"default_mode": "10bit"}
        )

        self.init_ui()
        self.load_data()

    def init_ui(self):
        # 1. 顶部 Hero Banner 卡片 (统一 Fluent Modern Card 样式)
        banner_card = QFrame()
        banner_card.setProperty("class", "GridCard")
        self.banner_card = banner_card
        b_layout = QHBoxLayout(banner_card)
        b_layout.setContentsMargins(22, 16, 22, 16)
        b_layout.setSpacing(16)

        # 图标
        icon_lbl = QLabel()
        icon_path = get_resource_path("icon.png")
        if os.path.exists(icon_path):
            pix = QPixmap(icon_path).scaled(46, 46, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_lbl.setPixmap(pix)
        b_layout.addWidget(icon_lbl)

        # 标题与描述
        info_box = QVBoxLayout()
        info_box.setSpacing(3)

        title_row = QHBoxLayout()
        title_row.setSpacing(10)

        t_lbl = QLabel("Windows Auto HDR 强制开启管理器")
        t_lbl.setProperty("class", "CardTitle")
        self.t_lbl = t_lbl
        title_row.addWidget(t_lbl)

        self.badge_count = QLabel("已配置 0 款游戏")
        self.badge_count.setStyleSheet("""
            color: #2F8F5B;
            font-size: 11px;
            font-weight: 700;
            background-color: #F5F5F5;
            padding: 3px 10px;
            border-radius: 8px;
            border: 1px solid #D4D4D4;
        """)
        title_row.addWidget(self.badge_count)
        title_row.addStretch()
        info_box.addLayout(title_row)

        d_lbl = QLabel("为未认证或未自动触发的 Direct3D 游戏强制开启 Windows 11 高动态范围 (Auto HDR) 渲染与 10-Bit 色深缓冲。")
        d_lbl.setProperty("class", "CardSubtitle")
        self.d_lbl = d_lbl
        info_box.addWidget(d_lbl)

        b_layout.addLayout(info_box, 1)
        self.body_layout.addWidget(banner_card)

        # 2. 控制操作栏
        ctrl_card = QFrame()
        ctrl_card.setProperty("class", "GridCard")
        self.ctrl_card = ctrl_card
        ctrl_layout = QVBoxLayout(ctrl_card)
        ctrl_layout.setContentsMargins(20, 14, 20, 14)
        ctrl_layout.setSpacing(10)

        # Row 1: single-item actions + search
        c_row1 = QHBoxLayout()
        c_row1.setSpacing(14)

        self.btn_add = QPushButton("➕ 添加游戏 / 程序")
        self.btn_add.setProperty("class", "PrimaryBtn")
        self.btn_add.setMinimumHeight(38)
        self.btn_add.setCursor(Qt.PointingHandCursor)
        self.btn_add.clicked.connect(self.on_add_game)
        c_row1.addWidget(self.btn_add)

        self.btn_refresh = QPushButton("🔄 刷新注册表")
        self.btn_refresh.setProperty("class", "OutlineBtn")
        self.btn_refresh.setMinimumHeight(38)
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.clicked.connect(self.load_data)
        c_row1.addWidget(self.btn_refresh)

        c_row1.addStretch()

        # 搜索框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 快速搜索已配置的游戏名称或路径...")
        self.search_input.setFixedWidth(280)
        self.search_input.setMinimumHeight(36)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #D4D4D4;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 13px;
                color: #2A2B2C;
            }
            QLineEdit:focus {
                border-color: #2F8F5B;
            }
        """)
        self.search_input.textChanged.connect(self.filter_data)
        c_row1.addWidget(self.search_input)
        ctrl_layout.addLayout(c_row1)

        # Row 2: one-click batch enable / disable for every configured game
        c_row2 = QHBoxLayout()
        c_row2.setSpacing(10)

        lbl_batch = QLabel("批量控制：")
        lbl_batch.setStyleSheet("font-size: 12px; font-weight: 700; color: #4A4A4A;")
        self.lbl_batch = lbl_batch
        c_row2.addWidget(lbl_batch)

        self.btn_enable_all = QPushButton("⚡ 一键全部开启 (10-bit)")
        self.btn_enable_all.setProperty("class", "PrimaryBtn")
        self.btn_enable_all.setMinimumHeight(34)
        self.btn_enable_all.setMinimumWidth(190)
        self.btn_enable_all.setCursor(Qt.PointingHandCursor)
        self.btn_enable_all.setToolTip("把列表中所有游戏统一设为【强制 Auto HDR (10-bit)】")
        self.btn_enable_all.clicked.connect(self.on_enable_all)
        c_row2.addWidget(self.btn_enable_all)

        self.btn_disable_all = QPushButton("🛑 一键全部关闭")
        self.btn_disable_all.setProperty("class", "DangerBtn")
        self.btn_disable_all.setMinimumHeight(34)
        self.btn_disable_all.setMinimumWidth(150)
        self.btn_disable_all.setCursor(Qt.PointingHandCursor)
        self.btn_disable_all.setToolTip("把列表中所有游戏统一设为【未开启 (Disabled)】，立即恢复游戏原生 HDR 行为")
        self.btn_disable_all.clicked.connect(self.on_disable_all)
        c_row2.addWidget(self.btn_disable_all)

        lbl_batch_hint = QLabel("对全部已配置游戏生效（不受搜索筛选影响）· 立即写入注册表")
        lbl_batch_hint.setStyleSheet("font-size: 11px; color: #94A3B8;")
        self.lbl_batch_hint = lbl_batch_hint
        c_row2.addWidget(lbl_batch_hint)

        c_row2.addStretch()
        ctrl_layout.addLayout(c_row2)

        self.body_layout.addWidget(ctrl_card)

        # 3. 游戏列表表格卡片
        table_card = QFrame()
        table_card.setProperty("class", "GridCard")
        self.table_card = table_card
        t_layout = QVBoxLayout(table_card)
        t_layout.setContentsMargins(18, 16, 18, 16)
        t_layout.setSpacing(10)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["序号", "游戏可执行程序路径", "Auto HDR 强化运行模式", "操作"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 55)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(2, 280)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(3, 95)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        t_layout.addWidget(self.table)
        self.body_layout.addWidget(table_card, 1)

        # 应用当前日间/夜间模式样式
        self.apply_theme()

    def apply_theme(self):
        """深度应用当前日间 / 夜间模式，重绘表格、下拉框与搜索框"""
        super().apply_theme()
        has_wp = bool(getattr(self, "wallpaper_pixmap", None) and not self.wallpaper_pixmap.isNull() and getattr(self, "wallpaper_config", {}).get("enabled", False))
        card_op = float(getattr(self, "wallpaper_config", {}).get("card_opacity", 0.86))

        # Acrylic styling for 3 main cards
        card_bg = f"rgba(26, 28, 36, {card_op:.2f})" if self.is_dark_mode else f"rgba(255, 255, 255, {card_op:.2f})"
        card_border = "rgba(255, 255, 255, 0.12)" if self.is_dark_mode else "rgba(0, 0, 0, 0.08)"
        solid_bg = "#2A2B2C" if self.is_dark_mode else "#FFFFFF"
        solid_border = "#3A3A3A" if self.is_dark_mode else "#E5E5E5"

        active_card_bg = card_bg if has_wp else solid_bg
        active_border = card_border if has_wp else solid_border

        for card in [getattr(self, "banner_card", None), getattr(self, "ctrl_card", None), getattr(self, "table_card", None)]:
            if card:
                card.setStyleSheet(f"""
                    QFrame {{
                        background-color: {active_card_bg};
                        border: 1px solid {active_border};
                        border-radius: 14px;
                    }}
                """)

        # Crisp high-contrast title and subtitle
        if hasattr(self, "t_lbl") and self.t_lbl:
            self.t_lbl.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {'#F9FAFB' if self.is_dark_mode else '#111827'};")
        if hasattr(self, "d_lbl") and self.d_lbl:
            self.d_lbl.setStyleSheet(f"font-size: 12px; color: {'#CBD5E1' if self.is_dark_mode else '#374151'};")

        # 1. 搜索框样式响应
        if hasattr(self, "search_input") and self.search_input:
            if self.is_dark_mode:
                self.search_input.setStyleSheet("""
                    QLineEdit {
                        background-color: #2A2B2C;
                        border: 1px solid #4A4A4A;
                        border-radius: 8px;
                        padding: 6px 12px;
                        font-size: 13px;
                        color: #F5F5F5;
                    }
                    QLineEdit:focus {
                        border-color: #8FE3B0;
                    }
                """)
            else:
                self.search_input.setStyleSheet("""
                    QLineEdit {
                        background-color: #FFFFFF;
                        border: 1px solid #D4D4D4;
                        border-radius: 8px;
                        padding: 6px 12px;
                        font-size: 13px;
                        color: #2A2B2C;
                    }
                    QLineEdit:focus {
                        border-color: #2F8F5B;
                    }
                """)

        # 2. 批量控制栏标签配色 + 顶部计数徽标（统一 DM 中性风格）
        if hasattr(self, "badge_count") and self.badge_count:
            if self.is_dark_mode:
                self.badge_count.setStyleSheet(
                    "color: #A0A0A0; background-color: #303132; border: 1px solid #3A3A3A;"
                    " padding: 3px 10px; border-radius: 8px; font-size: 11px; font-weight: 700;"
                )
            else:
                self.badge_count.setStyleSheet(
                    "color: #5A5A5A; background-color: #EFEFEF; border: 1px solid #E5E5E5;"
                    " padding: 3px 10px; border-radius: 8px; font-size: 11px; font-weight: 700;"
                )
        if hasattr(self, "lbl_batch") and self.lbl_batch:
            self.lbl_batch.setStyleSheet(
                f"font-size: 12px; font-weight: 700; color: {'#A0A0A0' if self.is_dark_mode else '#4A4A4A'};"
            )
        if hasattr(self, "btn_enable_all") and hasattr(self, "btn_disable_all") and self.btn_enable_all:
            if self.is_dark_mode:
                self.btn_enable_all.setStyleSheet(
                    "QPushButton { background-color: #303132; color: #E8E8E8; border: 1px solid #4A4A4A;"
                    " border-radius: 8px; padding: 6px 16px; font-weight: 700; }"
                    "QPushButton:hover { background-color: #6FD398; color: #FFFFFF; border-color: #6FD398; }"
                )
                self.btn_disable_all.setStyleSheet(
                    "QPushButton { background-color: #303132; color: #F87171; border: 1px solid #4A4A4A;"
                    " border-radius: 8px; padding: 6px 16px; font-weight: 700; }"
                    "QPushButton:hover { background-color: #3A3A3A; color: #FCA5A5; }"
                )
            else:
                self.btn_enable_all.setStyleSheet(
                    "QPushButton { background-color: #E8E8E8; color: #1A1A1A; border: 1px solid #D4D4D4;"
                    " border-radius: 8px; padding: 6px 16px; font-weight: 700; }"
                    "QPushButton:hover { background-color: #2F8F5B; color: #FFFFFF; border-color: #2F8F5B; }"
                )
                self.btn_disable_all.setStyleSheet(
                    "QPushButton { background-color: #F5F5F5; color: #B91C1C; border: 1px solid #E5E5E5;"
                    " border-radius: 8px; padding: 6px 16px; font-weight: 700; }"
                    "QPushButton:hover { background-color: #FEE2E2; border-color: #FCA5A5; }"
                )
        if hasattr(self, "lbl_batch_hint") and self.lbl_batch_hint:
            self.lbl_batch_hint.setStyleSheet(
                f"font-size: 11px; color: {'#64748B' if self.is_dark_mode else '#94A3B8'};"
            )

        # 3. 表格控件样式响应 (彻底解决黑夜模式反白与显示不全)
        if hasattr(self, "table") and self.table:
            if self.is_dark_mode:
                self.table.setStyleSheet("""
                    QTableWidget {
                        background-color: #2A2B2C;
                        alternate-background-color: #292929;
                        border: 1px solid #3A3A3A;
                        border-radius: 12px;
                        outline: none;
                        gridline-color: transparent;
                        color: #F5F5F5;
                        font-size: 13px;
                    }
                    QTableWidget::item {
                        padding: 8px 10px;
                        border-bottom: 1px solid #3A3A3A;
                        color: #F5F5F5;
                    }
                    QTableWidget::item:selected {
                        background-color: #3A3A3A;
                        color: #7ED9A2;
                    }
                    QHeaderView::section {
                        background-color: #292929;
                        color: #94A3B8;
                        font-weight: 700;
                        font-size: 13px;
                        padding: 10px 10px;
                        border: none;
                        border-bottom: 2px solid #3A3A3A;
                    }
                    QTableCornerButton::section {
                        background-color: #292929;
                        border: none;
                    }
                """)
            else:
                self.table.setStyleSheet("""
                    QTableWidget {
                        background-color: #FFFFFF;
                        alternate-background-color: #F5F5F5;
                        border: 1px solid #E5E5E5;
                        border-radius: 12px;
                        outline: none;
                        gridline-color: transparent;
                        color: #292929;
                        font-size: 13px;
                    }
                    QTableWidget::item {
                        padding: 8px 10px;
                        border-bottom: 1px solid #EFEFEF;
                        color: #292929;
                    }
                    QTableWidget::item:selected {
                        background-color: #F5F5F5;
                        color: #2F8F5B;
                    }
                    QHeaderView::section {
                        background-color: #F5F5F5;
                        color: #4A4A4A;
                        font-weight: 700;
                        font-size: 13px;
                        padding: 10px 10px;
                        border: none;
                        border-bottom: 2px solid #E5E5E5;
                    }
                    QTableCornerButton::section {
                        background-color: #F5F5F5;
                        border: none;
                    }
                """)

            if hasattr(self, "filtered_apps") and self.filtered_apps:
                self.render_table()

    def load_data(self):
        self.all_apps = AutoHDRManager.list_applications()
        self.badge_count.setText(f"已配置 {len(self.all_apps)} 款游戏")
        self.filter_data()
        self.set_status(f"已从 Windows 注册表读取 {len(self.all_apps)} 个 Direct3D Auto HDR 配置项。")

    def filter_data(self):
        keyword = self.search_input.text().strip().lower() if hasattr(self, "search_input") else ""
        if keyword:
            self.filtered_apps = [
                app for app in self.all_apps
                if keyword in app["path"].lower() or keyword in app["key_name"].lower()
            ]
        else:
            self.filtered_apps = list(self.all_apps)

        self.render_table()

    def render_table(self):
        # Remove previous cell widgets synchronously: on a theme switch a deferred-delete
        # ghost widget would otherwise overlap the freshly created combo for one frame.
        for r in range(self.table.rowCount()):
            for c in (2, 3):
                old = self.table.cellWidget(r, c)
                if old is not None:
                    self.table.removeCellWidget(r, c)
                    old.setParent(None)
                    old.deleteLater()

        self.table.setRowCount(len(self.filtered_apps))

        for row_idx, app in enumerate(self.filtered_apps):
            key_name = app["key_name"]
            path = app["path"]
            behav = app["behavior"]

            # 1. 序号
            item_num = QTableWidgetItem(f"{row_idx + 1}")
            item_num.setTextAlignment(Qt.AlignCenter)
            item_num.setFlags(Qt.ItemIsEnabled)
            item_num.setForeground(QColor("#94A3B8" if self.is_dark_mode else "#64748B"))
            self.table.setItem(row_idx, 0, item_num)

            # 2. 路径与文件名
            exe_name = os.path.basename(path) if path else "未知程序"
            item_path = QTableWidgetItem(f"{exe_name}\n{path}")
            item_path.setToolTip(path)
            item_path.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            item_path.setFont(QFont("Microsoft YaHei UI", 9, QFont.Bold))
            item_path.setForeground(QColor("#F5F5F5" if self.is_dark_mode else "#292929"))
            self.table.setItem(row_idx, 1, item_path)

            # 3. 运行模式下拉框 (主题自适应与圆角优化)
            combo = QComboBox()
            combo.addItems([MODE_10BIT, MODE_8BIT, MODE_DISABLED])
            combo.setCursor(Qt.PointingHandCursor)
            combo.setMinimumWidth(240)
            combo.setMinimumHeight(34)
            if self.is_dark_mode:
                combo.setStyleSheet("""
                    QComboBox {
                        background-color: #292929;
                        border: 1px solid #3A3A3A;
                        border-radius: 8px;
                        padding: 6px 12px;
                        font-size: 13px;
                        font-weight: 600;
                        color: #F5F5F5;
                    }
                    QComboBox:hover {
                        border-color: #8FE3B0;
                    }
                    /* Native chevron: the old CSS-border triangle hack is unsupported by
                       Qt and left an empty/broken box at the right edge. */
                    QComboBox QAbstractItemView {
                        background-color: #292929;
                        color: #F5F5F5;
                        selection-background-color: #2A2B2C;
                        selection-color: #8FE3B0;
                        border: 1px solid #3A3A3A;
                        border-radius: 8px;
                        padding: 4px;
                    }
                """)
            else:
                combo.setStyleSheet("""
                    QComboBox {
                        background-color: #FFFFFF;
                        border: 1px solid #D4D4D4;
                        border-radius: 8px;
                        padding: 6px 12px;
                        font-size: 13px;
                        font-weight: 600;
                        color: #2A2B2C;
                    }
                    QComboBox:hover {
                        border-color: #94A3B8;
                    }
                    /* Native chevron: see the dark-theme comment above. */
                    QComboBox QAbstractItemView {
                        background-color: #FFFFFF;
                        color: #2A2B2C;
                        selection-background-color: #F5F5F5;
                        selection-color: #2F8F5B;
                        border: 1px solid #D4D4D4;
                        border-radius: 8px;
                        padding: 4px;
                    }
                """)

            if VAL_10BIT in behav:
                combo.setCurrentText(MODE_10BIT)
            elif VAL_8BIT in behav:
                combo.setCurrentText(MODE_8BIT)
            else:
                combo.setCurrentText(MODE_DISABLED)

            # Connect with closure
            combo.currentTextChanged.connect(
                lambda val, k=key_name, p=path: self.on_mode_change(k, p, val)
            )
            combo_container = QWidget()
            c_box = QHBoxLayout(combo_container)
            c_box.setContentsMargins(6, 6, 6, 6)
            c_box.addWidget(combo)
            self.table.setCellWidget(row_idx, 2, combo_container)

            # 4. 删除按钮 (宽度充足，绝不截断)
            del_btn = QPushButton("🗑️ 移除")
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.setMinimumHeight(32)
            if self.is_dark_mode:
                del_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #303132;
                        color: #F87171;
                        border: 1px solid #4A4A4A;
                        border-radius: 6px;
                        padding: 4px 10px;
                        font-size: 12px;
                        font-weight: 600;
                    }
                    QPushButton:hover {
                        background-color: #3A3A3A;
                        color: #FCA5A5;
                    }
                """)
            else:
                del_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #F5F5F5;
                        color: #B91C1C;
                        border: 1px solid #E5E5E5;
                        border-radius: 6px;
                        padding: 4px 10px;
                        font-size: 12px;
                        font-weight: 600;
                    }
                    QPushButton:hover {
                        background-color: #FEE2E2;
                        color: #B91C1C;
                    }
                """)
            del_btn.clicked.connect(lambda _, k=key_name, p=path: self.on_delete(k, p))
            del_container = QWidget()
            d_box = QHBoxLayout(del_container)
            d_box.setContentsMargins(6, 6, 6, 6)
            d_box.addWidget(del_btn)
            self.table.setCellWidget(row_idx, 3, del_container)

            self.table.setRowHeight(row_idx, 56)

    # ---------------------------------------------------------------------
    # One-click batch enable / disable (all configured games)
    # ---------------------------------------------------------------------
    def _apply_mode_to_all(self, mode_str: str) -> tuple[int, int]:
        """Apply one mode to every configured registry entry. Returns (success, total)."""
        total = len(self.all_apps)
        success = 0
        for app in self.all_apps:
            try:
                AutoHDRManager.save_app(app["key_name"], app["path"], mode_str)
                success += 1
            except Exception:
                pass
        return success, total

    def _batch_apply(self, mode_str: str, action_label: str):
        if not self.all_apps:
            QMessageBox.information(self, "提示", "当前注册表中还没有已配置的游戏，请先添加游戏。")
            return

        progress_dlg = ModernProgressDialog(
            self,
            title=f"{action_label} · 批量应用 Auto HDR",
            description=f"正在为全部 {len(self.all_apps)} 个游戏写入注册表...",
            is_dark=self.is_dark_mode
        )
        progress_dlg.show()
        progress_dlg.set_progress(20, "正在批量改写 DirectX Auto HDR 注册表...", f"模式: {mode_str}")
        QApplication.processEvents()

        success, total = self._apply_mode_to_all(mode_str)
        self.load_data()

        all_ok = (success == total and total > 0)
        progress_dlg.finish(
            all_ok,
            "批量设置已生效！" if all_ok else "部分游戏写入失败",
            f"成功 {success}/{total} · 模式: {mode_str}",
            auto_close_delay_ms=800
        )
        self.set_status(f"✨ 已批量将 {success}/{total} 个游戏设为: {mode_str}")

    def on_enable_all(self):
        self._batch_apply(MODE_10BIT, "一键全部开启 (10-bit)")

    def on_disable_all(self):
        self._batch_apply(MODE_DISABLED, "一键全部关闭")

    def on_mode_change(self, key_name: str, path: str, mode_str: str):
        exe_name = os.path.basename(path) if path else key_name
        progress_dlg = ModernProgressDialog(
            self,
            title="应用 Auto HDR 模式设置",
            description=f"正在为 [{exe_name}] 应用新模式...",
            is_dark=self.is_dark_mode
        )
        progress_dlg.show()
        progress_dlg.set_progress(40, "正在改写 Windows DirectX 注册表分支...", f"模式: {mode_str}")
        QApplication.processEvents()

        AutoHDRManager.save_app(key_name, path, mode_str)

        progress_dlg.finish(True, "模式设置已成功生效！", f"已将 [{exe_name}] 更新为: {mode_str}", auto_close_delay_ms=800)
        self.set_status(f"✨ 已成功将 [{exe_name}] 的运行模式更新为: {mode_str}")

    def on_delete(self, key_name: str, path: str):
        exe_name = os.path.basename(path) if path else key_name
        reply = QMessageBox.question(
            self,
            "确认移除配置",
            f"确定要从 Windows 注册表中移除游戏：\n\n【{exe_name}】\n({path})\n\n的 Auto HDR 强制配置吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            progress_dlg = ModernProgressDialog(
                self,
                title="移除 Auto HDR 配置",
                description=f"正在移除 [{exe_name}]...",
                is_dark=self.is_dark_mode
            )
            progress_dlg.show()
            progress_dlg.set_progress(50, "正在从 Windows 注册表中删除配置项...", path)
            QApplication.processEvents()

            if AutoHDRManager.delete_app(key_name):
                self.load_data()
                progress_dlg.finish(True, "移除完成！", f"已移除: {exe_name}", auto_close_delay_ms=800)
                self.set_status(f"🗑️ 已成功移除配置: {exe_name}")
            else:
                progress_dlg.finish(False, "移除失败", "未能成功移除注册表项", auto_close_delay_ms=1500)
                QMessageBox.warning(self, "错误", "未能成功移除注册表项。")

    def on_add_game(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择游戏执行文件或快捷方式",
            "",
            "游戏可执行程序与快捷方式 (*.exe *.lnk);;所有文件 (*.*)"
        )
        if file_path:
            self.add_app_entry(file_path.replace("/", "\\"))

    def add_app_entry(self, full_path: str):
        # Prevent duplicates
        for app in self.all_apps:
            if app["path"].lower() == full_path.lower():
                QMessageBox.information(self, "提示", f"该游戏已在列表中，无需重复添加：\n\n{full_path}")
                return

        new_key = AutoHDRManager.find_free_subkey()
        exe_name = os.path.basename(full_path)
        progress_dlg = ModernProgressDialog(
            self,
            title="添加并配置游戏 Auto HDR",
            description=f"正在为 [{exe_name}] 注册配置...",
            is_dark=self.is_dark_mode
        )
        progress_dlg.show()
        progress_dlg.set_progress(35, "正在分配注册表键与解析执行路径...", full_path)
        QApplication.processEvents()

        AutoHDRManager.save_app(new_key, full_path, MODE_10BIT)
        self.load_data()

        progress_dlg.finish(True, "添加并配置成功！", f"已启用 10-bit Auto HDR: {exe_name}", auto_close_delay_ms=800)
        self.set_status(f"🎉 成功添加新游戏: {exe_name} (默认启用 10-bit Auto HDR)！")

    # Drag and Drop support
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        added_count = 0
        for u in urls:
            fp = u.toLocalFile()
            if fp.lower().endswith((".exe", ".lnk")):
                self.add_app_entry(fp.replace("/", "\\"))
                added_count += 1
        if added_count > 0:
            self.load_data()


def main():
    app = QApplication(sys.argv)
    from common.ui_theme import install_combo_arrows
    install_combo_arrows(app)

    app_font = QFont("Microsoft YaHei UI", 10)
    app_font.setStyleStrategy(QFont.PreferAntialias | QFont.PreferQuality)
    app.setFont(app_font)

    icon_path = get_resource_path("icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = AutoHDRWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
