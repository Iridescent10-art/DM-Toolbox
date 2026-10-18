# -*- coding: utf-8 -*-
"""
Entry point for App 1: 全硬件配置大师 (Hardware Master)
"""
import sys
from pathlib import Path

# Ensure root dir is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from main_window import main

if __name__ == "__main__":
    main()
