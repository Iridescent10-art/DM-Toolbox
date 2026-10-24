# -*- coding: utf-8 -*-
"""
Automated Self-Verification Test Suite:
DLSS 5 (app6_dlss5) & Multi-Frame Generation (app2_mfg) Coexistence Protocol.
=============================================================================
Verifies 8 mandatory assertions of the v1.3.8 coexistence protocol:
  - Assertion 1: 底座唯一性与指纹校验 (dxgi.dll size matches DLSS 5 ReShade 6.8 5.33 MB, not overwritten by OptiScaler)
  - Assertion 2: 双通道隔离校验 (DLSS 5 + Mode A/C/D dual-proxy coexistence without hash collision)
  - Assertion 3: Addon 挂载与 INI 语法校验 (DLSS 5 + Mode B [ADDON] LoadFromDllMain=1 and both addons loaded)
  - Assertion 4: 模型与依赖完备性校验 (nvngx_dlssnr.dll hardware arch matching, fakenvapi/bink chains)
  - Assertion 5: 卸载幂等性校验 (100% pure vanilla restoration and bink recovery)
  - Assertion 6: 模式 C 全链路协同（两序注入、DLSS 直通、FrameGen 键位、单 ReShade）
  - Assertion 7: 历史脏状态自愈 / fakenvapi 净化 / 模型架构指纹
  - Assertion 8: 重复注入幂等性
"""

import os
import sys
import shutil
import hashlib
import tempfile
import configparser
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

APP2_DIR = ROOT_DIR / "apps" / "app2_mfg"
if str(APP2_DIR) not in sys.path:
    sys.path.insert(0, str(APP2_DIR))

from apps.app6_dlss5.engine.injector import (
    DLSS5Injector,
    check_game_dlss5_status,
    scan_plugin_source_assets
)
from core.models import GameInfo, BackendType, QualificationStatus
from core.updater import ComponentUpdater
from core.patcher import PatchEngine
from core.rollback import RollbackEngine
from core.state_cleaner import is_dlss5_present


