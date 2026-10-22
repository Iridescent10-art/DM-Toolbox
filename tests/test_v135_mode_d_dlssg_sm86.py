# -*- coding: utf-8 -*-
"""
Test Suite v135: Mode C (DLSSG-SM86 原生插帧) & Mode D (OptiScaler 跨卡转译) Swapped Order Verification
Comprehensive tests covering:
1. BackendType & Model Registration:
   - BackendType.DLSSG_SM86 enum validation.
2. Preset Management:
   - Default preset integrity, loading, saving, and summary formatting.
3. INI Sync Engine (IniConfigManager):
   - sync_mode_d_forward writing dlssg_sm86.ini.
   - read_mode_d_reverse reading back parameters.
4. State Cleaner & Conflict Isolation:
   - Detecting Mode C (DLSSG-SM86) presence.
   - File isolation between Mode C and Modes A/B/D.
5. Patch Engine (PatchEngine):
   - Smart-Auto preference on RTX 20/30 series -> Mode C (DLSSG_SM86).
   - Smart-Auto preference on AMD/Intel/GTX -> Mode D (OPTISCALER_FSR).
   - Full transactional deployment of Mode C files.
   - Mode detection: detect_injected_mode() -> 'dlssg_sm86'.
   - Complete restoration / rollback of Mode C.
6. DLSS 5 & Mode C / Mode D Coexistence:
   - ConfigSyncService detecting Mode C (DLSSG-SM86) and Mode D (OptiScaler).
   - ConfigSyncService bidirectional sync for Mode C and Mode D.
   - Slot isolation: Mode C (version.dll) + DLSS 5 (dxgi.dll).
"""

import os
import sys
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Setup paths
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root_dir)
sys.path.insert(0, os.path.join(root_dir, "apps", "app2_mfg"))

from apps.app2_mfg.core.models import BackendType, GameInfo, QualificationStatus, PatchManifest
from apps.app2_mfg.core.optiscaler_config import (
    DEFAULT_DLSSG_SM86_PRESET,
    load_dlssg_sm86_preset,
    save_dlssg_sm86_preset,
    get_dlssg_sm86_preset_summary,
    get_preset_config_file,
)
from apps.app2_mfg.core.ini_sync import IniConfigManager
from apps.app2_mfg.core.state_cleaner import CleanGameDirectoryState, is_dlssg_sm86_present
from apps.app2_mfg.core.updater import ComponentUpdater
from apps.app2_mfg.core.patcher import PatchEngine


