# -*- coding: utf-8 -*-
"""Session-wide configuration for the DM-Toolbox test suite.

Constructing a GUI window starts background work in the real application:
a full drive library scan, the mirror speed test and the silent GitHub update
check. Under pytest those workers outlive the window that created them, keep
touching Qt objects while the next test builds new windows, and crash the
interpreter with an access violation. The suite therefore runs with every
automatic background worker disabled; the tests drive the features explicitly.
"""

import os

os.environ.setdefault("DM_DISABLE_AUTO_SCAN", "1")
os.environ.setdefault("DM_DISABLE_AUTO_UPDATE_CHECK", "1")
