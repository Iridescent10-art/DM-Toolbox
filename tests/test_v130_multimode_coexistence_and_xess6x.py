# -*- coding: utf-8 -*-
"""
Unit tests for Multi-mode Coexistence with DLSS 5, XeSS 2X~6X Multipliers,
and Simplified Chinese Overlay Defaults.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from apps.app2_mfg.core.ini_sync import IniConfigManager
from apps.app2_mfg.core.state_cleaner import is_dlss5_present, CleanGameDirectoryState
from apps.app2_mfg.core.optiscaler_config import get_preset_summary, load_optiscaler_preset
from apps.app6_dlss5.engine.injector import DLSS5Injector, check_dlss5_status


class TestMultiModeCoexistenceAndXeSS6X(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_mfg_dlss5_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_xess_interpolation_count_unlocks_up_to_6x(self):
        """Test that resolve_interpolation_count supports up to 5 (6X) without clamping to 2X or 4X."""
        # 1=2X, 2=3X, 3=4X, 4=5X, 5=6X
        for count in [1, 2, 3, 4, 5]:
            eff, max_supp, clamped = IniConfigManager.resolve_interpolation_count(self.test_dir, "xefg", count)
            self.assertEqual(eff, count)
            self.assertEqual(max_supp, 5)
            self.assertFalse(clamped)

        # Value higher than 5 clamps to 5
        eff, max_supp, clamped = IniConfigManager.resolve_interpolation_count(self.test_dir, "xefg", 9)
        self.assertEqual(eff, 5)

    def test_mode_c_sync_writes_6x_and_chinese_menu(self):
        """Test that sync_mode_c_forward writes 6X multipliers and Chinese font config into OptiScaler.ini."""
        preset = {
            "fg_output": "xefg",
            "fg_input": "dlssg",
            "interpolation_count": 5,  # 6X
            "dx12_upscaler": "auto",
            "rcas_enabled": False,
            "rcas_sharpness": 0.0,
            "dlss_preset": "Default",
            "menu_key": "Insert",
            "menu_scale": 2.0
        }
        ok = IniConfigManager.sync_mode_c_forward(self.test_dir, preset)
        self.assertTrue(ok)

        opti_ini = Path(self.test_dir) / "OptiScaler.ini"
        self.assertTrue(opti_ini.exists())

        sections = IniConfigManager.read_ini_sections(opti_ini)

        # Check XeFG section has InterpolationCount=5 and OverrideInterpolationCount=5
        self.assertEqual(sections.get("XeFG", {}).get("InterpolationCount"), "5")
        self.assertEqual(sections.get("XeFG", {}).get("OverrideInterpolationCount"), "5")

        # Check DLSSG section has InterpolationCount=5 and OverrideInterpolationCount=5
        self.assertEqual(sections.get("DLSSG", {}).get("InterpolationCount"), "5")
        self.assertEqual(sections.get("DLSSG", {}).get("OverrideInterpolationCount"), "5")

        # Check Menu section has Chinese font config
        menu_sec = sections.get("Menu", {})
        self.assertEqual(menu_sec.get("UseHQFont"), "true")
        self.assertIn("msyh.ttc", menu_sec.get("TTFFontPath", ""))

    def test_mode_b_sync_writes_chinese_overlay(self):
        """Test that sync_mode_b_forward (Mode B) writes Simplified Chinese overlay into ReShade.ini."""
        preset_b = {
            "force_multiplier": 6,
            "dlss_preset": "Default",
            "blackwell_kernels": 1
        }
        ok = IniConfigManager.sync_mode_b_forward(self.test_dir, preset_b)
        self.assertTrue(ok)

        reshade_ini = Path(self.test_dir) / "ReShade.ini"
        self.assertTrue(reshade_ini.exists())

        sections = IniConfigManager.read_ini_sections(reshade_ini)
        overlay_sec = sections.get("OVERLAY", {})
        self.assertEqual(overlay_sec.get("Language"), "zh-CN")
        self.assertIn("msyh.ttc", overlay_sec.get("Font", ""))
        self.assertEqual(overlay_sec.get("FontSize"), "18")

    def test_is_dlss5_present_detection(self):
        """Test that is_dlss5_present detects modern renodx-dlss5.addon64."""
        self.assertFalse(is_dlss5_present(self.test_dir))

        addon_path = Path(self.test_dir) / "renodx-dlss5.addon64"
        addon_path.write_bytes(b"dummy_addon")
        self.assertTrue(is_dlss5_present(self.test_dir))

    def test_dlss5_coexistence_with_mode_c_chainloading(self):
        """Test that when Mode C and DLSS 5 coexist, ReShade64.dll is used and LoadReshade=true is configured."""
        # Simulate Mode C OptiScaler
        (Path(self.test_dir) / "OptiScaler.ini").write_text("[Plugins]\nLoadReshade=auto\n", encoding="utf-8")
        (Path(self.test_dir) / "OptiScaler.dll").write_bytes(b"dummy_optiscaler")

        status = check_dlss5_status(self.test_dir)
        self.assertTrue(status["fg_info"]["is_optiscaler_fg"])

        # Inject DLSS 5 into Mode C game
        ok, msg = DLSS5Injector.inject(self.test_dir)
        self.assertTrue(ok)

        # Verify ReShade64.dll was deployed (not overwriting dxgi.dll)
        self.assertTrue((Path(self.test_dir) / "ReShade64.dll").exists())
        self.assertTrue((Path(self.test_dir) / "renodx-dlss5.addon64").exists())

        # Verify OptiScaler.ini has LoadReshade=true
        opti_ini = Path(self.test_dir) / "OptiScaler.ini"
        sec = IniConfigManager.read_ini_sections(opti_ini)
        self.assertEqual(sec.get("Plugins", {}).get("LoadReshade"), "true")


if __name__ == "__main__":
    unittest.main()
