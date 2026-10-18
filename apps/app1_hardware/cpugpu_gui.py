# -*- coding: utf-8 -*-
"""
电脑全套硬件配置自定义管理工具 (旗舰增强版)
全面突破与深度覆盖：CPU、GPU/显存、主板、内存、硬盘
支持 Windows 任务管理器、DirectX/DXGI、设备管理器、小黑盒加速器硬件检测
"""

import os
import sys
import json
import subprocess
import ctypes
import winreg
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox

# 路径常量
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
PUBLIC_CONFIG_FILE = r"C:\Users\Public\Hardware_Config.json"

# 官方真实硬件备份文件
CPU_BACKUP_FILE = r"C:\CPU_Backup.cfg"
GPU_BACKUP_FILE = r"C:\GPU_Backup.cfg"
GPU_PATH_BACKUP_FILE = r"C:\GPU_Path_Backup.cfg"
BOARD_VENDOR_BACKUP_FILE = r"C:\Board_Vendor_Backup.cfg"
BOARD_PRODUCT_BACKUP_FILE = r"C:\Board_Product_Backup.cfg"
DISK_BACKUP_FILE = r"C:\Disk_Backup.cfg"
DISK_PATH_BACKUP_FILE = r"C:\Disk_Path_Backup.cfg"
CPU_CONFIG_FILE = r"C:\CPU_Config.txt"

# 真实出厂硬件默认参考
DEFAULT_REAL_CPU = "AMD Ryzen 5 9600X 6-Core Processor"
DEFAULT_REAL_GPU = "NVIDIA GeForce RTX 4070"
DEFAULT_REAL_VRAM_BYTES = 12593397760  # ~11.73-12 GB
DEFAULT_REAL_GPU_DESC = "@oem22.inf,%nvidia_dev.2786%;NVIDIA GeForce RTX 4070"
DEFAULT_REAL_BOARD_VENDOR = "MAXSUN"
DEFAULT_REAL_BOARD_PRODUCT = "MS-eSport B650ITX"
DEFAULT_REAL_DISK_MODEL = "YSSDM-2TN3000"
DEFAULT_REAL_DISK_PATH = r"SCSI\DISK&VEN_NVME&PROD_YSSDM-2TN3000\5&1574F6F4&0&000000"


def is_admin():
    """检查当前进程是否具有管理员权限"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def request_admin(action_arg=""):
    """请求 Windows UAC 管理员提权并重启程序"""
    if not is_admin():
        if getattr(sys, "frozen", False):
            exe_path = sys.executable
            args = action_arg.strip()
            ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe_path, args, None, 1)
        else:
            exe_path = sys.executable
            script_path = os.path.abspath(__file__)
            args = f'"{script_path}" {action_arg}'.strip()
            ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe_path, args, None, 1)

        if ret > 32:
            sys.exit(0)
        else:
            messagebox.showerror(
                "权限提示",
                "修改底层硬件注册表需要管理员权限，请在弹出窗口中点击「是」，或右键选择「以管理员身份运行」！"
            )
            return False
    return True


def load_config():
    """读取 config.json，若不存在则返回全套默认预设"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"读取配置失败: {e}")

    return {
        "_说明": "全硬件自定义硬件信息配置文件",
        "current_hardware": {
            "detected_cpu": DEFAULT_REAL_CPU,
            "detected_gpu": DEFAULT_REAL_GPU,
            "gpu_instance_path": r"PCI\VEN_10DE&DEV_2786&SUBSYS_12017377&REV_A1\4&D0BDF66&0&0009",
            "motherboard_vendor": DEFAULT_REAL_BOARD_VENDOR,
            "motherboard_product": DEFAULT_REAL_BOARD_PRODUCT,
            "memory_vendor": "Asgard",
            "memory_size_gb": 32,
            "memory_clock_mhz": 6000,
            "disk_model": DEFAULT_REAL_DISK_MODEL,
            "disk_instance_path": DEFAULT_REAL_DISK_PATH
        },
        "custom_target": {
            "cpu_model": "AMD Ryzen 9 9950X3D2 16-Core Processor",
            "gpu_model": "NVIDIA GeForce RTX 5090",
            "gpu_vram_gb": 32,
            "target_gpu_instance_path": r"PCI\VEN_10DE&DEV_2786&SUBSYS_12017377&REV_A1\4&D0BDF66&0&0009",
            "motherboard_vendor": "ASUSTeK COMPUTER INC.",
            "motherboard_product": "ROG CROSSHAIR X870E HERO",
            "memory_vendor": "Corsair",
            "memory_size_gb": 64,
            "memory_clock_mhz": 7200,
            "disk_model": "Samsung SSD 990 PRO 4TB",
            "target_disk_instance_path": DEFAULT_REAL_DISK_PATH,
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
                "AMD Ryzen 9 7950X 16-Core Processor",
                "AMD Ryzen 7 5700X3D 8-Core Processor",
                "AMD Ryzen Threadripper 7980X 64-Core Processor",
                "AMD EPYC 9654 96-Core Processor",
                "Intel Core Ultra 9 285K",
                "Intel Core Ultra 7 265K",
                "Intel Core Ultra 5 245K",
                "14th Gen Intel(R) Core(TM) i9-14900KS",
                "14th Gen Intel(R) Core(TM) i9-14900K",
                "14th Gen Intel(R) Core(TM) i7-14700K",
                "14th Gen Intel(R) Core(TM) i5-14600K",
                "13th Gen Intel(R) Core(TM) i9-13900KS",
                "13th Gen Intel(R) Core(TM) i9-13900K",
                "12th Gen Intel(R) Core(TM) i9-12900K",
                "Intel(R) Xeon(R) Platinum 8592+"
            ],
            "gpu": [
                "NVIDIA GeForce RTX 5090",
                "NVIDIA GeForce RTX 5090 D",
                "NVIDIA GeForce RTX 5080",
                "NVIDIA GeForce RTX 5070 Ti",
                "NVIDIA GeForce RTX 5070",
                "NVIDIA GeForce RTX 4090",
                "NVIDIA GeForce RTX 4090 D",
                "NVIDIA GeForce RTX 4080 SUPER",
                "NVIDIA GeForce RTX 4080",
                "NVIDIA GeForce RTX 4070 Ti SUPER",
                "NVIDIA GeForce RTX 4070 Ti",
                "NVIDIA GeForce RTX 4070 SUPER",
                "NVIDIA GeForce RTX 4070",
                "NVIDIA GeForce RTX 4060 Ti",
                "NVIDIA GeForce RTX 3090 Ti",
                "NVIDIA GeForce RTX 3090",
                "NVIDIA RTX 6000 Ada Generation",
                "NVIDIA RTX 5000 Ada Generation",
                "NVIDIA H100 80GB HBM3",
                "AMD Radeon RX 7900 XTX",
                "AMD Radeon RX 7900 XT",
                "AMD Radeon RX 7900 GRE",
                "AMD Radeon RX 7800 XT"
            ],
            "vram": [
                "48 GB",
                "32 GB",
                "24 GB",
                "20 GB",
                "16 GB",
                "12 GB (保持原始)",
                "8 GB"
            ],
            "motherboard": [
                {"vendor": "ASUSTeK COMPUTER INC.", "product": "ROG CROSSHAIR X870E HERO"},
                {"vendor": "ASUSTeK COMPUTER INC.", "product": "ROG CROSSHAIR X870E DARK HERO"},
                {"vendor": "ASUSTeK COMPUTER INC.", "product": "ROG MAXIMUS Z890 EXTREME"},
                {"vendor": "ASUSTeK COMPUTER INC.", "product": "ROG MAXIMUS Z890 APEX"},
                {"vendor": "ASUSTeK COMPUTER INC.", "product": "ROG MAXIMUS Z890 HERO"},
                {"vendor": "ASUSTeK COMPUTER INC.", "product": "ROG STRIX X870-F GAMING WIFI"},
                {"vendor": "ASUSTeK COMPUTER INC.", "product": "ROG STRIX Z790-H GAMING WIFI"},
                {"vendor": "ASUSTeK COMPUTER INC.", "product": "TUF GAMING X870-PLUS WIFI"},
                {"vendor": "ASUSTeK COMPUTER INC.", "product": "ROG STRIX B650-A GAMING WIFI"},
                {"vendor": "Micro-Star International Co., Ltd.", "product": "MEG X870E GODLIKE"},
                {"vendor": "Micro-Star International Co., Ltd.", "product": "MEG Z890 GODLIKE"},
                {"vendor": "Micro-Star International Co., Ltd.", "product": "MPG X870E CARBON WIFI"},
                {"vendor": "Micro-Star International Co., Ltd.", "product": "MAG X870 TOMAHAWK WIFI"},
                {"vendor": "Micro-Star International Co., Ltd.", "product": "MAG B650 TOMAHAWK WIFI"},
                {"vendor": "Gigabyte Technology Co., Ltd.", "product": "X870E AORUS XTREME"},
                {"vendor": "Gigabyte Technology Co., Ltd.", "product": "X870E AORUS MASTER"},
                {"vendor": "Gigabyte Technology Co., Ltd.", "product": "Z890 AORUS MASTER"},
                {"vendor": "Gigabyte Technology Co., Ltd.", "product": "B650 AORUS ELITE AX"},
                {"vendor": "ASRock", "product": "X870E Taichi"}
            ],
            "memory_vendor": [
                "Corsair",
                "G.Skill",
                "Kingston",
                "Asgard",
                "Predator",
                "TEAMGROUP",
                "Crucial",
                "ADATA"
            ],
            "memory_size": [
                "128 GB",
                "96 GB (48GBx2)",
                "64 GB (32GBx2)",
                "48 GB (24GBx2)",
                "32 GB (16GBx2)",
                "16 GB (8GBx2)"
            ],
            "memory_clock": [
                "8400 MHz",
                "8000 MHz",
                "7600 MHz",
                "7200 MHz",
                "6800 MHz",
                "6400 MHz",
                "6000 MHz",
                "5600 MHz",
                "3600 MHz"
            ],
            "disk": [
                "Samsung SSD 990 PRO 2TB",
                "Samsung SSD 990 PRO 4TB",
                "Crucial T705 2TB PCIe 5.0 NVMe M.2 SSD",
                "WD_BLACK SN850X 2000GB",
                "WD_BLACK SN850X 4000GB",
                "ZhiTai TiPro7000 2TB NVMe SSD",
                "ZhiTai TiPlus7100 2TB NVMe SSD",
                "Kingston KC3000 2048GB PCIe 4.0 NVMe M.2 SSD",
                "SK hynix Platinum P41 2TB",
                "YSSDM-2TN3000"
            ]
        }
    }


