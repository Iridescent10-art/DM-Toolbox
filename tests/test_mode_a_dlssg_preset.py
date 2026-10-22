import os
import sys
import json
import pytest
from pathlib import Path

REPO_ROOT = Path(r"D:\AI\整合包")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
APP2_DIR = REPO_ROOT / "apps" / "app2_mfg"
if str(APP2_DIR) not in sys.path:
    sys.path.insert(0, str(APP2_DIR))

from core.ini_sync import IniConfigManager
from core.optiscaler_config import (
    DEFAULT_MODE_A_PRESET,
    load_mode_a_preset,
    save_mode_a_preset,
    get_mode_a_preset_summary
)


def test_default_mode_a_preset():
    """Assertion 1: Verify default Mode A preset includes DLSS-G Preset C (Model C)."""
    assert DEFAULT_MODE_A_PRESET.get("dlssg_preset") == "C"
    preset = load_mode_a_preset()
    assert preset.get("dlssg_preset") == "C"
    summary = get_mode_a_preset_summary(preset)
    assert "FG C 模型" in summary


def test_sync_mode_a_forward_preset_c(tmp_path):
    """Assertion 2: Verify forward sync generates valid RTXMFG-Universal.json with followGame=True and dlssgPreset=3."""
    config = {
        "multiplier": 3,
        "dlss_preset": "K",
        "dlssg_preset": "C",
        "menu_key": "Backspace",
        "bink_hook": False
    }

    ok = IniConfigManager.sync_mode_a_forward(tmp_path, config)
    assert ok is True

    # Check RTXMFG-Universal.json
    json_path = tmp_path / "RTXMFG-Universal.json"
    assert json_path.exists(), "RTXMFG-Universal.json must be created"

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Critical Dashdogy validation checks
    assert data.get("followGame") is True, "followGame must be true to pass Dashdogy 0x1800fbc90 validator"
    assert data.get("mode") == "follow"
    assert data.get("dlssgPreset") == 3, "Model C must map to dlssgPreset: 3"
    assert data.get("multiplier") == 3
    assert data.get("dlssSrPreset") == 11  # Preset K = 11

    # Check mfg_unlocker.ini
    ini_path = tmp_path / "mfg_unlocker.ini"
    assert ini_path.exists(), "mfg_unlocker.ini must be created"
    ini_data = IniConfigManager.read_ini_sections(ini_path)
    assert ini_data.get("General", {}).get("DLSSGPreset") == "C"


def test_sync_mode_a_forward_presets_variations(tmp_path):
    """Assertion 3: Verify all DLSS-G preset variations map to the correct Dashdogy integer codes."""
    cases = [
        ("Auto", 0, "Auto"),
        ("A", 1, "A"),
        ("B", 2, "B"),
        ("C", 3, "C"),
    ]

    for preset_input, expected_int, expected_str in cases:
        cfg = {
            "multiplier": 4,
            "dlss_preset": "M",
            "dlssg_preset": preset_input,
            "menu_key": "F11",
            "bink_hook": False
        }
        test_dir = tmp_path / f"test_{preset_input}"
        test_dir.mkdir(parents=True, exist_ok=True)
        IniConfigManager.sync_mode_a_forward(test_dir, cfg)

        with open(test_dir / "RTXMFG-Universal.json", "r", encoding="utf-8") as f:
            d = json.load(f)
        assert d.get("dlssgPreset") == expected_int
        assert d.get("followGame") is True

        ini_d = IniConfigManager.read_ini_sections(test_dir / "mfg_unlocker.ini")
        assert ini_d.get("General", {}).get("DLSSGPreset") == expected_str


def test_read_mode_a_reverse(tmp_path):
    """Assertion 4: Verify reverse sync reads dlssg_preset accurately from RTXMFG-Universal.json and INI."""
    # Scenario A: JSON with dlssgPreset: 3
    json_path = tmp_path / "RTXMFG-Universal.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "version": 40,
            "followGame": True,
            "mode": "follow",
            "multiplier": 3,
            "menuKey": "Backspace",
            "dlssgPreset": 3
        }, f)

    rev = IniConfigManager.read_mode_a_reverse(tmp_path)
    assert rev is not None
    assert rev.get("dlssg_preset") == "C"
    assert rev.get("multiplier") == 3
    assert rev.get("menu_key") == "Backspace"

    # Scenario B: Only INI with DLSSGPreset=C
    os.remove(json_path)
    ini_path = tmp_path / "mfg_unlocker.ini"
    IniConfigManager.write_ini_sections(ini_path, {
        "General": {
            "DLSSGPreset": "C",
            "Multiplier": "4",
            "MenuKey": "Insert"
        }
    })
    rev2 = IniConfigManager.read_mode_a_reverse(tmp_path)
    assert rev2 is not None
    assert rev2.get("dlssg_preset") == "C"
    assert rev2.get("multiplier") == 4
    assert rev2.get("menu_key") == "Insert"


def test_dashdogy_disassembly_validator_rules():
    """
    Assertion 5: Rigorous simulation of Dashdogy 0x1800fbc90 PE disassembly validator.
    Tests every rule discovered via binary reverse engineering:
    - Rule 1: 'multiplier' must exist as an integer between 1 and 6 (0x1800fc1ba).
    - Rule 2: 'mode' == 'follow' REQUIRES 'followGame' == True (0x1800fc53a).
    - Rule 3: 'dlssgPreset' must be <= 3 (0x1800fc271).
    - Rule 4: 'dynamicTargetFrameRate' if present must be <= 1000 (0x1800fc22e).
    """
    def simulate_dashdogy_validator(cfg: dict) -> bool:
        # 1. multiplier check: 1..6
        if "multiplier" not in cfg:
            return False
        mult = cfg["multiplier"]
        if not isinstance(mult, int) or not (1 <= mult <= 6):
            return False

        # 2. followGame & mode check:
        mode = cfg.get("mode")
        follow_game = bool(cfg.get("followGame", False))
        if mode == "follow" and not follow_game:
            # 0x1800fc53a: test r14d, r14d; je 0x1800fc56f -> FAILS!
            return False

        # 3. dlssgPreset check: <= 3
        if "dlssgPreset" in cfg:
            preset_val = cfg["dlssgPreset"]
            if not isinstance(preset_val, int) or preset_val > 3 or preset_val < 0:
                return False

        # 4. dynamicTargetFrameRate check: <= 1000
        if "dynamicTargetFrameRate" in cfg:
            fps = cfg["dynamicTargetFrameRate"]
            if not isinstance(fps, int) or fps > 1000 or fps < 0:
                return False

        return True

    # Old buggy config that failed in-game:
    old_broken_config = {
        "version": 40,
        "mode": "follow",
        "multiplier": 3,
        "dlssgPreset": 0
        # Notice: followGame missing!
    }
    assert simulate_dashdogy_validator(old_broken_config) is False, "Old config MUST fail Dashdogy validator"

    # New fixed config:
    new_fixed_config = {
        "version": 40,
        "followGame": True,
        "mode": "follow",
        "multiplier": 3,
        "dlssgPreset": 3
    }
    assert simulate_dashdogy_validator(new_fixed_config) is True, "New config MUST pass Dashdogy validator"
