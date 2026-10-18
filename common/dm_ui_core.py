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
from typing import Optional, List, Dict, Any, Union

from PySide6.QtCore import (
    Qt, QPoint, QTimer, QRectF, QPointF, QEvent,
    QPropertyAnimation, QEasingCurve, Signal, QObject, QSize
)
from PySide6.QtGui import (
    QIcon, QFont, QPixmap, QColor, QPainter, QPen,
    QCursor, QGuiApplication, QRegion
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
    width: 8px;
    margin: 4px 2px 4px 0px;
    border: none;
}
QScrollBar::handle:vertical {
    background: rgba(144, 157, 181, 0.45);
    min-height: 36px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(100, 116, 145, 0.75);
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
    width: 8px;
    margin: 4px 2px 4px 0px;
    border: none;
}
QScrollBar::handle:vertical {
    background: rgba(100, 116, 139, 0.5);
    min-height: 36px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(148, 163, 184, 0.8);
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
            # 白天: #D6E6FE -> 0x00FEE6D6; 黑夜: #232B3E -> 0x003E2B23
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
                    background-color: #DBEAFE;
                    color: #2563EB;
                """)
                header.addWidget(self.lbl_badge, 0, Qt.AlignmentFlag.AlignTop)

            self.card_layout.addLayout(header)

        self.apply_theme(self.is_dark)

    def apply_theme(self, is_dark: bool):
        self.is_dark = is_dark
        bg = "#1E293B" if is_dark else "#FFFFFF"
        border = "#334155" if is_dark else "#E2E8F0"
        title_c = "#F8FAFC" if is_dark else "#1E293B"
        sub_c = "#94A3B8" if is_dark else "#64748B"

        self.setStyleSheet(f"""
            QFrame#DMCardFrame {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 14px;
            }}
            QFrame#DMCardFrame:hover {{
                border: 1px solid {'#3B82F6' if is_dark else '#2563EB'};
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
                bg = QColor("#334155") if self.is_dark_mode else QColor("#CBD5E1")
                painter.fillRect(self.rect(), bg)
            elif self.is_hovered:
                bg = QColor("#1E293B") if self.is_dark_mode else QColor("#E2E8F0")
                painter.fillRect(self.rect(), bg)

        # Icon color
        if self.btn_type == DMCaptionButtonType.CLOSE and self.is_hovered:
            icon_color = QColor("#FFFFFF")
        else:
            icon_color = QColor("#CBD5E1") if self.is_dark_mode else QColor("#475569")

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
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
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
        self.btn_theme = QPushButton("🌙 黑夜模式" if not self.is_dark_mode else "☀️ 白天模式")
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
        bg = "#14171F" if self.is_dark_mode else "#F4F6F9"
        border = "#232B3E" if self.is_dark_mode else "#D6E6FE"
        tb_bg = "#1A1D26" if self.is_dark_mode else "#FFFFFF"
        tb_border = "#282E3D" if self.is_dark_mode else "#E8EEF5"
        text_color = "#F8FAFC" if self.is_dark_mode else "#1E293B"

        # Synchronize application palette to prevent OS dark palette bleedthrough
        app = QApplication.instance()
        if app:
            from PySide6.QtGui import QPalette
            pal = QPalette()
            if self.is_dark_mode:
                pal.setColor(QPalette.ColorRole.Window, QColor("#14171F"))
                pal.setColor(QPalette.ColorRole.WindowText, QColor("#F8FAFC"))
                pal.setColor(QPalette.ColorRole.Base, QColor("#1E293B"))
                pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#14171F"))
                pal.setColor(QPalette.ColorRole.Text, QColor("#F8FAFC"))
            else:
                pal.setColor(QPalette.ColorRole.Window, QColor("#F4F6F9"))
                pal.setColor(QPalette.ColorRole.WindowText, QColor("#1E293B"))
                pal.setColor(QPalette.ColorRole.Base, QColor("#FFFFFF"))
                pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#F1F5F9"))
                pal.setColor(QPalette.ColorRole.Text, QColor("#1E293B"))
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
                    border: 1px solid {border};
                    border-radius: 14px;
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
        self.btn_theme.setText("☀️ 白天模式" if self.is_dark_mode else "🌙 黑夜模式")
        pill_bg = "#232B3E" if self.is_dark_mode else "#F1F5F9"
        pill_fg = "#CBD5E1" if self.is_dark_mode else "#475569"
        pill_border = "#334155" if self.is_dark_mode else "#E2E8F0"
        self.btn_theme.setStyleSheet(f"""
            QPushButton#ThemeToggleBtn {{
                background-color: {pill_bg};
                color: {pill_fg};
                border: 1px solid {pill_border};
                border-radius: 12px;
                padding: 4px 14px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton#ThemeToggleBtn:hover {{
                background-color: {'#334155' if self.is_dark_mode else '#E2E8F0'};
                color: {'#F8FAFC' if self.is_dark_mode else '#1E293B'};
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
