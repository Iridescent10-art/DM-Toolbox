@echo off
chcp 65001 >nul
title CPU/GPU 配置管理面板
cd /d "%~dp0"

if exist "%~dp0CPU_GPU配置管理工具.exe" (
    start "" "%~dp0CPU_GPU配置管理工具.exe"
) else (
    start "" python "%~dp0cpugpu_gui.py"
)
