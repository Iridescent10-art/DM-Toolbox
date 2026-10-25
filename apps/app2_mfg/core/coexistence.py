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
from typing import Dict, List, Optional, Tuple, Any

# Proxy slots that may host a frame-generation core when dxgi.dll belongs to ReShade.
FG_PROXY_SLOTS: List[str] = ["version.dll", "winmm.dll", "dinput8.dll", "wininet.dll"]

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
    if is_dashdogy_binary(path):
        return False
    data = _read_signature_bytes(Path(path))
    return bool(data) and (b"OptiScaler" in data or b"libxess" in data)


def is_dashdogy_binary(path: os.PathLike | str) -> bool:
    """True for a dashdogy / MFG-Unlocker proxy binary."""
    data = _read_signature_bytes(Path(path))
    return bool(data) and (b"MFGUnlocker" in data or b"RTX40MFG" in data or b"RTXMFG" in data)


def is_dlssg_sm86_binary(path: os.PathLike | str) -> bool:
    """True for a dlssg_for_sm86 proxy binary."""
    data = _read_signature_bytes(Path(path))
    if not data:
        return False
    lower = data.lower()
    return (b"dlssg" in lower and b"sm86" in lower) or b"dlssg_sm86" in lower


def classify_slot(target_dir: os.PathLike | str, slot: str) -> str:
    """Classify one proxy slot: reshade / optiscaler / dashdogy / foreign / missing."""
    path = Path(target_dir) / slot
    if not path.is_file():
        return "missing"
    if is_reshade_binary(path):
        return "reshade"
    if is_dashdogy_binary(path):
        return "dashdogy"
    if is_optiscaler_binary(path):
        return "optiscaler"
    if is_dlssg_sm86_binary(path):
        return "dlssg_sm86"
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


def detect_dlssg_sm86_slot(target_dir: os.PathLike | str) -> Optional[str]:
    """Return the proxy slot currently hosting dlssg_for_sm86, if any."""
    for slot in OPTISCALER_SLOTS:
        if classify_slot(target_dir, slot) == "dlssg_sm86":
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


DLSS_RUNTIME_FILES: Tuple[str, ...] = ("nvngx_dlss.dll", "nvngx_dlssg.dll")

# Directories that must never be scanned for the game's own DLSS runtime: they
# hold the payload we ship, or backups of the game's files.
_DLSS_SCAN_SKIP_DIRS = {
    "optiscaler",
    "reshade",
    "renodx",
    "dm_backup",
    "dmbackup",
    "__pycache__",
    "backup",
}

# Bounded breadth-first walk; deep engine trees must not turn an injection into
# a multi-second disk crawl.
_DLSS_SCAN_MAX_DEPTH = 4
_DLSS_SCAN_MAX_DIRS = 4000


def find_dlss_runtime(target_dir: os.PathLike | str) -> Dict[str, str]:
    """
    Locate the game's own DLSS runtime DLLs and return root-relative paths.

    Looks at the game root first, then ``Streamline/``, then a bounded breadth-first
    walk of the engine tree, so a game that keeps ``nvngx_dlss.dll`` under
    ``Engine/Binaries/ThirdParty/...`` is still found. Every returned path is
    relative to the game root with backslashes, which is the format OptiScaler's
    ``[Libraries] NvngxDlssPath`` override expects.

    Only files that already belong to the game are reported; the OptiScaler /
    ReShade payload directories are skipped so we never point the game at our copy.
    """
    td = Path(target_dir)
    found: Dict[str, str] = {}
    if not td.is_dir():
        return found

    def _record(directory: Path) -> None:
        for name in DLSS_RUNTIME_FILES:
            if name in found:
                continue
            candidate = directory / name
            try:
                if candidate.is_file():
                    found[name] = str(candidate.relative_to(td)).replace("/", "\\")
            except Exception:
                continue

    _record(td)
    streamline = td / "Streamline"
    if streamline.is_dir():
        _record(streamline)
    if len(found) == len(DLSS_RUNTIME_FILES):
        return found

    visited = 0
    level: List[Tuple[Path, int]] = [(td, 0)]
    while level and visited < _DLSS_SCAN_MAX_DIRS and len(found) < len(DLSS_RUNTIME_FILES):
        nxt: List[Tuple[Path, int]] = []
        for directory, depth in level:
            visited += 1
            _record(directory)
            if depth >= _DLSS_SCAN_MAX_DEPTH:
                continue
            try:
                children = list(directory.iterdir())
            except Exception:
                continue
            for child in children:
                try:
                    if child.is_dir() and not child.is_symlink():
                        if child.name.lower() not in _DLSS_SCAN_SKIP_DIRS:
                            nxt.append((child, depth + 1))
                except Exception:
                    continue
            if visited >= _DLSS_SCAN_MAX_DIRS:
                break
        level = nxt
    return found


