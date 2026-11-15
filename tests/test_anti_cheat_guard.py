# -*- coding: utf-8 -*-
"""反作弊游戏识别与警告文案。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.anti_cheat import anti_cheat_warning_text, detect_anti_cheat  # noqa: E402


def test_forza_horizon_6_detected_by_name_and_exe():
    assert detect_anti_cheat("Forza Horizon 6") == "Forza Horizon 6"
    assert detect_anti_cheat("ForzaHorizon6", r"D:\game\ForzaHorizon6\forzahorizon6.exe") == "Forza Horizon 6"


def test_other_anti_cheat_titles_detected():
    assert "Battlefield" in (detect_anti_cheat("Battlefield 6") or "")
    assert "GTA V" in (detect_anti_cheat("GTA V Enhanced") or "")
    assert "Zenless" in (detect_anti_cheat("Zenless Zone Zero") or "")


def test_normal_game_not_detected(tmp_path):
    assert detect_anti_cheat("yysls", r"D:\game\yysls\yysls.exe", str(tmp_path)) is None


def test_easy_anti_cheat_module_directory_detected(tmp_path):
    ac_dir = tmp_path / "EasyAntiCheat"
    ac_dir.mkdir()
    (ac_dir / "EasyAntiCheat.exe").write_bytes(b"MZ")
    assert detect_anti_cheat("SomeGame", "", str(tmp_path)) is not None


def test_warning_text_mentions_force_continue():
    text = anti_cheat_warning_text("Forza Horizon 6")
    assert "Forza Horizon 6" in text
    assert "反作弊" in text
    assert "强制" in text
