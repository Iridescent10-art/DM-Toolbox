# 🎉 DM-Toolbox v1.3.26 · 全新自定义壁纸与毛玻璃可读性保护系统 / 终末地 ACE 防拦截加固 / 12线程极速打包

> **一站式全能硬件深度定制、游戏多帧生成补丁、Auto HDR 画质增强、JXR HDR 转换器、DLSS 5 神经重构与 DLSS 实时监测综合工具箱**

### 🌟 v1.3.26 核心更新与优化

1. **全新自定义壁纸系统与三层毛玻璃可读性保护管线**
   - **严格遵守绿色便携存储红线**：程序运行目录 0 写入，配置与缓存 100% 解耦存放于 `%APPDATA%/ToolboxMaster/`。
   - **三层视觉渲染管线**：
     - **底层壁纸绘制层**：`AspectFill` 等比缩放居中裁剪，主流分辨率预缩放（最高 2560×1440）与预高斯模糊缓存（PIL 硬件优化），窗口拖拽与缩放 0 掉帧；
     - **中层主题保护遮罩层**：深色模式遮罩 `rgba(18, 18, 22, 0.68)`、卡片底色 `rgba(32, 34, 40, 0.80)`、微光边框 `1px solid rgba(255, 255, 255, 0.08)`；浅色模式遮罩 `rgba(242, 244, 248, 0.72)`、卡片底色 `rgba(255, 255, 255, 0.80)`、细腻边框 `1px solid rgba(0, 0, 0, 0.06)`，彻底解决复杂背景下小字说明、版本号与状态标签的可读性问题；
     - **顶层交互保真层**：绿色主按钮（`#69db9b`）、状态标签与标题保持 100% 不透明高保真展示。
   - **标题栏统一入口与全功能设置面板 (DMWallpaperDialog)**：
     - 标题栏深浅切换按钮左侧新增 `🖼️`（自定义壁纸）入口；
     - 支持直接选择导入 `PNG / JPG / WEBP / BMP`，并集成 Windows 原生 WIC 模块直接支持 `.jxr` HDR 截图导入并自动映射为 SDR 壁纸；
     - 提供背景模糊度（0~40px）、深色遮罩浓度（20%~95%）、浅色遮罩浓度（20%~95%）、卡片透明度（50%~100%）四维滑块与实时预览；
     - 支持三种生效范围切换：全局统一壁纸 / 仅主程序生效 / 允许各子软件独立设置壁纸；
     - 支持一键恢复纯色默认主题。
   - **源文件删除强容错**：导入壁纸后即使手动删除桌面上的原始图片，软件依然正常从 AppData 缓存加载与重模糊，零报错零崩溃。
   - **全部 6 个子软件接入与跨窗口/跨进程实时热更新**：主工具箱与全硬件配置大师、DLSS多帧生成补丁、Auto HDR 管理器、超分与插帧指示器、JXR转换器、DLSS 5 插件一键注入全部无缝支持壁纸与毛玻璃，文件修改防抖同步（100ms）。
   - **既有功能联动**：“💾 缓存占用”自动包含壁纸缓存统计；“🧹 还原与清理”一键清理未引用壁纸历史缓存并重置出厂配置。

2. **《明日方舟：终末地》与 ACE 反作弊环境 DLSS 5 挂载加固**
   - 彻底清除 OptiScaler 代理冲突（避免 NTDLL 堆损坏 `0xC0000374`），纯净挂载最新 ReShade 6.8；
   - 注入配置硬编码禁用 OpenGL 拦截（`[INSTALL] HookOpenGL=0`），彻底杜绝由于 `cri_ware_unity.dll` 导入 OpenGL 引发 NVIDIA 驱动 `nvoglv64.dll` 崩溃闪退。

3. **Inno Setup 打包流水线 12 核心 CPU 多线程全开加速**
   - 启用 Inno Setup 原生多线程块并行压缩指令 `LZMANumBlockThreads={cpu_count}` 与 64 位独立压缩进程 `LZMAUseSeparateProcess=yes`；
   - 榨干全部 CPU 逻辑核心算力，彻底解决单线程打包耗时漫长的问题，构建速度大幅提升数倍。

---

# 🎉 DM-Toolbox v1.3.20 · DLSS 5 默认挂钩点调整为「之后」(Upscaled) / 彻底根治 4K+多帧生成 GPU 驱动挂起 (0x887A0006)

> **一站式全能硬件深度定制、游戏多帧生成补丁、Auto HDR 画质增强、JXR HDR 转换器、DLSS 5 神经重构与 DLSS 实时监测综合工具箱**

### 🌟 v1.3.20 核心更新与优化

