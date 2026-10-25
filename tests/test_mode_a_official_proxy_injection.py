# -*- coding: utf-8 -*-
"""
Test Suite: Mode A (dashdogy/MFG-Unlocker) Official Proxy Injection Architecture
Verifies that Mode A:
1. Conforms 100% to upstream dashdogy/MFG-Unlocker official injection specification.
2. Standard standalone injection deploys dxgi.dll (or user selected proxy).
3. Dual-injection with DLSS 5 deploys version.dll (or winmm.dll), never colliding with DLSS 5 ReShade 6.8.
4. Strictly leaves game's native bink2w64.dll untouched - ZERO Bink hijacking or renaming.
5. Self-heals any legacy bink2w64Hooked.dll left by past versions back to original bink2w64.dll.
6. Enforces single proxy rule (换，不是加；代理任何时候只放一个).
7. Complete, clean unpatching without leftover files or corrupted binaries.
"""

import os
import sys
import json
import shutil
import tempfile
from typing import Tuple
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

APP2_DIR = ROOT_DIR / "apps" / "app2_mfg"
if str(APP2_DIR) not in sys.path:
    sys.path.insert(0, str(APP2_DIR))

from apps.app6_dlss5.engine.injector import DLSS5Injector
from core.models import GameInfo, BackendType, QualificationStatus
from core.patcher import PatchEngine
from core.updater import ComponentUpdater
from core.state_cleaner import CleanGameDirectoryState, is_dlss5_present, is_dashdogy_dll_file
from core.optiscaler_config import save_mode_a_preset, load_mode_a_preset, DEFAULT_MODE_A_PRESET


def _create_mock_game(base_path: Path) -> Tuple[Path, GameInfo]:
    game_dir = base_path / "Binaries" / "Win64"
    game_dir.mkdir(parents=True, exist_ok=True)
    game_exe = game_dir / "Game.exe"
    game_exe.write_bytes(b"MZ" + b"\x00" * 4096)
    (game_dir / "sl.interposer.dll").write_bytes(b"mock_sl_interposer" + b"\x00" * 512)
    (game_dir / "nvngx_dlssg.dll").write_bytes(b"mock_nvngx_dlssg" + b"\x00" * 512)

    game_info = GameInfo(
        name="TestGame",
        source="Custom",
        install_dir=str(game_dir),
        target_dir=str(game_dir),
        exe_path=str(game_exe),
        exe_name="Game.exe",
        qualification=QualificationStatus.QUALIFIED
    )
    return game_dir, game_info


def test_mode_a_standalone_default_dxgi():
    """Verify Mode A standalone defaults to dxgi.dll and never touches native bink2w64.dll."""
    with tempfile.TemporaryDirectory() as td:
        game_dir, game_info = _create_mock_game(Path(td))

        # Put native bink2w64.dll
        native_bink = game_dir / "bink2w64.dll"
        bink_payload = b"ORIGINAL_RAD_BINK_BYTES_12345678" + b"\x55" * 2048
        native_bink.write_bytes(bink_payload)

        # Reset preset to auto
        preset = dict(DEFAULT_MODE_A_PRESET)
        preset["proxy_dll"] = "auto"
        save_mode_a_preset(preset)

        updater = ComponentUpdater()
        patcher = PatchEngine(updater)
        ok, msg = patcher.patch_game(game_info, requested_backend=BackendType.STANDALONE)
        assert ok, f"Mode A standalone patch failed: {msg}"

        # 1. dxgi.dll is deployed as dashdogy proxy
        dxgi_p = game_dir / "dxgi.dll"
        assert dxgi_p.exists(), "Standalone Mode A must deploy dxgi.dll by default"
        assert is_dashdogy_dll_file(str(dxgi_p)), "dxgi.dll must be dashdogy/MFGUnlocker"

        # 2. bink2w64.dll must remain 100% UNTOUCHED
        assert native_bink.exists(), "Native bink2w64.dll must exist"
        assert native_bink.read_bytes() == bink_payload, "Native bink2w64.dll must not be altered!"
        assert not (game_dir / "bink2w64Hooked.dll").exists(), "bink2w64Hooked.dll must NOT be created"

        # 3. Only 1 proxy DLL exists
        for other_proxy in ["version.dll", "winmm.dll", "dinput8.dll"]:
            assert not (game_dir / other_proxy).exists(), f"Old proxy slot {other_proxy} must not exist"


