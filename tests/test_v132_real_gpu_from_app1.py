# -*- coding: utf-8 -*-
"""
Test v1.3.2: Verification of Real GPU Detection via App 1 (CPU/GPU配置管理工具).
Ensures both DLSS 5 (App 6) and Frame Generation (App 2) retrieve the TRUE physical GPU model
from App 1's hardware configuration and backup snapshots, even when the system DriverDesc/WMI
has been spoofed or modified to another model (e.g. RTX 5090).
"""

import sys
import os
import unittest
from pathlib import Path
from unittest.mock import patch

# Setup paths
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "apps" / "app2_mfg"))
sys.path.insert(0, str(ROOT_DIR / "apps" / "app6_dlss5"))

from common.config_manager import get_real_gpu_model, get_real_gpu_info
from apps.app2_mfg.core.utils import get_system_gpu_name, is_rtx_40_or_newer
from apps.app6_dlss5.engine.injector import detect_system_gpu, get_dlss5_runtime_dll_path


class TestRealGpuFromApp1(unittest.TestCase):

    def test_real_gpu_model_retrieval(self):
        """Verify get_real_gpu_model returns real physical card from App 1."""
        real_gpu = get_real_gpu_model()
        self.assertIn("NVIDIA", real_gpu.upper())
        self.assertIn("RTX 4070", real_gpu.upper())

    def test_real_gpu_info_architecture(self):
        """Verify get_real_gpu_info accurately resolves architecture."""
        info = get_real_gpu_info()
        self.assertEqual(info["arch"], "rtx20_30_40")
        self.assertTrue(info["is_nvidia"])
        self.assertTrue(info["is_rtx_40_or_newer"])
        self.assertIn("4070", info["gpu_name"])

    def test_spoofed_driverdesc_does_not_fool_app2(self):
        """Verify App 2 get_system_gpu_name prioritizes App 1 data over spoofed registry."""
        # Even if registry DriverDesc is mocked to RTX 5090
        with patch("winreg.QueryValueEx", return_value=("NVIDIA GeForce RTX 5090", 1)):
            gpu_name = get_system_gpu_name()
            # Must return the REAL GPU from App 1 (RTX 4070)
            self.assertIn("RTX 4070", gpu_name)
            self.assertTrue(is_rtx_40_or_newer(gpu_name))

    def test_spoofed_wmi_does_not_fool_dlss5(self):
        """Verify DLSS 5 detect_system_gpu prioritizes App 1 data over spoofed WMI/PowerShell."""
        # Even if subprocess / WMI returns RTX 5090
        mock_output = "NVIDIA GeForce RTX 5090\n"
        with patch("subprocess.run") as mock_sub:
            mock_sub.return_value.stdout = mock_output
            mock_sub.return_value.returncode = 0
            
            info = detect_system_gpu()
            self.assertIn("RTX 4070", info["gpu_name"])
            self.assertEqual(info["arch"], "rtx20_30_40")
            
            # Runtime DLL path must be the RTX 20/30/40 model, NOT the Blackwell rtx50 model!
            dll_path = get_dlss5_runtime_dll_path(info["arch"])
            self.assertIsNotNone(dll_path)
            self.assertTrue(dll_path.endswith("nvngx_dlssnr_rtx20_30_40.dll"))


if __name__ == "__main__":
    unittest.main()
