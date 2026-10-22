# -*- coding: utf-8 -*-
"""
DM-Toolbox v1.3.8: DLSS 5 window assets / layout guards.

The window used to be clipped horizontally because a handful of unwrapped
labels (subtitle, arch radios, guidance block, long paths) pushed the scroll
content to ~1660px. These tests pin the two user-visible regressions:

  1. the shipped DLSS 5 icon must be a real 512px PNG (+ multi-size ICO),
     not a text file renamed to .png;
  2. long Windows paths must be soft-wrappable so they cannot force the
     window wider than the screen.
"""

import io
import sys
from pathlib import Path

from PIL import Image

ROOT_DIR = Path(__file__).resolve().parent.parent
for p in (ROOT_DIR, ROOT_DIR / "apps" / "app2_mfg"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def test_dlss5_icon_is_a_valid_image():
    print("\n--- Test 1: [DLSS 5 图标资产有效性] ---")
    for rel in ("common/assets/dlss5_icon.png", "apps/app6_dlss5/assets/dlss5_icon.png"):
        path = ROOT_DIR / rel
        assert path.is_file(), f"missing icon: {rel}"
        assert path.stat().st_size > 8 * 1024, f"icon too small: {rel}"
        with Image.open(path) as im:
            assert im.format == "PNG", f"{rel} is not a PNG (header {im.format})"
            assert im.size == (512, 512), f"{rel} should be 512x512, got {im.size}"
            assert im.mode == "RGBA"

    ico = ROOT_DIR / "common/assets/dlss5_icon.ico"
    assert ico.is_file(), "common/assets/dlss5_icon.ico missing (window icon uses it)"
    with Image.open(ico) as im:
        assert im.format == "ICO"
        sizes = getattr(im, "ico", None)
        print("   ico sizes:", sizes.sizes() if sizes else "?")
        assert sizes and (256, 256) in sizes.sizes(), "ICO must contain a 256px frame"
    print("   [PASS] PNG 512x512 + 多尺寸 ICO 均为有效图像")


def test_long_paths_are_soft_wrappable():
    print("\n--- Test 2: [长路径可换行] ---")
    try:
        from apps.app6_dlss5.app import _soft_wrap_path
    except Exception as exc:  # pragma: no cover - headless without PySide6
        print("   SKIP (PySide6 unavailable):", exc)
        return

    path = r"D:\game\yysls\yysls_medium\Engine\Binaries\Win64r\yysls.exe"
    wrapped = _soft_wrap_path(path)
    assert wrapped.count("\u200b") == path.count("\\"), "every separator needs a break opportunity"
    assert wrapped.replace("\u200b", "") == path, "soft wrap must not alter the visible path"
    print("   [PASS] 路径在每个反斜杠后可断行，且不改变实际字符")


def test_footer_grows_for_action_buttons():
    print("\n--- Test 3: [底栏为操作按钮留出边距] ---")
    try:
        from PySide6.QtWidgets import QApplication, QPushButton

        from common.dm_ui_core import DMFooterBar
    except Exception as exc:  # pragma: no cover - headless without PySide6
        print("   SKIP (PySide6 unavailable):", exc)
        return

    app = QApplication.instance() or QApplication([])
    bar = DMFooterBar(None)
    assert bar.height() == 32, "status-only footer keeps its compact 32px height"

    btn = QPushButton("一键注入")
    btn.setFixedHeight(34)  # same as the DLSS 5 footer buttons
    bar.add_action_widget(btn)

    # 34px button + at least 10px of vertical padding, and a real bottom margin
    assert bar.height() >= 34 + 10, f"footer must grow for 34px buttons, got {bar.height()}"
    margins = bar.root_layout.contentsMargins()
    assert margins.bottom() >= 8, f"bottom margin too small: {margins.bottom()}"
    assert margins.top() >= 4
    print(f"   [PASS] 底栏高度 {bar.height()}px，按钮下方留白 {margins.bottom()}px")


if __name__ == "__main__":
    test_dlss5_icon_is_a_valid_image()
    test_long_paths_are_soft_wrappable()
    test_footer_grows_for_action_buttons()
    print("\nALL DLSS5 UI ASSET TESTS PASSED")
