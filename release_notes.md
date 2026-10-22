# 🎉 DM-Toolbox v1.3.6 · 云端组件库智能测速优选与插帧+RHI全栈热更新

> **一站式全能硬件深度定制、游戏多帧生成补丁、Auto HDR 画质增强与 DLSS 实时监测综合工具箱**

### 🌟 v1.3.6 核心更新与优化

1. **插帧全后端 (Mode A/B/C/D) 与 RHI 模组全栈直连 GitHub 官方仓库**
   - **模式 A (Standalone)**: 直连 [dashdogy/MFG-Unlocker](https://github.com/dashdogy/MFG-Unlocker) (v1.6.1)
   - **模式 B (ReShade Addon)**: 直连 [mavismmg/MFGAdaUnlock-RenoDx](https://github.com/mavismmg/MFGAdaUnlock-RenoDx) (1.4.5)
   - **模式 C (DLSSG-SM86 原生插帧)**: 直连 [sdli1995/dlssg_for_sm86](https://github.com/sdli1995/dlssg_for_sm86) (v0.4.0)
   - **模式 D (OptiScaler 跨卡转译)**: 直连 [optiscaler/OptiScaler](https://github.com/optiscaler/OptiScaler) (Nightly / Stable 双通道)
   - **ReShade HDR (RHI)**: 直连 [RankFTW/RHI](https://github.com/RankFTW/RHI) (RHI-2.8.7)
   - 点击【检查并同步最新版本】即可全自动异步并行检查与拉取全部 5 大核心组件并更新至系统 AppData 隔离缓存。

2. **升级现代化云端更新测速引擎 (对齐主工具箱更新模式)**
   - 全面引入 MirrorSpeedTestWorker 异步多线程并发测速架构，启动或测速时 0 卡顿；
   - 包含 **⚡ 智能测速优选**、**🚀 GH-Proxy 节点**、**⚡ GHFast 节点**、**🌐 GHProxy 节点**、**🔗 GitHub 官方直连** 等全套加速节点；
   - 实时测速徽章显示：精确展示每个节点的实时往返延迟（如 343ms · 极速、576ms · 良好、1044ms · 较慢、连接超时）；
   - **⚡ 智能测速优选**模式：自动实时锁定当前网络下延迟最低、最稳妥的可用节点，即开即下；
   - 新增【⚡ 重新测速】便捷按钮，随时一键重测并刷新全网延迟；
   - 支持多节点自动无缝故障转移 (Failover)，单节点波动时自动切换备用镜像，杜绝下载中断。

3. **插帧引擎模式顺位调优 (C/D 对调)**
   - **模式 C**：定为 **DLSSG-SM86 原生插帧**（RTX 20/30 系专享原生 DLSS-G + INT8 超分，无转译开销）；
   - **模式 D**：定为 **OptiScaler 全显卡跨架构转译**（FSR 3.1 / XeFG 跨卡桥接，支持全品牌显卡）。

4. **系统深度排毒与 C 盘瘦身 (NVIDIA Streamline 崩溃日志自动清理)**
   - 彻底解决由于游戏异常闪退被 NVIDIA Streamline 捕获而在 `%ProgramData%\NVIDIA\Streamline\` 偷偷累积数千个 `.dmp` 崩溃转储、吞噬数 GB 甚至数十 GB C 盘空间的顽疾；
   - 工具箱在执行游戏清理、卸载还原或一键排毒时，全自动深度穿透并清空对应游戏的全局 NVIDIA 崩溃快照，彻底守护 C 盘纯净与高速运行。

---

# 🎉 DM-Toolbox v1.3.5 · 深度集成 DLSSG-SM86 原生插帧 (RTX 20/30 系专享 6X 原生 DLSS-G 与 INT8 超分加速)

> **一站式全能硬件深度定制、游戏多帧生成补丁、Auto HDR 画质增强与 DLSS 实时监测综合工具箱**

### 🌟 v1.3.5 核心更新与优化

1. **深度集成 DLSSG-SM86 原生插帧 (模式 C · 告别跨卡转译开销)**
   - 全面引入开源硬核项目 [sdli1995/dlssg_for_sm86](https://github.com/sdli1995/dlssg_for_sm86) (v0.4.0)；
   - 专为 **NVIDIA RTX 20 系列 (Turing 架构 · SM75)** 与 **RTX 30 系列 (Ampere 架构 · SM86)** 显卡定制，彻底绕过架构硬件锁；
   - 无需经过 FSR 3.1 或 XeFG 跨卡转译桥接，直接在 Turing/Ampere 架构上运行官方 DLSS-G (v310.9.16) 原生运行库与定制加速内核。

2. **最高 6X 动态多倍插帧与 FG Lite 轻量化加速**
   - 原生支持 **2X / 3X / 4X / 6X** 多倍帧生成上限设置（默认 4X 出厂推荐，最高支持 DLSS 4.5 规格的 6X 极限插帧）；
   - 提供 4 级渲染一致性优化档位：
     - **档位 2 (出厂推荐)**：轻量加速内核，在真实 4K 场景下与原厂画面达到 PSNR 44-53dB 极高保真度；
     - **档位 1 (逐位一致)**：画面输出与官方原厂逐位 (Bit-Identical) 完全一致；
     - **档位 0 (原厂内核)**：完全原厂计算内核，不做额外加速；
     - **档位 3 (极速激进)**：最大幅度压榨 GPU 吞吐，大幅降低每帧插帧计算延迟；
   - 支持 **FG Lite (Preset C)**：轻量候选采样混合，相比标准插帧可**减少 32%~54% 的每帧 GPU 计算耗时**，大幅缓解低配卡显卡瓶颈。

3. **RTX 20/30 DLSS INT8 超分辨率硬件加速**
   - 针对 RTX 20/30 架构深度优化：一键开启 `[SuperResolution] Mode=On`；
   - 在游戏开启 DLSS 性能档 (Preset L) 或超级性能档 (Preset M) 时，自动将推理调度切换至定制高效 INT8 内核，GPU 耗时进一步降低 5%~24%。

4. **Smart-Auto 智能卡种自适应与 DLL 槽位隔离**
   - 智能推荐算法全面升级：检测到当前显卡为 RTX 20 系或 RTX 30 系时，优先自动推荐并选中 **模式 C (DLSSG-SM86 原生插帧)**；
   - 完备的 DLL 槽位隔离与状态清理：DLSS-G 采用 `version.dll` 独立代理，DLSS 5 (`app6_dlss5`) 采用 `dxgi.dll` 协同运行，实现两大核心丝滑共存、互不干扰；
   - 完美适配 6 种备用代理动态库（`winmm.dll`、`dbghelp.dll`、`dinput8.dll`、`dxgi.dll`、`d3d12.dll`），杜绝启动拦截与注入失败。

5. **游戏内外 INI 双向实时同步与 DLSS 5 控制台联动**
   - 完整支持桌面端与游戏内 `dlssg_sm86.ini` 的正向写入与反向读取；
   - `app6_dlss5` 联动控制面板新增模式 C 专属配置页，支持实时切换一致性档位、FG Lite 预设及 INT8 超分加速。

---

# 🎉 DM-Toolbox v1.2.14 · 全盘智能动态探测、3层穿透检索与全景注册表游戏发现系统

> **一站式全能硬件深度定制、游戏多帧生成补丁、Auto HDR 画质增强与 DLSS 实时监测综合工具箱**

### 🌟 v1.2.14 核心更新与优化

1. **全盘驱动器动态探测 (彻底解决其他电脑扫不到游戏的问题)**
   - 彻底摒弃写死单一盘符的旧逻辑，全面采用 Windows 原生 `GetLogicalDrives()` 与 `GetDriveTypeW()` API；
   - 智能自动枚举当前电脑连接的所有本地磁盘与可移动驱动器（C:、D:、E:、F:、G:... 等所有实际存在的盘符）；
   - 自动过滤网络共享盘（WebDAV/SMB）与虚拟光驱，彻底杜绝网络环境下的无响应与盘符遍历卡死。

2. **深度 3 层智能穿透扫描 (完美适配免安装/子分类/打包游戏)**
   - 全面支持向候选根目录检索最多 **3 层子目录**（`depth <= 3`）；
   - 完美识别多级归档与打包游戏结构（如 `E:\游戏\对马岛之魂 导演剪辑版\15172\V1053.7.0809.1937`、`E:\game\刺客信条：黑旗\30001`、`D:\game\RSI\StarCitizen\LIVE\Bin64` 等）；
   - 引入 **『游戏识别即早停（Early Stopping）』** 算法：一旦某一目录确认为游戏根目录，立即采集纳管并停止深入其内部的贴图、着色器与音视频等数万个资产文件，确保全库扫描秒级完成。

3. **主流平台与 Windows 卸载注册表全景联动**
   - 新增 Windows 官方卸载注册表联动挖掘（`HKLM` 64/32 位及 `HKCU` 的 `CurrentVersion\Uninstall`），自动发现通过标准安装程序安装的所有单机与联机大作；
   - 深度集成主流数字平台专属注册表：Steam（跨所有盘符 `libraryfolders.vdf` 解析）、Epic Games（`Manifests`）、GOG Galaxy、Ubisoft Connect（育碧）、EA Desktop（EA）、腾讯 WeGame 以及网易游戏专有注册表（如 `yysls` / `wwm` 燕云十六声）。

4. **主执行文件智能定位与游戏名称向上回溯解析**
   - 主程序侦测深度适配虚幻引擎（`Binaries/Win64`、`Binaries/Win64r`）、REDengine（`bin/x64`）、星际公民（`Bin64`）、消逝的光芒（`ph/work/bin/x64`）等业界通用可执行文件存放目录；
   - 智能排除多卷分卷压缩包文件（`.part01.exe`）及启动器/反作弊子进程；
   - 游戏名称自适应解析：当可执行文件位于纯数字代号（如 `30001`）或版本号（如 `V1.05`）等子文件夹中时，自动向上回溯定位真实游戏名称，UI 展示整洁美观。

---


# 🎉 DM-Toolbox v1.2.13 · 智能多镜像测速优选、自动故障转移与防闪退安全架构

> **一站式全能硬件深度定制、游戏多帧生成补丁、Auto HDR 画质增强与 DLSS 实时监测综合工具箱**

### 🌟 v1.2.13 核心更新与优化

1. **智能多镜像测速优选与状态显化 (彻底解决镜像源连不上问题)**
   - 引入多线程并行测速探针（`MirrorSpeedTestWorker`），弹窗开启后自动对各加速节点并发测速；
   - 默认采用 **『⚡ 智能测速优选』** 模式，自动识别并锁定当前网络下延迟最低、连通性最佳的节点（如 `GH-Proxy 极速节点 380ms`）；
   - 在选择下拉框中实时显示各节点延迟徽章（如 `🚀 GH-Proxy 节点 (385ms · 极速)`、`🔗 GitHub 官方直连 (750ms)`、`🔴 连接超时`）；
   - 提供独立 **『⚡ 重新测速』** 按钮，支持随时手动刷新各节点链路状态。

2. **下载链路自动无缝故障转移 (Failover)**
   - 下载下载包时支持自动多节点故障转移：若当前节点在握手、传输过程中遇到网络阻断、403、502 或超时，后台将**自动无缝切换至下一个最快可用备用源**继续尝试，绝不卡死，确保下载必达。

3. **彻底根除取消更新引发的闪退问题**
   - 修复了此前在更新下载过程中点击“取消下载”或关闭窗口时，后台 QThread 套接字未安全释放以及向已销毁 Qt 对象派发信号导致的程序异常崩溃（闪退）；
   - 增强了线程生命周期安全闭环，点击“取消下载”时平滑安全中断并恢复交互界面，不再弹出误导性错误警报。

---

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
