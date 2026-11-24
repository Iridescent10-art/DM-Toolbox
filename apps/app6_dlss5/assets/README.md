# DLSS 5 组件资产说明

本目录随源码仓库只保留**体积较小、必需**的组件；两个神经重构运行库（每个约 260 MB）与 RHI 安装器体积过大，
不进入 Git 仓库，请从 Releases 的 `DM-BOX.exe` 安装包中获取（安装后位于 `apps/app6_dlss5/assets/`）。

## 模式 A：SF PLUS 4.2.0（ShortFuse 原生底座 + 独立控制面板）

| 文件 | 是否随源码提供 | 说明 |
|---|---|---|
| `renodx-dlss.addon64` | ✅ | SF PLUS 4.2.0 原生底座插件 |
| `ShortFusePlus-Panel.addon64` | ✅ | SF PLUS 独立控制面板插件（与 renodx-dlss.addon64 同目录） |
| `nvngx_dlssnr.dll` | ✅ | SF PLUS 面板 / NGX 代理（约 0.9 MB，加载真实运行库） |
| `runtimes/nvngx_dlssnr_rtx20_30_40.dll` | ❌（见安装包） | RTX 20/30/40 真实神经重构模型（263.37 MB） |
| `runtimes/nvngx_dlssnr_rtx50.dll` | ❌（见安装包） | RTX 50 / Blackwell 真实神经重构模型（254.08 MB） |

部署到游戏目录时：`nvngx_dlssnr.dll`（代理）+ `nvngx_dlssnr_real.dll`（真实模型，按显卡架构选择）。

## 模式 B：DLSS5 NR v15.1.0 Dev（Lecram 扩展底座）

| 文件 | 是否随源码提供 | 说明 |
|---|---|---|
| `lecram_v151/dlss5-nr.addon64` | ✅ | 64 位游戏主插件（18.0 MB） |
| `lecram_v151/dlss5-nr.addon32` | ✅ | 32 位游戏插件 |
| `lecram_v151/dlss5-nr-host/` | ✅ | 64 位宿主（`nr-host64.exe` + `ReShade64.dll`），DX9/10/11/OpenGL/32 位游戏由它承载 |
| `lecram_v151/INSTALL.txt` 等文档 | ✅ | 上游安装说明与第三方许可 |

## 公共组件

| 文件 | 是否随源码提供 | 说明 |
|---|---|---|
| `dxgi.dll` | ✅ | ReShade 6.8 64-bit 渲染底座（DLSS 5 / RenoDX Addon 宿主） |
| `presets/My look.ini` | ✅ | 默认预设模板（面部 / 皮肤重构强度默认 50%） |
| `tools/RHI-Setup.exe` | ❌（可另行下载） | ReShade HDR Installer 安装器 |

从源码运行时的获取方式：

1. 下载并安装 Releases 中的 `DM-BOX.exe`，把安装目录里的
   `apps/app6_dlss5/assets/runtimes/` 复制到本目录；或
2. 在 DLSS 5 注入器界面中点击「📁 浏览更换...」，指向任意包含上述资产的插件目录。
