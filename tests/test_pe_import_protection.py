import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import shutil
import tempfile
import pytest
from apps.app2_mfg.core.utils import get_game_statically_imported_dlls, auto_heal_game_dependencies
from apps.app2_mfg.core.state_cleaner import CleanGameDirectoryState

def test_witcher3_and_cp2077_pe_imports():
    w3_dir = Path(r"D:\game\steam\steamapps\common\The Witcher 3\bin\x64_dx12")
    if w3_dir.exists():
        imported = get_game_statically_imported_dlls(w3_dir)
        assert "libxess.dll" in imported
        assert "libxell.dll" in imported
        assert "libxess_fg.dll" in imported

    cp_dir = Path(r"D:\game\steam\steamapps\common\Cyberpunk 2077\bin\x64")
    if cp_dir.exists() and (cp_dir / "Cyberpunk2077.exe").exists():
        imported_cp = get_game_statically_imported_dlls(cp_dir)
        assert "libxess.dll" in imported_cp
        assert "libxell.dll" in imported_cp
        assert "libxess_fg.dll" in imported_cp

def test_auto_heal_dependencies():
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        # Copy a real Witcher 3 or Cyberpunk 2077 executable if available
        w3_exe = Path(r"D:\game\steam\steamapps\common\The Witcher 3\bin\x64_dx12\witcher3.exe")
        if w3_exe.exists():
            shutil.copy2(w3_exe, tdp / "witcher3.exe")
            # Initially missing libxess.dll
            assert not (tdp / "libxess.dll").exists()
            healed = auto_heal_game_dependencies(tdp)
            assert "libxess.dll" in healed
            assert (tdp / "libxess.dll").exists()
            assert (tdp / "libxell.dll").exists()
            assert (tdp / "libxess_fg.dll").exists()

def test_state_cleaner_pe_exemption():
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        w3_exe = Path(r"D:\game\steam\steamapps\common\The Witcher 3\bin\x64_dx12\witcher3.exe")
        if w3_exe.exists():
            shutil.copy2(w3_exe, tdp / "witcher3.exe")
            # Heal dependencies first
            auto_heal_game_dependencies(tdp)
            assert (tdp / "libxess.dll").exists()

            # Clean directory for Mode B
            ok, actions = CleanGameDirectoryState(tdp, target_mode="B", preserve_dlss5=True)
            assert ok
            # PE static imports MUST remain untouched!
            assert (tdp / "libxess.dll").exists()
            assert (tdp / "libxell.dll").exists()
            assert (tdp / "libxess_fg.dll").exists()
