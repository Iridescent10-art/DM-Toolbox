# -*- coding: utf-8 -*-
"""DLSS 5 NR VRAM budget guard: settings persistence and preset propagation."""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from apps.app6_dlss5.engine import injector as inj  # noqa: E402


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_sync_nr_vram_settings_updates_every_preset(tmp_path):
    game = tmp_path / "game"
    game.mkdir()
    _write(game / "ReShadePreset.ini", "NREnabled=1\nNRVramBudgetGuard=0\nNRVramBudgetMargin=0\n")
    _write(game / "RenoDX" / "DLSS5" / "Presets" / "My look.ini",
           "NREnabled=1\nNRVramBudgetGuard=0\nNRVramBudgetMargin=0\n")

    assert inj.sync_nr_vram_settings(game, True, 10) is True

    for path in (game / "ReShadePreset.ini",
                 game / "RenoDX" / "DLSS5" / "Presets" / "My look.ini"):
        text = path.read_text(encoding="utf-8")
        assert "NRVramBudgetGuard=1" in text
        assert "NRVramBudgetMargin=10" in text
        assert "VramBudgetGuard=1" in text
        assert "BudgetGuard=1" in text


def test_sync_nr_vram_settings_can_disable_again(tmp_path):
    game = tmp_path / "game"
    game.mkdir()
    _write(game / "ReShadePreset.ini", "NRVramBudgetGuard=1\nNRVramBudgetMargin=15\n")

    assert inj.sync_nr_vram_settings(game, False, 0) is True
    text = (game / "ReShadePreset.ini").read_text(encoding="utf-8")
    assert "NRVramBudgetGuard=0" in text
    assert "NRVramBudgetMargin=0" in text


def test_sync_nr_vram_settings_returns_false_without_target(tmp_path):
    assert inj.sync_nr_vram_settings(tmp_path / "missing") is False


def test_nr_vram_settings_roundtrip(tmp_path, monkeypatch):
    store = tmp_path / "nr_vram.json"
    monkeypatch.setattr(inj, "_nr_vram_settings_path", lambda: store)

    assert inj.save_nr_vram_settings(True, 15) is True
    loaded = inj.load_nr_vram_settings()
    assert loaded["guard"] is True
    assert loaded["margin"] == 15

    # Values are clamped into a sane range.
    assert inj.save_nr_vram_settings(False, 999) is True
    loaded = inj.load_nr_vram_settings()
    assert loaded["guard"] is False
    assert loaded["margin"] == 50


def test_nr_vram_defaults_are_guard_on_with_5pct(tmp_path, monkeypatch):
    """Factory default: guard enabled with a 5% reserve (4K + MFG safety net)."""
    monkeypatch.setattr(inj, "_nr_vram_settings_path", lambda: tmp_path / "missing.json")
    settings = inj.load_nr_vram_settings()
    assert settings["guard"] is True
    assert settings["margin"] == 5
