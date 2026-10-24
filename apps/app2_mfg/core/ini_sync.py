from core.state_cleaner import is_dlss5_present
"""
IniConfigManager - Unified INI Configuration Manager & Real-Time Sync Engine.
Handles bi-directional synchronization between DM-Toolbox GUI and game directory INI configs
(OptiScaler.ini, ReShade.ini, RTXMFG-UI.ini, mfg_unlocker.ini).

OptiScaler v0.9.4+ rule: `OptiScaler.ini` is the ONLY legal config file. The legacy
`nvngx.ini` alias is detected by OptiScaler and triggers the in-game red warning
"nvngx.ini detected, please move over to using OptiScaler.ini and delete the old config",
so it is purged on every sync / deployment.
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Union

# OptiScaler v0.9.4-final configuration contract
OPTISCALER_INI_NAME = "OptiScaler.ini"
LEGACY_OPTISCALER_INI_NAME = "nvngx.ini"
OPTISCALER_MENU_SCALE_MIN = 0.5
OPTISCALER_MENU_SCALE_MAX = 2.0
DEFAULT_OPTISCALER_MENU_SCALE = 2.0  # 4K / 3840x2160 default recommendation
OPTISCALER_MENU_SCALE_CHOICES: Tuple[float, ...] = (1.0, 1.5, 2.0)

# Keys that DM-Toolbox wrote for older builds / wrong sections. v0.9.4 does not know them,
# so they are stripped to keep OptiScaler.ini 100% aligned with the official template.
LEGACY_OPTISCALER_KEYS: Tuple[Tuple[str, str], ...] = (
    ("FrameGen", "FGType"),                     # 0.8.x only; v0.9.4 uses FGOutput
    ("FrameGen", "FrameGenerationMultiplier"),   # lives in [XeFG] InterpolationCount
    ("FrameGen", "InterpolationCount"),          # lives in [XeFG]
    ("Hotfix", "UseDelayedInit"),                # real key belongs to [Dx11withDx12], not [Hotfix]
    ("Sharpness", "Enabled"),                    # [Sharpness] only has OverrideSharpness/Sharpness
    ("CAS", "Sharpness"),                        # sharpening value lives in [Sharpness]
    ("LoadDlls", "LoadReshade"),                 # v0.9.4 uses [Plugins] LoadReshade
    ("LoadDlls", "ReshadePath"),                 # v0.9.4 uses [Plugins]
)

LEGACY_OPTISCALER_SECTIONS: Tuple[str, ...] = (
    "LoadDlls",
)


DLSS_PRESET_MAP: Dict[str, int] = {
    "Default": 0,
    "0": 0,
    "M": 13,
    "Preset M": 13,
    "13": 13,
    "L": 12,
    "Preset L": 12,
    "12": 12,
    "K": 11,
    "Preset K": 11,
    "11": 11,
    "J": 10,
    "Preset J": 10,
    "10": 10,
    "F": 6,
    "Preset F": 6,
    "6": 6,
    "E": 5,
    "Preset E": 5,
    "5": 5,
    "D": 4,
    "Preset D": 4,
    "4": 4,
    "C": 3,
    "Preset C": 3,
    "3": 3,
    "B": 2,
    "Preset B": 2,
    "2": 2,
    "A": 1,
    "Preset A": 1,
    "1": 1,
}

VK_KEY_MAP: Dict[str, int] = {
    "Backspace": 8,   # 0x08 VK_BACK
    "F11": 122,       # 0x7A VK_F11
    "Insert": 45,     # 0x2D VK_INSERT
    "Home": 36,       # 0x24 VK_HOME
    "End": 35,        # 0x23 VK_END
    "Delete": 46,     # 0x2E VK_DELETE
}


class IniConfigManager:
    """
    Unified INI Configuration Manager preserving all existing comments, blank lines,
    section order, and unmanaged keys while updating or injecting required key-values.
    """

    #: Structured outcome of the most recent Mode C forward sync (used by UI/patcher/tests).
    last_report: Dict[str, Any] = {}

    @staticmethod
    def read_ini_sections(file_path: Union[str, Path]) -> Dict[str, Dict[str, str]]:
        """
        Parse an INI file into a dictionary of {section: {key: value}},
        ignoring comments and preserving key/section casing.
        """
        path = Path(file_path)
        if not path.exists():
            return {}

        result: Dict[str, Dict[str, str]] = {}
        current_sec = ""

        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped or stripped.startswith(";") or stripped.startswith("#"):
                        continue
                    if stripped.startswith("[") and "]" in stripped:
                        current_sec = stripped[1:stripped.index("]")].strip()
                        if current_sec not in result:
                            result[current_sec] = {}
                        continue
                    if "=" in stripped:
                        k, v = stripped.split("=", 1)
                        if current_sec not in result:
                            result[current_sec] = {}
                        result[current_sec][k.strip()] = v.strip()
        except Exception:
            pass

        return result

    @staticmethod
    def write_ini_sections(file_path: Union[str, Path], updates: Dict[str, Dict[str, Any]]) -> bool:
        """
        Safely update or inject sections and key-values into an INI file.
        Preserves all comments, line formatting, and unmanaged fields.
        """
        path = Path(file_path)
        lines: List[str] = []
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
            except Exception:
                lines = []

        # Normalized lookup: { SECTION_UPPER: (OrigSectionName, { KEY_UPPER: (OrigKeyName, str_val) }) }
        updates_normalized = {
            sec.strip().upper(): (
                sec.strip(),
                {k.strip().upper(): (k.strip(), str(v)) for k, v in kv.items()}
            )
            for sec, kv in updates.items()
        }

        out_lines: List[str] = []
        current_sec_upper: Optional[str] = ""
        written_keys: Dict[str, set] = {sec_u: set() for sec_u in updates_normalized}

        def flush_missing_keys(sec_upper: str):
            if sec_upper in updates_normalized:
                orig_sec, kv_map = updates_normalized[sec_upper]
                for k_upper, (orig_k, val) in kv_map.items():
                    if k_upper not in written_keys[sec_upper]:
                        out_lines.append(f"{orig_k}={val}\n")
                        written_keys[sec_upper].add(k_upper)

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[") and "]" in stripped:
                if current_sec_upper is not None:
                    flush_missing_keys(current_sec_upper)
                sec_name = stripped[1:stripped.index("]")].strip()
                current_sec_upper = sec_name.upper()
                out_lines.append(line)
                continue

            if current_sec_upper is not None and current_sec_upper in updates_normalized:
                if "=" in stripped and not stripped.startswith(";") and not stripped.startswith("#"):
                    k, v = stripped.split("=", 1)
                    k_clean = k.strip().upper()
                    orig_sec, kv_map = updates_normalized[current_sec_upper]
                    if k_clean in kv_map:
                        orig_k, new_val = kv_map[k_clean]
                        indent = line[:len(line) - len(line.lstrip())]
                        out_lines.append(f"{indent}{orig_k}={new_val}\n")
                        written_keys[current_sec_upper].add(k_clean)
                        continue

            out_lines.append(line)

        # Flush keys for the trailing section
        if current_sec_upper is not None:
            flush_missing_keys(current_sec_upper)

        # Append completely new sections that were never encountered in the file
        for sec_upper, (orig_sec, kv_map) in updates_normalized.items():
            if not any(k in written_keys[sec_upper] for k in kv_map):
                if out_lines and not out_lines[-1].endswith("\n\n"):
                    out_lines.append("\n")
                if orig_sec:
                    out_lines.append(f"[{orig_sec}]\n")
                for k_upper, (orig_k, val) in kv_map.items():
                    out_lines.append(f"{orig_k}={val}\n")
                    written_keys[sec_upper].add(k_upper)

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(out_lines)
            return True
        except Exception:
            return False

    @staticmethod
    def remove_ini_keys(file_path: Union[str, Path], keys: List[Tuple[str, str]]) -> int:
        """
        Remove obsolete `Section/Key` lines from an INI while preserving every comment,
        blank line and unmanaged key. Returns the number of removed lines.
        """
        path = Path(file_path)
        if not path.exists() or not keys:
            return 0

        wanted: Dict[str, set] = {}
        for sec, key in keys:
            wanted.setdefault(sec.strip().upper(), set()).add(key.strip().upper())

        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception:
            return 0

        out_lines: List[str] = []
        current_sec = ""
        removed = 0
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[") and "]" in stripped:
                current_sec = stripped[1:stripped.index("]")].strip().upper()
                out_lines.append(line)
                continue
            if current_sec in wanted and "=" in stripped and not stripped.startswith(";"):
                key = stripped.split("=", 1)[0].strip().upper()
                if key in wanted[current_sec]:
                    removed += 1
                    continue
            out_lines.append(line)

        if removed:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.writelines(out_lines)
            except Exception:
                return 0
        return removed

    @staticmethod
    def remove_ini_sections(file_path: Union[str, Path], sections: List[str]) -> int:
        """
        Removes entire sections (including header and content) from an INI.
        """
        path = Path(file_path)
        if not path.exists() or not sections:
            return 0
        target_secs = {s.strip().upper() for s in sections}
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception:
            return 0
        out_lines: List[str] = []
        in_target_sec = False
        removed = 0
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[") and "]" in stripped:
                sec_name = stripped[1:stripped.index("]")].strip().upper()
                in_target_sec = (sec_name in target_secs)
                if in_target_sec:
                    removed += 1
                    continue
            if in_target_sec:
                removed += 1
                continue
            out_lines.append(line)
        if removed:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.writelines(out_lines)
            except Exception:
                return 0
        return removed

    # ---------------- Mode C (OptiScaler / XeSS 2.0 / FSR 3.1) Sync ----------------
    @staticmethod
    def normalize_menu_scale(value: Any) -> str:
        """Clamp the in-game ImGui menu scale to OptiScaler's legal 0.5 - 2.0 range."""
        try:
            scale = float(value)
        except (TypeError, ValueError):
            scale = DEFAULT_OPTISCALER_MENU_SCALE
        if scale != scale:  # NaN guard
            scale = DEFAULT_OPTISCALER_MENU_SCALE
        scale = max(OPTISCALER_MENU_SCALE_MIN, min(OPTISCALER_MENU_SCALE_MAX, scale))
        return f"{scale:.1f}"

    @classmethod
    def ensure_xemfg_plugin(cls, target_dir: Union[str, Path]) -> bool:
        """
        Ensure OptiScaler 10 backend and OptiScaler\\plugins\\MFGUnlocker.asi are present in target game
        directory so XeSS 2.0 multi-frame generation (XeMFG 2X/3X/4X) functions seamlessly.
        """
        try:
            target = Path(target_dir)
            if not target.exists():
                return False

            from core.updater import ComponentUpdater
            from core.models import BackendType
            updater = ComponentUpdater()

            # 1. Deploy OptiScaler 10 backend folder if missing or incomplete
            opti_cached = updater.get_latest_cached_file(BackendType.OPTISCALER_FSR)
            if opti_cached:
                cached_opti_dir = Path(opti_cached).parent
                cached_sub = cached_opti_dir / "OptiScaler"
                target_sub = target / "OptiScaler"
                if cached_sub.exists() and not target_sub.exists():
                    shutil.copytree(cached_sub, target_sub)

                # Upgrade existing proxy dll if old
                for p_name in ["dxgi.dll", "version.dll", "winmm.dll"]:
                    p_file = target / p_name
                    if p_file.exists():
                        try:
                            if p_file.stat().st_size != Path(opti_cached).stat().st_size:
                                shutil.copy2(opti_cached, p_file)
                        except Exception:
                            pass

            # 2. Deploy dashdogy MFGUnlocker.asi
            plugins_dir = target / "OptiScaler" / "plugins"
            asi_path = plugins_dir / "MFGUnlocker.asi"
            mfg_dll = updater.get_latest_cached_file(BackendType.STANDALONE)
            if not mfg_dll or not os.path.exists(mfg_dll):
                emb_mfg = Path(__file__).resolve().parent.parent / "embedded_components" / "dashdogy" / "v1.6.1" / "MFGUnlocker.dll"
                if emb_mfg.exists():
                    mfg_dll = str(emb_mfg)
            if mfg_dll and os.path.exists(mfg_dll):
                plugins_dir.mkdir(parents=True, exist_ok=True)
                if not asi_path.exists() or asi_path.stat().st_size != Path(mfg_dll).stat().st_size:
                    shutil.copy2(mfg_dll, asi_path)
            return True
        except Exception:
            return False

    @classmethod
    def detect_xefg_max_interpolations(cls, target_dir: Union[str, Path]) -> Optional[int]:
        """
        Scan OptiScaler.log for libxess_fg's reported Max supported interpolations.
        Reads both the beginning (initialization) and end of the log to support large log files.
        """
        log_path = Path(target_dir) / "OptiScaler.log"
        if not log_path.exists():
            return 5
        try:
            size = log_path.stat().st_size
            with open(log_path, "rb") as f:
                head = f.read(min(size, 2 * 1024 * 1024)).decode("utf-8", errors="ignore")
                tail = ""
                if size > 2 * 1024 * 1024:
                    f.seek(max(0, size - 2 * 1024 * 1024))
                    tail = f.read().decode("utf-8", errors="ignore")
            matches = re.findall(r"Max supported interpolations:\s*(\d+)", head + "\n" + tail)
            if matches:
                return max(1, min(5, int(matches[-1])))
        except Exception:
            pass
        return 5

    @classmethod
    def resolve_interpolation_count(cls, target_dir: Union[str, Path], fg_output: str, requested: Any) -> Tuple[int, Optional[int], bool]:
        """
        Return (effective, max_supported, clamped).
        - FSR 3.1 FG / Nukem9 bridge only supports 2X (1 interpolated frame).
        - XeFG is capped by libxess_fg's Max supported interpolations (default 5 for 6X).
        """
        try:
            requested = int(requested)
        except (TypeError, ValueError):
            requested = 2
        requested = max(1, min(5, requested))

        if str(fg_output).strip().lower() != "xefg":
            return 1, None, requested != 1

        target = Path(target_dir)
        cls.ensure_xemfg_plugin(target)

        xefg_max = cls.detect_xefg_max_interpolations(target) or 5
        effective = min(requested, xefg_max)
        return effective, xefg_max, effective != requested

    @classmethod
    def purge_legacy_nvngx_ini(cls, target_dir: Union[str, Path]) -> bool:
        """
        Delete the legacy `nvngx.ini` alias. OptiScaler v0.9.4 detects it and keeps showing
        "nvngx.ini detected, please move over to using OptiScaler.ini and delete the old config".
        """
        legacy = Path(target_dir) / LEGACY_OPTISCALER_INI_NAME
        if not legacy.exists():
            return False
        try:
            legacy.unlink()
            return True
        except PermissionError:
            try:
                os.chmod(legacy, 0o666)
                legacy.unlink()
                return True
            except Exception:
                return False
        except Exception:
            return False

    @classmethod
    def sync_mode_c_forward(cls, target_dir: Union[str, Path], preset: Dict[str, Any], exe_name: Optional[str] = None) -> bool:
        """
        Forward sync the Mode C preset into the ONE legal config file: `OptiScaler.ini`.

        OptiScaler v0.9.4-final contract (verified against the official bundled template and
        a real yysls 4K in-game session):
        - [FrameGen] Enabled / FGInput / FGOutput are consumed at D3D12 init, so they must be
          correct BEFORE launch. FGType / FrameGenerationMultiplier do not exist in v0.9.4.
        - [XeFG] InterpolationCount is the MFG multiplier (1=2X, 2=3X, 3=4X). libxess_fg
          clamps it to "Max supported interpolations"; asking for more leaves the menu stuck
          on "Restart the game to apply correct XeFG settings!".
        - [Menu] Scale is 0.5 - 2.0 (default 1.0 = unreadable on 4K). We write 2.0 by default
          and let the user pick 1.0 / 1.5 / 2.0 from the Mode C panel.
        - [Sharpness] OverrideSharpness + Sharpness carry the RCAS value. [CAS] Sharpness and
          [Sharpness] Enabled are not v0.9.4 keys and are stripped from legacy files.
        - `nvngx.ini` is never written and is deleted, silencing the red warning banner.

        Crash-prevention guards kept:
        - TargetProcessName isolates the game from launchers / crash handlers
        - SkipFirstFrames = 5 avoids Splash/SwapChain crashes in the Messiah engine
        - EarlyHooking = false avoids premature D3D12 root signature corruption
        - Dxgi = false on RTX 40/50 avoids driver-level hijacking conflicts
        """
        target = Path(target_dir)
        if not target.exists():
            return False

        fg_output = str(preset.get("fg_output", "xefg")).strip().lower()
        fg_input = str(preset.get("fg_input", "dlssg")).strip().lower()
        requested_interpolation = preset.get("interpolation_count", 2)
        try:
            requested_interpolation = int(requested_interpolation)
        except (TypeError, ValueError):
            requested_interpolation = 1

        # dashdogy Universal MFG Unlocker (OptiScaler/plugins/MFGUnlocker.asi)
        # patches libxess_fg's interpolation ceiling before OptiScaler queries it,
        # so the "Max supported interpolations = 1" clamp no longer applies and
        # 3X/4X XeFG becomes reachable on non-Arc GPUs. Only skip the clamp when
        # the unlocker is actually deployed.
        unlock_mfg = bool(preset.get("unlock_mfg", True))
        unlocker_present = (
            (target / "OptiScaler" / "plugins" / "MFGUnlocker.asi").exists()
            or (target / "OptiScaler" / "plugins" / "MFGUnlocker-loadlate.asi").exists()
        )
        if fg_output == "xefg" and unlock_mfg and unlocker_present:
            effective_interpolation = max(1, min(3, requested_interpolation))  # XeFG ceiling is 4X
            xefg_max = 3
            interpolation_clamped = effective_interpolation != requested_interpolation
        else:
            effective_interpolation, xefg_max, interpolation_clamped = cls.resolve_interpolation_count(
                target, fg_output, requested_interpolation
            )
        menu_scale = cls.normalize_menu_scale(preset.get("menu_scale", DEFAULT_OPTISCALER_MENU_SCALE))
        dx12_upscaler = preset.get("dx12_upscaler", "auto")
        rcas_enabled = bool(preset.get("rcas_enabled", False))
        rcas_sharpness = float(preset.get("rcas_sharpness", 0.0))
        sharp_str = f"{rcas_sharpness:.1f}" if not rcas_enabled else f"{rcas_sharpness:.2f}"

        dlss_p = str(preset.get("dlss_preset", "Default")).strip()
        is_dlss_default = dlss_p.lower() in ["default", "0", "none", ""]

        if is_dlss_default:
            dlss_sec = {
                "RenderPresetOverride": "false",
                "UseGenericAppIdWithDlss": "false",
                "RenderPresetForAll": "0",
                "RenderPresetDLAA": "0",
                "RenderPresetUltraQuality": "0",
                "RenderPresetQuality": "0",
                "RenderPresetBalanced": "0",
                "RenderPresetPerformance": "0",
                "RenderPresetUltraPerformance": "0"
            }
        else:
            enum_val = str(DLSS_PRESET_MAP.get(dlss_p, 13))
            dlss_sec = {
                "RenderPresetOverride": "true",
                "UseGenericAppIdWithDlss": "false",
                "RenderPresetForAll": enum_val,
                "RenderPresetDLAA": enum_val,
                "RenderPresetUltraQuality": enum_val,
                "RenderPresetQuality": enum_val,
                "RenderPresetBalanced": enum_val,
                "RenderPresetPerformance": enum_val,
                "RenderPresetUltraPerformance": enum_val
            }

        multiplier_num = effective_interpolation + 1  # 1->2X, 2->3X, 3->4X

        # Check GPU vendor
        try:
            from core.utils import get_system_gpu_name, is_rtx_40_or_newer
            gpu_name = get_system_gpu_name()
            is_rtx40_50 = is_rtx_40_or_newer(gpu_name)
        except Exception:
            gpu_name = ""
            is_rtx40_50 = True
        is_nvidia = "nvidia" in gpu_name.lower() or "geforce" in gpu_name.lower() or "rtx" in gpu_name.lower() or "gtx" in gpu_name.lower()

        menu_key = str(preset.get("menu_key", "Insert")).strip()
        if menu_key in VK_KEY_MAP:
            vk_code = VK_KEY_MAP[menu_key]
        elif menu_key.isdigit():
            vk_code = int(menu_key)
        else:
            vk_code = 45

        # 1. Update the ONE legal config file: OptiScaler.ini
        opti_ini = target / OPTISCALER_INI_NAME
        has_dlss5 = is_dlss5_present(target)

        frame_gen_sec = {
            "Enabled": "true",
            "FGInput": fg_input,
            "FGOutput": fg_output,
        }

        if has_dlss5:
            # DLSS 5 coexistence contract (v1.3.8):
            #
            # DLSS 5 owns super resolution / neural reconstruction. OptiScaler must
            # therefore stay a *pure frame-generation* layer, but it must NOT block
            # the game's DLSS calls - the RenoDX DLSS 5 addon replaces the DLSS
            # runtime from inside that very call chain. Writing [DLSS] Enabled=false
            # (the previous "fix") made OptiScaler swallow NVSDK_NGX_D3D12_CreateFeature,
            # so the addon never saw the game's DLSS call and the engine dereferenced
            # the failed feature handle -> 0xC0000005 on scene load when both patches
            # were injected.
            #
            # Dx12Upscaler=dlss keeps that chain: OptiScaler hooks NGX, forwards to
            # the original nvngx (where the DLSS 5 addon sits) and only takes over
            # the DLSS-G -> XeFG frame generation path. "none" is not a legal value
            # in the bundled OptiScaler template and made the parser fall back to
            # auto-detection (FSR/XeSS), which is what removed the in-game DLSS menu.
            dlss_sec = {
                "Enabled": "true",
                "RenderPresetOverride": "false",
                "UseGenericAppIdWithDlss": "false",
                "RenderPresetForAll": "0",
                "RenderPresetDLAA": "0",
                "RenderPresetUltraQuality": "0",
                "RenderPresetQuality": "0",
                "RenderPresetBalanced": "0",
                "RenderPresetPerformance": "0",
                "RenderPresetUltraPerformance": "0"
            }
            dlssd_sec = {
                "RenderPresetOverride": "false",
                "RenderPresetForAll": "0",
            }
            upscalers_sec = {
                "Dx12Upscaler": "dlss"
            }
            hooks_sec = {
                # Explicitly reset the key: older DM-Toolbox builds wrote true here
                # for coexistence, which made OptiScaler skip the game-local NGX
                # modules (where the DLSS 5 addon lives) and broke the DLSS chain.
                "HookOriginalNvngxOnly": "false",
                "EarlyHooking": "false",
                "UseNtdllHooks": "false"
            }
            plugins_sec = {
                # MFGUnlocker.asi (dashdogy Universal MFG Unlocker) is what lifts the
                # XeFG 2X ceiling; it must be loadable for 3X/4X. Users who hit a
                # startup hook conflict with the DLSS 5 addon can turn it off in the
                # Mode C panel (unlock_mfg=False) and fall back to plain 2X XeFG.
                "LoadAsiPlugins": "true" if unlock_mfg else "false",
                "LoadReshade": "false"
            }
            # XeFG own swapchain must survive the ReShade/DLSS 5 present path.
            # NOTE: the key lives in [FrameGen] in OptiScaler 0.9.x - writing it
            # into [XeFG] (as earlier builds did) is silently ignored by the parser.
            frame_gen_sec.update({
                "PreserveSwapChain": "true",
                "SkipResizeBuffers": "true",
                "AllowedFrameAhead": "1",
            })
            xefg_sec = {
                # yysls and most Streamline titles hand DLSS dilated (low-res) motion
                # vectors. libxess_fg's pre-ini checks then abort with
                # "Requires disabling dilated motion vectors" and the in-game toggle
                # stays greyed out, so the bypass must stay on for XeFG to run at all.
                "IgnoreInitChecks": "true",
                "InterpolationCount": str(effective_interpolation),
                "OverrideInterpolationCount": str(effective_interpolation),
                "DepthInverted": "true",
            }
            fsrfg_sec = {
                "UseMutexForSwapchain": "true"
            }
        else:
            dlss_sec["Enabled"] = "true"
            dlssd_sec = {
                "RenderPresetOverride": "false" if is_dlss_default else "true",
                "RenderPresetForAll": "0" if is_dlss_default else str(DLSS_PRESET_MAP.get(dlss_p, 13)),
            }
            upscalers_sec = {
                "Dx12Upscaler": dx12_upscaler if dx12_upscaler in ("auto", "dlss", "xess", "fsr31") else "auto"
            }
            hooks_sec = {
                "EarlyHooking": "false",
                "UseNtdllHooks": "false"
            }
            plugins_sec = {
                "LoadAsiPlugins": "true",
                "LoadReshade": "auto"
            }
            xefg_sec = {
                # Same bypass without DLSS 5: games that feed dilated MVs would
                # otherwise keep XeFG at OFF no matter what the UI says.
                "IgnoreInitChecks": "true",
                "InterpolationCount": str(effective_interpolation),
                "OverrideInterpolationCount": str(effective_interpolation),
                "DepthInverted": "true",
            }
            fsrfg_sec = {}

        libraries_sec: Dict[str, str] = {
            "OptiDllPath": "auto",
            "NvngxPath": "auto",
        }
        sl_dlss = target / "Streamline" / "nvngx_dlss.dll"
        local_dlss = target / "nvngx_dlss.dll"
        if sl_dlss.exists():
            libraries_sec["NvngxDlssPath"] = r"Streamline\nvngx_dlss.dll"
            libraries_sec["NvngxFeaturePath"] = "Streamline"
        elif local_dlss.exists():
            libraries_sec["NvngxDlssPath"] = "nvngx_dlss.dll"

        opti_updates: Dict[str, Dict[str, str]] = {
            "FrameGen": frame_gen_sec,
            "XeFG": xefg_sec,
            "DLSSG": {
                "InterpolationCount": str(effective_interpolation),
                "OverrideInterpolationCount": str(effective_interpolation),
            },
            "Plugins": plugins_sec,
            "Upscalers": upscalers_sec,
            "DLSS": dlss_sec,
            "DLSSD": dlssd_sec,
            "Libraries": libraries_sec,
            "Inputs": {
                "EnableDlssInputs": "true"
            },
            "CAS": {
                "Enabled": "true" if rcas_enabled else "false"
            },
            "Sharpness": {
                "OverrideSharpness": "true" if rcas_enabled else "false",
                "Sharpness": sharp_str
            },
            "Hotfix": {
                "SkipFirstFrames": "5",
                "CheckForUpdate": "false",
                "CreateD3D12DeviceForLuma": "false",
                "SimulateWaitableObject": "false"
            },
            "Hooks": hooks_sec,
            "Spoofing": {
                "Dxgi": "false" if is_rtx40_50 else "auto",
                "StreamlineSpoofing": "false" if (is_rtx40_50 or has_dlss5) else "auto",
                "DxgiFactoryWrapping": "false"
            },
            "fakenvapi": {
                "UseFakenvapi": "false" if is_nvidia else "auto"
            },
            "Menu": {
                # OptiScaler refuses to create its D3D12/FG hooks when the overlay
                # menu is disabled ("without this option OptiScaler will disable all
                # FG features" - bundled template, [Menu] OverlayMenu). Keeping it on
                # is what makes XeFG usable next to DLSS 5; the splash banner and the
                # FPS overlay stay off, and the shortcut only opens the panel on demand.
                "OverlayMenu": "true",
                "Scale": menu_scale,
                "ShortcutKey": str(vk_code),
                "DisableSplash": "true" if has_dlss5 else "false",
                "ShowFps": "false",
                "UseHQFont": "true",
                "TTFFontPath": r"C:\Windows\Fonts\msyh.ttc",
                "FontSize": "15.0"
            },
            "Log": {
                "LogToFile": "true",
                "LogLevel": "1"
            }
        }
        if fsrfg_sec:
            opti_updates["FSRFG"] = fsrfg_sec

        if exe_name:
            opti_updates["ProcessFilter"] = {
                "TargetProcessName": os.path.basename(exe_name)
            }

        ok_opti = cls.write_ini_sections(opti_ini, opti_updates)

        # In coexistence mode, automatically synchronize DLSS 5 hook point to Upscaled mode (0)
        # to prevent DLSS 5 Present hook from colliding with XeFG synthetic swapchain.
        if has_dlss5:
            cls.sync_dlss5_hook_point(target, hook_point="0")

        # Also sync mfg_unlocker.ini in target and OptiScaler/plugins for MFGUnlocker.asi
        mfg_updates = {
            "General": {
                "Multiplier": str(multiplier_num),
                "Preset": dlss_p if not is_dlss_default else "Default",
                "DLSSPreset": dlss_p if not is_dlss_default else "Default",
                "RenderPreset": str(DLSS_PRESET_MAP.get(dlss_p, 13)) if not is_dlss_default else "0"
            }
        }
        cls.write_ini_sections(target / "mfg_unlocker.ini", mfg_updates)
        plugins_dir = target / "OptiScaler" / "plugins"
        if plugins_dir.exists():
            cls.write_ini_sections(plugins_dir / "mfg_unlocker.ini", mfg_updates)

        # 2. Strip keys that do not exist in v0.9.4 (written by older DM-Toolbox builds).
        cls.remove_ini_keys(opti_ini, LEGACY_OPTISCALER_KEYS)
        if has_dlss5:
            # PreserveSwapChain belongs to [FrameGen]; older coexistence builds
            # injected it into [XeFG] where OptiScaler never reads it.
            cls.remove_ini_keys(opti_ini, [("XeFG", "PreserveSwapChain")])
        cls.remove_ini_sections(opti_ini, list(LEGACY_OPTISCALER_SECTIONS))

        # 3. Never keep a second config: OptiScaler keeps showing the red
        #    "nvngx.ini detected" banner while the legacy alias exists.
        nvngx_purged = cls.purge_legacy_nvngx_ini(target)

        warnings: List[str] = []
        if interpolation_clamped:
            if fg_output == "xefg":
                warnings.append(
                    f"本机 libxess_fg 最高支持 {((xefg_max or 1) + 1)}X 插帧，已将 {requested_interpolation + 1}X "
                    f"自动下调为 {effective_interpolation + 1}X，避免游戏内出现 "
                    f"Restart the game to apply correct XeFG settings! 黄字警告。"
                )
                if (xefg_max or 1) <= 1:
                    warnings.append(
                        "当前显卡的 Intel XeFG 只支持 2X（libxess_fg 报告 Max supported interpolations = 1，"
                        "常见于非 Arc 显卡）。如需 3X/4X 原生多倍插帧，请改用"
                        "【模式 A: dashdogy MFG-Unlocker】，XeFG 通道无法突破该硬件上限。"
                    )
            else:
                warnings.append(
                    f"{fg_output.upper()} 通道固定为 2X 双倍插帧，已将 {requested_interpolation + 1}X 自动锁定为 2X。"
                )
        if nvngx_purged:
            warnings.append("已删除遗留的 nvngx.ini，仅保留唯一的 OptiScaler.ini。")


        cls.last_report = {
            "ini_path": str(opti_ini),
            "fg_output": fg_output,
            "fg_input": fg_input,
            "multiplier": multiplier_num,
            "requested_interpolation_count": requested_interpolation,
            "interpolation_count": effective_interpolation,
            "xefg_max_interpolations": xefg_max,
            "interpolation_clamped": interpolation_clamped,
            "menu_scale": menu_scale,
            "menu_shortcut": vk_code,
            "nvngx_ini_removed": nvngx_purged,
            "nvngx_ini_present": (target / LEGACY_OPTISCALER_INI_NAME).exists(),
            "warnings": warnings,
        }

        return ok_opti

    @classmethod
    def read_mode_c_reverse(cls, target_dir: Union[str, Path]) -> Optional[Dict[str, Any]]:
        """
        Reverse sync from the ONE legal `OptiScaler.ini`.

        A legacy `nvngx.ini` is only read as a one-time migration fallback when no
        `OptiScaler.ini` exists yet; as soon as the real file is present the alias is deleted.
        """
        target = Path(target_dir)
        opti_ini = target / OPTISCALER_INI_NAME
        legacy_ini = target / LEGACY_OPTISCALER_INI_NAME

        if opti_ini.exists():
            data = cls.read_ini_sections(opti_ini)
            # Bidirectional sync cleanup: kill the red "nvngx.ini detected" banner.
            cls.purge_legacy_nvngx_ini(target)
        elif legacy_ini.exists():
            data = cls.read_ini_sections(legacy_ini)
        else:
            return None

        if not data:
            return None

        preset: Dict[str, Any] = {}

        # Parse FrameGen section (v0.9.4 uses FGOutput; FGType is 0.8.x legacy)
        fg_sec = data.get("FrameGen", {})
        if "FGOutput" in fg_sec:
            preset["fg_output"] = fg_sec["FGOutput"].strip().lower()
        elif "FGType" in fg_sec:
            preset["fg_output"] = fg_sec["FGType"].strip().lower()

        if "FGInput" in fg_sec:
            preset["fg_input"] = fg_sec["FGInput"].strip().lower()

        # Parse Multiplier / InterpolationCount (1=2X, 2=3X, 3=4X)
        xefg_sec = data.get("XeFG", {})
        if "InterpolationCount" in xefg_sec:
            try:
                preset["interpolation_count"] = max(1, min(5, int(xefg_sec["InterpolationCount"])))
            except Exception:
                pass
        elif "FrameGenerationMultiplier" in fg_sec:
            try:
                mult = int(fg_sec["FrameGenerationMultiplier"])
                preset["interpolation_count"] = max(1, min(3, mult - 1))
            except Exception:
                pass

        # Parse Upscaler
        up_sec = data.get("Upscalers", {})
        if "Dx12Upscaler" in up_sec:
            preset["dx12_upscaler"] = up_sec["Dx12Upscaler"].strip().lower()

        # Parse CAS & Sharpness
        cas_sec = data.get("CAS", {})
        sharp_sec = data.get("Sharpness", {})
        if "Enabled" in cas_sec:
            preset["rcas_enabled"] = (cas_sec["Enabled"].lower() == "true")
        elif "OverrideSharpness" in sharp_sec:
            preset["rcas_enabled"] = (sharp_sec["OverrideSharpness"].lower() == "true")

        if "Sharpness" in sharp_sec:
            try:
                preset["rcas_sharpness"] = float(sharp_sec["Sharpness"])
            except Exception:
                pass

        # Parse DLSS preset
        dlss_sec = data.get("DLSS", {})
        if dlss_sec.get("RenderPresetOverride", "").lower() == "true":
            raw_p = dlss_sec.get("RenderPresetForAll", "0")
            inv_dlss = {13: "M", 12: "L", 11: "K", 10: "J", 6: "F", 5: "E", 4: "D", 3: "C", 2: "B", 1: "A", 0: "Default"}
            try:
                preset["dlss_preset"] = inv_dlss.get(int(raw_p), "Default")
            except Exception:
                preset["dlss_preset"] = "Default"
        else:
            preset["dlss_preset"] = "Default"

        # Parse Menu shortcut key + menu scale
        menu_sec = data.get("Menu", {})
        if "ShortcutKey" in menu_sec:
            raw_key = menu_sec["ShortcutKey"]
            inv_keys = {8: "Backspace", 122: "F11", 45: "Insert", 36: "Home", 35: "End", 46: "Delete"}
            try:
                vk_int = int(raw_key, 0)
                if vk_int in inv_keys:
                    preset["menu_key"] = inv_keys[vk_int]
            except Exception:
                pass

        if "Scale" in menu_sec:
            try:
                preset["menu_scale"] = max(
                    OPTISCALER_MENU_SCALE_MIN,
                    min(OPTISCALER_MENU_SCALE_MAX, float(menu_sec["Scale"]))
                )
            except Exception:
                pass

        return preset if preset else None

    @classmethod
    def sync_dlss5_hook_point(cls, target_dir: Union[str, Path], hook_point: str = "0") -> bool:
        """
        Synchronizes DLSS 5 hook point between Present (2) and Upscaled (0) mode.
        When coexisting with Mode C (XeSS FG / OptiScaler), setting hook_point="0" prevents
        DLSS 5 from intercepting XeFG's synthetic swapchain presentation, resolving 0xc0000005 crashes.
        """
        target = Path(target_dir)
        if not target.exists() or not target.is_dir():
            return False

        always_pres = "0" if str(hook_point) == "0" else "1"
        str_hook = str(hook_point)

        hook_updates = {
            "NRHookPoint": str_hook,
            "HookStage": str_hook,
            "DirectNeuralRenderingHookStage": str_hook,
            "DirectNeuralRenderingAlwaysPresent": always_pres,
            "DirectNeuralRenderingPresentMode": always_pres,
            "NRPresentAlways": always_pres,
            "AlwaysPresent": always_pres,
            "NRFollowInputRes": "1",
            "NRResolutionScale": "0.500000",
            "ResolutionScale": "0.500000",
            "NeuralUplift": "1",
            "NRVramBuffering": "1",
            "VramBuffering": "1",
            "DirectNeuralRenderingVramBuffering": "1",
            "NRVramBudgetGuard": "0",
            "NRVramBudgetMargin": "0",
            "VramBudgetGuard": "0",
            "BudgetGuard": "0",
        }

        # 1. Update ReShade.ini
        reshade_ini = target / "ReShade.ini"
        if reshade_ini.exists():
            sections_to_update = {
                "RenoDX.DLSS5": hook_updates,
                "RenoDX DLSS5 preset": hook_updates,
                "RenoDX": hook_updates,
                "DLSSNR": hook_updates,
                "RenoDX-My look": hook_updates,
                "DLSS5": hook_updates,
                "DLSS5-NR": hook_updates
            }
            # Cleanse LoadFromDllMain in [ADDON]: DLSS addons must NEVER load from DllMain (violates Windows loader lock)
            existing_sections = cls.read_ini_sections(reshade_ini)
            addon_sec = existing_sections.get("ADDON", {})
            current_main = addon_sec.get("LoadFromDllMain", "")
            clean_addons = []
            for item in current_main.split(","):
                cand = item.strip()
                if not cand or cand == "1" or "dlss" in cand.lower() or "shortfuse" in cand.lower():
                    continue
                if (target / cand).exists() and cand.lower() not in [x.lower() for x in clean_addons]:
                    clean_addons.append(cand)
            sections_to_update["ADDON"] = {"LoadFromDllMain": ",".join(clean_addons)}

            cls.write_ini_sections(reshade_ini, sections_to_update)

        # 2. Update ReShadePreset.ini
        reshade_preset = target / "ReShadePreset.ini"
        if reshade_preset.exists():
            cls._update_preset_file_kv(reshade_preset, hook_updates)

        # 3. Update target directory RenoDX/DLSS5/Presets/*.ini
        preset_dir = target / "RenoDX" / "DLSS5" / "Presets"
        if preset_dir.exists() and preset_dir.is_dir():
            for p_file in preset_dir.glob("*.ini"):
                cls._update_preset_file_kv(p_file, hook_updates)

        # 4. Also synchronize AppData RenoDX presets if present
        appdata_reno_presets = Path(os.environ.get("LOCALAPPDATA", "")) / "RenoDX" / "DLSS5" / "Presets"
        if appdata_reno_presets.exists() and appdata_reno_presets.is_dir():
            for p_file in appdata_reno_presets.glob("*.ini"):
                cls._update_preset_file_kv(p_file, hook_updates)

        return True

    @staticmethod
    def _update_preset_file_kv(file_path: Path, kv: Dict[str, str]):
        if not file_path.exists():
            return
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines()
            found_keys = set()
            new_lines = []
            for line in lines:
                stripped = line.strip()
                if "=" in stripped and not stripped.startswith(";") and not stripped.startswith("#"):
                    k, _ = stripped.split("=", 1)
                    k_clean = k.strip()
                    k_lower = k_clean.lower()
                    matched = False
                    for target_k, target_v in kv.items():
                        if k_lower == target_k.lower():
                            new_lines.append(f"{target_k}={target_v}")
                            found_keys.add(target_k.lower())
                            matched = True
                            break
                    if matched:
                        continue
                new_lines.append(line)
            for target_k, target_v in kv.items():
                if target_k.lower() not in found_keys:
                    new_lines.append(f"{target_k}={target_v}")
            file_path.write_text("\n".join(new_lines).strip() + "\n", encoding="utf-8")
        except Exception:
            pass

    # ---------------- Mode B (RenoDX ReShade Addon) Sync ----------------
    @classmethod
    def sync_mode_b_forward(cls, target_dir: Union[str, Path], config: Dict[str, Any]) -> bool:
        """
        Forward sync Mode B parameters into TargetExeDir/ReShade.ini.
        Ensures early loading [ADDON] LoadFromDllMain and exact section/key names matching
        renodx-mfgunlock.addon64 binary: [RenoDX.MFGUnlock] (with [MFG Unlock] and [MFGAdaUnlock] mirrors).
        """
        target = Path(target_dir)
        if not target.exists():
            return False

        reshade_ini = target / "ReShade.ini"

        force_mult = int(config.get("force_multiplier", 3))
        blackwell = int(config.get("blackwell_kernels", 1))
        isr = int(config.get("thin_geometry_isr", 1))
        vwb = int(config.get("thin_geometry_vwb", 1))
        bam = int(config.get("thin_geometry_bam", 1))
        hdr_ui = int(config.get("hdr_ui_recomposition", 1))
        dynamic_mfg = int(config.get("dynamic_mfg", 0))
        temporal_fix = int(config.get("temporal_fix", 1))
        hdr_compat = int(config.get("hdr_compatibility", 0))

        # Core keys used by renodx-mfgunlock.addon64
        dlss_b_p = str(config.get("dlss_preset", "K")).strip()
        is_dlss_b_def = dlss_b_p.lower() in ["default", "0", "none", ""]
        clean_dlss_b = "Default" if is_dlss_b_def else (
            "M" if dlss_b_p in ["M", "Preset M", "13"] else
            "L" if dlss_b_p in ["L", "Preset L", "12"] else
            "K" if dlss_b_p in ["K", "Preset K", "11"] else
            "J" if dlss_b_p in ["J", "Preset J", "10"] else
            "F" if dlss_b_p in ["F", "Preset F", "6"] else
            "E" if dlss_b_p in ["E", "Preset E", "5"] else
            "D" if dlss_b_p in ["D", "Preset D", "4"] else
            "C" if dlss_b_p in ["C", "Preset C", "3"] else
            "B" if dlss_b_p in ["B", "Preset B", "2"] else
            "A" if dlss_b_p in ["A", "Preset A", "1"] else dlss_b_p
        )
        dlss_b_enum = str(DLSS_PRESET_MAP.get(clean_dlss_b, 11))

        mfg_keys = {
            "ForceMultiplier": str(force_mult),
            "DLSSPreset": clean_dlss_b,
            "RenderPreset": dlss_b_enum,
            "DeferredInit": "1",
            "BlackwellFrameworkKernels": str(blackwell),
            "ThinGeometryIntermediateScatter": str(isr),
            "ThinGeometryPreviousScatter": str(vwb),
            "ThinGeometryValidatedWarpBlend": str(bam),
            "HDRUIRecomposition": str(hdr_ui),
            "DynamicMFG": str(dynamic_mfg),
            "TemporalFix": str(temporal_fix),
            "HDRCompatibilityMode": str(hdr_compat),
            # Aliases for backward compatibility
            "EnableISR": str(isr),
            "EnableVWB": str(vwb),
            "EnableBAM": str(bam),
            "HdrUiFix": str(hdr_ui),
            "FrameGenMultiplier": str(force_mult),
        }

        # Safe DLSS 5 hook avoidance config (preserves Hook Point Present 2)
        dlss5_hooks = {
            "EnableHooks": "2",
            "RuntimeSelectionMode": "1",
            "HDRCompatibilityMode": "0",
            "NRRuntimePath": r".\nvngx_dlssnr.dll",
            "NRHookPoint": "0",
            "NRStyle": "2",
            "NRPass2Preset": "2",
            "NRSkinStructure": "1.000000",
            "NRPresentNonBlocking": "1",
            "NRVramBuffering": "1"
        }

        addon_name = "renodx-mfgunlock.addon64"
        addon_list = [addon_name]
        addon_updates = {}
        if reshade_ini.exists():
            existing_sections = cls.read_ini_sections(reshade_ini)
            existing_addon = existing_sections.get("ADDON", {})
            if "LoadFromDllMain" in existing_addon:
                raw_addons = [x.strip() for x in existing_addon["LoadFromDllMain"].split(",") if x.strip()]
                clean_addons = [x for x in raw_addons if x != "1" and "dlss" not in x.lower() and "shortfuse" not in x.lower()]
                if addon_name.lower() not in [x.lower() for x in clean_addons]:
                    clean_addons.append(addon_name)
                addon_list = clean_addons
            if "DisabledAddons" in existing_addon:
                disabled_list = [x.strip() for x in existing_addon["DisabledAddons"].split(",") if x.strip()]
                clean_disabled = [x for x in disabled_list if "mfgunlock" not in x.lower() and "dlss" not in x.lower()]
                addon_updates["DisabledAddons"] = ",".join(clean_disabled)
        addon_updates["LoadFromDllMain"] = ",".join(addon_list)

        updates = {
            "GENERAL": {
                "TutorialProgress": "4"
            },
            "OVERLAY": {
                "Language": "zh-CN",
                "Font": r"C:\Windows\Fonts\msyh.ttc",
                "FontSize": "18",
                "EditorFont": r"C:\Windows\Fonts\msyh.ttc",
                "EditorFontSize": "16",
                "KeyOverlay": "36,0,0,0",
                "TutorialProgress": "4"
            },
            "ADDON": addon_updates,
            "RenoDX.MFG": mfg_keys,
            "RenoDX.DLSS5": dlss5_hooks,
            "DLSS5": dlss5_hooks,
            "DLSS5-NR": dlss5_hooks,
            # Exact section recognized by the official binary
            "RenoDX.MFGUnlock": mfg_keys,
            # Mirror sections for compatibility with third-party/legacy forks
            "MFG Unlock": mfg_keys,
            "MFGAdaUnlock": mfg_keys
        }

        return cls.write_ini_sections(reshade_ini, updates)

    @classmethod
    def read_mode_b_reverse(cls, target_dir: Union[str, Path]) -> Optional[Dict[str, Any]]:
        """
        Reverse sync: read parameters from TargetExeDir/ReShade.ini.
        Checks [RenoDX.MFGUnlock], [MFG Unlock], and [MFGAdaUnlock].
        """
        target = Path(target_dir)
        reshade_ini = target / "ReShade.ini"
        if not reshade_ini.exists():
            return None

        data = cls.read_ini_sections(reshade_ini)
        # Check sections in priority order
        mfg_sec = (
            data.get("RenoDX.MFGUnlock")
            or data.get("MFG Unlock")
            or data.get("MFGAdaUnlock")
            or {}
        )
        if not mfg_sec:
            return None

        config: Dict[str, Any] = {}

        # Multiplier
        mult_val = mfg_sec.get("ForceMultiplier") or mfg_sec.get("FrameGenMultiplier")
        if mult_val is not None:
            try:
                config["force_multiplier"] = int(mult_val)
            except Exception:
                pass

        # Blackwell kernels
        if "BlackwellFrameworkKernels" in mfg_sec:
            config["blackwell_kernels"] = int(mfg_sec["BlackwellFrameworkKernels"])

        # Thin geometry ISR
        isr_val = mfg_sec.get("ThinGeometryIntermediateScatter") or mfg_sec.get("EnableISR")
        if isr_val is not None:
            config["thin_geometry_isr"] = int(isr_val)

        # Thin geometry VWB
        vwb_val = mfg_sec.get("ThinGeometryPreviousScatter") or mfg_sec.get("EnableVWB")
        if vwb_val is not None:
            config["thin_geometry_vwb"] = int(vwb_val)

        # Thin geometry BAM
        bam_val = mfg_sec.get("ThinGeometryValidatedWarpBlend") or mfg_sec.get("EnableBAM")
        if bam_val is not None:
            config["thin_geometry_bam"] = int(bam_val)

        # HDR UI Recomposition
        hdr_val = mfg_sec.get("HDRUIRecomposition") or mfg_sec.get("HdrUiFix")
        if hdr_val is not None:
            config["hdr_ui_recomposition"] = int(hdr_val)

        # Dynamic MFG
        if "DynamicMFG" in mfg_sec:
            config["dynamic_mfg"] = int(mfg_sec["DynamicMFG"])

        # Temporal Fix
        if "TemporalFix" in mfg_sec:
            config["temporal_fix"] = int(mfg_sec["TemporalFix"])

        # HDR Compatibility
        if "HDRCompatibilityMode" in mfg_sec:
            config["hdr_compatibility"] = int(mfg_sec["HDRCompatibilityMode"])

        # DLSS Preset
        raw_b_preset = mfg_sec.get("DLSSPreset") or mfg_sec.get("RenderPreset")
        if raw_b_preset is not None:
            p_b_clean = raw_b_preset.strip()
            inv_map = {13: "M", 12: "L", 11: "K", 10: "J", 6: "F", 5: "E", 4: "D", 3: "C", 2: "B", 1: "A", 0: "Default"}
            if p_b_clean.isdigit():
                config["dlss_preset"] = inv_map.get(int(p_b_clean), "K")
            else:
                config["dlss_preset"] = p_b_clean
        else:
            config["dlss_preset"] = "K"

        return config if config else None

    # ---------------- Mode A (dashdogy / Standalone) Sync ----------------
    @classmethod
    def sync_mode_a_forward(cls, target_dir: Union[str, Path], config: Dict[str, Any]) -> bool:
        """
        Forward sync Mode A configuration to TargetExeDir/RTXMFG-UI.ini, mfg_unlocker.ini, and RTX40MFG-UI.ini.
        Enforces proper hotkey mapping (Backspace = 8 / VK_BACK) and DLSS preset mapping.
        """
        target = Path(target_dir)
        if not target.exists():
            return False

        multiplier = int(config.get("multiplier", 3))
        menu_key = str(config.get("menu_key", "Backspace")).strip()
        preset = config.get("dlss_preset", "K")
        dlssg_preset = str(config.get("dlssg_preset", "C")).strip()
        bink_hook = config.get("bink_hook", False)

        preset_str = str(preset).strip()
        is_default = preset_str.lower() in ["default", "0", "none", ""]

        vk_code = VK_KEY_MAP.get(menu_key, 8)

        render_preset_val = "0"
        if not is_default:
            render_preset_val = str(DLSS_PRESET_MAP.get(preset_str, 13))

        clean_preset_name = "Default" if is_default else (
            "M" if preset_str in ["M", "Preset M", "13"] else
            "L" if preset_str in ["L", "Preset L", "12"] else
            "K" if preset_str in ["K", "Preset K", "11"] else
            "J" if preset_str in ["J", "Preset J", "10"] else
            "F" if preset_str in ["F", "Preset F", "6"] else
            "E" if preset_str in ["E", "Preset E", "5"] else
            "D" if preset_str in ["D", "Preset D", "4"] else
            "C" if preset_str in ["C", "Preset C", "3"] else
            "B" if preset_str in ["B", "Preset B", "2"] else
            "A" if preset_str in ["A", "Preset A", "1"] else preset_str
        )

        # DLSS-G Frame Generation Preset mapping for Dashdogy / RTXMFG-Universal.json:
        # 0: Follow Game / Driver (Auto)
        # 1: Preset A
        # 2: Preset B
        # 3: Preset C (Model C / FG Lite)
        raw_dlssg = dlssg_preset.upper()
        if raw_dlssg in ["C", "3", "PRESET C", "MODEL C"]:
            dlssg_preset_val = 3
            clean_dlssg_name = "C"
        elif raw_dlssg in ["B", "2", "PRESET B", "MODEL B"]:
            dlssg_preset_val = 2
            clean_dlssg_name = "B"
        elif raw_dlssg in ["A", "1", "PRESET A", "MODEL A"]:
            dlssg_preset_val = 1
            clean_dlssg_name = "A"
        elif raw_dlssg in ["AUTO", "0", "DEFAULT", "FOLLOW"]:
            dlssg_preset_val = 0
            clean_dlssg_name = "Auto"
        else:
            dlssg_preset_val = 3
            clean_dlssg_name = "C"

        # Write RTXMFG-Universal.json (dashdogy primary config)
        universal_json_path = target / "RTXMFG-Universal.json"
        try:
            has_dlss5_a = is_dlss5_present(target)
            universal_data = {
                "version": 40,
                "followGame": True,
                "mode": "follow",
                "multiplier": multiplier,
                "forcedMaximumMultiplier": multiplier,
                "hotkey": vk_code,
                "menuKey": menu_key,
                "overrideDlssPreset": False if is_default else True,
                "dlssPreset": 0 if is_default else int(render_preset_val),
                "dlssSrPreset": 0 if is_default else int(render_preset_val),
                "dlssgPreset": dlssg_preset_val,
                "enableImGui": not has_dlss5_a,
                "overlayMenu": not has_dlss5_a
            }
            with open(universal_json_path, "w", encoding="utf-8") as f:
                json.dump(universal_data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

        has_dlss5_a = is_dlss5_present(target)
        updates = {
            "General": {
                "MenuKey": menu_key,
                "ToggleKey": str(vk_code),
                "Multiplier": str(multiplier),
                "Preset": clean_preset_name,
                "DLSSPreset": clean_preset_name,
                "DLSSGPreset": clean_dlssg_name,
                "RenderPreset": render_preset_val,
                "OverrideDlssPreset": "0" if is_default else "1",
                "DlssSrPreset": render_preset_val,
                "BinkHook": "1" if bink_hook else "0",
                "OverlayMenu": "false" if has_dlss5_a else "true",
                "EnableImGui": "0" if has_dlss5_a else "1",
                "EnableUI": "0" if has_dlss5_a else "1"
            },
            "Compatibility": {
                "GpuNameOverride": "1",
                "Rtx30FlipMetering": "on"
            }
        }

        ok1 = cls.write_ini_sections(target / "RTXMFG-UI.ini", updates)
        ok2 = cls.write_ini_sections(target / "mfg_unlocker.ini", updates)

        overlay_updates = {
            "Overlay": {
                "ToggleKey": str(vk_code),
                "FirstLaunchMenuShown": "1",
                "OverlayMenu": "false" if has_dlss5_a else "true",
                "EnableImGui": "0" if has_dlss5_a else "1"
            },
            "Compatibility": {
                "GpuNameOverride": "1",
                "Rtx30FlipMetering": "on"
            }
        }
        ok3 = cls.write_ini_sections(target / "RTX40MFG-UI.ini", overlay_updates)


        return ok1 or ok2 or ok3

    @classmethod
    def read_mode_a_reverse(cls, target_dir: Union[str, Path]) -> Optional[Dict[str, Any]]:
        """
        Reverse sync: read parameters from TargetExeDir/RTXMFG-UI.ini, mfg_unlocker.ini, or RTX40MFG-UI.ini.
        """
        target = Path(target_dir)
        ini1 = target / "RTXMFG-UI.ini"
        ini2 = target / "mfg_unlocker.ini"
        ini3 = target / "RTX40MFG-UI.ini"

        data: Dict[str, Dict[str, str]] = {}
        if ini1.exists():
            data = cls.read_ini_sections(ini1)
        elif ini2.exists():
            data = cls.read_ini_sections(ini2)

        sec = data.get("General", {})
        config: Dict[str, Any] = {}
        if "Multiplier" in sec:
            try:
                config["multiplier"] = int(sec["Multiplier"])
            except Exception:
                pass

        if "MenuKey" in sec:
            config["menu_key"] = sec["MenuKey"]
        elif "ToggleKey" in sec:
            try:
                vk_code = int(sec["ToggleKey"])
                vk_inv = {8: "Backspace", 122: "F11", 45: "Insert", 36: "Home", 35: "End", 46: "Delete"}
                config["menu_key"] = vk_inv.get(vk_code, "Backspace")
            except Exception:
                config["menu_key"] = "Backspace"

        # Check RTX40MFG-UI.ini for actual Overlay ToggleKey
        if ini3.exists():
            data3 = cls.read_ini_sections(ini3)
            sec3 = data3.get("Overlay", {})
            if "ToggleKey" in sec3:
                try:
                    vk_code = int(sec3["ToggleKey"])
                    vk_inv = {8: "Backspace", 122: "F11", 45: "Insert", 36: "Home", 35: "End", 46: "Delete"}
                    if vk_code in vk_inv:
                        config["menu_key"] = vk_inv[vk_code]
                except Exception:
                    pass

        raw_p = sec.get("Preset") or sec.get("DLSSPreset") or sec.get("RenderPreset")
        if raw_p is not None:
            p_clean = raw_p.strip()
            if p_clean in ["0", "", "Default", "default", "none", "None"]:
                config["dlss_preset"] = "Default"
            elif p_clean in ["13", "M", "Preset M"]:
                config["dlss_preset"] = "M"
            elif p_clean in ["12", "L", "Preset L"]:
                config["dlss_preset"] = "L"
            elif p_clean in ["11", "K", "Preset K"]:
                config["dlss_preset"] = "K"
            elif p_clean in ["10", "J", "Preset J"]:
                config["dlss_preset"] = "J"
            elif p_clean in ["6", "F", "Preset F"]:
                config["dlss_preset"] = "F"
            elif p_clean in ["5", "E", "Preset E"]:
                config["dlss_preset"] = "E"
            elif p_clean in ["4", "D", "Preset D"]:
                config["dlss_preset"] = "D"
            elif p_clean in ["3", "C", "Preset C"]:
                config["dlss_preset"] = "C"
            elif p_clean in ["2", "B", "Preset B"]:
                config["dlss_preset"] = "B"
            elif p_clean in ["1", "A", "Preset A"]:
                config["dlss_preset"] = "A"
            else:
                config["dlss_preset"] = "K"
        else:
            config["dlss_preset"] = "Default"

        if "BinkHook" in sec:
            config["bink_hook"] = (sec["BinkHook"] in ["1", "true", "True"])

        # Reverse sync DLSS-G preset from RTXMFG-Universal.json and INI
        univ_json = target / "RTXMFG-Universal.json"
        if univ_json.exists():
            try:
                with open(univ_json, "r", encoding="utf-8") as f:
                    u_data = json.load(f)
                    if "multiplier" in u_data and "multiplier" not in config:
                        config["multiplier"] = int(u_data["multiplier"])
                    if "menuKey" in u_data and "menu_key" not in config:
                        config["menu_key"] = u_data["menuKey"]
                    if "dlssgPreset" in u_data:
                        g_map = {3: "C", 2: "B", 1: "A", 0: "Auto"}
                        config["dlssg_preset"] = g_map.get(int(u_data["dlssgPreset"]), "C")
            except Exception:
                pass

        if "dlssg_preset" not in config:
            raw_gp = sec.get("DLSSGPreset")
            if raw_gp:
                gp_clean = raw_gp.strip().upper()
                if gp_clean in ["C", "3"]:
                    config["dlssg_preset"] = "C"
                elif gp_clean in ["B", "2"]:
                    config["dlssg_preset"] = "B"
                elif gp_clean in ["A", "1"]:
                    config["dlssg_preset"] = "A"
                elif gp_clean in ["AUTO", "0"]:
                    config["dlssg_preset"] = "Auto"

        return config if (config or ini3.exists() or univ_json.exists()) else None
