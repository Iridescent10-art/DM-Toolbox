"""
Universal MFG Patcher - RHI (ReShade HDR Installer) Integration Module.
Upstream: https://github.com/RankFTW/RHI
"""

import os
import json
import shutil
import subprocess
from pathlib import Path
from typing import Tuple, Dict, Any, Optional
from core.utils import http_get_json, download_file, get_app_cache_dir

RHI_REPO_API = "https://api.github.com/repos/RankFTW/RHI/releases/latest"

class RHIInstaller:
    def __init__(self, cache_dir: Optional[str] = None):
        if cache_dir:
            c_path = Path(cache_dir)
            if (c_path / "gui_qt.py").exists() or (c_path / "main.py").exists() or c_path.name.lower() in ["多帧生成", "dist"]:
                self.tools_dir = get_app_cache_dir() / "tools"
                self.cache_dir = get_app_cache_dir()
            else:
                self.tools_dir = c_path / "tools"
                self.cache_dir = c_path
        else:
            self.tools_dir = get_app_cache_dir() / "tools"
            self.cache_dir = get_app_cache_dir()

        self.tools_dir.mkdir(parents=True, exist_ok=True)
        self.setup_exe = self.tools_dir / "RHI-Setup.exe"
        try:
            from common.config_manager import get_app_config_path
            self.config_file = get_app_config_path("app2_mfg", "rhi_config.json")
        except Exception:
            self.config_file = Path("C:/ToolboxData/config/app2_mfg/rhi_config.json")
        self.config_file.parent.mkdir(parents=True, exist_ok=True)

    def get_manual_path(self) -> Optional[str]:
        """Returns manually configured RHI executable path if valid and exists on disk."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    p = data.get("manual_path")
                    if p and os.path.exists(p):
                        return p
            except Exception:
                pass
        return None

    def set_manual_path(self, path: str):
        """Save user's manually chosen RHI executable path."""
        try:
            data = {}
            if self.config_file.exists():
                try:
                    with open(self.config_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    data = {}
            data["manual_path"] = str(Path(path).resolve())
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def clear_manual_path(self):
        """Remove user manual override and revert to automatic system detection."""
        try:
            if self.config_file.exists():
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if "manual_path" in data:
                    del data["manual_path"]
                with open(self.config_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def is_manual_path(self) -> bool:
        """Returns True if user currently has a manual path override active."""
        return bool(self.get_manual_path())

    def is_installed_or_cached(self) -> Tuple[bool, str]:
        """
        Check if RHI is installed on system or cached locally.
        Prioritizes user manual override, then system installations, then cached setup.
        """
        # 0. Check user manual override first
        manual = self.get_manual_path()
        if manual and os.path.exists(manual):
            return True, manual
        # 1. Check system installation in standard Program Files and AppData locations
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        local_app = os.environ.get("LOCALAPPDATA", "")

        candidates = [
            Path(pf) / "RHI" / "RHI.exe",
            Path(pf86) / "RHI" / "RHI.exe",
            Path(r"C:\Program Files\RHI\RHI.exe"),
            Path(r"C:\Program Files (x86)\RHI\RHI.exe"),
        ]
        if local_app:
            candidates.extend([
                Path(local_app) / "Programs" / "RHI" / "RHI.exe",
                Path(local_app) / "RHI" / "RHI.exe",
            ])

        for cand in candidates:
            if cand.exists():
                return True, str(cand)

        # 2. Check Windows Registry uninstall entries
        reg_path = self._find_in_registry()
        if reg_path and os.path.exists(reg_path):
            return True, reg_path

        # 3. Check system PATH
        which_path = shutil.which("RHI.exe") or shutil.which("RHI")
        if which_path and os.path.exists(which_path):
            return True, str(which_path)

        # 4. Check local downloaded cache installer
        if self.setup_exe.exists():
            return True, str(self.setup_exe)

        # 5. Check embedded RHI installer and auto-seed
        embedded_rhi = Path(__file__).resolve().parent.parent / "embedded_components" / "tools" / "RHI-Setup.exe"
        if embedded_rhi.exists():
            try:
                self.setup_exe.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(embedded_rhi, self.setup_exe)
                return True, str(self.setup_exe)
            except Exception:
                return True, str(embedded_rhi)

        return False, ""

    def _find_in_registry(self) -> Optional[str]:
        """Scan Windows Uninstall registry keys for installed RHI path."""
        try:
            import winreg
            roots = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall")
            ]
            for root, sub in roots:
                try:
                    with winreg.OpenKey(root, sub) as key:
                        count = winreg.QueryInfoKey(key)[0]
                        for i in range(count):
                            try:
                                subkey_name = winreg.EnumKey(key, i)
                                with winreg.OpenKey(key, subkey_name) as subkey:
                                    try:
                                        name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                                    except Exception:
                                        continue
                                    s_name = str(name).upper()
                                    if "RHI" in s_name or "RESHADE HDR" in s_name:
                                        try:
                                            loc, _ = winreg.QueryValueEx(subkey, "InstallLocation")
                                            clean_loc = str(loc).strip('"\'')
                                            exe_path = Path(clean_loc) / "RHI.exe"
                                            if exe_path.exists():
                                                return str(exe_path)
                                        except Exception:
                                            pass
                                        try:
                                            icon, _ = winreg.QueryValueEx(subkey, "DisplayIcon")
                                            clean_icon = Path(str(icon).strip('"\''))
                                            if clean_icon.suffix.lower() == ".exe" and clean_icon.exists():
                                                return str(clean_icon)
                                            elif clean_icon.parent.joinpath("RHI.exe").exists():
                                                return str(clean_icon.parent.joinpath("RHI.exe"))
                                        except Exception:
                                            pass
                            except Exception:
                                pass
                except Exception:
                    pass
        except Exception:
            pass
        return None

    def fetch_rhi_release_info(self) -> Tuple[bool, Dict[str, Any], str]:
        """Fetch latest RHI release info from GitHub API."""
        return http_get_json(RHI_REPO_API, timeout=12)

    def download_rhi(self, mirror_prefix: Optional[str] = None, progress_cb: Optional[Any] = None) -> Tuple[bool, str]:
        """Download latest RHI-Setup.exe from GitHub releases with mirror support."""
        ok, data, err = self.fetch_rhi_release_info()
        if not ok or not data:
            return False, f"获取 RHI 版本信息失败: {err}"

        assets = data.get("assets", [])
        setup_asset = None
        for a in assets:
            if a.get("name", "").lower().endswith(".exe"):
                setup_asset = a
                break

        if not setup_asset:
            return False, "未能找到 RHI 可执行安装包 (.exe) 资产。"

        download_url = setup_asset.get("browser_download_url")
        tag = data.get("tag_name", "latest")

        ok, dl_err = download_file(download_url, str(self.setup_exe), mirror_prefix=mirror_prefix, timeout=60, progress_cb=progress_cb)
        if not ok:
            return False, f"下载 RHI 失败: {dl_err}"

        return True, f"成功下载 RHI ({tag}) 至本地缓存: {self.setup_exe.name}"

    def launch_rhi(self) -> Tuple[bool, str]:
        """Launch RHI-Setup.exe or installed RHI.exe."""
        found, path = self.is_installed_or_cached()
        if not found:
            return False, "未找到 RHI 安装包或系统安装程序，请先在界面中点击【下载 RHI 工具包】。"

        try:
            os.startfile(path)
            return True, f"已成功启动 RHI: {os.path.basename(path)}"
        except Exception:
            try:
                subprocess.Popen([path])
                return True, f"已成功启动 RHI: {os.path.basename(path)}"
            except Exception as e:
                return False, f"启动 RHI 失败: {e}"
