"""
Universal MFG Patcher - Dual-Backend Patching Engine.
"""

import os
import shutil
import json
from pathlib import Path
from typing import Tuple, Optional, List
from core.models import GameInfo, BackendType, PatchManifest, QualificationStatus
from core.updater import ComponentUpdater
from core.rollback import RollbackEngine
from core.state_cleaner import CleanGameDirectoryState, is_dlss5_present
from core.utils import (
    is_process_running,
    get_system_gpu_name,
    is_rtx_40_or_newer,
    kill_locking_processes,
    safe_force_remove,
    cleanup_pending_files
)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent

PROXY_PRIORITY = ["version.dll", "winmm.dll", "dinput8.dll", "wininet.dll", "dxgi.dll"]

class PatchEngine:
    def __init__(self, updater: ComponentUpdater):
        self.updater = updater
        self.rollback_engine = RollbackEngine()

    def patch_game(
        self,
        game: GameInfo,
        requested_backend: BackendType = BackendType.SMART_AUTO,
        prefer_bink_hook: bool = False
    ) -> Tuple[bool, str]:
        """
        Execute one-click patching with transaction safety.
        Returns (success, message).
        """
        # 1. Process lock check and cleanup
        kill_locking_processes(game.target_dir, game.exe_name)
        cleanup_pending_files(game.target_dir)
        if is_process_running(game.exe_name):
            return False, f"游戏 '{game.name}' ({game.exe_name}) 正在运行中！\n请先完全退出游戏，防止文件写入损坏或共享冲突。"

        # 2. Check DLSS-G qualification
        if game.qualification == QualificationStatus.NOT_SUPPORTED:
            return False, f"该游戏未检测到 NVIDIA Streamline (缺少 sl.interposer.dll)，原生不支持 DLSS-G 帧生成！"

        # 3. Clean prior patch if present (prevent cross-pollution)
        manifest_file = os.path.join(game.target_dir, ".mfg_patch_manifest.json")
        if game.is_patched or os.path.exists(manifest_file):
            if os.path.exists(manifest_file):
                ok, msg = self.rollback_engine.rollback(game.target_dir, game.exe_name)
                if not ok:
                    return False, f"自动回滚已有补丁失败: {msg}"
            game.is_patched = False
            game.patched_backend = None

        # 4. Normalize and resolve backend
        if isinstance(requested_backend, str):
            for b in BackendType:
                if b.value == requested_backend or b.name.lower() == requested_backend.lower():
                    requested_backend = b
                    break
            else:
                requested_backend = BackendType.SMART_AUTO

        active_backend = requested_backend
        if active_backend == BackendType.SMART_AUTO:
            gpu_name = get_system_gpu_name()
            if not is_rtx_40_or_newer(gpu_name):
                # RTX 20/30 (SM75/SM86) -> Auto select Mode D (Native DLSS-G)!
                # GTX / AMD / Intel GPU -> Auto select Mode C (OptiScaler FSR 3.1 bridge)
                gpu_upper = gpu_name.upper()
                if "RTX 30" in gpu_upper or "RTX 20" in gpu_upper or "SM86" in gpu_upper or "SM75" in gpu_upper or "A100" in gpu_upper:
                    active_backend = BackendType.DLSSG_SM86
                else:
                    active_backend = BackendType.OPTISCALER_FSR
            else:
                # RTX 40 / 50 series -> Native DLSS-G MFG Unlocker
                if game.has_reshade:
                    active_backend = BackendType.RESHADE_ADDON
                else:
                    active_backend = BackendType.STANDALONE

        backend_str = active_backend.value if hasattr(active_backend, "value") else str(active_backend)

        manifest = PatchManifest(
            app_version="1.0.0",
            game_name=game.name,
            target_exe=game.exe_path,
            target_dir=game.target_dir,
            active_backend=backend_str,
            installed_version="latest"
        )

        try:
            if active_backend == BackendType.STANDALONE or backend_str == BackendType.STANDALONE.value:
                target_mode_char = "A"
            elif active_backend == BackendType.RESHADE_ADDON or backend_str == BackendType.RESHADE_ADDON.value:
                target_mode_char = "B"
            elif active_backend == BackendType.OPTISCALER_FSR or backend_str == BackendType.OPTISCALER_FSR.value:
                target_mode_char = "C"
            elif active_backend == BackendType.DLSSG_SM86 or backend_str == BackendType.DLSSG_SM86.value:
                target_mode_char = "D"
            else:
                target_mode_char = "C"
            has_dlss5 = is_dlss5_present(game.target_dir)
            target_proxy = self._resolve_proxy_slot(game, is_coexisting_with_dlss5=has_dlss5, active_backend=active_backend)
            CleanGameDirectoryState(game.target_dir, preserve_dlss5=has_dlss5, target_mode=target_mode_char, target_proxy=target_proxy)

            if active_backend == BackendType.STANDALONE or backend_str == BackendType.STANDALONE.value:
                success, err = self._apply_standalone_patch(game, manifest, prefer_bink_hook)
                if not success:
                    return False, err
            elif active_backend == BackendType.RESHADE_ADDON or backend_str == BackendType.RESHADE_ADDON.value:
                success, err = self._apply_reshade_addon_patch(game, manifest)
                if not success:
                    return False, err
            elif active_backend == BackendType.OPTISCALER_FSR or backend_str == BackendType.OPTISCALER_FSR.value:
                success, err = self._apply_optiscaler_patch(game, manifest)
                if not success:
                    return False, err
            elif active_backend == BackendType.DLSSG_SM86 or backend_str == BackendType.DLSSG_SM86.value:
                success, err = self._apply_dlssg_sm86_patch(game, manifest)
                if not success:
                    return False, err
            else:
                return False, f"未知的修补后端类型: {requested_backend}"

            # Write manifest to disk
            manifest_path = os.path.join(game.target_dir, ".mfg_patch_manifest.json")
            with open(manifest_path, "w", encoding="utf-8") as f:
                f.write(manifest.to_json())

            game.is_patched = True
            game.patched_backend = backend_str

            if active_backend == BackendType.OPTISCALER_FSR or backend_str == BackendType.OPTISCALER_FSR.value:
                try:
                    from core.optiscaler_config import load_optiscaler_preset, get_preset_summary
                    from core.ini_sync import IniConfigManager
                    c_preset = load_optiscaler_preset()
                    report = IniConfigManager.last_report or {}
                    if report.get("interpolation_count") is not None:
                        c_preset["interpolation_count"] = report["interpolation_count"]
                    if report.get("menu_scale") is not None:
                        c_preset["menu_scale"] = float(report["menu_scale"])
                    summary_str = get_preset_summary(c_preset)
                    key_name = c_preset.get("menu_key", "Insert")
                    warn_text = "".join(
                        f"\n⚠️ {w}" for w in (IniConfigManager.last_report or {}).get("warnings", [])
                    )
                    try:
                        from common.config_manager import detect_vram_overcommit
                        _vram = detect_vram_overcommit()
                        if _vram:
                            warn_text += f"\n⚠️ 【显存伪装风险】{_vram}"
                    except Exception:
                        pass
                    if has_dlss5 and not has_rtx_40_or_newer:
                        warn_text += (
                            "\n⚠️ 检测到 RTX 20/30 系 + DLSS 5：XeFG 需要游戏原生 DLSS-G 作为插帧输入，"
                            "而 20/30 系通常要靠 fakenvapi 伪装出 DLSS-G 开关，"
                            "它与 DLSS 5 的 NVAPI 查询冲突（已被自动禁用）。"
                            "如需 XeSS 多帧插帧，请单独使用模式 C（不叠加 DLSS 5），"
                            "或改用模式 D 的原生 DLSS-G 多帧。"
                        )
                    if has_dlss5:
                        callout = (
                            f"⚡ 检测到 DLSS 5 共存态：已启用全自动双通道无缝共存！\n"
                            f"✨ 核心插帧代理已安全挂载至【{target_proxy}】（避让 DLSS 5 ReShade 渲染底座 dxgi.dll）\n"
                            f"✨ 模式 C 已作为后台静默帧生成平稳运行（无悬浮窗干扰）\n"
                            f"✨ 在游戏画质设置中直接开启【DLSS 帧生成】即刻生效！\n"
                            f"✨ 已自动注入模式 C 预设: {summary_str}{warn_text}"
                        )
                    else:
                        callout = (
                            f"在游戏设置中开启【DLSS 帧生成】即按预设生效！\n"
                            f"✨ 进游戏按【{key_name}】呼出 OptiScaler 调校菜单\n"
                            f"✨ 核心插帧代理已挂载至【{target_proxy}】\n"
                            f"✨ 已自动注入模式 C 预设: {summary_str}{warn_text}"
                        )
                except Exception:
                    callout = "在游戏画质设置中开启【DLSS 帧生成】(进游戏按【Insert】呼出 OptiScaler 菜单)"
            elif active_backend == BackendType.STANDALONE or backend_str == BackendType.STANDALONE.value:
                try:
                    from core.optiscaler_config import load_mode_a_preset, get_mode_a_preset_summary
                    from core.ini_sync import IniConfigManager
                    preset_a = load_mode_a_preset()
                    summary_a = get_mode_a_preset_summary(preset_a)
                    IniConfigManager.sync_mode_a_forward(game.target_dir, preset_a)
                    callout = f"按 【Backspace】 打开菜单\n✨ 已自动写入模式 A 预设: {summary_a}"
                except Exception:
                    callout = "按 【Backspace】 打开菜单"
            elif active_backend == BackendType.DLSSG_SM86 or backend_str == BackendType.DLSSG_SM86.value:
                try:
                    from core.optiscaler_config import load_dlssg_sm86_preset, get_dlssg_sm86_preset_summary
                    from core.ini_sync import IniConfigManager
                    preset_d = load_dlssg_sm86_preset()
                    summary_d = get_dlssg_sm86_preset_summary(preset_d)
                    IniConfigManager.sync_mode_d_forward(game.target_dir, preset_d, game.exe_name)
                    callout = (
                        f"在游戏画质设置中直接开启【DLSS 帧生成】即刻生效！\n"
                        f"⚡ 已自动注入模式 D 原生预设: {summary_d}\n"
                        f"✨ 专为 RTX 20/30 系优化，原生 DLSS 3/4.5 多倍插帧 + INT8 超分加速"
                    )
                    try:
                        from core.utils import describe_mode_d_mfg_status
                        callout += describe_mode_d_mfg_status(game.target_dir)
                    except Exception:
                        pass
                except Exception:
                    callout = "在游戏画质设置中直接开启【DLSS 帧生成】"
            else:
                callout = "按 【Home】 在 ReShade 面板中打开菜单"

            reshade_notice = ""
            if active_backend == BackendType.RESHADE_ADDON or backend_str == BackendType.RESHADE_ADDON.value:
                game.has_reshade = True
                reshade_notice = "\n✨ 已全自动物理注入 ReShade 6.8 框架 (dxgi.dll) 与 RenoDX 插帧插件！\n(已替代 RHI 手动安装，进游戏按【Home】键即可直接调校)"

            return True, f"游戏 '{game.name}' 修补成功！\n使用模式: {backend_str}\n{callout}{reshade_notice}"

        except Exception as e:
            # Atomic rollback on exception
            self.rollback_engine.rollback(game.target_dir, game.exe_name)
            return False, f"修补过程发生异常，已自动回滚: {e}"

    def _apply_standalone_patch(self, game: GameInfo, manifest: PatchManifest, prefer_bink_hook: bool) -> Tuple[bool, str]:
        source_dll = self.updater.get_latest_cached_file(BackendType.STANDALONE)
        if not source_dll or not os.path.exists(source_dll):
            return False, "本地缓存中未找到 dashdogy/MFG-Unlocker 组件！\n请先在主界面点击【检查并同步最新版本】进行下载。"

        target_dir = game.target_dir
        kill_locking_processes(target_dir, game.exe_name)
        cleanup_pending_files(target_dir)

        # Purge Mode B & C conflicting files
        for mode_bc_file in ["OptiScaler.ini", "nvngx.ini", "dlssg_to_fsr3_amd_is_better.dll", "fakenvapi.dll", "fakenvapi.ini", "renodx-mfgunlock.addon64"]:
            f_p = os.path.join(target_dir, mode_bc_file)
            if os.path.exists(f_p):
                safe_force_remove(f_p)

        # Purge any old proxies that belong to OptiScaler or ReShade so they don't block dashdogy or conflict
        has_dlss5 = is_dlss5_present(target_dir)
        for proxy_cand in ["winmm.dll", "version.dll", "dinput8.dll", "wininet.dll", "dxgi.dll"]:
            p_p = os.path.join(target_dir, proxy_cand)
            if os.path.exists(p_p):
                if proxy_cand == "dxgi.dll":
                    if self._is_optiscaler_dll(p_p):
                        safe_force_remove(p_p)
                    elif not has_dlss5 and self._is_reshade_dll(p_p):
                        safe_force_remove(p_p)
                else:
                    if self._is_optiscaler_dll(p_p) or self._is_reshade_dll(p_p):
                        safe_force_remove(p_p)

        existing_files = {f.lower() for f in os.listdir(target_dir)}

        if prefer_bink_hook and "bink2w64.dll" in existing_files:
            # Bink hooked route
            orig_bink = os.path.join(target_dir, "bink2w64.dll")
            hooked_bink = os.path.join(target_dir, "bink2w64Hooked.dll")

            # Rename original to bink2w64Hooked.dll
            os.rename(orig_bink, hooked_bink)
            manifest.renamed_backups.append({"original": "bink2w64.dll", "backup": "bink2w64Hooked.dll"})

            # Copy MFGUnlocker as bink2w64.dll
            shutil.copy2(source_dll, orig_bink)
            manifest.created_files.append("bink2w64.dll")
            return True, ""

        # Mode A proxy slot: dynamically resolved based on PE imports (winmm > version)
        selected_proxy = self._resolve_proxy_slot(game, is_coexisting_with_dlss5=has_dlss5, active_backend=BackendType.STANDALONE)
        dest_proxy_path = os.path.join(target_dir, selected_proxy)
        if os.path.exists(dest_proxy_path):
            safe_force_remove(dest_proxy_path)
        shutil.copy2(source_dll, dest_proxy_path)
        manifest.created_files.append(selected_proxy)

        # If DLSS 5 is active in Mode A, ensure ReShade is deployed as dxgi.dll
        if has_dlss5:
            dxgi_path = os.path.join(target_dir, "dxgi.dll")
            if not os.path.exists(dxgi_path) or not self._is_reshade_dll(dxgi_path):
                dlss5_dxgi = ROOT_DIR / "apps" / "app6_dlss5" / "assets" / "dxgi.dll"
                reshade_src = str(dlss5_dxgi) if dlss5_dxgi.exists() else self.updater.get_reshade_framework_dll()
                if reshade_src and os.path.exists(reshade_src):
                    safe_force_remove(dxgi_path)
                    shutil.copy2(reshade_src, dxgi_path)
            # dxgi.dll belongs to DLSS 5, never register in created_files for Mode A!
            safe_force_remove(os.path.join(target_dir, "ReShade64.dll"))

        # Forward sync Mode A INI configs
        try:
            from core.optiscaler_config import load_mode_a_preset
            from core.ini_sync import IniConfigManager
            preset_a = load_mode_a_preset()
            IniConfigManager.sync_mode_a_forward(target_dir, preset_a)
            for ini_file in ["RTX40MFG-UI.ini", "RTXMFG-UI.ini", "mfg_unlocker.ini"]:
                if os.path.exists(os.path.join(target_dir, ini_file)) and ini_file not in manifest.created_files:
                    manifest.created_files.append(ini_file)
        except Exception:
            pass

        return True, ""

    def _read_dll_signature_bytes(self, path: str) -> bytes:
        if not path or not os.path.exists(path) or not os.path.isfile(path):
            return b""
        try:
            size = os.path.getsize(path)
            with open(path, "rb") as f:
                if size > 32 * 1024 * 1024:
                    head = f.read(16 * 1024 * 1024)
                    f.seek(max(0, size - 16 * 1024 * 1024))
                    return head + f.read()
                return f.read()
        except Exception:
            return b""

    def _is_dashdogy_dll(self, path: str) -> bool:
        """Check if a DLL file is dashdogy/MFGUnlocker."""
        data = self._read_dll_signature_bytes(path)
        return b"MFGUnlocker" in data or b"RTX40MFG" in data or b"RTXMFG" in data

    def _get_pe_imported_proxies(self, exe_path: str) -> List[str]:
        """
        Analyze PE Import Table of game executable to find natively imported proxy DLLs.
        If game imports WINMM.dll, winmm.dll is prioritized.
        If game imports VERSION.dll, version.dll is prioritized.
        """
        imported: List[str] = []
        if not exe_path or not os.path.exists(exe_path):
            return imported
        try:
            import pefile
            pe = pefile.PE(exe_path, fast_load=True)
            pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT']])
            for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
                dll_name = entry.dll.decode("utf-8", errors="ignore").lower()
                imported.append(dll_name)
        except Exception:
            try:
                with open(exe_path, "rb") as f:
                    bin_data = f.read(10 * 1024 * 1024)
                    for cand in ["winmm.dll", "version.dll", "dinput8.dll"]:
                        if cand.encode("utf-8") in bin_data.lower():
                            imported.append(cand)
            except Exception:
                pass
        return imported

    def _resolve_proxy_slot(
        self,
        game: GameInfo,
        is_coexisting_with_dlss5: bool,
        active_backend: Optional[BackendType] = None
    ) -> str:
        """
        Dynamically determine the optimal proxy DLL slot for the target game executable.
        - In standalone Mode C (OptiScaler without DLSS 5), dxgi.dll is the universal default.
        - In coexistence with DLSS 5 (or when dxgi.dll is occupied by DLSS 5 ReShade 6.8):
          Inspects the PE Import Table via _get_pe_imported_proxies(game.exe_path):
            1. If game imports 'winmm.dll': prioritize 'winmm.dll'!
            2. If game imports 'version.dll': use 'version.dll'!
            3. If game imports 'dinput8.dll': use 'dinput8.dll'!
            4. Fallback (if no proxy DLL found in import table, e.g. mock or packed binary):
               defaults to 'version.dll' (or 'winmm.dll' if version.dll is occupied by a foreign file).
        - For Mode A (dashdogy):
          Inspects PE Import Table: if game imports winmm.dll and not version.dll, uses winmm.dll;
          if game imports version.dll, uses version.dll; else defaults to version.dll.
        - For Mode D (DLSSG-SM86):
          If coexisting with DLSS 5, follows the same imported proxy rule.
        """
        if active_backend == BackendType.RESHADE_ADDON:
            return "dxgi.dll"

        if not is_coexisting_with_dlss5:
            if active_backend == BackendType.OPTISCALER_FSR:
                return "dxgi.dll"
            imported = self._get_pe_imported_proxies(game.exe_path)
            if "winmm.dll" in imported and "version.dll" not in imported:
                return "winmm.dll"
            if "version.dll" in imported:
                return "version.dll"
            if "dinput8.dll" in imported:
                return "dinput8.dll"
            return "version.dll"

        # Under DLSS 5 coexistence: dxgi.dll is strictly reserved for ReShade 6.8.
        # The shared coexistence router picks the slot the game imports first
        # (winmm.dll > version.dll > dinput8.dll > wininet.dll), and never returns
        # dxgi.dll, so both orders of injection converge to the same layout.
        try:
            from core.coexistence import pick_fg_proxy_slot
            return pick_fg_proxy_slot(game.target_dir, game.exe_path)
        except Exception:
            pass
        imported = self._get_pe_imported_proxies(game.exe_path)
        if "winmm.dll" in imported:
            return "winmm.dll"
        if "version.dll" in imported:
            return "version.dll"
        if "dinput8.dll" in imported:
            return "dinput8.dll"

        # Fallback when import table does not list known proxies (e.g. mock tests or dynamic load)
        target_dir = game.target_dir
        ver_path = os.path.join(target_dir, "version.dll")
        if os.path.exists(ver_path) and not (self._is_optiscaler_dll(ver_path) or self._is_dashdogy_dll(ver_path)):
            return "winmm.dll"
        return "version.dll"

    def _is_reshade_dll(self, path: str) -> bool:
        """Check if a DLL file is ReShade (excludes OptiScaler)."""
        data = self._read_dll_signature_bytes(path)
        if b"OptiScaler" in data:
            return False
        return b"ReShade" in data or b"crosire" in data

    def _is_reshade_addon_dll(self, path: str) -> bool:
        """Check if a DLL file is ReShade with full Add-on Support (contains AddonUninit / export hooks)."""
        data = self._read_dll_signature_bytes(path)
        if b"OptiScaler" in data:
            return False
        return (b"ReShade" in data or b"crosire" in data) and (
            b"AddonUninit" in data or b"reshade_addon" in data or len(data) >= 5 * 1024 * 1024
        )

    def _is_optiscaler_dll(self, path: str) -> bool:
        """Check if a DLL file is OptiScaler."""
        data = self._read_dll_signature_bytes(path)
        return b"OptiScaler" in data or b"libxess" in data

    def detect_injected_mode(self, target_dir: str) -> Optional[str]:
        """
        Detect currently injected backend mode ('dashdogy'/'mavismmg'/'optiscaler') from target directory files or manifest.
        """
        if not target_dir or not os.path.exists(target_dir):
            return None
        manifest_p = os.path.join(target_dir, ".mfg_patch_manifest.json")
        if os.path.exists(manifest_p):
            try:
                with open(manifest_p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    backend = data.get("active_backend")
                    if backend:
                        return backend
            except Exception:
                pass

        td = Path(target_dir)
        if (td / "dlssg_sm86.ini").exists() or (td / "dlssg_sm86").exists():
            return BackendType.DLSSG_SM86.value
        if (td / "OptiScaler.ini").exists() or (td / "nvngx.ini").exists():
            return BackendType.OPTISCALER_FSR.value
        if (td / "renodx-mfgunlock.addon64").exists():
            return BackendType.RESHADE_ADDON.value
        if (td / "RTXMFG-UI.ini").exists() or (td / "mfg_unlocker.ini").exists() or (td / "bink2w64Hooked.dll").exists():
            return BackendType.STANDALONE.value
        for p in ["version.dll", "winmm.dll", "dinput8.dll"]:
            if (td / p).exists():
                return BackendType.STANDALONE.value
        return None

    def verify_mode_b_integrity(self, target_dir: str) -> Tuple[bool, str, dict]:
        """
        Verify Mode B (ReShade framework + RenoDX addon) dual-injection integrity.
        Conditions:
        1. dxgi.dll exists and is confirmed as ReShade64 with Add-on support
        2. renodx-mfgunlock.addon64 exists
        3. ReShade.ini exists and [RenoDX.MFGUnlock] (or mirror) section is configured
        """
        if not target_dir or not os.path.exists(target_dir):
            return False, "目标目录不存在", {"has_dxgi": False, "has_addon": False, "has_ini": False}

        dxgi_path = os.path.join(target_dir, "dxgi.dll")
        addon_path = os.path.join(target_dir, "renodx-mfgunlock.addon64")
        ini_path = os.path.join(target_dir, "ReShade.ini")

        has_dxgi = os.path.exists(dxgi_path) and self._is_reshade_addon_dll(dxgi_path)
        has_addon = os.path.exists(addon_path)
        has_ini = False

        if os.path.exists(ini_path):
            try:
                from core.ini_sync import IniConfigManager
                b_cfg = IniConfigManager.read_mode_b_reverse(target_dir)
                if b_cfg and len(b_cfg) > 0:
                    has_ini = True
            except Exception:
                has_ini = False

        status = {
            "has_dxgi": has_dxgi,
            "has_addon": has_addon,
            "has_ini": has_ini
        }

        if has_dxgi and has_addon and has_ini:
            return True, "🟢 已激活 (ReShade 框架 + 插件双就绪 · 按 Home 调校)", status
        elif has_addon and not has_dxgi:
            return False, "⚠️ 缺失 ReShade 宿主底座 (dxgi.dll)，已触发自检补齐", status
        elif has_dxgi and not has_addon:
            return False, "⚠️ 已装 ReShade 底座，但缺失 renodx-mfgunlock.addon64 插件", status
        else:
            return False, "未完整激活模式 B 插件框架", status

    def auto_heal_mode_b(self, target_dir: str) -> Tuple[bool, str]:
        """
        Auto-heal: If renodx-mfgunlock.addon64 exists but dxgi.dll is missing or not ReShade addon,
        auto-copy ReShade64.dll to dxgi.dll and sync ReShade.ini.
        """
        if not target_dir or not os.path.exists(target_dir):
            return False, "目标目录不存在"

        addon_path = os.path.join(target_dir, "renodx-mfgunlock.addon64")
        if not os.path.exists(addon_path):
            return False, "未发现 Mode B 插件"

        dxgi_path = os.path.join(target_dir, "dxgi.dll")
        needs_dxgi = (not os.path.exists(dxgi_path)) or (not self._is_reshade_addon_dll(dxgi_path))

        healed = False
        if needs_dxgi:
            reshade_dll = self.updater.get_reshade_framework_dll()
            if reshade_dll and os.path.exists(reshade_dll):
                try:
                    if os.path.exists(dxgi_path) and not self._is_optiscaler_dll(dxgi_path):
                        bak = os.path.join(target_dir, "dxgi.dll.bak")
                        safe_force_remove(bak)
                        try:
                            os.rename(dxgi_path, bak)
                        except Exception:
                            pass
                            pass
                    shutil.copy2(reshade_dll, dxgi_path)
                    healed = True
                except Exception:
                    pass

        try:
            from core.ini_sync import IniConfigManager
            from core.optiscaler_config import load_reshade_preset
            b_cfg = IniConfigManager.read_mode_b_reverse(target_dir)
            if not b_cfg:
                IniConfigManager.sync_mode_b_forward(target_dir, load_reshade_preset())
                healed = True
        except Exception:
            pass

        if healed:
            return True, "已自动补全并修复 ReShade64 底座与配置"
        return False, "无需修复或修复未执行"

    def _apply_reshade_addon_patch(self, game: GameInfo, manifest: PatchManifest) -> Tuple[bool, str]:
        """
        Execute Mode B transactional deployment:
        Step 1: dxgi.dll conflict detection and migration
        Step 2: Physical injection of ReShade framework (ReShade64.dll -> dxgi.dll)
        Step 3: Physical injection of renodx-mfgunlock.addon64 and streamline dependencies
        Step 4: Synchronous write and lock of ReShade.ini early loading & exact keys
        """
        source_addon = self.updater.get_latest_cached_file(BackendType.RESHADE_ADDON)
        if not source_addon or not os.path.exists(source_addon):
            return False, "本地缓存中未找到 mavismmg/renodx-mfgunlock.addon64 组件！\n请先在主界面点击【检查并同步最新版本】进行下载。"

        source_reshade = self.updater.get_reshade_framework_dll()
        if not source_reshade or not os.path.exists(source_reshade):
            return False, "本地缓存及内置资源中未找到 ReShade64.dll 核心框架 (Full Add-on Support)！\n请检查 assets/reshade 或本地 RHI 缓存。"

        target_dir = game.target_dir
        kill_locking_processes(target_dir, game.exe_name)
        cleanup_pending_files(target_dir)

        # Purge Mode C conflicting bridge files
        for mode_c_file in ["OptiScaler.ini", "nvngx.ini", "dlssg_to_fsr3_amd_is_better.dll", "fakenvapi.dll", "fakenvapi.ini"]:
            f_p = os.path.join(target_dir, mode_c_file)
            if os.path.exists(f_p):
                safe_force_remove(f_p)

        # Also purge any leftover OptiScaler proxies that would collide with ReShade
        for proxy_cand in ["winmm.dll", "version.dll", "dinput8.dll", "wininet.dll"]:
            p_p = os.path.join(target_dir, proxy_cand)
            if os.path.exists(p_p) and self._is_optiscaler_dll(p_p):
                safe_force_remove(p_p)

        existing_files = {f.lower() for f in os.listdir(target_dir)}
        dxgi_path = os.path.join(target_dir, "dxgi.dll")

        # Step 1: dxgi.dll conflict detection and migration
        has_dlss5 = is_dlss5_present(target_dir)
        need_deploy_reshade = True
        if has_dlss5:
            # DLSS 5 Coexistence: Directly reuse DLSS 5's ReShade 6.8 dxgi.dll!
            if "dxgi.dll" in existing_files and self._is_reshade_dll(dxgi_path):
                need_deploy_reshade = False
            else:
                dlss5_dxgi = ROOT_DIR / "apps" / "app6_dlss5" / "assets" / "dxgi.dll"
                if dlss5_dxgi.exists():
                    source_reshade = str(dlss5_dxgi)
                need_deploy_reshade = True
        else:
            if "dxgi.dll" in existing_files:
                if self._is_optiscaler_dll(dxgi_path):
                    bak_path = os.path.join(target_dir, "dxgi.dll.opti_bak")
                    safe_force_remove(bak_path)
                    try:
                        os.rename(dxgi_path, bak_path)
                        manifest.renamed_backups.append({"original": "dxgi.dll", "backup": "dxgi.dll.opti_bak"})
                        existing_files.discard("dxgi.dll")
                    except Exception:
                        pass
                    need_deploy_reshade = True
                elif self._is_reshade_addon_dll(dxgi_path):
                    need_deploy_reshade = False
                elif self._is_reshade_dll(dxgi_path):
                    bak_path = os.path.join(target_dir, "dxgi.dll.bak")
                    safe_force_remove(bak_path)
                    try:
                        os.rename(dxgi_path, bak_path)
                        manifest.renamed_backups.append({"original": "dxgi.dll", "backup": "dxgi.dll.bak"})
                        existing_files.discard("dxgi.dll")
                    except Exception:
                        pass
                    need_deploy_reshade = True
                else:
                    bak_path = os.path.join(target_dir, "dxgi.dll.mfg_bak")
                    safe_force_remove(bak_path)
                    try:
                        os.rename(dxgi_path, bak_path)
                        manifest.renamed_backups.append({"original": "dxgi.dll", "backup": "dxgi.dll.mfg_bak"})
                        existing_files.discard("dxgi.dll")
                    except Exception:
                        pass
                    need_deploy_reshade = True

        # Step 2: Physical injection of ReShade framework (dxgi.dll)
        if need_deploy_reshade:
            shutil.copy2(source_reshade, dxgi_path)
            if not has_dlss5:
                manifest.created_files.append("dxgi.dll")

        # Step 3: Physical injection of renodx-mfgunlock.addon64
        dest_addon = os.path.join(target_dir, "renodx-mfgunlock.addon64")
        shutil.copy2(source_addon, dest_addon)
        manifest.created_files.append("renodx-mfgunlock.addon64")

        # Step 4: Synchronous write and lock of ReShade.ini early loading & exact keys
        try:
            from core.ini_sync import IniConfigManager
            from core.optiscaler_config import load_reshade_preset, get_reshade_preset_summary
            r_cfg = load_reshade_preset()
            IniConfigManager.sync_mode_b_forward(target_dir, r_cfg)
            summary_str = get_reshade_preset_summary(r_cfg)
            manifest.ini_modifications.append({
                "file": "ReShade.ini",
                "section": "RenoDX.MFGUnlock",
                "key": "Summary",
                "value_added": summary_str
            })
        except Exception:
            ini_path = os.path.join(target_dir, "ReShade.ini")
            addon_name = "renodx-mfgunlock.addon64"
            added_to_ini = self._ensure_ini_early_loading(ini_path, addon_name)
            if added_to_ini:
                manifest.ini_modifications.append({
                    "file": "ReShade.ini",
                    "section": "ADDON",
                    "key": "LoadFromDllMain",
                    "value_added": addon_name
                })

        return True, ""

    def _apply_optiscaler_patch(self, game: GameInfo, manifest: PatchManifest) -> Tuple[bool, str]:
        opti_dir = self.updater.get_latest_cached_dir(BackendType.OPTISCALER_FSR)
        if not opti_dir or not os.path.exists(opti_dir):
            return False, "本地缓存中未找到 OptiScaler / FSR 3.1 桥接组件！\n请先在主界面点击【检查并同步最新版本】进行下载。"

        source_dll = os.path.join(opti_dir, "OptiScaler.dll")
        if not os.path.exists(source_dll):
            return False, f"OptiScaler 缓存目录中缺少核心 OptiScaler.dll 文件！({opti_dir})"

        target_dir = game.target_dir
        kill_locking_processes(target_dir, game.exe_name)
        cleanup_pending_files(target_dir)

        # Mutual exclusivity cleanup:
        # Purge Mode B ReShade addon and any old OptiScaler secondary proxies to avoid dual-hook crashes
        dest_addon = os.path.join(target_dir, "renodx-mfgunlock.addon64")
        if os.path.exists(dest_addon):
            safe_force_remove(dest_addon)

        has_dlss5 = is_dlss5_present(target_dir)
        selected_proxy = self._resolve_proxy_slot(game, is_coexisting_with_dlss5=has_dlss5, active_backend=BackendType.OPTISCALER_FSR)

        for proxy_cand in ["dxgi.dll", "winmm.dll", "version.dll", "dinput8.dll", "wininet.dll"]:
            if proxy_cand == selected_proxy:
                continue
            p_path = os.path.join(target_dir, proxy_cand)
            if os.path.exists(p_path):
                if proxy_cand == "dxgi.dll" and self._is_reshade_dll(p_path):
                    continue
                if self._is_optiscaler_dll(p_path) or self._is_dashdogy_dll(p_path):
                    safe_force_remove(p_path)

        for mode_a_file in ["RTX40MFG-UI.ini", "RTXMFG-UI.ini", "mfg_unlocker.ini", "RTX40MFG-UI-layout.ini"]:
            f_p = os.path.join(target_dir, mode_a_file)
            if os.path.exists(f_p):
                safe_force_remove(f_p)

        if not has_dlss5:
            # Standalone OptiScaler: back up ReShade dxgi.dll if present
            dxgi_path = os.path.join(target_dir, "dxgi.dll")
            if os.path.exists(dxgi_path):
                if self._is_reshade_dll(dxgi_path):
                    bak_path = os.path.join(target_dir, "dxgi.dll.reshade_bak")
                    safe_force_remove(bak_path)
                    try:
                        os.rename(dxgi_path, bak_path)
                        manifest.renamed_backups.append({"original": "dxgi.dll", "backup": "dxgi.dll.reshade_bak"})
                    except Exception:
                        pass

        existing_files = {f.lower() for f in os.listdir(target_dir)}
        if has_dlss5:
            # Step 1: Dynamic Slot Routing for OptiScaler with DLSS 5 Coexistence
            # Rule 1: Lock dxgi.dll to DLSS 5 ReShade 6.8 (5.33 MB)
            dxgi_path = os.path.join(target_dir, "dxgi.dll")
            if not os.path.exists(dxgi_path) or not self._is_reshade_dll(dxgi_path):
                dlss5_dxgi = ROOT_DIR / "apps" / "app6_dlss5" / "assets" / "dxgi.dll"
                reshade_src = str(dlss5_dxgi) if dlss5_dxgi.exists() else self.updater.get_reshade_framework_dll()
                if reshade_src and os.path.exists(reshade_src):
                    safe_force_remove(dxgi_path)
                    shutil.copy2(reshade_src, dxgi_path)

            dest_proxy_path = os.path.join(target_dir, selected_proxy)
            if os.path.exists(dest_proxy_path):
                safe_force_remove(dest_proxy_path)
            shutil.copy2(source_dll, dest_proxy_path)
            manifest.created_files.append(selected_proxy)

            # Purge any secondary ReShade64 / d3d12-ReShade64 / dxgi.dll.reshade_bak
            # because ReShade 6.8 is already loaded natively as dxgi.dll!
            for r_cand in ["ReShade64.dll", "d3d12-ReShade64.dll", "dxgi.dll.reshade_bak"]:
                rp = os.path.join(target_dir, r_cand)
                if os.path.exists(rp):
                    safe_force_remove(rp)
        else:
            # Standalone OptiScaler (without DLSS 5): dxgi.dll (or resolved slot)
            dest_proxy_path = os.path.join(target_dir, selected_proxy)
            if os.path.exists(dest_proxy_path):
                safe_force_remove(dest_proxy_path)
            shutil.copy2(source_dll, dest_proxy_path)
            manifest.created_files.append(selected_proxy)

        # 2. Deploy bridge & runtime files
        gpu_name = get_system_gpu_name()
        has_rtx_40_or_newer = is_rtx_40_or_newer(gpu_name)
        is_qualified = (game.qualification == QualificationStatus.QUALIFIED)

        # Load the Mode C preset before copying: the selected FG output decides whether
        # fakenvapi is mandatory. OptiScaler's own template states:
        #   xefg   - requires libxess_fg.dll, libxell.dll and latest fakenvapi dll
        #   nukems - requires dlssg_to_fsr3_amd_is_better.dll (+ fakenvapi on AMD/Intel)
        # The real 4K session log proved it: without fakenvapi.dll the XeFG chain logs
        # "fakenvapi::Init Failed" / "Can't find fakenvapi.dll" and never produces frames.
        try:
            from core.optiscaler_config import load_optiscaler_preset
            preset = load_optiscaler_preset()
        except Exception:
            preset = {}

        fg_output = str(preset.get("fg_output", "xefg")).strip().lower()
        needs_fakenvapi = fg_output in ("xefg", "nukems")

        # fakenvapi is side-loaded by OptiScaler by file name (it is NOT installed as
        # nvapi64.dll), so it does not replace the driver NVAPI that Streamline uses.
        # It is only purged when the selected output does not need it and the GPU/game
        # already provides native DLSS-G.
        deploy_fakenvapi = needs_fakenvapi or not (has_rtx_40_or_newer or is_qualified)

        # Fatal conflict fix: fakenvapi emulates a whole NVAPI device, and the
        # DLSS 5 neural-reconstruction runtime queries NVAPI to pick its kernels.
        # A faked adapter makes it run kernels the physical GPU cannot execute,
        # which crashes right after the first reconstructed frame. This is true on
        # every GPU architecture, not only on RTX 40/50, so coexistence always
        # purges it and relies on the game's native DLSS-G as XeFG input.
        if has_dlss5:
            deploy_fakenvapi = False
            try:
                from core.coexistence import purge_fakenvapi
                purge_fakenvapi(target_dir)
            except Exception:
                pass

        items_to_copy = [
            "OptiScaler.ini",
            "amd_fidelityfx_dx12.dll",
            "amd_fidelityfx_framegeneration_dx12.dll",
            "amd_fidelityfx_upscaler_dx12.dll",
            "amd_fidelityfx_vk.dll",
            "libxell.dll",
            "libxess.dll",
            "libxess_dx11.dll",
            "libxess_fg.dll",
        ]
        if deploy_fakenvapi:
            items_to_copy.extend(["fakenvapi.dll", "fakenvapi.ini"])
        else:
            # Purge any leftover fakenvapi to prevent Streamline and Messiah engine crashes,
            # and prevent RenoDX DLSS 5 NVAPI query conflicts on RTX 40+ GPUs
            for f_name in ["fakenvapi.dll", "fakenvapi.ini", "fakenvapi.log"]:
                f_p = os.path.join(target_dir, f_name)
                if os.path.exists(f_p):
                    safe_force_remove(f_p)

        for item in items_to_copy:
            src_item = os.path.join(opti_dir, item)
            if not os.path.exists(src_item):
                src_item = os.path.join(opti_dir, "OptiScaler", item)
            if not os.path.exists(src_item):
                continue
            dst_item = os.path.join(target_dir, item)
            if os.path.exists(dst_item):
                # Backup existing file
                bak_name = item + ".mfg_bak"
                bak_path = os.path.join(target_dir, bak_name)
                safe_force_remove(bak_path)
                try:
                    os.rename(dst_item, bak_path)
                    manifest.renamed_backups.append({"original": item, "backup": bak_name})
                except Exception:
                    pass
            shutil.copy2(src_item, dst_item)
            manifest.created_files.append(item)

        # 3. Deploy OptiScaler subdirectory (OptiScaler 10+ backend libraries) if exists
        opti_sub = os.path.join(opti_dir, "OptiScaler")
        if os.path.exists(opti_sub) and os.path.isdir(opti_sub):
            dst_opti_sub = os.path.join(target_dir, "OptiScaler")
            if not os.path.exists(dst_opti_sub):
                shutil.copytree(opti_sub, dst_opti_sub)
                manifest.created_files.append("OptiScaler")
            else:
                for root, dirs, files in os.walk(opti_sub):
                    rel_path = os.path.relpath(root, opti_sub)
                    dest_path = os.path.join(dst_opti_sub, rel_path)
                    os.makedirs(dest_path, exist_ok=True)
                    for file in files:
                        shutil.copy2(os.path.join(root, file), os.path.join(dest_path, file))

        # 3.1 Deploy D3D12_Optiscaler directory if exists (legacy 0.9.x structure)
        d3d12_dir = os.path.join(opti_dir, "D3D12_Optiscaler")
        if os.path.exists(d3d12_dir) and os.path.isdir(d3d12_dir):
            dst_d3d12 = os.path.join(target_dir, "D3D12_Optiscaler")
            if not os.path.exists(dst_d3d12):
                shutil.copytree(d3d12_dir, dst_d3d12)
                manifest.created_files.append("D3D12_Optiscaler")

        # 3.4. Conditionally handle dlssg_to_fsr3
        if fg_output == "nukems":
            items_to_copy.append("dlssg_to_fsr3_amd_is_better.dll")
        else:
            # Purge lingering dlssg_to_fsr3_amd_is_better.dll to prevent conflicting FG stacks
            lingering_dlssg = os.path.join(target_dir, "dlssg_to_fsr3_amd_is_better.dll")
            if os.path.exists(lingering_dlssg):
                safe_force_remove(lingering_dlssg)

        # 3.5. Deploy dashdogy MFGUnlocker as an ASI plugin in OptiScaler/plugins/
        # OptiScaler 10+ loads ASI plugins via LoadAsiPlugins=true; dashdogy's
        # Universal MFG Unlocker (v1.5+) patches the XeSS-FG interpolation ceiling,
        # which is what actually enables 3X/4X XeFG. libxess_fg alone caps non-Arc
        # GPUs at "Max supported interpolations = 1" (2X), as the real session log
        # in issue #v1.3.8 shows.
        has_dlss5 = is_dlss5_present(target_dir)
        plugins_dir = os.path.join(target_dir, "OptiScaler", "plugins")
        dst_asi = os.path.join(plugins_dir, "MFGUnlocker.asi")
        unlock_mfg = bool(preset.get("unlock_mfg", True)) if isinstance(preset, dict) else True
        mfg_dll_path = self.updater.get_latest_cached_file(BackendType.STANDALONE)

        if unlock_mfg and mfg_dll_path and os.path.exists(mfg_dll_path):
            os.makedirs(plugins_dir, exist_ok=True)
            # Remove a stale late-load copy so only one injection path exists.
            _late = os.path.join(plugins_dir, "MFGUnlocker-loadlate.asi")
            if os.path.exists(_late):
                safe_force_remove(_late)
            shutil.copy2(mfg_dll_path, dst_asi)
            if "OptiScaler/plugins/MFGUnlocker.asi" not in manifest.created_files:
                manifest.created_files.append("OptiScaler/plugins/MFGUnlocker.asi")
        else:
            # Unlock disabled (or component missing): remove every ASI variant so a
            # stale unlocker can never hook the process behind the user's back.
            for _asi_name in ["MFGUnlocker.asi", "MFGUnlocker-loadlate.asi"]:
                _asi_path = os.path.join(plugins_dir, _asi_name)
                if os.path.exists(_asi_path):
                    try:
                        safe_force_remove(_asi_path)
                    except Exception:
                        pass

        if has_dlss5:
            # Purge d3d12-ReShade64.dll: OptiScaler accepts both "ReShade64.dll" and
            # "d3d12-ReShade64.dll" as chain-load targets. If both exist simultaneously,
            # two ReShade instances initialize and register duplicate D3D12 hooks -> crash.
            _d3d12_reshade = os.path.join(target_dir, "d3d12-ReShade64.dll")
            if os.path.exists(_d3d12_reshade):
                try:
                    safe_force_remove(_d3d12_reshade)
                except Exception:
                    pass

        # 4. Write the ONE legal config file (OptiScaler.ini) and delete the legacy alias.
        #    v0.9.4 shows a red banner while nvngx.ini exists, and reads FG init keys at
        #    D3D12 init, so everything must be on disk before the next launch.
        try:
            from core.ini_sync import IniConfigManager
            from core.optiscaler_config import load_optiscaler_preset, get_preset_summary
            if not preset:
                preset = load_optiscaler_preset()
            IniConfigManager.purge_legacy_nvngx_ini(target_dir)
            IniConfigManager.sync_mode_c_forward(target_dir, preset, exe_name=game.exe_name)
            report = IniConfigManager.last_report or {}
            if report.get("nvngx_ini_removed"):
                manifest.ini_modifications.append({
                    "file": "nvngx.ini",
                    "section": "-",
                    "key": "deleted",
                    "value_added": "legacy config removed"
                })
            if report.get("menu_scale"):
                manifest.ini_modifications.append({
                    "file": "OptiScaler.ini",
                    "section": "Menu",
                    "key": "Scale",
                    "value_added": report["menu_scale"]
                })
            if report.get("interpolation_count") is not None:
                manifest.ini_modifications.append({
                    "file": "OptiScaler.ini",
                    "section": "XeFG",
                    "key": "InterpolationCount",
                    "value_added": str(report["interpolation_count"])
                })
            # Report what is actually active, not the requested (possibly clamped) value
            display_preset = dict(preset)
            if report.get("interpolation_count") is not None:
                display_preset["interpolation_count"] = report["interpolation_count"]
            if report.get("menu_scale") is not None:
                display_preset["menu_scale"] = float(report["menu_scale"])
            summary_str = get_preset_summary(display_preset)
            manifest.ini_modifications.append({
                "file": "OptiScaler.ini",
                "section": "PresetConfig",
                "key": "Summary",
                "value_added": summary_str
            })
        except Exception:
            pass

        return True, ""

    def _ensure_ini_early_loading(self, ini_path: str, addon_name: str) -> bool:
        """
        Inject or append addon_name to [ADDON] LoadFromDllMain in ReShade.ini.
        NOTE: DLSS 5 (renodx-dlss) must NEVER be loaded in DllMain because of Windows loader lock (causes error 1114/0xc0000005).
        Only Mode B (renodx-mfgunlock.addon64) uses early loading.
        """
        if "dlss" in addon_name.lower() or "shortfuse" in addon_name.lower():
            return True

        lines = []
        if os.path.exists(ini_path):
            try:
                with open(ini_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
            except Exception:
                lines = []

        in_addon_sec = False
        addon_sec_found = False
        load_key_found = False
        modified = False
        new_lines = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                sec_name = stripped[1:-1].strip()
                if in_addon_sec and not load_key_found:
                    new_lines.append(f"LoadFromDllMain={addon_name}\n")
                    load_key_found = True
                    modified = True

                in_addon_sec = (sec_name.upper() == "ADDON")
                if in_addon_sec:
                    addon_sec_found = True
                new_lines.append(line)
                continue

            if in_addon_sec and "=" in stripped:
                k, v = stripped.split("=", 1)
                if k.strip().upper() == "LOADFROMDLLMAIN":
                    load_key_found = True
                    raw_addons = [x.strip() for x in v.split(",") if x.strip()]
                    clean_addons = [
                        x for x in raw_addons 
                        if x != "1" and "dlss" not in x.lower() and "shortfuse" not in x.lower()
                    ]
                    if addon_name.lower() not in [x.lower() for x in clean_addons]:
                        clean_addons.append(addon_name)
                    new_lines.append(f"{k.strip()}={','.join(clean_addons)}\n")
                    modified = True
                    continue

            new_lines.append(line)

        if not addon_sec_found:
            new_lines.append("\n[ADDON]\n")
            new_lines.append(f"LoadFromDllMain={addon_name}\n")
            modified = True
        elif not load_key_found:
            new_lines.append(f"LoadFromDllMain={addon_name}\n")
            modified = True

        if modified:
            with open(ini_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            return True

        return False

    def _apply_dlssg_sm86_patch(self, game: GameInfo, manifest: PatchManifest) -> Tuple[bool, str]:
        """
        Deploy Mode D (DLSSG for SM86/SM75 Native DLSS-G & INT8 Super Resolution)
        1. Clean conflicting Mode A, B, C files
        2. Deploy selected proxy DLL (default: version.dll)
        3. Deploy dlssg_sm86 folder (runtime, backend, kernels, sr, xefg)
        4. Deploy and forward sync dlssg_sm86.ini
        5. DLSS 5 coexistence: ensure ReShade is deployed on dxgi.dll if DLSS 5 present
        """
        source_dir = self.updater.get_latest_cached_dir(BackendType.DLSSG_SM86)
        if not source_dir or not os.path.exists(source_dir):
            return False, "本地缓存中未找到 DLSSG-SM86 组件！\n请先在主界面点击【检查并同步最新版本】进行下载。"

        target_dir = game.target_dir
        kill_locking_processes(target_dir, game.exe_name)
        cleanup_pending_files(target_dir)

        # 1. Clean conflicting Mode A, B, C files
        for conflicting_file in [
            "OptiScaler.ini", "nvngx.ini", "dlssg_to_fsr3_amd_is_better.dll",
            "fakenvapi.dll", "fakenvapi.ini", "renodx-mfgunlock.addon64",
            "RTX40MFG-UI.ini", "RTXMFG-UI.ini", "mfg_unlocker.ini", "RTXMFG-Universal.json"
        ]:
            f_p = os.path.join(target_dir, conflicting_file)
            if os.path.exists(f_p):
                safe_force_remove(f_p)

        has_dlss5 = is_dlss5_present(target_dir)

        # 2. Load Mode D preset to check preferred proxy DLL
        try:
            from core.optiscaler_config import load_dlssg_sm86_preset
            preset_d = load_dlssg_sm86_preset()
        except Exception:
            preset_d = {"proxy_dll": "version.dll"}

        selected_proxy = self._resolve_proxy_slot(game, is_coexisting_with_dlss5=has_dlss5, active_backend=BackendType.DLSSG_SM86)
        pref = str(preset_d.get("proxy_dll", "")).strip().lower()
        if pref and pref.endswith(".dll") and not (has_dlss5 and pref == "dxgi.dll"):
            imported = self._get_pe_imported_proxies(game.exe_path)
            if not imported or pref in imported:
                selected_proxy = pref

        # Locate proxy source file
        source_proxy = os.path.join(source_dir, selected_proxy)
        if not os.path.exists(source_proxy):
            # Check alternatives folder
            alt_path = os.path.join(source_dir, "alternatives", selected_proxy)
            if os.path.exists(alt_path):
                source_proxy = alt_path
            else:
                source_proxy = os.path.join(source_dir, "version.dll")

        if not os.path.exists(source_proxy):
            return False, f"DLSSG-SM86 资源目录中缺少代理文件 {selected_proxy} 或 version.dll！"

        dest_proxy_path = os.path.join(target_dir, selected_proxy)
        if os.path.exists(dest_proxy_path):
            safe_force_remove(dest_proxy_path)
        shutil.copy2(source_proxy, dest_proxy_path)
        manifest.created_files.append(selected_proxy)

        # 3. Deploy dlssg_sm86 directory (runtime, backend, kernels, sr, xefg)
        src_dlssg_sub = os.path.join(source_dir, "dlssg_sm86")
        if not os.path.exists(src_dlssg_sub):
            src_dlssg_sub = source_dir

        dst_dlssg_sub = os.path.join(target_dir, "dlssg_sm86")
        os.makedirs(dst_dlssg_sub, exist_ok=True)
        if "dlssg_sm86" not in manifest.created_files:
            manifest.created_files.append("dlssg_sm86")

        for root, dirs, files in os.walk(src_dlssg_sub):
            rel = os.path.relpath(root, src_dlssg_sub)
            if rel == ".":
                dest_root = dst_dlssg_sub
            else:
                dest_root = os.path.join(dst_dlssg_sub, rel)
            os.makedirs(dest_root, exist_ok=True)
            for file in files:
                if file.lower() == "nvngx_dlssnr.dll":
                    continue
                src_f = os.path.join(root, file)
                dst_f = os.path.join(dest_root, file)
                shutil.copy2(src_f, dst_f)

        # 4. Deploy and forward sync dlssg_sm86.ini
        src_ini = os.path.join(source_dir, "dlssg_sm86.ini")
        dst_ini = os.path.join(target_dir, "dlssg_sm86.ini")
        if os.path.exists(src_ini) and not os.path.exists(dst_ini):
            shutil.copy2(src_ini, dst_ini)
        if "dlssg_sm86.ini" not in manifest.created_files:
            manifest.created_files.append("dlssg_sm86.ini")

        try:
            from core.ini_sync import IniConfigManager
            IniConfigManager.sync_mode_d_forward(target_dir, preset_d, game.exe_name)
        except Exception:
            pass

        # 5. DLSS 5 Coexistence: ensure ReShade is deployed on dxgi.dll if DLSS 5 present
        if has_dlss5:
            dxgi_path = os.path.join(target_dir, "dxgi.dll")
            if not os.path.exists(dxgi_path) or not self._is_reshade_dll(dxgi_path):
                dlss5_dxgi = ROOT_DIR / "apps" / "app6_dlss5" / "assets" / "dxgi.dll"
                reshade_src = str(dlss5_dxgi) if dlss5_dxgi.exists() else self.updater.get_reshade_framework_dll()
                if reshade_src and os.path.exists(reshade_src):
                    safe_force_remove(dxgi_path)
                    shutil.copy2(reshade_src, dxgi_path)
            safe_force_remove(os.path.join(target_dir, "ReShade64.dll"))

        return True, ""