1. **DLSS 5 出厂默认挂钩点调整为「之后 (Upscaled · 超分之后)」**
   - **深挖 GPU 挂起根因 (0x887A0006 DXGI_ERROR_DEVICE_HUNG)**：
     - 用户崩溃转储（`dlss5-nr-crash-*.txt`）深度剖析确认：在 4K (3840x2160) + HDR10 + 3倍插帧生成（FG 3x）的极致压力下，若 DLSS 5 挂在 `Present`（呈现阶段），DLSS 5 会对包括合成插帧在内的全部 5000+ 帧画面执行强行重构；
     - 此时整个游戏进程显存申请高达 17.5 ~ 18 GB（远超 8GB 显卡上限），4K 纹理被迫走 PCIe 慢速内存交换，导致计算着色器流水线死锁超过 13.2 秒（`inside_age_ms=13264`），触发 Windows TDR 超时保护强制重置 GPU 驱动引发崩溃；
   - **全面切换默认至安全的「之后 (Upscaled)」**：
     - 将注入引擎（`injector.py`）、预设模板（`My look.ini`）以及配置同步系统（`ini_sync.py`）中的出厂默认挂钩点全面锁定为 `NRHookPoint=0`（`HookStage=0`, `NRPresentAlways=0`）；
     - **时序与开销革命性优化**：渲染管线严格解耦为 `游戏渲染 -> DLSS 5 神经重构 (仅针对 1080p 超分前画面) -> 多帧生成 (FG 3x) -> 呈现`；
     - 重构计算耗时从 5.2 ms 骤降至 1~2 ms，显存占用暴降 60% 以上，彻底根治 0x887A0006 显卡悬挂与画面卡死。

2. **全量自动化测试套件 100% PASS**
   - 107/107 项 pytest 单元测试与全链路共存测试全部通过，零回归。

---

# 🎉 DM-Toolbox v1.3.19 · 彻底修复 JXR 转换器拖拽红色禁止标志 / DLSS 5 默认显存缓冲调整为最小 (Minimal)

> **一站式全能硬件深度定制、游戏多帧生成补丁、Auto HDR 画质增强、JXR HDR 转换器、DLSS 5 神经重构与 DLSS 实时监测综合工具箱**

### 🌟 v1.3.19 核心更新与优化

1. **彻底解决 JXR HDR 转换器拖拽文件显示 Windows 红色禁止标志（UIPI 权限穿透与 RevokeDragDrop）**
   - **深挖根因 (Root Cause Analysis)**：
     - 在 WPF 原生机制中，一旦窗口或子控件标记了 `AllowDrop="True"`，WPF 会自动在底层向操作系统注册 OLE `IDropTarget` 接口；
     - 当主工具箱以管理员权限运行（High Integrity Level）时，标准权限的 Windows 资源管理器（`explorer.exe`，Medium Integrity Level）尝试向其拖拽文件时，受 Windows **UIPI（用户界面特权隔离）** 与 COM 安全机制限制，跨权限 COM 传输会被操作系统直接拦截，导致 Explorer 判定拖拽目标无效，从而显示红色的“禁止/Stop”鼠标光标，并且永远不会触发回退机制；
   - **彻底修复方案**：
     - 彻底清理 XAML 中残留的 `AllowDrop="True"`，杜绝 WPF 重复装载 OLE 接收器；
     - 窗口加载第一时刻显式调用 `ole32.dll!RevokeDragDrop(hwnd)` 撤销 WPF 默认的 OLE 拦截器；
     - 通过 `shell32.dll!DragAcceptFiles(hwnd, true)` 开启原生文件接收，并调用 `ChangeWindowMessageFilter` / `ChangeWindowMessageFilterEx` 完整穿透 `WM_DROPFILES`（0x0233）、`WM_COPYDATA`（0x004A）与 `WM_COPYGLOBALDATA`（0x0049）；
     - 将文件路径提取升级为宽字符 Unicode 原生 `DragQueryFileW`，完美支持带中文、特殊字符和空格的截图路径；
     - 重新编译生成全自包含单文件版 `apps/app5_jxr/JxrConverter.exe`（66.6 MB），支持单张、多选图片及包含子目录的文件夹无感拖拽。

2. **DLSS 5 注入默认显存缓冲参数调整为最小（Minimal）**
   - **内核规范与参数对齐**：
     - RenoDX 神经重构内核对 `NRVramBuffering` 参数有着严格的分级机制：`0: Full`（全量缓存全部挂钩路由，占显存最大）、`1: Reduced`（仅缓存当前路由）、`2: Minimal`（最小显存模式，仅分配当前挂钩点及 Pass 必需显存，空闲时立即释放）；
   - **全局默认值更新与自愈**：
     - 全面更新注入引擎（`injector.py`）、预设模板（`My look.ini`）以及配置协同同步器（`ini_sync.py`），将默认参数锁定为 `NRVramBuffering=2`（并同步对齐 `VramBuffering=2` 与 `DirectNeuralRenderingVramBuffering=2`）；
     - 在注入和同步时自动应用此参数，大幅降低 DLSS 5 对显存的额外占用，彻底消除 2K/4K 高画质或光追开启下的爆显存与显存溢出掉帧。

