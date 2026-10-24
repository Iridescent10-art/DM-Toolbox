# -*- coding: utf-8 -*-
"""
DLSS 5 (DLSS-NR / RenoDX addon) x Multi-Frame Generation coexistence router.
================================================================================
Single source of truth for proxy-DLL slot isolation between:

  * DLSS 5  -> ReShade 6.8 render host, must own ``dxgi.dll`` (loaded as early as
               possible, before the game creates its D3D12 device / NGX context);
  * Mode A  -> dashdogy / MFG-Unlocker, secondary proxy;
  * Mode C  -> OptiScaler / XeSS 2.0 / XeFG, secondary proxy;

Why a shared router is required
-------------------------------
Each app used to resolve its own slot and clean up *its own* idea of the other
app's files. ``DLSS5Injector.inject()`` used to overwrite ``dxgi.dll`` with
ReShade unconditionally, so a Mode C install deployed as ``dxgi.dll`` lost its
only OptiScaler proxy (``OptiScaler.ini`` + ``libxess_fg.dll`` stayed behind,
but nothing hooked the game any more). The inverse order produced the crash
reported by users: two independent proxies both hooking DXGI/D3D12/NGX, plus an
``OptiScaler.ini`` that disabled DLSS passthrough while XeFG still asked for a
DLSS-G input.

This module keeps the rules in one place so every entry point converges to the
same on-disk state:

  1. ``dxgi.dll`` is reserved for the ReShade host whenever DLSS 5 is active;
  2. exactly one OptiScaler / dashdogy proxy exists, in a slot the game really
     imports (``winmm.dll`` > ``version.dll`` > ``dinput8.dll``);
  3. no second ReShade host (``ReShade64.dll`` / ``d3d12-ReShade64.dll``);
  4. ``fakenvapi`` never lives next to a DLSS 5 install: it hijacks the whole
     NVAPI surface and makes the neural-reconstruction runtime query a fake GPU.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional

# Proxy slots that may host a frame-generation core when dxgi.dll belongs to ReShade.
FG_PROXY_SLOTS: List[str] = ["winmm.dll", "version.dll", "dinput8.dll", "wininet.dll"]

# Every proxy DLL a game may import that we could have created.
ALL_PROXY_SLOTS: List[str] = ["dxgi.dll"] + FG_PROXY_SLOTS

# Proxy slots OptiScaler itself is allowed to be renamed to.
OPTISCALER_SLOTS: List[str] = ["dxgi.dll"] + FG_PROXY_SLOTS

SECONDARY_RESHADE_FILES: List[str] = [
    "ReShade64.dll",
    "d3d12-ReShade64.dll",
    "dxgi.dll.reshade_bak",
    "ReShade64.dll.mfg_bak",
]

FAKENVAPI_FILES: List[str] = [
    "fakenvapi.dll",
    "fakenvapi.ini",
    "fakenvapi.log",
]

_SIG_WINDOW = 16 * 1024 * 1024


def _read_signature_bytes(path: Path) -> bytes:
    """Read the head (and tail for very large files) of a binary for signature checks."""
    try:
        if not path.is_file():
            return b""
        size = path.stat().st_size
        with open(path, "rb") as fh:
            if size > _SIG_WINDOW * 2:
                head = fh.read(_SIG_WINDOW)
                fh.seek(max(0, size - _SIG_WINDOW))
                return head + fh.read()
            return fh.read()
    except Exception:
        return b""


def is_reshade_binary(path: os.PathLike | str) -> bool:
    """True for a ReShade host binary (OptiScaler never matches)."""
    data = _read_signature_bytes(Path(path))
    if not data or b"OptiScaler" in data:
        return False
    return b"ReShade" in data or b"crosire" in data


def is_optiscaler_binary(path: os.PathLike | str) -> bool:
    """True for an OptiScaler core binary."""
    data = _read_signature_bytes(Path(path))
    return bool(data) and (b"OptiScaler" in data or b"libxess" in data)


def is_dashdogy_binary(path: os.PathLike | str) -> bool:
    """True for a dashdogy / MFG-Unlocker proxy binary."""
    data = _read_signature_bytes(Path(path))
    return bool(data) and (b"MFGUnlocker" in data or b"RTX40MFG" in data or b"RTXMFG" in data)


def classify_slot(target_dir: os.PathLike | str, slot: str) -> str:
    """Classify one proxy slot: reshade / optiscaler / dashdogy / foreign / missing."""
    path = Path(target_dir) / slot
    if not path.is_file():
        return "missing"
    if is_reshade_binary(path):
        return "reshade"
    if is_optiscaler_binary(path):
        return "optiscaler"
    if is_dashdogy_binary(path):
        return "dashdogy"
    return "foreign"


def scan_proxy_slots(target_dir: os.PathLike | str) -> Dict[str, str]:
    """Map every known proxy slot to its classification."""
    return {slot: classify_slot(target_dir, slot) for slot in ALL_PROXY_SLOTS}


def detect_optiscaler_slot(target_dir: os.PathLike | str) -> Optional[str]:
    """Return the proxy slot currently hosting OptiScaler, if any."""
    for slot in OPTISCALER_SLOTS:
        if classify_slot(target_dir, slot) == "optiscaler":
            return slot
    return None


def detect_dashdogy_slot(target_dir: os.PathLike | str) -> Optional[str]:
    """Return the proxy slot currently hosting dashdogy / MFG-Unlocker, if any."""
    for slot in OPTISCALER_SLOTS:
        if classify_slot(target_dir, slot) == "dashdogy":
            return slot
    return None


def read_pe_imports(exe_path: Optional[os.PathLike | str]) -> List[str]:
    """
    Return the lower-case DLL names imported by a PE executable.

    Uses pefile when available and falls back to a bounded byte scan, which is
    enough to pick a proxy slot on packed launchers.
    """
    imported: List[str] = []
    if not exe_path:
        return imported
    exe = Path(exe_path)
    if not exe.is_file():
        return imported
    try:
        with open(exe, "rb") as fh:
            hdr = fh.read(1024)
        if not hdr.startswith(b"MZ") or len(hdr) < 0x40:
            raise ValueError("Not a valid PE")
        pe_offset = int.from_bytes(hdr[0x3C:0x40], byteorder="little")
        if pe_offset <= 0 or pe_offset + 4 > len(hdr) or hdr[pe_offset:pe_offset+4] != b"PE\x00\x00":
            raise ValueError("Invalid PE offset/signature")
        import pefile  # type: ignore

        pe = pefile.PE(str(exe), fast_load=True)
        try:
            pe.parse_data_directories(
                directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]]
            )
            for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []) or []:
                try:
                    imported.append(entry.dll.decode("utf-8", errors="ignore").lower())
                except Exception:
                    continue
        finally:
            try:
                pe.close()
            except Exception:
                pass
    except Exception:
        try:
            with open(exe, "rb") as fh:
                blob = fh.read(16 * 1024 * 1024).lower()
            for cand in FG_PROXY_SLOTS:
                if cand.encode("ascii") in blob:
                    imported.append(cand)
        except Exception:
            pass
    return imported


def guess_game_executable(target_dir: os.PathLike | str) -> Optional[str]:
    """Pick the most likely game executable inside target_dir (largest .exe)."""
    td = Path(target_dir)
    if not td.is_dir():
        return None
    best: Optional[Path] = None
    try:
        for cand in td.iterdir():
            if not cand.is_file() or cand.suffix.lower() != ".exe":
                continue
            if best is None or cand.stat().st_size > best.stat().st_size:
                best = cand
    except Exception:
        return None
    return str(best) if best else None


def pick_fg_proxy_slot(
    target_dir: os.PathLike | str,
    exe_path: Optional[os.PathLike | str] = None,
) -> str:
    """
    Choose the secondary proxy slot for a frame-generation core.

    Priority follows the game's own import table (the earlier Windows resolves
    the DLL, the earlier the hook is installed). ``dxgi.dll`` is never returned:
    it is reserved for the ReShade host that DLSS 5 needs.
    """
    td = Path(target_dir)
    imported = read_pe_imports(exe_path or guess_game_executable(td))

    for slot in FG_PROXY_SLOTS:
        if slot in imported and classify_slot(td, slot) in ("missing", "optiscaler", "dashdogy"):
            return slot
    # No import-table hit (packed launcher / dynamic load): version.dll is the
    # safest default, every D3D12 title imports the version API.
    for slot in ("version.dll", "winmm.dll", "dinput8.dll", "wininet.dll"):
        if classify_slot(td, slot) in ("missing", "optiscaler", "dashdogy"):
            return slot
    return "version.dll"


def _remove(path: Path) -> bool:
    try:
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
        return True
    except Exception:
        try:
            os.chmod(path, 0o666)
            path.unlink(missing_ok=True)
            return True
        except Exception:
            return False


def purge_secondary_reshade(target_dir: os.PathLike | str) -> List[str]:
    """
    Remove every ReShade host that is not the ``dxgi.dll`` base.

    Two ReShade instances in one process install duplicate D3D12 hooks and
    crash on device destruction, which is exactly what happened when OptiScaler
    chain-loaded a second copy next to the DLSS 5 ``dxgi.dll``.
    """
    td = Path(target_dir)
    removed: List[str] = []
    for name in SECONDARY_RESHADE_FILES:
        path = td / name
        if path.exists():
            if _remove(path):
                removed.append(name)
    return removed


def purge_fakenvapi(target_dir: os.PathLike | str) -> List[str]:
    """
    Remove fakenvapi next to a DLSS 5 install.

    fakenvapi emulates a whole NVAPI device, and the neural-reconstruction
    runtime (``nvngx_dlssnr.dll``) queries NVAPI for the real GPU before it
    picks its kernels. A faked adapter makes it select kernels the physical GPU
    cannot run, which surfaces as an access violation right after the first
    upscaled frame. OptiScaler itself keeps working without it as long as the
    game exposes DLSS-G natively (RTX 40/50 + Streamline).
    """
    td = Path(target_dir)
    removed: List[str] = []
    for name in FAKENVAPI_FILES:
        path = td / name
        if path.exists() and _remove(path):
            removed.append(name)
    return removed


def _find_optiscaler_source() -> Optional[str]:
    """Locate a cached OptiScaler.dll to re-deploy a lost proxy."""
    try:
        from core.updater import ComponentUpdater
        from core.models import BackendType

        cached = ComponentUpdater().get_latest_cached_dir(BackendType.OPTISCALER_FSR)
        if cached:
            for cand in (Path(cached) / "OptiScaler.dll", Path(cached) / "OptiScaler" / "OptiScaler.dll"):
                if cand.is_file():
                    return str(cand)
    except Exception:
        pass
    root = Path(__file__).resolve().parent.parent.parent.parent
    emb = root / "apps" / "app2_mfg" / "embedded_components" / "optiscaler"
    try:
        for cand in sorted(emb.rglob("OptiScaler.dll")):
            if cand.is_file():
                return str(cand)
    except Exception:
        pass
    return None


def ensure_optiscaler_proxy(
    target_dir: os.PathLike | str,
    exe_path: Optional[os.PathLike | str] = None,
) -> Optional[str]:
    """
    Keep exactly one OptiScaler proxy in a game-imported secondary slot.

    Handles three situations:

    * OptiScaler sits on ``dxgi.dll`` (Mode C deployed standalone) and DLSS 5
      now needs that slot -> move it to ``winmm/version/dinput8``;
    * OptiScaler sits on another secondary slot -> keep it, drop duplicates;
    * no OptiScaler proxy at all (older DLSS 5 build overwrote ``dxgi.dll``)
      -> re-deploy the core from the component cache.
    """
    td = Path(target_dir)
    if not td.is_dir():
        return None

    current = detect_optiscaler_slot(td)
    slot = pick_fg_proxy_slot(td, exe_path)
    if slot == "dxgi.dll":  # defensive: never hand dxgi.dll to OptiScaler here
        slot = "version.dll"

    if current == slot:
        # Drop duplicated OptiScaler copies from other slots.
        for other in OPTISCALER_SLOTS:
            if other != slot and classify_slot(td, other) == "optiscaler":
                _remove(td / other)
        return slot

    if current is not None:
        src = td / current
        dst = td / slot
        try:
            _remove(dst)
            shutil.move(str(src), str(dst))
        except Exception:
            try:
                shutil.copy2(str(src), str(dst))
                _remove(src)
            except Exception:
                return current
        for other in OPTISCALER_SLOTS:
            if other != slot and classify_slot(td, other) == "optiscaler":
                _remove(td / other)
        return slot

    # No proxy at all: restore it from the component cache.
    source = _find_optiscaler_source()
    if not source:
        return None
    try:
        shutil.copy2(source, str(td / slot))
        return slot
    except Exception:
        return None


def coexistence_snapshot(target_dir: os.PathLike | str) -> Dict[str, object]:
    """Compact description of the current injection layout (for UI/tests/logs)."""
    td = Path(target_dir)
    slots = scan_proxy_slots(td)
    return {
        "target_dir": str(td),
        "dxgi_host": slots.get("dxgi.dll", "missing"),
        "optiscaler_slot": detect_optiscaler_slot(td),
        "dashdogy_slot": detect_dashdogy_slot(td),
        "secondary_reshade": [n for n in SECONDARY_RESHADE_FILES if (td / n).exists()],
        "fakenvapi": [n for n in FAKENVAPI_FILES if (td / n).exists()],
        "slots": slots,
    }
