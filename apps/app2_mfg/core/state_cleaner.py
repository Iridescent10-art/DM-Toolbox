# -*- coding: utf-8 -*-

"""

Game Directory State Machine Cleaner & DLL Slot Isolation Engine.

Enforces strict slot isolation across Mode A (dashdogy), Mode B (RenoDX),

and Mode C (OptiScaler), preventing cross-mode DLL conflicts and proxy leakage.

"""

import os

import sys

import shutil

from pathlib import Path

from typing import Union, Optional, Tuple, List

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent

if str(ROOT_DIR) not in sys.path:

    sys.path.insert(0, str(ROOT_DIR))


try:
    from core.utils import get_game_statically_imported_dlls, auto_heal_game_dependencies
except Exception:
    try:
        from apps.app2_mfg.core.utils import get_game_statically_imported_dlls, auto_heal_game_dependencies
    except Exception:
        def get_game_statically_imported_dlls(td): return set()
        def auto_heal_game_dependencies(td): return []

def _read_dll_signature_bytes(path: str) -> bytes:

    """Safely reads DLL binary signature data (first 16MB + last 16MB if >32MB, else full)."""

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

def is_reshade_dll_file(path: str) -> bool:

    """Check if file is a ReShade binary (excludes OptiScaler)."""

    if not os.path.exists(path) or not os.path.isfile(path):

        return False

    data = _read_dll_signature_bytes(path)

    if b"OptiScaler" in data:

        return False

    return b"ReShade" in data or b"crosire" in data

def is_optiscaler_dll_file(path: str) -> bool:

    """Check if file is an OptiScaler binary."""

    if not os.path.exists(path) or not os.path.isfile(path):

        return False

    data = _read_dll_signature_bytes(path)

    return b"OptiScaler" in data or b"libxess" in data

def is_dlss5_present(target_dir: Union[str, Path]) -> bool:

    """

    Centralized detector for any active DLSS 5 addon or manifest in target directory.

    Supports modern RenoDX ShortFuse (renodx-dlss.addon64), v11.9, Chinese builds, and legacy versions.

    """

    if not target_dir:

        return False

    td = Path(target_dir)

    if not td.exists() or not td.is_dir():

        return False



    # 1. Manifests, backups, and config markers

    if any((

        (td / ".dlss5_manifest.json").exists(),

        (td / ".dlss5_backup").exists(),

        (td / ".dlss5_patch_manifest.json").exists(),

        (td / ".dlss5_config.json").exists(),

    )):

        return True



    # 2. Known DLSS 5 addon binaries

    if any((

        (td / "renodx-dlss5-v11.9.addon64").exists(),

        (td / "renodx-dlss-ShortFuse-261017汉化版.addon64").exists(),

        (td / "renodx-dlss5.addon64").exists(),

        (td / "renodx-dlss5-Lecram-v11-Beta48.addon64").exists(),

        (td / "renodx-dlss.addon64").exists(),

        (td / "Lecram-v12.addon64").exists(),

        (td / "lecram-v12.addon64").exists(),

        (td / "lecram-dlss5-beta10.addon64").exists(),

        (td / "dlss5-nr.addon64").exists(),

    )):

        return True



    # 3. Dynamic glob for any addon containing dlss/shortfuse/renodx dlss (excluding mfgunlock)

    try:

        for a in list(td.glob("*.addon64")) + list(td.glob("*.addon")):

            name_lower = a.name.lower()

            if "mfgunlock" in name_lower:

                continue

            if any(k in name_lower for k in ["dlss5", "dlss-nr", "shortfuse"]) or ("renodx" in name_lower and "dlss" in name_lower):

                return True

    except Exception:

        pass



    # 4. Neural reconstruction model runtime & RenoDX DLSS preset folder

    if (td / "nvngx_dlssnr.dll").exists():

        return True

    if (td / "RenoDX" / "DLSS5").exists():

        return True



    return False





