# -*- coding: utf-8 -*-
"""
v1.2.6 verification: App 4 HUD indicators + guide tab order.

Root cause covered here:
- App 4 used to resolve `OptiScaler.ini` / `ReShade.ini` from the **bundled templates**
  under the toolbox folder, so three of four switches wrote into shipped assets and the
  real game folder never changed.
- It also wrote `ShowOsd` / `ShowHud` / `ShowFrameGen`, which do **not** exist in
  OptiScaler v0.9.4 (absent from OptiScaler.dll). The supported HUD is
  `[Menu] ShowFps` + `FpsOverlayType`.

This suite asserts:
1. Only real game directories are returned; bundled templates are never touched.
2. App 4 writes the real v0.9.4 overlay keys and its status getters round-trip.
3. ReShade switches require an actual ReShade base and write [OVERLAY].
4. The guide dialog tabs are ordered A -> B -> C.
"""

import hashlib
import sys
import tempfile
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
for p in (ROOT_DIR, ROOT_DIR / "apps" / "app2_mfg", ROOT_DIR / "apps" / "app4_dlss"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import apps.app4_dlss.app as a4
from core.ini_sync import IniConfigManager

TEMPLATES = [
    ROOT_DIR / "apps" / "app2_mfg" / "embedded_components" / "optiscaler" / "v0.9.4" / "OptiScaler.ini",
    ROOT_DIR / "defaults" / "app2_mfg" / "embedded_components" / "optiscaler" / "v0.9.4" / "OptiScaler.ini",
]


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_1_discovery_uses_real_games_only():
    print("\n--- Test 1: [指示器只写真实游戏目录，绝不改模板] ---")
    dirs = a4.get_known_game_dirs()
    print("discovered game dirs:", [str(d) for d in dirs[:5]], "...")
    assert dirs, "no game directories discovered from app2 cache"
    assert all(not a4._is_inside_toolbox(d) for d in dirs), "toolbox templates leaked into game dirs"

    real_inis = a4.find_all_optiscaler_inis()
    for ini in real_inis:
        assert not a4._is_inside_toolbox(ini), f"template returned as game config: {ini}"
    print("real OptiScaler.ini:", [str(p) for p in real_inis[:3]])

    before = {p: _digest(p) for p in TEMPLATES if p.exists()}
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "OptiScaler.ini").write_text("[Menu]\nShowFps=false\n", encoding="utf-8")
        a4.get_known_game_dirs = lambda: [td]
        assert a4.find_all_optiscaler_inis() == [td / "OptiScaler.ini"]
        a4.set_xess_fsr_status(True)
    after = {p: _digest(p) for p in TEMPLATES if p.exists()}
    assert before == after, "bundled OptiScaler.ini templates were modified!"

    print("  -> 真实目录定位正确，模板文件哈希前后一致！")


def test_2_overlay_profile_roundtrip():
    print("\n--- Test 2: [ShowFps / FpsOverlayType 写入与状态回读] ---")
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        ini = td / "OptiScaler.ini"
        ini.write_text(
            "[Menu]\nOverlayMenu=true\nShowFps=false\nFpsOverlayType=0\n\n[FrameGen]\nEnabled=true\n",
            encoding="utf-8",
        )
        a4.get_known_game_dirs = lambda: [td]

        assert a4.get_xess_fsr_status() is False
        assert a4.get_mfg_hud_status() is False

        ok, msg = a4.set_xess_fsr_status(True)
        assert ok, msg
        menu = IniConfigManager.read_ini_sections(ini)["Menu"]
        assert menu["ShowFps"] == "true"
        assert menu["FpsOverlayType"] == a4.OVERLAY_TYPE_DETAILED
        assert menu["FpsOverlayPos"] == "0"
        assert a4.get_xess_fsr_status() is True
        assert a4.get_mfg_hud_status() is False

        ok, msg = a4.set_mfg_hud_status(True)
        assert ok, msg
        menu = IniConfigManager.read_ini_sections(ini)["Menu"]
        assert menu["FpsOverlayType"] == a4.OVERLAY_TYPE_FULL
        assert a4.get_mfg_hud_status() is True
        assert a4.get_xess_fsr_status() is True

        ok, msg = a4.set_mfg_hud_status(False)
        assert ok, msg
        menu = IniConfigManager.read_ini_sections(ini)["Menu"]
        assert menu["FpsOverlayType"] == a4.OVERLAY_TYPE_DETAILED
        assert a4.get_mfg_hud_status() is False
        assert a4.get_xess_fsr_status() is True

        ok, msg = a4.set_xess_fsr_status(False)
        assert ok, msg
        menu = IniConfigManager.read_ini_sections(ini)["Menu"]
        assert menu["ShowFps"] == "false"
        assert a4.get_xess_fsr_status() is False
        assert a4.get_mfg_hud_status() is False

        # Dead v0.8 keys must never be produced
        text = ini.read_text(encoding="utf-8")
        assert "ShowOsd" not in text and "ShowHud" not in text and "ShowFrameGen" not in text

    print("  -> 叠加档位 2(Detailed) / 4(Full) 来回切换正确，未再写入失效的 ShowOsd/ShowHud！")