3. **全量自动化测试套件 100% PASS**
   - 107/107 项 pytest 测试用例全部通过，零回归。

---

# 🎉 DM-Toolbox v1.3.18 · 彻底解决 ReShade LoadFromDllMain 误载 DLSS 5 导致的 1114 初始化失败与 D3D12 启动闪退

> **一站式全能硬件深度定制、游戏多帧生成补丁、Auto HDR 画质增强、JXR HDR 转换器、DLSS 5 神经重构与 DLSS 实时监测综合工具箱**

### 🌟 v1.3.18 核心更新与优化

1. **彻底解决《燕云十六声》等游戏同时注入 DLSS 5 与多帧生成启动闪退（`0xc0000005`）的问题**
   - **深挖根因 (Root Cause Analysis)**：
     - 逆向分析崩溃转储（Minidump）确认，此前在 `ReShade.ini` 的 `[ADDON]` 配置中，错误地将 `renodx-dlss5-v11.9.addon64` 写入了 `LoadFromDllMain`；
     - ReShade 在 `dxgi.dll` 的 `DllMain` 执行期间受 Windows 操作系统的 `LoaderLock`（加载器锁）保护。由于 DLSS 5 插件（8.7 MB）链接了 NGX、D3D12 及复杂的多线程运行时，在 `DllMain` 中加载必然触发 Windows 安全机制失败，报错 `1114 (ERROR_DLL_INIT_FAILED)`；
     - 该初始化失败污染了随后的 DirectX 12 渲染管线状态，导致游戏启动片头视频解码器（`mfcore.dll` Media Foundation）在调用 `D3D12.dll + 0x10538` 时解引用空指针发生 `0xc0000005` 内存访问违规，从而在启动前几秒直接闪退崩溃。
   - **彻底根治与自愈修复**：
     - 明确架构分工：`LoadFromDllMain` 严格仅供必须极早拦截显卡能力的模式 B（`renodx-mfgunlock.addon64`）使用，DLSS 5 插件必须在离开 `DllMain` 后由 ReShade 标准扩展管线安全装载；
     - 全面修复 `injector.py` 与 `ini_sync.py`：严禁任何 `renodx-dlss*.addon64` 进入 `LoadFromDllMain`，并在每次注入和同步时自动清洗过滤历史残留的非法挂载项，实现全自动无感自愈。
   - **实机运行长效验证**：
     - 在《燕云十六声》（Win64r/yysls.exe）、《赛博朋克2077》、《巫师3》等真实游戏环境下进行单注入与双注入（DLSS 5 + 模式 C / 模式 A）实测，连续稳定运行 > 25 秒，流畅渲染全屏 4K 画面，片头视频与游戏世界加载 100% 正常，0 崩溃报错！

2. **全量自动化测试套件 100% PASS**
   - 107/107 项 pytest 单元测试与共存集成测试全部通过，保障全模块零回归。

---

# 🎉 DM-Toolbox v1.3.13 · 解决 Cyberpunk 2077 依赖缺失报错 / 完善 ReShade Addon 挂载与全量测试闭环

> **一站式全能硬件深度定制、游戏多帧生成补丁、Auto HDR 画质增强、JXR HDR 转换器、DLSS 5 神经重构与 DLSS 实时监测综合工具箱**

### 🌟 v1.3.13 核心更新与优化

1. **解决 Cyberpunk 2077 等 CDPR 游戏缺少 XeSS/XeFG 运行库导致启动报错的问题**
   - **根因分析**：Cyberpunk 2077（v2.5+ / 3.0）主程序 Cyberpunk2077.exe 存在针对 libxell.dll、libxess.dll 与 libxess_fg.dll 的静态 PE 导入。若用户运行清理或目标目录缺失这三项动态链接库，Windows PE 加载器将在进入游戏入口前直接弹出系统错误弹窗阻断进程启动；
   - **解决与自愈**：深度提取并补齐 CDPR 官方认证的完整 XeSS/XeFG 运行时套件（libxell.dll、libxess.dll、libxess_fg.dll、igxess.dll），经 PE 导入表与 ctypes 动态探测验证 100% 匹配无缺失；
   - **消除双重 Hook 冲突**：彻底排查并清理历史遗留的 
