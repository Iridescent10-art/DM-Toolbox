# -*- coding: utf-8 -*-
"""
Unit tests for App 6: DLSS 5 Neural Reconstruction Injector,
Coexistence with OptiScaler, RHI Avoidance, Anti-Preset D Enforcement, and Loader Lock Prevention.
"""

import os
import sys
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from apps.app6_dlss5.engine.injector import (
    DLSS5Injector, check_dlss5_status, detect_frame_generation,
    find_reshade_framework_dll, get_dlss5_addon_path, get_dlss5_runtime_dll_path,
    find_rhi_setup_exe, enforce_optiscaler_anti_d_preset, _configure_reshade_ini_for_dlss5
)
from launcher.main import APPS_METADATA, APP_EXACT_TITLES


class TestDLSS5Injector(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_dlss5_")
        self.game_dir = Path(self.test_dir) / "Cyberpunk2077" / "bin" / "x64"
        self.game_dir.mkdir(parents=True, exist_ok=True)
        # Create mock executable
        (self.game_dir / "Cyberpunk2077.exe").write_bytes(b"MZ" + b"\x00" * 1024)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_launcher_registration_and_assets(self):
        """Verify app6_dlss5 is correctly registered in launcher metadata, titles, and assets."""
        app_ids = [m["id"] for m in APPS_METADATA]
        self.assertIn("app6_dlss5", app_ids)
        self.assertIn("app6_dlss5", APP_EXACT_TITLES)
        self.assertEqual(APP_EXACT_TITLES["app6_dlss5"], "DM工具箱 - DLSS 5 神经重构与画质注入器")

        # Verify addon asset file
        addon_src = get_dlss5_addon_path()
        self.assertIsNotNone(addon_src)
        self.assertTrue(os.path.exists(addon_src))
        self.assertGreater(os.path.getsize(addon_src), 2 * 1024 * 1024)

        # Verify runtime DLL asset file (nvngx_dlssnr.dll ~165 MB)
        runtime_src = get_dlss5_runtime_dll_path()
        self.assertIsNotNone(runtime_src)
        self.assertTrue(os.path.exists(runtime_src))
        self.assertGreater(os.path.getsize(runtime_src), 100 * 1024 * 1024)

    def test_clean_status(self):
        """Verify status detection on an unpatched game."""
        status = DLSS5Injector.get_status(str(self.game_dir))
        self.assertFalse(status["is_injected"])
        self.assertFalse(status["has_addon"])
        self.assertFalse(status["has_dxgi"])
        self.assertFalse(status["fg_info"]["has_fg"])
        self.assertFalse(status["avoidance_active"])

    def test_inject_clean_game(self):
        """Verify injection into a game without Frame Generation (standalone mode)."""
        ok, msg = DLSS5Injector.inject(str(self.game_dir))
        self.assertTrue(ok, msg)
        self.assertIn("✅", msg)

        # Check injected files
        addon_dest = self.game_dir / "renodx-dlss.addon64"
        runtime_dest = self.game_dir / "nvngx_dlssnr.dll"
        dxgi_dest = self.game_dir / "dxgi.dll"
        ini_dest = self.game_dir / "ReShade.ini"
        manifest_dest = self.game_dir / ".dlss5_patch_manifest.json"

        self.assertTrue(addon_dest.exists())
        self.assertTrue(runtime_dest.exists())
        self.assertTrue(dxgi_dest.exists())
        self.assertTrue(ini_dest.exists())
        self.assertTrue(manifest_dest.exists())

        # Check manifest
        with open(manifest_dest, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        self.assertTrue(manifest["reshade_injected_by_dlss5"])
        self.assertTrue(manifest["runtime_injected_by_dlss5"])
        self.assertIn("nvngx_dlssnr.dll", manifest["injected_files"])

        # Check ReShade.ini: LoadFromDllMain must NOT contain dlss5 addon (Loader Lock Deadlock prevention)
        ini_text = ini_dest.read_text(encoding="utf-8")
        self.assertNotIn("LoadFromDllMain=lecram", ini_text)
        self.assertIn("NRRuntimePath=.\\nvngx_dlssnr.dll", ini_text)

        # Check status
        status = DLSS5Injector.get_status(str(self.game_dir))
        self.assertTrue(status["is_injected"])
        self.assertTrue(status["has_addon"])
        self.assertTrue(status["has_runtime"])
        self.assertTrue(status["has_dxgi"])

    def test_rhi_collision_avoidance(self):
        """
        CRITICAL TEST 1: RHI RenoDX Frame Generation Avoidance.
        'RHI的插帧才不需要重新装' -> ReShade base dxgi.dll is ALREADY installed by RHI/RenoDX.
        DLSS 5 must NOT overwrite dxgi.dll, avoids base reinstallation, and directly chains addon.
        """
        # 1. Simulate existing App 2 (RHI RenoDX Frame Generation) injection
        mock_mfg_dxgi = b"MOCK_RESHADE_ADDON_HOST_FOR_MFG" + b"\x00" * 1024
        (self.game_dir / "dxgi.dll").write_bytes(mock_mfg_dxgi)
        (self.game_dir / "renodx-mfgunlock.addon64").write_bytes(b"MOCK_RENODX_ADDON")
        (self.game_dir / ".mfg_patch_manifest.json").write_text(json.dumps({
            "active_backend": "reshade_addon",
            "injected_files": ["renodx-mfgunlock.addon64", "dxgi.dll", "ReShade.ini"]
        }), encoding="utf-8")

        initial_ini = (
            "[GENERAL]\n"
            "EffectSearchPaths=.\\\n"
            "[ADDON]\n"
            "LoadFromDllMain=renodx-mfgunlock.addon64\n"
        )
        (self.game_dir / "ReShade.ini").write_text(initial_ini, encoding="utf-8")

        # 2. Status should detect RHI Frame Generation and activate avoidance
        status_before = DLSS5Injector.get_status(str(self.game_dir))
        self.assertTrue(status_before["fg_info"]["has_fg"])
        self.assertTrue(status_before["fg_info"]["is_rhi_fg"])
        self.assertTrue(status_before["avoidance_active"])
        self.assertFalse(status_before["is_injected"])

        # 3. Base injection should be avoided
        ok_base, msg_base = DLSS5Injector.inject_reshade_base(str(self.game_dir))
        self.assertTrue(ok_base)
        self.assertIn("免重复安装", msg_base)

        # 4. Inject DLSS 5
        ok, msg = DLSS5Injector.inject(str(self.game_dir))
        self.assertTrue(ok, msg)
        self.assertIn("避让生效", msg)

        # 5. CRITICAL VERIFICATION: dxgi.dll MUST NOT BE OVERWRITTEN!
        dxgi_bytes = (self.game_dir / "dxgi.dll").read_bytes()
        self.assertEqual(dxgi_bytes, mock_mfg_dxgi, "dxgi.dll was modified despite RHI being present!")

        # 6. DLSS 5 addon and runtime must be copied
        addon_dest = self.game_dir / "renodx-dlss.addon64"
        runtime_dest = self.game_dir / "nvngx_dlssnr.dll"
        self.assertTrue(addon_dest.exists())
        self.assertTrue(runtime_dest.exists())

        # 7. ReShade.ini must contain RenoDX in LoadFromDllMain, but NOT dlss5 addon (Loader Lock safe!)
        ini_content = (self.game_dir / "ReShade.ini").read_text(encoding="utf-8")
        self.assertIn("renodx-mfgunlock.addon64", ini_content)
        self.assertNotIn("lecram-dlss5-beta10.addon64", ini_content)
        self.assertIn("NRRuntimePath=.\\nvngx_dlssnr.dll", ini_content)

        # 8. Check manifest flags
        manifest_dest = self.game_dir / ".dlss5_patch_manifest.json"
        with open(manifest_dest, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        self.assertFalse(manifest["reshade_injected_by_dlss5"])
        self.assertTrue(manifest["rhi_avoidance_active"])

        # 9. Test Restore: DLSS 5 must be removed WITHOUT destroying RHI Frame Generation!
        ok_restore, msg_restore = DLSS5Injector.restore(str(self.game_dir))
        self.assertTrue(ok_restore, msg_restore)

        # DLSS 5 addon and runtime must be gone
        self.assertFalse(addon_dest.exists())
        self.assertFalse(runtime_dest.exists())
        self.assertFalse(manifest_dest.exists())

        # Frame Generation files MUST REMAIN INTACT!
        self.assertTrue((self.game_dir / "renodx-mfgunlock.addon64").exists())
        self.assertTrue((self.game_dir / "dxgi.dll").exists())
        self.assertEqual((self.game_dir / "dxgi.dll").read_bytes(), mock_mfg_dxgi)
        self.assertTrue((self.game_dir / ".mfg_patch_manifest.json").exists())

        # ReShade.ini should still have renodx-mfgunlock
        ini_after = (self.game_dir / "ReShade.ini").read_text(encoding="utf-8")
        self.assertIn("renodx-mfgunlock.addon64", ini_after)
        self.assertNotIn("DLSS5", ini_after)

    def test_optiscaler_coexistence(self):
        """
        CRITICAL TEST 2: OptiScaler Frame Generation Coexistence & Anti-Preset D Enforcement.
        'opt插帧应该和RHIdlss5共存啊' -> OptiScaler is preserved as dxgi.dll.
        ReShade64.dll is deployed alongside OptiScaler and LoadReshade=true is configured in OptiScaler.ini.
        Preset D is strictly prevented and Preset K (DLSS 4 Transformer model) is enforced!
        """
        # 1. Simulate existing App 2 (OptiScaler Frame Generation) injection with Preset D or unconfigured
        mock_opti_dxgi = b"MOCK_OPTISCALER_DXGI_DLL" + b"\x00" * 1024
        (self.game_dir / "dxgi.dll").write_bytes(mock_opti_dxgi)
        (self.game_dir / "OptiScaler.dll").write_bytes(b"MOCK_OPTISCALER_CORE")
        (self.game_dir / "OptiScaler.ini").write_text(
            "[Plugins]\n"
            "LoadReshade=auto\n"
            "LoadSpecialK=auto\n\n"
            "[DLSS]\n"
            "RenderPresetOverride=auto\n"
            "RenderPresetForAll=4\n",  # Preset D simulation
            encoding="utf-8"
        )
        (self.game_dir / ".mfg_patch_manifest.json").write_text(json.dumps({
            "active_backend": "optiscaler",
            "injected_files": ["dxgi.dll", "OptiScaler.dll", "OptiScaler.ini"]
        }), encoding="utf-8")

        # 2. Status check
        status_before = DLSS5Injector.get_status(str(self.game_dir))
        self.assertTrue(status_before["fg_info"]["has_fg"])
        self.assertTrue(status_before["fg_info"]["is_optiscaler_fg"])
        self.assertFalse(status_before["avoidance_active"])
        self.assertTrue(status_before["optiscaler_coexisting"])

        # 3. Test base deployment for OptiScaler
        ok_base, msg_base = DLSS5Injector.inject_reshade_base(str(self.game_dir))
        self.assertTrue(ok_base, msg_base)
        self.assertIn("链式共存底座部署成功", msg_base)
        self.assertTrue((self.game_dir / "ReShade64.dll").exists())

        # Check OptiScaler.ini LoadReshade=true and Preset K enforced
        opti_ini = (self.game_dir / "OptiScaler.ini").read_text(encoding="utf-8")
        self.assertIn("LoadReshade=true", opti_ini)
        self.assertIn("RenderPresetForAll=11", opti_ini)
        self.assertNotIn("RenderPresetForAll=4", opti_ini)

        # 4. Inject DLSS 5
        ok, msg = DLSS5Injector.inject(str(self.game_dir))
        self.assertTrue(ok, msg)
        self.assertIn("OptiScaler 链式共存模式生效", msg)

        # 5. Check files
        self.assertTrue((self.game_dir / "renodx-dlss.addon64").exists())
        self.assertTrue((self.game_dir / "nvngx_dlssnr.dll").exists())
        self.assertTrue((self.game_dir / "ReShade.ini").exists())
        # OptiScaler dxgi.dll MUST NOT BE OVERWRITTEN!
        self.assertEqual((self.game_dir / "dxgi.dll").read_bytes(), mock_opti_dxgi)

        # 6. Check restore
        ok_restore, msg_restore = DLSS5Injector.restore(str(self.game_dir))
        self.assertTrue(ok_restore, msg_restore)
        self.assertFalse((self.game_dir / "renodx-dlss.addon64").exists())
        self.assertFalse((self.game_dir / "nvngx_dlssnr.dll").exists())
        self.assertFalse((self.game_dir / "ReShade64.dll").exists())

        # OptiScaler files remain intact!
        self.assertTrue((self.game_dir / "OptiScaler.dll").exists())
        self.assertTrue((self.game_dir / "dxgi.dll").exists())
        self.assertEqual((self.game_dir / "dxgi.dll").read_bytes(), mock_opti_dxgi)

        # OptiScaler.ini resets LoadReshade to auto, but keeps anti-D model
        opti_ini_restored = (self.game_dir / "OptiScaler.ini").read_text(encoding="utf-8")
        self.assertIn("LoadReshade=auto", opti_ini_restored)
        self.assertIn("RenderPresetForAll=11", opti_ini_restored)

    def test_anti_preset_d_enforcement(self):
        """Verify enforce_optiscaler_anti_d_preset upgrades Preset D and preserves user models."""
        ini_path = self.game_dir / "test_opti.ini"

        # Case 1: Preset D (4) -> Must be upgraded to Preset K (11)
        ini_path.write_text(
            "[DLSS]\n"
            "RenderPresetOverride=true\n"
            "RenderPresetForAll=4\n"
            "RenderPresetDLAA=4\n",
            encoding="utf-8"
        )
        enforce_optiscaler_anti_d_preset(ini_path)
        content1 = ini_path.read_text(encoding="utf-8")
        self.assertIn("RenderPresetForAll=11", content1)
        self.assertIn("RenderPresetDLAA=11", content1)
        self.assertNotIn("RenderPresetForAll=4", content1)

        # Case 2: User custom Preset M (13) -> Must be PRESERVED in [DLSS]
        ini_path.write_text(
            "[DLSS]\n"
            "RenderPresetOverride=true\n"
            "RenderPresetForAll=13\n"
            "RenderPresetDLAA=13\n",
            encoding="utf-8"
        )
        enforce_optiscaler_anti_d_preset(ini_path)
        content2 = ini_path.read_text(encoding="utf-8")
        self.assertIn("RenderPresetForAll=13", content2)
        dlss_part = content2.split("[DLSSD]")[0]
        self.assertNotIn("RenderPresetForAll=11", dlss_part)

    def test_loader_lock_prevention(self):
        """Verify ReShade.ini avoids LoadFromDllMain deadlock entries and sets NRRuntimePath."""
        ini_path = self.game_dir / "test_reshade.ini"
        ini_path.write_text(
            "[ADDON]\n"
            "LoadFromDllMain=1,lecram-dlss5-beta10.addon64,other_plugin.addon64\n",
            encoding="utf-8"
        )
        _configure_reshade_ini_for_dlss5(ini_path, remove=False)
        content = ini_path.read_text(encoding="utf-8")

        # '1' and 'lecram-dlss5-beta10.addon64' must be stripped!
        self.assertNotIn("=1,", content)
        self.assertNotIn("lecram-dlss5-beta10", content)
        self.assertIn("LoadFromDllMain=other_plugin.addon64", content)
        self.assertIn("NRRuntimePath=.\\nvngx_dlssnr.dll", content)

    def test_restore_clean_game(self):
        """Verify restoring a standalone DLSS 5 injection cleans up all its deployed files."""
        DLSS5Injector.inject(str(self.game_dir))
        self.assertTrue((self.game_dir / "renodx-dlss.addon64").exists())
        self.assertTrue((self.game_dir / "nvngx_dlssnr.dll").exists())
        self.assertTrue((self.game_dir / "dxgi.dll").exists())

        ok, msg = DLSS5Injector.restore(str(self.game_dir))
        self.assertTrue(ok, msg)
        self.assertFalse((self.game_dir / "renodx-dlss.addon64").exists())
        self.assertFalse((self.game_dir / "nvngx_dlssnr.dll").exists())
        self.assertFalse((self.game_dir / "dxgi.dll").exists())
        self.assertFalse((self.game_dir / ".dlss5_patch_manifest.json").exists())


    def test_mfg_dlss5_crash_guard_and_safe_routing(self):
        """
        Verify that write_game_dlss5_config automatically protects against D3D12 command list collisions
        and VRAM thrashing when Multi-Frame Generation is detected.
        """
        from apps.app6_dlss5.engine.dlss5_config import write_game_dlss5_config
        from apps.app2_mfg.core.ini_sync import IniConfigManager

        ini_path = self.game_dir / "ReShade.ini"

        # Case 1: Standalone game without Frame Generation -> user choices are respected
        cfg_standalone = {
            "uplift": 1,
            "hook_point": 0,  # After Upscaling
            "vram": "Full"
        }
        ok = write_game_dlss5_config(ini_path, cfg_standalone)
        self.assertTrue(ok)
        sec = IniConfigManager.read_ini_sections(ini_path)["DLSS5"]
        self.assertEqual(sec.get("NRHookPoint"), "0")
        self.assertEqual(sec.get("NRVramBuffering"), "0")

        # Case 2: Game has Mode A (version.dll) active -> safety guard must reroute to Present (2) and Reduced
        (self.game_dir / "version.dll").write_bytes(b"MOCK_MFG_VERSION_DLL")
        cfg_mfg = {
            "uplift": 1,
            "hook_point": 0,  # Dangerous After Upscaling under MFG
            "vram": "Full"    # Dangerous Full buffering under 4K MFG
        }
        ok_mfg = write_game_dlss5_config(ini_path, cfg_mfg)
        self.assertTrue(ok_mfg)
        sec_mfg = IniConfigManager.read_ini_sections(ini_path)["DLSS5"]
        self.assertEqual(sec_mfg.get("NRHookPoint"), "2")
        self.assertEqual(sec_mfg.get("NRVramBuffering"), "1")


    def test_deep_clean_coexistence_purge(self):
        """
        Verify that RollbackEngine.rollback(clean_all=True) and DLSS5Injector.restore(force_clean_all=True)
        completely purge all injected proxies, mod folders, logs, crash dumps, and configs when both
        OptiScaler (Mode C) and DLSS 5 coexist, restoring 100% pure baseline without leaving artifacts.
        """
        from apps.app2_mfg.core.rollback import RollbackEngine

        # 1. Simulate game directory cluttered with OptiScaler + DLSS 5 + logs + crash dumps
        (self.game_dir / "dxgi.dll").write_bytes(b"OPTISCALER_PROXY_26MB" + b"\x00" * 1024)
        (self.game_dir / "ReShade64.dll").write_bytes(b"RESHADE_CORE" + b"\x00" * 1024)
        (self.game_dir / "renodx-dlss.addon64").write_bytes(b"DLSS5_ADDON" + b"\x00" * 1024)
        (self.game_dir / "nvngx_dlssnr.dll").write_bytes(b"DLSS5_RUNTIME" + b"\x00" * 1024)
        (self.game_dir / "fakenvapi.dll").write_bytes(b"FAKENVAPI" + b"\x00" * 1024)
        (self.game_dir / "fakenvapi.ini").write_text("[fakenvapi]\nenabled=true", encoding="utf-8")
        (self.game_dir / "OptiScaler.ini").write_text("[Plugins]\nLoadReshade=true", encoding="utf-8")
        (self.game_dir / "ReShade.ini").write_text("[DLSS5]\nNRHookPoint=2", encoding="utf-8")
        (self.game_dir / ".dlss5_config.json").write_text("{}", encoding="utf-8")
        (self.game_dir / ".dlss5_patch_manifest.json").write_text("{}", encoding="utf-8")
        (self.game_dir / ".mfg_patch_manifest.json").write_text(json.dumps({
            "game_name": "TestGame",
            "active_backend": "optiscaler",
            "created_files": ["dxgi.dll", "OptiScaler.ini"],
            "renamed_backups": []
        }), encoding="utf-8")

        # Mod directories
        (self.game_dir / "OptiScaler").mkdir(exist_ok=True)
        (self.game_dir / "OptiScaler" / "dummy.txt").write_text("dummy", encoding="utf-8")
        (self.game_dir / "dlss5-nr-runtime").mkdir(exist_ok=True)
        (self.game_dir / "dlss5-nr-runtime" / "dummy.txt").write_text("dummy", encoding="utf-8")
        (self.game_dir / "XeSS").mkdir(exist_ok=True)
        (self.game_dir / "amd_fidelityfx").mkdir(exist_ok=True)

        # Logs and crash dumps
        (self.game_dir / "dlss5-nr-crash-001.txt").write_text("CRASH DUMP", encoding="utf-8")
        (self.game_dir / "dlss5-nr-crash-002.txt").write_text("CRASH DUMP", encoding="utf-8")
        (self.game_dir / "RTXMFG-20261021.log").write_text("LOG", encoding="utf-8")
        (self.game_dir / "RTXMFG-20261021.csv").write_text("CSV", encoding="utf-8")
        (self.game_dir / "OptiScaler.log").write_text("LOG", encoding="utf-8")
        (self.game_dir / "ReShade.log").write_text("LOG", encoding="utf-8")

        # Verify cluttered state
        self.assertTrue((self.game_dir / "dxgi.dll").exists())
        self.assertTrue((self.game_dir / "renodx-dlss.addon64").exists())
        self.assertTrue((self.game_dir / "OptiScaler").is_dir())

        # 2. Test DLSS5Injector.restore with force_clean_all=True
        ok, msg = DLSS5Injector.restore(str(self.game_dir), force_clean_all=True)
        self.assertTrue(ok, msg)

        # 3. Assert EVERY SINGLE foreign file and directory is purged
        self.assertFalse((self.game_dir / "dxgi.dll").exists(), "dxgi.dll must be deleted!")
        self.assertFalse((self.game_dir / "ReShade64.dll").exists(), "ReShade64.dll must be deleted!")
        self.assertFalse((self.game_dir / "renodx-dlss.addon64").exists(), "DLSS5 addon must be deleted!")
        self.assertFalse((self.game_dir / "nvngx_dlssnr.dll").exists(), "nvngx_dlssnr.dll must be deleted!")
        self.assertFalse((self.game_dir / "fakenvapi.dll").exists(), "fakenvapi.dll must be deleted!")
        self.assertFalse((self.game_dir / "fakenvapi.ini").exists(), "fakenvapi.ini must be deleted!")
        self.assertFalse((self.game_dir / "OptiScaler.ini").exists(), "OptiScaler.ini must be deleted!")
        self.assertFalse((self.game_dir / "ReShade.ini").exists(), "ReShade.ini must be deleted!")
        self.assertFalse((self.game_dir / ".dlss5_config.json").exists(), ".dlss5_config.json must be deleted!")
        self.assertFalse((self.game_dir / ".dlss5_patch_manifest.json").exists(), ".dlss5_patch_manifest.json must be deleted!")
        self.assertFalse((self.game_dir / ".mfg_patch_manifest.json").exists(), ".mfg_patch_manifest.json must be deleted!")

        self.assertFalse((self.game_dir / "OptiScaler").exists(), "OptiScaler dir must be deleted!")
        self.assertFalse((self.game_dir / "dlss5-nr-runtime").exists(), "dlss5-nr-runtime dir must be deleted!")
        self.assertFalse((self.game_dir / "XeSS").exists(), "XeSS dir must be deleted!")
        self.assertFalse((self.game_dir / "amd_fidelityfx").exists(), "amd_fidelityfx dir must be deleted!")

        self.assertFalse((self.game_dir / "dlss5-nr-crash-001.txt").exists(), "Crash dump must be deleted!")
        self.assertFalse((self.game_dir / "dlss5-nr-crash-002.txt").exists(), "Crash dump must be deleted!")
        self.assertFalse((self.game_dir / "RTXMFG-20261021.log").exists(), "RTXMFG log must be deleted!")
        self.assertFalse((self.game_dir / "RTXMFG-20261021.csv").exists(), "RTXMFG csv must be deleted!")
        self.assertFalse((self.game_dir / "OptiScaler.log").exists(), "OptiScaler log must be deleted!")
        self.assertFalse((self.game_dir / "ReShade.log").exists(), "ReShade log must be deleted!")

        # Game executable MUST remain intact
        self.assertTrue((self.game_dir / "Cyberpunk2077.exe").exists(), "Game exe must remain intact!")



    def test_dual_architecture_model_routing(self):
        """Verify dual-architecture GPU detection and runtime selection (RTX 50 vs RTX 20/30/40)."""
        from apps.app6_dlss5.engine.injector import detect_system_gpu, get_dlss5_runtime_dll_path
        gpu_info = detect_system_gpu()
        self.assertIn("arch", gpu_info)
        self.assertIn("gpu_name", gpu_info)
        
        # Test explicit architecture resolution
        rtx50_path = get_dlss5_runtime_dll_path(arch="rtx50")
        self.assertIsNotNone(rtx50_path)
        self.assertTrue(os.path.exists(rtx50_path))
        
        rtx20_path = get_dlss5_runtime_dll_path(arch="rtx20_30_40")
        self.assertIsNotNone(rtx20_path)
        self.assertTrue(os.path.exists(rtx20_path))


    def test_dlss5_panel_params(self):
        """Verify DLSS 5 configuration read/write and default RenoDX values."""
        from apps.app6_dlss5.engine.dlss5_config import DEFAULT_DLSS5_CONFIG, read_game_dlss5_config, write_game_dlss5_config
        self.assertIn("status", DEFAULT_DLSS5_CONFIG)
        self.assertIn("style", DEFAULT_DLSS5_CONFIG)
        self.assertIn("dlss_preset", DEFAULT_DLSS5_CONFIG)
        self.assertEqual(DEFAULT_DLSS5_CONFIG["style"], 2)
        self.assertEqual(DEFAULT_DLSS5_CONFIG["dlss_preset"], 0)

        ok = write_game_dlss5_config(str(self.game_dir), DEFAULT_DLSS5_CONFIG)
        self.assertTrue(ok)
        read_cfg = read_game_dlss5_config(str(self.game_dir))
        self.assertEqual(read_cfg.get("status"), 1)
        self.assertEqual(read_cfg.get("style"), 2)
        self.assertEqual(read_cfg.get("dlss_preset"), 0)

if __name__ == "__main__":
    unittest.main()
