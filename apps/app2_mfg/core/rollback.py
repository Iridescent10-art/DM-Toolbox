"""
Universal MFG Patcher - Transactional Manifest-Based Rollback Engine.
"""

import os
import shutil
import json
import configparser
from pathlib import Path
from typing import Tuple, List, Optional
from core.models import GameInfo, PatchManifest
from core.utils import is_process_running, kill_locking_processes, safe_force_remove, cleanup_pending_files

class RollbackEngine:
    def __init__(self):
        pass

    def rollback(self, target_dir: str, exe_name: Optional[str] = None) -> Tuple[bool, str]:
        """
        Perform a safe, atomic rollback based on .mfg_patch_manifest.json.
        Applies triple-layer force unlock and removal pipeline:
        1. Terminate any lingering processes in target_dir or matching exe_name/crash handlers
        2. Atomic NTFS rename bypass for active DLL locks
        3. Restore all original backups and manifests
        Returns (success, message).
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
        if not os.path.exists(manifest_file):
            return False, f"未找到修补清单文件 (.mfg_patch_manifest.json)，目标游戏可能未通过本软件修补。"

        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
            manifest = PatchManifest(**manifest_data)
        except Exception as e:
            return False, f"无法读取修补清单: {e}"

        errors: List[str] = []

        # Check if other third-party / user addons exist in target_dir (e.g. HDR mods, RTX40MFG-UI, etc.)
        other_addons = []
        try:
            for item in os.listdir(target_dir):
                item_lower = item.lower()
                if (item_lower.endswith(".addon64") or item_lower.endswith(".addon")) and item_lower != "renodx-mfgunlock.addon64":
                    other_addons.append(item)
        except Exception:
            other_addons = []

        from core.state_cleaner import is_optiscaler_dll_file, is_reshade_dll_file, find_reshade_framework_dll

        # 1. Delete created files via safe_force_remove
        for rel_file in manifest.created_files:
            full_path = os.path.join(target_dir, rel_file)
            if rel_file.lower() == "dxgi.dll" and other_addons:
                # If dxgi.dll was OptiScaler, NEVER leave OptiScaler behind when rolling back!
                if is_optiscaler_dll_file(full_path):
                    safe_force_remove(full_path)
                    # Replace with real ReShade so remaining addons (e.g. DLSS 5) can continue to function
                    reshade_fw = find_reshade_framework_dll()
                    if reshade_fw and os.path.exists(reshade_fw):
                        try:
                            shutil.copy2(reshade_fw, full_path)
                        except Exception:
                            pass
                continue

            if os.path.exists(full_path) or os.path.islink(full_path):
                ok = safe_force_remove(full_path)
                if not ok and os.path.exists(full_path):
                    errors.append(f"删除注入文件失败 '{rel_file}': 文件被系统保护")

        # 2. Restore renamed backups
        for rec in manifest.renamed_backups:
            orig_name = rec.get("original")
            bak_name = rec.get("backup")
            if not orig_name or not bak_name:
                continue

            orig_path = os.path.join(target_dir, orig_name)
            bak_path = os.path.join(target_dir, bak_name)

            # If other addons exist and original was dxgi.dll, only preserve if already a valid ReShade
            if orig_name.lower() == "dxgi.dll" and other_addons:
                if is_reshade_dll_file(orig_path):
                    continue

            orig_path = os.path.join(target_dir, orig_name)
            bak_path = os.path.join(target_dir, bak_name)

            if os.path.exists(bak_path):
                if os.path.exists(orig_path):
                    safe_force_remove(orig_path)
                try:
                    os.replace(bak_path, orig_path)
                except Exception as e:
                    errors.append(f"恢复备份文件失败 '{orig_name}': {e}")

        # 3. Rollback INI modifications (e.g. ReShade.ini LoadFromDllMain)
        for ini_mod in manifest.ini_modifications:
            ini_filename = ini_mod.get("file", "ReShade.ini")
            section_name = ini_mod.get("section", "ADDON")
            key_name = ini_mod.get("key", "LoadFromDllMain")
            val_to_remove = ini_mod.get("value_added", "").strip().lower()

            ini_path = os.path.join(target_dir, ini_filename)
            if os.path.exists(ini_path) and val_to_remove:
                self._remove_from_ini(ini_path, section_name, key_name, val_to_remove)

        # 4. Clean up any leftover runtime log, temp json or old proxy
        leftover_patterns = [
            "RTXMFG-Universal.json", "MFGUnlocker.log", "rtxmfg.log",
            "OptiScaler.log", "fakenvapi.log", "dlssg_to_fsr3.log"
        ]
        for p in leftover_patterns:
            lp = os.path.join(target_dir, p)
            if os.path.exists(lp):
                safe_force_remove(lp)

        # 5. Remove manifest file itself
        safe_force_remove(manifest_file)

        # 6. Final sweep of any temporary trash files
        cleanup_pending_files(target_dir)

        if errors:
            return False, "还原过程中出现警告/错误:\n" + "\n".join(errors)
        return True, f"已成功还原游戏 '{manifest.game_name}' 至修补前纯净状态！"

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
