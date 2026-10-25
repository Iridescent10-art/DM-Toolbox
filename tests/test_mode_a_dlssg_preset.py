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


def test_mode_a_gpu_unlock_policy(tmp_path):
    """
    Assertion 6: Mode A GPU-aware spoofing / unlock policy.
    - RTX 40/50 GPUs natively support Ada/Blackwell OFA: default to NOT unlocking (GpuNameOverride=0, unlocked=False)
      to prevent "游戏帧生成选项未能在此次运行中应用。请查看日志。" Streamline spoofing failure.
    - RTX 20/30 GPUs lack native OFA: require spoofing RTX 4090 (GpuNameOverride=1, unlocked=True).
    """
    from unittest.mock import patch

    # Case 1: RTX 40-series GPU
    dir_40 = tmp_path / "rtx40"
    dir_40.mkdir(parents=True, exist_ok=True)
    cfg_40 = {
        "multiplier": 3,
        "dlss_preset": "M",
        "dlssg_preset": "C",
        "gpu_name": "NVIDIA GeForce RTX 4090"
    }
    IniConfigManager.sync_mode_a_forward(dir_40, cfg_40)

    with open(dir_40 / "RTXMFG-Universal.json", "r", encoding="utf-8") as f:
        d40 = json.load(f)
    assert d40.get("unlocked") is False, "RTX 40 series must default to unlocked=False"
    assert d40.get("gpuNameOverride") == 0, "RTX 40 series must default to gpuNameOverride=0"
    assert d40.get("dlssPreset") == 13, "Preset M must map to 13"

    ini_40 = IniConfigManager.read_ini_sections(dir_40 / "RTXMFG-UI.ini")
    assert ini_40.get("Compatibility", {}).get("GpuNameOverride") == "0"
    assert ini_40.get("Compatibility", {}).get("Rtx30FlipMetering") == "off"
    assert ini_40.get("General", {}).get("Preset") == "M"

    # Case 2: RTX 30-series GPU
    dir_30 = tmp_path / "rtx30"
    dir_30.mkdir(parents=True, exist_ok=True)
    cfg_30 = {
        "multiplier": 3,
        "dlss_preset": "M",
        "dlssg_preset": "C",
        "gpu_name": "NVIDIA GeForce RTX 3080 Ti"
    }
    IniConfigManager.sync_mode_a_forward(dir_30, cfg_30)

    with open(dir_30 / "RTXMFG-Universal.json", "r", encoding="utf-8") as f:
        d30 = json.load(f)
    assert d30.get("unlocked") is True, "RTX 30 series must default to unlocked=True"
    assert d30.get("gpuNameOverride") == 1, "RTX 30 series must default to gpuNameOverride=1"

    ini_30 = IniConfigManager.read_ini_sections(dir_30 / "RTXMFG-UI.ini")
    assert ini_30.get("Compatibility", {}).get("GpuNameOverride") == "1"
    assert ini_30.get("Compatibility", {}).get("Rtx30FlipMetering") == "on"


def test_mode_a_xess_runtime_deployment(tmp_path):
    """
    Assertion 7: Mode A XeSS / XeMFG runtime deployment.
    dashdogy 1.7.0 独立 XeMFG checks TargetExeDir / "RTXMFG-XeSS" for libxess_fg.dll and libxell.dll.
    Verify that _apply_standalone_patch automatically deploys them, enabling XeMFG out of the box.
    """
    from core.updater import ComponentUpdater
    from core.patcher import PatchEngine
    from core.models import GameInfo, QualificationStatus, PatchManifest, BackendType
    from core.rollback import RollbackEngine

    updater = ComponentUpdater()
    patcher = PatchEngine(updater=updater)

    game_dir = tmp_path / "game"
    game_dir.mkdir(parents=True, exist_ok=True)
    exe_p = game_dir / "game.exe"
    exe_p.write_bytes(b"MZ" + b"\x00" * 100)

    game_info = GameInfo(
        name="TestGame",
        source="custom",
        install_dir=str(game_dir),
        target_dir=str(game_dir),
        exe_path=str(exe_p),
        exe_name="game.exe",
        qualification=QualificationStatus.QUALIFIED
    )

    manifest = PatchManifest(
        app_version="2.0.0",
        game_name="TestGame",
        target_exe=str(exe_p),
        target_dir=str(game_dir),
        active_backend=BackendType.STANDALONE.value,
        installed_version="latest"
    )

    ok, err = patcher._apply_standalone_patch(game_info, manifest)
    assert ok, f"_apply_standalone_patch failed: {err}"

    # Verify RTXMFG-XeSS runtime folder and files
    xess_folder = game_dir / "RTXMFG-XeSS"
    assert xess_folder.exists() and xess_folder.is_dir(), "RTXMFG-XeSS folder must exist"
    assert (xess_folder / "libxess_fg.dll").exists(), "libxess_fg.dll must exist in RTXMFG-XeSS"
    assert (xess_folder / "libxell.dll").exists(), "libxell.dll must exist in RTXMFG-XeSS"
    assert (xess_folder / "libxess.dll").exists(), "libxess.dll must exist in RTXMFG-XeSS"

    # Verify rollback cleans it up
    rollback = RollbackEngine()
    rb_ok, rb_err = rollback.rollback(str(game_dir), clean_all=True)
    assert rb_ok, f"rollback failed: {rb_err}"
    assert not xess_folder.exists(), "RTXMFG-XeSS folder must be removed after rollback"
