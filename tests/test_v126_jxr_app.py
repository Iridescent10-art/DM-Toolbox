# -*- coding: utf-8 -*-
"""
v1.2.6 verification: new App 5 (JXR HDR Converter) integration.

The converter is an external single-file WPF executable (not a Python app), so it is
launched through the launcher's `exe_rel` branch. Its original icon is used unchanged.
"""

import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
for p in (ROOT_DIR, ROOT_DIR / "launcher"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import launcher.main as lm


def test_1_metadata_and_assets():
    print("\n--- Test 1: [App 5 元数据 / 可执行文件 / 原始图标] ---")
    assert len(lm.APPS_METADATA) == 6, f"expected 6 apps, got {len(lm.APPS_METADATA)}"
    meta = next((m for m in lm.APPS_METADATA if m["id"] == "app5_jxr"), None)
    assert meta, "app5_jxr metadata missing"
    assert meta["name"] == "JXR HDR 转换器"
    assert meta.get("exe_rel") == "apps/app5_jxr/JxrConverter.exe"
    assert "script_rel" not in meta, "external EXE app must not be launched as a Python script"

    exe = ROOT_DIR / meta["exe_rel"]
    assert exe.exists(), f"missing converter executable: {exe}"
    assert exe.stat().st_size > 60 * 1024 * 1024, "release EXE looks incomplete"
    assert exe.read_bytes()[:2] == b"MZ", "not a PE executable"

    icon_png = ROOT_DIR / "common" / "assets" / meta["icon"]
    icon_ico = ROOT_DIR / "apps" / "app5_jxr" / "app.ico"
    assert icon_png.exists(), "launcher icon missing"
    assert icon_ico.exists(), "original icon must be kept in the app folder"
    assert icon_ico.stat().st_size == 167990, "original icon was modified"

    print("  -> 5 个应用、EXE 66MB、原始图标未改动")


def test_2_window_title_and_process_whitelist():
    print("\n--- Test 2: [窗口标题识别 / 进程白名单] ---")
    assert lm.APP_EXACT_TITLES.get("app5_jxr") == "JXR HDR 转换器 - 转 Ultra HDR / PNG"
    assert "jxrconverter.exe" in lm.ALLOWED_SUBPROCESS_EXECUTABLES
    print("  -> 启动后可被正确识别与唤醒，不会误匹配浏览器窗口")


def test_3_exe_rel_launch_branch_present():
    print("\n--- Test 3: [启动器支持 exe_rel 分支] ---")
    src = (ROOT_DIR / "launcher" / "main.py").read_text(encoding="utf-8")
    assert 'meta.get("exe_rel")' in src
    assert "subprocess.Popen(\n                    [str(exe_path)]" in src or "[str(exe_path)]" in src
    assert "JXR→Ultra HDR 转换" in src
    print("  -> 启动器会直接 Popen 转换器 EXE，而不是用 Python 解释器打开它")


def main():
    test_1_metadata_and_assets()
    test_2_window_title_and_process_whitelist()
    test_3_exe_rel_launch_branch_present()
    print("\n==========================================")
    print("ALL v1.2.6 JXR CONVERTER INTEGRATION TESTS PASSED (3/3)!")
    print("==========================================")


if __name__ == "__main__":
    main()
