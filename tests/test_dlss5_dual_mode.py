# -*- coding: utf-8 -*-
"""
Unit and Integration Test Suite for DLSS 5 Dual-Mode Base Upgrade (Phase 1 to Phase 4).
Tests:
1. Physical Assets & Constants Definition (Phase 1)
2. UI Banner, Mode Selection & Assets Dynamic Info (Phase 2)
3. Pre-injection Mutex Cleanup, Dual-Mode Injection & Restore (Phase 3)
4. UI State Synchronization & Strict Default Policy (Phase 4)
5. Mode A Figure 1 Default Settings & Mode B F12 Hotkey Verification
6. Hook Point Synchronization for both Mode A and Mode B
"""

import os
import sys
import shutil
import tempfile
import configparser
import pytest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from apps.app6_dlss5.engine.injector import (
    DLSS5_ENGINE_MODES,
    DEFAULT_DLSS5_MODE,
    CONFLICT_DLSS_ADDONS,
    clean_conflicting_addons,
    scan_plugin_source_assets,
    check_game_dlss5_status,
    sync_dlss5_hook_point,
    DLSS5Injector,
    LOCAL_ASSETS_DIR
)


def test_phase1_constants_and_assets():
    """Validates Phase 1 constants and presence of physical dual-base assets."""
    assert DEFAULT_DLSS5_MODE == "MODE_A"
    assert "MODE_A" in DLSS5_ENGINE_MODES
    assert "MODE_B" in DLSS5_ENGINE_MODES

    mode_a = DLSS5_ENGINE_MODES["MODE_A"]
    mode_b = DLSS5_ENGINE_MODES["MODE_B"]

    assert mode_a["addon_file"] == "renodx-dlss.addon64"
    assert mode_b["addon_file"] == "Lecram-v12.addon64"
    assert mode_a["ini_section"] == "RenoDX DLSS"
    assert mode_b["ini_section"] == "RenoDX DLSS5"

    for required_conflict in ["renodx-dlss.addon64", "Lecram-v12.addon64", "renodx-dlss5-v11.9.addon64"]:
        assert required_conflict in CONFLICT_DLSS_ADDONS

    # Check physical assets in package
    assert (LOCAL_ASSETS_DIR / "renodx-dlss.addon64").is_file(), "Mode A asset renodx-dlss.addon64 must exist"
    assert (LOCAL_ASSETS_DIR / "Lecram-v12.addon64").is_file(), "Mode B asset Lecram-v12.addon64 must exist"
    assert (LOCAL_ASSETS_DIR / "renodx-dlss5-Lecram-v12.5.addon64").is_file(), "Mode B v12.5 asset must exist"
    assert (LOCAL_ASSETS_DIR / "dxgi.dll").is_file(), "dxgi.dll must exist"
    assert (LOCAL_ASSETS_DIR / "runtimes" / "nvngx_dlssnr_rtx50.dll").is_file()
    assert (LOCAL_ASSETS_DIR / "runtimes" / "nvngx_dlssnr_rtx20_30_40.dll").is_file()


def test_phase2_asset_scanning_and_dual_mode_selection():
    """Validates scanning of Mode A and Mode B assets."""
    assets_a = scan_plugin_source_assets(LOCAL_ASSETS_DIR, mode="MODE_A")
    assert assets_a["exists"] is True
    assert assets_a["mode_a_exists"] is True
    assert assets_a["mode_b_exists"] is True
    assert assets_a["mode_a_size_mb"] > 0
    assert assets_a["mode_b_size_mb"] > 0
    assert assets_a["addon_name"] == "renodx-dlss.addon64"

    assets_b = scan_plugin_source_assets(LOCAL_ASSETS_DIR, mode="MODE_B")
    assert assets_b["addon_name"] == "renodx-dlss5-Lecram-v12.5.addon64"


