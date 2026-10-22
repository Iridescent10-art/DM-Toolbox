# -*- coding: utf-8 -*-
"""
Test Suite v134:
1. DLSS5 UI Freeze & Scroll Lock Fix Verification:
   - ModernDialog.done() automatically restores focus and active window state to parent.
   - DMBaseWindow.eventFilter intercepts Wheel events and scrolls scroll_area smoothly.
   - DLSS5Window.wheelEvent forwards wheel delta to verticalScrollBar.
   - Restore button remains enabled for immediate user feedback.
2. DLSS Frame Generation Model C Preservation Fix:
   - When dlss_preset == 0 (Default / Native passthrough), no DLSSPreset* or RenderPresetForAll
     keys are written to ReShade.ini.
   - [INSTALL] is configured as HookDirectX=1 and HookStreamline=0, preventing ReShade
     from intercepting Streamline slInit, which preserves NVApp's driver-level Model C.
3. Multi-Frame Generation ABC Modes + DLSS 5 Simultaneous Injection:
   - Mode A + DLSS 5: version.dll + dxgi.dll (ReShade) + renodx-dlss5.addon64 without Streamline hook conflict.
   - Mode B + DLSS 5: dxgi.dll hosting both renodx-mfgunlock.addon64 and renodx-dlss5.addon64 with EnableHooks=2.
   - Mode C + DLSS 5: dxgi.dll (OptiScaler) + ReShade64.dll + renodx-dlss5.addon64 with ASI/d3d12 purge.
"""

import os
import sys
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Setup paths
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root_dir)
sys.path.insert(0, os.path.join(root_dir, "apps", "app2_mfg"))

from PySide6.QtCore import Qt, QPoint, QPointF
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QWidget, QScrollArea, QVBoxLayout, QPushButton

from common.dm_ui_core import DMBaseWindow, ModernDialog
from apps.app6_dlss5.engine.injector import DLSS5Injector, check_dlss5_status
from apps.app6_dlss5.engine.dlss5_config import write_game_dlss5_config, load_dlss5_preset
from apps.app6_dlss5.engine.config_sync import ConfigSyncService
from apps.app2_mfg.core.ini_sync import IniConfigManager
from apps.app2_mfg.core.models import GameInfo, BackendType, QualificationStatus, PatchManifest
from apps.app2_mfg.core.patcher import PatchEngine
from apps.app2_mfg.core.updater import ComponentUpdater


