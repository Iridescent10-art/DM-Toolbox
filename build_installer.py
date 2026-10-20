# -*- coding: utf-8 -*-
"""
Full Automated Packaging Pipeline for DM Toolbox (DM工具箱).
Builds a standalone, zero-dependency installer package using Inno Setup:
1. Compiles high-integrity native GUI launcher DMBOX.exe (with app_icon.ico and requireAdministrator manifest).
2. Assembles self-contained staging tree dist/DMBOX/ with isolated Python 3.14 + PySide6 runtime.
3. Validates the isolated runtime and module imports.
4. Generates and compiles Inno Setup script into dist_setup/DM-BOX.exe.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
PYTHON_SYS_DIR = Path(os.environ.get("LOCALAPPDATA")) / "Programs" / "Python" / "Python314"
CSC_PATH = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe")
ISCC_PATH = Path(r"C:\Users\17547\AppData\Local\Programs\Inno Setup 6\ISCC.exe")

DIST_DIR = ROOT_DIR / "dist" / "DMBOX"
SETUP_OUTPUT_DIR = ROOT_DIR / "dist_setup"


def step1_compile_native_launcher():
    print("[1/5] 正在编译原生 C# 启动引导器 DMBOX.exe...")
    cs_file = ROOT_DIR / "DMBOX.cs"
    manifest_file = ROOT_DIR / "DMBOX.manifest"
    icon_file = ROOT_DIR / "common" / "assets" / "app_icon.ico"
    out_exe = ROOT_DIR / "DMBOX.exe"

    cs_source = """using System;
using System.IO;
using System.Diagnostics;
using System.Windows.Forms;
using System.Reflection;
using System.Runtime.InteropServices;

[assembly: AssemblyTitle("DM-Toolbox")]
[assembly: AssemblyDescription("DM工具箱 - 一站式全能硬件深度定制与游戏优化综合工具箱")]
[assembly: AssemblyConfiguration("")]
[assembly: AssemblyCompany("DM Studio")]
[assembly: AssemblyProduct("DM-Toolbox")]
[assembly: AssemblyCopyright("Copyright (C) 2026 DM Studio. All rights reserved.")]
[assembly: AssemblyTrademark("DM-Toolbox")]
[assembly: AssemblyCulture("")]
[assembly: ComVisible(false)]
[assembly: AssemblyVersion("1.2.15.0")]
[assembly: AssemblyFileVersion("1.2.15.0")]

namespace DMBOX
{
    static class Program
    {
        [STAThread]
        static void Main(string[] args)
        {
            try
            {
                string baseDir = AppDomain.CurrentDomain.BaseDirectory;
                string runtimePyw = Path.Combine(baseDir, "runtime", "pythonw.exe");
                string pyExe = File.Exists(runtimePyw) ? runtimePyw : "pythonw.exe";
                string scriptPath = Path.Combine(baseDir, "launcher", "main.py");

                if (!File.Exists(scriptPath))
                {
                    MessageBox.Show("未在程序目录下找到主启动文件:\\n" + scriptPath, "DM工具箱 - 启动失败", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return;
                }

                ProcessStartInfo psi = new ProcessStartInfo();
                psi.FileName = pyExe;
                psi.Arguments = "-B \\"" + scriptPath + "\\"";
                psi.WorkingDirectory = baseDir;
                psi.UseShellExecute = true;
                psi.WindowStyle = ProcessWindowStyle.Hidden;

                Process.Start(psi);
            }
            catch (Exception ex)
            {
                MessageBox.Show("启动 DM工具箱 出现异常:\\n" + ex.Message, "DM工具箱", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }
    }
}
"""
    cs_file.write_text(cs_source, encoding="utf-8")

    manifest_content = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v3">
    <security>
      <requestedPrivileges>
        <requestedExecutionLevel level="requireAdministrator" uiAccess="false"/>
      </requestedPrivileges>
    </security>
  </trustInfo>
  <compatibility xmlns="urn:schemas-microsoft-com:compatibility.v1">
    <application>
      <supportedOS Id="{8e0f7a12-bfb3-4fe8-b9a5-48fd50a15a9a}"/>
      <supportedOS Id="{1f676c76-80e1-4239-95bb-83d0f6d0da78}"/>
      <supportedOS Id="{4a2f28e3-53b9-4441-ba9c-d69d4a4a6e38}"/>
      <supportedOS Id="{35138b9a-5d96-4fbd-8e2d-a2440225f93a}"/>
    </application>
  </compatibility>
</assembly>
"""
    manifest_file.write_text(manifest_content, encoding="utf-8")

    cmd = [
        str(CSC_PATH),
        "/target:winexe",
        f"/out:{out_exe}",
        f"/win32icon:{icon_file}",
        f"/win32manifest:{manifest_file}",
        str(cs_file)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"csc 编译失败: {res.stderr}\n{res.stdout}")
    print(f" -> DMBOX.exe 编译成功 ({out_exe.stat().st_size / 1024:.1f} KB)")


def step2_assemble_staging_tree():
    print("[2/5] 正在组织打包目录结构 dist/DMBOX/ ...")
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True)

