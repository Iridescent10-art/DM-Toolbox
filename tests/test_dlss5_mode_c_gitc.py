# -*- coding: utf-8 -*-
"""DLSS 5 模式 C：GITC Uplift 底座（部署 / 状态识别 / 卸载）。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.app6_dlss5.engine import injector as inj  # noqa: E402


def test_scan_finds_gitc_uplift_assets():
    assets = inj.scan_plugin_source_assets(inj.LOCAL_ASSETS_DIR, mode="MODE_C")
    assert assets["mode_c_exists"] is True
    assert Path(assets["addon_path"]).name == "gitc-uplift.addon64"
    assert assets["addon_name"] == "gitc-uplift.addon64"


def test_mode_c_inject_deploys_gitc_layout_and_restore_cleans(tmp_path):
    game = tmp_path / "game"
    game.mkdir()
    (game / "game.exe").write_bytes(b"MZ" + b"\x00" * 64)

    ok, msg = inj.DLSS5Injector.inject(str(game), mode="MODE_C", hook_point="0")
    assert ok is True, msg

    assert (game / "gitc-uplift.addon64").exists()
    assert (game / "gitc-uplift.addon32").exists()
    assert (game / "gitc-uplift-helper64.exe").exists()
    assert (game / "GITC-Uplift" / "nvngx_dlssnr.dll").exists()
    assert (game / "Uplift.fx").exists()
    assert (game / "UpliftMask.fx").exists()
    # 模式 C 不能把 NR 运行库放到游戏根目录（50 系驱动会抢先加载）
    assert not (game / "nvngx_dlssnr.dll").exists()

    stat = inj.check_game_dlss5_status(str(game))
    assert stat["detected_mode"] == "MODE_C"
    assert "GITC Uplift" in stat["mode_status_display"]

    ok, msg = inj.DLSS5Injector.restore(str(game))
    assert ok is True, msg
    assert not (game / "gitc-uplift.addon64").exists()
    assert not (game / "gitc-uplift.addon32").exists()
    assert not (game / "gitc-uplift-helper64.exe").exists()
    assert not (game / "GITC-Uplift").exists()
    assert not (game / "Uplift.fx").exists()
    assert not (game / "UpliftMask.fx").exists()


def test_mode_c_cleans_reno_dx_addons_on_switch(tmp_path):
    game = tmp_path / "game"
    game.mkdir()
    (game / "game.exe").write_bytes(b"MZ" + b"\x00" * 64)
    (game / "renodx-dlss.addon64").write_bytes(b"\x00" * 16)

    ok, msg = inj.DLSS5Injector.inject(str(game), mode="MODE_C", hook_point="0")
    assert ok is True, msg
    assert not (game / "renodx-dlss.addon64").exists()
    assert (game / "gitc-uplift.addon64").exists()
