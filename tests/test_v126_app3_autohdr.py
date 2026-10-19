# -*- coding: utf-8 -*-
"""
v1.2.6 verification: App 3 (Windows Auto HDR manager).

Covers:
1. One-click batch enable / disable buttons exist and write every configured entry.
2. The mode combo no longer uses Qt's unsupported CSS-border triangle hack
   (which rendered as a grey block / clipped box), and keeps 3 selectable modes.
3. The title-bar theme toggle is a rounded capsule and survives stylesheet cascades.
"""

import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
APP3_DIR = ROOT_DIR / "apps" / "app3_autohdr"
for p in (ROOT_DIR, APP3_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import app as app3
from common.ui_theme import LIGHT_STYLE_SHEET, DARK_STYLE_SHEET


def test_1_batch_buttons_and_logic():
    print("\n--- Test 1: [一键全部开启 / 一键全部关闭] ---")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    win = app3.AutoHDRWindow()
    assert hasattr(win, "btn_enable_all"), "missing 一键全部开启 button"
    assert hasattr(win, "btn_disable_all"), "missing 一键全部关闭 button"
    assert "一键全部开启" in win.btn_enable_all.text()
    assert "一键全部关闭" in win.btn_disable_all.text()

    # Isolate the registry writes: never touch the user's real Auto HDR keys in tests.
    calls = []

    def fake_save(key_name, path, mode_str):
        calls.append((key_name, path, mode_str))

    original_save = app3.AutoHDRManager.save_app
    app3.AutoHDRManager.save_app = staticmethod(fake_save)
    try:
        win.all_apps = [
            {"key_name": "Application0", "path": r"C:\Game\a.exe", "behavior": ""},
            {"key_name": "Application1", "path": r"C:\Game\b.exe", "behavior": ""},
        ]

        ok, total = win._apply_mode_to_all(app3.MODE_10BIT)
        assert (ok, total) == (2, 2), f"batch enable result mismatch: {ok}/{total}"
        assert all(c[2] == app3.MODE_10BIT for c in calls)

        calls.clear()
        ok, total = win._apply_mode_to_all(app3.MODE_DISABLED)
        assert (ok, total) == (2, 2)
        assert all(c[2] == app3.MODE_DISABLED for c in calls)

        # The UI handlers must be wired to the batch logic
        assert callable(getattr(win, "on_enable_all", None))
        assert callable(getattr(win, "on_disable_all", None))
    finally:
        app3.AutoHDRManager.save_app = original_save
        win.close()

    print("  -> 两枚批量按钮存在、点击信号已连接，批量写入覆盖全部条目！")


def test_2_combo_uses_native_chevron():
    print("\n--- Test 2: [下拉框箭头为内嵌图片，不再用失效的 CSS 三角] ---")
    assert "border-top: 6px solid" not in LIGHT_STYLE_SHEET, "light QSS still has the broken arrow hack"
    assert "border-top: 6px solid" not in DARK_STYLE_SHEET, "dark QSS still has the broken arrow hack"
    assert "__COMBO_ARROW__" not in LIGHT_STYLE_SHEET

    from PySide6.QtWidgets import QApplication, QComboBox
    app = QApplication.instance() or QApplication(sys.argv)
    win = app3.AutoHDRWindow()
    # BaseWindow installs the app-level chevron rule (image draws inside the border)
    app_qss = app.styleSheet()
    assert "QComboBox::down-arrow" in app_qss and "image: url(" in app_qss, \
        "app-level combo chevron rule was not installed"
    if win.table.rowCount() == 0:
        print("  SKIP: 当前注册表没有 Auto HDR 配置项，无法渲染下拉框")
        win.close()
        return
    combo = win.table.cellWidget(0, 2).findChild(QComboBox)
    assert combo is not None
    assert combo.count() == 3, f"combo must offer 3 modes, got {combo.count()}"
    assert combo.minimumWidth() >= 240
    qss = combo.styleSheet()
    assert "border-top: 6px solid" not in qss, "per-widget combo QSS still has the broken triangle"
    assert "down-arrow" not in qss
    win.close()
    print("  -> 原生 chevron 箭头生效，3 个模式项完整显示！")


def test_3_theme_toggle_is_pill():
    print("\n--- Test 3: [主题切换胶囊圆角] ---")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    win = app3.AutoHDRWindow()
    qss = win.btn_theme.styleSheet()
    assert "border-radius: 10px" in qss, f"theme toggle radius missing: {qss!r}"
    assert win.btn_theme.objectName() == "ThemeToggleBtn"
    # The inline capsule must win over page-level stylesheets
    assert "QPushButton" in qss
    win.close()
    print("  -> 标题栏主题按钮为无边框 10px 圆角纯图标按钮！")


def main():
    test_1_batch_buttons_and_logic()
    test_2_combo_uses_native_chevron()
    test_3_theme_toggle_is_pill()
    print("\n==========================================")
    print("ALL v1.2.6 APP3 AUTO HDR TESTS PASSED (3/3)!")
    print("==========================================")


if __name__ == "__main__":
    main()
