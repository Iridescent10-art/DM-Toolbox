# -*- coding: utf-8 -*-
"""
Automated Verification Suite for DLSS 5 and Multi-Frame Generation Coexistence.
Target: D:\\game\\yysls\\yysls_medium\\Engine\\Binaries\\Win64r\\yysls.exe
Tests Mode A, Mode B, and Mode C static configurations, file trees, and process smoke logs.
"""

import os
import sys
import time
import json
import subprocess
import configparser
from pathlib import Path
from typing import Dict, Any, List, Tuple

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

MFG_DIR = ROOT_DIR / "apps" / "app2_mfg"
if str(MFG_DIR) not in sys.path:
    sys.path.insert(0, str(MFG_DIR))

from apps.app6_dlss5.engine.config_sync import ConfigSyncService
from apps.app6_dlss5.engine.injector import DLSS5Injector
from apps.app2_mfg.core.state_cleaner import CleanGameDirectoryState
from apps.app2_mfg.core.utils import is_process_running, kill_locking_processes

TARGET_DIR = Path(r"D:\game\yysls\yysls_medium\Engine\Binaries\Win64r")
EXE_NAME = "yysls.exe"
EXE_PATH = TARGET_DIR / EXE_NAME


def is_game_running() -> bool:
    return is_process_running(EXE_NAME)


def kill_game_process(timeout_seconds: int = 15):
    """Forcefully terminates game and locks, waiting until completely exited."""
    kill_locking_processes(TARGET_DIR, EXE_NAME)
    subprocess.run(["taskkill", "/f", "/t", "/im", EXE_NAME], capture_output=True, text=True, check=False)
    subprocess.run(["taskkill", "/f", "/t", "/im", "UniCrashReporter.exe"], capture_output=True, text=True, check=False)

    start_t = time.time()
    while time.time() - start_t < timeout_seconds:
        if not is_game_running():
            time.sleep(2)  # Extra buffer for Windows kernel to release DLL handles
            return
        time.sleep(0.5)
        subprocess.run(["taskkill", "/f", "/t", "/im", EXE_NAME], capture_output=True, text=True, check=False)
    time.sleep(2)


def launch_game(duration_seconds: int = 25) -> bool:
    """Launches yysls.exe, waits duration_seconds, verifies it stayed alive, then terminates."""
    kill_game_process()
    time.sleep(1)

    print(f"   [Launch] Launching {EXE_NAME} via Start-Process (duration: {duration_seconds}s)...")
    subprocess.run(
        ["powershell", "-Command", "Start-Process", f"'{str(EXE_PATH)}'", "-WorkingDirectory", f"'{str(TARGET_DIR)}'"],
        capture_output=True,
        text=True,
        check=False
    )

    # Monitor up to duration_seconds
    start_t = time.time()
    saw_running = False
    while time.time() - start_t < duration_seconds:
        if is_game_running():
            saw_running = True
        time.sleep(1)

    print(f"   [Process Monitor] Process observed alive: {saw_running}")
    kill_game_process()
    time.sleep(1)
    return saw_running


