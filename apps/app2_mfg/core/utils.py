"""
Universal MFG Patcher - Utility functions for Windows PE inspection, process detection, and network.
"""

import os
import sys
import ctypes
from ctypes import wintypes
import hashlib
import json
import stat
import time
import shutil
import urllib.request
import urllib.error
import subprocess
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, Union, List

# Windows API for PE version inspection
def get_pe_file_version(filepath: str) -> Optional[str]:
    """
    Extract exact file version string (e.g. '310.9.16.0') from PE file resource.
    Uses Win32 GetFileVersionInfoW API without external dependencies.
    """
    if not os.path.exists(filepath):
        return None
        
    try:
        version_dll = ctypes.windll.version
        wpath = str(filepath)
        
        # GetFileVersionInfoSizeW
        dummy = wintypes.DWORD()
        size = version_dll.GetFileVersionInfoSizeW(wpath, ctypes.byref(dummy))
        if size == 0:
            return None
            
        data = ctypes.create_string_buffer(size)
        if not version_dll.GetFileVersionInfoW(wpath, 0, size, data):
            return None
            
        # VerQueryValueW to read VS_FIXEDFILEINFO root
        p_val = ctypes.c_void_p()
        val_len = wintypes.UINT()
        
        if not version_dll.VerQueryValueW(data, "\\", ctypes.byref(p_val), ctypes.byref(val_len)):
            return None
            
        # VS_FIXEDFILEINFO structure offset 8: dwFileVersionMS, offset 12: dwFileVersionLS
        # Each is a DWORD with high and low word
        ptr = ctypes.cast(p_val, ctypes.POINTER(ctypes.c_uint32))
        # Layout:
        # 0: dwSignature
        # 1: dwStrucVersion
        # 2: dwFileVersionMS
        # 3: dwFileVersionLS
        file_ver_ms = ptr[2]
        file_ver_ls = ptr[3]
        
        major = (file_ver_ms >> 16) & 0xFFFF
        minor = file_ver_ms & 0xFFFF
        build = (file_ver_ls >> 16) & 0xFFFF
        revision = file_ver_ls & 0xFFFF
        
        return f"{major}.{minor}.{build}.{revision}"
    except Exception:
        return None


def is_process_running(exe_name: str) -> bool:
    """
    Check if a process with exe_name is currently running on Windows.
    Prevents file-locking conflicts when patching or rolling back.
    """
    try:
        target = os.path.basename(exe_name).lower()
        cmd = ["tasklist", "/FO", "CSV", "/NH", "/FI", f"IMAGENAME eq {target}"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5, creationflags=0x08000000)
        output = result.stdout.strip().lower()
        return target in output
    except Exception:
        return False


def kill_locking_processes(target_dir: Union[str, Path], exe_name: Optional[str] = None) -> List[int]:
    """
    Precision lock termination: Scans running processes and forcefully terminates any process
    whose executable path is located inside target_dir, or matches exe_name or common game
    crash handlers/watchdogs (e.g. CrashReportClient.exe, UnrealCEFSubProcess.exe, UnityCrashHandler64.exe).
    Returns list of terminated PIDs.
    """
    terminated_pids = []
    norm_target_dir = os.path.normpath(str(target_dir)).lower() if target_dir else ""

    target_names = set()
    if exe_name:
        target_names.add(os.path.basename(exe_name).lower())

    common_handlers = {
        "crashreportclient.exe", "crashreportclienteditor.exe",
        "unrealcefsubprocess.exe", "unitycrashhandler64.exe",
        "unitycrashhandler32.exe", "werfault.exe", "easyanticheat.exe",
        "gamelaunchhelper.exe"
    }
    target_names.update(common_handlers)

    try:
        TH32CS_SNAPPROCESS = 0x00000002
        class PROCESSENTRY32(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_void_p),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", wintypes.LONG),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", ctypes.c_char * 260)
            ]

        hSnapshot = ctypes.windll.kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if hSnapshot != ctypes.c_void_p(-1).value and hSnapshot != 0:
            pe = PROCESSENTRY32()
            pe.dwSize = ctypes.sizeof(PROCESSENTRY32)
            has_next = ctypes.windll.kernel32.Process32First(hSnapshot, ctypes.byref(pe))
            
            pids_to_kill = set()
            current_pid = os.getpid()

            while has_next:
                pid = pe.th32ProcessID
                if pid > 4 and pid != current_pid:
                    try:
                        pname = pe.szExeFile.decode("gbk", "ignore").lower()
                    except Exception:
                        pname = ""

                    matched = False
                    if pname and pname in target_names:
                        matched = True

                    if not matched and norm_target_dir:
                        hProc = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
                        if hProc:
                            buf = ctypes.create_unicode_buffer(1024)
                            size = wintypes.DWORD(1024)
                            if ctypes.windll.kernel32.QueryFullProcessImageNameW(hProc, 0, buf, ctypes.byref(size)):
                                full_exe = os.path.normpath(buf.value).lower()
                                if full_exe.startswith(norm_target_dir):
                                    matched = True
                            ctypes.windll.kernel32.CloseHandle(hProc)

                    if matched:
                        pids_to_kill.add((pid, pname))

                has_next = ctypes.windll.kernel32.Process32Next(hSnapshot, ctypes.byref(pe))

            ctypes.windll.kernel32.CloseHandle(hSnapshot)

            for pid, pname in pids_to_kill:
                killed = False
                hTerm = ctypes.windll.kernel32.OpenProcess(0x0001, False, pid)  # PROCESS_TERMINATE
                if hTerm:
                    if ctypes.windll.kernel32.TerminateProcess(hTerm, 1):
                        killed = True
                    ctypes.windll.kernel32.CloseHandle(hTerm)

                if not killed:
                    try:
                        subprocess.run(
                            ["taskkill", "/F", "/PID", str(pid)],
                            capture_output=True,
                            timeout=2,
                            creationflags=0x08000000
                        )
                        killed = True
                    except Exception:
                        pass

                if killed:
                    terminated_pids.append(pid)

    except Exception:
        pass

    if terminated_pids:
        time.sleep(0.3)

    return terminated_pids