def is_mode_c_present(target_dir: Union[str, Path]) -> bool:

    """

    Check if Mode C (OptiScaler / XeSS 2.0 / XeFG frame generation) is present in target directory.

    Detected via presence of OptiScaler.ini or libxess_fg.dll.

    """

    if not target_dir:

        return False

    td = Path(target_dir)

    if not td.exists() or not td.is_dir():

        return False

    return (td / "OptiScaler.ini").exists() or (td / "OptiScaler.dll").exists()





    # Purge legacy backend from manifest if present
    manifest_p = td / ".mfg_patch_manifest.json"
    if manifest_p.exists():
        try:
            import json
            with open(manifest_p, "r", encoding="utf-8") as mf:
                mdata = json.load(mf)
            if mdata.get("active_backend") in ("mavismmg", "dlssg_sm86"):
                safe_remove_file(manifest_p)
                actions_taken.append("清理并重置旧版遗留后端配置 (.mfg_patch_manifest.json)")
        except Exception:
            pass

def is_dashdogy_dll_file(path: str) -> bool:

    """Check if file is a dashdogy / MFGUnlocker binary."""

    if not os.path.exists(path) or not os.path.isfile(path):

        return False

    data = _read_dll_signature_bytes(path)

    return b"MFGUnlocker" in data or b"RTX40MFG" in data or b"RTXMFG" in data

def find_reshade_framework_dll() -> Optional[str]:

    """Locate ReShade64.dll with full Add-on Support."""

    candidates = [

        ROOT_DIR / "apps" / "app2_mfg" / "embedded_components" / "reshade" / "6.8.0" / "ReShade64.dll",

        ROOT_DIR / "defaults" / "app2_mfg" / "embedded_components" / "reshade" / "6.8.0" / "ReShade64.dll",

    ]

    appdata = os.environ.get("APPDATA", "")

    if appdata:

        candidates.append(Path(appdata) / "ToolboxMaster" / "cache" / "app2_mfg" / "reshade" / "6.8.0" / "ReShade64.dll")

        cache_reshade = Path(appdata) / "ToolboxMaster" / "cache" / "reshade"

        if cache_reshade.exists():

            for f in cache_reshade.rglob("ReShade64.dll"):

                if f.is_file() and f.stat().st_size > 4 * 1024 * 1024:

                    candidates.append(f)

    local_app = os.environ.get("LOCALAPPDATA", "")

    if local_app:

        candidates.extend([

            Path(local_app) / "RHI" / "reshade" / "ReShade64.dll",

            Path(local_app) / "RHI" / "reshade-nightly" / "ReShade64.dll",

            Path(local_app) / "RHI" / "reshade-normal" / "ReShade64.dll",

        ])

    for cand in candidates:

        if cand.exists() and cand.is_file() and cand.stat().st_size > 4 * 1024 * 1024:

            return str(cand)

    return None

def safe_remove_file(file_path: Union[str, Path]) -> bool:

    """Safely removes a file with permission unlocking."""

    p = Path(file_path)

    if not p.exists():

        return True

    try:

        if not os.access(p, os.W_OK):

            os.chmod(p, 0o777)

        p.unlink(missing_ok=True)

        return True

    except Exception:

        try:

            # Fallback rename then delete

            temp_name = p.parent / f"{p.name}.trash_{os.getpid()}"

            p.rename(temp_name)

            temp_name.unlink(missing_ok=True)

            return True

        except Exception:

            return False

