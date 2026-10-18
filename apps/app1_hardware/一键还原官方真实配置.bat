@echo off
chcp 65001 >nul
title 还原 CPU/GPU 官方真实配置
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0restore_config.ps1"