def _register_pending_cleanup(path_str: str):
    """Register locked temporary file for deferred cleanup."""
    try:
        from common.config_manager import CONFIG_ROOT
        pending_f = CONFIG_ROOT / "pending_cleanup.json"
    except Exception:
        appdata = os.environ.get("APPDATA", str(Path.home()))
        pending_f = Path(appdata) / "ToolboxMaster" / "config" / "pending_cleanup.json"
    try:
        pending_f.parent.mkdir(parents=True, exist_ok=True)
        items = []
        if pending_f.exists():
            with open(pending_f, "r", encoding="utf-8") as f:
                items = json.load(f)
        if path_str not in items:
            items.append(path_str)
        with open(pending_f, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def cleanup_pending_files(directory: Optional[Union[str, Path]] = None):
    """Clean up any leftover *._locked_*.tmp files in directory or from pending cleanup registry."""
    try:
        from common.config_manager import CONFIG_ROOT
        pending_f = CONFIG_ROOT / "pending_cleanup.json"
    except Exception:
        appdata = os.environ.get("APPDATA", str(Path.home()))
        pending_f = Path(appdata) / "ToolboxMaster" / "config" / "pending_cleanup.json"

    if pending_f.exists():
        try:
            with open(pending_f, "r", encoding="utf-8") as f:
                items = json.load(f)
            remaining = []
            for item in items:
                p = Path(item)
                if p.exists():
                    try:
                        os.chmod(str(p), stat.S_IWRITE)
                        p.unlink(missing_ok=True)
                    except Exception:
                        remaining.append(item)
            with open(pending_f, "w", encoding="utf-8") as f:
                json.dump(remaining, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    if directory:
        d = Path(directory)
        if d.exists() and d.is_dir():
            try:
                for tmp_file in d.glob("*._locked_*.tmp"):
                    try:
                        os.chmod(str(tmp_file), stat.S_IWRITE)
                        tmp_file.unlink(missing_ok=True)
                    except Exception:
                        pass
            except Exception:
                pass


def safe_force_remove(file_path: Union[str, Path]) -> bool:
    """
    Triple-layer force unlock and removal pipeline:
    1. Check existence; if gone, return True immediately.
    2. Reset file attributes (remove read-only / system flags) via chmod.
    3. Direct unlink / rmtree.
    4. If PermissionError / WinError 5 (file locked by active process):
       Atomic NTFS rename via os.replace to a temporary trash name (*._locked_*.tmp).
       Because Windows NTFS allows renaming locked DLLs, the original file is instantly
       removed from the game directory, restoring the game to 100% pure state.
       The trash file is deleted or scheduled for deletion upon reboot.
    5. Returns True if the original file no longer exists at file_path.
    """
    p = Path(file_path)
    if not p.exists() and not p.is_symlink():
        return True

    # Layer 1: Reset file attributes (clear read-only)
    try:
        os.chmod(str(p), stat.S_IWRITE)
    except Exception:
        pass

    # Layer 2: Direct removal
    try:
        if p.is_dir():
            shutil.rmtree(str(p), ignore_errors=True)
        else:
            p.unlink(missing_ok=True)
        if not p.exists():
            return True
    except Exception:
        pass

    # Layer 3: Atomic NTFS rename to bypass file lock
    try:
        ts = int(time.time() * 1000)
        trash_name = f"{p.name}._locked_{ts}.tmp"
        trash_path = p.parent / trash_name

        os.replace(str(p), str(trash_path))

        # Original name is now gone from target folder!
        try:
            trash_path.unlink(missing_ok=True)
        except Exception:
            try:
                MOVEFILE_DELAY_UNTIL_REBOOT = 0x00000004
                ctypes.windll.kernel32.MoveFileExW(str(trash_path), None, MOVEFILE_DELAY_UNTIL_REBOOT)
            except Exception:
                pass
            _register_pending_cleanup(str(trash_path))

        return not p.exists()
    except Exception:
        pass

    return not p.exists()


def calculate_sha256(filepath: str) -> str:
    """Calculate SHA256 checksum of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().lower()


def http_get_json(url: str, timeout: int = 10, mirror_prefix: Optional[str] = None) -> Tuple[bool, Any, str]:
    """
    Fetch JSON from a URL with custom User-Agent and optional mirror prefix.
    Returns (success, parsed_data_or_none, error_message_or_empty).
    """
    target_url = url
    if mirror_prefix and not url.startswith(mirror_prefix):
        target_url = f"{mirror_prefix.rstrip('/')}/{url.lstrip('/')}"
        
    req = urllib.request.Request(
        target_url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/vnd.github.v3+json"
        }
    )
    
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
            return True, data, ""
    except urllib.error.HTTPError as e:
        return False, None, f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        return False, None, str(e)


def download_file(url: str, dest_path: str, mirror_prefix: Optional[str] = None, timeout: int = 30, progress_cb: Optional[Any] = None) -> Tuple[bool, str]:
    """
    Download file to local destination with optional mirror and progress callback.
    progress_cb(bytes_downloaded, total_bytes) is called for each read chunk.
    Returns (success, error_message).
    """
    target_url = url
    if mirror_prefix and not url.startswith(mirror_prefix):
        target_url = f"{mirror_prefix.rstrip('/')}/{url.lstrip('/')}"
        
    os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
    
    req = urllib.request.Request(
        target_url,
        headers={"User-Agent": "Universal-MFG-Patcher/1.0"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response, open(dest_path, "wb") as out_file:
            content_length = response.headers.get("Content-Length")
            total_bytes = int(content_length) if content_length and content_length.isdigit() else 0
            downloaded = 0
            while chunk := response.read(65536):
                out_file.write(chunk)
                downloaded += len(chunk)
                if progress_cb:
                    try:
                        progress_cb(downloaded, total_bytes)
                    except Exception:
                        pass
        return True, ""
    except Exception as e:
        if os.path.exists(dest_path):
            try:
                os.remove(dest_path)
            except OSError:
                pass
        return False, str(e)


def get_app_cache_dir() -> Path:
    """
    Returns the dedicated C:/ToolboxData cache directory for UniversalMFGPatcher.
    Routes all DLLs, downloads, and temporary files into C:/ToolboxData/cache/app2_mfg/.
    """
    try:
        from common.config_manager import get_app_cache_dir as toolbox_cache_dir
        return toolbox_cache_dir("app2_mfg")
    except Exception:
        cache_path = Path("C:/ToolboxData/cache/app2_mfg")
        cache_path.mkdir(parents=True, exist_ok=True)
        return cache_path


def get_system_gpu_name() -> str:
    """
    Detects active TRUE physical GPU name, prioritizing App 1 (CPU/GPU配置管理工具)
    出厂真实硬件数据与备份快照，防止因注册表/WMI中已被修改伪装（如伪装成 RTX 5090 等）导致插帧补丁识别为错误架构。
    """
    try:
        from common.config_manager import get_real_gpu_model
        gpu = get_real_gpu_model()
        if gpu and gpu != "Unknown GPU":
            return gpu
    except Exception:
        pass

    try:
        import winreg
        path = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
            for i in range(12):
                try:
                    sub = winreg.EnumKey(key, i)
                    with winreg.OpenKey(key, sub) as sk:
                        name, _ = winreg.QueryValueEx(sk, "DriverDesc")
                        s = str(name).strip()
                        if any(k in s.upper() for k in ["NVIDIA", "GEFORCE", "RTX", "GTX", "RADEON", "INTEL ARC"]):
                            return s
                except Exception:
                    pass
    except Exception:
        pass
    return "Unknown GPU"


def is_rtx_40_or_newer(gpu_name: str) -> bool:
    """Check if GPU has native OFA Gen 4+ supporting native DLSS-G (RTX 40/50+)."""
    import re
    name = gpu_name.upper()
    if re.search(r"RTX\s*(40\d\d|50\d\d|60\d\d)", name):
        return True
    return False

