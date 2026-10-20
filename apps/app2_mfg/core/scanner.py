"""
Universal MFG Patcher - Game Library Discovery and Deep Binary Sniffer.
Supports dynamic multi-drive detection, 3-level deep folder discovery,
multi-platform registries (Steam, Epic, GOG, Ubisoft, EA, NetEase, WeGame),
and Windows standard Uninstall registry discovery with intelligent pruning.
"""

import os
import re
import json
import winreg
import ctypes
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
from core.models import GameInfo, QualificationStatus
from core.utils import get_pe_file_version, is_process_running

IGNORE_EXE_PATTERNS = {
    "crashreportclient.exe", "unrealcefsubprocess.exe", "launcher.exe",
    "easyanticheat.exe", "easyanticheat_eos.exe", "unitycrashhandler64.exe",
    "unitycrashhandler32.exe", "dxsetup.exe", "vcredist_x64.exe", "vcredist_x86.exe",
    "cleanup.exe", "touchup.exe", "uninstall.exe", "uninstaller.exe", "unins000.exe",
    "unins001.exe", "updater.exe", "unicrashreporter.exe", "gamelaunchhelper.exe",
    "ccvideoplayerapp64.exe", "mliveccplayerapp64.exe", "patcher.exe", "update.exe",
    "devcon.exe", "ffmpeg.exe", "ffprobe.exe", "7z.exe", "7zg.exe", "winrar.exe", "cmd.exe",
    "powershell.exe", "conhost.exe", "wechat.exe", "weixin.exe", "qq.exe",
    "cloudmusic.exe", "kugou.exe", "baidunetdisk.exe", "thunder.exe", "chrome.exe",
    "msedge.exe", "firefox.exe", "steam.exe", "epicgameslauncher.exe", "wegame.exe",
    "battleye.exe", "beservice.exe", "gameoverlayui.exe", "repairapp.exe",
    "rtinstaller64.exe", "cefviewwing.exe", "platformprocess.exe", "ace-service64.exe",
    "ace-setup64.exe", "crossproxy.exe", "exceptionreport.exe", "crossproxy.exe",
    "assistant.exe", "bugreport.exe", "client.exe", "fping.exe", "startup_runner.exe",
    "tinydl.exe", "ace-helper.exe", "leagueclient.exe", "leagueclientux.exe",
    "leagueclientuxrender.exe", "leaguecrashhandler64.exe", "riotclientcrashhandler.exe",
    "riotclientservices.exe", "tfttencentclient.exe"
}

PRUNE_EXACT_NAMES = {
    "windows", "system32", "syswow64", "$recycle.bin", "system volume information",
    "appdata", "programdata", "microsoft", "temp", "tmp", "cache", "node_modules",
    ".git", ".svn", "venv", ".venv", "env", "packages", "drivers", "nvidia",
    "intel", "amd", "recovery", "msocache", "config.msi", "$windows.~bt", "$windows.~ws",
    "mod", "mods", "dlss5", "downloading", "workshop", "patch", "patches", "backup",
    "backups", "saves", "saved", "savegames", "tools", "tool", "logs", "log", "apk"
}

PRUNE_SUBSTRING_KEYWORDS = {
    "存档", "备份", "$recycle", "system volume", "shadercache"
}

PRUNE_ASSET_DIRS = {
    "content", "paks", "movies", "sound", "audio", "music", "textures",
    "shadercache", "shaders", "localization", "saved", "intermediate", "docs"
}

GAME_ROOT_KEYWORDS = (
    "game", "games", "steam", "steamlibrary", "epic", "epic games", "xbox",
    "wegame", "wegameapps", "riot games", "ubisoft", "ea games", "origin games",
    "battlenet", "battle.net", "gog games", "gog galaxy", "3dm", "ali213",
    "游侠", "单机", "网络游戏", "游戏", "娱乐", "download", "downloads", "xunlei"
)

GAME_PUBLISHERS = {
    "steam", "valve", "epic games", "ubisoft", "electronic arts", "ea games", "ea sports",
    "rockstar games", "cd projekt red", "atlus", "kunos simulazioni", "playground games",
    "asobo studio", "firaxis games", "codemasters", "netease", "mihoyo", "cognosphere",
    "kurogame", "tencent", "square enix", "capcom", "bandai namco", "sega", "bethesda",
    "blizzard entertainment", "cloud imperium games", "game science", "2k games", "paradox",
    "rebellion", "focus entertainment", "deep silver", "thq nordic", "warner bros",
    "sony interactive entertainment", "xbox game studios", "hypergryph"
}

