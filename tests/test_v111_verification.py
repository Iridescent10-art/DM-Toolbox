# -*- coding: utf-8 -*-
"""
Verification script for v1.1.1 UI & Logic bug fixes in DM-Toolbox (app2_mfg).
Checks:
1. Entrance card boxes style (border, background, height >= 40px)
2. Tab order A -> B -> C and 3 tabs completeness
3. Mode auto-detection and activation marker
4. Tab click switching and page visibility
5. Initial zero-deformation (all combos width >= 260, height >= 34)
Outputs "ALL 5 UI & LOGIC CHECKS PASSED!" upon successful verification.
"""

import os
import sys
from pathlib import Path

# Set offscreen if headless environment
if "QT_QPA_PLATFORM" not in os.environ:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

sys.stdout.reconfigure(encoding="utf-8")

# Add paths
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir / "apps" / "app2_mfg"))
sys.path.insert(0, str(root_dir))

from PySide6.QtWidgets import QApplication, QFrame, QComboBox
from PySide6.QtCore import Qt, QTimer
from gui_qt import ModernMFGGUI, OptiScalerPresetDialog

def run_tests():
    app = QApplication.instance() or QApplication(sys.argv)

    print("=== STARTING V1.1.1 AUTOMATED VERIFICATION ===")

    # -------------------------------------------------------------
    # CHECK 1: Entrance Card Boxes Style
    # -------------------------------------------------------------
    print("\n--- Running Check 1: Entrance Card Boxes Style ---")
    win = ModernMFGGUI()
    win.show()
    app.processEvents()

    for card_name in ["card_bink", "card_guide", "card_preset"]:
        assert hasattr(win, card_name), f"Check 1 Failed: Main window missing attribute '{card_name}'"
        card = getattr(win, card_name)
        assert isinstance(card, QFrame), f"Check 1 Failed: '{card_name}' must be an instance of QFrame, got {type(card)}"
        
        qss = card.styleSheet().lower()
        assert "border" in qss, f"Check 1 Failed: '{card_name}' styleSheet must define 'border'. Current: {card.styleSheet()}"
        assert "background" in qss, f"Check 1 Failed: '{card_name}' styleSheet must define 'background'. Current: {card.styleSheet()}"
        
        effective_height = max(card.height(), card.minimumHeight())
        assert effective_height >= 40, f"Check 1 Failed: '{card_name}' height must be >= 40px, got {effective_height}px"
        print(f"  [PASS] {card_name}: QFrame with border, background, and height={effective_height}px >= 40px")

    print("[SUCCESS] Check 1 passed: All entrance cards conform to container specifications!")

    # -------------------------------------------------------------
    # CHECK 2: Tab Order A -> B -> C and Completeness
    # -------------------------------------------------------------
    print("\n--- Running Check 2: Tab Order A -> B -> C and Completeness ---")
    dlg = OptiScalerPresetDialog(initial_mode="A")
    dlg.show()
    app.processEvents()

    # Tab count
    tab_count = dlg.stacked_widget.count()
    btn_count = len(dlg.tab_buttons)
    assert tab_count == 3, f"Check 2 Failed: stacked_widget tab count must be 3, got {tab_count}"
    assert btn_count == 3, f"Check 2 Failed: tab buttons count must be 3, got {btn_count}"

    btn_texts = [btn.text() for btn in dlg.tab_buttons]
    print(f"  Detected Tab Titles: {btn_texts}")

    assert "模式 A" in btn_texts[0], f"Check 2 Failed: Tab 0 title must contain '模式 A', got '{btn_texts[0]}'"
    assert "模式 B" in btn_texts[1], f"Check 2 Failed: Tab 1 title must contain '模式 B', got '{btn_texts[1]}'"
    assert "模式 C" in btn_texts[2], f"Check 2 Failed: Tab 2 title must contain '模式 C', got '{btn_texts[2]}'"

    # Mode A controls check
    assert hasattr(dlg, "combo_a_mult"), "Check 2 Failed: Mode A missing multiplier combo"
    assert hasattr(dlg, "combo_a_preset"), "Check 2 Failed: Mode A missing DLSS preset combo"
    assert hasattr(dlg, "combo_a_key"), "Check 2 Failed: Mode A missing hotkey combo"
    assert hasattr(dlg, "chk_a_bink"), "Check 2 Failed: Mode A missing bink hook checkbox"

    print("[SUCCESS] Check 2 passed: Tabs strictly ordered A -> B -> C with full Mode A parameters!")

    # -------------------------------------------------------------
    # CHECK 3: Mode Auto-Detection & Jump
    # -------------------------------------------------------------
    print("\n--- Running Check 3: Mode Auto-Detection & Jump ---")
    test_cases = [
        ("A", 0, "模式 A"),
        ("B", 1, "模式 B"),
        ("C", 2, "模式 C"),
    ]

    for mode_str, expected_idx, label in test_cases:
        # Test with named parameter
        dlg_named = OptiScalerPresetDialog(initial_mode=mode_str)
        dlg_named.show()
        app.processEvents()
        idx_named = dlg_named.stacked_widget.currentIndex()
        assert idx_named == expected_idx, f"Check 3 Failed: initial_mode='{mode_str}' gave index {idx_named}, expected {expected_idx}"
        assert "当前正在使用该模式" in dlg_named.tab_buttons[expected_idx].toolTip() or "当前使用" in dlg_named.tab_buttons[expected_idx].text(), f"Check 3 Failed: expected active marker on tab {expected_idx}"

        # Test with positional parameter (OptiScalerPresetDialog("A"))
        dlg_pos = OptiScalerPresetDialog(mode_str)
        dlg_pos.show()
        app.processEvents()
        idx_pos = dlg_pos.stacked_widget.currentIndex()
        assert idx_pos == expected_idx, f"Check 3 Failed: positional arg '{mode_str}' gave index {idx_pos}, expected {expected_idx}"

        print(f"  [PASS] Mode '{mode_str}' correctly auto-detected and navigated to Tab {expected_idx} ({label})")

    print("[SUCCESS] Check 3 passed: Mode auto-detection and active marker working flawlessly!")

    # -------------------------------------------------------------
    # CHECK 4: Tab Click Switching & Page Visibility
    # -------------------------------------------------------------
    print("\n--- Running Check 4: Tab Click Switching & Page Visibility ---")
    test_dlg = OptiScalerPresetDialog(initial_mode="A")
    test_dlg.show()
    app.processEvents()

    click_sequence = [1, 2, 0, 1, 0, 2]
    for target_idx in click_sequence:
        btn = test_dlg.tab_buttons[target_idx]
        btn.click()
        app.processEvents()

        curr_idx = test_dlg.stacked_widget.currentIndex()
        curr_page = test_dlg.stacked_widget.currentWidget()
        assert curr_idx == target_idx, f"Check 4 Failed: After clicking tab {target_idx}, currentIndex is {curr_idx}"
        assert curr_page.isVisible(), f"Check 4 Failed: Page {target_idx} is not visible after switching"
        assert btn.isChecked(), f"Check 4 Failed: Button {target_idx} should be checked"
        print(f"  [PASS] Clicked Tab {target_idx} -> StackedWidget Index = {curr_idx}, Page isVisible = True")

    print("[SUCCESS] Check 4 passed: Tab clicking triggers instant mutual-exclusive page switching!")

    # -------------------------------------------------------------
    # CHECK 5: Initial Zero-Deformation (No Dragging Needed)
    # -------------------------------------------------------------
    print("\n--- Running Check 5: Initial Zero-Deformation (No Dragging Needed) ---")
    deform_dlg = OptiScalerPresetDialog(initial_mode="A")
    deform_dlg.show()
    app.processEvents()

    combos = deform_dlg.findChildren(QComboBox)
    assert len(combos) >= 8, f"Check 5 Failed: Expected at least 8 QComboBox controls across all tabs, found {len(combos)}"

    for i, cb in enumerate(combos):
        w = cb.width()
        h = cb.height()
        min_w = cb.minimumWidth()
        min_h = cb.minimumHeight()
        assert h >= 34, f"Check 5 Failed: Combo {i} height {h}px < 34px! (min_h={min_h})"
        assert w >= 260, f"Check 5 Failed: Combo {i} width {w}px < 260px! (min_w={min_w})"
        print(f"  [PASS] Combo {i} ({cb.objectName() or 'unnamed'}): width={w}px >= 260px, height={h}px >= 34px")

    # Render screenshots for verification records
    artifact_dir = Path(r"C:\Users\17547\.gemini\antigravity\brain\f20364b0-8af4-45b1-a8b6-b621a086cb69")
    if artifact_dir.exists():
        # Save Tab 0 Mode A screenshot
        deform_dlg.switch_preset_tab(0)
        app.processEvents()
        deform_dlg.grab().save(str(artifact_dir / "verification_preset_tab_a.png"))

        # Save Tab 1 Mode B screenshot
        deform_dlg.switch_preset_tab(1)
        app.processEvents()
        deform_dlg.grab().save(str(artifact_dir / "verification_preset_tab_b.png"))

        # Save Tab 2 Mode C screenshot
        deform_dlg.switch_preset_tab(2)
        app.processEvents()
        deform_dlg.grab().save(str(artifact_dir / "verification_preset_tab_c.png"))

        # Save Main Window dashboard screenshot
        win.grab().save(str(artifact_dir / "verification_main_window_cards.png"))
        print(f"  [INFO] Verification screenshots saved to: {artifact_dir}")

    deform_dlg.close()
    win.close()

    print("[SUCCESS] Check 5 passed: All combos satisfy minimum width and height constraints on first render!")

    # -------------------------------------------------------------
    # ALL CHECKS PASSED
    # -------------------------------------------------------------
    print("\n" + "=" * 50)
    print("ALL 5 UI & LOGIC CHECKS PASSED!")
    print("=" * 50)

if __name__ == "__main__":
    run_tests()
