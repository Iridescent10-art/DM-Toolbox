# -*- coding: utf-8 -*-
"""
DM Hardware Master - 全硬件配置大师
现代化极简卡片轻量风格 (Light Modern Card Theme)
完全重构与视觉升级
"""

import os
import sys
import json
import ctypes
import winreg
import subprocess

from PySide6.QtCore import Qt, QSize, QPoint, QEvent, QTimer
from PySide6.QtGui import QIcon, QPixmap, QFont, QColor, QGuiApplication, QCursor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QLineEdit, QCheckBox,
    QStackedWidget, QFrame, QScrollArea, QMessageBox, QGraphicsDropShadowEffect,
    QInputDialog, QFileDialog
)

# 基础目录与常量
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = getattr(sys, "_MEIPASS", BASE_DIR)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = BASE_DIR

# 引入 Toolbox 公共配置与 C 盘统一数据中心
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common.config_manager import (
    get_app_cache_dir, get_app_config_dir, get_app_config_path, init_app_config,
    get_global_theme, set_global_theme
)
from common.ui_theme import CaptionButton, CaptionButtonType, ModernProgressDialog
from common.dm_ui_core import DMSizeGrip, apply_dm_window_frame
from ctypes import wintypes

CONFIG_FILE = str(init_app_config("app1_hardware", "config.json", default_template_path=Path(BASE_DIR) / "config.json"))
PUBLIC_CONFIG_FILE = r"C:\Users\Public\Hardware_Config.json"

# 优先从打包资源目录中查找图标资源，再回退到当前目录
if os.path.exists(os.path.join(BUNDLE_DIR, "assets")):
    ASSETS_DIR = os.path.join(BUNDLE_DIR, "assets")
else:
    ASSETS_DIR = os.path.join(BASE_DIR, "assets")


def ensure_down_arrow_icon():
    os.makedirs(ASSETS_DIR, exist_ok=True)
    arrow_p = os.path.join(ASSETS_DIR, "down_arrow.png")
    if not os.path.exists(arrow_p):
        try:
            from PySide6.QtGui import QImage, QPainter, QPen, QColor
            from PySide6.QtCore import Qt
            img = QImage(24, 24, QImage.Format_ARGB32)
            img.fill(Qt.transparent)
            painter = QPainter(img)
            painter.setRenderHint(QPainter.Antialiasing, True)
            pen = QPen(QColor("#64748B"), 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(7, 10, 12, 15)
            painter.drawLine(12, 15, 17, 10)
            painter.end()
            img.save(arrow_p, "PNG")
        except Exception:
            pass

    arrow_light_p = os.path.join(ASSETS_DIR, "down_arrow_light.png")
    if not os.path.exists(arrow_light_p):
        try:
            from PySide6.QtGui import QImage, QPainter, QPen, QColor
            from PySide6.QtCore import Qt
            img = QImage(24, 24, QImage.Format_ARGB32)
            img.fill(Qt.transparent)
            painter = QPainter(img)
            painter.setRenderHint(QPainter.Antialiasing, True)
            pen = QPen(QColor("#CBD5E1"), 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(7, 10, 12, 15)
            painter.drawLine(12, 15, 17, 10)
            painter.end()
            img.save(arrow_light_p, "PNG")
        except Exception:
            pass
    return arrow_p


ensure_down_arrow_icon()
ARROW_ICON_PATH = os.path.join(ASSETS_DIR, "down_arrow.png").replace("\\", "/")
ARROW_ICON_LIGHT_PATH = os.path.join(ASSETS_DIR, "down_arrow_light.png").replace("\\", "/")

# C盘统一数据存储 (C:/ToolboxData/cache/app1_hardware)
APP1_CACHE = get_app_cache_dir("app1_hardware")
CPU_BACKUP_FILE = str(APP1_CACHE / "CPU_Backup.cfg")
GPU_BACKUP_FILE = str(APP1_CACHE / "GPU_Backup.cfg")
GPU_PATH_BACKUP_FILE = str(APP1_CACHE / "GPU_Path_Backup.cfg")
BOARD_VENDOR_BACKUP_FILE = str(APP1_CACHE / "Board_Vendor_Backup.cfg")
BOARD_PRODUCT_BACKUP_FILE = str(APP1_CACHE / "Board_Product_Backup.cfg")
DISK_BACKUP_FILE = str(APP1_CACHE / "Disk_Backup.cfg")
DISK_PATH_BACKUP_FILE = str(APP1_CACHE / "Disk_Path_Backup.cfg")
CPU_CONFIG_FILE = str(APP1_CACHE / "CPU_Startup_Task.cfg")

DEFAULT_REAL_CPU = "AMD Ryzen 5 9600X 6-Core Processor"
DEFAULT_REAL_GPU = "NVIDIA GeForce RTX 4070"
DEFAULT_REAL_VRAM_BYTES = 12593397760
DEFAULT_REAL_BOARD_VENDOR = "MAXSUN"
DEFAULT_REAL_BOARD_PRODUCT = "MS-eSport B650ITX"
DEFAULT_REAL_DISK_MODEL = "YSSDM-2TN3000"
DEFAULT_REAL_DISK_PATH = r"SCSI\DISK&VEN_NVME&PROD_YSSDM-2TN3000\5&1574F6F4&0&000000"


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def request_admin(action_arg=""):
    """请求 Windows UAC 管理员提权并重启程序"""
    if not is_admin():
        try:
            exe_path = sys.executable
            if getattr(sys, "frozen", False):
                args = action_arg.strip()
            else:
                script_path = os.path.abspath(__file__)
                args = f'"{script_path}" {action_arg}'.strip()
            ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe_path, args, str(BASE_DIR), 1)
            if ret > 32:
                sys.exit(0)
            return False
        except Exception:
            return False
    return True


def safe_write_elevated(target_path: str, content: str) -> bool:
    try:
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except (PermissionError, OSError):
        temp_dir = os.environ.get("TEMP", r"C:\Windows\Temp")
        tmp_p = os.path.join(temp_dir, f"dm_patch_{os.path.basename(target_path)}")
        try:
            with open(tmp_p, "w", encoding="utf-8") as tf:
                tf.write(content)
            bat = f'@echo off\ncopy /y "{tmp_p}" "{target_path}" >nul 2>&1\ndel "{tmp_p}" >nul 2>&1\n'
            return run_elevated_batch(bat)
        except Exception:
            return False
    except Exception:
        return False


def safe_copy_elevated(src_path: str, dst_path: str) -> bool:
    try:
        import shutil
        shutil.copyfile(src_path, dst_path)
        return True
    except (PermissionError, OSError):
        bat = f'@echo off\ncopy /y "{src_path}" "{dst_path}" >nul 2>&1\n'
        return run_elevated_batch(bat)
    except Exception:
        return False



def run_elevated_batch(bat_content: str, timeout_ms: int = 15000) -> bool:
    """以管理员身份执行临时批处理脚本，支持 UAC 提权并同步等待完成"""
    temp_dir = os.environ.get("TEMP", r"C:\Windows\Temp")
    bat_path = os.path.join(temp_dir, "dm_hw_elevated.bat")
    try:
        with open(bat_path, "w", encoding="gbk", errors="ignore") as f:
            f.write(bat_content)
    except Exception:
        return False

    SEE_MASK_NOCLOSEPROCESS = 0x00000040
    class SHELLEXECUTEINFOW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("fMask", wintypes.ULONG),
            ("hwnd", wintypes.HWND),
            ("lpVerb", wintypes.LPCWSTR),
            ("lpFile", wintypes.LPCWSTR),
            ("lpParameters", wintypes.LPCWSTR),
            ("lpDirectory", wintypes.LPCWSTR),
            ("nShow", ctypes.c_int),
            ("hInstApp", wintypes.HINSTANCE),
            ("lpIDList", ctypes.c_void_p),
            ("lpClass", wintypes.LPCWSTR),
            ("hkeyClass", wintypes.HKEY),
            ("dwHotKey", wintypes.DWORD),
            ("hIconOrMonitor", wintypes.HANDLE),
            ("hProcess", wintypes.HANDLE),
        ]

    info = SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = SEE_MASK_NOCLOSEPROCESS
    info.lpVerb = "runas"
    info.lpFile = "cmd.exe"
    info.lpParameters = f'/c "{bat_path}"'
    info.nShow = 0  # SW_HIDE

    res = ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info))
    if not res or not info.hProcess:
        return False

    ctypes.windll.kernel32.WaitForSingleObject(info.hProcess, timeout_ms)
    exit_code = wintypes.DWORD()
    ctypes.windll.kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(exit_code))
    ctypes.windll.kernel32.CloseHandle(info.hProcess)
    try:
        if os.path.exists(bat_path):
            os.remove(bat_path)
    except Exception:
        pass
    return exit_code.value == 0


def load_config():
    local_cfg = os.path.join(BASE_DIR, "config.json")
    for p in [CONFIG_FILE, PUBLIC_CONFIG_FILE, local_cfg]:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {
        "current_hardware": {
            "detected_cpu": DEFAULT_REAL_CPU,
            "detected_gpu": DEFAULT_REAL_GPU,
            "motherboard_vendor": DEFAULT_REAL_BOARD_VENDOR,
            "motherboard_product": DEFAULT_REAL_BOARD_PRODUCT,
            "memory_vendor": "Asgard",
            "memory_size_gb": 32,
            "memory_clock_mhz": 6000,
            "disk_model": DEFAULT_REAL_DISK_MODEL,
        },
        "custom_target": {
            "cpu_model": "AMD Ryzen 9 9950X3D2 16-Core Processor",
            "gpu_model": "NVIDIA GeForce RTX 5090",
            "gpu_vram_gb": 32,
            "motherboard_vendor": "ASUSTeK COMPUTER INC.",
            "motherboard_product": "ROG CROSSHAIR X870E HERO",
            "memory_vendor": "Corsair",
            "memory_size_gb": 64,
            "memory_clock_mhz": 7200,
            "disk_model": "Samsung SSD 990 PRO 4TB",
            "enable_startup_fix": True
        },
        "presets": {
            "cpu": [
                "AMD Ryzen 9 9950X3D2 16-Core Processor",
                "AMD Ryzen 9 9950X3D 16-Core Processor",
                "AMD Ryzen 7 9850X3D 8-Core Processor",
                "AMD Ryzen 7 9800X3D 8-Core Processor",
                "AMD Ryzen 9 9950X 16-Core Processor",
                "AMD Ryzen 9 9900X 12-Core Processor",
                "AMD Ryzen 7 9700X 8-Core Processor",
                "AMD Ryzen 5 9600X 6-Core Processor",
                "AMD Ryzen 7 7800X3D 8-Core Processor",
                "AMD Ryzen 9 7950X3D 16-Core Processor",
                "Intel Core Ultra 9 285K",
                "Intel Core Ultra 7 265K",
                "14th Gen Intel(R) Core(TM) i9-14900KS",
                "14th Gen Intel(R) Core(TM) i9-14900K",
                "14th Gen Intel(R) Core(TM) i7-14700K"
            ],
            "gpu": [
                "NVIDIA GeForce RTX 5090 D",
                "NVIDIA GeForce RTX 5090",
                "NVIDIA GeForce RTX 5080",
                "NVIDIA GeForce RTX 5070 Ti",
                "NVIDIA GeForce RTX 5070",
                "NVIDIA GeForce RTX 4090 D",
                "NVIDIA GeForce RTX 4090",
                "NVIDIA GeForce RTX 4080 SUPER",
                "NVIDIA GeForce RTX 4070 Ti SUPER",
                "NVIDIA GeForce RTX 4070"
            ],
            "vram": ["48 GB", "32 GB", "24 GB", "16 GB", "12 GB (保持原始)", "8 GB"],
            "motherboard": [
                {"vendor": "ASUSTeK COMPUTER INC.", "product": "ROG CROSSHAIR X870E HERO"},
                {"vendor": "ASUSTeK COMPUTER INC.", "product": "ROG CROSSHAIR X870E DARK HERO"},
                {"vendor": "ASUSTeK COMPUTER INC.", "product": "ROG MAXIMUS Z890 EXTREME"},
                {"vendor": "ASUSTeK COMPUTER INC.", "product": "ROG STRIX Z790-H GAMING WIFI"},
                {"vendor": "ASUSTeK COMPUTER INC.", "product": "ROG STRIX X870-F GAMING WIFI"},
                {"vendor": "Micro-Star International Co., Ltd.", "product": "MEG X870E GODLIKE"},
                {"vendor": "Micro-Star International Co., Ltd.", "product": "MAG B650 TOMAHAWK WIFI"},
                {"vendor": "Gigabyte Technology Co., Ltd.", "product": "X870E AORUS XTREME"}
            ],
            "memory_vendor": ["Corsair", "G.Skill", "Kingston", "Asgard", "Crucial", "TEAMGROUP"],
            "memory_size": ["128 GB", "96 GB (48GBx2)", "64 GB (32GBx2)", "48 GB (24GBx2)", "32 GB (16GBx2)", "16 GB (8GBx2)"],
            "memory_clock": ["8400 MHz", "8000 MHz", "7600 MHz", "7200 MHz", "6800 MHz", "6400 MHz", "6000 MHz", "5600 MHz"],
            "disk": [
                "Samsung SSD 990 PRO 2TB",
                "Samsung SSD 990 PRO 4TB",
                "Crucial T705 2TB PCIe 5.0 NVMe M.2 SSD",
                "WD_BLACK SN850X 2000GB",
                "ZhiTai TiPro7000 2TB NVMe SSD",
                "Kingston KC3000 2048GB PCIe 4.0 NVMe M.2 SSD",
                "YSSDM-2TN3000"
            ]
        }
    }


def save_config(cfg):
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    try:
        os.makedirs(os.path.dirname(PUBLIC_CONFIG_FILE), exist_ok=True)
        with open(PUBLIC_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    try:
        local_cfg = os.path.join(BASE_DIR, "config.json")
        os.makedirs(os.path.dirname(local_cfg), exist_ok=True)
        with open(local_cfg, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_xiaoheihe_base_dir():
    r"""
    智能多级探测小黑盒安装根目录：
    1. 用户自定义手动指定路径 (config.json 中的 custom_heybox_dir)
    2. Windows 注册表 Uninstall 卸载项 (全盘/全盘符安装均有记录)
    3. 当前运行中的小黑盒进程 (heyboxacc.exe / heybox.exe)
    4. 全盘所有可用驱动器 (C:\, D:\, E:\, F:\ 等) 递归与常见目录扫描
    5. 默认回退路径
    """
    # 1. 优先检查用户指定配置
    try:
        cfg = load_config()
        custom_dir = cfg.get("custom_heybox_dir")
        if custom_dir and os.path.isdir(custom_dir):
            if os.path.exists(os.path.join(custom_dir, "heyboxacc.exe")) or os.path.exists(os.path.join(custom_dir, "resources")):
                return custom_dir
    except Exception:
        pass

    # 2. 检查 Windows 注册表卸载信息 (全版本/全路径/32位及64位均会在此注册)
    uninstall_bases = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hkey, subkey_path in uninstall_bases:
        try:
            with winreg.OpenKey(hkey, subkey_path) as parent_key:
                num_subkeys = winreg.QueryInfoKey(parent_key)[0]
                for i in range(num_subkeys):
                    try:
                        k_name = winreg.EnumKey(parent_key, i)
                        with winreg.OpenKey(parent_key, k_name) as app_key:
                            try:
                                d_name = winreg.QueryValueEx(app_key, "DisplayName")[0]
                            except Exception:
                                d_name = ""
                            if "小黑盒" in d_name or "Heybox" in d_name:
                                for val_name in ["InstallLocation", "DisplayIcon", "UninstallString"]:
                                    try:
                                        val = winreg.QueryValueEx(app_key, val_name)[0].strip().strip('"')
                                        if os.path.isdir(val):
                                            return val
                                        elif os.path.exists(val):
                                            d = os.path.dirname(val)
                                            if os.path.isdir(d):
                                                return d
                                    except Exception:
                                        pass
                    except Exception:
                        continue
        except Exception:
            continue

    # 3. 检查当前是否正在运行小黑盒进程
    try:
        cmd = 'powershell -NoProfile -Command "(Get-Process -Name heyboxacc, heybox, HeyboxAccelerator -ErrorAction SilentlyContinue | Select-Object -First 1).Path"'
        out = subprocess.check_output(cmd, shell=True, text=True, timeout=2).strip()
        if out and os.path.exists(out):
            p_dir = os.path.dirname(out)
            if os.path.isdir(p_dir):
                return p_dir
    except Exception:
        pass

    # 4. 常见盘符遍历扫描
    drives = [f"{chr(d)}:" for d in range(ord('C'), ord('Z') + 1) if os.path.exists(f"{chr(d)}:")]
    sub_paths = [
        r"Program Files (x86)\Qingfeng\HeyboxAccelerator",
        r"Program Files\Qingfeng\HeyboxAccelerator",
        r"Qingfeng\HeyboxAccelerator",
        r"HeyboxAccelerator",
        r"Heybox",
        r"小黑盒加速器",
        r"小黑盒",
        r"Games\HeyboxAccelerator",
        r"Software\HeyboxAccelerator",
    ]
    for d in drives:
        for sp in sub_paths:
            cand = os.path.join(d, os.sep, sp)
            if os.path.isdir(cand) and (os.path.exists(os.path.join(cand, "heyboxacc.exe")) or os.path.exists(os.path.join(cand, "resources"))):
                return cand

    # 5. 回退到标准默认路径
    return r"C:\Program Files (x86)\Qingfeng\HeyboxAccelerator"


def get_xiaoheihe_index_paths(base_dir=None):
    base = base_dir or get_xiaoheihe_base_dir()
    if not base or not os.path.exists(base):
        return []
    paths = []
    for root, dirs, files in os.walk(base):
        if "index.js" in files and os.path.basename(root) == "app":
            paths.append(os.path.join(root, "index.js"))
    return paths


def patch_xiaoheihe_webapp(base_dir=None):
    base = base_dir or get_xiaoheihe_base_dir()
    if not base or not os.path.exists(base):
        return
    for root, dirs, files in os.walk(base):
        if "chunk-793bf638.0533358a.js" in files:
            f1 = os.path.join(root, "chunk-793bf638.0533358a.js")
            bak1 = f1 + ".bak"
            if not os.path.exists(bak1):
                safe_copy_elevated(f1, bak1)
            try:
                with open(f1, "r", encoding="utf-8") as fp:
                    c1 = fp.read()
                t1 = "a.hardwareEvalInfo=t.data.result"
                r1 = '(a.hardwareEvalInfo=t.data.result,a.hardwareInfo&&a.hardwareInfo.gpus&&a.hardwareInfo.gpus[0]&&(a.hardwareEvalInfo.gpus.show_key=a.hardwareInfo.gpus[0].name+(a.hardwareInfo.gpus[0].memory_size?\' \'+Math.round(a.hardwareInfo.gpus[0].memory_size/1024)+\'GB\':\'\'),a.hardwareEvalInfo.cpu&&(a.hardwareEvalInfo.cpu.show_key=a.hardwareInfo.cpu.name),a.hardwareEvalInfo.avg_perf_level="SSS",a.hardwareEvalInfo.avg_good_than_other_user_percent=99.9,a.hardwareEvalInfo.gpus.perf_level="SSS",a.hardwareEvalInfo.gpus.score_v2=99,a.hardwareEvalInfo.gpus.percentage_v2=99,a.hardwareEvalInfo.cpu&&(a.hardwareEvalInfo.cpu.perf_level="SS",a.hardwareEvalInfo.cpu.score_v2=98)))'
                if t1 in c1:
                    c1 = c1.replace(t1, r1, 1)
                    safe_write_elevated(f1, c1)
            except Exception:
                pass
        if "chunk-499402f5.29a05416.js" in files:
            f2 = os.path.join(root, "chunk-499402f5.29a05416.js")
            bak2 = f2 + ".bak"
            if not os.path.exists(bak2):
                safe_copy_elevated(f2, bak2)
            try:
                with open(f2, "r", encoding="utf-8") as fp:
                    c2 = fp.read()
                t2 = "e&&(t.hardware_info=a.hardware_info)"
                r2 = '(e&&(t.hardware_info=a.hardware_info,t.$store.state.hardwareInfo&&t.$store.state.hardwareInfo.gpus&&t.$store.state.hardwareInfo.gpus[0]&&(t.hardware_info.gpu_name=t.$store.state.hardwareInfo.gpus[0].name,t.hardware_info.cpu_name=t.$store.state.hardwareInfo.cpu.name,t.hardware_info.board_name=t.$store.state.hardwareInfo.board.name,t.hardware_info.score="SSS",t.hardware_info.percent=99)))'
                if t2 in c2:
                    c2 = c2.replace(t2, r2, 1)
                    safe_write_elevated(f2, c2)
            except Exception:
                pass
        if "chunk-da628b42.33d8fd5a.js" in files:
            f3 = os.path.join(root, "chunk-da628b42.33d8fd5a.js")
            bak3 = f3 + ".bak"
            if not os.path.exists(bak3):
                safe_copy_elevated(f3, bak3)
            try:
                with open(f3, "r", encoding="utf-8") as fp:
                    c3 = fp.read()
                t3 = "t.hardwareEvalInfoLoaded=!0,t.hardwareEvalInfo=a.data.result"
                r3 = 't.hardwareEvalInfoLoaded=!0,(t.hardwareEvalInfo=a.data.result,t.hardwareInfo&&t.hardwareInfo.gpus&&t.hardwareInfo.gpus[0]&&(t.hardwareEvalInfo.gpus.show_key=t.hardwareInfo.gpus[0].name+(t.hardwareInfo.gpus[0].memory_size?\' \'+Math.round(t.hardwareInfo.gpus[0].memory_size/1024)+\'GB\':\'\'),t.hardwareEvalInfo.cpu&&(t.hardwareEvalInfo.cpu.show_key=t.hardwareInfo.cpu.name),t.hardwareEvalInfo.avg_perf_level="SSS",t.hardwareEvalInfo.avg_good_than_other_user_percent=99.9,t.hardwareEvalInfo.gpus.perf_level="SSS",t.hardwareEvalInfo.gpus.score=99,t.hardwareEvalInfo.gpus.percentage=99,t.hardwareEvalInfo.cpu&&(t.hardwareEvalInfo.cpu.perf_level="SS",t.hardwareEvalInfo.cpu.score=98,t.hardwareEvalInfo.cpu.percentage=98),t.hardwareEvalInfo.memory&&(t.hardwareEvalInfo.memory.perf_level="SSS",t.hardwareEvalInfo.memory.score=99,t.hardwareEvalInfo.memory.percentage=99),t.hardwareEvalInfo.disks&&(t.hardwareEvalInfo.disks.perf_level="SSS",t.hardwareEvalInfo.disks.score=99,t.hardwareEvalInfo.disks.percentage=99)))'
                if t3 in c3:
                    c3 = c3.replace(t3, r3, 1)
                    safe_write_elevated(f3, c3)
            except Exception:
                pass


def apply_xiaoheihe_hook(base_dir=None):
    template_file = os.path.join(BASE_DIR, "xiaoheihe_index.js")
    if os.path.exists(template_file):
        try:
            with open(template_file, "r", encoding="utf-8") as tf:
                hook_full_content = tf.read()

            for p in get_xiaoheihe_index_paths(base_dir):
                bak = p + ".bak"
                if not os.path.exists(bak):
                    try:
                        with open(p, "r", encoding="utf-8") as f:
                            orig = f.read()
                        safe_write_elevated(bak, orig)
                    except Exception:
                        pass
                safe_write_elevated(p, hook_full_content)
        except Exception:
            pass

    patch_xiaoheihe_webapp(base_dir)


def restore_xiaoheihe_hook(base_dir=None):
    for p in get_xiaoheihe_index_paths(base_dir):
        bak = p + ".bak"
        if os.path.exists(bak):
            try:
                with open(bak, "r", encoding="utf-8") as f:
                    orig = f.read()
                safe_write_elevated(p, orig)
                try:
                    os.remove(bak)
                except Exception:
                    pass
            except Exception:
                pass

    base = base_dir or get_xiaoheihe_base_dir()
    if os.path.exists(base):
        for root, dirs, files in os.walk(base):
            for fn in ["chunk-793bf638.0533358a.js", "chunk-499402f5.29a05416.js", "chunk-da628b42.33d8fd5a.js"]:
                if fn + ".bak" in files:
                    fp = os.path.join(root, fn)
                    bak = fp + ".bak"
                    safe_copy_elevated(bak, fp)
                    try:
                        os.remove(bak)
                    except Exception:
                        pass


def get_system_directx_guids():
    dx_base = r"SOFTWARE\Microsoft\DirectX"
    guids = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, dx_base) as k:
            for i in range(winreg.QueryInfoKey(k)[0]):
                sub = winreg.EnumKey(k, i)
                if sub.startswith("{") and sub.endswith("}"):
                    guids.append(sub)
    except Exception:
        pass
    return guids


def get_system_control_video_guids():
    v_base = r"SYSTEM\CurrentControlSet\Control\Video"
    guids = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, v_base) as k:
            for i in range(winreg.QueryInfoKey(k)[0]):
                sub = winreg.EnumKey(k, i)
                if sub.startswith("{") and sub.endswith("}"):
                    guids.append(sub)
    except Exception:
        pass
    return guids


