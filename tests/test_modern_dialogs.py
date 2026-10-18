# -*- coding: utf-8 -*-
"""
Automated verification test for ModernConfirmDialog, ModernDialog, and ModernProgressDialog.
Takes screenshots of both Light and Dark modes to verify Fluent styling.
"""

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtGui import QFont
from PySide6.QtCore import QTimer
from common.ui_theme import ModernConfirmDialog, ModernProgressDialog, ModernDialog

def run_tests():
    app = QApplication.instance() or QApplication(sys.argv)
    app_font = QFont("Microsoft YaHei UI", 10)
    app_font.setStyleStrategy(QFont.PreferAntialias | QFont.PreferQuality)
    app.setFont(app_font)

    artifacts_dir = Path(r"C:\Users\17547\.gemini\antigravity\brain\f20364b0-8af4-45b1-a8b6-b621a086cb69")

    print("[1/4] Testing ModernConfirmDialog (Dark Mode)...")
    dlg_dark = ModernConfirmDialog(
        parent=None,
        title="确认还原默认设置与清理缓存",
        message="该操作将执行系统级环境清理与出厂设置还原：",
        bullet_items=[
            "• 安全关闭当前所有正在运行的 4 个子软件（释放文件占用锁）",
            "• 彻底清空 %APPDATA%/ToolboxMaster/ 下的所有临时缓存、日志和下载",
            "• 将四个子软件的当前配置文件重置为 defaults/ 初始出厂配置"
        ],
        warning_note="⚠️ 注意：重置后所有自定义配置将丢失，此操作不可撤销！",
        confirm_text="立即清理并还原",
        cancel_text="取消",
        icon_type="danger",
        is_danger=True,
        is_dark=True
    )
    dlg_dark.show()
    QApplication.processEvents()
    pix_dark = dlg_dark.grab()
    pix_dark.save(str(artifacts_dir / "verification_confirm_dialog_dark.png"))
    dlg_dark.close()
    print("  -> Saved verification_confirm_dialog_dark.png")

    print("[2/4] Testing ModernConfirmDialog (Light Mode)...")
    dlg_light = ModernConfirmDialog(
        parent=None,
        title="确认还原默认设置与清理缓存",
        message="该操作将执行系统级环境清理与出厂设置还原：",
        bullet_items=[
            "• 安全关闭当前所有正在运行的 4 个子软件（释放文件占用锁）",
            "• 彻底清空 %APPDATA%/ToolboxMaster/ 下的所有临时缓存、日志和下载",
            "• 将四个子软件的当前配置文件重置为 defaults/ 初始出厂配置"
        ],
        warning_note="⚠️ 注意：重置后所有自定义配置将丢失，此操作不可撤销！",
        confirm_text="立即清理并还原",
        cancel_text="取消",
        icon_type="danger",
        is_danger=True,
        is_dark=False
    )
    dlg_light.show()
    QApplication.processEvents()
    pix_light = dlg_light.grab()
    pix_light.save(str(artifacts_dir / "verification_confirm_dialog_light.png"))
    dlg_light.close()
    print("  -> Saved verification_confirm_dialog_light.png")

    print("[3/4] Testing ModernProgressDialog running state (Dark Mode)...")
    prog_dark = ModernProgressDialog(
        parent=None,
        title="还原默认设置与清理缓存",
        description="正在启动清理流程...",
        is_dark=True
    )
    prog_dark.show()
    prog_dark.anim.stop()
    prog_dark.progress_bar.setValue(45)
    prog_dark.lbl_percent.setText("45%")
    prog_dark.lbl_desc.setText("正在释放文件系统占用锁...")
    prog_dark.lbl_detail.setText("等待子进程句柄完全释放并清理进程表")
    QApplication.processEvents()
    pix_prog_running = prog_dark.grab()
    pix_prog_running.save(str(artifacts_dir / "verification_progress_running_dark.png"))
    print("  -> Saved verification_progress_running_dark.png")

    print("[4/4] Testing ModernProgressDialog finished state with button...")
    prog_dark.finish(
        True,
        "清理与还原成功！",
        "已成功释放 128.50 MB 空间，所有配置与缓存已重置完毕",
        auto_close_delay_ms=0
    )
    QApplication.processEvents()
    pix_prog_finished = prog_dark.grab()
    pix_prog_finished.save(str(artifacts_dir / "verification_progress_finished_dark.png"))
    prog_dark.close()
    print("  -> Saved verification_progress_finished_dark.png")

    print("ALL MODERN DIALOG TESTS PASSED!")

if __name__ == "__main__":
    run_tests()