def CleanGameDirectoryState(

    target_dir: Union[str, Path],

    preserve_dlss5: bool = False,

    target_mode: Optional[str] = None,

    target_proxy: Optional[str] = None

) -> Tuple[bool, List[str]]:

    """

    Cleans target game directory state, removes cross-mode conflicting files,

    and maintains whitelist backups.

    target_mode:

      - 'A': Prepares for Mode A (dashdogy). ReShade uses dxgi.dll if DLSS 5 active; dashdogy uses version.dll.

             Removes ReShade64.dll, renodx-mfgunlock.addon64, OptiScaler.ini, OptiScaler.log.

      - 'B': Prepares for Mode B (RenoDX). ReShade uses dxgi.dll with both addons.

             Removes version.dll, winmm.dll, ReShade64.dll, OptiScaler.ini, RTXMFG-Universal.json.

      - 'C': Prepares for Mode C (OptiScaler / XeSS 2.0 / FSR 3.1).

             OptiScaler uses dxgi.dll in standalone, or dynamic proxy (winmm.dll / version.dll) if DLSS 5 active.

             Removes Mode A/B/D conflicting files.


             Removes Mode A/B/C conflicting files.

      - None: Full unpatch clean state.

    """

    td = Path(target_dir)

    if not td.exists() or not td.is_dir():

        return False, [f"目标目录不存在: {target_dir}"]

    actions_taken: List[str] = []

    # 1. Whitelist Backup Mechanism

    backup_dir = td / ".dm_backup"

    try:

        if not backup_dir.exists():

            backup_dir.mkdir(parents=True, exist_ok=True)

            actions_taken.append("创建 .dm_backup 原始白名单目录")

        imported_pe_dlls = get_game_statically_imported_dlls(td)
        whitelist_natives = [
            "nvngx_dlss.dll",
            "nvngx_dlssg.dll",
            "sl.interposer.dll",
            "sl.dlss_g.dll"
        ]
        for pe_dll in imported_pe_dlls:
            if pe_dll.lower() not in [x.lower() for x in whitelist_natives]:
                whitelist_natives.append(pe_dll)

        for native_name in whitelist_natives:

            native_path = td / native_name

            backup_path = backup_dir / native_name

            if native_path.exists() and not backup_path.exists():

                # Only backup if not an injected proxy

                if not is_optiscaler_dll_file(str(native_path)) and not is_dashdogy_dll_file(str(native_path)):

                    try:

                        shutil.copy2(native_path, backup_path)

                        actions_taken.append(f"白名单备份原版核心: {native_name}")

                    except Exception as e:

                        actions_taken.append(f"备份 {native_name} 失败: {e}")

        # 1.1 Restore any orphan *.mfg_bak files in td where destination is missing or injected
        for bak_f in td.glob("*.mfg_bak"):
            orig_name = bak_f.name[:-8]
            orig_path = td / orig_name
            if not orig_path.exists() or is_optiscaler_dll_file(str(orig_path)) or is_dashdogy_dll_file(str(orig_path)):
                try:
                    if orig_path.exists():
                        safe_remove_file(orig_path)
                    shutil.copy2(str(bak_f), str(orig_path))
                    safe_remove_file(bak_f)
                    actions_taken.append(f"从 .mfg_bak 恢复游戏原生核心: {orig_name}")
                except Exception:
                    pass

    except Exception as e:

        actions_taken.append(f"初始化白名单备份目录失败: {e}")

    # 2. Bink2 Hook Restoration

    bink_hooked = td / "bink2w64Hooked.dll"

    bink_orig = td / "bink2w64.dll"

    if bink_hooked.exists():

        # If not Mode A (or switching modes), unhook bink

        if target_mode != "A":

            safe_remove_file(bink_orig)

            try:

                bink_hooked.rename(bink_orig)

                actions_taken.append("恢复原版 bink2w64.dll (解除 Bink 劫持)")

            except Exception as e:

                actions_taken.append(f"解除 Bink 劫持失败: {e}")

    # 3. Mode-Specific DLL Slot Isolation

    mode = str(target_mode).upper() if target_mode else ""

    target_proxy_norm = target_proxy.lower().strip() if target_proxy else ""



    # (A) ReShade64.dll: Legacy bridge file, clean when not needed

    reshade64_path = td / "ReShade64.dll"

    if reshade64_path.exists():

        if mode != "D" or preserve_dlss5:

            safe_remove_file(reshade64_path)

            actions_taken.append("清理 ReShade64.dll 槽位")



    # (B) version.dll, winmm.dll, dinput8.dll Proxy Slots:

    # Mode A / C / D dynamically utilize one of these proxy slots.

    # When target_proxy is specified, the chosen proxy is strictly protected.

    version_path = td / "version.dll"

    if version_path.exists():

        if is_dashdogy_dll_file(str(version_path)) or is_optiscaler_dll_file(str(version_path)):

            if target_proxy_norm == "version.dll":

                pass  # Exempt! Active target proxy

            elif mode not in ("A", "C", "D") or (target_proxy_norm and target_proxy_norm != "version.dll"):

                safe_remove_file(version_path)

                actions_taken.append("清理非目标代理槽位的 version.dll")



    winmm_path = td / "winmm.dll"

    if winmm_path.exists():

        if is_dashdogy_dll_file(str(winmm_path)) or is_optiscaler_dll_file(str(winmm_path)):

            if target_proxy_norm == "winmm.dll":

                pass  # Exempt! Active target proxy for yysls / winmm-imported games

            elif mode not in ("A", "C", "D") or (target_proxy_norm and target_proxy_norm != "winmm.dll"):

                safe_remove_file(winmm_path)

                actions_taken.append("清理非目标代理槽位的 winmm.dll")



    dinput8_path = td / "dinput8.dll"

    if dinput8_path.exists():

        if is_dashdogy_dll_file(str(dinput8_path)) or is_optiscaler_dll_file(str(dinput8_path)):

            if target_proxy_norm == "dinput8.dll":

                pass  # Exempt! Active target proxy

            elif mode not in ("A", "C", "D") or (target_proxy_norm and target_proxy_norm != "dinput8.dll"):

                safe_remove_file(dinput8_path)

                actions_taken.append("清理非目标代理槽位的 dinput8.dll")



    # (C) renodx-mfgunlock.addon64: ONLY exists in Mode B!

    renodx_addon = td / "renodx-mfgunlock.addon64"
    if renodx_addon.exists() and mode != "B":
        safe_remove_file(renodx_addon)
        actions_taken.append("清理非模式 B 的 renodx-mfgunlock.addon64")



    # If restoring/unpatching (target_mode is None), restore all backed-up files from .dm_backup
    if target_mode is None:
        if backup_dir.exists() and backup_dir.is_dir():
            for bf in backup_dir.glob("*"):
                if bf.is_file() and not bf.name.endswith(".json"):
                    dest_f = td / bf.name
                    if not is_optiscaler_dll_file(str(bf)) and not is_dashdogy_dll_file(str(bf)) and not is_reshade_dll_file(str(bf)):
                        try:
                            safe_remove_file(dest_f)
                            shutil.copy2(str(bf), str(dest_f))
                            actions_taken.append(f"从 .dm_backup 还原原始文件: {bf.name}")
                        except Exception as e:
                            actions_taken.append(f"还原 {bf.name} 失败: {e}")

    # (D) dxgi.dll Slot Management:

    # Under DLSS 5 coexistence: dxgi.dll is STRICTLY reserved for ReShade 6.8 (DLSS 5 base).

    # OptiScaler, Mode A, Mode D MUST NOT overwrite dxgi.dll!

    dxgi_path = td / "dxgi.dll"

    if dxgi_path.exists():

        if preserve_dlss5:

            # DLSS 5 Coexistence: purge non-ReShade proxies so ReShade takes dxgi.dll

            if is_optiscaler_dll_file(str(dxgi_path)) or is_dashdogy_dll_file(str(dxgi_path)):

                safe_remove_file(dxgi_path)

                actions_taken.append("清理 dxgi.dll (非 ReShade 代理)，锁死 ReShade 6.8 渲染底座")

        else:

            if mode == "B":

                if is_optiscaler_dll_file(str(dxgi_path)) or is_dashdogy_dll_file(str(dxgi_path)):

                    safe_remove_file(dxgi_path)

                    actions_taken.append("清理 dxgi.dll (非 ReShade 代理)，为模式 B 让出槽位")

            elif mode in ("B", "C"):

                if target_proxy_norm and target_proxy_norm != "dxgi.dll":

                    if is_optiscaler_dll_file(str(dxgi_path)) or is_dashdogy_dll_file(str(dxgi_path)):

                        safe_remove_file(dxgi_path)

                        actions_taken.append("清理非目标代理槽位的 dxgi.dll")

                else:

                    if is_dashdogy_dll_file(str(dxgi_path)):

                        safe_remove_file(dxgi_path)

                        actions_taken.append("清理 dxgi.dll (dashdogy)，为模式 C 让出槽位")

            elif mode in ("A", "D"):

                if is_optiscaler_dll_file(str(dxgi_path)):

                    safe_remove_file(dxgi_path)

                    actions_taken.append("清理残留的 dxgi.dll (OptiScaler)")

            elif mode == "":

                if is_optiscaler_dll_file(str(dxgi_path)) or is_dashdogy_dll_file(str(dxgi_path)):

                    safe_remove_file(dxgi_path)

                    actions_taken.append("完全卸载清理 dxgi.dll 代理")

                elif not preserve_dlss5 and is_reshade_dll_file(str(dxgi_path)):

                    safe_remove_file(dxgi_path)

                    actions_taken.append("完全卸载清理 dxgi.dll (ReShade)")



    # If preserving DLSS 5, ensure dxgi.dll has ReShade 6.8 host

    if preserve_dlss5:

        if not dxgi_path.exists() or not is_reshade_dll_file(str(dxgi_path)):

            dlss5_dxgi = ROOT_DIR / "apps" / "app6_dlss5" / "assets" / "dxgi.dll"

            reshade_fw = str(dlss5_dxgi) if dlss5_dxgi.exists() else find_reshade_framework_dll()

            if reshade_fw and os.path.exists(reshade_fw):

                try:

                    safe_remove_file(dxgi_path)

                    shutil.copy2(reshade_fw, dxgi_path)

                    actions_taken.append("自动恢复 DLSS 5 所需 ReShade 64 宿主底座 (dxgi.dll)")

                except Exception as e:

                    actions_taken.append(f"部署 ReShade 底座失败: {e}")



    # Clean any stale trash files

    for trash in td.glob("*.trash_*"):

        safe_remove_file(trash)



    # (E) Config and Log File Isolation:

    # Mode A configs:

    mode_a_configs = [

        "RTXMFG-Universal.json",

        "RTXMFG-Universal.status.json",

        "RTX40MFG-UI.ini",

        "RTXMFG-UI.ini",

        "mfg_unlocker.ini",

        "RTX40MFG-UI-layout.ini",

        "MFGUnlocker.log",

        "rtxmfg.log",

        "MFGUnlocker.dll"

    ]

    if mode != "A":

        for cfg in mode_a_configs:

            f = td / cfg

            if f.exists():

                safe_remove_file(f)

                actions_taken.append(f"清理非模式 A 配置文件: {cfg}")

    # Mode C (OptiScaler / XeSS 2.0 / FSR 3.1) configs & runtime DLLs:

    mode_c_configs = [

        "OptiScaler.dll",

        "OptiScaler.ini",

        "OptiScaler.log",

        "nvngx.ini",

        "dlssg_to_fsr3.log",

        "dlssg_to_fsr3_amd_is_better.dll",

        "fakenvapi.ini",

        "fakenvapi.log",

        "fakenvapi.dll",

        "amd_fidelityfx_dx12.dll",

        "amd_fidelityfx_framegeneration_dx12.dll",

        "amd_fidelityfx_upscaler_dx12.dll",

        "amd_fidelityfx_vk.dll",

        "libxell.dll",

        "libxess.dll",

        "libxess_dx11.dll",

        "libxess_fg.dll"

    ]

    if mode not in ("B", "C"):
        imported_pe_dlls = get_game_statically_imported_dlls(td)
        has_ffx_loader = (td / "amd_fidelityfx_loader_dx12.dll").exists()
        for cfg in mode_c_configs:
            if has_ffx_loader and cfg == "amd_fidelityfx_upscaler_dx12.dll":
                actions_taken.append("豁免保留游戏原生态 FidelityFX Upscaler 依赖库: amd_fidelityfx_upscaler_dx12.dll")
                continue
            if cfg.lower() in imported_pe_dlls:
                actions_taken.append(f"豁免保留游戏原生PE静态依赖库: {cfg}")
                continue
            f = td / cfg
            if f.exists():
                safe_remove_file(f)
                actions_taken.append(f"清理非模式 C 配置文件: {cfg}")

        for opti_d_name in ["OptiScaler", "D3D12_Optiscaler", "XeSS", "amd_fidelityfx"]:

            opti_dir = td / opti_d_name

            if opti_dir.exists() and opti_dir.is_dir():

                try:

                    shutil.rmtree(opti_dir, ignore_errors=True)

                    actions_taken.append(f"清理非模式 C {opti_d_name} 目录")

                except Exception:

                    pass



    # Clean legacy dlssg_sm86 files if present:
    dlssg_sm86_dir = td / "dlssg_sm86"
    dlssg_sm86_ini = td / "dlssg_sm86.ini"
    if dlssg_sm86_ini.exists():
        safe_remove_file(dlssg_sm86_ini)
        actions_taken.append("清理遗留配置文件: dlssg_sm86.ini")
    if dlssg_sm86_dir.exists() and dlssg_sm86_dir.is_dir():
        try:
            shutil.rmtree(dlssg_sm86_dir, ignore_errors=True)
            actions_taken.append("清理遗留 dlssg_sm86 目录")
        except Exception:
            pass

    # (F) DLSS 5 Addon & Runtime Protection / Removal:

    if not preserve_dlss5:

        dlss5_files = [

            "renodx-dlss5-v11.9.addon64",

            "renodx-dlss5.addon64",

            "renodx-dlss5-Lecram-v11-Beta48.addon64",

            "renodx-dlss.addon64",

            "Lecram-v12.addon64",

            "lecram-v12.addon64",

            "renodx-dlss-ShortFuse-261017汉化版.addon64",

            "lecram-dlss5-beta10.addon64",

            "dlss5-nr.addon64",

            "nvngx_dlssnr.dll",

            ".dlss5_manifest.json",

            ".dlss5_config.json",

            ".dlss5_patch_manifest.json",

            "ReShade.ini",

            "ReShade.ini.v11-backup",

            "ReShade.log"

        ]

        for f_name in dlss5_files:

            f = td / f_name

            if f.exists():

                safe_remove_file(f)

                actions_taken.append(f"清理 DLSS 5 资产: {f_name}")

        dlss5_runtime_dir = td / "dlss5-nr-runtime"

        if dlss5_runtime_dir.exists() and dlss5_runtime_dir.is_dir():

            try:

                shutil.rmtree(dlss5_runtime_dir, ignore_errors=True)

                actions_taken.append("清理 DLSS 5 运行时目录")

            except Exception:

                pass

        for crash_dump in td.glob("dlss5-nr-crash-*.txt"):

            safe_remove_file(crash_dump)

            actions_taken.append(f"清理 DLSS 5 崩溃日志: {crash_dump.name}")

    # (H) NVIDIA Streamline Crash Dumps in %ProgramData%:

    # Whenever unpatching or cleaning state, also clean any leftover NVIDIA crash dumps

    try:

        game_tag = td.name.lower()

        if (td / "yysls.exe").exists() or "yysls" in str(td).lower():

            game_tag = "yysls"

        sl_actions = clean_nvidia_streamline_dumps(game_tag)

        actions_taken.extend(sl_actions)

    except Exception:

        pass

    try:
        healed = auto_heal_game_dependencies(td)
        for h in healed:
            actions_taken.append(f"自动自愈恢复缺失的游戏原生依赖库: {h}")
    except Exception:
        pass

    return True, actions_taken

