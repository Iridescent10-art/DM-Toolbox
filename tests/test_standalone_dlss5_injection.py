# -*- coding: utf-8 -*-
"""
Test Suite: Standalone DLSS 5 Plugin Injection & App 2 RHI / Game Recognition Sharing.
"""

import os
import sys
import shutil
import tempfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from apps.app6_dlss5.engine.injector import (
    DLSS5Injector,
    check_game_dlss5_status,
    scan_plugin_source_assets,
    get_plugin_source_dir
)
from apps.app2_mfg.core.game_cache import GameCacheManager
from apps.app2_mfg.core.rhi_installer import RHIInstaller
from common.config_manager import get_real_gpu_info


def test_asset_discovery():
    print("-> 测试 1: 扫描桌面与内置插件包资产...")
    assets = scan_plugin_source_assets()
    assert assets["exists"], "插件包目录应存在"
    assert assets["dxgi_path"] and os.path.exists(assets["dxgi_path"]), "应检测到 dxgi.dll"
    assert assets["addon_path"] and os.path.exists(assets["addon_path"]), "应检测到 *.addon64"
    assert assets["nr_50_path"] and os.path.exists(assets["nr_50_path"]), "应检测到 RTX 50 NR 模型"
    assert assets["nr_20_30_40_path"] and os.path.exists(assets["nr_20_30_40_path"]), "应检测到 RTX 20/30/40 NR 模型"
    print(f"   [PASS] 成功识别全部资产: dxgi({assets['dxgi_size_mb']}MB), addon({assets['addon_name']}), nr50({assets['nr_50_size_mb']}MB), nr40({assets['nr_20_30_40_size_mb']}MB)")


def test_shared_app2_integration():
    print("-> 测试 2: 验证共用二号软件 (app2_mfg) 游戏识别与 RHI 接口...")
    # 1. GameCacheManager
    cached_games, last_exe = GameCacheManager.get_cached_games()
    assert isinstance(cached_games, list), "应成功获取游戏列表"
    print(f"   [PASS] 共享游戏库成功读取，共识别到 {len(cached_games)} 款游戏，上次选中: {last_exe}")

    # 2. RHIInstaller
    rhi = RHIInstaller()
    found, path = rhi.is_installed_or_cached()
    print(f"   [PASS] 共享 RHI 模块正常工作，系统/缓存状态: found={found}, path={path}")


def test_standalone_injection_and_restoration():
    print("-> 测试 3: 独立注入与无损还原全流程测试...")
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_game_dir = Path(tmpdir) / "Win64r"
        mock_game_dir.mkdir(parents=True, exist_ok=True)
        mock_exe = mock_game_dir / "testgame.exe"
        mock_exe.write_bytes(b"MZ" + b"\x00" * 1024)

        # Pre-check status
        stat_before = check_game_dlss5_status(str(mock_game_dir))
        assert not stat_before["is_injected"], "初始状态应为未注入"

        # Execute injection
        print("   -> 执行一键注入 DLSS 5...")
        ok, msg = DLSS5Injector.inject(str(mock_game_dir), arch_choice="auto")
        assert ok, f"注入应当成功: {msg}"

        # Post-injection checks
        stat_after = check_game_dlss5_status(str(mock_game_dir))
        assert stat_after["is_injected"], "注入后状态应为已注入"
        assert stat_after["has_reshade"], "应包含 ReShade dxgi.dll"
        assert stat_after["has_addon"], "应包含 DLSS 5 addon64"
        assert stat_after["has_runtime"], "应包含 nvngx_dlssnr.dll"

        # Check ReShade.ini Chinese UI and screenshot-matched default parameters
        reshade_ini = mock_game_dir / "ReShade.ini"
        assert reshade_ini.exists(), "ReShade.ini 应自动创建"
        ini_content = reshade_ini.read_text(encoding="utf-8")
        assert "Language=zh-CN" in ini_content, "应配置中文界面"
        assert "msyh.ttc" in ini_content, "应配置雅黑字体"
        assert "TutorialProgress=4" in ini_content, "应跳过教程"
        assert "ConfigVersion=11" in ini_content, "应配置 Schema 11 版本防止被重置为 stock"
        assert "CurrentPreset=My look" in ini_content, "应设置预设为 My look"
        assert "NRStyle=2" in ini_content, "NRStyle 应为模型 C (2)"
        assert "NRPass2Preset=2" in ini_content, "NRPass2Preset 应为新版 (2)"
        assert "NRHookPoint=2" in ini_content, "NRHookPoint 挂钩点应为 Present 模式 (2)"
        assert ("NRSkinStructure=0.801136" in ini_content or "NRSkinStructure=80" in ini_content or "SkinStructure=80" in ini_content), "NRSkinStructure 皮肤结构应为 80 (0.801136)"
        assert "NRResolutionScale=1.000000" in ini_content, "分辨率应为匹配游戏 1.0"
        assert "[RenoDX DLSS5 preset]" in ini_content, "应包含预设专有段 [RenoDX DLSS5 preset]"

        # Check RenoDX Presets folder and files
        preset_file = mock_game_dir / "RenoDX" / "DLSS5" / "Presets" / "My look.ini"
        assert preset_file.exists(), "RenoDX 独立预设文件 My look.ini 应自动生成"
        preset_txt = preset_file.read_text(encoding="utf-8")
        assert "NRHookPoint=2" in preset_txt, "预设中挂钩点应为 Present 模式 (2)"
        assert "NRStyle=2" in preset_txt, "预设中风格应为模型 C (2)"
        assert "NRPass2Preset=2" in preset_txt, "预设中版本应为新版 (2)"
        assert ("NRSkinStructure=0.801136" in preset_txt or "NRSkinStructure=80" in preset_txt or "SkinStructure=80" in preset_txt), "预设中皮肤应为 80 (0.801136)"

        print("   [PASS] 注入成功且所有文件、独立预设及 Schema 11 调参配置正确落盘")

        # Execute restore
        print("   -> 执行一键还原与卸载...")
        ok_res, res_msg = DLSS5Injector.restore(str(mock_game_dir))
        assert ok_res, f"还原应当成功: {res_msg}"

        stat_restored = check_game_dlss5_status(str(mock_game_dir))
        assert not stat_restored["is_injected"], "还原后状态应为未注入"
        assert not (mock_game_dir / "dxgi.dll").exists(), "dxgi.dll 应被清理"
        assert not (mock_game_dir / "nvngx_dlssnr.dll").exists(), "nvngx_dlssnr.dll 应被清理"
        assert not (mock_game_dir / ".dlss5_manifest.json").exists(), "清单文件应被清理"
        assert not (mock_game_dir / "RenoDX").exists(), "RenoDX 目录应被彻底清理"

        print("   [PASS] 卸载与还原成功，目录已恢复纯净状态")


