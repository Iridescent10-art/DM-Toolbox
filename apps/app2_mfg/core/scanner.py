"""
Universal MFG Patcher - Game Library Discovery and Deep Binary Sniffer.
"""

import os
import re
import json
import winreg
from pathlib import Path
from typing import List, Dict, Optional, Set
from core.models import GameInfo, QualificationStatus
from core.utils import get_pe_file_version, is_process_running

IGNORE_EXE_PATTERNS = {
    "crashreportclient.exe", "unrealcefsubprocess.exe", "launcher.exe",
    "easyanticheat.exe", "unitycrashhandler64.exe", "unitycrashhandler32.exe",
    "dxsetup.exe", "vcredist_x64.exe", "vcredist_x86.exe", "cleanup.exe",
    "touchup.exe", "uninstall.exe", "uninstaller.exe", "unins000.exe",
    "updater.exe", "unicrashreporter.exe", "gamelaunchhelper.exe",
    "ccvideoplayerapp64.exe", "mliveccplayerapp64.exe", "patcher.exe"
}

KNOWN_GAME_NAMES = {
    "yysls": "燕云十六声 (Where Winds Meet)",
    "b1": "黑神话：悟空 (Black Myth: Wukong)",
    "naraka": "永劫无间 (Naraka: Bladepoint)",
    "genshin": "原神 (Genshin Impact)",
    "zenless": "绝区零 (Zenless Zone Zero)",
    "wutheringwaves": "鸣潮 (Wuthering Waves)"
}

