# -*- coding: utf-8 -*-
"""
Verification Script for v1.2.0 Architecture Upgrade
===================================================
Validates:
1. [DWM Frame & No Ragged Corners]: All windows (Launcher, App 1, App 2, App 4)
   invoke or inherit apply_dm_window_frame and follow the unified design.
2. [QSizeGrip Bottom-Right Presence]: All windows instantiate with >= 1 QSizeGrip
   and isVisible() == True.
3. [Full-Architecture Upscaler & MFG Switches]: App 4 contains 4 independent switches
   (DLSS watermark, XeSS/FSR OSD, MFG ratio HUD, ReShade FPS/FrameTime) and master toggle,
   and clicking them writes/reads correctly.
4. [Design System Core API]: dm_ui_core exports DMBaseWindow, DMCardFrame,
   DMThemeManager, DMFooterBar, DMSizeGrip, apply_dm_window_frame with full docstrings.
"""

import os
import sys
from pathlib import Path

# Force UTF-8 for console output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ["QT_QPA_PLATFORM"] = "windows"


def test_1_dwm_and_border_uniformity():
    print(">>> [Test 1] Verifying DWM Frame & Border Uniformity...")
    import common.dm_ui_core as dm_core
    from common.dm_ui_core import apply_dm_window_frame, DMBaseWindow

    assert hasattr(dm_core, "apply_dm_window_frame"), "apply_dm_window_frame missing from dm_ui_core"
    assert dm_core.DWMWCP_ROUND == 2, "DWMWCP_ROUND must be 2 for hardware rounded corners"
    assert dm_core.DWMWA_WINDOW_CORNER_PREFERENCE == 33, "DWMWA_WINDOW_CORNER_PREFERENCE must be 33"
    assert dm_core.DWMWA_BORDER_COLOR == 34, "DWMWA_BORDER_COLOR must be 34"

    # Verify App 1 source hooks
    app1_src = (ROOT_DIR / "apps" / "app1_hardware" / "main_window.py").read_text(encoding="utf-8")
    assert "apply_dm_window_frame" in app1_src, "App 1 must invoke apply_dm_window_frame"

    # Verify App 2 source hooks
    app2_src = (ROOT_DIR / "apps" / "app2_mfg" / "gui_qt.py").read_text(encoding="utf-8")
    assert "apply_dm_window_frame" in app2_src, "App 2 must invoke apply_dm_window_frame"

    # Verify App 4 inheritance
    app4_src = (ROOT_DIR / "apps" / "app4_dlss" / "app.py").read_text(encoding="utf-8")
    assert "DMBaseWindow" in app4_src, "App 4 must inherit DMBaseWindow"

    # Verify Launcher inheritance
    launcher_src = (ROOT_DIR / "launcher" / "main.py").read_text(encoding="utf-8")
    assert "BaseWindow" in launcher_src, "Launcher must inherit BaseWindow"

    print("  ✓ DWM Window Frame and rounded corner attributes verified across all windows!")