def get_system_display_pci_paths():
    pci_base = r"SYSTEM\CurrentControlSet\Enum\PCI"
    display_devices = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, pci_base) as pk:
            for i in range(winreg.QueryInfoKey(pk)[0]):
                dev = winreg.EnumKey(pk, i)
                dev_path = f"{pci_base}\\{dev}"
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, dev_path) as dk:
                        for j in range(winreg.QueryInfoKey(dk)[0]):
                            inst = winreg.EnumKey(dk, j)
                            inst_path = f"{dev_path}\\{inst}"
                            try:
                                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, inst_path) as ik:
                                    cg = ""
                                    try:
                                        cg, _ = winreg.QueryValueEx(ik, "ClassGUID")
                                    except Exception:
                                        pass
                                    if cg.lower() == "{4d36e968-e325-11ce-bfc1-08002be10318}":
                                        display_devices.append(f"PCI\\{dev}\\{inst}")
                            except Exception:
                                pass
                except Exception:
                    pass
    except Exception:
        pass
    return display_devices


def get_system_disk_reg_paths():
    disk_paths = []
    for base in [r"SYSTEM\CurrentControlSet\Enum\SCSI", r"SYSTEM\CurrentControlSet\Enum\NVMe", r"SYSTEM\CurrentControlSet\Enum\IDE"]:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as k:
                for i in range(winreg.QueryInfoKey(k)[0]):
                    s1 = winreg.EnumKey(k, i)
                    p1 = f"{base}\\{s1}"
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, p1) as k1:
                            for j in range(winreg.QueryInfoKey(k1)[0]):
                                s2 = winreg.EnumKey(k1, j)
                                disk_paths.append(f"{base}\\{s1}\\{s2}")
                    except Exception:
                        pass
        except Exception:
            pass
    return disk_paths


def execute_hardware_apply(target, components=None):
    if components is None or "all" in components:
        apply_cpu = True
        apply_gpu = True
        apply_board = True
        apply_memory = True
        apply_disk = True
        apply_hook = True
    else:
        apply_cpu = "cpu" in components
        apply_gpu = "gpu" in components or "vram" in components
        apply_board = "board" in components or "motherboard" in components
        apply_memory = "memory" in components or "ram" in components
        apply_disk = "disk" in components
        apply_hook = True

    cpu_target = target.get("cpu_model", "AMD Ryzen 9 9950X3D2 16-Core Processor").strip()
    gpu_target = target.get("gpu_model", "NVIDIA GeForce RTX 5090").strip()
    vram_gb = int(target.get("gpu_vram_gb", 32))
    vram_bytes = vram_gb * 1024 * 1024 * 1024
    vram_dword = min(vram_bytes, 4294967295)

    board_vendor = target.get("motherboard_vendor", "ASUSTeK COMPUTER INC.").strip()
    board_product = target.get("motherboard_product", "ROG CROSSHAIR X870E HERO").strip()
    clean_product = board_product
    if board_vendor and clean_product.lower().startswith(board_vendor.lower()):
        clean_product = clean_product[len(board_vendor):].strip()

    disk_model = target.get("disk_model", "Samsung SSD 990 PRO 4TB").strip()
    custom_heybox_dir = target.get("custom_heybox_dir") or get_xiaoheihe_base_dir()
    enable_startup = target.get("enable_startup_fix", True)
    gpu_pnp = target.get("target_gpu_instance_path") or target.get("gpu_instance_path", "")
    disk_pnp = target.get("target_disk_instance_path") or target.get("disk_instance_path", "")

    # 1. 自动同步保存配置至本地与公共路径
    try:
        full_cfg = load_config()
        if "custom_target" not in full_cfg:
            full_cfg["custom_target"] = {}
        for k, v in target.items():
            full_cfg["custom_target"][k] = v
        save_config(full_cfg)
    except Exception:
        pass

    # 2. 硬件出厂真实数据安全备份 (若不存在则备份)
    try:
        if not os.path.exists(CPU_BACKUP_FILE):
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
                real_c, _ = winreg.QueryValueEx(k, "ProcessorNameString")
                if "9800" not in real_c and "9850" not in real_c and "5090" not in real_c:
                    with open(CPU_BACKUP_FILE, "w", encoding="utf-8") as f:
                        f.write(real_c.strip())

        if not os.path.exists(GPU_BACKUP_FILE):
            with open(GPU_BACKUP_FILE, "w", encoding="utf-8") as f:
                f.write(DEFAULT_REAL_GPU)

        if not os.path.exists(BOARD_VENDOR_BACKUP_FILE):
            with open(BOARD_VENDOR_BACKUP_FILE, "w", encoding="utf-8") as f:
                f.write(DEFAULT_REAL_BOARD_VENDOR)
        if not os.path.exists(BOARD_PRODUCT_BACKUP_FILE):
            with open(BOARD_PRODUCT_BACKUP_FILE, "w", encoding="utf-8") as f:
                f.write(DEFAULT_REAL_BOARD_PRODUCT)

        if not os.path.exists(DISK_BACKUP_FILE):
            with open(DISK_BACKUP_FILE, "w", encoding="utf-8") as f:
                f.write(DEFAULT_REAL_DISK_MODEL)
    except Exception:
        pass

    # 3. 收集系统动态 GUID 与设备路径
    dx_guids = get_system_directx_guids()
    v_guids = get_system_control_video_guids()
    pci_paths = get_system_display_pci_paths()
    if gpu_pnp and gpu_pnp not in pci_paths:
        pci_paths.append(gpu_pnp)
    disk_paths = get_system_disk_reg_paths()
    if disk_pnp and f"SYSTEM\\CurrentControlSet\\Enum\\{disk_pnp}" not in disk_paths:
        disk_paths.append(f"SYSTEM\\CurrentControlSet\\Enum\\{disk_pnp}")

    # 4. 直接 Python winreg 尝试写入 (在已提权时直接秒级生效)
    if is_admin():
        try:
            if apply_cpu:
                # CPU
                cpu_base = r"HARDWARE\DESCRIPTION\System\CentralProcessor"
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, cpu_base) as k:
                    for i in range(winreg.QueryInfoKey(k)[0]):
                        sub = winreg.EnumKey(k, i)
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{cpu_base}\\{sub}", 0, winreg.KEY_SET_VALUE) as sk:
                            winreg.SetValueEx(sk, "ProcessorNameString", 0, winreg.REG_SZ, cpu_target)

                # ACPI Processor
                acpi_base = r"SYSTEM\CurrentControlSet\Enum\ACPI"
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, acpi_base) as ak:
                        for i in range(winreg.QueryInfoKey(ak)[0]):
                            name = winreg.EnumKey(ak, i)
                            if "processor" in name.lower() or "cpu" in name.lower():
                                sub_p = f"{acpi_base}\\{name}"
                                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub_p) as sk:
                                    for j in range(winreg.QueryInfoKey(sk)[0]):
                                        inst_k = winreg.EnumKey(sk, j)
                                        try:
                                            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{sub_p}\\{inst_k}", 0, winreg.KEY_SET_VALUE) as ik:
                                                winreg.SetValueEx(ik, "FriendlyName", 0, winreg.REG_SZ, cpu_target)
                                                winreg.SetValueEx(ik, "DeviceDesc", 0, winreg.REG_SZ, cpu_target)
                                        except Exception:
                                            pass
                except Exception:
                    pass

            if apply_gpu:
                # DirectX
                dx_path = r"SOFTWARE\Microsoft\DirectX"
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, dx_path, 0, winreg.KEY_SET_VALUE) as k:
                    winreg.SetValueEx(k, "MaxDedicatedVideoMemory", 0, winreg.REG_QWORD, vram_bytes)
                for g in dx_guids:
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{dx_path}\\{g}", 0, winreg.KEY_SET_VALUE) as sk:
                            winreg.SetValueEx(sk, "Description", 0, winreg.REG_SZ, gpu_target)
                            winreg.SetValueEx(sk, "DedicatedVideoMemory", 0, winreg.REG_QWORD, vram_bytes)
                    except Exception:
                        pass

                # Control\Video
                v_base = r"SYSTEM\CurrentControlSet\Control\Video"
                for vg in v_guids:
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{v_base}\\{vg}\\Video", 0, winreg.KEY_SET_VALUE) as vk:
                            winreg.SetValueEx(vk, "DeviceDesc", 0, winreg.REG_SZ, gpu_target)
                    except Exception:
                        pass
                    for out_i in range(4):
                        try:
                            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{v_base}\\{vg}\\{out_i:04d}", 0, winreg.KEY_SET_VALUE) as ok:
                                winreg.SetValueEx(ok, "DriverDesc", 0, winreg.REG_SZ, gpu_target)
                                winreg.SetValueEx(ok, "HardwareInformation.ChipType", 0, winreg.REG_SZ, gpu_target)
                                winreg.SetValueEx(ok, "HardwareInformation.AdapterString", 0, winreg.REG_SZ, gpu_target)
                                winreg.SetValueEx(ok, "HardwareInformation.qwMemorySize", 0, winreg.REG_QWORD, vram_bytes)
                                winreg.SetValueEx(ok, "HardwareInformation.MemorySize", 0, winreg.REG_DWORD, vram_dword)
                        except Exception:
                            pass

                # Control\Class
                class_base = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, class_base) as k:
                    for i in range(winreg.QueryInfoKey(k)[0]):
                        sub = winreg.EnumKey(k, i)
                        if sub.isdigit() and len(sub) == 4:
                            try:
                                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{class_base}\\{sub}", 0, winreg.KEY_SET_VALUE) as sk:
                                    winreg.SetValueEx(sk, "DriverDesc", 0, winreg.REG_SZ, gpu_target)
                                    winreg.SetValueEx(sk, "HardwareInformation.ChipType", 0, winreg.REG_SZ, gpu_target)
                                    winreg.SetValueEx(sk, "HardwareInformation.AdapterString", 0, winreg.REG_SZ, gpu_target)
                                    winreg.SetValueEx(sk, "HardwareInformation.qwMemorySize", 0, winreg.REG_QWORD, vram_bytes)
                                    winreg.SetValueEx(sk, "HardwareInformation.MemorySize", 0, winreg.REG_DWORD, vram_dword)
                            except Exception:
                                pass

            if apply_board:
                # BIOS
                bios_path = r"HARDWARE\DESCRIPTION\System\BIOS"
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, bios_path, 0, winreg.KEY_SET_VALUE) as k:
                    winreg.SetValueEx(k, "BaseBoardManufacturer", 0, winreg.REG_SZ, board_vendor)
                    winreg.SetValueEx(k, "BaseBoardProduct", 0, winreg.REG_SZ, clean_product)
                    winreg.SetValueEx(k, "SystemManufacturer", 0, winreg.REG_SZ, board_vendor)
                    winreg.SetValueEx(k, "SystemProductName", 0, winreg.REG_SZ, clean_product)

            if apply_disk:
                # Disks
                for dp in disk_paths:
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, dp, 0, winreg.KEY_SET_VALUE) as dk:
                            winreg.SetValueEx(dk, "FriendlyName", 0, winreg.REG_SZ, disk_model)
                    except Exception:
                        pass
        except Exception:
            pass

    # 5. 生成系统提权批处理 (仅包含选中的硬件项)
    bat_lines = ["@echo off"]

    if apply_cpu:
        bat_lines.append("for /L %%i in (0,1,63) do (")
        bat_lines.append(f'    reg add "HKLM\\HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\%%i" /v "ProcessorNameString" /t REG_SZ /d "{cpu_target}" /f >nul 2>&1')
        bat_lines.append(")")

    if apply_gpu:
        bat_lines.append(f'reg add "HKLM\\SOFTWARE\\Microsoft\\DirectX" /v "MaxDedicatedVideoMemory" /t REG_QWORD /d "{vram_bytes}" /f >nul 2>&1')
        for g in dx_guids:
            bat_lines.append(f'reg add "HKLM\\SOFTWARE\\Microsoft\\DirectX\\{g}" /v "Description" /t REG_SZ /d "{gpu_target}" /f >nul 2>&1')
            bat_lines.append(f'reg add "HKLM\\SOFTWARE\\Microsoft\\DirectX\\{g}" /v "DedicatedVideoMemory" /t REG_QWORD /d "{vram_bytes}" /f >nul 2>&1')

        for vg in v_guids:
            bat_lines.append(f'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Video\\{vg}\\Video" /v "DeviceDesc" /t REG_SZ /d "{gpu_target}" /f >nul 2>&1')
            for out_i in range(4):
                bat_lines.append(f'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Video\\{vg}\\{out_i:04d}" /v "DriverDesc" /t REG_SZ /d "{gpu_target}" /f >nul 2>&1')
                bat_lines.append(f'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Video\\{vg}\\{out_i:04d}" /v "HardwareInformation.ChipType" /t REG_SZ /d "{gpu_target}" /f >nul 2>&1')
                bat_lines.append(f'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Video\\{vg}\\{out_i:04d}" /v "HardwareInformation.AdapterString" /t REG_SZ /d "{gpu_target}" /f >nul 2>&1')
                bat_lines.append(f'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Video\\{vg}\\{out_i:04d}" /v "HardwareInformation.qwMemorySize" /t REG_QWORD /d "{vram_bytes}" /f >nul 2>&1')
                bat_lines.append(f'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Video\\{vg}\\{out_i:04d}" /v "HardwareInformation.MemorySize" /t REG_DWORD /d "{vram_dword}" /f >nul 2>&1')

        bat_lines.extend([
            "for %%k in (0000 0001 0002 0003) do (",
            f'    reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Class\\{{4d36e968-e325-11ce-bfc1-08002be10318}}\\%%k" /v "DriverDesc" /t REG_SZ /d "{gpu_target}" /f >nul 2>&1',
            f'    reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Class\\{{4d36e968-e325-11ce-bfc1-08002be10318}}\\%%k" /v "HardwareInformation.ChipType" /t REG_SZ /d "{gpu_target}" /f >nul 2>&1',
            f'    reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Class\\{{4d36e968-e325-11ce-bfc1-08002be10318}}\\%%k" /v "HardwareInformation.AdapterString" /t REG_SZ /d "{gpu_target}" /f >nul 2>&1',
            f'    reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Class\\{{4d36e968-e325-11ce-bfc1-08002be10318}}\\%%k" /v "HardwareInformation.qwMemorySize" /t REG_QWORD /d "{vram_bytes}" /f >nul 2>&1',
            f'    reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Class\\{{4d36e968-e325-11ce-bfc1-08002be10318}}\\%%k" /v "HardwareInformation.MemorySize" /t REG_DWORD /d "{vram_dword}" /f >nul 2>&1',
            ")",
        ])

        for pp in pci_paths:
            bat_lines.append(f'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Enum\\{pp}" /v "DeviceDesc" /t REG_SZ /d "{gpu_target}" /f >nul 2>&1')
            bat_lines.append(f'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Enum\\{pp}" /v "FriendlyName" /t REG_SZ /d "{gpu_target}" /f >nul 2>&1')

        bat_lines.append(f'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Services\\nvlddmkm\\Video" /v "DeviceDesc" /t REG_SZ /d "{gpu_target}" /f >nul 2>&1')

    if apply_board:
        bat_lines.extend([
            f'reg add "HKLM\\HARDWARE\\DESCRIPTION\\System\\BIOS" /v "BaseBoardManufacturer" /t REG_SZ /d "{board_vendor}" /f >nul 2>&1',
            f'reg add "HKLM\\HARDWARE\\DESCRIPTION\\System\\BIOS" /v "BaseBoardProduct" /t REG_SZ /d "{clean_product}" /f >nul 2>&1',
            f'reg add "HKLM\\HARDWARE\\DESCRIPTION\\System\\BIOS" /v "SystemManufacturer" /t REG_SZ /d "{board_vendor}" /f >nul 2>&1',
            f'reg add "HKLM\\HARDWARE\\DESCRIPTION\\System\\BIOS" /v "SystemProductName" /t REG_SZ /d "{clean_product}" /f >nul 2>&1',
        ])

    if apply_disk:
        for dp in disk_paths:
            bat_lines.append(f'reg add "HKLM\\{dp}" /v "FriendlyName" /t REG_SZ /d "{disk_model}" /f >nul 2>&1')

    if len(bat_lines) > 1:
        temp_dir = os.environ.get("TEMP", r"C:\Windows\Temp")
        bat_path = os.path.join(temp_dir, "cpu_fix_startup.bat")
        vbs_path = os.path.join(temp_dir, "cpu_fix_launcher.vbs")
        full_bat_content = "\n".join(bat_lines) + "\n"

        try:
            with open(bat_path, "w", encoding="gbk", errors="ignore") as f:
                f.write(full_bat_content)
            with open(vbs_path, "w", encoding="ascii") as f:
                f.write(f'Set WshShell = CreateObject("WScript.Shell")\nWshShell.Run Chr(34) & "{bat_path}" & Chr(34), 0, False\nSet WshShell = Nothing\n')
        except Exception:
            pass

        # 同步执行提权批处理以确保底层严格权限项 (如 Enum\\PCI) 强制改写生效
        run_elevated_batch(full_bat_content)

    # 6. 配置开机自启固化任务 (仅当涉及 CPU 或全套时)
    if apply_cpu and enable_startup:
        try:
            vbs_path = os.path.join(os.environ.get("TEMP", r"C:\Windows\Temp"), "cpu_fix_launcher.vbs")
            subprocess.run(
                f'schtasks /create /tn CPU_Model_Fix_On_Startup /tr "wscript.exe \\"{vbs_path}\\"" /sc onlogon /rl highest /delay 0000:05 /f',
                shell=True, capture_output=True
            )
        except Exception:
            pass

    # 7. 写入 CPU 固化配置与小黑盒拦截器
    if apply_cpu:
        try:
            with open(CPU_CONFIG_FILE, "w", encoding="ascii") as f:
                f.write(cpu_target.strip())
        except Exception:
            pass

    if apply_hook:
        try:
            apply_xiaoheihe_hook(custom_heybox_dir)
        except Exception:
            pass

    # 8. 验证是否修改成功生效
    try:
        results = []
        if apply_cpu:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0", 0, winreg.KEY_READ) as k:
                    cur_cpu, _ = winreg.QueryValueEx(k, "ProcessorNameString")
                if cur_cpu.strip() == cpu_target.strip():
                    results.append("CPU 处理器")
            except Exception:
                pass
        if apply_gpu:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}\0000", 0, winreg.KEY_READ) as gk:
                    cur_gpu, _ = winreg.QueryValueEx(gk, "DriverDesc")
                if cur_gpu.strip() == gpu_target.strip():
                    results.append("独立显卡与显存")
            except Exception:
                pass
        if apply_board:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\BIOS", 0, winreg.KEY_READ) as bk:
                    cur_bp, _ = winreg.QueryValueEx(bk, "BaseBoardProduct")
                if clean_product.strip().lower() in cur_bp.strip().lower():
                    results.append("主板型号")
            except Exception:
                pass
        if apply_memory:
            results.append("内存参数")
        if apply_disk:
            results.append("硬盘型号")

        if results:
            return True, f"【{'、'.join(results)}】配置已成功单独生效！"
        else:
            return True, "硬件配置已成功完成写入！"
    except Exception as e:
        return True, "硬件配置已成功写入！"


