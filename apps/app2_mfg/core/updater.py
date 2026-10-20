"""
Universal MFG Patcher - Cloud Synchronization and Component Hot-Updater.
"""

import os
import zipfile
import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from core.models import BackendType
from core.utils import http_get_json, download_file, calculate_sha256, get_app_cache_dir

OPTISCALER_CHANNELS = {
    "nightly": "https://api.github.com/repos/optiscaler/OptiScaler-nightly/releases?per_page=1",
    "stable": "https://api.github.com/repos/optiscaler/OptiScaler/releases/latest"
}

UPSTREAM_REPOS = {
    BackendType.STANDALONE: [
        "https://api.github.com/repos/dashdogy/MFG-Unlocker/releases/latest",
        "https://api.github.com/repos/dashdogy/RTX40MFG-Unlock/releases/latest"
    ],
    BackendType.RESHADE_ADDON: [
        "https://api.github.com/repos/mavismmg/MFGAdaUnlock-RenoDx/releases/latest"
    ],
    BackendType.OPTISCALER_FSR: [
        "https://api.github.com/repos/optiscaler/OptiScaler-nightly/releases?per_page=1",
        "https://api.github.com/repos/optiscaler/OptiScaler/releases/latest"
    ]
}

DEFAULT_MIRRORS = {
    "Direct (GitHub)": "",
    "GHProxy": "https://ghproxy.net/",
    "GHFast": "https://ghfast.top/"
}