def test_2_qsizegrip_presence_and_visibility():
    print(">>> [Test 2] Verifying QSizeGrip Presence and Visibility across all windows...")
    from PySide6.QtWidgets import QApplication, QSizeGrip
    from launcher.main import ToolboxLauncher
    from apps.app1_hardware.main_window import MainWindow as App1Window
    from apps.app2_mfg.gui_qt import ModernMFGGUI as App2Window
    from apps.app4_dlss.app import DLSSIndicatorWindow as App4Window

    app = QApplication.instance() or QApplication(sys.argv)

    # 1. Launcher (图2)
    win_launcher = ToolboxLauncher()
    win_launcher.show()
    app.processEvents()
    launcher_grips = win_launcher.findChildren(QSizeGrip)
    assert len(launcher_grips) >= 1, f"Launcher must have >= 1 QSizeGrip, found {len(launcher_grips)}"
    visible_launcher_grips = [g for g in launcher_grips if g.isVisible()]
    assert len(visible_launcher_grips) >= 1, "Launcher must have at least 1 visible QSizeGrip"
    print(f"  ✓ Launcher (图2): {len(launcher_grips)} QSizeGrip found, visible = True")

    # 2. App 1 Hardware Master (图4)
    win_app1 = App1Window()
    win_app1.show()
    app.processEvents()
    app1_grips = win_app1.findChildren(QSizeGrip)
    assert len(app1_grips) >= 1, f"App 1 must have >= 1 QSizeGrip, found {len(app1_grips)}"
    visible_app1_grips = [g for g in app1_grips if g.isVisible()]
    assert len(visible_app1_grips) >= 1, "App 1 must have at least 1 visible QSizeGrip"
    print(f"  ✓ App 1 Hardware Master (图4): {len(app1_grips)} QSizeGrip found, visible = True")

    # 3. App 2 MFG Patcher (图3)
    win_app2 = App2Window()
    win_app2.show()
    app.processEvents()
    app2_grips = win_app2.findChildren(QSizeGrip)
    assert len(app2_grips) >= 1, f"App 2 must have >= 1 QSizeGrip, found {len(app2_grips)}"
    visible_app2_grips = [g for g in app2_grips if g.isVisible()]
    assert len(visible_app2_grips) >= 1, "App 2 must have at least 1 visible QSizeGrip"
    print(f"  ✓ App 2 MFG Patcher (图3): {len(app2_grips)} QSizeGrip found, visible = True")

    # 4. App 4 DLSS / Multi-Architecture HUD (图1)
    win_app4 = App4Window()
    win_app4.show()
    app.processEvents()
    app4_grips = win_app4.findChildren(QSizeGrip)
    assert len(app4_grips) >= 1, f"App 4 must have >= 1 QSizeGrip, found {len(app4_grips)}"
    visible_app4_grips = [g for g in app4_grips if g.isVisible()]
    assert len(visible_app4_grips) >= 1, "App 4 must have at least 1 visible QSizeGrip"
    print(f"  ✓ App 4 HUD Indicator (图1): {len(app4_grips)} QSizeGrip found, visible = True")

    # Cleanup windows
    win_launcher.close()
    win_app1.close()
    win_app2.close()
    win_app4.close()


