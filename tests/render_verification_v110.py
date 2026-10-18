import os
import sys
from pathlib import Path

# Add app paths
base_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(base_dir / "apps" / "app2_mfg"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer
from gui_qt import ModernMFGGUI, OptiScalerPresetDialog
from core.models import GameInfo, QualificationStatus

app = QApplication.instance() or QApplication(sys.argv)

output_dir = Path(r"C:\Users\17547\.gemini\antigravity\brain\08a92d93-f2ef-4b23-aef8-8b59c8d5b3cd")
output_dir.mkdir(parents=True, exist_ok=True)

# 1. Render Preset Dialog in Light Mode (Tab 1 & Tab 2)
dlg_light = OptiScalerPresetDialog(is_dark=False)
dlg_light.show()
app.processEvents()

# Tab 1 Mode C
dlg_light.tab_widget.setCurrentIndex(0)
app.processEvents()
pix_l_t1 = dlg_light.grab()
pix_l_t1.save(str(output_dir / "preset_dialog_v110_light_tab1.png"))

# Tab 2 Mode B
dlg_light.tab_widget.setCurrentIndex(1)
app.processEvents()
pix_l_t2 = dlg_light.grab()
pix_l_t2.save(str(output_dir / "preset_dialog_v110_light_tab2.png"))
dlg_light.close()

# 2. Render Preset Dialog in Dark Mode (Tab 1 & Tab 2)
dlg_dark = OptiScalerPresetDialog(is_dark=True)
dlg_dark.show()
app.processEvents()

# Tab 1 Mode C
dlg_dark.tab_widget.setCurrentIndex(0)
app.processEvents()
pix_d_t1 = dlg_dark.grab()
pix_d_t1.save(str(output_dir / "preset_dialog_v110_dark_tab1.png"))

# Tab 2 Mode B
dlg_dark.tab_widget.setCurrentIndex(1)
app.processEvents()
pix_d_t2 = dlg_dark.grab()
pix_d_t2.save(str(output_dir / "preset_dialog_v110_dark_tab2.png"))
dlg_dark.close()

# 3. Render Main Window with RHI page (showing live ecosystem card)
win = ModernMFGGUI()
win.show()
app.processEvents()

# Switch to RHI page (index 3)
win.switch_page(3)
app.processEvents()
pix_rhi = win.grab()
pix_rhi.save(str(output_dir / "main_window_v110_rhi_page.png"))

# Switch to Dashboard (index 0) with Mode B selected
win.switch_page(0)
# Select Mode B in combo
idx_b = win.combo_backend.findData("mavismmg")
if idx_b >= 0:
    win.combo_backend.setCurrentIndex(idx_b)
app.processEvents()
pix_dash = win.grab()
pix_dash.save(str(output_dir / "main_window_v110_mode_b_dash.png"))

win.close()
print("All verification screenshots successfully rendered!")
