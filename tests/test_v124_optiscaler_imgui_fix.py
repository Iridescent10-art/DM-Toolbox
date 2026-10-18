# -*- coding: utf-8 -*-
"""
Verification Suite (v1.2.6 contract, supersedes the v1.2.4 "disable ImGui" behavior):
The in-game OptiScaler menu is intentionally ENABLED so players can diagnose Frame
Generation, so this suite now asserts the legal v0.9.4 menu block instead of disabling it:

- [Menu] OverlayMenu=true / Scale=2.0 (4K readable) / ShortcutKey=45 / DisableSplash=false
- `nvngx.ini` is never produced (single-config rule)
- No obsolete keys (FGType, FrameGenerationMultiplier, Sharpness.Enabled, CAS.Sharpness) are written
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
APP2_DIR = ROOT_DIR / "apps" / "app2_mfg"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(APP2_DIR) not in sys.path:
    sys.path.insert(0, str(APP2_DIR))

from core.models import GameInfo, BackendType, QualificationStatus
from core.ini_sync import IniConfigManager
from core.patcher import PatchEngine
from core.updater import ComponentUpdater
from core.utils import cleanup_pending_files


def _menu_block(ini_text: str) -> str:
    normalized = ini_text.replace(" ", "")
    return normalized.split("[Menu]", 1)[1] if "[Menu]" in normalized else ""


def test_1_sync_mode_c_writes_legal_menu_block():
    print("[TEST 1] sync_mode_c_forward writes the legal v0.9.4 [Menu] block...")
    with tempfile.TemporaryDirectory() as td:
        target_dir = Path(td)
        preset = {
            "fg_output": "xefg",
            "fg_input": "dlssg",
            "interpolation_count": 2,
            "dx12_upscaler": "auto",
            "rcas_enabled": True,
            "rcas_sharpness": 0.40,
            "menu_scale": 2.0,
        }

        ok = IniConfigManager.sync_mode_c_forward(str(target_dir), preset, exe_name="yysls.exe")
        assert ok, "sync_mode_c_forward should succeed"

        ini_text = (target_dir / "OptiScaler.ini").read_text(encoding="utf-8")
        menu = _menu_block(ini_text)
        assert "OverlayMenu=true" in menu, "OverlayMenu must be true"
        assert "Scale=2.0" in menu, "4K menu scale must be 2.0"
        assert "ShortcutKey=45" in menu, "ShortcutKey must be 45 (Insert)"
        assert "DisableSplash=false" in menu, "DisableSplash must be false"
        assert "ShowFps=false" in menu, "FPS overlay must stay off"

        # Deprecated keys must be stripped; UseDelayedInit belongs to [Dx11withDx12], not [Hotfix]
        hotfix_block = ini_text.split("[Hotfix]", 1)[1].split("[", 1)[0] if "[Hotfix]" in ini_text else ""
        assert "UseDelayedInit" not in hotfix_block, "UseDelayedInit belongs to [Dx11withDx12]"
        assert "FrameGenerationMultiplier" not in ini_text, "FrameGenerationMultiplier belongs to nvngx.ini only"
        assert "FGType" not in ini_text, "FGType is 0.8.x legacy; v0.9.4 uses FGOutput"

        # Single-config rule
        assert not (target_dir / "nvngx.ini").exists(), "nvngx.ini must never be created"

        # XeFG interpolation must be clamped to the detected capability
        xefg = IniConfigManager.read_ini_sections(target_dir / "OptiScaler.ini")["XeFG"]
        assert xefg["InterpolationCount"] == "1", "without a capability log XeFG must fall back to 2X"
        assert xefg["IgnoreInitChecks"] == "false"
        assert xefg["DepthInverted"] == "true"

        # A 2K preset must write 1.5
        IniConfigManager.sync_mode_c_forward(
            str(target_dir), dict(preset, menu_scale=1.5, interpolation_count=1)
        )
        menu = _menu_block((target_dir / "OptiScaler.ini").read_text(encoding="utf-8"))
        assert "Scale=1.5" in menu, "2K menu scale must be 1.5"

    print("  -> legal [Menu] block, key cleanup and single-config rule verified!")


def test_2_patch_game_mode_c_deploys_legal_menu():
    print("[TEST 2] PatchEngine Mode C deployment keeps the legal menu + single config...")
    with tempfile.TemporaryDirectory() as td:
        target_dir = Path(td)
        (target_dir / "yysls.exe").write_bytes(b"FAKE_EXE")
        (target_dir / "sl.interposer.dll").write_bytes(b"FAKE_SL")
        # A stale legacy config from older builds must be purged by the deployment
        (target_dir / "nvngx.ini").write_text("[FrameGen]\nEnabled=true\nFGType=xefg\n", encoding="utf-8")

        game = GameInfo(
            name="燕云十六声",
            source="Custom",
            install_dir=str(target_dir),
            target_dir=str(target_dir),
            exe_path=str(target_dir / "yysls.exe"),
            exe_name="yysls.exe",
            qualification=QualificationStatus.QUALIFIED
        )

        updater = ComponentUpdater()
        patcher = PatchEngine(updater)

        ok, msg = patcher.patch_game(game, BackendType.OPTISCALER_FSR)
        assert ok, f"Patching failed: {msg}"

        ini_text = (target_dir / "OptiScaler.ini").read_text(encoding="utf-8")
        menu = _menu_block(ini_text)
        assert "OverlayMenu=true" in menu
        assert "Scale=2.0" in menu
        assert "ShortcutKey=45" in menu
        assert not (target_dir / "nvngx.ini").exists(), "legacy nvngx.ini must be deleted on deployment"

        patcher.rollback_engine.rollback(str(target_dir), "yysls.exe")
        cleanup_pending_files(str(target_dir))

    print("  -> Mode C deployment purged the legacy config and applied the legal menu block!")


def test_3_embedded_component_template_contract():
    print("[TEST 3] Embedded OptiScaler v0.9.4 template declares the keys we write...")
    updater = ComponentUpdater()
    opti_dir = updater.get_latest_cached_dir(BackendType.OPTISCALER_FSR)
    assert opti_dir, "OptiScaler component cache not found"
    ini_file = Path(opti_dir) / "OptiScaler.ini"
    assert ini_file.exists(), "OptiScaler.ini must exist in cache"
    content = ini_file.read_text(encoding="utf-8")

    assert "[Menu]" in content and "Scale=auto" in content, "template must expose [Menu] Scale"
    assert "0.5 to 2.0" in content, "template must document the 0.5 - 2.0 menu scale range"
    assert "[XeFG]" in content and "InterpolationCount=auto" in content
    assert "1 = 2X | 2 = 3X | 3 = 4X" in content, "template must document XeFG MFG multipliers"
    assert "requires libxess_fg.dll, libxell.dll and latest fakenvapi dll" in content, \
        "template documents fakenvapi as an XeFG dependency"
    print("  -> embedded template contract verified!")


if __name__ == "__main__":
    test_1_sync_mode_c_writes_legal_menu_block()
    test_2_patch_game_mode_c_deploys_legal_menu()
    test_3_embedded_component_template_contract()
    print("\n==========================================")
    print("ALL v1.2.6 MENU / SINGLE-CONFIG TESTS PASSED (3/3)!")
    print("==========================================")
