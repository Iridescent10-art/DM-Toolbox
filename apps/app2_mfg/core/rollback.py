"""
Universal MFG Patcher - Transactional Manifest-Based Rollback Engine.
"""

import os
import sys
import shutil
import json
import configparser
from pathlib import Path
from typing import Tuple, List, Optional

APP2_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = APP2_DIR.parent.parent
if str(APP2_DIR) not in sys.path:
    sys.path.insert(0, str(APP2_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.models import GameInfo, PatchManifest
from core.utils import is_process_running, kill_locking_processes, safe_force_remove, cleanup_pending_files
from core.state_cleaner import is_optiscaler_dll_file, is_reshade_dll_file, is_dashdogy_dll_file, find_reshade_framework_dll

class RollbackEngine:
    def __init__(self):
        pass

    def rollback(self, target_dir: str, exe_name: Optional[str] = None, clean_all: bool = False) -> Tuple[bool, str]:
        """
        Perform a safe, atomic rollback and deep directory purge.
        Applies triple-layer force unlock and removal pipeline:
        1. Terminate any lingering processes in target_dir or matching exe_name/crash handlers
        2. Atomic NTFS rename bypass for active DLL locks
        3. Restore all original backups and manifests
        4. Deep purge of proxy DLLs, mod runtimes, logs, and crash dumps

        clean_all:
          - True: Complete 100% official pure restore. Purges all injected proxies,
            OptiScaler/MFG/DLSS 5 runtimes, logs, configs, and crash dumps.
          - False: Preserves DLSS 5 addon & runtime while restoring MFG components.
        """
        # Layer 1: Force terminate any locking processes in target directory
        kill_locking_processes(target_dir, exe_name)
        cleanup_pending_files(target_dir)

        if exe_name and is_process_running(exe_name):
            # If still running after kill attempt, re-check
            time_waited = 0
            while time_waited < 1.0 and is_process_running(exe_name):
                import time
                time.sleep(0.2)
                time_waited += 0.2
            if is_process_running(exe_name):
                return False, f"游戏进程 '{exe_name}' 正在运行中！请先关闭游戏，再执行还原。"

        manifest_file = os.path.join(target_dir, ".mfg_patch_manifest.json")
        manifest = None
        if os.path.exists(manifest_file):
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
                manifest = PatchManifest(**manifest_data)
            except Exception as e:
                manifest = None
        elif not clean_all:
            return False, "未找到修补清单文件 (.mfg_patch_manifest.json)，目标游戏可能未通过本软件修补。"

        errors: List[str] = []

        # Check if other third-party / user addons exist in target_dir (e.g. DLSS 5, HDR mods)
        other_addons = []
        try:
            for item in os.listdir(target_dir):
                item_lower = item.lower()
                if (item_lower.endswith(".addon64") or item_lower.endswith(".addon")) and item_lower != "renodx-mfgunlock.addon64":
                    other_addons.append(item)
        except Exception:
            other_addons = []

        restored_originals = set()

        # 1. Restore renamed backups
        if manifest:
            for rec in manifest.renamed_backups:
                orig_name = rec.get("original")
                bak_name = rec.get("backup")
                if not orig_name or not bak_name:
                    continue

                orig_path = os.path.join(target_dir, orig_name)
                bak_path = os.path.join(target_dir, bak_name)

                # If other addons exist and original was dxgi.dll, only preserve if already a valid ReShade and clean_all is False
                if not clean_all and orig_name.lower() == "dxgi.dll" and other_addons:
                    if is_reshade_dll_file(orig_path):
                        continue

                if os.path.exists(bak_path):
                    if os.path.exists(orig_path):
                        safe_force_remove(orig_path)
                    try:
                        os.replace(bak_path, orig_path)
                        restored_originals.add(orig_name.lower())
                    except Exception:
                        try:
                            shutil.copy2(bak_path, orig_path)
                            safe_force_remove(bak_path)
                            restored_originals.add(orig_name.lower())
                        except Exception as e:
                            errors.append(f"恢复备份文件失败 '{orig_name}': {e}")

        imported_pe_dlls = set()
        try:
            from core.utils import get_game_statically_imported_dlls, auto_heal_game_dependencies
            imported_pe_dlls = get_game_statically_imported_dlls(target_dir)
        except Exception:
            pass

        # 2. Delete created files via safe_force_remove
        if manifest:
            for rel_file in manifest.created_files:
                if rel_file.lower() in restored_originals or rel_file.lower() in imported_pe_dlls:
                    continue
                full_path = os.path.join(target_dir, rel_file)
                if not clean_all and rel_file.lower() == "dxgi.dll" and other_addons:
                    # If dxgi.dll was OptiScaler, replace with pure ReShade so DLSS 5 can run
                    if is_optiscaler_dll_file(full_path):
                        safe_force_remove(full_path)
                        reshade_fw = find_reshade_framework_dll()
                        if reshade_fw and os.path.exists(reshade_fw):
                            try:
                                shutil.copy2(reshade_fw, full_path)
                            except Exception:
                                pass
                    continue

                if os.path.isdir(full_path):
                    shutil.rmtree(full_path, ignore_errors=True)
                elif os.path.exists(full_path) or os.path.islink(full_path):
                    ok = safe_force_remove(full_path)
                    if not ok and os.path.exists(full_path):
                        errors.append(f"删除注入文件失败 '{rel_file}': 文件被系统保护")

        # 3. Rollback INI modifications
        if manifest and not clean_all:
            for ini_mod in manifest.ini_modifications:
                ini_filename = ini_mod.get("file", "ReShade.ini")
                section_name = ini_mod.get("section", "ADDON")
                key_name = ini_mod.get("key", "LoadFromDllMain")
                val_to_remove = ini_mod.get("value_added", "").strip().lower()

                ini_path = os.path.join(target_dir, ini_filename)
                if os.path.exists(ini_path) and val_to_remove:
                    self._remove_from_ini(ini_path, section_name, key_name, val_to_remove)

        # 4. Deep Directory Purge & Anti-Conflict Sweep
        # (A) Remove mod directories
        dirs_to_clean = ["OptiScaler", "D3D12_Optiscaler", "XeSS", "amd_fidelityfx", "dlssg_sm86", "RenoDX"]
        if clean_all:
            dirs_to_clean.append("dlss5-nr-runtime")

        for d_name in dirs_to_clean:
            dp = os.path.join(target_dir, d_name)
            if os.path.exists(dp) and os.path.isdir(dp):
                try:
                    shutil.rmtree(dp, ignore_errors=True)
                except Exception:
                    pass

        # (B) Restore .dm_backup if present and purge .dm_backup directory
        dm_backup_dir = os.path.join(target_dir, ".dm_backup")
        if os.path.exists(dm_backup_dir) and os.path.isdir(dm_backup_dir):
            try:
                for bf in os.listdir(dm_backup_dir):
                    src_b = os.path.join(dm_backup_dir, bf)
                    dst_b = os.path.join(target_dir, bf)
                    if not os.path.exists(dst_b) or is_optiscaler_dll_file(dst_b) or is_dashdogy_dll_file(dst_b):
                        safe_force_remove(dst_b)
                        shutil.copy2(src_b, dst_b)
                        restored_originals.add(bf.lower())
                pass
            except Exception:
                pass

        # (C) Bink2 Hook Restoration
        bink_hook = os.path.join(target_dir, "bink2w64Hooked.dll")
        bink_orig = os.path.join(target_dir, "bink2w64.dll")
        if os.path.exists(bink_hook):
            safe_force_remove(bink_orig)
            try:
                os.replace(bink_hook, bink_orig)
            except Exception:
                try:
                    shutil.copy2(bink_hook, bink_orig)
                    safe_force_remove(bink_hook)
                except Exception:
                    pass

        # (D) Remove specific OptiScaler & third-party bridge files (protecting game static PE dependencies)
        imported_pe_dlls = set()
        try:
            from core.utils import get_game_statically_imported_dlls, auto_heal_game_dependencies
            imported_pe_dlls = get_game_statically_imported_dlls(target_dir)
        except Exception:
            pass

        mode_c_files = [
            "OptiScaler.dll", "dlssg_to_fsr3_amd_is_better.dll",
            "amd_fidelityfx_dx12.dll", "amd_fidelityfx_framegeneration_dx12.dll",
            "amd_fidelityfx_upscaler_dx12.dll", "amd_fidelityfx_vk.dll",
            "libxell.dll", "libxess.dll", "libxess_dx11.dll", "libxess_fg.dll",
            "fakenvapi.dll", "fakenvapi.ini", "fakenvapi.log",
            "OptiScaler.ini", "OptiScaler.log", "nvngx.ini", "dlssg_to_fsr3.log", "dlssg_sm86.ini"
        ]
        for f_name in mode_c_files:
            if f_name.lower() in imported_pe_dlls:
                continue
            fp = os.path.join(target_dir, f_name)
            if os.path.exists(fp):
                safe_force_remove(fp)
        try:
            auto_heal_game_dependencies(target_dir)
        except Exception:
            pass

        # (E) Remove Mode A configs and logs
        mode_a_files = [
            "RTXMFG-Universal.json", "RTXMFG-Universal.status.json",
            "RTX40MFG-UI.ini", "RTXMFG-UI.ini", "mfg_unlocker.ini",
            "RTX40MFG-UI-layout.ini", "MFGUnlocker.log", "rtxmfg.log",
            "MFGUnlocker.dll"
        ]
        for f_name in mode_a_files:
            fp = os.path.join(target_dir, f_name)
            if os.path.exists(fp):
                safe_force_remove(fp)

        # (F) Remove Mode B addon
        safe_force_remove(os.path.join(target_dir, "renodx-mfgunlock.addon64"))

        # (G) Remove ReShade64.dll (always a secondary bridge)
        safe_force_remove(os.path.join(target_dir, "ReShade64.dll"))

        # (H) Remove proxy DLLs if injected
        for proxy in ["version.dll", "winmm.dll", "dinput8.dll", "wininet.dll"]:
            pp = os.path.join(target_dir, proxy)
            if os.path.exists(pp) and proxy.lower() not in restored_originals:
                if is_dashdogy_dll_file(pp) or is_optiscaler_dll_file(pp) or is_reshade_dll_file(pp):
                    safe_force_remove(pp)

        # (I) Clean crash dumps and runtime logs
        td_path = Path(target_dir)
        for crash_file in td_path.glob("dlss5-nr-crash-*.txt"):
            safe_force_remove(str(crash_file))
        for rtx_log in td_path.glob("RTXMFG-*.log"):
            safe_force_remove(str(rtx_log))
        for rtx_csv in td_path.glob("RTXMFG-*.csv"):
            safe_force_remove(str(rtx_csv))

        # (J) Clean DLSS 5 files and dxgi.dll
        dxgi_p = os.path.join(target_dir, "dxgi.dll")
        if clean_all:
            for addon_file in list(td_path.glob("*.addon64")) + list(td_path.glob("*.addon")):
                safe_force_remove(str(addon_file))
            for proxy_f in ["version.dll", "winmm.dll", "dinput8.dll", "wininet.dll", "fakenvapi.dll", "fakenvapi.ini", "fakenvapi.log"]:
                safe_force_remove(os.path.join(target_dir, proxy_f))
            safe_force_remove(os.path.join(target_dir, ".dlss5_manifest.json"))
            safe_force_remove(os.path.join(target_dir, ".mfg_patch_manifest.json"))
            safe_force_remove(os.path.join(target_dir, "renodx-dlss5.addon64"))
            safe_force_remove(os.path.join(target_dir, "renodx-dlss5-v11.9.addon64"))
            safe_force_remove(os.path.join(target_dir, "renodx-dlss5-Lecram-v11-Beta48.addon64"))
            safe_force_remove(os.path.join(target_dir, "renodx-dlss.addon64"))
            safe_force_remove(os.path.join(target_dir, "renodx-dlss-ShortFuse-261017汉化版.addon64"))
            safe_force_remove(os.path.join(target_dir, "lecram-dlss5-beta10.addon64"))
            safe_force_remove(os.path.join(target_dir, "dlss5-nr.addon64"))
            safe_force_remove(os.path.join(target_dir, "nvngx_dlssnr.dll"))
            safe_force_remove(os.path.join(target_dir, ".dlss5_config.json"))
            safe_force_remove(os.path.join(target_dir, ".dlss5_patch_manifest.json"))
            safe_force_remove(os.path.join(target_dir, "ReShade.ini"))
            safe_force_remove(os.path.join(target_dir, "ReShade.ini.v11-backup"))
            safe_force_remove(os.path.join(target_dir, "ReShade.log"))

            dlss5_bak = os.path.join(target_dir, "dxgi.dll.dlss5_bak")
            if os.path.exists(dlss5_bak):
                safe_force_remove(dxgi_p)
                try:
                    os.replace(dlss5_bak, dxgi_p)
                except Exception:
                    pass
            elif "dxgi.dll" not in restored_originals:
                if is_reshade_dll_file(dxgi_p) or is_optiscaler_dll_file(dxgi_p):
                    safe_force_remove(dxgi_p)
        else:
            # clean_all is False: if other addons exist (like DLSS 5 or user HDR mod), ensure dxgi.dll has ReShade host
            if other_addons:
                if is_optiscaler_dll_file(dxgi_p):
                    safe_force_remove(dxgi_p)
                if not os.path.exists(dxgi_p) or not is_reshade_dll_file(dxgi_p):
                    reshade_fw = find_reshade_framework_dll()
                    if reshade_fw and os.path.exists(reshade_fw):
                        try:
                            shutil.copy2(reshade_fw, dxgi_p)
                        except Exception:
                            pass
            elif "dxgi.dll" not in restored_originals:
                # No other addons exist: clean dxgi.dll completely!
                if is_reshade_dll_file(dxgi_p) or is_optiscaler_dll_file(dxgi_p):
                    safe_force_remove(dxgi_p)

        # 5. Remove manifest file itself
        safe_force_remove(manifest_file)
        if os.path.exists(dm_backup_dir) and os.path.isdir(dm_backup_dir):
            shutil.rmtree(dm_backup_dir, ignore_errors=True)

        # 6. Final sweep of any temporary trash files
        cleanup_pending_files(target_dir)

        game_name = manifest.game_name if manifest else "目标游戏"
        if errors:
            return False, f"还原游戏 '{game_name}' 过程中出现警告:\n" + "\n".join(errors)
        return True, f"已成功彻底还原游戏 '{game_name}' 至官方纯净状态！"

    def _remove_from_ini(self, ini_path: str, section: str, key: str, val_to_remove: str):
        """Safely parse ReShade.ini and remove the addon without touching other addons or comments."""
        try:
            with open(ini_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            in_target_section = False
            modified = False
            new_lines = []

            for line in lines:
                stripped = line.strip()
                if stripped.startswith("[") and stripped.endswith("]"):
                    sec_name = stripped[1:-1].strip()
                    in_target_section = (sec_name.lower() == section.lower())
                    new_lines.append(line)
                    continue

                if in_target_section and "=" in stripped:
                    k, v = stripped.split("=", 1)
                    if k.strip().lower() == key.lower():
                        # Parse comma-separated addons
                        items = [x.strip() for x in v.split(",") if x.strip()]
                        filtered_items = [x for x in items if x.lower() != val_to_remove]
                        if filtered_items:
                            new_lines.append(f"{k.strip()}={','.join(filtered_items)}\n")
                        else:
                            # If no addons left, we can omit key or leave empty
                            new_lines.append(f"{k.strip()}=\n")
                        modified = True
                        continue

                new_lines.append(line)

            if modified:
                with open(ini_path, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
        except Exception:
            pass
