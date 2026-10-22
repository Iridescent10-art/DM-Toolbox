# -*- coding: utf-8 -*-
"""
DM 通用设计语言底座 SDK (DM Design System Core SDK) - v1.2.6
============================================================
以【DM工具箱主界面】为唯一标准设计规范，提供：
1. DWM 硬件级无锯齿平滑圆角与边框合成机制 (apply_dm_window_frame)
2. 标准右下角缩放斜纹标识 (DMSizeGrip, 继承 QSizeGrip)
3. 统一底部状态与操作底栏 (DMFooterBar)
4. 标准圆角卡片容器 (DMCardFrame)
5. 全局跨窗口 / 跨进程主题协调器 (DMThemeManager)
6. 现代化标准窗口基类 (DMBaseWindow)

新增任何子软件只需：
    from dm_ui_core import DMBaseWindow, DMCardFrame, DMThemeManager
即可开箱即用生成 100% 视觉对齐的现代化界面。
"""

import sys
import os
import ctypes
from ctypes import wintypes
from pathlib import Path
from typing import Optional, List, Dict, Any, Union, Tuple

from PySide6.QtCore import (
    Qt, QPoint, QTimer, QRectF, QPointF, QEvent,
    QPropertyAnimation, QEasingCurve, Signal, QObject, QSize
)
from PySide6.QtGui import (
    QIcon, QFont, QPixmap, QColor, QPainter, QPen,
    QCursor, QGuiApplication, QRegion, QPainterPath
)
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QGraphicsDropShadowEffect,
    QApplication, QProgressBar, QDialog, QSizeGrip, QSizePolicy,
    QSpacerItem
)

# Root path resolution
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

ASSETS_DIR = Path(__file__).resolve().parent / "assets"

def _theme_toggle_icon(is_dark: bool, size: int = 32) -> QIcon:
    """Crescent moon with craters (JXR converter style)."""
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
# Windows DWM Hardware Corner & Frame API Constants
# =========================================================================
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_BORDER_COLOR = 34
DWMWCP_ROUND = 2  # Hardware-accelerated rounded corners (Win 11)

# =========================================================================
# 标准现代化极简圆角滚动条样式 (与图2主界面 100% 对齐)
# =========================================================================
SCROLLBAR_LIGHT_QSS = """
QScrollArea {
    border: none;
    background: transparent;
}
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 4px 2px 4px 0px;
    border: none;
}
QScrollBar::handle:vertical {
    background: rgba(100, 116, 139, 0.60);
    min-height: 48px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(51, 65, 85, 0.85);
}
QScrollBar::handle:vertical:pressed {
    background: rgba(30, 41, 59, 0.95);
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
    width: 0px;
    border: none;
    background: none;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
QScrollBar:horizontal {
    height: 0px;
    width: 0px;
    background: transparent;
    border: none;
}
QScrollBar::handle:horizontal {
    height: 0px;
    width: 0px;
    background: transparent;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    height: 0px;
    width: 0px;
    background: transparent;
    border: none;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}
"""

SCROLLBAR_DARK_QSS = """
QScrollArea {
    border: none;
    background: transparent;
}
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 4px 2px 4px 0px;
    border: none;
}
QScrollBar::handle:vertical {
    background: rgba(148, 163, 184, 0.55);
    min-height: 48px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(203, 213, 225, 0.85);
}
QScrollBar::handle:vertical:pressed {
    background: rgba(241, 245, 249, 0.95);
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
    width: 0px;
    border: none;
    background: none;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
QScrollBar:horizontal {
    height: 0px;
    width: 0px;
    background: transparent;
    border: none;
}
QScrollBar::handle:horizontal {
    height: 0px;
    width: 0px;
    background: transparent;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    height: 0px;
    width: 0px;
    background: transparent;
    border: none;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}
"""


def apply_dm_window_frame(window: QWidget, is_dark: Optional[bool] = None) -> bool:
    """
    为目标窗口应用 Windows DWM 硬件级圆角合成与主题对齐边框，
    彻底消除 QSS 软裁剪带来的四角白边与锯齿毛刺。
    """
    if is_dark is None:
        is_dark = (get_global_theme() == "dark")

    if isinstance(window, QDialog):
        window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    try:
        hwnd = int(window.winId())
        if hwnd:
            # 1. 强制启用 Windows 11 原生硬件平滑圆角 (DWMWCP_ROUND = 2)
            corner_val = ctypes.c_int(DWMWCP_ROUND)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_WINDOW_CORNER_PREFERENCE,
                ctypes.byref(corner_val),
                ctypes.sizeof(corner_val)
            )

            # 2. 同步暗黑/浅色沉浸式系统边框与标题栏属性
            dark_val = ctypes.c_int(1 if is_dark else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(dark_val),
                ctypes.sizeof(dark_val)
            )

            # 3. 设置 DWM 硬件级边框对齐色 (0x00BBGGRR 格式)
            # 白天: #E5E5E5 -> 0x00FEE6D6; 黑夜: #303132 -> 0x003E2B23
            border_color = ctypes.c_ulong(0x003E2B23 if is_dark else 0x00FEE6D6)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_BORDER_COLOR,
                ctypes.byref(border_color),
                ctypes.sizeof(border_color)
            )
            return True
    except Exception:
        pass
    return False


