"""
Game Library Local Persistence Cache Manager.
Implements Cache-First + Background Silent Refresh Architecture for instant startup.
"""

import os
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

try:
    from core.models import GameInfo, QualificationStatus
except ModuleNotFoundError:
    from apps.app2_mfg.core.models import GameInfo, QualificationStatus


def get_cache_file() -> Path:
    """Resolve unified path to mfg_game_cache.json in AppData/ToolboxMaster/config."""
    try:
        from common.config_manager import CONFIG_ROOT
        return CONFIG_ROOT / "mfg_game_cache.json"
    except Exception:
        appdata = os.environ.get("APPDATA", str(Path.home()))
        cfg_dir = Path(appdata) / "ToolboxMaster" / "config"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        return cfg_dir / "mfg_game_cache.json"


def _get_fallback_cache_file() -> Path:
    """Check app2_mfg subfolder fallback."""
    try:
        from common.config_manager import get_app_config_path
        return get_app_config_path("app2_mfg", "mfg_game_cache.json")
    except Exception:
        appdata = os.environ.get("APPDATA", str(Path.home()))
        return Path(appdata) / "ToolboxMaster" / "config" / "app2_mfg" / "mfg_game_cache.json"


class GameCacheManager:
    """Manages reading, writing, and merging of cached games and custom games."""

    CACHE_FILE = get_cache_file()

    @classmethod
    def load_cache(cls) -> Dict[str, Any]:
        """Load raw cache dictionary from disk."""
        target_f = get_cache_file()
        fallback_f = _get_fallback_cache_file()

        file_to_read = None
        if target_f.exists():
            file_to_read = target_f
        elif fallback_f.exists():
            file_to_read = fallback_f

        if file_to_read and file_to_read.exists():
            try:
                with open(file_to_read, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception:
                pass

        return {
            "last_selected_exe": "",
            "custom_added_games": [],
            "scanned_games_cache": [],
            "last_scan_timestamp": 0
        }

    @classmethod
    def get_cached_games(cls) -> Tuple[List[GameInfo], Optional[str]]:
        """
        Load cached games for instantaneous startup.
        Returns:
            (all_games: List[GameInfo], last_selected_exe: Optional[str])
        """
        cache = cls.load_cache()
        last_exe = cache.get("last_selected_exe") or None

        games: List[GameInfo] = []
        seen_exes = set()

        # 1. First add custom games (priority)
        for item in cache.get("custom_added_games", []):
            try:
                g = GameInfo.from_dict(item)
                norm = g.exe_path.lower()
                if norm not in seen_exes:
                    seen_exes.add(norm)
                    games.append(g)
            except Exception:
                pass

        # 2. Add scanned library games
        for item in cache.get("scanned_games_cache", []):
            try:
                g = GameInfo.from_dict(item)
                norm = g.exe_path.lower()
                if norm not in seen_exes:
                    seen_exes.add(norm)
                    games.append(g)
            except Exception:
                pass

        # 3. Reconcile the cached patch state with the real on-disk manifest.
        #    A stale custom game used to keep `is_patched=True, patched_backend=optiscaler`
        #    after a successful restore, so the whole UI "jumped back" to Mode C.
        cls.reconcile_patch_state(games)

        return games, last_exe

    @staticmethod
    def reconcile_patch_state(games: List[GameInfo]) -> None:
        """Trust the on-disk manifest, never the cached is_patched/patched_backend flags."""
        for game in games:
            try:
                target = Path(game.target_dir or "")
                if not game.target_dir or not target.exists():
                    continue
                manifest = target / ".mfg_patch_manifest.json"
                if not manifest.exists():
                    game.is_patched = False
                    game.patched_backend = None
                    game.installed_version = None
                    continue
                with open(manifest, "r", encoding="utf-8") as f:
                    data = json.load(f)
                game.is_patched = True
                game.patched_backend = data.get("active_backend") or game.patched_backend
                game.installed_version = data.get("installed_version") or game.installed_version
            except Exception:
                continue

    @classmethod
    def update_patch_state(
        cls,
        exe_path: str,
        is_patched: bool,
        backend: Optional[str] = None,
        installed_version: Optional[str] = None
    ) -> bool:
        """Persist a patch/restore result immediately so the next startup is correct."""
        if not exe_path:
            return False
        cache = cls.load_cache()
        changed = False
        for bucket in ("custom_added_games", "scanned_games_cache"):
            for item in cache.get(bucket, []):
                if str(item.get("exe_path", "")).lower() != exe_path.lower():
                    continue
                item["is_patched"] = bool(is_patched)
                item["patched_backend"] = backend if is_patched else None
                if installed_version is not None:
                    item["installed_version"] = installed_version
                changed = True
        if not changed:
            return False
        try:
            target_f = get_cache_file()
            target_f.parent.mkdir(parents=True, exist_ok=True)
            with open(target_f, "w", encoding="utf-8") as f:
                json.dump(cache, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    @classmethod
    def save_cache(
        cls,
        last_selected_exe: Optional[str] = None,
        custom_games: Optional[List[GameInfo]] = None,
        scanned_games: Optional[List[GameInfo]] = None
    ) -> bool:
        """Persist games and last selection to cache."""
        target_f = get_cache_file()
        cur_cache = cls.load_cache()

        if last_selected_exe is not None:
            cur_cache["last_selected_exe"] = last_selected_exe

        if custom_games is not None:
            cur_cache["custom_added_games"] = [g.to_dict() for g in custom_games]

        if scanned_games is not None:
            cur_cache["scanned_games_cache"] = [g.to_dict() for g in scanned_games]
            cur_cache["last_scan_timestamp"] = int(time.time())

        try:
            target_f.parent.mkdir(parents=True, exist_ok=True)
            with open(target_f, "w", encoding="utf-8") as f:
                json.dump(cur_cache, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    @classmethod
    def save_last_selected(cls, exe_path: str):
        """Update just the last selected executable path."""
        if not exe_path:
            return
        cache = cls.load_cache()
        cache["last_selected_exe"] = exe_path
        target_f = get_cache_file()
        try:
            target_f.parent.mkdir(parents=True, exist_ok=True)
            with open(target_f, "w", encoding="utf-8") as f:
                json.dump(cache, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    @classmethod
    def add_custom_game(cls, game: GameInfo):
        """Add or update a user custom picked game into persistent custom list."""
        cache = cls.load_cache()
        custom_list = cache.get("custom_added_games", [])

        # Dedup by exe_path
        norm = game.exe_path.lower()
        new_list = [item for item in custom_list if str(item.get("exe_path", "")).lower() != norm]
        new_list.insert(0, game.to_dict())
        cache["custom_added_games"] = new_list
        cache["last_selected_exe"] = game.exe_path

        target_f = get_cache_file()
        try:
            target_f.parent.mkdir(parents=True, exist_ok=True)
            with open(target_f, "w", encoding="utf-8") as f:
                json.dump(cache, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
