# -*- coding: utf-8 -*-
"""小黑盒桌面版（HeyboxDesktop 2.x）hardware.mjs 注入逻辑。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "apps" / "app1_hardware"))

import heybox_desktop_patch as h  # noqa: E402

SAMPLE = 'var Ct=function(e){return {getInventory(){return {memory:{totalBytes:1}}},getReportInfo(){return {memory:{memory_size:1}}}}};var Pt=async e=>{};export{Ct as create,Pt as dispose};'


def test_inject_replaces_export_and_is_idempotent(tmp_path):
    f = tmp_path / "hardware.mjs"
    f.write_text(SAMPLE, encoding="utf-8")

    assert h.patch_hardware_module(f) is True
    text = f.read_text(encoding="utf-8")
    assert h.MARKER in text
    assert "export{Ct as create" not in text
    assert "export { __tbxCreate as create, Pt as dispose }" in text
    assert (tmp_path / "hardware.mjs.tbx_bak").exists()

    # 已注入过则不重复注入
    assert h.patch_hardware_module(f) is False


def test_restore_brings_original_back(tmp_path):
    f = tmp_path / "hardware.mjs"
    f.write_text(SAMPLE, encoding="utf-8")
    h.patch_hardware_module(f)
    assert h.restore_hardware_module(f) is True
    assert f.read_text(encoding="utf-8") == SAMPLE


def test_missing_export_raises(tmp_path):
    f = tmp_path / "hardware.mjs"
    f.write_text("var x=1;", encoding="utf-8")
    try:
        h.patch_hardware_module(f)
    except RuntimeError:
        pass
    else:
        raise AssertionError("缺少 export 时应抛错，避免把文件写坏")
