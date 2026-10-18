@echo off
chcp 65001 >nul
title 应用 CPU/GPU 自定义配置
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0apply_config.ps1"