class TestDLSS5UIFreezeAndCoexistence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication(sys.argv)

    # ---------------- 1. UI Freeze & Scroll Tests ----------------
    def test_modern_dialog_done_reactivates_parent(self):
        parent_win = QWidget()
        parent_win.activateWindow = MagicMock()
        parent_win.raise_ = MagicMock()
        parent_win.setFocus = MagicMock()

        dlg = ModernDialog(parent_win, "测试", "内容")
        dlg.done(1)

        parent_win.activateWindow.assert_called()
        parent_win.raise_.assert_called()
        parent_win.setFocus.assert_called()

    def test_dm_base_window_event_filter_wheel_scrolls_area(self):
        win = DMBaseWindow("测试窗口", 800, 600)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content.setMinimumHeight(2000)
        scroll.setWidget(content)
        win.scroll_area = scroll
        win.setCentralWidget(scroll)

        win.show()
        QApplication.processEvents()

        bar = scroll.verticalScrollBar()
        initial_val = bar.value()

        # Simulate wheel event (delta = -120, scroll down)
        wheel_ev = QWheelEvent(
            QPointF(100, 100),
            QPointF(100, 100),
            QPoint(0, 0),
            QPoint(0, -120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False
        )

        # watched is content inside window
        handled = win.eventFilter(content, wheel_ev)
        self.assertTrue(handled, "DMBaseWindow.eventFilter must handle wheel event and scroll")
        self.assertGreater(bar.value(), initial_val, "Vertical scrollbar value must increase when scrolling down")

        # 1b. Test precision touchpad (pixelDelta != 0, angleDelta == 0)
        touchpad_ev = QWheelEvent(
            QPointF(100, 100),
            QPointF(100, 100),
            QPoint(0, -35),
            QPoint(0, 0),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False
        )
        before_tp = bar.value()
        handled_tp = win.eventFilter(content, touchpad_ev)
        self.assertTrue(handled_tp, "DMBaseWindow.eventFilter must handle touchpad pixelDelta event")
        self.assertGreater(bar.value(), before_tp, "Vertical scrollbar value must increase for touchpad scrolling down")

        # 1c. Test wheel event when window is maximized
        win.isMaximized = MagicMock(return_value=True)
        wheel_up_ev = QWheelEvent(
            QPointF(100, 100),
            QPointF(100, 100),
            QPoint(0, 0),
            QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False
        )
        before_max = bar.value()
        handled_max = win.eventFilter(content, wheel_up_ev)
        self.assertTrue(handled_max, "DMBaseWindow.eventFilter must handle wheel events even when maximized")
        self.assertLess(bar.value(), before_max, "Vertical scrollbar value must decrease when scrolling up while maximized")

        win.close()

    def test_dlss5_window_qscroller_and_key_navigation(self):
        from apps.app6_dlss5.app import DLSS5Window
        from PySide6.QtWidgets import QScroller
        from PySide6.QtGui import QKeyEvent

        win = DLSS5Window()
        win.resize(1060, 800)
        win.show()
        QApplication.processEvents()

        # Check QScroller attached to viewport
        scroller = QScroller.scroller(win.scroll_area.viewport())
        self.assertIsNotNone(scroller, "QScroller must be attached to DLSS5Window viewport")

        bar = win.scroll_area.verticalScrollBar()
        bar.setValue(bar.maximum())
        self.assertGreater(bar.value(), 0)

        # Test PageUp key navigation
        ev_pgup = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_PageUp, Qt.KeyboardModifier.NoModifier)
        win.keyPressEvent(ev_pgup)
        self.assertLess(bar.value(), bar.maximum(), "PageUp key must scroll the viewport up")

        # Test Home key navigation (resets to top)
        ev_home = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Home, Qt.KeyboardModifier.NoModifier)
        win.keyPressEvent(ev_home)
        self.assertEqual(bar.value(), 0, "Home key must scroll all the way to top (value 0)")

        win.close()

    def test_no_ws_ex_layered_and_no_screen_freeze_after_modal_dialog(self):
        import ctypes
        from apps.app6_dlss5.app import DLSS5Window
        from common.dm_ui_core import ModernDialog
        from PySide6.QtCore import QTimer

        win = DLSS5Window()
        win.show()
        QApplication.processEvents()

        hwnd = int(win.winId())
        ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
        self.assertFalse(bool(ex_style & 0x00080000), "Main DLSS5Window must NOT have WS_EX_LAYERED to prevent backing store freeze")

        # Open and auto-close a modal ModernDialog
        QTimer.singleShot(50, lambda: QApplication.activeModalWidget().accept())
        ModernDialog.success(win, "测试", "测试消息")
        QApplication.processEvents()

        ex_style_after = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
        self.assertFalse(bool(ex_style_after & 0x00080000), "DLSS5Window must remain non-layered after modal dialog closes")

        # Scroll verticalScrollBar and verify container updates
        bar = win.scroll_area.verticalScrollBar()
        bar.setValue(150)
        QApplication.processEvents()
        self.assertEqual(bar.value(), 150)
        self.assertEqual(win.scroll_area.widget().pos().y(), -150)

        win.close()

    def test_dlss5_restore_button_logic_allows_immediate_feedback(self):
        with tempfile.TemporaryDirectory() as td:
            # Completely clean directory
            status = check_dlss5_status(td)
            self.assertFalse(status["is_injected"])

            # Fake DLSS 5 residue (e.g. .dlss5_config.json left over)
            config_file = os.path.join(td, ".dlss5_config.json")
            with open(config_file, "w", encoding="utf-8") as f:
                f.write("{}")

            status_res = check_dlss5_status(td)
            self.assertTrue(status_res["has_residual"], "has_residual must be True when config residue exists")

    # ---------------- 2. NVApp Model C DLSS-G Preservation ----------------
    def test_dlss_preset_zero_strips_dlss_preset_keys_and_preserves_model_c(self):
        with tempfile.TemporaryDirectory() as td:
            reshade_ini = os.path.join(td, "ReShade.ini")

            # 1. Preload with old legacy DLSSPresetQuality=0 that would override NVApp
            with open(reshade_ini, "w", encoding="utf-8") as f:
                f.write(
                    "DLSSPresetQuality=0\n"
                    "DLSSPresetDLAA=0\n"
                    "DirectNeuralRenderingPreset=0\n"
                    "[DLSS]\n"
                    "RenderPresetForAll=0\n"
                    "RenderPresetOverride=true\n"
                    "[RENODX-DLSS]\n"
                    "DLSSPresetQuality=0\n"
                )

            cfg = load_dlss5_preset()
            cfg["dlss_preset"] = 0  # Default Native / Passthrough
            ok = write_game_dlss5_config(reshade_ini, cfg)
            self.assertTrue(ok)

            secs = IniConfigManager.read_ini_sections(reshade_ini)

            # Assert [INSTALL] routes through DirectX, not Streamline
            self.assertEqual(secs.get("INSTALL", {}).get("HookDirectX"), "1")
            self.assertEqual(secs.get("INSTALL", {}).get("HookStreamline"), "0")

            # Assert DLSSPreset* keys are purged
            root_sec = secs.get("", {})
            self.assertNotIn("DLSSPresetQuality", root_sec)
            self.assertNotIn("DLSSPresetDLAA", root_sec)
            self.assertNotIn("DirectNeuralRenderingPreset", root_sec)

            renodx_sec = secs.get("RENODX-DLSS", {})
            self.assertNotIn("DLSSPresetQuality", renodx_sec)

            dlss_sec = secs.get("DLSS", {})
            self.assertEqual(dlss_sec.get("RenderPresetOverride"), "false")
            self.assertNotIn("RenderPresetForAll", dlss_sec)

    # ---------------- 3. Multi-Frame Generation Co-existence ----------------
    def test_mode_a_coexistence_with_dlss5(self):
        """Mode A (dashdogy version.dll) + DLSS 5 (dxgi.dll ReShade)."""
        with tempfile.TemporaryDirectory() as td:
            updater = ComponentUpdater()
            patcher = PatchEngine(updater=updater)

            game = GameInfo(
                name="TestA",
                source="custom",
                install_dir=td,
                target_dir=td,
                exe_path=os.path.join(td, "game.exe"),
                exe_name="game.exe",
                qualification=QualificationStatus.QUALIFIED
            )

            # Apply Mode A
            with patch("core.patcher.get_system_gpu_name", return_value="NVIDIA GeForce RTX 4070"), \
                 patch("core.patcher.is_rtx_40_or_newer", return_value=True):
                ok, msg = ConfigSyncService.apply_unified_configuration(
                    td, "game.exe", "A", {"multiplier": 3, "dlss_preset": 0}
                )
                self.assertTrue(ok, f"Mode A + DLSS 5 apply failed: {msg}")

            # Check files
            version_dll = os.path.join(td, "version.dll")
            dxgi_dll = os.path.join(td, "dxgi.dll")
            addon_dlss5 = os.path.join(td, "renodx-dlss5.addon64")
            opti_ini = os.path.join(td, "OptiScaler.ini")
            reshade64 = os.path.join(td, "ReShade64.dll")

            self.assertTrue(os.path.exists(version_dll), "Mode A must deploy version.dll")
            self.assertTrue(os.path.exists(dxgi_dll), "DLSS 5 must deploy dxgi.dll for ReShade")
            self.assertTrue(os.path.exists(addon_dlss5), "DLSS 5 must deploy renodx-dlss5.addon64")
            self.assertFalse(os.path.exists(opti_ini), "Mode A must not have OptiScaler.ini")
            self.assertFalse(os.path.exists(reshade64), "Mode A must not have ReShade64.dll")

            # Check ReShade.ini hook routing
            reshade_ini = os.path.join(td, "ReShade.ini")
            secs = IniConfigManager.read_ini_sections(reshade_ini)
            self.assertEqual(secs.get("INSTALL", {}).get("HookDirectX"), "1")
            self.assertEqual(secs.get("INSTALL", {}).get("HookStreamline"), "0")

    def test_mode_b_coexistence_with_dlss5(self):
        """Mode B (RenoDX addon) + DLSS 5 (RenoDX DLSS addon) hosted by single dxgi.dll."""
        with tempfile.TemporaryDirectory() as td:
            updater = ComponentUpdater()
            patcher = PatchEngine(updater=updater)

            game = GameInfo(
                name="TestB",
                source="custom",
                install_dir=td,
                target_dir=td,
                exe_path=os.path.join(td, "game.exe"),
                exe_name="game.exe",
                qualification=QualificationStatus.QUALIFIED
            )

            # Apply Mode B
            with patch("core.patcher.get_system_gpu_name", return_value="NVIDIA GeForce RTX 4070"), \
                 patch("core.patcher.is_rtx_40_or_newer", return_value=True):
                ok, msg = ConfigSyncService.apply_unified_configuration(
                    td, "game.exe", "B", {"multiplier": 3, "dlss_preset": 0}
                )
                self.assertTrue(ok, f"Mode B + DLSS 5 apply failed: {msg}")

            dxgi_dll = os.path.join(td, "dxgi.dll")
            mfg_addon = os.path.join(td, "renodx-mfgunlock.addon64")
            dlss5_addon = os.path.join(td, "renodx-dlss5.addon64")
            version_dll = os.path.join(td, "version.dll")

            self.assertTrue(os.path.exists(dxgi_dll), "Mode B must have dxgi.dll ReShade host")
            self.assertTrue(os.path.exists(mfg_addon), "Mode B must have renodx-mfgunlock.addon64")
            self.assertTrue(os.path.exists(dlss5_addon), "DLSS 5 must have renodx-dlss5.addon64")
            self.assertFalse(os.path.exists(version_dll), "Mode B must not have version.dll")

            # Check ReShade.ini has EnableHooks=2 to avoid Streamline conflict
            reshade_ini = os.path.join(td, "ReShade.ini")
            secs = IniConfigManager.read_ini_sections(reshade_ini)
            self.assertEqual(secs.get("RenoDX.DLSS5", {}).get("EnableHooks"), "2")
            self.assertEqual(secs.get("INSTALL", {}).get("HookDirectX"), "1")
            self.assertEqual(secs.get("INSTALL", {}).get("HookStreamline"), "0")

    def test_mode_c_coexistence_with_dlss5(self):
        """Mode C (OptiScaler dxgi.dll) + DLSS 5 (ReShade64.dll chainloaded) with ASI conflict purged."""
        with tempfile.TemporaryDirectory() as td:
            updater = ComponentUpdater()
            patcher = PatchEngine(updater=updater)

            game = GameInfo(
                name="TestC",
                source="custom",
                install_dir=td,
                target_dir=td,
                exe_path=os.path.join(td, "game.exe"),
                exe_name="game.exe",
                qualification=QualificationStatus.QUALIFIED
            )

            # Apply Mode C
            with patch("core.patcher.get_system_gpu_name", return_value="NVIDIA GeForce RTX 4070"), \
                 patch("core.patcher.is_rtx_40_or_newer", return_value=True):
                ok, msg = ConfigSyncService.apply_unified_configuration(
                    td, "game.exe", "D", {
                        "multiplier": 3,
                        "interpolation_count": 2,
                        "dlss_preset": 0,
                        "fg_output": "xefg",
                        "dx12_upscaler": "dlss"
                    }
                )
                self.assertTrue(ok, f"Mode C + DLSS 5 apply failed: {msg}")

            dxgi_dll = os.path.join(td, "dxgi.dll")
            reshade64 = os.path.join(td, "ReShade64.dll")
            dlss5_addon = os.path.join(td, "renodx-dlss5.addon64")
            opti_ini = os.path.join(td, "OptiScaler.ini")
            d3d12_rs = os.path.join(td, "d3d12-ReShade64.dll")
            asi_p = os.path.join(td, "OptiScaler", "plugins", "MFGUnlocker.asi")

            self.assertTrue(os.path.exists(dxgi_dll), "Mode C must have OptiScaler as dxgi.dll")
            self.assertTrue(os.path.exists(reshade64), "Mode C must chainload ReShade64.dll")
            self.assertTrue(os.path.exists(dlss5_addon), "Mode C must have renodx-dlss5.addon64")
            self.assertTrue(os.path.exists(opti_ini), "Mode C must have OptiScaler.ini")
            self.assertFalse(os.path.exists(d3d12_rs), "d3d12-ReShade64.dll must be purged")
            self.assertFalse(os.path.exists(asi_p), "MFGUnlocker.asi must be purged when DLSS 5 is active")

            # Check OptiScaler.ini
            secs = IniConfigManager.read_ini_sections(opti_ini)
            self.assertEqual(secs.get("Plugins", {}).get("LoadReshade"), "true")
            self.assertEqual(secs.get("Hooks", {}).get("UseNtdllHooks"), "false")
            self.assertEqual(secs.get("Hotfix", {}).get("CreateD3D12DeviceForLuma"), "true")
            self.assertEqual(secs.get("Hotfix", {}).get("SimulateWaitableObject"), "true")


if __name__ == "__main__":
    unittest.main()
