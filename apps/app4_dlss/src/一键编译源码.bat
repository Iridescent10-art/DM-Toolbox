@echo off
chcp 65001 >nul
title 编译 DLSS 超分显示开关源码
cd /d "%~dp0"
echo 正在调用 Windows 内置 .NET 编译器 (csc.exe) 编译 Program.cs...

set CSC=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe

"%CSC%" /target:winexe /win32manifest:app.manifest /win32icon:app.ico /out:..\DLSS超分显示开关.exe Program.cs

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [成功] 已成功从 Program.cs 编译生成: DLSS超分显示开关.exe
) else (
    echo.
    echo [错误] 编译失败，请检查报错信息。
)
pause
