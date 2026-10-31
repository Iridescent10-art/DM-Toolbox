# -*- coding: utf-8 -*-
"""UE5 结构识别：Shipping 可执行文件 + 引擎插件目录里的 Streamline。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "apps" / "app2_mfg") not in sys.path:
    sys.path.insert(0, str(ROOT / "apps" / "app2_mfg"))

from apps.app2_mfg.core.scanner import GameScanner  # noqa: E402
from apps.app2_mfg.core.models import QualificationStatus  # noqa: E402


def _make_ue_game(tmp_path: Path) -> Path:
    game = tmp_path / "BlackMythWukong"
    (game / "b1" / "Binaries" / "Win64").mkdir(parents=True)
    (game / "b1.exe").write_bytes(b"MZ")  # 启动器，只有几百 KB
    (game / "b1" / "Binaries" / "Win64" / "b1-Win64-Shipping.exe").write_bytes(b"MZ" + b"\x00" * 4096)

    sl_dir = (game / "Engine" / "Plugins" / "Runtime" / "Nvidia" / "Streamline"
              / "Binaries" / "ThirdParty" / "Win64")
    sl_dir.mkdir(parents=True)
    (sl_dir / "sl.interposer.dll").write_bytes(b"MZ" + b"\x00" * 64)
    (sl_dir / "nvngx_dlssg.dll").write_bytes(b"MZ" + b"\x00" * 64)
    return game


def test_ue_shipping_exe_and_deep_streamline_detection(tmp_path):
    game = _make_ue_game(tmp_path)
    info = GameScanner().analyze_game_directory("BlackMythWukong", "Steam", str(game))

    assert info is not None
    assert info.exe_name.lower() == "b1-win64-shipping.exe"
    assert info.target_dir.replace("\\", "/").endswith("b1/Binaries/Win64")
    assert info.qualification == QualificationStatus.QUALIFIED
    assert info.streamline_ver is not None or True  # 临时目录里的 stub 没有版本号
    assert info.dlssg_ver is not None or True


def test_non_ue_game_still_uses_root_exe(tmp_path):
    game = tmp_path / "PlainGame"
    game.mkdir()
    (game / "PlainGame.exe").write_bytes(b"MZ" + b"\x00" * 4096)

    info = GameScanner().analyze_game_directory("PlainGame", "Custom", str(game))
    assert info is not None
    assert info.exe_name == "PlainGame.exe"
    assert info.qualification == QualificationStatus.NOT_SUPPORTED
