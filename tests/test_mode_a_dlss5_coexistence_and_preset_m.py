# -*- coding: utf-8 -*-
import os
import sys
import shutil
import json
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

APP2_DIR = ROOT_DIR / "apps" / "app2_mfg"
if str(APP2_DIR) not in sys.path:
    sys.path.insert(0, str(APP2_DIR))

from apps.app6_dlss5.engine.injector import DLSS5Injector
from core.models import BackendType, GameInfo, QualificationStatus
from core.updater import ComponentUpdater
from core.patcher import PatchEngine
from core.ini_sync import IniConfigManager
from core.optiscaler_config import (
    get_adaptive_default_dlss_preset,
    load_mode_a_preset,
    load_optiscaler_preset,
    load_dlssg_sm86_preset
)
from core.coexistence import is_dashdogy_binary, is_reshade_binary, restore_mfg_after_dlss5_removal


def test_gpu_adaptive_presets_modes_abc():
    """
    Verifies user request:
    'ABC三种模式都是，40-50系显卡设置为M模型，20-30系显卡设置为K模型'
    """
    # 1. RTX 40/50 series -> M model across Mode A, B, C
    for gpu_40 in ["NVIDIA GeForce RTX 4070", "RTX 4090", "GeForce RTX 5080 Laptop GPU"]:
        assert get_adaptive_default_dlss_preset(gpu_40) == "M", f"{gpu_40} must default to M"
        preset_a = load_mode_a_preset(gpu_40)
        assert preset_a["dlss_preset"] == "M", f"Mode A on {gpu_40} must default to M"
        preset_b = load_optiscaler_preset(gpu_40)
        assert preset_b["dlss_preset"] == "M", f"Mode B on {gpu_40} must default to M"
        preset_c = load_dlssg_sm86_preset(gpu_40)
        assert preset_c["dlss_preset"] == "M", f"Mode C on {gpu_40} must default to M"

    # 2. RTX 20/30 series -> K model across Mode A, B, C
    for gpu_20_30 in ["NVIDIA GeForce RTX 3070", "RTX 3080 Ti", "GeForce RTX 2060 Super", "TITAN RTX"]:
        assert get_adaptive_default_dlss_preset(gpu_20_30) == "K", f"{gpu_20_30} must default to K"
        preset_a = load_mode_a_preset(gpu_20_30)
        assert preset_a["dlss_preset"] == "K", f"Mode A on {gpu_20_30} must default to K"
        preset_b = load_optiscaler_preset(gpu_20_30)
        assert preset_b["dlss_preset"] == "K", f"Mode B on {gpu_20_30} must default to K"
        preset_c = load_dlssg_sm86_preset(gpu_20_30)
        assert preset_c["dlss_preset"] == "K", f"Mode C on {gpu_20_30} must default to K"


def test_mode_a_sync_forward_adaptive_and_dlss_fg(tmp_path):
    """
    Verifies forward sync outputs DLSS FG (xemfgStandalone=0) and hardware-appropriate preset.
    """
    game_exe = tmp_path / "yysls.exe"
    game_exe.write_bytes(b"MZ\x90\x00" + b"\x00" * 1024)

    # Test 40-series GPU forward sync: M (13)
    preset_40 = {"multiplier": 3, "gpu_name": "NVIDIA GeForce RTX 4070"}
    IniConfigManager.sync_mode_a_forward(tmp_path, preset_40)
    data_40 = json.loads((tmp_path / "RTXMFG-Universal.json").read_text(encoding="utf-8"))
    assert data_40["xemfgStandalone"] == 0, "Default must be DLSS frame generation"
    assert data_40["dlssPreset"] == 13, "40-series must sync Preset M (13)"

    # Test 30-series GPU forward sync: K (11)
    preset_30 = {"multiplier": 3, "gpu_name": "NVIDIA GeForce RTX 3070"}
    IniConfigManager.sync_mode_a_forward(tmp_path, preset_30)
    data_30 = json.loads((tmp_path / "RTXMFG-Universal.json").read_text(encoding="utf-8"))
    assert data_30["xemfgStandalone"] == 0, "Default must be DLSS frame generation"
    assert data_30["dlssPreset"] == 11, "30-series must sync Preset K (11)"


def test_mode_a_then_dlss5_coexistence(tmp_path):
    """
    Verifies coexistence:
    Mode A is migrated to secondary proxy without clobbering, ReShade takes dxgi.dll,
    both coexist, and ReShade.ini syncs active preset.
    """
    game_exe = tmp_path / "yysls.exe"
    # Create fake PE with winmm.dll in import table
    game_exe.write_bytes(b"MZ\x90\x00" + b"winmm.dll\x00" + b"\x00" * 2048)

    game_info = GameInfo(
        name="Where Winds Meet",
        source="Custom",
        install_dir=str(tmp_path),
        target_dir=str(tmp_path),
        exe_path=str(game_exe),
        exe_name="yysls.exe",
        qualification=QualificationStatus.QUALIFIED
    )

    updater = ComponentUpdater()
    patcher = PatchEngine(updater)
    ok_a, msg_a = patcher.patch_game(game_info, requested_backend=BackendType.STANDALONE)
    assert ok_a, f"Mode A injection failed: {msg_a}"

    assert (tmp_path / "dxgi.dll").exists(), "Standalone Mode A must deploy to dxgi.dll"
    assert not (tmp_path / "libxess_fg.dll").exists(), "libxess_fg.dll must NOT pollute target_dir root"

    # Inject DLSS 5
    ok_5, msg_5 = DLSS5Injector.inject(
        target_dir=str(tmp_path),
        mode="MODE_A"
    )
    assert ok_5, f"DLSS 5 injection failed: {msg_5}"

    assert (tmp_path / "winmm.dll").exists(), "Mode A dashdogy must migrate to winmm.dll"
    assert is_dashdogy_binary(tmp_path / "winmm.dll"), "winmm.dll must be dashdogy"
    assert (tmp_path / "dxgi.dll").exists(), "DLSS 5 ReShade must be at dxgi.dll"
    assert is_reshade_binary(tmp_path / "dxgi.dll"), "dxgi.dll must be ReShade"

    # Rollback DLSS 5: Mode A restored to dxgi.dll
    ok_rest, msg_rest = restore_mfg_after_dlss5_removal(tmp_path, game_exe)
    assert ok_rest, f"Restoring Mode A failed: {msg_rest}"

    assert (tmp_path / "dxgi.dll").exists(), "Mode A must be restored back to dxgi.dll"
    assert is_dashdogy_binary(tmp_path / "dxgi.dll"), "dxgi.dll must be dashdogy after DLSS 5 removal"
    assert not (tmp_path / "winmm.dll").exists(), "Secondary proxy winmm.dll must be cleaned up"
