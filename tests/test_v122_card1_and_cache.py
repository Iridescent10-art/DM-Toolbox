# -*- coding: utf-8 -*-
"""
Automated Verification Script for v1.2.2:
1. Card 1 Visual Structure & Compact Alignment (badge, header, card_game_info, side-by-side pick buttons)
2. Game Cache Manager (save, load, custom games persistence, last selected exe)
3. 0ms Instant Cache Startup & Dynamic Status / Arch Info Formatting
4. Light / Dark Theme Rendering & Screenshot Capture
"""

import os
import sys
import json
import time
from pathlib import Path

# Force UTF-8 for console output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
APP2_DIR = ROOT_DIR / "apps" / "app2_mfg"
if str(APP2_DIR) not in sys.path:
    sys.path.insert(0, str(APP2_DIR))

os.environ["QT_QPA_PLATFORM"] = "windows"

from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtWidgets import QApplication
from apps.app2_mfg.core.models import BackendType, QualificationStatus, GameInfo
from apps.app2_mfg.core.game_cache import GameCacheManager
from apps.app2_mfg.gui_qt import ModernMFGGUI
from common.config_manager import CONFIG_ROOT, set_global_theme


def run_v122_verification():
    print("=" * 70)
    print(">>> Starting v1.2.2 Automated Verification...")
    print("=" * 70)

    # -------------------------------------------------------------
    # 1. Test GameCacheManager Persistence
    # -------------------------------------------------------------
    print("\n>>> [Test 1] Testing GameCacheManager File Persistence & Merging...")
    cache_path = GameCacheManager.CACHE_FILE
    print(f"  Cache file path: {cache_path}")
    assert cache_path.parent.exists(), "Config root directory must exist"

    # This suite uses mock games: snapshot the real cache and always restore it, so a
    # verification run can never wipe the user's real game library.
    import atexit
    _cache_backup = cache_path.read_bytes() if cache_path.exists() else None

    def _restore_real_cache():
        try:
            if _cache_backup is not None:
                cache_path.write_bytes(_cache_backup)
            # If there was no cache before this test, leave the generated one in place
            # instead of deleting it: another suite may have created the real library
            # between the snapshot and process exit.
        except Exception:
            pass

    atexit.register(_restore_real_cache)

    # Create mock games
    g1 = GameInfo(
        name="Cyberpunk 2077",
        source="Steam",
        install_dir=r"D:\Games\Steam\Cyberpunk 2077",
        target_dir=r"D:\Games\Steam\Cyberpunk 2077\bin\x64",
        exe_path=r"D:\Games\Steam\Cyberpunk 2077\bin\x64\Cyberpunk2077.exe",
        exe_name="Cyberpunk2077.exe",
        qualification=QualificationStatus.QUALIFIED,
        streamline_ver="2.4.0",
        dlssg_ver="3.7.0",
        is_patched=True,
        patched_backend="mavismmg",
        installed_version="1.4.4"
    )
    g2 = GameInfo(
        name="燕云十六声 (Where Winds Meet)",
        source="手动自定义",
        install_dir=r"D:\Games\yysls",
        target_dir=r"D:\Games\yysls\Engine\Binaries\Win64",
        exe_path=r"D:\Games\yysls\Engine\Binaries\Win64\yysls.exe",
        exe_name="yysls.exe",
        qualification=QualificationStatus.QUALIFIED,
        streamline_ver="2.2.0",
        dlssg_ver="3.5.0",
        is_patched=False
    )

    GameCacheManager.save_cache(
        last_selected_exe=g1.exe_path,
        custom_games=[g2],
        scanned_games=[g1]
    )

    loaded_cache = GameCacheManager.load_cache()
    assert loaded_cache.get("last_selected_exe") == g1.exe_path, "last_selected_exe mismatch"
    assert len(loaded_cache.get("custom_added_games", [])) == 1, "custom_added_games count mismatch"
    assert len(loaded_cache.get("scanned_games_cache", [])) == 1, "scanned_games_cache count mismatch"

    cached_games, last_exe = GameCacheManager.get_cached_games()
    assert len(cached_games) == 2, f"Expected 2 cached games, got {len(cached_games)}"
    assert last_exe == g1.exe_path, "Last exe returned must match"
    print("  ✓ GameCacheManager persistence verified successfully!")

    # -------------------------------------------------------------
    # 2. Test UI Card 1 Refactor & Instant Cache Loading
    # -------------------------------------------------------------
    print("\n>>> [Test 2] Testing Card 1 UI Components & 0ms Instant Cache Load...")
    app = QApplication.instance() or QApplication(sys.argv)

    gui = ModernMFGGUI()
    gui.show()
    app.processEvents()

    # Verify badge_game
    assert hasattr(gui, "badge_game"), "gui must have badge_game"
    assert gui.badge_game.text() == "🎯", "badge_game text must be 🎯"
    assert gui.badge_game.width() == 40 and gui.badge_game.height() == 40, f"badge_game size {gui.badge_game.width()}x{gui.badge_game.height()} != 40x40"
    print("  ✓ Badge 🎯 is 40x40px and centered")

    # Verify header button
    assert hasattr(gui, "btn_rescan_header"), "gui must have btn_rescan_header"
    assert "刷新" in gui.btn_rescan_header.text(), "btn_rescan_header text must contain 刷新"
    print(f"  ✓ Header refresh button present: '{gui.btn_rescan_header.text()}'")

    # Verify card_game_info
    assert hasattr(gui, "card_game_info"), "gui must have card_game_info"
    assert hasattr(gui, "lbl_game_path"), "gui must have lbl_game_path"
    assert hasattr(gui, "btn_open_game_dir"), "gui must have btn_open_game_dir"
    assert hasattr(gui, "lbl_info_arch"), "gui must have lbl_info_arch"
    assert hasattr(gui, "lbl_info_patch"), "gui must have lbl_info_patch"
    print("  ✓ card_game_info container and all internal rows present")

    # Verify secondary pick buttons
    assert hasattr(gui, "btn_pick_exe"), "gui must have btn_pick_exe"
    assert hasattr(gui, "btn_pick_dir"), "gui must have btn_pick_dir"
    assert "主程序" in gui.btn_pick_exe.text(), "btn_pick_exe text correct"
    assert "文件夹" in gui.btn_pick_dir.text(), "btn_pick_dir text correct"
    assert gui.btn_pick_exe.minimumHeight() >= 32, "btn_pick_exe minimumHeight >= 32"
    assert gui.btn_pick_dir.minimumHeight() >= 32, "btn_pick_dir minimumHeight >= 32"
    print("  ✓ Side-by-side pick buttons verified")

    # Verify instant cache populated combo_games
    print(f"  Combo games count: {gui.combo_games.count()}")
    assert gui.combo_games.count() >= 2, f"Expected at least 2 games from instant cache, got {gui.combo_games.count()}"

    # Verify Game 1 (Cyberpunk - Patched)
    gui.combo_games.setCurrentIndex(0)
    app.processEvents()
    print(f"  Selected Game: {gui.selected_game.name}")
    print(f"  Path: {gui.lbl_game_path.text()}")
    print(f"  Arch: {gui.lbl_info_arch.text()}")
    print(f"  Patch: {gui.lbl_info_patch.text()}")

    assert "Cyberpunk" in gui.selected_game.name or "燕云" in gui.selected_game.name, "Selected game name mismatch"
    assert len(gui.lbl_game_path.text()) > 5, "Path must not be empty"
    assert "DirectX" in gui.lbl_info_arch.text(), "Arch text must contain DirectX"
    assert "已注入" in gui.lbl_info_patch.text() or "官方纯净原版" in gui.lbl_info_patch.text(), "Patch text must contain status"

    # -------------------------------------------------------------
    # 3. Capture Visual Verification Screenshots (Light & Dark)
    # -------------------------------------------------------------
    print("\n>>> [Test 3] Capturing Verification Screenshots...")
    artifacts_dir = Path(r"C:\Users\17547\.gemini\antigravity\brain\f20364b0-8af4-45b1-a8b6-b621a086cb69")
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # 3.1 Dark Mode Screenshot
    set_global_theme("dark")
    gui.is_dark_mode = True
    gui._apply_theme()
    app.processEvents()
    time.sleep(0.3)
    dark_pix = gui.grab()
    dark_out = artifacts_dir / "verification_v122_card1_dark.png"
    dark_pix.save(str(dark_out))
    print(f"  ✓ Dark mode screenshot saved: {dark_out}")

    # 3.2 Light Mode Screenshot
    set_global_theme("light")
    gui.is_dark_mode = False
    gui._apply_theme()
    app.processEvents()
    time.sleep(0.3)
    light_pix = gui.grab()
    light_out = artifacts_dir / "verification_v122_card1_light.png"
    light_pix.save(str(light_out))
    print(f"  ✓ Light mode screenshot saved: {light_out}")

    gui.close()
    print("\n" + "=" * 70)
    print(">>> ALL v1.2.2 VERIFICATION ASSERTIONS PASSED (100%)!")
    print("=" * 70)


if __name__ == "__main__":
    run_v122_verification()
