# -*- coding: utf-8 -*-

"""

Test Suite v136 - Universal MFG Patcher Mirror Speed Testing & RHI GitHub Sync Integration

"""



import os

import sys

import tempfile

import unittest

from pathlib import Path



# Add project root to sys.path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:

    sys.path.insert(0, str(PROJECT_ROOT))

app2_dir = PROJECT_ROOT / "apps" / "app2_mfg"

if str(app2_dir) not in sys.path:

    sys.path.insert(0, str(app2_dir))



from PySide6.QtWidgets import QApplication

from apps.app2_mfg.core.models import BackendType

from apps.app2_mfg.core.updater import ComponentUpdater, UPSTREAM_REPOS, MIRROR_SOURCES, DEFAULT_MIRRORS

from common.app_updater import MirrorSpeedTestWorker

from apps.app2_mfg.gui_qt import ModernMFGGUI





class TestMFGMirrorSpeedTestAndRHI(unittest.TestCase):

    @classmethod

    def setUpClass(cls):

        cls.app = QApplication.instance()

        if not cls.app:

            cls.app = QApplication([])



    def test_01_backend_type_and_mode_order(self):

        """Verify BackendType definitions and Mode C / Mode D order."""

        self.assertEqual(BackendType.STANDALONE.value, "dashdogy")

        self.assertEqual(BackendType.RESHADE_ADDON.value, "mavismmg")

        self.assertEqual(BackendType.DLSSG_SM86.value, "dlssg_sm86")

        self.assertEqual(BackendType.OPTISCALER_FSR.value, "optiscaler")

        self.assertEqual(BackendType.RHI.value, "rhi")



    def test_02_upstream_repos_contain_all_5_components(self):

        """Verify all 4 frame gen modes + RHI are mapped to upstream GitHub repos."""

        self.assertIn(BackendType.STANDALONE, UPSTREAM_REPOS)

        self.assertIn("dashdogy/MFG-Unlocker", UPSTREAM_REPOS[BackendType.STANDALONE][0])



        self.assertIn(BackendType.RESHADE_ADDON, UPSTREAM_REPOS)

        self.assertIn("mavismmg/MFGAdaUnlock-RenoDx", UPSTREAM_REPOS[BackendType.RESHADE_ADDON][0])



        self.assertIn(BackendType.DLSSG_SM86, UPSTREAM_REPOS)

        self.assertIn("sdli1995/dlssg_for_sm86", UPSTREAM_REPOS[BackendType.DLSSG_SM86][0])



        self.assertIn(BackendType.OPTISCALER_FSR, UPSTREAM_REPOS)

        self.assertTrue(any("optiscaler" in url for url in UPSTREAM_REPOS[BackendType.OPTISCALER_FSR]))



        self.assertIn(BackendType.RHI, UPSTREAM_REPOS)

        self.assertIn("RankFTW/RHI", UPSTREAM_REPOS[BackendType.RHI][0])



    def test_03_mirror_sources_structure(self):

        """Verify MIRROR_SOURCES has auto, ghproxy_com, ghfast, ghproxy_net, direct."""

        mirror_ids = [m["id"] for m in MIRROR_SOURCES]

        self.assertIn("auto", mirror_ids)

        self.assertIn("ghproxy_com", mirror_ids)

        self.assertIn("ghfast", mirror_ids)

        self.assertIn("ghproxy_net", mirror_ids)

        self.assertIn("direct", mirror_ids)



    def test_04_rhi_caching_and_registry(self):

        """Test RHI caching to tools/RHI-Setup.exe and registry recording."""

        with tempfile.TemporaryDirectory() as tmp_dir:

            updater = ComponentUpdater(cache_dir=tmp_dir)
            updater._find_embedded_dir = lambda: None

            fake_rhi_release = {

                "tag_name": "RHI-2.8.7",

                "assets": [

                    {

                        "name": "RHI-Setup.exe",

                        "browser_download_url": "https://example.com/fake-RHI-Setup.exe"

                    }

                ]

            }



            # Mock download_file

            import apps.app2_mfg.core.updater as upd_mod

            orig_download = upd_mod.download_file

            try:

                def fake_dl(url, dest, mirror_prefix=None, timeout=30, progress_cb=None):

                    Path(dest).parent.mkdir(parents=True, exist_ok=True)

                    Path(dest).write_bytes(b"MZ_FAKE_RHI_SETUP_EXE_DATA")

                    return True, ""



                upd_mod.download_file = fake_dl

                ok, msg = updater.download_and_cache(BackendType.RHI, fake_rhi_release)

                self.assertTrue(ok, f"Caching failed: {msg}")



                # Check on disk

                target_exe = Path(tmp_dir) / "tools" / "RHI-Setup.exe"

                self.assertTrue(target_exe.exists())



                # Check registry

                reg = updater.load_registry()

                self.assertIn("rhi", reg)

                self.assertEqual(reg["rhi"]["latest_tag"], "RHI-2.8.7")

                self.assertIn("RHI-2.8.7", reg["rhi"]["cached_versions"])



                # Check get_latest_cached_file

                f_path = updater.get_latest_cached_file(BackendType.RHI)

                self.assertIsNotNone(f_path)

                self.assertTrue(Path(f_path).exists())

            finally:

                upd_mod.download_file = orig_download



    def test_05_gui_card4_mirror_and_speed_test_widgets(self):

        """Verify Card 4 UI has combo_mirror with MIRROR_SOURCES, btn_speed_test, and status label."""

        gui = ModernMFGGUI()

        try:

            self.assertTrue(hasattr(gui, "combo_mirror"))

            self.assertTrue(hasattr(gui, "btn_speed_test"))

            self.assertTrue(hasattr(gui, "lbl_mirror_status"))



            # Verify combo_mirror items

            combo_ids = [gui.combo_mirror.itemData(i) for i in range(gui.combo_mirror.count())]

            self.assertEqual(combo_ids[0], "auto")

            self.assertIn("ghproxy_com", combo_ids)

            self.assertIn("direct", combo_ids)



            # Check button text

            self.assertEqual(gui.btn_speed_test.text(), "⚡ 重新测速")



            # Check effective mirror prefix

            gui.best_mirror_id = "ghproxy_com"

            gui.combo_mirror.setCurrentIndex(0)  # auto

            prefix = gui.get_effective_mirror_prefix()

            self.assertEqual(prefix, "https://gh-proxy.com/")



            # Switch to direct

            idx_direct = gui.combo_mirror.findData("direct")

            gui.combo_mirror.setCurrentIndex(idx_direct)

            prefix_direct = gui.get_effective_mirror_prefix()

            self.assertEqual(prefix_direct, "")



            # Test speed test finished handler simulation

            fake_results = {

                "ghproxy_com": {"latency": 350, "ok": True},

                "ghfast": {"latency": 480, "ok": True},

                "direct": {"latency": 800, "ok": True}

            }

            gui._on_speed_test_finished(fake_results, "ghproxy_com")

            gui.combo_mirror.setCurrentIndex(0)  # auto

            self.assertIn("GH-Proxy", gui.lbl_mirror_status.text())

            self.assertIn("350ms", gui.lbl_mirror_status.text())



            # Test cache status includes RHI

            gui._load_cache_status()

            summary_text = gui.lbl_cache_summary.text()

            self.assertIn("Standalone", summary_text)

            self.assertIn("ReShade", summary_text)

            self.assertIn("DLSSG-SM86", summary_text)

            self.assertIn("OptiScaler", summary_text)

            self.assertIn("RHI", summary_text)



        finally:

            gui.close()



    def test_06_clean_nvidia_streamline_dumps(self):

        """Verify clean_nvidia_streamline_dumps removes dumps and calculates freed space."""

        from apps.app2_mfg.core.state_cleaner import clean_nvidia_streamline_dumps

        with tempfile.TemporaryDirectory() as tmp_pd:

            sl_dir = Path(tmp_pd) / "NVIDIA" / "Streamline" / "test_game"

            sl_dir.mkdir(parents=True)

            dummy_dmp = sl_dir / "sl-test.dmp"

            dummy_dmp.write_bytes(b"X" * (1024 * 1024 * 5))  # 5MB dummy dump



            # Patch ProgramData environment variable

            old_pd = os.environ.get("ProgramData")

            try:

                os.environ["ProgramData"] = tmp_pd

                actions = clean_nvidia_streamline_dumps("test_game")

                self.assertTrue(any("test_game" in a and "5.0 MB" in a for a in actions))

                self.assertFalse(sl_dir.exists())

            finally:

                if old_pd:

                    os.environ["ProgramData"] = old_pd

                else:

                    os.environ.pop("ProgramData", None)





if __name__ == "__main__":

    unittest.main()