rchain_nvngx.dll、旧版 RTX40MFG 与重复 ersion.dll，确保 RTX 40 系显卡在 Cyberpunk 2077 中享受纯净的 DLSS 3 原生帧生成与 DLSS 5 神经重构协同。

2. **ReShade 6.8 LoadFromDllMain 严格白名单与智能自愈挂载**
   - 彻底修复历史清理逻辑对 
enodx-dlss*.addon64 的误伤，增加目标目录存在性动态校验与自动登记；
   - 杜绝 LoadFromDllMain=1 等非字符串合法值导致的 ReShade 内核 126 报错，确保 DLSS 5 扩展插件在游戏启动第一帧被可靠加载。

3. **104 项全矩阵自动化测试 100% PASS**
   - 全面覆盖硬件定制、多帧生成模式 A/B/C/D、DLSS 5 神经重构、JXR 批量转换与多模式共存避让逻辑，保障全平台稳定交付。

---

# 🎉 DM-Toolbox v1.3.12 · 彻底修复多帧生成与 DLSS 5 共存闪退 (0x887A0006) / 修复分辨率异常映射 4K 全屏

> **一站式全能硬件深度定制、游戏多帧生成补丁、Auto HDR 画质增强、JXR HDR 转换器、DLSS 5 神经重构与 DLSS 实时监测综合工具箱**

### 🌟 v1.3.12 核心更新与优化

1. **彻底修复多帧生成（Mode A 3x / Mode B / Mode C / Mode D）与 DLSS 5 (RenoDX) 同时注入进入游戏闪退 (`0x887A0006 DXGI_ERROR_DEVICE_HUNG`)**
   - **深挖 GPU 崩溃根因**：根据实机崩溃转储诊断，在 Present 呈现阶段挂钩（`NRHookPoint=2` 且 `NRPresentAlways=1`）时，DLSS 5 错误劫持了由多帧生成器（DLSS-G 插帧队列 `nv.sl.dlss_g.cmdQ.pacer`）合成的插值帧。由于插值帧在管线中缺乏 G-buffer 深度与历史矢量缓冲，导致 D3D12 命令列表死锁挂起引发显卡驱动崩溃；
   - **协同渲染管线重构**：全面改写注入引擎与预设配置，将 DLSS 5 挂钩点出厂默认及协同规则锁定为 `NRHookPoint=0` (Upscaled / 超分之后)。渲染管线严格遵循 `游戏渲染 -> DLSS 超分 -> DLSS 5 神经重构 -> 多帧生成 (2x/3x/4x) -> 画面呈现` 的时序解耦执行，DLSS 5 绝不触碰多帧生成的起搏队列；
   - **全模式协同防崩保证**：无论用户开启模式 A (通用多帧 3x/4x)、模式 B (Ada FG 解锁)、模式 C (XeSS 2.0 / FSR 3.1) ，只要检测到与 DLSS 5 共存，工具箱自动锁定安全的 Upscaled 挂钩点并禁用 Present 强开，彻底根治 0x887A0006 设备悬挂。

2. **彻底解决 DLSS 5「匹配游戏」分辨率变为全部分辨率（4K 3840x2160）导致 15.2 ms 超高耗时与掉帧的问题**
   - **根因分析**：在 Present 挂钩点下，画面已完成全屏呈现缩放，RenoDX 无法捕获原始 DLSS 缩放输入尺寸，从而兜底按照 4K 交换链全屏尺寸执行神经重构，导致重构耗时暴涨至 15.2 ms 并造成显存枯竭；
   - **修复方案**：在 `Upscaled` 挂钩点下，`NRFollowInputRes=1`（匹配游戏）精准锚定 DLSS 内部超分渲染分辨率（如 1080p/1440p），并在预设中精准匹配 50% 轴比采样，彻底恢复毫秒级超低延迟重构，告别显存爆满与帧率骤降。

3. **存量游戏与本地预设智能自愈升级**
   - 注入器启动与执行注入时，自动扫描目标游戏目录与本地 AppData 预设缓存（`ReShade.ini`、`ReShadePreset.ini`、`RenoDX/DLSS5/Presets/*.ini`）；
   - 一键清理历史冲突的 `NRHookPoint=2`、`NRPresentAlways=1` 与 4K 全屏污染配置，无感自愈迁移至稳定的 `Upscaled` 模式与合法 Addon 配置。

---

# 🎉 DM-Toolbox v1.3.11 · 修复手动添加游戏报错 / 智能识别 64 位主引擎与精准注入路径 (2077/巫师3等)

> **一站式全能硬件深度定制、游戏多帧生成补丁、Auto HDR 画质增强、JXR HDR 转换器、DLSS 5 神经重构与 DLSS 实时监测综合工具箱**

