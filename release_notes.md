# 🎉 DM-Toolbox v1.2.12 · 更新界面高对比度可读性重构与多镜像加速源自由切换

> **一站式全能硬件深度定制、游戏多帧生成补丁、Auto HDR 画质增强与 DLSS 实时监测综合工具箱**

### 🌟 v1.2.12 核心更新与优化

1. **更新界面全要素高对比度清晰度重构 (彻底解决“字看不清”问题)**
   - 彻底修复系统浅色/深色主题切换时，更新弹窗内设置项与提示文字对比度不足的问题；
   - 采用深邃清晰的正文字体配色（浅色模式 `#111827`，深色模式 `#F3F4F6`），各级标题均使用加粗高对比度渲染；
   - 重构勾选框指示器（Check Indicator），内置自主绘制的高清抗锯齿白色对勾图标 (`✓`)，彻底告别单色绿块，状态一目了然；
   - 将镜像选择与后台检测选项整合至现代流式设置卡片 (`SettingsCard`)，界面整洁规范。

2. **内置多镜像加速下载节点切换**
   - 新增自由切换下载镜像源下拉列表，满足各类复杂网络环境需求：
     - **🚀 GHProxy 节点 (推荐 · 国内高速 CDN 加速)**：国内用户首选，超快 CDN 缓存链路；
     - **⚡ GHFast 节点 (备用 · 国内高速镜像)**：多线路备用，应对特定运营商解析波动；
     - **🌐 GitHub 官方直连 (适合已开启科学上网 / 全局代理)**：原汁原味官方源，适合具备网络代理环境的用户；
   - 智能记忆用户的镜像源偏好，后续更新自动复用最佳节点。

3. **开机后台静默检测与版本自由选择**
   - 软件启动 2 秒后在后台静默发起 GitHub API 异步检测，完全不影响首页和各子工具的秒开体验；
   - 发现新版时主页顶部自动呈现显眼的高亮提示按钮；
   - 保留所有历史 GitHub Release 记录，自由按需更新或回退。

---

# 🎉 DM-Toolbox v1.2.11 · 全局集成在线检查更新与开机后台静默检测

> **一站式全能硬件深度定制、游戏多帧生成补丁、Auto HDR 画质增强与 DLSS 实时监测综合工具箱**

### 🌟 v1.2.11 核心更新与优化

1. **为整个软件引入云端版本检查与智能在线更新器 (`AppUpdateDialog`)**
   - 支持自由查询 GitHub 官方发布的所有版本列表，可按需**选择更新到最新 GitHub 版本**或回退/重装特定版本；
   - 界面直观呈现当前版本、最新版本、发布时间、安装包大小及完整的 Markdown 更新日志；
   - 支持实时动态下载进度条（显示下载 MB / 总 MB、完成百分比与实时下载速度）；
   - 内置国内网络高速镜像加速选项 (`GHProxy`)，国内网络环境下载稳定流畅；
   - 下载完成后支持一键无感拉起安装向导进行热覆盖安装。

2. **每次开启软件自动在后台检查更新**
   - 软件启动 2 秒后自动在后台发起静默更新检查，完全不影响首页和各子工具的秒开体验；
   - 当检测到新版本时，首页『检查更新』按钮自动升级为醒目的『✨ 发现新版本 vX.X.X』高亮状态，方便用户一键打开更新器；
   - 在更新器内提供『每次开启软件自动在后台检查更新』开关选项，满足不同用户的个性化需求。

3. **全窗口标题栏快捷检查更新**
   - 在全架构基础窗口框架（`BaseWindow`）标题栏右上角嵌入『🔄 检查更新』快捷入口，无论是主页还是任意子工具内均可随时一键检查更新。

---

# 🎉 DM-Toolbox v1.2.10 · 默认强制锁定 DLSS 4 Preset K 模型与 XeSS 3X 三倍帧生成

> **一站式全能硬件深度定制、游戏多帧生成补丁、Auto HDR 画质增强与 DLSS 实时监测综合工具箱**

### 🌟 v1.2.10 核心更新与优化

1. **默认超分模型切换为 DLSS 4 第一代 Transformer 模型 Preset K**
   - 彻底解决部分游戏与引擎回退到旧版 D 模型导致的画面重影抖动与模糊问题；
   - 模式 A (dashdogy) 与 模式 C (OptiScaler) 默认预设均自动锁定写入 `Preset K` (枚举值 11)；
   - 保留 Default 与 Preset M/L/J/E/C/F 等自由切换选项。

2. **XeSS 2.0 / XeMFG 默认升级为 3X 三倍帧生成**
   - 模式 C 插帧默认倍率由 2X 提升为 **3X (InterpolationCount=2)**，配合高刷电竞显示器体验极致丝滑流体画面；
   - 模式 A 默认倍率同步保持为 3X (Multiplier=3)。

---

