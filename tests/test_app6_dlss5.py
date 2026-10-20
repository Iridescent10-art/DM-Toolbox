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

        # Check status
        status = DLSS5Injector.get_status(str(self.game_dir))
        self.assertTrue(status["is_injected"])
        self.assertTrue(status["has_addon"])
        self.assertTrue(status["has_dxgi"])

    def test_rhi_collision_avoidance(self):
        """
        CRITICAL TEST 1: RHI RenoDX Frame Generation Avoidance.
        "RHI的插帧才不需要重新装" -> ReShade base dxgi.dll is ALREADY installed by RHI/RenoDX.
        DLSS 5 must NOT overwrite dxgi.dll, avoids base reinstallation, and directly chains addon.
        """
        # 1. Simulate existing App 2 (RHI RenoDX Frame Generation) injection
        mock_mfg_dxgi = b"MOCK_RESHADE_ADDON_HOST_FOR_MFG" + b"\x00" * 1024
        (self.game_dir / "dxgi.dll").write_bytes(mock_mfg_dxgi)
        (self.game_dir / "renodx-mfgunlock.addon64").write_bytes(b"MOCK_RENODX_ADDON")
        (self.game_dir / ".mfg_patch_manifest.json").write_text(json.dumps({
            "active_backend": "reshade_addon",
            "injected_files": ["renodx-mfgunlock.addon64", "dxgi.dll", "ReShade.ini"]
        }), encoding="utf-8")

        initial_ini = (
            "[GENERAL]\n"
            "EffectSearchPaths=.\\\n"
            "[ADDON]\n"
            "LoadFromDllMain=renodx-mfgunlock.addon64\n"
        )
        (self.game_dir / "ReShade.ini").write_text(initial_ini, encoding="utf-8")

        # 2. Status should detect RHI Frame Generation and activate avoidance
        status_before = DLSS5Injector.get_status(str(self.game_dir))
        self.assertTrue(status_before["fg_info"]["has_fg"])
        self.assertTrue(status_before["fg_info"]["is_rhi_fg"])
        self.assertTrue(status_before["avoidance_active"])
        self.assertFalse(status_before["is_injected"])

        # 3. Base injection should be avoided
        ok_base, msg_base = DLSS5Injector.inject_reshade_base(str(self.game_dir))
        self.assertTrue(ok_base)
        self.assertIn("免重复安装", msg_base)

        # 4. Inject DLSS 5
        ok, msg = DLSS5Injector.inject(str(self.game_dir))
        self.assertTrue(ok, msg)
        self.assertIn("避让生效", msg)

        # 5. CRITICAL VERIFICATION: dxgi.dll MUST NOT BE OVERWRITTEN!
        dxgi_bytes = (self.game_dir / "dxgi.dll").read_bytes()
        self.assertEqual(dxgi_bytes, mock_mfg_dxgi, "dxgi.dll was modified despite RHI being present!")

        # 6. DLSS 5 addon must be copied
        addon_dest = self.game_dir / "lecram-dlss5-beta10.addon64"
        self.assertTrue(addon_dest.exists())

        # 7. ReShade.ini must contain BOTH addons
        ini_content = (self.game_dir / "ReShade.ini").read_text(encoding="utf-8")
        self.assertIn("renodx-mfgunlock.addon64", ini_content)
        self.assertIn("lecram-dlss5-beta10.addon64", ini_content)

        # 8. Check manifest flags
        manifest_dest = self.game_dir / ".dlss5_patch_manifest.json"
        with open(manifest_dest, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        self.assertFalse(manifest["reshade_injected_by_dlss5"])
        self.assertTrue(manifest["rhi_avoidance_active"])

        # 9. Test Restore: DLSS 5 must be removed WITHOUT destroying RHI Frame Generation!
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

    def test_optiscaler_coexistence(self):
        """
        CRITICAL TEST 2: OptiScaler Frame Generation Coexistence.
        "opt插帧应该和RHIdlss5共存啊" -> OptiScaler is preserved as dxgi.dll.
        ReShade64.dll is deployed alongside OptiScaler and LoadReshade=true is configured in OptiScaler.ini.
        Both OptiScaler FG and DLSS 5 co-exist seamlessly!
        """
        # 1. Simulate existing App 2 (OptiScaler Frame Generation) injection
        mock_opti_dxgi = b"MOCK_OPTISCALER_DXGI_DLL" + b"\x00" * 1024
        (self.game_dir / "dxgi.dll").write_bytes(mock_opti_dxgi)
        (self.game_dir / "OptiScaler.dll").write_bytes(b"MOCK_OPTISCALER_CORE")
        (self.game_dir / "OptiScaler.ini").write_text(
            "[Plugins]\nLoadReshade=auto\nLoadSpecialK=auto\n",
            encoding="utf-8"
        )
        (self.game_dir / ".mfg_patch_manifest.json").write_text(json.dumps({
            "active_backend": "optiscaler",
            "injected_files": ["dxgi.dll", "OptiScaler.dll", "OptiScaler.ini"]
        }), encoding="utf-8")

        # 2. Status check
        status_before = DLSS5Injector.get_status(str(self.game_dir))
        self.assertTrue(status_before["fg_info"]["has_fg"])
        self.assertTrue(status_before["fg_info"]["is_optiscaler_fg"])
        self.assertFalse(status_before["avoidance_active"])  # OptiScaler does NOT avoid ReShade; it coexists!
        self.assertTrue(status_before["optiscaler_coexisting"])

        # 3. Test base deployment for OptiScaler
        ok_base, msg_base = DLSS5Injector.inject_reshade_base(str(self.game_dir))
        self.assertTrue(ok_base, msg_base)
        self.assertIn("链式共存底座部署成功", msg_base)
        self.assertTrue((self.game_dir / "ReShade64.dll").exists())

        # Check OptiScaler.ini LoadReshade=true
        opti_ini = (self.game_dir / "OptiScaler.ini").read_text(encoding="utf-8")
        self.assertIn("LoadReshade=true", opti_ini)

        # 4. Inject DLSS 5
        ok, msg = DLSS5Injector.inject(str(self.game_dir))
        self.assertTrue(ok, msg)
        self.assertIn("OptiScaler 链式共存模式生效", msg)

        # 5. Check files
        self.assertTrue((self.game_dir / "lecram-dlss5-beta10.addon64").exists())
        self.assertTrue((self.game_dir / "ReShade.ini").exists())
        # OptiScaler dxgi.dll MUST NOT BE OVERWRITTEN!
        self.assertEqual((self.game_dir / "dxgi.dll").read_bytes(), mock_opti_dxgi)

        # 6. Check restore
        ok_restore, msg_restore = DLSS5Injector.restore(str(self.game_dir))
        self.assertTrue(ok_restore, msg_restore)
        self.assertFalse((self.game_dir / "lecram-dlss5-beta10.addon64").exists())
        # OptiScaler files remain intact!
        self.assertTrue((self.game_dir / "OptiScaler.dll").exists())
        self.assertTrue((self.game_dir / "dxgi.dll").exists())
        self.assertEqual((self.game_dir / "dxgi.dll").read_bytes(), mock_opti_dxgi)

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