class TestModeCDLSSGSM86AndModeDOptiScaler(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="dm_test_moded_")
        self.game_exe = os.path.join(self.test_dir, "Cyberpunk2077.exe")
        with open(self.game_exe, "wb") as f:
            f.write(b"MOCK_GAME_EXE_CONTENT")

        self.game_info = GameInfo(
            name="Cyberpunk 2077",
            source="Custom",
            install_dir=self.test_dir,
            target_dir=self.test_dir,
            exe_path=self.game_exe,
            exe_name="Cyberpunk2077.exe",
            qualification=QualificationStatus.QUALIFIED,
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # ---------------- 1. Backend Type & Model Tests ----------------
    def test_01_backend_type_enum(self):
        self.assertEqual(BackendType.DLSSG_SM86.value, "dlssg_sm86")
        self.assertIn("dlssg_sm86", [b.value for b in BackendType])

    # ---------------- 2. Preset Management Tests ----------------
    def test_02_preset_defaults_and_io(self):
        # Verify defaults
        self.assertEqual(DEFAULT_DLSSG_SM86_PRESET["max_generated_frames"], 2)
        self.assertEqual(DEFAULT_DLSSG_SM86_PRESET["optimized"], 2)
        self.assertEqual(DEFAULT_DLSSG_SM86_PRESET["dlssg_preset"], "Auto")
        self.assertEqual(DEFAULT_DLSSG_SM86_PRESET["super_resolution_mode"], "On")
        self.assertEqual(DEFAULT_DLSSG_SM86_PRESET["proxy_dll"], "version.dll")

        # Test summary
        summary = get_dlssg_sm86_preset_summary(DEFAULT_DLSSG_SM86_PRESET)
        self.assertIn("DLSSG-SM86", summary)
        self.assertIn("原生插帧", summary)
        self.assertIn("轻量加速", summary)
        self.assertIn("Auto", summary)

        # Test save and load with custom preset
        custom_preset = dict(DEFAULT_DLSSG_SM86_PRESET)
        custom_preset["max_generated_frames"] = 5
        custom_preset["optimized"] = 3
        custom_preset["dlssg_preset"] = "C"
        custom_preset["super_resolution_mode"] = "On"

        # Mock config file path
        mock_cfg_file = Path(self.test_dir) / "dlssg_sm86_preset.json"
        with patch("apps.app2_mfg.core.optiscaler_config.get_preset_config_file", return_value=mock_cfg_file):
            save_dlssg_sm86_preset(custom_preset)
            loaded = load_dlssg_sm86_preset()
            self.assertEqual(loaded["max_generated_frames"], 5)
            self.assertEqual(loaded["optimized"], 3)
            self.assertEqual(loaded["dlssg_preset"], "C")
            self.assertEqual(loaded["super_resolution_mode"], "On")

    # ---------------- 3. INI Sync Engine Tests ----------------
    def test_03_ini_sync_forward_and_reverse(self):
        ini_path = os.path.join(self.test_dir, "dlssg_sm86.ini")
        params = {
            "max_generated_frames": 3,
            "engine": "DLSS",
            "proxy_dll": "version.dll",
            "optimized": 1,
            "dlssg_preset": "C",
            "super_resolution_mode": "On",
        }

        # Test forward sync
        res = IniConfigManager.sync_mode_d_forward(self.test_dir, params)
        self.assertTrue(res)
        self.assertTrue(os.path.exists(ini_path))

        with open(ini_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("[FrameGeneration]", content)
        self.assertIn("MaxGeneratedFrames=3", content)
        self.assertIn("Engine=DLSS", content)
        self.assertIn("[DLSSG]", content)
        self.assertIn("Optimized=1", content)
        self.assertIn("Preset=C", content)
        self.assertIn("[SuperResolution]", content)
        self.assertIn("Mode=On", content)

        # Test reverse read
        read_back = IniConfigManager.read_mode_d_reverse(self.test_dir)
        self.assertEqual(read_back["max_generated_frames"], 3)
        self.assertEqual(read_back["engine"], "DLSS")
        self.assertEqual(read_back["optimized"], 1)
        self.assertEqual(read_back["dlssg_preset"], "C")
        self.assertEqual(read_back["super_resolution_mode"], "On")

    # ---------------- 4. State Cleaner & Isolation Tests ----------------
    def test_04_state_cleaner_and_isolation(self):
        # Create mock Mode C (DLSSG-SM86) files
        dlssg_dir = os.path.join(self.test_dir, "dlssg_sm86")
        os.makedirs(dlssg_dir, exist_ok=True)
        with open(os.path.join(dlssg_dir, "test.dll"), "wb") as f:
            f.write(b"DLL")
        with open(os.path.join(self.test_dir, "dlssg_sm86.ini"), "w") as f:
            f.write("[DLSSG]\n")
        with open(os.path.join(self.test_dir, "version.dll"), "wb") as f:
            f.write(b"PROXY")

        self.assertTrue(is_dlssg_sm86_present(self.test_dir))

        # Switch to Mode B (CleanGameDirectoryState with target_mode="B")
        success, actions = CleanGameDirectoryState(self.test_dir, target_mode="B")
        self.assertTrue(success)

        self.assertFalse(os.path.exists(dlssg_dir))
        self.assertFalse(os.path.exists(os.path.join(self.test_dir, "dlssg_sm86.ini")))
        # Game exe remains untouched
        self.assertTrue(os.path.exists(self.game_exe))

    # ---------------- 5. Patch Engine & Smart Auto Tests ----------------
    def test_05_smart_auto_prefers_mode_c_on_rtx_20_30(self):
        updater = MagicMock(spec=ComponentUpdater)
        engine = PatchEngine(updater)

        # Test RTX 3080 auto-selection -> Mode C (DLSSG_SM86)
        with patch("apps.app2_mfg.core.patcher.get_system_gpu_name", return_value="NVIDIA GeForce RTX 3080"):
            with patch("apps.app2_mfg.core.patcher.is_rtx_40_or_newer", return_value=False):
                with patch.object(engine, "_apply_dlssg_sm86_patch", return_value=(True, "OK")):
                    ok, msg = engine.patch_game(self.game_info, requested_backend=BackendType.SMART_AUTO)
                    self.assertTrue(ok)
                    self.assertEqual(self.game_info.patched_backend, BackendType.DLSSG_SM86.value)

        # Test RTX 2060 Super auto-selection -> Mode C (DLSSG_SM86)
        with patch("apps.app2_mfg.core.patcher.get_system_gpu_name", return_value="NVIDIA GeForce RTX 2060 Super"):
            with patch("apps.app2_mfg.core.patcher.is_rtx_40_or_newer", return_value=False):
                with patch.object(engine, "_apply_dlssg_sm86_patch", return_value=(True, "OK")):
                    ok, msg = engine.patch_game(self.game_info, requested_backend=BackendType.SMART_AUTO)
                    self.assertTrue(ok)
                    self.assertEqual(self.game_info.patched_backend, BackendType.DLSSG_SM86.value)

        # Test AMD Radeon RX 7800 XT auto-selection -> Mode D (OptiScaler)
        with patch("apps.app2_mfg.core.patcher.get_system_gpu_name", return_value="AMD Radeon RX 7800 XT"):
            with patch("apps.app2_mfg.core.patcher.is_rtx_40_or_newer", return_value=False):
                with patch.object(engine, "_apply_optiscaler_patch", return_value=(True, "OK")):
                    ok, msg = engine.patch_game(self.game_info, requested_backend=BackendType.SMART_AUTO)
                    self.assertTrue(ok)
                    self.assertEqual(self.game_info.patched_backend, BackendType.OPTISCALER_FSR.value)

    def test_06_patch_and_rollback_mode_c(self):
        updater = MagicMock(spec=ComponentUpdater)

        # Mock embedded component dir
        mock_embedded = os.path.join(self.test_dir, "mock_embedded")
        mock_tree = os.path.join(mock_embedded, "dlssg_sm86")
        os.makedirs(os.path.join(mock_tree, "backend"), exist_ok=True)
        with open(os.path.join(mock_embedded, "version.dll"), "wb") as f:
            f.write(b"MOCK_VERSION_DLL")
        with open(os.path.join(mock_tree, "backend", "sm86_backend.dll"), "wb") as f:
            f.write(b"MOCK_BACKEND")
        with open(os.path.join(mock_embedded, "dlssg_sm86.ini"), "w", encoding="utf-8") as f:
            f.write("[General]\nEnabled=1\n[DLSSG]\nOptimized=2\n")

        updater.get_latest_cached_dir.return_value = mock_embedded
        updater.get_latest_cached_file.return_value = mock_embedded

        engine = PatchEngine(updater)
        ok, msg = engine.patch_game(self.game_info, requested_backend=BackendType.DLSSG_SM86)
        self.assertTrue(ok)

        # Check files landed
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "version.dll")))
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "dlssg_sm86.ini")))
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "dlssg_sm86", "backend", "sm86_backend.dll")))

        # Check detection
        injected_mode = engine.detect_injected_mode(self.test_dir)
        self.assertEqual(injected_mode, "dlssg_sm86")

        # Rollback via rollback_engine
        restored, r_msg = engine.rollback_engine.rollback(self.test_dir, self.game_info.exe_name)
        self.assertTrue(restored)
        self.assertFalse(os.path.exists(os.path.join(self.test_dir, "version.dll")))
        self.assertFalse(os.path.exists(os.path.join(self.test_dir, "dlssg_sm86.ini")))
        self.assertFalse(os.path.exists(os.path.join(self.test_dir, "dlssg_sm86")))
        self.assertTrue(os.path.exists(self.game_exe))

    # ---------------- 6. Coexistence with DLSS 5 Tests ----------------
