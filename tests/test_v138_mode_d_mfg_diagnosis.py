# -*- coding: utf-8 -*-
"""
DM-Toolbox v1.3.8: Mode D (DLSSG-SM86) multi-frame diagnosis.

Mode D only raises the advertised ceiling ([FrameGeneration] MaxGeneratedFrames);
the number of generated frames is requested by the game's Streamline plugin via
DLSSG.MultiFrameCount. These tests pin down the explanations the tool now shows.
"""

import sys
import tempfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
for p in (ROOT_DIR, ROOT_DIR / "apps" / "app2_mfg"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from core.utils import (
    describe_mode_d_mfg_status,
    detect_streamline_mfg_support,
    find_streamline_fg_plugin,
    read_mode_d_log_summary,
)


def _write_plugin(td: Path, mfg_capable: bool, subdir: str = "Streamline") -> Path:
    folder = td / subdir if subdir else td
    folder.mkdir(parents=True, exist_ok=True)
    plugin = folder / "sl.dlss_g.dll"
    payload = b"MZ" + b"\x00" * 64
    if mfg_capable:
        payload += b"DLSSG.MultiFrameCount\x00DLSSG.MultiFrameCountMax\x00numFramesToGenerate\x00"
    plugin.write_bytes(payload)
    return plugin


def test_mfg_capable_plugin_explanation():
    print("\n--- Test 1: [支持 MFG 的插件] ---")
    with tempfile.TemporaryDirectory() as tmp:
        td = Path(tmp)
        plugin = _write_plugin(td, mfg_capable=True)
        assert find_streamline_fg_plugin(td) == str(plugin)
        assert detect_streamline_mfg_support(td) is True

        msg = describe_mode_d_mfg_status(td)
        assert "支持 MFG" in msg
        assert "由游戏请求决定" in msg, "必须说明倍率由游戏请求，而不是由 INI 强制"
        print("   [PASS] 支持 MFG 的插件会提示「上限已写入、实际倍率看游戏请求」")


def test_legacy_plugin_cannot_mfg():
    print("\n--- Test 2: [旧代 2X-only 插件] ---")
    with tempfile.TemporaryDirectory() as tmp:
        td = Path(tmp)
        _write_plugin(td, mfg_capable=False)
        assert detect_streamline_mfg_support(td) is False

        msg = describe_mode_d_mfg_status(td)
        assert "旧代插件" in msg
        assert "只能 2X" in msg
        assert "模式 A" in msg and "模式 C" in msg, "必须给出可用的替代模式"
        print("   [PASS] 旧代插件会明确说明只能 2X，并指向模式 A / 模式 C")


def test_missing_plugin_and_log_excerpt():
    print("\n--- Test 3: [缺少插件 / 日志回显] ---")
    with tempfile.TemporaryDirectory() as tmp:
        td = Path(tmp)
        assert detect_streamline_mfg_support(td) is None
        assert "未找到" in describe_mode_d_mfg_status(td)

        # A previous session's log must be echoed so the user can see the ceiling.
        log_dir = td / "dlssg_sm86" / "logs"
        log_dir.mkdir(parents=True)
        (log_dir / "session.log").write_text(
            "[INFO] configuration_warning{section=FrameGeneration,key=MaxGeneratedFrames}\n"
            "[INFO] fg_gate_capability DLSSG.MultiFrameCountMax=3\n",
            encoding="utf-8",
        )
        excerpt = read_mode_d_log_summary(td)
        assert excerpt and "MultiFrameCountMax=3" in excerpt
        assert "MultiFrameCountMax=3" in describe_mode_d_mfg_status(td)
        print("   [PASS] 缺少插件时给出说明，历史日志中的 MultiFrameCountMax 会被回显")


if __name__ == "__main__":
    test_mfg_capable_plugin_explanation()
    test_legacy_plugin_cannot_mfg()
    test_missing_plugin_and_log_excerpt()
    print("\nALL MODE D MFG DIAGNOSIS TESTS PASSED")
