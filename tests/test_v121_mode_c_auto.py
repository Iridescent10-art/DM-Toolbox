import os
import sys
from pathlib import Path

ROOT_DIR = Path(r"d:\AI\整合包")
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "apps" / "app2_mfg"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from apps.app2_mfg.gui_qt import ModernMFGGUI, OptiScalerPresetDialog

def run_verification():
    app = QApplication.instance() or QApplication(sys.argv)
    
    # 1. Main Window
    w = ModernMFGGUI()
    w.show()
    app.processEvents()
    
    summary_text = w.lbl_preset_summary.text()
    assert "自动继承游戏内超分" in summary_text, f"Main summary missing '自动继承游戏内超分': {summary_text}"
    assert "XeSS 2.0 AI 超分" not in summary_text, f"Main summary still has 'XeSS 2.0 AI 超分': {summary_text}"
    
    artifact_dir = Path(r"C:\Users\17547\.gemini\antigravity\brain\f20364b0-8af4-45b1-a8b6-b621a086cb69")
    pix_main = w.grab()
    pix_main.save(str(artifact_dir / "verification_mode_c_summary_main.png"))
    print("Main window verified and saved!")
    
    # 2. Preset Dialog Tab C
    dlg = OptiScalerPresetDialog(w, is_dark=False, game=w.selected_game)
    dlg.switch_preset_tab(2)
    dlg.show()
    app.processEvents()
    
    assert dlg.combo_upscaler.currentData() == "auto", f"Expected 'auto', got {dlg.combo_upscaler.currentData()}"
    assert "Auto (自动继承游戏内设定)" in dlg.combo_upscaler.currentText()
    
    pix_dlg = dlg.grab()
    pix_dlg.save(str(artifact_dir / "verification_mode_c_dialog_tab_c.png"))
    print("Preset dialog verified and saved!")
    
    w.close()
    dlg.close()
    print("All tests passed 100%!")

if __name__ == "__main__":
    run_verification()
