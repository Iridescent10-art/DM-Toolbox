# -*- coding: utf-8 -*-
"""模式 D：MFGAdaUnlock-RenoDX（ReShade/RHI 插件）部署与 DLSS 5 共存。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "apps" / "app2_mfg"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from core.models import BackendType, GameInfo, QualificationStatus  # noqa: E402
from core.patcher import PatchEngine  # noqa: E402
from core.updater import ComponentUpdater  # noqa: E402


def _make_game(tmp_path: Path) -> GameInfo:
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    exe = game_dir / "game.exe"
    exe.write_bytes(b"MZ" + b"\x00" * 512)
    return GameInfo(
        name="TestGame",
        source="Steam",
        install_dir=str(game_dir),
        target_dir=str(game_dir),
        exe_path=str(exe),
        exe_name="game.exe",
        qualification=QualificationStatus.QUALIFIED,
    )


def test_mode_d_deploys_reshade_addon(tmp_path):
    game = _make_game(tmp_path)
    engine = PatchEngine(updater=ComponentUpdater())
    ok, msg = engine.patch_game(game, requested_backend=BackendType.RESHADE_ADDON)
    assert ok, msg

    td = Path(game.target_dir)
    assert (td / "renodx-mfgunlock.addon64").exists(), "模式 D 必须部署 RenoDX MFG addon"
    assert (td / "dxgi.dll").exists(), "模式 D 必须部署 ReShade 宿主"
    assert (td / "ReShade.ini").exists()


def test_mode_d_addon_survives_dlss5_injection(tmp_path):
    game = _make_game(tmp_path)
    engine = PatchEngine(updater=ComponentUpdater())
    ok, msg = engine.patch_game(game, requested_backend=BackendType.RESHADE_ADDON)
    assert ok, msg

    from apps.app6_dlss5.engine import injector as dlss5
    ok, msg = dlss5.DLSS5Injector.inject(str(Path(game.target_dir)), mode="MODE_A", hook_point="0")
    assert ok, msg

    td = Path(game.target_dir)
    assert (td / "renodx-mfgunlock.addon64").exists(), "DLSS 5 注入不得删除模式 D 插件"
    assert (td / "renodx-dlss.addon64").exists(), "DLSS 5 插件应正常部署"
    ini = (td / "ReShade.ini").read_text(encoding="utf-8", errors="ignore")
    assert "renodx-dlss" in ini.lower() or "loadfromdllmain" in ini.lower()
