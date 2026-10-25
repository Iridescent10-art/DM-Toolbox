# -*- coding: utf-8 -*-
"""
Mode B (OptiScaler / XeFG) x DLSS 5 coexistence contract.

These tests describe the on-disk state the reverse dual-channel topology needs:

  game.exe ──> dxgi.dll            (ReShade 6.8 + RenoDX DLSS-NR addon)
           └─> version.dll         (OptiScaler core, frame generation only)

and the OptiScaler.ini contract that keeps the two pipelines apart. They run on
mock game folders, so they need neither a GPU nor a real game install.

These are pure-logic tests (no Qt). The module name keeps them after the window
tests, which are order-sensitive on this Qt/Python stack.
"""

import configparser
import json
import shutil
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
for _p in (ROOT_DIR, ROOT_DIR / "apps" / "app2_mfg"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from apps.app2_mfg.core import coexistence as coex  # noqa: E402
from apps.app2_mfg.core.ini_sync import IniConfigManager  # noqa: E402

OPTISCALER_TEMPLATE = (
    ROOT_DIR / "apps/app2_mfg/embedded_components/optiscaler/nightly-20261023/OptiScaler.ini"
)


def _fake_pe(imports):
    """Minimal PE-like blob whose byte scan exposes the imported proxy names."""
    body = b"".join(name.encode("ascii") + b"\x00\x00" for name in imports)
    return b"MZ" + b"\x00" * 0x3A + (0x40).to_bytes(4, "little") + b"PE\x00\x00" + b"\x00" * 0x3C + body


def _make_mode_b_game(tmp_path: Path, imports=("version.dll", "winmm.dll")) -> Path:
    """Game folder with Mode B standalone (OptiScaler owns dxgi.dll) and DLSS under Streamline/."""
    (tmp_path / "Game.exe").write_bytes(_fake_pe(imports))
    (tmp_path / "Streamline").mkdir()
    (tmp_path / "Streamline" / "nvngx_dlss.dll").write_bytes(b"game nvngx_dlss" + b"\x00" * 64)
    (tmp_path / "Streamline" / "nvngx_dlssg.dll").write_bytes(b"game nvngx_dlssg" + b"\x00" * 64)
    shutil.copy2(OPTISCALER_TEMPLATE, tmp_path / "OptiScaler.ini")
    (tmp_path / "OptiScaler.dll").write_bytes(b"OptiScaler core" + b"\x00" * 32)
    (tmp_path / "dxgi.dll").write_bytes(b"OptiScaler proxy" + b"\x00" * 32)
    (tmp_path / "fakenvapi.dll").write_bytes(b"fakenvapi" + b"\x00" * 8)
    (tmp_path / "fakenvapi.ini").write_bytes(b"[fakenvapi]" + b"\x00" * 8)
    (tmp_path / "ReShade64.dll").write_bytes(b"ReShade64 secondary" + b"\x00" * 8)
    return tmp_path


def _read_ini(path: Path) -> configparser.ConfigParser:
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.read(path, encoding="utf-8")
    return cp


def test_find_dlss_runtime_prefers_root_then_streamline_then_nested(tmp_path):
    assert coex.find_dlss_runtime(tmp_path) == {}

    (tmp_path / "Streamline").mkdir()
    (tmp_path / "Streamline" / "nvngx_dlss.dll").write_bytes(b"x")
    assert coex.find_dlss_runtime(tmp_path) == {"nvngx_dlss.dll": r"Streamline\nvngx_dlss.dll"}

    nested = tmp_path / "Engine" / "Binaries" / "ThirdParty" / "NVIDIA"
    nested.mkdir(parents=True)
    (nested / "nvngx_dlssg.dll").write_bytes(b"y")
    found = coex.find_dlss_runtime(tmp_path)
    assert found["nvngx_dlss.dll"] == r"Streamline\nvngx_dlss.dll"
    assert found["nvngx_dlssg.dll"] == r"Engine\Binaries\ThirdParty\NVIDIA\nvngx_dlssg.dll"

    # A root copy always wins over a deeper one.
    (tmp_path / "nvngx_dlss.dll").write_bytes(b"z")
    assert coex.find_dlss_runtime(tmp_path)["nvngx_dlss.dll"] == "nvngx_dlss.dll"


def test_adapt_mode_b_moves_proxy_and_writes_coexistence_contract(tmp_path):
    game = _make_mode_b_game(tmp_path)

    ok, message = coex.adapt_mode_b_for_dlss5(game, game / "Game.exe")
    assert ok, message

    # 1. dxgi.dll is vacated for the ReShade host, OptiScaler lands in an imported slot.
    assert not (game / "dxgi.dll").exists()
    assert coex.detect_optiscaler_slot(game) in ("version.dll", "winmm.dll")

    # 2. No second ReShade, no fakenvapi fingerprint spoofing next to DLSS 5.
    assert not (game / "ReShade64.dll").exists()
    assert not (game / "fakenvapi.dll").exists()
    assert not (game / "fakenvapi.ini").exists()

    # 3. OptiScaler stays a pure frame-generation layer that forwards DLSS.
    cp = _read_ini(game / "OptiScaler.ini")
    assert cp.get("Upscalers", "Dx12Upscaler") == "dlss"
    assert cp.get("DLSS", "Enabled").lower() == "true"
    assert cp.get("DLSS", "RenderPresetOverride").lower() == "false"
    assert cp.get("Hooks", "HookOriginalNvngxOnly").lower() == "false"
    assert cp.get("Hooks", "EarlyHooking").lower() == "false"
    assert cp.get("Hooks", "UseNtdllHooks").lower() == "false"
    assert cp.get("Plugins", "LoadReshade").lower() == "false"
    assert cp.get("Plugins", "LoadAsiPlugins").lower() == "true"
    assert cp.get("FrameGen", "FGInput") == "dlssg"
    assert cp.get("FrameGen", "FGOutput") == "xefg"
    assert cp.get("FrameGen", "PreserveSwapChain").lower() == "true"
    assert cp.get("FrameGen", "SkipResizeBuffers").lower() == "true"
    assert cp.get("XeFG", "IgnoreInitChecks").lower() == "true"
    assert cp.get("XeFG", "InterpolationCount") == "2"  # 3X factory default
    assert cp.get("fakenvapi", "UseFakenvapi").lower() == "false"
    # OptiScaler must not hook the game's NVNGX DLSS call: the DLSS 5 addon owns
    # CreateFeature there, and a competing create returns FAIL_NotInitialized
    # (0xBAD00007), which makes OptiScaler fall back to FSR/XeSS.
    assert cp.get("Inputs", "EnableDlssInputs").lower() == "false"

    # 4. OptiScaler is pointed at the game's real DLSS runtime, not left at auto.
    assert cp.get("Libraries", "NvngxDlssPath") == r"Streamline\nvngx_dlss.dll"
    assert cp.get("Libraries", "NvngxFeaturePath") == "Streamline"

    # 5. The runtime is mirrored at the game root and recorded for a clean rollback.
    assert (game / "nvngx_dlss.dll").is_file()
    marker = json.loads((game / ".mfg_coex_backup.json").read_text(encoding="utf-8"))
    assert marker["adapted_for_dlss5"] is True
    assert set(marker["exposed_root_files"]) == {"nvngx_dlss.dll", "nvngx_dlssg.dll"}


def test_restore_mode_b_removes_exposed_runtime_and_marker(tmp_path):
    game = _make_mode_b_game(tmp_path)
    ok, message = coex.adapt_mode_b_for_dlss5(game, game / "Game.exe")
    assert ok, message
    # Pretend DLSS 5 took dxgi.dll.
    (game / "dxgi.dll").write_bytes(b"ReShade 6.8 host" + b"\x00" * 32)

    ok, message = coex.restore_mode_b_from_dlss5(game, game / "Game.exe")
    assert ok, message

    assert coex.detect_optiscaler_slot(game) == "dxgi.dll"
    assert not (game / "nvngx_dlss.dll").exists(), "root copy must not survive uninstall"
    assert not (game / "nvngx_dlssg.dll").exists()
    assert (game / "Streamline" / "nvngx_dlss.dll").is_file(), "the game's original stays"
    assert not (game / ".mfg_coex_backup.json").exists()


def test_streamline_spoofing_stays_auto_on_pre_ada_cards(monkeypatch, tmp_path):
    import core.utils as core_utils

    monkeypatch.setattr(
        core_utils, "get_system_gpu_name", lambda: "NVIDIA GeForce RTX 3060 Laptop GPU"
    )
    game = _make_mode_b_game(tmp_path)
    (game / ".dlss5_manifest.json").write_text("{}", encoding="utf-8")

    IniConfigManager.sync_mode_b_forward(game, {"dx12_upscaler": "dlss"})

    cp = _read_ini(game / "OptiScaler.ini")
    # Auto keeps Streamline seeing an Ada-class device: without it the in-game
    # DLSS super-resolution entry disappears and XeFG loses its motion vectors.
    assert cp.get("Spoofing", "StreamlineSpoofing") == "auto"
    assert cp.get("Spoofing", "Dxgi") == "auto"
    assert cp.get("fakenvapi", "UseFakenvapi").lower() == "false"