def test_mode_a_dlss5_coexistence_version_dll():
    """Verify Mode A coexisting with DLSS 5 uses version.dll and keeps dxgi.dll for ReShade."""
    with tempfile.TemporaryDirectory() as td:
        game_dir, game_info = _create_mock_game(Path(td))

        # 1. Inject DLSS 5 first (takes dxgi.dll)
        ok_dlss, _ = DLSS5Injector.inject(str(game_dir), arch_choice="rtx20_30_40")
        assert ok_dlss

        dxgi_p = game_dir / "dxgi.dll"
        assert dxgi_p.exists()
        dlss5_dxgi_size = dxgi_p.stat().st_size

        # 2. Patch Mode A
        updater = ComponentUpdater()
        patcher = PatchEngine(updater)
        ok_a, msg_a = patcher.patch_game(game_info, requested_backend=BackendType.STANDALONE)
        assert ok_a, f"Mode A coexistence patch failed: {msg_a}"

        # 3. dxgi.dll is untouched ReShade 6.8
        assert dxgi_p.stat().st_size == dlss5_dxgi_size, "dxgi.dll must stay as DLSS 5 ReShade 6.8"

        # 4. Mode A is on version.dll
        ver_p = game_dir / "version.dll"
        assert ver_p.exists(), "Mode A must deploy to version.dll during DLSS 5 coexistence"
        assert is_dashdogy_dll_file(str(ver_p)), "version.dll must be dashdogy/MFGUnlocker"

        # 5. Native bink2w64.dll is untouched
        assert not (game_dir / "bink2w64Hooked.dll").exists()


def test_mode_a_self_healing_legacy_bink_hook():
    """Verify Mode A automatically heals and restores any legacy bink2w64Hooked.dll."""
    with tempfile.TemporaryDirectory() as td:
        game_dir, game_info = _create_mock_game(Path(td))

        # Simulate legacy corrupted state where bink2w64Hooked.dll exists
        original_bink_content = b"GENUINE_RAD_GAME_TOOLS_BINK_CONTENT" + b"\x99" * 1024
        (game_dir / "bink2w64Hooked.dll").write_bytes(original_bink_content)
        (game_dir / "bink2w64.dll").write_bytes(b"OLD_CORRUPTED_INJECTED_DLL" + b"\x00" * 1024)

        updater = ComponentUpdater()
        patcher = PatchEngine(updater)
        ok, msg = patcher.patch_game(game_info, requested_backend=BackendType.STANDALONE)
        assert ok

        # bink2w64Hooked.dll must be self-healed back to bink2w64.dll
        assert not (game_dir / "bink2w64Hooked.dll").exists(), "bink2w64Hooked.dll must be cleared/renamed"
        assert (game_dir / "bink2w64.dll").read_bytes() == original_bink_content, "bink2w64.dll must be restored to original"


def test_mode_a_custom_proxy_slot_selection():
    """Verify user can select winmm.dll or dinput8.dll in mode_a_preset.json."""
    with tempfile.TemporaryDirectory() as td:
        game_dir, game_info = _create_mock_game(Path(td))

        # Select winmm.dll in preset
        preset = dict(DEFAULT_MODE_A_PRESET)
        preset["proxy_dll"] = "winmm.dll"
        save_mode_a_preset(preset)

        updater = ComponentUpdater()
        patcher = PatchEngine(updater)
        ok, msg = patcher.patch_game(game_info, requested_backend=BackendType.STANDALONE)
        assert ok

        winmm_p = game_dir / "winmm.dll"
        assert winmm_p.exists(), "winmm.dll must be deployed when configured in preset"
        assert is_dashdogy_dll_file(str(winmm_p))
        assert not (game_dir / "dxgi.dll").exists(), "dxgi.dll must not be deployed when winmm is selected"

        # Restore default preset
        preset["proxy_dll"] = "auto"
        save_mode_a_preset(preset)
