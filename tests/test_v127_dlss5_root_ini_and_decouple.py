# -*- coding: utf-8 -*-
"""
Test v127: Verification of DLSS 5 In-Game Settings Persistence,
ReShade Root Section Writing, Dual-Prefix RenoDX Addon Contract,
and Standalone Injection Decoupling (Preserving XeFG InterpolationCount).
"""

import unittest
import tempfile
import shutil
from pathlib import Path

from apps.app6_dlss5.engine.dlss5_config import (
    load_dlss5_preset,
    write_game_dlss5_config,
    read_game_dlss5_config,
    DEFAULT_DLSS5_CONFIG
)
from apps.app2_mfg.core.ini_sync import IniConfigManager
from apps.app6_dlss5.engine.injector import DLSS5Injector, _configure_reshade_ini_for_dlss5


class TestDLSS5RootIniAndDecouple(unittest.TestCase):

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="test_dlss5_root_"))
        self.reshade_ini = self.test_dir / "ReShade.ini"

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_default_auto_mask_is_enabled(self):
        """Verify default auto_mask is 1 (enabled)."""
        cfg = load_dlss5_preset()
        self.assertEqual(cfg.get("auto_mask"), 1)
        self.assertEqual(DEFAULT_DLSS5_CONFIG.get("auto_mask"), 1)

    def test_write_game_dlss5_config_root_and_sections(self):
        """Verify write_game_dlss5_config writes keys to root section and [RenoDX] / [DLSS]."""
        cfg = load_dlss5_preset()
        cfg["auto_mask"] = 1
        cfg["intensity"] = 1.0
        cfg["style"] = 2
        cfg["processing_scale"] = 0.67

        ok = write_game_dlss5_config(self.test_dir, cfg)
        self.assertTrue(ok)
        self.assertTrue(self.reshade_ini.exists())

        raw_text = self.reshade_ini.read_text(encoding="utf-8")
        
        # 1. Root keys must appear before any section header
        first_section_pos = raw_text.find("[")
        self.assertGreater(first_section_pos, 0, "Expected at least one section header")
        root_part = raw_text[:first_section_pos]
        self.assertIn("DirectNeuralRenderingStatus=1", root_part)
        self.assertIn("DirectNeuralRenderingAutoMask=1", root_part)
        self.assertIn("DirectNeuralRenderingStyle=2", root_part)
        self.assertIn("DLSSNR.Enabled=1", root_part)
        self.assertIn("DLSSNR.UseAutoMask=1", root_part)

        # 2. Section keys must also exist under [RenoDX] and [DLSS]
        sections = IniConfigManager.read_ini_sections(self.reshade_ini)
        self.assertIn("RenoDX", sections)
        self.assertEqual(sections["RenoDX"]["DirectNeuralRenderingStatus"], "1")
        self.assertEqual(sections["RenoDX"]["DirectNeuralRenderingAutoMask"], "1")
        self.assertEqual(sections["RenoDX"]["DLSSNR.Enabled"], "1")

        # 3. Read back
        read_back = read_game_dlss5_config(self.test_dir)
        self.assertEqual(read_back.get("auto_mask"), 1)
        self.assertEqual(read_back.get("style"), 2)

    def test_restore_removes_root_and_section_keys(self):
        """Verify _configure_reshade_ini_for_dlss5 with remove=True purges root and section keys."""
        cfg = load_dlss5_preset()
        write_game_dlss5_config(self.test_dir, cfg)

        ok = _configure_reshade_ini_for_dlss5(self.reshade_ini, remove=True)
        self.assertTrue(ok)

        raw_text = self.reshade_ini.read_text(encoding="utf-8")
        self.assertNotIn("DirectNeuralRenderingStatus", raw_text)
        self.assertNotIn("DLSSNR.Enabled", raw_text)
        self.assertNotIn("[RenoDX]", raw_text)
        self.assertNotIn("[DLSS5]", raw_text)

    def test_standalone_optiscaler_interpolation_count_preserved(self):
        """Verify injecting DLSS 5 standalone into an OptiScaler game preserves XeFG InterpolationCount=2 (3X)."""
        opti_ini = self.test_dir / "OptiScaler.ini"
        opti_ini.write_text(
            "[Plugins]\nLoadReshade=auto\n\n[XeFG]\nInterpolationCount=2\n\n[DLSS]\nRenderPresetForAll=11\n",
            encoding="utf-8"
        )
        (self.test_dir / "OptiScaler.dll").write_text("dummy", encoding="utf-8")

        from apps.app6_dlss5.engine.injector import set_optiscaler_load_reshade
        set_optiscaler_load_reshade(str(self.test_dir), enable=True)

        sections = IniConfigManager.read_ini_sections(opti_ini)
        self.assertEqual(sections.get("Plugins", {}).get("LoadReshade"), "true")
        self.assertEqual(sections.get("XeFG", {}).get("InterpolationCount"), "2", "InterpolationCount should not be wiped to 1!")


if __name__ == "__main__":
    unittest.main()
