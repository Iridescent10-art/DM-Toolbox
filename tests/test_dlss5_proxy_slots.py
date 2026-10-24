# -*- coding: utf-8 -*-
"""
Unit and Integration Test Suite for DLSS 5 Anti-Cheat Bypass and Proxy Slots.
Tests:
1. detect_game_render_api (Unity / ACE anti-cheat / OptiScaler detection)
2. clean_conflicting_proxies (multi-proxy mutex cleanup)
3. DLSS 5 injection with proxy_choice (d3d11.dll, ReShade64.dll, auto)
4. OptiScaler chain-loading activation (LoadReshade = true)
5. DLSS 5 status reporting with active_proxy
6. DLSS 5 restore cleaning all proxy slots
7. DLSS5DelayedInjector process query, window detection, and remote thread injection
"""

import os
import sys
import time
import shutil
import tempfile
import subprocess
import pytest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from apps.app6_dlss5.engine.injector import (
    DLSS5_PROXY_SLOTS,
    DEFAULT_PROXY_SLOT,
    ALL_DLSS5_PROXY_NAMES,
    detect_game_render_api,
    clean_conflicting_proxies,
    check_game_dlss5_status,
    DLSS5Injector,
    DLSS5DelayedInjector,
    LOCAL_ASSETS_DIR
)


def test_proxy_slots_constants():
    """Verify proxy slots definitions."""
    assert "auto" in DLSS5_PROXY_SLOTS
    assert "dxgi.dll" in DLSS5_PROXY_SLOTS
    assert "d3d11.dll" in DLSS5_PROXY_SLOTS
    assert "d3d12.dll" in DLSS5_PROXY_SLOTS
    assert "ReShade64.dll" in DLSS5_PROXY_SLOTS
    for p in ["dxgi.dll", "d3d11.dll", "d3d12.dll", "ReShade64.dll"]:
        assert p in ALL_DLSS5_PROXY_NAMES


def test_detect_game_render_api():
    """Verify engine and anti-cheat auto-detection."""
    with tempfile.TemporaryDirectory() as tmpdir:
        td = Path(tmpdir)
        # 1. Standard game -> dxgi.dll
        rec_proxy, reason, details = detect_game_render_api(td)
        assert rec_proxy == "dxgi.dll"
        assert details["anticheat"] is False

        # 2. Unity game (UnityPlayer.dll) -> ReShade64.dll (zero-landing delayed injection)
        (td / "UnityPlayer.dll").write_bytes(b"Unity")
        rec_proxy, reason, details = detect_game_render_api(td)
        assert rec_proxy == "ReShade64.dll"
        assert details["engine"] == "unity"

        # 3. Unity game with ACE anti-cheat -> d3d12.dll (Nexus Mods / RenoDX verified ACE bypass)
        (td / "ACE-Base64.dll").write_bytes(b"ACE")
        rec_proxy, reason, details = detect_game_render_api(td)
        assert rec_proxy == "d3d12.dll"
        assert details["anticheat"] is True
        assert details["anticheat_type"] == "ACE"


def test_clean_conflicting_proxies():
    """Verify mutual exclusion: cleans competing ReShade proxies while keeping chosen one."""
    with tempfile.TemporaryDirectory() as tmpdir:
        td = Path(tmpdir)
        fake_reshade = b"MZ" + b"\x00" * 100 + b"crosire ReShade" + b"\x00" * 1000

        (td / "dxgi.dll").write_bytes(fake_reshade)
        (td / "d3d11.dll").write_bytes(fake_reshade)
        (td / "d3d12.dll").write_bytes(fake_reshade)

        ok, msg, removed = clean_conflicting_proxies(td, keep_proxy="d3d11.dll")
        assert ok is True
        assert not (td / "dxgi.dll").exists()
        assert not (td / "d3d12.dll").exists()
        assert (td / "d3d11.dll").exists()
        assert "dxgi.dll" in removed
        assert "d3d12.dll" in removed
        assert "d3d11.dll" not in removed


