"""
Universal MFG Patcher - Data models and schemas.
"""

from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
import json
import time

class BackendType(str, Enum):
    STANDALONE = "dashdogy"          # Standalone Proxy DLL (MFGUnlocker.dll)
    RESHADE_ADDON = "mavismmg"       # ReShade Addon (renodx-mfgunlock.addon64)
    DLSSG_SM86 = "dlssg_sm86"        # Mode C: DLSSG for SM86/SM75 Native DLSS-G (RTX 20/30 series)
    OPTISCALER_FSR = "optiscaler"    # Mode D: OptiScaler / FSR 3.1 Bridge (for 20/30 series & universal)
    SMART_AUTO = "smart_auto"        # Auto detect best backend
    RHI = "rhi"                      # ReShade HDR Installer (RankFTW/RHI)

class QualificationStatus(str, Enum):
    QUALIFIED = "QUALIFIED"          # Has sl.interposer.dll and nvngx_dlssg.dll
    MISSING_DLSSG = "MISSING_DLSSG"  # Streamline detected but nvngx_dlssg missing
    NOT_SUPPORTED = "NOT_SUPPORTED"  # No Streamline integration found

@dataclass
class GameInfo:
    name: str
    source: str                      # "Steam", "Epic", "GOG", "Custom"
    install_dir: str
    target_dir: str                  # Directory where real shipping exe is located
    exe_path: str                    # Full path to game executable
    exe_name: str
    qualification: QualificationStatus
    streamline_ver: Optional[str] = None
    dlssg_ver: Optional[str] = None
    has_reshade: bool = False
    is_patched: bool = False
    patched_backend: Optional[str] = None
    installed_version: Optional[str] = None
    is_running: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if isinstance(self.qualification, QualificationStatus):
            d["qualification"] = self.qualification.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GameInfo":
        d = dict(data)
        if "qualification" in d and isinstance(d["qualification"], str):
            try:
                d["qualification"] = QualificationStatus(d["qualification"])
            except Exception:
                d["qualification"] = QualificationStatus.NOT_SUPPORTED
        valid_keys = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in d.items() if k in valid_keys}
        return cls(**filtered)


@dataclass
class RenameRecord:
    original: str
    backup: str


@dataclass
class IniRecord:
    file: str
    section: str
    key: str
    value_added: str


@dataclass
class PatchManifest:
    app_version: str = "1.0.0"
    game_name: str = ""
    target_exe: str = ""
    target_dir: str = ""
    active_backend: str = ""
    installed_version: str = ""
    patch_timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    created_files: List[str] = field(default_factory=list)
    renamed_backups: List[Dict[str, str]] = field(default_factory=list)
    ini_modifications: List[Dict[str, str]] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, data: str) -> "PatchManifest":
        d = json.loads(data)
        return cls(**d)