def save_config(cfg):
    """保存配置到 config.json 及公共共享路径"""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存配置失败: {e}")
    try:
        with open(PUBLIC_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_xiaoheihe_index_paths():
    """查找小黑盒加速器 resources\\app\\index.js 路径"""
    base = r"C:\Program Files (x86)\Qingfeng\HeyboxAccelerator"
    if not os.path.exists(base):
        return []
    paths = []
    for root, dirs, files in os.walk(base):
        if "index.js" in files and os.path.basename(root) == "app":
            paths.append(os.path.join(root, "index.js"))
    return paths


def patch_xiaoheihe_webapp():
    """修补小黑盒前端 UI 实时同步硬件评分与卡片展示"""
    base = r"C:\Program Files (x86)\Qingfeng\HeyboxAccelerator"
    if not os.path.exists(base):
        return
    for root, dirs, files in os.walk(base):
        if "chunk-793bf638.0533358a.js" in files:
            f1 = os.path.join(root, "chunk-793bf638.0533358a.js")
            bak1 = f1 + ".bak"
            if not os.path.exists(bak1):
                try:
                    import shutil
                    shutil.copyfile(f1, bak1)
                except Exception:
                    pass
            try:
                with open(f1, "r", encoding="utf-8") as fp:
                    c1 = fp.read()
                t1 = "a.hardwareEvalInfo=t.data.result"
                r1 = '(a.hardwareEvalInfo=t.data.result,a.hardwareInfo&&a.hardwareInfo.gpus&&a.hardwareInfo.gpus[0]&&(a.hardwareEvalInfo.gpus.show_key=a.hardwareInfo.gpus[0].name+(a.hardwareInfo.gpus[0].memory_size?\' \'+Math.round(a.hardwareInfo.gpus[0].memory_size/1024)+\'GB\':\'\'),a.hardwareEvalInfo.cpu&&(a.hardwareEvalInfo.cpu.show_key=a.hardwareInfo.cpu.name),a.hardwareEvalInfo.avg_perf_level="SSS",a.hardwareEvalInfo.avg_good_than_other_user_percent=99.9,a.hardwareEvalInfo.gpus.perf_level="SSS",a.hardwareEvalInfo.gpus.score_v2=99,a.hardwareEvalInfo.gpus.percentage_v2=99,a.hardwareEvalInfo.cpu&&(a.hardwareEvalInfo.cpu.perf_level="SS",a.hardwareEvalInfo.cpu.score_v2=98)))'
                if t1 in c1:
                    c1 = c1.replace(t1, r1, 1)
                    with open(f1, "w", encoding="utf-8") as fp:
                        fp.write(c1)
            except Exception:
                pass
        if "chunk-499402f5.29a05416.js" in files:
            f2 = os.path.join(root, "chunk-499402f5.29a05416.js")
            bak2 = f2 + ".bak"
            if not os.path.exists(bak2):
                try:
                    import shutil
                    shutil.copyfile(f2, bak2)
                except Exception:
                    pass
            try:
                with open(f2, "r", encoding="utf-8") as fp:
                    c2 = fp.read()
                t2 = "e&&(t.hardware_info=a.hardware_info)"
                r2 = '(e&&(t.hardware_info=a.hardware_info,t.$store.state.hardwareInfo&&t.$store.state.hardwareInfo.gpus&&t.$store.state.hardwareInfo.gpus[0]&&(t.hardware_info.gpu_name=t.$store.state.hardwareInfo.gpus[0].name,t.hardware_info.cpu_name=t.$store.state.hardwareInfo.cpu.name,t.hardware_info.board_name=t.$store.state.hardwareInfo.board.name,t.hardware_info.score="SSS",t.hardware_info.percent=99)))'
                if t2 in c2:
                    c2 = c2.replace(t2, r2, 1)
                    with open(f2, "w", encoding="utf-8") as fp:
                        fp.write(c2)
            except Exception:
                pass


def apply_xiaoheihe_hook():
    """向小黑盒注入全套硬件检测拦截器与前端渲染补丁"""
    template_file = os.path.join(BASE_DIR, "xiaoheihe_index.js")
    if os.path.exists(template_file):
        with open(template_file, "r", encoding="utf-8") as tf:
            hook_full_content = tf.read()

        for p in get_xiaoheihe_index_paths():
            try:
                bak = p + ".bak"
                if not os.path.exists(bak):
                    with open(p, "r", encoding="utf-8") as f:
                        orig = f.read()
                    with open(bak, "w", encoding="utf-8") as f:
                        f.write(orig)

                with open(p, "w", encoding="utf-8") as f:
                    f.write(hook_full_content)
            except Exception:
                pass

    patch_xiaoheihe_webapp()


def restore_xiaoheihe_hook():
    """还原小黑盒原始入口文件与前端文件"""
    for p in get_xiaoheihe_index_paths():
        try:
            bak = p + ".bak"
            if os.path.exists(bak):
                with open(bak, "r", encoding="utf-8") as f:
                    orig = f.read()
                with open(p, "w", encoding="utf-8") as f:
                    f.write(orig)
                os.remove(bak)
        except Exception:
            pass

    base = r"C:\Program Files (x86)\Qingfeng\HeyboxAccelerator"
    if os.path.exists(base):
        for root, dirs, files in os.walk(base):
            for fn in ["chunk-793bf638.0533358a.js", "chunk-499402f5.29a05416.js"]:
                if fn + ".bak" in files:
                    fp = os.path.join(root, fn)
                    bak = fp + ".bak"
                    try:
                        import shutil
                        shutil.copyfile(bak, fp)
                        os.remove(bak)
                    except Exception:
                        pass


def apply_hardware_modifications(
    cpu_target,
    gpu_target,
    gpu_pnp,
    vram_gb,
    board_vendor,
    board_product,
    memory_vendor,
    memory_gb,
    memory_clock,
    disk_model,
    disk_pnp,
    enable_startup
):
    """
    【核心突破】深度应用全套硬件修改：
    同时覆盖 CPU、DirectX/DXGI、任务管理器专用显存、Control\\Video、Control\\Class、Enum、主板BIOS、硬盘FriendlyName与小黑盒加速器
    """
    vram_bytes = int(vram_gb * 1024 * 1024 * 1024)
    vram_dword = min(vram_bytes, 0xFFFFFFFF)
    errors = []

    # 1. 自动备份硬件出厂原始数据
    try:
        if not os.path.exists(CPU_BACKUP_FILE):
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
                real_c, _ = winreg.QueryValueEx(k, "ProcessorNameString")
                with open(CPU_BACKUP_FILE, "w", encoding="utf-8") as f:
                    f.write(real_c.strip())

        if not os.path.exists(GPU_BACKUP_FILE) and gpu_pnp:
            enum_path = r"SYSTEM\CurrentControlSet\Enum\\" + gpu_pnp
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, enum_path) as k:
                real_g, _ = winreg.QueryValueEx(k, "DeviceDesc")
                with open(GPU_BACKUP_FILE, "w", encoding="utf-8") as f:
                    f.write(real_g.strip())
                with open(GPU_PATH_BACKUP_FILE, "w", encoding="utf-8") as f:
                    f.write(gpu_pnp.strip())

        if not os.path.exists(BOARD_VENDOR_BACKUP_FILE):
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\BIOS") as k:
                try:
                    bv, _ = winreg.QueryValueEx(k, "BaseBoardManufacturer")
                    with open(BOARD_VENDOR_BACKUP_FILE, "w", encoding="utf-8") as f:
                        f.write(bv.strip())
                except Exception:
                    pass
                try:
                    bp, _ = winreg.QueryValueEx(k, "BaseBoardProduct")
                    with open(BOARD_PRODUCT_BACKUP_FILE, "w", encoding="utf-8") as f:
                        f.write(bp.strip())
                except Exception:
                    pass

        if not os.path.exists(DISK_BACKUP_FILE) and disk_pnp:
            disk_reg = r"SYSTEM\CurrentControlSet\Enum\\" + disk_pnp
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, disk_reg) as k:
                    rd, _ = winreg.QueryValueEx(k, "FriendlyName")
                    with open(DISK_BACKUP_FILE, "w", encoding="utf-8") as f:
                        f.write(rd.strip())
                    with open(DISK_PATH_BACKUP_FILE, "w", encoding="utf-8") as f:
                        f.write(disk_pnp.strip())
            except Exception:
                pass
    except Exception as e:
        errors.append(f"硬件备份提示: {e}")

    # 2. 修改 CPU 注册表
    try:
        cpu_base = r"HARDWARE\DESCRIPTION\System\CentralProcessor"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, cpu_base) as k:
            num_cores = winreg.QueryInfoKey(k)[0]
            for i in range(num_cores):
                sub_name = winreg.EnumKey(k, i)
                if sub_name.isdigit():
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{cpu_base}\\{sub_name}", 0, winreg.KEY_WRITE) as sk:
                        winreg.SetValueEx(sk, "ProcessorNameString", 0, winreg.REG_SZ, cpu_target)
    except Exception as e:
        errors.append(f"CPU核心修改失败: {e}")

    # 写入 ACPI 处理器友好名称
    try:
        acpi_base = r"SYSTEM\CurrentControlSet\Enum\ACPI"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, acpi_base) as ak:
            n_keys = winreg.QueryInfoKey(ak)[0]
            for i in range(n_keys):
                name = winreg.EnumKey(ak, i)
                if "processor" in name.lower() or "cpu" in name.lower():
                    sub_p = f"{acpi_base}\\{name}"
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub_p) as sk:
                            for j in range(winreg.QueryInfoKey(sk)[0]):
                                inst_k = winreg.EnumKey(sk, j)
                                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{sub_p}\\{inst_k}", 0, winreg.KEY_WRITE) as ik:
                                    winreg.SetValueEx(ik, "FriendlyName", 0, winreg.REG_SZ, cpu_target)
                                    winreg.SetValueEx(ik, "DeviceDesc", 0, winreg.REG_SZ, cpu_target)
                    except Exception:
                        pass
    except Exception:
        pass

    try:
        with open(CPU_CONFIG_FILE, "w", encoding="ascii") as f:
            f.write(cpu_target.strip())
    except Exception:
        pass

    # 3. 修改 DirectX / DXGI 适配器描述与显存 (任务管理器性能面板)
    try:
        dx_base = r"SOFTWARE\Microsoft\DirectX"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, dx_base, 0, winreg.KEY_READ | winreg.KEY_WRITE) as dxk:
            winreg.SetValueEx(dxk, "MaxDedicatedVideoMemory", 0, winreg.REG_QWORD, vram_bytes)
            for i in range(winreg.QueryInfoKey(dxk)[0]):
                guid = winreg.EnumKey(dxk, i)
                if guid.startswith("{") and guid.endswith("}"):
                    sub_path = f"{dx_base}\\{guid}"
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub_path, 0, winreg.KEY_READ | winreg.KEY_WRITE) as sk:
                            desc, _ = winreg.QueryValueEx(sk, "Description")
                            if "basic" not in desc.lower() and "virtual" not in desc.lower():
                                winreg.SetValueEx(sk, "Description", 0, winreg.REG_SZ, gpu_target)
                                winreg.SetValueEx(sk, "DedicatedVideoMemory", 0, winreg.REG_QWORD, vram_bytes)
                    except Exception:
                        pass
    except Exception as e:
        errors.append(f"DirectX显存修改提示: {e}")

    # 4. 修改 Control\\Video 底层显存与硬件描述
    v_base = r"SYSTEM\CurrentControlSet\Control\Video"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, v_base, 0, winreg.KEY_READ) as vk:
            n_sub = winreg.QueryInfoKey(vk)[0]
            for idx in range(n_sub):
                guid = winreg.EnumKey(vk, idx)
                if guid.startswith("{") and guid.endswith("}"):
                    guid_path = f"{v_base}\\{guid}"
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{guid_path}\\Video", 0, winreg.KEY_READ | winreg.KEY_WRITE) as vdk:
                            cur_desc, _ = winreg.QueryValueEx(vdk, "DeviceDesc")
                            if "virtual" not in cur_desc.lower() and "remote" not in cur_desc.lower():
                                winreg.SetValueEx(vdk, "DeviceDesc", 0, winreg.REG_SZ, gpu_target)
                    except Exception:
                        pass

                    for out_i in range(8):
                        out_name = f"{out_i:04d}"
                        out_path = f"{guid_path}\\{out_name}"
                        try:
                            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, out_path, 0, winreg.KEY_READ | winreg.KEY_WRITE) as ok:
                                chip, _ = winreg.QueryValueEx(ok, "HardwareInformation.ChipType")
                                if "virtual" not in str(chip).lower() and "remote" not in str(chip).lower():
                                    winreg.SetValueEx(ok, "HardwareInformation.ChipType", 0, winreg.REG_SZ, gpu_target)
                                    winreg.SetValueEx(ok, "HardwareInformation.AdapterString", 0, winreg.REG_SZ, gpu_target)
                                    winreg.SetValueEx(ok, "HardwareInformation.qwMemorySize", 0, winreg.REG_QWORD, vram_bytes)
                                    winreg.SetValueEx(ok, "HardwareInformation.MemorySize", 0, winreg.REG_DWORD, vram_dword)
                                    winreg.SetValueEx(ok, "DriverDesc", 0, winreg.REG_SZ, gpu_target)
                        except Exception:
                            pass
    except Exception as e:
        errors.append(f"Control\\Video修改提示: {e}")

    # 5. 修改 Class 显示适配器项
    class_base = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, class_base, 0, winreg.KEY_READ) as ck:
            for idx in range(winreg.QueryInfoKey(ck)[0]):
                sub = winreg.EnumKey(ck, idx)
                if sub.isdigit() and len(sub) == 4:
                    sub_path = f"{class_base}\\{sub}"
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub_path, 0, winreg.KEY_READ | winreg.KEY_WRITE) as sk:
                            drv, _ = winreg.QueryValueEx(sk, "DriverDesc")
                            if "virtual" not in drv.lower() and "remote" not in drv.lower():
                                winreg.SetValueEx(sk, "DriverDesc", 0, winreg.REG_SZ, gpu_target)
                                winreg.SetValueEx(sk, "HardwareInformation.ChipType", 0, winreg.REG_SZ, gpu_target)
                                winreg.SetValueEx(sk, "HardwareInformation.AdapterString", 0, winreg.REG_SZ, gpu_target)
                                winreg.SetValueEx(sk, "HardwareInformation.qwMemorySize", 0, winreg.REG_QWORD, vram_bytes)
                                winreg.SetValueEx(sk, "HardwareInformation.MemorySize", 0, winreg.REG_DWORD, vram_dword)
                    except Exception:
                        pass
    except Exception as e:
        errors.append(f"Class显示适配器修改提示: {e}")

    # 6. 修改 GPU Enum 注册表项
    if gpu_pnp:
        enum_gpu_path = r"SYSTEM\CurrentControlSet\Enum\\" + gpu_pnp
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, enum_gpu_path, 0, winreg.KEY_WRITE) as k:
                winreg.SetValueEx(k, "DeviceDesc", 0, winreg.REG_SZ, gpu_target)
                winreg.SetValueEx(k, "FriendlyName", 0, winreg.REG_SZ, gpu_target)
        except Exception as e:
            errors.append(f"显卡Enum修改失败: {e}")

    # 7. 修改 nvlddmkm 服务
    nv_video = r"SYSTEM\CurrentControlSet\Services\nvlddmkm\Video"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, nv_video, 0, winreg.KEY_READ | winreg.KEY_WRITE) as nvk:
            winreg.SetValueEx(nvk, "DeviceDesc", 0, winreg.REG_SZ, gpu_target)
    except Exception:
        pass

    # 8. 修改主板 BIOS 注册表
    if board_vendor and board_product:
        try:
            bios_base = r"HARDWARE\DESCRIPTION\System\BIOS"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, bios_base, 0, winreg.KEY_WRITE) as bk:
                winreg.SetValueEx(bk, "BaseBoardManufacturer", 0, winreg.REG_SZ, board_vendor)
                winreg.SetValueEx(bk, "BaseBoardProduct", 0, winreg.REG_SZ, board_product)
                winreg.SetValueEx(bk, "SystemManufacturer", 0, winreg.REG_SZ, board_vendor)
                winreg.SetValueEx(bk, "SystemProductName", 0, winreg.REG_SZ, board_product)
        except Exception as e:
            errors.append(f"主板BIOS修改提示: {e}")

    # 9. 修改硬盘 FriendlyName (设备管理器与磁盘列表)
    if disk_model:
        try:
            scsi_base = r"SYSTEM\CurrentControlSet\Enum\SCSI"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, scsi_base) as sk:
                for i in range(winreg.QueryInfoKey(sk)[0]):
                    sub1 = winreg.EnumKey(sk, i)
                    sub1_path = f"{scsi_base}\\{sub1}"
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub1_path) as s1k:
                            for j in range(winreg.QueryInfoKey(s1k)[0]):
                                sub2 = winreg.EnumKey(s1k, j)
                                inst_path = f"{sub1_path}\\{sub2}"
                                try:
                                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, inst_path, 0, winreg.KEY_READ | winreg.KEY_WRITE) as dev_k:
                                        fn, _ = winreg.QueryValueEx(dev_k, "FriendlyName")
                                        if "virtual" not in fn.lower():
                                            winreg.SetValueEx(dev_k, "FriendlyName", 0, winreg.REG_SZ, disk_model)
                                except Exception:
                                    pass
                    except Exception:
                        pass
        except Exception as e:
            errors.append(f"硬盘名称修改提示: {e}")

    # 10. 小黑盒加速器全硬件拦截 Hook 注入
    apply_xiaoheihe_hook()

    # 11. 开机防还原自启计划任务配置
    task_name = "CPU_Model_Fix_On_Startup"
    if enable_startup:
        temp_dir = os.environ.get("TEMP", r"C:\Windows\Temp")
        bat_file = os.path.join(temp_dir, "cpu_fix_startup.bat")
        vbs_file = os.path.join(temp_dir, "cpu_fix_launcher.vbs")

        with open(bat_file, "w", encoding="gbk", errors="ignore") as f:
            f.write("@echo off\n")
            for c_idx in range(64):
                f.write(f'reg add "HKLM\\HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\{c_idx}" /v "ProcessorNameString" /t REG_SZ /d "{cpu_target}" /f >nul 2>&1\n')
            f.write(f'reg add "HKLM\\SOFTWARE\\Microsoft\\DirectX" /v "MaxDedicatedVideoMemory" /t REG_QWORD /d "{vram_bytes}" /f >nul 2>&1\n')
            if board_vendor and board_product:
                f.write(f'reg add "HKLM\\HARDWARE\\DESCRIPTION\\System\\BIOS" /v "BaseBoardManufacturer" /t REG_SZ /d "{board_vendor}" /f >nul 2>&1\n')
                f.write(f'reg add "HKLM\\HARDWARE\\DESCRIPTION\\System\\BIOS" /v "BaseBoardProduct" /t REG_SZ /d "{board_product}" /f >nul 2>&1\n')
                f.write(f'reg add "HKLM\\HARDWARE\\DESCRIPTION\\System\\BIOS" /v "SystemManufacturer" /t REG_SZ /d "{board_vendor}" /f >nul 2>&1\n')
                f.write(f'reg add "HKLM\\HARDWARE\\DESCRIPTION\\System\\BIOS" /v "SystemProductName" /t REG_SZ /d "{board_product}" /f >nul 2>&1\n')
            if disk_pnp:
                f.write(f'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Enum\\{disk_pnp}" /v "FriendlyName" /t REG_SZ /d "{disk_model}" /f >nul 2>&1\n')

        with open(vbs_file, "w", encoding="ascii") as f:
            f.write('Set WshShell = CreateObject("WScript.Shell")\n')
            f.write(f'WshShell.Run Chr(34) & "{bat_file}" & Chr(34), 0, False\n')
            f.write('Set WshShell = Nothing\n')

        subprocess.run(
            ["schtasks", "/create", "/tn", task_name, "/tr", f'wscript.exe "{vbs_file}"', "/sc", "onlogon", "/rl", "highest", "/delay", "0000:05", "/f"],
            capture_output=True
        )
    else:
        subprocess.run(["schtasks", "/delete", "/tn", task_name, "/f"], capture_output=True)

    return errors