def expose_dlss_runtime(target_dir: os.PathLike | str) -> List[str]:
    """
    Mirror the game's DLSS runtime at the game root when it only lives in a subfolder.

    Some engines (and OptiScaler's own startup probe) resolve ``nvngx_dlss.dll``
    from the game root. Without the root copy, OptiScaler logs
    ``nvngx_dlss.dll not found, disabling DLSS``: the in-game DLSS super-resolution
    entry vanishes and neither the DLSS 5 hand-off nor the XeFG motion-vector input
    reaches the frame-generation chain.

    Returns the names of the files that were copied, so the coexistence marker can
    record them and uninstall removes only the copies this tool created.
    """
    td = Path(target_dir)
    copied: List[str] = []
    if not td.is_dir():
        return copied
    runtime = find_dlss_runtime(td)
    for name in DLSS_RUNTIME_FILES:
        rel = runtime.get(name)
        if not rel:
            continue
        source = td / rel
        destination = td / name
        if destination.exists() or not source.is_file():
            continue
        try:
            shutil.copy2(source, destination)
            copied.append(name)
        except Exception:
            continue
    return copied


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
        if slot in imported and classify_slot(td, slot) in ("missing", "optiscaler", "dashdogy", "dlssg_sm86"):
            return slot
    # No import-table hit (packed launcher / dynamic load): version.dll is the
    # safest default, every D3D12 title imports the version API.
    for slot in ("version.dll", "winmm.dll", "dinput8.dll", "wininet.dll"):
        if classify_slot(td, slot) in ("missing", "optiscaler", "dashdogy", "dlssg_sm86"):
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


def _find_dashdogy_source() -> Optional[str]:
    """Locate a cached MFGUnlocker.dll (v1.7.0 or v1.6.1) to deploy Mode A proxy."""
    try:
        from core.updater import ComponentUpdater
        from core.models import BackendType
        cached = ComponentUpdater().get_latest_cached_file(BackendType.STANDALONE)
        if cached and Path(cached).is_file():
            return str(cached)
    except Exception:
        pass
    root = Path(__file__).resolve().parent.parent.parent.parent
    for cand in [
        root / "apps" / "app2_mfg" / "embedded_components" / "dashdogy" / "v1.7.0" / "MFGUnlocker.dll",
        root / "apps" / "app2_mfg" / "embedded_components" / "dashdogy" / "v1.6.1" / "MFGUnlocker.dll",
    ]:
        if cand.is_file():
            return str(cand)
    return None


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
        "dlssg_sm86_slot": detect_dlssg_sm86_slot(td),
        "secondary_reshade": [n for n in SECONDARY_RESHADE_FILES if (td / n).exists()],
        "fakenvapi": [n for n in FAKENVAPI_FILES if (td / n).exists()],
        "slots": slots,
    }


def ensure_dashdogy_proxy(
    target_dir: os.PathLike | str,
    exe_path: Optional[os.PathLike | str] = None,
) -> Optional[str]:
    """Ensure dashdogy proxy is deployed in a secondary proxy slot (version.dll)."""
    td = Path(target_dir)
    current = detect_dashdogy_slot(td)
    slot = pick_fg_proxy_slot(td, exe_path)
    if slot == "dxgi.dll":
        slot = "version.dll"

    if current == slot:
        for other in OPTISCALER_SLOTS:
            if other != slot and classify_slot(td, other) == "dashdogy":
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
            if other != slot and classify_slot(td, other) == "dashdogy":
                _remove(td / other)
        return slot

    source = _find_dashdogy_source()
    if source and Path(source).is_file():
        dst = td / slot
        try:
            _remove(dst)
            shutil.copy2(source, str(dst))
            return slot
        except Exception:
            pass
    return None


