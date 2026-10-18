# -*- coding: utf-8 -*-
"""Render v1.2.0 screenshots for user verification"""
import os
import sys
from pathlib import Path

# Force UTF-8 for console output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ["QT_QPA_PLATFORM"] = "windows"

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap
from launcher.main import ToolboxLauncher
from apps.app1_hardware.main_window import MainWindow as App1Window
from apps.app2_mfg.gui_qt import ModernMFGGUI as App2Window
from apps.app4_dlss.app import DLSSIndicatorWindow as App4Window
from common.config_manager import set_global_theme

ARTIFACTS_DIR = Path(r"C:\Users\17547\.gemini\antigravity\brain\f20364b0-8af4-45b1-a8b6-b621a086cb69")
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

app = QApplication.instance() or QApplication(sys.argv)

# 1. Render App 4 Light Mode
set_global_theme("light")
win4_light = App4Window()
win4_light.show()
app.processEvents()
pix4_light = win4_light.grab()
pix4_light.save(str(ARTIFACTS_DIR / "verification_v120_app4_light.png"))
print("Saved verification_v120_app4_light.png")
win4_light.close()

# 2. Render App 4 Dark Mode
set_global_theme("dark")
win4_dark = App4Window()
win4_dark.show()
app.processEvents()
pix4_dark = win4_dark.grab()
pix4_dark.save(str(ARTIFACTS_DIR / "verification_v120_app4_dark.png"))
print("Saved verification_v120_app4_dark.png")
win4_dark.close()

# 3. Render Launcher Light Mode
set_global_theme("light")
win_launcher = ToolboxLauncher()
win_launcher.show()
app.processEvents()
pix_launcher = win_launcher.grab()
pix_launcher.save(str(ARTIFACTS_DIR / "verification_v120_launcher.png"))
print("Saved verification_v120_launcher.png")
win_launcher.close()

# 4. Render App 1 Light Mode
win_app1 = App1Window()
win_app1.show()
app.processEvents()
pix_app1 = win_app1.grab()
pix_app1.save(str(ARTIFACTS_DIR / "verification_v120_app1.png"))
print("Saved verification_v120_app1.png")
win_app1.close()

# 5. Render App 2 Light Mode
win_app2 = App2Window()
win_app2.show()
app.processEvents()
pix_app2 = win_app2.grab()
pix_app2.save(str(ARTIFACTS_DIR / "verification_v120_app2.png"))
print("Saved verification_v120_app2.png")
win_app2.close()

print("ALL SCREENSHOTS RENDERED SUCCESSFULLY!")
