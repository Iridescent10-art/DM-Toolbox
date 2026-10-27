# -*- coding: utf-8 -*-
"""Mode A XeSS (XeMFG) option + 一键卸载残留清理。"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
APP2_DIR = REPO_ROOT / "apps" / "app2_mfg"
if str(APP2_DIR) not in sys.path:
    sys.path.insert(0, str(APP2_DIR))

from core.ini_sync import IniConfigManager  # noqa: E402


def test_mode_a_xemfg_writes_standalone_without_dlss_overrides(tmp_path):
    config = {
        "multiplier": 3,
        "dlss_preset": "M",
        "dlssg_preset": "C",
        "menu_key": "Backspace",
        "xemfg_standalone": True,
    }
    assert IniConfigManager.sync_mode_a_forward(tmp_path, config) is True

    data = json.loads((tmp_path / "RTXMFG-Universal.json").read_text(encoding="utf-8"))
    assert data["xemfgStandalone"] == 1
    assert data["xemfgFrames"] == 3
    # 切到 XeSS 时不再向 DLSS 特性下发 SR / DLSS-G 预设
    assert data["overrideDlssPreset"] is False
    assert data["dlssPreset"] == 0
    assert data["dlssSrPreset"] == 0
    assert data["dlssgPreset"] == 0

    ini = (tmp_path / "mfg_unlocker.ini").read_text(encoding="utf-8")
    assert "Standalone=1" in ini
    assert "DLSSGPreset=Auto" in ini


def test_mode_a_dlssg_keeps_preset_overrides(tmp_path):
    config = {
        "multiplier": 3,
        "dlss_preset": "M",
        "dlssg_preset": "C",
        "menu_key": "Backspace",
        "xemfg_standalone": False,
    }
    assert IniConfigManager.sync_mode_a_forward(tmp_path, config) is True
    data = json.loads((tmp_path / "RTXMFG-Universal.json").read_text(encoding="utf-8"))
    assert data["xemfgStandalone"] == 0
    assert data["overrideDlssPreset"] is True
    assert data["dlssSrPreset"] == 13
    assert data["dlssgPreset"] == 3


def test_full_restore_removes_mfg_dxgi_and_reshade_leftovers(tmp_path):
    """彻底清除全部：dashdogy 占用 dxgi.dll 时也要删掉，ReShade 预设/备份目录一并清理。"""
    from core.updater import ComponentUpdater
    from core.patcher import PatchEngine
    from core.models import GameInfo, QualificationStatus, PatchManifest, BackendType
    from core.rollback import RollbackEngine

    game_dir = tmp_path / "game"
    game_dir.mkdir(parents=True, exist_ok=True)
    exe_p = game_dir / "game.exe"
    exe_p.write_bytes(b"MZ" + b"\x00" * 100)

    game_info = GameInfo(
        name="TestGame",
        source="custom",
        install_dir=str(game_dir),
        target_dir=str(game_dir),
        exe_path=str(exe_p),
        exe_name="game.exe",
        qualification=QualificationStatus.QUALIFIED,
    )
    manifest = PatchManifest(
        app_version="3.0.2",
        game_name="TestGame",
        target_exe=str(exe_p),
        target_dir=str(game_dir),
        active_backend=BackendType.STANDALONE.value,
        installed_version="latest",
    )
    ok, err = PatchEngine(updater=ComponentUpdater())._apply_standalone_patch(game_info, manifest)
    assert ok, f"_apply_standalone_patch failed: {err}"
    assert (game_dir / "dxgi.dll").exists()

    # 模拟 DLSS 5 / ReShade 留下的残留
    (game_dir / "ReShade.ini").write_text("[GENERAL]\n", encoding="utf-8")
    (game_dir / "ReShadePreset.ini").write_text("[Preset]\n", encoding="utf-8")
    (game_dir / ".dlss5_backup").mkdir(exist_ok=True)
    (game_dir / ".mfg_coex_backup.json").write_text("{}", encoding="utf-8")
    (game_dir / "old.addon64.bak").write_bytes(b"\0")

    rb_ok, rb_err = RollbackEngine().rollback(str(game_dir), clean_all=True)
    assert rb_ok, f"rollback failed: {rb_err}"

    assert not (game_dir / "dxgi.dll").exists(), "dashdogy 的 dxgi.dll 必须被彻底清除"
    assert not (game_dir / "ReShade.ini").exists()
    assert not (game_dir / "ReShadePreset.ini").exists()
    assert not (game_dir / ".dlss5_backup").exists()
    assert not (game_dir / ".mfg_coex_backup.json").exists()
    assert not (game_dir / "old.addon64.bak").exists()