### 🌟 v1.3.11 核心更新与优化

1. **彻底修复手动添加游戏报错 (`'GameScanner' object has no attribute 'get_game_info_from_exe'`)**
   - 在 `GameScanner` 核心嗅探器中全面实现 `get_game_info_from_exe(file_path)` 与 `scan_games()` 兼容方法；
   - 彻底解决 DLSS 5 插件及多帧生成插件中手动点击选择可执行文件时的异常弹窗，支持选择主程序或启动器时秒级智能解析。

2. **64 位真实游戏主程序嗅探与注入目录精准纠偏 (解决 2077 / 巫师 3 / 大镖客 2 注入失效问题)**
   - **智能识别根目录启动器**：针对赛博朋克 2077、巫师 3、荒野大镖客 2 等将 `REDprelauncher.exe`、`PlayRDR2.exe` 置于根目录的游戏，嗅探器自动识别启动器伪装，深度穿透并优先绑定真实 64 位 DirectX 12 渲染引擎（如 `bin/x64/Cyberpunk2077.exe`、`bin/x64_dx12/witcher3.exe`、`RDR2.exe`）；
   - **精确注入路径对齐**：调整扫描器标准子目录判定权重（`bin/x64` > `bin/x64_dx12` > `Binaries/Win64` > ... > 根目录），彻底消除将 `dxgi.dll`、`ReShade.ini`、`nvngx_dlssnr.dll` 误注入到游戏外层根目录导致 DLSS 5 / 插帧不生效的问题；
   - **历史缓存智能自愈升级**：`GameCacheManager` 启动时自动遍历检测现有游戏缓存，将陈旧的启动器记录无感自愈迁移至真实二进制主程序与注入目录，保证存量游戏开箱即用。

---

# 🎉 DM-Toolbox v1.3.10 · JXR HDR 转换器支持直接拖拽图片与多选图片批量拖入 / UIPI 提权穿透

> **一站式全能硬件深度定制、游戏多帧生成补丁、Auto HDR 画质增强、JXR HDR 转换器、DLSS 5 神经重构与 DLSS 实时监测综合工具箱**

### 🌟 v1.3.10 核心更新与优化

1. **JXR HDR 转换器全窗口直接拖拽与多选图片批量拖入支持**
   - **UIPI 提权消息穿透**：当主工具箱以管理员权限运行时，Windows 安全隔离机制 (UIPI) 会默认拦截标准权限资源管理器（explorer.exe）的拖拽。新版在 `JxrConverter` 窗口底层引入 `ChangeWindowMessageFilterEx` 与 `DragAcceptFiles`，彻底突破权限屏障，拖拽即刻响应；
   - **全窗口区域与数据网格双通道捕获**：引入 WPF `PreviewDragOver` 与 `PreviewDrop` 隧道事件，并在 `RootBorder` 与列表网格全局开启 `AllowDrop`，无论是拖拽到大面积空白列表、设置卡片还是窗口任意角落，均能 100% 稳定捕获；
   - **格式扩展与多选智能识别**：支持直接单张或批量多选拖入 `.jxr`、`.wdp`、`.hdp`、`.png`、`.jpg`、`.jpeg`、`.bmp`、`.tiff` 等常见格式图片，同时支持拖拽整个文件夹自动深度扫描导入；
   - **优雅空列表提示**：列表为空时展示直观的「📥 直接把图片拖入此处（支持单张 / 多选图片批量拖入）」指引遮罩。

---

# 🎉 DM-Toolbox v1.3.9 · 模式 A 支持自定义 DLSS-G 模型 (默认锁定 Model C) & 修复游戏内无法保存预设

> **一站式全能硬件深度定制、游戏多帧生成补丁、Auto HDR 画质增强、DLSS 5 神经重构与 DLSS 实时监测综合工具箱**

### 🌟 v1.3.9 核心更新与优化

1. **解决游戏内覆盖层报错「无法保存预设选择」**
   - 经逆向反汇编 Dashdogy v1.6.1 验证器发现：当 `mode == "follow"` 时，验证算法严格要求配置中存在 `followGame == True`，缺失时验证函数校验失败并返回 0，导致覆盖层保存被中断、弹出「无法保存预设选择」报错并回退到预设 B；
   - 现已修复配置序列化逻辑，生成 `RTXMFG-Universal.json` 时始终完整写入 `"followGame": true`，彻底消除覆盖层报错，游戏内调参保存畅通无阻。

