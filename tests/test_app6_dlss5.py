# -*- coding: utf-8 -*-
"""
Unit tests for App 6: DLSS 5 Neural Reconstruction Injector & Frame Generation Avoidance.
"""

import os
import sys
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from apps.app6_dlss5.core.injector import (
    DLSS5Injector, check_dlss5_status, detect_frame_generation,
    find_reshade_framework_dll, get_dlss5_addon_path, find_rhi_setup_exe
)
from launcher.main import APPS_METADATA, APP_EXACT_TITLES


class TestDLSS5Injector(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_dlss5_")
        self.game_dir = Path(self.test_dir) / "Cyberpunk2077" / "bin" / "x64"
        self.game_dir.mkdir(parents=True, exist_ok=True)
        # Create mock executable
        (self.game_dir / "Cyberpunk2077.exe").write_bytes(b"MZ" + b"\x00" * 1024)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_launcher_registration(self):
        """Verify app6_dlss5 is correctly registered in launcher metadata and titles."""
        app_ids = [m["id"] for m in APPS_METADATA]
        self.assertIn("app6_dlss5", app_ids)
        self.assertIn("app6_dlss5", APP_EXACT_TITLES)
        self.assertEqual(APP_EXACT_TITLES["app6_dlss5"], "DM工具箱 - DLSS 5 神经重构与画质注入器")

        # Verify asset files
        addon_src = get_dlss5_addon_path()
        self.assertIsNotNone(addon_src)
        self.assertTrue(os.path.exists(addon_src))
        self.assertGreater(os.path.getsize(addon_src), 5 * 1024 * 1024)

    def test_clean_status(self):
        """Verify status detection on an unpatched game."""
        status = DLSS5Injector.get_status(str(self.game_dir))
        self.assertFalse(status["is_injected"])
        self.assertFalse(status["has_addon"])
        self.assertFalse(status["has_dxgi"])
        self.assertFalse(status["fg_info"]["has_fg"])
        self.assertFalse(status["avoidance_active"])

    def test_inject_clean_game(self):
        """Verify injection into a game without Frame Generation (standalone mode)."""
        ok, msg = DLSS5Injector.inject(str(self.game_dir))
        self.assertTrue(ok, msg)
        self.assertIn("✅", msg)

        # Check injected files
        addon_dest = self.game_dir / "lecram-dlss5-beta10.addon64"
        dxgi_dest = self.game_dir / "dxgi.dll"
        ini_dest = self.game_dir / "ReShade.ini"
        manifest_dest = self.game_dir / ".dlss5_patch_manifest.json"

        self.assertTrue(addon_dest.exists())
        self.assertTrue(dxgi_dest.exists())
        self.assertTrue(ini_dest.exists())
        self.assertTrue(manifest_dest.exists())

        # Check manifest
        with open(manifest_dest, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        self.assertTrue(manifest["reshade_injected_by_dlss5"])
        self.assertFalse(manifest["frame_generation_coexisting"])

        # Check status
        status = DLSS5Injector.get_status(str(self.game_dir))
        self.assertTrue(status["is_injected"])
        self.assertTrue(status["has_addon"])
        self.assertTrue(status["has_dxgi"])

    def test_collision_avoidance_with_frame_generation(self):
        """
        CRITICAL TEST: Verify that if Frame Generation (App 2) is already injected,
        DLSS 5 does NOT overwrite dxgi.dll, avoids host collision, and coexists cleanly.
        """
        # 1. Simulate existing App 2 (RenoDX Frame Generation) injection
        mock_mfg_dxgi = b"MOCK_RESHADE_ADDON_HOST_FOR_MFG" + b"\x00" * 1024
        (self.game_dir / "dxgi.dll").write_bytes(mock_mfg_dxgi)
        (self.game_dir / "renodx-mfgunlock.addon64").write_bytes(b"MOCK_RENODX_ADDON")
        (self.game_dir / ".mfg_patch_manifest.json").write_text(json.dumps({
            "backend": "reshade_addon",
            "injected_files": ["renodx-mfgunlock.addon64", "dxgi.dll", "ReShade.ini"]
        }), encoding="utf-8")

        initial_ini = (
            "[GENERAL]\n"
            "EffectSearchPaths=.\\\n"
            "[ADDON]\n"
            "LoadFromDllMain=renodx-mfgunlock.addon64\n"
        )
        (self.game_dir / "ReShade.ini").write_text(initial_ini, encoding="utf-8")

        # 2. Status should detect Frame Generation and activate avoidance readiness
        status_before = DLSS5Injector.get_status(str(self.game_dir))
        self.assertTrue(status_before["fg_info"]["has_fg"])
        self.assertTrue(status_before["avoidance_active"])
        self.assertFalse(status_before["is_injected"])

        # 3. Inject DLSS 5
        ok, msg = DLSS5Injector.inject(str(self.game_dir))
        self.assertTrue(ok, msg)
        self.assertIn("避让生效", msg)

        # 4. CRITICAL VERIFICATION: dxgi.dll MUST NOT BE OVERWRITTEN!
        dxgi_bytes = (self.game_dir / "dxgi.dll").read_bytes()
        self.assertEqual(dxgi_bytes, mock_mfg_dxgi, "dxgi.dll was modified despite Frame Generation being present!")

        # 5. DLSS 5 addon must be copied
        addon_dest = self.game_dir / "lecram-dlss5-beta10.addon64"
        self.assertTrue(addon_dest.exists())

        # 6. ReShade.ini must contain BOTH addons
        ini_content = (self.game_dir / "ReShade.ini").read_text(encoding="utf-8")
        self.assertIn("renodx-mfgunlock.addon64", ini_content)
        self.assertIn("lecram-dlss5-beta10.addon64", ini_content)

        # 7. Check manifest flags
        manifest_dest = self.game_dir / ".dlss5_patch_manifest.json"
        with open(manifest_dest, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        self.assertFalse(manifest["reshade_injected_by_dlss5"])
        self.assertTrue(manifest["frame_generation_coexisting"])

        # 8. Test Restore: DLSS 5 must be removed WITHOUT destroying Frame Generation!
        ok_restore, msg_restore = DLSS5Injector.restore(str(self.game_dir))
        self.assertTrue(ok_restore, msg_restore)

        # DLSS 5 addon must be gone
        self.assertFalse(addon_dest.exists())
        self.assertFalse(manifest_dest.exists())

        # Frame Generation files MUST REMAIN INTACT!
        self.assertTrue((self.game_dir / "renodx-mfgunlock.addon64").exists())
        self.assertTrue((self.game_dir / "dxgi.dll").exists())
        self.assertEqual((self.game_dir / "dxgi.dll").read_bytes(), mock_mfg_dxgi)
        self.assertTrue((self.game_dir / ".mfg_patch_manifest.json").exists())

        # ReShade.ini should still have renodx-mfgunlock
        ini_after = (self.game_dir / "ReShade.ini").read_text(encoding="utf-8")
        self.assertIn("renodx-mfgunlock.addon64", ini_after)
        self.assertNotIn("lecram-dlss5-beta10.addon64", ini_after)

    def test_restore_clean_game(self):
        """Verify restoring a standalone DLSS 5 injection cleans up all its deployed files."""
        DLSS5Injector.inject(str(self.game_dir))
        self.assertTrue((self.game_dir / "lecram-dlss5-beta10.addon64").exists())
        self.assertTrue((self.game_dir / "dxgi.dll").exists())

        ok, msg = DLSS5Injector.restore(str(self.game_dir))
        self.assertTrue(ok, msg)
        self.assertFalse((self.game_dir / "lecram-dlss5-beta10.addon64").exists())
        self.assertFalse((self.game_dir / "dxgi.dll").exists())
        self.assertFalse((self.game_dir / ".dlss5_patch_manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