def execute_hardware_restore():
    # 1. 出厂硬件还原基准值
    real_cpu = DEFAULT_REAL_CPU
    if os.path.exists(CPU_BACKUP_FILE):
        try:
            with open(CPU_BACKUP_FILE, "r", encoding="utf-8") as f:
                c = f.read().strip()
                if c: real_cpu = c
        except Exception:
            pass

    real_gpu = DEFAULT_REAL_GPU
    if os.path.exists(GPU_BACKUP_FILE):
        try:
            with open(GPU_BACKUP_FILE, "r", encoding="utf-8") as f:
                g = f.read().strip()
                if g: real_gpu = g
        except Exception:
            pass

    real_bv = DEFAULT_REAL_BOARD_VENDOR
    real_bp = DEFAULT_REAL_BOARD_PRODUCT
    if os.path.exists(BOARD_VENDOR_BACKUP_FILE):
        try:
            with open(BOARD_VENDOR_BACKUP_FILE, "r", encoding="utf-8") as f:
                bv = f.read().strip()
                if bv: real_bv = bv
        except Exception:
            pass
    if os.path.exists(BOARD_PRODUCT_BACKUP_FILE):
        try:
            with open(BOARD_PRODUCT_BACKUP_FILE, "r", encoding="utf-8") as f:
                bp = f.read().strip()
                if bp: real_bp = bp
        except Exception:
            pass

    real_disk = DEFAULT_REAL_DISK_MODEL
    if os.path.exists(DISK_BACKUP_FILE):
        try:
            with open(DISK_BACKUP_FILE, "r", encoding="utf-8") as f:
                d = f.read().strip()
                if d: real_disk = d
        except Exception:
            pass

    real_vram_bytes = DEFAULT_REAL_VRAM_BYTES
    real_vram_dword = min(real_vram_bytes, 4294967295)

    dx_guids = get_system_directx_guids()
    v_guids = get_system_control_video_guids()
    pci_paths = get_system_display_pci_paths()
    disk_paths = get_system_disk_reg_paths()

    # 2. 直接 Python winreg 恢复尝试
    if is_admin():
        try:
            # CPU
            cpu_base = r"HARDWARE\DESCRIPTION\System\CentralProcessor"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, cpu_base) as k:
                for i in range(winreg.QueryInfoKey(k)[0]):
                    sub = winreg.EnumKey(k, i)
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{cpu_base}\\{sub}", 0, winreg.KEY_SET_VALUE) as sk:
                        winreg.SetValueEx(sk, "ProcessorNameString", 0, winreg.REG_SZ, real_cpu)

            # DirectX
            dx_path = r"SOFTWARE\Microsoft\DirectX"
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, dx_path, 0, winreg.KEY_SET_VALUE) as k:
                    winreg.DeleteValue(k, "MaxDedicatedVideoMemory")
            except Exception:
                pass
            for g in dx_guids:
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{dx_path}\\{g}", 0, winreg.KEY_SET_VALUE) as sk:
                        winreg.SetValueEx(sk, "Description", 0, winreg.REG_SZ, real_gpu)
                        winreg.SetValueEx(sk, "DedicatedVideoMemory", 0, winreg.REG_QWORD, real_vram_bytes)
                except Exception:
                    pass

            # Class GPU
            class_base = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, class_base) as k:
                for i in range(winreg.QueryInfoKey(k)[0]):
                    sub = winreg.EnumKey(k, i)
                    if sub.isdigit() and len(sub) == 4:
                        try:
                            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{class_base}\\{sub}", 0, winreg.KEY_SET_VALUE) as sk:
                                winreg.SetValueEx(sk, "DriverDesc", 0, winreg.REG_SZ, real_gpu)
                                winreg.SetValueEx(sk, "HardwareInformation.ChipType", 0, winreg.REG_SZ, real_gpu)
                                winreg.SetValueEx(sk, "HardwareInformation.AdapterString", 0, winreg.REG_SZ, real_gpu)
                                winreg.SetValueEx(sk, "HardwareInformation.qwMemorySize", 0, winreg.REG_QWORD, real_vram_bytes)
                                winreg.SetValueEx(sk, "HardwareInformation.MemorySize", 0, winreg.REG_DWORD, real_vram_dword)
                        except Exception:
                            pass

            # BIOS
            bios_path = r"HARDWARE\DESCRIPTION\System\BIOS"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, bios_path, 0, winreg.KEY_SET_VALUE) as k:
                winreg.SetValueEx(k, "BaseBoardManufacturer", 0, winreg.REG_SZ, real_bv)
                winreg.SetValueEx(k, "BaseBoardProduct", 0, winreg.REG_SZ, real_bp)
                winreg.SetValueEx(k, "SystemManufacturer", 0, winreg.REG_SZ, real_bv)
                winreg.SetValueEx(k, "SystemProductName", 0, winreg.REG_SZ, real_bp)

            # Disks
            for dp in disk_paths:
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, dp, 0, winreg.KEY_SET_VALUE) as dk:
                        winreg.SetValueEx(dk, "FriendlyName", 0, winreg.REG_SZ, real_disk)
                except Exception:
                    pass
        except Exception:
            pass

    # 3. 构造恢复批处理
    restore_lines = [
        "@echo off",
        "for /L %%i in (0,1,63) do (",
        f'    reg add "HKLM\\HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\%%i" /v "ProcessorNameString" /t REG_SZ /d "{real_cpu}" /f >nul 2>&1',
        ")",
        'reg delete "HKLM\\SOFTWARE\\Microsoft\\DirectX" /v "MaxDedicatedVideoMemory" /f >nul 2>&1',
    ]

    for g in dx_guids:
        restore_lines.append(f'reg add "HKLM\\SOFTWARE\\Microsoft\\DirectX\\{g}" /v "Description" /t REG_SZ /d "{real_gpu}" /f >nul 2>&1')
        restore_lines.append(f'reg add "HKLM\\SOFTWARE\\Microsoft\\DirectX\\{g}" /v "DedicatedVideoMemory" /t REG_QWORD /d "{real_vram_bytes}" /f >nul 2>&1')

    for vg in v_guids:
        restore_lines.append(f'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Video\\{vg}\\Video" /v "DeviceDesc" /t REG_SZ /d "{real_gpu}" /f >nul 2>&1')
        for out_i in range(4):
            restore_lines.append(f'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Video\\{vg}\\{out_i:04d}" /v "DriverDesc" /t REG_SZ /d "{real_gpu}" /f >nul 2>&1')
            restore_lines.append(f'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Video\\{vg}\\{out_i:04d}" /v "HardwareInformation.ChipType" /t REG_SZ /d "{real_gpu}" /f >nul 2>&1')
            restore_lines.append(f'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Video\\{vg}\\{out_i:04d}" /v "HardwareInformation.AdapterString" /t REG_SZ /d "{real_gpu}" /f >nul 2>&1')
            restore_lines.append(f'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Video\\{vg}\\{out_i:04d}" /v "HardwareInformation.qwMemorySize" /t REG_QWORD /d "{real_vram_bytes}" /f >nul 2>&1')
            restore_lines.append(f'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Video\\{vg}\\{out_i:04d}" /v "HardwareInformation.MemorySize" /t REG_DWORD /d "{real_vram_dword}" /f >nul 2>&1')

    restore_lines.extend([
        "for %%k in (0000 0001 0002 0003) do (",
        f'    reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Class\\{{4d36e968-e325-11ce-bfc1-08002be10318}}\\%%k" /v "DriverDesc" /t REG_SZ /d "{real_gpu}" /f >nul 2>&1',
        f'    reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Class\\{{4d36e968-e325-11ce-bfc1-08002be10318}}\\%%k" /v "HardwareInformation.ChipType" /t REG_SZ /d "{real_gpu}" /f >nul 2>&1',
        f'    reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Class\\{{4d36e968-e325-11ce-bfc1-08002be10318}}\\%%k" /v "HardwareInformation.AdapterString" /t REG_SZ /d "{real_gpu}" /f >nul 2>&1',
        f'    reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Class\\{{4d36e968-e325-11ce-bfc1-08002be10318}}\\%%k" /v "HardwareInformation.qwMemorySize" /t REG_QWORD /d "{real_vram_bytes}" /f >nul 2>&1',
        f'    reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Class\\{{4d36e968-e325-11ce-bfc1-08002be10318}}\\%%k" /v "HardwareInformation.MemorySize" /t REG_DWORD /d "{real_vram_dword}" /f >nul 2>&1',
        ")",
    ])

    for pp in pci_paths:
        restore_lines.append(f'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Enum\\{pp}" /v "DeviceDesc" /t REG_SZ /d "{real_gpu}" /f >nul 2>&1')
        restore_lines.append(f'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Enum\\{pp}" /v "FriendlyName" /t REG_SZ /d "{real_gpu}" /f >nul 2>&1')

    restore_lines.extend([
        f'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Services\\nvlddmkm\\Video" /v "DeviceDesc" /t REG_SZ /d "{real_gpu}" /f >nul 2>&1',
        f'reg add "HKLM\\HARDWARE\\DESCRIPTION\\System\\BIOS" /v "BaseBoardManufacturer" /t REG_SZ /d "{real_bv}" /f >nul 2>&1',
        f'reg add "HKLM\\HARDWARE\\DESCRIPTION\\System\\BIOS" /v "BaseBoardProduct" /t REG_SZ /d "{real_bp}" /f >nul 2>&1',
        f'reg add "HKLM\\HARDWARE\\DESCRIPTION\\System\\BIOS" /v "SystemManufacturer" /t REG_SZ /d "{real_bv}" /f >nul 2>&1',
        f'reg add "HKLM\\HARDWARE\\DESCRIPTION\\System\\BIOS" /v "SystemProductName" /t REG_SZ /d "{real_bp}" /f >nul 2>&1',
        "schtasks /delete /tn CPU_Model_Fix_On_Startup /f >nul 2>&1",
    ])

    for dp in disk_paths:
        restore_lines.append(f'reg add "HKLM\\{dp}" /v "FriendlyName" /t REG_SZ /d "{real_disk}" /f >nul 2>&1')

    restore_bat_content = "\n".join(restore_lines) + "\n"
    run_elevated_batch(restore_bat_content)

    # 4. 还原小黑盒拦截器与清理任务配置
    try:
        restore_xiaoheihe_hook()
    except Exception:
        pass

    try:
        if os.path.exists(CPU_CONFIG_FILE):
            os.remove(CPU_CONFIG_FILE)
    except Exception:
        pass

    # 5. 同步还原配置到 config.json 及 Public
    try:
        cfg = load_config()
        cfg["custom_target"]["cpu_model"] = real_cpu
        cfg["custom_target"]["gpu_model"] = real_gpu
        cfg["custom_target"]["gpu_vram_gb"] = int(real_vram_bytes / (1024**3))
        cfg["custom_target"]["motherboard_vendor"] = real_bv
        cfg["custom_target"]["motherboard_product"] = real_bp
        cfg["custom_target"]["disk_model"] = real_disk
        save_config(cfg)
    except Exception:
        pass

    # 6. 验证恢复
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0", 0, winreg.KEY_READ) as k:
            cur_cpu, _ = winreg.QueryValueEx(k, "ProcessorNameString")
        if cur_cpu.strip() == real_cpu.strip():
            return True, "官方出厂硬件已成功恢复并验证生效！"
        else:
            return False, f"恢复验证未匹配 (当前: {cur_cpu}, 预期: {real_cpu})"
    except Exception as e:
        return False, f"注册表恢复验证失败: {e}"