def test_phase3_mutex_cleanup():
    """Tests 3.1 mutex cleanup: removes conflicting addons while preserving Mode B MFG unlocker."""
    with tempfile.TemporaryDirectory() as tmpdir:
        td = Path(tmpdir)
        (td / "renodx-dlss.addon64").write_bytes(b"mode_a")
        (td / "Lecram-v12.addon64").write_bytes(b"mode_b")
        (td / "renodx-dlss5-v11.9.addon64").write_bytes(b"legacy")
        (td / "renodx-mfgunlock.addon64").write_bytes(b"mfg_protect")

        ok, msg, removed = clean_conflicting_addons(td, keep_addon="renodx-dlss.addon64")
        assert ok is True
        assert (td / "renodx-dlss.addon64").exists(), "Keep addon must not be removed"
        assert not (td / "Lecram-v12.addon64").exists(), "Conflicting Mode B addon must be removed"
        assert not (td / "renodx-dlss5-v11.9.addon64").exists(), "Conflicting legacy addon must be removed"
        assert (td / "renodx-mfgunlock.addon64").exists(), "Mode B MFG unlocker must NEVER be deleted"


def test_phase3_mode_a_and_mode_b_injection_lifecycle():
    """Tests 3.2 injection and 3.3 status detection for Mode A and switching to Mode B."""
    with tempfile.TemporaryDirectory() as tmpdir:
        game_dir = Path(tmpdir) / "bin"
        game_dir.mkdir(parents=True, exist_ok=True)
        (game_dir / "game.exe").write_bytes(b"MZ" + b"\x00" * 1024)

        # Initial status: not installed
        stat0 = check_game_dlss5_status(str(game_dir))
        assert stat0["is_injected"] is False
        assert "未安装" in stat0["mode_status_display"]

        # Step 1: Inject Mode A
        ok_a, msg_a = DLSS5Injector.inject(str(game_dir), arch_choice="auto", mode="MODE_A")
        assert ok_a is True, f"Mode A injection failed: {msg_a}"
        assert (game_dir / "renodx-dlss.addon64").exists()
        assert (game_dir / "dxgi.dll").exists()
        assert (game_dir / "nvngx_dlssnr.dll").exists()
        assert not (game_dir / "Lecram-v12.addon64").exists()

        stat_a = check_game_dlss5_status(str(game_dir))
        assert stat_a["is_injected"] is True
        assert stat_a["detected_mode"] == "MODE_A"
        assert "模式 A · ShortFuse 原生底座" in stat_a["mode_status_display"]

        # Step 2: Switch & Inject Mode B (verify mutex cleanup removes Mode A)
        ok_b, msg_b = DLSS5Injector.inject(str(game_dir), arch_choice="auto", mode="MODE_B")
        assert ok_b is True, f"Mode B injection failed: {msg_b}"
        assert list(game_dir.glob("*Lecram*.addon64")), "Mode B addon must be deployed"
        assert not (game_dir / "renodx-dlss.addon64").exists(), "Mode A addon must be cleaned during Mode B injection"

        stat_b = check_game_dlss5_status(str(game_dir))
        assert stat_b["is_injected"] is True
        assert stat_b["detected_mode"] == "MODE_B"
        assert "模式 B · Lecram v12.5 扩展底座" in stat_b["mode_status_display"]

        # Step 3: Test legacy detection
        for _f in game_dir.glob("*Lecram*.addon64"):
            _f.unlink()
        (game_dir / "renodx-dlss5-v11.9.addon64").write_bytes(b"legacy")
        stat_legacy = check_game_dlss5_status(str(game_dir))
        assert "检测到旧版插件 (v11.9)" in stat_legacy["mode_status_display"]

        # Step 4: Test 3.4 full uninstallation and restore
        ok_res, msg_res = DLSS5Injector.restore(str(game_dir))
        assert ok_res is True
        stat_end = check_game_dlss5_status(str(game_dir))
        assert stat_end["is_injected"] is False
        assert not (game_dir / "renodx-dlss.addon64").exists()
        assert not (game_dir / "Lecram-v12.addon64").exists()
        assert not (game_dir / "renodx-dlss5-v11.9.addon64").exists()
        assert not (game_dir / "dxgi.dll").exists()
        assert not (game_dir / "nvngx_dlssnr.dll").exists()


