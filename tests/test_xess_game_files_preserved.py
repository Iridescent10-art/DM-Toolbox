# -*- coding: utf-8 -*-
"""游戏本体静态导入的 XeSS 运行库（Cyberpunk / 巫师3）不得被模式 A/C 清理误删。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "apps" / "app2_mfg"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from core.models import (  # noqa: E402
    BackendType, GameInfo, PatchManifest, QualificationStatus,
)
from core.patcher import PatchEngine  # noqa: E402
from core.rollback import RollbackEngine  # noqa: E402
from core.updater import ComponentUpdater  # noqa: E402


def _make_cyberpunk_like(tmp_path: Path) -> GameInfo:
    game_dir = tmp_path / "Cyberpunk 2077" / "bin" / "x64"
    game_dir.mkdir(parents=True)
    exe = game_dir / "Cyberpunk2077.exe"
    exe.write_bytes(b"MZ" + b"\x00" * 4096)
    (game_dir / "libxess.dll").write_bytes(b"game-xess")
    (game_dir / "libxess_fg.dll").write_bytes(b"game-xess-fg")
    (game_dir / "libxell.dll").write_bytes(b"game-xell")
    return GameInfo(
        name="Cyberpunk 2077",
        source="Steam",
        install_dir=str(game_dir.parent.parent),
        target_dir=str(game_dir),
        exe_path=str(exe),
        exe_name="Cyberpunk2077.exe",
        qualification=QualificationStatus.QUALIFIED,
    )


def test_mode_a_keeps_game_imported_xess_runtimes(tmp_path):
    game = _make_cyberpunk_like(tmp_path)
    manifest = PatchManifest(
        app_version="3.1.4",
        game_name=game.name,
        target_exe=game.exe_path,
        target_dir=game.target_dir,
        active_backend=BackendType.STANDALONE.value,
        installed_version="latest",
    )

    engine = PatchEngine(updater=ComponentUpdater())
    ok, err = engine._apply_standalone_patch(game, manifest)
    assert ok, err

    target = Path(game.target_dir)
    assert (target / "libxess_fg.dll").exists(), "游戏静态导入的 libxess_fg.dll 不能被清理"
    assert (target / "libxell.dll").exists(), "游戏静态导入的 libxell.dll 不能被清理"
    assert (target / "libxess.dll").exists()

    rb_ok, rb_err = RollbackEngine().rollback(str(target), clean_all=True)
    assert rb_ok, rb_err
    assert (target / "libxess_fg.dll").exists()
    assert (target / "libxell.dll").exists()