class ComponentUpdater:
    def __init__(self, cache_dir: Optional[str] = None, legacy_root_dir: Optional[str] = None):
        if cache_dir is not None:
            c_path = Path(cache_dir)
            # If software root directory was passed, do NOT store cache there
            if (c_path / "gui_qt.py").exists() or (c_path / "main.py").exists() or c_path.name.lower() in ["多帧生成", "dist"]:
                legacy_root_dir = str(c_path)
                self.cache_dir = get_app_cache_dir()
            elif c_path.name.lower() == "cache" and ((c_path.parent / "gui_qt.py").exists() or (c_path.parent / "main.py").exists()):
                legacy_root_dir = str(c_path.parent)
                self.cache_dir = get_app_cache_dir()
            else:
                self.cache_dir = c_path
        else:
            self.cache_dir = get_app_cache_dir()

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.versions_file = self.cache_dir / "versions.json"

        # Migrate legacy cache out of software root
        if legacy_root_dir:
            self._migrate_legacy_cache(Path(legacy_root_dir) / "cache")
        # Ensure embedded components are seeded into cache and registry is fully synced
        self._seed_from_embedded()
        self._ensure_registry()
        self._sync_registry_from_disk()

    def _find_embedded_dir(self) -> Optional[Path]:
        """Locates embedded_components folder from multiple potential locations."""
        candidates = [
            Path(__file__).resolve().parent.parent / "embedded_components",
            Path(__file__).resolve().parent.parent.parent.parent / "defaults" / "app2_mfg" / "embedded_components",
            Path(__file__).resolve().parent.parent.parent.parent / "apps" / "app2_mfg" / "embedded_components",
        ]
        for c in candidates:
            if c.exists() and (c / "dashdogy").exists():
                return c
        return None

    def _seed_from_embedded(self):
        """Auto-seed embedded 3 models and tools into cache and synchronize registry."""
        embedded_dir = self._find_embedded_dir()
        if not embedded_dir or not embedded_dir.exists():
            return

        try:
            # 1. Copy directory trees (dashdogy, mavismmg, optiscaler, tools) if not present
            for item in embedded_dir.iterdir():
                if item.name == "versions.json":
                    continue
                target = self.cache_dir / item.name
                if not target.exists():
                    if item.is_dir():
                        shutil.copytree(item, target)
                    elif item.is_file():
                        shutil.copy2(item, target)
                else:
                    if item.is_dir():
                        for sub_f in item.rglob("*"):
                            if sub_f.is_file():
                                rel = sub_f.relative_to(item)
                                target_f = target / rel
                                if not target_f.exists():
                                    target_f.parent.mkdir(parents=True, exist_ok=True)
                                    shutil.copy2(sub_f, target_f)

            # 2. Merge/seed versions.json from embedded versions.json
            emb_versions_f = embedded_dir / "versions.json"
            reg = self.load_registry() if self.versions_file.exists() else {}
            dirty = False

            if emb_versions_f.exists():
                try:
                    with open(emb_versions_f, "r", encoding="utf-8") as f:
                        emb_data = json.load(f)
                    for b_name, b_info in emb_data.items():
                        if b_name not in reg or not reg[b_name].get("cached_versions"):
                            reg[b_name] = b_info
                            dirty = True
                        else:
                            cached = reg[b_name].setdefault("cached_versions", {})
                            for tag, tag_info in b_info.get("cached_versions", {}).items():
                                if tag not in cached:
                                    cached[tag] = tag_info
                                    dirty = True
                            if not reg[b_name].get("latest_tag") and b_info.get("latest_tag"):
                                reg[b_name]["latest_tag"] = b_info.get("latest_tag")
                                dirty = True
                except Exception:
                    pass

            # 3. Fixup local paths to match current user's cache_dir
            for b_name, b_data in reg.items():
                cached = b_data.get("cached_versions", {})
                for tag, info in cached.items():
                    expected = self.cache_dir / b_name / tag / info.get("file", "")
                    if expected.exists():
                        if info.get("path") != str(expected):
                            info["path"] = str(expected)
                            dirty = True
                        if "dir" in info and info.get("dir") != str(expected.parent):
                            info["dir"] = str(expected.parent)
                            dirty = True

            if dirty or not self.versions_file.exists():
                self.save_registry(reg)

        except Exception:
            pass

    def _sync_registry_from_disk(self):
        """
        Deep-scans cache_dir and registers all discovered backend versions on disk.
        Auto-recovers from corrupted/empty registry or manual folder installations.
        """
        reg = self.load_registry()
        dirty = False

        backends_map = {
            BackendType.STANDALONE.value: {
                "file_patterns": ["MFGUnlocker.dll", "*.dll"],
                "default_name": "MFGUnlocker.dll"
            },
            BackendType.RESHADE_ADDON.value: {
                "file_patterns": ["renodx-mfgunlock.addon64", "*.addon64"],
                "default_name": "renodx-mfgunlock.addon64"
            },
            BackendType.OPTISCALER_FSR.value: {
                "file_patterns": ["OptiScaler.dll"],
                "default_name": "OptiScaler.dll"
            },
            "reshade": {
                "file_patterns": ["ReShade64.dll", "*.dll"],
                "default_name": "ReShade64.dll"
            }
        }

        for b_name, b_cfg in backends_map.items():
            if b_name not in reg:
                reg[b_name] = {"latest_tag": None, "cached_versions": {}}
            b_dir = self.cache_dir / b_name
            if not b_dir.exists() or not b_dir.is_dir():
                continue

            for tag_folder in b_dir.iterdir():
                if not tag_folder.is_dir():
                    continue
                tag_name = tag_folder.name
                matched_file = None
                for pat in b_cfg["file_patterns"]:
                    candidates = list(tag_folder.glob(pat))
                    if candidates:
                        matched_file = candidates[0]
                        break

                if matched_file and matched_file.exists():
                    cached = reg[b_name].setdefault("cached_versions", {})
                    if tag_name not in cached or cached[tag_name].get("path") != str(matched_file):
                        info = {
                            "file": matched_file.name,
                            "path": str(matched_file),
                            "sha256": calculate_sha256(str(matched_file))
                        }
                        if b_name == BackendType.OPTISCALER_FSR.value:
                            info["dir"] = str(tag_folder)
                        cached[tag_name] = info
                        dirty = True

            cached = reg[b_name].get("cached_versions", {})
            current_tag = reg[b_name].get("latest_tag")
            if (not current_tag or current_tag not in cached) and cached:
                reg[b_name]["latest_tag"] = list(cached.keys())[-1]
                dirty = True

        if dirty:
            self.save_registry(reg)

    def _migrate_legacy_cache(self, legacy_cache: Path):
        """Move legacy cache files out of software root into AppData cache."""
        try:
            if legacy_cache.exists() and legacy_cache.is_dir():
                resolved_legacy = legacy_cache.resolve()
                resolved_target = self.cache_dir.resolve()
                if resolved_legacy != resolved_target:
                    for item in legacy_cache.iterdir():
                        dest = self.cache_dir / item.name
                        if item.is_dir():
                            if not dest.exists():
                                shutil.copytree(item, dest)
                            else:
                                for sub_root, _, files in os.walk(item):
                                    rel = os.path.relpath(sub_root, item)
                                    target_sub = dest / rel
                                    target_sub.mkdir(parents=True, exist_ok=True)
                                    for f in files:
                                        tf = target_sub / f
                                        if not tf.exists():
                                            shutil.copy2(os.path.join(sub_root, f), tf)
                        elif item.is_file():
                            if not dest.exists():
                                shutil.copy2(item, dest)
                    # Remove the old cache from the software root directory
                    shutil.rmtree(legacy_cache, ignore_errors=True)
        except Exception as e:
            pass

    def get_cache_size_bytes(self) -> int:
        """Calculate total bytes occupied by cache directory."""
        total = 0
        if self.cache_dir.exists():
            for root, _, files in os.walk(self.cache_dir):
                for f in files:
                    try:
                        total += os.path.getsize(os.path.join(root, f))
                    except Exception:
                        pass
        return total

    def clear_cache(self) -> Tuple[bool, str, int]:
        """
        Deletes all cached components, downloaded files, and resets versions registry.
        Then automatically restores the built-in 3 core models from embedded assets.
        Returns (success, message, freed_bytes).
        """
        freed = self.get_cache_size_bytes()
        try:
            if self.cache_dir.exists():
                for item in self.cache_dir.iterdir():
                    if item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                    elif item.is_file():
                        try:
                            item.unlink()
                        except Exception:
                            pass
            self._seed_from_embedded()
            self._ensure_registry()
            self._sync_registry_from_disk()
            freed_mb = freed / (1024 * 1024)
            return True, f"本地缓存已完全重置，已自动恢复内置 3 大核心组件！", freed
        except Exception as e:
            return False, f"重置缓存失败: {e}", 0

    def _ensure_registry(self):
        if not self.versions_file.exists():
            initial_data = {
                BackendType.STANDALONE: {"latest_tag": None, "cached_versions": {}},
                BackendType.RESHADE_ADDON: {"latest_tag": None, "cached_versions": {}},
                BackendType.OPTISCALER_FSR: {"latest_tag": None, "cached_versions": {}}
            }
            with open(self.versions_file, "w", encoding="utf-8") as f:
                json.dump(initial_data, f, indent=2)

    def load_registry(self) -> Dict[str, Any]:
        try:
            with open(self.versions_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {
                BackendType.STANDALONE: {"latest_tag": None, "cached_versions": {}},
                BackendType.RESHADE_ADDON: {"latest_tag": None, "cached_versions": {}},
                BackendType.OPTISCALER_FSR: {"latest_tag": None, "cached_versions": {}}
            }

    def save_registry(self, data: Dict[str, Any]):
        with open(self.versions_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def fetch_latest_release_info(self, backend: BackendType, mirror_prefix: Optional[str] = None, channel: Optional[str] = None) -> Tuple[bool, Dict[str, Any], str]:
        """Fetch latest GitHub release metadata (always direct API call)."""
        urls = UPSTREAM_REPOS.get(backend, [])
        if (backend == BackendType.OPTISCALER_FSR or str(backend) == BackendType.OPTISCALER_FSR.value) and channel:
            if channel in OPTISCALER_CHANNELS:
                urls = [OPTISCALER_CHANNELS[channel]]
        last_error = ""
        for url in urls:
            # GitHub API should be called directly, mirror is for asset downloads
            ok, data, err = http_get_json(url, timeout=12, mirror_prefix=None)
            if ok and data:
                if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict) and "tag_name" in data[0]:
                    return True, data[0], ""
                elif isinstance(data, dict) and "tag_name" in data:
                    return True, data, ""
            last_error = err or "Invalid response"
        return False, {}, last_error

    def download_and_cache(self, backend: BackendType, release_data: Dict[str, Any], mirror_prefix: Optional[str] = None, progress_cb: Optional[Any] = None) -> Tuple[bool, str]:
        """
        Download assets from release_data, unpack if zip, verify and register in cache.
        """
        tag_name = release_data.get("tag_name", "unknown")
        assets = release_data.get("assets", [])
        if not assets:
            return False, "Release has no assets."

        target_dir = self.cache_dir / backend.value / tag_name
        target_dir.mkdir(parents=True, exist_ok=True)

        if backend == BackendType.STANDALONE:
            # Look for zip containing DLL or direct DLL asset
            zip_asset = None
            for asset in assets:
                name = asset.get("name", "").lower()
                if name.endswith(".zip"):
                    zip_asset = asset
                    break

            if not zip_asset:
                return False, "Could not find .zip release asset for dashdogy standalone."

            download_url = zip_asset.get("browser_download_url")
            temp_zip = target_dir / "temp_download.zip"
            ok, err = download_file(download_url, str(temp_zip), mirror_prefix=mirror_prefix, progress_cb=progress_cb)
            if not ok:
                return False, f"Failed to download zip: {err}"

            # Extract zip
            try:
                with zipfile.ZipFile(temp_zip, "r") as zf:
                    zf.extractall(target_dir)
            except Exception as e:
                return False, f"Failed to extract zip archive: {e}"
            finally:
                if temp_zip.exists():
                    temp_zip.unlink()

            # Locate MFGUnlocker.dll or RTXMFG.dll
            found_dll = None
            for root, _, files in os.walk(target_dir):
                for f in files:
                    if f.lower() in ["mfgunlocker.dll", "rtxmfg.dll"]:
                        found_dll = Path(root) / f
                        break
                if found_dll:
                    break

            if not found_dll:
                return False, "Archive did not contain MFGUnlocker.dll or RTXMFG.dll"

            final_dll = target_dir / "MFGUnlocker.dll"
            if found_dll != final_dll:
                shutil.copy2(found_dll, final_dll)

            sha256 = calculate_sha256(str(final_dll))
            reg = self.load_registry()
            reg[backend.value]["latest_tag"] = tag_name
            reg[backend.value]["cached_versions"][tag_name] = {
                "file": "MFGUnlocker.dll",
                "path": str(final_dll),
                "sha256": sha256
            }
            self.save_registry(reg)
            return True, f"Successfully cached {backend.value} {tag_name} ({sha256[:8]})"

        elif backend == BackendType.RESHADE_ADDON:
            # Look for renodx-mfgunlock.addon64
            addon_asset = None
            for asset in assets:
                name = asset.get("name", "").lower()
                if name.endswith(".addon64") or "addon" in name:
                    addon_asset = asset
                    break

            if not addon_asset:
                return False, "Could not find .addon64 release asset for mavismmg."

            download_url = addon_asset.get("browser_download_url")
            final_addon = target_dir / "renodx-mfgunlock.addon64"
            ok, err = download_file(download_url, str(final_addon), mirror_prefix=mirror_prefix, progress_cb=progress_cb)
            if not ok:
                return False, f"Failed to download addon: {err}"

            sha256 = calculate_sha256(str(final_addon))
            reg = self.load_registry()
            reg[backend.value]["latest_tag"] = tag_name
            reg[backend.value]["cached_versions"][tag_name] = {
                "file": "renodx-mfgunlock.addon64",
                "path": str(final_addon),
                "sha256": sha256
            }
            self.save_registry(reg)
            return True, f"Successfully cached {backend.value} {tag_name} ({sha256[:8]})"

        elif backend == BackendType.OPTISCALER_FSR or str(backend) == BackendType.OPTISCALER_FSR.value or (hasattr(backend, "value") and backend.value == BackendType.OPTISCALER_FSR.value):
            archive_asset = None
            for asset in assets:
                name = asset.get("name", "").lower()
                if name.endswith(".7z") or name.endswith(".zip"):
                    archive_asset = asset
                    break

            if not archive_asset:
                return False, "未能找到 OptiScaler 发布资产 (.7z / .zip)。"

            download_url = archive_asset.get("browser_download_url")
            asset_name = archive_asset.get("name", "optiscaler.7z")
            temp_archive = target_dir / asset_name

            ok, err = download_file(download_url, str(temp_archive), mirror_prefix=mirror_prefix, progress_cb=progress_cb)
            if not ok:
                return False, f"下载 OptiScaler 资产失败: {err}"

            # Extract archive using bsdtar
            try:
                if temp_archive.suffix.lower() == ".zip":
                    with zipfile.ZipFile(temp_archive, "r") as zf:
                        zf.extractall(target_dir)
                else:
                    res = subprocess.run(["tar.exe", "-xf", str(temp_archive), "-C", str(target_dir)], capture_output=True)
                    if res.returncode != 0:
                        return False, f"解压 OptiScaler 归档失败: {res.stderr.decode('utf-8', errors='ignore')}"
            except Exception as e:
                return False, f"解压 OptiScaler 过程异常: {e}"
            finally:
                if temp_archive.exists():
                    try:
                        temp_archive.unlink()
                    except Exception:
                        pass

            # Locate OptiScaler.dll
            found_dll = None
            for root, _, files in os.walk(target_dir):
                for f in files:
                    if f.lower() == "optiscaler.dll":
                        found_dll = Path(root) / f
                        break
                if found_dll:
                    break

            if not found_dll:
                return False, "OptiScaler 资产归档中未找到 OptiScaler.dll！"

            b_key = BackendType.OPTISCALER_FSR.value
            sha256 = calculate_sha256(str(found_dll))
            reg = self.load_registry()
            if b_key not in reg:
                reg[b_key] = {"latest_tag": None, "cached_versions": {}}
            reg[b_key]["latest_tag"] = tag_name
            reg[b_key]["cached_versions"][tag_name] = {
                "file": "OptiScaler.dll",
                "path": str(found_dll),
                "dir": str(found_dll.parent),
                "sha256": sha256
            }
            self.save_registry(reg)
            return True, f"成功缓存 OptiScaler / FSR 3.1 资产 {tag_name} ({sha256[:8]})"

        return False, "Unsupported backend."

    def get_latest_cached_file(self, backend: BackendType) -> Optional[str]:
        """Returns the local path of the latest cached artifact for the backend."""
        backend_key = backend.value if hasattr(backend, "value") else str(backend)

        # 1. Try registry first
        reg = self.load_registry()
        backend_data = reg.get(backend_key, {})
        latest_tag = backend_data.get("latest_tag")
        if not latest_tag:
            versions = backend_data.get("cached_versions", {})
            if versions:
                latest_tag = list(versions.keys())[-1]

        if latest_tag:
            ver_info = backend_data.get("cached_versions", {}).get(latest_tag, {})
            cached_path = ver_info.get("path")
            if cached_path and os.path.exists(cached_path):
                return cached_path
            filename = ver_info.get("file")
            if filename:
                expected_local = self.cache_dir / backend_key / latest_tag / filename
                if expected_local.exists():
                    ver_info["path"] = str(expected_local)
                    self.save_registry(reg)
                    return str(expected_local)

        # 2. Self-heal via disk sync
        self._seed_from_embedded()
        self._sync_registry_from_disk()
        reg = self.load_registry()
        backend_data = reg.get(backend_key, {})
        latest_tag = backend_data.get("latest_tag")
        if not latest_tag:
            versions = backend_data.get("cached_versions", {})
            if versions:
                latest_tag = list(versions.keys())[-1]

        if latest_tag:
            ver_info = backend_data.get("cached_versions", {}).get(latest_tag, {})
            cached_path = ver_info.get("path")
            if cached_path and os.path.exists(cached_path):
                return cached_path
            filename = ver_info.get("file")
            if filename:
                expected_local = self.cache_dir / backend_key / latest_tag / filename
                if expected_local.exists():
                    ver_info["path"] = str(expected_local)
                    self.save_registry(reg)
                    return str(expected_local)

        # 3. Direct disk scan fallback in cache_dir
        b_dir = self.cache_dir / backend_key
        if b_dir.exists():
            for f in b_dir.rglob("*.dll"):
                if backend_key == BackendType.STANDALONE.value and "mfg" in f.name.lower():
                    return str(f)
                elif backend_key == BackendType.OPTISCALER_FSR.value and "optiscaler.dll" == f.name.lower():
                    return str(f)
            for f in b_dir.rglob("*.addon64"):
                if backend_key == BackendType.RESHADE_ADDON.value:
                    return str(f)

        # 4. Embedded fallback: search embedded_components directly
        emb_dir = self._find_embedded_dir()
        if emb_dir and emb_dir.exists():
            emb_b_dir = emb_dir / backend_key
            if emb_b_dir.exists():
                for ef in emb_b_dir.rglob("*"):
                    if ef.is_file():
                        if backend_key == BackendType.STANDALONE.value and ef.suffix.lower() == ".dll":
                            return str(ef)
                        elif backend_key == BackendType.RESHADE_ADDON.value and ef.suffix.lower() == ".addon64":
                            return str(ef)
                        elif backend_key == BackendType.OPTISCALER_FSR.value and ef.name.lower() == "optiscaler.dll":
                            return str(ef)

        return None

    def get_latest_cached_dir(self, backend: BackendType) -> Optional[str]:
        """Returns the folder containing the cached backend assets."""
        f = self.get_latest_cached_file(backend)
        if f and os.path.exists(f):
            return os.path.dirname(f)
        return None

    def get_reshade_framework_dll(self) -> Optional[str]:
        """
        Locates and returns the official ReShade64.dll path with full Add-on Support.
        Multi-tier discovery with auto-caching:
        1. Local cache directory (cache_dir / reshade / 6.8.0 / ReShade64.dll or any cached version)
        2. Embedded components directory (embedded_components / reshade / 6.8.0 / ReShade64.dll)
        3. Auto-extraction from system %LocalAppData%\\RHI cache
        When discovered from external sources, automatically copies to cache and updates registry.
        """
        # Tier 1: Local cache
        reshade_cache = self.cache_dir / "reshade"
        if reshade_cache.exists():
            for f in reshade_cache.rglob("ReShade64.dll"):
                if f.is_file() and f.stat().st_size > 4 * 1024 * 1024:
                    return str(f)

        # Tier 2: Embedded components
        emb = self._find_embedded_dir()
        if emb and emb.exists():
            for ef in emb.rglob("ReShade64.dll"):
                if ef.is_file() and ef.stat().st_size > 4 * 1024 * 1024:
                    dest = self.cache_dir / "reshade" / "6.8.0" / "ReShade64.dll"
                    try:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(ef, dest)
                        return str(dest)
                    except Exception:
                        return str(ef)

        # Tier 3: System %LocalAppData%\RHI cache
        local_app = os.environ.get("LOCALAPPDATA", "")
        if local_app:
            rhi_candidates = [
                Path(local_app) / "RHI" / "reshade" / "ReShade64.dll",
                Path(local_app) / "RHI" / "reshade-nightly" / "ReShade64.dll",
                Path(local_app) / "RHI" / "reshade-normal" / "ReShade64.dll",
            ]
            for cand in rhi_candidates:
                if cand.exists() and cand.stat().st_size > 4 * 1024 * 1024:
                    dest = self.cache_dir / "reshade" / "6.8.0" / "ReShade64.dll"
                    try:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(cand, dest)
                        if emb and emb.exists():
                            emb_dest = emb / "reshade" / "6.8.0" / "ReShade64.dll"
                            emb_dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(cand, emb_dest)
                        return str(dest)
                    except Exception:
                        return str(cand)

        return None

