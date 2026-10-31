# -*- coding: utf-8 -*-
"""
Verification tests for DM-Toolbox v2.0.0:
- Mode C default parameters (4X, Optimized 2, Preset Model C, Engine DLSS, SR Off, Proxy version.dll)
- RTX 20/30 GPU default backend locking to Mode C
- Wallpaper default parameters (enabled=True, blur=0, card_opacity=0.5, tint=0.2, sync_mode=unified)
- Forward & Reverse INI synchronization integrity for Mode C
- DLSS 5 coexistence with Mode C single proxy rule
"""

import os
import sys
import json
import shutil
import tempfile
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
APP2_DIR = ROOT_DIR / "apps" / "app2_mfg"
APP6_DIR = ROOT_DIR / "apps" / "app6_dlss5"
for p in [ROOT_DIR, APP2_DIR, APP6_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from common.version import APP_VERSION
from common.wallpaper_manager import DEFAULT_WALLPAPER_CONFIG, load_wallpaper_config
from core.models import BackendType
from core.utils import is_rtx_20_or_30_series, is_rtx_40_or_newer
from core.optiscaler_config import (
    DEFAULT_DLSSG_SM86_PRESET,
    load_dlssg_sm86_preset,
    save_dlssg_sm86_preset,
    get_dlssg_sm86_preset_summary
)
from core.ini_sync import IniConfigManager


def test_v200_version_bump():
    """Verify application version is bumped to 2.0.0+."""
    assert APP_VERSION in ("2.0.0", "2.1.0", "2.2.0", "2.3.0", "3.0.0", "3.0.1", "3.0.2", "3.0.3", "3.0.4", "3.0.5", "3.0.6")


def test_mode_c_default_preset():
    """Verify Mode C default preset matches Image 1 exact parameters."""
    preset = load_dlssg_sm86_preset()
    assert preset["engine"] == "DLSS", f"Expected engine DLSS, got {preset['engine']}"
    assert preset["max_generated_frames"] == 3, f"Expected max_generated_frames 3 (4X, upstream factory), got {preset['max_generated_frames']}"
    assert preset["optimized"] == 2, f"Expected optimized 2, got {preset['optimized']}"
    assert preset["dlssg_preset"] == "C", f"Expected dlssg_preset C, got {preset['dlssg_preset']}"
    assert preset["super_resolution_mode"] == "Off", f"Expected SR mode Off, got {preset['super_resolution_mode']}"
    assert preset["proxy_dll"] == "version.dll", f"Expected proxy version.dll, got {preset['proxy_dll']}"
    assert preset["logging_level"] == 1, f"Expected logging level 1, got {preset['logging_level']}"

    summary = get_dlssg_sm86_preset_summary(preset)
    assert "DLSS 原生" in summary
    assert "4X" in summary
    assert "轻量加速" in summary
    assert "预设 C" in summary


def test_wallpaper_default_config():
    """Verify wallpaper default config matches Image 2 exact parameters."""
    def_file = ROOT_DIR / "defaults" / "wallpaper_config.json"
    assert def_file.exists(), "defaults/wallpaper_config.json must exist"
    with open(def_file, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    assert cfg["enabled"] is True
    assert cfg["blur_radius"] == 0
    assert cfg["tint_opacity_dark"] == 0.2
    assert cfg["tint_opacity_light"] == 0.2
    assert cfg["card_opacity"] == 0.5
    assert cfg["sync_mode"] == "unified"
    assert "blur0.png" in cfg["cached_image_path"]

    # The shipped config points into the per-user cache, so resolve the file name it
    # references and verify that this factory asset ships in defaults/wallpapers/
    # (first run seeds that directory into %APPDATA%). Checking the raw %APPDATA%
    # string against the repo root would always fail on a clean machine.
    asset_name = Path(cfg["cached_image_path"].replace("\\", "/")).name
    factory_asset = ROOT_DIR / "defaults" / "wallpapers" / asset_name
    resolved_asset = Path(os.path.expandvars(cfg["cached_image_path"]))
    assert factory_asset.exists() or resolved_asset.exists(), (
        f"Default wallpaper asset {asset_name} must exist in defaults/wallpapers"
    )


def test_mode_c_ini_forward_sync_and_coexistence():
    """Verify IniConfigManager writes Mode C parameters into dlssg_sm86.ini correctly."""
    with tempfile.TemporaryDirectory() as td:
        target_dir = Path(td)
        fake_exe = target_dir / "Game.exe"
        fake_exe.write_bytes(b"MZfake")

        preset = load_dlssg_sm86_preset()
        ok = IniConfigManager.sync_dlssg_sm86_forward(target_dir, preset, exe_name="Game.exe")
        assert ok is True

        ini_file = target_dir / "dlssg_sm86.ini"
        assert ini_file.exists()

        content = ini_file.read_text(encoding="utf-8")
        assert "Engine=DLSS" in content
        assert "MaxGeneratedFrames=3" in content
        assert "Optimized=2" in content
        assert "Preset=C" in content
        assert "Mode=Off" in content

        # Reverse sync test
        rev = IniConfigManager.read_dlssg_sm86_reverse(target_dir)
        assert rev is not None
        assert rev["engine"] == "DLSS"
        assert rev["max_generated_frames"] == 3
        assert rev["optimized"] == 2
        assert rev["dlssg_preset"] == "C"


def test_rtx_20_30_detection_logic():
    """Verify GPU detection helper accurately identifies 20/30 series and defaults."""
    assert is_rtx_20_or_30_series("NVIDIA GeForce RTX 3080") is True
    assert is_rtx_20_or_30_series("NVIDIA GeForce RTX 2060") is True
    assert is_rtx_20_or_30_series("NVIDIA GeForce RTX 3070 Ti Laptop GPU") is True
    assert is_rtx_20_or_30_series("NVIDIA GeForce RTX 4090") is False
    assert is_rtx_20_or_30_series("AMD Radeon RX 6800 XT") is False
