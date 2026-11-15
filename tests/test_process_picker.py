# -*- coding: utf-8 -*-
"""「从运行中的进程添加游戏」：候选过滤 + 进程枚举 + 对话框加载。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "apps" / "app2_mfg") not in sys.path:
    sys.path.insert(0, str(ROOT / "apps" / "app2_mfg"))

from common.process_scanner import _is_candidate, list_running_processes  # noqa: E402


def test_candidate_filter_rejects_launchers_and_system_tools():
    assert _is_candidate("b1-Win64-Shipping.exe", r"D:\game\BlackMythWukong\b1\Binaries\Win64\b1-Win64-Shipping.exe")
    assert _is_candidate("yysls.exe", r"D:\game\yysls\yysls_medium\Engine\Binaries\Win64r\yysls.exe")

    assert not _is_candidate("steam.exe", r"D:\Steam\steam.exe")
    assert not _is_candidate("explorer.exe", r"C:\Windows\explorer.exe")
    assert not _is_candidate("svchost.exe", r"C:\Windows\System32\svchost.exe")
    assert not _is_candidate("python.exe", r"C:\Python314\python.exe")
    assert not _is_candidate("unins000.exe", r"D:\game\unins000.exe")
    assert not _is_candidate("GameBar.exe", r"C:\Windows\SystemApps\GameBar.exe")


def test_list_running_processes_shape():
    rows = list_running_processes()
    assert isinstance(rows, list)
    for row in rows[:10]:
        assert set(row) >= {"pid", "name", "path", "has_window"}
        assert row["pid"] > 0
        assert row["path"].lower().endswith(".exe")
        assert "steam.exe" != row["name"].lower()
    # 有窗口的应排在无窗口的前面
    flags = [r["has_window"] for r in rows]
    if True in flags and False in flags:
        assert flags.index(True) < flags.index(False)
