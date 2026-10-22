# -*- coding: utf-8 -*-
"""
Automated unit tests for DLSS 5 (app6_dlss5) Game Dropdown switching and real-time sync.
Guarantees that switching games in the dropdown immediately updates displayed game paths,
and external cache updates (from app2_mfg) seamlessly synchronize.
"""

import sys
import pytest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
for p in (ROOT_DIR, ROOT_DIR / "apps" / "app2_mfg"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from PySide6.QtWidgets import QApplication
from apps.app6_dlss5.app import DLSS5MainWindow
from apps.app2_mfg.core.models import GameInfo, QualificationStatus
from apps.app2_mfg.core.game_cache import GameCacheManager


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_dropdown_switch_updates_game_path_and_target_dir(qapp):
    win = DLSS5MainWindow()
    
    # Mock two distinct game entries
    game_a = GameInfo(
        name="Game Alpha", source="Steam",
        install_dir=r"D:\game\Alpha", target_dir=r"D:\game\Alpha\bin",
        exe_path=r"D:\game\Alpha\bin\alpha.exe", exe_name="alpha.exe",
        qualification=QualificationStatus.QUALIFIED
    )
    game_b = GameInfo(
        name="Game Beta", source="Epic",
        install_dir=r"D:\game\Beta", target_dir=r"D:\game\Beta\Win64",
        exe_path=r"D:\game\Beta\Win64\beta.exe", exe_name="beta.exe",
        qualification=QualificationStatus.QUALIFIED
    )

    win.combo_games.blockSignals(True)
    win.combo_games.clear()
    win.combo_games.addItem("[Steam] Game Alpha", game_a)
    win.combo_games.addItem("[Epic] Game Beta", game_b)
    win.combo_games.setCurrentIndex(-1)
    win.combo_games.blockSignals(False)

    # 1. Switch to Game Alpha
    win.combo_games.setCurrentIndex(0)
    assert win.selected_game.name == "Game Alpha"
    assert "alpha.exe" in win.lbl_game_path.text()
    assert r"D:\game\Alpha\bin" in win.lbl_target_dir.text().replace("\u200b", "")

    # 2. Switch to Game Beta
    win.combo_games.setCurrentIndex(1)
    assert win.selected_game.name == "Game Beta"
    assert "beta.exe" in win.lbl_game_path.text()
    assert r"D:\game\Beta\Win64" in win.lbl_target_dir.text().replace("\u200b", "")
    assert "alpha.exe" not in win.lbl_game_path.text()

    # 3. Switch back to Game Alpha
    win.combo_games.setCurrentIndex(0)
    assert win.selected_game.name == "Game Alpha"
    assert "alpha.exe" in win.lbl_game_path.text()
    assert r"D:\game\Alpha\bin" in win.lbl_target_dir.text().replace("\u200b", "")
    assert "beta.exe" not in win.lbl_game_path.text()

    win.close()


def test_external_game_cache_sync(qapp):
    win = DLSS5MainWindow()
    
    game_1 = GameInfo(
        name="SyncGame1", source="Steam",
        install_dir=r"C:\g1", target_dir=r"C:\g1",
        exe_path=r"C:\g1\game1.exe", exe_name="game1.exe",
        qualification=QualificationStatus.QUALIFIED
    )
    game_2 = GameInfo(
        name="SyncGame2", source="Steam",
        install_dir=r"C:\g2", target_dir=r"C:\g2",
        exe_path=r"C:\g2\game2.exe", exe_name="game2.exe",
        qualification=QualificationStatus.QUALIFIED
    )

    win.combo_games.blockSignals(True)
    win.combo_games.clear()
    win.combo_games.addItem("SyncGame1", game_1)
    win.combo_games.addItem("SyncGame2", game_2)
    win.combo_games.setCurrentIndex(-1)
    win.combo_games.blockSignals(False)

    win.combo_games.setCurrentIndex(0)
    assert "game1.exe" in win.lbl_game_path.text()

    # Simulate App 2 saving last selected game
    GameCacheManager.save_last_selected(r"C:\g2\game2.exe")
    win._sync_selected_game_from_cache()

    # Verify DLSS5 window synced to game 2
    assert win.combo_games.currentIndex() == 1
    assert win.selected_game.name == "SyncGame2"
    assert "game2.exe" in win.lbl_game_path.text()

    win.close()