def test_phase4_ui_elements_and_default_behavior():
    """Tests UI components, banner text, mode switching, and default policy."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    from apps.app6_dlss5.app import DLSS5MainWindow

    win = DLSS5MainWindow()

    # 2.1 Banner subtitle check
    sub_title_label = win.findChild(object, "dlss5_sub_title")
    assert sub_title_label is not None
    assert "搭载 ShortFuse 原生底座 (模式 A 默认) / Lecram v12 扩展底座 (模式 B 可选)" in sub_title_label.text()
    assert "共用二号软件游戏库与 RHI 底座 · 自动兼容多帧生成共存" in sub_title_label.text()

    # 2.2 Mode selection widget check
    assert hasattr(win, "combo_dlss5_mode")
    assert hasattr(win, "lbl_mode_hint")
    assert win.combo_dlss5_mode.count() == 2
    assert win.combo_dlss5_mode.currentIndex() == 0, "Default must be Mode A (index 0)"
    assert win.combo_dlss5_mode.currentData() == "MODE_A"
    assert "当前已选模式 A (默认)" in win.lbl_mode_hint.text()

    # Switch to Mode B in UI
    win.combo_dlss5_mode.setCurrentIndex(1)
    assert win.combo_dlss5_mode.currentData() == "MODE_B"
    assert "当前已选模式 B (可选)" in win.lbl_mode_hint.text()
    assert "F12" in win.lbl_mode_hint.text()
    assert "F12" in win.combo_dlss5_mode.currentText()

    # Switch back to Mode A
    win.combo_dlss5_mode.setCurrentIndex(0)
    assert win.combo_dlss5_mode.currentData() == "MODE_A"
    assert "当前已选模式 A (默认)" in win.lbl_mode_hint.text()

    # Sync mode selector test
    win._sync_mode_selector("MODE_B")
    assert win.combo_dlss5_mode.currentIndex() == 1
    assert "当前已选模式 B (可选)" in win.lbl_mode_hint.text()

    win._sync_mode_selector("MODE_A")
    assert win.combo_dlss5_mode.currentIndex() == 0
    assert "当前已选模式 A (默认)" in win.lbl_mode_hint.text()

    win.close()


def test_mode_a_figure1_parameters_and_mode_b_f12_hotkey():
    """
    Verifies that injecting Mode A writes the exact default parameters shown in Figure 1,
    and injecting Mode B writes KeyOverlay=123,0,0,0 (F12).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        game_dir = Path(tmpdir) / "bin"
        game_dir.mkdir(parents=True, exist_ok=True)
        (game_dir / "game.exe").write_bytes(b"MZ" + b"\x00" * 1024)

        # Inject Mode A
        ok_a, _ = DLSS5Injector.inject(str(game_dir), arch_choice="auto", mode="MODE_A")
        assert ok_a is True

        reshade_ini = game_dir / "ReShade.ini"
        assert reshade_ini.exists()

        cp = configparser.ConfigParser(interpolation=None, strict=False)
        cp.read(reshade_ini, encoding="utf-8")

        # Check Mode A shortcut key: Home (36,0,0,0)
        assert cp.get("OVERLAY", "KeyOverlay", fallback="") == "36,0,0,0"

        # Check real game-generated sections [RENODX-DLSS] and [RENODX-DLSS-preset1]
        assert cp.has_section("RENODX-DLSS"), "Must have [RENODX-DLSS] section"
        assert cp.get("RENODX-DLSS", "DirectNeuralRenderingHookStage") == "1"
        assert cp.has_section("RENODX-DLSS-preset1"), "Must have [RENODX-DLSS-preset1] section"
        sec_renodx_p1 = cp["RENODX-DLSS-preset1"]
        assert sec_renodx_p1.get("DirectNeuralRenderingStyle") == "2"
        assert sec_renodx_p1.get("DirectNeuralRenderingAutoMask") == "1"
        assert sec_renodx_p1.get("DirectNeuralRenderingSkinStructureStrength") == "0.8"
        assert sec_renodx_p1.get("DirectNeuralRenderingProcessingScale") == "100"
        assert sec_renodx_p1.get("DirectNeuralRenderingFilterDomain") == "0"
        assert sec_renodx_p1.get("DirectNeuralRenderingPreset") == "2"

        # Check native renodx-dlss.addon64 required sections [renodx] and [renodx-preset1]
        assert cp.has_section("renodx"), "Must have lowercase [renodx] section for FNV-1a lookup"
        assert cp.get("renodx", "Preset") == "1", "Preset in [renodx] must be '1' (Preset #1), not 'My look'"
        assert cp.get("renodx", "DirectNeuralRenderingStatus") == "1"

        assert cp.has_section("renodx-preset1"), "Must have [renodx-preset1] section"
        sec_preset1 = cp["renodx-preset1"]
        assert sec_preset1.get("DirectNeuralRenderingStyle") == "2"
        assert sec_preset1.get("DirectNeuralRenderingAutoMask") == "1"
        assert sec_preset1.get("DirectNeuralRenderingSkinStructureStrength") == "0.800000"
        assert sec_preset1.get("DirectNeuralRenderingFilterDomain") == "0"
        assert sec_preset1.get("DirectNeuralRenderingIntensity") == "1.000000"

        # Check that ReShadePreset.ini also received the sections
        preset_ini = game_dir / "ReShadePreset.ini"
        assert preset_ini.exists()
        cp_preset = configparser.ConfigParser(interpolation=None, strict=False)
        cp_preset.read(preset_ini, encoding="utf-8")
        assert cp_preset.has_section("renodx")
        assert cp_preset.has_section("renodx-preset1")

        # Check Figure 1 settings in [RenoDX DLSS]
        assert cp.has_section("RenoDX DLSS")
        sec_a = cp["RenoDX DLSS"]
        assert sec_a.get("OptionsMode") == "0"  # DLSS-NR
        assert sec_a.get("DirectNeuralRenderingIntensity") == "1.000000"  # Overall Intensity: 1.00
        assert sec_a.get("DirectNeuralRenderingStyle") == "2"  # Model: Model C
        assert sec_a.get("DirectNeuralRenderingLocalStructureStrength") == "1.000000"  # Structure Intensity: 1.00
        assert sec_a.get("DirectNeuralRenderingLocalToneStrength") == "1.000000"  # Tone Intensity: 1.00
        assert sec_a.get("DirectNeuralRenderingAutoMask") == "1"  # Character Mask: On
        assert sec_a.get("DirectNeuralRenderingSkinStructureStrength") == "0.800000"  # Character Intensity: 0.80
        assert sec_a.get("DirectNeuralRenderingProcessingScale") == "100.000000"  # Resolution Scale: 100%
        assert sec_a.get("DirectNeuralRenderingFilterDomain") == "0"  # Scaling Domain: scRGB-nl
        assert sec_a.get("DirectNeuralRenderingDownsampleFilter") == "0"  # Downsample Filter: Area
        assert sec_a.get("DirectNeuralRenderingUpsampleFilter") == "0"  # Upsample Filter: Bilinear
        assert sec_a.get("DirectNeuralRenderingScaleReconstruction") == "0"  # Scale Reconstruction: RGB residual
        assert sec_a.get("DirectNeuralRenderingPreset") == "2"  # Preset: Preset B
        assert sec_a.get("DirectNeuralRenderingEncoding") == "0"  # Encoding: Auto
        assert sec_a.get("DirectNeuralRenderingSignalEncoding") == "0"  # NR Signal Encoding: sRGB
        assert sec_a.get("DirectNeuralRenderingDiffuseWhiteNits") == "100.000000"  # Diffuse White (nits): 100
        assert sec_a.get("DirectNeuralRenderingBlockHudless") == "0"  # Block Hudless: Off
        assert sec_a.get("DirectNeuralRenderingExposure") == "1.000000"  # Exposure: 1.00x
        assert sec_a.get("DirectNeuralRenderingExposureMode") == "1"  # Use Exposure Value: On
        assert sec_a.get("DirectNeuralRenderingModelCorrections") == "0"  # Model Corrections: Off
        assert sec_a.get("DirectNeuralRenderingReuseDlssUpscalingResources") == "0"  # Never

        # Inject Mode B
        ok_b, _ = DLSS5Injector.inject(str(game_dir), arch_choice="auto", mode="MODE_B")
        assert ok_b is True

        cp_b = configparser.ConfigParser(interpolation=None, strict=False)
        cp_b.read(reshade_ini, encoding="utf-8")

        # Check Mode B shortcut key: F12 (123,0,0,0)
        assert cp_b.get("OVERLAY", "KeyOverlay", fallback="") == "123,0,0,0"
        assert cp_b.get("INPUT", "KeyOverlay", fallback="") == "123,0,0,0"
        assert cp_b.get("RenoDX.DLSS5", "NRPanelKey", fallback="") == "123,0,0,0"


