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
        # 0. Auto-heal any accidentally missing game native dependencies
        try:
            from core.utils import auto_heal_game_dependencies
            auto_heal_game_dependencies(game.target_dir)
        except Exception:
            pass

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
        if active_backend in (None, BackendType.SMART_AUTO):
            gpu_name = get_system_gpu_name()
            from core.utils import is_rtx_20_or_30_series, is_rtx_40_or_newer
            if is_rtx_20_or_30_series(gpu_name):
                # RTX 20/30 (Turing/Ampere) -> Mode C: dlssg_for_sm86 is the #1 FIRST CHOICE!
                active_backend = BackendType.DLSSG_SM86
            elif is_rtx_40_or_newer(gpu_name):
                # RTX 40/50 series -> Mode A (dashdogy Universal)
                active_backend = BackendType.STANDALONE
            else:
                # AMD / Intel / GTX series -> Mode B (OptiScaler 跨架构转译)
                active_backend = BackendType.OPTISCALER_FSR

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
            elif active_backend == BackendType.OPTISCALER_FSR or backend_str == BackendType.OPTISCALER_FSR.value:
                target_mode_char = "B"
            elif active_backend == BackendType.RESHADE_ADDON or backend_str == BackendType.RESHADE_ADDON.value:
                target_mode_char = "B"
            elif active_backend == BackendType.DLSSG_SM86 or backend_str == BackendType.DLSSG_SM86.value:
                target_mode_char = "C"
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
                            f"✨ 模式 B (OptiScaler) 已作为后台静默帧生成平稳运行（无悬浮窗干扰）\n"
                            f"✨ 在游戏画质设置中直接开启【DLSS 帧生成】即刻生效！\n"
                            f"✨ 已自动注入模式 B 预设: {summary_str}{warn_text}"
                        )
                    else:
                        callout = (
                            f"在游戏设置中开启【DLSS 帧生成】即按预设生效！\n"
                            f"✨ 进游戏按【{key_name}】呼出 OptiScaler 调校菜单\n"
                            f"✨ 核心插帧代理已挂载至【{target_proxy}】\n"
                            f"✨ 已自动注入模式 B 预设: {summary_str}{warn_text}"
                        )
                except Exception:
                    callout = "在游戏画质设置中开启【DLSS 帧生成】(进游戏按【Insert】呼出 OptiScaler 菜单)"
                display_mode = "模式 B (OptiScaler 跨架构转译)"
            elif active_backend == BackendType.DLSSG_SM86 or backend_str == BackendType.DLSSG_SM86.value:
                try:
                    from core.optiscaler_config import load_dlssg_sm86_preset, get_dlssg_sm86_preset_summary
                    preset_c = load_dlssg_sm86_preset()
                    summary_c = get_dlssg_sm86_preset_summary(preset_c)
                    if has_dlss5:
                        callout = (
                            f"⚡ 检测到 DLSS 5 共存态：已启用全自动双通道无缝共存！\n"
                            f"✨ 核心插帧代理已安全挂载至【{target_proxy}】（避让 DLSS 5 ReShade 渲染底座 dxgi.dll）\n"
                            f"✨ 超分由 DLSS 5 神经网络全权重构，插帧由 dlssg_sm86 原生内核加速驱动，双剑合璧！\n"
                            f"✨ 在游戏画质设置中直接开启【DLSS 帧生成】即刻生效！\n"
                            f"✨ 已自动注入模式 C 预设: {summary_c}"
                        )
                    else:
                        callout = (
                            f"在游戏画质设置中直接开启【DLSS 帧生成】即刻生效！\n"
                            f"✨ 专为 RTX 20/30 系显卡深度定制，原生运行 DLSS-G 神经网络与专属加速内核\n"
                            f"✨ 核心插帧代理已安全挂载至【{target_proxy}】\n"
                            f"✨ 已自动注入模式 C 预设: {summary_c}"
                        )
                except Exception:
                    callout = "在游戏画质设置中开启【DLSS 帧生成】"
                display_mode = "模式 C (dlssg_for_sm86 原生插帧 · RTX 20/30 首选)"
            else:
                try:
                    from core.optiscaler_config import load_mode_a_preset, get_mode_a_preset_summary
                    from core.ini_sync import IniConfigManager
                    preset_a = load_mode_a_preset()
                    summary_a = get_mode_a_preset_summary(preset_a)
                    IniConfigManager.sync_mode_a_forward(game.target_dir, preset_a)
                    callout = (
                        f"在游戏画质设置中开启【DLSS 帧生成】即刻生效！\n"
                        f"✨ 进游戏按【Backspace】呼出 dashdogy 参数菜单\n"
                        f"✨ 核心插帧代理已挂载至【{target_proxy}】\n"
                        f"✨ 已自动写入模式 A 预设: {summary_a}"
                    )
                except Exception:
                    callout = "在游戏画质设置中开启【DLSS 帧生成】(进游戏按【Backspace】呼出菜单)"
                display_mode = "模式 A (dashdogy 原生多帧解锁器)"

            return True, f"游戏 '{game.name}' 修补成功！\n使用模式: {display_mode}\n{callout}"

        except Exception as e:
            # Atomic rollback on exception
            self.rollback_engine.rollback(game.target_dir, game.exe_name)
            return False, f"修补过程发生异常，已自动回滚: {e}"

    def _apply_standalone_patch(self, game: GameInfo, manifest: PatchManifest, prefer_bink_hook: bool = False) -> Tuple[bool, str]:
        source_dll = self.updater.get_latest_cached_file(BackendType.STANDALONE)
        if not source_dll or not os.path.exists(source_dll):
            return False, "本地缓存中未找到 dashdogy/MFG-Unlocker 组件！\n请先在主界面点击【检查并同步最新版本】进行下载。"

        target_dir = game.target_dir
        kill_locking_processes(target_dir, game.exe_name)
        cleanup_pending_files(target_dir)

        # Purge Mode B & C conflicting files and stale root XeSS runtime DLLs (Mode A runtimes live inside RTXMFG-XeSS/)
        for mode_bc_file in ["OptiScaler.ini", "nvngx.ini", "dlssg_to_fsr3_amd_is_better.dll", "fakenvapi.dll", "fakenvapi.ini", "renodx-mfgunlock.addon64", "dlssg_sm86.ini", "libxess_fg.dll", "libxell.dll"]:
            f_p = os.path.join(target_dir, mode_bc_file)
            if os.path.exists(f_p):
                safe_force_remove(f_p)
        dlssg_sm86_dir = os.path.join(target_dir, "dlssg_sm86")
        if os.path.exists(dlssg_sm86_dir):
            safe_force_remove(dlssg_sm86_dir)

        # Self-healing: restore any bink2w64Hooked.dll back to bink2w64.dll unconditionally
        hooked_bink = os.path.join(target_dir, "bink2w64Hooked.dll")
        orig_bink = os.path.join(target_dir, "bink2w64.dll")
        if os.path.exists(hooked_bink):
            try:
                if os.path.exists(orig_bink):
                    safe_force_remove(orig_bink)
                os.rename(hooked_bink, orig_bink)
            except Exception:
                pass

        # Load Mode A preset
        try:
            from core.optiscaler_config import load_mode_a_preset
            preset_a = load_mode_a_preset()
        except Exception:
            preset_a = {}

        has_dlss5 = is_dlss5_present(target_dir)

        # Resolve selected proxy slot according to official standard:
        # Standalone: dxgi.dll (or user configured / PE imported slot)
        # Coexistence with DLSS 5: version.dll (or winmm.dll), strictly leaving dxgi.dll to DLSS 5 ReShade 6.8
        configured_proxy = str(preset_a.get("proxy_dll", "auto")).lower().strip()
        if configured_proxy in ["dxgi.dll", "version.dll", "winmm.dll", "dinput8.dll"]:
            if has_dlss5 and configured_proxy == "dxgi.dll":
                selected_proxy = "version.dll"
            else:
                selected_proxy = configured_proxy
        else:
            selected_proxy = self._resolve_proxy_slot(game, is_coexisting_with_dlss5=has_dlss5, active_backend=BackendType.STANDALONE)

        # Clean old proxy candidates: strictly maintain only 1 proxy DLL slot for Mode A!
        all_proxies = ["dxgi.dll", "version.dll", "winmm.dll", "dinput8.dll", "wininet.dll"]
        for proxy_cand in all_proxies:
            if proxy_cand == selected_proxy:
                continue
            if proxy_cand == "dxgi.dll" and has_dlss5:
                continue
            p_p = os.path.join(target_dir, proxy_cand)
            if os.path.exists(p_p):
                if self._is_dashdogy_dll(p_p) or self._is_optiscaler_dll(p_p) or self._is_dlssg_sm86_dll(p_p) or (proxy_cand != "dxgi.dll" and self._is_reshade_dll(p_p)):
                    safe_force_remove(p_p)

        dest_proxy_path = os.path.join(target_dir, selected_proxy)
        if os.path.exists(dest_proxy_path):
            if not self._is_dashdogy_dll(dest_proxy_path) and not self._is_optiscaler_dll(dest_proxy_path) and not self._is_reshade_dll(dest_proxy_path) and not self._is_dlssg_sm86_dll(dest_proxy_path):
                dm_backup_dir = os.path.join(target_dir, ".dm_backup")
                os.makedirs(dm_backup_dir, exist_ok=True)
                dm_proxy_bak = os.path.join(dm_backup_dir, selected_proxy)
                if not os.path.exists(dm_proxy_bak):
                    try:
                        shutil.copy2(dest_proxy_path, dm_proxy_bak)
                    except Exception:
                        pass
            safe_force_remove(dest_proxy_path)
        shutil.copy2(source_dll, dest_proxy_path)
        manifest.created_files.append(selected_proxy)

        # If DLSS 5 is active in Mode A, ensure ReShade is deployed as dxgi.dll and record coex marker
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
            coex_marker = os.path.join(target_dir, ".mfg_coex_backup.json")
            try:
                import json
                with open(coex_marker, "w", encoding="utf-8") as f:
                    json.dump({
                        "backend": "A",
                        "original_proxy": "dxgi.dll",
                        "current_proxy": selected_proxy,
                        "adapted_for_dlss5": True
                    }, f, indent=2)
            except Exception:
                pass

        # Deploy Intel XeSS Frame Generation runtimes for dashdogy standalone XeMFG support
        # dashdogy 1.7.0 checks TargetExeDir / "RTXMFG-XeSS" folder first for libxess_fg.dll and libxell.dll,
        # or beside the game's executable in target_dir.
        xess_src_dir = ROOT_DIR / "apps" / "app2_mfg" / "embedded_components" / "optiscaler" / "nightly-20261023" / "OptiScaler"
        if xess_src_dir.exists():
            xemfg_sub = os.path.join(target_dir, "RTXMFG-XeSS")
            os.makedirs(xemfg_sub, exist_ok=True)
            if "RTXMFG-XeSS" not in manifest.created_files:
                manifest.created_files.append("RTXMFG-XeSS")

            for lib_name in ["libxess_fg.dll", "libxell.dll", "libxess.dll", "libxess_dx11.dll"]:
                lib_src = xess_src_dir / lib_name
                if lib_src.exists():
                    dst_sub = os.path.join(xemfg_sub, lib_name)
                    safe_force_remove(dst_sub)
                    shutil.copy2(str(lib_src), dst_sub)
                    # Runtimes reside strictly in RTXMFG-XeSS/ to avoid polluting target_dir or triggering false Mode B detection
                    pass

        # Forward sync Mode A INI configs
        try:
            from core.optiscaler_config import load_mode_a_preset
            from core.ini_sync import IniConfigManager
            preset_a = load_mode_a_preset()
            IniConfigManager.sync_mode_a_forward(target_dir, preset_a)
            for ini_file in ["RTX40MFG-UI.ini", "RTXMFG-UI.ini", "mfg_unlocker.ini", "RTXMFG-Universal.json"]:
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

    def _is_dlssg_sm86_dll(self, path: str) -> bool:
        """Check if a DLL file is dlssg_for_sm86 loader proxy binary."""
        data = self._read_dll_signature_bytes(path)
        return b"dlssg_sm86" in data or b"dlssg_for_sm86" in data

    def _get_pe_imported_proxies(self, exe_path: str) -> List[str]:
        """
        Analyze PE Import Table of game executable to find natively imported proxy DLLs.
        If game imports WINMM.dll, winmm.dll is prioritized.
        If game imports VERSION.dll, version.dll is prioritized.
        """
        imported: List[str] = []
        if not exe_path or not os.path.exists(exe_path) or os.path.getsize(exe_path) < 1024:
            return imported
        try:
            with open(exe_path, "rb") as fh:
                hdr = fh.read(1024)
            if not hdr.startswith(b"MZ") or len(hdr) < 0x40:
                raise ValueError("Not a valid PE")
            pe_offset = int.from_bytes(hdr[0x3C:0x40], byteorder="little")
            if pe_offset <= 0 or pe_offset + 4 > len(hdr) or hdr[pe_offset:pe_offset+4] != b"PE\x00\x00":
                raise ValueError("Invalid PE offset/signature")
            import pefile
            pe = pefile.PE(exe_path, fast_load=True)
            try:
                pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT']])
                for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
                    dll_name = entry.dll.decode("utf-8", errors="ignore").lower()
                    imported.append(dll_name)
            finally:
                try:
                    pe.close()
                except Exception:
                    pass
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
        """
        if active_backend == BackendType.RESHADE_ADDON:
            return "dxgi.dll"
        if active_backend == BackendType.DLSSG_SM86:
            return "version.dll"

        # 1. Standalone Mode (WITHOUT DLSS 5):
        # dxgi.dll is the universal standard DirectX hook for Mode A (dashdogy) and Mode B (OptiScaler).
        if not is_coexisting_with_dlss5:
            if active_backend == BackendType.STANDALONE:
                try:
                    from core.optiscaler_config import load_mode_a_preset
                    user_proxy = load_mode_a_preset().get("proxy_dll", "auto")
                    if user_proxy and user_proxy != "auto":
                        return user_proxy
                except Exception:
                    pass
                return "dxgi.dll"
            elif active_backend == BackendType.OPTISCALER_FSR:
                return "dxgi.dll"
            return "dxgi.dll"

        # 2. Coexistence with DLSS 5:
        # dxgi.dll is strictly reserved for DLSS 5 ReShade 6.8.
        # Pick the optimal non-dxgi proxy slot that the game's PE Import Table loads.
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
        if (td / "OptiScaler.ini").exists() or (td / "nvngx.ini").exists() or (td / "OptiScaler.dll").exists() or (td / "libxess_fg.dll").exists():
            return BackendType.OPTISCALER_FSR.value
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
                        try:
                            safe_force_remove(bak)
                            os.rename(dxgi_path, bak)
                        except Exception:
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
                IniConfigManager.sync_legacy_reshade_forward(target_dir, load_reshade_preset())
                healed = True
        except Exception:
            pass

        if healed:
            return True, "自动全量修复 ReShade64 底座与配置完成"
        return False, "底座与配置正常无需修复" 

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
            IniConfigManager.sync_legacy_reshade_forward(target_dir, r_cfg)
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

        # fakenvapi is only for non-NVIDIA GPUs (AMD/Intel) that lack official NVAPI.
        # On NVIDIA GPUs, native NVAPI exists and fakenvapi causes crashes (0xC0000005) in Streamline/Messiah
        # and disables native DLSS capability reporting.
        is_nvidia_gpu = "nvidia" in gpu_name.lower() or "geforce" in gpu_name.lower() or "rtx" in gpu_name.lower() or "gtx" in gpu_name.lower()
        if is_nvidia_gpu:
            deploy_fakenvapi = False
        else:
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
            dm_backup_dir = os.path.join(target_dir, ".dm_backup")
            os.makedirs(dm_backup_dir, exist_ok=True)
            dm_bak_file = os.path.join(dm_backup_dir, item)

            was_preexisting = os.path.exists(dst_item)
            if was_preexisting:
                if not os.path.exists(dm_bak_file) and not self._is_optiscaler_dll(dst_item) and not self._is_dashdogy_dll(dst_item):
                    try:
                        shutil.copy2(dst_item, dm_bak_file)
                    except Exception:
                        pass
                bak_name = item + ".mfg_bak"
                bak_path = os.path.join(target_dir, bak_name)
                safe_force_remove(bak_path)
                try:
                    os.rename(dst_item, bak_path)
                    manifest.renamed_backups.append({"original": item, "backup": bak_name})
                except Exception:
                    pass
            shutil.copy2(src_item, dst_item)
            if not was_preexisting:
                manifest.created_files.append(item)

        # 2.5 Expose game-local Streamline DLSS runtime at root for OptiScaler
        # Streamline games place nvngx_dlss.dll under Streamline/ subdirectory.
        # OptiScaler's root scan looks for nvngx_dlss.dll at game root. Exposing it ensures
        # OptiScaler finds DLSS and does not disable it ("nvngx_dlss.dll not found, disabling DLSS"),
        # keeping in-game DLSS Super Resolution 100% available and stable.
        sl_dir = os.path.join(target_dir, "Streamline")
        if os.path.exists(sl_dir) and os.path.isdir(sl_dir):
            for sl_file in ["nvngx_dlss.dll", "nvngx_dlssg.dll"]:
                sl_src = os.path.join(sl_dir, sl_file)
                root_dst = os.path.join(target_dir, sl_file)
                if os.path.exists(sl_src) and not os.path.exists(root_dst):
                    try:
                        shutil.copy2(sl_src, root_dst)
                        manifest.created_files.append(sl_file)
                    except Exception:
                        pass

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
        # Universal MFG Unlocker patches the XeSS-FG interpolation ceiling,
        # which is what actually enables 2X/3X/4X XeFG on non-Arc / NVIDIA GPUs.
        # CRITICAL: We deploy dashdogy v1.6.1 (which has NO DLSS 5 menu/tab)
        # and configure mfg_unlocker.ini with EnableImGui = 0, EnableUI = 0,
        # OverlayMenu = false, ToggleKey = 0.
        # This completely suppresses the 1.7.0 DLSS 5 window while restoring
        # multi-frame generation in Mode B!
        has_dlss5 = is_dlss5_present(target_dir)
        plugins_dir = os.path.join(target_dir, "OptiScaler", "plugins")
        os.makedirs(plugins_dir, exist_ok=True)
        dst_asi = os.path.join(plugins_dir, "MFGUnlocker.asi")

        # Prioritize v1.6.1 for OptiScaler ASI plugin to guarantee zero DLSS 5 UI pollution
        v161_path = ROOT_DIR / "apps" / "app2_mfg" / "embedded_components" / "dashdogy" / "v1.6.1" / "MFGUnlocker.dll"
        mfg_dll_path = str(v161_path) if v161_path.exists() else self.updater.get_latest_cached_file(BackendType.STANDALONE)

        if mfg_dll_path and os.path.exists(mfg_dll_path):
            # Remove a stale late-load copy so only one injection path exists.
            _late = os.path.join(plugins_dir, "MFGUnlocker-loadlate.asi")
            if os.path.exists(_late):
                safe_force_remove(_late)
            shutil.copy2(mfg_dll_path, dst_asi)
            if "OptiScaler/plugins/MFGUnlocker.asi" not in manifest.created_files:
                manifest.created_files.append("OptiScaler/plugins/MFGUnlocker.asi")

            # Write silenced mfg_unlocker.ini in plugins_dir to eliminate any UI overlay
            mfg_ini_path = os.path.join(plugins_dir, "mfg_unlocker.ini")
            from core.ini_sync import IniConfigManager
            IniConfigManager.write_ini_sections(mfg_ini_path, {
                "Overlay": {
                    "OverlayMenu": "false",
                    "EnableImGui": "0",
                    "EnableUI": "0",
                    "ToggleKey": "0"
                },
                "General": {
                    "OverlayMenu": "false",
                    "EnableImGui": "0",
                    "EnableUI": "0"
                },
                "Compatibility": {
                    "GpuNameOverride": "0"
                }
            })
            if "OptiScaler/plugins/mfg_unlocker.ini" not in manifest.created_files:
                manifest.created_files.append("OptiScaler/plugins/mfg_unlocker.ini")

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
            IniConfigManager.sync_mode_b_forward(target_dir, preset, exe_name=game.exe_name)
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
        Deploy Mode C (DLSSG for SM86/SM75 Native DLSS-G - 首选推荐: RTX 20/30 系列)
        严格注入三项:
          1. 代理 DLL (默认 version.dll，或用户指定的单一备选)
          2. dlssg_sm86.ini
          3. 整个 dlssg_sm86 目录
        代理任何时候只放一个；换槽位时彻底移除旧代理。严禁注入无关 dxgi.dll / ReShade。
        """
        source_dir = self.updater.get_latest_cached_dir(BackendType.DLSSG_SM86)
        if not source_dir or not os.path.exists(source_dir):
            emb = ROOT_DIR / "apps" / "app2_mfg" / "embedded_components" / "dlssg_sm86" / "v0.4.0"
            if emb.exists():
                source_dir = str(emb)
            else:
                return False, "本地缓存中未找到 dlssg_for_sm86 组件！\n请先在主界面点击【检查并同步最新版本】进行下载。"

        target_dir = game.target_dir
        kill_locking_processes(target_dir, game.exe_name)
        cleanup_pending_files(target_dir)

        # 1. 彻底清理旧版方案 C (OptiScaler/XeSS/FSR) 遗留目录与文件，杜绝残留混淆
        for opti_d_name in ["OptiScaler", "D3D12_Optiscaler", "XeSS", "amd_fidelityfx"]:
            opti_dir = os.path.join(target_dir, opti_d_name)
            if os.path.exists(opti_dir) and os.path.isdir(opti_dir):
                shutil.rmtree(opti_dir, ignore_errors=True)

        for conflicting_file in [
            "OptiScaler.ini", "nvngx.ini", "OptiScaler.log", "nvngx.log", "dlssg_to_fsr3.log",
            "dlssg_to_fsr3_amd_is_better.dll", "OptiScaler.dll",
            "fakenvapi.dll", "fakenvapi.ini", "fakenvapi.log", "renodx-mfgunlock.addon64",
            "RTX40MFG-UI.ini", "RTXMFG-UI.ini", "mfg_unlocker.ini", "RTXMFG-Universal.json",
            "RTX40MFG-UI-layout.ini", "MFGUnlocker.log", "rtxmfg.log", "MFGUnlocker.dll",
            "libxess_fg.dll", "libxess.dll", "libxess_dx11.dll", "libxell.dll",
            "amd_fidelityfx_dx12.dll", "amd_fidelityfx_framegeneration_dx12.dll",
            "amd_fidelityfx_upscaler_dx12.dll", "amd_fidelityfx_vk.dll",
            "ReShade64.dll"
        ]:
            f_p = os.path.join(target_dir, conflicting_file)
            if os.path.exists(f_p):
                safe_force_remove(f_p)

        # Unhook Bink if hooked by Mode A
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

        has_dlss5 = is_dlss5_present(target_dir)

        # 2. 确定选用的唯一代理 DLL (默认 version.dll)
        try:
            from core.optiscaler_config import load_dlssg_sm86_preset
            preset_c = load_dlssg_sm86_preset()
        except Exception:
            preset_c = {"proxy_dll": "version.dll"}

        valid_proxies = ["version.dll", "winmm.dll", "dbghelp.dll", "dinput8.dll", "d3d12.dll", "dxgi.dll"]
        pref = str(preset_c.get("proxy_dll", "version.dll")).strip().lower()
        if pref in valid_proxies:
            if has_dlss5 and pref == "dxgi.dll":
                selected_proxy = "version.dll"
            else:
                selected_proxy = pref
        else:
            selected_proxy = "version.dll"

        # 严格执行: 代理任何时候只放一个！彻底清理所有其他代理槽位 (换，不是加)
        for p_name in valid_proxies:
            if p_name.lower() == selected_proxy.lower():
                continue
            cand_p = os.path.join(target_dir, p_name)
            if os.path.exists(cand_p):
                # 仅当目标目录存在实体的 DLSS 5 addon 时保留 dxgi.dll (由 DLSS 5 独立管理)
                if p_name.lower() == "dxgi.dll" and has_dlss5 and self._is_reshade_dll(cand_p):
                    continue
                safe_force_remove(cand_p)

        # 定位代理文件源 (version.dll 在根目录，备选在 alternatives/)
        source_proxy = os.path.join(source_dir, selected_proxy)
        if not os.path.exists(source_proxy):
            alt_path = os.path.join(source_dir, "alternatives", selected_proxy)
            if os.path.exists(alt_path):
                source_proxy = alt_path
            else:
                source_proxy = os.path.join(source_dir, "version.dll")
                selected_proxy = "version.dll"

        if not os.path.exists(source_proxy):
            return False, f"dlssg_for_sm86 组件目录中缺少核心代理文件 {selected_proxy} 或 version.dll！"

        dest_proxy_path = os.path.join(target_dir, selected_proxy)
        dm_backup_dir = os.path.join(target_dir, ".dm_backup")
        os.makedirs(dm_backup_dir, exist_ok=True)
        dm_proxy_bak = os.path.join(dm_backup_dir, selected_proxy)

        if os.path.exists(dest_proxy_path):
            if not os.path.exists(dm_proxy_bak) and not self._is_dashdogy_dll(dest_proxy_path) and not self._is_optiscaler_dll(dest_proxy_path) and not self._is_reshade_dll(dest_proxy_path):
                try:
                    shutil.copy2(dest_proxy_path, dm_proxy_bak)
                except Exception:
                    pass
            safe_force_remove(dest_proxy_path)

        shutil.copy2(source_proxy, dest_proxy_path)
        manifest.created_files.append(selected_proxy)

        # 3. 部署整个 dlssg_sm86 目录 (runtime, backend, kernels, sr, xefg)
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

        # 4. 部署与前向同步 dlssg_sm86.ini
        src_ini = os.path.join(source_dir, "dlssg_sm86.ini")
        dst_ini = os.path.join(target_dir, "dlssg_sm86.ini")
        if os.path.exists(src_ini) and not os.path.exists(dst_ini):
            shutil.copy2(src_ini, dst_ini)
        if "dlssg_sm86.ini" not in manifest.created_files:
            manifest.created_files.append("dlssg_sm86.ini")

        # 与 DLSS 5 共存时，强制 SuperResolution Mode=Off 避免与 DLSS 5 超分冲突
        if has_dlss5:
            preset_c["super_resolution_mode"] = "Off"

        try:
            from core.ini_sync import IniConfigManager
            IniConfigManager.sync_dlssg_sm86_forward(target_dir, preset_c, game.exe_name)
        except Exception:
            pass

        return True, ""
