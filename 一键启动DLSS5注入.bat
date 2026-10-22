@echo off
chcp 65001 >nul
cd /d "%~dp0"

:: 检查是否具备管理员权限
whoami /groups | findstr "S-1-16-12288" >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在请求管理员权限以保障插件注入与系统设置生效...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

:: 优先检测整合包自带的绿色独立运行环境 runtime\pythonw.exe
if exist "%~dp0runtime\pythonw.exe" (
    start "" "%~dp0runtime\pythonw.exe" -B apps\app6_dlss5\main.py
    exit /b
)

:: 检测系统 PATH 中的 pythonw / python
where pythonw >nul 2>nul
if %errorlevel% equ 0 (
    start "" pythonw -B apps\app6_dlss5\main.py
    exit /b
)

where python >nul 2>nul
if %errorlevel% equ 0 (
    start "" python -B apps\app6_dlss5\main.py
    exit /b
)

:: 回退检测常见用户目录安装的 Python 运行时
if exist "%LOCALAPPDATA%\Programs\Python\Python314\pythonw.exe" (
    start "" "%LOCALAPPDATA%\Programs\Python\Python314\pythonw.exe" -B apps\app6_dlss5\main.py
    exit /b
)

if exist "%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe" (
    start "" "%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe" -B apps\app6_dlss5\main.py
    exit /b
)

if exist "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" (
    start "" "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" -B apps\app6_dlss5\main.py
    exit /b
)

if exist "C:\Python314\pythonw.exe" (
    start "" "C:\Python314\pythonw.exe" -B apps\app6_dlss5\main.py
    exit /b
)

echo 未在当前系统检测到可用的 Python 运行环境！请确认整合包完整性或安装 Python。
pause