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
        # No OptiScaler log in the temp dir -> XeFG is safely capped at 2X (1 interpolation)
        assert secs["XeFG"]["InterpolationCount"] == "1"
        # Verify Default preset is Default (RenderPresetOverride=false, UseGenericAppIdWithDlss=false)
        assert secs["DLSS"]["RenderPresetOverride"] == "false"
        assert secs["DLSS"]["RenderPresetForAll"] == "0"
        assert secs["DLSS"]["UseGenericAppIdWithDlss"] == "false"
        # Verify RCAS is false
        assert secs["CAS"]["Enabled"] == "false"
        # Verify Log is enabled
        assert secs["Log"]["LogToFile"] == "true"

        # Verify reverse sync
        rev = IniConfigManager.read_mode_c_reverse(td)
        assert rev is not None, "read_mode_c_reverse returned None"
        assert rev["menu_key"] == "Insert", f"rev menu_key should be Insert, got {rev.get('menu_key')}"
        assert rev["fg_output"] == "xefg"
        assert rev["interpolation_count"] == 1
        assert rev["dlss_preset"] == "Default"
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
        assert "2X 双倍" in summary
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

    print("\nALL OPTISCALER XESS FG AND MENU CHECKS PASSED 100%!")

if __name__ == "__main__":
    run_tests()