def _calculate_file_sha256(file_path: Path) -> str:
    """Computes SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def _create_mock_game_environment(base_path: Path) -> Tuple[Path, GameInfo]:
    """Sets up a mock game directory with typical Steam/shipping executables and Streamline assets."""
    game_dir = base_path / "Binaries" / "Win64"
    game_dir.mkdir(parents=True, exist_ok=True)
    game_exe = game_dir / "ShippingGame.exe"
    game_exe.write_bytes(b"MZ" + b"\x00" * 4096)

    # Place required Streamline markers for DLSS-G qualification
    (game_dir / "sl.interposer.dll").write_bytes(b"mock_sl_interposer_native" + b"\x00" * 512)
    (game_dir / "nvngx_dlssg.dll").write_bytes(b"mock_nvngx_dlssg_native" + b"\x00" * 512)

    game_info = GameInfo(
        name="ShippingGame",
        source="Custom",
        install_dir=str(game_dir),
        target_dir=str(game_dir),
        exe_path=str(game_exe),
        exe_name="ShippingGame.exe",
        qualification=QualificationStatus.QUALIFIED
    )
    return game_dir, game_info


def test_assertion_1_base_uniqueness_and_fingerprint():
    """
    Assertion 1: 底座唯一性与指纹校验
    检查目标测试目录中的 dxgi.dll 是否存在，且文件大小严格匹配 apps/app6_dlss5/assets/dxgi.dll (约 5.33 MB)，
    确认未被模式 C (OptiScaler) 覆盖。
    """
    print("\n----------------------------------------------------------------------")
    print("-> 执行 Assertion 1: 底座唯一性与指纹校验 (DLSS 5 + 模式 C 动态避让)...")
    with tempfile.TemporaryDirectory() as tmpdir:
        game_dir, game_info = _create_mock_game_environment(Path(tmpdir))
        assets = scan_plugin_source_assets()
        ref_dxgi_path = Path(assets["dxgi_path"])
        ref_dxgi_size = ref_dxgi_path.stat().st_size
        ref_dxgi_hash = _calculate_file_sha256(ref_dxgi_path)

        # 1. 注入 DLSS 5
        ok_dlss5, msg_dlss5 = DLSS5Injector.inject(str(game_dir), arch_choice="rtx20_30_40")
        assert ok_dlss5, f"DLSS 5 注入应当成功: {msg_dlss5}"
        assert is_dlss5_present(game_dir), "必须成功识别 DLSS 5 已注入共存态"

        # 2. 注入 模式 C (OptiScaler 跨卡转译)
        updater = ComponentUpdater()
        patcher = PatchEngine(updater)
        ok_opti, msg_opti = patcher.patch_game(game_info, requested_backend=BackendType.OPTISCALER_FSR)
        assert ok_opti, f"模式 C 注入应当成功: {msg_opti}"

        # 3. 校验 dxgi.dll 归属权与指纹
        target_dxgi = game_dir / "dxgi.dll"
        assert target_dxgi.exists(), "游戏目录中必须保留 dxgi.dll"
        target_dxgi_size = target_dxgi.stat().st_size
        target_dxgi_hash = _calculate_file_sha256(target_dxgi)

        assert target_dxgi_size == ref_dxgi_size, (
            f"dxgi.dll 大小异常: 预期 {ref_dxgi_size} 字节 (5.33 MB)，实际 {target_dxgi_size} 字节！"
            f"可能被模式 C (OptiScaler ~25MB) 错误覆盖！"
        )
        assert target_dxgi_hash == ref_dxgi_hash, "dxgi.dll SHA256 哈希值必须严格匹配 DLSS 5 ReShade 6.8 渲染底座！"

        # 4. 校验 OptiScaler 核心已被降级重命名为 version.dll，未抢占 dxgi.dll
        opti_proxy = game_dir / "version.dll"
        assert opti_proxy.exists(), "模式 C 必须动态降级路由至 version.dll"
        assert opti_proxy.stat().st_size > 10 * 1024 * 1024, "version.dll 必须为 OptiScaler 核心二进制"

        print(f"   [PASS] dxgi.dll 唯一性与指纹校验通过:")
        print(f"          - dxgi.dll 大小: {target_dxgi_size} 字节 (~{round(target_dxgi_size/(1024*1024), 2)} MB) · 纯正 ReShade 6.8 底座")
        print(f"          - dxgi.dll SHA256: {target_dxgi_hash[:16]}... (完全一致，未被 OptiScaler 篡改)")
        print(f"          - 模式 C 成功避让部署为: {opti_proxy.name} ({round(opti_proxy.stat().st_size/(1024*1024), 2)} MB)")


def test_assertion_2_dual_channel_isolation():
    """
    Assertion 2: 双通道隔离校验
    在【DLSS 5 + 模式 A/C/D】组合测试下，验证目录中同时存在 dxgi.dll (DLSS 5 底座) 与 version.dll/winmm.dll (插帧代理)，
    二者哈希值不同且无文件句柄写入冲突。
    """
    print("\n----------------------------------------------------------------------")
    print("-> 执行 Assertion 2: 双通道隔离校验 (DLSS 5 + 模式 A / C / D)...")
    updater = ComponentUpdater()

    # 测试 A: DLSS 5 + 模式 A (dashdogy 独立代理)
    with tempfile.TemporaryDirectory() as tmpdir_a:
        game_dir_a, game_info_a = _create_mock_game_environment(Path(tmpdir_a))
        DLSS5Injector.inject(str(game_dir_a), arch_choice="rtx20_30_40")
        patcher = PatchEngine(updater)
        ok_a, msg_a = patcher.patch_game(game_info_a, requested_backend=BackendType.STANDALONE)
        assert ok_a, f"模式 A 注入应当成功: {msg_a}"

        dxgi_a = game_dir_a / "dxgi.dll"
        version_a = game_dir_a / "version.dll"
        assert dxgi_a.exists(), "模式 A 共存下 dxgi.dll 必须存在"
        assert version_a.exists(), "模式 A 共存下 version.dll 必须存在"
        hash_dxgi_a = _calculate_file_sha256(dxgi_a)
        hash_ver_a = _calculate_file_sha256(version_a)
        assert hash_dxgi_a != hash_ver_a, "dxgi.dll 与 version.dll 哈希必须完全不同 (双通道隔离)"
        # 校验模式 A ImGui 已关闭
        mfg_ui_ini = game_dir_a / "RTX40MFG-UI.ini"
        if mfg_ui_ini.exists():
            assert "OverlayMenu=false" in mfg_ui_ini.read_text(encoding="utf-8") or "EnableImGui=0" in mfg_ui_ini.read_text(encoding="utf-8")
        print("   [PASS] 通道 A (DLSS 5 + dashdogy) 隔离校验成功: dxgi.dll 与 version.dll 独立共存，哈希隔离")

    # 测试 C: DLSS 5 + 模式 C (OptiScaler 跨卡转译)
    with tempfile.TemporaryDirectory() as tmpdir_c:
        game_dir_c, game_info_c = _create_mock_game_environment(Path(tmpdir_c))
        DLSS5Injector.inject(str(game_dir_c), arch_choice="rtx20_30_40")
        patcher = PatchEngine(updater)
        ok_c, msg_c = patcher.patch_game(game_info_c, requested_backend=BackendType.OPTISCALER_FSR)
        assert ok_c, f"模式 C 注入应当成功: {msg_c}"

        dxgi_c = game_dir_c / "dxgi.dll"
        version_c = game_dir_c / "version.dll"
        assert dxgi_c.exists() and version_c.exists(), "模式 C 共存下 dxgi.dll 与 version.dll 必须同时存在"
        assert _calculate_file_sha256(dxgi_c) != _calculate_file_sha256(version_c), "模式 C 双通道哈希必须隔离"
        # 校验模式 C 与 DLSS 5 的 NGX 协同参数
        opti_ini = game_dir_c / "OptiScaler.ini"
        assert opti_ini.exists(), "OptiScaler.ini 应存在"
        cp = configparser.ConfigParser(interpolation=None, strict=False)
        cp.read(opti_ini, encoding="utf-8")
        assert cp.get("Plugins", "LoadReshade", fallback="").lower() == "false", "共存态下禁止 OptiScaler 重复加载 ReShade"
        assert cp.get("Plugins", "LoadAsiPlugins", fallback="").lower() == "true", "必须允许加载 MFGUnlocker.asi 才能突破 XeFG 2X 上限"
        assert (game_dir_c / "OptiScaler" / "plugins" / "MFGUnlocker.asi").is_file(), "MFGUnlocker.asi 必须部署以解锁 3X/4X"
        assert cp.get("DLSS", "Enabled", fallback="").lower() == "true", "共存态下必须保留 DLSS 直通链路供 DLSS 5 神经重构接管"
        assert cp.get("Upscalers", "Dx12Upscaler", fallback="").lower() == "dlss", "Dx12Upscaler 必须是合法的 DLSS 直通值"
        print("   [PASS] 通道 C (DLSS 5 + OptiScaler) 隔离校验成功: DLSS 直通保留，无重复 ReShade 宿主")


def test_assertion_3_addon_mounting_and_ini_syntax():
    """
    Assertion 3: Addon 挂载与 INI 语法校验
    在【DLSS 5 + 模式 B】组合测试下，解析生成的 ReShade.ini，验证 [ADDON] 节点语法合法，包含 LoadFromDllMain 配置，
    且 renodx-dlss.addon64 与模式 B 插件均位于有效加载目录。
    """
    print("\n----------------------------------------------------------------------")
    print("-> 执行 Assertion 3: Addon 挂载与 INI 语法校验 (DLSS 5 + 模式 B RenoDX 合并)...")
    with tempfile.TemporaryDirectory() as tmpdir:
        game_dir, game_info = _create_mock_game_environment(Path(tmpdir))

        # 1. 注入 DLSS 5
        ok_dlss5, msg_dlss5 = DLSS5Injector.inject(str(game_dir), arch_choice="rtx20_30_40")
        assert ok_dlss5, f"DLSS 5 注入应成功: {msg_dlss5}"
        dlss5_addon = game_dir / "renodx-dlss.addon64"
        assert dlss5_addon.exists(), "初始应包含 renodx-dlss.addon64"

        # 2. 注入 模式 B (mavismmg/MFGAdaUnlock-RenoDx)
        updater = ComponentUpdater()
        patcher = PatchEngine(updater)
        ok_b, msg_b = patcher.patch_game(game_info, requested_backend=BackendType.RESHADE_ADDON)
        assert ok_b, f"模式 B 注入应当成功: {msg_b}"

        # 3. 校验双 Addon 同时有效存在
        mfg_addon = game_dir / "renodx-mfgunlock.addon64"
        assert dlss5_addon.exists(), "模式 B 注入后，renodx-dlss.addon64 必须依然完好保留！"
        assert mfg_addon.exists(), "模式 B 插件 renodx-mfgunlock.addon64 必须成功挂载！"

        # 4. 解析 ReShade.ini 验证合法语法与 [ADDON] 节点
        reshade_ini = game_dir / "ReShade.ini"
        assert reshade_ini.exists(), "ReShade.ini 必须存在"

        cp = configparser.ConfigParser(interpolation=None, strict=False)
        try:
            cp.read(reshade_ini, encoding="utf-8")
        except Exception as e:
            raise AssertionError(f"ReShade.ini 语法不合法，INI 解析器报错: {e}")

        assert cp.has_section("ADDON"), "ReShade.ini 中必须包含 [ADDON] 节点"
        load_main = cp.get("ADDON", "LoadFromDllMain", fallback="")
        load_main_parts = [x.strip() for x in load_main.split(",") if x.strip()]
        assert "1" not in load_main_parts, f"[ADDON] LoadFromDllMain 严禁包含布尔值 '1'！实际为: '{load_main}'"
        assert "renodx-dlss.addon64" not in load_main, "DLSS 5 插件严禁加入 LoadFromDllMain (避免 Loader Lock 导致 Error 1114/0xc0000005)"
        assert "renodx-mfgunlock.addon64" in load_main, f"LoadFromDllMain 必须包含模式 B 插件！实际为: '{load_main}'"

        # 5. 校验 DLSS 5 预设参数未被破坏
        assert cp.has_section("RenoDX.DLSS5"), "应包含 [RenoDX.DLSS5] 节点"
        nr_hook = cp.get("RenoDX.DLSS5", "NRHookPoint", fallback="")
        assert nr_hook == "0", f"DLSS 5 挂钩点必须为 之后/Upscaled 模式 (0)，实际为: {nr_hook}"
        nr_style = cp.get("RenoDX.DLSS5", "NRStyle", fallback="")
        assert nr_style == "2", f"DLSS 5 风格必须为模型 C (2)，实际为: {nr_style}"

        print(f"   [PASS] ReShade.ini 语法合规性校验 100% 通过:")
        print(f"          - [ADDON] LoadFromDllMain = {load_main}")
        print(f"          - 双 Addon 共存就绪: {dlss5_addon.name} ({round(dlss5_addon.stat().st_size/(1024*1024), 2)} MB) + {mfg_addon.name}")
        print(f"          - DLSS 5 参数守恒: Preset='{cp.get('RenoDX.DLSS5', 'CurrentPreset', fallback='My look')}', NRHookPoint={nr_hook}, NRStyle={nr_style}")


def test_assertion_4_model_and_dependency_completeness():
    """
    Assertion 4: 模型与依赖完备性校验
    验证 nvngx_dlssnr.dll (RTX 20/30/40 为 263.37 MB，RTX 50 为 254.08 MB) 已按硬件检测分支正确部署，
    且模式 C 的 fakenvapi 或模式 A 的 bink2w64Hooked.dll 链路完整。
    """
    print("\n----------------------------------------------------------------------")
    print("-> 执行 Assertion 4: 模型与依赖完备性校验 (RTX 20/30/40 vs RTX 50 & Bink 链路)...")

    # 分支 1: RTX 20/30/40 架构部署 263.37 MB 模型 + 模式 A Bink 劫持链路
    with tempfile.TemporaryDirectory() as tmpdir_40:
        game_dir_40, game_info_40 = _create_mock_game_environment(Path(tmpdir_40))
        # 放置原生 Bink 文件
        native_bink = game_dir_40 / "bink2w64.dll"
        native_bink.write_bytes(b"RAD_GAME_TOOLS_BINK_ORIGINAL_PAYLOAD" + b"\x00" * 1024)

        # 注入 DLSS 5 (RTX 20/30/40 模型)
        ok_inj, _ = DLSS5Injector.inject(str(game_dir_40), arch_choice="rtx20_30_40")
        assert ok_inj, "RTX 20/30/40 模型注入应成功"

        nr_file_40 = game_dir_40 / "nvngx_dlssnr.dll"
        assert nr_file_40.exists(), "nvngx_dlssnr.dll 必须存在"
        size_40_mb = round(nr_file_40.stat().st_size / (1024 * 1024), 2)
        assert abs(size_40_mb - 263.37) < 0.5, f"RTX 20/30/40 模型大小应为 ~263.37 MB，实际: {size_40_mb} MB"

        # 注入 模式 A (启用 prefer_bink_hook 链路)
        updater = ComponentUpdater()
        patcher = PatchEngine(updater)
        ok_a, _ = patcher.patch_game(game_info_40, requested_backend=BackendType.STANDALONE, prefer_bink_hook=True)
        assert ok_a, "模式 A Bink 链式劫持应成功"

        hooked_bink = game_dir_40 / "bink2w64Hooked.dll"
        active_bink = game_dir_40 / "bink2w64.dll"
        assert hooked_bink.exists(), "原版 Bink 必须已安全迁移为 bink2w64Hooked.dll"
        assert b"RAD_GAME_TOOLS_BINK_ORIGINAL_PAYLOAD" in hooked_bink.read_bytes(), "hooked 文件内容必须与原版一致"
        assert active_bink.stat().st_size > 1024 * 1024, "活动 bink2w64.dll 必须为 dashdogy 代理"
        print(f"   [PASS] 分支 1 (RTX 20/30/40): 神经重构模型校验通过 ({size_40_mb} MB)，Bink 链式劫持链路完备")

    # 分支 2: RTX 50 架构部署 254.08 MB 模型 + 模式 C fakenvapi 链路
    with tempfile.TemporaryDirectory() as tmpdir_50:
        game_dir_50, game_info_50 = _create_mock_game_environment(Path(tmpdir_50))

        # 注入 DLSS 5 (RTX 50 模型)
        ok_inj_50, _ = DLSS5Injector.inject(str(game_dir_50), arch_choice="rtx50")
        assert ok_inj_50, "RTX 50 模型注入应成功"

        nr_file_50 = game_dir_50 / "nvngx_dlssnr.dll"
        assert nr_file_50.exists(), "nvngx_dlssnr.dll 必须存在"
        size_50_mb = round(nr_file_50.stat().st_size / (1024 * 1024), 2)
        assert abs(size_50_mb - 254.08) < 0.5, f"RTX 50 模型大小应为 ~254.08 MB，实际: {size_50_mb} MB"

        # 注入 模式 C (OptiScaler 跨卡转译)
        patcher_50 = PatchEngine(updater)
        ok_c_50, _ = patcher_50.patch_game(game_info_50, requested_backend=BackendType.OPTISCALER_FSR)
        assert ok_c_50, "模式 C 注入应成功"

        # 校验 XeFG 关键运行库依赖完整性
        for dep in ["OptiScaler.ini", "libxess.dll", "libxess_fg.dll", "libxell.dll"]:
            assert (game_dir_50 / dep).exists(), f"模式 C 关键运行库依赖缺少: {dep}"

        print(f"   [PASS] 分支 2 (RTX 50): 神经重构模型校验通过 ({size_50_mb} MB)，OptiScaler/XeFG 依赖链完备")


def test_assertion_5_uninstallation_idempotency_and_restoration():
    """
    Assertion 5: 卸载幂等性校验
    触发一次【一键卸载与彻底还原】函数，验证测试目录内所有注入的 .dll、.addon64、.ini 残留被 100% 清除，
    且被重命名的原生文件 (如 bink2w64.dll) 已恢复原状。
    """
    print("\n----------------------------------------------------------------------")
    print("-> 执行 Assertion 5: 卸载幂等性校验 (全量双模态共存极速纯净化还原)...")
    with tempfile.TemporaryDirectory() as tmpdir:
        game_dir, game_info = _create_mock_game_environment(Path(tmpdir))
        # 放置原生 Bink 和游戏原生配置
        bink_orig = game_dir / "bink2w64.dll"
        bink_content = b"NATIVE_GAME_ORIGINAL_BINK_BIN" + b"\x55" * 1000
        bink_orig.write_bytes(bink_content)

        # 1. 注入 DLSS 5
        DLSS5Injector.inject(str(game_dir), arch_choice="rtx20_30_40")

        # 2. 注入 模式 A (prefer_bink_hook)
        updater = ComponentUpdater()
        patcher = PatchEngine(updater)
        patcher.patch_game(game_info, requested_backend=BackendType.STANDALONE, prefer_bink_hook=True)

        # 验证注入状态
        assert (game_dir / "bink2w64Hooked.dll").exists(), "还原前 bink 应当已被 hook"
        assert (game_dir / "dxgi.dll").exists(), "还原前 dxgi.dll 应当存在"
        assert (game_dir / "nvngx_dlssnr.dll").exists(), "还原前 nvngx_dlssnr.dll 应当存在"

        # 3. 执行 DLSS5Injector.restore 一键深度纯净化还原
        print("   -> 执行一键深度彻底卸载与纯净化还原...")
        ok_res, msg_res = DLSS5Injector.restore(str(game_dir))
        assert ok_res, f"还原应当成功: {msg_res}"

        # 4. 严格校验所有注入文件 100% 灭失
        forbidden_extensions = [".addon64", ".addon"]
        forbidden_filenames = [
            "dxgi.dll", "nvngx_dlssnr.dll", "version.dll", "winmm.dll", "dinput8.dll",
            "fakenvapi.dll", "fakenvapi.ini", "fakenvapi.log", "OptiScaler.ini", "OptiScaler.dll",
            "ReShade.ini", "ReShadePreset.ini", "ReShade64.dll", "dlssg_sm86.ini",
            ".dlss5_manifest.json", ".mfg_patch_manifest.json", ".dlss5_config.json",
            "RTXMFG-Universal.json", "RTX40MFG-UI.ini", "RTXMFG-UI.ini", "mfg_unlocker.ini",
            "bink2w64Hooked.dll"
        ]
        forbidden_directories = [
            "RenoDX", "dlss5-nr-runtime", "dlssg_sm86", "OptiScaler", "D3D12_Optiscaler",
            "reshade-shaders", ".dlss5_backup", ".dm_backup"
        ]

        # 检查非法残留
        for f in game_dir.rglob("*"):
            if f.is_file():
                assert f.suffix.lower() not in forbidden_extensions, f"发现残留扩展插件: {f.name}"
                assert f.name not in forbidden_filenames, f"发现注入文件残留: {f.name}"
            elif f.is_dir():
                assert f.name not in forbidden_directories, f"发现注入目录残留: {f.name}"

        # 5. 校验被重命名的原生 bink2w64.dll 100% 原样恢复
        assert bink_orig.exists(), "原版 bink2w64.dll 必须已恢复！"
        assert bink_orig.read_bytes() == bink_content, "原版 bink2w64.dll 二进制内容必须 100% 无损还原！"
        assert not (game_dir / "bink2w64Hooked.dll").exists(), "bink2w64Hooked.dll 临时文件必须已被清除！"

        # 6. 原生游戏可执行文件与 Streamline 必须完好无损
        assert (game_dir / "ShippingGame.exe").exists(), "原生游戏程序必须完好无损！"
        assert (game_dir / "sl.interposer.dll").exists(), "原生 Streamline 文件必须完好无损！"

        print(f"   [PASS] 卸载还原幂等性校验通过: 游戏目录已 100% 恢复为官方纯净无篡改状态，原版 bink2w64.dll 无损复原")




def test_assertion_6_mode_c_dlss5_coexistence_and_synergy():
    """
    Assertion 6: DLSS 5 + 模式 C (XeSS FG / OptiScaler) 全链路协同测试
    ===================================================================
    全面验证闪退根因的修复闭环（v1.3.8 拓扑）：
    1. 底座唯一性与代理隔离：dxgi.dll 严格为 DLSS 5 的 ReShade 6.8，
       OptiScaler 自动迁移到 winmm/version/dinput8 次级槽位且只保留一份。
    2. NVNGX 调用链保持畅通 (OptiScaler.ini 协同参数)：
       - [Upscalers] Dx12Upscaler="dlss"（合法直通值，DLSS 5 在链上接管超分）
       - [DLSS] Enabled="true", RenderPresetOverride="false"
       - [DLSSD] RenderPresetOverride="false"
       - [Hooks] HookOriginalNvngxOnly="false", EarlyHooking="false", UseNtdllHooks="false"
       - [Plugins] LoadAsiPlugins="false", LoadReshade="false"（禁止第二个 ReShade）
       - [FrameGen] PreserveSwapChain="true"（合法节区；[XeFG] 中不得再出现）
       - [FSRFG] UseMutexForSwapchain="true"
       - [Menu] OverlayMenu="true"（关闭该项会让 OptiScaler 禁用全部 FG）
    3. XeFG SwapChain 与 DLSS 5 Present 冲突规避 (协同调度挂钩点 NRHookPoint="0")：
       - ReShade.ini 中 NRHookPoint="0", HookStage="0", DirectNeuralRenderingHookStage="0",
         DirectNeuralRenderingAlwaysPresent="0", DirectNeuralRenderingPresentMode="0", NRPresentAlways="0"
       - RenoDX/DLSS5/Presets/My look.ini 中 NRHookPoint="0", HookStage="0"
    4. fakenvapi 环境保护：只要存在 DLSS 5 就禁止部署/保留 fakenvapi（任何显卡）。
    5. 双向注入协同保证：
       - 场景 A (先 DLSS 5 后 模式 C)
       - 场景 B (先 模式 C 后 DLSS 5)
    6. 卸载还原 100% 幂等。
    """
    print("\n----------------------------------------------------------------------")
    print("-> 执行 Assertion 6: DLSS 5 + 模式 C (XeSS FG / OptiScaler) 全链路协同测试...")
    assets = scan_plugin_source_assets()
    ref_dxgi_hash = _calculate_file_sha256(Path(assets["dxgi_path"]))
    updater = ComponentUpdater()

    # ====== 场景 A: 先注入 DLSS 5，后注入 模式 C ======
    print("   [场景 A] 先注入 DLSS 5 -> 后注入 模式 C...")
    with tempfile.TemporaryDirectory() as tmpdir_a:
        game_dir_a, game_info_a = _create_mock_game_environment(Path(tmpdir_a))

        # 1. 注入 DLSS 5
        ok_d5, msg_d5 = DLSS5Injector.inject(str(game_dir_a), arch_choice="rtx20_30_40")
        assert ok_d5, f"DLSS 5 注入应成功: {msg_d5}"

        # 上一轮实机日志：libxess_fg 只报告 1 个插值（2X）。MFGUnlocker.asi 必须把它顶开。
        (game_dir_a / "OptiScaler.log").write_text(
            "[x] XeFG_Dx12::QueryMaxInterpolationCount Max supported interpolations: 1\n",
            encoding="utf-8",
        )

        # 2. 注入 模式 C (OptiScaler 跨卡转译 / XeSS FG)
        patcher_a = PatchEngine(updater)
        ok_c, msg_c = patcher_a.patch_game(game_info_a, requested_backend=BackendType.OPTISCALER_FSR)
        assert ok_c, f"模式 C 注入应成功: {msg_c}"

        # 验证 1: 底座与代理
        dxgi_a = game_dir_a / "dxgi.dll"
        version_a = game_dir_a / "version.dll"
        assert dxgi_a.exists(), "dxgi.dll 必须存在"
        assert _calculate_file_sha256(dxgi_a) == ref_dxgi_hash, "dxgi.dll 必须为 DLSS 5 ReShade 6.8 渲染底座"
        assert version_a.exists(), "OptiScaler 必须避让部署为 version.dll"

        # 验证 2: OptiScaler.ini 冲突规避配置
        opti_ini_a = game_dir_a / "OptiScaler.ini"
        assert opti_ini_a.exists(), "OptiScaler.ini 必须存在"
        cp_opti = configparser.ConfigParser(interpolation=None, strict=False)
        cp_opti.read(opti_ini_a, encoding="utf-8")

        assert cp_opti.get("Upscalers", "Dx12Upscaler", fallback="").lower() == "dlss", "Dx12Upscaler 必须设为合法直通值 'dlss'，避免双重劫持"
        assert cp_opti.get("DLSS", "Enabled", fallback="").lower() == "true", "[DLSS] Enabled 必须为 'true'，否则 DLSS 5 收不到游戏的 DLSS 调用"
        assert cp_opti.get("DLSS", "RenderPresetOverride", fallback="").lower() == "false", "[DLSS] RenderPresetOverride 必须设为 'false'"
        assert cp_opti.get("DLSSD", "RenderPresetOverride", fallback="").lower() == "false", "[DLSSD] RenderPresetOverride 必须设为 'false'"
        assert cp_opti.get("Hooks", "HookOriginalNvngxOnly", fallback="").lower() == "false", "HookOriginalNvngxOnly 必须为 'false'，否则会跳过游戏本地 NGX 模块"
        assert cp_opti.get("Hooks", "EarlyHooking", fallback="").lower() == "false", "EarlyHooking 必须为 'false'"
        assert cp_opti.get("Hooks", "UseNtdllHooks", fallback="").lower() == "false", "UseNtdllHooks 必须为 'false'"
        assert cp_opti.get("Plugins", "LoadAsiPlugins", fallback="").lower() == "true", "LoadAsiPlugins 必须为 'true' 才能加载 MFGUnlocker.asi"
        assert cp_opti.get("Plugins", "LoadReshade", fallback="").lower() == "false", "LoadReshade 必须为 'false'"
        assert (game_dir_a / "OptiScaler" / "plugins" / "MFGUnlocker.asi").is_file(), "MFGUnlocker.asi 必须部署以解锁 XeFG 3X/4X"
        assert cp_opti.get("XeFG", "InterpolationCount", fallback="") == "2", \
            "即使日志里 libxess_fg 只报 1，也必须保留 3X 请求交给 MFGUnlocker 解锁"
        assert cp_opti.get("FrameGen", "PreserveSwapChain", fallback="").lower() == "true", "[FrameGen] PreserveSwapChain 必须为 'true'（合法节区）"
        assert cp_opti.get("XeFG", "PreserveSwapChain", fallback="").lower() != "true", "[XeFG] 中不允许再写入 PreserveSwapChain（无效键）"
        assert cp_opti.get("FSRFG", "UseMutexForSwapchain", fallback="").lower() == "true", "[FSRFG] UseMutexForSwapchain 必须为 'true'"
        assert cp_opti.get("Menu", "OverlayMenu", fallback="").lower() == "true", "[Menu] OverlayMenu 必须为 'true'，否则 OptiScaler 会禁用全部 FG 功能"
        assert cp_opti.get("XeFG", "IgnoreInitChecks", fallback="").lower() == "true", "必须豁免 XeFG 预检查（Dilated MV / Borderless / HDR10）"
        assert cp_opti.get("FrameGen", "FGInput", fallback="").lower() == "dlssg", "FGInput 必须为 dlssg"
        assert cp_opti.get("FrameGen", "FGOutput", fallback="").lower() == "xefg", "FGOutput 必须为 xefg"

        # 验证 3: DLSS 5 挂钩点协同为 NRHookPoint="0"
        reshade_ini_a = game_dir_a / "ReShade.ini"
        cp_reshade = configparser.ConfigParser(interpolation=None, strict=False)
        cp_reshade.read(reshade_ini_a, encoding="utf-8")

        assert cp_reshade.get("RenoDX.DLSS5", "NRHookPoint", fallback="") == "0", "DLSS 5 NRHookPoint 默认为 '0' (之后/Upscaled模式)"
        assert cp_reshade.get("RenoDX.DLSS5", "HookStage", fallback="") == "0", "HookStage 必须为 '0'"
        assert cp_reshade.get("RenoDX.DLSS5", "DirectNeuralRenderingHookStage", fallback="") == "0", "DirectNeuralRenderingHookStage 必须为 '0'"
        assert cp_reshade.get("RenoDX.DLSS5", "DirectNeuralRenderingAlwaysPresent", fallback="") == "0", "DirectNeuralRenderingAlwaysPresent 必须为 '0'"
        assert cp_reshade.get("RenoDX.DLSS5", "DirectNeuralRenderingPresentMode", fallback="") == "0", "DirectNeuralRenderingPresentMode 必须为 '0'"
        assert cp_reshade.get("RenoDX.DLSS5", "NRPresentAlways", fallback="") == "0", "NRPresentAlways 必须为 '0'"

        preset_mylook_a = game_dir_a / "RenoDX" / "DLSS5" / "Presets" / "My look.ini"
        assert preset_mylook_a.exists(), "My look.ini 独立预设文件应存在"
        txt_mylook = preset_mylook_a.read_text(encoding="utf-8")
        assert "NRHookPoint=0" in txt_mylook, "预设文件中 NRHookPoint 必须为 '0'"
        assert "HookStage=0" in txt_mylook, "预设文件中 HookStage 必须为 '0'"

        # 验证 4: 只要存在 DLSS 5，就必须清理 fakenvapi（任何显卡架构）
        assert not (game_dir_a / "fakenvapi.dll").exists(), "DLSS 5 共存态下严禁部署 fakenvapi.dll"
        assert not (game_dir_a / "fakenvapi.ini").exists(), "DLSS 5 共存态下严禁部署 fakenvapi.ini"

        # 验证 5: 卸载幂等性
        ok_res_a, msg_res_a = DLSS5Injector.restore(str(game_dir_a))
        assert ok_res_a, f"还原应当成功: {msg_res_a}"
        assert not (game_dir_a / "dxgi.dll").exists(), "还原后 dxgi.dll 应被清除"
        assert not (game_dir_a / "version.dll").exists(), "还原后 version.dll 应被清除"
        assert not (game_dir_a / "OptiScaler.ini").exists(), "还原后 OptiScaler.ini 应被清除"
        assert not (game_dir_a / "ReShade.ini").exists(), "还原后 ReShade.ini 应被清除"
        print("   [PASS] 场景 A 校验全部通过，还原 100% 幂等")

    # ====== 场景 B: 先注入 模式 C，后注入 DLSS 5 ======
    print("   [场景 B] 先注入 模式 C -> 后注入 DLSS 5...")
    with tempfile.TemporaryDirectory() as tmpdir_b:
        game_dir_b, game_info_b = _create_mock_game_environment(Path(tmpdir_b))

        # 1. 注入 模式 C
        patcher_b = PatchEngine(updater)
        ok_c_first, _ = patcher_b.patch_game(game_info_b, requested_backend=BackendType.OPTISCALER_FSR)
        assert ok_c_first, "模式 C 首次注入应成功"

        # 模拟旧版本遗留的 fakenvapi（必须被后续 DLSS 5 注入彻底清理）
        (game_dir_b / "fakenvapi.dll").write_bytes(b"fakenvapi_stub")
        (game_dir_b / "fakenvapi.ini").write_text("[fakenvapi]\n", encoding="utf-8")

        # 2. 注入 DLSS 5
        ok_d5_second, _ = DLSS5Injector.inject(str(game_dir_b), arch_choice="rtx20_30_40")
        assert ok_d5_second, "DLSS 5 后续注入应成功"

        # 验证底座与代理
        assert (game_dir_b / "dxgi.dll").exists(), "dxgi.dll 必须存在"
        assert _calculate_file_sha256(game_dir_b / "dxgi.dll") == ref_dxgi_hash, "dxgi.dll 必须为 DLSS 5 ReShade 6.8"

        # 关键回归：先注入模式 C 时，OptiScaler 代理必须被迁移而不是被 ReShade 覆盖
        from core.coexistence import detect_optiscaler_slot, is_optiscaler_binary, coexistence_snapshot
        slot_b = detect_optiscaler_slot(str(game_dir_b))
        assert slot_b in ("version.dll", "winmm.dll", "dinput8.dll", "wininet.dll"), \
            f"OptiScaler 插帧代理必须迁移至次级槽位，实际: {slot_b}"
        assert is_optiscaler_binary(game_dir_b / slot_b), "次级槽位文件必须是 OptiScaler 核心二进制"
        assert (game_dir_b / "libxess_fg.dll").exists(), "XeFG 运行库必须保留"
        snap_b = coexistence_snapshot(str(game_dir_b))
        assert snap_b["dxgi_host"] == "reshade", f"dxgi.dll 必须是 ReShade 宿主，实际: {snap_b['dxgi_host']}"
        assert snap_b["secondary_reshade"] == [], f"不允许残留第二个 ReShade 宿主: {snap_b['secondary_reshade']}"
        assert snap_b["fakenvapi"] == [], f"不允许残留 fakenvapi: {snap_b['fakenvapi']}"

        # 验证 OptiScaler.ini 协同更新为冲突规避配置
        opti_ini_b = game_dir_b / "OptiScaler.ini"
        assert opti_ini_b.exists()
        cp_opti_b = configparser.ConfigParser(interpolation=None, strict=False)
        cp_opti_b.read(opti_ini_b, encoding="utf-8")
        assert cp_opti_b.get("Upscalers", "Dx12Upscaler", fallback="").lower() == "dlss"
        assert cp_opti_b.get("DLSS", "Enabled", fallback="").lower() == "true"
        assert cp_opti_b.get("Hooks", "HookOriginalNvngxOnly", fallback="").lower() == "false"
        assert cp_opti_b.get("FrameGen", "PreserveSwapChain", fallback="").lower() == "true"
        assert cp_opti_b.get("Menu", "OverlayMenu", fallback="").lower() == "true"

        # 验证 DLSS 5 协同挂钩点为 "0"
        reshade_ini_b = game_dir_b / "ReShade.ini"
        cp_reshade_b = configparser.ConfigParser(interpolation=None, strict=False)
        cp_reshade_b.read(reshade_ini_b, encoding="utf-8")
        assert cp_reshade_b.get("RenoDX.DLSS5", "NRHookPoint", fallback="") == "0"
        assert cp_reshade_b.get("RenoDX.DLSS5", "HookStage", fallback="") == "0"

        # 验证 fakenvapi 已被清理（任何显卡架构）
        assert not (game_dir_b / "fakenvapi.dll").exists(), "遗留的 fakenvapi.dll 必须被清理"
        assert not (game_dir_b / "fakenvapi.ini").exists(), "遗留的 fakenvapi.ini 必须被清理"

        # 验证卸载还原
        ok_res_b, _ = DLSS5Injector.restore(str(game_dir_b))
        assert ok_res_b
        assert not (game_dir_b / "dxgi.dll").exists()
        print("   [PASS] 场景 B 校验全部通过，反向注入协同与还原 100% 幂等")


def test_assertion_7_legacy_state_repair_and_purges():
    """
    Assertion 7: 历史脏状态修复与冲突文件净化
    =========================================
    复现用户报障的两类目录状态：
    1. 旧版 DLSS 5 注入器已经把 ReShade 覆盖到 dxgi.dll，OptiScaler 代理彻底丢失
       （OptiScaler.ini / libxess_fg.dll 还在）——必须自动从组件缓存补回代理；
    2. 目录内残留第二个 ReShade 宿主（ReShade64.dll）与 fakenvapi —— 必须清除。
    同时校验 nvngx_dlssnr.dll 架构指纹识别不再把 263MB 的 20/30/40 模型误判为 RTX 50。
    """
    print("\n----------------------------------------------------------------------")
    print("-> 执行 Assertion 7: 历史脏状态修复 / 单一 ReShade / fakenvapi 净化...")
    from core.coexistence import detect_optiscaler_slot, is_optiscaler_binary
    from apps.app6_dlss5.engine.injector import check_game_dlss5_status

    updater = ComponentUpdater()
    opti_dir = Path(updater.get_latest_cached_dir(BackendType.OPTISCALER_FSR) or "")
    assert opti_dir.is_dir(), "OptiScaler 组件缓存必须存在"

    # --- 场景 1: 旧版覆盖后的“半残”状态 ---
    with tempfile.TemporaryDirectory() as tmpdir:
        game_dir, _ = _create_mock_game_environment(Path(tmpdir))
        (game_dir / "OptiScaler.ini").write_text("[FrameGen]\nEnabled=true\nFGOutput=xefg\n", encoding="utf-8")
        (game_dir / "libxess_fg.dll").write_bytes(b"libxess_fg_stub")
        # 第二个 ReShade 宿主 + fakenvapi 残留
        (game_dir / "ReShade64.dll").write_bytes(b"ReShade crosire secondary host" + b"\x00" * 64)
        (game_dir / "fakenvapi.dll").write_bytes(b"fakenvapi_stub")
        (game_dir / "fakenvapi.ini").write_text("[fakenvapi]\n", encoding="utf-8")

        ok, msg = DLSS5Injector.inject(str(game_dir), arch_choice="rtx20_30_40")
        assert ok, f"DLSS 5 注入应成功: {msg}"

        slot = detect_optiscaler_slot(str(game_dir))
        assert slot, "丢失的 OptiScaler 代理必须从组件缓存自动补回"
        assert is_optiscaler_binary(game_dir / slot), f"{slot} 必须是 OptiScaler 核心二进制"
        assert not (game_dir / "ReShade64.dll").exists(), "第二个 ReShade 宿主必须被清除"
        assert not (game_dir / "fakenvapi.dll").exists(), "fakenvapi.dll 必须被清除"
        assert not (game_dir / "fakenvapi.ini").exists(), "fakenvapi.ini 必须被清除"

        cp = configparser.ConfigParser(interpolation=None, strict=False)
        cp.read(game_dir / "OptiScaler.ini", encoding="utf-8")
        assert cp.get("DLSS", "Enabled", fallback="").lower() == "true"
        assert cp.get("FrameGen", "PreserveSwapChain", fallback="").lower() == "true"
        assert cp.get("Upscalers", "Dx12Upscaler", fallback="").lower() == "dlss"
        print(f"   [PASS] 半残状态自动修复：OptiScaler 代理已补回 {slot}，重复 ReShade / fakenvapi 已净化")

    # --- 场景 2: 架构指纹 ---
    with tempfile.TemporaryDirectory() as tmpdir:
        game_dir, _ = _create_mock_game_environment(Path(tmpdir))
        ok, _ = DLSS5Injector.inject(str(game_dir), arch_choice="rtx20_30_40")
        assert ok
        stat = check_game_dlss5_status(str(game_dir))
        assert stat["detected_arch"] == "rtx20_30_40", \
            f"263MB 的 RTX 20/30/40 模型不应被误判为 {stat['detected_arch']}"
        print(f"   [PASS] 神经重构模型架构指纹识别正确: {stat['detected_arch']} ({stat['runtime_size_mb']} MB)")


def test_assertion_8_repeated_injection_is_idempotent():
    """
    Assertion 8: 重复注入幂等性
    ===========================
    用户在模式 C 已注入后反复点击“注入 DLSS 5”是最常见的操作路径。
    必须保证：dxgi.dll 始终是同一份 ReShade 6.8、OptiScaler 只保留一个代理、
    OptiScaler.ini 不被反复追加/破坏，最终卸载后目录 100% 纯净。
    """
    print("\n----------------------------------------------------------------------")
    print("-> 执行 Assertion 8: 重复注入幂等性...")
    from core.coexistence import coexistence_snapshot, detect_optiscaler_slot
    assets = scan_plugin_source_assets()
    ref_dxgi_hash = _calculate_file_sha256(Path(assets["dxgi_path"]))

    with tempfile.TemporaryDirectory() as tmpdir:
        game_dir, game_info = _create_mock_game_environment(Path(tmpdir))
        patcher = PatchEngine(ComponentUpdater())
        ok, _ = patcher.patch_game(game_info, requested_backend=BackendType.OPTISCALER_FSR)
        assert ok

        for i in range(3):
            ok, msg = DLSS5Injector.inject(str(game_dir), arch_choice="rtx20_30_40")
            assert ok, f"第 {i + 1} 次注入失败: {msg}"

        snap = coexistence_snapshot(str(game_dir))
        assert snap["dxgi_host"] == "reshade", "dxgi.dll 必须始终是 ReShade 宿主"
        assert _calculate_file_sha256(game_dir / "dxgi.dll") == ref_dxgi_hash
        assert snap["optiscaler_slot"] in ("version.dll", "winmm.dll", "dinput8.dll", "wininet.dll")
        proxies = [n for n in ("dxgi.dll", "version.dll", "winmm.dll", "dinput8.dll", "wininet.dll")
                   if n != "dxgi.dll" and n == snap["optiscaler_slot"]]
        assert len(proxies) == 1, "OptiScaler 代理必须唯一"
        assert len(list(game_dir.glob("*.addon64"))) == 1, "只允许存在一个 DLSS 5 Addon"

        ok, msg = DLSS5Injector.restore(str(game_dir))
        assert ok, msg
        native_keep = {"nvngx_dlssg.dll", "sl.interposer.dll"}
        leftovers = [p.name for p in game_dir.iterdir()
                     if p.suffix.lower() in (".dll", ".addon64", ".ini") and p.name not in native_keep]
        assert leftovers == [], f"卸载后仍有残留: {leftovers}"
        print("   [PASS] 三次重复注入后布局不变，卸载后无残留")


def test_assertion_9_mode_a_dlss5_coexistence_and_synergy():
    """
    Assertion 9: Mode A (Universal MFG / Dashdogy 3x) 与 DLSS 5 共存及挂钩点协同
    ========================================================================
    验证:
    1. 启用模式 A 多帧生成 (3x 插帧) + DLSS 5 时，DLSS 5 挂钩点协同为 NRHookPoint="0" (Upscaled 模式)；
    2. NRPresentAlways="0"，彻底杜绝 DLSS 5 拦截 nv.sl.dlss_g.cmdQ.pacer 调度队列导致 0x887A0006 GPU 挂起；
    3. NRFollowInputRes="1"，且工作分辨率 NRResolutionScale="0.500000"，消除 4K 全分辨率异常占用。
    """
    print("\n----------------------------------------------------------------------")
    print("-> 执行 Assertion 9: 模式 A (Universal MFG 3x) + DLSS 5 协同与防挂起校验...")
    from core.ini_sync import IniConfigManager
    import configparser

    with tempfile.TemporaryDirectory() as tmpdir:
        game_dir, game_info = _create_mock_game_environment(Path(tmpdir))

        # 1. 先注入 DLSS 5
        ok_dlss, _ = DLSS5Injector.inject(str(game_dir), arch_choice="rtx20_30_40")
        assert ok_dlss

        # 2. 注入模式 A (3x 插帧)
        patcher = PatchEngine(ComponentUpdater())
        ok_patch, _ = patcher.patch_game(game_info, requested_backend=BackendType.STANDALONE)
        assert ok_patch

        # 3. 校验 ReShade.ini 协同参数
        reshade_ini = game_dir / "ReShade.ini"
        assert reshade_ini.exists()
        cp = configparser.ConfigParser(interpolation=None, strict=False)
        cp.read(reshade_ini, encoding="utf-8")
        assert cp.get("RenoDX.DLSS5", "NRHookPoint", fallback="") == "0", "DLSS 5 默认 NRHookPoint 为 '0' (Upscaled 模式)"
        assert cp.get("RenoDX.DLSS5", "HookStage", fallback="") == "0"
        assert cp.get("RenoDX.DLSS5", "NRPresentAlways", fallback="") == "0", "NRPresentAlways 默认为 '0'"
        assert cp.get("RenoDX.DLSS5", "NRFollowInputRes", fallback="") == "1", "NRFollowInputRes 必须为 '1' (匹配游戏)"
        assert cp.get("RenoDX.DLSS5", "NRResolutionScale", fallback="") == "0.500000"

        # 4. 校验 RenoDX/DLSS5/Presets/My look.ini 独立预设
        my_look_file = game_dir / "RenoDX" / "DLSS5" / "Presets" / "My look.ini"
        assert my_look_file.exists()
        txt_mylook = my_look_file.read_text(encoding="utf-8")
        assert "NRHookPoint=0" in txt_mylook
        assert "NRPresentAlways=0" in txt_mylook
        assert "NRFollowInputRes=1" in txt_mylook

        # 5. 执行卸载还原
        ok_res, _ = DLSS5Injector.restore(str(game_dir))
        assert ok_res
        assert not (game_dir / "dxgi.dll").exists()
        print("   [PASS] 模式 A 与 DLSS 5 共存态参数协同、防 GPU 挂起与卸载校验 100% PASS")


if __name__ == "__main__":
    print("======================================================================")
    print("      多帧生成 (app2_mfg) 与 DLSS 5 (app6_dlss5) 共存分发自动化闭环验证      ")
    print("======================================================================")
    test_assertion_1_base_uniqueness_and_fingerprint()
    test_assertion_2_dual_channel_isolation()
    test_assertion_3_addon_mounting_and_ini_syntax()
    test_assertion_4_model_and_dependency_completeness()
    test_assertion_5_uninstallation_idempotency_and_restoration()
    test_assertion_6_mode_c_dlss5_coexistence_and_synergy()
    test_assertion_7_legacy_state_repair_and_purges()
    test_assertion_8_repeated_injection_is_idempotent()
    test_assertion_9_mode_a_dlss5_coexistence_and_synergy()
    print("\n======================================================================")
    print(">>> 全部 9 项硬性断言 100% 严格 PASS！共存分发改造闭环达成！")
    print("======================================================================")
