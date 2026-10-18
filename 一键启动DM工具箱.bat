@echo off
cd /d "%~dp0"

:: 检查是否具备管理员权限 (通过 S-1-16-12288 高完整性 SID 精确检测)
whoami /groups | findstr "S-1-16-12288" >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在请求管理员权限以保障硬件与系统设置深度生效...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

where pythonw >nul 2>nul
if %errorlevel% equ 0 (
    start "" pythonw launcher\main.py
) else (
    start "" "C:\Users\17547\AppData\Local\Programs\Python\Python314\pythonw.exe" launcher\main.py
)