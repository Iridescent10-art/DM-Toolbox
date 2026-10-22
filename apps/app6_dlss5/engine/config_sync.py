# -*- coding: utf-8 -*-
"""
Unified Configuration & Two-Way Synchronization Service.
Bridges DLSS 5 Injector UI with Mode A, Mode B, and Mode C Multi-Frame Generation,
maintaining shared state with App 2 and synchronizing game directory INI/JSON files.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List, Union

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

MFG_DIR = ROOT_DIR / "apps" / "app2_mfg"
if str(MFG_DIR) not in sys.path:
    sys.path.insert(0, str(MFG_DIR))

from apps.app2_mfg.core.models import GameInfo, BackendType, QualificationStatus
from apps.app2_mfg.core.updater import ComponentUpdater
from apps.app2_mfg.core.patcher import PatchEngine
from apps.app2_mfg.core.ini_sync import IniConfigManager, DLSS_PRESET_MAP, VK_KEY_MAP
from apps.app2_mfg.core.optiscaler_config import (
    load_mode_a_preset, save_mode_a_preset,
    load_reshade_preset, save_reshade_preset,
    load_optiscaler_preset, save_optiscaler_preset,
    load_dlssg_sm86_preset, save_dlssg_sm86_preset
)
from apps.app2_mfg.core.state_cleaner import CleanGameDirectoryState
from apps.app6_dlss5.engine.injector import DLSS5Injector, check_dlss5_status


class ConfigSyncService:
    """Manages two-way configuration synchronization between DLSS 5 UI and Game Directory."""

    @staticmethod
    def detect_active_mode(target_dir: Union[str, Path]) -> str:
        """
        Detects active Multi-Frame Generation mode in target directory:
        Returns 'A', 'B', 'C', or '' (None).
        """
        td = Path(target_dir)
        if not td.exists() or not td.is_dir():
            return ""

        manifest_file = td / ".mfg_patch_manifest.json"
        if manifest_file.exists():
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    backend = data.get("active_backend") or data.get("backend") or ""
                    backend_s = str(backend).lower()
                    if "dlssg" in backend_s or "sm86" in backend_s:
                        return "C"
                    if "optiscaler" in backend_s:
                        return "D"
                    if "reshade" in backend_s or "renodx" in backend_s:
                        return "B"
                    if "standalone" in backend_s or "dashdogy" in backend_s:
                        return "A"
            except Exception:
                pass

        if (td / "dlssg_sm86.ini").exists() or (td / "dlssg_sm86").exists():
            return "C"
        if (td / "OptiScaler.ini").exists() or (td / "OptiScaler.dll").exists():
            return "D"
        if (td / "renodx-mfgunlock.addon64").exists():
            return "B"
        if (td / "RTXMFG-UI.ini").exists() or (td / "mfg_unlocker.ini").exists() or (td / "version.dll").exists():
            return "A"

        return ""

    @staticmethod
    def load_mode_config(target_dir: Union[str, Path], mode: str) -> Dict[str, Any]:
        """Loads configuration for given mode, reading live game files if present."""
        td = Path(target_dir)
        mode = mode.upper()

        if mode == "A":
            preset = load_mode_a_preset()
            if td.exists():
                disk_a = IniConfigManager.read_mode_a_reverse(td)
                if disk_a:
                    preset.update(disk_a)
                # Read RTXMFG-Universal.json if present
                u_json = td / "RTXMFG-Universal.json"
                if u_json.exists():
                    try:
                        with open(u_json, "r", encoding="utf-8") as f:
                            ud = json.load(f)
                            if "multiplier" in ud:
                                preset["multiplier"] = int(ud["multiplier"])
                            if "dlssPreset" in ud:
                                p_val = int(ud["dlssPreset"])
                                p_rev = {
                                    0: "Default", 13: "M", 12: "L", 11: "K", 10: "J",
                                    6: "F", 5: "E", 4: "D", 3: "C", 2: "B", 1: "A"
                                }
                                preset["dlss_preset"] = p_rev.get(p_val, "K")
                    except Exception:
                        pass
            return preset

        elif mode == "B":
            preset = load_reshade_preset()
            if td.exists():
                disk_b = IniConfigManager.read_mode_b_reverse(td)
                if disk_b:
                    preset.update(disk_b)
            return preset

        elif mode == "C":
            preset = load_dlssg_sm86_preset()
            if td.exists():
                disk_c = IniConfigManager.read_mode_d_reverse(td)
                if disk_c:
                    preset.update(disk_c)
            return preset

        elif mode == "D":
            preset = load_optiscaler_preset()
            if td.exists():
                disk_d = IniConfigManager.read_mode_c_reverse(td)
                if disk_d:
                    preset.update(disk_d)
            return preset

        return {}

    @staticmethod
    def apply_unified_configuration(
        target_dir: Union[str, Path],
        game_exe: str,
        mode: str,
        params: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Executes unified transactional deployment:
        1. Atomic slot cleanup with CleanGameDirectoryState.
        2. Applies Multi-Frame Generation backend patch (Mode A, B, or C).
        3. Deploys DLSS 5 addon and runtime (nvngx_dlssnr.dll).
        4. Synchronizes all configuration files (RTXMFG-Universal.json / ReShade.ini / OptiScaler.ini).
        """
        td = Path(target_dir)
        if not td.exists() or not td.is_dir():
            return False, f"目标目录不存在: {target_dir}"

        mode = mode.upper()
        if mode not in ("A", "B", "C", "D"):
            return False, f"未知的工作模式: {mode}"

        updater = ComponentUpdater()
        patcher = PatchEngine(updater)

        game_name = Path(game_exe).stem if game_exe else "Game"
        game_info = GameInfo(
            name=game_name,
            source="Custom",
            install_dir=str(td),
            target_dir=str(td),
            exe_path=str(td / game_exe) if game_exe else str(td),
            exe_name=os.path.basename(game_exe) if game_exe else "game.exe",
            has_reshade=(td / "ReShade.ini").exists() or (td / "dxgi.dll").exists(),
            is_patched=False,
            qualification=QualificationStatus.QUALIFIED
        )

        # Step 1: Clean slot state (preserve DLSS 5 if already present)
        CleanGameDirectoryState(td, preserve_dlss5=True, target_mode=mode)

        # Step 2: Apply Mode Patch and synchronize configurations
        if mode == "A":
            # Update and save Mode A preset
            preset_a = load_mode_a_preset()
            preset_a["multiplier"] = int(params.get("multiplier", 3))
            preset_a["dlss_preset"] = params.get("dlss_preset", "K")
            preset_a["menu_key"] = params.get("menu_key", "Backspace")
            preset_a["bink_hook"] = bool(params.get("bink_hook", False))
            save_mode_a_preset(preset_a)

            ok, msg = patcher.patch_game(game_info, requested_backend=BackendType.STANDALONE, prefer_bink_hook=preset_a["bink_hook"])
            if not ok:
                return False, f"模式 A 注入失败: {msg}"

            IniConfigManager.sync_mode_a_forward(td, preset_a)

        elif mode == "B":
            preset_b = load_reshade_preset()
            preset_b["force_multiplier"] = int(params.get("multiplier", 3))
            preset_b["dlss_preset"] = params.get("dlss_preset", "K")
            preset_b["blackwell_kernels"] = int(params.get("blackwell_kernels", 1))
            preset_b["thin_geometry_isr"] = int(params.get("thin_geometry_isr", 1))
            preset_b["thin_geometry_vwb"] = int(params.get("thin_geometry_vwb", 1))
            preset_b["thin_geometry_bam"] = int(params.get("thin_geometry_bam", 1))
            preset_b["hdr_ui_recomposition"] = int(params.get("hdr_ui_recomposition", 1))
            preset_b["dynamic_mfg"] = int(params.get("dynamic_mfg", 0))
            preset_b["temporal_fix"] = int(params.get("temporal_fix", 1))
            preset_b["hdr_compatibility"] = int(params.get("hdr_compatibility", 0))
            save_reshade_preset(preset_b)

            ok, msg = patcher.patch_game(game_info, requested_backend=BackendType.RESHADE_ADDON)
            if not ok:
                return False, f"模式 B 注入失败: {msg}"

            IniConfigManager.sync_mode_b_forward(td, preset_b)

        elif mode == "C":
            preset_c = load_dlssg_sm86_preset()
            if "max_generated_frames" in params:
                preset_c["max_generated_frames"] = int(params["max_generated_frames"])
            elif "multiplier" in params:
                preset_c["max_generated_frames"] = max(1, min(5, int(params["multiplier"]) - 1))
            if "optimized" in params:
                preset_c["optimized"] = int(params["optimized"])
            if "dlssg_preset" in params:
                preset_c["dlssg_preset"] = str(params["dlssg_preset"])
            if "super_resolution_mode" in params:
                preset_c["super_resolution_mode"] = str(params["super_resolution_mode"])
            if "engine" in params:
                preset_c["engine"] = str(params["engine"])
            if "proxy_dll" in params:
                preset_c["proxy_dll"] = str(params["proxy_dll"])
            save_dlssg_sm86_preset(preset_c)

            ok, msg = patcher.patch_game(game_info, requested_backend=BackendType.DLSSG_SM86)
            if not ok:
                return False, f"模式 C 注入失败: {msg}"

            IniConfigManager.sync_mode_d_forward(td, preset_c, exe_name=game_info.exe_name)

        elif mode == "D":
            preset_d = load_optiscaler_preset()
            preset_d["interpolation_count"] = int(params.get("interpolation_count", max(1, int(params.get("multiplier", 3)) - 1)))
            preset_d["dlss_preset"] = params.get("dlss_preset", "K")
            preset_d["menu_key"] = params.get("menu_key", "Insert")
            preset_d["fg_output"] = params.get("fg_output", "xefg")
            preset_d["fg_input"] = params.get("fg_input", "dlssg")
            preset_d["dx12_upscaler"] = params.get("dx12_upscaler", "dlss")
            preset_d["rcas_enabled"] = bool(params.get("rcas_enabled", False))
            preset_d["rcas_sharpness"] = float(params.get("rcas_sharpness", 0.0))
            save_optiscaler_preset(preset_d)

            ok, msg = patcher.patch_game(game_info, requested_backend=BackendType.OPTISCALER_FSR)
            if not ok:
                return False, f"模式 D 注入失败: {msg}"

            IniConfigManager.sync_mode_c_forward(td, preset_d, exe_name=game_info.exe_name)

        # Step 3: Deploy DLSS 5 addon & runtime
        ok_dlss5, msg_dlss5 = DLSS5Injector.inject(str(td), dlss5_config=params.get("dlss5_params"))
        if not ok_dlss5:
            return False, f"多帧生成注入成功，但 DLSS 5 挂载失败: {msg_dlss5}"

        mode_names = {
            "A": "模式 A (dashdogy 独立代理)",
            "B": "模式 B (RenoDX 插件优化)",
            "C": "模式 C (DLSSG-SM86 原生插帧)",
            "D": "模式 D (OptiScaler 跨卡转译)"
        }
        res_msg = (
            f"✅ 【{mode_names.get(mode)} + DLSS 5 神经重构】联动注入成功！\n\n"
            f"⚡ 插帧配置已自动同步至游戏目录及控制台。\n"
            f"🎮 启动游戏后按对应热键即可调校（模式 A: Backspace，模式 B: Home，模式 D: Insert）。"
        )
        return True, res_msg
