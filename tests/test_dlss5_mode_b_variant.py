# -*- coding: utf-8 -*-
"""DLSS 5 Mode B (Lecram) addon variants: v12 default, v12.5 optional."""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from apps.app6_dlss5.engine import injector as inj  # noqa: E402


def _make_assets(tmp_path: Path) -> Path:
    src = tmp_path / "assets"
    src.mkdir()
    (src / "dxgi.dll").write_bytes(b"\0" * 16)
    (src / "renodx-dlss.addon64").write_bytes(b"\0" * 32)
    (src / "Lecram-v12.addon64").write_bytes(b"\0" * 40)
    (src / "renodx-dlss5-Lecram-v12.5.addon64").write_bytes(b"\0" * 48)
    return src


def test_mode_b_defaults_to_v12(tmp_path):
    src = _make_assets(tmp_path)
    assets = inj.scan_plugin_source_assets(src, mode="MODE_B")
    assert assets["mode_b_v125_exists"] is True
    assert Path(assets["addon_path"]).name == "Lecram-v12.addon64"
    assert assets["mode_b_variant"] == "v12"


def test_mode_b_v125_selected_on_request(tmp_path):
    src = _make_assets(tmp_path)
    assets = inj.scan_plugin_source_assets(src, mode="MODE_B", mode_b_variant="v12.5")
    assert Path(assets["addon_path"]).name == "renodx-dlss5-Lecram-v12.5.addon64"
    assert assets["mode_b_variant"] == "v12.5"


def test_mode_a_ignores_mode_b_variant(tmp_path):
    src = _make_assets(tmp_path)
    assets = inj.scan_plugin_source_assets(src, mode="MODE_A", mode_b_variant="v12.5")
    assert Path(assets["addon_path"]).name == "renodx-dlss.addon64"


def test_missing_v125_falls_back_to_v12(tmp_path, monkeypatch):
    empty_local = tmp_path / "local_empty"
    empty_local.mkdir()
    monkeypatch.setattr(inj, "LOCAL_ASSETS_DIR", empty_local)
    src = tmp_path / "assets"
    src.mkdir()
    (src / "Lecram-v12.addon64").write_bytes(b"\0" * 40)
    assets = inj.scan_plugin_source_assets(src, mode="MODE_B", mode_b_variant="v12.5")
    assert Path(assets["addon_path"]).name == "Lecram-v12.addon64"
    assert assets["mode_b_variant"] == "v12"
