# -*- coding: utf-8 -*-
"""
Common UI Theme and BaseWindow for Toolbox.
Provides unified Fluent Modern Card styling (Light and Dark modes)
and a robust frameless BaseWindow with custom title bar matching Image 2,
sleek 6px transparent scrollbars matching Image 1, and real-time global theme synchronization.
"""

import sys
import os
import ctypes
import tempfile
from ctypes import wintypes
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from PySide6.QtCore import Qt, QPoint, QTimer, QRectF, QPointF, QEvent, QPropertyAnimation, QEasingCurve, Signal, QObject, QSize, QFileSystemWatcher, QRect
from PySide6.QtGui import QIcon, QFont, QPixmap, QColor, QPainter, QPen, QCursor, QGuiApplication, QImage, QPainterPath
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QGraphicsDropShadowEffect, QApplication,
    QProgressBar, QDialog, QSizePolicy, QSpacerItem, QSizeGrip
)

from common.wallpaper_manager import (
    load_wallpaper_config, resolve_cached_image_path,
    render_wallpaper_background, get_acrylic_qss_styles,
    GLOBAL_WALLPAPER_NOTIFIER, DMWallpaperDialog,
    GLOBAL_WALLPAPER_CONFIG_PATH
)
from common.dm_ui_core import (
    DMBaseWindow,
    DMCardFrame,
    DMFooterBar,
    DMSizeGrip,
    DMThemeManager,
    apply_dm_window_frame
)

ASSETS_DIR = Path(__file__).resolve().parent / "assets"


def theme_toggle_icon(is_dark: bool, size: int = 32) -> QIcon:
    """Line-art crescent moon with craters (JXR converter style), used in both themes."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    color = QColor("#E8E8E8" if is_dark else "#1A1A1A")
    pen = QPen(color, 1.6)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    if is_dark:
        import math
        c = size / 2.0
        p.drawEllipse(QPointF(c, c), size * 0.18, size * 0.18)
        for i in range(8):
            a = math.radians(i * 45)
            r1, r2 = size * 0.32, size * 0.44
            p.drawLine(QPointF(c + math.cos(a) * r1, c + math.sin(a) * r1),
                       QPointF(c + math.cos(a) * r2, c + math.sin(a) * r2))
    else:
        outer = QPainterPath()
        outer.addEllipse(QRectF(size * 0.10, size * 0.10, size * 0.64, size * 0.64))
        cut = QPainterPath()
        cut.addEllipse(QRectF(size * 0.30, 0.0, size * 0.68, size * 0.68))
        p.drawPath(outer.subtracted(cut))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        for cx, cy, cr in ((0.56, 0.34, 0.055), (0.47, 0.50, 0.045), (0.60, 0.60, 0.040)):
            p.drawEllipse(QPointF(size * cx, size * cy), size * cr, size * cr)
    p.end()
    return QIcon(pm)


try:
    from common.config_manager import get_global_theme, set_global_theme
except ImportError:
    def get_global_theme() -> str:
        return "light"
    def set_global_theme(theme_name: str):
        pass

# =========================================================================
# Shared combo-box chevron (rendered once into the temp folder)
# =========================================================================
def get_combo_arrow_url(dark: bool = False) -> str:
    """
    Return a QSS-friendly path to a crisp anti-aliased chevron PNG.

    Qt QSS cannot draw CSS-border triangles, and its native drop-down arrow paints over
    the combo's bottom border, so every app installs this image for a clean, integrated
    arrow (see install_combo_arrows()).
    """
    color = "#94A3B8" if dark else "#64748B"
    path = Path(tempfile.gettempdir()) / f"dmtb_chevron_{'dark' if dark else 'light'}.png"
    try:
        if not path.exists():
            img = QImage(36, 24, QImage.Format.Format_ARGB32)
            img.fill(Qt.GlobalColor.transparent)
            painter = QPainter(img)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(QColor(color), 3.2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(9, 8, 18, 18)
            painter.drawLine(18, 18, 27, 8)
            painter.end()
            img.save(str(path))
    except Exception:
        pass
    return path.as_posix()


def combo_arrow_qss(dark: bool = False) -> str:
    """QSS fragment that draws the integrated combo chevron inside the border."""
    url = get_combo_arrow_url(dark)
    return f"""
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 30px;
            border: none;
            background: transparent;
        }}
        QComboBox::down-arrow {{
            image: url("{url}");
            width: 12px;
            height: 8px;
            margin-right: 9px;
        }}
    """


def install_combo_arrows(app=None) -> None:
    """Install the integrated chevron for every QComboBox in the application."""
    app = app or QApplication.instance()
    if app is None:
        return
    app.setStyleSheet(combo_arrow_qss(False))


# =========================================================================
# Unified Light Theme (Fluent Modern Card - Primary Default)
# =========================================================================
LIGHT_STYLE_SHEET = """
QLabel, QPushButton, QComboBox, QLineEdit, QCheckBox, QDialog, QMessageBox, QTableWidget, QHeaderView {
    font-family: "Microsoft YaHei UI", "PingFang SC", "Segoe UI", sans-serif;
}

QMainWindow {
    background: transparent;
}

QWidget#CentralWidget {
    background-color: #F5F5F5;
    border: none;
    border-radius: 8px;
}

/* 顶部标题栏 */
QFrame#TitleBar {
    background-color: #FFFFFF;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    border-bottom: 1px solid #E5E5E5;
}

QLabel#WindowTitle {
    color: #2A2B2C;
    font-size: 14px;
    font-weight: 700;
}

/* 图2右上角主题切换胶囊按钮 */
QPushButton#ThemeToggleBtn, QPushButton#UpdateBtn { 
    background-color: transparent;
    color: #3A3A3A;
    border: none;
    border-radius: 10px;
    padding: 4px 6px;
    min-height: 24px;
}

QPushButton#ThemeToggleBtn:hover, QPushButton#UpdateBtn:hover { background-color: #EFEFEF; border: none; }

/* 图2右上角极简窗口控制按钮 */
QPushButton.WindowControl, QPushButton.TitleBtn {
    background-color: transparent;
    color: #64748B;
    border: none;
    border-radius: 6px;
    min-width: 34px;
    max-width: 34px;
    min-height: 28px;
    max-height: 28px;
    font-size: 14px;
    font-weight: 600;
}

QPushButton#TitleBtnMax, QPushButton.TitleBtnMax {
    font-size: 17px;
    font-weight: 700;
}

QPushButton.WindowControl:hover, QPushButton.TitleBtn:hover {
    background-color: #E5E5E5;
    color: #292929;
}

QPushButton#WindowCloseBtn, QPushButton.TitleBtnClose {
    background-color: transparent;
    color: #64748B;
    border: none;
    border-radius: 6px;
    min-width: 34px;
    max-width: 34px;
    min-height: 28px;
    max-height: 28px;
    font-size: 14px;
    font-weight: 600;
}

QPushButton#WindowCloseBtn:hover, QPushButton.TitleBtnClose:hover {
    background-color: #EF4444;
    color: #FFFFFF;
}

/* 图1优化：现代化极简 6px 细致圆角滑动条 (彻底清除 Windows 原始丑陋箭头与斑点) */
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 6px;
    margin: 0px 0px 0px 0px;
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
    margin: 0px 0px 0px 0px;
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

/* 滚动区域透明化 */
QScrollArea {
    background: transparent;
    background-color: transparent;
    border: none;
}

QScrollArea > QWidget {
    background: transparent;
    background-color: transparent;
    border: none;
}

QScrollArea > QWidget > QWidget {
    background: transparent;
    background-color: transparent;
    border: none;
}

/* 现代卡片 */
QFrame.GridCard, QFrame.ToolCard, QFrame.card {
    background-color: #FFFFFF;
    border: 1px solid #E5E5E5;
    border-radius: 16px;
}

QFrame.GridCard:hover, QFrame.ToolCard:hover, QFrame.card:hover {
    border-color: #A7F3D0;
}

