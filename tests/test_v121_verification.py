# -*- coding: utf-8 -*-
"""
Automated Verification Script for v1.2.1 UI Fixes
=================================================
Validates:
1. [Assertion Zero Horizontal Truncation]:
   - content_widget.width() <= scroll_area.viewport().width()
   - card_xess.geometry().right() <= content_widget.width() - 16
   - card_reshade.geometry().right() <= content_widget.width() - 16
   - Both columns are completely visible within viewport, zero clipping.
2. [Assertion Scrollbar Styled in Theme]:
   - Window or scroll_area.verticalScrollBar().styleSheet() includes:
     "QScrollBar::handle:vertical", "border-radius", "height: 0px"
   - No native retro Windows scrollbar square arrows.
3. [Assertion Bottom Reference Card Fully Scrollable and Visible]:
   - Simulate vertical scroll to maximum (vbar.setValue(vbar.maximum()))
   - Assert bottom reference card is within visible viewport coordinates.
"""

import os
import sys
from pathlib import Path

# Force UTF-8 for console output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ["QT_QPA_PLATFORM"] = "windows"

from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtWidgets import QApplication
from apps.app4_dlss.app import DLSSIndicatorWindow
import dm_ui_core


def run_v121_verification():
    print("=" * 70)
    print(">>> Starting v1.2.1 UI Automated Verification...")
    print("=" * 70)

    app = QApplication.instance() or QApplication(sys.argv)

    # Instantiate App 4 Window (图1：全架构超分与插帧水印指示器)
    win = DLSSIndicatorWindow()
    win.show()
    app.processEvents()

    scroll_area = win.scroll_area
    content_widget = scroll_area.widget()
    vbar = scroll_area.verticalScrollBar()
    viewport = scroll_area.viewport()

    app.processEvents()

    print(f"[*] Window Size: {win.width()}x{win.height()}")
    print(f"[*] Viewport Size: {viewport.width()}x{viewport.height()}")
    print(f"[*] Content Widget Size: {content_widget.width()}x{content_widget.height()}")

    # -------------------------------------------------------------
    # 1. [断言零横向截断]
    # -------------------------------------------------------------
    print("\n>>> [Assertion 1] Verifying Zero Horizontal Truncation...")
    c_w = content_widget.width()
    vp_w = viewport.width()
    assert c_w <= vp_w, (
        f"FAILED: content_widget.width() ({c_w}) > scroll_area.viewport().width() ({vp_w})! "
        f"Horizontal overflow detected!"
    )
    print(f"  ✓ Content widget width ({c_w}px) <= Viewport width ({vp_w}px)")

    card_xess_geom = win.card_xess.geometry()
    card_reshade_geom = win.card_reshade.geometry()
    limit = c_w - 16

    print(f"  [*] XeSS Card right: {card_xess_geom.right()}px (Limit: <= {limit}px)")
    print(f"  [*] ReShade Card right: {card_reshade_geom.right()}px (Limit: <= {limit}px)")

    assert card_xess_geom.right() <= limit, (
        f"FAILED: card_xess.geometry().right() ({card_xess_geom.right()}) > {limit}! Right card clipped!"
    )
    assert card_reshade_geom.right() <= limit, (
        f"FAILED: card_reshade.geometry().right() ({card_reshade_geom.right()}) > {limit}! Right card clipped!"
    )
    print("  ✓ [PASSED] Assertion 1: Zero horizontal truncation on all cards!")

    # -------------------------------------------------------------
    # 2. [断言滚动条样式已写入主题]
    # -------------------------------------------------------------
    print("\n>>> [Assertion 2] Verifying Scrollbar Style in Theme...")
    vbar_qss = vbar.styleSheet()
    scroll_qss = scroll_area.styleSheet()
    win_qss = win.styleSheet()

    combined_qss = f"{win_qss}\n{scroll_qss}\n{vbar_qss}"

    assert "QScrollBar::handle:vertical" in combined_qss, "FAILED: 'QScrollBar::handle:vertical' missing from stylesheets!"
    assert "border-radius" in combined_qss, "FAILED: 'border-radius' missing from scrollbar styles!"
    assert "height: 0px" in combined_qss, "FAILED: 'height: 0px' missing (arrows not hidden)!"

    # Verify both light and dark QSS are in dm_ui_core
    assert hasattr(dm_ui_core, "SCROLLBAR_LIGHT_QSS"), "SCROLLBAR_LIGHT_QSS missing from dm_ui_core"
    assert hasattr(dm_ui_core, "SCROLLBAR_DARK_QSS"), "SCROLLBAR_DARK_QSS missing from dm_ui_core"

    # Verify theme toggle updates scrollbar colors smoothly
    win.is_dark_mode = True
    win.apply_theme()
    app.processEvents()
    dark_vbar_qss = vbar.styleSheet()
    assert "rgba(100, 116, 139" in dark_vbar_qss or "rgba(100, 116, 139" in scroll_area.styleSheet()

    win.is_dark_mode = False
    win.apply_theme()
    app.processEvents()
    light_vbar_qss = vbar.styleSheet()
    assert "rgba(144, 157, 181" in light_vbar_qss or "rgba(144, 157, 181" in scroll_area.styleSheet()

    print("  ✓ [PASSED] Assertion 2: Modern rounded scrollbar styling is actively applied in both light/dark themes!")

    # -------------------------------------------------------------
    # 3. [断言底部速查表可完整滚轮浏览]
    # -------------------------------------------------------------
    print("\n>>> [Assertion 3] Verifying Bottom Reference Card Scrollability...")
    max_scroll = vbar.maximum()
    print(f"  [*] Vertical scrollbar maximum: {max_scroll}")
    assert max_scroll > 0, "FAILED: Scrollbar has no scroll range (maximum == 0)!"

    vbar.setValue(max_scroll)
    app.processEvents()

    # Map ref_card to viewport coordinates
    ref_card = win.ref_card
    ref_pt_in_vp = ref_card.mapTo(viewport, QPoint(0, 0))
    ref_rect_in_vp = QRect(ref_pt_in_vp, ref_card.size())

    print(f"  [*] Ref Card top in viewport: {ref_rect_in_vp.top()}px")
    print(f"  [*] Ref Card bottom in viewport: {ref_rect_in_vp.bottom()}px")
    print(f"  [*] Viewport height: {viewport.height()}px")

    # Bottom edge of ref_card should be inside viewport (allowing small bottom margin)
    assert ref_rect_in_vp.bottom() <= viewport.height() + 5, (
        f"FAILED: Bottom reference card is cut off! bottom={ref_rect_in_vp.bottom()} > viewport={viewport.height()}"
    )
    assert ref_rect_in_vp.top() < viewport.height(), "FAILED: Bottom reference card is not visible!"

    print("  ✓ [PASSED] Assertion 3: Bottom reference card is fully scrollable and completely visible!")

    win.close()
    print("\n" + "=" * 70)
    print(">>> ALL v1.2.1 VERIFICATION ASSERTIONS PASSED (3/3 100%)!")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = run_v121_verification()
    sys.exit(0 if success else 1)
