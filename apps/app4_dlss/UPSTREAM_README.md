# DLSS 超分显示开关

一个用于切换 NVIDIA DLSS 超分状态指示器的 Windows 小工具。

## 使用方法

1. 下载 `release/DLSS超分显示开关.exe`。
2. 右键选择“以管理员身份运行”。
3. 点击“打开超分显示”或“关闭超分显示”。
4. 如果游戏正在运行，请重新启动游戏后查看效果。

## 功能

- 图形化显示当前状态
- 一键写入注册表：`HKLM\\SOFTWARE\\NVIDIA Corporation\\Global\\NGXCore\\ShowDlssIndicator`
- 无需分别导入两个注册表文件

## 文件说明

- `src/Program.cs`：C# WinForms 源代码
- `release/DLSS超分显示开关.exe`：可直接运行的程序
- `reg/`：原始注册表脚本
