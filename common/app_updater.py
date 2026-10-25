# -*- coding: utf-8 -*-
"""
DM-Toolbox - Cloud Application Updater & GitHub Release Manager.
Provides checking for updates, selecting releases, background silent checks on startup,
intelligent multi-source mirror speed testing with auto-selection, automatic failover
during downloads, safe cancellation handling to prevent crashes, and launching the setup wizard.
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
from typing import Optional, List, Dict, Any, Tuple, Callable, Union

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

MIRROR_SOURCES = [
    {
        "id": "auto",
        "name": "⚡ 智能测速优选 (推荐 · 自动检测并选用最快节点)",
        "prefix": ""
    },
    {
        "id": "ghproxy_com",
        "name": "🚀 GH-Proxy 节点 (国内高速 CDN 加速)",
        "prefix": "https://gh-proxy.com/"
    },
    {
        "id": "ghfast",
        "name": "⚡ GHFast 节点 (国内高速镜像备用)",
        "prefix": "https://ghfast.top/"
    },
    {
        "id": "ghproxy_net",
        "name": "🌐 GHProxy 节点 (公共镜像源)",
        "prefix": "https://ghproxy.net/"
    },
    {
        "id": "direct",
        "name": "🔗 GitHub 官方直连 (适合已开启科学上网 / 全局代理)",
        "prefix": ""
    }
]


def get_updater_config() -> Dict[str, Any]:
    """Load updater preferences, defaults to auto_check=True, mirror_id='auto'."""
    defaults = {
        "auto_check": True,
        "mirror_id": "auto",
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
                    # Legacy migration: if older config had 'ghproxy' or 'ghproxy_net', recommend 'auto'
                    if defaults.get("mirror_id") in ("ghproxy", "ghproxy_net"):
                        defaults["mirror_id"] = "auto"
                    elif "use_mirror" in data and "mirror_id" not in data:
                        defaults["mirror_id"] = "auto" if data.get("use_mirror", True) else "direct"
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
    """Parse version string like 'v1.2.12' or '1.2.12.0' into comparable tuple of ints."""
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
    """Asynchronous background worker to check GitHub Releases with multi-source fallback."""
    finished = Signal(bool, list, str)

    def __init__(self):
        super().__init__()
        self._cancelled = False

    def cancel(self):
        """Stop before the next mirror attempt; used when the app shuts down."""
        self._cancelled = True

    def run(self):
        urls = [
            GITHUB_API_RELEASES,
            f"https://gh-proxy.com/{GITHUB_API_RELEASES}",
            f"https://ghfast.top/{GITHUB_API_RELEASES}",
            f"https://ghproxy.net/{GITHUB_API_RELEASES}"
        ]
        headers = {
            "User-Agent": "DM-Toolbox-Updater",
            "Accept": "application/vnd.github.v3+json"
        }

        last_err = ""
        for url in urls:
            if self._cancelled:
                return
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=8) as resp:
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


class MirrorSpeedTestWorker(QThread):
    """
    Asynchronously measures ping latency & availability to all candidate mirror sources concurrently.
    Emits node_tested(mirror_id, latency_ms, ok) and finished(results_dict, best_mirror_id).
    """
    node_tested = Signal(str, int, bool)
    finished = Signal(dict, str)

    def __init__(self, mirrors: List[Dict[str, Any]], test_asset_url: str):
        super().__init__()
        self.mirrors = mirrors
        self.test_asset_url = test_asset_url
        self._is_cancelled = False
        self._active_resps = []

    def cancel(self):
        self._is_cancelled = True
        for r in getattr(self, "_active_resps", []):
            try:
                r.close()
            except Exception:
                pass

    def run(self):
        from concurrent.futures import ThreadPoolExecutor, as_completed
        results = {}

        def _test_single(m):
            if self._is_cancelled:
                return m["id"], -1, False
            prefix = m["prefix"]
            url = f"{prefix}{self.test_asset_url}" if prefix else self.test_asset_url
            t0 = time.time()
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Range": "bytes=0-100"}
            )
            try:
                with urllib.request.urlopen(req, timeout=2.2) as resp:
                    self._active_resps.append(resp)
                    if resp.status in (200, 206):
                        lat = int((time.time() - t0) * 1000)
                        return m["id"], lat, True
            except Exception:
                pass
            return m["id"], -1, False

        testable = [m for m in self.mirrors if m["id"] != "auto"]
        executor = ThreadPoolExecutor(max_workers=min(len(testable), 6))
        try:
            future_to_mirror = {executor.submit(_test_single, m): m for m in testable}
            for fut in as_completed(future_to_mirror):
                if self._is_cancelled:
                    break
                try:
                    m_id, lat, ok = fut.result()
                    results[m_id] = {"latency": lat, "ok": ok}
                    self.node_tested.emit(m_id, lat, ok)
                except Exception:
                    pass
        finally:
            executor.shutdown(wait=False)

        # Determine best mirror (lowest latency among ok=True)
        best_id = "ghproxy_com"
        best_lat = 999999
        for m_id, data in results.items():
            if data["ok"] and 0 <= data["latency"] < best_lat:
                best_lat = data["latency"]
                best_id = m_id

        if not self._is_cancelled:
            self.finished.emit(results, best_id)


class DownloadInstallerWorker(QThread):
    """
    Asynchronous background worker for downloading DM-BOX installer with speed & progress reporting.
    Supports candidate download URLs with automatic seamless failover to fallback mirrors.
    """
    progress = Signal(int, int, float)  # downloaded, total, speed_bytes_per_sec
    status_msg = Signal(str)            # status text updates (e.g. automatic failover notifications)
    finished = Signal(bool, str, str)   # success, output_path, error_msg

    def __init__(self, candidate_urls: Any, dest_path: str, mirror_prefix: str = ""):
        super().__init__()
        if isinstance(candidate_urls, str):
            if mirror_prefix:
                p = mirror_prefix.rstrip('/')
                u = candidate_urls.lstrip('/')
                self.candidate_urls = [f"{p}/{u}"]
            else:
                self.candidate_urls = [candidate_urls]
        else:
            self.candidate_urls = list(candidate_urls)

        self.dest_path = dest_path
        self._is_cancelled = False
        self._active_resp = None

    def cancel(self):
        self._is_cancelled = True
        if self._active_resp:
            try:
                self._active_resp.close()
            except Exception:
                pass

    def run(self):
        dest_file = Path(self.dest_path)
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        temp_file = dest_file.with_suffix(".tmp")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        last_err = ""
        total_candidates = len(self.candidate_urls)

        for idx, target_url in enumerate(self.candidate_urls):
            if self._is_cancelled:
                self.finished.emit(False, "", "用户已取消下载")
                return

            if idx > 0:
                self.status_msg.emit(f"⚠️ 正在自动无缝切换至备用镜像节点 ({idx + 1}/{total_candidates})...")

            try:
                req = urllib.request.Request(target_url, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    self._active_resp = resp
                    content_len = resp.headers.get("Content-Length")
                    total_bytes = int(content_len) if content_len and content_len.isdigit() else 0

                    with open(temp_file, "wb") as f_out:
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

                # Verification: file size > 1MB
                if temp_file.exists() and temp_file.stat().st_size > 1024 * 1024:
                    if dest_file.exists():
                        try:
                            dest_file.unlink()
                        except Exception:
                            pass
                    temp_file.rename(dest_file)
                    self.finished.emit(True, str(dest_file), "")
                    return
                else:
                    last_err = "下载文件不完整或大小异常"
            except Exception as e:
                last_err = str(e)
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                    except Exception:
                        pass
                if self._is_cancelled:
                    self.finished.emit(False, "", "用户已取消下载")
                    return
                continue

        # If all candidates failed
        self.finished.emit(False, "", f"所有镜像源及直连均连接失败: {last_err}")


class AppUpdateDialog(QDialog):
    """
    Modern Fluent Dialog for DM-Toolbox Application Updates.
    Allows viewing all GitHub releases, selecting any target release, intelligent mirror speed testing,
    auto-selection, automatic failover, and crash-proof cancellation.
    """
    def __init__(self, parent=None, is_dark: Optional[bool] = None, preloaded_releases: Optional[List[Dict[str, Any]]] = None):
        super().__init__(parent)
        if is_dark is None:
            self.is_dark = (get_global_theme() == "dark")
        else:
            self.is_dark = is_dark

        self.setWindowTitle("DM工具箱 - 软件更新")
        self.setFixedSize(720, 640)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)

        self.updater_cfg = get_updater_config()
        self.releases_data: List[Dict[str, Any]] = preloaded_releases or []
        self.selected_release: Optional[Dict[str, Any]] = None
        self.selected_asset: Optional[Dict[str, Any]] = None

        self.download_worker: Optional[DownloadInstallerWorker] = None
        self.downloaded_installer_path: Optional[str] = None

        self.speed_test_worker: Optional[MirrorSpeedTestWorker] = None
        self.mirror_speed_results: Dict[str, Dict[str, Any]] = {}
        self.best_mirror_id: str = "ghproxy_com"

        self._init_ui()
        self._apply_style()

        if self.releases_data:
            self._on_releases_fetched(True, self.releases_data, "")
        else:
            self._start_fetch_releases()

        # Initiate background mirror speed test
        self.start_mirror_speed_test()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 18, 20, 18)
        main_layout.setSpacing(12)

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
        lbl_sel.setObjectName("StrongLabel")
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
        self.lbl_rel_date.setMinimumWidth(230)
        self.lbl_rel_size = QLabel("安装包大小: --")
        self.lbl_rel_size.setMinimumWidth(260)
        self.meta_box.addWidget(self.lbl_rel_date)
        self.meta_box.addSpacing(16)
        self.meta_box.addWidget(self.lbl_rel_size)
        self.meta_box.addStretch()
        main_layout.addLayout(self.meta_box)

        # 4. Changelog Text Area
        lbl_notes = QLabel("📝 版本更新日志与特性:")
        lbl_notes.setObjectName("StrongLabel")
        main_layout.addWidget(lbl_notes)

        self.text_notes = QTextBrowser()
        self.text_notes.setOpenExternalLinks(True)
        self.text_notes.setMinimumHeight(150)
        main_layout.addWidget(self.text_notes, 1)

        # 5. Mirror Sources & Settings Card (Dedicated visible settings card)
        settings_card = QFrame()
        settings_card.setObjectName("SettingsCard")
        s_layout = QVBoxLayout(settings_card)
        s_layout.setContentsMargins(12, 10, 12, 10)
        s_layout.setSpacing(8)

        # Mirror Source Selection Row
        mirror_row = QHBoxLayout()
        mirror_row.setSpacing(8)
        lbl_mirror = QLabel("🌐 下载加速镜像源:")
        lbl_mirror.setObjectName("StrongLabel")
        lbl_mirror.setFixedWidth(125)
        mirror_row.addWidget(lbl_mirror)

        self.combo_mirror = QComboBox()
        self.combo_mirror.setMinimumHeight(32)
        self.combo_mirror.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for m in MIRROR_SOURCES:
            self.combo_mirror.addItem(m["name"], m["id"])

        saved_mirror_id = self.updater_cfg.get("mirror_id", "auto")
        idx_m = self.combo_mirror.findData(saved_mirror_id)
        if idx_m >= 0:
            self.combo_mirror.setCurrentIndex(idx_m)
        self.combo_mirror.currentIndexChanged.connect(self._on_mirror_selection_changed)
        mirror_row.addWidget(self.combo_mirror, 1)

        self.btn_speed_test = QPushButton("⚡ 重新测速")
        self.btn_speed_test.setFixedWidth(104)
        self.btn_speed_test.setMinimumHeight(32)
        self.btn_speed_test.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_speed_test.setToolTip("重新对所有镜像加速节点发起并行测速，并自动优选最快节点")
        self.btn_speed_test.clicked.connect(self.start_mirror_speed_test)
        mirror_row.addWidget(self.btn_speed_test)
        s_layout.addLayout(mirror_row)

        # Mirror Status / Latency hint label
        self.lbl_mirror_status = QLabel("⏳ 正在自动测试各镜像源延迟并优选最快可用节点...")
        self.lbl_mirror_status.setStyleSheet("font-size: 11.5px; color: #16A34A; font-weight: 600; padding-left: 2px;")
        s_layout.addWidget(self.lbl_mirror_status)

        # Auto Check Checkbox Row (High contrast, clearly visible)
        auto_row = QHBoxLayout()
        self.chk_auto_check = QCheckBox("🔔 每次开启软件自动在后台检查更新 (发现新版将在主页顶部显眼提示)")
        self.chk_auto_check.setChecked(self.updater_cfg.get("auto_check", True))
        self.chk_auto_check.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_auto_check.stateChanged.connect(self._save_options)
        auto_row.addWidget(self.chk_auto_check)
        auto_row.addStretch()
        s_layout.addLayout(auto_row)

        main_layout.addWidget(settings_card)

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

        self.btn_download = QPushButton("⬇️ 立即下载安装")
        self.btn_download.setObjectName("PrimaryButton")
        self.btn_download.setMinimumHeight(36)
        self.btn_download.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_download.setEnabled(False)
        self.btn_download.clicked.connect(self._start_download)
        btn_row.addWidget(self.btn_download)

        self.btn_close = QPushButton("关闭")
        self.btn_close.setMinimumHeight(36)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.clicked.connect(self._on_close_clicked)
        btn_row.addWidget(self.btn_close)

        main_layout.addLayout(btn_row)

    def _save_options(self):
        self.updater_cfg["mirror_id"] = self.combo_mirror.currentData()
        self.updater_cfg["auto_check"] = self.chk_auto_check.isChecked()
        save_updater_config(self.updater_cfg)

    def _get_mirror_name(self, mirror_id: str) -> str:
        for m in MIRROR_SOURCES:
            if m["id"] == mirror_id:
                # Return clean short title
                name = m["name"]
                m_clean = re.sub(r'\s*\(.*?\)', '', name).strip()
                return m_clean
        return mirror_id

    def _on_mirror_selection_changed(self):
        self._save_options()
        cur_id = self.combo_mirror.currentData()
        if cur_id == "auto":
            best_info = self.mirror_speed_results.get(self.best_mirror_id, {})
            lat = best_info.get("latency", 0)
            self.lbl_mirror_status.setText(f"✅ 智能测速优选已锁定最快可用节点: [{self._get_mirror_name(self.best_mirror_id)}] (延迟 {lat}ms · 即开即下)")
        elif cur_id in self.mirror_speed_results:
            info = self.mirror_speed_results[cur_id]
            if info.get("ok"):
                self.lbl_mirror_status.setText(f"🟢 当前手动指定节点 [{self._get_mirror_name(cur_id)}] 连接正常 (延迟 {info['latency']}ms)")
            else:
                self.lbl_mirror_status.setText(f"⚠️ 当前手动指定节点不可用或超时！下载时将自动无缝故障转移至备用可用节点")

    def start_mirror_speed_test(self):
        """Starts asynchronous concurrent testing of all candidate mirrors."""
        if self.speed_test_worker and self.speed_test_worker.isRunning():
            return

        test_url = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/download/v{APP_VERSION}/DM-BOX.exe"
        if self.selected_asset and self.selected_asset.get("browser_download_url"):
            test_url = self.selected_asset["browser_download_url"]

        self.btn_speed_test.setEnabled(False)
        self.lbl_mirror_status.setText("⏳ 正在自动测试各镜像源延迟并优选最快可用节点...")

        self.speed_test_worker = MirrorSpeedTestWorker(MIRROR_SOURCES, test_url)
        self.speed_test_worker.node_tested.connect(self._on_speed_test_node_tested)
        self.speed_test_worker.finished.connect(self._on_speed_test_finished)
        self.speed_test_worker.start()

    def _on_speed_test_node_tested(self, mirror_id: str, latency: int, ok: bool):
        idx = self.combo_mirror.findData(mirror_id)
        if idx >= 0:
            base_m = next((m for m in MIRROR_SOURCES if m["id"] == mirror_id), None)
            if base_m:
                clean_name = re.sub(r'\s*\(.*?\)', '', base_m["name"]).strip()
                if ok:
                    tag = "极速" if latency <= 600 else "良好" if latency <= 1500 else "较慢"
                    self.combo_mirror.setItemText(idx, f"{clean_name} ({latency}ms · {tag})")
                else:
                    self.combo_mirror.setItemText(idx, f"{clean_name} (连接超时/不可用)")

    def _on_speed_test_finished(self, results: dict, best_id: str):
        self.mirror_speed_results = results
        self.best_mirror_id = best_id
        self.btn_speed_test.setEnabled(True)

        best_info = results.get(best_id, {})
        best_lat = best_info.get("latency", 0)

        # Update auto option text
        idx_auto = self.combo_mirror.findData("auto")
        if idx_auto >= 0:
            self.combo_mirror.setItemText(idx_auto, f"⚡ 智能测速优选 (已自动优选: {self._get_mirror_name(best_id)} · {best_lat}ms)")

        # Update status message
        cur_id = self.combo_mirror.currentData()
        if cur_id == "auto":
            self.lbl_mirror_status.setText(f"✅ 测速完成！智能优选已锁定最快可用节点: [{self._get_mirror_name(best_id)}] (延迟 {best_lat}ms · 即开即下)")
        elif cur_id in results and results[cur_id].get("ok"):
            self.lbl_mirror_status.setText(f"🟢 当前手动指定节点 [{self._get_mirror_name(cur_id)}] 连接正常 (延迟 {results[cur_id]['latency']}ms)")
        else:
            self.lbl_mirror_status.setText(f"⚠️ 当前手动指定节点不可用！下载时将自动无缝故障转移至可用节点: [{self._get_mirror_name(best_id)}]")

    def _get_download_candidate_urls(self, download_url: str) -> List[str]:
        cur_id = self.combo_mirror.currentData()
        candidates = []

        def make_url(prefix: str) -> str:
            if not prefix:
                return download_url
            return f"{prefix.rstrip('/')}/{download_url.lstrip('/')}"

        # 1. If user explicitly selected a specific mirror (and not auto), put it first
        if cur_id != "auto":
            for m in MIRROR_SOURCES:
                if m["id"] == cur_id and m["id"] != "auto":
                    candidates.append(make_url(m["prefix"]))
                    break

        # 2. Add best mirror from speed test
        best_m = next((m for m in MIRROR_SOURCES if m["id"] == self.best_mirror_id), None)
        if best_m:
            url = make_url(best_m["prefix"])
            if url not in candidates:
                candidates.append(url)

        # 3. Add other working mirrors sorted by lowest latency
        tested_ok = [
            (m_id, data["latency"])
            for m_id, data in self.mirror_speed_results.items()
            if data.get("ok") and m_id != cur_id and m_id != self.best_mirror_id
        ]
        tested_ok.sort(key=lambda x: x[1])
        for m_id, _ in tested_ok:
            m = next((item for item in MIRROR_SOURCES if item["id"] == m_id), None)
            if m:
                url = make_url(m["prefix"])
                if url not in candidates:
                    candidates.append(url)

        # 4. Add any remaining defined mirrors as fallback
        for m in MIRROR_SOURCES:
            if m["id"] != "auto":
                url = make_url(m["prefix"])
                if url not in candidates:
                    candidates.append(url)

        # 5. Always ensure direct GitHub download URL is in the fallback list
        if download_url not in candidates:
            candidates.append(download_url)

        return candidates

    def _apply_style(self):
        if self.is_dark:
            bg_color = "#202124"
            card_bg = "#292A2D"
            card_border = "#3C4043"
            text_color = "#F3F4F6"
            sub_color = "#9CA3AF"
            accent_green = "#8FE3B0"
            btn_text = "#10231A"
            input_bg = "#303134"
            border_color = "#4B5563"
            chk_text_color = "#F3F4F6"
            self.badge_status.setStyleSheet("color: #8FE3B0; background-color: #1E3A2F; padding: 4px 10px; border-radius: 8px; font-size: 12px; font-weight: 700;")
        else:
            bg_color = "#F3F4F6"
            card_bg = "#FFFFFF"
            card_border = "#E5E7EB"
            text_color = "#111827"
            sub_color = "#4B5563"
            accent_green = "#16A34A"
            btn_text = "#FFFFFF"
            input_bg = "#FFFFFF"
            border_color = "#D1D5DB"
            chk_text_color = "#111827"
            self.badge_status.setStyleSheet("color: #16A34A; background-color: #DCFCE7; padding: 4px 10px; border-radius: 8px; font-size: 12px; font-weight: 700;")

        check_icon_p = Path(__file__).resolve().parent / "assets" / "check_white.png"
        check_icon_url = check_icon_p.as_posix() if check_icon_p.exists() else ""

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
                color: {text_color};
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            }}
            QFrame#HeaderCard, QFrame#SettingsCard {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 10px;
            }}
            QLabel {{
                color: {text_color};
            }}
            QLabel#StrongLabel {{
                font-size: 13px;
                font-weight: 700;
                color: {text_color};
            }}
            QCheckBox {{
                color: {chk_text_color} !important;
                font-size: 12.5px;
                font-weight: 600;
                spacing: 8px;
                background: transparent;
            }}
            QCheckBox:hover {{
                color: {accent_green} !important;
            }}
            QCheckBox::indicator {{
                width: 17px;
                height: 17px;
                border: 1.5px solid {'#4B5563' if self.is_dark else '#9CA3AF'};
                border-radius: 4px;
                background-color: {'#303134' if self.is_dark else '#FFFFFF'};
            }}
            QCheckBox::indicator:hover {{
                border-color: {accent_green};
            }}
            QCheckBox::indicator:checked {{
                background-color: {accent_green};
                border-color: {accent_green};
                image: url("{check_icon_url}");
            }}
            QComboBox {{
                background-color: {input_bg};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 8px;
                padding: 4px 12px;
                font-size: 13px;
            }}
            QComboBox:hover {{
                border-color: {accent_green};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 25px;
                border-left-width: 0px;
            }}
            QTextBrowser {{
                background-color: {card_bg};
                color: {text_color};
                border: 1px solid {card_border};
                border-radius: 8px;
                padding: 10px;
            }}
            QPushButton {{
                background-color: {'#374151' if self.is_dark else '#E5E7EB'};
                color: {text_color};
                border: 1px solid {card_border};
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 12.5px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {'#4B5563' if self.is_dark else '#D1D5DB'};
            }}
            QProgressBar {{
                background-color: {'#374151' if self.is_dark else '#E5E7EB'};
                border-radius: 7px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {accent_green};
                border-radius: 7px;
            }}
            QPushButton#PrimaryButton {{
                background-color: {accent_green};
                color: {btn_text};
                border: none;
                font-weight: 700;
            }}
            QPushButton#PrimaryButton:hover {{
                background-color: {'#A3F2C2' if self.is_dark else '#15803D'};
            }}
            QPushButton#PrimaryButton:disabled {{
                background-color: {'#4B5563' if self.is_dark else '#D1D5DB'};
                color: {'#9CA3AF' if self.is_dark else '#9CA3AF'};
            }}
        """)

    def _start_fetch_releases(self):
        self.btn_refresh.setEnabled(False)
        self.badge_status.setText("⏳ 正在查询 GitHub Releases...")
        self.badge_status.setStyleSheet("color: #EAB308; background-color: #713F12; padding: 4px 10px; border-radius: 8px; font-size: 12px; font-weight: 700;" if self.is_dark else "color: #D97706; background-color: #FEF3C7; padding: 4px 10px; border-radius: 8px; font-size: 12px; font-weight: 700;")

        self.fetch_worker = CheckUpdateWorker()
        self.fetch_worker.finished.connect(self._on_releases_fetched)
        self.fetch_worker.start()

    def _on_releases_fetched(self, success: bool, releases: list, err: str):
        self.btn_refresh.setEnabled(True)
        if not success or not releases:
            self.badge_status.setText("❌ 获取失败")
            self.badge_status.setStyleSheet("color: #EF4444; background-color: #450A0A; padding: 4px 10px; border-radius: 8px; font-size: 12px; font-weight: 700;" if self.is_dark else "color: #DC2626; background-color: #FEE2E2; padding: 4px 10px; border-radius: 8px; font-size: 12px; font-weight: 700;")
            self.text_notes.setHtml(f"<p style='color: #EF4444;'><b>获取版本列表失败:</b> {err}</p><p>请检查网络连接或稍后点击『重新检查』。</p>")
            return

        self.releases_data = releases
        self.combo_versions.blockSignals(True)
        self.combo_versions.clear()

        latest_rel = releases[0]
        latest_tag = latest_rel.get("tag_name", "")
        has_new = parse_version_tuple(latest_tag) > parse_version_tuple(APP_VERSION)

        if has_new:
            self.badge_status.setText(f"🎉 发现新版本 ({latest_tag})")
            self.badge_status.setStyleSheet("color: #FBBF24; background-color: #78350F; padding: 4px 10px; border-radius: 8px; font-size: 12px; font-weight: 700;" if self.is_dark else "color: #B45309; background-color: #FEF3C7; padding: 4px 10px; border-radius: 8px; font-size: 12px; font-weight: 700;")
        else:
            self.badge_status.setText(f"🟢 已是最新版本 (v{APP_VERSION})")
            self.badge_status.setStyleSheet("color: #8FE3B0; background-color: #1E3A2F; padding: 4px 10px; border-radius: 8px; font-size: 12px; font-weight: 700;" if self.is_dark else "color: #16A34A; background-color: #DCFCE7; padding: 4px 10px; border-radius: 8px; font-size: 12px; font-weight: 700;")

        for idx, r in enumerate(releases):
            tag = r.get("tag_name", "Unknown")
            name = r.get("name", "")
            display_text = f"{tag}"
            if idx == 0:
                display_text += " (最新)"
            if name and name != tag:
                display_text += f" · {name}"
            self.combo_versions.addItem(display_text, r)

        self.combo_versions.blockSignals(False)

        # Select top release by default
        if self.combo_versions.count() > 0:
            self.combo_versions.setCurrentIndex(0)
            self._on_version_selected(0)

    def _on_version_selected(self, index: int):
        if index < 0 or index >= len(self.releases_data):
            return

        release = self.combo_versions.itemData(index)
        if not release:
            return

        self.selected_release = release
        tag = release.get("tag_name", "")
        pub_at = release.get("published_at", "")
        if pub_at:
            pub_at = pub_at.replace("T", " ").replace("Z", "")
        self.lbl_rel_date.setText(f"发布时间: <b>{pub_at}</b>")

        # Find DM-BOX.exe asset
        assets = release.get("assets", [])
        installer_asset = None
        for a in assets:
            if a.get("name", "").lower().endswith(".exe"):
                installer_asset = a
                break

        self.selected_asset = installer_asset
        if installer_asset:
            size_mb = installer_asset.get("size", 0) / (1024 * 1024)
            self.lbl_rel_size.setText(f"安装包: <b>{installer_asset.get('name')}</b> ({size_mb:.2f} MB)")
            self.btn_download.setEnabled(True)
            if parse_version_tuple(tag) > parse_version_tuple(APP_VERSION):
                self.btn_download.setText(f"🚀 立即更新到 {tag}")
            elif parse_version_tuple(tag) == parse_version_tuple(APP_VERSION):
                self.btn_download.setText(f"🔄 重新下载安装 {tag}")
            else:
                self.btn_download.setText(f"⏮️ 回退安装 {tag}")
        else:
            self.lbl_rel_size.setText("安装包: <span style='color: #EF4444;'>未随此版本提供 exe</span>")
            self.btn_download.setEnabled(False)
            self.btn_download.setText("暂无可用安装程序")

        # Render release notes
        body = release.get("body", "")
        html = markdown_to_html(body, is_dark=self.is_dark)
        self.text_notes.setHtml(html)

    def _start_download(self):
        if not self.selected_asset:
            ModernDialog.warning(self, "无法下载", "当前选中的版本没有可用的安装包资产 (DM-BOX.exe)。")
            return

        download_url = self.selected_asset.get("browser_download_url")
        if not download_url:
            ModernDialog.warning(self, "下载失败", "安装包下载链接无效。")
            return

        tag = self.selected_release.get("tag_name", "update")
        target_dir = CACHE_ROOT / "updates"
        target_dir.mkdir(parents=True, exist_ok=True)
        dest_path = str(target_dir / f"DM-BOX-{tag}.exe")

        # Switch UI to downloading state
        self.progress_frame.setVisible(True)
        self.bar_download.setValue(0)
        self.lbl_progress.setText("正在连接下载服务器并优选最快节点...")
        self.btn_download.setEnabled(False)
        self.btn_refresh.setEnabled(False)
        self.combo_versions.setEnabled(False)
        self.combo_mirror.setEnabled(False)
        self.btn_speed_test.setEnabled(False)
        self.btn_close.setText("取消下载")

        candidate_urls = self._get_download_candidate_urls(download_url)
        self.download_worker = DownloadInstallerWorker(candidate_urls, dest_path)
        self.download_worker.progress.connect(self._on_download_progress)
        self.download_worker.status_msg.connect(self._on_download_status_msg)
        self.download_worker.finished.connect(self._on_download_finished)
        self.download_worker.start()

    def _on_download_status_msg(self, msg: str):
        self.lbl_progress.setText(f"<span style='color: #F59E0B;'>{msg}</span>")

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
        self.combo_mirror.setEnabled(True)
        self.btn_speed_test.setEnabled(True)
        self.btn_close.setText("关闭")

        if not success:
            if err == "用户已取消下载":
                self.lbl_progress.setText("⏹️ 下载已取消。可随时重新点击『下载安装』。")
                return
            self.lbl_progress.setText(f"<span style='color: #EF4444;'>下载失败: {err}</span>")
            warn_msg = f"更新安装包下载中断:\n{err}\n\n建议尝试点击『⚡ 重新测速』或切换不同镜像源后重试。"
            ModernDialog.warning(self, "下载失败", warn_msg)
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
                CREATE_NEW_PROCESS_GROUP = 0x00000200
                DETACHED_PROCESS = 0x00000008
                creation_flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
                subprocess.Popen([file_path], creationflags=creation_flags)
                QApplication.quit()
                sys.exit(0)
            except Exception as e:
                ModernDialog.warning(self, "启动安装向导失败", f"无法自动启动安装程序:\n{e}\n\n请手动双击运行该文件:\n{file_path}")

    def _on_close_clicked(self):
        # If currently downloading, clicking "取消下载" cancels the download without closing dialog
        if self.download_worker and self.download_worker.isRunning():
            self.lbl_progress.setText("⏳ 正在取消下载...")
            self.download_worker.cancel()
            return
        self.close()

    def closeEvent(self, event):
        # Disconnect worker signals to prevent C++ deleted object crashes on close
        if self.download_worker:
            try:
                self.download_worker.progress.disconnect()
            except Exception:
                pass
            try:
                self.download_worker.status_msg.disconnect()
            except Exception:
                pass
            try:
                self.download_worker.finished.disconnect()
            except Exception:
                pass
            if self.download_worker.isRunning():
                self.download_worker.cancel()
                self.download_worker.wait(2500)

        if hasattr(self, "speed_test_worker") and self.speed_test_worker:
            try:
                self.speed_test_worker.node_tested.disconnect()
            except Exception:
                pass
            try:
                self.speed_test_worker.finished.disconnect()
            except Exception:
                pass
            if self.speed_test_worker.isRunning():
                self.speed_test_worker.cancel()
                self.speed_test_worker.wait(2500)

        super().closeEvent(event)

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

    def stop(self, timeout_ms: int = 3000):
        """Cancel a running background check and wait briefly for the thread to exit.

        Without this the QThread can still be running when the window is torn down,
        which crashes the process at shutdown ("QThread: Destroyed while thread is
        still running").
        """
        worker = self.worker
        if worker is None:
            return
        try:
            worker.cancel()
            if worker.isRunning():
                worker.wait(timeout_ms)
        except Exception:
            pass

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