def test_hook_point_dual_mode_synchronization():
    """
    Verifies that applying hook points (Upscaled '0', Present '2', Before '1')
    correctly configures both Mode A and Mode B sections, and check_game_dlss5_status
    accurately detects the hook point under both modes.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        game_dir = Path(tmpdir) / "bin"
        game_dir.mkdir(parents=True, exist_ok=True)
        (game_dir / "game.exe").write_bytes(b"MZ" + b"\x00" * 1024)

        # 1. Mode A with Upscaled ("0")
        DLSS5Injector.inject(str(game_dir), arch_choice="auto", mode="MODE_A", hook_point="0")
        stat_a_up = check_game_dlss5_status(str(game_dir))
        assert stat_a_up["hook_point"] == "0"
        assert "之后 (Upscaled" in stat_a_up["hook_point_label"]

        cp = configparser.ConfigParser(interpolation=None, strict=False)
        cp.read(game_dir / "ReShade.ini", encoding="utf-8")
        assert cp.get("RENODX-DLSS", "DirectNeuralRenderingHookStage") == "1"
        assert cp.get("renodx", "DirectNeuralRenderingHookStage") == "1"
        assert cp.get("renodx-preset1", "DirectNeuralRenderingHookStage") == "1"
        assert cp.get("RenoDX DLSS", "DirectNeuralRenderingHookStage") == "1"  # Upscaled in Mode A
        assert cp.get("RenoDX.DLSS5", "NRHookPoint") == "0"  # Upscaled in Mode B

        # 2. Mode A apply Present ("2")
        ok_p, _ = DLSS5Injector.apply_hook_point(str(game_dir), hook_point="2")
        assert ok_p is True
        stat_a_pres = check_game_dlss5_status(str(game_dir))
        assert stat_a_pres["hook_point"] == "2"
        assert "呈现 (Present" in stat_a_pres["hook_point_label"]

        cp.read(game_dir / "ReShade.ini", encoding="utf-8")
        assert cp.get("RENODX-DLSS", "DirectNeuralRenderingHookStage") == "2"
        assert cp.get("renodx", "DirectNeuralRenderingHookStage") == "2"
        assert cp.get("renodx-preset1", "DirectNeuralRenderingHookStage") == "2"
        assert cp.get("RenoDX DLSS", "DirectNeuralRenderingHookStage") == "2"  # Present in Mode A
        assert cp.get("RenoDX.DLSS5", "NRHookPoint") == "2"  # Present in Mode B

        # 3. Switch to Mode B and apply Before / Render ("1")
        DLSS5Injector.inject(str(game_dir), arch_choice="auto", mode="MODE_B", hook_point="1")
        stat_b_before = check_game_dlss5_status(str(game_dir))
        assert stat_b_before["hook_point"] == "1"
        assert "之前 (Before" in stat_b_before["hook_point_label"]

        cp.read(game_dir / "ReShade.ini", encoding="utf-8")
        assert cp.get("RENODX-DLSS", "DirectNeuralRenderingHookStage") == "0"
        assert cp.get("renodx", "DirectNeuralRenderingHookStage") == "0"
        assert cp.get("renodx-preset1", "DirectNeuralRenderingHookStage") == "0"
        assert cp.get("RenoDX DLSS", "DirectNeuralRenderingHookStage") == "0"  # Render in Mode A
        assert cp.get("RenoDX.DLSS5", "NRHookPoint") == "1"  # Render in Mode B

        # 4. Mode B apply Upscaled ("0")
        ok_up, _ = DLSS5Injector.apply_hook_point(str(game_dir), hook_point="0")
        assert ok_up is True
        stat_b_up = check_game_dlss5_status(str(game_dir))
        assert stat_b_up["hook_point"] == "0"
        assert "之后 (Upscaled" in stat_b_up["hook_point_label"]