2. **解决多帧生成无法设定模型 & 未跟随 NVIDIA App 设定为 Model C 的问题**
   - 深入逆向分析实机日志与汇编：Dashdogy 在读取驱动层预设缓存时若遇到 `dlssgPreset == 0`（跟随游戏），因未能成功解析驱动缓存分支会主动触发降级逻辑，闭锁至 Model B 并提示版本不匹配；
   - 模式 A (通用独立多帧) 面板全新引入「🎯 DLSS-G 帧生成模型」快捷配置项（支持 Model C、自动/跟随驱动、Model B、Model A），出厂默认锁定为 **Model C**；
   - 注入时自动将 `dlssgPreset: 3` 与 `followGame: true` 写入 `RTXMFG-Universal.json`，并将 `DLSSGPreset=C` 写入 `mfg_unlocker.ini`，彻底消除游戏内版本警告，直通 NVIDIA 官方 Model C 帧生成内核；
   - 完善反向同步解析与状态回滚清单，支持双向读取与干净卸载。

3. **修复 DLSS 5 目标游戏下拉框切换后主程序与目标目录不联动刷新 & 跨软件实时同步问题**
   - 根因分析：在 `app6_dlss5/app.py` 中，切换下拉框事件接收的 `itemData` 曾因命名空间双重导入差异导致 `isinstance(data, GameInfo)` 校验失败，使得切换游戏后 `selected_game` 未更新，路径显示被锁死在上一款游戏（表现为下拉框切到新游戏后下方主程序与目标目录不刷新）；
   - 现已重构事件监听器，使用属性解耦校验，并在窗口激活与后台增加静默同步机制，与二号软件 (app2_mfg) 实现双向无感同步，下拉切换即刻刷新；
   - 编写专项自动化测试 `tests/test_dlss5_game_dropdown_sync.py`，验证路径刷新与双向缓存同步。

4. **自动化测试与质量保障**
   - 新增 `tests/test_mode_a_dlssg_preset.py` 与 `tests/test_dlss5_game_dropdown_sync.py`；
   - 全套回归测试 100% 验证通过。

---

# 🎉 DM-Toolbox v1.3.8 · 彻底修复「模式 C (OptiScaler / XeSS 多帧生成) + DLSS 5 神经重构」同时注入闪退

> **一站式全能硬件深度定制、游戏多帧生成补丁、Auto HDR 画质增强与 DLSS 实时监测综合工具箱**

### 🌟 v1.3.8 核心更新与优化

1. **闪退根因一：两序注入竞态（先模式 C 后 DLSS 5 时代理被顶掉）**
   - 旧逻辑在注入 DLSS 5 时无条件把 ReShade 覆盖到 `dxgi.dll`，而模式 C 独立部署时 OptiScaler 正占用该槽位，结果目录里只剩 `OptiScaler.ini` + `libxess_fg.dll` 的“半套配置”，代理被彻底顶掉；
   - 新增统一共存路由 `apps/app2_mfg/core/coexistence.py`：先按游戏 PE 导入表把 OptiScaler 迁移到 `winmm.dll > version.dll > dinput8.dll`，再让 ReShade 占用 `dxgi.dll`；
   - 无论先注入模式 C 还是先注入 DLSS 5，最终目录布局完全一致；代理若已被旧版本覆盖丢失，会自动从组件缓存补回。

2. **闪退根因二：NVNGX 调用链被切断（本次闪退的直接原因）**
   - 旧共存配置写入 `[DLSS] Enabled=false` + `[Upscalers] Dx12Upscaler=none`：前者让 OptiScaler 不再把 DLSS 调用转发给原始 nvngx，而 DLSS 5 的神经重构恰好挂在这条调用链上；后者并不是合法的 upscaler 取值；
   - 游戏随后拿到空的 DLSS Feature 句柄，进入场景即 `0xC0000005` 访问冲突；
   - 现修正为 `Dx12Upscaler=dlss` + `[DLSS] Enabled=true` + `RenderPresetOverride=false`：DLSS 直通、DLSS 5 接管超分与神经重构、OptiScaler 只接管 `DLSS-G → XeFG` 插帧，互不抢夺。

3. **闪退根因三：XeFG 键位写错节区 + 误关 ImGui 菜单导致多帧生成失效**
   - `PreserveSwapChain` 属于 `[FrameGen]`，旧版本写进 `[XeFG]` 被 OptiScaler 静默忽略；
   - `[Menu] OverlayMenu=false` 会让 OptiScaler 关闭全部 FG 功能（官方模板明确说明），旧版本为“防 ImGui 崩溃”关闭它，等于直接关掉 XeFG；
   - 现键位归位 `[FrameGen]`，并保留 `OverlayMenu=true`，只关闭开屏横幅与 FPS 叠加，不再牺牲插帧能力。