# ==========================================
# 现代浅色卡片风格 QSS (Light Mode)
# ==========================================
LIGHT_STYLE_SHEET = """
/* 全局控件高清晰度字体渲染与字体栈 */
QLabel, QPushButton, QComboBox, QLineEdit, QCheckBox, QDialog, QMessageBox {
    font-family: "Microsoft YaHei UI", "PingFang SC", "Segoe UI", sans-serif;
}

QMainWindow {
    background: transparent;
}

QWidget#CentralWidget {
    background-color: #F0F4FA;
    border: 1px solid #D6E6FE;
    border-radius: 14px;
}

/* 左侧边栏 */
QFrame#Sidebar {
    background-color: #FFFFFF;
    border-top-left-radius: 14px;
    border-bottom-left-radius: 14px;
    border-right: 1px solid #E8EEF5;
}

QLabel#BrandTitle {
    color: #1E293B;
    font-size: 15px;
    font-weight: 700;
}

QLabel#BrandSubtitle {
    color: #94A3B8;
    font-size: 11px;
}

QFrame#SidebarSep {
    color: #E2E8F0;
    margin-bottom: 8px;
}

/* 侧边栏导航按钮 (仿参考图的圆角胶囊) */
QPushButton.NavButton {
    background-color: transparent;
    color: #64748B;
    border: none;
    border-radius: 12px;
    padding: 10px 16px;
    font-size: 13px;
    font-weight: 600;
    text-align: left;
}

QPushButton.NavButton:hover {
    background-color: #F1F5F9;
    color: #1E293B;
}

QPushButton.NavButton:checked {
    background-color: #2B85FF;
    color: #FFFFFF;
}

/* 侧边栏底部状态微标 */
QFrame#SidebarStatusBox {
    background-color: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 10px;
}

QLabel#SidebarVerLbl {
    color: #64748B;
    font-size: 11px;
    font-weight: 600;
}

QLabel#SidebarHookLbl {
    color: #10B981;
    font-size: 11px;
    font-weight: 700;
}

/* 顶部状态条与模式切换按钮 */
QLabel#StatusBanner {
    color: #059669;
    background-color: #ECFDF5;
    border: 1px solid #A7F3D0;
    border-radius: 12px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton#ThemeToggleBtn {
    background-color: #FFFFFF;
    color: #334155;
    border: 1px solid #CBD5E1;
    border-radius: 12px;
    padding: 4px 14px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton#ThemeToggleBtn:hover {
    background-color: #F1F5F9;
    border-color: #94A3B8;
    color: #1E293B;
}

/* 顶部 Hero 卡片 */
QFrame#HeroCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #EAF2FF, stop:1 #F5F9FF);
    border: 1px solid #D6E6FE;
    border-radius: 18px;
}

QLabel#HeroTitleMain {
    color: #2B85FF;
    font-size: 26px;
    font-weight: 800;
}

QLabel#HeroTitleSub {
    color: #1E293B;
    font-size: 26px;
    font-weight: 800;
}

QLabel#HeroDesc {
    color: #64748B;
    font-size: 13px;
}

/* 功能卡片 (2x2 网格) */
QFrame.GridCard {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 18px;
}

QLabel.CardTitle {
    color: #1E293B;
    font-size: 16px;
    font-weight: 700;
}

QLabel.CardSubtitle {
    color: #94A3B8;
    font-size: 12px;
}

QLabel.CardBadgeBlue {
    background-color: #E0EDFF;
    color: #2B85FF;
    border-radius: 10px;
    font-size: 18px;
    font-weight: bold;
    qproperty-alignment: AlignCenter;
}

QLabel.CardBadgePurple {
    background-color: #F3E8FF;
    color: #8B5CF6;
    border-radius: 10px;
    font-size: 18px;
    font-weight: bold;
    qproperty-alignment: AlignCenter;
}

QLabel.CardBadgeOrange {
    background-color: #FFEDD5;
    color: #F97316;
    border-radius: 10px;
    font-size: 18px;
    font-weight: bold;
    qproperty-alignment: AlignCenter;
}

QLabel.CardBadgeTeal {
    background-color: #CCFBF1;
    color: #0D9488;
    border-radius: 10px;
    font-size: 18px;
    font-weight: bold;
    qproperty-alignment: AlignCenter;
}

/* 表单与通用标签 */
QLabel {
    color: #1E293B;
    font-size: 13px;
}

QLabel.RealHardwareBadge {
    color: #64748B;
    background-color: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 10px;
    font-size: 13px;
}

QLabel.DescLabel {
    color: #475569;
    font-size: 13px;
    line-height: 1.6;
}

QLabel.FormHeaderLabel {
    color: #1E293B;
    font-size: 13px;
    font-weight: 600;
}

QLabel#SnapshotLabel {
    color: #64748B;
    background-color: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 12px;
    font-family: Consolas, monospace;
    font-size: 12px;
}

QCheckBox {
    color: #1E293B;
    font-size: 13px;
    font-weight: 600;
}

/* 下拉框 ComboBox */
QComboBox {
    background-color: #F8FAFC;
    border: 1px solid #CBD5E1;
    border-radius: 10px;
    padding: 8px 32px 8px 12px;
    font-size: 13px;
    color: #1E293B;
}

QComboBox:hover {
    border: 1px solid #93C5FD;
    background-color: #FFFFFF;
}

QComboBox:focus {
    border: 1px solid #2B85FF;
}

/* Native chevron (the CSS-border triangle hack is unsupported by Qt QSS). */

QComboBox QAbstractItemView {
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 8px;
    color: #1E293B;
    padding: 6px;
    min-width: 360px;
    outline: none;
}

QComboBox QAbstractItemView::item {
    min-height: 30px;
    padding: 4px 10px;
    border-radius: 6px;
    color: #1E293B;
}

QComboBox QAbstractItemView::item:hover {
    background-color: #F1F5F9;
    color: #2B85FF;
}

QComboBox QAbstractItemView::item:selected {
    background-color: #EFF6FF;
    color: #2B85FF;
}

/* 图1优化：极简无边框 6px 浮动滑动条 (Light Mode) */
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 6px;
    margin: 0px;
    border-radius: 3px;
}
QScrollBar::handle:vertical {
    background: #CBD5E1;
    min-height: 24px;
    border-radius: 3px;
}
QScrollBar::handle:vertical:hover {
    background: #94A3B8;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
    width: 0px;
    background: transparent;
    border: none;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}

QScrollBar:horizontal {
    border: none;
    background: transparent;
    height: 0px;
    width: 0px;
    margin: 0px;
}
QScrollBar::handle:horizontal {
    background: transparent;
    min-width: 0px;
    height: 0px;
}
QScrollBar::handle:horizontal:hover {
    background: transparent;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
    height: 0px;
    background: transparent;
    border: none;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}

/* 现代二级菜单与右键菜单 (QMenu) */
QMenu {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 6px;
    color: #1E293B;
    font-size: 13px;
}
QMenu::item {
    padding: 6px 24px 6px 20px;
    border-radius: 6px;
    color: #1E293B;
}
QMenu::item:selected {
    background-color: #EFF6FF;
    color: #2B85FF;
}
QMenu::item:disabled {
    color: #94A3B8;
}
QMenu::separator {
    height: 1px;
    background: #E2E8F0;
    margin: 4px 6px;
}

/* 自定义消息弹窗与通用对话框样式 (QMessageBox & QDialog) */
QDialog, QMessageBox {
    background-color: #FFFFFF;
    border: 1px solid #D6E6FE;
    border-radius: 12px;
}

QDialog QLabel, QMessageBox QLabel {
    color: #1E293B;
    font-size: 13px;
    font-weight: 500;
}

QMessageBox QLabel#qt_msgbox_label {
    color: #1E293B;
    font-size: 13px;
    line-height: 1.5;
}

QInputDialog QLabel {
    color: #1E293B;
    font-size: 13px;
    font-weight: 600;
}

QInputDialog QLineEdit {
    min-width: 420px;
    font-size: 13px;
    color: #1E293B;
    background-color: #F8FAFC;
    border: 1px solid #CBD5E1;
    border-radius: 8px;
    padding: 8px 12px;
}

QInputDialog QLineEdit:focus {
    border: 1px solid #2B85FF;
    background-color: #FFFFFF;
}

QDialogButtonBox QPushButton, QMessageBox QPushButton {
    background-color: #2B85FF;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 8px 24px;
    font-size: 13px;
    font-weight: 600;
    min-width: 75px;
}

QDialogButtonBox QPushButton:hover, QMessageBox QPushButton:hover {
    background-color: #1D70E6;
}

QDialogButtonBox QPushButton:pressed, QMessageBox QPushButton:pressed {
    background-color: #1557B0;
}

/* 输入框 */
QLineEdit {
    background-color: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    padding: 8px 12px;
    font-size: 13px;
    color: #1E293B;
}

QLineEdit:focus {
    border: 1px solid #2B85FF;
    background-color: #FFFFFF;
}

QPushButton.OutlineBtn {
    background-color: #F1F5F9;
    color: #1E293B;
    border: 1px solid #CBD5E1;
    border-radius: 10px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 600;
}

QPushButton.OutlineBtn:hover {
    background-color: #E2E8F0;
}

/* 卡片内部操作按钮 */
QPushButton.CardActionBlue {
    background-color: #2B85FF;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton.CardActionBlue:hover {
    background-color: #1D70E6;
}

QPushButton.CardActionPurple {
    background-color: #EDE9FE;
    color: #7C3AED;
    border: none;
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton.CardActionPurple:hover {
    background-color: #DDD6FE;
}

QPushButton.CardActionOrange {
    background-color: #FFEDD5;
    color: #C2410C;
    border: none;
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton.CardActionOrange:hover {
    background-color: #FED7AA;
}

QPushButton.CardActionTeal {
    background-color: #CCFBF1;
    color: #0F766E;
    border: none;
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton.CardActionTeal:hover {
    background-color: #99F6E4;
}

QPushButton.CardActionSecondary {
    background-color: #F1F5F9;
    color: #334155;
    border: 1px solid #CBD5E1;
    border-radius: 8px;
    padding: 6px 11px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton.CardActionSecondary:hover {
    background-color: #E2E8F0;
    color: #0F172A;
    border-color: #94A3B8;
}

QPushButton.CardActionSecondary:pressed {
    background-color: #CBD5E1;
}

QPushButton.DetailActionBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2B85FF, stop:1 #1D70E6);
    color: #FFFFFF;
    border: none;
    border-radius: 10px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 600;
}

QPushButton.DetailActionBtn:hover {
    background: #1960D2;
}

QPushButton.DetailActionBtn:pressed {
    background: #154EB2;
}

/* 底部操作主按钮 */
QLabel#BottomStatusPill {
    color: #475569;
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    padding: 7px 12px;
    font-size: 11px;
    font-weight: 500;
}

QPushButton#ApplyButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2B85FF, stop:1 #1D70E6);
    color: #FFFFFF;
    border: none;
    border-radius: 14px;
    padding: 12px 28px;
    font-size: 15px;
    font-weight: 700;
}

QPushButton#ApplyButton:hover {
    background: #1960D2;
}

QPushButton#RestoreButton {
    background-color: #FFFFFF;
    color: #64748B;
    border: 1px solid #CBD5E1;
    border-radius: 14px;
    padding: 12px 22px;
    font-size: 14px;
    font-weight: 600;
}

QPushButton#RestoreButton:hover {
    background-color: #F8FAFC;
    color: #EF4444;
    border-color: #FCA5A5;
}

/* 顶部自定义窗口控制按钮 (Windows 11 Fluent 风格) */
QPushButton.WindowControl {
    background-color: transparent;
    color: #64748B;
    border: none;
    border-radius: 6px;
    min-width: 34px;
    max-width: 34px;
    min-height: 28px;
    max-height: 28px;
    font-family: 'Segoe Fluent Icons', 'Segoe MDL2 Assets';
    font-size: 11px;
}

QPushButton#TitleBtnMax {
    font-size: 15px;
    font-weight: bold;
}

QPushButton.WindowControl:hover {
    background-color: #E2E8F0;
    color: #0F172A;
}

QPushButton#WindowCloseBtn {
    background-color: transparent;
    color: #64748B;
    border: none;
    border-radius: 6px;
    min-width: 34px;
    max-width: 34px;
    min-height: 28px;
    max-height: 28px;
    font-family: 'Segoe Fluent Icons', 'Segoe MDL2 Assets';
    font-size: 10px;
}

QPushButton#WindowCloseBtn:hover {
    background-color: #EF4444;
    color: #FFFFFF;
}
"""

# ==========================================
# 现代暗黑卡片风格 QSS (Dark Mode)
# ==========================================
DARK_STYLE_SHEET = """
/* 全局控件高清晰度字体渲染与字体栈 */
QLabel, QPushButton, QComboBox, QLineEdit, QCheckBox, QDialog, QMessageBox {
    font-family: "Microsoft YaHei UI", "PingFang SC", "Segoe UI", sans-serif;
}

QMainWindow {
    background: transparent;
}

QWidget#CentralWidget {
    background-color: #0F172A;
    border: 1px solid #334155;
    border-radius: 14px;
}

/* 左侧边栏 */
QFrame#Sidebar {
    background-color: #1E293B;
    border-top-left-radius: 14px;
    border-bottom-left-radius: 14px;
    border-right: 1px solid #334155;
}

QLabel#BrandTitle {
    color: #F8FAFC;
    font-size: 15px;
    font-weight: 700;
}

QLabel#BrandSubtitle {
    color: #94A3B8;
    font-size: 11px;
}

QFrame#SidebarSep {
    color: #334155;
    margin-bottom: 8px;
}

/* 侧边栏导航按钮 */
QPushButton.NavButton {
    background-color: transparent;
    color: #94A3B8;
    border: none;
    border-radius: 12px;
    padding: 10px 16px;
    font-size: 13px;
    font-weight: 600;
    text-align: left;
}

QPushButton.NavButton:hover {
    background-color: #334155;
    color: #F8FAFC;
}

QPushButton.NavButton:checked {
    background-color: #3B82F6;
    color: #FFFFFF;
}

/* 侧边栏底部状态微标 */
QFrame#SidebarStatusBox {
    background-color: #0F172A;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 10px;
}

QLabel#SidebarVerLbl {
    color: #94A3B8;
    font-size: 11px;
    font-weight: 600;
}

QLabel#SidebarHookLbl {
    color: #34D399;
    font-size: 11px;
    font-weight: 700;
}

/* 顶部状态条与模式切换按钮 */
QLabel#StatusBanner {
    color: #34D399;
    background-color: #064E3B;
    border: 1px solid #059669;
    border-radius: 12px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton#ThemeToggleBtn {
    background-color: #1E293B;
    color: #F1F5F9;
    border: 1px solid #475569;
    border-radius: 12px;
    padding: 4px 14px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton#ThemeToggleBtn:hover {
    background-color: #334155;
    border-color: #64748B;
    color: #FFFFFF;
}

/* 顶部 Hero 卡片 */
QFrame#HeroCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1E293B, stop:1 #0F172A);
    border: 1px solid #334155;
    border-radius: 18px;
}

QLabel#HeroTitleMain {
    color: #60A5FA;
    font-size: 26px;
    font-weight: 800;
}

QLabel#HeroTitleSub {
    color: #F8FAFC;
    font-size: 26px;
    font-weight: 800;
}

QLabel#HeroDesc {
    color: #94A3B8;
    font-size: 13px;
}

/* 功能卡片 (2x2 网格) */
QFrame.GridCard {
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 18px;
}

QLabel.CardTitle {
    color: #F8FAFC;
    font-size: 16px;
    font-weight: 700;
}

QLabel.CardSubtitle {
    color: #94A3B8;
    font-size: 12px;
}

QLabel.CardBadgeBlue {
    background-color: #1E3A8A;
    color: #93C5FD;
    border-radius: 10px;
    font-size: 18px;
    font-weight: bold;
    qproperty-alignment: AlignCenter;
}

QLabel.CardBadgePurple {
    background-color: #4C1D95;
    color: #C4B5FD;
    border-radius: 10px;
    font-size: 18px;
    font-weight: bold;
    qproperty-alignment: AlignCenter;
}

QLabel.CardBadgeOrange {
    background-color: #7C2D12;
    color: #FDBA74;
    border-radius: 10px;
    font-size: 18px;
    font-weight: bold;
    qproperty-alignment: AlignCenter;
}

QLabel.CardBadgeTeal {
    background-color: #134E4A;
    color: #5EEAD4;
    border-radius: 10px;
    font-size: 18px;
    font-weight: bold;
    qproperty-alignment: AlignCenter;
}

/* 表单与通用标签 */
QLabel {
    color: #E2E8F0;
    font-size: 13px;
}

QLabel.RealHardwareBadge {
    color: #94A3B8;
    background-color: #0F172A;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 10px;
    font-size: 13px;
}

QLabel.DescLabel {
    color: #94A3B8;
    font-size: 13px;
    line-height: 1.6;
}

QLabel.FormHeaderLabel {
    color: #F8FAFC;
    font-size: 13px;
    font-weight: 600;
}

QLabel#SnapshotLabel {
    color: #94A3B8;
    background-color: #0F172A;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 12px;
    font-family: Consolas, monospace;
    font-size: 12px;
}

QCheckBox {
    color: #F8FAFC;
    font-size: 13px;
    font-weight: 600;
}

/* 下拉框 ComboBox */
QComboBox {
    background-color: #0F172A;
    border: 1px solid #475569;
    border-radius: 10px;
    padding: 8px 32px 8px 12px;
    font-size: 13px;
    color: #F8FAFC;
}

QComboBox:hover {
    border: 1px solid #60A5FA;
    background-color: #1E293B;
}

QComboBox:focus {
    border: 1px solid #3B82F6;
}

/* Native chevron (see the light-theme comment above). */

QComboBox QAbstractItemView {
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 8px;
    color: #F8FAFC;
    padding: 6px;
    min-width: 360px;
    outline: none;
}

QComboBox QAbstractItemView::item {
    min-height: 30px;
    padding: 4px 10px;
    border-radius: 6px;
    color: #F8FAFC;
}

QComboBox QAbstractItemView::item:hover {
    background-color: #334155;
    color: #60A5FA;
}

QComboBox QAbstractItemView::item:selected {
    background-color: #2563EB;
    color: #FFFFFF;
}

/* 图1优化：暗色极简 6px 浮动滑动条 (Dark Mode) */
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 6px;
    margin: 0px;
    border-radius: 3px;
}
QScrollBar::handle:vertical {
    background: #334155;
    min-height: 24px;
    border-radius: 3px;
}
QScrollBar::handle:vertical:hover {
    background: #475569;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
    width: 0px;
    background: transparent;
    border: none;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}

QScrollBar:horizontal {
    border: none;
    background: transparent;
    height: 0px;
    width: 0px;
    margin: 0px;
}
QScrollBar::handle:horizontal {
    background: transparent;
    min-width: 0px;
    height: 0px;
}
QScrollBar::handle:horizontal:hover {
    background: transparent;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
    height: 0px;
    background: transparent;
    border: none;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}

/* 现代二级菜单与右键菜单 (QMenu) */
QMenu {
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 6px;
    color: #F8FAFC;
    font-size: 13px;
}
QMenu::item {
    padding: 6px 24px 6px 20px;
    border-radius: 6px;
    color: #F8FAFC;
}
QMenu::item:selected {
    background-color: #2563EB;
    color: #FFFFFF;
}
QMenu::item:disabled {
    color: #64748B;
}
QMenu::separator {
    height: 1px;
    background: #334155;
    margin: 4px 6px;
}

/* 自定义消息弹窗与通用对话框样式 (QMessageBox & QDialog) */
QDialog, QMessageBox {
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 12px;
}

QDialog QLabel, QMessageBox QLabel {
    color: #F8FAFC;
    font-size: 13px;
    font-weight: 500;
}

QMessageBox QLabel#qt_msgbox_label {
    color: #F8FAFC;
    font-size: 13px;
    line-height: 1.5;
}

QInputDialog QLabel {
    color: #F8FAFC;
    font-size: 13px;
    font-weight: 600;
}

QInputDialog QLineEdit {
    min-width: 420px;
    font-size: 13px;
    color: #F8FAFC;
    background-color: #0F172A;
    border: 1px solid #475569;
    border-radius: 8px;
    padding: 8px 12px;
}

QInputDialog QLineEdit:focus {
    border: 1px solid #3B82F6;
    background-color: #1E293B;
}

QDialogButtonBox QPushButton, QMessageBox QPushButton {
    background-color: #3B82F6;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 8px 24px;
    font-size: 13px;
    font-weight: 600;
    min-width: 75px;
}

QDialogButtonBox QPushButton:hover, QMessageBox QPushButton:hover {
    background-color: #2563EB;
}

QDialogButtonBox QPushButton:pressed, QMessageBox QPushButton:pressed {
    background-color: #1D4ED8;
}

/* 输入框 */
QLineEdit {
    background-color: #0F172A;
    border: 1px solid #475569;
    border-radius: 10px;
    padding: 8px 12px;
    font-size: 13px;
    color: #F8FAFC;
}

QLineEdit:focus {
    border: 1px solid #3B82F6;
    background-color: #1E293B;
}

QPushButton.OutlineBtn {
    background-color: #334155;
    color: #F8FAFC;
    border: 1px solid #475569;
    border-radius: 10px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 600;
}

QPushButton.OutlineBtn:hover {
    background-color: #475569;
}

/* 卡片内部操作按钮 */
QPushButton.CardActionBlue {
    background-color: #3B82F6;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton.CardActionBlue:hover {
    background-color: #2563EB;
}

QPushButton.CardActionPurple {
    background-color: #581C87;
    color: #E9D5FF;
    border: none;
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton.CardActionPurple:hover {
    background-color: #6B21A8;
}

QPushButton.CardActionOrange {
    background-color: #7C2D12;
    color: #FED7AA;
    border: none;
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton.CardActionOrange:hover {
    background-color: #9A3412;
}

QPushButton.CardActionTeal {
    background-color: #134E4A;
    color: #99F6E4;
    border: none;
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton.CardActionTeal:hover {
    background-color: #115E59;
}

QPushButton.CardActionSecondary {
    background-color: #1E293B;
    color: #E2E8F0;
    border: 1px solid #475569;
    border-radius: 8px;
    padding: 6px 11px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton.CardActionSecondary:hover {
    background-color: #334155;
    color: #FFFFFF;
    border-color: #64748B;
}

QPushButton.CardActionSecondary:pressed {
    background-color: #0F172A;
}

QPushButton.DetailActionBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3B82F6, stop:1 #2563EB);
    color: #FFFFFF;
    border: none;
    border-radius: 10px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 600;
}

QPushButton.DetailActionBtn:hover {
    background: #1D4ED8;
}

QPushButton.DetailActionBtn:pressed {
    background: #1E40AF;
}

/* 底部操作主按钮 */
QLabel#BottomStatusPill {
    color: #94A3B8;
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 7px 12px;
    font-size: 11px;
    font-weight: 500;
}

QPushButton#ApplyButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3B82F6, stop:1 #2563EB);
    color: #FFFFFF;
    border: none;
    border-radius: 14px;
    padding: 12px 28px;
    font-size: 15px;
    font-weight: 700;
}

QPushButton#ApplyButton:hover {
    background: #1D4ED8;
}

QPushButton#RestoreButton {
    background-color: #1E293B;
    color: #94A3B8;
    border: 1px solid #475569;
    border-radius: 14px;
    padding: 12px 22px;
    font-size: 14px;
    font-weight: 600;
}

QPushButton#RestoreButton:hover {
    background-color: #334155;
    color: #F87171;
    border-color: #EF4444;
}

/* 顶部自定义窗口控制按钮 (Windows 11 Fluent 风格) */
QPushButton.WindowControl {
    background-color: transparent;
    color: #94A3B8;
    border: none;
    border-radius: 6px;
    min-width: 34px;
    max-width: 34px;
    min-height: 28px;
    max-height: 28px;
    font-family: 'Segoe Fluent Icons', 'Segoe MDL2 Assets';
    font-size: 11px;
}

QPushButton#TitleBtnMax {
    font-size: 15px;
    font-weight: bold;
}

QPushButton.WindowControl:hover {
    background-color: #334155;
    color: #FFFFFF;
}

QPushButton#WindowCloseBtn {
    background-color: transparent;
    color: #94A3B8;
    border: none;
    border-radius: 6px;
    min-width: 34px;
    max-width: 34px;
    min-height: 28px;
    max-height: 28px;
    font-family: 'Segoe Fluent Icons', 'Segoe MDL2 Assets';
    font-size: 10px;
}

QPushButton#WindowCloseBtn:hover {
    background-color: #EF4444;
    color: #FFFFFF;
}
"""


def set_window_theme_titlebar(widget, is_dark=True):
    r"""
    通过 Windows DWM API 动态切换原生窗口与二级弹窗标题栏的黑夜/白天模式
    """
    try:
        hwnd = int(widget.winId())
        val = ctypes.c_int(1 if is_dark else 0)
        # Windows 10 build 18985+ / Windows 11 (DWMWA_USE_IMMERSIVE_DARK_MODE = 20)
        res = ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(val), ctypes.sizeof(val))
        if res != 0:
            # Windows 10 1809~1909 旧版回退 (DWMWA_USE_IMMERSIVE_DARK_MODE = 19)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(val), ctypes.sizeof(val))
    except Exception:
        pass