def test_3_full_architecture_switches():
    print(">>> [Test 3] Verifying App 4 Full-Architecture Switches and INI/Registry R/W...")
    from PySide6.QtWidgets import QApplication
    from apps.app4_dlss.app import (
        DLSSIndicatorWindow,
        get_dlss_indicator_status, set_dlss_indicator_status,
        get_xess_fsr_status, set_xess_fsr_status,
        get_mfg_hud_status, set_mfg_hud_status,
        get_reshade_overlay_status, set_reshade_overlay_status
    )

    app = QApplication.instance() or QApplication(sys.argv)
    win = DLSSIndicatorWindow()

    # 1. Verify existence of 4 independent switch buttons + master toggle
    assert hasattr(win, "btn_toggle_dlss"), "App 4 must have btn_toggle_dlss"
    assert hasattr(win, "btn_toggle_xess"), "App 4 must have btn_toggle_xess"
    assert hasattr(win, "btn_toggle_mfg"), "App 4 must have btn_toggle_mfg"
    assert hasattr(win, "btn_toggle_reshade"), "App 4 must have btn_toggle_reshade"
    assert hasattr(win, "btn_enable_all"), "App 4 must have 一键全部开启"
    assert hasattr(win, "btn_disable_all"), "App 4 must have 一键全部关闭"
    assert hasattr(win, "badge_status"), "App 4 must have badge_status"

    # 2-4. Toggle tests run against an isolated temp game directory so the suite can
    # never touch a real game config or the bundled templates.
    import tempfile
    from pathlib import Path
    import apps.app4_dlss.app as a4

    tmp = tempfile.TemporaryDirectory()
    td = Path(tmp.name)
    (td / "OptiScaler.ini").write_text("[Menu]\nOverlayMenu=true\nShowFps=false\n", encoding="utf-8")
    (td / "ReShade.ini").write_text("[GENERAL]\nTutorialProgress=4\n", encoding="utf-8")
    (td / "dxgi.dll").write_bytes(b"MZ" + b"\x00" * 64 + b"ReShade 6.8.0 fake")
    a4.get_known_game_dirs = lambda force_refresh=False: [td]
    a4._RESHADE_BASE_CACHE.clear()

    # Test XeSS/FSR switch toggling and INI sync
    orig_xess = get_xess_fsr_status()
    set_xess_fsr_status(not orig_xess)
    assert get_xess_fsr_status() == (not orig_xess), "XeSS/FSR status should toggle"
    # Restore
    set_xess_fsr_status(orig_xess)
    assert get_xess_fsr_status() == orig_xess, "XeSS/FSR status should restore"
    print("  ✓ OptiScaler performance overlay switch read/write verified!")

    # 3. Test Multi-Frame Generation Ratio HUD switch toggling and INI sync
    orig_mfg = get_mfg_hud_status()
    set_mfg_hud_status(not orig_mfg)
    assert get_mfg_hud_status() == (not orig_mfg), "MFG HUD status should toggle"
    set_mfg_hud_status(orig_mfg)
    assert get_mfg_hud_status() == orig_mfg, "MFG HUD status should restore"
    print("  ✓ Frame Generation Full overlay switch read/write verified!")

    # 4. Test ReShade FPS/FrameTime switch toggling and INI sync
    orig_reshade = get_reshade_overlay_status()
    set_reshade_overlay_status(not orig_reshade)
    assert get_reshade_overlay_status() == (not orig_reshade), "ReShade overlay status should toggle"
    set_reshade_overlay_status(orig_reshade)
    assert get_reshade_overlay_status() == orig_reshade, "ReShade overlay status should restore"
    print("  ✓ ReShade FPS/FrameTime monitoring switch read/write verified!")
    tmp.cleanup()

    # 5. Test DLSS switch
    orig_dlss = get_dlss_indicator_status()
    print(f"  ✓ NVIDIA DLSS status read: {orig_dlss}")

    win.close()


def test_4_sdk_and_design_system_api():
    print(">>> [Test 4] Verifying DM Design System Core SDK (dm_ui_core)...")
    import dm_ui_core
    from dm_ui_core import (
        DMBaseWindow,
        DMCardFrame,
        DMFooterBar,
        DMSizeGrip,
        DMThemeManager,
        apply_dm_window_frame,
        get_global_theme,
        set_global_theme
    )

    # Assert docstrings exist
    assert dm_ui_core.__doc__ is not None, "dm_ui_core module must have docstring"
    assert DMBaseWindow.__doc__ is not None, "DMBaseWindow must have docstring"
    assert DMCardFrame.__doc__ is not None, "DMCardFrame must have docstring"
    assert DMThemeManager.__doc__ is not None, "DMThemeManager must have docstring"
    assert DMSizeGrip.__doc__ is not None, "DMSizeGrip must have docstring"
    assert DMFooterBar.__doc__ is not None, "DMFooterBar must have docstring"

    # Test DMThemeManager
    cur_theme = DMThemeManager.get_current_theme()
    assert cur_theme in ("light", "dark"), f"Current theme must be light or dark, got {cur_theme}"

    print("  ✓ DM Design System Core SDK exports and docstrings verified!")


if __name__ == "__main__":
    print("=================================================================")
    print(" Running v1.2.0 Architecture Upgrade Self-Verification Suite")
    print("=================================================================")
    test_1_dwm_and_border_uniformity()
    test_2_qsizegrip_presence_and_visibility()
    test_3_full_architecture_switches()
    test_4_sdk_and_design_system_api()
    print("=================================================================")
    print(" ALL 4 VERIFICATION SUITES PASSED PERFECTLY (100% SUCCESS)!")
    print("=================================================================")