4. **闪退根因四：fakenvapi 与 DLSS 5 争夺 NVAPI**
   - fakenvapi 会伪造整套 NVAPI 设备，而 `nvngx_dlssnr.dll` 需要按真实 GPU 选择神经重构内核；
   - 旧逻辑只在 RTX 40+ 清理，其余显卡仍会部署 → 运行库按假 GPU 选内核，首帧重构后崩溃；
   - 现在只要检测到 DLSS 5 就一律清理 `fakenvapi.dll / fakenvapi.ini / fakenvapi.log`，并回落到游戏原生 DLSS-G 作为 XeFG 输入源。

5. **稳定性加固与自检**
   - 单一 ReShade 宿主：注入前清理 `ReShade64.dll`、`d3d12-ReShade64.dll`、`dxgi.dll.reshade_bak`，避免双份 D3D12 Hook 在设备销毁时崩溃；
   - 半残状态自愈：检测到 `OptiScaler.ini` 存在但代理缺失时自动补回 OptiScaler 代理；
   - 修正 `nvngx_dlssnr.dll` 架构指纹识别（263MB 的 RTX 20/30/40 模型不再被误判为 RTX 50）；
   - 模式 C 面板文案与真实注入行为对齐（共存时自动让出 `dxgi.dll`）。

6. **修复「游戏内 XeFG 灰显 OFF / Requires disabling dilated motion vectors」**
   - 《燕云十六声》等 Streamline 游戏向 DLSS 传入的是 Dilated（低分辨率膨胀）运动矢量，`libxess_fg` 的预初始化检查会直接拒绝，表现为游戏内 XeFG 开关灰显、`Current XeFG state: OFF`；
   - 现已自动写入 `[XeFG] IgnoreInitChecks=true` 豁免该预检查（同时覆盖“独占全屏 / 仅支持 HDR10”两类误判），注入后 XeFG 面板可正常切到 Frame Gen；
   - 注意：豁免后仍需在游戏【画面设置 → DLSS 帧生成】中打开帧生成，`Frame Generation (Streamline FG Inputs)` 才会从 `ACTIVATE FG` 变为激活状态并开始插帧。

7. **重新接通 dashdogy Universal MFG Unlocker：XeFG 3X/4X 多帧解锁**
   - 上一版为避免与 DLSS 5 的 MinHook 冲突，共存态下移除了 `OptiScaler/plugins/MFGUnlocker.asi`，结果 XeFG 被 `libxess_fg` 硬限制在 2X（实机日志 `Max supported interpolations: 1`）；
   - 现恢复 `MFGUnlocker.asi`（dashdogy v1.6.1，明确支持 “XeSS multi-frame generation needs OptiScaler, with XeFG as FG output”），并在共存态写入 `LoadAsiPlugins=true`；同时不再把 `[XeFG] InterpolationCount` 预先压回 2X，让解锁后的 OptiScaler 真正拿到 3X/4X 请求；
   - 模式 C 面板新增「🚀 启用 MFG-Unlocker 多帧解锁」开关，**出厂默认开启、倍率默认 3X**；旧配置会做一次性迁移（`preset_schema_version=2`），保证升级后直接是「解锁 + 3X」；若某些游戏与 DLSS 5 在启动阶段出现 Hook 冲突，可取消勾选退回 2X 稳定档，再重新注入即可。

8. **修复「运行一两分钟后闪退」——显存伪装导致的 GPU TDR**
   - 实机日志证据：`NR-VRAM now process_local=14.6 GB budget=11.68 GB` + `Device removal reason is DXGI_ERROR_DEVICE_HUNG`，Windows 事件 `nvlddmkm 153`；
   - 根因是 **App1 把 12GB 显卡伪装成 32GB 显存**：游戏按 32GB 预算分配纹理，实际超过 12GB 后驱动挂起（TDR），与 DLSS 5 / XeFG 本身无关；
   - 现在 DLSS 5 注入与模式 C 注入完成后都会做显存伪装预检，发现「伪装显存 > 物理显存」时直接给出警告，并提示到 App1 把显存改回「保持原始」或一键还原官方配置。


10. **DLSS 5 界面排版修复 + 专属图标**
   - 旧版窗口内容的最小宽度被几处**未换行的长文本**撑到约 1660px（副标题、架构单选、说明块、完整游戏路径），980px 窗口下右侧被直接裁掉；
   - 现在副标题/卡片标题/说明块全部自动换行，架构单选改为短标签+悬浮提示，游戏下拉框不再按最长游戏名撑宽，长路径在每个反斜杠后可断行；横向滚动条改为“需要时出现”兜底，980px / 1120px 下横向溢出均为 0；
   - 重新绘制并内置 **DLSS 5 专属图标**（512px PNG + 16~256px 多尺寸 ICO，神经网络“5”+ 多帧叠层），修复旧文件损坏导致标题栏/任务栏图标为空的问题；图标生成脚本 `apps/app6_dlss5/assets/create_dlss5_icon.py` 可重复执行；
   - 底部操作栏不再“贴边”：底栏会按按钮实际高度自动增高（34px 按钮 → 52px 底栏），按钮下方保留 11px 留白，右下角缩放手柄也不会再压住按钮；
   - 默认窗口尺寸调整为 1120×820（仍会按屏幕 92% 自动收敛）。

