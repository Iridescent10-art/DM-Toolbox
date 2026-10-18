@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ===================================================
echo       DM工具箱 一键式全资源安装包自动化制作
echo ===================================================
echo 正在运行打包程序，请稍候...
python -u build_installer.py
pause