def adapt_mode_b_for_dlss5(
    target_dir: os.PathLike | str,
    exe_path: Optional[os.PathLike | str] = None,
) -> Tuple[bool, str]:
    """
    Called when DLSS 5 is injected into a directory where Mode B (OptiScaler) is already present.
    1. Moves OptiScaler proxy from dxgi.dll to a secondary slot (version.dll).
    2. Updates OptiScaler.ini for DLSS 5 coexistence:
       - Dx12Upscaler = dlss (passthrough for DLSS 5 neural reconstruction)
       - LoadReshade = false (prevents second ReShade instance crashing)
       - LoadAsiPlugins = true
       - FGInput = dlssg, FGOutput = xefg
       - PreserveSwapChain = true
       - IgnoreInitChecks = true, DepthInverted = true
    3. Purges fakenvapi.dll (which causes GPU query failure in DLSS 5) and secondary ReShade binaries.
    4. Records coexistence marker in target_dir / ".mfg_coex_backup.json".
    """
    td = Path(target_dir)
    if not td.is_dir():
        return False, f"目标目录不存在: {target_dir}"

    slot = ensure_optiscaler_proxy(td, exe_path)
    if not slot:
        return False, "未能为 OptiScaler 迁移至次级代理槽位"

    purge_fakenvapi(td)
    purge_secondary_reshade(td)

    # Forward sync OptiScaler.ini into coexistence mode (Direct reliable configparser update + optional ini_sync)
    opti_ini = td / "OptiScaler.ini"
    if opti_ini.exists():
        try:
            import configparser
            cp = configparser.ConfigParser(interpolation=None, strict=False)
            cp.read(opti_ini, encoding="utf-8")
            if not cp.has_section("Upscalers"):
                cp.add_section("Upscalers")
            cp.set("Upscalers", "Dx12Upscaler", "dlss")
            if not cp.has_section("Plugins"):
                cp.add_section("Plugins")
            cp.set("Plugins", "LoadReshade", "false")
            if not cp.has_section("FrameGen"):
                cp.add_section("FrameGen")
            cp.set("FrameGen", "PreserveSwapChain", "true")
            with open(opti_ini, "w", encoding="utf-8") as f:
                cp.write(f)
        except Exception:
            pass
        try:
            from apps.app2_mfg.core.ini_sync import IniConfigManager
            from apps.app2_mfg.core.optiscaler_config import load_optiscaler_preset
            preset = IniConfigManager.read_mode_c_reverse(td) or load_optiscaler_preset()
            preset["dx12_upscaler"] = "dlss"
            if isinstance(preset, dict):
                preset["plugins"] = preset.get("plugins", {})
                if isinstance(preset["plugins"], dict):
                    preset["plugins"]["LoadReshade"] = "false"
            IniConfigManager.sync_mode_b_forward(
                td,
                preset,
                exe_name=Path(exe_path).name if exe_path else None,
                # ReShade / addon / nvngx_dlssnr.dll are copied only after this
                # adaptation runs, so is_dlss5_present() is still false here. Tell
                # the writer explicitly that this is a coexistence layout, otherwise
                # it writes the standalone policy (LoadReshade=auto, ...).
                force_dlss5_coexistence=True,
            )
        except Exception:
            pass

    exposed_files = expose_dlss_runtime(td)

    coex_marker = td / ".mfg_coex_backup.json"
    marker_data = {
        "backend": "B",
        "original_proxy": "dxgi.dll",
        "current_proxy": slot,
        "adapted_for_dlss5": True,
        "exposed_root_files": exposed_files,
    }
    try:
        import json
        with open(coex_marker, "w", encoding="utf-8") as f:
            json.dump(marker_data, f, indent=2)
    except Exception:
        pass

    return True, f"模式 B 已自动回退适配为与 DLSS 5 双轨共存模式（OptiScaler 迁移至 {slot}，超分直通 DLSS，防冲突机制已生效）"