# =========================================================================
# 标准右下角缩放手柄 (DMSizeGrip 继承 QSizeGrip)
# =========================================================================
class DMSizeGrip(QSizeGrip):
    """
    标准右下角缩放手柄，继承自 QSizeGrip。
    - 具有完全的 QSizeGrip 类型兼容性 (findChildren(QSizeGrip) 完全匹配)
    - 绘制与【图2：主界面】100% 对齐的双斜线 (//) 矢量图标 (16x16px)
    - 支持鼠标拖拽右下角平滑双向无极缩放窗口
    """
    def __init__(self, parent_window: QWidget = None):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.setFixedSize(16, 16)
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self.setToolTip("拖拽右下角可斜向自由缩放窗口大小")
        self.setMouseTracking(True)
        self.is_dark_mode = (get_global_theme() == "dark")

    def set_dark_mode(self, is_dark: bool):
        self.is_dark_mode = is_dark
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        color = QColor("#64748B") if self.is_dark_mode else QColor("#94A3B8")
        pen = QPen(color, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        w = self.width()
        h = self.height()
        # 绘制与图2右下角完全一致的双平行斜线 //
        painter.drawLine(w - 5, h - 3, w - 3, h - 5)
        painter.drawLine(w - 9, h - 3, w - 3, h - 9)
        painter.drawLine(w - 13, h - 3, w - 3, h - 13)


# =========================================================================
# 标准底栏组件 (DMFooterBar)
# =========================================================================
class DMFooterBar(QFrame):
    """
    DM 通用底栏组件 (对齐图2底部状态与图3/图4操作按钮区)。
    - 左侧：实时状态文本 (如 '● 状态: 就绪')
    - 中右侧：可插入操作按钮组
    - 最右下角：挂载标准 DMSizeGrip
    """
    def __init__(self, parent_window: QWidget = None, initial_status: str = "● 状态: 就绪"):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.setObjectName("DMFooterBar")
        self.setFixedHeight(32)
        self.setStyleSheet("""
            QFrame#DMFooterBar {
                background-color: transparent;
                border: none;
            }
        """)

        self.root_layout = QHBoxLayout(self)
        self.root_layout.setContentsMargins(16, 0, 4, 4)
        self.root_layout.setSpacing(12)

        # 状态文本标签
        self.lbl_status = QLabel(initial_status)
        self.lbl_status.setObjectName("DMFooterStatus")
        self.lbl_status.setStyleSheet("color: #64748B; font-size: 11px; font-weight: 500;")
        self.root_layout.addWidget(self.lbl_status)

        self.root_layout.addStretch()

        # 动态操作按钮容器 (供子软件挂载按钮)
        self.actions_layout = QHBoxLayout()
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        self.actions_layout.setSpacing(10)
        self.root_layout.addLayout(self.actions_layout)

        # 最右下角标准缩放斜纹手柄
        self.size_grip = DMSizeGrip(parent_window or self)
        self.root_layout.addWidget(
            self.size_grip,
            0,
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight
        )

    def set_status(self, text: str):
        self.lbl_status.setText(text)

    def add_action_widget(self, widget: QWidget):
        self.actions_layout.addWidget(widget)

    def set_dark_mode(self, is_dark: bool):
        color = "#94A3B8" if is_dark else "#64748B"
        self.lbl_status.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: 500;")
        self.size_grip.set_dark_mode(is_dark)


# =========================================================================
# 标准卡片容器组件 (DMCardFrame)
# =========================================================================
class DMCardFrame(QFrame):
    """
    DM 通用标准卡片容器 (图2同款纯白/深灰蓝圆角卡片)。
    - border-radius: 14px
    - 悬停微光边框与平滑过渡
    - 统一支持 title, subtitle, badge
    """
    def __init__(self, title: str = "", subtitle: str = "", badge_text: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("DMCardFrame")
        self.setProperty("class", "GridCard")
        self.is_dark = (get_global_theme() == "dark")

        self.card_layout = QVBoxLayout(self)
        self.card_layout.setContentsMargins(20, 16, 20, 16)
        self.card_layout.setSpacing(10)

        if title or subtitle or badge_text:
            header = QHBoxLayout()
            header.setSpacing(10)

            title_box = QVBoxLayout()
            title_box.setSpacing(3)
            if title:
                self.lbl_title = QLabel(title)
                self.lbl_title.setObjectName("CardTitle")
                self.lbl_title.setStyleSheet("font-size: 15px; font-weight: 700;")
                title_box.addWidget(self.lbl_title)
            if subtitle:
                self.lbl_sub = QLabel(subtitle)
                self.lbl_sub.setObjectName("CardSubtitle")
                self.lbl_sub.setStyleSheet("font-size: 12px; color: #64748B;")
                self.lbl_sub.setWordWrap(True)
                title_box.addWidget(self.lbl_sub)
            header.addLayout(title_box, 1)

            if badge_text:
                self.lbl_badge = QLabel(badge_text)
                self.lbl_badge.setStyleSheet("""
                    padding: 3px 10px;
                    border-radius: 6px;
                    font-size: 11px;
                    font-weight: 600;
                    background-color: #E8E8E8;
                    color: #2F8F5B;
                """)
                header.addWidget(self.lbl_badge, 0, Qt.AlignmentFlag.AlignTop)

            self.card_layout.addLayout(header)

        self.apply_theme(self.is_dark)

    def apply_theme(self, is_dark: bool):
        self.is_dark = is_dark
        bg = "#2A2B2C" if is_dark else "#FFFFFF"
        border = "#3A3A3A" if is_dark else "#E5E5E5"
        title_c = "#E8E8E8" if is_dark else "#1A1A1A"
        sub_c = "#A0A0A0" if is_dark else "#8A8A8A"

        self.setStyleSheet(f"""
            QFrame#DMCardFrame {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 14px;
            }}
            QFrame#DMCardFrame:hover {{
                border: 1px solid {'#3E9E69' if is_dark else '#2F8F5B'};
            }}
        """)
        if hasattr(self, "lbl_title"):
            self.lbl_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {title_c}; border: none; background: transparent;")
        if hasattr(self, "lbl_sub"):
            self.lbl_sub.setStyleSheet(f"font-size: 12px; color: {sub_c}; border: none; background: transparent;")


# =========================================================================
# 全局主题同步管理器 (DMThemeManager)
# =========================================================================
class DMThemeManager:
    """全局跨进程 / 跨窗口主题同步协调器"""
    @staticmethod
    def get_current_theme() -> str:
        return get_global_theme()

    @staticmethod
    def set_theme(theme_name: str):
        set_global_theme(theme_name)

    @staticmethod
    def is_dark() -> bool:
        return get_global_theme() == "dark"

    @staticmethod
    def toggle_theme() -> str:
        new_theme = "light" if DMThemeManager.is_dark() else "dark"
        DMThemeManager.set_theme(new_theme)
        return new_theme


# =========================================================================
# 顶栏按钮 (CaptionButton)
# =========================================================================
class DMCaptionButtonType:
    MINIMIZE = 1
    MAXIMIZE = 2
    CLOSE = 3


class DMCaptionButton(QPushButton):
    """高精度矢量自绘顶栏按钮 (最小化 / 最大化 / 关闭)"""
    def __init__(self, btn_type: int, parent=None):
        super().__init__(parent)
        self.btn_type = btn_type
        self.is_maximized = False
        self.is_hovered = False
        self.is_pressed = False
        self.is_dark_mode = (get_global_theme() == "dark")
        self.setFixedSize(36, 30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

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
        self.is_pressed = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_pressed = True
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.is_pressed = False
        self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        cx = w / 2.0
        cy = h / 2.0

        # Background on hover / pressed
        if self.btn_type == DMCaptionButtonType.CLOSE:
            if self.is_pressed:
                painter.fillRect(self.rect(), QColor("#B91C1C"))
            elif self.is_hovered:
                painter.fillRect(self.rect(), QColor("#E11D48"))
        else:
            if self.is_pressed:
                bg = QColor("#3A3A3A") if self.is_dark_mode else QColor("#D4D4D4")
                painter.fillRect(self.rect(), bg)
            elif self.is_hovered:
                bg = QColor("#2A2B2C") if self.is_dark_mode else QColor("#E5E5E5")
                painter.fillRect(self.rect(), bg)

        # Icon color
        if self.btn_type == DMCaptionButtonType.CLOSE and self.is_hovered:
            icon_color = QColor("#FFFFFF")
        else:
            icon_color = QColor("#D4D4D4") if self.is_dark_mode else QColor("#4A4A4A")

        pen = QPen(icon_color, 1.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        if self.btn_type == DMCaptionButtonType.MINIMIZE:
            painter.drawLine(QPointF(cx - 5.0, cy), QPointF(cx + 5.0, cy))
        elif self.btn_type == DMCaptionButtonType.MAXIMIZE:
            if self.is_maximized:
                painter.drawRect(QRectF(cx - 3.5, cy - 5.0, 7.5, 7.5))
                painter.drawRect(QRectF(cx - 5.0, cy - 3.5, 7.5, 7.5))
            else:
                painter.drawRect(QRectF(cx - 4.5, cy - 4.5, 9.0, 9.0))
        elif self.btn_type == DMCaptionButtonType.CLOSE:
            painter.drawLine(QPointF(cx - 4.5, cy - 4.5), QPointF(cx + 4.5, cy + 4.5))
            painter.drawLine(QPointF(cx + 4.5, cy - 4.5), QPointF(cx - 4.5, cy + 4.5))


# =========================================================================
# 标准窗口基类 (DMBaseWindow)
# =========================================================================
class DMBaseWindow(QMainWindow):
    """
    DM 通用标准窗口基类。
    规范：以【图2：DM工具箱主界面】为基准设计：
    - DWM 硬件级无锯齿圆角抗锯齿合成 (DWMWA_WINDOW_CORNER_PREFERENCE = 2)
    - 图2同款无缝标题栏 (左侧图标+标题，右侧黑夜/白天胶囊切换 + 最小化/最大化/关闭按钮)
    - 统一外框 QSS (白天 #F4F6F9 / 黑夜 #14171F，1px 细腻描边)
    - 统一底部状态栏与最右下角标准 QSizeGrip 斜纹手柄
    - 8 方向 DPI 智能边缘拖拽缩放
    - 跨窗口实时 500ms 主题同步
    """
    BORDER_SIZE = 7
    CORNER_SIZE = 20

    def __init__(self, title: str = "DM工具箱", width: int = 960, height: int = 640, icon_filename: str = None):
        super().__init__()
        self.setWindowTitle(title)
        self.BORDER_SIZE = 7
        self.CORNER_SIZE = 20

        # Frameless window configuration
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowMinMaxButtonsHint)
        self.setMouseTracking(True)

        # 屏幕几何自适应保护
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

        # 拖拽与缩放状态机
        self._is_dragging = False
        self._drag_pos = QPoint()
        self._resize_edge = 0
        self._resize_start_pos = QPoint()
        self._resize_start_geom = self.geometry()
        self._edge_cursor_active = False

        qApp = QApplication.instance()
        if qApp:
            qApp.installEventFilter(self)

        self.is_dark_mode = (get_global_theme() == "dark")
        self._setup_base_ui(title)

        if icon_filename:
            icon_p = ASSETS_DIR / icon_filename
            if icon_p.exists():
                self.set_app_icon(icon_p)

        self.apply_theme()
        self.center_on_screen()

        # DWM 硬件级圆角合成
        apply_dm_window_frame(self, self.is_dark_mode)

        # 跨进程主题同步器 (500ms)
        self.theme_sync_timer = QTimer(self)
        self.theme_sync_timer.setInterval(500)
        self.theme_sync_timer.timeout.connect(self.check_external_theme_change)
        self.theme_sync_timer.start()

    def _setup_base_ui(self, title: str):
        # 根容器
        self.central_widget = QWidget()
        self.central_widget.setObjectName("RootContainer")
        self.central_widget.setMouseTracking(True)
        self.setCentralWidget(self.central_widget)

        self.root_layout = QVBoxLayout(self.central_widget)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        # 自定义顶栏 (TitleBar)
        self.title_bar = QFrame()
        self.title_bar.setObjectName("TitleBar")
        self.title_bar.setFixedHeight(44)

        tb_layout = QHBoxLayout(self.title_bar)
        tb_layout.setContentsMargins(16, 0, 10, 0)
        tb_layout.setSpacing(8)
        tb_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.lbl_title_icon = QLabel()
        self.lbl_title_icon.setFixedSize(22, 22)
        tb_layout.addWidget(self.lbl_title_icon)

        self.lbl_window_title = QLabel(title)
        self.lbl_window_title.setObjectName("WindowTitle")
        self.lbl_window_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        tb_layout.addWidget(self.lbl_window_title)

        tb_layout.addStretch()

        # 图2右上角主题切换胶囊
        self.btn_theme = QPushButton("")
        self.btn_theme.setFixedSize(30, 30)
        self.btn_theme.setIcon(_theme_toggle_icon(self.is_dark_mode))
        self.btn_theme.setIconSize(QSize(16, 16))
        self.btn_theme.setObjectName("ThemeToggleBtn")
        self.btn_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_theme.setToolTip("切换日间 / 夜间模式 (将同步切换所有打开的软件)")
        self.btn_theme.clicked.connect(self.toggle_theme)
        tb_layout.addWidget(self.btn_theme)

        # 控制按钮组 (最小化 / 最大化 / 关闭)
        self.btn_min = DMCaptionButton(DMCaptionButtonType.MINIMIZE, self)
        self.btn_min.setToolTip("最小化")
        self.btn_min.clicked.connect(self.showMinimized)
        tb_layout.addWidget(self.btn_min)

        self.btn_max = DMCaptionButton(DMCaptionButtonType.MAXIMIZE, self)
        self.btn_max.setToolTip("最大化 / 还原")
        self.btn_max.clicked.connect(self.toggle_maximize)
        tb_layout.addWidget(self.btn_max)

        self.btn_close = DMCaptionButton(DMCaptionButtonType.CLOSE, self)
        self.btn_close.setToolTip("关闭")
        self.btn_close.clicked.connect(self.close)
        tb_layout.addWidget(self.btn_close)

        self.root_layout.addWidget(self.title_bar)

        # 核心内容视窗
        self.body_widget = QWidget()
        self.body_layout = QVBoxLayout(self.body_widget)
        self.body_layout.setContentsMargins(20, 14, 20, 14)
        self.body_layout.setSpacing(12)
        self.root_layout.addWidget(self.body_widget, 1)

        # 标准底栏组件 (内置状态显示与右下角 DMSizeGrip)
        self.footer_bar = DMFooterBar(self)
        self.root_layout.addWidget(self.footer_bar)

    def set_status(self, text: str):
        if hasattr(self, "footer_bar") and self.footer_bar:
            self.footer_bar.set_status(text)

    def set_app_icon(self, icon_path: Union[str, Path]):
        p = Path(icon_path)
        if p.exists():
            pix = QPixmap(str(p)).scaled(22, 22, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.lbl_title_icon.setPixmap(pix)
            self.setWindowIcon(QIcon(str(p)))

    def toggle_theme(self):
        new_theme = DMThemeManager.toggle_theme()
        self.is_dark_mode = (new_theme == "dark")
        self.apply_theme()

    def check_external_theme_change(self):
        target_is_dark = (get_global_theme() == "dark")
        if self.is_dark_mode != target_is_dark:
            self.is_dark_mode = target_is_dark
            self.apply_theme()

    def apply_theme(self):
        bg = "#292929" if self.is_dark_mode else "#F5F5F5"
        border = "#303132" if self.is_dark_mode else "#E5E5E5"
        tb_bg = "#2A2B2C" if self.is_dark_mode else "#FFFFFF"
        tb_border = "#3A3A3A" if self.is_dark_mode else "#E5E5E5"
        text_color = "#E8E8E8" if self.is_dark_mode else "#1A1A1A"

        # Synchronize application palette to prevent OS dark palette bleedthrough
        app = QApplication.instance()
        if app:
            from PySide6.QtGui import QPalette
            pal = QPalette()
            if self.is_dark_mode:
                pal.setColor(QPalette.ColorRole.Window, QColor("#292929"))
                pal.setColor(QPalette.ColorRole.WindowText, QColor("#F5F5F5"))
                pal.setColor(QPalette.ColorRole.Base, QColor("#2A2B2C"))
                pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#292929"))
                pal.setColor(QPalette.ColorRole.Text, QColor("#F5F5F5"))
            else:
                pal.setColor(QPalette.ColorRole.Window, QColor("#F5F5F5"))
                pal.setColor(QPalette.ColorRole.WindowText, QColor("#2A2B2C"))
                pal.setColor(QPalette.ColorRole.Base, QColor("#FFFFFF"))
                pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#EFEFEF"))
                pal.setColor(QPalette.ColorRole.Text, QColor("#2A2B2C"))
            app.setPalette(pal)

        # 0. 全局现代化极简圆角滚动条样式 (与图2主界面 100% 对齐)
        scrollbar_qss = SCROLLBAR_DARK_QSS if self.is_dark_mode else SCROLLBAR_LIGHT_QSS
        self.setStyleSheet(scrollbar_qss)

        # 1. 根外框样式 (根据最大化状态自适应圆角与边框)
        if self.isMaximized():
            self.central_widget.setStyleSheet(f"""
                QWidget#RootContainer {{
                    background-color: {bg};
                    border: none;
                    border-radius: 0px;
                }}
            """)
        else:
            self.central_widget.setStyleSheet(f"""
                QWidget#RootContainer {{
                    background-color: {bg};
                    border: none;
                    border-radius: 8px;
                }}
            """)

        # 2. 标题栏
        self.title_bar.setStyleSheet(f"""
            QFrame#TitleBar {{
                background-color: {tb_bg};
                border-top-left-radius: {0 if self.isMaximized() else 14}px;
                border-top-right-radius: {0 if self.isMaximized() else 14}px;
                border-bottom: 1px solid {tb_border};
            }}
        """)
        self.lbl_window_title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {text_color}; border: none; background: transparent;")

        # 3. 主题胶囊按钮
        self.btn_theme.setText("")
        self.btn_theme.setIcon(_theme_toggle_icon(self.is_dark_mode))
        pill_bg = "#303132" if self.is_dark_mode else "#EFEFEF"
        pill_fg = "#D4D4D4" if self.is_dark_mode else "#4A4A4A"
        pill_border = "#3A3A3A" if self.is_dark_mode else "#E5E5E5"
        self.btn_theme.setStyleSheet(f"""
            QPushButton#ThemeToggleBtn {{
                background-color: transparent;
                color: {text_color};
                border: none;
                border-radius: 10px;
                padding: 4px 6px;
            }}
            QPushButton#ThemeToggleBtn:hover {{
                background-color: {'#3A3A3A' if self.is_dark_mode else '#E5E5E5'};
                color: {'#F5F5F5' if self.is_dark_mode else '#2A2B2C'};
            }}
        """)

        # 4. 标题栏按钮
        if hasattr(self, "btn_min"):
            self.btn_min.set_dark_mode(self.is_dark_mode)
        if hasattr(self, "btn_max"):
            self.btn_max.set_dark_mode(self.is_dark_mode)
            self.btn_max.set_maximized_state(self.isMaximized())
        if hasattr(self, "btn_close"):
            self.btn_close.set_dark_mode(self.is_dark_mode)

        # 5. 底栏与手柄
        if hasattr(self, "footer_bar"):
            self.footer_bar.set_dark_mode(self.is_dark_mode)

        # 6. DWM 硬件圆角重同步
        apply_dm_window_frame(self, self.is_dark_mode)

    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        self.apply_theme()

    def center_on_screen(self):
        screen = self.screen() or QGuiApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            new_x = avail.left() + max(0, (avail.width() - self.width()) // 2)
            new_y = avail.top() + max(0, (avail.height() - self.height()) // 2)
            self.move(new_x, new_y)

    # -----------------------------------------------------------------
    # Multi-Screen & High-DPI DPI-Safe 8-Directional Edge Drag Resizing
    # -----------------------------------------------------------------
    def _get_resize_edge(self, pos: QPoint) -> int:
        b = self.BORDER_SIZE
        c = self.CORNER_SIZE
        w = self.width()
        h = self.height()

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

                if self._resize_edge & 1:  # Left
                    new_w = max(min_w, w - delta.x())
                    x = rect.right() - new_w + 1
                    w = new_w
                elif self._resize_edge & 2:  # Right
                    w = max(min_w, w + delta.x())

                if self._resize_edge & 4:  # Top
                    new_h = max(min_h, h - delta.y())
                    y = rect.bottom() - new_h + 1
                    h = new_h
                elif self._resize_edge & 8:  # Bottom
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

                if self._resize_edge & 1:
                    new_w = max(min_w, w - delta.x())
                    x = rect.right() - new_w + 1
                    w = new_w
                elif self._resize_edge & 2:
                    w = max(min_w, w + delta.x())

                if self._resize_edge & 4:
                    new_h = max(min_h, h - delta.y())
                    y = rect.bottom() - new_h + 1
                    h = new_h
                elif self._resize_edge & 8:
                    h = max(min_h, h + delta.y())

                self.setGeometry(x, y, w, h)
                return True

            elif et == QEvent.Type.MouseButtonRelease:
                self._resize_edge = 0
                self.unsetCursor()
                self._edge_cursor_active = False
                return True

        # Wheel event handling: active for both normal and maximized window states
        if isinstance(watched, QWidget) and et == QEvent.Type.Wheel:
            try:
                if watched.window() is self:
                    from PySide6.QtWidgets import QComboBox, QScrollBar
                    if not isinstance(watched, QScrollBar):
                        if not (isinstance(watched, QComboBox) and watched.view() and watched.view().isVisible()):
                            if hasattr(self, "scroll_area") and self.scroll_area is not None:
                                bar = self.scroll_area.verticalScrollBar()
                                if bar is not None and bar.maximum() > 0:
                                    # Support both high-precision touchpads (pixelDelta) and standard mouse wheels (angleDelta)
                                    delta = 0
                                    p_delta = event.pixelDelta().y()
                                    if p_delta != 0:
                                        delta = p_delta
                                    else:
                                        a_delta = event.angleDelta().y()
                                        if a_delta != 0:
                                            delta = a_delta
                                    if delta != 0:
                                        bar.setValue(bar.value() - delta)
                                        if hasattr(self, "scroll_area") and self.scroll_area and self.scroll_area.viewport():
                                            self.scroll_area.viewport().update()
                                        return True
            except Exception:
                pass

        if not self.isMaximized() and isinstance(watched, QWidget):
            try:
                from PySide6.QtWidgets import QScrollBar
                if isinstance(watched, QScrollBar) or (hasattr(self, "scroll_area") and watched is self.scroll_area.verticalScrollBar()):
                    return super().eventFilter(watched, event)
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


# =========================================================================
# 标准现代化圆角模态对话框 (ModernDialog)
# 与 DM 工具箱设计语言 100% 对齐，支持亮色 (白天) / 暗色 (夜间) 高对比度自适应
# =========================================================================
class ModernDialog(QDialog):
    """
    DM 通用设计语言标准模态对话框。
    具备：
    1. Windows 11 DWM 硬件级圆角与半透明浮层微阴影。
    2. 白天 (Light) 与夜间 (Dark) 高对比度自适应配色方案，保证白天烈日/强光下文字与按钮 100% 清晰可见。
    3. 支持 info, success, warning, error, question 五种状态指示器及高对比度圆角徽章。
    4. 智能支持长文本滚动、可复制文本 (TextSelectableByMouse)。
    5. 支持原生现代按钮、多分支决策 (choice3)、确认对话 (confirm)。
    """
    def __init__(
        self,
        parent=None,
        title: str = "提示",
        message: str = "",
        dialog_type: str = "info",
        is_dark: Optional[bool] = None,
        custom_buttons: Optional[List[Tuple[str, int, str]]] = None,
        ok_text: str = "我知道了",
        cancel_text: str = "取消"
    ):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(True)

        self.is_dark = self._resolve_is_dark(parent, is_dark)
        is_dark_eff = self.is_dark

        # 配色系统：严格遵循 WCAG 2.1 AAA 高对比度规范
        if is_dark_eff:
            bg_color = "#1E293B"      # 深深蓝灰卡片底色
            border_color = "#334155"  # 深灰边框
            text_color = "#F8FAFC"    # 标题文字 (纯净高亮白)
            msg_color = "#CBD5E1"     # 正文文字 (浅灰蓝，对比度 > 9:1)
            btn_sec_bg = "#334155"
            btn_sec_border = "#475569"
            btn_sec_text = "#F8FAFC"
            btn_sec_hover = "#475569"
            btn_can_bg = "#0F172A"
            btn_can_border = "#334155"
            btn_can_text = "#94A3B8"
            btn_can_hover = "#1E293B"
            btn_can_hover_text = "#F8FAFC"
            badge_map = {
                "success": ("✓", "#064E3B", "#34D399"),
                "info": ("ℹ", "#0C4A6E", "#38BDF8"),
                "warning": ("⚠", "#78350F", "#FBBF24"),
                "error": ("✕", "#7F1D1D", "#F87171"),
                "question": ("?", "#4C1D95", "#A78BFA")
            }
        else:
            # 白天模式：彻底消除白字泛白、浅灰模糊，确保极其清晰锐利
            bg_color = "#FFFFFF"      # 纯白卡片底色
            border_color = "#CBD5E1"  # 明亮利落边框
            text_color = "#0F172A"    # 标题文字 (深岩灰，极强对比度)
            msg_color = "#334155"     # 正文文字 (深墨蓝灰，对比度 > 9.5:1)
            btn_sec_bg = "#F1F5F9"
            btn_sec_border = "#CBD5E1"
            btn_sec_text = "#1E293B"  # 深色文字，绝非泛白
            btn_sec_hover = "#E2E8F0"
            btn_can_bg = "#F8FAFC"
            btn_can_border = "#CBD5E1"
            btn_can_text = "#334155"  # 深岩灰文字，清晰易辨
            btn_can_hover = "#E2E8F0"
            btn_can_hover_text = "#0F172A"
            badge_map = {
                "success": ("✓", "#DCFCE7", "#16A34A"),
                "info": ("ℹ", "#E0F2FE", "#0284C7"),
                "warning": ("⚠", "#FEF3C7", "#D97706"),
                "error": ("✕", "#FEE2E2", "#DC2626"),
                "question": ("?", "#EDE9FE", "#7C3AED")
            }

        icon_char, b_bg, b_fg = badge_map.get(dialog_type, badge_map["info"])

        # 尺寸自适应
        dialog_width = 540 if (custom_buttons and len(custom_buttons) >= 3) else 480
        self.setFixedWidth(dialog_width)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # 卡片容器
        card = QFrame()
        card.setObjectName("ModernDialogCard")
        card.setStyleSheet(f"""
            QFrame#ModernDialogCard {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 14px;
            }}
        """)

        # 浮动微阴影
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 80 if is_dark_eff else 30))
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 18, 22, 18)
        card_layout.setSpacing(14)

        # 1. Header (图标徽章 + 标题 + 关闭按钮)
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
        lbl_title.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {text_color}; border: none;")
        header.addWidget(lbl_title, 1)

        btn_x = QPushButton("✕")
        btn_x.setFixedSize(28, 28)
        btn_x.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_x.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {'#94A3B8' if is_dark_eff else '#64748B'};
                border: none;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: #EF4444;
                color: #FFFFFF;
            }}
        """)
        btn_x.clicked.connect(self.reject)
        header.addWidget(btn_x)

        card_layout.addLayout(header)

        # 2. Body Message
        # 若内容较长则开启精致滚动区，防止溢出屏幕
        needs_scroll = len(message) > 280 or message.count("\n") >= 6

        lbl_msg = QLabel(message)
        lbl_msg.setStyleSheet(f"font-size: 13px; color: {msg_color}; line-height: 1.5; border: none; font-weight: 500;")
        lbl_msg.setWordWrap(True)
        lbl_msg.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        if needs_scroll:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setMaximumHeight(260)
            scroll.setStyleSheet(f"""
                QScrollArea {{
                    background: transparent;
                    border: none;
                }}
                QScrollArea > QWidget > QWidget {{
                    background: transparent;
                }}
                {SCROLLBAR_DARK_QSS if is_dark_eff else SCROLLBAR_LIGHT_QSS}
            """)
            msg_container = QWidget()
            msg_layout = QVBoxLayout(msg_container)
            msg_layout.setContentsMargins(0, 0, 8, 0)
            msg_layout.addWidget(lbl_msg)
            scroll.setWidget(msg_container)
            card_layout.addWidget(scroll)
        else:
            card_layout.addWidget(lbl_msg)

        # 3. Action Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.setSpacing(10)

        # 按钮样式定义
        primary_btn_style = """
            QPushButton {
                background-color: #10B981;
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 8px 22px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #059669;
            }
            QPushButton:pressed {
                background-color: #047857;
            }
        """

        secondary_btn_style = f"""
            QPushButton {{
                background-color: {btn_sec_bg};
                color: {btn_sec_text};
                border: 1px solid {btn_sec_border};
                border-radius: 8px;
                padding: 8px 18px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {btn_sec_hover};
            }}
        """

        cancel_btn_style = f"""
            QPushButton {{
                background-color: {btn_can_bg};
                color: {btn_can_text};
                border: 1px solid {btn_can_border};
                border-radius: 8px;
                padding: 8px 18px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {btn_can_hover};
                color: {btn_can_hover_text};
            }}
        """

        if custom_buttons:
            for b_text, b_code, b_style in custom_buttons:
                btn = QPushButton(b_text)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setMinimumHeight(34)
                if b_style == "primary":
                    btn.setStyleSheet(primary_btn_style)
                elif b_style == "secondary":
                    btn.setStyleSheet(secondary_btn_style)
                else:
                    btn.setStyleSheet(cancel_btn_style)
                btn.clicked.connect(lambda checked=False, c=b_code: self.done(c))
                btn_row.addWidget(btn)
        elif dialog_type == "question":
            btn_c = QPushButton(cancel_text)
            btn_c.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_c.setMinimumHeight(34)
            btn_c.setStyleSheet(cancel_btn_style)
            btn_c.clicked.connect(self.reject)
            btn_row.addWidget(btn_c)

            btn_ok = QPushButton(ok_text if ok_text != "我知道了" else "确认执行")
            btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_ok.setMinimumHeight(34)
            btn_ok.setStyleSheet(primary_btn_style)
            btn_ok.clicked.connect(self.accept)
            btn_row.addWidget(btn_ok)
        else:
            btn_ok = QPushButton(ok_text)
            btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_ok.setMinimumHeight(34)
            btn_ok.setStyleSheet(primary_btn_style)
            btn_ok.clicked.connect(self.accept)
            btn_row.addWidget(btn_ok)

        card_layout.addLayout(btn_row)
        main_layout.addWidget(card)

        # DWM Rounded Frame
        try:
            apply_dm_window_frame(self, is_dark_eff)
        except Exception:
            pass

        # 智能居中于父窗口或主屏幕
        self._center_window(parent)

    def _center_window(self, parent):
        try:
            target_rect = None
            if parent and hasattr(parent, "window") and parent.window():
                p_win = parent.window()
                if p_win.isVisible() and not p_win.isMinimized():
                    target_rect = p_win.geometry()
            if not target_rect:
                screen = QGuiApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
                if screen:
                    target_rect = screen.availableGeometry()
            if target_rect:
                self.move(
                    target_rect.left() + max(0, (target_rect.width() - self.width()) // 2),
                    target_rect.top() + max(0, (target_rect.height() - self.height()) // 2)
                )
        except Exception:
            pass

    def done(self, r: int):
        grabber = QWidget.mouseGrabber()
        if grabber is not None:
            try:
                grabber.releaseMouse()
            except Exception:
                pass
        p = self.parent()
        super().done(r)
        if p is not None:
            try:
                p_win = p.window() if hasattr(p, "window") else p
                if p_win is not None:
                    p_win.activateWindow()
                    p_win.raise_()
                    p_win.setFocus()
                    if hasattr(p_win, "scroll_area") and p_win.scroll_area is not None:
                        p_win.scroll_area.setFocus()
                        if p_win.scroll_area.viewport():
                            p_win.scroll_area.viewport().update()
                        if p_win.scroll_area.widget():
                            p_win.scroll_area.widget().update()
                    p_win.update()
            except Exception:
                pass
        qApp = QApplication.instance()
        if qApp is not None:
            qApp.processEvents()

    @classmethod
    def _resolve_is_dark(cls, parent=None, is_dark: Optional[bool] = None) -> bool:
        if is_dark is not None:
            return bool(is_dark)
        if parent:
            if hasattr(parent, "is_dark_mode"):
                return bool(parent.is_dark_mode)
            if hasattr(parent, "is_dark"):
                return bool(parent.is_dark)
            p_win = parent.window() if hasattr(parent, "window") else None
            if p_win:
                if hasattr(p_win, "is_dark_mode"):
                    return bool(p_win.is_dark_mode)
                if hasattr(p_win, "is_dark"):
                    return bool(p_win.is_dark)
        try:
            from common.config_manager import get_global_theme
            return get_global_theme() == "dark"
        except Exception:
            return False

    @classmethod
    def info(cls, parent, title: str, message: str, is_dark: Optional[bool] = None, ok_text: str = "我知道了"):
        dlg = cls(parent, title, message, "info", is_dark, ok_text=ok_text)
        return dlg.exec()

    @classmethod
    def success(cls, parent, title: str, message: str, is_dark: Optional[bool] = None, ok_text: str = "我知道了"):
        dlg = cls(parent, title, message, "success", is_dark, ok_text=ok_text)
        return dlg.exec()

    @classmethod
    def warning(cls, parent, title: str, message: str, is_dark: Optional[bool] = None, ok_text: str = "我知道了"):
        dlg = cls(parent, title, message, "warning", is_dark, ok_text=ok_text)
        return dlg.exec()

    @classmethod
    def error(cls, parent, title: str, message: str, is_dark: Optional[bool] = None, ok_text: str = "我知道了"):
        dlg = cls(parent, title, message, "error", is_dark, ok_text=ok_text)
        return dlg.exec()

    @classmethod
    def confirm(cls, parent, title: str, message: str, is_dark: Optional[bool] = None, ok_text: str = "确认", cancel_text: str = "取消") -> bool:
        dlg = cls(parent, title, message, "question", is_dark, ok_text=ok_text, cancel_text=cancel_text)
        return dlg.exec() == QDialog.DialogCode.Accepted

    @classmethod
    def choice3(cls, parent, title: str, message: str, btn1_text: str, btn2_text: str, btn3_text: str = "取消", is_dark: Optional[bool] = None) -> int:
        buttons = [
            (btn3_text, 0, "cancel"),
            (btn2_text, 2, "secondary"),
            (btn1_text, 1, "primary")
        ]
        dlg = cls(parent, title, message, "question", is_dark, custom_buttons=buttons)
        return dlg.exec()
