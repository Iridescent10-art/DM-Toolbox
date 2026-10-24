# -*- coding: utf-8 -*-
"""
Unit and integration tests for v1.3.30 Mode C: dlssg_for_sm86 integration:
1. BackendType.DLSSG_SM86 and embedded assets verification.
2. Smart Auto GPU routing: RTX 20/30 series preference for Mode C.
3. DLSSG_SM86 patch deployment: exactly 3 items, purging old Scheme C (OptiScaler/XeSS), single proxy rule.
4. INI synchronization and preset management for dlssg_sm86.
5. Coexistence with DLSS 5: zero DXGI collision, SuperResolution Mode=Off.
6. Rollback and mode switching state cleanliness.
7. Preset & Guide Dialogs for Mode C.
8. Proxy hot-swapping from alternatives/ (换，不是加；代理任何时候只放一个).
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# Force UTF-8 for console output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
APP2_DIR = ROOT_DIR / "apps" / "app2_mfg"
APP6_DIR = ROOT_DIR / "apps" / "app6_dlss5"
for p in [ROOT_DIR, APP2_DIR, APP6_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from core.models import GameInfo, BackendType, PatchManifest, QualificationStatus
from core.patcher import PatchEngine
from core.rollback import RollbackEngine
from core.updater import ComponentUpdater
from core.ini_sync import IniConfigManager
from core.optiscaler_config import (
    DEFAULT_DLSSG_SM86_PRESET,
    load_dlssg_sm86_preset,
    save_dlssg_sm86_preset,
    get_dlssg_sm86_preset_summary
)
from core.coexistence import is_dlssg_sm86_binary, detect_dlssg_sm86_slot
from core.state_cleaner import is_dlssg_sm86_present, CleanGameDirectoryState


def test_1_embedded_assets_and_updater():
    print("[TEST 1] Verifying embedded assets for dlssg_sm86...")
    embedded_dir = APP2_DIR / "embedded_components" / "dlssg_sm86" / "v0.4.0"
    assert embedded_dir.exists(), f"Embedded dir missing: {embedded_dir}"
    
    assert (embedded_dir / "version.dll").exists(), "version.dll missing in embedded components"
    assert (embedded_dir / "dlssg_sm86.ini").exists(), "dlssg_sm86.ini missing in embedded components"
    assert (embedded_dir / "dlssg_sm86").is_dir(), "dlssg_sm86 subdirectory missing in embedded components"
    assert (embedded_dir / "dlssg_sm86" / "backend").is_dir(), "dlssg_sm86/backend directory missing"

    # Verify alternatives directory
    alt_dir = embedded_dir / "alternatives"
    assert alt_dir.is_dir(), "alternatives directory missing"
    for alt_dll in ["winmm.dll", "dbghelp.dll", "dinput8.dll", "d3d12.dll", "dxgi.dll"]:
        assert (alt_dir / alt_dll).exists(), f"Alternative proxy missing: {alt_dll}"

    updater = ComponentUpdater()
    cached_dir = updater.get_latest_cached_dir("dlssg_sm86")
    assert cached_dir is not None and Path(cached_dir).exists(), f"Updater failed to locate dlssg_sm86 cached dir: {cached_dir}"
    print("  -> Embedded assets, alternatives, and ComponentUpdater lookup verified successfully!")


def test_2_gpu_smart_auto_preference():
    print("[TEST 2] Verifying RTX 20/30 series preference for Mode C...")
    from core.utils import is_rtx_20_or_30_series

    # RTX 20/30 series (should be True)
    assert is_rtx_20_or_30_series("NVIDIA GeForce RTX 3080") is True
    assert is_rtx_20_or_30_series("NVIDIA GeForce RTX 3060 Laptop GPU") is True
    assert is_rtx_20_or_30_series("GeForce RTX 2070 SUPER") is True
    assert is_rtx_20_or_30_series("NVIDIA GeForce RTX 2060") is True
    assert is_rtx_20_or_30_series("RTX 3090 Ti") is True

    # Other GPUs (should be False)
    assert is_rtx_20_or_30_series("NVIDIA GeForce RTX 4090") is False
    assert is_rtx_20_or_30_series("NVIDIA GeForce RTX 4070") is False
    assert is_rtx_20_or_30_series("GeForce RTX 5080") is False
    assert is_rtx_20_or_30_series("AMD Radeon RX 7900 XTX") is False
    assert is_rtx_20_or_30_series("Intel Arc A770") is False
    assert is_rtx_20_or_30_series("GeForce GTX 1080 Ti") is False
    print("  -> GPU detection accurately maps RTX 20/30 series to True and others to False!")


def test_3_patch_engine_deployment_mode_c():
    print("[TEST 3] Testing PatchEngine deployment of Mode C (dlssg_sm86: 规范三样注入与彻底清理)...")
    td = Path(tempfile.mkdtemp())
    try:
        # 1. Simulate legacy leftovers from old Mode C (OptiScaler / XeSS) and rogue proxies
        (td / "OptiScaler").mkdir(parents=True, exist_ok=True)
        (td / "OptiScaler" / "dummy.txt").write_text("old", encoding="utf-8")
        (td / "XeSS").mkdir(parents=True, exist_ok=True)
        (td / "XeSS" / "libxess.dll").write_text("old xess", encoding="utf-8")
        (td / "OptiScaler.ini").write_text("old opti ini", encoding="utf-8")
        (td / "libxess_fg.dll").write_text("old fg", encoding="utf-8")
        (td / "winmm.dll").write_text("stale winmm proxy", encoding="utf-8")
        (td / "dxgi.dll").write_text("stale dxgi proxy", encoding="utf-8")

        game_exe = td / "game.exe"
        game_exe.write_text("dummy exe", encoding="utf-8")
        dlss_dll = td / "nvngx_dlss.dll"
        dlss_dll.write_text("dummy dlss", encoding="utf-8")

        game = GameInfo(
            name="TestGame",
            source="Custom",
            install_dir=str(td),
            target_dir=str(td),
            exe_path=str(game_exe),
            exe_name=game_exe.name,
            qualification=QualificationStatus.QUALIFIED,
            is_patched=False
        )

        updater = ComponentUpdater()
        patch_engine = PatchEngine(updater=updater)
        success, msg = patch_engine.patch_game(game, requested_backend=BackendType.DLSSG_SM86)
        assert success, f"Patching failed: {msg}"
        print(f"  -> Patch message: {msg[:60]}...")

        # 2. Verify EXACTLY three items were deployed:
        # (1) version.dll, (2) dlssg_sm86.ini, (3) dlssg_sm86/
        assert (td / "version.dll").exists(), "version.dll was not deployed"
        assert (td / "dlssg_sm86.ini").exists(), "dlssg_sm86.ini was not deployed"
        assert (td / "dlssg_sm86").is_dir(), "dlssg_sm86 directory was not deployed"
        assert (td / "dlssg_sm86" / "backend").is_dir(), "dlssg_sm86/backend directory was not deployed"

        # 3. Verify ALL old OptiScaler/XeSS directories and rogue proxies were completely PURGED!
        assert not (td / "OptiScaler").exists(), "Old OptiScaler directory was not cleaned"
        assert not (td / "XeSS").exists(), "Old XeSS directory was not cleaned"
        assert not (td / "OptiScaler.ini").exists(), "Old OptiScaler.ini was not cleaned"
        assert not (td / "libxess_fg.dll").exists(), "Old libxess_fg.dll was not cleaned"
        assert not (td / "winmm.dll").exists(), "Rogue winmm.dll was not cleaned (single proxy rule violated!)"
        assert not (td / "dxgi.dll").exists(), "Rogue dxgi.dll was not cleaned (single proxy rule violated!)"

        # 4. Verify manifest
        manifest_file = td / ".mfg_patch_manifest.json"
        assert manifest_file.exists(), "Manifest file was not saved"
        manifest = PatchManifest.from_json(manifest_file.read_text(encoding="utf-8"))
        assert manifest is not None, "Manifest was not parsed"
        assert manifest.active_backend == BackendType.DLSSG_SM86.value

        # 5. Verify state cleaner recognition
        assert is_dlssg_sm86_present(td) is True
    finally:
        shutil.rmtree(td, ignore_errors=True)
    print("  -> Mode C deployment: 3-item injection, legacy purge, and single proxy rule verified!")


def test_4_ini_sync_and_preset():
    print("[TEST 4] Testing IniConfigManager and presets for dlssg_sm86...")
    td = Path(tempfile.mkdtemp())
    try:
        ini_file = td / "dlssg_sm86.ini"
        ini_file.write_text(
            "[General]\nEnabled=1\n\n[DLSSG]\nOptimized=2\nPreset=Default\n\n[SuperResolution]\nMode=Off\n\n[FrameGeneration]\nEngine=Auto\nMaxGeneratedFrames=2\n",
            encoding="utf-8"
        )

        read_preset = IniConfigManager.read_dlssg_sm86_reverse(td)
        assert read_preset is not None, "Failed to read dlssg_sm86.ini"
        assert read_preset.get("enabled") == 1
        assert read_preset.get("optimized") == 2
        assert read_preset.get("super_resolution_mode") == "Off"
        assert read_preset.get("max_generated_frames") == 2

        # Modify preset and sync forward
        read_preset["optimized"] = 3
        read_preset["max_generated_frames"] = 3
        sync_ok = IniConfigManager.sync_dlssg_sm86_forward(td, read_preset)
        assert sync_ok is True, "Failed to sync forward dlssg_sm86.ini"

        content = ini_file.read_text(encoding="utf-8")
        assert "Optimized=3" in content or "Optimized = 3" in content
        assert "MaxGeneratedFrames=3" in content or "MaxGeneratedFrames = 3" in content
    finally:
        shutil.rmtree(td, ignore_errors=True)
    print("  -> INI sync forward and reverse verified successfully!")


def test_5_dlss5_coexistence_and_sr_off():
    print("[TEST 5] Testing DLSS 5 + Mode C coexistence isolation...")
    td = Path(tempfile.mkdtemp())
    try:
        game_exe = td / "Cyberpunk2077.exe"
        game_exe.write_text("dummy cp2077", encoding="utf-8")
        
        # Simulate DLSS 5 already injected (dxgi.dll ReShade + renodx-dlss.addon64)
        reshade_dll = td / "dxgi.dll"
        reshade_dll.write_text("ReShade 6.8 DLSS5", encoding="utf-8")
        addon = td / "renodx-dlss.addon64"
        addon.write_text("DLSS5 Addon", encoding="utf-8")

        game = GameInfo(
            name="Cyberpunk2077",
            source="Custom",
            install_dir=str(td),
            target_dir=str(td),
            exe_path=str(game_exe),
            exe_name=game_exe.name,
            qualification=QualificationStatus.QUALIFIED,
            is_patched=False
        )

        updater = ComponentUpdater()
        patch_engine = PatchEngine(updater=updater)
        success, msg = patch_engine.patch_game(game, requested_backend=BackendType.DLSSG_SM86)
        assert success, f"Patching failed: {msg}"

        # dxgi.dll MUST NOT be touched/overwritten because it belongs to DLSS 5!
        assert reshade_dll.read_text(encoding="utf-8") == "ReShade 6.8 DLSS5"

        # dlssg_sm86 MUST be deployed to version.dll
        assert (td / "version.dll").exists(), "dlssg_sm86 should use version.dll"

        # SuperResolution Mode MUST be forced to Off to let DLSS 5 handle neural reconstruction exclusively!
        ini_text = (td / "dlssg_sm86.ini").read_text(encoding="utf-8")
        assert "Mode=Off" in ini_text or "Mode = Off" in ini_text, "SuperResolution Mode should be Off when DLSS 5 is present"

        # Now test DLSS 5 injector recognizing dlssg_sm86
        from apps.app6_dlss5.engine.injector import DLSS5Injector
        inj_success, inj_msg = DLSS5Injector.inject(str(td))
        assert inj_success is True, f"DLSS 5 injection failed: {inj_msg}"
        assert "dlssg_for_sm86" in inj_msg, "DLSS 5 injection should acknowledge dlssg_for_sm86 coexistence"
        print("  -> Coexistence message:\n", inj_msg)
    finally:
        shutil.rmtree(td, ignore_errors=True)
    print("  -> DLSS 5 and Mode C dual-channel coexistence verified!")


def test_6_clean_and_rollback():
    print("[TEST 6] Testing RollbackEngine and clean isolation...")
    td = Path(tempfile.mkdtemp())
    try:
        game_exe = td / "game.exe"
        game_exe.write_text("dummy exe", encoding="utf-8")

        game = GameInfo(
            name="TestGame",
            source="Custom",
            install_dir=str(td),
            target_dir=str(td),
            exe_path=str(game_exe),
            exe_name=game_exe.name,
            qualification=QualificationStatus.QUALIFIED,
            is_patched=False
        )

        updater = ComponentUpdater()
        patch_engine = PatchEngine(updater=updater)
        patch_engine.patch_game(game, requested_backend=BackendType.DLSSG_SM86)
        assert (td / "version.dll").exists()
        assert (td / "dlssg_sm86").exists()

        # Execute rollback
        rollback_engine = RollbackEngine()
        rb_ok, rb_msg = rollback_engine.rollback(str(td), game_exe.name)
        assert rb_ok is True, f"Rollback failed: {rb_msg}"

        assert not (td / "version.dll").exists(), "version.dll should be removed after rollback"
        assert not (td / "dlssg_sm86.ini").exists(), "dlssg_sm86.ini should be removed after rollback"
        assert not (td / "dlssg_sm86").exists(), "dlssg_sm86 directory should be removed after rollback"
        assert not (td / ".mfg_patch_manifest.json").exists(), "manifest should be removed"
    finally:
        shutil.rmtree(td, ignore_errors=True)
    print("  -> Rollback and state cleaning verified successfully!")


def test_7_preset_and_guide_dialogs_mode_c():
    print("[TEST 7] Testing Preset & Guide Dialogs for Mode C...")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    from gui_qt import OptiScalerPresetDialog, ModernTranslationGuideDialog

    # 1. Test OptiScalerPresetDialog defaults and initial_modes
    dlg_def = OptiScalerPresetDialog()
    assert dlg_def.stacked_widget.count() == 3, f"Expected 3 tabs in preset dialog, got {dlg_def.stacked_widget.count()}"
    assert hasattr(dlg_def, "combo_sm86_mult"), "Mode C combo_sm86_mult missing in preset dialog"
    assert hasattr(dlg_def, "combo_sm86_opt"), "Mode C combo_sm86_opt missing in preset dialog"
    assert hasattr(dlg_def, "combo_sm86_preset"), "Mode C combo_sm86_preset missing in preset dialog"
    assert hasattr(dlg_def, "combo_sm86_engine"), "Mode C combo_sm86_engine missing in preset dialog"
    assert hasattr(dlg_def, "combo_sm86_sr"), "Mode C combo_sm86_sr missing in preset dialog"
    assert hasattr(dlg_def, "combo_sm86_proxy"), "Mode C combo_sm86_proxy missing in preset dialog"

    dlg_a = OptiScalerPresetDialog(initial_mode="A")
    assert dlg_a.stacked_widget.currentIndex() == 0, f"Expected tab 0 for Mode A, got {dlg_a.stacked_widget.currentIndex()}"

    dlg_b = OptiScalerPresetDialog(initial_mode="B")
    assert dlg_b.stacked_widget.currentIndex() == 1, f"Expected tab 1 for Mode B, got {dlg_b.stacked_widget.currentIndex()}"

    dlg_c = OptiScalerPresetDialog(initial_mode="C")
    assert dlg_c.stacked_widget.currentIndex() == 2, f"Expected tab 2 for Mode C, got {dlg_c.stacked_widget.currentIndex()}"

    # 2. Test ModernTranslationGuideDialog tabs
    dlg_guide = ModernTranslationGuideDialog()
    assert dlg_guide.tabs.count() == 3, f"Expected 3 tabs in guide dialog, got {dlg_guide.tabs.count()}"
    print("  -> OptiScalerPresetDialog and ModernTranslationGuideDialog verified successfully!")


def test_8_proxy_hot_swap_alternatives():
    print("[TEST 8] Testing proxy hot-swapping from alternatives/ ('换，不是加' & '代理任何时候只放一个')...")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from gui_qt import OptiScalerPresetDialog

    td = Path(tempfile.mkdtemp())
    try:
        game_exe = td / "game.exe"
        game_exe.write_text("dummy exe", encoding="utf-8")

        game = GameInfo(
            name="TestGame",
            source="Custom",
            install_dir=str(td),
            target_dir=str(td),
            exe_path=str(game_exe),
            exe_name=game_exe.name,
            qualification=QualificationStatus.QUALIFIED,
            is_patched=False
        )

        updater = ComponentUpdater()
        patch_engine = PatchEngine(updater=updater)
        # Patch Mode C initial state (default proxy: version.dll)
        success, msg = patch_engine.patch_game(game, requested_backend=BackendType.DLSSG_SM86)
        assert success is True
        assert (td / "version.dll").exists()
        assert not (td / "winmm.dll").exists()

        dlg = OptiScalerPresetDialog(game=game)

        # 1. Swap from version.dll -> winmm.dll
        dlg._swap_dlssg_sm86_proxy(str(td), "winmm.dll")
        assert not (td / "version.dll").exists(), "version.dll was not removed on proxy swap!"
        assert (td / "winmm.dll").exists(), "winmm.dll was not deployed on proxy swap!"
        assert not (td / "dbghelp.dll").exists()
        assert not (td / "dxgi.dll").exists()

        # 2. Swap from winmm.dll -> dbghelp.dll
        dlg._swap_dlssg_sm86_proxy(str(td), "dbghelp.dll")
        assert not (td / "winmm.dll").exists(), "winmm.dll was not removed on proxy swap!"
        assert (td / "dbghelp.dll").exists(), "dbghelp.dll was not deployed on proxy swap!"

        # 3. Swap from dbghelp.dll -> back to version.dll
        dlg._swap_dlssg_sm86_proxy(str(td), "version.dll")
        assert not (td / "dbghelp.dll").exists(), "dbghelp.dll was not removed on proxy swap!"
        assert (td / "version.dll").exists(), "version.dll was not deployed on proxy swap!"

        # 4. Verify reverse detection reads active proxy from disk
        cfg = IniConfigManager.read_dlssg_sm86_reverse(td)
        assert cfg is not None
        assert cfg.get("proxy_dll") == "version.dll"

        print("  -> Proxy hot-swapping ('换，不是加') and single proxy enforcement verified!")
    finally:
        shutil.rmtree(td, ignore_errors=True)


if __name__ == "__main__":
    print("=== Running v1.3.30 Mode C (dlssg_for_sm86) Verification Suite ===")
    test_1_embedded_assets_and_updater()
    test_2_gpu_smart_auto_preference()
    test_3_patch_engine_deployment_mode_c()
    test_4_ini_sync_and_preset()
    test_5_dlss5_coexistence_and_sr_off()
    test_6_clean_and_rollback()
    test_7_preset_and_guide_dialogs_mode_c()
    test_8_proxy_hot_swap_alternatives()
    print("=== ALL 8 TESTS PASSED SUCCESSFULLY! ===")
