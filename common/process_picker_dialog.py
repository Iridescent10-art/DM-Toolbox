# -*- coding: utf-8 -*-
"""任务管理器式「从运行中的进程添加游戏」对话框（多帧生成 / DLSS 5 共用）。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from common.process_scanner import list_running_processes


class RunningProcessPickerDialog(QDialog):
    """列出正在运行、带可见窗口的程序，选中后返回其可执行文件路径。"""

    def __init__(self, parent=None, is_dark: bool = True):
        super().__init__(parent)
        self.is_dark = is_dark
        self._selected_path = ""
        self._all_rows = []

        self.setWindowTitle("从运行中的进程添加游戏")
        self.resize(820, 540)

        bg = "#1e1f22" if is_dark else "#ffffff"
        fg = "#e5e7eb" if is_dark else "#111827"
        sub = "#9ca3af" if is_dark else "#4b5563"
        border = "#3f4147" if is_dark else "#d1d5db"
        sel = "#2b3a4a" if is_dark else "#dbeafe"

        self.setStyleSheet(f"""
            QDialog {{ background: {bg}; color: {fg}; }}
            QLabel {{ color: {fg}; }}
            QLineEdit {{
                background: {'#26272b' if is_dark else '#f9fafb'};
                color: {fg}; border: 1px solid {border};
                border-radius: 6px; padding: 6px 8px;
            }}
            QPushButton {{
                background: {'#2d2f34' if is_dark else '#f3f4f6'};
                color: {fg}; border: 1px solid {border};
                border-radius: 6px; padding: 7px 14px;
            }}
            QPushButton:hover {{ background: {'#3a3d44' if is_dark else '#e5e7eb'}; }}
            QTableWidget {{
                background: {'#191a1d' if is_dark else '#ffffff'};
                color: {fg}; border: 1px solid {border};
                gridline-color: {border}; selection-background-color: {sel};
            }}
            QHeaderView::section {{
                background: {'#26272b' if is_dark else '#f3f4f6'};
                color: {sub}; border: none; padding: 6px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        tip = QLabel("列出当前正在运行、且带可见窗口的程序；选中后会自动识别游戏目录并加入游戏库。")
        tip.setStyleSheet(f"color: {sub}; font-size: 12px;")
        tip.setWordWrap(True)
        layout.addWidget(tip)

        search_row = QHBoxLayout()
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("搜索进程名或路径…")
        self.edit_search.textChanged.connect(self._populate)
        search_row.addWidget(self.edit_search, 1)
        btn_refresh = QPushButton("🔄 刷新")
        btn_refresh.clicked.connect(self._reload)
        search_row.addWidget(btn_refresh)
        layout.addLayout(search_row)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["进程", "PID", "可执行文件路径"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.doubleClicked.connect(lambda *_: self._accept())
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        btn_add = QPushButton("➕ 添加选中进程")
        btn_add.setStyleSheet(
            "background:#2563eb; color:#ffffff; border:none; border-radius:6px; padding:8px 16px; font-weight:600;"
        )
        btn_add.clicked.connect(self._accept)
        btn_row.addWidget(btn_add)
        layout.addLayout(btn_row)

        self._reload()

    def _reload(self):
        try:
            self._all_rows = list_running_processes()
        except Exception:
            self._all_rows = []
        self._populate()

    def _populate(self):
        keyword = (self.edit_search.text() or "").strip().lower()
        rows = self._all_rows
        if keyword:
            rows = [r for r in rows
                    if keyword in r["name"].lower() or keyword in r["path"].lower()]
        self.table.setRowCount(0)
        for row in rows:
            idx = self.table.rowCount()
            self.table.insertRow(idx)
            name_item = QTableWidgetItem(("🟢 " if row.get("has_window") else "⚪ ") + row["name"])
            pid_item = QTableWidgetItem(str(row["pid"]))
            path_item = QTableWidgetItem(row["path"])
            path_item.setData(Qt.ItemDataRole.UserRole, row["path"])
            for col, item in enumerate((name_item, pid_item, path_item)):
                self.table.setItem(idx, col, item)

    def _accept(self):
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 2)
        if item is None:
            return
        self._selected_path = item.data(Qt.ItemDataRole.UserRole) or item.text()
        self.accept()

    def selected_path(self) -> str:
        return self._selected_path