QLabel.CardTitle {
    color: #2A2B2C;
    font-size: 16px;
    font-weight: 700;
}

QLabel.CardSubtitle {
    color: #64748B;
    font-size: 12px;
    line-height: 1.4;
}

/* 按钮规范 */
QPushButton.PrimaryBtn, QPushButton.CardActionBlue {
    background-color: #8FE3B0;
    color: #10231A;
    border: none;
    border-radius: 10px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 700;
}

QPushButton.PrimaryBtn:hover, QPushButton.CardActionBlue:hover {
    background-color: #7ED9A2;
}

QPushButton.SecondaryBtn, QPushButton.OutlineBtn {
    background-color: #FFFFFF;
    color: #3A3A3A;
    border: 1px solid #D4D4D4;
    border-radius: 10px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 600;
}

QPushButton.SecondaryBtn:hover, QPushButton.OutlineBtn:hover {
    background-color: #F5F5F5;
    border-color: #94A3B8;
}

QPushButton.DangerBtn, QPushButton.CardActionRed {
    background-color: #F5F5F5;
    color: #B91C1C;
    border: 1px solid #E5E5E5;
    border-radius: 10px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 600;
}

QPushButton.DangerBtn:hover, QPushButton.CardActionRed:hover {
    background-color: #FEE2E2;
    color: #991B1B;
}

/* 输入框与下拉列表 */
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

QComboBox {
    background-color: #FFFFFF;
    border: 1px solid #D4D4D4;
    border-radius: 8px;
    padding: 6px 28px 6px 12px;
    font-size: 13px;
    color: #2A2B2C;
}

QComboBox:hover {
    border-color: #A7F3D0;
}

/* Let Qt paint its native chevron. The previous CSS-border triangle hack is not
   supported by Qt QSS and rendered as a broken grey square on the right edge. */

QComboBox QAbstractItemView {
    background-color: #FFFFFF;
    color: #292929;
    selection-background-color: #F5F5F5;
    selection-color: #2F8F5B;
    border: 1px solid #D4D4D4;
    border-radius: 8px;
    padding: 4px;
    outline: none;
}

QComboBox QAbstractItemView::item {
    min-height: 30px;
    padding: 4px 10px;
    color: #292929;
}

QComboBox QAbstractItemView::item:hover {
    background-color: #EFEFEF;
    color: #2F8F5B;
}

QComboBox QAbstractItemView::item:selected {
    background-color: #F5F5F5;
    color: #2F8F5B;
}

QFrame#StatusBar {
    background-color: transparent;
    border: none;
}

/* 表格 */
QTableWidget {
    background-color: #FFFFFF;
    border: 1px solid #E5E5E5;
    border-radius: 12px;
    gridline-color: transparent;
    color: #2A2B2C;
    font-size: 13px;
}

QHeaderView::section {
    background-color: #F5F5F5;
    color: #64748B;
    border: none;
    border-bottom: 1px solid #E5E5E5;
    padding: 8px;
    font-weight: 600;
}

/* 状态药丸 */
QLabel#StatusBanner {
    color: #059669;
    background-color: #ECFDF5;
    border: 1px solid #A7F3D0;
    border-radius: 12px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 600;
}

/* 现代化 Fluent 动态进度条规范 */
QProgressBar {
    background-color: #E5E5E5;
    border: none;
    border-radius: 5px;
    height: 10px;
    text-align: center;
    color: #2A2B2C;
    font-size: 11px;
    font-weight: 600;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2F8F5B, stop:1 #3E9E69);
    border-radius: 5px;
}
"""

# =========================================================================
# Unified Dark Theme (Fluent Modern Card - Dark Mode)
# =========================================================================
DARK_STYLE_SHEET = """
QLabel, QPushButton, QComboBox, QLineEdit, QCheckBox, QDialog, QMessageBox, QTableWidget, QHeaderView {
    font-family: "Microsoft YaHei UI", "PingFang SC", "Segoe UI", sans-serif;
}

QMainWindow {
    background: transparent;
}

QWidget#CentralWidget {
    background-color: #292929;
    border: none;
    border-radius: 8px;
}

QFrame#TitleBar {
    background-color: #2A2B2C;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    border-bottom: 1px solid #3A3A3A;
}

QLabel#WindowTitle {
    color: #E8E8E8;
    font-size: 14px;
    font-weight: 700;
}

QPushButton#ThemeToggleBtn, QPushButton#UpdateBtn { 
    background-color: transparent;
    color: #E8E8E8;
    border: none;
    border-radius: 10px;
    padding: 4px 6px;
    min-height: 24px;
}

QPushButton#ThemeToggleBtn:hover, QPushButton#UpdateBtn:hover { background-color: #3A3A3A; border: none; }

QPushButton.WindowControl, QPushButton.TitleBtn {
    background-color: transparent;
    color: #A0A0A0;
    border: none;
    border-radius: 6px;
    min-width: 34px;
    max-width: 34px;
    min-height: 28px;
    max-height: 28px;
    font-size: 14px;
    font-weight: 600;
}

QPushButton#TitleBtnMax, QPushButton.TitleBtnMax {
    font-size: 17px;
    font-weight: 700;
}

QPushButton.WindowControl:hover, QPushButton.TitleBtn:hover {
    background-color: #3A3A3A;
    color: #FFFFFF;
}

QPushButton#WindowCloseBtn, QPushButton.TitleBtnClose {
    background-color: transparent;
    color: #A0A0A0;
    border: none;
    border-radius: 6px;
    min-width: 34px;
    max-width: 34px;
    min-height: 28px;
    max-height: 28px;
    font-size: 14px;
    font-weight: 600;
}

QPushButton#WindowCloseBtn:hover, QPushButton.TitleBtnClose:hover {
    background-color: #EF4444;
    color: #FFFFFF;
}

/* 图1优化：暗色极简 6px 滚动条 */
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 6px;
    margin: 0px 0px 0px 0px;
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
    margin: 0px 0px 0px 0px;
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

QScrollArea {
    background: transparent;
    background-color: transparent;
    border: none;
}

QScrollArea > QWidget {
    background: transparent;
    background-color: transparent;
    border: none;
}

QScrollArea > QWidget > QWidget {
    background: transparent;
    background-color: transparent;
    border: none;
}

QFrame.GridCard, QFrame.ToolCard, QFrame.card {
    background-color: #2A2B2C;
    border: 1px solid #3A3A3A;
    border-radius: 16px;
}

QFrame.GridCard:hover, QFrame.ToolCard:hover, QFrame.card:hover {
    border-color: #A7F3D0;
}

QLabel.CardTitle {
    color: #E8E8E8;
    font-size: 16px;
    font-weight: 700;
}

QLabel.CardSubtitle {
    color: #A0A0A0;
    font-size: 12px;
    line-height: 1.4;
}

QPushButton.PrimaryBtn, QPushButton.CardActionBlue {
    background-color: #8FE3B0;
    color: #10231A;
    border: none;
    border-radius: 10px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 700;
}

QPushButton.PrimaryBtn:hover, QPushButton.CardActionBlue:hover {
    background-color: #7ED9A2;
}

QPushButton.SecondaryBtn, QPushButton.OutlineBtn {
    background-color: #2A2B2C;
    color: #E8E8E8;
    border: 1px solid #4A4A4A;
    border-radius: 10px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 600;
}

QPushButton.SecondaryBtn:hover, QPushButton.OutlineBtn:hover {
    background-color: #3A3A3A;
    border-color: #8A8A8A;
}

QPushButton.DangerBtn, QPushButton.CardActionRed {
    background-color: #303132;
    color: #F87171;
    border: 1px solid #4A4A4A;
    border-radius: 10px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 600;
}

QPushButton.DangerBtn:hover, QPushButton.CardActionRed:hover {
    background-color: #3A3A3A;
    color: #FCA5A5;
}