def restore_mode_b_from_dlss5(
    target_dir: os.PathLike | str,
    exe_path: Optional[os.PathLike | str] = None,
) -> Tuple[bool, str]:
    """
    Called when DLSS 5 is removed/uninstalled from a game that had Mode B.
    1. Removes the DLSS 5 ReShade dxgi.dll.
    2. Moves the OptiScaler proxy from version.dll (or secondary slot) back to dxgi.dll.
    3. Restores OptiScaler.ini to standalone mode (Dx12Upscaler = auto, LoadReshade = auto).
    4. Removes .mfg_coex_backup.json.
    """
    td = Path(target_dir)
    if not td.is_dir():
        return False, f"目标目录不存在: {target_dir}"

    current_slot = detect_optiscaler_slot(td)
    dxgi_dest = td / "dxgi.dll"

    # Remove DLSS 5 dxgi.dll if it's ReShade
    if dxgi_dest.exists() and is_reshade_binary(dxgi_dest):
        _remove(dxgi_dest)

    # Move OptiScaler back to dxgi.dll
    if current_slot and current_slot != "dxgi.dll":
        src_proxy = td / current_slot
        if src_proxy.exists():
            try:
                _remove(dxgi_dest)
                shutil.move(str(src_proxy), str(dxgi_dest))
            except Exception:
                try:
                    shutil.copy2(str(src_proxy), str(dxgi_dest))
                    _remove(src_proxy)
                except Exception:
                    pass
    elif not dxgi_dest.exists():
        source = _find_dashdogy_source()
        if source and Path(source).is_file():
            shutil.copy2(source, str(dxgi_dest))
    elif not dxgi_dest.exists():
        source = _find_optiscaler_source()
        if source:
            shutil.copy2(source, str(dxgi_dest))

    # Clean up any leftover secondary OptiScaler copies
    for other in FG_PROXY_SLOTS:
        other_p = td / other
        if other_p.exists() and is_optiscaler_binary(other_p):
            _remove(other_p)

    # Restore OptiScaler.ini to standalone mode
    opti_ini = td / "OptiScaler.ini"
    if opti_ini.exists():
        try:
            import configparser
            cp = configparser.ConfigParser(interpolation=None, strict=False)
            cp.read(opti_ini, encoding="utf-8")
            if not cp.has_section("Upscalers"):
                cp.add_section("Upscalers")
            cp.set("Upscalers", "Dx12Upscaler", "auto")
            if cp.has_section("Plugins"):
                cp.set("Plugins", "LoadReshade", "auto")
            with open(opti_ini, "w", encoding="utf-8") as f:
                cp.write(f)
        except Exception:
            pass
        try:
            from apps.app2_mfg.core.ini_sync import IniConfigManager
            IniConfigManager.write_ini_sections(opti_ini, {
                "Upscalers": {"Dx12Upscaler": "auto"},
                "Plugins": {"LoadReshade": "auto"}
            })
        except Exception:
            pass

    # Remove the runtime copies this tool exposed at the game root (they only ever
    # exist because of coexistence; the game's originals stay where they were).
    marker_path = td / ".mfg_coex_backup.json"
    if marker_path.exists():
        try:
            import json
            with open(marker_path, "r", encoding="utf-8") as f:
                marker = json.load(f)
            for name in marker.get("exposed_root_files") or []:
                exposed = td / str(name)
                if exposed.is_file() and exposed.name in DLSS_RUNTIME_FILES:
                    _remove(exposed)
        except Exception:
            pass

    # Remove coex marker
    marker_path.unlink(missing_ok=True)

    return True, "已自动将多帧生成模式 B 恢复至独立运行状态（OptiScaler 重新挂载至 dxgi.dll，超分与渲染钩子已重置为独立运行）"


def adapt_mode_a_for_dlss5(
    target_dir: os.PathLike | str,
    exe_path: Optional[os.PathLike | str] = None,
) -> Tuple[bool, str]:
    """Adapt Mode A (dashdogy) for DLSS 5 coexistence by moving it to secondary slot."""
    td = Path(target_dir)
    slot = ensure_dashdogy_proxy(td, exe_path)
    if not slot:
        return False, "未能为 MFG-Unlocker 迁移至次级代理槽位"

    coex_marker = td / ".mfg_coex_backup.json"
    marker_data = {
        "backend": "A",
        "original_proxy": "dxgi.dll",
        "current_proxy": slot,
        "adapted_for_dlss5": True
    }
    try:
        import json
        with open(coex_marker, "w", encoding="utf-8") as f:
            json.dump(marker_data, f, indent=2)
    except Exception:
        pass
    return True, f"模式 A 已自动回退适配为与 DLSS 5 双轨共存模式（MFG-Unlocker 迁移至 {slot}）"


