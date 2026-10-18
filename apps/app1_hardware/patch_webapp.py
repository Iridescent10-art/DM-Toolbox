import os
import sys
import shutil
import json
import winreg
import subprocess

def find_heybox_dir():
    # 1. 命令行参数传入
    if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]):
        return sys.argv[1]

    # 2. 配置文件指定
    for cfg_path in [r"C:\Users\Public\Hardware_Config.json", os.path.join(os.path.dirname(__file__), "config.json")]:
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    p = data.get("custom_heybox_dir") or data.get("custom_target", {}).get("custom_heybox_dir")
                    if p and os.path.isdir(p):
                        return p
            except Exception:
                pass

    # 3. 注册表检测
    uninstall_bases = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hkey, subkey_path in uninstall_bases:
        try:
            with winreg.OpenKey(hkey, subkey_path) as parent_key:
                for i in range(winreg.QueryInfoKey(parent_key)[0]):
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

    # 4. 常见路径回退
    drives = [f"{chr(d)}:" for d in range(ord('C'), ord('Z') + 1) if os.path.exists(f"{chr(d)}:")]
    sub_paths = [
        r"Program Files (x86)\Qingfeng\HeyboxAccelerator",
        r"Program Files\Qingfeng\HeyboxAccelerator",
        r"Qingfeng\HeyboxAccelerator",
        r"HeyboxAccelerator",
        r"Heybox",
        r"小黑盒加速器",
        r"小黑盒",
    ]
    for d in drives:
        for sp in sub_paths:
            cand = os.path.join(d, os.sep, sp)
            if os.path.isdir(cand) and (os.path.exists(os.path.join(cand, "heyboxacc.exe")) or os.path.exists(os.path.join(cand, "resources"))):
                return cand

    return r"C:\Program Files (x86)\Qingfeng\HeyboxAccelerator"

base = find_heybox_dir()
if not os.path.exists(base):
    print(f"Heybox directory not found: {base}")
    sys.exit(0)

print(f"Scanning Heybox directory: {base}")
for root, dirs, files in os.walk(base):
    for fn in files:
        if fn.startswith("chunk-793bf638") and fn.endswith(".js") and not fn.endswith(".bak"):
            f1 = os.path.join(root, fn)
            bak1 = f1 + ".bak"
            if not os.path.exists(bak1):
                try:
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
                    print(f"Patched {fn} successfully!")
                else:
                    print(f"{fn} already patched or pattern not found.")
            except Exception as e:
                print(f"Error patching {fn}: {e}")

        if fn.startswith("chunk-499402f5") and fn.endswith(".js") and not fn.endswith(".bak"):
            f2 = os.path.join(root, fn)
            bak2 = f2 + ".bak"
            if not os.path.exists(bak2):
                try:
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
                    print(f"Patched {fn} successfully!")
                else:
                    print(f"{fn} already patched or pattern not found.")
            except Exception as e:
                print(f"Error patching {fn}: {e}")