NON_GAME_APP_KEYWORDS = {
    "launcher", "service", "driver", "redistributable", "sdk", "connect", "manager",
    "remote", "translator", "suite", "assistant", "hwinfo", "vortex", "tool", "toolkit",
    "client", "livehime", "gameviewer", "pit house", "androws", "expert"
}

KNOWN_GAME_NAMES = {
    "yysls": "燕云十六声 (Where Winds Meet)",
    "wwm": "燕云十六声 (Where Winds Meet)",
    "b1": "黑神话：悟空 (Black Myth: Wukong)",
    "naraka": "永劫无间 (Naraka: Bladepoint)",
    "genshin": "原神 (Genshin Impact)",
    "zenless": "绝区零 (Zenless Zone Zero)",
    "wutheringwaves": "鸣潮 (Wuthering Waves)",
    "endfield": "明日方舟：终末地 (Arknights Endfield)",
    "starcitizen": "星际公民 (Star Citizen)"
}

STANDARD_EXE_SUBDIRS = [
    "", "Binaries/Win64", "Binaries/Win64r", "Bin64", "bin/x64", "bin", "x64",
    "Game", "game/bin", "ph/work/bin/x64", "Game/Binaries/Win64"
]

def get_local_drives() -> List[str]:
    """Return local fixed and removable drives only (excluding remote network shares and CD-ROMs)."""
    drives = []
    try:
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for i in range(26):
            if bitmask & (1 << i):
                drive_letter = f"{chr(65 + i)}:\\"
                dtype = ctypes.windll.kernel32.GetDriveTypeW(drive_letter)
                # 2: DRIVE_REMOVABLE, 3: DRIVE_FIXED
                if dtype in (2, 3):
                    drives.append(drive_letter)
    except Exception:
        for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            root = f"{letter}:\\"
            if os.path.exists(root):
                drives.append(root)
    return drives

def is_dir_pruned(dirname: str) -> bool:
    lower = dirname.lower().strip()
    if lower.startswith((".", "$")):
        return True
    if lower in PRUNE_EXACT_NAMES:
        return True
    return any(kw in lower for kw in PRUNE_SUBSTRING_KEYWORDS)


