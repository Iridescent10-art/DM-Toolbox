# -*- coding: utf-8 -*-
"""
v1.2.6 verification: patch-state truth after switching backends / restoring.

Reproduces the reported bug:
- Patch Mode C, then Mode B, then "一键还原官方真实文件".
- The files were removed, but the custom game entry kept `is_patched=True` and
  `patched_backend=optiscaler`, so the UI "jumped back" to Mode C after a refresh.

Covers:
1. `GameCacheManager.reconcile_patch_state` trusts the on-disk manifest.
2. `GameCacheManager.update_patch_state` persists patch/restore immediately.
3. Switching C -> B leaves no OptiScaler config/proxy behind.
4. Restore removes the manifest and all deployed files.
"""

import json
import sys
import tempfile
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "apps" / "app2_mfg"))

from core.models import GameInfo, PatchManifest, QualificationStatus, BackendType
from core.game_cache import GameCacheManager, get_cache_file
from core.updater import ComponentUpdater
from core.patcher import PatchEngine
from core.rollback import RollbackEngine


def _game(target_dir: Path) -> GameInfo:
    return GameInfo(
        name="测试游戏",
        source="手动自定义",
        install_dir=str(target_dir),
        target_dir=str(target_dir),
        exe_path=str(target_dir / "yysls.exe"),
        exe_name="yysls.exe",
        qualification=QualificationStatus.QUALIFIED,
        streamline_ver="2.11.1",
        dlssg_ver="310.9.1.0",
    )


def test_1_reconcile_trusts_manifest():
    print("\n--- Test 1: [缓存状态必须与磁盘清单一致] ---")
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        g = _game(td)
        g.is_patched = True
        g.patched_backend = "optiscaler"
        g.installed_version = "latest"

        # No manifest -> must be reported as unpatched (this was the bug)
        GameCacheManager.reconcile_patch_state([g])
        assert g.is_patched is False
        assert g.patched_backend is None
        assert g.installed_version is None

        # Manifest says mavismmg -> must override stale optiscaler
        (td / ".mfg_patch_manifest.json").write_text(
            PatchManifest(game_name=g.name, target_dir=str(td), active_backend="mavismmg",
                          installed_version="1.4.4").to_json(),
            encoding="utf-8",
        )
        g.is_patched = False
        g.patched_backend = None
        GameCacheManager.reconcile_patch_state([g])
        assert g.is_patched is True
        assert g.patched_backend == "mavismmg"
        assert g.installed_version == "1.4.4"

    print("  -> 无清单=未修补，有清单=以清单后端为准！")


def test_2_update_patch_state_roundtrip():
    print("\n--- Test 2: [补丁/还原后立即持久化状态] ---")
    import core.game_cache as gc

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        cache_file = td / "mfg_game_cache.json"
        original = gc.get_cache_file
        gc.get_cache_file = lambda: cache_file
        try:
            cache_file.write_text(json.dumps({
                "last_selected_exe": str(td / "yysls.exe"),
                "custom_added_games": [{
                    "name": "测试游戏", "source": "手动自定义",
                    "install_dir": str(td), "target_dir": str(td),
                    "exe_path": str(td / "yysls.exe"), "exe_name": "yysls.exe",
                    "qualification": "QUALIFIED",
                    "is_patched": True, "patched_backend": "optiscaler",
                    "installed_version": "latest",
                }],
                "scanned_games_cache": [],
            }, ensure_ascii=False), encoding="utf-8")

            assert gc.GameCacheManager.update_patch_state(str(td / "yysls.exe"), False) is True
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            entry = data["custom_added_games"][0]
            assert entry["is_patched"] is False
            assert entry["patched_backend"] is None

            assert gc.GameCacheManager.update_patch_state(str(td / "yysls.exe"), True, "mavismmg", "1.4.4") is True
            entry = json.loads(cache_file.read_text(encoding="utf-8"))["custom_added_games"][0]
            assert entry["is_patched"] is True and entry["patched_backend"] == "mavismmg"
        finally:
            gc.get_cache_file = original

    print("  -> 还原/修补后缓存即时更新，重启不会回跳！")