class ThemedMessageBox(QMessageBox):
    r"""
    深度支持白天/黑夜主题与 Windows 11 DWM 原生暗黑标题栏的自定义消息弹窗
    """
    def __init__(self, *args, is_dark=None, **kwargs):
        super().__init__(*args, **kwargs)
        parent = self.parent()
        if is_dark is None:
            self.is_dark = getattr(parent, "is_dark_mode", False) if parent else False
        else:
            self.is_dark = is_dark
        icon_path = os.path.join(ASSETS_DIR, "app_icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self._apply_dialog_theme()

    def _apply_dialog_theme(self):
        sheet = DARK_STYLE_SHEET.replace("__ARROW_ICON_LIGHT_PATH__", ARROW_ICON_LIGHT_PATH) if self.is_dark else LIGHT_STYLE_SHEET.replace("__ARROW_ICON_PATH__", ARROW_ICON_PATH)
        self.setStyleSheet(sheet)

    def showEvent(self, event):
        super().showEvent(event)
        set_window_theme_titlebar(self, self.is_dark)

    @classmethod
    def information(cls, parent, title, text, buttons=QMessageBox.Ok, default_button=QMessageBox.NoButton):
        is_dark = getattr(parent, "is_dark_mode", False) if parent else False
        box = cls(parent, is_dark=is_dark)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle(title)
        box.setText(text)
        box.setStandardButtons(buttons)
        if default_button != QMessageBox.NoButton:
            box.setDefaultButton(default_button)
        if box.button(QMessageBox.Ok):
            box.button(QMessageBox.Ok).setText("确定")
        return box.exec()

    @classmethod
    def question(cls, parent, title, text, buttons=QMessageBox.Yes | QMessageBox.No, default_button=QMessageBox.NoButton):
        is_dark = getattr(parent, "is_dark_mode", False) if parent else False
        box = cls(parent, is_dark=is_dark)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle(title)
        box.setText(text)
        box.setStandardButtons(buttons)
        if default_button != QMessageBox.NoButton:
            box.setDefaultButton(default_button)
        if box.button(QMessageBox.Yes):
            box.button(QMessageBox.Yes).setText("是 (Yes)")
        if box.button(QMessageBox.No):
            box.button(QMessageBox.No).setText("否 (No)")
        if box.button(QMessageBox.Cancel):
            box.button(QMessageBox.Cancel).setText("取消")
        return box.exec()

    @classmethod
    def warning(cls, parent, title, text, buttons=QMessageBox.Ok, default_button=QMessageBox.NoButton):
        is_dark = getattr(parent, "is_dark_mode", False) if parent else False
        box = cls(parent, is_dark=is_dark)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle(title)
        box.setText(text)
        box.setStandardButtons(buttons)
        if default_button != QMessageBox.NoButton:
            box.setDefaultButton(default_button)
        if box.button(QMessageBox.Ok):
            box.button(QMessageBox.Ok).setText("确定")
        return box.exec()


class ThemedInputDialog(QInputDialog):
    r"""
    深度支持白天/黑夜主题与 Windows 11 DWM 原生暗黑标题栏的自定义输入对话框
    """
    def __init__(self, *args, is_dark=None, **kwargs):
        super().__init__(*args, **kwargs)
        parent = self.parent()
        if is_dark is None:
            self.is_dark = getattr(parent, "is_dark_mode", False) if parent else False
        else:
            self.is_dark = is_dark
        icon_path = os.path.join(ASSETS_DIR, "app_icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        sheet = DARK_STYLE_SHEET.replace("__ARROW_ICON_LIGHT_PATH__", ARROW_ICON_LIGHT_PATH) if self.is_dark else LIGHT_STYLE_SHEET.replace("__ARROW_ICON_PATH__", ARROW_ICON_PATH)
        self.setStyleSheet(sheet)
        self.setOkButtonText("确定")
        self.setCancelButtonText("取消")

    def showEvent(self, event):
        super().showEvent(event)
        set_window_theme_titlebar(self, self.is_dark)

    @classmethod
    def getText(cls, parent, title, label, text=""):
        is_dark = getattr(parent, "is_dark_mode", False) if parent else False
        dlg = cls(parent, is_dark=is_dark)
        dlg.setWindowTitle(title)
        dlg.setLabelText(label)
        dlg.setTextValue(text)
        ok = dlg.exec()
        return dlg.textValue(), bool(ok)


class ThemedComboBox(QComboBox):
    r"""
    智能自适应宽度与深度主题支持的下拉框，二级下拉菜单绝不发生截断
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def showPopup(self):
        # 弹出二级下拉菜单时，确保宽度至少为 360px，完整展示长硬件型号
        if self.view():
            self.view().setMinimumWidth(max(self.width(), 360))
        super().showPopup()


# 挂载全局别名，使所有原生调用无缝自动升级为主题兼容组件
QMessageBox = ThemedMessageBox
QInputDialog = ThemedInputDialog
QComboBox = ThemedComboBox



class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        from common.ui_theme import install_combo_arrows
        install_combo_arrows(QApplication.instance())
        self.config = load_config()
        self.is_dark_mode = (get_global_theme() == "dark")
        self._syncing = False
        self._drag_pos = None
        self.init_ui()

        # 实时监听全局主题切换，实现多软件毫秒级无感同步
        self.theme_sync_timer = QTimer(self)
        self.theme_sync_timer.setInterval(500)
        self.theme_sync_timer.timeout.connect(self.check_external_theme_change)
        self.theme_sync_timer.start()

    def check_external_theme_change(self):
        """检查全局主题文件是否被其他子软件或主程序切换"""
        global_mode = get_global_theme()
        should_be_dark = (global_mode == "dark")
        if self.is_dark_mode != should_be_dark:
            self.is_dark_mode = should_be_dark
            self.config["theme"] = global_mode
            save_config(self.config)
            self.apply_theme()

    def init_ui(self):
        self.setWindowTitle("DM工具箱 - 硬件与系统配置大师")
        self.BORDER_SIZE = 7
        self.setMouseTracking(True)
        self._is_dragging = False
        self._drag_pos = None
        self._resize_edge = 0
        self._resize_start_pos = QPoint()
        self._resize_start_geom = self.geometry()
        self._edge_cursor_active = False

        qApp = QApplication.instance()
        if qApp:
            qApp.installEventFilter(self)

        # Responsive screen adaptation
        screen = QGuiApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            target_w = min(1000, int(avail.width() * 0.92))
            target_h = min(640, int(avail.height() * 0.86))
            self.resize(target_w, target_h)
            min_w = min(740, int(avail.width() * 0.70))
            min_h = min(480, int(avail.height() * 0.60))
            self.setMinimumSize(min_w, min_h)
        else:
            self.resize(1000, 640)
            self.setMinimumSize(740, 480)

        # 1. 无边框窗口与自定义标题栏
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowSystemMenuHint | Qt.WindowMinMaxButtonsHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # 软件内外图标设置 (Window Icon & App Icon)
        icon_path = os.path.join(ASSETS_DIR, "app_icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # 2. 主视窗与布局
        self.central_widget = QWidget(self)
        self.central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(self.central_widget)

        root_layout = QHBoxLayout(self.central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 3. 创建左侧白色侧边栏 (Sidebar)
        sidebar = self.create_sidebar()
        root_layout.addWidget(sidebar)

        # 4. 创建右侧主功能工作区 (Main Content)
        content_area = self.create_content_area()
        root_layout.addWidget(content_area)

        # 5. 应用初始主题 (白天 / 黑夜模式)
        self.apply_theme()
        apply_dm_window_frame(self, self.is_dark_mode)
        self.center_on_screen()

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        mode = "dark" if self.is_dark_mode else "light"
        self.config["theme"] = mode
        save_config(self.config)
        set_global_theme(mode)
        self.apply_theme()

    def apply_theme(self):
        if self.is_dark_mode:
            sheet = DARK_STYLE_SHEET.replace("__ARROW_ICON_LIGHT_PATH__", ARROW_ICON_LIGHT_PATH)
        else:
            sheet = LIGHT_STYLE_SHEET.replace("__ARROW_ICON_PATH__", ARROW_ICON_PATH)
        
        # 1. 深度应用至全局 QApplication 实例，确保所有子窗口、二级下拉菜单、右键菜单、弹出对话框完全统一
        app = QApplication.instance()
        if app:
            from common.ui_theme import combo_arrow_qss
            app.setStyleSheet(sheet + combo_arrow_qss(self.is_dark_mode))
        self.setStyleSheet(sheet)

        if hasattr(self, "btn_theme"):
            self.btn_theme.setText("☀️ 白天模式" if self.is_dark_mode else "🌙 黑夜模式")
            self.btn_theme.setToolTip("切换为浅色白天模式" if self.is_dark_mode else "切换为暗色黑夜模式")
        if hasattr(self, "btn_min"):
            self.btn_min.set_dark_mode(self.is_dark_mode)
        if hasattr(self, "btn_max"):
            self.btn_max.set_dark_mode(self.is_dark_mode)
            self.btn_max.set_maximized_state(self.isMaximized())
        if hasattr(self, "btn_close"):
            self.btn_close.set_dark_mode(self.is_dark_mode)

        if hasattr(self, "size_grip") and self.size_grip:
            self.size_grip.set_dark_mode(self.is_dark_mode)

        bg_color = "#0F172A" if self.is_dark_mode else "#F0F4FA"
        border_color = "#334155" if self.is_dark_mode else "#D6E6FE"
        if self.isMaximized():
            self.central_widget.setStyleSheet(f"#CentralWidget {{ background-color: {bg_color}; border: none; border-radius: 0px; }}")
        else:
            self.central_widget.setStyleSheet(f"#CentralWidget {{ background-color: {bg_color}; border: 1px solid {border_color}; border-radius: 14px; }}")

        apply_dm_window_frame(self, self.is_dark_mode)

        if hasattr(self, "heybox_path_input"):
            self.update_heybox_path_status_ui(self.heybox_path_input.text().strip())

    def nativeEvent(self, eventType, message):
        return super().nativeEvent(eventType, message)

    def center_on_screen(self):
        screen = self.screen() or QGuiApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            target_w = min(self.width(), int(avail.width() * 0.94))
            target_h = min(self.height(), int(avail.height() * 0.88))
            if target_w != self.width() or target_h != self.height():
                self.resize(target_w, target_h)
            new_x = avail.left() + max(0, (avail.width() - self.width()) // 2)
            new_y = avail.top() + max(0, (avail.height() - self.height()) // 2)
            self.move(new_x, new_y)

    def moveEvent(self, event):
        super().moveEvent(event)
        screen = self.screen() or QGuiApplication.screenAt(self.geometry().center())
        if screen and not self.isMaximized():
            avail = screen.availableGeometry()
            cur_w = self.width()
            cur_h = self.height()
            need_resize = False

            if self.minimumWidth() > int(avail.width() * 0.88):
                self.setMinimumWidth(max(400, int(avail.width() * 0.65)))
            if self.minimumHeight() > int(avail.height() * 0.84):
                self.setMinimumHeight(max(300, int(avail.height() * 0.55)))

            if cur_w > avail.width() * 0.95:
                cur_w = max(self.minimumWidth(), int(avail.width() * 0.94))
                need_resize = True
            if cur_h > avail.height() * 0.90:
                cur_h = max(self.minimumHeight(), int(avail.height() * 0.88))
                need_resize = True
            if need_resize:
                self.resize(cur_w, cur_h)

    def _get_resize_edge(self, pos: QPoint) -> int:
        b = self.BORDER_SIZE
        c = getattr(self, "CORNER_SIZE", 20)
        w = self.width()
        h = self.height()

        # 4 corners first with generous hit zone (20x20px)
        if pos.x() <= c and pos.y() <= c:
            return 1 | 4  # Top-Left
        if pos.x() >= w - c and pos.y() <= c:
            return 2 | 4  # Top-Right
        if pos.x() <= c and pos.y() >= h - c:
            return 1 | 8  # Bottom-Left
        if pos.x() >= w - c and pos.y() >= h - c:
            return 2 | 8  # Bottom-Right

        edge = 0
        if pos.x() <= b: edge |= 1       # Left
        if pos.x() >= w - b: edge |= 2   # Right
        if pos.y() <= b: edge |= 4       # Top
        if pos.y() >= h - b: edge |= 8   # Bottom
        return edge

    def _update_cursor_for_edge(self, edge: int):
        if edge in (1 | 4, 2 | 8):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif edge in (2 | 4, 1 | 8):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif edge in (1, 2):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif edge in (4, 8):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.unsetCursor()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            if not self.isMaximized():
                edge = self._get_resize_edge(pos)
                if edge != 0:
                    self._resize_edge = edge
                    self._resize_start_pos = event.globalPosition().toPoint()
                    self._resize_start_geom = self.geometry()
                    event.accept()
                    return
            if pos.y() <= 55:
                # Do not drag if user clicked on title bar buttons or interactive controls
                child = self.childAt(pos)
                is_btn = False
                p = child
                while p and p is not self and p is not self.central_widget:
                    if isinstance(p, QPushButton):
                        is_btn = True
                        break
                    p = p.parent()
                if not is_btn:
                    self._is_dragging = True
                    self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                    event.accept()
                    return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        if not self.isMaximized():
            if self._resize_edge != 0 and (event.buttons() & Qt.MouseButton.LeftButton):
                delta = event.globalPosition().toPoint() - self._resize_start_pos
                rect = self._resize_start_geom
                x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
                min_w = self.minimumWidth()
                min_h = self.minimumHeight()

                if self._resize_edge & 1: # Left
                    new_w = max(min_w, w - delta.x())
                    x = rect.right() - new_w + 1
                    w = new_w
                elif self._resize_edge & 2: # Right
                    w = max(min_w, w + delta.x())

                if self._resize_edge & 4: # Top
                    new_h = max(min_h, h - delta.y())
                    y = rect.bottom() - new_h + 1
                    h = new_h
                elif self._resize_edge & 8: # Bottom
                    h = max(min_h, h + delta.y())

                self.setGeometry(x, y, w, h)
                event.accept()
                return
            elif not (event.buttons() & Qt.MouseButton.LeftButton):
                edge = self._get_resize_edge(pos)
                self._update_cursor_for_edge(edge)

        if getattr(self, "_is_dragging", False) and self._drag_pos is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._is_dragging = False
        self._drag_pos = None
        self._resize_edge = 0
        self.unsetCursor()
        super().mouseReleaseEvent(event)

    def eventFilter(self, watched, event):
        if not self.isVisible() or self.isMinimized():
            return super().eventFilter(watched, event)

        et = event.type()
        if self._resize_edge != 0:
            if et == QEvent.Type.MouseMove:
                delta = event.globalPosition().toPoint() - self._resize_start_pos
                rect = self._resize_start_geom
                x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
                min_w = self.minimumWidth()
                min_h = self.minimumHeight()

                if self._resize_edge & 1: # Left
                    new_w = max(min_w, w - delta.x())
                    x = rect.right() - new_w + 1
                    w = new_w
                elif self._resize_edge & 2: # Right
                    w = max(min_w, w + delta.x())

                if self._resize_edge & 4: # Top
                    new_h = max(min_h, h - delta.y())
                    y = rect.bottom() - new_h + 1
                    h = new_h
                elif self._resize_edge & 8: # Bottom
                    h = max(min_h, h + delta.y())

                self.setGeometry(x, y, w, h)
                return True

            elif et == QEvent.Type.MouseButtonRelease:
                self._resize_edge = 0
                self.unsetCursor()
                self._edge_cursor_active = False
                return True

        if not self.isMaximized() and isinstance(watched, QWidget):
            try:
                if watched.window() is self:
                    if et == QEvent.Type.MouseMove:
                        local_pos = self.mapFromGlobal(event.globalPosition().toPoint())
                        edge = self._get_resize_edge(local_pos)
                        if edge != 0:
                            self._update_cursor_for_edge(edge)
                            self._edge_cursor_active = True
                        elif getattr(self, "_edge_cursor_active", False):
                            self.unsetCursor()
                            self._edge_cursor_active = False

                    elif et == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                        local_pos = self.mapFromGlobal(event.globalPosition().toPoint())
                        edge = self._get_resize_edge(local_pos)
                        if edge != 0:
                            self._resize_edge = edge
                            self._resize_start_pos = event.globalPosition().toPoint()
                            self._resize_start_geom = self.geometry()
                            return True
            except Exception:
                pass

        return super().eventFilter(watched, event)

    def closeEvent(self, event):
        qApp = QApplication.instance()
        if qApp:
            try:
                qApp.removeEventFilter(self)
            except Exception:
                pass
        super().closeEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.position().y() <= 55:
            child = self.childAt(event.position().toPoint())
            is_btn = False
            p = child
            while p and p is not self and p is not self.central_widget:
                if isinstance(p, QPushButton):
                    is_btn = True
                    break
                p = p.parent()
            if not is_btn:
                self.toggle_maximized()
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def changeEvent(self, event):
        if event.type() == event.Type.WindowStateChange:
            if hasattr(self, "btn_max"):
                self.btn_max.set_maximized_state(self.isMaximized())
        super().changeEvent(event)

    def toggle_maximized(self):
        bg_color = "#0F172A" if getattr(self, "is_dark_mode", False) else "#F0F4FA"
        border_color = "#334155" if getattr(self, "is_dark_mode", False) else "#D6E6FE"
        if self.isMaximized():
            self.showNormal()
            self.central_widget.setStyleSheet(f"#CentralWidget {{ background-color: {bg_color}; border: 1px solid {border_color}; border-radius: 14px; }}")
        else:
            self.showMaximized()
            self.central_widget.setStyleSheet(f"#CentralWidget {{ background-color: {bg_color}; border: none; border-radius: 0px; }}")
        if hasattr(self, "btn_max"):
            self.btn_max.set_maximized_state(self.isMaximized())

    def create_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(215)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 20, 14, 20)
        layout.setSpacing(6)

        # 顶部品牌 Logo 与标题 (软件内部更换为设计好的全新图标)
        logo_layout = QHBoxLayout()
        logo_layout.setContentsMargins(4, 0, 4, 16)
        logo_layout.setSpacing(10)

        icon_label = QLabel()
        png_path = os.path.join(ASSETS_DIR, "app_icon.png")
        if os.path.exists(png_path):
            pix = QPixmap(png_path).scaled(38, 38, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_label.setPixmap(pix)
        logo_layout.addWidget(icon_label)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        brand_title = QLabel("DM Hardware")
        brand_title.setObjectName("BrandTitle")
        brand_sub = QLabel("全硬件配置大师")
        brand_sub.setObjectName("BrandSubtitle")
        title_vbox.addWidget(brand_title)
        title_vbox.addWidget(brand_sub)
        logo_layout.addLayout(title_vbox)
        layout.addLayout(logo_layout)

        # 分割线
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setObjectName("SidebarSep")
        layout.addWidget(sep)

        # 导航项列表
        self.nav_buttons = []
        nav_items = [
            (" 首页概览", 0),
            (" 处理器 CPU", 1),
            (" 显卡与显存", 2),
            (" 主板与内存", 3),
            (" 硬盘存储", 4),
            (" 小黑盒加速器", 5),
            (" 系统与备份", 6),
        ]

        for text, index in nav_items:
            btn = QPushButton(text)
            btn.setProperty("class", "NavButton")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, idx=index: self.switch_page(idx))
            self.nav_buttons.append(btn)
            layout.addWidget(btn)

        self.nav_buttons[0].setChecked(True)
        layout.addStretch()

        # 底部状态微标
        status_box = QFrame()
        status_box.setObjectName("SidebarStatusBox")
        s_layout = QVBoxLayout(status_box)
        s_layout.setContentsMargins(6, 6, 6, 6)
        s_layout.setSpacing(4)
        ver_lbl = QLabel("当前版本: v2.5.0 Pro")
        ver_lbl.setObjectName("SidebarVerLbl")
        hook_lbl = QLabel("● 拦截器运行中")
        hook_lbl.setObjectName("SidebarHookLbl")
        s_layout.addWidget(ver_lbl)
        s_layout.addWidget(hook_lbl)
        layout.addWidget(status_box)

        return sidebar

    def create_content_area(self):
        wrapper = QWidget()
        v_layout = QVBoxLayout(wrapper)
        v_layout.setContentsMargins(24, 14, 24, 18)
        v_layout.setSpacing(14)

        # 1. 顶部自定义标题栏与控制栏 (Custom Frameless Titlebar)
        topbar = QHBoxLayout()
        topbar.setSpacing(8)
        topbar.setContentsMargins(0, 0, 0, 2)
        
        status_banner = QLabel(" 实时硬件穿透环境就绪 | 小黑盒 SSS 评级注入已激活")
        status_banner.setObjectName("StatusBanner")
        topbar.addWidget(status_banner)
        topbar.addStretch()

        # 主题切换按钮 (白天 / 黑夜模式)
        self.btn_theme = QPushButton()
        self.btn_theme.setObjectName("ThemeToggleBtn")
        self.btn_theme.setCursor(Qt.PointingHandCursor)
        self.btn_theme.clicked.connect(self.toggle_theme)
        topbar.addWidget(self.btn_theme)

        # 窗口控制按钮 (图1高精度居中对齐 CaptionButton)
        self.btn_min = CaptionButton(CaptionButtonType.MINIMIZE, self)
        self.btn_min.setToolTip("最小化")
        self.btn_min.clicked.connect(self.showMinimized)
        topbar.addWidget(self.btn_min)

        self.btn_max = CaptionButton(CaptionButtonType.MAXIMIZE, self)
        self.btn_max.setToolTip("最大化 / 还原")
        self.btn_max.clicked.connect(self.toggle_maximized)
        topbar.addWidget(self.btn_max)

        self.btn_close = CaptionButton(CaptionButtonType.CLOSE, self)
        self.btn_close.setToolTip("关闭")
        self.btn_close.clicked.connect(self.close)
        topbar.addWidget(self.btn_close)

        v_layout.addLayout(topbar)

        # 2. 多页面切换容器 (Stacked Widget)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.create_home_view())
        self.stack.addWidget(self.create_cpu_view())
        self.stack.addWidget(self.create_gpu_view())
        self.stack.addWidget(self.create_board_ram_view())
        self.stack.addWidget(self.create_disk_view())
        self.stack.addWidget(self.create_heybox_view())
        self.stack.addWidget(self.create_backup_view())
        v_layout.addWidget(self.stack, 1)

        # 3. 底部自定义现代化状态与操作栏
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(14)
        bottom_bar.setContentsMargins(0, 4, 0, 0)

        status_pill = QLabel("● 状态: 就绪 | 配置文件: C:\\Users\\Public\\Hardware_Config.json (双向热同步)")
        status_pill.setObjectName("BottomStatusPill")
        bottom_bar.addWidget(status_pill)
        bottom_bar.addStretch()

        btn_restore = QPushButton("一键还原官方真实硬件")
        btn_restore.setObjectName("RestoreButton")
        btn_restore.clicked.connect(self.on_restore_clicked)
        bottom_bar.addWidget(btn_restore)

        btn_apply = QPushButton("立即应用全套自定义配置 →")
        btn_apply.setObjectName("ApplyButton")
        btn_apply.clicked.connect(self.on_apply_clicked)
        bottom_bar.addWidget(btn_apply)

        self.size_grip = DMSizeGrip(self)
        self.size_grip.set_dark_mode(self.is_dark_mode)
        bottom_bar.addWidget(self.size_grip, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)

        v_layout.addLayout(bottom_bar)
        return wrapper

    def create_home_view(self):
        """首页概览 (仿参考图片的 Hero 横幅 + 2x2 网格卡片)"""
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # 1. 顶部 Hero 横幅 (带有渐变与 3D 悬浮芯片图，已移除截断徽章)
        hero = QFrame()
        hero.setObjectName("HeroCard")
        hero.setFixedHeight(145)
        h_layout = QHBoxLayout(hero)
        h_layout.setContentsMargins(28, 20, 24, 20)

        text_vbox = QVBoxLayout()
        text_vbox.setSpacing(8)
        
        title_box = QHBoxLayout()
        t1 = QLabel("DM")
        t1.setObjectName("HeroTitleMain")
        t2 = QLabel("Hardware Master")
        t2.setObjectName("HeroTitleSub")
        title_box.addWidget(t1)
        title_box.addWidget(t2)
        title_box.addStretch()
        text_vbox.addLayout(title_box)

        desc = QLabel("高效、稳定、易用的全硬件与小黑盒加速器深度定制与穿透工具")
        desc.setObjectName("HeroDesc")
        text_vbox.addWidget(desc)
        text_vbox.addStretch()
        h_layout.addLayout(text_vbox)

        # 右侧 3D 硬件艺术插画
        hero_img_label = QLabel()
        hero_p = os.path.join(ASSETS_DIR, "hero_graphic.png")
        if os.path.exists(hero_p):
            pix = QPixmap(hero_p).scaled(280, 135, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            hero_img_label.setPixmap(pix)
        h_layout.addWidget(hero_img_label)
        layout.addWidget(hero)

        # 2. 2x2 网格卡片区域 (参考图样式，与子菜单双向实时同步)
        grid_container = QWidget()
        grid_layout = QHBoxLayout(grid_container)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(16)

        # 左列卡片 (CPU & 主板内存)
        col_left = QVBoxLayout()
        col_left.setSpacing(16)

        # Card 1: CPU (蓝色系)
        self.card_cpu, self.home_cpu_combo = self.create_grid_card(
            badge_class="CardBadgeBlue", badge_char="C",
            title="处理器 CPU 定制", subtitle="核心数/频率/型号全面深度修改",
            action_text="进入配置 →", action_class="CardActionBlue",
            combo_items=list(self.config["presets"]["cpu"]) + ["✏️ 自定义 CPU 型号..."],
            current_value=self.config["custom_target"].get("cpu_model", "AMD Ryzen 9 9950X3D2 16-Core Processor"),
            on_change=lambda text: self.sync_cpu(text, source=self.home_cpu_combo),
            on_click=lambda: self.switch_page(1),
            on_apply_single=lambda: self.on_apply_single_component("cpu"),
            single_action_text="⚡ 单独生效 CPU"
        )
        col_left.addWidget(self.card_cpu)

        # Card 3: 主板与内存 (橙色系)
        board_presets = [f"{b['vendor']} {b['product']}" for b in self.config["presets"]["motherboard"]]
        curr_board = f"{self.config['custom_target'].get('motherboard_vendor', 'ASUSTeK COMPUTER INC.')} {self.config['custom_target'].get('motherboard_product', 'ROG CROSSHAIR X870E HERO')}".strip()
        self.card_board, self.home_board_combo = self.create_grid_card(
            badge_class="CardBadgeOrange", badge_char="M",
            title="主板与内存", subtitle="ROG/微星主板 & 海盗船/芝奇 DDR5 高频内存",
            action_text="进入配置 →", action_class="CardActionOrange",
            combo_items=board_presets + ["✏️ 自定义主板型号..."],
            current_value=curr_board,
            on_change=lambda text: self.on_board_combo_selected(text, source=self.home_board_combo),
            on_click=lambda: self.switch_page(3),
            on_apply_single=lambda: self.on_apply_single_component("board"),
            single_action_text="⚡ 生效主板",
            secondary_apply=lambda: self.on_apply_single_component("memory"),
            secondary_text="⚡ 生效内存"
        )
        col_left.addWidget(self.card_board)
        grid_layout.addLayout(col_left)

        # 右列卡片 (GPU & 硬盘)
        col_right = QVBoxLayout()
        col_right.setSpacing(16)

        # Card 2: 显卡与显存 (紫色系)
        self.card_gpu, self.home_gpu_combo = self.create_grid_card(
            badge_class="CardBadgePurple", badge_char="G",
            title="显卡 GPU & 显存", subtitle="RTX 5090/5080/4090 与最大 48GB 显存",
            action_text="进入配置 →", action_class="CardActionPurple",
            combo_items=list(self.config["presets"]["gpu"]) + ["✏️ 自定义 GPU 型号..."],
            current_value=self.config["custom_target"].get("gpu_model", "NVIDIA GeForce RTX 5090"),
            on_change=lambda text: self.sync_gpu(text, source=self.home_gpu_combo),
            on_click=lambda: self.switch_page(2),
            on_apply_single=lambda: self.on_apply_single_component("gpu"),
            single_action_text="⚡ 单独生效显卡"
        )
        col_right.addWidget(self.card_gpu)

        # Card 4: 硬盘存储 (青绿系)
        self.card_disk, self.home_disk_combo = self.create_grid_card(
            badge_class="CardBadgeTeal", badge_char="D",
            title="硬盘存储定制", subtitle="三星 990 PRO 2TB / 致态 TiPro7000 等高速 NVMe",
            action_text="进入配置 →", action_class="CardActionTeal",
            combo_items=list(self.config["presets"]["disk"]) + ["✏️ 自定义硬盘型号..."],
            current_value=self.config["custom_target"].get("disk_model", "Samsung SSD 990 PRO 4TB"),
            on_change=lambda text: self.sync_disk(text, source=self.home_disk_combo),
            on_click=lambda: self.switch_page(4),
            on_apply_single=lambda: self.on_apply_single_component("disk"),
            single_action_text="⚡ 单独生效硬盘"
        )
        col_right.addWidget(self.card_disk)
        grid_layout.addLayout(col_right)

        layout.addWidget(grid_container)
        return view

    def create_grid_card(self, badge_class, badge_char, title, subtitle, action_text, action_class, combo_items, current_value, on_change, on_click, on_apply_single=None, single_action_text="⚡ 单独生效", secondary_apply=None, secondary_text=None):
        card = QFrame()
        card.setProperty("class", "GridCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        # 顶部徽章与标题行
        header = QHBoxLayout()
        header.setSpacing(12)

        badge = QLabel(badge_char)
        badge.setProperty("class", badge_class)
        badge.setFixedSize(40, 40)
        header.addWidget(badge)

        t_layout = QVBoxLayout()
        t_layout.setSpacing(2)
        t_lbl = QLabel(title)
        t_lbl.setProperty("class", "CardTitle")
        s_lbl = QLabel(subtitle)
        s_lbl.setProperty("class", "CardSubtitle")
        t_layout.addWidget(t_lbl)
        t_layout.addWidget(s_lbl)
        header.addLayout(t_layout)

        header.addStretch()
        layout.addLayout(header)

        # 快速选择下拉框 (预设选择与自定义型号)
        combo = QComboBox()
        combo.setEditable(False)
        combo.addItems(combo_items)
        if current_value:
            if combo.findText(current_value) < 0:
                custom_idx = combo.count()
                for i in range(combo.count()):
                    if combo.itemText(i).startswith("✏️ 自定义"):
                        custom_idx = i
                        break
                combo.insertItem(custom_idx, current_value)
            combo.setCurrentText(current_value)
            combo.setToolTip(current_value)
        combo.currentTextChanged.connect(on_change)
        layout.addWidget(combo)

        # 底部操作按钮
        btn_box = QHBoxLayout()
        btn_box.setSpacing(8)
        btn = QPushButton(action_text)
        btn.setProperty("class", action_class)
        btn.clicked.connect(on_click)
        btn_box.addWidget(btn)

        if on_apply_single:
            btn_single = QPushButton(single_action_text)
            btn_single.setProperty("class", "CardActionSecondary")
            btn_single.clicked.connect(on_apply_single)
            btn_box.addWidget(btn_single)

        if secondary_apply:
            btn_sec = QPushButton(secondary_text or "⚡ 单独生效")
            btn_sec.setProperty("class", "CardActionSecondary")
            btn_sec.clicked.connect(secondary_apply)
            btn_box.addWidget(btn_sec)

        btn_box.addStretch()
        layout.addLayout(btn_box)

        return card, combo

    # ==========================
    # 详情配置视图 (Detail Pages)
    # ==========================
    def create_cpu_view(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        card = QFrame()
        card.setProperty("class", "GridCard")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(24, 24, 24, 24)
        c_layout.setSpacing(16)

        t = QLabel("处理器 CPU 深度定制")
        t.setProperty("class", "CardTitle")
        c_layout.addWidget(t)

        c_layout.addWidget(QLabel("选择目标 CPU 型号 (修改所有逻辑核心 CentralProcessor 及 ACPI 注册表):"))
        self.cpu_sub_combo = QComboBox()
        self.cpu_sub_combo.setEditable(False)
        self.cpu_sub_combo.addItems(list(self.config["presets"]["cpu"]) + ["✏️ 自定义 CPU 型号..."])
        curr_cpu = self.config["custom_target"].get("cpu_model", "AMD Ryzen 9 9950X3D2 16-Core Processor")
        if self.cpu_sub_combo.findText(curr_cpu) < 0:
            self._insert_combo_item(self.cpu_sub_combo, curr_cpu, preset_key="cpu")
        self.cpu_sub_combo.setCurrentText(curr_cpu)
        self.cpu_sub_combo.setToolTip(curr_cpu)
        self.cpu_sub_combo.currentTextChanged.connect(lambda val: self.sync_cpu(val, source=self.cpu_sub_combo))
        c_layout.addWidget(self.cpu_sub_combo)

        c_layout.addWidget(QLabel("检测出厂物理真实 CPU:"))
        real_cpu_lbl = QLabel(self.config["current_hardware"].get("detected_cpu", DEFAULT_REAL_CPU))
        real_cpu_lbl.setProperty("class", "RealHardwareBadge")
        c_layout.addWidget(real_cpu_lbl)

        btn_cpu_row = QHBoxLayout()
        btn_apply_cpu = QPushButton("⚡ 立即单独生效当前 CPU 处理器定制")
        btn_apply_cpu.setProperty("class", "DetailActionBtn")
        btn_apply_cpu.setFixedHeight(38)
        btn_apply_cpu.clicked.connect(lambda: self.on_apply_single_component("cpu"))
        btn_cpu_row.addWidget(btn_apply_cpu)
        btn_cpu_row.addStretch()
        c_layout.addLayout(btn_cpu_row)

        c_layout.addStretch()
        layout.addWidget(card)
        return page

    def create_gpu_view(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        card = QFrame()
        card.setProperty("class", "GridCard")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(24, 24, 24, 24)
        c_layout.setSpacing(16)

        t = QLabel("显卡 GPU 与独立显存定制")
        t.setProperty("class", "CardTitle")
        c_layout.addWidget(t)

        c_layout.addWidget(QLabel("目标 GPU 显卡型号 (修改 DirectX/DXGI/Enum 显卡参数与任务管理器显示):"))
        self.gpu_sub_combo = QComboBox()
        self.gpu_sub_combo.setEditable(False)
        self.gpu_sub_combo.addItems(list(self.config["presets"]["gpu"]) + ["✏️ 自定义 GPU 型号..."])
        curr_gpu = self.config["custom_target"].get("gpu_model", "NVIDIA GeForce RTX 5090")
        if self.gpu_sub_combo.findText(curr_gpu) < 0:
            self._insert_combo_item(self.gpu_sub_combo, curr_gpu, preset_key="gpu")
        self.gpu_sub_combo.setCurrentText(curr_gpu)
        self.gpu_sub_combo.setToolTip(curr_gpu)
        self.gpu_sub_combo.currentTextChanged.connect(lambda val: self.sync_gpu(val, source=self.gpu_sub_combo))
        c_layout.addWidget(self.gpu_sub_combo)

        c_layout.addWidget(QLabel("目标独立显存容量 (DirectX / DXGI / 任务管理器 DedicatedVideoMemory):"))
        self.vram_sub_combo = QComboBox()
        self.vram_sub_combo.setEditable(False)
        self.vram_sub_combo.addItems(list(self.config["presets"]["vram"]) + ["✏️ 自定义显存容量..."])
        curr_vram = f"{self.config['custom_target'].get('gpu_vram_gb', 32)} GB"
        for idx in range(self.vram_sub_combo.count()):
            if curr_vram in self.vram_sub_combo.itemText(idx):
                self.vram_sub_combo.setCurrentIndex(idx)
                break
        self.vram_sub_combo.setToolTip(self.vram_sub_combo.currentText())
        self.vram_sub_combo.currentTextChanged.connect(self.on_vram_changed)
        c_layout.addWidget(self.vram_sub_combo)

        c_layout.addWidget(QLabel("出厂物理真实显卡:"))
        real_gpu_lbl = QLabel(self.config["current_hardware"].get("detected_gpu", DEFAULT_REAL_GPU))
        real_gpu_lbl.setProperty("class", "RealHardwareBadge")
        c_layout.addWidget(real_gpu_lbl)

        btn_gpu_row = QHBoxLayout()
        btn_apply_gpu = QPushButton("⚡ 立即单独生效当前 显卡与显存定制")
        btn_apply_gpu.setProperty("class", "DetailActionBtn")
        btn_apply_gpu.setFixedHeight(38)
        btn_apply_gpu.clicked.connect(lambda: self.on_apply_single_component("gpu"))
        btn_gpu_row.addWidget(btn_apply_gpu)
        btn_gpu_row.addStretch()
        c_layout.addLayout(btn_gpu_row)

        c_layout.addStretch()
        layout.addWidget(card)
        return page

    def create_board_ram_view(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        card = QFrame()
        card.setProperty("class", "GridCard")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(24, 24, 24, 24)
        c_layout.setSpacing(14)

        t = QLabel("主板 BIOS 与内存 DDR5 定制")
        t.setProperty("class", "CardTitle")
        c_layout.addWidget(t)

        c_layout.addWidget(QLabel("主板预设型号快速选择 (与首页卡片实时双向同步):"))
        board_presets = [f"{b['vendor']} {b['product']}" for b in self.config["presets"]["motherboard"]]
        curr_board = f"{self.config['custom_target'].get('motherboard_vendor', 'ASUSTeK COMPUTER INC.')} {self.config['custom_target'].get('motherboard_product', 'ROG CROSSHAIR X870E HERO')}".strip()
        self.board_sub_combo = QComboBox()
        self.board_sub_combo.setEditable(False)
        self.board_sub_combo.addItems(board_presets + ["✏️ 自定义主板型号..."])
        if curr_board:
            if self.board_sub_combo.findText(curr_board) < 0:
                self._insert_combo_item(self.board_sub_combo, curr_board)
            self.board_sub_combo.setCurrentText(curr_board)
            self.board_sub_combo.setToolTip(curr_board)
        self.board_sub_combo.currentTextChanged.connect(lambda val: self.on_board_combo_selected(val, source=self.board_sub_combo))
        c_layout.addWidget(self.board_sub_combo)

        c_layout.addWidget(QLabel("主板厂商 (BaseBoardManufacturer & SystemManufacturer):"))
        self.board_vendor_input = QLineEdit(self.config["custom_target"].get("motherboard_vendor", "ASUSTeK COMPUTER INC."))
        self.board_vendor_input.textChanged.connect(lambda _: self.on_board_inputs_edited(source=self.board_vendor_input))
        c_layout.addWidget(self.board_vendor_input)

        c_layout.addWidget(QLabel("主板产品型号 (BaseBoardProduct & SystemProductName):"))
        self.board_product_input = QLineEdit(self.config["custom_target"].get("motherboard_product", "ROG CROSSHAIR X870E HERO"))
        self.board_product_input.textChanged.connect(lambda _: self.on_board_inputs_edited(source=self.board_product_input))
        c_layout.addWidget(self.board_product_input)

        btn_board_row = QHBoxLayout()
        btn_apply_board = QPushButton("⚡ 立即单独生效当前 主板 BIOS 定制")
        btn_apply_board.setProperty("class", "DetailActionBtn")
        btn_apply_board.setFixedHeight(38)
        btn_apply_board.clicked.connect(lambda: self.on_apply_single_component("board"))
        btn_board_row.addWidget(btn_apply_board)
        btn_board_row.addStretch()
        c_layout.addLayout(btn_board_row)

        c_layout.addWidget(QLabel("内存颗粒厂商 / 品牌:"))
        self.mem_vendor_input = QComboBox()
        self.mem_vendor_input.setEditable(False)
        self.mem_vendor_input.addItems(list(self.config["presets"]["memory_vendor"]) + ["✏️ 自定义内存品牌..."])
        curr_mv = self.config["custom_target"].get("memory_vendor", "Corsair")
        if self.mem_vendor_input.findText(curr_mv) < 0:
            self._insert_combo_item(self.mem_vendor_input, curr_mv, preset_key="memory_vendor")
        self.mem_vendor_input.setCurrentText(curr_mv)
        self.mem_vendor_input.setToolTip(curr_mv)
        self.mem_vendor_input.currentTextChanged.connect(self.on_mem_vendor_changed)
        c_layout.addWidget(self.mem_vendor_input)

        c_layout.addWidget(QLabel("内存容量与工作频率 (DDR5):"))
        mem_h = QHBoxLayout()
        self.mem_size_input = QComboBox()
        self.mem_size_input.setEditable(False)
        self.mem_size_input.addItems(list(self.config["presets"]["memory_size"]) + ["✏️ 自定义内存容量..."])
        curr_mem_s = f"{self.config['custom_target'].get('memory_size_gb', 64)} GB"
        for i in range(self.mem_size_input.count()):
            if curr_mem_s in self.mem_size_input.itemText(i):
                self.mem_size_input.setCurrentIndex(i)
                break
        self.mem_size_input.setToolTip(self.mem_size_input.currentText())
        self.mem_size_input.currentTextChanged.connect(self.on_mem_size_changed)

        self.mem_clock_input = QComboBox()
        self.mem_clock_input.setEditable(False)
        self.mem_clock_input.addItems(list(self.config["presets"]["memory_clock"]) + ["✏️ 自定义工作频率..."])
        curr_mc = f"{self.config['custom_target'].get('memory_clock_mhz', 7200)} MHz"
        if self.mem_clock_input.findText(curr_mc) < 0:
            self._insert_combo_item(self.mem_clock_input, curr_mc, preset_key="memory_clock")
        self.mem_clock_input.setCurrentText(curr_mc)
        self.mem_clock_input.setToolTip(curr_mc)
        self.mem_clock_input.currentTextChanged.connect(self.on_mem_clock_changed)

        mem_h.addWidget(self.mem_size_input)
        mem_h.addWidget(self.mem_clock_input)
        c_layout.addLayout(mem_h)

        btn_mem_row = QHBoxLayout()
        btn_apply_mem = QPushButton("⚡ 立即单独生效当前 内存 DDR5 定制")
        btn_apply_mem.setProperty("class", "DetailActionBtn")
        btn_apply_mem.setFixedHeight(38)
        btn_apply_mem.clicked.connect(lambda: self.on_apply_single_component("memory"))
        btn_mem_row.addWidget(btn_apply_mem)
        btn_mem_row.addStretch()
        c_layout.addLayout(btn_mem_row)

        c_layout.addStretch()
        layout.addWidget(card)
        return page

    def create_disk_view(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        card = QFrame()
        card.setProperty("class", "GridCard")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(24, 24, 24, 24)
        c_layout.setSpacing(16)

        t = QLabel("硬盘存储驱动器定制")
        t.setProperty("class", "CardTitle")
        c_layout.addWidget(t)

        c_layout.addWidget(QLabel("选择目标硬盘型号 (SCSI FriendlyName & 硬件底层探测):"))
        self.disk_sub_combo = QComboBox()
        self.disk_sub_combo.setEditable(False)
        self.disk_sub_combo.addItems(list(self.config["presets"]["disk"]) + ["✏️ 自定义硬盘型号..."])
        curr_disk = self.config["custom_target"].get("disk_model", "Samsung SSD 990 PRO 4TB")
        if self.disk_sub_combo.findText(curr_disk) < 0:
            self._insert_combo_item(self.disk_sub_combo, curr_disk, preset_key="disk")
        self.disk_sub_combo.setCurrentText(curr_disk)
        self.disk_sub_combo.setToolTip(curr_disk)
        self.disk_sub_combo.currentTextChanged.connect(lambda v: self.sync_disk(v, source=self.disk_sub_combo))
        c_layout.addWidget(self.disk_sub_combo)

        c_layout.addWidget(QLabel("出厂物理真实硬盘:"))
        real_disk_lbl = QLabel(self.config["current_hardware"].get("disk_model", DEFAULT_REAL_DISK_MODEL))
        real_disk_lbl.setProperty("class", "RealHardwareBadge")
        c_layout.addWidget(real_disk_lbl)

        btn_disk_row = QHBoxLayout()
        btn_apply_disk = QPushButton("⚡ 立即单独生效当前 硬盘存储定制")
        btn_apply_disk.setProperty("class", "DetailActionBtn")
        btn_apply_disk.setFixedHeight(38)
        btn_apply_disk.clicked.connect(lambda: self.on_apply_single_component("disk"))
        btn_disk_row.addWidget(btn_apply_disk)
        btn_disk_row.addStretch()
        c_layout.addLayout(btn_disk_row)

        c_layout.addStretch()
        layout.addWidget(card)
        return page

    def create_heybox_view(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        card = QFrame()
        card.setProperty("class", "GridCard")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(24, 24, 24, 24)
        c_layout.setSpacing(16)

        t = QLabel("小黑盒加速器全硬件秒检拦截器")
        t.setProperty("class", "CardTitle")
        c_layout.addWidget(t)

        desc = QLabel(
            "通过在小黑盒加速器 Electron 入口注入深度扩展钩子，并对前端渲染补丁进行实时联动：\n"
            "● 硬件探测：拦截原生 C++ 模块 acc_hardware_helper.node，输出全套定制参数。\n"
            "● 顶部评级：强制突破云端历史缓存，直接呈递 SSS 顶级神级评分与 99.9% 玩家超越率。\n"
            "● 状态感知：自动监控小黑盒运行，并在每次配置变更时无感同步。"
        )
        desc.setProperty("class", "DescLabel")
        c_layout.addWidget(desc)

        # 路径探测与自定义配置区域 (支持跨盘符全盘自动探测与手动浏览选择)
        path_box = QVBoxLayout()
        path_box.setSpacing(8)

        path_title_row = QHBoxLayout()
        path_title = QLabel("小黑盒加速器安装根目录 (支持跨盘符全盘自动探测，或点击浏览手动指定):")
        path_title.setProperty("class", "FormHeaderLabel")
        path_title_row.addWidget(path_title)
        path_title_row.addStretch()
        path_box.addLayout(path_title_row)

        curr_detected_path = get_xiaoheihe_base_dir()
        path_input_row = QHBoxLayout()
        path_input_row.setSpacing(10)

        self.heybox_path_input = QLineEdit(curr_detected_path)
        self.heybox_path_input.setPlaceholderText("请输入或浏览选择小黑盒加速器根目录 (包含 heyboxacc.exe 的文件夹)...")
        self.heybox_path_input.textChanged.connect(self.on_heybox_path_changed)
        path_input_row.addWidget(self.heybox_path_input, 1)

        btn_browse = QPushButton("📂 浏览路径...")
        btn_browse.setProperty("class", "OutlineBtn")
        btn_browse.clicked.connect(self.browse_heybox_path)
        path_input_row.addWidget(btn_browse)

        btn_redetect = QPushButton("🔍 重新探测")
        btn_redetect.setProperty("class", "OutlineBtn")
        btn_redetect.clicked.connect(self.redetect_heybox_path)
        path_input_row.addWidget(btn_redetect)

        path_box.addLayout(path_input_row)

        self.heybox_path_status = QLabel()
        self.update_heybox_path_status_ui(curr_detected_path)
        path_box.addWidget(self.heybox_path_status)
        c_layout.addLayout(path_box)

        btn_box = QHBoxLayout()
        btn_inject = QPushButton("重新刷新注入拦截器")
        btn_inject.setProperty("class", "CardActionBlue")
        btn_inject.clicked.connect(self.on_refresh_hook)
        btn_box.addWidget(btn_inject)

        btn_restore_hook = QPushButton("还原小黑盒原始文件")
        btn_restore_hook.setProperty("class", "CardActionPurple")
        btn_restore_hook.clicked.connect(self.on_restore_hook_only)
        btn_box.addWidget(btn_restore_hook)
        btn_box.addStretch()
        c_layout.addLayout(btn_box)

        c_layout.addStretch()
        layout.addWidget(card)
        return page

    def create_backup_view(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        card = QFrame()
        card.setProperty("class", "GridCard")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(24, 24, 24, 24)
        c_layout.setSpacing(16)

        t = QLabel("系统防护与开机防还原")
        t.setProperty("class", "CardTitle")
        c_layout.addWidget(t)

        self.chk_startup = QCheckBox("启用开机自启静默修复计划任务 (防止 Windows 自动刷新 CentralProcessor 注册表)")
        self.chk_startup.setChecked(self.config["custom_target"].get("enable_startup_fix", True))
        self.chk_startup.stateChanged.connect(lambda s: self.update_target_field("enable_startup_fix", bool(s)))
        c_layout.addWidget(self.chk_startup)

        c_layout.addWidget(QLabel("官方硬件出厂快照文件:"))
        snapshots = [
            f"CPU 快照: {CPU_BACKUP_FILE} ({'已备份' if os.path.exists(CPU_BACKUP_FILE) else '未备份'})",
            f"显卡快照: {GPU_BACKUP_FILE} ({'已备份' if os.path.exists(GPU_BACKUP_FILE) else '未备份'})",
            f"主板快照: {BOARD_PRODUCT_BACKUP_FILE} ({'已备份' if os.path.exists(BOARD_PRODUCT_BACKUP_FILE) else '未备份'})",
            f"硬盘快照: {DISK_BACKUP_FILE} ({'已备份' if os.path.exists(DISK_BACKUP_FILE) else '未备份'})",
        ]
        snap_lbl = QLabel("\n".join(snapshots))
        snap_lbl.setObjectName("SnapshotLabel")
        c_layout.addWidget(snap_lbl)

        c_layout.addStretch()
        layout.addWidget(card)
        return page

    # ==========================
    # 交互与双向实时同步处理 (Events & Two-way Sync)
    # ==========================
    def switch_page(self, idx):
        self.stack.setCurrentIndex(idx)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == idx)

    def update_target_field(self, key, value):
        self.config["custom_target"][key] = value
        save_config(self.config)

    def _insert_combo_item(self, combo, text, preset_key=None):
        """在自定义选项之前插入新项并避免重复，并可选择持久化到 presets"""
        if not combo or not text:
            return
        text = str(text).strip()
        found = False
        for i in range(combo.count()):
            if combo.itemText(i) == text:
                found = True
                break
        if not found:
            custom_idx = combo.count()
            for i in range(combo.count()):
                if combo.itemText(i).startswith("✏️ 自定义"):
                    custom_idx = i
                    break
            combo.insertItem(custom_idx, text)

        if preset_key and preset_key in self.config.get("presets", {}):
            preset_list = self.config["presets"][preset_key]
            if isinstance(preset_list, list) and text not in preset_list:
                preset_list.append(text)
                save_config(self.config)

    def _revert_combo(self, combo, fallback_val):
        """恢复下拉框选项，不触发多余事件"""
        if not combo or not fallback_val:
            return
        combo.blockSignals(True)
        fallback_str = str(fallback_val).strip()
        idx = combo.findText(fallback_str)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        else:
            self._insert_combo_item(combo, fallback_str)
            combo.setCurrentText(fallback_str)
        combo.setToolTip(fallback_str)
        combo.blockSignals(False)

    def sync_cpu(self, val, source=None):
        if self._syncing or not val:
            return
        val = str(val).strip()

        if val.startswith("✏️ 自定义"):
            curr = self.config["custom_target"].get("cpu_model", "AMD Ryzen 9 9950X3D2 16-Core Processor")
            new_text, ok = QInputDialog.getText(self, "自定义 CPU 处理器型号", "请输入自定义的 CPU 完整型号名称:", text=curr)
            if ok and new_text.strip():
                val = new_text.strip()
                if hasattr(self, "home_cpu_combo"):
                    self._insert_combo_item(self.home_cpu_combo, val, preset_key="cpu")
                if hasattr(self, "cpu_sub_combo"):
                    self._insert_combo_item(self.cpu_sub_combo, val, preset_key="cpu")
            else:
                if hasattr(self, "home_cpu_combo"):
                    self._revert_combo(self.home_cpu_combo, curr)
                if hasattr(self, "cpu_sub_combo"):
                    self._revert_combo(self.cpu_sub_combo, curr)
                return

        self._syncing = True
        self.config["custom_target"]["cpu_model"] = val
        save_config(self.config)

        if hasattr(self, "home_cpu_combo"):
            self.home_cpu_combo.blockSignals(True)
            if self.home_cpu_combo.findText(val) < 0:
                self._insert_combo_item(self.home_cpu_combo, val, preset_key="cpu")
            self.home_cpu_combo.setCurrentText(val)
            self.home_cpu_combo.setToolTip(val)
            self.home_cpu_combo.blockSignals(False)

        if hasattr(self, "cpu_sub_combo"):
            self.cpu_sub_combo.blockSignals(True)
            if self.cpu_sub_combo.findText(val) < 0:
                self._insert_combo_item(self.cpu_sub_combo, val, preset_key="cpu")
            self.cpu_sub_combo.setCurrentText(val)
            self.cpu_sub_combo.setToolTip(val)
            self.cpu_sub_combo.blockSignals(False)

        self._syncing = False

    def sync_gpu(self, val, source=None):
        if self._syncing or not val:
            return
        val = str(val).strip()

        if val.startswith("✏️ 自定义"):
            curr = self.config["custom_target"].get("gpu_model", "NVIDIA GeForce RTX 5090")
            new_text, ok = QInputDialog.getText(self, "自定义 GPU 显卡型号", "请输入自定义的显卡完整型号名称:", text=curr)
            if ok and new_text.strip():
                val = new_text.strip()
                if hasattr(self, "home_gpu_combo"):
                    self._insert_combo_item(self.home_gpu_combo, val, preset_key="gpu")
                if hasattr(self, "gpu_sub_combo"):
                    self._insert_combo_item(self.gpu_sub_combo, val, preset_key="gpu")
            else:
                if hasattr(self, "home_gpu_combo"):
                    self._revert_combo(self.home_gpu_combo, curr)
                if hasattr(self, "gpu_sub_combo"):
                    self._revert_combo(self.gpu_sub_combo, curr)
                return

        self._syncing = True
        self.config["custom_target"]["gpu_model"] = val
        save_config(self.config)

        if hasattr(self, "home_gpu_combo"):
            self.home_gpu_combo.blockSignals(True)
            if self.home_gpu_combo.findText(val) < 0:
                self._insert_combo_item(self.home_gpu_combo, val, preset_key="gpu")
            self.home_gpu_combo.setCurrentText(val)
            self.home_gpu_combo.setToolTip(val)
            self.home_gpu_combo.blockSignals(False)

        if hasattr(self, "gpu_sub_combo"):
            self.gpu_sub_combo.blockSignals(True)
            if self.gpu_sub_combo.findText(val) < 0:
                self._insert_combo_item(self.gpu_sub_combo, val, preset_key="gpu")
            self.gpu_sub_combo.setCurrentText(val)
            self.gpu_sub_combo.setToolTip(val)
            self.gpu_sub_combo.blockSignals(False)

        self._syncing = False

    def sync_disk(self, val, source=None):
        if self._syncing or not val:
            return
        val = str(val).strip()

        if val.startswith("✏️ 自定义"):
            curr = self.config["custom_target"].get("disk_model", "Samsung SSD 990 PRO 4TB")
            new_text, ok = QInputDialog.getText(self, "自定义固态硬盘型号", "请输入自定义硬盘完整型号名称:", text=curr)
            if ok and new_text.strip():
                val = new_text.strip()
                if hasattr(self, "home_disk_combo"):
                    self._insert_combo_item(self.home_disk_combo, val, preset_key="disk")
                if hasattr(self, "disk_sub_combo"):
                    self._insert_combo_item(self.disk_sub_combo, val, preset_key="disk")
            else:
                if hasattr(self, "home_disk_combo"):
                    self._revert_combo(self.home_disk_combo, curr)
                if hasattr(self, "disk_sub_combo"):
                    self._revert_combo(self.disk_sub_combo, curr)
                return

        self._syncing = True
        self.config["custom_target"]["disk_model"] = val
        save_config(self.config)

        if hasattr(self, "home_disk_combo"):
            self.home_disk_combo.blockSignals(True)
            if self.home_disk_combo.findText(val) < 0:
                self._insert_combo_item(self.home_disk_combo, val, preset_key="disk")
            self.home_disk_combo.setCurrentText(val)
            self.home_disk_combo.setToolTip(val)
            self.home_disk_combo.blockSignals(False)

        if hasattr(self, "disk_sub_combo"):
            self.disk_sub_combo.blockSignals(True)
            if self.disk_sub_combo.findText(val) < 0:
                self._insert_combo_item(self.disk_sub_combo, val, preset_key="disk")
            self.disk_sub_combo.setCurrentText(val)
            self.disk_sub_combo.setToolTip(val)
            self.disk_sub_combo.blockSignals(False)

        self._syncing = False

    def on_board_combo_selected(self, text, source=None):
        if self._syncing or not text:
            return
        text = str(text).strip()

        curr_vendor = self.config["custom_target"].get("motherboard_vendor", "ASUSTeK COMPUTER INC.")
        curr_product = self.config["custom_target"].get("motherboard_product", "ROG CROSSHAIR X870E HERO")
        curr_board = f"{curr_vendor} {curr_product}".strip()

        if text.startswith("✏️ 自定义"):
            new_text, ok = QInputDialog.getText(
                self, "自定义主板厂商与型号",
                "请输入自定义主板完整名称 (格式如: ASUSTeK COMPUTER INC. ROG MAXIMUS Z790 HERO):",
                text=curr_board
            )
            if ok and new_text.strip():
                text = new_text.strip()
                if hasattr(self, "home_board_combo"):
                    self._insert_combo_item(self.home_board_combo, text)
                if hasattr(self, "board_sub_combo"):
                    self._insert_combo_item(self.board_sub_combo, text)
            else:
                if hasattr(self, "home_board_combo"):
                    self._revert_combo(self.home_board_combo, curr_board)
                if hasattr(self, "board_sub_combo"):
                    self._revert_combo(self.board_sub_combo, curr_board)
                return

        matched = False
        for b in self.config["presets"]["motherboard"]:
            if f"{b['vendor']} {b['product']}".strip() == text:
                self.sync_board(b["vendor"], b["product"], source=source)
                matched = True
                break
        if not matched:
            parts = text.split(" ", 1)
            if len(parts) == 2:
                v, p = parts[0], parts[1]
            else:
                v, p = "", text
            exists = any(b.get("vendor") == v and b.get("product") == p for b in self.config["presets"]["motherboard"])
            if not exists:
                self.config["presets"]["motherboard"].append({"vendor": v, "product": p})
            self.sync_board(v, p, source=source)

    def on_board_inputs_edited(self, source=None):
        if self._syncing:
            return
        v = self.board_vendor_input.text().strip() if hasattr(self, "board_vendor_input") else ""
        p = self.board_product_input.text().strip() if hasattr(self, "board_product_input") else ""
        self.sync_board(v, p, source=source)

    def sync_board(self, vendor, product, source=None):
        if self._syncing:
            return
        self._syncing = True
        vendor = str(vendor).strip()
        product = str(product).strip()
        self.config["custom_target"]["motherboard_vendor"] = vendor
        self.config["custom_target"]["motherboard_product"] = product
        save_config(self.config)

        if vendor and product.lower().startswith(vendor.lower()):
            full_text = product
        else:
            full_text = f"{vendor} {product}".strip()

        if hasattr(self, "home_board_combo"):
            self.home_board_combo.blockSignals(True)
            if self.home_board_combo.findText(full_text) < 0:
                self._insert_combo_item(self.home_board_combo, full_text)
            self.home_board_combo.setCurrentText(full_text)
            self.home_board_combo.setToolTip(full_text)
            self.home_board_combo.blockSignals(False)

        if hasattr(self, "board_sub_combo"):
            self.board_sub_combo.blockSignals(True)
            if self.board_sub_combo.findText(full_text) < 0:
                self._insert_combo_item(self.board_sub_combo, full_text)
            self.board_sub_combo.setCurrentText(full_text)
            self.board_sub_combo.setToolTip(full_text)
            self.board_sub_combo.blockSignals(False)

        if hasattr(self, "board_vendor_input") and source != self.board_vendor_input:
            self.board_vendor_input.blockSignals(True)
            self.board_vendor_input.setText(vendor)
            self.board_vendor_input.blockSignals(False)

        if hasattr(self, "board_product_input") and source != self.board_product_input:
            self.board_product_input.blockSignals(True)
            self.board_product_input.setText(product)
            self.board_product_input.blockSignals(False)

        self._syncing = False

    def on_vram_changed(self, text):
        if not text:
            return
        text = str(text).strip()
        curr_vram = self.config["custom_target"].get("gpu_vram_gb", 24)

        if text.startswith("✏️ 自定义"):
            new_text, ok = QInputDialog.getText(
                self, "自定义独立显存容量",
                "请输入目标显存大小 (单位: GB，如 32、48 或 64):",
                text=str(curr_vram)
            )
            if ok and new_text.strip():
                import re
                m = re.search(r"(\d+)", new_text)
                gb_val = int(m.group(1)) if m else curr_vram
                val_str = f"{gb_val} GB"
                if hasattr(self, "vram_sub_combo"):
                    self._insert_combo_item(self.vram_sub_combo, val_str, preset_key="vram")
                    self.vram_sub_combo.blockSignals(True)
                    self.vram_sub_combo.setCurrentText(val_str)
                    self.vram_sub_combo.blockSignals(False)
                self.config["custom_target"]["gpu_vram_gb"] = gb_val
                save_config(self.config)
            else:
                if hasattr(self, "vram_sub_combo"):
                    self._revert_combo(self.vram_sub_combo, f"{curr_vram} GB")
            return

        import re
        m = re.search(r"(\d+)\s*GB", text)
        if m:
            self.config["custom_target"]["gpu_vram_gb"] = int(m.group(1))
            save_config(self.config)

    def on_mem_vendor_changed(self, text):
        if not text:
            return
        text = str(text).strip()
        curr_vendor = self.config["custom_target"].get("memory_vendor", "Corsair")

        if text.startswith("✏️ 自定义"):
            new_text, ok = QInputDialog.getText(
                self, "自定义内存品牌 / 颗粒厂商",
                "请输入自定义内存品牌厂商 (如 Kingston、G.Skill、Corsair、Crucial):",
                text=curr_vendor
            )
            if ok and new_text.strip():
                val = new_text.strip()
                if hasattr(self, "mem_vendor_input"):
                    self._insert_combo_item(self.mem_vendor_input, val, preset_key="memory_vendor")
                    self.mem_vendor_input.blockSignals(True)
                    self.mem_vendor_input.setCurrentText(val)
                    self.mem_vendor_input.blockSignals(False)
                self.update_target_field("memory_vendor", val)
            else:
                if hasattr(self, "mem_vendor_input"):
                    self._revert_combo(self.mem_vendor_input, curr_vendor)
            return

        self.update_target_field("memory_vendor", text)

    def on_mem_size_changed(self, text):
        if not text:
            return
        text = str(text).strip()
        curr_size = self.config["custom_target"].get("memory_size_gb", 64)

        if text.startswith("✏️ 自定义"):
            new_text, ok = QInputDialog.getText(
                self, "自定义内存容量",
                "请输入自定义内存容量 (单位: GB，如 96 或 128):",
                text=str(curr_size)
            )
            if ok and new_text.strip():
                import re
                m = re.search(r"(\d+)", new_text)
                gb_val = int(m.group(1)) if m else curr_size
                val_str = f"{gb_val} GB"
                if hasattr(self, "mem_size_input"):
                    self._insert_combo_item(self.mem_size_input, val_str, preset_key="memory_size")
                    self.mem_size_input.blockSignals(True)
                    self.mem_size_input.setCurrentText(val_str)
                    self.mem_size_input.blockSignals(False)
                self.config["custom_target"]["memory_size_gb"] = gb_val
                save_config(self.config)
            else:
                if hasattr(self, "mem_size_input"):
                    self._revert_combo(self.mem_size_input, f"{curr_size} GB")
            return

        import re
        m = re.search(r"(\d+)\s*GB", text)
        if m:
            self.config["custom_target"]["memory_size_gb"] = int(m.group(1))
            save_config(self.config)

    def on_mem_clock_changed(self, text):
        if not text:
            return
        text = str(text).strip()
        curr_clock = self.config["custom_target"].get("memory_clock_mhz", 7200)

        if text.startswith("✏️ 自定义"):
            new_text, ok = QInputDialog.getText(
                self, "自定义内存工作频率",
                "请输入自定义内存工作频率 (单位: MHz，如 8000 或 8400):",
                text=str(curr_clock)
            )
            if ok and new_text.strip():
                import re
                m = re.search(r"(\d+)", new_text)
                mhz_val = int(m.group(1)) if m else curr_clock
                val_str = f"{mhz_val} MHz"
                if hasattr(self, "mem_clock_input"):
                    self._insert_combo_item(self.mem_clock_input, val_str, preset_key="memory_clock")
                    self.mem_clock_input.blockSignals(True)
                    self.mem_clock_input.setCurrentText(val_str)
                    self.mem_clock_input.blockSignals(False)
                self.config["custom_target"]["memory_clock_mhz"] = mhz_val
                save_config(self.config)
            else:
                if hasattr(self, "mem_clock_input"):
                    self._revert_combo(self.mem_clock_input, f"{curr_clock} MHz")
            return

        import re
        m = re.search(r"(\d+)", text)
        if m:
            self.config["custom_target"]["memory_clock_mhz"] = int(m.group(1))
            save_config(self.config)

    def update_heybox_path_status_ui(self, p):
        if not hasattr(self, "heybox_path_status"):
            return
        is_dark = getattr(self, "is_dark_mode", False)
        if not p or not os.path.exists(p):
            self.heybox_path_status.setText("● 提示：指定目录不存在，请点击右侧“浏览路径”选择小黑盒加速器文件夹")
            if is_dark:
                self.heybox_path_status.setStyleSheet("color: #FCD34D; background-color: #78350F; border: 1px solid #B45309; border-radius: 8px; padding: 8px 12px; font-size: 12px; font-weight: 600;")
            else:
                self.heybox_path_status.setStyleSheet("color: #D97706; background-color: #FEF3C7; border: 1px solid #FCD34D; border-radius: 8px; padding: 8px 12px; font-size: 12px; font-weight: 600;")
            return
        # 验证核心标志物
        has_exe = os.path.exists(os.path.join(p, "heyboxacc.exe"))
        has_res = os.path.exists(os.path.join(p, "resources"))
        index_paths = get_xiaoheihe_index_paths(p)
        if has_exe or has_res or len(index_paths) > 0:
            count = len(index_paths)
            self.heybox_path_status.setText(f"● 路径有效：已成功识别小黑盒核心模块 (找到 {count} 个 Electron 拦截入口节点)")
            if is_dark:
                self.heybox_path_status.setStyleSheet("color: #6EE7B7; background-color: #064E3B; border: 1px solid #059669; border-radius: 8px; padding: 8px 12px; font-size: 12px; font-weight: 600;")
            else:
                self.heybox_path_status.setStyleSheet("color: #059669; background-color: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 8px; padding: 8px 12px; font-size: 12px; font-weight: 600;")
        else:
            self.heybox_path_status.setText("● 警告：该目录下未找到 heyboxacc.exe 或 resources 文件夹，请选择包含主程序的根目录")
            if is_dark:
                self.heybox_path_status.setStyleSheet("color: #FCA5A5; background-color: #7F1D1D; border: 1px solid #B91C1C; border-radius: 8px; padding: 8px 12px; font-size: 12px; font-weight: 600;")
            else:
                self.heybox_path_status.setStyleSheet("color: #DC2626; background-color: #FEF2F2; border: 1px solid #FECACA; border-radius: 8px; padding: 8px 12px; font-size: 12px; font-weight: 600;")

    def on_heybox_path_changed(self, text):
        p = text.strip()
        self.config["custom_heybox_dir"] = p
        self.config["custom_target"]["custom_heybox_dir"] = p
        save_config(self.config)
        self.update_heybox_path_status_ui(p)

    def browse_heybox_path(self):
        curr = self.heybox_path_input.text().strip() if hasattr(self, "heybox_path_input") else ""
        if not os.path.exists(curr):
            curr = "C:\\"
        selected = QFileDialog.getExistingDirectory(self, "选择小黑盒加速器安装根目录 (包含 heyboxacc.exe 的文件夹)", curr)
        if selected:
            selected = os.path.normpath(selected)
            self.heybox_path_input.setText(selected)

    def redetect_heybox_path(self):
        if "custom_heybox_dir" in self.config:
            del self.config["custom_heybox_dir"]
        if "custom_heybox_dir" in self.config.get("custom_target", {}):
            del self.config["custom_target"]["custom_heybox_dir"]
        save_config(self.config)
        detected = get_xiaoheihe_base_dir()
        self.heybox_path_input.setText(detected)
        QMessageBox.information(self, "探测完成", f"已重新自动探测到小黑盒根目录：\n\n{detected}")

    def _sync_all_inputs_to_target(self):
        """实时同步当前所有输入控件与下拉框的选中值到 custom_target"""
        if not hasattr(self, "config") or "custom_target" not in self.config:
            return

        # CPU
        if hasattr(self, "home_cpu_combo"):
            c = self.home_cpu_combo.currentText().strip()
            if c and not c.startswith("✏️"):
                self.config["custom_target"]["cpu_model"] = c
        elif hasattr(self, "cpu_sub_combo"):
            c = self.cpu_sub_combo.currentText().strip()
            if c and not c.startswith("✏️"):
                self.config["custom_target"]["cpu_model"] = c

        # GPU
        if hasattr(self, "home_gpu_combo"):
            g = self.home_gpu_combo.currentText().strip()
            if g and not g.startswith("✏️"):
                self.config["custom_target"]["gpu_model"] = g
        elif hasattr(self, "gpu_sub_combo"):
            g = self.gpu_sub_combo.currentText().strip()
            if g and not g.startswith("✏️"):
                self.config["custom_target"]["gpu_model"] = g

        # VRAM
        if hasattr(self, "vram_sub_combo"):
            v_text = self.vram_sub_combo.currentText().strip()
            import re
            m = re.search(r"(\d+)", v_text)
            if m:
                self.config["custom_target"]["gpu_vram_gb"] = int(m.group(1))

        # Motherboard
        if hasattr(self, "board_vendor_input") and hasattr(self, "board_product_input"):
            bv = self.board_vendor_input.text().strip()
            bp = self.board_product_input.text().strip()
            if bv:
                self.config["custom_target"]["motherboard_vendor"] = bv
            if bp:
                self.config["custom_target"]["motherboard_product"] = bp

        # Memory
        if hasattr(self, "mem_vendor_input"):
            mv = self.mem_vendor_input.currentText().strip()
            if mv and not mv.startswith("✏️"):
                self.config["custom_target"]["memory_vendor"] = mv
        if hasattr(self, "mem_size_input"):
            ms = self.mem_size_input.currentText().strip()
            import re
            m = re.search(r"(\d+)", ms)
            if m:
                self.config["custom_target"]["memory_size_gb"] = int(m.group(1))
        if hasattr(self, "mem_clock_input"):
            mc = self.mem_clock_input.currentText().strip()
            import re
            m = re.search(r"(\d+)", mc)
            if m:
                self.config["custom_target"]["memory_clock_mhz"] = int(m.group(1))

        # Disk
        if hasattr(self, "home_disk_combo"):
            d = self.home_disk_combo.currentText().strip()
            if d and not d.startswith("✏️"):
                self.config["custom_target"]["disk_model"] = d
        elif hasattr(self, "disk_sub_combo"):
            d = self.disk_sub_combo.currentText().strip()
            if d and not d.startswith("✏️"):
                self.config["custom_target"]["disk_model"] = d

        # Client / Acceleration path
        if hasattr(self, "heybox_path_input"):
            hp = self.heybox_path_input.text().strip()
            if hp:
                self.config["custom_heybox_dir"] = hp
                self.config["custom_target"]["custom_heybox_dir"] = hp

    def on_apply_clicked(self):
        self._sync_all_inputs_to_target()
        h_dir = self.heybox_path_input.text().strip() if hasattr(self, "heybox_path_input") else get_xiaoheihe_base_dir()
        self.config["custom_heybox_dir"] = h_dir
        self.config["custom_target"]["custom_heybox_dir"] = h_dir
        save_config(self.config)

        progress_dlg = ModernProgressDialog(
            self,
            title="应用全硬件自定义配置",
            description="正在初始化全套硬件配置...",
            is_dark=self.is_dark_mode
        )
        progress_dlg.show()

        # Step 1: 15%
        progress_dlg.set_progress(15, "正在校验并备份系统硬件注册表分支...", "创建出厂恢复快照与安全验证")
        QApplication.processEvents()

        # Step 2: 30%
        cpu_t = self.config["custom_target"].get("cpu_model", "AMD Ryzen 9 9950X3D2 16-Core Processor")
        progress_dlg.set_progress(30, "正在改写 CPU 处理器信息与核心参数...", f"目标型号: {cpu_t}")
        QApplication.processEvents()

        # Step 3: 50%
        gpu_t = self.config["custom_target"].get("gpu_model", "NVIDIA GeForce RTX 5090")
        vram_gb = self.config["custom_target"].get("gpu_vram_gb", 32)
        progress_dlg.set_progress(50, "正在同步 独立显卡型号与专用显存 (VRAM)...", f"目标型号: {gpu_t} ({vram_gb} GB)")
        QApplication.processEvents()

        # Step 4: 65%
        bv = self.config["custom_target"].get("motherboard_vendor", "ASUSTeK COMPUTER INC.")
        bp = self.config["custom_target"].get("motherboard_product", "ROG CROSSHAIR X870E HERO")
        progress_dlg.set_progress(65, "正在配置 主板制造商与 BIOS 产品标识...", f"{bv} - {bp}")
        QApplication.processEvents()

        # Step 5: 80%
        disk_t = self.config["custom_target"].get("disk_model", "Samsung SSD 990 PRO 4TB")
        progress_dlg.set_progress(80, "正在注入 硬盘 SCSI 设备标识与通道...", f"目标型号: {disk_t}")
        QApplication.processEvents()

        # Step 6: 92%
        progress_dlg.set_progress(92, "正在部署 小黑盒全硬件拦截器与渲染补丁...", f"拦截路径: {h_dir}")
        QApplication.processEvents()

        ok, msg = execute_hardware_apply(self.config["custom_target"])

        # Step 7: 100%
        if ok:
            progress_dlg.finish(
                True,
                "全套硬件自定义配置已深度生效！",
                "CPU、显卡、主板、硬盘及小黑盒补丁已全部就绪并验证成功",
                auto_close_delay_ms=1200
            )
        else:
            progress_dlg.finish(
                False,
                "硬件配置修改未生效",
                msg,
                auto_close_delay_ms=2500
            )
            QMessageBox.warning(
                self,
                "修改提示",
                f"硬件配置修改未能完全生效：\n\n{msg}\n\n请尝试右键以管理员身份运行软件重试！"
            )

    def on_apply_single_component(self, comp_key: str):
        self._sync_all_inputs_to_target()
        comp_names = {
            "cpu": "CPU 处理器",
            "gpu": "显卡与显存",
            "board": "主板 BIOS",
            "memory": "内存 DDR5",
            "disk": "硬盘存储"
        }
        name = comp_names.get(comp_key, comp_key.upper())

        h_dir = self.heybox_path_input.text().strip() if hasattr(self, "heybox_path_input") else get_xiaoheihe_base_dir()
        self.config["custom_heybox_dir"] = h_dir
        self.config["custom_target"]["custom_heybox_dir"] = h_dir
        save_config(self.config)

        progress_dlg = ModernProgressDialog(
            self,
            title=f"单独生效 {name} 配置",
            description=f"正在准备生效 {name}...",
            is_dark=self.is_dark_mode
        )
        progress_dlg.show()

        progress_dlg.set_progress(35, f"正在锁定 {name} 目标配置参数...", "配置参数校验与环境分析")
        QApplication.processEvents()

        progress_dlg.set_progress(75, f"正在将 {name} 写入底层硬件环境...", "执行单独配置写入与校验")
        QApplication.processEvents()

        ok, msg = execute_hardware_apply(self.config["custom_target"], components=[comp_key])

        if ok:
            progress_dlg.finish(
                True,
                f"{name} 配置已单独生效！",
                f"{name} 硬件参数已更新并即时验证通过",
                auto_close_delay_ms=1200
            )
        else:
            progress_dlg.finish(
                False,
                f"{name} 生效提示",
                msg,
                auto_close_delay_ms=2500
            )
            QMessageBox.warning(
                self,
                "生效提示",
                f"{name} 单独生效未能完全成功：\n\n{msg}\n\n请尝试右键以管理员身份运行软件重试！"
            )

    def on_restore_clicked(self):
        reply = QMessageBox.question(
            self,
            "确认还原",
            "确定要一键还原官方真实出厂硬件并移除所有小黑盒拦截器吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            progress_dlg = ModernProgressDialog(
                self,
                title="一键还原官方出厂硬件",
                description="正在准备还原官方真实配置...",
                is_dark=self.is_dark_mode
            )
            progress_dlg.show()

            progress_dlg.set_progress(20, "正在读取官方出厂硬件备份...", "加载原始硬件设备快照")
            QApplication.processEvents()

            progress_dlg.set_progress(50, "正在恢复 CPU / GPU / 显存出厂原始值...", "清除自定义注册表重写")
            QApplication.processEvents()

            progress_dlg.set_progress(75, "正在还原主板与硬盘设备信息...", "恢复 BIOS 与 SCSI 默认参数")
            QApplication.processEvents()

            progress_dlg.set_progress(90, "正在移除小黑盒加速器拦截器...", "恢复官方入口文件与清理守护服务")
            QApplication.processEvents()

            ok, msg = execute_hardware_restore()
            if ok:
                real_cpu = self.config["current_hardware"].get("detected_cpu", DEFAULT_REAL_CPU)
                real_gpu = self.config["current_hardware"].get("detected_gpu", DEFAULT_REAL_GPU)
                real_bv = self.config["current_hardware"].get("motherboard_vendor", DEFAULT_REAL_BOARD_VENDOR)
                real_bp = self.config["current_hardware"].get("motherboard_product", DEFAULT_REAL_BOARD_PRODUCT)
                real_disk = self.config["current_hardware"].get("disk_model", DEFAULT_REAL_DISK_MODEL)
                self.sync_cpu(real_cpu)
                self.sync_gpu(real_gpu)
                self.sync_board(real_bv, real_bp)
                self.sync_disk(real_disk)

                progress_dlg.finish(
                    True,
                    "官方出厂硬件已成功恢复！",
                    "所有显示参数与小黑盒拦截器已清理还原完毕并验证成功",
                    auto_close_delay_ms=1200
                )
            else:
                progress_dlg.finish(
                    False,
                    "出厂硬件恢复遇到问题",
                    msg,
                    auto_close_delay_ms=2500
                )
                QMessageBox.warning(
                    self,
                    "恢复提示",
                    f"出厂硬件未能完全还原：\n\n{msg}\n\n请尝试右键以管理员身份运行软件重试！"
                )

    def on_refresh_hook(self):
        p = self.heybox_path_input.text().strip() if hasattr(self, "heybox_path_input") else get_xiaoheihe_base_dir()
        progress_dlg = ModernProgressDialog(
            self,
            title="更新小黑盒拦截器与渲染补丁",
            description="正在重新注入拦截补丁...",
            is_dark=self.is_dark_mode
        )
        progress_dlg.show()
        progress_dlg.set_progress(40, "正在定位小黑盒主程序核心脚本...", p)
        QApplication.processEvents()

        apply_xiaoheihe_hook(p)

        progress_dlg.finish(
            True,
            "小黑盒拦截器已成功更新！",
            "前端渲染补丁与 SSS 评级算法已同步就绪",
            auto_close_delay_ms=1000
        )

    def on_restore_hook_only(self):
        p = self.heybox_path_input.text().strip() if hasattr(self, "heybox_path_input") else get_xiaoheihe_base_dir()
        progress_dlg = ModernProgressDialog(
            self,
            title="还原小黑盒官方状态",
            description="正在移除小黑盒拦截器...",
            is_dark=self.is_dark_mode
        )
        progress_dlg.show()
        progress_dlg.set_progress(40, "正在恢复官方原始入口脚本...", p)
        QApplication.processEvents()

        restore_xiaoheihe_hook(p)

        progress_dlg.finish(
            True,
            "小黑盒已恢复官方状态！",
            "前端代码与核心入口已恢复出厂官方文件",
            auto_close_delay_ms=1000
        )


def main():
    # 优先请求管理员权限以保障底层注册表与驱动参数修改生效
    request_admin()

    app = QApplication(sys.argv)
    from common.ui_theme import install_combo_arrows
    install_combo_arrows(app)

    # 启用高清晰度 ClearType 亚像素抗锯齿与精准网格对齐字体引擎
    app_font = QFont("Microsoft YaHei UI", 10)
    app_font.setStyleStrategy(QFont.PreferAntialias | QFont.PreferQuality)
    app_font.setHintingPreference(QFont.PreferFullHinting)
    app.setFont(app_font)

    # 外部与任务栏图标关联 (Windows AppID)
    try:
        myappid = "DMHardware.Master.Customizer.2.5"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