class GameScanner:
    def __init__(self):
        pass

    def scan_all_libraries(self) -> List[GameInfo]:
        """Scan all supported digital storefronts and common game drives/directories."""
        games: List[GameInfo] = []
        seen_dirs: Set[str] = set()

        # 1. Steam
        for g in self.scan_steam():
            normalized = os.path.normpath(g.install_dir).lower()
            if normalized not in seen_dirs:
                seen_dirs.add(normalized)
                games.append(g)

        # 2. Epic Games
        for g in self.scan_epic():
            normalized = os.path.normpath(g.install_dir).lower()
            if normalized not in seen_dirs:
                seen_dirs.add(normalized)
                games.append(g)

        # 3. GOG
        for g in self.scan_gog():
            normalized = os.path.normpath(g.install_dir).lower()
            if normalized not in seen_dirs:
                seen_dirs.add(normalized)
                games.append(g)

        # 4. WeGame & Common Domestic Game Drives (e.g. D:\game, E:\game, etc.)
        for g in self.scan_domestic_and_drives():
            normalized = os.path.normpath(g.install_dir).lower()
            if normalized not in seen_dirs:
                seen_dirs.add(normalized)
                games.append(g)

        return games

    def scan_steam(self) -> List[GameInfo]:
        """Discover Steam libraries and parse installed app manifests."""
        steam_path = self._get_steam_path()
        if not steam_path or not os.path.exists(steam_path):
            return []

        library_dirs = [steam_path]
        vdf_path = os.path.join(steam_path, "steamapps", "libraryfolders.vdf")
        if os.path.exists(vdf_path):
            library_dirs.extend(self._parse_libraryfolders_vdf(vdf_path))

        discovered = []
        for lib in set(library_dirs):
            steamapps = os.path.join(lib, "steamapps")
            if not os.path.exists(steamapps):
                continue
            for item in os.listdir(steamapps):
                if item.startswith("appmanifest_") and item.endswith(".acf"):
                    acf_path = os.path.join(steamapps, item)
                    info = self._parse_acf(acf_path, lib)
                    if info:
                        game_obj = self.analyze_game_directory(info["name"], "Steam", info["path"])
                        if game_obj:
                            discovered.append(game_obj)
        return discovered

    def _get_steam_path(self) -> Optional[str]:
        keys = [
            (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam")
        ]
        for root, subkey in keys:
            try:
                with winreg.OpenKey(root, subkey) as k:
                    val, _ = winreg.QueryValueEx(k, "SteamPath")
                    if val and os.path.exists(val):
                        return val
            except Exception:
                continue
        return None

    def _parse_libraryfolders_vdf(self, vdf_path: str) -> List[str]:
        libs = []
        try:
            with open(vdf_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            # Match "path" "\s*"(.*?)"
            matches = re.findall(r'"path"\s+"([^"]+)"', content)
            for m in matches:
                clean = m.replace(r"\\", "\\")
                if os.path.exists(clean):
                    libs.append(clean)
        except Exception:
            pass
        return libs

    def _parse_acf(self, acf_path: str, lib_base: str) -> Optional[Dict[str, str]]:
        try:
            with open(acf_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            name_m = re.search(r'"name"\s+"([^"]+)"', content)
            dir_m = re.search(r'"installdir"\s+"([^"]+)"', content)
            if name_m and dir_m:
                name = name_m.group(1)
                installdir = dir_m.group(1)
                full_path = os.path.join(lib_base, "steamapps", "common", installdir)
                if os.path.exists(full_path):
                    return {"name": name, "path": full_path}
        except Exception:
            pass
        return None

    def scan_epic(self) -> List[GameInfo]:
        """Scan Epic Games manifests in ProgramData."""
        discovered = []
        prog_data = os.environ.get("ProgramData", r"C:\ProgramData")
        manifests_dir = os.path.join(prog_data, "Epic", "EpicGamesLauncher", "Data", "Manifests")
        if not os.path.exists(manifests_dir):
            return []

        for item in os.listdir(manifests_dir):
            if item.endswith(".item"):
                item_path = os.path.join(manifests_dir, item)
                try:
                    with open(item_path, "r", encoding="utf-8", errors="ignore") as f:
                        data = json.load(f)
                    display_name = data.get("DisplayName")
                    install_loc = data.get("InstallLocation")
                    if display_name and install_loc and os.path.exists(install_loc):
                        g = self.analyze_game_directory(display_name, "Epic", install_loc)
                        if g:
                            discovered.append(g)
                except Exception:
                    continue
        return discovered

    def scan_gog(self) -> List[GameInfo]:
        """Scan GOG registry entries."""
        discovered = []
        keys = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\GOG.com\Games"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\GOG.com\Games")
        ]
        for root, subkey in keys:
            try:
                with winreg.OpenKey(root, subkey) as k:
                    sub_count, _, _ = winreg.QueryInfoKey(k)
                    for i in range(sub_count):
                        try:
                            game_id = winreg.EnumKey(k, i)
                            with winreg.OpenKey(k, game_id) as gk:
                                name, _ = winreg.QueryValueEx(gk, "gameName")
                                path_val, _ = winreg.QueryValueEx(gk, "path")
                                if name and path_val and os.path.exists(path_val):
                                    g = self.analyze_game_directory(name, "GOG", path_val)
                                    if g:
                                        discovered.append(g)
                        except Exception:
                            continue
            except Exception:
                continue
        return discovered

    def scan_domestic_and_drives(self) -> List[GameInfo]:
        r"""Scan common domestic game drives (D:\game, E:\game, etc.) and WeGame."""
        discovered: List[GameInfo] = []
        search_roots = [
            r"D:\game", r"D:\Games", r"E:\game", r"E:\Games",
            os.path.expandvars(r"%ProgramFiles(x86)%\Tencent\WeGameApps")
        ]

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Tencent\WeGame") as k:
                val, _ = winreg.QueryValueEx(k, "InstallPath")
                if val:
                    search_roots.append(os.path.join(val, "WeGameApps"))
        except Exception:
            pass

        seen_paths = set()
        for root_dir in search_roots:
            if not os.path.exists(root_dir):
                continue
            try:
                for item in os.listdir(root_dir):
                    sub_path = os.path.join(root_dir, item)
                    if not os.path.isdir(sub_path):
                        continue
                    if item.lower() in ["steam", "mods", "dlss5", "downloading"]:
                        continue

                    if item.lower() in ["wegame", "wegameapps", "common_apps"]:
                        try:
                            for w_item in os.listdir(sub_path):
                                w_sub = os.path.join(sub_path, w_item)
                                if os.path.isdir(w_sub) and w_sub.lower() not in seen_paths:
                                    seen_paths.add(w_sub.lower())
                                    g = self.analyze_game_directory(w_item, "WeGame", w_sub)
                                    if g:
                                        discovered.append(g)
                        except Exception:
                            pass
                        continue

                    if sub_path.lower() in seen_paths:
                        continue
                    seen_paths.add(sub_path.lower())

                    display_name = KNOWN_GAME_NAMES.get(item.lower(), item)
                    g = self.analyze_game_directory(display_name, "国产/独立", sub_path)
                    if g:
                        discovered.append(g)
            except Exception:
                continue

        return discovered

    def analyze_game_directory(self, game_name: str, source: str, install_dir: str) -> Optional[GameInfo]:
        """
        Deep binary discovery inside game directory:
        1. Locate Streamline interposer (sl.interposer.dll) and nvngx_dlssg.dll
        2. Identify the real main shipping binary rather than the launcher
        3. Check PE versions and existing patch/ReShade status
        """
        if not os.path.exists(install_dir):
            return None

        interposer_path = None
        dlssg_path = None
        target_dir = install_dir

        # Shallow and deep walk up to 6 levels (UE games can have deep Binaries/Win64r/Streamline)
        for root, dirs, files in os.walk(install_dir):
            try:
                rel_depth = len(Path(root).relative_to(install_dir).parts)
            except Exception:
                rel_depth = 0
            if rel_depth > 6:
                continue
            lower_files = {f.lower(): f for f in files}
            if "sl.interposer.dll" in lower_files:
                interposer_path = os.path.join(root, lower_files["sl.interposer.dll"])
                if os.path.basename(root).lower() == "streamline":
                    target_dir = os.path.dirname(root)
                else:
                    target_dir = root

                if "nvngx_dlssg.dll" in lower_files:
                    dlssg_path = os.path.join(root, lower_files["nvngx_dlssg.dll"])
                else:
                    for check_d in [target_dir, os.path.join(target_dir, "Streamline")]:
                        if os.path.exists(os.path.join(check_d, "nvngx_dlssg.dll")):
                            dlssg_path = os.path.join(check_d, "nvngx_dlssg.dll")
                            break
                break

        if not dlssg_path:
            for root, _, files in os.walk(install_dir):
                lower_files = {f.lower(): f for f in files}
                if "nvngx_dlssg.dll" in lower_files:
                    dlssg_path = os.path.join(root, lower_files["nvngx_dlssg.dll"])
                    if not interposer_path:
                        if os.path.basename(root).lower() == "streamline":
                            target_dir = os.path.dirname(root)
                        else:
                            target_dir = root
                    break

        exe_path = self._find_primary_executable(target_dir, install_dir)
        if not exe_path:
            return None

        exe_name = os.path.basename(exe_path)
        stem = Path(exe_path).stem.lower()
        if (game_name.lower() in ["win64", "win64r", "binaries", "shipping", "x64", "game"] or not game_name) and stem in KNOWN_GAME_NAMES:
            game_name = KNOWN_GAME_NAMES[stem]
        elif stem in KNOWN_GAME_NAMES and (game_name == stem or game_name.lower() in ["win64", "win64r"]):
            game_name = KNOWN_GAME_NAMES[stem]
        else:
            for part in Path(install_dir).parts:
                if part.lower() in KNOWN_GAME_NAMES:
                    game_name = KNOWN_GAME_NAMES[part.lower()]
                    break

        streamline_ver = get_pe_file_version(interposer_path) if interposer_path else None
        dlssg_ver = get_pe_file_version(dlssg_path) if dlssg_path else None

        if interposer_path and dlssg_path:
            qualification = QualificationStatus.QUALIFIED
        elif interposer_path:
            qualification = QualificationStatus.MISSING_DLSSG
        else:
            qualification = QualificationStatus.NOT_SUPPORTED

        # Check existing ReShade
        has_reshade = False
        target_files_lower = [f.lower() for f in os.listdir(target_dir)] if os.path.exists(target_dir) else []
        if "reshade64.dll" in target_files_lower:
            has_reshade = True
        elif "dxgi.dll" in target_files_lower:
            # Check if dxgi is ReShade. ReShade 6.8 keeps its signature around ~4.3 MB,
            # so read the whole file instead of only the first 1 MB.
            dxgi_file = os.path.join(target_dir, "dxgi.dll")
            try:
                with open(dxgi_file, "rb") as f:
                    content = f.read(16 * 1024 * 1024)
                if b"crosire" in content.lower() or b"reshade" in content.lower():
                    has_reshade = True
            except Exception:
                pass

        # Check patch manifest
        manifest_path = os.path.join(target_dir, ".mfg_patch_manifest.json")
        is_patched = False
        patched_backend = None
        installed_version = None
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    mdata = json.load(f)
                    is_patched = True
                    patched_backend = mdata.get("active_backend")
                    installed_version = mdata.get("installed_version")
            except Exception:
                is_patched = True

        running = is_process_running(exe_name)

        return GameInfo(
            name=game_name,
            source=source,
            install_dir=install_dir,
            target_dir=target_dir,
            exe_path=exe_path,
            exe_name=exe_name,
            qualification=qualification,
            streamline_ver=streamline_ver,
            dlssg_ver=dlssg_ver,
            has_reshade=has_reshade,
            is_patched=is_patched,
            patched_backend=patched_backend,
            installed_version=installed_version,
            is_running=running
        )

    def _find_primary_executable(self, target_dir: str, install_dir: str) -> Optional[str]:
        """Find the real executable, filtering out known launchers and sub-processes."""
        candidates = []
        # First scan target_dir
        if os.path.exists(target_dir):
            for item in os.listdir(target_dir):
                if item.lower().endswith(".exe") and item.lower() not in IGNORE_EXE_PATTERNS:
                    candidates.append(os.path.join(target_dir, item))

        # If no executable found in target_dir, check install_dir
        if not candidates and target_dir != install_dir and os.path.exists(install_dir):
            for item in os.listdir(install_dir):
                if item.lower().endswith(".exe") and item.lower() not in IGNORE_EXE_PATTERNS:
                    candidates.append(os.path.join(install_dir, item))

        if not candidates:
            return None

        # Prioritize *Shipping.exe, Win64, or matching game folder names
        for c in candidates:
            lower = os.path.basename(c).lower()
            if "shipping.exe" in lower or "win64" in lower or "yysls.exe" in lower:
                return c

        for c in candidates:
            lower = os.path.basename(c).lower()
            if "launch" not in lower and "setup" not in lower and "unist" not in lower:
                return c

        return candidates[0]