QLineEdit {
    background-color: #292929;
    border: 1px solid #4A4A4A;
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 13px;
    color: #E8E8E8;
}

QLineEdit:focus {
    border-color: #A7F3D0;
}

QComboBox {
    background-color: #292929;
    border: 1px solid #4A4A4A;
    border-radius: 8px;
    padding: 6px 28px 6px 12px;
    font-size: 13px;
    color: #E8E8E8;
}

QComboBox:hover {
    border-color: #A7F3D0;
}

/* Native chevron (see the light-theme comment above). */

QComboBox QAbstractItemView {
    background-color: #2A2B2C;
    color: #E8E8E8;
    selection-background-color: #1E3A8A;
    selection-color: #A7F3D0;
    border: 1px solid #4A4A4A;
    border-radius: 8px;
    padding: 4px;
    outline: none;
}

QComboBox QAbstractItemView::item {
    min-height: 30px;
    padding: 4px 10px;
    color: #E8E8E8;
}

QComboBox QAbstractItemView::item:hover {
    background-color: #3A3A3A;
    color: #A7F3D0;
}

QComboBox QAbstractItemView::item:selected {
    background-color: #1E3A8A;
    color: #A7F3D0;
}

QFrame#StatusBar {
    background-color: transparent;
    border: none;
}

QTableWidget {
    background-color: #2A2B2C;
    border: 1px solid #3A3A3A;
    border-radius: 12px;
    gridline-color: transparent;
    color: #E8E8E8;
    font-size: 13px;
}

QHeaderView::section {
    background-color: #292929;
    color: #A0A0A0;
    border: none;
    border-bottom: 1px solid #3A3A3A;
    padding: 8px;
    font-weight: 600;
}

QLabel#StatusBanner {
    color: #34D399;
    background-color: #064E3B;
    border: 1px solid #059669;
    border-radius: 12px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 600;
}