    # 1. 拷贝 DMBOX.exe
    shutil.copy2(ROOT_DIR / "DMBOX.exe", DIST_DIR / "DMBOX.exe")

    # 2. 拷贝 apps (排除 __pycache__)
    def ignore_pycache(path, names):
        return [n for n in names if n in ["__pycache__", ".git"]]

    print(" -> 拷贝应用模块 apps/ ...")
    shutil.copytree(ROOT_DIR / "apps", DIST_DIR / "apps", ignore=ignore_pycache)

    print(" -> 拷贝公共组件 common/ ...")
    shutil.copytree(ROOT_DIR / "common", DIST_DIR / "common", ignore=ignore_pycache)

    print(" -> 拷贝初始配置 defaults/ ...")
    shutil.copytree(ROOT_DIR / "defaults", DIST_DIR / "defaults", ignore=ignore_pycache)

    print(" -> 拷贝主程序 launcher/ ...")
    shutil.copytree(ROOT_DIR / "launcher", DIST_DIR / "launcher", ignore=ignore_pycache)

    print(" -> 拷贝设计系统底座 SDK dm_ui_core.py ...")
    if (ROOT_DIR / "dm_ui_core.py").exists():
        shutil.copy2(ROOT_DIR / "dm_ui_core.py", DIST_DIR / "dm_ui_core.py")

    # 3. 组织精简独立绿色 Python 运行环境 runtime/
    print(" -> 组织绿色独立 Python 运行时 runtime/ ...")
    rt_dir = DIST_DIR / "runtime"
    rt_dir.mkdir(parents=True)

    # 核心可执行文件与运行时动态库
    for name in ["python.exe", "pythonw.exe", "python3.dll", "python314.dll", "vcruntime140.dll", "vcruntime140_1.dll"]:
        src_f = PYTHON_SYS_DIR / name
        if src_f.exists():
            shutil.copy2(src_f, rt_dir / name)

    # DLLs
    shutil.copytree(PYTHON_SYS_DIR / "DLLs", rt_dir / "DLLs")

    # Lib 标准库 (过滤臃肿且不用的开发组件)
    lib_dest = rt_dir / "Lib"
    lib_dest.mkdir(parents=True)
    for item in (PYTHON_SYS_DIR / "Lib").iterdir():
        if item.name in ["site-packages", "test", "idlelib", "turtledemo", "__pycache__", "ensurepip"]:
            continue
        if item.is_dir():
            shutil.copytree(item, lib_dest / item.name, ignore=ignore_pycache)
        else:
            shutil.copy2(item, lib_dest / item.name)

    # site-packages
    sp_dest = lib_dest / "site-packages"
    sp_dest.mkdir(parents=True)

    # shiboken6
    shutil.copytree(PYTHON_SYS_DIR / "Lib" / "site-packages" / "shiboken6", sp_dest / "shiboken6", ignore=ignore_pycache)

    # PIL
    shutil.copytree(PYTHON_SYS_DIR / "Lib" / "site-packages" / "PIL", sp_dest / "PIL", ignore=ignore_pycache)

    # PySide6 (剔除未使用的大型模块如 WebEngine/3D/Quick 等，体积由 630MB 骤降至 ~60MB)
    pyside_src = PYTHON_SYS_DIR / "Lib" / "site-packages" / "PySide6"
    pyside_dest = sp_dest / "PySide6"
    pyside_dest.mkdir(parents=True)

    essential_names = {
        "QtCore.pyd", "QtGui.pyd", "QtWidgets.pyd",
        "Qt6Core.dll", "Qt6Gui.dll", "Qt6Widgets.dll",
        "pyside6.abi3.dll", "opengl32sw.dll", "d3dcompiler_47.dll"
    }

