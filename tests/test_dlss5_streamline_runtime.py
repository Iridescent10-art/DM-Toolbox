# -*- coding: utf-8 -*-
"""DLSS 5：游戏 Streamline 目录里的 NR 运行库同步（修复 50 系专用文件被优先加载）。"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.app6_dlss5.engine import injector as inj  # noqa: E402


def test_inject_replaces_streamline_nr_runtime_and_restore_puts_it_back(tmp_path):
    game = tmp_path / "bin"
    game.mkdir(parents=True)
    (game / "game.exe").write_bytes(b"MZ" + b"\x00" * 64)

    sl = game / "Streamline"
    sl.mkdir()
    stub = sl / "nvngx_dlssnr.dll"
    stub.write_bytes(b"stub-50-series-runtime")

    ok, msg = inj.DLSS5Injector.inject(str(game), mode="MODE_A", hook_point="0")
    assert ok is True, msg

    runtime_asset = inj.LOCAL_ASSETS_DIR / "runtimes" / "nvngx_dlssnr_rtx20_30_40.dll"
    assert stub.stat().st_size == runtime_asset.stat().st_size, "Streamline 里的运行库必须换成匹配架构版本"
    backup = sl / "nvngx_dlssnr.dll.dlss5_bak"
    assert backup.exists(), "替换前必须备份游戏原文件"
    assert backup.read_bytes() == b"stub-50-series-runtime"

    manifest = json.loads((game / ".dlss5_manifest.json").read_text(encoding="utf-8"))
    assert any("Streamline" in p for p in manifest.get("streamline_runtime_replaced", []))

    ok, msg = inj.DLSS5Injector.restore(str(game))
    assert ok is True, msg
    assert stub.read_bytes() == b"stub-50-series-runtime", "卸载后必须还原游戏原文件"
    assert not (sl / "nvngx_dlssnr.dll.dlss5_bak").exists()