# 🎉 DM-Toolbox v1.2.9 · dashdogy v1.6.1 升级与 Default 直通优先继承 NVIDIA App 驱动层模型

> **一站式全能硬件深度定制、游戏多帧生成补丁、Auto HDR 画质增强与 DLSS 实时监测综合工具箱**

### 🌟 v1.2.9 核心升级与优化

1. **全面升级 dashdogy (MFG-Unlocker) 至最新发布版 v1.6.1**
   - 包含最新的 RTX 50 系原生适配与 RTX 20/30/40 系实时 DLSS 预设切换支持；
   - 增强在第三方工具挂钩 DirectX 12 管线时的 Tensor Core 高性能帧生成稳定性；
   - 智能同步模式 A (winmm/MFGUnlocker.dll) 与模式 C XeMFG 插件 (OptiScaler/plugins/MFGUnlocker.asi)，自动按版本与文件校验升级。

2. **Default 直通项深度优化：优先继承 NVIDIA App 驱动层模型**
   - 当用户在 DLSS 预设下拉框中选择 **Default (直通 · 优先继承 NVIDIA App / 全局驱动设置模型)** 时，自动写入 RenderPresetOverride=false、UseGenericAppIdWithDlss=false 及 RenderPresetForAll=0；
   - 彻底解决由于伪装 AppId 导致 NVIDIA App 游戏专属配置文件失效的问题，让用户在 NVIDIA App 或驱动层全局替换的 DLSS 4/4.5 (Model M / Model K) 模型能够 100% 优先无损直通生效；
   - 用户如需强制锁定特定模型，也可在下拉框中自由指定 Preset M / L / K / J / E / C / F。

3. **内置最新版 OptiScaler 10 (Nightly-20261020)**
   - 内置 OptiScaler 10 最新架构与完整 XeSS 2.0 / FSR 3.1 核心组件，开箱即用，无需二次下载。

---

# 🎉 DM-Toolbox 正式版 (Official Release)

> **一站式全能硬件深度定制、游戏多帧生成补丁、Auto HDR 画质增强与 DLSS 实时监测综合工具箱**

---

### 🌟 核心功能一览

#### 1. 🛠️ 全硬件配置大师 (`app1_hardware`)
- **硬件自定义与检测支持**：CPU / GPU / 显存 / 主板 / 内存 / 硬盘 自定义硬件，支持游戏客户端检测。
- **板块单独设置即时生效**：支持对 **CPU 处理器、独立显卡、主板 BIOS、内存 DDR5、硬盘存储** 每一个硬件板块进行**单独设置与即时生效**（主页快捷卡片与各详情配置页均提供一键单独生效入口），无需每次全盘重写，大幅提升调试效率。
- **全层级驱动模拟覆盖**：穿透覆盖 DirectX Adapter GUID、`Control\Video`、`Enum\PCI` 硬件总线、Windows Class 注册表、BIOS 及 WMI 查询。
- **客户端深度支持**：针对游戏客户端检测提供专属挂钩补丁与即时生效机制，支持一键保存与无损还原官方硬件配置。
- **原生标准下拉与提示**：全面升级非编辑态标准对齐视图，解决长型号横滚裁切问题，附带悬浮气泡全称提示。

#### 2. ⚡ DLSS 多帧生成补丁 (`app2_mfg`)
- **全架构显卡帧率倍增**：为全架构显卡（RTX 20/30/40/50 系、GTX、AMD Radeon、Intel Arc）解除 DLSS-G / FSR3 / XeSS 插帧限制。
- **内置 3 大主流插帧核心模式**：
  - **模式 A (dashdogy 独立代理)**：高稳定性帧生成解除核心，支持 2X/3X/4X 多倍率插帧、Bink 链式劫持与原生代理；进游戏按 `Backspace` 呼出调参菜单。
  - **模式 B (RenoDX 插件优化)**：RenoDX 深度光流调度插件，支持 2X~6X 极速插帧、Blackwell 架构内核、薄几何体 ISR/VWB 与 BAM 边缘抗撕裂；进游戏按 `Home` 呼出调参面板。
  - **模式 C (OptiScaler 跨卡转译)**：跨架构转译框架，原生解锁 Intel XeFG 官方插帧与 XeSS 2.0 AI 超分；进游戏按 `Insert`（或自选快捷键）呼出 ImGui 菜单，完美解决高分辨率（2K/4K）UI 缩放与按键响应。
- **DLSS 4/4.5 Transformer 超分模型矩阵**：
  - 扩充完整 AI 模型预设矩阵：包含 **Preset M**（DLSS 4.5 第二代 Transformer 旗舰画质）、**Preset L**（DLSS 4.5 超性能）、**Preset K**（DLSS 4 经典锐利推荐）、**Preset J**（DLSS 4 细节强化）以及 CNN 终极版（Preset E/C/F）；
  - 默认选中项与一键恢复推荐统一设为 **`Default`**（保持游戏原生默认档位），支持 INI 正向反向双向无缝映射同步。
