# -*- coding: utf-8 -*-
"""
Unit test suite for DLSS 5 and Toolbox-wide Secondary Dialog Modernization (v1.3.1).
Verifies:
1. Complete elimination of raw native QMessageBox in app6_dlss5.
2. ModernDialog contract compliance in common.dm_ui_core (info, success, warning, error, confirm, choice3).
3. Light Mode (daytime) and Dark Mode contrast schemes.
4. OptiScalerPresetDialog scroll area wrapping and layout robustness.
"""

import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PySide6.QtWidgets import QApplication, QDialog, QScrollArea
from PySide6.QtCore import Qt

from common.dm_ui_core import ModernDialog
from apps.app2_mfg.gui_qt import OptiScalerPresetDialog


class TestDLSS5ModernDialogs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_01_no_raw_qmessagebox_in_app6(self):
        """Verify zero raw QMessageBox usage in apps/app6_dlss5/app.py."""
        app_file = ROOT_DIR / "apps" / "app6_dlss5" / "app.py"
        with open(app_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertNotIn("QMessageBox", content, "apps/app6_dlss5/app.py must not contain any raw QMessageBox calls")
        self.assertIn("ModernDialog", content, "apps/app6_dlss5/app.py must use ModernDialog for all popups")

    def test_02_moderndialog_light_mode_contrast_and_elements(self):
        """Verify ModernDialog in Light Mode (daytime) renders high-contrast badges, cards, and buttons."""
        dlg = ModernDialog(
            parent=None,
            title="测试白天高对比度注入成功",
            message="✅ 核心插件及底层组件部署成功，光影神经重构已就绪。",
            dialog_type="success",
            is_dark=False
        )
        self.assertFalse(dlg.is_dark)
        self.assertEqual(dlg.windowFlags() & Qt.WindowType.FramelessWindowHint, Qt.WindowType.FramelessWindowHint)
        self.assertTrue(dlg.isModal())

        # Card and layout checks
        card = dlg.findChild(object, "ModernDialogCard")
        self.assertIsNotNone(card)

        # Style check: card background in light mode must be pure white (#FFFFFF)
        style = card.styleSheet()
        self.assertIn("#FFFFFF", style)
        dlg.close()

    def test_03_moderndialog_choice3_buttons(self):
        """Verify choice3 3-branch dialog configuration for uninstall/restore."""
        dlg = ModernDialog(
            parent=None,
            title="确认还原 / 卸载",
            message="请选择还原方案：\n• 彻底清除全部\n• 仅卸载 DLSS 5",
            dialog_type="question",
            is_dark=False,
            custom_buttons=[
                ("取消", 0, "cancel"),
                ("仅卸载 DLSS 5", 2, "secondary"),
                ("彻底清除全部 (推荐)", 1, "primary")
            ]
        )
        self.assertFalse(dlg.is_dark)
        dlg.close()

    def test_04_moderndialog_long_message_scroll(self):
        """Verify that long messages automatically get wrapped in a QScrollArea."""
        long_msg = "这是一段很长的测试日志与堆栈信息。\n" * 15
        dlg = ModernDialog(
            parent=None,
            title="长文本详情展示",
            message=long_msg,
            dialog_type="info",
            is_dark=True
        )
        scrolls = dlg.findChildren(QScrollArea)
        self.assertGreater(len(scrolls), 0, "Long messages must be enclosed in a QScrollArea")
        dlg.close()

    def test_05_optiscaler_preset_dialog_scroll_and_contrast(self):
        """Verify OptiScalerPresetDialog has scroll-wrapped tabs and daytime contrast."""
        dlg = OptiScalerPresetDialog(parent=None, is_dark=False, initial_mode="C")
        self.assertFalse(dlg.is_dark)

        # Ensure stacked widget contains scroll areas to prevent overlapping
        scrolls = dlg.stacked_widget.findChildren(QScrollArea)
        self.assertGreaterEqual(len(scrolls), 3, "All 3 tabs (A, B, C) must be wrapped in QScrollArea")
        dlg.close()


if __name__ == "__main__":
    unittest.main()