def test_injection_with_proxy_slots():
    """Verify injection deploying to specified proxy slots."""
    with tempfile.TemporaryDirectory() as tmpdir:
        game_dir = Path(tmpdir) / "bin"
        game_dir.mkdir(parents=True, exist_ok=True)
        (game_dir / "game.exe").write_bytes(b"MZ" + b"\x00" * 1024)

        # 1. Inject with d3d11.dll
        ok, msg = DLSS5Injector.inject(
            target_dir=str(game_dir),
            source_dir=str(LOCAL_ASSETS_DIR),
            proxy_choice="d3d11.dll",
            mode="MODE_A"
        )
        assert ok is True
        assert (game_dir / "d3d11.dll").is_file()
        assert not (game_dir / "dxgi.dll").exists()
        assert (game_dir / "renodx-dlss.addon64").is_file()

        stat = check_game_dlss5_status(str(game_dir))
        assert stat["is_injected"] is True
        assert stat["has_reshade"] is True
        assert stat["active_proxy"] == "d3d11.dll"

        # 2. Inject with ReShade64.dll on game with OptiScaler.ini
        (game_dir / "OptiScaler.ini").write_text("[Plugins]\nLoadReshade = false\n", encoding="utf-8")
        ok, msg = DLSS5Injector.inject(
            target_dir=str(game_dir),
            source_dir=str(LOCAL_ASSETS_DIR),
            proxy_choice="ReShade64.dll",
            mode="MODE_A"
        )
        assert ok is True
        assert (game_dir / "ReShade64.dll").is_file()
        assert not (game_dir / "d3d11.dll").exists(), "Old d3d11 proxy must be purged by mutex cleaner"

        # Verify OptiScaler.ini has LoadReshade = true
        opti_content = (game_dir / "OptiScaler.ini").read_text(encoding="utf-8")
        assert "LoadReshade = true" in opti_content

        stat = check_game_dlss5_status(str(game_dir))
        assert stat["active_proxy"] == "ReShade64.dll"

        # 3. Clean Restore
        ok, res_msg = DLSS5Injector.restore(str(game_dir))
        assert ok is True
        assert not (game_dir / "ReShade64.dll").exists()
        assert not (game_dir / "renodx-dlss.addon64").exists()
        assert not (game_dir / "nvngx_dlssnr.dll").exists()


def test_delayed_injector_apis():
    """Verify DLSS5DelayedInjector process query and injection engine."""
    current_pid = os.getpid()
    python_pids = DLSS5DelayedInjector.get_pids_by_name("python.exe")
    assert current_pid in python_pids

    # Check is_module_loaded
    assert DLSS5DelayedInjector.is_module_loaded(current_pid, "kernel32.dll") is True

    # Test injection on a spawned target process
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(5)"])
    try:
        time.sleep(0.5)
        ok, msg = DLSS5DelayedInjector.inject_dll_to_process(p.pid, r"C:\Windows\System32\version.dll")
        assert ok is True
        assert DLSS5DelayedInjector.is_module_loaded(p.pid, "version.dll") is True
    finally:
        p.terminate()


def test_ace_endfield_clean_d3d12_deployment():
    """Verify pure ReShade 6.8 deployment as d3d12.dll with HookOpenGL=0 on ACE games."""
    with tempfile.TemporaryDirectory() as tmpdir:
        game_dir = Path(tmpdir) / "Arknights Endfield"
        game_dir.mkdir(parents=True, exist_ok=True)
        (game_dir / "Endfield.exe").write_bytes(b"MZ" + b"\x00" * 1024)
        (game_dir / "PlatformProcess.exe").write_bytes(b"MZ" + b"\x00" * 1024)
        (game_dir / "ACE-Base64.dll").write_bytes(b"ACE" + b"\x00" * 1024)

        # 1. Inject with d3d12.dll
        ok, msg = DLSS5Injector.inject(
            target_dir=str(game_dir),
            source_dir=str(LOCAL_ASSETS_DIR),
            proxy_choice="d3d12.dll",
            mode="MODE_A"
        )
        assert ok is True
        assert (game_dir / "d3d12.dll").is_file()
        assert (game_dir / "renodx-dlss.addon64").is_file()
        assert not (game_dir / "OptiScaler.ini").exists()

        # Verify ReShade.ini contains HookOpenGL=0 protection
        ini_content = (game_dir / "ReShade.ini").read_text(encoding="utf-8")
        assert "HookOpenGL=0" in ini_content
        assert "HookDirectX=1" in ini_content

        stat = check_game_dlss5_status(str(game_dir))
        assert stat["is_injected"] is True
        assert stat["has_reshade"] is True
        assert stat["active_proxy"] == "d3d12.dll"

        # 2. Restore
        ok, res_msg = DLSS5Injector.restore(str(game_dir))
        assert ok is True
        assert not (game_dir / "d3d12.dll").exists()
        assert not (game_dir / "renodx-dlss.addon64").exists()
