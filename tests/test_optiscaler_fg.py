import sys
import os
import tempfile
import shutil
from pathlib import Path

# Add project root and app2_mfg to path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root_dir)
sys.path.insert(0, os.path.join(root_dir, "apps", "app2_mfg"))

from core.ini_sync import IniConfigManager, VK_KEY_MAP
from core.optiscaler_config import load_optiscaler_preset, DEFAULT_OPTISCALER_PRESET, get_preset_summary
from core.patcher import PatchEngine
from core.models import GameInfo, BackendType, QualificationStatus

def run_tests():
    print("=== 1. Testing Mode C IniConfigManager Forward & Reverse Sync ===")
    with tempfile.TemporaryDirectory() as td:
        preset = dict(DEFAULT_OPTISCALER_PRESET)
        ok = IniConfigManager.sync_mode_c_forward(td, preset, exe_name="test.exe")
        assert ok, "sync_mode_c_forward failed"

        opti_ini = os.path.join(td, "OptiScaler.ini")
        nvngx_ini = os.path.join(td, "nvngx.ini")
        assert os.path.exists(opti_ini), "OptiScaler.ini was not created"
        assert not os.path.exists(nvngx_ini), "nvngx.ini must NOT be created (v0.9.4 single-config rule)"

        secs = IniConfigManager.read_ini_sections(opti_ini)
        # Verify OverlayMenu is true (CRITICAL for OptiScaler Frame Generation!)
        assert secs["Menu"]["OverlayMenu"] == "true", f"OverlayMenu should be true, got {secs['Menu'].get('OverlayMenu')}"
        # Verify ShortcutKey is 45 (Insert)
        assert secs["Menu"]["ShortcutKey"] == "45", f"ShortcutKey should be 45, got {secs['Menu'].get('ShortcutKey')}"
        assert secs["Menu"]["DisableSplash"] == "false", "DisableSplash should be false"
        # Verify 4K menu scale
        assert secs["Menu"]["Scale"] == "2.0", f"Menu Scale should be 2.0 (4K), got {secs['Menu'].get('Scale')}"
        # Verify FrameGen is enabled
        assert secs["FrameGen"]["Enabled"] == "true"
        assert secs["FrameGen"]["FGOutput"] == "xefg"
        assert secs["FrameGen"]["FGInput"] == "dlssg"
        # XeFG default is 3X frame generation (2 interpolations)
        assert secs["XeFG"]["InterpolationCount"] == "2"
        # Verify Default preset is Preset K (RenderPresetOverride=true, RenderPresetForAll=11)
        assert secs["DLSS"]["RenderPresetOverride"] == "true"
        assert secs["DLSS"]["RenderPresetForAll"] == "11"
        # Verify RCAS is false
        assert secs["CAS"]["Enabled"] == "false"
        # Verify Log is enabled
        assert secs["Log"]["LogToFile"] == "true"

        # Verify reverse sync
        rev = IniConfigManager.read_mode_c_reverse(td)
        assert rev is not None, "read_mode_c_reverse returned None"
        assert rev["menu_key"] == "Insert", f"rev menu_key should be Insert, got {rev.get('menu_key')}"
        assert rev["fg_output"] == "xefg"
        assert rev["interpolation_count"] == 2
        assert rev["dlss_preset"] == "K"
        assert abs(rev["menu_scale"] - 2.0) < 1e-6

        # Test custom hotkey Backspace and Preset M
        preset["menu_key"] = "Backspace"
        preset["dlss_preset"] = "M"
        preset["rcas_enabled"] = True
        preset["rcas_sharpness"] = 0.45
        ok = IniConfigManager.sync_mode_c_forward(td, preset, exe_name="test.exe")
        assert ok

        secs2 = IniConfigManager.read_ini_sections(opti_ini)
        assert secs2["Menu"]["ShortcutKey"] == "8", f"ShortcutKey should be 8 (Backspace), got {secs2['Menu'].get('ShortcutKey')}"
        assert secs2["DLSS"]["RenderPresetOverride"] == "true"
        assert secs2["DLSS"]["RenderPresetForAll"] == "13"
        assert secs2["CAS"]["Enabled"] == "true"

        rev2 = IniConfigManager.read_mode_c_reverse(td)
        assert rev2["menu_key"] == "Backspace"
        assert rev2["dlss_preset"] == "M"
        assert rev2["rcas_enabled"] is True

        summary = get_preset_summary(preset)
        print("Preset summary string:", summary)
        assert "Intel XeFG 官方插帧" in summary
        assert "3X 三倍" in summary
        assert "快捷键: Backspace" in summary
        assert "DLSS M" in summary

    print("=== 2. Testing PE Import Table Proxy Resolution ===")
    yysls_exe = r"D:\game\yysls\yysls_medium\Engine\Binaries\Win64r\yysls.exe"
    if os.path.exists(yysls_exe):
        patcher = PatchEngine(updater=None)
        pe_proxies = patcher._get_pe_imported_proxies(yysls_exe)
        print("PE Imported proxies in yysls.exe:", pe_proxies)
        assert "winmm.dll" in pe_proxies, "yysls.exe must import winmm.dll"

        # Simulate proxy selection for yysls.exe
        opti_proxies = ["dxgi.dll", "version.dll", "winmm.dll", "dinput8.dll", "wininet.dll"]
        dynamic_priority = list(opti_proxies)
        for pe_cand in reversed(["winmm.dll", "version.dll", "dinput8.dll"]):
            if pe_cand in pe_proxies and pe_cand in dynamic_priority:
                dynamic_priority.remove(pe_cand)
                dynamic_priority.insert(0, pe_cand)

        print("Resolved proxy priority for yysls.exe:", dynamic_priority)
        assert dynamic_priority[0] == "winmm.dll", f"Index 0 must be winmm.dll for yysls.exe, got {dynamic_priority[0]}"

    print("=== 3. Testing Mode B Pure OptiScaler & Conditional MFGUnlocker.asi ===")
    with tempfile.TemporaryDirectory() as td:
        from core.updater import ComponentUpdater
        from unittest.mock import patch
        from core.models import PatchManifest
        updater = ComponentUpdater()
        patcher = PatchEngine(updater=updater)
        manifest = PatchManifest(
            app_version="2.0.0",
            game_name="TestGame",
            target_exe=os.path.join(td, "game.exe"),
            target_dir=td,
            active_backend=BackendType.OPTISCALER_FSR.value,
            installed_version="latest"
        )
        fake_game = GameInfo(
            name="TestGame",
            source="custom",
            install_dir=td,
            target_dir=td,
            exe_path=os.path.join(td, "game.exe"),
            exe_name="game.exe",
            qualification=QualificationStatus.QUALIFIED
        )
        # 3A: Default Mode B - Pure OptiScaler without redundant dashdogy 1.7.0 UI overlay
        with patch("core.patcher.get_system_gpu_name", return_value="NVIDIA GeForce RTX 4070 Laptop GPU"),              patch("core.patcher.is_rtx_40_or_newer", return_value=True):
            ok, err = patcher._apply_optiscaler_patch(fake_game, manifest)
            assert ok, f"_apply_optiscaler_patch failed: {err}"
            asi_path = os.path.join(td, "OptiScaler", "plugins", "MFGUnlocker.asi")
            assert not os.path.exists(asi_path), "Mode B 默认严禁注入 MFGUnlocker.asi，杜绝 1.7.0 菜单重复弹出!"
            opti_ini = os.path.join(td, "OptiScaler.ini")
            secs = IniConfigManager.read_ini_sections(opti_ini)
            assert secs["Plugins"]["LoadAsiPlugins"] == "false", "LoadAsiPlugins 默认必须为 false"
            assert secs["XeFG"]["IgnoreInitChecks"] == "true", "IgnoreInitChecks must be true"
            print("Mode B default test passed: Pure OptiScaler without duplicate ASI injection!")

        # 3B: Explicit unlock_mfg=True user toggle
        with patch("core.optiscaler_config.load_optiscaler_preset", return_value={"unlock_mfg": True, "fg_output": "xefg", "interpolation_count": 2}),              patch("core.patcher.get_system_gpu_name", return_value="NVIDIA GeForce RTX 4070 Laptop GPU"),              patch("core.patcher.is_rtx_40_or_newer", return_value=True):
            manifest_un = PatchManifest(
                app_version="2.0.0",
                game_name="TestGame",
                target_exe=os.path.join(td, "game.exe"),
                target_dir=td,
                active_backend=BackendType.OPTISCALER_FSR.value,
                installed_version="latest"
            )
            ok2, err2 = patcher._apply_optiscaler_patch(fake_game, manifest_un)
            assert ok2, f"_apply_optiscaler_patch with unlock failed: {err2}"
            assert os.path.exists(asi_path), "显式开启 unlock_mfg 时才部署 MFGUnlocker.asi"
            secs2 = IniConfigManager.read_ini_sections(opti_ini)
            assert secs2["Plugins"]["LoadAsiPlugins"] == "true", "显式开启时 LoadAsiPlugins 为 true"
            print("Mode B explicit unlock_mfg=True test passed!")

    print("\nALL OPTISCALER XESS FG AND MENU CHECKS PASSED 100%!")

if __name__ == "__main__":
    run_tests()