def restore_hardware_modifications():
    """一键将 CPU、GPU、显存、主板、硬盘及所有底层注册表完全恢复为真实官方状态"""
    real_cpu = DEFAULT_REAL_CPU
    if os.path.exists(CPU_BACKUP_FILE):
        try:
            with open(CPU_BACKUP_FILE, "r", encoding="utf-8", errors="ignore") as f:
                real_cpu = f.read().strip()
        except Exception:
            pass

    real_gpu = DEFAULT_REAL_GPU
    real_gpu_desc = DEFAULT_REAL_GPU_DESC
    if os.path.exists(GPU_BACKUP_FILE):
        try:
            with open(GPU_BACKUP_FILE, "r", encoding="utf-8", errors="ignore") as f:
                real_gpu_desc = f.read().strip()
                if ";" in real_gpu_desc:
                    real_gpu = real_gpu_desc.split(";")[-1].strip()
        except Exception:
            pass

    gpu_pnp = ""
    if os.path.exists(GPU_PATH_BACKUP_FILE):
        try:
            with open(GPU_PATH_BACKUP_FILE, "r", encoding="utf-8", errors="ignore") as f:
                gpu_pnp = f.read().strip()
        except Exception:
            pass

    real_board_vendor = DEFAULT_REAL_BOARD_VENDOR
    if os.path.exists(BOARD_VENDOR_BACKUP_FILE):
        try:
            with open(BOARD_VENDOR_BACKUP_FILE, "r", encoding="utf-8", errors="ignore") as f:
                real_board_vendor = f.read().strip()
        except Exception:
            pass

    real_board_product = DEFAULT_REAL_BOARD_PRODUCT
    if os.path.exists(BOARD_PRODUCT_BACKUP_FILE):
        try:
            with open(BOARD_PRODUCT_BACKUP_FILE, "r", encoding="utf-8", errors="ignore") as f:
                real_board_product = f.read().strip()
        except Exception:
            pass

    real_disk = DEFAULT_REAL_DISK_MODEL
    if os.path.exists(DISK_BACKUP_FILE):
        try:
            with open(DISK_BACKUP_FILE, "r", encoding="utf-8", errors="ignore") as f:
                real_disk = f.read().strip()
        except Exception:
            pass

    disk_pnp = DEFAULT_REAL_DISK_PATH
    if os.path.exists(DISK_PATH_BACKUP_FILE):
        try:
            with open(DISK_PATH_BACKUP_FILE, "r", encoding="utf-8", errors="ignore") as f:
                disk_pnp = f.read().strip()
        except Exception:
            pass

    # 1. 还原 CPU
    try:
        cpu_base = r"HARDWARE\DESCRIPTION\System\CentralProcessor"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, cpu_base) as k:
            num_cores = winreg.QueryInfoKey(k)[0]
            for i in range(num_cores):
                sub_name = winreg.EnumKey(k, i)
                if sub_name.isdigit():
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{cpu_base}\\{sub_name}", 0, winreg.KEY_WRITE) as sk:
                        winreg.SetValueEx(sk, "ProcessorNameString", 0, winreg.REG_SZ, real_cpu)
    except Exception:
        pass

    # 2. 还原 DirectX
    try:
        dx_base = r"SOFTWARE\Microsoft\DirectX"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, dx_base, 0, winreg.KEY_READ | winreg.KEY_WRITE) as dxk:
            winreg.SetValueEx(dxk, "MaxDedicatedVideoMemory", 0, winreg.REG_QWORD, DEFAULT_REAL_VRAM_BYTES)
            for i in range(winreg.QueryInfoKey(dxk)[0]):
                guid = winreg.EnumKey(dxk, i)
                if guid.startswith("{") and guid.endswith("}"):
                    sub_path = f"{dx_base}\\{guid}"
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub_path, 0, winreg.KEY_READ | winreg.KEY_WRITE) as sk:
                            desc, _ = winreg.QueryValueEx(sk, "Description")
                            if "basic" not in desc.lower():
                                winreg.SetValueEx(sk, "Description", 0, winreg.REG_SZ, real_gpu)
                                winreg.SetValueEx(sk, "DedicatedVideoMemory", 0, winreg.REG_QWORD, DEFAULT_REAL_VRAM_BYTES)
                    except Exception:
                        pass
    except Exception:
        pass

    # 3. 还原 Control\\Video
    v_base = r"SYSTEM\CurrentControlSet\Control\Video"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, v_base, 0, winreg.KEY_READ) as vk:
            n_sub = winreg.QueryInfoKey(vk)[0]
            for idx in range(n_sub):
                guid = winreg.EnumKey(vk, idx)
                if guid.startswith("{") and guid.endswith("}"):
                    guid_path = f"{v_base}\\{guid}"
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{guid_path}\\Video", 0, winreg.KEY_READ | winreg.KEY_WRITE) as vdk:
                            cur_desc, _ = winreg.QueryValueEx(vdk, "DeviceDesc")
                            if "virtual" not in cur_desc.lower() and "remote" not in cur_desc.lower():
                                winreg.SetValueEx(vdk, "DeviceDesc", 0, winreg.REG_SZ, real_gpu_desc)
                    except Exception:
                        pass

                    for out_i in range(8):
                        out_path = f"{guid_path}\\{out_i:04d}"
                        try:
                            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, out_path, 0, winreg.KEY_READ | winreg.KEY_WRITE) as ok:
                                chip, _ = winreg.QueryValueEx(ok, "HardwareInformation.ChipType")
                                if "virtual" not in str(chip).lower() and "remote" not in str(chip).lower():
                                    winreg.SetValueEx(ok, "HardwareInformation.ChipType", 0, winreg.REG_SZ, real_gpu)
                                    winreg.SetValueEx(ok, "HardwareInformation.AdapterString", 0, winreg.REG_SZ, real_gpu)
                                    winreg.SetValueEx(ok, "HardwareInformation.qwMemorySize", 0, winreg.REG_QWORD, DEFAULT_REAL_VRAM_BYTES)
                                    winreg.SetValueEx(ok, "HardwareInformation.MemorySize", 0, winreg.REG_DWORD, 4293918720)
                                    winreg.SetValueEx(ok, "DriverDesc", 0, winreg.REG_SZ, real_gpu)
                        except Exception:
                            pass
    except Exception:
        pass

    # 4. 还原 Class
    class_base = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, class_base, 0, winreg.KEY_READ) as ck:
            for idx in range(winreg.QueryInfoKey(ck)[0]):
                sub = winreg.EnumKey(ck, idx)
                if sub.isdigit() and len(sub) == 4:
                    sub_path = f"{class_base}\\{sub}"
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub_path, 0, winreg.KEY_READ | winreg.KEY_WRITE) as sk:
                            drv, _ = winreg.QueryValueEx(sk, "DriverDesc")
                            if "virtual" not in drv.lower() and "remote" not in drv.lower():
                                winreg.SetValueEx(sk, "DriverDesc", 0, winreg.REG_SZ, real_gpu)
                                winreg.SetValueEx(sk, "HardwareInformation.ChipType", 0, winreg.REG_SZ, real_gpu)
                                winreg.SetValueEx(sk, "HardwareInformation.AdapterString", 0, winreg.REG_SZ, real_gpu)
                                winreg.SetValueEx(sk, "HardwareInformation.qwMemorySize", 0, winreg.REG_QWORD, DEFAULT_REAL_VRAM_BYTES)
                                winreg.SetValueEx(sk, "HardwareInformation.MemorySize", 0, winreg.REG_DWORD, 4293918720)
                    except Exception:
                        pass
    except Exception:
        pass

    # 5. 还原 Enum
    if gpu_pnp:
        enum_gpu_path = r"SYSTEM\CurrentControlSet\Enum\\" + gpu_pnp
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, enum_gpu_path, 0, winreg.KEY_WRITE) as k:
                winreg.SetValueEx(k, "DeviceDesc", 0, winreg.REG_SZ, real_gpu_desc)
                winreg.SetValueEx(k, "FriendlyName", 0, winreg.REG_SZ, real_gpu)
        except Exception:
            pass

    # 6. 还原 nvlddmkm
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services\nvlddmkm\Video", 0, winreg.KEY_READ | winreg.KEY_WRITE) as nvk:
            winreg.SetValueEx(nvk, "DeviceDesc", 0, winreg.REG_SZ, real_gpu_desc)
    except Exception:
        pass

    # 7. 还原主板 BIOS
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\BIOS", 0, winreg.KEY_WRITE) as bk:
            winreg.SetValueEx(bk, "BaseBoardManufacturer", 0, winreg.REG_SZ, real_board_vendor)
            winreg.SetValueEx(bk, "BaseBoardProduct", 0, winreg.REG_SZ, real_board_product)
            winreg.SetValueEx(bk, "SystemManufacturer", 0, winreg.REG_SZ, real_board_vendor)
            winreg.SetValueEx(bk, "SystemProductName", 0, winreg.REG_SZ, real_board_product)
    except Exception:
        pass

    # 8. 还原硬盘 FriendlyName
    if disk_pnp:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"SYSTEM\\CurrentControlSet\\Enum\\{disk_pnp}", 0, winreg.KEY_WRITE) as dk:
                winreg.SetValueEx(dk, "FriendlyName", 0, winreg.REG_SZ, real_disk)
        except Exception:
            pass

    # 9. 清理自启任务
    subprocess.run(["schtasks", "/delete", "/tn", "CPU_Model_Fix_On_Startup", "/f"], capture_output=True)
    if os.path.exists(CPU_CONFIG_FILE):
        try:
            os.remove(CPU_CONFIG_FILE)
        except Exception:
            pass

    # 10. 还原小黑盒加速器入口
    restore_xiaoheihe_hook()


