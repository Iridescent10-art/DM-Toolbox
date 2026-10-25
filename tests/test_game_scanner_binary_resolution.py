# -*- coding: utf-8 -*-
"""
Tests for GameScanner deep binary sniffing and get_game_info_from_exe resolution.
Verifies that:
1. get_game_info_from_exe and scan_games methods exist and operate correctly.
2. Root launchers (e.g. REDprelauncher.exe) automatically resolve to the real 64-bit engine binary in bin/x64.
3. Target injection directory is strictly set to the binary directory containing DirectX 12/Streamline/DLSS DLLs.
4. GameCacheManager reconciles existing cached launcher paths to genuine engine binaries.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
import pytest

# Add package roots
PACKAGE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PACKAGE_ROOT / "apps" / "app2_mfg"))
sys.path.insert(0, str(PACKAGE_ROOT))

from apps.app2_mfg.core.scanner import GameScanner, KNOWN_GAME_NAMES, STANDARD_EXE_SUBDIRS
from apps.app2_mfg.core.models import GameInfo, QualificationStatus
from apps.app2_mfg.core.game_cache import GameCacheManager


def test_scanner_methods_exist():
    scanner = GameScanner()
    assert hasattr(scanner, "get_game_info_from_exe"), "GameScanner must expose get_game_info_from_exe"
    assert hasattr(scanner, "scan_games"), "GameScanner must expose scan_games"
    assert callable(scanner.get_game_info_from_exe)
    assert callable(scanner.scan_games)


def test_standard_subdirs_prioritizes_subfolders():
    # Subdirectories with 64-bit binaries must precede root ""
    assert STANDARD_EXE_SUBDIRS[0] != "", "Root directory must not be first in STANDARD_EXE_SUBDIRS"
    assert STANDARD_EXE_SUBDIRS[-1] == "", "Root directory should be last fallback in STANDARD_EXE_SUBDIRS"
    assert "bin/x64" in STANDARD_EXE_SUBDIRS
    assert "bin/x64_dx12" in STANDARD_EXE_SUBDIRS
    assert "Binaries/Win64" in STANDARD_EXE_SUBDIRS


def test_mock_launcher_auto_upgrade():
    """Verify that picking a launcher in root automatically detects the real binary in bin/x64."""
    with tempfile.TemporaryDirectory() as td:
        root_dir = Path(td)
        # Create root launcher
        launcher_exe = root_dir / "REDprelauncher.exe"
        launcher_exe.write_bytes(b"MZmocklauncher")

        # Create real 64-bit binary in bin/x64
        bin_dir = root_dir / "bin" / "x64"
        bin_dir.mkdir(parents=True)
        game_exe = bin_dir / "Cyberpunk2077.exe"
        game_exe.write_bytes(b"MZmockgame")

        # Add mock Streamline & DLSSG
        (bin_dir / "sl.interposer.dll").write_bytes(b"MZinterposer")
        (bin_dir / "nvngx_dlssg.dll").write_bytes(b"MZdlssg")

        scanner = GameScanner()

        # Case 1: User explicitly picks launcher_exe
        info_from_launcher = scanner.get_game_info_from_exe(str(launcher_exe))
        assert info_from_launcher is not None
        assert info_from_launcher.exe_path.lower() == str(game_exe).lower()
        assert info_from_launcher.target_dir.lower() == str(bin_dir).lower()
        assert info_from_launcher.exe_name.lower() == "cyberpunk2077.exe"
        assert "Cyberpunk 2077" in info_from_launcher.name

        # Case 2: User explicitly picks game_exe
        info_from_game = scanner.get_game_info_from_exe(str(game_exe))
        assert info_from_game is not None
        assert info_from_game.exe_path.lower() == str(game_exe).lower()
        assert info_from_game.target_dir.lower() == str(bin_dir).lower()

        # Case 3: Folder scan on root_dir
        info_from_dir = scanner.analyze_game_directory("Cyberpunk 2077", "Test", str(root_dir))
        assert info_from_dir is not None
        assert info_from_dir.exe_path.lower() == str(game_exe).lower()
        assert info_from_dir.target_dir.lower() == str(bin_dir).lower()


def test_real_cyberpunk_resolution_if_present():
    """If real Cyberpunk 2077 is installed on the user's system, verify exact detection."""
    real_cp = Path(r"D:\game\steam\steamapps\common\Cyberpunk 2077")
    if not real_cp.exists() or not (real_cp / "bin" / "x64" / "Cyberpunk2077.exe").exists():
        pytest.skip("Cyberpunk 2077 not installed at default test path")

    scanner = GameScanner()
    g = scanner.analyze_game_directory("Cyberpunk 2077", "Steam", str(real_cp))
    assert g is not None
    assert g.exe_name.lower() == "cyberpunk2077.exe"
    assert g.target_dir.lower() == str(real_cp / "bin" / "x64").lower()
    assert g.qualification == QualificationStatus.QUALIFIED


def test_cache_reconciliation():
    """Verify that GameCacheManager.reconcile_game_binaries upgrades launcher paths."""
    with tempfile.TemporaryDirectory() as td:
        root_dir = Path(td)
        launcher_exe = root_dir / "REDprelauncher.exe"
        launcher_exe.write_bytes(b"MZmocklauncher")

        bin_dir = root_dir / "bin" / "x64"
        bin_dir.mkdir(parents=True)
        game_exe = bin_dir / "Cyberpunk2077.exe"
        game_exe.write_bytes(b"MZmockgame")

        stale_game = GameInfo(
            name="Cyberpunk 2077",
            source="Steam",
            install_dir=str(root_dir),
            target_dir=str(root_dir),
            exe_path=str(launcher_exe),
            exe_name="REDprelauncher.exe",
            qualification=QualificationStatus.NOT_SUPPORTED
        )

        games = [stale_game]
        changed = GameCacheManager.reconcile_game_binaries(games)
        assert changed is True
        assert games[0].exe_name.lower() == "cyberpunk2077.exe"
        assert games[0].target_dir.lower() == str(bin_dir).lower()