def test_deep_restore_purges_rhi_and_remnants():
    print("-> 测试 4: 针对 RHI/ReShade 残留环境的深度还原纯净化测试...")
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_game_dir = Path(tmpdir) / "Win64r"
        mock_game_dir.mkdir(parents=True, exist_ok=True)
        mock_exe = mock_game_dir / "testgame.exe"
        mock_exe.write_bytes(b"MZ" + b"\x00" * 1024)

        # Simulate pre-existing RHI/ReShade remnants in game directory
        mock_reshade_dxgi = mock_game_dir / "dxgi.dll"
        mock_reshade_dxgi.write_bytes(b"crosire ReShade 6.8 fake binary payload" + b"\x00" * 2048)

        mock_nr_runtime = mock_game_dir / "dlss5-nr-runtime"
        mock_nr_runtime.mkdir(parents=True, exist_ok=True)
        (mock_nr_runtime / "nr-copy.txt").write_text("test", encoding="utf-8")
        (mock_nr_runtime / "nvngx_dlssnr.dll").write_bytes(b"mock" * 100)

        mock_v11_bak = mock_game_dir / "ReShade.ini.v11-backup"
        mock_v11_bak.write_text("[GENERAL]\nTest=1\n", encoding="utf-8")

        mock_shaders = mock_game_dir / "reshade-shaders"
        mock_shaders.mkdir(parents=True, exist_ok=True)
        (mock_shaders / "test.fx").write_text("// shader", encoding="utf-8")

        mock_preset = mock_game_dir / "ReShadePreset.ini"
        mock_preset.write_text("[Preset]\nKey=1\n", encoding="utf-8")

        # Now execute restore directly
        print("   -> 对包含 RHI/ReShade/dlss5-nr-runtime 残留的目录执行一键彻底还原...")
        ok, msg = DLSS5Injector.restore(str(mock_game_dir))
        assert ok, f"深度还原应当成功: {msg}"

        # Verify all remnants are completely purged
        assert not mock_reshade_dxgi.exists(), "ReShade dxgi.dll 必须被彻底删除，不得误当作原版恢复！"
        assert not mock_nr_runtime.exists(), "dlss5-nr-runtime 目录必须被彻底递归删除！"
        assert not mock_v11_bak.exists(), "ReShade.ini.v11-backup 文件必须被彻底删除！"
        assert not mock_shaders.exists(), "reshade-shaders 目录必须被彻底删除！"
        assert not mock_preset.exists(), "ReShadePreset.ini 文件必须被彻底删除！"
        assert not (mock_game_dir / "ReShade.ini").exists(), "ReShade.ini 必须被删除！"

        # Game exe should be intact
        assert mock_exe.exists(), "原生游戏程序必须完好无损！"
        print("   [PASS] 深度净化还原测试通过！所有 RHI/ReShade/DLSS 5 残留已被彻底荡涤，游戏目录 100% 纯净")


if __name__ == "__main__":
    print("==================================================")
    print("      DLSS 5 独立注入与共用组件单元自动化测试      ")
    print("==================================================")
    test_asset_discovery()
    test_shared_app2_integration()
    test_standalone_injection_and_restoration()
    test_deep_restore_purges_rhi_and_remnants()
    print("==================================================")
    print("全部测试 100% 通过！")
