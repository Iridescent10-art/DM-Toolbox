# -*- coding: utf-8 -*-
"""模式 C 0.4.2：sr 超分内核按需部署（保留给 RTX 20/30 用户）。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "apps" / "app2_mfg") not in sys.path:
    sys.path.insert(0, str(ROOT / "apps" / "app2_mfg"))

from core.models import (  # noqa: E402
    BackendType, GameInfo, PatchManifest, QualificationStatus,
)
from core.patcher import PatchEngine  # noqa: E402
from core.updater import ComponentUpdater  # noqa: E402
from core import optiscaler_config  # noqa: E402


def _make_game(tmp_path: Path) -> GameInfo:
    game_dir = tmp_path / "game"
    game_dir.mkdir(parents=True)
    exe = game_dir / "game.exe"
    exe.write_bytes(b"MZ" + b"\x00" * 64)
    return GameInfo(
        name="TestGame",
        source="custom",
        install_dir=str(game_dir),
        target_dir=str(game_dir),
        exe_path=str(exe),
        exe_name="game.exe",
        qualification=QualificationStatus.QUALIFIED,
    )


def _manifest(game: GameInfo) -> PatchManifest:
    return PatchManifest(
        app_version="3.0.8",
        game_name=game.name,
        target_exe=game.exe_path,
        target_dir=game.target_dir,
        active_backend=BackendType.DLSSG_SM86.value,
        installed_version="0.4.2",
    )


def test_mode_c_skips_sr_when_super_resolution_off(tmp_path, monkeypatch):
    game = _make_game(tmp_path)
    monkeypatch.setattr(
        optiscaler_config,
        "load_dlssg_sm86_preset",
        lambda *a, **k: {
            "enabled": 1, "engine": "DLSS", "max_generated_frames": 3,
            "optimized": 1, "dlssg_preset": "C",
            "super_resolution_mode": "Off", "proxy_dll": "version.dll",
            "logging_level": 1,
        },
    )
    engine = PatchEngine(updater=ComponentUpdater())
    ok, err = engine._apply_dlssg_sm86_patch(game, _manifest(game))
    assert ok, err
    game_dir = Path(game.target_dir)
    assert (game_dir / "dlssg_sm86" / "runtime" / "nvngx_dlssg.dll").exists()
    assert not (game_dir / "dlssg_sm86" / "sr").exists(), "默认 Off 不应部署 172MB 的 sr 内核"


def test_mode_c_deploys_sr_when_super_resolution_enabled(tmp_path, monkeypatch):
    game = _make_game(tmp_path)
    monkeypatch.setattr(
        optiscaler_config,
        "load_dlssg_sm86_preset",
        lambda *a, **k: {
            "enabled": 1, "engine": "DLSS", "max_generated_frames": 3,
            "optimized": 1, "dlssg_preset": "C",
            "super_resolution_mode": "M-INT8", "proxy_dll": "version.dll",
            "logging_level": 1,
        },
    )
    engine = PatchEngine(updater=ComponentUpdater())
    ok, err = engine._apply_dlssg_sm86_patch(game, _manifest(game))
    assert ok, err
    sr_dir = Path(game.target_dir) / "dlssg_sm86" / "sr"
    assert (sr_dir / "nvngx_dlss.dll").exists(), "选择 INT8 超分时必须部署 sr 运行库"
    assert (sr_dir / "sr_kernels.dll").exists()
