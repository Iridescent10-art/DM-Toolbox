# -*- coding: utf-8 -*-
"""
Entry point for App 2: DLSS多帧生成补丁 (Universal MFG Patcher)
"""
import sys
from pathlib import Path

# Ensure root dir and app dir are in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

# Initialize config from defaults
try:
    from common.config_manager import init_app_config
    defaults_template = ROOT_DIR / "defaults" / "app2_mfg" / "settings.json"
    init_app_config("app2_mfg", "settings.json", default_template_path=defaults_template)
except Exception:
    pass

from gui_qt import main

if __name__ == "__main__":
    main()