def test_3_switch_c_to_b_then_restore():
    print("\n--- Test 3: [C → B → 还原 的完整文件链] ---")
    updater = ComponentUpdater()
    engine = PatchEngine(updater)
    rollback = RollbackEngine()

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "yysls.exe").write_bytes(b"FAKE_EXE")
        (td / "sl.interposer.dll").write_bytes(b"FAKE_SL")
        game = _game(td)

        # 1) Mode C
        ok, msg = engine.patch_game(game, BackendType.OPTISCALER_FSR)
        assert ok, f"Mode C patch failed: {msg}"
        assert (td / ".mfg_patch_manifest.json").exists()
        assert (td / "OptiScaler.ini").exists()
        c_proxies = [n for n in ("winmm.dll", "dxgi.dll", "version.dll") if (td / n).exists()]
        assert c_proxies, "Mode C must deploy a proxy"

        # 2) Mode B over C (patch_game rolls C back first)
        ok, msg = engine.patch_game(game, BackendType.RESHADE_ADDON)
        assert ok, f"Mode B patch failed: {msg}"
        manifest = json.loads((td / ".mfg_patch_manifest.json").read_text(encoding="utf-8"))
        assert manifest["active_backend"] == "mavismmg", manifest["active_backend"]
        assert not (td / "OptiScaler.ini").exists(), "Mode B must purge OptiScaler.ini"
        for proxy in ("winmm.dll", "version.dll", "dinput8.dll", "wininet.dll"):
            p = td / proxy
            if p.exists():
                assert b"OptiScaler" not in p.read_bytes()[:2_000_000], f"{proxy} still hosts OptiScaler"
        assert (td / "dxgi.dll").exists(), "Mode B must deploy ReShade dxgi.dll"

        # 3) Restore
        ok, msg = rollback.rollback(str(td), "yysls.exe")
        assert ok, f"Restore failed: {msg}"
        assert not (td / ".mfg_patch_manifest.json").exists(), "manifest must be removed"
        assert not (td / "dxgi.dll").exists(), "ReShade dxgi.dll must be removed"
        assert not (td / "renodx-mfgunlock.addon64").exists()
        assert not (td / "OptiScaler.ini").exists()

        # 4) The game object must now be detected as clean
        game.is_patched = True
        game.patched_backend = "optiscaler"
        GameCacheManager.reconcile_patch_state([game])
        assert game.is_patched is False and game.patched_backend is None

    print("  -> 模式切换与还原后文件/清单/状态全部一致，不再回跳 OptiScaler！")


def test_4_scanner_detects_large_reshade():
    print("\n--- Test 4: [扫描器识别 4MB 之后的 ReShade 签名] ---")
    from core.scanner import GameScanner

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "game.exe").write_bytes(b"MZ" + b"\x00" * 128)
        (td / "ReShade.ini").write_text("[GENERAL]\nTutorialProgress=4\n", encoding="utf-8")
        (td / "dxgi.dll").write_bytes(b"\x00" * (4 * 1024 * 1024 + 110_000) + b"ReShade 6.8.0")

        game = GameScanner().analyze_game_directory("测试游戏", "Custom", str(td))
        assert game.has_reshade is True, "scanner missed ReShade signature beyond 1MB/4MB"

    print("  -> 扫描器正确识别大体积 ReShade 底座，UI 可显示「ReShade 框架就绪」！")


def main():
    test_1_reconcile_trusts_manifest()
    test_2_update_patch_state_roundtrip()
    test_3_switch_c_to_b_then_restore()
    test_4_scanner_detects_large_reshade()
    print("\n==========================================")
    print("ALL v1.2.6 PATCH-STATE TRUTH TESTS PASSED (4/4)!")
    print("==========================================")


if __name__ == "__main__":
    main()