def clean_nvidia_streamline_dumps(game_exe_or_dir_name: Optional[str] = None) -> List[str]:

    r"""

    Cleans NVIDIA Streamline crash dumps (.dmp) located in %ProgramData%\NVIDIA\Streamline.

    When games with Streamline crash or terminate abnormally, NVIDIA silently saves ~6.7MB

    dumps per crash into %ProgramData%\NVIDIA\Streamline\<game>\<timestamp>\sl-sha-xxxx.dmp,

    which quickly consumes multiple gigabytes of disk space.

    """

    actions = []

    prog_data = os.environ.get("ProgramData", r"C:\ProgramData")

    streamline_dir = Path(prog_data) / "NVIDIA" / "Streamline"

    if not streamline_dir.exists() or not streamline_dir.is_dir():

        return actions

    targets = []

    if game_exe_or_dir_name:

        clean_name = Path(game_exe_or_dir_name).stem.lower()

        sub = streamline_dir / clean_name

        if sub.exists():

            targets.append(sub)

        # Also check common aliases like yysls

        if "yysls" in clean_name or "yanyun" in clean_name:

            yysls_sub = streamline_dir / "yysls"

            if yysls_sub.exists() and yysls_sub not in targets:

                targets.append(yysls_sub)

    else:

        try:

            targets = [d for d in streamline_dir.iterdir() if d.is_dir()]

        except Exception:

            pass

    for target in targets:

        try:

            files = [f for f in target.rglob("*") if f.is_file()]

            if files:

                total_mb = sum(f.stat().st_size for f in files) / (1024 * 1024)

                file_count = len(files)

                shutil.rmtree(target, ignore_errors=True)

                if not target.exists():

                    actions.append(f"彻底清理 NVIDIA Streamline 崩溃转储: {target.name} ({file_count} 个文件，释放约 {total_mb:.1f} MB)")

                else:

                    remaining = sum(f.stat().st_size for f in target.rglob("*") if f.is_file()) / (1024 * 1024)

                    freed = max(0.0, total_mb - remaining)

                    actions.append(f"清理 NVIDIA Streamline 崩溃转储: {target.name} (已释放约 {freed:.1f} MB)")

        except Exception as e:

            actions.append(f"清理 Streamline 转储 {target.name} 异常: {e}")

    return actions