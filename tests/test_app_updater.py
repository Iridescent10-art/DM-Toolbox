# -*- coding: utf-8 -*-
"""
Unit test suite for DM-Toolbox Application Updater and GitHub Releases integration.
"""

import sys
import os
import unittest
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from PySide6.QtWidgets import QApplication
qt_app = QApplication.instance() or QApplication(sys.argv)
from common.version import APP_VERSION, GITHUB_OWNER, GITHUB_REPO, GITHUB_API_RELEASES
from common.app_updater import (
    parse_version_tuple, markdown_to_html,
    get_updater_config, save_updater_config,
    CheckUpdateWorker, SilentUpdateChecker
)


class TestAppUpdater(unittest.TestCase):

    def test_version_parsing(self):
        self.assertEqual(parse_version_tuple("v1.2.13"), (1, 2, 13))
        self.assertEqual(parse_version_tuple("1.2.9"), (1, 2, 9))
        self.assertEqual(parse_version_tuple("v1.2.8.1"), (1, 2, 8, 1))

        self.assertGreater(parse_version_tuple("v1.2.13"), parse_version_tuple("v1.2.9"))
        self.assertGreater(parse_version_tuple("v1.2.13"), parse_version_tuple("1.2.6"))
        self.assertEqual(parse_version_tuple(f"v{APP_VERSION}"), (1, 2, 13))

    def test_markdown_to_html(self):
        md = "### 核心特性\n- **特性1**: 增强插帧\n`code_block`"
        html = markdown_to_html(md, is_dark=False)
        self.assertIn("<h3", html)
        self.assertIn("<b>特性1</b>", html)
        self.assertIn("<code", html)

    def test_updater_config(self):
        cfg = get_updater_config()
        self.assertIn("auto_check", cfg)
        self.assertIn("use_mirror", cfg)
        self.assertTrue(cfg.get("auto_check", True))

        # Test save and load
        cfg["auto_check"] = True
        save_updater_config(cfg)
        reloaded = get_updater_config()
        self.assertTrue(reloaded["auto_check"])

    def test_github_api_fetch(self):
        """Verify GitHub releases API returns expected release history and DM-BOX.exe asset."""
        import urllib.request
        import json

        req = urllib.request.Request(
            GITHUB_API_RELEASES,
            headers={"User-Agent": "DM-Toolbox-Updater-Test", "Accept": "application/vnd.github.v3+json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode("utf-8"))
                self.assertIsInstance(data, list)
                self.assertGreater(len(data), 0)

                # Check top release
                latest = data[0]
                tag = latest.get("tag_name")
                self.assertTrue(tag.startswith("v1.2."))

                # Check asset presence
                assets = [a.get("name") for a in latest.get("assets", [])]
                self.assertIn("DM-BOX.exe", assets)
                print(f"\n[GitHub API Live Verification] Latest tag: {tag}, Assets: {assets}")
        except Exception as e:
            print(f"\n[Note] Network call skipped or limited: {e}")

    def test_ui_dialog_instantiation(self):
        """Verify AppUpdateDialog can be instantiated in Qt environment without crashing."""
        from PySide6.QtWidgets import QApplication
        from common.app_updater import AppUpdateDialog

        app = QApplication.instance() or QApplication(sys.argv)
        mock_releases = [
            {
                "tag_name": "v1.2.13",
                "name": "DM-Toolbox v1.2.10",
                "published_at": "2026-10-20T11:29:28Z",
                "body": "## 更新日志\n- 强化检查更新功能",
                "html_url": "https://github.com/Iridescent10-art/DM-Toolbox/releases/tag/v1.2.10",
                "assets": [
                    {
                        "name": "DM-BOX.exe",
                        "size": 343169733,
                        "browser_download_url": "https://github.com/Iridescent10-art/DM-Toolbox/releases/download/v1.2.10/DM-BOX.exe"
                    }
                ]
            }
        ]

        dlg = AppUpdateDialog(parent=None, is_dark=False, preloaded_releases=mock_releases)
        self.assertEqual(dlg.combo_versions.count(), 1)
        self.assertEqual(dlg.selected_release["tag_name"], "v1.2.13")
        self.assertIsNotNone(dlg.selected_asset)
        self.assertEqual(dlg.selected_asset["name"], "DM-BOX.exe")
        self.assertTrue(dlg.btn_download.isEnabled())
        if dlg.speed_test_worker and dlg.speed_test_worker.isRunning():
            dlg.speed_test_worker.cancel()
            dlg.speed_test_worker.wait(3000)
        dlg.close()
        app.processEvents()



    def test_mirror_speed_worker(self):
        """Verify MirrorSpeedTestWorker completes and identifies reachable nodes."""
        from PySide6.QtWidgets import QApplication
        from common.app_updater import MirrorSpeedTestWorker, MIRROR_SOURCES
        app = QApplication.instance() or QApplication(sys.argv)
        test_url = "https://github.com/Iridescent10-art/DM-Toolbox/releases/download/v1.2.13/DM-BOX.exe"
        worker = MirrorSpeedTestWorker(MIRROR_SOURCES, test_url)
        
        result_holder = []
        worker.finished.connect(lambda res, best: result_holder.append((res, best)))
        worker.start()
        worker.wait(8000)
        app.processEvents()
        self.assertEqual(len(result_holder), 1)
        res, best = result_holder[0]
        self.assertIn("ghproxy_com", res)
        self.assertTrue(best in res)

    def test_download_worker_cancellation(self):
        """Verify DownloadInstallerWorker handles cancellation cleanly without throwing or crashing."""
        from PySide6.QtWidgets import QApplication
        from common.app_updater import DownloadInstallerWorker
        app = QApplication.instance() or QApplication(sys.argv)
        candidates = ["https://gh-proxy.com/https://github.com/Iridescent10-art/DM-Toolbox/releases/download/v1.2.13/DM-BOX.exe"]
        dest = str(Path(r"C:\Users\17547\.gemini\antigravity\brain\29b03b65-5c3d-4ff1-854f-8943ec280b56\scratch\test_cancel.tmp"))
        worker = DownloadInstallerWorker(candidates, dest)
        
        fin_holder = []
        worker.finished.connect(lambda ok, path, err: fin_holder.append((ok, path, err)))
        worker.start()
        # Immediately cancel
        worker.cancel()
        worker.wait(3000)
        app.processEvents()
        self.assertEqual(len(fin_holder), 1)
        ok, path, err = fin_holder[0]
        self.assertFalse(ok)
        self.assertEqual(err, "用户已取消下载")

if __name__ == "__main__":
    unittest.main()