- **ReShade 框架防冲突与 `dxgi.dll` 避让锁**：
  - 存在 ReShade 底座时，`dxgi.dll` 绝对锁死留给 ReShade，OptiScaler 自动退避使用 `version.dll` 或 `winmm.dll`，实现两大框架无冲突丝滑共存。
- **PE 导入表动态分析**：针对未静态链接 `dxgi.dll` 的游戏（如《燕云十六声》等），智能分析 PE 导入表并优先选择 `winmm.dll`，确保游戏启动第一时间加载并拦截 Streamline。

#### 3. 🎨 全局游戏 SDR 转 Auto HDR 画质增强 (`app3_autohdr`)
- 自动遍历检测系统注册游戏与常见游戏目录，支持一键批量开启/关闭 Auto HDR 增强。
- 内嵌高品质矢量 Chevron 下拉指示箭头与平滑胶囊圆角交互，体验丝滑流畅。

#### 4. 🔍 全架构超分与插帧水印指示器 (`app4_dlss`)
- **4 大独立分项与一键总控**：
  1. `🟢 NVIDIA DLSS 官方超分水印`：注册表底层 `ShowDlssIndicator=1024`，左下角显示 DLSS 版本、渲染分辨率与 Preset 档位；
  2. `🔵 OptiScaler 性能叠加`：写入游戏真实目录的 `OptiScaler.ini [Menu] ShowFps`，在屏幕左上角显示当前超分引擎、渲染→输出分辨率与实时帧率；
  3. `⚡ 帧生成 Full 叠加`：将 OptiScaler 叠加升级为 `FpsOverlayType=4`，显示实时/插帧后双 FPS、FG 管线与 Reflex 延迟，用双 FPS 比值即可判断 2X / 3X / 4X；
  4. `📊 ReShade 帧率监控`：写入游戏 `ReShade.ini` 的 `[OVERLAY] ShowFps / ShowFrameTime`（需已安装 ReShade 底座）。
- **使用指南顺序与逻辑**：模式 A (Backspace) → 模式 B (Home) → 模式 C (Insert) 清晰直观。

#### 5. 🖼️ JXR HDR 转换器 (`app5_jxr`)
- 把 Windows HDR 截图（JPEG XR / `.jxr`）批量转换为 **Ultra HDR JPEG** 或 **SDR PNG**，支持拖拽文件/文件夹与后台并发队列。
- 内置 Google `libultrahdr 1.5.1` + `libjpeg-turbo 3.2.0`，支持 `libultrahdr` / `ACES` / `BT.2446` 三种 Tone Mapping、JPEG 质量 60–100、峰值亮度自动/预设/自定义、EXIF/XMP 元数据透传。
- 独立单文件 `JxrConverter.exe`（免 .NET 运行时安装），由启动器以外部 EXE 方式打开；窗口保持原版 Fluent 设计风格。

---

### 📦 安装与使用说明

1. 下载下方 Assets 中的 **`DM-BOX.exe`** 安装包直接运行安装。
2. 安装完成后运行桌面上的 **DM工具箱** 快捷方式。
3. 纯绿色、无冗余外部依赖，全套 Python 3.14 + PySide6 离线内嵌运行库，开箱即用！

---

### 🙏 致谢开源项目 (Acknowledgments)

本项目深度致谢以下杰出的上游开源项目与作者团队：
- **[OptiScaler](https://github.com/cdozdil/OptiScaler)** (by cdozdil)
- **[MFG-Unlocker](https://github.com/dashdogy)** (by dashdogy)
- **[RenoDX](https://github.com/clshortfuse/renodx)** (by clshortfuse / mavismmg)
- **[ReShade](https://reshade.me/)** (by Crosire & ReShade Community)
- **[Intel® XeSS / XeFG](https://github.com/intel/xess)**
- **[AMD FidelityFX™ SDK](https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK)**
- **[PySide6 / Qt Project](https://www.qt.io)**

---

### 🚫 严禁倒卖与开源声明 (Anti-Resale Notice)

- **永久免费开源**：DM-Toolbox 为公益免费开源项目，官方发布的源码与安装包均完全免费！
- **严禁倒卖售卖**：严禁任何个人或商家在各电商平台（淘宝、闲鱼、拼多多等）、社交群聊或自媒体以任何形式收费、倒卖或捆绑售卖！
- **谨防受骗**：切勿购买任何收费“定制版”或“内部加速器”，谨防上当受骗！
- **反作弊封禁免责**：多帧生成涉及图形 API 与 DLL 代理拦截技术，严禁在具备在线反作弊机制（如 EAC/BE/Vanguard/ACE/VAC 等）的多人联机网游中使用，违规使用导致的一切封禁责任由使用者自行承担！
