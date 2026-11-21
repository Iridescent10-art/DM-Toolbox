# -*- coding: utf-8 -*-
"""小黑盒 helper 运行时拦截（IFEO + C# shim）基础检查。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "apps" / "app1_hardware"))

import heybox_helper_ifEO as h  # noqa: E402


def test_shim_executable_exists():
    src = h._shim_source()
    assert src is not None and src.exists(), "安装包必须包含 HeyboxHelperShim.exe"
    assert src.stat().st_size > 1024


def test_status_never_raises():
    assert isinstance(h.ifEO_status(), str)


def test_find_packages_returns_paths():
    pkgs = h.find_helper_packages()
    assert isinstance(pkgs, list)
    for p in pkgs[:3]:
        assert (p / "native" / "x64" / h.HELPER_NAME).exists()
