# DM-Toolbox (DM工具箱)

<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="common/assets/preview_main_dark.png">
  <source media="(prefers-color-scheme: light)" srcset="common/assets/preview_main_light.png">
  <img alt="DM-Toolbox" src="common/assets/preview_main.png">
</picture>

**一站式全能硬件深度定制、游戏多帧生成补丁、Auto HDR 画质增强、DLSS 5 神经重构与 DLSS 实时监测综合工具箱**

[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011-blue.svg)](https://microsoft.com)
[![Python](https://img.shields.io/badge/Python-3.14+-green.svg)](https://python.org)
[![Qt](https://img.shields.io/badge/GUI-PySide6%20%2F%20Fluent%20Design-orange.svg)](https://www.qt.io)
[![Release](https://img.shields.io/badge/Release-v1.3.10-brightgreen.svg)](https://github.com/Iridescent10-art/DM-Toolbox/releases)

</div>

---

## 🌟 核心功能一览

`DM-Toolbox` 整合了 6 款独立功能模块，采用全新统一的 **DM 通用设计语言底座 SDK (`dm_ui_core.py`)**：
- **DWM 硬件级无锯齿圆角抗锯齿合成 (`DWMWCP_ROUND=2`)**：彻底消除 QSS 软裁剪带来的四角白边与毛边锯齿；
- **全窗口统一右下角双斜线 `//` 矢量缩放手柄 (`DMSizeGrip`)**：主启动器与所有子软件窗口风格 100% 像素级对齐；
- **跨窗口日间 / 夜间模式实时无感同步 (`DMThemeManager`)**。

### 1. 🛠️ 全硬件配置大师 (`app1_hardware`)
- **硬件自定义与检测支持**：CPU / GPU / 显存 / 主板 / 内存 / 硬盘 自定义硬件，支持游戏客户端检测。
- **板块单独设置即时生效**：支持对 **CPU 处理器、独立显卡、主板 BIOS、内存 DDR5、硬盘存储** 每一个硬件板块进行**单独设置与即时生效**（主页快捷卡片与各详情配置页均提供一键单独生效入口），无需全盘重写，灵活高效。
- **全层级驱动模拟覆盖**：穿透覆盖 DirectX Adapter GUID、`Control\Video`、`Enum\PCI` 硬件总线、Windows Class 注册表、BIOS 及 WMI 查询。
- **客户端深度支持**：针对游戏客户端检测提供专属挂钩补丁与即时生效机制，支持一键保存与无损还原官方硬件配置。
- **原生标准对齐与气泡提示**：标准非编辑态单向下拉对齐视图，解决长型号横滚裁切问题，附带悬浮气泡全称提示。

<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="common/assets/preview_hardware_dark.png">
  <source media="(prefers-color-scheme: light)" srcset="common/assets/preview_hardware_light.png">
  <img alt="全硬件配置大师" src="common/assets/preview_hardware.png">
</picture>

</div>

### 2. ⚡ DLSS 多帧生成补丁 (`app2_mfg`)
- **帧率倍增黑科技**：为全架构显卡（RTX 20/30/40 系、GTX、AMD Radeon、Intel Arc）解除 DLSS-G / FSR3 / XeSS 插帧限制。
- **内置 4 大主流插帧核心模式**：
  - **模式 A (dashdogy 独立代理)**：高稳定性帧生成解除核心，支持 2X/3X/4X 多倍率插帧、Bink 链式劫持与原生代理；
  - **模式 B (RenoDX 插件优化)**：RenoDX 深度光流调度插件，支持 2X~6X 极速插帧、Blackwell 架构内核、薄几何体 ISR/VWB 与 BAM 边缘抗撕裂；
  - **模式 C (DLSSG-SM86 原生插帧)**：基于 `sdli1995/dlssg_for_sm86` 深度定制，专为 RTX 20 系 (Turing / SM75) 与 RTX 30 系 (Ampere / SM86) 显卡打造的原生硬件级 DLSS-G 运行库支持。内置 Ampere/Turing 专用光流与插帧内核，原生解锁最高 6X 动态多倍插帧；支持 FG Lite (Preset C，降低 32%~54% GPU 耗时) 与 4 级一致性加速档位；专享 RTX 20/30 DLSS INT8 超分辨率硬件加速，无需跨卡转译损耗，丝滑释放原生画质与超高帧率！
  - **模式 D (OptiScaler 跨卡转译)**：跨架构转译框架，为全显卡（包含非 RTX 卡、GTX 系列、AMD Radeon 与 Intel Arc）提供通用跨架构转译，原生解锁 Intel XeFG 2X~4X 官方插帧与 XeSS 2.0 AI 超分。
- **DLSS 4/4.5 Transformer 超分模型矩阵**：
  - 扩充完整 AI 模型预设矩阵：包含 **Preset M**（DLSS 4.5 第二代 Transformer 旗舰画质）、**Preset L**（DLSS 4.5 超性能）、**Preset K**（DLSS 4 经典锐利推荐）、**Preset J**（DLSS 4 细节强化）以及 CNN 终极版（Preset E/C/F）；
  - 默认选中项与一键恢复推荐统一设为 **`Default`**（保持游戏原生默认档位），支持 INI 正向反向双向无缝映射同步。
- **ReShade 框架防冲突与 `dxgi.dll` 避让锁**：
  - 存在 ReShade 底座时，`dxgi.dll` 绝对锁死留给 ReShade，OptiScaler 自动退避使用 `version.dll` 或 `winmm.dll`，实现两大框架无冲突丝滑共存。
- **游戏内外参数【双向实时同步】**：
  - **正向同步**：统一通过 `IniConfigManager` 保持注释与结构，UI 调整参数后即刻写入游戏根目录 `RTXMFG-UI.ini`、`mfg_unlocker.ini`、`OptiScaler.ini`（v0.9.4 唯一合法配置，自动清除遗留 `nvngx.ini`）与 `ReShade.ini` (`[RenoDX.MFGUnlock]`)；
  - **反向同步**：内置 `QFileSystemWatcher` 后台防抖监听（400ms Debounce + 抑制自循环），游戏内按快捷键调参保存后，桌面软件 UI 自动反向同步刷新！
- **集成 ReShade HDR (RHI) 与云端智能测速同步**：
  - 内置独立离线 RHI-Setup.exe，直连 RankFTW/RHI 官方 GitHub 仓库热更新；
  - 拥有与主工具箱完全一致的 **智能测速优选**（GH-Proxy / GHFast / 直连等多节点并发 Ping 测速与徽章标注），自动锁定最低延迟节点，支持多节点无缝故障转移；
  - 一键异步检查并同步 Mode A/B/C/D 四大插帧后端与 RHI 工具包，安全隔离存放于系统 AppData，不污染游戏或软件目录。

> [!WARNING]
> **反作弊与多人联机安全须知 (Anti-Cheat Warning)**：
> 多帧生成与跨架构转译补丁通过向游戏根目录植入代理动态库（如 `dxgi.dll`、`version.dll`、`winmm.dll` 等）来拦截图形 API 并调度插帧管线。**严禁在任何配备在线反作弊系统（如 EAC、BattlEye、Vanguard、Ricochet、ACE、VAC 等）的多人联机或竞技网游中使用！** 反作弊程序极易将 DLL 注入与函数拦截识别为未授权第三方外挂，可能导致账号被封禁。本项目仅供单机离线游戏与图形技术研究交流，**若在反作弊环境中使用造成封号，所有后果由使用者自行承担！**

### 3. 🌈 Windows Auto HDR 管理器 (`app3_autohdr`)
- **强制全局高动态范围**：解决部分 DirectX 11/12 游戏因未获微软认证而无法开启 Auto HDR 的问题。
- **自动游戏检测与配置**：智能识别系统中已安装的兼容游戏，一键配置 10-bit / 8-bit 高精度颜色映射。

### 4. 🔍 全架构超分与插帧水印指示器 (`app4_dlss`) (v1.2.0 重构升级)
- **4 大独立分项与一键总控**：
  1. `🟢 NVIDIA DLSS 官方超分水印`：注册表底层 `ShowDlssIndicator=1024`，左下角显示 DLSS 版本、渲染分辨率与 Preset 档位；
  2. `🔵 OptiScaler 性能叠加`：写入游戏 `OptiScaler.ini` 的 `[Menu] ShowFps`，在屏幕左上角显示当前超分引擎、渲染→输出分辨率与实时帧率；
  3. `⚡ 帧生成 Full 叠加`：将 OptiScaler 叠加升级为 `FpsOverlayType=4`，显示实时/插帧后双 FPS、FG 管线与 Reflex 延迟，用双 FPS 比值即可判断 2X / 3X / 4X；
  4. `📊 ReShade 帧率监控`：写入游戏 `ReShade.ini` 的 `[OVERLAY] ShowFPS / ShowFrameTime`（需已安装 ReShade 底座）。
- **全架构超分与插帧刷新率速查指南**：包含 2X (120Hz~144Hz)、3X (165Hz~180Hz)、4X~6X (240Hz~360Hz) 刷新率匹配防撕裂最佳实践。

### 5. 🖼️ JXR HDR 转换器 (`app5_jxr`)
- 把 Windows HDR 截图（JPEG XR / `.jxr`）批量转换为 **Ultra HDR JPEG** 或 **SDR PNG**，支持拖拽文件/文件夹与后台并发队列。
- 内置 Google `libultrahdr 1.5.1` + `libjpeg-turbo 3.2.0`，支持 `libultrahdr` / `ACES` / `BT.2446` 三种 Tone Mapping、JPEG 质量 60–100、峰值亮度自动/预设/自定义、EXIF/XMP 元数据透传。
- 独立单文件 `JxrConverter.exe`（约 66MB，免 .NET 运行时安装），由启动器以外部 EXE 方式打开；**沿用作者原始图标，未做任何修改**。
- **深 / 浅主题切换**：标题栏太阳/月亮按钮即时切换，选择保存到 `settings.json`；强调色由蓝色改为浅绿色，界面与工具箱的 DM 中性主题一致。

### 6. 🧠 DLSS 5 神经重构注入器 (`app6_dlss5`)

<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="common/assets/preview_dlss5_dark.png">
  <source media="(prefers-color-scheme: light)" srcset="common/assets/preview_dlss5_light.png">
  <img alt="DLSS 5 神经重构注入器" src="common/assets/preview_dlss5.png">
</picture>

</div>

- **RenoDX DLSS 5 v11.9 旗舰插件**：一键部署 ReShade 6.8 Add-on 底座 (`dxgi.dll`) + `renodx-dlss5-v11.9.addon64` + `nvngx_dlssnr.dll`，为 DLSS 超分接管神经网络渲染与画质重构。
- **架构自适应运行库**：按物理显卡自动选择模型——RTX 20/30/40 用 263.37 MB 版本、RTX 50 (Blackwell) 用 254.08 MB 版本，避免内核与硬件不匹配。
- **与多帧生成全自动共存**：模式 A/B/C/D 同时注入时自动做 DLL 槽位隔离（ReShade 固定 `dxgi.dll`、OptiScaler 迁移到 `winmm`/`version`），并清理 fakenvapi 与重复 ReShade 实例，从根上修掉「模式 C + DLSS 5 同时注入闪退」。
- **游戏内中文面板**：按 `Home` 呼出 RenoDX 中文调参面板（Preset / 风格 / 强度 / 皮肤结构 / 显存缓冲），`F6` 实时开关神经重构。
- **无损还原**：一键卸载并深度净化 ReShade / DLSS 5 / runtime / 代理 DLL，100% 恢复游戏原生目录。

---

## 💾 存储规范与绿色便携架构

程序遵循现代 Windows 绿色应用设计标准，**程序本体文件与用户持久化数据彻底解耦**：
- **配置文件持久化**：统一存储于 `%APPDATA%/ToolboxMaster/config/{app_name}/`
- **临时缓存与下载**：统一存储于 `%APPDATA%/ToolboxMaster/cache/{app_name}/`
- **一键出厂重置**：主页内置“🧹 还原与清理”功能，可一键关闭运行进程、清空缓存并毫秒级还原至 `defaults/` 出厂初始配置。

---

## 📦 安装与下载

### 方式一：下载 Windows 独立安装包 (推荐)
直接在 [Releases 页面](https://github.com/Iridescent10-art/DM-Toolbox/releases) 下载最新版的 `DM-BOX.exe`：
- **零环境依赖**：内置专属优化版绿色 Python 3.14 运行时环境，无需安装 Python。
- **标准安装体验**：默认安装至 `C:\Program Files\DMBOX`，提供桌面快捷方式创建选项。
- **原生极速启动**：安装后由原生编译的 `DMBOX.exe` 直接拉起，自带管理员授权。

### 方式二：从源码运行与二次开发
1. 克隆本仓库：
   ```bash
   git clone https://github.com/Iridescent10-art/DM-Toolbox.git
   cd DM-Toolbox
   ```
2. 安装依赖库：
   ```bash
   pip install PySide6 pillow
   ```
3. 启动工具箱：
   - 双击根目录下的 `一键启动DM工具箱.bat`，或在终端执行：
     ```bash
     python launcher/main.py
     ```

---

## 🔨 本地构建安装包

如果您修改了代码并希望重新制作单文件安装包：
直接双击根目录下的 **`一键打包制作安装包.bat`**，即可自动调用 Inno Setup 编译器在 `dist_setup/` 下生成最新的高压缩安装程序。

---

## 🙏 致谢开源项目 (Acknowledgments & Open Source Credits)

DM-Toolbox 的诞生与演进离不开全球开源社区与图形学极客们的无私奉献。在此特别向本项目所引用、集成或借鉴的上游优秀开源项目及核心作者表达崇高的敬意与诚挚的感谢：

- **[dlssg_for_sm86](https://github.com/sdli1995/dlssg_for_sm86)** (by sdli1995) - 专为 NVIDIA RTX 20 (SM75) 与 RTX 30 (SM86) 显卡打造的原生 DLSS-G 帧生成与 INT8 超分辨率硬件加速运行库。
- **[OptiScaler](https://github.com/cdozdil/OptiScaler)** (by cdozdil) - 卓越的跨显卡架构超分辨率与帧生成转译框架，为全卡畅玩提供底层驱动级可能。
- **[MFG-Unlocker](https://github.com/dashdogy)** (by dashdogy) - 极具创新的 DLSS 多帧生成解除与链式代理核心。
- **[RenoDX](https://github.com/clshortfuse/renodx)** (by clshortfuse / mavismmg) - 深度光流调度与高级帧生成优化插件。
- **[ReShade](https://reshade.me/)** (by Crosire & ReShade Community) - 行业标准的通用后期处理着色器底层底座。
- **[Intel® XeSS / XeFG](https://github.com/intel/xess)** - 高品质 AI 超分与帧生成 SDK。
- **[AMD FidelityFX™ SDK](https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK)** - 开放的 FSR 空间放大与帧生成套件。
- **[Qt / PySide6](https://www.qt.io)** - 现代高品质 Fluent GUI 设计系统底座。

---

## 🚫 严禁倒卖与开源声明 (Anti-Resale & License Notice)

> [!CAUTION]
> **本项目完全免费、纯开源发布，严禁任何形式的倒卖、付费售卖、捆绑收费或商业谋利！**

1. **完全免费**：DM-Toolbox 是一款公益开源工具箱，官方发布的源码、安装包及所有功能模块**永久免费**提供给广大玩家个人学习、技术研究与测试使用。
2. **严禁倒卖**：严禁任何个人或组织将本项目（包括源码、编译成品、衍生打包或内置组件）在各电商平台（淘宝、闲鱼、拼多多等）、社交平台、自媒体平台进行**任何形式的明码标价售卖、付费入群、赞助获取、捆绑收费**！
3. **谨防受骗**：凡是以“独家内部版”、“防封付费定制”、“独家加速器”、“永久激活版”等名目向您收取任何费用的，**均为未经授权的侵权倒卖行为，请广大玩家切勿受骗并积极举报！**
4. **技术学习声明**：本工具箱仅供个人计算机图形优化、画质增强、多屏校准与硬件测试学习交流之用。请在法律法规与游戏最终用户许可协议允许的范围内合理使用。
5. **反作弊与封禁免责声明**：本工具箱所集成的多帧生成、DLL 代理及渲染注入技术仅面向单人单机游戏与图形测试。任何在线联机或配备反作弊保护的游戏均可能因 DLL 拦截触发安全封禁，使用者须自行辨别并承担全部风险与责任，本项目及开发者不对任何账号封停、数据损失或连带责任负责。