/* 现代化 Fluent 动态进度条规范 (暗黑模式) */
QProgressBar {
    background-color: #2A2B2C;
    border: 1px solid #3A3A3A;
    border-radius: 5px;
    height: 10px;
    text-align: center;
    color: #E8E8E8;
    font-size: 11px;
    font-weight: 600;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6FD398, stop:1 #A7F3D0);
    border-radius: 5px;
}
"""


class CaptionButtonType:
    MINIMIZE = "min"
    MAXIMIZE = "max"
    CLOSE = "close"


class CaptionButton(QPushButton):
    """
    Precision custom-painted Window Caption Button matching Figure 1.
    Guarantees mathematically identical horizontal center-line alignment for -, □, and ✕.
    Supports Windows 11 style rounded corners on maximize and fluent hover transitions.
    """
    def __init__(self, btn_type: str, parent=None):
        super().__init__(parent)
        self.btn_type = btn_type
        self.is_maximized = False
        self.is_hovered = False
        self.is_dark_mode = False
        self.setFixedSize(42, 30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setStyleSheet("background: transparent; border: none;")

    def set_dark_mode(self, is_dark: bool):
        self.is_dark_mode = is_dark
        self.update()

    def set_maximized_state(self, is_max: bool):
        self.is_maximized = is_max
        self.update()

    def enterEvent(self, event):
        self.is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        cx = w / 2.0
        cy = h / 2.0

        # Hover Background
        if self.is_hovered:
            if self.btn_type == CaptionButtonType.CLOSE:
                bg_color = QColor("#EF4444")
            else:
                bg_color = QColor("#3A3A3A") if self.is_dark_mode else QColor("#E5E5E5")
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(bg_color)
            painter.drawRoundedRect(QRectF(1.0, 1.0, w - 2.0, h - 2.0), 6.0, 6.0)

        # Icon Pen & Color
        if self.btn_type == CaptionButtonType.CLOSE and self.is_hovered:
            icon_color = QColor("#FFFFFF")
        else:
            icon_color = QColor("#F5F5F5") if self.is_dark_mode else QColor("#3A3A3A")

        pen = QPen(icon_color, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if self.btn_type == CaptionButtonType.MINIMIZE:
            # Clean horizontal line (length 11px, centered strictly at cy = 15.0)
            painter.drawLine(QPointF(cx - 5.5, cy), QPointF(cx + 5.5, cy))

        elif self.btn_type == CaptionButtonType.MAXIMIZE:
            if not self.is_maximized:
                # Rounded square with 2.2px radius (11x11px, centered strictly at cx, cy)
                painter.drawRoundedRect(QRectF(cx - 5.5, cy - 5.5, 11.0, 11.0), 2.2, 2.2)
            else:
                # Restored 2 overlapping rounded boxes
                painter.drawRoundedRect(QRectF(cx - 3.5, cy - 6.0, 9.0, 9.0), 1.5, 1.5)
                painter.drawRoundedRect(QRectF(cx - 6.0, cy - 3.5, 9.0, 9.0), 1.5, 1.5)

        elif self.btn_type == CaptionButtonType.CLOSE:
            # Clean diagonal cross (centered strictly at cx, cy)
            painter.drawLine(QPointF(cx - 5.0, cy - 5.0), QPointF(cx + 5.0, cy + 5.0))
            painter.drawLine(QPointF(cx + 5.0, cy - 5.0), QPointF(cx - 5.0, cy + 5.0))


CornerResizeGrip = DMSizeGrip


class ProgressSignalBridge(QObject):
    """Thread-safe signal dispatcher for asynchronous progress updates."""
    progress_updated = Signal(int, str, str)           # val (0-100), text, detail
    indeterminate_requested = Signal(str, str)        # text, detail
    finished = Signal(bool, str, str)                 # ok, final_text, detail


class ModernProgressDialog(QDialog):
    """
    Unified Fluent Modern Progress Dialog.
    Features:
    - Frameless translucent rounded card design with drop shadow
    - Dynamic animated QProgressBar with smooth QPropertyAnimation (glides seamlessly)
    - Supports both indeterminate (sweep pulse) and determinate (0-100%) modes
    - Real-time Title, Description, and detailed Sub-step text
    - Auto-detects and synchronizes with global light/dark theme
    - Complete non-blocking integration with Qt event loop
    """
    def __init__(self, parent=None, title="正在执行操作", description="请稍候...", is_dark=None, cancelable=False):
        super().__init__(parent)
        if is_dark is None:
            self.is_dark = (get_global_theme() == "dark")
        else:
            self.is_dark = is_dark
        self.cancelable = cancelable
        self._target_value = 0
        self._drag_pos = None

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(460)

        app_font = QFont("Microsoft YaHei UI", 10)
        app_font.setStyleStrategy(QFont.PreferAntialias | QFont.PreferQuality)
        self.setFont(app_font)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # Card container
        self.card = QFrame()
        self.card_layout = QVBoxLayout(self.card)
        self.card_layout.setContentsMargins(24, 20, 24, 22)
        self.card_layout.setSpacing(14)
        main_layout.addWidget(self.card)

        # Drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 80 if self.is_dark else 35))
        shadow.setOffset(0, 6)
        self.card.setGraphicsEffect(shadow)

        # Header row
        header = QHBoxLayout()
        header.setSpacing(12)

        self.badge = QLabel("⚡")
        self.badge.setFixedSize(36, 36)
        header.addWidget(self.badge)

        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("font-size: 15px; font-weight: 700; border: none;")
        header.addWidget(self.lbl_title)
        header.addStretch()

        if self.cancelable:
            self.btn_close = QPushButton("✕")
            self.btn_close.setFixedSize(26, 26)
            self.btn_close.clicked.connect(self.reject)
            header.addWidget(self.btn_close)
        else:
            self.btn_close = None

        self.card_layout.addLayout(header)

        # Description / Main status label
        self.lbl_desc = QLabel(description)
        self.lbl_desc.setWordWrap(True)
        self.lbl_desc.setStyleSheet("font-size: 13px; font-weight: 600; border: none;")
        self.card_layout.addWidget(self.lbl_desc)

        # Progress bar + Percent label row
        pb_row = QHBoxLayout()
        pb_row.setSpacing(12)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(10)
        pb_row.addWidget(self.progress_bar, 1)

        self.lbl_percent = QLabel("0%")
        self.lbl_percent.setFixedWidth(46)
        self.lbl_percent.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_percent.setStyleSheet("font-size: 12px; font-weight: 700; border: none;")
        pb_row.addWidget(self.lbl_percent)

        self.card_layout.addLayout(pb_row)

        # Detail text (sub-step or download speed/bytes)
        self.lbl_detail = QLabel("")
        self.lbl_detail.setWordWrap(True)
        self.lbl_detail.setStyleSheet("font-size: 11px; border: none;")
        self.card_layout.addWidget(self.lbl_detail)

        # Animation for smooth progress transitions
        self.anim = QPropertyAnimation(self.progress_bar, b"value")
        self.anim.setDuration(220)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.valueChanged.connect(self._on_anim_value_changed)

        self._apply_theme()

    def _apply_theme(self):
        bg = "#2A2B2C" if self.is_dark else "#FFFFFF"
        border = "#3A3A3A" if self.is_dark else "#E5E5E5"
        title_c = "#F5F5F5" if self.is_dark else "#292929"
        desc_c = "#E5E5E5" if self.is_dark else "#2A2B2C"
        detail_c = "#94A3B8" if self.is_dark else "#64748B"
        badge_bg = "#1E3A8A" if self.is_dark else "#E8E8E8"
        badge_fg = "#7ED9A2" if self.is_dark else "#2F8F5B"

        self.card.setStyleSheet(f"""
            QFrame {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 14px;
            }}
        """)
        self.badge.setStyleSheet(f"""
            background-color: {badge_bg};
            color: {badge_fg};
            border-radius: 10px;
            font-size: 17px;
            qproperty-alignment: AlignCenter;
            border: none;
        """)
        self.lbl_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {title_c}; border: none;")
        self.lbl_desc.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {desc_c}; border: none;")
        self.lbl_percent.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {badge_fg}; border: none;")
        self.lbl_detail.setStyleSheet(f"font-size: 11px; color: {detail_c}; border: none;")

        if self.btn_close:
            self.btn_close.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {detail_c};
                    border: none;
                    font-size: 14px;
                    font-weight: bold;
                    border-radius: 6px;
                }}
                QPushButton:hover {{
                    background: {'#3A3A3A' if self.is_dark else '#EFEFEF'};
                    color: {'#EF4444' if self.is_dark else '#DC2626'};
                }}
            """)

        # Style progress bar
        pb_bg = "#292929" if self.is_dark else "#E5E5E5"
        chunk_c1 = "#3E9E69" if self.is_dark else "#2F8F5B"
        chunk_c2 = "#7ED9A2" if self.is_dark else "#3E9E69"
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {pb_bg};
                border: none;
                border-radius: 5px;
                height: 10px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {chunk_c1}, stop:1 {chunk_c2});
                border-radius: 5px;
            }}
        """)

    def _on_anim_value_changed(self, val):
        if self.progress_bar.maximum() > 0:
            pct = int((val / self.progress_bar.maximum()) * 100)
            self.lbl_percent.setText(f"{pct}%")

    def set_indeterminate(self, text: Optional[str] = None, detail: Optional[str] = None):
        """Sets the progress bar to indeterminate continuous pulse animation."""
        self.anim.stop()
        self.progress_bar.setRange(0, 0)
        self.lbl_percent.setText("...")
        if text:
            self.lbl_desc.setText(text)
        if detail is not None:
            self.lbl_detail.setText(detail)
        QApplication.processEvents()

    def set_progress(self, value: int, text: Optional[str] = None, detail: Optional[str] = None):
        """
        Smoothly animates progress to target percentage (0-100).
        Dynamically updates description and detail labels.
        """
        value = max(0, min(100, int(value)))
        if self.progress_bar.maximum() == 0:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)

        self._target_value = value
        self.anim.stop()
        self.anim.setStartValue(self.progress_bar.value())
        self.anim.setEndValue(value)
        self.anim.start()

        if text:
            self.lbl_desc.setText(text)
        if detail is not None:
            self.lbl_detail.setText(detail)

        QApplication.processEvents()

    def finish(self, success: bool = True, final_text: str = "已完成", detail: str = "", auto_close_delay_ms: int = 0):
        """Marks progress as completed, shows success/failure state, and allows manual or timed close."""
        self.anim.stop()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.lbl_percent.setText("100%")
        if final_text:
            self.lbl_desc.setText(final_text)
        if detail is not None:
            self.lbl_detail.setText(detail)
        if success:
            self.badge.setText("✓")
            self.badge.setStyleSheet(f"""
                background-color: {'#064E3B' if self.is_dark else '#DCFCE7'};
                color: {'#34D399' if self.is_dark else '#16A34A'};
                border-radius: 10px;
                font-size: 18px;
                qproperty-alignment: AlignCenter;
                border: none;
            """)
        else:
            self.badge.setText("✕")
            self.badge.setStyleSheet(f"""
                background-color: {'#7F1D1D' if self.is_dark else '#FEE2E2'};
                color: {'#F87171' if self.is_dark else '#DC2626'};
                border-radius: 10px;
                font-size: 18px;
                qproperty-alignment: AlignCenter;
                border: none;
            """)
        QApplication.processEvents()

        if auto_close_delay_ms > 0:
            QTimer.singleShot(auto_close_delay_ms, self.accept)
        else:
            # 响应用户需求：弹出提示窗口必须由用户自己点击关闭，绝不自动退出
            if not hasattr(self, "btn_confirm_finish") or self.btn_confirm_finish is None:
                btn_row = QHBoxLayout()
                btn_row.addStretch()
                self.btn_confirm_finish = QPushButton("确定并关闭")
                btn_bg = "#2F8F5B" if not self.is_dark else "#3E9E69"
                btn_hover = "#26784C" if not self.is_dark else "#2F8F5B"
                self.btn_confirm_finish.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {btn_bg};
                        color: #FFFFFF;
                        border: none;
                        border-radius: 8px;
                        padding: 8px 26px;
                        font-size: 13px;
                        font-weight: 700;
                    }}
                    QPushButton:hover {{
                        background-color: {btn_hover};
                    }}
                """)
                self.btn_confirm_finish.setCursor(Qt.CursorShape.PointingHandCursor)
                self.btn_confirm_finish.clicked.connect(self.accept)
                btn_row.addWidget(self.btn_confirm_finish)
                self.card_layout.addLayout(btn_row)
                self.adjustSize()

    def showEvent(self, event):
        super().showEvent(event)
        self._center_on_parent()

    def _center_on_parent(self):
        p = self.parent()
        if p and p.isVisible():
            p_geom = p.geometry()
            x = p_geom.x() + (p_geom.width() - self.width()) // 2
            y = p_geom.y() + (p_geom.height() - self.height()) // 2
            self.move(max(0, x), max(0, y))
        else:
            screen = QGuiApplication.primaryScreen()
            if screen:
                sg = screen.availableGeometry()
                self.move((sg.width() - self.width()) // 2, (sg.height() - self.height()) // 2)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def attach_bridge(self, bridge: ProgressSignalBridge):
        """Connects a ProgressSignalBridge so background threads can update this dialog."""
        bridge.progress_updated.connect(self.set_progress)
        bridge.indeterminate_requested.connect(self.set_indeterminate)
        bridge.finished.connect(lambda ok, t, d: self.finish(ok, t, d))


class ModernConfirmDialog(QDialog):
    """
    Unified Fluent Modern Confirmation Dialog.
    Features:
    - Frameless translucent rounded card design with drop shadow
    - Strictly centers over parent window
    - Supports draggable window area
    - Light / Dark theme synchronized
    - Badge icons for warning (⚠️), danger/clean (🧹), info (ℹ️), error (✕), success (✓), question (❓)
    - Structured message presentation: supports subtitles, inset bullet lists, and warning notices
    - Fluent styled primary/danger confirm button and secondary cancel button
    - Keyboard Enter/Esc support
    """
    def __init__(
        self,
        parent=None,
        title: str = "确认操作",
        message: str = "",
        bullet_items: Optional[List[str]] = None,
        warning_note: Optional[str] = None,
        confirm_text: str = "确定",
        cancel_text: str = "取消",
        icon_type: str = "warning",
        is_danger: bool = False,
        is_dark: Optional[bool] = None,
        single_button: bool = False
    ):
        super().__init__(parent)
        if is_dark is None:
            self.is_dark = (get_global_theme() == "dark")
        else:
            self.is_dark = is_dark
        self.is_danger = is_danger
        self.single_button = single_button
        self._drag_pos = None

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(500)

        app_font = QFont("Microsoft YaHei UI", 10)
        app_font.setStyleStrategy(QFont.PreferAntialias | QFont.PreferQuality)
        self.setFont(app_font)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # Card container
        self.card = QFrame()
        self.card_layout = QVBoxLayout(self.card)
        self.card_layout.setContentsMargins(24, 22, 24, 22)
        self.card_layout.setSpacing(14)
        main_layout.addWidget(self.card)

        # Drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setColor(QColor(0, 0, 0, 95 if self.is_dark else 35))
        shadow.setOffset(0, 8)
        self.card.setGraphicsEffect(shadow)

        # Header row
        header = QHBoxLayout()
        header.setSpacing(12)

        icon_map = {
            "warning": ("⚠️", "#F5F5F5", "#D97706", "#78350F", "#FBBF24"),
            "danger": ("🧹", "#FEE2E2", "#DC2626", "#7F1D1D", "#F87171"),
            "error": ("✕", "#FEE2E2", "#DC2626", "#7F1D1D", "#F87171"),
            "info": ("ℹ️", "#E8E8E8", "#2F8F5B", "#1E3A8A", "#7ED9A2"),
            "question": ("❓", "#EDE9FE", "#7C3AED", "#4C1D95", "#A78BFA"),
            "success": ("✓", "#DCFCE7", "#16A34A", "#064E3B", "#34D399"),
        }
        badge_text, l_bg, l_fg, d_bg, d_fg = icon_map.get(icon_type, icon_map["warning"])
        badge_bg = d_bg if self.is_dark else l_bg
        badge_fg = d_fg if self.is_dark else l_fg

        self.badge = QLabel(badge_text)
        self.badge.setFixedSize(38, 38)
        self.badge.setStyleSheet(f"""
            background-color: {badge_bg};
            color: {badge_fg};
            border-radius: 12px;
            font-size: 18px;
            qproperty-alignment: AlignCenter;
            border: none;
        """)
        header.addWidget(self.badge)

        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet(f"""
            font-size: 16px;
            font-weight: 700;
            color: {'#F5F5F5' if self.is_dark else '#292929'};
            border: none;
        """)
        header.addWidget(self.lbl_title)
        header.addStretch()

        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(28, 28)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.clicked.connect(self.reject)
        self.btn_close.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {'#94A3B8' if self.is_dark else '#64748B'};
                border: none;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background: {'#3A3A3A' if self.is_dark else '#EFEFEF'};
                color: {'#EF4444' if self.is_dark else '#DC2626'};
            }}
        """)
        header.addWidget(self.btn_close)
        self.card_layout.addLayout(header)

        # Message / Subtitle
        if message:
            self.lbl_message = QLabel(message)
            self.lbl_message.setWordWrap(True)
            self.lbl_message.setStyleSheet(f"""
                font-size: 13px;
                line-height: 1.6;
                color: {'#E5E5E5' if self.is_dark else '#3A3A3A'};
                border: none;
            """)
            self.card_layout.addWidget(self.lbl_message)

        # Inset items list box (if bullet_items given)
        if bullet_items:
            items_frame = QFrame()
            items_layout = QVBoxLayout(items_frame)
            items_layout.setContentsMargins(14, 12, 14, 12)
            items_layout.setSpacing(8)

            f_bg = "#292929" if self.is_dark else "#F5F5F5"
            f_border = "#3A3A3A" if self.is_dark else "#E5E5E5"
            f_text = "#D4D4D4" if self.is_dark else "#4A4A4A"

            items_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {f_bg};
                    border: 1px solid {f_border};
                    border-radius: 8px;
                }}
            """)
            for item in bullet_items:
                lbl_it = QLabel(item)
                lbl_it.setWordWrap(True)
                lbl_it.setStyleSheet(f"font-size: 12px; line-height: 1.5; color: {f_text}; border: none; background: transparent;")
                items_layout.addWidget(lbl_it)
            self.card_layout.addWidget(items_frame)

        # Warning note banner (if given)
        if warning_note:
            note_frame = QFrame()
            note_layout = QHBoxLayout(note_frame)
            note_layout.setContentsMargins(12, 8, 12, 8)
            note_layout.setSpacing(8)

            n_bg = "#451A03" if self.is_dark else "#FFFFFF"
            n_border = "#78350F" if self.is_dark else "#E5E5E5"
            n_text = "#FCD34D" if self.is_dark else "#B45309"

            note_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {n_bg};
                    border: 1px solid {n_border};
                    border-radius: 8px;
                }}
            """)
            lbl_note = QLabel(warning_note)
            lbl_note.setWordWrap(True)
            lbl_note.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {n_text}; border: none; background: transparent;")
            note_layout.addWidget(lbl_note)
            self.card_layout.addWidget(note_frame)

        # Buttons row
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        if not self.single_button:
            self.btn_cancel = QPushButton(cancel_text)
            self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_cancel.clicked.connect(self.reject)
            c_bg = "#3A3A3A" if self.is_dark else "#EFEFEF"
            c_fg = "#94A3B8" if self.is_dark else "#4A4A4A"
            c_bd = "#4A4A4A" if self.is_dark else "#D4D4D4"
            c_hbg = "#4A4A4A" if self.is_dark else "#E5E5E5"
            c_hfg = "#F5F5F5" if self.is_dark else "#292929"
            self.btn_cancel.setStyleSheet(f"""
                QPushButton {{
                    background-color: {c_bg};
                    color: {c_fg};
                    border: 1px solid {c_bd};
                    border-radius: 8px;
                    padding: 8px 18px;
                    font-size: 13px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: {c_hbg};
                    color: {c_hfg};
                }}
            """)
            btn_layout.addWidget(self.btn_cancel)

        self.btn_confirm = QPushButton(confirm_text)
        self.btn_confirm.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_confirm.clicked.connect(self.accept)

        if self.is_danger:
            c_bg = "#DC2626" if not self.is_dark else "#EF4444"
            c_hover = "#B91C1C" if not self.is_dark else "#DC2626"
            c_press = "#991B1B" if not self.is_dark else "#B91C1C"
        else:
            c_bg = "#2F8F5B" if not self.is_dark else "#3E9E69"
            c_hover = "#26784C" if not self.is_dark else "#2F8F5B"
            c_press = "#1E40AF" if not self.is_dark else "#26784C"

        self.btn_confirm.setStyleSheet(f"""
            QPushButton {{
                background-color: {c_bg};
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 8px 22px;
                font-size: 13px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {c_hover};
            }}
            QPushButton:pressed {{
                background-color: {c_press};
            }}
        """)
        btn_layout.addWidget(self.btn_confirm)
        self.card_layout.addLayout(btn_layout)

        # Card theme
        card_bg = "#2A2B2C" if self.is_dark else "#FFFFFF"
        card_border = "#3A3A3A" if self.is_dark else "#E5E5E5"
        self.card.setStyleSheet(f"""
            QFrame {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 14px;
            }}
        """)

    def showEvent(self, event):
        super().showEvent(event)
        self._center_on_parent()

    def _center_on_parent(self):
        p = self.parent()
        if p and p.isVisible():
            p_geom = p.geometry()
            x = p_geom.x() + (p_geom.width() - self.width()) // 2
            y = p_geom.y() + (p_geom.height() - self.height()) // 2
            self.move(max(0, x), max(0, y))
        else:
            screen = QGuiApplication.primaryScreen()
            if screen:
                sg = screen.availableGeometry()
                self.move((sg.width() - self.width()) // 2, (sg.height() - self.height()) // 2)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.accept()
        else:
            super().keyPressEvent(event)


class ModernDialog:
    """Static convenience methods for Fluent modern popups and confirmations."""

    @staticmethod
    def confirm(
        parent=None,
        title: str = "确认操作",
        message: str = "",
        bullet_items: Optional[List[str]] = None,
        warning_note: Optional[str] = None,
        confirm_text: str = "确定",
        cancel_text: str = "取消",
        icon_type: str = "warning",
        is_danger: bool = False,
        is_dark: Optional[bool] = None
    ) -> bool:
        dlg = ModernConfirmDialog(
            parent=parent,
            title=title,
            message=message,
            bullet_items=bullet_items,
            warning_note=warning_note,
            confirm_text=confirm_text,
            cancel_text=cancel_text,
            icon_type=icon_type,
            is_danger=is_danger,
            is_dark=is_dark,
            single_button=False
        )
        return dlg.exec() == QDialog.DialogCode.Accepted

    @staticmethod
    def question(
        parent=None,
        title: str = "确认",
        message: str = "",
        confirm_text: str = "确定",
        cancel_text: str = "取消",
        is_dark: Optional[bool] = None
    ) -> bool:
        return ModernDialog.confirm(
            parent=parent,
            title=title,
            message=message,
            confirm_text=confirm_text,
            cancel_text=cancel_text,
            icon_type="question",
            is_danger=False,
            is_dark=is_dark
        )

    @staticmethod
    def info(parent=None, title: str = "提示", message: str = "", is_dark: Optional[bool] = None):
        dlg = ModernConfirmDialog(
            parent=parent,
            title=title,
            message=message,
            confirm_text="确定",
            icon_type="info",
            is_danger=False,
            is_dark=is_dark,
            single_button=True
        )
        dlg.exec()

    @staticmethod
    def warning(parent=None, title: str = "警告", message: str = "", is_dark: Optional[bool] = None):
        dlg = ModernConfirmDialog(
            parent=parent,
            title=title,
            message=message,
            confirm_text="确定",
            icon_type="warning",
            is_danger=False,
            is_dark=is_dark,
            single_button=True
        )
        dlg.exec()

    @staticmethod
    def error(parent=None, title: str = "错误", message: str = "", is_dark: Optional[bool] = None):
        dlg = ModernConfirmDialog(
            parent=parent,
            title=title,
            message=message,
            confirm_text="确定",
            icon_type="error",
            is_danger=True,
            is_dark=is_dark,
            single_button=True
        )
        dlg.exec()


class BaseRootContainer(QWidget):
    """Root container for BaseWindow with custom wallpaper support."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CentralWidget")
        self.setMouseTracking(True)

    def paintEvent(self, event):
        win = self.window()
        if hasattr(win, "paint_window_background"):
            painter = QPainter(self)
            win.paint_window_background(painter, self.rect())
            painter.end()
        super().paintEvent(event)


