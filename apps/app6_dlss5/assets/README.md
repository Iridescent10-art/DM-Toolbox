# DLSS 5 组件资产说明

本目录随源码仓库只保留**体积较小、必需**的组件；两个神经重构运行库（每个约 260 MB）与 RHI 安装器体积过大，
不进入 Git 仓库，请从 Releases 的 `DM-BOX.exe` 安装包中获取（安装后位于 `apps/app6_dlss5/assets/`）。

| 文件 | 是否随源码提供 | 说明 |
|---|---|---|
| `dxgi.dll` | ✅ | ReShade 6.8 64-bit 渲染底座（DLSS 5 / RenoDX Addon 宿主） |
| `renodx-dlss5-v11.9.addon64` | ✅ | RenoDX DLSS 5 v11.9 旗舰插件（默认） |
| `renodx-dlss-ShortFuse-261017汉化版.addon64` | ✅ | 备选汉化插件 |
| `runtimes/nvngx_dlssnr_rtx20_30_40.dll` | ❌（见安装包） | RTX 20/30/40 神经重构模型（263.37 MB） |
| `runtimes/nvngx_dlssnr_rtx50.dll` | ❌（见安装包） | RTX 50 / Blackwell 模型（254.08 MB） |
| `tools/RHI-Setup.exe` | ❌（可另行下载） | ReShade HDR Installer 安装器 |
| `presets/My look.ini` | ✅ | RenoDX DLSS 5 中文预设模板 |

从源码运行时的获取方式：

1. 下载并安装 Releases 中的 `DM-BOX.exe`，把安装目录里的
   `apps/app6_dlss5/assets/runtimes/` 复制到本目录；或
2. 在 DLSS 5 注入器界面中点击「📁 浏览更换...」，指向任意包含上述资产的插件目录。