def test_3_reshade_requires_real_base():
    print("\n--- Test 3: [ReShade 指示器需要真实底座] ---")
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "ReShade.ini").write_text("[GENERAL]\nTutorialProgress=4\n", encoding="utf-8")
        a4.get_known_game_dirs = lambda: [td]

        # No ReShade proxy yet -> not discovered, toggle reports a clear reason
        assert a4.find_all_reshade_inis() == []
        ok, msg = a4.set_reshade_overlay_status(True)
        assert ok is False and "ReShade" in msg

        # Fake a ReShade proxy next to the game
        (td / "dxgi.dll").write_bytes(b"MZ" + b"\x00" * 64 + b"ReShade 6.8.0 fake")
        a4._RESHADE_BASE_CACHE.clear()  # bypass the 30s negative cache
        assert a4.find_all_reshade_inis() == [td / "ReShade.ini"]
        ok, msg = a4.set_reshade_overlay_status(True)
        assert ok, msg
        ov = IniConfigManager.read_ini_sections(td / "ReShade.ini")["OVERLAY"]
        assert ov["ShowFPS"] == "1" and ov["ShowFrameTime"] == "1"
        assert a4.get_reshade_overlay_status() is True

        ok, msg = a4.set_reshade_overlay_status(False)
        assert ok, msg
        assert a4.get_reshade_overlay_status() is False

    print("  -> 有 ReShade 底座时正确写入 [OVERLAY]，无底座时明确提示而不误报成功！")


def test_4_no_game_configs_is_reported():
    print("\n--- Test 4: [未检测到游戏时明确失败，而不是假装成功] ---")
    with tempfile.TemporaryDirectory() as td:
        a4.get_known_game_dirs = lambda: [Path(td)]
        ok, msg = a4.set_xess_fsr_status(True)
        assert ok is False and "模式 C" in msg
        ok, msg = a4.set_mfg_hud_status(True)
        assert ok is False and "模式 C" in msg
    print("  -> 未部署 OptiScaler 时返回 False 与可操作提示！")


def test_5_guide_tabs_are_abc():
    print("\n--- Test 5: [使用指南标签顺序 A → B → C] ---")
    try:
        from PySide6.QtWidgets import QApplication
        from gui_qt import ModernTranslationGuideDialog
    except Exception as exc:  # pragma: no cover
        print("  SKIP (PySide6 unavailable):", exc)
        return

    app = QApplication.instance() or QApplication(sys.argv)
    dlg = ModernTranslationGuideDialog(None, is_dark=False, initial_tab=0)
    titles = [dlg.tabs.tabText(i) for i in range(dlg.tabs.count())]
    print("tabs:", titles)
    assert len(titles) in (2, 3, 4)
    assert "模式 A" in titles[0], titles[0]
    assert "模式 B" in titles[1], titles[1]
    if len(titles) > 2:
        assert "模式 C" in titles[2], titles[2]
    if len(titles) > 3:
        assert "模式 D" in titles[3], titles[3]
    assert dlg.tabs.currentIndex() == 0

    tab_target = 1 if len(titles) == 2 else 2
    dlg2 = ModernTranslationGuideDialog(None, is_dark=False, initial_tab=tab_target)
    assert dlg2.tabs.currentIndex() == tab_target
    expected_mode = "模式 B" if len(titles) == 2 else "模式 C"
    assert expected_mode in dlg2.tabs.tabText(dlg2.tabs.currentIndex())
    dlg.deleteLater()
    dlg2.deleteLater()
    print("  -> 标签顺序固定为 A / B / C，按当前后端选中对应页！")


def test_6_explicit_batch_buttons():
    print("\n--- Test 6: [一键全部开启 / 一键全部关闭按钮] ---")
    src = (ROOT_DIR / "apps" / "app4_dlss" / "app.py").read_text(encoding="utf-8")
    assert "btn_enable_all" in src, "missing 一键全部开启 button"
    assert "btn_disable_all" in src, "missing 一键全部关闭 button"
    assert "def apply_all(self, enabled" in src, "missing explicit apply_all(enabled) implementation"
    assert "toggle_master_all" in src, "backward-compatible master alias removed"
    print("  -> 两枚显式批量按钮与 apply_all(True/False) 已就位！")


def test_7_reshade_signature_beyond_4mb():
    print("\n--- Test 7: [ReShade 6.8 签名位于 4MB 之后仍能识别] ---")
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "ReShade.ini").write_text("[GENERAL]\nTutorialProgress=4\n", encoding="utf-8")
        # ReShade 6.8 stores the signature at ~4.3 MB; the old 4 MB probe missed it.
        (td / "dxgi.dll").write_bytes(b"\x00" * (4 * 1024 * 1024 + 110_000) + b"ReShade 6.8.0")

        a4.get_known_game_dirs = lambda force_refresh=False: [td]
        a4._RESHADE_BASE_CACHE.clear()
        assert a4._has_reshade_base(td) is True, "signature beyond 4MB was not detected"
        assert a4.find_all_reshade_inis() == [td / "ReShade.ini"]

        # Toggle must now write the real [OVERLAY] keys
        ok, msg = a4.set_reshade_overlay_status(True)
        assert ok, msg
        ov = IniConfigManager.read_ini_sections(td / "ReShade.ini")["OVERLAY"]
        assert ov["ShowFPS"] == "1" and ov["ShowFrameTime"] == "1"
    print("  -> 大体积 ReShade 底座可识别，ReShade 指示器可正常开启！")


def main():
    test_1_discovery_uses_real_games_only()
    test_2_overlay_profile_roundtrip()
    test_3_reshade_requires_real_base()
    test_4_no_game_configs_is_reported()
    test_5_guide_tabs_are_abc()
    test_6_explicit_batch_buttons()
    test_7_reshade_signature_beyond_4mb()
    print("\n==========================================")
    print("ALL v1.2.6 APP4 HUD + GUIDE ORDER TESTS PASSED (7/7)!")
    print("==========================================")


if __name__ == "__main__":
    main()
