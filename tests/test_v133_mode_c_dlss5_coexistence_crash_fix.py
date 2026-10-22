import os
import sys
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

# Setup paths
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root_dir)
sys.path.insert(0, os.path.join(root_dir, "apps", "app2_mfg"))

from core.ini_sync import IniConfigManager, LEGACY_OPTISCALER_KEYS
from core.optiscaler_config import DEFAULT_OPTISCALER_PRESET
from core.patcher import PatchEngine
from core.models import GameInfo, BackendType, QualificationStatus, PatchManifest
from apps.app6_dlss5.engine.dlss5_config import write_game_dlss5_config, read_game_dlss5_config, load_dlss5_preset
from apps.app6_dlss5.engine.injector import set_optiscaler_load_reshade, _create_default_reshade_ini


class TestModeCDLSS5CoexistenceCrashFix(unittest.TestCase):
    """
    Validates fixes for simultaneous Mode C (OptiScaler XeFG multi-frame generation)
    and DLSS 5 (RenoDX neural reconstruction) injection:
    1. OptiScaler.ini crash prevention:
       - UseNtdllHooks = false (Windows 11 24H2 0xC0000374 heap corruption fix)
       - CreateD3D12DeviceForLuma = true (D3D12 device init prior to ReShade)
       - SimulateWaitableObject = true (frame latency waitable object fix)
       - StreamlineSpoofing = false (native NVIDIA Streamline routing)
       - Legacy [LoadDlls] section purged
    2. ReShade.ini hook isolation:
       - [INSTALL] HookStreamline = 1 (hooks Streamline instead of wrapping DXGI)
       - [INSTALL] HookDirectX = 0
    3. ASI conflict avoidance:
       - When DLSS 5 is present, MFGUnlocker.asi AND MFGUnlocker-loadlate.asi are NOT
         deployed into OptiScaler/plugins/ to prevent slInit MinHook conflict with
         renodx-dlss5.addon64.
       - Mode C XeFG native 2X~6X multi-frame generation via [XeFG] InterpolationCount is preserved.
    4. Dual ReShade init crash prevention:
       - d3d12-ReShade64.dll is purged when DLSS5 is active, because OptiScaler loads
         BOTH "ReShade64.dll" and "d3d12-ReShade64.dll" as chain-load targets.
         Having both causes duplicate D3D12 hook registration -> immediate crash.
    """

    def test_mode_c_forward_sync_crash_prevention_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            preset = dict(DEFAULT_OPTISCALER_PRESET)
            preset["interpolation_count"] = 2  # 3X frame gen
            ok = IniConfigManager.sync_mode_c_forward(td, preset, exe_name="test.exe")
            self.assertTrue(ok)

            opti_ini = os.path.join(td, "OptiScaler.ini")
            self.assertTrue(os.path.exists(opti_ini))

            secs = IniConfigManager.read_ini_sections(opti_ini)
            # 1. NTDLL heap corruption prevention
            self.assertEqual(secs.get("Hooks", {}).get("UseNtdllHooks"), "false")
            # 2. Luma / D3D12 device readiness
            self.assertEqual(secs.get("Hotfix", {}).get("CreateD3D12DeviceForLuma"), "true")
            # 3. SimulateWaitableObject for DXGI waitable swapchains
            self.assertEqual(secs.get("Hotfix", {}).get("SimulateWaitableObject"), "true")
            # 4. StreamlineSpoofing false on genuine NVIDIA hardware
            self.assertEqual(secs.get("Spoofing", {}).get("StreamlineSpoofing"), "false")
            # 5. Dead [LoadDlls] must not exist
            self.assertNotIn("LoadDlls", secs)
            # 6. Plugins must load Reshade and ASI
            self.assertEqual(secs.get("Plugins", {}).get("LoadReshade"), "true")
            self.assertEqual(secs.get("Plugins", {}).get("LoadAsiPlugins"), "true")
            # 7. XeFG multiplier retained
            self.assertEqual(secs.get("XeFG", {}).get("InterpolationCount"), "2")

    def test_dlss5_config_directx_routing_and_passthrough(self):
        with tempfile.TemporaryDirectory() as td:
            reshade_ini = os.path.join(td, "ReShade.ini")
            cfg = load_dlss5_preset()
            # Default preset has dlss_preset == 0
            ok = write_game_dlss5_config(reshade_ini, cfg)
            self.assertTrue(ok)

            secs = IniConfigManager.read_ini_sections(reshade_ini)
            self.assertIn("INSTALL", secs)
            # Must hook DirectX and NOT hook Streamline directly to preserve NVApp driver Model C
            self.assertEqual(secs["INSTALL"].get("HookDirectX"), "1")
            self.assertEqual(secs["INSTALL"].get("HookStreamline"), "0")

            # When dlss_preset == 0, DLSSPreset* must NOT be present in root or RenoDX sections
            root_sec = secs.get("", {})
            self.assertNotIn("DLSSPresetQuality", root_sec)
            self.assertNotIn("DLSSPresetDLAA", root_sec)
            self.assertNotIn("DirectNeuralRenderingPreset", root_sec)
            renodx_sec = secs.get("RENODX-DLSS", {})
            self.assertNotIn("DLSSPresetQuality", renodx_sec)

    def test_default_reshade_ini_contains_install_section(self):
        with tempfile.TemporaryDirectory() as td:
            reshade_ini = Path(td) / "ReShade.ini"
            _create_default_reshade_ini(reshade_ini)
            self.assertTrue(reshade_ini.exists())

            secs = IniConfigManager.read_ini_sections(reshade_ini)
            self.assertIn("INSTALL", secs)
            self.assertEqual(secs["INSTALL"].get("HookDirectX"), "1")
            self.assertEqual(secs["INSTALL"].get("HookStreamline"), "0")
            root_sec = secs.get("", {})
            self.assertNotIn("DLSSPresetQuality", root_sec)

    def test_dlss5_explicit_preset_writes_keys(self):
        with tempfile.TemporaryDirectory() as td:
            reshade_ini = os.path.join(td, "ReShade.ini")
            cfg = load_dlss5_preset()
            cfg["dlss_preset"] = 11  # Preset K
            ok = write_game_dlss5_config(reshade_ini, cfg)
            self.assertTrue(ok)

            secs = IniConfigManager.read_ini_sections(reshade_ini)
            root_sec = secs.get("", {})
            self.assertEqual(root_sec.get("DLSSPresetQuality"), "11")
            self.assertEqual(root_sec.get("DirectNeuralRenderingPreset"), "11")

    def test_set_optiscaler_load_reshade_applies_safe_coexistence(self):
        with tempfile.TemporaryDirectory() as td:
            opti_ini = Path(td) / "OptiScaler.ini"
            # Simulate pre-existing OptiScaler.ini with dangerous NTDLL hooks
            pre_content = (
                "[Plugins]\nLoadReshade=auto\n\n"
                "[Hooks]\nUseNtdllHooks=true\n\n"
                "[Hotfix]\nCreateD3D12DeviceForLuma=false\n\n"
                "[LoadDlls]\nLoadReshade=true\n"
            )
            opti_ini.write_text(pre_content, encoding="utf-8")

            ok = set_optiscaler_load_reshade(td, enable=True)
            self.assertTrue(ok)

            secs = IniConfigManager.read_ini_sections(opti_ini)
            self.assertEqual(secs.get("Plugins", {}).get("LoadReshade"), "true")
            self.assertEqual(secs.get("Hooks", {}).get("UseNtdllHooks"), "false")
            self.assertEqual(secs.get("Hotfix", {}).get("CreateD3D12DeviceForLuma"), "true")
            self.assertEqual(secs.get("Hotfix", {}).get("SimulateWaitableObject"), "true")
            self.assertEqual(secs.get("Spoofing", {}).get("StreamlineSpoofing"), "false")
            self.assertNotIn("LoadDlls", secs)

    def test_mfg_unlocker_asi_bypassed_when_dlss5_present(self):
        with tempfile.TemporaryDirectory() as td:
            from core.updater import ComponentUpdater
            updater = ComponentUpdater()
            patcher = PatchEngine(updater=updater)

            manifest = PatchManifest(
                app_version="1.3.1",
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

            # Case A: DLSS 5 present (renodx-dlss5.addon64 exists)
            addon_path = os.path.join(td, "renodx-dlss5.addon64")
            with open(addon_path, "wb") as f:
                f.write(b"FAKE_ADDON")

            with patch("core.patcher.get_system_gpu_name", return_value="NVIDIA GeForce RTX 4070 Laptop GPU"), \
                 patch("core.patcher.is_rtx_40_or_newer", return_value=True):
                ok, err = patcher._apply_optiscaler_patch(fake_game, manifest)
                self.assertTrue(ok, f"_apply_optiscaler_patch failed: {err}")

                asi_path = os.path.join(td, "OptiScaler", "plugins", "MFGUnlocker.asi")
                # When DLSS 5 is present, MFGUnlocker.asi must NOT be installed to prevent slInit MinHook conflict!
                self.assertFalse(os.path.exists(asi_path), "MFGUnlocker.asi must NOT be deployed when DLSS 5 addon is active")

                opti_ini = os.path.join(td, "OptiScaler.ini")
                secs = IniConfigManager.read_ini_sections(opti_ini)
                self.assertEqual(secs.get("Hooks", {}).get("UseNtdllHooks"), "false")
                self.assertEqual(secs.get("XeFG", {}).get("InterpolationCount"), "2")

    def test_mfg_unlocker_asi_deployed_when_dlss5_absent(self):
        with tempfile.TemporaryDirectory() as td:
            from core.updater import ComponentUpdater
            updater = ComponentUpdater()
            patcher = PatchEngine(updater=updater)

            manifest = PatchManifest(
                app_version="1.3.1",
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

            # Case B: DLSS 5 NOT present
            with patch("core.patcher.get_system_gpu_name", return_value="NVIDIA GeForce RTX 4070 Laptop GPU"), \
                 patch("core.patcher.is_rtx_40_or_newer", return_value=True):
                ok, err = patcher._apply_optiscaler_patch(fake_game, manifest)
                self.assertTrue(ok, f"_apply_optiscaler_patch failed: {err}")

                asi_path = os.path.join(td, "OptiScaler", "plugins", "MFGUnlocker.asi")
                self.assertTrue(os.path.exists(asi_path), "MFGUnlocker.asi must be deployed when DLSS 5 is absent")


    def test_loadlate_asi_variant_removed_when_dlss5_present(self):
        """MFGUnlocker-loadlate.asi must also be purged when DLSS5 is active (MinHook slInit conflict)."""
        with tempfile.TemporaryDirectory() as td:
            from core.updater import ComponentUpdater
            updater = ComponentUpdater()
            patcher = PatchEngine(updater=updater)

            manifest = PatchManifest(
                app_version="1.3.3",
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

            # DLSS5 present marker
            with open(os.path.join(td, "renodx-dlss5.addon64"), "wb") as f:
                f.write(b"FAKE_ADDON")

            # Pre-create -loadlate ASI variant in plugins dir
            plugins_dir = os.path.join(td, "OptiScaler", "plugins")
            os.makedirs(plugins_dir, exist_ok=True)
            loadlate_asi = os.path.join(plugins_dir, "MFGUnlocker-loadlate.asi")
            with open(loadlate_asi, "wb") as f:
                f.write(b"FAKE_LOADLATE_ASI")

            with patch("core.patcher.get_system_gpu_name", return_value="NVIDIA GeForce RTX 4070"), \
                 patch("core.patcher.is_rtx_40_or_newer", return_value=True):
                ok, err = patcher._apply_optiscaler_patch(fake_game, manifest)
                self.assertTrue(ok, f"_apply_optiscaler_patch failed: {err}")
                # -loadlate variant must be removed alongside standard .asi
                self.assertFalse(
                    os.path.exists(loadlate_asi),
                    "MFGUnlocker-loadlate.asi must be removed when DLSS5 is active"
                )

    def test_d3d12_reshade64_purged_when_dlss5_present(self):
        """d3d12-ReShade64.dll must be removed when DLSS5 is active to prevent dual ReShade init crash."""
        with tempfile.TemporaryDirectory() as td:
            from core.updater import ComponentUpdater
            updater = ComponentUpdater()
            patcher = PatchEngine(updater=updater)

            manifest = PatchManifest(
                app_version="1.3.3",
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

            # DLSS5 present marker
            with open(os.path.join(td, "renodx-dlss5.addon64"), "wb") as f:
                f.write(b"FAKE_ADDON")

            # Simulate d3d12-ReShade64.dll pre-existing (legacy deployment artifact)
            d3d12_reshade = os.path.join(td, "d3d12-ReShade64.dll")
            with open(d3d12_reshade, "wb") as f:
                f.write(b"FAKE_D3D12_RESHADE" * 100)

            with patch("core.patcher.get_system_gpu_name", return_value="NVIDIA GeForce RTX 4070"), \
                 patch("core.patcher.is_rtx_40_or_newer", return_value=True):
                ok, err = patcher._apply_optiscaler_patch(fake_game, manifest)
                self.assertTrue(ok, f"_apply_optiscaler_patch failed: {err}")
                self.assertFalse(
                    os.path.exists(d3d12_reshade),
                    "d3d12-ReShade64.dll must be purged when DLSS5 is active to prevent dual ReShade D3D12 hook crash"
                )


if __name__ == "__main__":
    unittest.main()