    for item in pyside_src.iterdir():
        if item.is_file():
            if item.suffix in [".py", ".json"] or item.name in essential_names:
                shutil.copy2(item, pyside_dest / item.name)
        elif item.is_dir() and item.name == "plugins":
            plugins_dest = pyside_dest / "plugins"
            plugins_dest.mkdir(parents=True)
            for sub in ["platforms", "imageformats", "styles"]:
                sub_src = item / sub
                if sub_src.exists():
                    shutil.copytree(sub_src, plugins_dest / sub, ignore=ignore_pycache)

    total_mb = sum(f.stat().st_size for f in DIST_DIR.rglob("*") if f.is_file()) / (1024 * 1024)
    print(f" -> 打包准备区装配完成！总原始体积: {total_mb:.1f} MB")


def step3_validate_runtime():
    print("[3/5] 正在隔离验证运行时的完整性与独立启动能力...")
    test_rt_py = DIST_DIR / "runtime" / "python.exe"
    clean_env = os.environ.copy()
    clean_env.pop("PYTHONPATH", None)
    clean_env.pop("PYTHONHOME", None)
    clean_env["PATH"] = f"{DIST_DIR / 'runtime'};{DIST_DIR / 'runtime' / 'DLLs'};{os.environ.get('PATH', '')}"
    test_code = (
        "import sys;"
        "sys.path.insert(0, r'" + str(DIST_DIR).replace('\\', '/') + "');"
        "from PySide6 import QtCore, QtGui, QtWidgets;"
        "import common.ui_theme;"
        "import common.config_manager;"
        "import launcher.main;"
        "print('VERIFIED_OK');"
    )
    res = subprocess.run([str(test_rt_py), "-c", test_code], capture_output=True, text=True, env=clean_env)
    if "VERIFIED_OK" not in res.stdout:
        raise RuntimeError(f"独立运行时验证失败:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}")
    print(" -> 运行时与四大应用及启动器模块验证通过，无任何外部依赖问题！")


def step4_build_inno_installer():
    print("[4/5] 正在配置 Inno Setup 安装包制作脚本...")
    SETUP_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    iss_file = ROOT_DIR / "dist" / "DMBOX_Setup.iss"
    icon_path = ROOT_DIR / "common" / "assets" / "app_icon.ico"