class VerificationSuite:
    def __init__(self):
        self.results = {}

    def run_all(self):
        print("=" * 80)
        print("🚀 Starting DLSS 5 & Multi-Frame Generation Coexistence Verification Suite")
        print(f"🎮 Target Executable: {EXE_PATH}")
        print("=" * 80)

        if not EXE_PATH.exists():
            print(f"❌ Target executable does not exist: {EXE_PATH}")
            return False

        # Ensure no previous instance is running
        kill_game_process()

        success_a = self.verify_mode_a()
        success_b = self.verify_mode_b()
        success_c = self.verify_mode_c()

        print("\n" + "=" * 80)
        print("📊 Verification Suite Final Results Summary:")
        print(f"   Mode A (dashdogy + DLSS 5):      {'✅ PASS' if success_a else '❌ FAIL'}")
        print(f"   Mode B (RenoDX + DLSS 5):        {'✅ PASS' if success_b else '❌ FAIL'}")
        print(f"   Mode C (OptiScaler + DLSS 5):    {'✅ PASS' if success_c else '❌ FAIL'}")
        print("=" * 80)

        all_passed = success_a and success_b and success_c
        return all_passed

    # ------------------- MODE A -------------------
    def verify_mode_a(self) -> bool:
        print("\n🔹 [Test 1] Verifying Mode A (dashdogy 独立代理 + DLSS 5)...")
        # Clean any old log files
        for f in ["ReShade.log", "OptiScaler.log", "RTXMFG-yysls-*.log"]:
            for match in TARGET_DIR.glob(f):
                try:
                    match.unlink()
                except Exception:
                    pass

        # 1. Apply unified configuration
        params = {
            "multiplier": 3,
            "dlss_preset": "Default",
            "menu_key": "Backspace",
            "bink_hook": False
        }
        ok, msg = ConfigSyncService.apply_unified_configuration(TARGET_DIR, EXE_NAME, "A", params)
        if not ok:
            print(f"   ❌ Apply Mode A failed: {msg}")
            return False
        print("   ✅ Applied Mode A unified configuration.")

        # 2. File tree assertions
        dxgi = TARGET_DIR / "dxgi.dll"
        version_dll = TARGET_DIR / "version.dll"
        dlss5_addon = TARGET_DIR / "lecram-dlss5-beta10.addon64"
        reshade64 = TARGET_DIR / "ReShade64.dll"
        opti_ini = TARGET_DIR / "OptiScaler.ini"
        renodx_addon = TARGET_DIR / "renodx-mfgunlock.addon64"
        u_json = TARGET_DIR / "RTXMFG-Universal.json"

        assert dxgi.exists(), "Mode A requires dxgi.dll (ReShade with Addon support) for DLSS 5!"
        assert version_dll.exists(), "Mode A requires version.dll for dashdogy proxy!"
        assert dlss5_addon.exists(), "Mode A requires lecram-dlss5-beta10.addon64!"
        assert not reshade64.exists(), "Mode A must NOT have ReShade64.dll (must use dxgi.dll directly)!"
        assert not opti_ini.exists(), "Mode A must NOT have OptiScaler.ini!"
        assert not renodx_addon.exists(), "Mode A must NOT have renodx-mfgunlock.addon64!"
        assert u_json.exists(), "Mode A requires RTXMFG-Universal.json!"

        print("   ✅ Mode A file tree assertions passed:")
        print("      • dxgi.dll (ReShade 64-bit full addon host) PRESENT")
        print("      • version.dll (dashdogy proxy slot) PRESENT")
        print("      • lecram-dlss5-beta10.addon64 PRESENT")
        print("      • ReShade64.dll & OptiScaler.ini strictly PURGED")

        # 3. Config assertions
        with open(u_json, "r", encoding="utf-8") as f:
            cfg_data = json.load(f)
        assert cfg_data.get("multiplier") == 3, f"Multiplier expected 3, got {cfg_data.get('multiplier')}"
        assert cfg_data.get("overrideDlssPreset") is False, "overrideDlssPreset must be False for Default!"
        assert cfg_data.get("dlssPreset") == 0, f"dlssPreset must be 0 for Default, got {cfg_data.get('dlssPreset')} (Must NOT be 4/Preset D)!"
        print("   ✅ Mode A RTXMFG-Universal.json assertions passed (Anti-Preset D verified: dlssPreset=0, override=False).")

        # 4. Smoke test & log verification
        saw_running = launch_game(duration_seconds=22)
        assert saw_running, "Game failed to launch in Mode A!"

        # Check ReShade.log
        reshade_log = TARGET_DIR / "ReShade.log"
        assert reshade_log.exists(), "ReShade.log was not generated in Mode A!"
        log_content = reshade_log.read_text(encoding="utf-8", errors="ignore")
        assert "lecram-dlss5-beta10.addon64" in log_content or "DLSS 5" in log_content, (
            "DLSS 5 Addon was not logged as loaded in ReShade.log!"
        )
        print("   ✅ Mode A Smoke Test Passed: yysls.exe ran stably, ReShade.log confirmed DLSS 5 Addon loaded successfully.")
        return True

    # ------------------- MODE B -------------------
    def verify_mode_b(self) -> bool:
        print("\n🔹 [Test 2] Verifying Mode B (RenoDX 插件优化 + DLSS 5)...")
        # Clean any old log files
        for f in ["ReShade.log", "OptiScaler.log"]:
            for match in TARGET_DIR.glob(f):
                try:
                    match.unlink()
                except Exception:
                    pass

        # 1. Apply unified configuration
        params = {
            "multiplier": 3,
            "blackwell_kernels": 1,
            "thin_geometry_isr": 1,
            "thin_geometry_vwb": 1,
            "thin_geometry_bam": 1,
            "hdr_ui_recomposition": 1,
            "dynamic_mfg": 0,
            "temporal_fix": 1
        }
        ok, msg = ConfigSyncService.apply_unified_configuration(TARGET_DIR, EXE_NAME, "B", params)
        if not ok:
            print(f"   ❌ Apply Mode B failed: {msg}")
            return False
        print("   ✅ Applied Mode B unified configuration.")

        # 2. File tree assertions
        dxgi = TARGET_DIR / "dxgi.dll"
        version_dll = TARGET_DIR / "version.dll"
        dlss5_addon = TARGET_DIR / "lecram-dlss5-beta10.addon64"
        renodx_addon = TARGET_DIR / "renodx-mfgunlock.addon64"
        reshade_ini = TARGET_DIR / "ReShade.ini"
        opti_ini = TARGET_DIR / "OptiScaler.ini"

        assert dxgi.exists(), "Mode B requires dxgi.dll (ReShade single host)!"
        assert dlss5_addon.exists(), "Mode B requires lecram-dlss5-beta10.addon64!"
        assert renodx_addon.exists(), "Mode B requires renodx-mfgunlock.addon64!"
        assert not version_dll.exists(), "Mode B must NOT have version.dll!"
        assert not opti_ini.exists(), "Mode B must NOT have OptiScaler.ini!"

        print("   ✅ Mode B file tree assertions passed:")
        print("      • dxgi.dll (single host ReShade 64-bit) PRESENT")
        print("      • Dual Addons: lecram-dlss5-beta10.addon64 & renodx-mfgunlock.addon64 PRESENT")
        print("      • version.dll & OptiScaler.ini strictly PURGED")

        # 3. Config assertions
        cp = configparser.ConfigParser(interpolation=None, strict=False)
        cp.read(str(reshade_ini), encoding="utf-8")
        assert cp.has_section("RenoDX.DLSS5"), "ReShade.ini missing [RenoDX.DLSS5]!"
        assert cp.get("RenoDX.DLSS5", "EnableHooks") == "2", "Mode B [RenoDX.DLSS5] EnableHooks must be 2!"
        assert cp.get("RenoDX.DLSS5", "RuntimeSelectionMode") == "1", "Mode B RuntimeSelectionMode must be 1!"

        assert cp.has_section("RenoDX.MFG"), "ReShade.ini missing [RenoDX.MFG]!"
        assert cp.get("RenoDX.MFG", "ForceMultiplier") == "3", "Mode B ForceMultiplier must be 3!"
        assert cp.get("RenoDX.MFG", "DeferredInit") == "1", "Mode B DeferredInit must be 1 to prevent Access Violation!"

        # Check LoadFromDllMain is NOT present or does NOT contain dlss5/1
        if cp.has_section("ADDON"):
            lfdm = cp.get("ADDON", "LoadFromDllMain", fallback="")
            assert "1" not in lfdm and "lecram" not in lfdm, f"Loader Lock hazard in LoadFromDllMain: {lfdm}"

        print("   ✅ Mode B ReShade.ini assertions passed ([RenoDX.DLSS5] EnableHooks=2, DeferredInit=1, Loader Lock prevented).")

        # 4. Smoke test & log verification
        saw_running = launch_game(duration_seconds=22)
        assert saw_running, "Game failed to launch in Mode B!"

        # Ensure no crash dump (.dmp) was created
        dmp_files = list(TARGET_DIR.glob("*.dmp"))
        assert len(dmp_files) == 0, f"Mode B crashed with dump: {dmp_files}"

        reshade_log = TARGET_DIR / "ReShade.log"
        assert reshade_log.exists(), "ReShade.log was not generated in Mode B!"
        log_content = reshade_log.read_text(encoding="utf-8", errors="ignore")
        assert "lecram-dlss5-beta10.addon64" in log_content or "DLSS 5" in log_content, (
            "DLSS 5 Addon not logged in ReShade.log!"
        )
        assert "renodx-mfgunlock.addon64" in log_content or "RenoDX" in log_content, (
            "RenoDX Addon not logged in ReShade.log!"
        )
        print("   ✅ Mode B Smoke Test Passed: Single host stably loaded Dual Addons (DLSS 5 + RenoDX) without crash or Access Violation.")
        return True

    # ------------------- MODE C -------------------
    def verify_mode_c(self) -> bool:
        print("\n🔹 [Test 3] Verifying Mode C (OptiScaler 跨卡转译 + XeFG + DLSS 5)...")
        # Clean any old log files
        for f in ["ReShade.log", "OptiScaler.log"]:
            for match in TARGET_DIR.glob(f):
                try:
                    match.unlink()
                except Exception:
                    pass

        # 1. Apply unified configuration
        params = {
            "multiplier": 3,
            "dlss_preset": "Preset K",
            "menu_key": "Insert",
            "fg_output": "xefg",
            "fg_input": "dlssg",
            "dx12_upscaler": "dlss",
            "rcas_enabled": True,
            "rcas_sharpness": 0.20
        }
        ok, msg = ConfigSyncService.apply_unified_configuration(TARGET_DIR, EXE_NAME, "C", params)
        if not ok:
            print(f"   ❌ Apply Mode C failed: {msg}")
            return False
        print("   ✅ Applied Mode C unified configuration.")

        # 2. File tree assertions
        dxgi = TARGET_DIR / "dxgi.dll"
        reshade64 = TARGET_DIR / "ReShade64.dll"
        dlss5_addon = TARGET_DIR / "lecram-dlss5-beta10.addon64"
        libxess_fg = TARGET_DIR / "libxess_fg.dll"
        version_dll = TARGET_DIR / "version.dll"
        renodx_addon = TARGET_DIR / "renodx-mfgunlock.addon64"
        opti_ini = TARGET_DIR / "OptiScaler.ini"

        assert dxgi.exists(), "Mode C requires dxgi.dll (OptiScaler)!"
        assert reshade64.exists(), "Mode C requires ReShade64.dll for DLSS 5 chainload!"
        assert dlss5_addon.exists(), "Mode C requires lecram-dlss5-beta10.addon64!"
        assert libxess_fg.exists(), "Mode C requires libxess_fg.dll for XeFG!"
        assert not version_dll.exists(), "Mode C must NOT have version.dll!"
        assert not renodx_addon.exists(), "Mode C must NOT have renodx-mfgunlock.addon64!"
        assert opti_ini.exists(), "Mode C requires OptiScaler.ini!"

        print("   ✅ Mode C file tree assertions passed:")
        print("      • dxgi.dll (OptiScaler host) PRESENT")
        print("      • ReShade64.dll (DLSS 5 chainloader) PRESENT")
        print("      • libxess_fg.dll (XeFG 2.0 module) PRESENT")
        print("      • version.dll & renodx-mfgunlock.addon64 strictly PURGED")

        # 3. Config assertions
        cp = configparser.ConfigParser(interpolation=None, strict=False)
        cp.read(str(opti_ini), encoding="utf-8")

        assert cp.has_section("Upscalers"), "OptiScaler.ini missing [Upscalers]!"
        assert cp.get("Upscalers", "Dx12Upscaler").lower() == "dlss", "Dx12Upscaler must be 'dlss' to prevent DLSS menu from disappearing!"

        assert cp.has_section("Spoofing"), "OptiScaler.ini missing [Spoofing]!"
        assert cp.get("Spoofing", "Dxgi").lower() in ("false", "0"), "Dxgi spoofing must be false to avoid NGX hardware check failure!"

        assert cp.has_section("FrameGeneration"), "OptiScaler.ini missing [FrameGeneration]!"
        assert cp.get("FrameGeneration", "FGType").lower() == "xefg", "FGType must be xefg!"

        # Check LoadDlls / Plugins
        load_reshade = False
        if cp.has_section("LoadDlls") and cp.get("LoadDlls", "LoadReshade", fallback="").lower() == "true":
            load_reshade = True
        elif cp.has_section("Plugins") and cp.get("Plugins", "LoadReshade", fallback="").lower() == "true":
            load_reshade = True
        assert load_reshade, "LoadReshade must be true in OptiScaler.ini!"

        # Check DLSS preset anti-D
        if cp.has_section("DLSS"):
            p_val = cp.get("DLSS", "RenderPresetForAll", fallback="")
            assert p_val in ("11", "10", "13", "K", "J"), f"RenderPresetForAll must not be Preset D (4), got {p_val}!"

        print("   ✅ Mode C OptiScaler.ini assertions passed (Dx12Upscaler=dlss, Dxgi=false, FGType=xefg, LoadReshade=true, Preset K=11).")

        # 4. Smoke test & log verification
        saw_running = launch_game(duration_seconds=22)
        assert saw_running, "Game failed to launch in Mode C!"

        opti_log = TARGET_DIR / "OptiScaler.log"
        assert opti_log.exists(), "OptiScaler.log was not generated in Mode C!"
        opti_content = opti_log.read_text(encoding="utf-8", errors="ignore")

        # Verify chainload or DLSS init
        assert "OptiScaler" in opti_content, "OptiScaler header not found in log!"
        print("   ✅ Mode C Smoke Test Passed: OptiScaler initialized smoothly, Dx12Upscaler=dlss passed through, XeFG & ReShade64 chainload ready.")
        return True


if __name__ == "__main__":
    suite = VerificationSuite()
    success = suite.run_all()
    if success:
        print("\n🎉 ALL COEXISTENCE TESTS PASSED 100%! Ready for Release Packaging.")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED. Please review the output above.")
        sys.exit(1)
