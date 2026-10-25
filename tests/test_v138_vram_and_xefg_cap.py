# -*- coding: utf-8 -*-
"""
DM-Toolbox v1.3.8 regression tests:
  1. VRAM spoof preflight  (App1 disguised VRAM -> DXGI_ERROR_DEVICE_HUNG / TDR)
  2. XeFG hardware interpolation cap warning (libxess_fg Max supported interpolations = 1)
"""

import sys
import tempfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
APP2_DIR = ROOT_DIR / "apps" / "app2_mfg"
if str(APP2_DIR) not in sys.path:
    sys.path.insert(0, str(APP2_DIR))

from common.config_manager import (
    describe_vram_overcommit,
    detect_vram_overcommit,
    get_physical_vram_gb,
)
from core.ini_sync import IniConfigManager


def test_vram_overcommit_warning():
    print("\n--- Test 1: [显存伪装风险检测] ---")
    # 12 GB physical board impersonating a 32 GB card -> must warn with both numbers.
    msg = describe_vram_overcommit(12, 32)
    assert msg, "12GB -> 32GB spoof must produce a warning"
    assert "32" in msg and "12" in msg
    assert "DEVICE_HUNG" in msg or "TDR" in msg
    assert "保持原始" in msg, "warning must tell the user how to fix it"

    # Identical / lower spoof is harmless.
    assert describe_vram_overcommit(12, 12) is None
    assert describe_vram_overcommit(12, 8) is None
    # Unknown physical model -> stay silent instead of guessing.
    assert describe_vram_overcommit(None, 32) is None

    # Runtime entry point must never raise, whatever the machine looks like.
    result = detect_vram_overcommit()
    assert result is None or isinstance(result, str)
    print("   [PASS] 显存伪装检测逻辑正确（真实 12GB / 伪装 32GB 会给出 TDR 警告）")


def test_xefg_cap_warning_suggests_native_mfg():
    print("\n--- Test 2: [XeFG 2X 硬件上限提示] ---")
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        # libxess_fg reported "Max supported interpolations: 1" (2X) in a real yysls session.
        (td / "OptiScaler.log").write_text(
            "[23:06:12.550] [I] XeFG_Dx12::QueryMaxInterpolationCount Max supported interpolations: 1\n",
            encoding="utf-8",
        )
        preset = {
            "fg_output": "xefg",
            "fg_input": "dlssg",
            "interpolation_count": 2,   # request 3X
            "dx12_upscaler": "auto",
        }
        assert IniConfigManager.sync_mode_c_forward(str(td), preset, exe_name="yysls.exe")

        report = IniConfigManager.last_report
        assert report["xefg_max_interpolations"] == 1
        assert report["interpolation_count"] == 1, "must clamp to the hardware max (2X)"
        assert report["interpolation_clamped"] is True
        joined = "\n".join(report["warnings"])
        assert ("模式 C" in joined or "模式 D" in joined) and "模式 A" in joined, (
            "warning must point users to the native DLSS-G multi-frame modes"
        )
        print("   [PASS] 2X 上限被正确识别，并提示改用模式 A / 模式 D 获取 3X/4X")


def test_mfg_unlocker_bypasses_xefg_2x_cap():
    print("\n--- Test 3: [MFGUnlocker.asi 解锁 3X/4X] ---")
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "OptiScaler" / "plugins").mkdir(parents=True)
        (td / "OptiScaler" / "plugins" / "MFGUnlocker.asi").write_bytes(b"MFGUnlocker stub")
        (td / "OptiScaler.log").write_text(
            "[x] XeFG_Dx12::QueryMaxInterpolationCount Max supported interpolations: 1\n",
            encoding="utf-8",
        )
        preset = {
            "fg_output": "xefg",
            "fg_input": "dlssg",
            "interpolation_count": 2,   # request 3X
            "dx12_upscaler": "auto",
            "unlock_mfg": True,
        }
        assert IniConfigManager.sync_mode_c_forward(str(td), preset, exe_name="yysls.exe")
        report = IniConfigManager.last_report
        assert report["interpolation_count"] == 2, "with the unlocker deployed, 3X must be written"
        assert report["interpolation_clamped"] is False
        secs = IniConfigManager.read_ini_sections(td / "OptiScaler.ini")
        assert secs["XeFG"]["InterpolationCount"] == "2"
        assert secs["Plugins"]["LoadAsiPlugins"] == "true"
        print("   [PASS] MFGUnlocker.asi 存在时 3X 请求不再被 2X 上限压回")


def test_factory_default_is_unlock_and_3x():
    print("\n--- Test 4: [出厂默认 = 多帧解锁 + 3X] ---")
    import json

    from core.optiscaler_config import DEFAULT_OPTISCALER_PRESET

    assert DEFAULT_OPTISCALER_PRESET["unlock_mfg"] is True, "出厂默认必须开启 MFG-Unlocker"
    assert DEFAULT_OPTISCALER_PRESET["interpolation_count"] == 2, "出厂默认必须是 3X (InterpolationCount=2)"

    factory = ROOT_DIR / "defaults" / "app2_mfg" / "optiscaler_preset.json"
    data = json.loads(factory.read_text(encoding="utf-8"))
    assert data.get("unlock_mfg") is True
    assert data.get("interpolation_count") == 2
    assert data.get("preset_schema_version") == 2
    print("   [PASS] 出厂配置与代码默认均为「解锁 + 3X」")


if __name__ == "__main__":
    test_vram_overcommit_warning()
    test_xefg_cap_warning_suggests_native_mfg()
    test_mfg_unlocker_bypasses_xefg_2x_cap()
    test_factory_default_is_unlock_and_3x()
    print("\nALL v1.3.8 VRAM / XeFG CAP TESTS PASSED")
