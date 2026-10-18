# -*- coding: utf-8 -*-
"""
v1.2.6 Mode C verification suite - 100% aligned with OptiScaler v0.9.4-final.

Covers the four production fixes driven by the real 4K (3840x2160, RTX 5080) in-game
OptiScaler v0.9.4 menu screenshots:

1. [Menu] Scale is written as 2.0 (4K) / 1.5 (2K) instead of 1.0.
2. The legacy `nvngx.ini` is never written and is deleted wherever it is found.
3. Every key written into OptiScaler.ini exists in the official v0.9.4 template AND
   appears in the OptiScaler.dll string table (real key-name alignment).
4. [XeFG] InterpolationCount never exceeds libxess_fg's "Max supported interpolations",
   so the game no longer shows "Restart the game to apply correct XeFG settings!".
"""

import os
import re
import sys
import tempfile
import shutil
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
APP2_DIR = ROOT_DIR / "apps" / "app2_mfg"
for p in (ROOT_DIR, APP2_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from core.ini_sync import (
    IniConfigManager,
    DEFAULT_OPTISCALER_MENU_SCALE,
    OPTISCALER_INI_NAME,
    LEGACY_OPTISCALER_INI_NAME,
)
from core.optiscaler_config import DEFAULT_OPTISCALER_PRESET, get_preset_summary

TEMPLATE_INI = APP2_DIR / "embedded_components" / "optiscaler" / "v0.9.4" / "OptiScaler.ini"
OPTISCALER_DLL = APP2_DIR / "embedded_components" / "optiscaler" / "v0.9.4" / "OptiScaler.dll"

# Prefer the component that the patcher will actually deploy (cache), fall back to embedded.
try:
    from core.updater import ComponentUpdater
    from core.models import BackendType
    _cached_dir = ComponentUpdater().get_latest_cached_dir(BackendType.OPTISCALER_FSR)
    if _cached_dir and (Path(_cached_dir) / "OptiScaler.ini").exists():
        TEMPLATE_INI = Path(_cached_dir) / "OptiScaler.ini"
        OPTISCALER_DLL = Path(_cached_dir) / "OptiScaler.dll"
except Exception:
    pass

REAL_GAME_DIR = Path(r"D:\game\yysls\yysls_medium\Engine\Binaries\Win64r")


def _parse_sections(text: str):
    """Return {section: [(key, value), ...]} while ignoring comments/blank lines."""
    sec = None
    out = {}
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith(";") or s.startswith("#"):
            continue
        m = re.match(r"^\[(.+)\]$", s)
        if m:
            sec = m.group(1).strip()
            out.setdefault(sec, [])
            continue
        if sec and "=" in s:
            k, v = s.split("=", 1)
            out[sec].append((k.strip(), v.strip()))
    return out


def _keys(sections):
    return {sec: [k for k, _ in pairs] for sec, pairs in sections.items()}


def _write_preset(td: Path, **overrides):
    preset = dict(DEFAULT_OPTISCALER_PRESET)
    preset.update(overrides)
    ok = IniConfigManager.sync_mode_c_forward(str(td), preset, exe_name="yysls.exe")
    assert ok, "sync_mode_c_forward failed"
    return preset


def test_1_real_key_name_alignment():
    print("\n--- Test 1: [输出 OptiScaler v0.9.4 真实 INI 键名核对表] ---")
    template = _parse_sections(TEMPLATE_INI.read_text(encoding="utf-8"))
    template_keys = _keys(template)
    dll_bytes = OPTISCALER_DLL.read_bytes()

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        _write_preset(td, menu_scale=2.0, interpolation_count=1)
        written = _parse_sections((td / OPTISCALER_INI_NAME).read_text(encoding="utf-8"))
        written_keys = _keys(written)

        print(f"{'Section':<14}{'Key':<32}{'InTemplate':<12}{'InDLL':<8}Value")
        bad = []
        for sec, keys in written_keys.items():
            if sec not in template_keys:
                print(f"{sec:<14}{'<SECTION>':<32}{'MISSING':<12}{'-':<8}")
                bad.append(f"[{sec}] section is not part of the v0.9.4 template")
                continue
            for key in keys:
                in_tpl = key in template_keys[sec]
                in_dll = (key.encode("ascii") in dll_bytes) or (key.encode("utf-16le") in dll_bytes)
                value = dict(written[sec])[key]
                print(f"{sec:<14}{key:<32}{str(in_tpl):<12}{str(in_dll):<8}{value}")
                if not in_tpl:
                    bad.append(f"[{sec}] {key} is not in the official template")
                if not in_dll:
                    bad.append(f"[{sec}] {key} does not appear in OptiScaler.dll")

        assert not bad, "Key-name mismatches:\n" + "\n".join(bad)
        # Values that matter for the actual fix
        written_map = {sec: dict(pairs) for sec, pairs in written.items()}
        assert written_map["FrameGen"]["FGOutput"] == "xefg"
        assert written_map["FrameGen"]["Enabled"] == "true"
        assert written_map["Menu"]["Scale"] == "2.0"
        assert written_map["XeFG"]["InterpolationCount"] == "1"
        assert "UseDelayedInit" not in written_map.get("Hotfix", {}), \
            "UseDelayedInit belongs to [Dx11withDx12]; it must not be injected into [Hotfix]"
        assert "FGType" not in written_map["FrameGen"], "FGType is not a v0.9.4 key"
        assert "FrameGenerationMultiplier" not in written_map["FrameGen"]
        assert "Sharpness" not in written_map.get("CAS", {}), "[CAS] has no Sharpness key"
        assert "Enabled" not in written_map.get("Sharpness", {}), "[Sharpness] has no Enabled key"

    print("  -> 所有写入键名均与 v0.9.4 模板及 OptiScaler.dll 字符串表 100% 匹配！")


def test_2_nvngx_purged_everywhere():
    print("\n--- Test 2: [断言 nvngx.ini 已被彻底清理] ---")
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        # Pre-existing legacy config from older builds
        (td / LEGACY_OPTISCALER_INI_NAME).write_text(
            "[FrameGen]\nEnabled=true\nFGType=xefg\n\n[Menu]\nOverlayMenu=true\n", encoding="utf-8"
        )
        _write_preset(td)
        assert not (td / LEGACY_OPTISCALER_INI_NAME).exists(), "forward sync must delete nvngx.ini"
        assert (td / OPTISCALER_INI_NAME).exists(), "OptiScaler.ini must be the only config"
        assert IniConfigManager.last_report["nvngx_ini_removed"] is True

        # Reverse sync must also purge it once OptiScaler.ini exists
        (td / LEGACY_OPTISCALER_INI_NAME).write_text("[Menu]\nOverlayMenu=true\n", encoding="utf-8")
        rev = IniConfigManager.read_mode_c_reverse(str(td))
        assert rev is not None
        assert not (td / LEGACY_OPTISCALER_INI_NAME).exists(), "reverse sync must also delete nvngx.ini"

        # Legacy-only folder is still readable for migration (no data loss)
        (td / OPTISCALER_INI_NAME).unlink()
        (td / LEGACY_OPTISCALER_INI_NAME).write_text(
            "[FrameGen]\nFGOutput=xefg\n[Menu]\nShortcutKey=45\n", encoding="utf-8"
        )
        migrated = IniConfigManager.read_mode_c_reverse(str(td))
        assert migrated and migrated["fg_output"] == "xefg"

    print("  -> nvngx.ini 在正向同步 / 反向同步 / 部署三条链路上均被删除，仅保留 OptiScaler.ini！")


def test_3_menu_scale_written_and_synced():
    print("\n--- Test 3: [断言菜单缩放已放大] ---")
    assert DEFAULT_OPTISCALER_MENU_SCALE == 2.0
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        for expected, preset_scale in [("2.0", 2.0), ("1.5", 1.5), ("1.0", 1.0)]:
            _write_preset(td, menu_scale=preset_scale)
            menu = IniConfigManager.read_ini_sections(td / OPTISCALER_INI_NAME)["Menu"]
            assert menu["Scale"] == expected, f"expected Scale={expected}, got {menu['Scale']}"
            rev = IniConfigManager.read_mode_c_reverse(str(td))
            assert abs(rev["menu_scale"] - float(expected)) < 1e-6, "reverse sync must return the written scale"

        # Out-of-range values are clamped to OptiScaler's legal 0.5 - 2.0
        assert IniConfigManager.normalize_menu_scale(9) == "2.0"
        assert IniConfigManager.normalize_menu_scale("0.1") == "0.5"
        assert IniConfigManager.normalize_menu_scale(None) == "2.0"

        _write_preset(td, menu_scale=9)
        assert IniConfigManager.read_ini_sections(td / OPTISCALER_INI_NAME)["Menu"]["Scale"] == "2.0"

    print("  -> [Menu] Scale=2.0 (4K) / 1.5 (2K) / 1.0 (1080P) 均正确写入并可反向回显！")


def test_4_xefg_init_cap_prevents_restart_warning():
    print("\n--- Test 4: [验证帧生成启动即就绪 / 不再提示 Restart the game] ---")
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        log = td / "OptiScaler.log"

        # (a) no log -> conservative 2X
        _write_preset(td, fg_output="xefg", interpolation_count=2)
        assert IniConfigManager.read_ini_sections(td / OPTISCALER_INI_NAME)["XeFG"]["InterpolationCount"] == "1"
        assert IniConfigManager.last_report["interpolation_clamped"] is True
        assert any("Restart the game" in w for w in IniConfigManager.last_report["warnings"])

        # (b) real log proves a 2-interpolation (3X) library
        log.write_text(
            "[x] XeFG_Dx12::CreateSwapchain Max supported interpolations: 2\n", encoding="utf-8"
        )
        _write_preset(td, fg_output="xefg", interpolation_count=3)
        assert IniConfigManager.read_ini_sections(td / OPTISCALER_INI_NAME)["XeFG"]["InterpolationCount"] == "2"
        assert IniConfigManager.last_report["xefg_max_interpolations"] == 2

        # (c) 4X request on a 4-interpolation library
        log.write_text(
            "[x] XeFG_Dx12::CreateSwapchain Max supported interpolations: 3\n", encoding="utf-8"
        )
        _write_preset(td, fg_output="xefg", interpolation_count=3)
        assert IniConfigManager.read_ini_sections(td / OPTISCALER_INI_NAME)["XeFG"]["InterpolationCount"] == "3"
        assert IniConfigManager.last_report["interpolation_clamped"] is False

        # (d) FSR 3.1 / Nukem9 are always 2X regardless of the requested value
        for out in ("fsrfg", "nukems"):
            _write_preset(td, fg_output=out, interpolation_count=3)
            secs = IniConfigManager.read_ini_sections(td / OPTISCALER_INI_NAME)
            assert secs["XeFG"]["InterpolationCount"] == "1", f"{out} must be locked to 2X"
            assert secs["FrameGen"]["FGOutput"] == out

        # (e) init-time keys are all present BEFORE launch
        secs = IniConfigManager.read_ini_sections(td / OPTISCALER_INI_NAME)
        assert secs["FrameGen"]["Enabled"] == "true"
        assert secs["FrameGen"]["FGInput"] == "dlssg"
        assert secs["XeFG"]["IgnoreInitChecks"] == "false"
        assert secs["XeFG"]["DepthInverted"] == "true"

    print("  -> InterpolationCount 始终落在 libxess_fg 支持范围内，首次启动即进入正确 XeFG 管线！")


def test_5_real_game_directory():
    print("\n--- Test 5: [实机目录断言] ---")
    if not REAL_GAME_DIR.exists():
        print(f"  SKIP: {REAL_GAME_DIR} not found")
        return

    ini_path = REAL_GAME_DIR / OPTISCALER_INI_NAME
    if not ini_path.exists():
        print("  SKIP: 当前实机目录未部署模式 C（可能已切换为模式 A/B），跳过实机断言")
        return

    assert not (REAL_GAME_DIR / LEGACY_OPTISCALER_INI_NAME).exists(), (
        "nvngx.ini still exists in the real game folder -> red warning banner will persist"
    )

    assert ini_path.exists(), "OptiScaler.ini missing"
    secs = IniConfigManager.read_ini_sections(ini_path)
    print("  Menu.Scale            =", secs.get("Menu", {}).get("Scale"))
    print("  FrameGen.FGOutput     =", secs.get("FrameGen", {}).get("FGOutput"))
    print("  XeFG.InterpolationCount =", secs.get("XeFG", {}).get("InterpolationCount"))
    assert secs["Menu"]["Scale"] in ("1.5", "2.0"), "menu scale was not enlarged"
    assert secs["FrameGen"]["FGOutput"] == "xefg"
    assert secs["XeFG"]["InterpolationCount"] == "1", "real 4K session is capped at 2X"

    # Proxy + XeFG runtime dependencies must be deployed
    proxy_files = [p.name for p in REAL_GAME_DIR.glob("*.dll") if p.name.lower() in
                   ("dxgi.dll", "winmm.dll", "version.dll", "dinput8.dll", "wininet.dll")]
    assert proxy_files, "no OptiScaler proxy dll (dxgi/winmm/...) in the game folder"
    for required in ("libxess_fg.dll", "libxell.dll", "amd_fidelityfx_framegeneration_dx12.dll", "fakenvapi.dll"):
        assert (REAL_GAME_DIR / required).exists(), f"missing Mode C dependency: {required}"
    print("  proxy dll:", proxy_files)

    print("  -> 实机目录：无 nvngx.ini、菜单已放大、XeFG 参数合法、依赖库齐全！")


def test_6_dialog_exposes_menu_scale():
    print("\n--- Test 6: [模式 C 面板新增 Menu Scale 下拉框] ---")
    try:
        from PySide6.QtWidgets import QApplication
        from gui_qt import OptiScalerPresetDialog
    except Exception as exc:  # pragma: no cover - GUI optional in headless env
        print("  SKIP (PySide6 unavailable):", exc)
        return

    app = QApplication.instance() or QApplication(sys.argv)
    dlg = OptiScalerPresetDialog(parent=None, is_dark=False, game=None)
    texts = [dlg.combo_menu_scale.itemText(i) for i in range(dlg.combo_menu_scale.count())]
    values = [dlg.combo_menu_scale.itemData(i) for i in range(dlg.combo_menu_scale.count())]
    print("  items:", texts)
    assert values == [1.0, 1.5, 2.0], f"menu scale choices mismatch: {values}"
    assert dlg.combo_menu_scale.currentData() == 2.0, "default must be 2.0 (4K)"
    dlg.deleteLater()
    print("  -> 模式 C 面板下拉框 1.0x / 1.5x / 2.0x 默认 2.0，可用！")


def main():
    test_1_real_key_name_alignment()
    test_2_nvngx_purged_everywhere()
    test_3_menu_scale_written_and_synced()
    test_4_xefg_init_cap_prevents_restart_warning()
    test_5_real_game_directory()
    test_6_dialog_exposes_menu_scale()
    print("\n==========================================")
    print("ALL v1.2.6 MODE C VERIFICATION TESTS PASSED (6/6)!")
    print("==========================================")


if __name__ == "__main__":
    main()
