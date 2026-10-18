"""
Universal MFG Patcher - Main Program Entrypoint.
Defaults to Modern High-DPI Qt GUI, with fallback to Tkinter.
"""

import sys
from pathlib import Path

# Ensure root directory is on Python search path
sys.path.insert(0, str(Path(__file__).parent))

def run():
    try:
        from gui_qt import main as qt_main
        qt_main()
    except ImportError:
        from gui import launch_gui as tk_main
        tk_main()

if __name__ == "__main__":
    run()