def restore_mode_a_from_dlss5(
    target_dir: os.PathLike | str,
    exe_path: Optional[os.PathLike | str] = None,
) -> Tuple[bool, str]:
    """Restore Mode A from DLSS 5 coexistence back to standalone dxgi.dll."""
    td = Path(target_dir)
    current_slot = detect_dashdogy_slot(td)
    dxgi_dest = td / "dxgi.dll"

    if dxgi_dest.exists() and is_reshade_binary(dxgi_dest):
        _remove(dxgi_dest)

    if current_slot and current_slot != "dxgi.dll":
        src_proxy = td / current_slot
        if src_proxy.exists():
            try:
                _remove(dxgi_dest)
                shutil.move(str(src_proxy), str(dxgi_dest))
            except Exception:
                try:
                    shutil.copy2(str(src_proxy), str(dxgi_dest))
                    _remove(src_proxy)
                except Exception:
                    pass
    elif not dxgi_dest.exists():
        source = _find_dashdogy_source()
        if source and Path(source).is_file():
            shutil.copy2(source, str(dxgi_dest))

    for other in FG_PROXY_SLOTS:
        other_p = td / other
        if other_p.exists() and is_dashdogy_binary(other_p):
            _remove(other_p)

    (td / ".mfg_coex_backup.json").unlink(missing_ok=True)
    return True, "已自动将多帧生成模式 A 恢复至独立运行状态（MFG-Unlocker 重新挂载至 dxgi.dll）"


def adapt_mode_c_for_dlss5(target_dir: os.PathLike | str) -> Tuple[bool, str]:
    """Adapt Mode C (dlssg_for_sm86) for DLSS 5 coexistence by turning off internal SR."""
    td = Path(target_dir)
    ini_path = td / "dlssg_sm86.ini"
    if ini_path.exists():
        try:
            from apps.app2_mfg.core.ini_sync import IniConfigManager
            from apps.app2_mfg.core.optiscaler_config import load_dlssg_sm86_preset
            sm86_p = IniConfigManager.read_dlssg_sm86_reverse(td) or load_dlssg_sm86_preset()
            sm86_p["super_resolution_mode"] = "Off"
            IniConfigManager.sync_dlssg_sm86_forward(td, sm86_p)
        except Exception:
            pass

    coex_marker = td / ".mfg_coex_backup.json"
    marker_data = {
        "backend": "C",
        "original_proxy": "version.dll",
        "current_proxy": "version.dll",
        "adapted_for_dlss5": True
    }
    try:
        import json
        with open(coex_marker, "w", encoding="utf-8") as f:
            json.dump(marker_data, f, indent=2)
    except Exception:
        pass
    return True, "模式 C 已自动适配为与 DLSS 5 共存模式（超分辨率托管已关闭，让位给 DLSS 5 神经重构）"


def restore_mode_c_from_dlss5(target_dir: os.PathLike | str) -> Tuple[bool, str]:
    """Restore Mode C from DLSS 5 coexistence by restoring internal SR to Auto."""
    td = Path(target_dir)
    dxgi_dest = td / "dxgi.dll"
    if dxgi_dest.exists() and is_reshade_binary(dxgi_dest):
        _remove(dxgi_dest)

    ini_path = td / "dlssg_sm86.ini"
    if ini_path.exists():
        try:
            from apps.app2_mfg.core.ini_sync import IniConfigManager
            from apps.app2_mfg.core.optiscaler_config import load_dlssg_sm86_preset
            sm86_p = IniConfigManager.read_dlssg_sm86_reverse(td) or load_dlssg_sm86_preset()
            sm86_p["super_resolution_mode"] = "Auto"
            IniConfigManager.sync_dlssg_sm86_forward(td, sm86_p)
        except Exception:
            pass

    (td / ".mfg_coex_backup.json").unlink(missing_ok=True)
    return True, "已自动将多帧生成模式 C 恢复至独立运行状态（超分辨率托管恢复为 Auto）"


def restore_mfg_after_dlss5_removal(
    target_dir: os.PathLike | str,
    exe_path: Optional[os.PathLike | str] = None,
) -> Tuple[bool, str]:
    """Unified handler: detects active MFG mode and restores it to standalone."""
    td = Path(target_dir)
    coex_marker = td / ".mfg_coex_backup.json"
    backend = None
    if coex_marker.exists():
        try:
            import json
            with open(coex_marker, "r", encoding="utf-8") as f:
                data = json.load(f)
                backend = data.get("backend")
        except Exception:
            pass

    if backend == "A" or (td / "RTXMFG-Universal.json").exists() or (td / "RTXMFG-UI.ini").exists():
        return restore_mode_a_from_dlss5(td, exe_path)
    elif backend == "B" or (td / "OptiScaler.ini").exists() or (td / "OptiScaler.dll").exists():
        return restore_mode_b_from_dlss5(td, exe_path)
    elif backend == "C" or (td / "dlssg_sm86.ini").exists() or (td / "dlssg_sm86").exists():
        return restore_mode_c_from_dlss5(td)

    return False, "未检测到多帧生成组件"