class CPUGPUApp:
    def __init__(self, root):
        self.root = root
        self.root.title("电脑全套硬件配置自定义管理工具 (旗舰增强版)")
        self.root.geometry("860x780")
        self.root.minsize(820, 720)

        # 加载配置
        self.config = load_config()

        # 初始化外观与硬件探测
        self.setup_styles()
        self.detect_hardware()
        self.setup_ui()

    def setup_styles(self):
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        self.root.configure(bg="#f8fafc")

        self.style.configure(".", font=("Microsoft YaHei", 9), background="#f8fafc")
        self.style.configure("Header.TLabel", font=("Microsoft YaHei", 15, "bold"), foreground="#0f172a", background="#f8fafc")
        self.style.configure("SubHeader.TLabel", font=("Microsoft YaHei", 9), foreground="#64748b", background="#f8fafc")
        self.style.configure("Section.TLabel", font=("Microsoft YaHei", 10, "bold"), foreground="#1e293b", background="#ffffff")
        self.style.configure("InfoKey.TLabel", font=("Microsoft YaHei", 9), foreground="#64748b", background="#ffffff")
        self.style.configure("InfoVal.TLabel", font=("Microsoft YaHei", 9, "bold"), foreground="#0f172a", background="#ffffff")
        self.style.configure("Card.TFrame", background="#ffffff", relief="flat")

        # 选项卡样式
        self.style.configure("TNotebook", background="#f8fafc", borderwidth=0)
        self.style.configure("TNotebook.Tab", font=("Microsoft YaHei", 10), padding=(16, 8), background="#e2e8f0", foreground="#334155")
        self.style.map("TNotebook.Tab", background=[("selected", "#ffffff")], foreground=[("selected", "#2563eb")])

        # 按钮样式
        self.style.configure("Primary.TButton", font=("Microsoft YaHei", 10, "bold"), background="#2563eb", foreground="#ffffff", borderwidth=0, padding=(16, 10))
        self.style.map("Primary.TButton", background=[("active", "#1d4ed8"), ("pressed", "#1e40af")])

        self.style.configure("Danger.TButton", font=("Microsoft YaHei", 9), background="#ef4444", foreground="#ffffff", borderwidth=0, padding=(12, 8))
        self.style.map("Danger.TButton", background=[("active", "#dc2626"), ("pressed", "#b91c1c")])

        self.style.configure("Secondary.TButton", font=("Microsoft YaHei", 9), background="#e2e8f0", foreground="#334155", borderwidth=0, padding=(10, 6))
        self.style.map("Secondary.TButton", background=[("active", "#cbd5e1"), ("pressed", "#94a3b8")])

    def detect_hardware(self):
        # 检测 CPU
        self.current_cpu = "未知 CPU"
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
                self.current_cpu = winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()
        except Exception:
            pass

        # 检测 GPU
        self.current_gpu = "未知 GPU"
        try:
            cls_base = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, cls_base) as ck:
                for i in range(winreg.QueryInfoKey(ck)[0]):
                    sub = winreg.EnumKey(ck, i)
                    if sub.isdigit() and len(sub) == 4:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{cls_base}\\{sub}") as sk:
                            drv = winreg.QueryValueEx(sk, "DriverDesc")[0]
                            if drv and "virtual" not in drv.lower() and "remote" not in drv.lower():
                                self.current_gpu = drv.strip()
                                break
        except Exception:
            pass

        # 检测主板
        self.current_board = "未知主板"
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\BIOS") as k:
                bv = winreg.QueryValueEx(k, "BaseBoardManufacturer")[0].strip()
                bp = winreg.QueryValueEx(k, "BaseBoardProduct")[0].strip()
                self.current_board = f"{bv} {bp}".strip()
        except Exception:
            pass

        # 检测硬盘
        self.current_disk = "未知硬盘"
        try:
            disk_pnp = self.config.get("custom_target", {}).get("target_disk_instance_path", DEFAULT_REAL_DISK_PATH)
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"SYSTEM\\CurrentControlSet\\Enum\\{disk_pnp}") as k:
                self.current_disk = winreg.QueryValueEx(k, "FriendlyName")[0].strip()
        except Exception:
            self.current_disk = DEFAULT_REAL_DISK_MODEL

        # 真实出厂备份
        self.real_cpu = DEFAULT_REAL_CPU
        if os.path.exists(CPU_BACKUP_FILE):
            try:
                with open(CPU_BACKUP_FILE, "r", encoding="utf-8", errors="ignore") as f:
                    self.real_cpu = f.read().strip()
            except Exception:
                pass

        # 显卡 PNP
        self.gpu_pnp = self.config.get("custom_target", {}).get("target_gpu_instance_path", "")
        if not self.gpu_pnp and os.path.exists(GPU_PATH_BACKUP_FILE):
            try:
                with open(GPU_PATH_BACKUP_FILE, "r", encoding="utf-8", errors="ignore") as f:
                    self.gpu_pnp = f.read().strip()
            except Exception:
                pass

        # 硬盘 PNP
        self.disk_pnp = self.config.get("custom_target", {}).get("target_disk_instance_path", DEFAULT_REAL_DISK_PATH)
        if os.path.exists(DISK_PATH_BACKUP_FILE):
            try:
                with open(DISK_PATH_BACKUP_FILE, "r", encoding="utf-8", errors="ignore") as f:
                    self.disk_pnp = f.read().strip()
            except Exception:
                pass

        # 小黑盒适配与Hook状态检测
        self.xiaoheihe_installed = False
        self.xiaoheihe_hooked = False
        idx_paths = get_xiaoheihe_index_paths()
        if idx_paths:
            self.xiaoheihe_installed = True
            for p in idx_paths:
                try:
                    with open(p, "r", encoding="utf-8", errors="ignore") as f:
                        if "Xiaoheihe Hardware Detection Hook" in f.read():
                            self.xiaoheihe_hooked = True
                            break
                except Exception:
                    pass

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="16 10 16 10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. 头部标题
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 6))

        title = ttk.Label(header_frame, text="⚡ 电脑全套硬件配置自定义管理工具 (旗舰增强版)", style="Header.TLabel")
        title.pack(anchor=tk.W)

        subtitle = ttk.Label(
            header_frame,
            text="支持 CPU、显卡/显存、主板、内存及硬盘全套硬件自定义伪装与穿透，覆盖任务管理器/小黑盒/DirectX/设备管理器",
            style="SubHeader.TLabel"
        )
        subtitle.pack(anchor=tk.W, pady=(2, 4))

        # 2. 权限状态栏
        admin_frame = tk.Frame(main_frame, bg="#dcfce7" if is_admin() else "#fef3c7", padx=12, pady=5)
        admin_frame.pack(fill=tk.X, pady=(0, 8))

        admin_txt = "✅ 当前已获得系统管理员权限 (Administrator)，配置可直接深度生效并写入系统底层及小黑盒" if is_admin() else "⚠️ 当前为普通用户权限。点击「一键应用」将自动弹出 Windows 授权提权窗口"
        admin_fg = "#15803d" if is_admin() else "#b45309"
        lbl_admin = tk.Label(admin_frame, text=admin_txt, fg=admin_fg, bg=admin_frame["bg"], font=("Microsoft YaHei", 9, "bold"))
        lbl_admin.pack(anchor=tk.W)

        # 3. 硬件状态总览卡片
        card_curr = ttk.Frame(main_frame, style="Card.TFrame", padding="12 8 12 8")
        card_curr.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(card_curr, text="🖥️ 当前系统检测硬件状态", style="Section.TLabel").grid(row=0, column=0, columnspan=4, sticky=tk.W, pady=(0, 4))

        ttk.Label(card_curr, text="CPU 显示:", style="InfoKey.TLabel").grid(row=1, column=0, sticky=tk.W, padx=(0, 6), pady=2)
        self.lbl_cpu_display = ttk.Label(card_curr, text=self.current_cpu, style="InfoVal.TLabel", foreground="#2563eb")
        self.lbl_cpu_display.grid(row=1, column=1, sticky=tk.W, pady=2, padx=(0, 20))

        ttk.Label(card_curr, text="GPU 显示:", style="InfoKey.TLabel").grid(row=1, column=2, sticky=tk.W, padx=(0, 6), pady=2)
        self.lbl_gpu_display = ttk.Label(card_curr, text=self.current_gpu, style="InfoVal.TLabel", foreground="#16a34a")
        self.lbl_gpu_display.grid(row=1, column=3, sticky=tk.W, pady=2)

        ttk.Label(card_curr, text="主板 显示:", style="InfoKey.TLabel").grid(row=2, column=0, sticky=tk.W, padx=(0, 6), pady=2)
        self.lbl_board_display = ttk.Label(card_curr, text=self.current_board, style="InfoVal.TLabel", foreground="#7c3aed")
        self.lbl_board_display.grid(row=2, column=1, sticky=tk.W, pady=2, padx=(0, 20))

        ttk.Label(card_curr, text="硬盘 显示:", style="InfoKey.TLabel").grid(row=2, column=2, sticky=tk.W, padx=(0, 6), pady=2)
        self.lbl_disk_display = ttk.Label(card_curr, text=self.current_disk, style="InfoVal.TLabel", foreground="#0891b2")
        self.lbl_disk_display.grid(row=2, column=3, sticky=tk.W, pady=2)

        ttk.Label(card_curr, text="小黑盒状态:", style="InfoKey.TLabel").grid(row=3, column=0, sticky=tk.W, padx=(0, 6), pady=2)
        x_status = "✅ 全硬件拦截器已激活 (小黑盒检测将同步呈现全部目标硬件)" if self.xiaoheihe_hooked else ("⚡ 已适配 (点击「一键应用」自动注入)" if self.xiaoheihe_installed else "未检测到小黑盒安装")
        x_color = "#16a34a" if self.xiaoheihe_hooked else ("#2563eb" if self.xiaoheihe_installed else "#6b7280")
        self.lbl_xiaoheihe = ttk.Label(card_curr, text=x_status, style="InfoVal.TLabel", foreground=x_color)
        self.lbl_xiaoheihe.grid(row=3, column=1, columnspan=3, sticky=tk.W, pady=2)

        # 4. 配置选项卡 Notebook
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        # Tab 1: 核心计算硬件 (CPU & GPU)
        tab_core = ttk.Frame(self.notebook, style="Card.TFrame", padding="14 10 14 10")
        self.notebook.add(tab_core, text=" 🖥️ 核心硬件 (CPU / 显卡 / 显存) ")

        # CPU 设置
        ttk.Label(tab_core, text="【处理器 CPU 配置】", style="Section.TLabel").grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 4))
        ttk.Label(tab_core, text="目标 CPU 型号:", style="InfoKey.TLabel").grid(row=1, column=0, sticky=tk.W, pady=4)
        self.cpu_var = tk.StringVar(value=self.config.get("custom_target", {}).get("cpu_model", "AMD Ryzen 9 9950X3D2 16-Core Processor"))
        cpu_presets = self.config.get("presets", {}).get("cpu", [])
        self.cpu_combo = ttk.Combobox(tab_core, textvariable=self.cpu_var, values=cpu_presets, width=54)
        self.cpu_combo.grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=4)

        # GPU 设置
        ttk.Label(tab_core, text="【图形显卡 GPU 与显存配置】", style="Section.TLabel").grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(12, 4))
        ttk.Label(tab_core, text="目标 GPU 型号:", style="InfoKey.TLabel").grid(row=3, column=0, sticky=tk.W, pady=4)
        self.gpu_var = tk.StringVar(value=self.config.get("custom_target", {}).get("gpu_model", "NVIDIA GeForce RTX 5090"))
        gpu_presets = self.config.get("presets", {}).get("gpu", [])
        self.gpu_combo = ttk.Combobox(tab_core, textvariable=self.gpu_var, values=gpu_presets, width=54)
        self.gpu_combo.grid(row=3, column=1, sticky=tk.W, padx=(10, 0), pady=4)
        self.gpu_combo.bind("<<ComboboxSelected>>", self.on_gpu_selected)

        # 显存 VRAM
        ttk.Label(tab_core, text="专用显存 (VRAM):", style="InfoKey.TLabel").grid(row=4, column=0, sticky=tk.W, pady=4)
        saved_vram = self.config.get("custom_target", {}).get("gpu_vram_gb", 32)
        self.vram_var = tk.StringVar(value=f"{saved_vram} GB")
        vram_presets = self.config.get("presets", {}).get("vram", ["48 GB", "32 GB", "24 GB", "20 GB", "16 GB", "12 GB (保持原始)", "8 GB"])
        self.vram_combo = ttk.Combobox(tab_core, textvariable=self.vram_var, values=vram_presets, width=24)
        self.vram_combo.grid(row=4, column=1, sticky=tk.W, padx=(10, 0), pady=4)

        # 显卡设备路径
        ttk.Label(tab_core, text="显卡设备实例路径:", style="InfoKey.TLabel").grid(row=5, column=0, sticky=tk.W, pady=4)
        self.pnp_var = tk.StringVar(value=self.gpu_pnp)
        pnp_entry = ttk.Entry(tab_core, textvariable=self.pnp_var, width=56)
        pnp_entry.grid(row=5, column=1, sticky=tk.W, padx=(10, 0), pady=4)

        # Tab 2: 外围硬件 (主板、内存、硬盘)
        tab_peripheral = ttk.Frame(self.notebook, style="Card.TFrame", padding="14 10 14 10")
        self.notebook.add(tab_peripheral, text=" 🖲️ 外围硬件 (主板 / 内存 / 硬盘) ")

        # 主板配置
        ttk.Label(tab_peripheral, text="【主板 Motherboard 配置】", style="Section.TLabel").grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 4))

        ttk.Label(tab_peripheral, text="预设主板型号:", style="InfoKey.TLabel").grid(row=1, column=0, sticky=tk.W, pady=4)
        self.board_presets = self.config.get("presets", {}).get("motherboard", [])
        board_preset_names = [f"{b.get('vendor', '')} {b.get('product', '')}".strip() for b in self.board_presets]
        self.board_preset_var = tk.StringVar(value="ASUSTeK COMPUTER INC. ROG CROSSHAIR X870E HERO")
        self.board_preset_combo = ttk.Combobox(tab_peripheral, textvariable=self.board_preset_var, values=board_preset_names, width=54)
        self.board_preset_combo.grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=4)
        self.board_preset_combo.bind("<<ComboboxSelected>>", self.on_board_selected)

        ttk.Label(tab_peripheral, text="主板厂商 (Vendor):", style="InfoKey.TLabel").grid(row=2, column=0, sticky=tk.W, pady=4)
        self.board_vendor_var = tk.StringVar(value=self.config.get("custom_target", {}).get("motherboard_vendor", "ASUSTeK COMPUTER INC."))
        ttk.Entry(tab_peripheral, textvariable=self.board_vendor_var, width=56).grid(row=2, column=1, sticky=tk.W, padx=(10, 0), pady=4)

        ttk.Label(tab_peripheral, text="主板型号 (Product):", style="InfoKey.TLabel").grid(row=3, column=0, sticky=tk.W, pady=4)
        self.board_product_var = tk.StringVar(value=self.config.get("custom_target", {}).get("motherboard_product", "ROG CROSSHAIR X870E HERO"))
        ttk.Entry(tab_peripheral, textvariable=self.board_product_var, width=56).grid(row=3, column=1, sticky=tk.W, padx=(10, 0), pady=4)

        # 内存配置
        ttk.Label(tab_peripheral, text="【内存 RAM 配置】", style="Section.TLabel").grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=(10, 4))

        mem_box = ttk.Frame(tab_peripheral, style="Card.TFrame")
        mem_box.grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=2)

        ttk.Label(mem_box, text="内存品牌:", style="InfoKey.TLabel").pack(side=tk.LEFT)
        self.mem_vendor_var = tk.StringVar(value=self.config.get("custom_target", {}).get("memory_vendor", "Corsair"))
        mem_vendors = self.config.get("presets", {}).get("memory_vendor", ["Corsair", "G.Skill", "Kingston", "Asgard"])
        ttk.Combobox(mem_box, textvariable=self.mem_vendor_var, values=mem_vendors, width=12).pack(side=tk.LEFT, padx=(6, 16))

        ttk.Label(mem_box, text="容量:", style="InfoKey.TLabel").pack(side=tk.LEFT)
        self.mem_size_var = tk.StringVar(value=f"{self.config.get('custom_target', {}).get('memory_size_gb', 64)} GB")
        mem_sizes = self.config.get("presets", {}).get("memory_size", ["128 GB", "96 GB", "64 GB", "32 GB", "16 GB"])
        ttk.Combobox(mem_box, textvariable=self.mem_size_var, values=mem_sizes, width=14).pack(side=tk.LEFT, padx=(6, 16))

        ttk.Label(mem_box, text="频率:", style="InfoKey.TLabel").pack(side=tk.LEFT)
        self.mem_clock_var = tk.StringVar(value=f"{self.config.get('custom_target', {}).get('memory_clock_mhz', 7200)} MHz")
        mem_clocks = self.config.get("presets", {}).get("memory_clock", ["8000 MHz", "7200 MHz", "6400 MHz", "6000 MHz"])
        ttk.Combobox(mem_box, textvariable=self.mem_clock_var, values=mem_clocks, width=12).pack(side=tk.LEFT, padx=(6, 0))

        # 硬盘配置
        ttk.Label(tab_peripheral, text="【硬盘 SSD 配置】", style="Section.TLabel").grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=(10, 4))
        ttk.Label(tab_peripheral, text="目标硬盘型号:", style="InfoKey.TLabel").grid(row=7, column=0, sticky=tk.W, pady=4)
        self.disk_var = tk.StringVar(value=self.config.get("custom_target", {}).get("disk_model", "Samsung SSD 990 PRO 4TB"))
        disk_presets = self.config.get("presets", {}).get("disk", [])
        self.disk_combo = ttk.Combobox(tab_peripheral, textvariable=self.disk_var, values=disk_presets, width=54)
        self.disk_combo.grid(row=7, column=1, sticky=tk.W, padx=(10, 0), pady=4)

        # Tab 3: 高级选项与开机防还原
        tab_adv = ttk.Frame(self.notebook, style="Card.TFrame", padding="14 10 14 10")
        self.notebook.add(tab_adv, text=" ⚙️ 高级与开机防还原 ")

        self.startup_var = tk.BooleanVar(value=self.config.get("custom_target", {}).get("enable_startup_fix", True))
        chk_startup = ttk.Checkbutton(
            tab_adv,
            text="启用开机静默防还原机制 (通过 Windows 高权限计划任务自动持久化 CPU/主板/显存配置)",
            variable=self.startup_var
        )
        chk_startup.pack(anchor=tk.W, pady=6)

        ttk.Label(tab_adv, text="【出厂硬件原始备份参考】", style="Section.TLabel").pack(anchor=tk.W, pady=(10, 4))
        ttk.Label(tab_adv, text=f"• 原始 CPU: {self.real_cpu}", style="InfoKey.TLabel").pack(anchor=tk.W, pady=2)
        ttk.Label(tab_adv, text=f"• 原始 显卡: {DEFAULT_REAL_GPU} (12 GB 显存)", style="InfoKey.TLabel").pack(anchor=tk.W, pady=2)
        ttk.Label(tab_adv, text=f"• 原始 主板: {DEFAULT_REAL_BOARD_VENDOR} {DEFAULT_REAL_BOARD_PRODUCT}", style="InfoKey.TLabel").pack(anchor=tk.W, pady=2)
        ttk.Label(tab_adv, text=f"• 原始 硬盘: {DEFAULT_REAL_DISK_MODEL}", style="InfoKey.TLabel").pack(anchor=tk.W, pady=2)

        # 5. 操作按钮栏
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(6, 4))

        btn_apply = ttk.Button(btn_frame, text="🚀 一键深度应用全套硬件修改", style="Primary.TButton", command=self.apply_changes)
        btn_apply.pack(side=tk.LEFT, padx=(0, 10))

        btn_restore = ttk.Button(btn_frame, text="🔄 一键还原官方出厂硬件", style="Danger.TButton", command=self.restore_official)
        btn_restore.pack(side=tk.LEFT, padx=(0, 10))

        btn_save = ttk.Button(btn_frame, text="💾 仅保存设置", style="Secondary.TButton", command=self.save_only)
        btn_save.pack(side=tk.LEFT, padx=(0, 10))

        btn_restart_tm = ttk.Button(btn_frame, text="🔄 重启任务管理器", style="Secondary.TButton", command=self.restart_taskmgr)
        btn_restart_tm.pack(side=tk.RIGHT)

        # 6. 底部提示
        tip_frame = tk.Frame(main_frame, bg="#eff6ff", padx=10, pady=5)
        tip_frame.pack(fill=tk.X, pady=(4, 0))

        tip_title = tk.Label(tip_frame, text="💡 生效提醒与指引：", bg="#eff6ff", fg="#1e40af", font=("Microsoft YaHei", 8, "bold"))
        tip_title.pack(anchor=tk.W)

        tip_desc = tk.Label(
            tip_frame,
            text="1. 本工具已全面打通 CPU、显卡/显存、主板、内存及硬盘；\n"
                 "2. 应用修改后，关闭并重新打开【任务管理器】可看到最新显存与硬件；\n"
                 "3. 小黑盒加速器若已在后台运行，请在右下角系统托盘图标【右键彻底退出】后再重新打开，即可看到全套定制硬件！",
            bg="#eff6ff", fg="#1e3a8a", justify=tk.LEFT, font=("Microsoft YaHei", 8)
        )
        tip_desc.pack(anchor=tk.W, pady=(1, 0))

    def on_gpu_selected(self, event=None):
        val = self.gpu_var.get()
        if "5090" in val:
            self.vram_var.set("24 GB" if "D" in val else "32 GB")
        elif "5080" in val or "5070 Ti" in val or "4080" in val or "7900" in val:
            self.vram_var.set("16 GB")
        elif "6000" in val:
            self.vram_var.set("48 GB")
        elif "H100" in val:
            self.vram_var.set("80 GB")

    def on_board_selected(self, event=None):
        sel = self.board_preset_var.get().strip()
        for b in self.board_presets:
            fullname = f"{b.get('vendor', '')} {b.get('product', '')}".strip()
            if fullname == sel:
                self.board_vendor_var.set(b.get("vendor", ""))
                self.board_product_var.set(b.get("product", ""))
                break

    def parse_vram_gb(self):
        val_str = self.vram_var.get()
        digits = "".join([c for c in val_str.split()[0] if c.isdigit()])
        try:
            return int(digits)
        except Exception:
            return 24

    def parse_mem_gb(self):
        val_str = self.mem_size_var.get()
        digits = "".join([c for c in val_str.split()[0] if c.isdigit()])
        try:
            return int(digits)
        except Exception:
            return 64

    def parse_mem_clock(self):
        val_str = self.mem_clock_var.get()
        digits = "".join([c for c in val_str.split()[0] if c.isdigit()])
        try:
            return int(digits)
        except Exception:
            return 7200

    def refresh_display(self):
        self.detect_hardware()
        self.lbl_cpu_display.config(text=self.current_cpu)
        self.lbl_gpu_display.config(text=self.current_gpu)
        self.lbl_board_display.config(text=self.current_board)
        self.lbl_disk_display.config(text=self.current_disk)

        x_status = "✅ 全硬件拦截器已激活 (小黑盒检测将同步呈现全部目标硬件)" if self.xiaoheihe_hooked else ("⚡ 已适配 (点击「一键应用」自动注入)" if self.xiaoheihe_installed else "未检测到小黑盒安装")
        x_color = "#16a34a" if self.xiaoheihe_hooked else ("#2563eb" if self.xiaoheihe_installed else "#6b7280")
        self.lbl_xiaoheihe.config(text=x_status, foreground=x_color)

    def sync_to_config(self):
        self.config["custom_target"]["cpu_model"] = self.cpu_var.get().strip()
        self.config["custom_target"]["gpu_model"] = self.gpu_var.get().strip()
        self.config["custom_target"]["gpu_vram_gb"] = self.parse_vram_gb()
        self.config["custom_target"]["target_gpu_instance_path"] = self.pnp_var.get().strip()

        self.config["custom_target"]["motherboard_vendor"] = self.board_vendor_var.get().strip()
        self.config["custom_target"]["motherboard_product"] = self.board_product_var.get().strip()

        self.config["custom_target"]["memory_vendor"] = self.mem_vendor_var.get().strip()
        self.config["custom_target"]["memory_size_gb"] = self.parse_mem_gb()
        self.config["custom_target"]["memory_clock_mhz"] = self.parse_mem_clock()

        self.config["custom_target"]["disk_model"] = self.disk_var.get().strip()
        self.config["custom_target"]["target_disk_instance_path"] = self.disk_pnp
        self.config["custom_target"]["enable_startup_fix"] = self.startup_var.get()
        save_config(self.config)

    def save_only(self):
        self.sync_to_config()
        messagebox.showinfo("成功", "已将当前全部硬件设置保存到 config.json！")

    def apply_changes(self):
        self.sync_to_config()
        if not is_admin():
            if not request_admin("--apply"):
                return
            return

        cpu_target = self.cpu_var.get().strip()
        gpu_target = self.gpu_var.get().strip()
        gpu_pnp = self.pnp_var.get().strip()
        vram_gb = self.parse_vram_gb()

        board_vendor = self.board_vendor_var.get().strip()
        board_product = self.board_product_var.get().strip()

        mem_vendor = self.mem_vendor_var.get().strip()
        mem_gb = self.parse_mem_gb()
        mem_clock = self.parse_mem_clock()

        disk_model = self.disk_var.get().strip()
        enable_startup = self.startup_var.get()

        if not cpu_target or not gpu_target:
            messagebox.showwarning("警告", "CPU 型号和 GPU 型号不能为空！")
            return

        errors = apply_hardware_modifications(
            cpu_target,
            gpu_target,
            gpu_pnp,
            vram_gb,
            board_vendor,
            board_product,
            mem_vendor,
            mem_gb,
            mem_clock,
            disk_model,
            self.disk_pnp,
            enable_startup
        )
        self.refresh_display()

        if errors:
            msg = "修改完成，但部分项提示：\n" + "\n".join(errors)
            messagebox.showwarning("应用提示", msg)
        else:
            messagebox.showinfo(
                "全套硬件修改成功",
                f"✅ 全部自定义硬件配置已深度生效！\n\n"
                f"• CPU 目标: {cpu_target}\n"
                f"• GPU 目标: {gpu_target} ({vram_gb} GB 显存)\n"
                f"• 主板目标: {board_vendor} {board_product}\n"
                f"• 内存目标: {mem_vendor} DDR5 {mem_gb}GB {mem_clock}MHz\n"
                f"• 硬盘目标: {disk_model}\n\n"
                f"【生效提醒】：\n"
                f"1. 任务管理器：重新打开任务管理器查看全新显卡、显存与硬盘；\n"
                f"2. 小黑盒：右下角系统托盘彻底退出小黑盒后重新打开即可！"
            )

    def restore_official(self):
        if not is_admin():
            if not request_admin("--restore"):
                return
            return

        restore_hardware_modifications()
        self.refresh_display()
        messagebox.showinfo(
            "还原成功",
            f"✅ 已成功恢复为官方出厂真实硬件信息！\n\n"
            f"• CPU: {self.real_cpu}\n"
            f"• GPU: {DEFAULT_REAL_GPU} (12 GB 显存)\n"
            f"• 主板: {DEFAULT_REAL_BOARD_VENDOR} {DEFAULT_REAL_BOARD_PRODUCT}\n"
            f"• 硬盘: {DEFAULT_REAL_DISK_MODEL}\n\n"
            f"重新打开任务管理器与小黑盒即可恢复官方真实检测。"
        )

    def restart_taskmgr(self):
        subprocess.run(["taskkill", "/F", "/IM", "Taskmgr.exe"], capture_output=True)
        subprocess.Popen(["Taskmgr.exe"])


def main():
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg == "--apply":
            cfg = load_config().get("custom_target", {})
            apply_hardware_modifications(
                cfg.get("cpu_model", DEFAULT_REAL_CPU),
                cfg.get("gpu_model", DEFAULT_REAL_GPU),
                cfg.get("target_gpu_instance_path", ""),
                cfg.get("gpu_vram_gb", 24),
                cfg.get("motherboard_vendor", DEFAULT_REAL_BOARD_VENDOR),
                cfg.get("motherboard_product", DEFAULT_REAL_BOARD_PRODUCT),
                cfg.get("memory_vendor", "Corsair"),
                cfg.get("memory_size_gb", 64),
                cfg.get("memory_clock_mhz", 7200),
                cfg.get("disk_model", DEFAULT_REAL_DISK_MODEL),
                cfg.get("target_disk_instance_path", DEFAULT_REAL_DISK_PATH),
                cfg.get("enable_startup_fix", True)
            )
            sys.exit(0)
        elif arg == "--restore":
            restore_hardware_modifications()
            sys.exit(0)

    root = tk.Tk()
    app = CPUGPUApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