class GameScanner:
    def __init__(self):
        self.seen_dirs: Set[str] = set()

    def _normalize(self, path: str) -> str:
        return os.path.normpath(path).lower()

    def scan_all_libraries(self) -> List[GameInfo]:
        """Scan all supported digital storefronts, platform registries, and 3-level deep game drives."""
        games: List[GameInfo] = []
        self.seen_dirs.clear()

        # 1. Steam (Cross-drive libraries via libraryfolders.vdf)
        for g in self.scan_steam():
            k = self._normalize(g.install_dir)
            if k not in self.seen_dirs:
                self.seen_dirs.add(k)
                games.append(g)

        # 2. Epic Games (Manifests in ProgramData)
        for g in self.scan_epic():
            k = self._normalize(g.install_dir)
            if k not in self.seen_dirs:
                self.seen_dirs.add(k)
                games.append(g)

        # 3. GOG Galaxy
        for g in self.scan_gog():
            k = self._normalize(g.install_dir)
            if k not in self.seen_dirs:
                self.seen_dirs.add(k)
                games.append(g)

        # 4. Platform Registries (NetEase, Ubisoft, EA, WeGame)
        for g in self.scan_platform_registries():
            k = self._normalize(g.install_dir)
            if k not in self.seen_dirs:
                self.seen_dirs.add(k)
                games.append(g)

        # 5. Windows Uninstall Registry (Official installed games)
        for g in self.scan_windows_uninstall():
            k = self._normalize(g.install_dir)
            if k not in self.seen_dirs:
                self.seen_dirs.add(k)
                games.append(g)

        # 6. Dynamic All Drives Depth-3 Search (Unregistered / Portable / Repack Games)
        for g in self.scan_all_drives_depth_3():
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
            try:
                for item in os.listdir(steamapps):
                    if item.startswith("appmanifest_") and item.endswith(".acf"):
                        acf_path = os.path.join(steamapps, item)
                        info = self._parse_acf(acf_path, lib)
                        if info:
                            game_obj = self.analyze_game_directory(info["name"], "Steam", info["path"])
                            if game_obj:
                                discovered.append(game_obj)
            except Exception:
                pass
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
        try:
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
        except Exception:
            pass
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

    def scan_platform_registries(self) -> List[GameInfo]:
        """Scan Ubisoft, EA, NetEase, and WeGame registry paths."""
        discovered = []

        # 1. Ubisoft Connect
        ubi_keys = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Ubisoft\Launcher\Installs"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Ubisoft\Launcher\Installs")
        ]
        for root, subkey in ubi_keys:
            try:
                with winreg.OpenKey(root, subkey) as k:
                    count, _, _ = winreg.QueryInfoKey(k)
                    for i in range(count):
                        try:
                            gid = winreg.EnumKey(k, i)
                            with winreg.OpenKey(k, gid) as gk:
                                path_val, _ = winreg.QueryValueEx(gk, "InstallDir")
                                if path_val and os.path.exists(path_val):
                                    name = os.path.basename(os.path.normpath(path_val))
                                    g = self.analyze_game_directory(name, "Ubisoft", path_val)
                                    if g:
                                        discovered.append(g)
                        except Exception:
                            continue
            except Exception:
                pass

        # 2. EA Games
        ea_keys = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Electronic Arts\EA Games"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Electronic Arts\EA Games")
        ]
        for root, subkey in ea_keys:
            try:
                with winreg.OpenKey(root, subkey) as k:
                    count, _, _ = winreg.QueryInfoKey(k)
                    for i in range(count):
                        try:
                            gname = winreg.EnumKey(k, i)
                            with winreg.OpenKey(k, gname) as gk:
                                path_val, _ = winreg.QueryValueEx(gk, "Install Dir")
                                if path_val and os.path.exists(path_val):
                                    g = self.analyze_game_directory(gname, "EA", path_val)
                                    if g:
                                        discovered.append(g)
                        except Exception:
                            continue
            except Exception:
                pass

        # 3. NetEase Games (e.g. yysls, wwm, naraka)
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\NetEase") as k:
                count, _, _ = winreg.QueryInfoKey(k)
                for i in range(count):
                    try:
                        app_name = winreg.EnumKey(k, i)
                        with winreg.OpenKey(k, app_name) as ak:
                            p = None
                            for val_name in ["installpath", "InstallLocation", "Path", "InstallPath"]:
                                try:
                                    p, _ = winreg.QueryValueEx(ak, val_name)
                                    if p:
                                        break
                                except Exception:
                                    pass
                            if p and os.path.exists(p):
                                g = self.analyze_game_directory(KNOWN_GAME_NAMES.get(app_name.lower(), app_name), "网易", p)
                                if g:
                                    discovered.append(g)
                    except Exception:
                        continue
        except Exception:
            pass

        # 4. WeGame
        wegame_roots = []
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Tencent\WeGame") as k:
                val, _ = winreg.QueryValueEx(k, "InstallPath")
                if val:
                    wegame_roots.append(os.path.join(val, "WeGameApps"))
        except Exception:
            pass

        for w_root in wegame_roots:
            if os.path.exists(w_root):
                try:
                    for item in os.listdir(w_root):
                        sub = os.path.join(w_root, item)
                        if os.path.isdir(sub):
                            g = self.analyze_game_directory(item, "WeGame", sub)
                            if g:
                                discovered.append(g)
                except Exception:
                    pass

        return discovered

    def scan_windows_uninstall(self) -> List[GameInfo]:
        """Discover games registered in standard Windows Uninstall keys."""
        discovered = []
        keys = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall")
        ]

        skip_publishers = {
            "microsoft", "intel", "nvidia corporation", "advanced micro devices, inc.",
            "realtek semiconductor corp.", "google llc", "asus", "asustek computer inc.",
            "igor pavlov", "jrsoftware.org", "the git development community", "henry++",
            "martin malik", "raelix s.r.o.", "wagnardsoft", "bill", "bililive",
            "the qt company", "python software foundation", "apple inc."
        }

        for root, subkey in keys:
            try:
                with winreg.OpenKey(root, subkey) as k:
                    sub_count, _, _ = winreg.QueryInfoKey(k)
                    for i in range(sub_count):
                        try:
                            sub = winreg.EnumKey(k, i)
                            with winreg.OpenKey(k, sub) as sk:
                                try:
                                    name, _ = winreg.QueryValueEx(sk, "DisplayName")
                                except Exception:
                                    continue
                                if not name or len(name.strip()) < 2:
                                    continue

                                pub = None
                                try:
                                    pub, _ = winreg.QueryValueEx(sk, "Publisher")
                                    if pub and pub.strip().lower() in skip_publishers:
                                        continue
                                except Exception:
                                    pass

                                try:
                                    loc, _ = winreg.QueryValueEx(sk, "InstallLocation")
                                except Exception:
                                    loc = None

                                try:
                                    icon, _ = winreg.QueryValueEx(sk, "DisplayIcon")
                                except Exception:
                                    icon = None

                                target_dir = None
                                if loc and os.path.exists(loc) and os.path.isdir(loc):
                                    target_dir = loc
                                elif icon:
                                    clean_icon = icon.split(",")[0].strip("\"' ")
                                    if os.path.exists(clean_icon):
                                        if os.path.isfile(clean_icon):
                                            target_dir = os.path.dirname(clean_icon)
                                        elif os.path.isdir(clean_icon):
                                            target_dir = clean_icon

                                if not target_dir:
                                    continue

                                norm_dir = target_dir.lower()
                                if any(p in norm_dir for p in ["\\windows\\", "\\system32\\", "\\nvidia\\", "\\package cache\\"]):
                                    continue

                                lower_name = name.lower()
                                if any(kw in lower_name for kw in NON_GAME_APP_KEYWORDS):
                                    continue

                                # Check likelihood of being a game
                                is_game = False
                                if any(kw in norm_dir for kw in ["\\game\\", "\\games\\", "\\steamapps\\", "\\epic games\\"]):
                                    is_game = True
                                elif pub and any(gp in pub.lower() for gp in GAME_PUBLISHERS):
                                    is_game = True
                                elif any(kw in lower_name for kw in ["game", "remastered", "edition", "simulator", "online"]):
                                    is_game = True
                                elif lower_name in KNOWN_GAME_NAMES or Path(target_dir).name.lower() in KNOWN_GAME_NAMES:
                                    is_game = True

                                if not is_game:
                                    continue

                                g = self.analyze_game_directory(name, "已安装游戏", target_dir)
                                if g:
                                    if g.qualification == QualificationStatus.NOT_SUPPORTED and not (pub and any(gp in pub.lower() for gp in GAME_PUBLISHERS)):
                                        continue
                                    discovered.append(g)
                        except Exception:
                            continue
            except Exception:
                continue

        return discovered

    def scan_all_drives_depth_3(self) -> List[GameInfo]:
        """
        Dynamically enumerate all local drives and scan candidate folders up to 3 levels deep.
        Prunes non-game dirs and terminates early once a game folder is discovered.
        """
        discovered = []
        drives = get_local_drives()
        candidate_roots = []

        for drive in drives:
            try:
                for entry in os.scandir(drive):
                    if entry.is_dir():
                        ename = entry.name.lower()
                        if any(kw in ename for kw in GAME_ROOT_KEYWORDS):
                            if not is_dir_pruned(ename):
                                candidate_roots.append(entry.path)
            except Exception:
                pass

        candidate_roots = list(dict.fromkeys(candidate_roots))

        for root in candidate_roots:
            self._scan_folder_recursive(root, root, depth=0, max_depth=3, results=discovered)

        return discovered

    def _resolve_game_title(self, current_dir: str, root_dir: str, exe_stem: str) -> str:
        """Resolve readable game title from directory path components."""
        if exe_stem.lower() in KNOWN_GAME_NAMES:
            return KNOWN_GAME_NAMES[exe_stem.lower()]

        try:
            rel_parts = Path(current_dir).relative_to(root_dir).parts
        except Exception:
            rel_parts = Path(current_dir).parts

        def is_generic_or_version(name: str) -> bool:
            lower = name.lower().strip()
            if lower in ["binaries", "win64", "win64r", "shipping", "x64", "bin", "game", "live", "steam", "common"]:
                return True
            if lower.startswith("v") and any(c.isdigit() for c in lower):
                return True
            if lower.startswith("build."):
                return True
            if lower.isdigit():
                return True
            return False

        # Check from deepest folder upward to find the actual game folder name
        for part in reversed(rel_parts):
            if not is_generic_or_version(part):
                return part

        return os.path.basename(current_dir)

    def _scan_folder_recursive(self, current_dir: str, root_dir: str, depth: int, max_depth: int, results: List[GameInfo]):
        if depth > max_depth:
            return

        norm_curr = self._normalize(current_dir)
        if norm_curr in self.seen_dirs:
            return

        base_name = os.path.basename(current_dir).lower()
        if depth > 0 and (is_dir_pruned(base_name) or base_name in PRUNE_ASSET_DIRS):
            return

        if depth > 0:
            display_name = self._resolve_game_title(current_dir, root_dir, base_name)
            game = self.analyze_game_directory(display_name, "本地扫描", current_dir)
            if game is not None:
                self.seen_dirs.add(norm_curr)
                results.append(game)
                # Early stop: do not recurse into game subfolders
                return

        if depth < max_depth:
            try:
                for entry in os.scandir(current_dir):
                    if entry.is_dir():
                        ename = entry.name.lower()
                        if is_dir_pruned(ename) or ename in PRUNE_ASSET_DIRS:
                            continue
                        self._scan_folder_recursive(entry.path, root_dir, depth + 1, max_depth, results)
            except (PermissionError, OSError):
                pass

    def scan_domestic_and_drives(self) -> List[GameInfo]:
        """Backward-compatible entry point for domestic and custom drive scanning."""
        games: List[GameInfo] = []
        for g in self.scan_platform_registries():
            games.append(g)
        for g in self.scan_windows_uninstall():
            games.append(g)
        for g in self.scan_all_drives_depth_3():
            games.append(g)
        return games

    def analyze_game_directory(self, game_name: str, source: str, install_dir: str) -> Optional[GameInfo]:
        """
        Deep binary discovery inside game directory:
        1. Fast executable discovery in root and standard binary subpaths (Binaries/Win64, bin/x64, Bin64, etc.)
        2. Streamline interposer (sl.interposer.dll) and nvngx_dlssg.dll detection
        3. Check PE versions and existing patch / ReShade status
        """
        if not os.path.exists(install_dir) or not os.path.isdir(install_dir):
            return None

        # 1. Quick primary executable discovery in standard locations
        exe_path, resolved_target = self._find_primary_executable_and_dir(install_dir)
        if not exe_path:
            return None

        target_dir = resolved_target if resolved_target else install_dir

        # 2. Check for Streamline interposer & nvngx_dlssg in direct locations
        interposer_path = None
        dlssg_path = None

        direct_check_dirs = [
            target_dir,
            os.path.join(target_dir, "Streamline"),
            install_dir,
            os.path.join(install_dir, "Streamline"),
            os.path.join(install_dir, "Binaries", "Win64"),
            os.path.join(install_dir, "Binaries", "Win64", "Streamline"),
            os.path.join(install_dir, "bin", "x64"),
            os.path.join(install_dir, "bin", "x64", "Streamline")
        ]
        seen_chk = set()
        for d in direct_check_dirs:
            norm_d = d.lower()
            if norm_d in seen_chk or not os.path.exists(d):
                continue
            seen_chk.add(norm_d)
            try:
                files_lower = {f.lower(): f for f in os.listdir(d)}
                if not interposer_path and "sl.interposer.dll" in files_lower:
                    interposer_path = os.path.join(d, files_lower["sl.interposer.dll"])
                if not dlssg_path and "nvngx_dlssg.dll" in files_lower:
                    dlssg_path = os.path.join(d, files_lower["nvngx_dlssg.dll"])
            except Exception:
                pass

        exe_name = os.path.basename(exe_path)
        stem = Path(exe_path).stem.lower()
        if (game_name.lower() in ["win64", "win64r", "binaries", "shipping", "x64", "game", "live"] or not game_name) and stem in KNOWN_GAME_NAMES:
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
            # so read up to 16 MB.
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

    def _find_primary_executable_and_dir(self, install_dir: str) -> Tuple[Optional[str], Optional[str]]:
        """Find executable in root or standard subdirectories, returning (exe_path, resolved_dir)."""
        def pick_best(candidates: List[str]) -> Optional[str]:
            if not candidates:
                return None
            # Filter out repack multi-part RAR archives (e.g. .part01.exe)
            valid = [c for c in candidates if not re.search(r'\.part\d+\.exe$', os.path.basename(c).lower())]
            if not valid:
                valid = candidates
            for c in valid:
                lower = os.path.basename(c).lower()
                if "shipping.exe" in lower or "win64" in lower or "yysls.exe" in lower or "starcitizen.exe" in lower or "endfield.exe" in lower:
                    return c
            for c in valid:
                lower = os.path.basename(c).lower()
                if not any(k in lower for k in ["launch", "setup", "unist", "crash", "helper", "tool", "config", "patch"]):
                    return c
            return valid[0]

        for sub in STANDARD_EXE_SUBDIRS:
            chk = os.path.join(install_dir, sub.replace("/", os.sep)) if sub else install_dir
            if os.path.isdir(chk):
                try:
                    cands = []
                    for f in os.listdir(chk):
                        if f.lower().endswith(".exe") and f.lower() not in IGNORE_EXE_PATTERNS:
                            cands.append(os.path.join(chk, f))
                    best = pick_best(cands)
                    if best:
                        return best, chk
                except Exception:
                    pass

        return None, None

    def _find_primary_executable(self, target_dir: str, install_dir: Optional[str] = None) -> Optional[str]:
        """Backward-compatible helper returning single exe_path."""
        search_root = install_dir if install_dir else target_dir
        exe, _ = self._find_primary_executable_and_dir(search_root)
        if not exe and target_dir != search_root:
            exe, _ = self._find_primary_executable_and_dir(target_dir)
        return exe