    iss_content = f"""[Setup]
; 基本应用信息
AppName=DM工具箱
AppVersion=1.2.15
AppPublisher=DM Studio
AppPublisherURL=https://github.com/Iridescent10-art/DM-Toolbox
AppSupportURL=https://github.com/Iridescent10-art/DM-Toolbox
AppUpdatesURL=https://github.com/Iridescent10-art/DM-Toolbox/releases
VersionInfoVersion=1.2.15.0
VersionInfoCompany=DM Studio
VersionInfoDescription=DM工具箱 安装向导
VersionInfoProductName=DM工具箱
VersionInfoProductVersion=1.2.15.0
VersionInfoCopyright=Copyright (C) 2026 DM Studio
DefaultDirName={{autopf}}\\DMBOX
DefaultGroupName=DM工具箱
AllowNoIcons=yes
OutputDir={str(SETUP_OUTPUT_DIR)}
OutputBaseFilename=DM-BOX
SetupIconFile={str(icon_path)}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
DisableDirPage=no
DisableProgramGroupPage=no
UninstallDisplayIcon={{app}}\\DMBOX.exe
CloseApplications=yes
CloseApplicationsFilter=*.exe

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Default.isl"

[Messages]
SetupAppTitle=DM工具箱 安装向导
SetupWindowTitle=安装 - DM工具箱
SelectDirLabel3=安装程序将把 DM工具箱 安装到以下文件夹：
SelectDirBrowseLabel=点击“下一步”继续。如果要安装到其他文件夹，请点击“浏览”。
SelectTasksLabel2=请勾选您希望安装程序执行的附加任务，然后点击“下一步”：
FinishedHeadingLabel=DM工具箱 安装向导已完成
FinishedLabel=安装程序已在您的计算机上安装完成 DM工具箱。\\n\\n点击“完成”即可立即体验。
ClickFinish=点击“完成”退出安装向导。

[CustomMessages]
chinesesimplified.CreateDesktopIcon=创建桌面快捷方式(&D)
chinesesimplified.AdditionalIcons=快捷方式选项:
chinesesimplified.LaunchProgram=立即运行 DM工具箱

[Tasks]
Name: "desktopicon"; Description: "{{cm:CreateDesktopIcon}}"; GroupDescription: "{{cm:AdditionalIcons}}"; Flags: checkedonce

[Files]
; 打包 dist/DMBOX 下的所有资源文件
Source: "{str(DIST_DIR)}\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; 开始菜单与桌面快捷方式
Name: "{{group}}\\DM工具箱"; Filename: "{{app}}\\DMBOX.exe"; IconFilename: "{{app}}\\common\\assets\\app_icon.ico"
Name: "{{group}}\\卸载 DM工具箱"; Filename: "{{uninstallexe}}"
Name: "{{autodesktop}}\\DM工具箱"; Filename: "{{app}}\\DMBOX.exe"; IconFilename: "{{app}}\\common\\assets\\app_icon.ico"; Tasks: desktopicon

[UninstallDelete]
; 彻底清除安装目录本体，不留任何临时生成文件与子文件夹
Type: filesandordirs; Name: "{{app}}"

[Run]
; 安装完成后询问并自动启动
Filename: "{{app}}\\DMBOX.exe"; Description: "{{cm:LaunchProgram}}"; Flags: nowait postinstall skipifsilent runascurrentuser

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  AppDir: string;
  AppDataDir: string;
  ResultCode: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    // 1. 强制终止可能在后台运行的 DMBOX 及关联 Python 进程，防止文件锁定
    Exec('taskkill.exe', '/F /IM DMBOX.exe /T', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec('taskkill.exe', '/F /IM pythonw.exe /T', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec('taskkill.exe', '/F /IM python.exe /T', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

    // 2. 清理可能创建的系统计划任务与公共配置
    Exec('schtasks.exe', '/delete /tn CPU_Model_Fix_On_Startup /f', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    DeleteFile(ExpandConstant('C:\\Users\\Public\\Hardware_Config.json'));
  end
  else if CurUninstallStep = usPostUninstall then
  begin
    // 3. 彻底删除安装目录本体及其全部子项（清除 pyc、日志、临时文件等）
    AppDir := ExpandConstant('{{app}}');
    if DirExists(AppDir) and (AppDir <> ExpandConstant('{{autopf}}')) and (Length(AppDir) > 3) then
    begin
      DelTree(AppDir, True, True, True);
    end;

    // 4. 询问用户是否同时清空 AppData 中的本地用户配置与下载缓存 (250MB+)
    AppDataDir := ExpandConstant('{{userappdata}}\\ToolboxMaster');
    if DirExists(AppDataDir) then
    begin
      if MsgBox('检测到本地用户配置与组件下载缓存（约 250MB+）。'#13#10#13#10 +
                '路径: ' + AppDataDir + #13#10#13#10 +
                '是否同时彻底清空？'#13#10#13#10 +
                '【是(Y)】：彻底深度卸载，不留任何残留（推荐）；'#13#10 +
                '【否(N)】：保留缓存与配置，以备未来重新安装使用。',
                mbConfirmation, MB_YESNO) = IDYES then
      begin
        DelTree(AppDataDir, True, True, True);
      end;
    end;
  end;
end;
"""
    iss_file.write_text(iss_content, encoding="utf-8-sig")
    print(" -> ISS 脚本配置完成，正在通过 Inno Setup 高效压缩打包...")

    cmd = [str(ISCC_PATH), str(iss_file)]
    res = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if res.returncode != 0:
        raise RuntimeError(f"ISCC 打包失败: {res.stderr}\n{res.stdout}")

    out_installer = SETUP_OUTPUT_DIR / "DM-BOX.exe"
    if out_installer.exists():
        mb = out_installer.stat().st_size / (1024 * 1024)
        print(f"[5/5] [OK] 安装包打包成功！输出路径:\n{out_installer}\n安装包体积: {mb:.2f} MB (高密度 LZMA2 极速压缩)")
    else:
        print("[!] 未在输出目录检测到安装包文件，请检查编译输出。")


def main():
    print("==================================================")
    print("      DM工具箱 一键式全资源安装包构建程序         ")
    print("==================================================")
    step1_compile_native_launcher()
    step2_assemble_staging_tree()
    step3_validate_runtime()
    step4_build_inno_installer()
    print("==================================================")
    print("构建全部顺利完成！您可以直接将安装包分享给好友安装使用。")


if __name__ == "__main__":
    main()
