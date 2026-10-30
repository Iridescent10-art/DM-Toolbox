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


def test_mode_b_defaults_to_v125(tmp_path):
    """模式 B 的出厂默认版本是 Lecram v12.5。"""
    src = _make_assets(tmp_path)
    assets = inj.scan_plugin_source_assets(src, mode="MODE_B")
    assert assets["mode_b_v125_exists"] is True
    assert Path(assets["addon_path"]).name == "renodx-dlss5-Lecram-v12.5.addon64"
    assert assets["mode_b_variant"] == "v12.5"


def test_mode_b_can_select_v12_explicitly(tmp_path):
    src = _make_assets(tmp_path)
    assets = inj.scan_plugin_source_assets(src, mode="MODE_B", mode_b_variant="v12")
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


def test_inject_mode_a_reports_failure_when_mode_b_addon_cannot_be_removed(tmp_path):
    """旧底座删不掉时必须报错，而不是“假成功”继续注入模式 A。"""
    from apps.app6_dlss5.engine.injector import DLSS5Injector

    game = tmp_path / "game"
    game.mkdir()
    (game / "game.exe").write_bytes(b"MZ" + b"\x00" * 64)
    locked = game / "Lecram-v12.addon64"
    locked.write_bytes(b"\x00" * 64)

    # 模拟“清理函数以为删掉了、其实文件还在”的情况，验证注入后的兜底校验
    import apps.app6_dlss5.engine.injector as _inj
    orig = _inj.clean_conflicting_addons
    _inj.clean_conflicting_addons = lambda *a, **k: (True, "skipped", [])
    try:
        ok, msg = DLSS5Injector.inject(str(game), mode="MODE_A", hook_point="0")
    finally:
        _inj.clean_conflicting_addons = orig

    assert ok is False
    assert "底座切换未完成" in msg
    assert "Lecram-v12.addon64" in msg
