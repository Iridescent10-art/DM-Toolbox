# -*- coding: utf-8 -*-
"""
DM-Toolbox - Cloud Application Updater & GitHub Release Manager.
Provides checking for updates, selecting releases, background silent checks on startup,
downloading installers with mirror acceleration, and launching the setup wizard.
"""

import os
import sys
import time
import json
import re
import urllib.request
import urllib.error
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Callable

from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QIcon, QPixmap, QFont, QColor
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QTextBrowser, QProgressBar,
    QCheckBox, QFrame, QSizePolicy, QApplication
)

from common.version import (
    APP_NAME, APP_VERSION, GITHUB_OWNER, GITHUB_REPO,
    GITHUB_API_RELEASES, GITHUB_WEB_RELEASES
)
from common.config_manager import CONFIG_ROOT, CACHE_ROOT, get_global_theme
from common.ui_theme import ModernDialog

UPDATER_CONFIG_FILE = CONFIG_ROOT / "updater.json"


def get_updater_config() -> Dict[str, Any]:
    """Load updater preferences, defaults to auto_check=True, use_mirror=True."""
    defaults = {
        "auto_check": True,
        "use_mirror": True,
        "last_checked_tag": "",
        "last_check_time": 0
    }
    if UPDATER_CONFIG_FILE.exists():
        try:
            with open(UPDATER_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    defaults.update(data)
        except Exception:
            pass
    return defaults


def save_updater_config(cfg: Dict[str, Any]) -> bool:
    """Save updater preferences."""
    try:
        UPDATER_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(UPDATER_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def parse_version_tuple(v_str: str) -> Tuple[int, ...]:
    """Parse version string like 'v1.2.10' or '1.2.10.0' into comparable tuple of ints."""
    clean = re.sub(r'^[vV]', '', str(v_str).strip())
    parts = []
    for p in clean.split('.'):
        m = re.match(r'^\d+', p)
        if m:
            parts.append(int(m.group(0)))
        else:
            break
    return tuple(parts) if parts else (0, 0, 0)


def markdown_to_html(md_text: str, is_dark: bool = False) -> str:
    """Converts release note markdown syntax into clean styled HTML."""
    if not md_text:
        return "<p style='color: #888;'>暂无版本更新说明</p>"

    text = md_text.replace("\r\n", "\n")
    lines = text.split("\n")
    html_lines = []

    text_color = "#E5E5E5" if is_dark else "#2A2B2C"
    h_color = "#8FE3B0" if is_dark else "#16A34A"
    sub_color = "#94A3B8" if is_dark else "#64748B"
    code_bg = "#2D3748" if is_dark else "#F1F5F9"

    for line in lines:
        s = line.strip()
        if not s:
            html_lines.append("<div style='height: 6px;'></div>")
            continue

        # Headers
        if s.startswith("### "):
            html_lines.append(f"<h3 style='margin: 8px 0 4px 0; font-size: 14px; font-weight: 700; color: {h_color};'>{s[4:]}</h3>")
            continue
        elif s.startswith("## "):
            html_lines.append(f"<h2 style='margin: 10px 0 6px 0; font-size: 15px; font-weight: 800; color: {h_color};'>{s[3:]}</h2>")
            continue
        elif s.startswith("# "):
            html_lines.append(f"<h1 style='margin: 12px 0 8px 0; font-size: 16px; font-weight: 800; color: {h_color};'>{s[2:]}</h1>")
            continue

        # Blockquote
        if s.startswith("> "):
            html_lines.append(f"<blockquote style='margin: 4px 0; padding-left: 10px; border-left: 3px solid {h_color}; color: {sub_color}; font-size: 12px;'>{s[2:]}</blockquote>")
            continue

        # Horizontal rule
        if s in ("---", "***", "___"):
            border_color = "#3A3A3A" if is_dark else "#E5E5E5"
            html_lines.append(f"<hr style='border: none; border-top: 1px solid {border_color}; margin: 8px 0;'/>")
            continue

        # Bullet list
        if s.startswith("- ") or s.startswith("* "):
            content = s[2:]
            content = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', content)
            content = re.sub(r'`(.+?)`', rf'<code style="background-color: {code_bg}; padding: 1px 4px; border-radius: 4px; font-family: Consolas, monospace;">\1</code>', content)
            html_lines.append(f"<div style='margin: 3px 0; padding-left: 14px; color: {text_color}; font-size: 12.5px; line-height: 1.5;'>• {content}</div>")
            continue

        # Numbered list
        m_num = re.match(r'^(\d+)\.\s+(.*)', s)
        if m_num:
            num = m_num.group(1)
            content = m_num.group(2)
            content = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', content)
            content = re.sub(r'`(.+?)`', rf'<code style="background-color: {code_bg}; padding: 1px 4px; border-radius: 4px; font-family: Consolas, monospace;">\1</code>', content)
            html_lines.append(f"<div style='margin: 3px 0; padding-left: 14px; color: {text_color}; font-size: 12.5px; line-height: 1.5;'><b>{num}.</b> {content}</div>")
            continue

        # Normal text with bold and inline code
        content = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)
        content = re.sub(r'`(.+?)`', rf'<code style="background-color: {code_bg}; padding: 1px 4px; border-radius: 4px; font-family: Consolas, monospace;">\1</code>', content)
        html_lines.append(f"<p style='margin: 3px 0; color: {text_color}; font-size: 12.5px; line-height: 1.5;'>{content}</p>")

    return "".join(html_lines)


class CheckUpdateWorker(QThread):
    """Asynchronous background worker to check GitHub Releases without blocking UI."""
    finished = Signal(bool, list, str)

    def run(self):
        urls = [
            GITHUB_API_RELEASES,
            f"https://ghproxy.net/{GITHUB_API_RELEASES}"
        ]
        headers = {
            "User-Agent": "DM-Toolbox-Updater",
            "Accept": "application/vnd.github.v3+json"
        }

        last_err = ""
        for url in urls:
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        if isinstance(data, list) and len(data) > 0:
                            self.finished.emit(True, data, "")
                            return
            except urllib.error.HTTPError as e:
                last_err = f"HTTP {e.code}: {e.reason}"
            except Exception as e:
                last_err = str(e)

        self.finished.emit(False, [], last_err or "网络连接超时，无法访问 GitHub 接口")


class DownloadInstallerWorker(QThread):
    """Asynchronous background worker for downloading DM-BOX installer with speed & progress reporting."""
    progress = Signal(int, int, float)  # downloaded, total, speed_bytes_per_sec
    finished = Signal(bool, str, str)   # success, output_path, error_msg

    def __init__(self, download_url: str, dest_path: str, use_mirror: bool = True):
        super().__init__()
        self.download_url = download_url
        self.dest_path = dest_path
        self.use_mirror = use_mirror
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        target_url = self.download_url
        if self.use_mirror:
            if not target_url.startswith("https://ghproxy.net/"):
                target_url = f"https://ghproxy.net/{target_url}"

        dest_file = Path(self.dest_path)
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        temp_file = dest_file.with_suffix(".tmp")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        try:
            req = urllib.request.Request(target_url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp, open(temp_file, "wb") as f_out:
                content_len = resp.headers.get("Content-Length")
                total_bytes = int(content_len) if content_len and content_len.isdigit() else 0

                downloaded = 0
                last_time = time.time()
                last_downloaded = 0

                while True:
                    if self._is_cancelled:
                        f_out.close()
                        if temp_file.exists():
                            try:
                                temp_file.unlink()
                            except Exception:
                                pass
                        self.finished.emit(False, "", "用户已取消下载")
                        return

                    chunk = resp.read(65536)
                    if not chunk:
                        break

                    f_out.write(chunk)
                    downloaded += len(chunk)

                    now = time.time()
                    elapsed = now - last_time
                    if elapsed >= 0.25:
                        speed = (downloaded - last_downloaded) / elapsed
                        self.progress.emit(downloaded, total_bytes, speed)
                        last_time = now
                        last_downloaded = downloaded

            # Completed download
            if temp_file.exists():
                if dest_file.exists():
                    try:
                        dest_file.unlink()
                    except Exception:
                        pass
                temp_file.rename(dest_file)

            self.finished.emit(True, str(dest_file), "")
        except Exception as e:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass
            self.finished.emit(False, "", f"下载中断: {e}")


class AppUpdateDialog(QDialog):
    """
    Modern Fluent Dialog for DM-Toolbox Application Updates.
    Allows viewing all GitHub releases, selecting any target release, and downloading/updating.
    """
    def __init__(self, parent=None, is_dark: Optional[bool] = None, preloaded_releases: Optional[List[Dict[str, Any]]] = None):
        super().__init__(parent)
        if is_dark is None:
            self.is_dark = (get_global_theme() == "dark")
        else:
            self.is_dark = is_dark

        self.setWindowTitle("DM工具箱 - 软件更新")
        self.setFixedSize(680, 580)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)

        self.updater_cfg = get_updater_config()
        self.releases_data: List[Dict[str, Any]] = preloaded_releases or []
        self.selected_release: Optional[Dict[str, Any]] = None
        self.selected_asset: Optional[Dict[str, Any]] = None

        self.download_worker: Optional[DownloadInstallerWorker] = None
        self.downloaded_installer_path: Optional[str] = None

        self._init_ui()
        self._apply_style()

        if self.releases_data:
            self._on_releases_fetched(True, self.releases_data, "")
        else:
            self._start_fetch_releases()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 18, 20, 18)
        main_layout.setSpacing(14)

        # 1. Header Card (App Icon, Title, Current Version)
        h_card = QFrame()
        h_card.setObjectName("HeaderCard")
        h_layout = QHBoxLayout(h_card)
        h_layout.setContentsMargins(14, 12, 14, 12)
        h_layout.setSpacing(12)

        icon_lbl = QLabel()
        icon_lbl.setFixedSize(42, 42)
        app_icon_p = Path(__file__).resolve().parent / "assets" / "app_icon.png"
        if app_icon_p.exists():
            icon_lbl.setPixmap(QPixmap(str(app_icon_p)).scaled(42, 42, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        h_layout.addWidget(icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        lbl_app_name = QLabel(f"{APP_NAME} · 软件在线更新")
        lbl_app_name.setStyleSheet("font-size: 16px; font-weight: 800;")
        self.lbl_current_ver = QLabel(f"当前安装版本: v{APP_VERSION}")
        self.lbl_current_ver.setStyleSheet("font-size: 12px; color: #94A3B8;")
        title_vbox.addWidget(lbl_app_name)
        title_vbox.addWidget(self.lbl_current_ver)
        h_layout.addLayout(title_vbox, 1)

        # Status badge
        self.badge_status = QLabel("⏳ 正在检查最新版本...")
        self.badge_status.setStyleSheet("font-size: 12px; font-weight: 700; padding: 4px 10px; border-radius: 8px;")
        h_layout.addWidget(self.badge_status)
        main_layout.addWidget(h_card)

        # 2. Release Selection Row
        ver_row = QHBoxLayout()
        ver_row.setSpacing(10)
        lbl_sel = QLabel("选择更新版本:")
        lbl_sel.setStyleSheet("font-size: 13px; font-weight: 700;")
        lbl_sel.setFixedWidth(95)
        ver_row.addWidget(lbl_sel)

        self.combo_versions = QComboBox()
        self.combo_versions.setMinimumHeight(34)
        self.combo_versions.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.combo_versions.currentIndexChanged.connect(self._on_version_selected)
        ver_row.addWidget(self.combo_versions, 1)

        self.btn_refresh = QPushButton("🔄 重新检查")
        self.btn_refresh.setMinimumHeight(34)
        self.btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh.clicked.connect(self._start_fetch_releases)
        ver_row.addWidget(self.btn_refresh)

        main_layout.addLayout(ver_row)

        # 3. Release Metadata Row (Date & Size)
        self.meta_box = QHBoxLayout()
        self.lbl_rel_date = QLabel("发布时间: --")
        self.lbl_rel_size = QLabel("安装包大小: --")
        self.meta_box.addWidget(self.lbl_rel_date)
        self.meta_box.addSpacing(20)
        self.meta_box.addWidget(self.lbl_rel_size)
        self.meta_box.addStretch()
        main_layout.addLayout(self.meta_box)

        # 4. Changelog Text Area
        lbl_notes = QLabel("📝 版本更新日志与特性:")
        lbl_notes.setStyleSheet("font-size: 12.5px; font-weight: 700;")
        main_layout.addWidget(lbl_notes)

        self.text_notes = QTextBrowser()
        self.text_notes.setOpenExternalLinks(True)
        self.text_notes.setMinimumHeight(160)
        main_layout.addWidget(self.text_notes, 1)

        # 5. Mirror & Auto-check Options Row
        opt_row = QHBoxLayout()
        self.chk_mirror = QCheckBox("🚀 启用国内高速镜像加速下载 (GHProxy)")
        self.chk_mirror.setChecked(self.updater_cfg.get("use_mirror", True))
        self.chk_mirror.setStyleSheet("font-size: 12px; font-weight: 600;")
        self.chk_mirror.stateChanged.connect(self._save_options)
        opt_row.addWidget(self.chk_mirror)

        opt_row.addSpacing(16)

        self.chk_auto_check = QCheckBox("🔔 每次开启软件自动在后台检查更新")
        self.chk_auto_check.setChecked(self.updater_cfg.get("auto_check", True))
        self.chk_auto_check.setStyleSheet("font-size: 12px; font-weight: 600;")
        self.chk_auto_check.stateChanged.connect(self._save_options)
        opt_row.addWidget(self.chk_auto_check)

        opt_row.addStretch()
        main_layout.addLayout(opt_row)

        # 6. Download Progress Bar Area (Hidden by default)
        self.progress_frame = QFrame()
        self.progress_frame.setVisible(False)
        p_layout = QVBoxLayout(self.progress_frame)
        p_layout.setContentsMargins(0, 4, 0, 4)
        p_layout.setSpacing(6)

        self.lbl_progress = QLabel("准备下载...")
        self.lbl_progress.setStyleSheet("font-size: 12px; font-weight: 600;")
        p_layout.addWidget(self.lbl_progress)

        self.bar_download = QProgressBar()
        self.bar_download.setRange(0, 100)
        self.bar_download.setValue(0)
        self.bar_download.setMinimumHeight(14)
        self.bar_download.setTextVisible(False)
        p_layout.addWidget(self.bar_download)
        main_layout.addWidget(self.progress_frame)

        # 7. Bottom Action Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_web = QPushButton("🌐 前往 GitHub Release 网页")
        self.btn_web.setMinimumHeight(36)
        self.btn_web.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_web.clicked.connect(self._open_web_releases)
        btn_row.addWidget(self.btn_web)

        btn_row.addStretch()

        self.btn_download = QPushButton("⚡ 立即下载并安装更新")
        self.btn_download.setMinimumHeight(36)
        self.btn_download.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_download.clicked.connect(self._start_download)
        btn_row.addWidget(self.btn_download)

        self.btn_close = QPushButton("关闭")
        self.btn_close.setMinimumHeight(36)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.clicked.connect(self._on_close_clicked)
        btn_row.addWidget(self.btn_close)

        main_layout.addLayout(btn_row)

    def _save_options(self):
        self.updater_cfg["use_mirror"] = self.chk_mirror.isChecked()
        self.updater_cfg["auto_check"] = self.chk_auto_check.isChecked()
        save_updater_config(self.updater_cfg)

    def _apply_style(self):
        if self.is_dark:
            bg_color = "#202124"
            card_bg = "#292A2D"
            card_border = "#3C4043"
            text_color = "#E8EAED"
            sub_color = "#9AA0A6"
            accent_green = "#8FE3B0"
            btn_text = "#10231A"
            input_bg = "#303134"
            border_color = "#3C4043"
            self.badge_status.setStyleSheet("color: #8FE3B0; background-color: #1E3A2F; padding: 4px 10px; border-radius: 8px; font-size: 12px; font-weight: 700;")
        else:
            bg_color = "#F8F9FA"
            card_bg = "#FFFFFF"
            card_border = "#E5E7EB"
            text_color = "#1F2937"
            sub_color = "#6B7280"
            accent_green = "#16A34A"
            btn_text = "#FFFFFF"
            input_bg = "#FFFFFF"
            border_color = "#D1D5DB"
            self.badge_status.setStyleSheet("color: #16A34A; background-color: #DCFCE7; padding: 4px 10px; border-radius: 8px; font-size: 12px; font-weight: 700;")

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
                color: {text_color};
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            }}
            QFrame#HeaderCard {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 10px;
            }}
            QLabel {{
                color: {text_color};
            }}
            QComboBox {{
                background-color: {input_bg};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 8px;
                padding: 4px 12px;
                font-size: 13px;
                font-weight: 600;
            }}
            QComboBox QAbstractItemView {{
                background-color: {card_bg};
                color: {text_color};
                border: 1px solid {card_border};
                selection-background-color: {'#374151' if self.is_dark else '#E5E7EB'};
                selection-color: {text_color};
            }}
            QTextBrowser {{
                background-color: {card_bg};
                color: {text_color};
                border: 1px solid {card_border};
                border-radius: 10px;
                padding: 10px;
            }}
            QPushButton {{
                background-color: {'#374151' if self.is_dark else '#F3F4F6'};
                color: {text_color};
                border: 1px solid {card_border};
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {'#4B5563' if self.is_dark else '#E5E7EB'};
            }}
            QProgressBar {{
                background-color: {'#374151' if self.is_dark else '#E5E7EB'};
                border: none;
                border-radius: 7px;
            }}
            QProgressBar::chunk {{
                background-color: {accent_green};
                border-radius: 7px;
            }}
        """)

        # Highlight primary download button
        self.btn_download.setStyleSheet(f"""
            QPushButton {{
                background-color: {accent_green};
                color: {btn_text};
                border: none;
                border-radius: 8px;
                padding: 6px 18px;
                font-size: 13px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {'#7ADCA0' if self.is_dark else '#15803D'};
            }}
            QPushButton:disabled {{
                background-color: {'#4B5563' if self.is_dark else '#D1D5DB'};
                color: {'#9CA3AF' if self.is_dark else '#9CA3AF'};
            }}
        """)

    def _start_fetch_releases(self):
        self.badge_status.setText("⏳ 正在获取 GitHub 版本列表...")
        self.btn_refresh.setEnabled(False)
        self.btn_download.setEnabled(False)
        self.combo_versions.clear()
        self.text_notes.setHtml("<p style='color: #888; font-size: 13px;'>正在连接 GitHub 检查版本更新，请稍候...</p>")

        self.check_worker = CheckUpdateWorker()
        self.check_worker.finished.connect(self._on_releases_fetched)
        self.check_worker.start()

    def _on_releases_fetched(self, success: bool, releases: list, err: str):
        self.btn_refresh.setEnabled(True)
        if not success or not releases:
            self.badge_status.setText("❌ 获取失败")
            if self.is_dark:
                self.badge_status.setStyleSheet("color: #F87171; background-color: #3B1C1C; padding: 4px 10px; border-radius: 8px;")
            else:
                self.badge_status.setStyleSheet("color: #DC2626; background-color: #FEE2E2; padding: 4px 10px; border-radius: 8px;")
            self.text_notes.setHtml(f"<p style='color: #EF4444;'><b>检查更新失败:</b> {err}</p><p>您可以点击下方按钮直接前往 GitHub 官方 Releases 网页手动下载。</p>")
            return

        self.releases_data = releases
        self.combo_versions.blockSignals(True)
        self.combo_versions.clear()

        curr_tuple = parse_version_tuple(APP_VERSION)
        latest_rel = releases[0]
        latest_tag = latest_rel.get("tag_name", "")
        latest_tuple = parse_version_tuple(latest_tag)

        # Populate versions dropdown
        for idx, rel in enumerate(releases):
            tag = rel.get("tag_name", "")
            title = rel.get("name", tag)
            is_latest = (idx == 0)
            tag_display = f"{tag} (最新)" if is_latest else tag
            self.combo_versions.addItem(f"{tag_display} · {title}", rel)

        self.combo_versions.blockSignals(False)

        # Determine update status
        if latest_tuple > curr_tuple:
            self.badge_status.setText(f"🚀 发现新版本: {latest_tag}")
            if self.is_dark:
                self.badge_status.setStyleSheet("color: #60A5FA; background-color: #1E293B; padding: 4px 10px; border-radius: 8px; font-weight: 700;")
            else:
                self.badge_status.setStyleSheet("color: #2563EB; background-color: #DBEAFE; padding: 4px 10px; border-radius: 8px; font-weight: 700;")
            self.btn_download.setText(f"⚡ 立即下载并升级到 {latest_tag}")
        else:
            self.badge_status.setText(f"🟢 已是最新版本 ({latest_tag})")
            if self.is_dark:
                self.badge_status.setStyleSheet("color: #8FE3B0; background-color: #1E3A2F; padding: 4px 10px; border-radius: 8px; font-weight: 700;")
            else:
                self.badge_status.setStyleSheet("color: #16A34A; background-color: #DCFCE7; padding: 4px 10px; border-radius: 8px; font-weight: 700;")
            self.btn_download.setText(f"🔄 重新下载安装该版本")

        # Select top release
        self.combo_versions.setCurrentIndex(0)
        self._on_version_selected(0)

    def _on_version_selected(self, index: int):
        if index < 0 or index >= len(self.releases_data):
            return

        rel = self.releases_data[index]
        self.selected_release = rel

        tag = rel.get("tag_name", "")
        published_at = rel.get("published_at", "")[:16].replace("T", " ")
        self.lbl_rel_date.setText(f"发布时间: <b>{published_at}</b>")

        # Find executable installer asset
        assets = rel.get("assets", [])
        installer_asset = None
        for a in assets:
            a_name = a.get("name", "").lower()
            if a_name.endswith(".exe") and "dm" in a_name:
                installer_asset = a
                break
        if not installer_asset and assets:
            for a in assets:
                if a.get("name", "").lower().endswith(".exe"):
                    installer_asset = a
                    break

        self.selected_asset = installer_asset
        if installer_asset:
            mb = installer_asset.get("size", 0) / (1024 * 1024)
            self.lbl_rel_size.setText(f"安装包: <b>{installer_asset.get('name')}</b> ({mb:.2f} MB)")
            self.btn_download.setEnabled(True)
        else:
            self.lbl_rel_size.setText("安装包: <i>(未上传安装包资产)</i>")
            self.btn_download.setEnabled(False)

        # Render release notes
        body = rel.get("body", "")
        html = markdown_to_html(body, self.is_dark)
        self.text_notes.setHtml(html)

        # Update button text based on selection vs installed
        rel_tuple = parse_version_tuple(tag)
        curr_tuple = parse_version_tuple(APP_VERSION)
        if rel_tuple > curr_tuple:
            self.btn_download.setText(f"⚡ 立即下载并升级到 {tag}")
        elif rel_tuple == curr_tuple:
            self.btn_download.setText(f"🔄 重新下载安装 v{APP_VERSION}")
        else:
            self.btn_download.setText(f"⚠️ 下载回退至旧版本 {tag}")

    def _start_download(self):
        if not self.selected_asset:
            ModernDialog.warning(self, "无法下载", "选中的发布版本中未找到可执行安装包 (DM-BOX.exe)。")
            return

        download_url = self.selected_asset.get("browser_download_url", "")
        if not download_url:
            ModernDialog.warning(self, "无法下载", "未获取到下载链接。")
            return

        tag = self.selected_release.get("tag_name", "latest")
        target_dir = Path(CACHE_ROOT) / "updates"
        target_dir.mkdir(parents=True, exist_ok=True)
        dest_path = str(target_dir / f"DM-BOX-{tag}.exe")

        # Switch UI to downloading state
        self.progress_frame.setVisible(True)
        self.bar_download.setValue(0)
        self.lbl_progress.setText("正在连接下载服务器...")
        self.btn_download.setEnabled(False)
        self.btn_refresh.setEnabled(False)
        self.combo_versions.setEnabled(False)
        self.btn_close.setText("取消下载")

        use_mirror = self.chk_mirror.isChecked()
        self.download_worker = DownloadInstallerWorker(download_url, dest_path, use_mirror=use_mirror)
        self.download_worker.progress.connect(self._on_download_progress)
        self.download_worker.finished.connect(self._on_download_finished)
        self.download_worker.start()

    def _on_download_progress(self, downloaded: int, total: int, speed: float):
        if total > 0:
            pct = int((downloaded / total) * 100)
            self.bar_download.setValue(pct)
            dl_mb = downloaded / (1024 * 1024)
            tot_mb = total / (1024 * 1024)
            spd_mb = speed / (1024 * 1024)
            self.lbl_progress.setText(f"正在下载: <b>{dl_mb:.1f} MB / {tot_mb:.1f} MB</b> ({pct}%) · 速度: <b>{spd_mb:.2f} MB/s</b>")
        else:
            dl_mb = downloaded / (1024 * 1024)
            self.lbl_progress.setText(f"正在下载: <b>{dl_mb:.1f} MB</b>")

    def _on_download_finished(self, success: bool, file_path: str, err: str):
        self.btn_download.setEnabled(True)
        self.btn_refresh.setEnabled(True)
        self.combo_versions.setEnabled(True)
        self.btn_close.setText("关闭")

        if not success:
            self.lbl_progress.setText(f"<span style='color: #EF4444;'>下载失败: {err}</span>")
            ModernDialog.warning(self, "下载失败", f"更新安装包下载中断:\n{err}\n\n建议尝试切换『国内网络镜像加速下载』选项后重试。")
            return

        self.lbl_progress.setText("✅ 下载完成！校验通过。")
        self.bar_download.setValue(100)
        self.downloaded_installer_path = file_path

        # Prompt user to launch installer
        confirm = ModernDialog.confirm(
            parent=self,
            title="更新已就绪",
            message="DM工具箱 最新版本安装包已下载完成！\n\n是否立即启动安装向导以完成覆盖更新？",
            bullet_items=[
                f"安装包路径: {file_path}",
                "启动安装向导后，当前 DM工具箱 将自动退出以释放所有文件占用",
                "您的个人设置与扫描缓存将 100% 自动无损保留"
            ],
            confirm_text="立即安装更新",
            cancel_text="稍后手动安装",
            icon_type="info"
        )

        if confirm:
            try:
                # Launch installer detached
                CREATE_NEW_PROCESS_GROUP = 0x00000200
                DETACHED_PROCESS = 0x00000008
                creation_flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
                subprocess.Popen([file_path], creationflags=creation_flags)
                # Quit current app completely
                QApplication.quit()
                sys.exit(0)
            except Exception as e:
                ModernDialog.warning(self, "启动安装向导失败", f"无法自动启动安装程序:\n{e}\n\n请手动双击运行该文件:\n{file_path}")

    def _on_close_clicked(self):
        if self.download_worker and self.download_worker.isRunning():
            self.download_worker.cancel()
            self.download_worker.wait(1500)
        self.close()

    def _open_web_releases(self):
        import webbrowser
        target_url = GITHUB_WEB_RELEASES
        if self.selected_release and self.selected_release.get("html_url"):
            target_url = self.selected_release["html_url"]
        webbrowser.open(target_url)


def show_update_dialog(parent=None, preloaded_releases: Optional[List[Dict[str, Any]]] = None) -> None:
    """Convenience helper to show the update dialog modally."""
    dlg = AppUpdateDialog(parent=parent, preloaded_releases=preloaded_releases)
    dlg.exec()


class SilentUpdateChecker:
    """
    Non-blocking silent update checker for software startup.
    Runs silently in the background and calls callback only when a newer release is found.
    """
    def __init__(self, callback_on_update_found: Callable[[str, List[Dict[str, Any]]], None]):
        self.callback = callback_on_update_found
        self.worker: Optional[CheckUpdateWorker] = None

    def start_check(self):
        cfg = get_updater_config()
        if not cfg.get("auto_check", True):
            return

        self.worker = CheckUpdateWorker()
        self.worker.finished.connect(self._on_check_finished)
        self.worker.start()

    def _on_check_finished(self, success: bool, releases: list, err: str):
        if not success or not releases:
            return

        latest_rel = releases[0]
        latest_tag = latest_rel.get("tag_name", "")
        if parse_version_tuple(latest_tag) > parse_version_tuple(APP_VERSION):
            try:
                self.callback(latest_tag, releases)
            except Exception:
                pass
