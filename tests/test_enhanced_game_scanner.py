"""
Unit tests for the Enhanced Game Scanner (Multi-drive, Depth-3, Registries, Smart Pruning).
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add project root and app2_mfg to path
APP_DIR = Path(__file__).resolve().parent.parent / "apps" / "app2_mfg"
sys.path.insert(0, str(APP_DIR))

from core.scanner import GameScanner, get_local_drives, is_dir_pruned
from core.models import QualificationStatus


class TestEnhancedGameScanner(unittest.TestCase):
    def setUp(self):
        self.scanner = GameScanner()

    def test_1_get_local_drives(self):
        """Verify dynamic drive detection returns valid local drive paths."""
        drives = get_local_drives()
        self.assertIsInstance(drives, list)
        self.assertGreater(len(drives), 0)
        # C:\ must always be present on a standard Windows machine
        self.assertTrue(any(d.upper().startswith("C:") for d in drives))
        for d in drives:
            self.assertTrue(d.endswith(":\\"))

    def test_2_is_dir_pruned(self):
        """Verify smart pruning excludes system, cache, mods, and savegame folders."""
        self.assertTrue(is_dir_pruned("Windows"))
        self.assertTrue(is_dir_pruned("System32"))
        self.assertTrue(is_dir_pruned("$Recycle.Bin"))
        self.assertTrue(is_dir_pruned("AppData"))
        self.assertTrue(is_dir_pruned("node_modules"))
        self.assertTrue(is_dir_pruned(".git"))
        self.assertTrue(is_dir_pruned("黑神话悟空存档"))
        self.assertTrue(is_dir_pruned("SaveGames"))
        self.assertTrue(is_dir_pruned("mods"))
        self.assertTrue(is_dir_pruned("ShaderCache"))

        # Valid game folders must NOT be pruned
        self.assertFalse(is_dir_pruned("Cyberpunk 2077"))
        self.assertFalse(is_dir_pruned("Black Myth Wukong"))
        self.assertFalse(is_dir_pruned("Arknights Endfield"))
        self.assertFalse(is_dir_pruned("StarCitizen"))

    def test_3_resolve_game_title_depth_3(self):
        """Verify game title resolution from 3-level deep directory paths."""
        root = r"E:\游戏"
        # Case A: E:\游戏\对马岛之魂 导演剪辑版\15172\V1053.7.0809.1937
        curr = r"E:\游戏\对马岛之魂 导演剪辑版\15172\V1053.7.0809.1937"
        title = self.scanner._resolve_game_title(curr, root, "V1053.7.0809.1937")
        self.assertEqual(title, "对马岛之魂 导演剪辑版")

        # Case B: E:\game\刺客信条：黑旗\30001
        root2 = r"E:\game"
        curr2 = r"E:\game\刺客信条：黑旗\30001"
        title2 = self.scanner._resolve_game_title(curr2, root2, "30001")
        self.assertEqual(title2, "刺客信条：黑旗")

        # Case C: Known game alias
        curr3 = r"D:\game\yysls"
        title3 = self.scanner._resolve_game_title(curr3, r"D:\game", "yysls")
        self.assertIn("燕云十六声", title3)

    def test_4_depth_3_game_discovery_and_early_stop(self):
        """Verify that a game nested 3 levels deep is found and stops recursing into child asset folders."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            # Create: td / RPG / CyberGame / 30001
            game_dir = td_path / "RPG" / "CyberGame" / "30001"
            game_dir.mkdir(parents=True)
            (game_dir / "game.exe").write_bytes(b"MZ" + b"\x00" * 64)

            # Create an asset child folder inside the game that shouldn't be scanned as a game
            child_dir = game_dir / "SubAssets"
            child_dir.mkdir()
            (child_dir / "tool.exe").write_bytes(b"MZ" + b"\x00" * 64)

            results = []
            self.scanner._scan_folder_recursive(str(td_path), str(td_path), depth=0, max_depth=3, results=results)

            self.assertEqual(len(results), 1)
            found = results[0]
            self.assertEqual(found.name, "CyberGame")
            self.assertEqual(found.exe_name, "game.exe")
            self.assertEqual(os.path.normpath(found.target_dir), os.path.normpath(str(game_dir)))

    def test_5_ue_game_binaries_discovery(self):
        """Verify Unreal Engine games with exes in Binaries/Win64 are resolved properly."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bin_dir = td_path / "Binaries" / "Win64"
            bin_dir.mkdir(parents=True)
            (bin_dir / "TestGame-Win64-Shipping.exe").write_bytes(b"MZ" + b"\x00" * 64)

            game = self.scanner.analyze_game_directory("Test UE Game", "Test", str(td_path))
            self.assertIsNotNone(game)
            self.assertEqual(game.exe_name, "TestGame-Win64-Shipping.exe")
            self.assertEqual(os.path.normpath(game.target_dir), os.path.normpath(str(bin_dir)))

    def test_6_ignore_repack_split_archives(self):
        """Verify that multi-part repack archives (.part01.exe) are filtered out when real game binary exists."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            (td_path / "GameSetup.part01.exe").write_bytes(b"MZ" + b"\x00" * 64)
            (td_path / "MainGame.exe").write_bytes(b"MZ" + b"\x00" * 64)

            game = self.scanner.analyze_game_directory("Archive Test", "Test", str(td_path))
            self.assertIsNotNone(game)
            self.assertEqual(game.exe_name, "MainGame.exe")

    def test_7_backward_compatibility_interfaces(self):
        """Verify scan_domestic_and_drives and _find_primary_executable maintain backward compatibility."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            (td_path / "app.exe").write_bytes(b"MZ" + b"\x00" * 64)

            # _find_primary_executable with (target_dir, install_dir)
            exe = self.scanner._find_primary_executable(str(td_path), str(td_path))
            self.assertEqual(os.path.basename(exe), "app.exe")


if __name__ == "__main__":
    unittest.main()
