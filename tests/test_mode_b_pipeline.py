import os
import shutil
import tempfile
import unittest
from pathlib import Path
import sys

# Ensure apps/app2_mfg is on path
current_dir = Path(__file__).resolve().parent
app_dir = current_dir.parent / "apps" / "app2_mfg"
sys.path.insert(0, str(app_dir))

from core.models import GameInfo, BackendType, QualificationStatus, PatchManifest
from core.updater import ComponentUpdater
from core.patcher import PatchEngine
from core.rollback import RollbackEngine
from core.ini_sync import IniConfigManager

class TestModeBPipeline(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.game_dir = os.path.join(self.temp_dir, "GameX", "bin", "x64")
        os.makedirs(self.game_dir, exist_ok=True)
        self.updater = ComponentUpdater()
        self.patcher = PatchEngine(self.updater)
        self.game = GameInfo(
            name="TestGame",
            source="Steam",
            install_dir=os.path.join(self.temp_dir, "GameX"),
            target_dir=self.game_dir,
            exe_path=os.path.join(self.game_dir, "GameX.exe"),
            exe_name="GameX.exe",
            qualification=QualificationStatus.QUALIFIED
        )
        # Create dummy exe
        with open(self.game.exe_path, "wb") as f:
            f.write(b"MZ\x90\x00dummy")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_reshade_framework_resolution(self):
        reshade_dll = self.updater.get_reshade_framework_dll()
        self.assertIsNotNone(reshade_dll)
        self.assertTrue(os.path.exists(reshade_dll))
        self.assertTrue(self.patcher._is_reshade_dll(reshade_dll))
        self.assertTrue(self.patcher._is_reshade_addon_dll(reshade_dll))

    def test_apply_mode_b_bundles_reshade(self):
        # Apply Mode B
        ok, msg = self.patcher.patch_game(self.game, BackendType.RESHADE_ADDON)
        self.assertTrue(ok, msg)

        # 1. dxgi.dll must exist and be ReShade with Add-on Support
        dxgi_path = os.path.join(self.game_dir, "dxgi.dll")
        self.assertTrue(os.path.exists(dxgi_path))
        self.assertTrue(self.patcher._is_reshade_addon_dll(dxgi_path))

        # 2. renodx-mfgunlock.addon64 must exist
        addon_path = os.path.join(self.game_dir, "renodx-mfgunlock.addon64")
        self.assertTrue(os.path.exists(addon_path))

        # 3. ReShade.ini must exist and have TutorialProgress=4, LoadFromDllMain=1, [RenoDX.MFGUnlock]
        ini_path = os.path.join(self.game_dir, "ReShade.ini")
        self.assertTrue(os.path.exists(ini_path))
        with open(ini_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("TutorialProgress=4", content)
        self.assertTrue("LoadFromDllMain=1" in content or "LoadFromDllMain=renodx-mfgunlock.addon64" in content)
        self.assertIn("[RenoDX.MFGUnlock]", content)
        self.assertIn("ForceMultiplier=", content)

        # 4. Verify integrity
        v_ok, v_msg, v_stat = self.patcher.verify_mode_b_integrity(self.game_dir)
        self.assertTrue(v_ok, v_msg)
        self.assertTrue(v_stat["has_dxgi"])
        self.assertTrue(v_stat["has_addon"])
        self.assertTrue(v_stat["has_ini"])

    def test_rollback_preserves_reshade_when_other_addons_exist(self):
        # 1. Apply Mode B
        self.patcher.patch_game(self.game, BackendType.RESHADE_ADDON)

        # 2. Simulate user also having an HDR mod
        user_hdr_mod = os.path.join(self.game_dir, "renodx-cyberpunk.addon64")
        with open(user_hdr_mod, "wb") as f:
            f.write(b"USER_HDR_ADDON")

        # 3. Rollback Mode B
        rb = RollbackEngine()
        ok, msg = rb.rollback(self.game_dir, self.game.exe_name)
        self.assertTrue(ok, msg)

        # renodx-mfgunlock.addon64 should be deleted
        self.assertFalse(os.path.exists(os.path.join(self.game_dir, "renodx-mfgunlock.addon64")))
        # dxgi.dll SHOULD BE PRESERVED because user still has user_hdr_mod!
        self.assertTrue(os.path.exists(os.path.join(self.game_dir, "dxgi.dll")))
        self.assertTrue(os.path.exists(user_hdr_mod))

    def test_rollback_deletes_reshade_when_no_other_addons_exist(self):
        # 1. Apply Mode B
        self.patcher.patch_game(self.game, BackendType.RESHADE_ADDON)

        # 2. Rollback Mode B without any other addons
        rb = RollbackEngine()
        ok, msg = rb.rollback(self.game_dir, self.game.exe_name)
        self.assertTrue(ok, msg)

        # Both should be deleted
        self.assertFalse(os.path.exists(os.path.join(self.game_dir, "renodx-mfgunlock.addon64")))
        self.assertFalse(os.path.exists(os.path.join(self.game_dir, "dxgi.dll")))

    def test_auto_heal_mode_b(self):
        # Simulate game having only addon64 (user or previous version placed it without ReShade framework)
        addon_path = os.path.join(self.game_dir, "renodx-mfgunlock.addon64")
        with open(addon_path, "wb") as f:
            f.write(b"DUMMY_ADDON")

        dxgi_path = os.path.join(self.game_dir, "dxgi.dll")
        self.assertFalse(os.path.exists(dxgi_path))

        # Auto-heal
        ok, msg = self.patcher.auto_heal_mode_b(self.game_dir)
        self.assertTrue(ok, msg)

        # dxgi.dll should now be healed and present as ReShade64 with addon support!
        self.assertTrue(os.path.exists(dxgi_path))
        self.assertTrue(self.patcher._is_reshade_addon_dll(dxgi_path))

        # ReShade.ini should be initialized with [RenoDX.MFGUnlock]
        ini_path = os.path.join(self.game_dir, "ReShade.ini")
        self.assertTrue(os.path.exists(ini_path))
        with open(ini_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("[RenoDX.MFGUnlock]", content)

if __name__ == "__main__":
    unittest.main()