11. **自动化验证**
   - `tests/test_coexistence_dlss5_mfg.py` 扩充为 8 组硬性断言：两序注入一致性、代理迁移、单 ReShade 宿主、fakenvapi 净化、半残状态自愈、模型架构指纹、重复注入幂等、卸载无残留；
   - 新增 `tests/test_v138_vram_and_xefg_cap.py`：显存伪装检测、XeFG 2X 硬件上限提示、MFGUnlocker 3X 解锁绕过、出厂默认「解锁 + 3X」；
   - 新增 `tests/test_v138_mode_d_mfg_diagnosis.py`：Mode D 插件 MFG 能力识别与日志回显；
   - 新增 `tests/test_v138_dlss5_ui_assets.py`：图标 PNG/ICO 有效性、长路径可断行、底栏为按钮自动留白；
   - 全量测试 **91 项全部 PASS**。

---

# 🎉 DM-Toolbox v1.3.7 · 深度换装 RenoDX DLSS 5 v11.9 旗舰神经渲染引擎与旧版彻底净化

> **一站式全能硬件深度定制、游戏多帧生成补丁、Auto HDR 画质增强与 DLSS 实时监测综合工具箱**

### 🌟 v1.3.7 核心更新与优化

1. **全面升级 RenoDX DLSS 5 官方最新 v11.9 旗舰版架构**
   - 彻底废除并删除旧版 3.3MB `renodx-dlss.addon64` 及相关遗留插件；
   - 正式全面搭载 `renodx-dlss5-v11.9.addon64`（体积 8.32MB），规范化命名为 `renodx-dlss5.addon64`；
   - 深度集成 DLSS-G 帧生成与 DLSS SR 超分调度优化器，支持全显卡架构（RTX 20/30/40/50 及全品牌卡）下的神经重构、全局光照与高动态 HDR 渲染；
   - 包含多语言原生界面与底层自适应兼容策略，大幅提升稳定性与画质表现。

2. **多版本插件冲突【彻底主动净化引擎】**
   - 在部署与注入新版 DLSS 5 时，新增强制前置清理机制，自动彻底抹除游戏目录中残留的旧版插件（`renodx-dlss.addon64`、`renodx-dlss-ShortFuse-261017汉化版.addon64`、`lecram-dlss5-beta10.addon64`、`dlss5-nr.addon64` 等）；
   - 杜绝因 ReShade 重复加载多个不同版本的 DLSS 5 Addon 导致的崩溃、冲突或报错；
   - 状态清理与一键还原模块同步将旧版与新版全部纳入无残留卸载清单。

---

# 🎉 DM-Toolbox v1.3.6 · 云端组件库智能测速优选与插帧+RHI全栈热更新



> **一站式全能硬件深度定制、游戏多帧生成补丁、Auto HDR 画质增强与 DLSS 实时监测综合工具箱**



### 🌟 v1.3.6 核心更新与优化



1. **插帧全后端 (Mode A/B/C/D) 与 RHI 模组全栈直连 GitHub 官方仓库**

   - **模式 A (Standalone)**: 直连 [dashdogy/MFG-Unlocker](https://github.com/dashdogy/MFG-Unlocker) (v1.6.1)

   - **模式 B (ReShade Addon)**: 直连 [mavismmg/MFGAdaUnlock-RenoDx](https://github.com/mavismmg/MFGAdaUnlock-RenoDx) (1.4.5)
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
   - **模式 D**：定为 **OptiScaler 全显卡跨架构转译**（FSR 3.1 / XeFG 跨卡桥接，支持全品牌显卡）。



4. **系统深度排毒与 C 盘瘦身 (NVIDIA Streamline 崩溃日志自动清理)**

   - 彻底解决由于游戏异常闪退被 NVIDIA Streamline 捕获而在 `%ProgramData%\NVIDIA\Streamline\` 偷偷累积数千个 `.dmp` 崩溃转储、吞噬数 GB 甚至数十 GB C 盘空间的顽疾；

   - 工具箱在执行游戏清理、卸载还原或一键排毒时，全自动深度穿透并清空对应游戏的全局 NVIDIA 崩溃快照，彻底守护 C 盘纯净与高速运行。



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

