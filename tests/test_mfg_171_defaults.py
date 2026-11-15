# -*- coding: utf-8 -*-
"""MFG Unlocker 1.7.1：全显卡默认模式 A，AMD 默认 XeSS 多帧生成。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "apps" / "app2_mfg"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from apps.app2_mfg.core import updater as upd  # noqa: E402
from apps.app2_mfg.core.models import BackendType  # noqa: E402
from apps.app2_mfg.core.patcher import PatchEngine  # noqa: E402
from apps.app2_mfg.core.utils import is_amd_gpu  # noqa: E402
from core import optiscaler_config  # noqa: E402


def test_amd_detection():
    assert is_amd_gpu("AMD Radeon RX 7900 XTX") is True
    assert is_amd_gpu("AMD Radeon(TM) Graphics") is True
    assert is_amd_gpu("NVIDIA GeForce RTX 4070") is False
    assert is_amd_gpu("Intel Arc B580") is False


def test_smart_auto_defaults_to_mode_a_for_every_gpu():
    for gpu in ("NVIDIA GeForce RTX 4070", "NVIDIA GeForce RTX 3080",
                "NVIDIA GeForce RTX 2080 Ti", "AMD Radeon RX 7900 XTX"):
        assert PatchEngine.resolve_smart_auto_backend(gpu) == BackendType.STANDALONE


def test_amd_default_turns_on_xemfg(monkeypatch):
    state = {"preset": {"multiplier": 3, "xemfg_standalone": False}, "saved": False}

    monkeypatch.setattr(optiscaler_config, "load_mode_a_preset", lambda: dict(state["preset"]), raising=False)

    def _save(preset):
        state["preset"] = dict(preset)
        state["saved"] = True

    monkeypatch.setattr(optiscaler_config, "save_mode_a_preset", _save, raising=False)

    PatchEngine._ensure_amd_xemfg_default()
    assert state["preset"]["xemfg_standalone"] is True
    assert state["saved"] is True


def test_version_compare_prefers_newer_dashdogy():
    assert upd._is_newer_tag("v1.7.1", "v1.7.0") is True
    assert upd._is_newer_tag("v1.7.0", "v1.7.1") is False
    assert upd._is_newer_tag("v1.7.1", None) is True
    assert upd._is_newer_tag("nightly-20261023", "nightly-20261001") is True