class BaseWindow(QMainWindow):
    """
    Standard Base Window for Toolbox.
    Features:
    - Frameless with custom title bar matching Figure 1
    - Custom-painted CaptionButtons with 100% horizontal center-line alignment
    - Full border drag resizing (拖动放大缩小) on all 8 borders/corners
    - Theme toggle pill button with text: "☾ 黑夜模式" / "☀ 白天模式"
    - Automatic real-time cross-process theme synchronization
    - Sleek 6px transparent scrollbars matching Image 1 with 0px horizontal scrollbar
    """

    BORDER_SIZE = 6

    def __init__(self, title: str = "DM工具箱", width: int = 960, height: int = 640, icon_filename: str = None):
        super().__init__()
        self.setWindowTitle(title)
        self.BORDER_SIZE = 6

        # Frameless window configuration
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowMinMaxButtonsHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

        # Responsive screen adaptation: clamp initial size to available geometry of active monitor
        screen = QGuiApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            target_w = min(width, int(avail.width() * 0.92))
            target_h = min(height, int(avail.height() * 0.86))
            self.resize(target_w, target_h)
            min_w = min(680, int(avail.width() * 0.70))
            min_h = min(440, int(avail.height() * 0.60))
            self.setMinimumSize(min_w, min_h)
        else:
            self.resize(width, height)
            self.setMinimumSize(680, 440)

        self.BORDER_SIZE = 7
        self.CORNER_SIZE = 20

        # Drag & Resize tracking state
        self._is_dragging = False
        self._drag_pos = QPoint()
        self._resize_edge = 0
        self._resize_start_pos = QPoint()
        self._resize_start_geom = self.geometry()
        self._edge_cursor_active = False

        # Install application-level event filter for bulletproof 8-directional edge resizing
        qApp = QApplication.instance()
        if qApp:
            qApp.installEventFilter(self)
        # Integrated combo chevron for every window of this app
        install_combo_arrows(qApp)

        # Sync with global theme setting
        self.is_dark_mode = (get_global_theme() == "dark")

        self._setup_base_ui(title)
        if icon_filename:
            icon_p = ASSETS_DIR / icon_filename
            if icon_p.exists():
                self.set_app_icon(icon_p)

        self.subapp_id = "launcher"
        self.wallpaper_pixmap = None
        self.wallpaper_config = {}
        self._last_wallpaper_mtime = 0

        # In-process wallpaper event bus
        GLOBAL_WALLPAPER_NOTIFIER.wallpaper_changed.connect(self._on_wallpaper_event)

        # Cross-process wallpaper file watcher (100ms debounce)
        self.wallpaper_file_watcher = QFileSystemWatcher(self)
        if GLOBAL_WALLPAPER_CONFIG_PATH.parent.exists():
            self.wallpaper_file_watcher.addPath(str(GLOBAL_WALLPAPER_CONFIG_PATH.parent))
        if GLOBAL_WALLPAPER_CONFIG_PATH.exists():
            self.wallpaper_file_watcher.addPath(str(GLOBAL_WALLPAPER_CONFIG_PATH))
        self.wallpaper_file_watcher.fileChanged.connect(self._on_wallpaper_file_changed)
        self.wallpaper_file_watcher.directoryChanged.connect(self._on_wallpaper_file_changed)
        self._wp_debounce_timer = QTimer(self)
        self._wp_debounce_timer.setSingleShot(True)
        self._wp_debounce_timer.setInterval(100)
        self._wp_debounce_timer.timeout.connect(self.reload_wallpaper)

        self.reload_wallpaper()
        self.apply_theme()
        self.center_on_screen()
        apply_dm_window_frame(self, self.is_dark_mode)

        # Background timer for simultaneous cross-software theme synchronization (500ms)
        self.theme_sync_timer = QTimer(self)
        self.theme_sync_timer.setInterval(500)
        self.theme_sync_timer.timeout.connect(self.check_external_theme_change)
        self.theme_sync_timer.start()

    def _setup_base_ui(self, title: str):
        # Root central container
        self.central_widget = BaseRootContainer(self)
        self.central_widget.setObjectName("CentralWidget")
        self.central_widget.setMouseTracking(True)
        self.setCentralWidget(self.central_widget)

        self.root_layout = QVBoxLayout(self.central_widget)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        # Custom Title Bar
        self.title_bar = QFrame()
        self.title_bar.setObjectName("TitleBar")
        self.title_bar.setFixedHeight(44)

        tb_layout = QHBoxLayout(self.title_bar)
        tb_layout.setContentsMargins(16, 0, 10, 0)
        tb_layout.setSpacing(6)
        tb_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # App Icon & Title
        self.lbl_title_icon = QLabel()
        self.lbl_title_icon.setFixedSize(22, 22)
        tb_layout.addWidget(self.lbl_title_icon)

        self.lbl_window_title = QLabel(title)
        self.lbl_window_title.setObjectName("WindowTitle")
        tb_layout.addWidget(self.lbl_window_title)

        tb_layout.addStretch()

        # 图2右上角自定义壁纸按钮 (位于主题切换按钮左侧)
        self.btn_wallpaper = QPushButton("🖼️")
        self.btn_wallpaper.setFixedSize(30, 30)
        self.btn_wallpaper.setObjectName("WallpaperBtn")
        self.btn_wallpaper.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_wallpaper.setToolTip("自定义壁纸与毛玻璃保护设置")
        self.btn_wallpaper.clicked.connect(self.open_wallpaper_settings)
        tb_layout.addWidget(self.btn_wallpaper)

        # 图2右上角主题切换胶囊
        self.btn_theme = QPushButton("")
        self.btn_theme.setFixedSize(30, 30)
        self.btn_theme.setIcon(theme_toggle_icon(self.is_dark_mode))
        self.btn_theme.setIconSize(QSize(16, 16))
        self.btn_theme.setObjectName("ThemeToggleBtn")
        self.btn_theme.setProperty("class", "ThemeToggleBtn")
        self.btn_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_theme.setToolTip("切换日间 / 夜间模式 (将同步切换所有打开的软件)")
        self.btn_theme.clicked.connect(self.toggle_theme)
        tb_layout.addWidget(self.btn_theme)

        # 检查更新胶囊按钮
        self.btn_update = QPushButton("🔄")
        self.btn_update.setFixedSize(30, 30)
        self.btn_update.setObjectName("UpdateBtn")
        self.btn_update.setProperty("class", "ThemeToggleBtn")
        self.btn_update.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_update.setToolTip("检查软件更新 (获取 GitHub 最新版本)")
        self.btn_update.clicked.connect(self._open_update_dialog)
        tb_layout.addWidget(self.btn_update)

        # 图1对齐的高精度绘制控制按钮
        self.btn_min = CaptionButton(CaptionButtonType.MINIMIZE, self)
        self.btn_min.setToolTip("最小化")
        self.btn_min.clicked.connect(self.showMinimized)
        tb_layout.addWidget(self.btn_min)

        self.btn_max = CaptionButton(CaptionButtonType.MAXIMIZE, self)
        self.btn_max.setToolTip("最大化 / 还原")
        self.btn_max.clicked.connect(self.toggle_maximize)
        tb_layout.addWidget(self.btn_max)

        self.btn_close = CaptionButton(CaptionButtonType.CLOSE, self)
        self.btn_close.setToolTip("关闭")
        self.btn_close.clicked.connect(self.close)
        tb_layout.addWidget(self.btn_close)

        self.root_layout.addWidget(self.title_bar)

        # Main Body Widget for subclasses to populate
        self.body_widget = QWidget()
        self.body_layout = QVBoxLayout(self.body_widget)
        self.body_layout.setContentsMargins(20, 16, 20, 16)
        self.body_layout.setSpacing(12)
        self.root_layout.addWidget(self.body_widget, 1)

        # Bottom Status Bar Frame
        self.status_bar_frame = QFrame()
        self.status_bar_frame.setObjectName("StatusBar")
        self.status_bar_frame.setFixedHeight(28)
        self.status_bar_frame.setStyleSheet("""
            QFrame#StatusBar {
                background-color: transparent;
                border: none;
            }
        """)
        sb_layout = QHBoxLayout(self.status_bar_frame)
        sb_layout.setContentsMargins(16, 0, 8, 0)
        self.lbl_status = QLabel("就绪")
        self.lbl_status.setStyleSheet("color: #64748B; font-size: 11px;")
        sb_layout.addWidget(self.lbl_status)
        sb_layout.addStretch()
        self.resize_grip = CornerResizeGrip(self)
        sb_layout.addWidget(self.resize_grip)
        self.root_layout.addWidget(self.status_bar_frame)

    def set_status(self, text: str):
        if hasattr(self, "lbl_status") and self.lbl_status:
            self.lbl_status.setText(text)

    def set_app_icon(self, icon_path: Path):
        """Sets the title bar and window icon from a file."""
        if Path(icon_path).exists():
            pix = QPixmap(str(icon_path)).scaled(22, 22, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.lbl_title_icon.setPixmap(pix)
            self.setWindowIcon(QIcon(str(icon_path)))

    def apply_theme(self):
        ss = DARK_STYLE_SHEET if self.is_dark_mode else LIGHT_STYLE_SHEET
        self.setStyleSheet(ss)
        self._apply_theme_button_style()

        has_wp = bool(self.wallpaper_pixmap and not self.wallpaper_pixmap.isNull() and self.wallpaper_config.get("enabled", False))
        card_op = float(self.wallpaper_config.get("card_opacity", 0.80))
        styles = get_acrylic_qss_styles(self.is_dark_mode, card_op, has_wallpaper=has_wp)

        if has_wp:
            self.central_widget.setStyleSheet("""
                QWidget#CentralWidget {
                    background-color: transparent;
                    border: none;
                }
            """)
            self.title_bar.setStyleSheet(f"""
                QFrame#TitleBar {{
                    {styles['titlebar']}
                    border-top-left-radius: {0 if self.isMaximized() else 14}px;
                    border-top-right-radius: {0 if self.isMaximized() else 14}px;
                }}
            """)
        else:
            self.central_widget.setStyleSheet("""
                QWidget#CentralWidget {
                    background-color: transparent;
                    border: none;
                }
            """)
            tb_bg = "#2A2B2C" if self.is_dark_mode else "#FFFFFF"
            tb_border = "#3A3A3A" if self.is_dark_mode else "#E5E5E5"
            self.title_bar.setStyleSheet(f"""
                QFrame#TitleBar {{
                    background-color: {tb_bg};
                    border-top-left-radius: {0 if self.isMaximized() else 14}px;
                    border-top-right-radius: {0 if self.isMaximized() else 14}px;
                    border-bottom: 1px solid {tb_border};
                }}
            """)

        # Style btn_wallpaper
        if hasattr(self, "btn_wallpaper"):
            text_color = "#E8E8E8" if self.is_dark_mode else "#1A1A1A"
            self.btn_wallpaper.setStyleSheet(f"""
                QPushButton#WallpaperBtn {{
                    background-color: transparent;
                    color: {text_color};
                    border: none;
                    border-radius: 10px;
                    font-size: 15px;
                    padding: 4px 6px;
                }}
                QPushButton#WallpaperBtn:hover {{
                    background-color: {'#3A3A3A' if self.is_dark_mode else '#E5E5E5'};
                }}
            """)
        if hasattr(self, "btn_theme"):
            self.btn_theme.setText("")
            self.btn_theme.setIcon(theme_toggle_icon(self.is_dark_mode))
            self.btn_theme.setToolTip("切换为浅色白天模式" if self.is_dark_mode else "切换为暗色黑夜模式")
        if hasattr(self, "btn_min"):
            self.btn_min.set_dark_mode(self.is_dark_mode)
        if hasattr(self, "btn_max"):
            self.btn_max.set_dark_mode(self.is_dark_mode)
            self.btn_max.set_maximized_state(self.isMaximized())
        if hasattr(self, "btn_close"):
            self.btn_close.set_dark_mode(self.is_dark_mode)
        if hasattr(self, "resize_grip"):
            self.resize_grip.set_dark_mode(self.is_dark_mode)
            self.resize_grip.setVisible(not self.isMaximized())
        apply_dm_window_frame(self, self.is_dark_mode)

    def _apply_theme_button_style(self):
        """
        Apply the theme pill with a widget-level stylesheet.

        Child-level stylesheet has priority over the window QSS, so the capsule keeps its
        rounded corners even if a page/table stylesheet or a native palette rule tries to
        paint a square QPushButton background.
        """
        if not hasattr(self, "btn_theme") or self.btn_theme is None:
            return
        if self.is_dark_mode:
            bg, fg, bd = "#2A2B2C", "#F5F5F5", "#4A4A4A"
            hover_bg, hover_fg, hover_bd = "#3A3A3A", "#FFFFFF", "#64748B"
        else:
            bg, fg, bd = "#FFFFFF", "#3A3A3A", "#D4D4D4"
            hover_bg, hover_fg, hover_bd = "#EFEFEF", "#2A2B2C", "#94A3B8"
        self.btn_theme.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {fg};
                border: none;
                border-radius: 10px;
                padding: 4px 6px;
                min-height: 24px;
            }}
            QPushButton:hover {{
                background-color: {hover_bg};
                color: {hover_fg};
                border: none;
            }}
            QPushButton:pressed {{
                background-color: {hover_bg};
                border: none;
            }}
        """)

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        set_global_theme("dark" if self.is_dark_mode else "light")
        self.apply_theme()

    def _on_wallpaper_event(self, target_subapp: str):
        self.reload_wallpaper()

    def _on_wallpaper_file_changed(self, path: str):
        self._wp_debounce_timer.start()

    def open_wallpaper_settings(self):
        dlg = DMWallpaperDialog(self, subapp_id=getattr(self, "subapp_id", "launcher"))
        dlg.exec()
        self.reload_wallpaper()

    def reload_wallpaper(self):
        self.wallpaper_config = load_wallpaper_config(getattr(self, "subapp_id", "launcher"))
        if self.wallpaper_config.get("enabled", False):
            img_path = resolve_cached_image_path(self.wallpaper_config.get("cached_image_path", ""))
            if img_path and img_path.exists():
                self.wallpaper_pixmap = QPixmap(str(img_path))
            else:
                self.wallpaper_pixmap = None
        else:
            self.wallpaper_pixmap = None

        if GLOBAL_WALLPAPER_CONFIG_PATH.exists():
            try:
                self._last_wallpaper_mtime = GLOBAL_WALLPAPER_CONFIG_PATH.stat().st_mtime
            except Exception:
                pass

        self.apply_theme()
        if hasattr(self, "central_widget") and self.central_widget:
            self.central_widget.update()
        self.update()

    def paint_window_background(self, painter: QPainter, rect: QRect):
        has_wp = bool(self.wallpaper_pixmap and not self.wallpaper_pixmap.isNull() and self.wallpaper_config.get("enabled", False))
        if has_wp:
            tint_dark = float(self.wallpaper_config.get("tint_opacity_dark", 0.68))
            tint_light = float(self.wallpaper_config.get("tint_opacity_light", 0.72))
            radius = 0 if self.isMaximized() else 8
            render_wallpaper_background(
                painter, rect, self.wallpaper_pixmap, self.is_dark_mode,
                tint_dark=tint_dark, tint_light=tint_light, border_radius=radius
            )
        else:
            bg_col = QColor("#292929" if self.is_dark_mode else "#F5F5F5")
            if not self.isMaximized():
                path = QPainterPath()
                path.addRoundedRect(QRectF(rect), 8, 8)
                painter.fillPath(path, bg_col)
            else:
                painter.fillRect(rect, bg_col)

    def check_external_theme_change(self):
        """Checks if another window changed the global theme or wallpaper and synchronizes instantly."""
        global_mode = get_global_theme()
        should_be_dark = (global_mode == "dark")
        theme_changed = (self.is_dark_mode != should_be_dark)
        if theme_changed:
            self.is_dark_mode = should_be_dark

        wp_mtime = 0
        if GLOBAL_WALLPAPER_CONFIG_PATH.exists():
            try:
                wp_mtime = GLOBAL_WALLPAPER_CONFIG_PATH.stat().st_mtime
            except Exception:
                pass
        wp_changed = (getattr(self, "_last_wallpaper_mtime", 0) != wp_mtime)

        if theme_changed or wp_changed:
            self.reload_wallpaper()

    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        if hasattr(self, "btn_max"):
            self.btn_max.set_maximized_state(self.isMaximized())
        if hasattr(self, "resize_grip"):
            self.resize_grip.setVisible(not self.isMaximized())

    def changeEvent(self, event):
        if event.type() == event.Type.WindowStateChange:
            if hasattr(self, "btn_max"):
                self.btn_max.set_maximized_state(self.isMaximized())
            if hasattr(self, "resize_grip"):
                self.resize_grip.setVisible(not self.isMaximized())
        super().changeEvent(event)

    def center_on_screen(self):
        screen = self.screen() or QGuiApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            target_w = min(self.width(), int(avail.width() * 0.94))
            target_h = min(self.height(), int(avail.height() * 0.88))
            if target_w != self.width() or target_h != self.height():
                self.resize(target_w, target_h)
            new_x = avail.left() + max(0, (avail.width() - self.width()) // 2)
            new_y = avail.top() + max(0, (avail.height() - self.height()) // 2)
            self.move(new_x, new_y)

    def moveEvent(self, event):
        super().moveEvent(event)
        # Dynamic multi-screen adaptation: shrink gracefully if moved to a screen with smaller resolution
        screen = self.screen() or QGuiApplication.screenAt(self.geometry().center())
        if screen and not self.isMaximized():
            avail = screen.availableGeometry()
            cur_w = self.width()
            cur_h = self.height()
            need_resize = False

            # Allow minimum size to scale down if moving to a smaller monitor
            if self.minimumWidth() > int(avail.width() * 0.88):
                self.setMinimumWidth(max(400, int(avail.width() * 0.65)))
            if self.minimumHeight() > int(avail.height() * 0.84):
                self.setMinimumHeight(max(300, int(avail.height() * 0.55)))

            if cur_w > avail.width() * 0.95:
                cur_w = max(self.minimumWidth(), int(avail.width() * 0.94))
                need_resize = True
            if cur_h > avail.height() * 0.90:
                cur_h = max(self.minimumHeight(), int(avail.height() * 0.88))
                need_resize = True
            if need_resize:
                self.resize(cur_w, cur_h)

    # -----------------------------------------------------------------
    # Multi-Screen & High-DPI DPI-Safe 8-Directional Edge Drag Resizing
    # -----------------------------------------------------------------
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

    def mousePressEvent(self, event):
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
            if hasattr(self, "title_bar") and pos.y() <= self.title_bar.height():
                # Avoid capturing if user clicked on title bar buttons
                tb_pos = self.title_bar.mapFromParent(pos)
                child = self.title_bar.childAt(tb_pos)
                if child is None or child is self.title_bar or isinstance(child, QLabel):
                    self._is_dragging = True
                    self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                    event.accept()
                    return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
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

    def _open_update_dialog(self):
        try:
            from common.app_updater import show_update_dialog
            show_update_dialog(parent=self)
        except Exception as e:
            from common.ui_theme import ModernDialog
            ModernDialog.warning(parent=self, title="检查更新失败", message=f"无法打开更新器:\n{e}")

    def closeEvent(self, event):
        qApp = QApplication.instance()
        if qApp:
            try:
                qApp.removeEventFilter(self)
            except Exception:
                pass
        super().closeEvent(event)

    def mouseReleaseEvent(self, event):
        self._is_dragging = False
        self._resize_edge = 0
        self.unsetCursor()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and hasattr(self, "title_bar") and event.position().y() <= self.title_bar.height():
            tb_pos = self.title_bar.mapFromParent(event.position().toPoint())
            child = self.title_bar.childAt(tb_pos)
            if child is None or child is self.title_bar or isinstance(child, QLabel):
                self.toggle_maximize()
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

