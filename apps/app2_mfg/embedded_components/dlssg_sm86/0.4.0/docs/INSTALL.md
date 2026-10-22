# DLSSG SM86 融合版

**中文** · [English](INSTALL.en.md)

**把发布包根目录的 `version.dll`、`dlssg_sm86.ini` 和 `dlssg_sm86\` 这个文件夹复制到游戏实际渲染 EXE 旁，照常启动。** `version.dll` 是唯一要放的代理（钩子 DLL）；游戏不加载它时，删掉它，按固定顺序一次换一个 `alternatives\` 里的代理（见下面“代理只放一个”）。运行时无需 Python 或 PowerShell 启动器。第一次安装、想一步一步照着做的，先看发布包根目录的安装手册 `MANUAL.html`（双击用浏览器打开）；本文是全部设置的完整说明。

发布树长这样，每一样东西都是一个文件，代理本身只有半兆、不内嵌任何载荷：

```
<游戏 EXE 目录>\
  version.dll                    代理（只有加载器）；EXE 旁只放这一个代理
  dlssg_sm86.ini
  dlssg_sm86\
    backend\sm86_backend.dll     本包这个模型的后端（已签名）
    kernels\fg_kernels.dll       帧生成内核包：全部内核镜像（cubin + PTX）与清单，只有资源、没有代码；缺了它 RTX 30 / 20 上没有帧生成（日志 kernel_pack_missing）
    runtime\nvngx_dlssg.dll      配套的原版 DLSSG 运行库，`Mode=Bundled` 用的就是它
    sr\nvngx_dlss.dll            超分 snippet（DLSS 310.7.129），开关关着时完全不碰
    sr\sr_kernels.dll            超分内核包：RTX 30 / 20 的 INT8 内核集（四套），只有资源、没有代码；缺了它超分开关不生效（日志 sr_gate 写明找的是这个文件）
                                 （老版本的 sr\ 里还有 index.json 与 set_* 目录，新版不再读它们，可以删）
                                 （老版本还有 rr\，是 2026-10-09 删除的光线重建路线的；留着的话不会被读取，可以删）
    logs\                        日志
```

发布包里另有 `alternatives\`：`winmm.dll`、`dbghelp.dll`、`dinput8.dll`、`dxgi.dll`、`d3d12.dll` 五个备用代理（与 `version.dll` 是同一份加载器）和一份说明 `README.md`。平时不用复制，只在游戏不加载 `version.dll` 时取其中一个换上。

代理按**自己所在目录**解析这些路径（不是进程工作目录），所以代理、`dlssg_sm86.ini` 与 `dlssg_sm86\` 要放进同一个目录；把代理单独拷过去、`dlssg_sm86\` 留在原地，日志里会是 `backend_loaded{loaded:false}` 或 `bundled_runtime_unavailable`，游戏保留它自己的 DLSS-G。

**不再往 `%LOCALAPPDATA%` 写任何东西。** 老版本会把运行库和后端释放到 `%LOCALAPPDATA%\DlssgSm86\bundles\<id>\` 再从那里加载；现在没有这一步（那也是杀软和 Windows「智能应用控制」最容易拦的一步）。从老版本升级的人可以手动删掉 `%LOCALAPPDATA%\DlssgSm86`，mod 自己不会去删它——那个目录里可能还有别的版本在用的东西。

**出厂 INI 只有两种模式**（见下面“常规使用”）。所有诊断 / 兼容性 / 性能实验开关仍然被解析和支持，但不在出厂 INI 里；缺失时各自取安全且经过验证的默认值，完整清单见后面的“高级 / 诊断键”。

## 运行库模型（包里是哪个运行库）

发布包只带**一个**运行库和配套的一个后端，`manifest.json` 的 `runtime_model` 写明是哪一个。2026-10-14 起默认模型是 **310.9.16**，310.9 仍可构建、作为备选：

| 模型 | 产物 | 随包运行库 | 最大生成帧 | 备注 |
|---|---|---|---|---|
| **310.9.16**（默认） | `dlssg-release-0.4.0-x64.zip` | `nvngx_dlssg.dll` 310.9.16.0 | 5（6×） | 2026-10-14 起的默认。71 个内核里 68 个与 310.9.1 逐字节相同；`Kernel_BlendCandidatesFused`、`Kernel_DownsampleRGBAndEstimateUIFused` 有改动、`Kernel_BlendCandidatesFGLite` 是新的（三个都从运行库自己的 sm_120 PTX 重定向到 sm_86 / sm_75）。默认预设下与 310.9.1 **逐位相同**（合成场景 56/56、两份真实抓取各 105/105 个平面）。多一个**预设 C（FG Lite）**，见下面 `Preset` 一节。变体行 60 + 3 个图像补丁（P7 按 310.9.16 的 `Kernel_BlendCandidatesFused` 重新推导，另两个与 310.9.1 共用）；`DetailRestore` / `CatmullRomWarp` 的行挂在 310.9.1 的旧内核上，这个模型的内核包里没有（键写了只记一条 `detail_restore_row_unknown`、`effect:off`，帧照常）。`Router=SM75` 可用（3070 前向 JIT 已验证；新三个内核在真 Turing 上还没跑过） |
| **310.9**（备选） | `dlssg-release-0.4.0-x64-310.9.zip` | `nvngx_dlssg.dll` 310.9.1.0 | 5（6×） | 原生 6×；优化内核、跨内核合并与图像内核补丁均可用（63 个变体行：60 个网络变体 + 3 个按 310.9.1 RVA 重新推导的图像补丁）。`Router=SM75`（RTX 20）可用（3070 前向 JIT 与真 Turing（RTX 2080 Ti）都已验证）。`HardwareBilinear` 不起作用（后端强制关闭） |

构建方式：`powershell -File build.ps1`（默认 `-RuntimeModel 310.9.16`，产物在 `out\build-310.9.16`、`dist\Release-310.9.16`；`-RuntimeModel 310.9` 构建备选）。运行库是 NVIDIA 的材料，不随源码分发，
用 `-Runtime310916 <路径>` / `-Runtime3109 <路径>`（直接配置 CMake 时是 `-DDLSSG_RUNTIME_310916=<路径>` / `-DDLSSG_RUNTIME_3109=<路径>`）交给构建。
**游戏自己带的是 310.9.1 时**：出厂 `[Runtime] Mode=Bundled` 下代理把游戏对 `nvngx_dlssg.dll` 的请求换成随包的 310.9.16，游戏自己那份根本不加载，所以与游戏带哪个版本无关。`Mode=Auto` 在 0.4.0 删除（`docs/COMPAT.md` C86）：它只在游戏那份恰好就是随包运行库时才装得进去，其余情况游戏保留自己的 DLSS-G（RTX 30 / 20 上就没有帧生成）；旧 INI 里的 `Auto` 现在按 `Bundled` 运行，并记一条 `configuration_warning`。`Mode=Pinned` / `External` 指向 310.9.1 的文件认不出、回退到随包的 310.9.16（`pinned_runtime_rejected` / `external_runtime_rejected` 会写明“它是 310.9.1.0”）。写了 `[DLSSG] Preset=C` 时预设优先于运行库选择：`Pinned` / `External` 选中的文件即使有 `[Backends]` 配的后端、只要不是 310.9.16，也改用随包的 310.9.16，记一条 Level 1 的 `preset_runtime_override`（不是告警，两个键都合法）。要跑 310.9.1，用 `-RuntimeModel 310.9` 的构建（它的 310.9.1 钩子表、内核包与路径和改默认之前逐字节相同）。出厂 INI 里的
`MaxGeneratedFrames=3`（4×）直接生效；想要 6× 要**自己把它改成 5**（见下）。

## 代理只放一个（`version.dll`，不行再按顺序换）

发布包根目录只有一个代理 `version.dll`，绝大多数游戏都会加载它。**任何时候 EXE 旁只放一个本项目的代理。** 游戏不加载 `version.dll` 时，退出游戏、**先删掉它**，再从 `alternatives\` 按下面的固定顺序一次换一个，每换一个启动一次游戏：

1. `version.dll`（根目录，首选）
2. `alternatives\winmm.dll`
3. `alternatives\dbghelp.dll`
4. `alternatives\dinput8.dll`
5. `alternatives\dxgi.dll` 或 `alternatives\d3d12.dll`：渲染路径代理，在 D3D12 热路径上、加载顺序敏感，只作最后手段，两者不要同时放（Vulkan 游戏不加载这两个）

前四个是工具类 DLL，不在渲染热路径上。六个名字是同一份加载器（都从同一个 `dlssg_sm86\backend\` 加载同一个后端），区别只有文件名和转发目标，换名字不改变行为；挑选说明也随包放在 `alternatives\README.md`。

怎么判断代理被加载了：把 `[Logging] Level` 临时改成 `2`，进游戏打开帧生成。loader 日志里有 `runtime_redirect` 即已生效，`configuration` 记录里的 `proxies` 写明是哪个代理在干活，例如 `{"active":"version.dll","standby":[]}`。`Level=2` 下开了帧生成也没有 `loader_*.jsonl`，最常见的原因就是这个代理没被游戏加载，换下一个。

同一个目录里万一有好几个本项目的代理，也不会装出两份帧生成：

- 进程里第一个被加载的那个代理（DllMain 先跑的）拿到一个进程内的命名标记，成为 **active**：它挂 `LoadLibrary` 钩子、读 INI、加载后端。
- 之后加载的同族代理成为 **standby**：照常解析并转发自己那份系统 DLL 的全部导出（转发是完整的），但**不装钩子、不读 INI、不写日志**。`configuration.proxies` 形如 `{"active":"version.dll","standby":["winmm.dll"]}`。
- 谁先被加载由游戏的加载顺序决定，不由文件名决定，所以不要这样放，只留一个。

**从四代理的版本升级**：0.3.1 到 0.3.6 让用户把 `version.dll`、`winmm.dll`、`dbghelp.dll`、`dinput8.dll` 四个都放进游戏目录。升级到本版时把旧的 `winmm.dll`、`dbghelp.dll`、`dinput8.dll` 删掉：它们若先被游戏加载，跑的是那个旧版本自己内嵌的运行库与后端，新的 `version.dll` 只做转发（`docs/COMPAT.md` C80）。

## INI 放在哪里、何时生效

配置文件固定命名为 `dlssg_sm86.ini`，放在代理 DLL 所在目录（= 渲染 EXE 目录）。**修改后完全退出并重新启动游戏**，当前没有热重载。

- 布尔开关填写 `0` 或 `1`。以 `;` 开头的行为注释。
- `Mode` 等枚举值不区分大小写。
- 日志目录等路径可以填写绝对路径；相对路径以代理 DLL / INI 所在目录为基准（**不是进程工作目录**）。自定义路径不会展开 `%LOCALAPPDATA%`、`%TEMP%` 等环境变量，请填写实际路径（唯一的例外是 `Mode=External` 下的 `[Runtime] Path`，那一个会先展开）。`[Runtime] CacheDirectory` 现在**完全不起作用**（没有缓存了）：写了会记一条 `configuration_warning`，其余什么都不变。
- **某个键写错（非法数字、枚举拼错、越界）只影响这个键**：该键回退到自己的默认值，日志里记一条 `configuration_warning{section,key,value,default,reason}`（Level 1 即可见），mod 照常启用，其余键不受影响。例如 `MaxGeneratedFrames=99` 会回到 `3`、`Router=typo` 会回到 `Auto`、`[Runtime] Path` 指向的文件不可用会回到 `Mode=Bundled`。
- `configuration_error`（整个 mod 关闭、保留游戏原始的 DLSSG 加载）现在只留给**整份配置根本读不了**的情况（内存不足、`[Logging] Directory` / `[Debug] CaptureDirectory` / `[Runtime] Path` 写成了无法构成路径的字符串）。正常的拼写错误不会再走到这里。
- 后端不支持 INI 要求的某个开关时（例如 `[Backends]` 指向一个老 ABI 的外部后端），loader 会**去掉那几个标志位继续安装**，并记一条 `kernel_selection_unsupported{requested_flags,supported_flags,stripped_flags,effect:"installed without them"}`；该开关无效，其余功能照常。

## 常规使用：两种模式

出厂 `dlssg_sm86.ini` 的完整内容：

```ini
[General]
Enabled=1

[FrameGeneration]
Engine=DLSS
MaxGeneratedFrames=3

[DLSSG]
Optimized=2
Preset=Auto

[XeSSFG]
FlowResolution=Middle
UseHudless=1

[Logging]
Level=1
Directory=dlssg_sm86\logs

[Runtime]
Mode=Bundled

[SuperResolution]
Mode=Off
```

**两个插帧引擎（2026-10-14）。** 键按“对谁生效”分节：`[General]`、`[FrameGeneration]`（`Engine`、`MaxGeneratedFrames`）、
`[Logging]`、`[Runtime]`、`[SuperResolution]` 两个引擎都读；`[DLSSG]` 只有 `Engine=DLSS` 读，`[XeSSFG]` 只有
`Engine=XeSS` 读。另一个引擎的键写成了非出厂值，日志记一条 `configuration_warning`（`default` 是 `(ignored)`，
`reason` 是 `ignored under Engine=…`）；出厂值不告警，所以出厂 INI 在两个引擎下都是零告警。下面“高级 / 诊断键”里
`[FrameGeneration]` 的 `DetailRestore*` / `CatmullRomWarp` / `ImageApprox*` / `ForceGeneratedFrames` / `ForcePluginFrames`
与 `[Compatibility]` 的内核类键（`KernelImage`、`Router`、`SM75Family`、`LaunchChains`、`DisableFusions`、`PlainVariant`、
`ChainBlock0`、`ImagePatches`、`ImageApprox`、`AccelerateNewerGpus`）**只对 DLSS 引擎生效**；`[Compatibility]` 的
进程类键（`SpoofArchToGame`、`SpoofArchValue`、`ForceSM86Route`、`SimulateAmpere`）两个引擎都需要。`Engine=XeSS` 用本项目
自己的 D3D12 运行器跑 Intel XeSS-FG 模型（只 2X），着色器与权重在 `dlssg_sm86\xefg\xefg_kernels.dll`；不带、也不加载 Intel 的
`libxess_fg.dll`。CreateFeature 仍由 NVIDIA 运行库完成，帧节奏与呈现仍归 Streamline，只换 Evaluate。XeSS-FG 跑不了的后缓冲格式
（R8G8B8A8 / B8G8R8A8 / R10G10B10A2 以外，如 RGBA16F）记一条 `xefg_fallback`，该特性改跑 DLSS；`xefg_kernels.dll` 缺失或损坏记一条
`xefg_unavailable`，按 DLSS 运行（`docs/COMPAT.md` C85）。这两条从 0.4.0 起是 Level 1（出厂日志级别就能看到）。不改跑 DLSS 的情况：
游戏的 HUD-less 画面或 UI 平面与后缓冲尺寸不同，或 `UseHudless=1` 而游戏没给 HUD-less，这些帧按 `UseHudless=0` 的输入跑 XeSS，
第一次记一条 Level 1 的 `xefg_hudless_unused`（`xefg_summary.hudless_unused` 计帧数）；`MaxGeneratedFrames` 写了 2 以上时
记一条 Level 1 的 `xefg_multiplier_clamped`（XeSS 只 2X）。仍然改跑 DLSS 的条件与原因见 `docs/COMPAT.md` C86。

只有一个决定“怎么跑帧生成”的开关：`[DLSSG] Optimized`（2026-10-14 之前是 `[FrameGeneration] Optimized`，旧位置照旧读）。它是一个**一致性档位**，判据只有一条：
**允许生成的画面偏离官方 NVIDIA 运行库多远**。档位越高越快、离官方画面越远；其余所有旋钮都由档位决定，
普通用户不需要逐个理解。

| 档位 | 设置 | 一致性保证 | 这一档打开了什么 |
|---|---|---|---|
| **0 原厂（stock）** | `Optimized=0` | **与官方运行库逐位一致** | 什么加速都不做。**注意这不是“不替换内核”**：SM86 路线仍然生效，后端替换进去的是从运行库里提取出来的**原厂内核镜像**（真 SM86 卡用 cubin，其它架构用 PTX），数值与运行库完全一致。它不等于 `KernelImage=Original`——在 **Ampere** 上尤其重要：310.9.1 的原厂图像内核是 sm_89 blob，在 Ampere 上根本创建不出来，所以 Ampere 上的“原厂数值”只能靠这条路径。 |
| **1 逐位一致（参照档）** | `Optimized=1` | **与官方运行库逐位一致**（两份真实游戏抓取、320 张图实测）。要和官方画面逐位对照、或判断某个画面现象是不是本项目引入的，用这一档 | 全部**可证明不改变输出**的加速：60 个重写内核变体 + 全部跨内核合并、精确图像内核补丁（P1/P3/P4/P7/P8/P9/P10）。等价于 `OptimizedKernels=1, ImagePatches=1, HardwareBilinear=0, ChainBlock0=0, LaunchChains=0, PlainVariant=0, DisableFusions=0`。 |
| **2 快（有损；默认，推荐）** | `Optimized=2` | **不再逐位一致**：真实游戏 4K 4X 抓取上对官方数值 PSNR 44–53 dB，运动越快越低（RTX 3070 上 Resonance 最快的那段最差 44.06 dB）；对真值只比档位 1 低 0.02–0.13 dB，两者差得最多的区块并排看不出差别（见下面“档位 2 / 3”一节） | 档位 1 + 有损图像内核行（目前只有一行：A6，`Kernel_OutputPull` 的 warp 取样改为最近点）。每生成帧比档位 1 快 1.8 %（1080p）/ 1.8 %（1440p）/ 2.9 %（4K）（RTX 3070，4X，0.4.0；之前是 2.6 / 2.9 / 4.5 %——0.4.0 的 P8/P9/P10 让档位 1 自己快得更多）。 |
| **3 最快（有损）** | `Optimized=3` | **不再逐位一致**，画质代价最大 | 全部仍然更快的有损加速：每一行有损图像内核。慢的或有结构性伪影的变体已永久退役，任何档位都不会启用。 |

档位是**累加且单调**的：更高的档位只会再加东西，不会撤回低档位的加速。想逐个覆盖某一项，用下面“高级 / 诊断键”
里的 `ImagePatches` / `ImageApprox` / `ImageApproxMask`——它们在档位
之后生效，可以把档位打开的东西再关掉，也可以在低档位上单独打开某一项。

其余出厂键：

| 配置项 | 节 | 默认值 | 说明 |
|---|---|---|---|
| `Enabled` | `[General]` | `1` | `1` 启用 DLSSG 重定向、适配和帧生成；`0` 关闭：游戏原样加载它自己的 DLSSG（在 Ampere 上就意味着没有帧生成）。代理仍转发系统 DLL 的原有导出。 |
| `Engine` | `[FrameGeneration]` | `DLSS` | 插帧引擎：`DLSS` = NVIDIA DLSS-G 模型（本项目的 SM86 / SM75 内核）；`XeSS` = Intel XeSS-FG 模型（本项目自己的运行器，只 2×，见上）。写 `XeSS` 时 `configuration` 记录多一个 `engine{requested,effective,xessfg}` 字段（写 `DLSS` 或不写时没有），加载器记 `xefg_requested`，后端记 `xefg_engine` / `xefg_context` / `xefg_summary`（或 `xefg_unavailable` / `xefg_fallback`）。拼错回到 `DLSS` 并记一条 `configuration_warning`。 |
| `Optimized` | `[DLSSG]` | `2` | 一致性档位 `0`–`3`，见上表。**旧位置**：`[FrameGeneration] Optimized`（2026-10-14 之前）与更早的 `[Compatibility] OptimizedKernels`，都接受 `0`–`3`（老 INI 里的 `OptimizedKernels=1` 仍然是档位 1）。三处里**按 `[DLSSG]` → `[FrameGeneration]` → `[Compatibility]` 的顺序第一个写了的生效**，都没写时默认档位 0；每个写了的旧位置记一条 `configuration_warning` 指向 `[DLSSG] Optimized`（它生效时 `default` 是 `(honoured)`，有更新的位置也写了时是 `(ignored)`，被忽略的那一行的值不再解析）。**值写错或超范围时回退到出厂档位 2** 并记一条 `configuration_warning`——写了这个键的人本意是要打开加速，不该被静默退回原厂。只对 `Engine=DLSS` 生效。 |
| `MaxGeneratedFrames` | `[FrameGeneration]` | `3` | 上报的最大“额外生成帧”数量的上限：`5`=最多 6×，`3`=最多 4×，`2`=3×，`1`=2×，`0`=保留运行库原有上报。**实际生成数量由游戏请求决定**。出厂值是 `3`（4×）：自带 Dynamic MFG 的游戏默认会直接跑到这里给出的上限，`5` 对多数人偏高（公开 issue #497/#499），所以 6× 改成**按需手动开**——把这一行改成 `5` 即可。自带旧版 4X Streamline 插件的游戏无论写几都只有 4×。**实际运行的引擎是 XeSS 时钳到 `1`（2×）**，`0` 不变。 |
| `Preset` | `[DLSSG]` | `Auto` | DLSSG 渲染预设（UI 重组）。`Auto` 让游戏 / 驱动配置决定（默认）；`C` = FG Lite（可选，只有 310.9.16：每生成帧 GPU 时间 −32…−54 %，画质略低）；`A` 强制关闭 UI 重组；`B` 强制开启（生成帧里 HUD/UI 更干净）——**但 B 只在游戏同时向 DLSS-G 交出 HUD-less 图和 UI 平面时才生效**，多数游戏不提供、此时为空操作；0.4.0 起这种情况日志记一条 Level 1 的 `preset_ineffective`（每个特性一条，写明缺哪张平面，交出的平面变了才再记），见 COMPAT C87。旧位置 `[Compatibility] Preset`（2026-10-14 之前）照旧读，规则与 `Optimized` 相同：`[DLSSG] Preset` 没写时用旧位置，写了旧位置就记一条 `configuration_warning`（`(honoured)` / `(ignored)`）。`[DLSSG] Preset=`（写了空值）算拼错：回到 `Auto` 并告警，不会退到旧位置。只对 `Engine=DLSS` 生效。 |
| `FlowResolution` | `[XeSSFG]` | `Middle` | XeSS-FG 光流分辨率：`Coarse` / `Middle` / `Fine`（XeSS-FG 运行库的 `0x410` / `0x408` / `0x208`），越细越慢。只对 `Engine=XeSS` 生效；拼错回到 `Middle` 并告警。 |
| `UseHudless` | `[XeSSFG]` | `1` | `1` = 游戏给了无 HUD 画面就用它做网络输入并合成 UI（默认，业主 10-14）；`0` = 不用；游戏没给时自动按 `0`。只对 `Engine=XeSS` 生效（同上）。 |
| `Level` | `[Logging]` | `1` | `0` 关闭日志；`1` 只记错误；`2` 增加配置、加载和能力信息；`3` 再增加内核创建、Evaluate 和标记信息。日志文件名为 `loader_<PID>.jsonl` 和 `backend_<PID>.jsonl`。 |
| `Directory` | `[Logging]` | `dlssg_sm86\logs` | 日志目录，相对路径以 INI 目录为基准。 |
| `Mode` | `[Runtime]` | `Bundled` | 运行库来源。`Bundled` = 随包的 `dlssg_sm86\runtime\nvngx_dlssg.dll`（普通安装用这个，无须版本匹配）。`External`（`[Runtime] Path` 指定另一个位置，默认值就是上面那个文件）/ `Pinned` 是高级用法，见下。`Auto` 在 0.4.0 删除：写了按 `Bundled` 运行并记一条 `configuration_warning`。 |
| `Mode` | `[SuperResolution]` | `Off` | DLSS 超分，只在 RTX 30 / RTX 20 上生效。`Off` = 不介入，与没有这一节完全相同；`On` = 游戏在哪一档用预设 L / M（通常是性能档与超级性能档），就把那一档换成本项目的 INT8 内核，预设不变。见下面 `[SuperResolution]` 一节。 |

一般安装保留出厂 INI 不动即可（档位 2）。要画面与官方运行库逐位一致（例如判断某个现象是不是本项目引入的）把
`Optimized` 改成 `1`，想对比原厂数值改成 `0`，其它一律不用碰。从老版本升级时保留了旧 INI 的，仍是旧 INI 里写的档位
（老版本出厂是 `Optimized=1`；2026-10-14 之前的出厂 INI 把它写在 `[FrameGeneration]`、把 `Preset` 写在 `[Compatibility]`，
这两行照旧生效，日志各记一条旧名告警，换成新的出厂 INI 就没有了）。

## RTX 40 / RTX 50（0.4.0 起）

0.4.0 起本项目的帧生成内核**默认也在 RTX 40（sm_89）和 RTX 50（sm_120）上运行**，档位照样由 `Optimized` 决定（出厂档位 2）。
此前这两代卡上运行库只用它自己的内核。只认计算能力 8.9 / 12.0、CUDA 显卡名带 `RTX` 的卡（包括 RTX 6000 Ada、RTX PRO 6000
Blackwell 这类工作站卡；名字不带 RTX 的数据中心卡不受影响）。

- **速度还没有在 RTX 40 / 50 实机上量过。** 开发机只有 RTX 3070：这条路线在 3070 上用开发开关完整跑过（同一份 PTX，输出与
  RTX 30 路线逐位相同）；2026-09 在 RTX 5070 上，这套内核（当时的版本，之后的改动只在 RTX 3070 上验证过逐位一致）与官方输出
  逐位一致，但对官方内核的耗时差一次都没有量过。
  一键测试包在 RTX 40 / 50 上会自动多测一列"官方"（见测试包 README），量出来之前收益未知，也可能更慢。
- **怎么关**：INI 的 `[Compatibility]` 节写 `AccelerateNewerGpus=0`（节不存在就加一个），就回到运行库自己的内核（0.4.0 之前的行为）。
- **镜像是 PTX**：包里 sm_86 族的 PTX 由驱动即时编译（包里没有 sm_89 / sm_120 cubin）。第一次创建帧生成特性要多编译一遍，
  RTX 5070 上实测冷启动整次 CreateFeature 约 3.0–3.3 秒（约 1.2 秒是 70 个基础内核——RTX 50 上官方运行库自己也要即时编译
  同样多的 PTX——约 1.7–1.8 秒是本项目的 63 个优化行），之后命中驱动的计算缓存（`%APPDATA%\NVIDIA\ComputeCache`，上限 1 GiB）
  只要约 0.13 秒；驱动更新或缓存被挤掉后会再编一次。RTX 40 上官方运行库用的是 cubin，不需要编译，所以这几秒全是新增的。
- **画面**：RTX 50 上档位 0 / 1 预期与官方逐位一致（档位 2 照旧有损）；**RTX 40 上档位 0 / 1 也不会与官方逐位一致**——官方在
  RTX 40 上跑的是另一套构建（为不做多帧生成的产品编的 Ada 版图像内核与 sm_89 cubin 网络），本项目跑的是 RTX 50 那一套的算法，
  两者在 RTX 5070 上实测相差 55–82 dB（差异集中在 UI 重组 / 候选混合路径）。
- **不变的**：游戏里能选的倍率不变（RTX 40 仍是 2X），不改对游戏、Streamline、NGX 核心的任何架构答复（`SpoofArchToGame`
  在这两代卡上照旧什么都不改写；也不像 RTX 30 那样改写运行库对 NGX 核心声明的最低架构）。
- **出错时**：驱动拒绝本项目的任何一个镜像（PTX 编译或创建失败）时，那个内核改用运行库自己的镜像，这个进程从下一次创建特性
  起只用运行库自己的内核，日志记一条错误级 `newer_gpu_route_fallback`。
- 日志：后端在 RTX 30 / 20 以外的卡上记一条 `newer_gpu_route`（`engaged`、`reason`、`key`、`default_on`、`image`），
  `Level=2` 可见。

## INI 键的稳定性：三级

加载器读的 INI 键一共 104 个（`tests/golden/surface.json` 的 `ini_keys`，CTest `compat_surface` 逐个钉住，见
`docs/COMPAT.md` C4）。它们按对外的承诺分三级，另有四个仍被接受的旧名（2026-10-05 业主定；2026-10-14 两个插帧引擎
的布局又加了两个，C84）：

| 级 | 哪些键 | 承诺 |
|---|---|---|
| **1 冻结** | 出厂 INI 里的 11 个键（2026-10-10 起含 `[SuperResolution] Mode`；2026-10-14 起含 `[FrameGeneration] Engine` 与 `[DLSSG]`、`[XeSSFG]` 两节） | 节、键名和取值的含义都不变。真要改名，旧键继续按原意生效（`[Compatibility] OptimizedKernels` 就是 `Optimized` 改名后留下的旧名；2026-10-14 `Optimized` / `Preset` 搬进 `[DLSSG]`，旧位置同样照旧生效），至少也要被读到并记一条 `configuration_warning` 指向新写法：任何一份出厂 INI，以后的版本都读得懂。 |
| **2 保持兼容** | 写给玩家的 5 个键：`[Compatibility] SpoofArchToGame`、`[Compatibility] AccelerateNewerGpus`（RTX 40 / 50 的关闭开关）、`[FrameGeneration] CatmullRomWarp`、`[SuperResolution] Tier`、`[Runtime] Path` | 可以增加取值、改进行为，但不会悄悄失效：移除或改名时，旧写法要么继续生效，要么记一条 `configuration_warning` 说明替代写法。 |
| **3 诊断** | 其余全部：开发、验证、抓取、探针与测量用的键，内核格式与内核族、架构上报值、运行库路线的高级写法 | 版本之间可以改名、改义或删除。删除的键在之后的版本里仍然被读：写了就记一条 `configuration_warning`、不起任何作用——`[SuperResolution]` 的 `kRemovedKeys`（旧的 `Int8`、`ForcePreset*` 等）与 2026-10-09 整节删除的 `[RayReconstruction]` 的键就是这个机制。 |
| **旧名** | `[FrameGeneration] Optimized` 与 `[Compatibility] OptimizedKernels`（`[DLSSG] Optimized` 的旧位置 / 旧名）、`[Compatibility] Preset`（`[DLSSG] Preset` 的旧位置）、`[Compatibility] ImageApprox`（`[FrameGeneration] ImageApprox` 的旧位置） | 仍被接受、按原意生效；写了就记一条 `configuration_warning` 指向新键（`default` 是 `(honoured)`；更新的位置也写了时旧名被忽略，`default` 是 `(ignored)`）。 |

不论哪一级，一个键不再被读都会让 `compat_surface` 失败；删掉它的改动要同时更新 `tests/golden/surface.json`，并在
`tests/golden/README.md` 写一行：删了什么、为什么、用什么代替。`[Backends]` 的键是运行库的 SHA-256 而不是固定名字，不在表里。

`[FrameGeneration] SkipRepeatedRealCopy` 原是第 2 级的键，2026-10-08 删除（见下面「`SkipRepeatedRealCopy`（已删除）」）。按第 2 级的承诺它仍被读取，只为告警，所以下表把它列在第 3 级。

`[RayReconstruction] Mode` 原也是第 2 级的键，2026-10-09 随光线重建路线删除（见下面「[RayReconstruction]（已删除）」与 `docs/RR.md`）。同理它仍被读取、只为告警，下表也把它列在第 3 级；这一节的其余键、`[Runtime] RRMode` / `RRPath` 与 `[Debug] CaptureRR` / `CaptureFeature` 一样只为告警而读。

| 节 | 第 1 级（11） | 第 2 级（5） | 第 3 级（84） | 旧名（4） |
|---|---|---|---|---|
| `[General]` | `Enabled` |  |  |  |
| `[DLSSG]` | `Optimized`、`Preset` |  |  |  |
| `[XeSSFG]` | `FlowResolution`、`UseHudless` |  |  |  |
| `[FrameGeneration]` | `Engine`、`MaxGeneratedFrames` | `CatmullRomWarp` | `DetailRestore`、`DetailRestoreA`、`DetailRestoreAlpha`、`DetailRestoreB`、`DetailRestoreC`、`DetailRestoreCasMul`、`DetailRestoreD`、`DetailRestoreGate`、`DetailRestoreWeightProbe`、`ForceGeneratedFrames`、`ForcePluginFrames`、`ImageApprox`、`ImageApproxMask`、`SkipRepeatedRealCopy`（已删除：只为告警而读） | `Optimized`（`[DLSSG] Optimized` 的旧位置） |
| `[Compatibility]` |  | `SpoofArchToGame`、`AccelerateNewerGpus` | `ChainBlock0`、`DisableFusions`、`ForceSM86Route`、`HardwareBilinear`（不起作用：后端强制关闭，写了就记 `configuration_warning`）、`ImagePatches`、`KernelImage`、`LaunchChains`、`PlainVariant`、`Router`、`SM75Family`、`SimulateAmpere`、`SpoofArchValue` | `ImageApprox`（`[FrameGeneration] ImageApprox` 的旧位置）、`OptimizedKernels`（`Optimized` 的旧名）、`Preset`（`[DLSSG] Preset` 的旧位置） |
| `[Logging]` | `Level`、`Directory` |  | `DebugOutput`、`EvaluateEvery`、`File`、`FrameTiming` |  |
| `[Runtime]` | `Mode` | `Path` | `CacheDirectory`（已失效：只为告警而读）、`RRMode`、`RRPath`（这两个已删除：只为告警而读）、`SRMode`、`SRPath` |  |
| `[SuperResolution]` | `Mode` | `Tier` | `Auxiliary`、`KernelImage`、`KernelSet`、`KernelSetSM`、`ObserveFrames` |  |
| `[RayReconstruction]` |  |  | `Mode`、`KernelImage`、`KernelSet`、`Observe`、`ObserveFrames`（整节已删除：只为告警而读） |  |
| `[Debug]` |  |  | `Capture`、`CaptureAsyncCopy`、`CaptureDirectory`、`CaptureFeature`（已删除：只为告警而读）、`CaptureInputs`、`CaptureLean`、`CaptureMemoryMB`、`CaptureNoStall`、`CaptureOutputs`、`CaptureRR`（已删除：只为告警而读）、`CaptureRingSlots`、`CaptureSR`、`CaptureSRAsyncCopy`、`CaptureSRBursts`、`CaptureSRDedup`、`CaptureSRDirectory`、`CaptureSRFrames`、`CaptureSRLean`、`CaptureSRMaxGB`、`CaptureSRMemoryMB`、`CaptureSRNoStall`、`CaptureSRRingSlots`、`CaptureSRSkip`、`CaptureSRStartKey`、`CaptureSRStartOnCreate`、`CaptureSRStride`、`CaptureSRVramMB`、`CaptureSkip`、`CaptureStartKey`、`CaptureStartOnReset`、`CaptureVramMB`、`MarkGeneratedFrames`、`MarkerScale`、`MarkerX`、`MarkerY`、`MfgProbe`、`NgxLog`、`NgxLogLevel`、`QueueTrace` |  |


## 高级 / 诊断键（不在出厂 INI 里）

下面这些键**仍然被 loader 解析和支持**（开发、验证、监控、抓取、MFG 探针都要用），只是不在出厂 INI 里。**缺失时各自取安全 / 最佳默认值**，所以正常安装不需要写它们。要用时把对应的节和键补进 INI（节不存在就自己加一个 `[节名]`）。

> **注意：以下开关默认已经是最快 / 最安全的一组。** 打开这几项会**降低性能**，只用于诊断或特定硬件复测：
> `ChainBlock0=1`、`LaunchChains=1`、`PlainVariant>0`、`DisableFusions>0`、`ForceGeneratedFrames>0`。

### [FrameGeneration]

| 配置项 | 值 | 默认 | 说明 |
|---|---|---|---|
| `SkipRepeatedRealCopy` | — | — | **已删除**（2026-10-08）：Streamline 只在 index 1 交出 `OutputReal`，游戏里没有它可跳的拷贝。INI 里还写着它（非空值）只记一条 `configuration_warning`（`default` 是 `(no effect)`），其余不受影响；空值等同于没写。见下面「`SkipRepeatedRealCopy`（已删除）」。 |
| `ImageApprox` | `0/1` | **档位决定**（档位 ≥2 为 `1`） | 有损图像内核行的显式开关，覆盖档位的答案：在档位 1 上写 `1` 就只加有损图像行，在档位 2/3 上写 `0` 就只留逐位一致的部分。档位 0 不建任何行，在那里写 `1` 不起作用（记一条 `configuration_warning`）。`[Compatibility] ImageApprox` 是它的旧位置：仍被读取，写了就记一条 `configuration_warning` 指向这个键。 |
| `ImageApproxMask` | 位掩码 | **档位决定**（档位 2 = 默认集，档位 3 = 全部） | 精确指定启用哪几行有损图像内核，每一位对应一个固定槽位。槽位**一次分配、永不回收**：退役的行留下空位，所以老文档里写下的掩码值永远指同一批行；掩码里出现未分配的位会被忽略并记一条 `image_approx_mask_unassigned`。同一个内核有多行时只启用位号最小的那一行，另一行记 `image_approx_row_shadowed`。armed 的行、槽位与资源号都在后端 `image_approx` 记录里。 |
| `CatmullRomWarp` | `0/1/2` | **`0`**（任何档位都不打开） | 把 `Kernel_BlendCandidatesFused` 里两次**运动 warp 取样**从取样器的双线性换成 **Catmull-Rom**。`1` = 丢掉四个角点再归一化的**五抽头**档（每候选 5 次硬件过滤取样）——实测的性价比档，也是唯一推荐的值；`2` = 精确的可分离 4×4（**九抽头**，每候选 9 次），能量并不更高而代价翻倍，留着是为了完整而不是为了推荐。**不引入任何判据**（纯重采样改动，没有"校验通过就怎样"这类分支），而且位移为 0 时 Catmull-Rom 退化成取中心纹素，所以车停着的画面按构造不变。5070 实测（赛博朋克 4K 抓取）：细结构能量比 `E_gen/E_real` 从 **0.897 抬到 0.953**，1080p / 1440p 每生成帧约 **+2.5 %**、4K 约 **+4 %**（K39 这一个内核逐 launch +20 %，九抽头是 +42 %）；**HUD 区块也变好**，但**肉眼能看出的改善很轻微**。按设计**偏离**官方输出（不再逐位一致），所以不进任何 `Optimized` 档位。**它需要 `Optimized` ≥1，且 `[Compatibility] ImagePatches` 不是 0**：它是一行图像补丁行（建在精确补丁 P7 的 PTX 上），档位 0 不建任何行，`ImagePatches=0` 关掉所有图像补丁行；这两种配置下写它什么都不做，loader 记一条 `configuration_warning`，后端的 `catmull_rom_warp` 记录写 `enabled:false` 与 `disabled_reason`。`0` 时输出与官方运行库逐位一致。**它是独立的顶层键，不需要 `DetailRestore`**。 |
| `DetailRestore` | `0/1` | **`0`**（任何档位都不打开） | **实验性细节修复的主开关**（`B`/`C`/`D` 三个子模式；原来的 `A` 已经变成上面的 `CatmullRomWarp`）。`0` 时下面几个 `DetailRestore*` 子键**连读都不读**，所以把子键写在 INI 里、只翻这一个键就能做 A/B。**只写 `DetailRestore=1` 而不写任何子键是空操作**（实测与官方运行库 94/94 平面逐位一致）。按设计**偏离**官方输出，所以不进任何 `Optimized` 档位。和 `CatmullRomWarp` 一样，它的行需要 `Optimized` ≥1 且 `ImagePatches` 不是 0，否则什么都不做（记一条 `configuration_warning`，`detail_restore` 记录写 `enabled:false`）。 |
| `DetailRestoreB` | `0/1` | `0` | 成品帧上的能量对齐锐化（接在 `Kernel_OutputPushFine` 之后的一次额外发射）。**本构建没有实现它**：写 `1` 会被如实拒绝并记一条错误级 `detail_restore_post_unavailable`，`CatmullRomWarp`/C/D 照常生效。 |
| `DetailRestoreC` | `0/1` | `0` | 高频回注：把"两张 warp 后真实帧的高频里被平均掉的那一份"加回去，强度 `DetailRestoreAlpha`，带遮挡门。加给两个候选同一份修正，所以它活过下游的候选混合。 |
| `DetailRestoreD` | `0/1` | `0` | 高频选择：低频照常按运行库的权重混，**高频往"高频更多的那个候选"移** `DetailRestoreAlpha`，带同一个遮挡门。比 `C` 多一倍的低通取样。 |
| `DetailRestoreAlpha` | `0`–`1000` | `500` | `C` / `D` 的强度 ×1/1000。**这个数编进了内核**，所以写别的值会记一条 `configuration_warning` 并回到 `500`；真要改只能重新生成内核。 |
| `DetailRestoreGate` | `0`–`1000` | `100` | 遮挡门：两个候选的平均通道差达到这个值（×1/1000 颜色单位）时 `C`/`D` 的修正完全关闭。同样**编进内核**，改法同上。 |
| `DetailRestoreCasMul` | `0`–`2000` | `900` | `B` 的能量靶子倍数 ×1/1000（`0.90` 是实测的折扣：两端真实帧能量的运动补偿插值比真正的中间帧高约 6 %）。`B` 未实现，所以目前只被记录。 |
| `DetailRestoreA` | — | — | **已删除**（原来的模式 A）。它现在是独立的顶层键 `CatmullRomWarp`，且**两个值对调了**：旧的 `DetailRestoreA=2`（五抽头）= 新的 `CatmullRomWarp=1`，旧的 `=1`（九抽头）= 新的 `=2`。INI 里还写着这个键会记一条 `configuration_warning` 指向新键，并被忽略。 |
| `DetailRestoreWeightProbe` | `0/1` | `0` | **诊断，会毁掉画面**。把两个候选都换成"(候选 A 的共位↔warp 权重, 候选 B 的, 两者均值)"，用来把那个权重从重放输出里读回来。需要 `DetailRestore=1`。 |
| `ForceGeneratedFrames` | `0`–`16` | `0` | **诊断实验（会降低体验）**。让 `DLSSG.MultiFrameCount` 及 NVIDIA App 覆盖通道的**每一次 getter** 返回这个数（夹到 `MaxGeneratedFrames` 与后端上限），不动 setter。只有当游戏 Streamline 插件会**读回**帧数时才有作用；否则只会让插值相位错乱、画面发抖。配合 `[Debug] MfgProbe=1` 判定，方法见 `docs/MFG_PROBE.md`。用完改回 `0`。 |
| `ForcePluginFrames` | `0`/`2`–`5` | `0` | **实验性**。给自带**旧版 4X** Streamline 插件的游戏（悟空 `sl.dlss_g.dll` 2.7.4、赛博朋克 2077 2.7.1）在内存里打补丁跑 6X：把插件硬编码的 4X 上限（`min(MultiFrameCountMax,3)` 里的 `3`）与默认初值改成 N，并钩住插件的逐帧常量下发把 `numFramesToGenerate` 强制成 N，使运行库视图、插件循环、资源分配都落在 N（这正是 `ForceGeneratedFrames` 单改 getter 会失步的原因）。仅在按 SHA-256/FileVersion + 唯一字节特征**精确识别**到已知版本时才动，否则不动并记 `plugin_mfg_unrecognized`。须同时设 `MaxGeneratedFrames=N`。补丁在插件验签**之后**、CreateFeature 计算上限**之前**施加。**"哪个模块是 DLSS-G 插件"按路径判断**：叶名 `sl.dlss_g.dll`，或 NGX 模型库里 Streamline ≥ 2.11 实际加载的那份 OTA 副本（`\ngx\models\sl_dlss_g_0\versions\<n>\files\1B0_E658703.dll`、`sl_dlss_g_override_0\…\1B0_E658700.dll`）；每条 `plugin_mfg_*` 记录都带 `plugin_match`（`leaf`/`ota`/`ota_override`）与真正扫描的模块，`plugin_mfg_modules` 也会把模型库里的 `sl_*` 一起列出来。**实测结论（悟空 2.7.4，2026-09-14）：补丁机制成功**（日志 `plugin_mfg_install` 上限 3→5、`plugin_mfg_force` 把 `numFramesToGenerate` 强制成 5），**但游戏跑几帧 6X 后整个 DLSS-G 硬失败关闭**（连 4X 也没了）——4X 集成的交换链后备缓冲按 4X 一次性建好，强制第 5 帧无缓冲可呈现，Streamline 不优雅退回而是关掉整个帧生成。**故本键对 4X 游戏不可用、且有害**，默认关。真 6X 需要游戏自带 ≥2.11.1 的 `sl.dlss_g.dll`（如 A Plague Tale 的 2.11.1，实测原生 6X 干净）。见 `docs/MFG_PROBE.md`。 |

### [Logging]

| 配置项 | 值 | 默认 | 说明 |
|---|---|---|---|
| `File` | `0/1` | `1` | `1` 写日志文件；`0` 关闭文件输出（仍受 `Level` 控制）。 |
| `DebugOutput` | `0/1` | `0` | `1` 同时通过 Windows 调试输出发送日志，可由调试器接收；不在游戏画面上显示。 |
| `EvaluateEvery` | `1`–`1000000` | `120` | 正常 Evaluate / 标记日志的采样间隔（按 Evaluate 调用计数）。`1` 记录每次；`0` 按 120 处理。Level 3 下前 12 次总是记录。 |
| `FrameTiming` | `0/1` | `0` | `1`：每个真实帧在 `Directory` 下的 `frames_<pid>.jsonl` 写一行——CPU 帧间隔、这一帧超分 Evaluate 的 GPU 时间、它全部帧生成 Evaluate 的 GPU 时间（D3D12 时间戳），每秒一行汇总（含 GPU 占用率），与 `Level` / `File` 无关。`0` 或不写：什么都不加载、不装钩子。值非法记一条 `configuration_warning`，按 `0` 处理。见下面「帧时间文件」。 |

#### 帧时间文件 `frames_<pid>.jsonl`（`[Logging] FrameTiming=1`）

写了 `FrameTiming=1` 的进程在第一次 DLSS Evaluate 之后建这个文件，放在 `[Logging] Directory`（默认 `dlssg_sm86\logs`，与 `loader_` / `backend_` 日志同一个目录，打包日志时会一起带上）。只开超分、只开帧生成、两个都开都写；`[General] Enabled=0` 时也写，量的是游戏自己的 DLSS / DLSS-G，可以直接与开着本项目的一次做 A/B。Vulkan 游戏不计时，文件里一行 `frame_timing_unsupported` 说明原因。

一个真实帧（游戏自己渲染的一帧）一行：开着帧生成时是一组 `MultiFrameIndex` 1..N 的帧生成 Evaluate，这一帧之前的超分 Evaluate 也算在它里面；不开帧生成时是一次超分 Evaluate。每行是一个 JSON 对象，`t` 说是哪一种：

| `t` | 何时 | 内容 |
|---|---|---|
| `hdr` | 第一行 | 每个字段的含义与单位、显卡名、时间戳频率、括号盖住什么 |
| `ctx` | 第一帧之前，之后每次变化 | 超分：渲染与输出分辨率、预设、`kernels`（`int8` = 本项目的 INT8 内核，`native` = 本项目的路线在、跑的是 NVIDIA 的内核，`game` = 游戏自己的 DLSS）；帧生成：倍数、分辨率、`route`（`ours` / `runtime`）、档位、内核镜像 |
| `f` | 每个真实帧 | `f` 帧号、`c` 距第一次计时的毫秒、`dt` 与上一帧的 CPU 间隔（游戏的真实帧时间）、`sr` 超分的 GPU 毫秒、`fg` 这一帧全部帧生成 Evaluate 的 GPU 毫秒之和、`n` 生成帧数、`fgw` 第一个帧生成 Evaluate 开始到最后一个结束的 GPU 跨度、`gdt` 与上一帧在 GPU 时间线上的间隔；没有的不写，`x` 说哪一项的时间戳迟到或丢了 |
| `s` | 每秒一行 | `fps`，`dt` / `sr` / `fg` / `gdt` 的 avg / p50 / p95 / max（毫秒），`n`，`gpu` 与 `fb` 占用率（%） |
| `end` | 正常退出时最后一行 | 帧数与计数器；没有这一行就是进程被杀或崩溃 |

例（RTX 3070；前两行是超分 M INT8 1080p 性能档，后两行是 4K 帧生成 4X、档位 2）：

```
{"t":"ctx","f":1,"sr":{"in":[960,540],"out":[1920,1080],"preset":"M","kernels":"int8"}}
{"t":"f","f":1,"c":88.042,"dt":88.042,"sr":1.350,"gdt":60.583}
{"t":"f","f":1,"c":64.203,"dt":64.203,"fg":6.726,"n":3,"fgw":6.737,"gdt":46.244}
{"t":"s","s":1,"frames":19,"fps":19.09,"dt":{"avg":52.391,"p50":52.139,"p95":57.062,"max":57.062},"fg":{"avg":6.429,"p50":6.428,"p95":6.443,"max":6.443},"n":3,"gdt":{"avg":52.376,"p50":51.778,"p95":57.330,"max":57.330},"gpu":53,"fb":10}
```

怎么读：

- `dt` 是游戏的真实帧时间，`1000 / dt` 是真实帧率（显示帧率再乘帧生成倍数）。`gpu` 接近 100 % 是 GPU 瓶颈，这时 `sr` / `fg` 变小会直接变成帧率；`gpu` 明显低于 100 % 而帧率不高，是 CPU（或帧率限制）瓶颈，GPU 时间省下来也不会变成帧率。`gpu` 是整张卡、所有进程，NVAPI 每秒采一次（常用 overlay 显示的就是这个数）。
- `sr` / `fg` 是本项目在 NGX 核心的 EvaluateFeature 调用前后录进游戏命令列表的两个时间戳之差：运行库在这次 Evaluate 里录的全部 GPU 工作都在里面（帧生成还包括本项目替换、融合的内核）。不在里面：Streamline 在 Evaluate 之外的工作、同一组 Evaluate 之间的空隙（只在 `fgw` 里）、呈现与节奏控制、游戏自己的渲染。同时跑在别的队列上的工作会让它变长，那是真实代价。
- 代价（RTX 3070 实测）：每次 Evaluate 的 GPU 时间多约 3–8 µs（两个时间戳加一次回读拷贝；4X 帧生成每真实帧多 13–20 µs，即 +0.3–0.5 %），超分每次 Evaluate 的 CPU 时间多约 7–13 µs。不改任何像素：开与不开，超分与帧生成的输出逐字节相同。
- 大小：一行约 70–100 字节，每秒汇总约 0.3 KB；60 fps 每小时约 23 MB，120 fps 约 45 MB。帧行写到 64 MiB 为止（一行 `cap` 说明），之后只写每秒汇总（每小时约 1 MB），整个文件到 256 MiB 停止。

读：`python scripts\perf\frame_timing_report.py <frames_A.jsonl> [<frames_B.jsonl>]` 给每个文件一段汇总（真实帧率，`dt` / `sr` / `fg` 的 avg / p50 / p95，GPU 占用率，各段上下文）；给两个文件时再给一段 B 对 A 的差，毫秒与百分比都列。`--skip-seconds N` 去掉开头 N 秒（加载画面）。

### [Debug]

| 配置项 | 值 | 默认 | 说明 |
|---|---|---|---|
| `MarkGeneratedFrames` | `0/1` | `0` | `1` 在生成输出上绘制 `FG 1/3` 等实际序号标记，用于区分毛刺出现在生成帧还是真实帧。真实帧和 Reset 输出跳过。标记会改动生成帧像素，做全图数值比较时请关闭。 |
| `MarkerX` / `MarkerY` | `0`–`65535` | `8` / `8` | 标记左上角坐标（输出纹理像素）。 |
| `MarkerScale` | `1`–`8` | `2` | 标记缩放倍率；矩形为 `24×scale` 宽、`9×scale` 高。 |
| `Capture` | `0`–`100000` | `0` | 录多少次 Evaluate 的参数、输入和输出，供离线重放（GCR）。`0` 完全不装任何钩子，性能影响为零。数的是 Evaluate 次数（3× 每真实帧 2 次、6× 每真实帧 5 次）。1080p RGBA8 约 48 MB/次。完整机制见 `docs/CAPTURE.md`。 |
| `CaptureDirectory` | 路径 | `dlssg_sm86\capture` | 抓取目录，相对游戏 EXE 目录。 |
| `CaptureSkip` | `0`–`1e8` | `0` | 先跳过多少次 Evaluate（跳过加载画面 / 过场）。 |
| `CaptureStartOnReset` | `0/1/2` | `1` | 从哪一帧开始录。`2`：只等“刚创建完特性之后的第一次 Evaluate”，是重放能逐位一致的唯一起点；`1`：`DLSSG.Reset` 帧或新建特性的第一帧，先到先算；`0`：立刻开始。`1`/`2` 等满 3 分钟不到就什么都不录。 |
| `CaptureStartKey` | 键名 / VK 码 | `0` | 按键触发起点：`F9`（F1–F24）、单个字母或数字，或虚拟键码（`120` / `0x78`）。设了之后 `CaptureSkip` 满足后继续等，直到在游戏里按下这个键，再从那一刻应用 `CaptureStartOnReset` 的规则（`0` = 按下的那次 Evaluate 立刻开始录，`start_reason=key`；`1`/`2` = 从按键起再等 Reset / 新建特性，3 分钟超时从按键算起）。这是让抓取落在“人物正在运动”那一刻的办法；等待期间记 `capture_waiting_for_key`，按下记 `capture_start_key`。 |
| `CaptureNoStall` | `0/1` | `0` | `1`：游戏线程永远不等。整份抓取缓冲在系统内存里：环和请求的次数一样深、回读缓冲由写盘线程在等待起点期间提前建好、录满之后文件在后台写完（`capture_finishing` → `capture_done`），所以录到的是连续的帧；组的内存按预热时学到的尺寸整组估算（第一组或没有东西在飞时总是放行，预算小于一组时退化成一次只录一组），预算不够时整组跳过（组 = 同一真实帧的全部生成帧，`MultiFrameIndex` 1..count），绝不在组中间丢平面或丢帧。`0`：4 槽环、写盘跟不上时游戏线程最多等 2 秒（4K 下游戏会降到几帧）。事件 `capture_prewarm` / `capture_group_skipped`，manifest `capture.taken_groups` / `skipped_groups` / `skipped_groups_memory`。重放时每个间隙后的第一组只用来暖运行库的上一帧历史，`capture_compare.py` 默认把它排除在汇总外。 |
| `CaptureRingSlots` | `0`、`4`–`1024` | `0` | 在飞的回读槽位数；`0` = 默认（4，`CaptureNoStall=1` 时等于 `Capture` 的次数）。 |
| `CaptureMemoryMB` | `0`–`1048576` | `0` | 回读内存预算（池里的 + 在飞的），MiB；`0` = 安装时可用物理内存的一半。回读堆在系统内存，不占显存。 |
| `CaptureAsyncCopy` | `0/1` | `1` | `1`：把 PCIe 传输从渲染时间线上挪走。游戏自己的命令列表里只做显存→显存的 `CopyResource`（拷进一张暂存纹理），再由一条独立的 `COPY` 队列把暂存纹理搬进回读缓冲，和游戏渲染并行；`COPY` 队列先 `Wait` 游戏那次提交的 fence，`collect()` 等的是 `COPY` 队列自己的 fence。`0`：回读拷贝留在游戏的命令列表里（旧路径，3070 实测 4K 每生成帧 +122 %）。事件 `capture_plane_inline`（某个平面退回旧路径）、`capture_async_copy_unavailable`（这台机器建不出 `COPY` 队列/列表，全部退回旧路径）。 |
| `CaptureVramMB` | `0`–`1048576` | `0` | 暂存纹理的显存预算，MiB；`0` = 1536。暂存纹理按 (设备, 格式, 尺寸) 池化复用，`COPY` 队列读完就还池，所以稳态只需要几组的量；超出预算的平面退回逐平面的内联回读并记 `capture_plane_inline`，抓取不会因此不完整。`CaptureAsyncCopy=0` 时这个键没有作用。 |
| `CaptureLean` | `0/1` | `0` | `1`：只回读不能重建的数据。同一组内 index>1 的 Evaluate 交出的输入资源和 index 1 完全相同（三份悟空抓取 54/54 个纹理平面逐字节一致），所以只记成对 index 1 文件的引用；`DLSSG.OutputReal` 是运行库对 `DLSSG.Backbuffer` 的拷贝（18/18），也记成引用。被引用的平面 json 里 `stored=false`、`source=<相对抓取根目录的文件>`，`sm86_replay` 与 `capture_compare.py` 会跟过去。4X 下每组字节约减半，回读的 PCIe 时间同步减少。16 字节的 buffer 参数总是照录。 |
| `CaptureInputs` | `0/1` | `1` | `0` 不录输入像素（体积大幅下降，但不能重放）。 |
| `CaptureOutputs` | `0/1` | `1` | `0` 不录 `OutputInterpolated` / `OutputReal` 像素。 |
| `MfgProbe` | `0/1` | `0` | `1` 记录每一次对帧数参数的 set 与 get，带调用方模块名、槽位、值和上下文，用来判断“生成几帧”是谁决定的。复用抓取的参数存储钩子，但 `Capture=0` 时也能单独工作。事件与判定见 `docs/MFG_PROBE.md`。 |
| `NgxLog` | `0/1` | `0` | `1` 给 NGX 核心装一个我们自己的日志回调（钩它的四个 `NVSDK_NGX_D3D12_Init*`，把 `NVSDK_NGX_FeatureCommonInfo::LoggingInfo` 换成我们的），核心与它的 snippet 自己写的日志行落到 `[Logging] Directory` 下的 `ngx_log_<pid>.txt`——**这是唯一能读到"运行库最终选了哪个 DLSS 预设"的地方**（snippet 的 `Render Preset:` 行只经宿主回调输出）。武装点是 `_nvngx.dll` 的加载（核心的 Init 早于游戏请求帧生成运行库），所以这个键**只装后端、不碰运行库、不做 GPU 检测**。永远不让 Init 失败、不拿掉游戏自己的日志 sink、不抬高游戏声明的 SDK 版本（低于 `0x14` 时核心不会用这个回调，`ngx_log_init.logging_honoured` 如实记 `false`）。文件可以边跑边看。 |
| `NgxLogLevel` | `1/2` | `1` | `NgxLog=1` 时的 `NVSDK_NGX_Logging_Level`：`1` = on（`Render Preset:` 就在这一级），`2` = verbose（行数多很多）。 |
| `QueueTrace` | `0`–`4096` | `0` | 记 N 条 `queue_submit`，回答"帧生成的命令列表到底提交在哪条 D3D12 队列上、和下一帧有没有重叠"：每批提交一条，带队列指针与**类型**（`queue_type_name`：direct / compute / copy）、优先级、这一批的列表数、是否载有 Evaluate 拿到的那个列表（`carries_fg_list`）、本次 Evaluate 的第几次 FG 提交、上一批 FG 提交此时是否仍在 GPU 上（`prev_fg_batch_complete`）；写满 N 条再记一条 `queue_trace_summary`（进程里每条队列的批数 / FG 批数）。与 `Capture` 独立：不拷贝、不落盘，只钩 `ID3D12CommandQueue::ExecuteCommandLists`（与抓取共用那一个跳板，用一条自建、永不提交的队列读共享 vtable）。旧构建不认这个键时 loader 记 `capture_unsupported`。 |

#### DLSS 超分输入抓取（`docs/CAPTURE_SR.md`）

和上面那套帧生成抓取**完全独立**：它钩的是 NGX 核心而不是 DLSS-G 运行库，**在从来不加载 DLSS-G 的游戏里也能用**
（只要游戏开了 DLSS 超分或 DLAA，帧生成不必打开，显卡也不必是 Ampere），任何 DLSS 版本（2.x / 3.x / 310.x）、
游戏直接调 NGX 还是经 UE 插件 / Streamline `sl.dlss` 都一样。录的是 DLSS 超分（NGX feature 1）每帧的
颜色 / 深度 / 运动矢量 / 曝光输入和全部参数，给 INT8 超分工作做真实内容的标定与验证。`CaptureSR=0` 时整套机制不存在
（连后端都不会为它加载）。用**光线重建**（Ray Reconstruction，feature 13）的游戏不创建 feature 1，这时什么都录不到，
后端会记一条 `capture_sr_feature{stage:"other_feature"}` 说明原因。

**`[General] Enabled=0` 不会关掉它**：那个键关的是帧生成那套（替换内核的部分），而这套抓取不属于它。
`Enabled=0` + `CaptureSR=N` 就是“只采集输入”的部署：随包的 DLSS-G 运行库文件连打开都不打开、`nvngx_dlssg.dll` 原样交给系统
（没有 `runtime_redirect`）、不调 `DlssgMod_Install`（不检测 GPU、不替换内核、不做融合）、不改 NVAPI 架构上报、
不做 `turing_host`。loader 会记一条 `capture_sr_only` 把这份“没做什么”的清单写出来，`capture_sr_requested` 带
`mod_enabled` / `runtime_extracted` / `dlssg_untouched` 三个字段。CTest `capture_sr_disabled_mod` 钉住这条路。

| 键 | 取值 | 默认 | 说明 |
|---|---|---|---|
| `CaptureSR` | `0`–`4096` | `0` | **每段**录多少帧 DLSS 超分（超分每个真实帧只调一次 Evaluate）。`0` = 关闭。`CaptureSRFrames` 是同义别名。 |
| `CaptureSRDirectory` | 路径 | `dlssg_sm86\capture_sr` | 绝对路径，或相对于游戏 EXE 目录。 |
| `CaptureSRStride` | `1`–`100000` | `1` | 段内每 N 次 Evaluate 录 1 帧。标定要的是**内容多样性**而不是连续切片：60 fps 下步长 30 把 100 帧摊到 50 秒的游玩，而不是 1.7 秒里几乎一样的 100 帧。`>1` 时这一段不再连续，`pack.json` 的 `source.consecutive` 为 `false`。 |
| `CaptureSRBursts` | `0`–`4096` | `1` | 一局最多录几段；一段 = 按一次起录键。`1` = 传统的“录一次就结束”，`0` = 不限：想按几次按几次，直到写满 `CaptureSRMaxGB` 或游戏退出。每段一个 `burst_NNNN\` 子目录，都登记在同一份 `manifest.json` 的 `bursts[]` 里。 |
| `CaptureSRMaxGB` | `0`–`4096` | `0` | 整局写到多少 GiB **像素**就停（`params.json` 与各平面 `.json` 不算在内）。`0` = 不限。这是不限段数时**唯一**的界，所以 `CaptureSRBursts=0` 而这个键是 0 时后端会替你放一个 **8 GiB 默认上限**并记一条 `capture_sr_options`。到上限时记 `capture_sr_done{stage:"budget"}`，已经录下的照常可用。 |
| `CaptureSRDedup` | `0/1` | `1` | `1`：整局里内容（SHA-256）相同的平面只写一份，后面的 json 写 `stored=false` + `source` 指过去（和帧生成抓取的 lean 引用同一套约定）。1×1 曝光纹理、没变的 mask、静态平面因此每局只存一次。离线工具会跟着引用走。 |
| `CaptureSRSkip` | `0`–`1e8` | `0` | 先跳过多少帧。 |
| `CaptureSRStartKey` | 键名 / VK 码 | `Insert` | 按键触发起点。可写 `Insert` / `Delete` / `Home` / `End` / `PageUp` / `PageDown` / `Pause` / `ScrollLock`、`F1`–`F24`、单个字母或数字，或虚拟键码（`45` / `0x2D`）。`0` = 不用按键。默认不是“无”而是 Insert：标定要的是玩家走到的真实画面，而三种自动起点都落在菜单或固定计数上。多段时**每段都要重新按一次**（按键必须先松开，否则按住半秒会一次开完所有段）。等待期间记 `capture_sr_waiting_for_key`。 |
| `CaptureSRStartOnCreate` | `0/1` | `0` | `1`：按键之后继续等，直到“刚新建的超分特性”的第一帧——DLSS 超分把全部时域状态留在特性内部，只有那一帧的历史是空的，也只有从那里起录，离线重放才可能复现游戏自己的输出（在游戏里就是去设置里把 DLSS 关掉再打开）。**只对“一段 + 步长 1”有意义**，其它设置下后端把它关掉并记一条 `capture_sr_options` 说明原因（一个带步长或多段的会话本来就不是某个特性历史的连续切片）。等满 3 分钟不到就什么都不录（`capture_sr_done{stage:"start_timeout"}`）。 |
| `CaptureSRLean` | `0/1` | `1` | `1`（默认）：不回读游戏自己的 `Output`。它能靠重放输入重新生成，而且是 4K 下最大的一个平面；`0` 才录（要和游戏自己的输出对账时）。 |
| `CaptureSRNoStall` | `0/1` | `1` | `1`（默认）：游戏线程永远不等写盘，回读缓冲提前建好，录满后在后台写完；内存或槽位不够时整帧跳过（`capture_sr_skipped`）。`0`：4 槽环 + 游戏线程最多等 2 秒（录到的一定完整但会卡）。 |
| `CaptureSRRingSlots` | `0`、`4`–`128` | `0` | 在飞的回读槽位数；`0` = 默认 `min(每段帧数, 16)`（至少 4）。**不再等于帧数**：一局能录几千帧，而环只需要盖住写盘的延迟（每帧几毫秒，带步长时两帧之间还隔着整帧时间），16 个 4K HDR 槽位约 0.5 GB，128 个就是 4 GB。 |
| `CaptureSRMemoryMB` | `0`–`1048576` | `0` | 回读内存预算（MiB）；`0` = 配置时可用物理内存的一半。 |
| `CaptureSRVramMB` | `0`–`1048576` | `0` | 暂存纹理的显存预算（MiB）；`0` = 1536。 |
| `CaptureSRAsyncCopy` | `0/1` | `1` | 和 `CaptureAsyncCopy` 同义：把 PCIe 传输挪到独立的 `COPY` 队列上。 |

后三个预算是两套抓取**共用**的池，由**先配置的那一份**决定；一般 SR 先配置（它在 `nvngx_dlss.dll` 加载时就装好了）。
事件：`capture_sr_requested` / `_unsupported` / `capture_sr_only`（loader），`capture_sr_hooks` / `_install` /
`_options` / `_feature` / `_prewarm` / `_waiting_for_key` / `_start` / `_burst` / `_frame` / `_skipped` / `_done`（后端）。

落盘之后还有三步离线处理（开发侧，都只用 Python 标准库）：无损压缩并逐个校验 SHA-256、把一堆会话列成表（按内核族、
分辨率、预设、DLSS 版本）、转成给探针重放的输入包（可以每段一个包）。抓取格式见 `docs/CAPTURE_SR.md`。

### [Compatibility]

| 配置项 | 值 | 默认 | 说明 |
|---|---|---|---|
| `OptimizedKernels` | `0`–`3` | 档位 0（见旧名说明） | `[DLSSG] Optimized` 最老的**旧名**，接受同样的档位范围；`[DLSSG] Optimized` 或 `[FrameGeneration] Optimized` 写了时它被忽略。老 INI 里的 `OptimizedKernels=1` 仍然是档位 1。写了它就记一条 `configuration_warning` 指向 `[DLSSG] Optimized`（它生效时 `default` 为 `(honoured)`，被忽略时为 `(ignored)`）。 |
| `KernelImage` | `Auto/PTX/Cubin/Original` | `Auto` | 内核加载格式，见下表。**cubin 被驱动拒绝时自动回退到同一内核的 PTX**（见“驱动版本要求与 cubin → PTX 自动回退”）。`Original` 只装钩子不替换任何内核（本机取原厂数值参考；**Ampere 上用不了这一项**——310.9.1 的原厂图像内核是 sm_89，Ampere 上创建失败，本机参考请用 `Optimized=0`+`KernelImage=PTX`）。 |
| `Router` | `Auto/SM86/SM75` | `Auto` | 内核族。`Auto` 按物理 GPU 选（SM86 及以上走 SM86，Turing 走 SM75）。**SM75 是实验项**。`Optimized=1` 时创建 63 个变体行（60 个网络变体 + 3 个按 310.9.1 RVA 重新推导的图像补丁）、跨内核合并与图像补丁全开，日志记一条 `sm75_route_limits`（`variant_rows=63`、`image_patches_partial` 为空）；纹理探针挂靠的那个内核 310.9.1 已删除，所以 `HardwareBilinear` 强制为 0。3070 前向 JIT 上与 SM86 原厂路线逐位一致（含 6×）；**真 Turing（RTX 2080 Ti）上**：sm_75 cubin 与 PTX、档 0 与档 1 都逐位一致，且同一份输入下的输出与 RTX 3080 Ti 的输出逐位一致（rotate 合成场景 32/32；两者与 RTX 5070 上官方输出的差异也逐字节相同，是 Blackwell 与 Turing/Ampere 之间的硬件累加差）。Turing 上的性能尚未测量。SM75 原厂内核族来自 Coldwood1026（见 `THIRD_PARTY_NOTICES.txt`）。 |
| `SM75Family` | `Repaired/Original` | `Repaired` | 仅在 `Router=SM75`（或物理 Turing）时有意义，选哪一份**导入的 sm_75 原厂内核族**。`Repaired` 是本项目修复过的那份：Coldwood1026 的 f16x2 min/max 模拟经一块用通用地址寻址的 `.local` 缓冲交换半字（未定义行为，9 个 DL2 内核 342 处），已按值等价地改写进寄存器，72 个 cubin 也由修复后的 PTX 重新编译——**默认值，本仓库的全部结果都是在它上面测的**。`Original` 是原样导入的那份（cubin 逐字节是 Coldwood 的二进制，PTX 只做了 `.version` 归一化），留着是因为离线 `ptxas` 会给未修复的 PTX 分配真栈帧，**原厂 cubin 路径在真实 Turing 上很可能从来没碰到这个缺陷**，而只有 20 系实机能回答；给真实 Turing 用户做 A/B 用。以 PTX 为输入的 JIT 路径（非 Turing 卡上的前向 JIT，3070 实测）用 `Original` 会重现修复前那张 43–73 dB 的表。只换原厂内核，我们自己重写的变体与图像补丁不受影响；只覆盖 310.9.1 与 310.1 共用的 44 个内核（310.9.1 新增的 26 个没有"原样"版本）。走 SM86 路线时该键完全无效，日志记一条 `sm75_family_ignored`。 |
| `Preset` | `Auto/A/B/C` | `Auto` | **旧位置**：2026-10-14 起是 `[DLSSG] Preset`；这里写的只在 `[DLSSG] Preset` 没写时生效，并记一条旧名告警。DLSSG 渲染预设（UI 重组）。`Auto` 不干预；`A` 强制关闭 UI 重组；`B` 强制开启（需要游戏同时提供 HUD-less 与 UI 平面，另占两张全分辨率 FP16 表面）；`C` = FG Lite（UI 重组关 + 轻量候选混合，只有 310.9.16 运行库有；310.9.1 上记 `preset_unsupported`、什么都不钉）。详见下面小节。 |
| `SpoofArchToGame` | 缺省 / `0/1` | **缺省 = 自动** | 只管**游戏（以及代它做判断的 Streamline）那道架构闸门**。**这是个三态键**：**不写**（出厂 INI 就没有这一行）= 自动，**写 `1`** = 显式，两者装重定向的时机完全一样——取下面五个时机里最早的那个，与显卡无关；**写 `0`** = 永不装（这一档在完整解析 INI 之前就要知道，所以 loader 在启动时先用 kernel32 的 `GetPrivateProfileStringW` 单独读一次 `[General] Enabled` 与本键，值非法或为空都当自动），Turing 上记一条 `arch_spoof_disabled{redirect_installed}`。自动与显式 `1` 的唯一区别在**日志**：自动档只在确认这是 Turing 主机之后才把 `arch_spoof_*` 记录放出来（第一次真正改写，或后端的 Turing 判决 + `turing_host_defaults`），所以**非 Turing 显卡上出厂 INI 一条 `arch_spoof_*` 都不会有**。为什么要装这么早：**Streamline 2.x 在 `slInit` 里就决定帧生成插件"本硬件不支持"** —— `sl.dlss_g` 默认最低架构 AD100，`sl.common` 拿每个适配器的 `NvAPI_GPU_GetArchInfo` 架构去比它，然后把插件卸掉（日志里是 `Ignoring plugin 'sl.dlss_g' since it is not supported on this platform`），这发生在 D3D 设备存在之前、远早于 NGX 核心向我们索要 DLSS-G snippet，所以任何"等运行库加载之后"的武装都来不及（RTX 2080 Ti + FF7 Rebirth / Streamline 2.8.0.0 实测：写 `1` 与不写这一行的结果一模一样，插件都不在进程里）。机制：把 `nvapi64.dll` 导出表里 `nvapi_QueryInterface` 那一项重定向到该模块自己节尾填充里的 14 字节跳板，使 `NvAPI_GPU_GetArchInfo` 对外报告一个更新的架构（报哪个由下一行的 `SpoofArchValue` 决定：默认对 Turing 和 Ampere 都报 Blackwell `0x1b0`；不改任何 NVIDIA 代码字节；**NVIDIA 自己的组件一律看真实架构**：`_nvngx.dll`、`nvngx_*`、`nvapi*`、我们自己的 `sm86_backend.dll`、`\DriverStore\FileRepository\` 下的驱动组件，以及 **NGX 模型库里的 snippet**——NVIDIA App 的「DLSS override」或 NGX OTA 之后，核心是从 `C:\ProgramData\NVIDIA\NGX\models\dlss\versions\<n>\files\160_E658700.bin` 这样的路径加载超分 / 光线重建 / 帧生成 snippet 的，名字里没有 `nvngx_`，0.3.3 把它们一起骗了，超分 snippet 于是走 `arch>=0x180` 的内核路径把 GPU 挂死（创建 SuperSampling 特性之后立刻 `DXGI_ERROR_DEVICE_HUNG`，帧生成都还没被创建；issue #535，以及启动崩溃 #538 / #540 / #542），所以 0.3.4 起 `\NVIDIA\NGX\models\` 下除 `sl_*` 以外的每个组件、以及任何 `.bin` 模块都看真实架构；`models\sl_*`（Streamline 自己的 OTA 插件）正是要改写的对象，照常改写）。日志里每个**不同的**调用方模块一条 `arch_spoof_applied`（新增 `path` 字段给出完整路径），被排除的调用方每个模块一条 `arch_spoof_excluded`，所以能看出是谁问的、又给了它哪个答复。**只有真实答案是 Turing（`0x160`）或 Ampere（`0x170`）才改写**（Ampere 是 0.3.3 加入的：RTX 3060 Laptop 在 FF7 Rebirth 上与 2080 Ti 现象相同，issue #509）：别的架构上重定向照装但什么都不做，并记一条 `arch_spoof_inert{real_arch,rewritten_archs}`；完整解析 INI 后读到 `0`（启动时那次读不到 INI 的情况）也会让它立刻停止改写。`arch_spoof_installed` 带 `trigger` 与 `default`：**早期三档** `dllmain`（我们被加载时 `nvapi64.dll` 已在进程里）/ `nvapi_load`（我们的 LoadLibrary 钩子接住了 `nvapi64.dll` 自己的加载）/ `dependency_load`（`nvapi64.dll` 作为别的模块的静态导入进来，某次加载之后才发现它在）——只有这三档赶在 `slInit` 之前；**兜底两档** `settings`（读完 INI，即游戏第一次索要 `nvngx_dlssg.dll`）/ `backend`（后端装完）。`default=true` 表示是自动档做的决定，与早晚无关。**它与 NGX 核心的 `0xbad0000b` 无关**：那一条是核心拿显卡架构去比运行库导出的最低架构（见下面 `fg_gate_create_feature` 一行），任何 NVAPI spoof 都改不了。 |
| `SpoofArchValue` | `Auto/Ada/Blackwell` | `Auto` | 改写时对外上报哪个架构。`Auto`（默认）对 **RTX 20（Turing）和 RTX 30（Ampere）都报 Blackwell（`0x1b0`）**：随包的运行库做多帧生成，后端本来也是以 Blackwell 主机的身份把适配器交给运行库，而游戏和 Streamline 的 3X / 4X / 6X 选项正是按这个架构放开的——报 Ada 能过帧生成那道闸门，但游戏里只剩 2X（真 20 系实测，issue #527 / #528）。`Ada`（`0x190`）留作**诊断覆盖**：0.2.4 与 0.3.0–0.3.2 对外报的就是它，需要对比时可以写回去。`Blackwell` 显式写死同一个值（两者也接受 `0x190` / `0x1b0`）。**这个值从来不是 0.3.3 崩溃的原因**：崩的是 NVIDIA 自己的 DLSS 超分模型也收到了改写后的架构——NVIDIA App 的「DLSS override」或 NGX 在线更新生效时，它是从 NGX 模型目录里按 `160_E658700.bin` 这样的名字加载的，按叶名的排除规则拦不到；3070 上实测报 Ada 与报 Blackwell **都**会挂 GPU，而把这个 snippet 排除之后**两个都不会**，所以修的是「按路径排除 NVIDIA 自己的组件」（`src/common/spoof_policy.h`，见上一行），不是换一个更小的架构。和 `SpoofArchToGame` 一样在启动时用 kernel32 单独读一次；值非法回到 `Auto` 并记一条 `configuration_warning`。`configuration.spoof_arch_value`、`arch_spoof_installed{spoof_arch_value,reported_arch_turing,reported_arch_ampere}`、`arch_spoof_applied.reported_arch`（432 / 400）说明实际用的是哪个。 |
| `AccelerateNewerGpus` | 缺省 / `0/1` | **缺省 = 按架构的默认：RTX 40、RTX 50 都是开** | RTX 40（sm_89）/ RTX 50（sm_120）上要不要也跑本项目的帧生成内核（上面"RTX 40 / RTX 50"一节）。`0` = 运行库自己的内核（0.4.0 之前的行为）；`1` = 跑本项目的内核，不管默认是什么；不写 = 默认（两代都开，后端 `src/common/kernel_selection.h` 的 `newerGpus::kAdaDefault` / `kBlackwellDefault` 各一行）。开着时与 RTX 30 一样按 `Optimized` 的档位换内核，镜像是 PTX；只装内核创建钩子和运行库内部的 SM 答复，**不装** RTX 30 / 20 需要的架构桥接（snippet 最低架构、requirements、`GPU_GetArchInfo`），不新增倍率。`KernelImage=Cubin` 在这条路线上按 PTX 跑（没有 sm_89 / sm_120 cubin），`KernelImage=Original` 时不开这条路线（这两代卡本来就能跑运行库自己的内核）。**在 RTX 30 / 20 上不起作用**：写了只在 `configuration` 里多一个 `accelerate_newer_gpus` 字段。值非法按不写处理，记一条 `configuration_warning`。 |
| `ForceSM86Route` | `0/1` | `0` | `1` 允许在非 SM86 GPU 上强制走 SM86 后端做验证（低于 SM86 仍被拒）。这是验证配置：它连 RTX 30 那套架构桥接一起装上，与 `AccelerateNewerGpus` 不是一回事。 |
| `SimulateAmpere` | `0/1` | `0` | `1` 为验证调整架构上报（运行库自己读到的架构改成 Ampere）；必须同时 `ForceSM86Route=1`。不改物理 GPU。`AccelerateNewerGpus` 的路线不需要它，也不会装它。 |
| `LaunchChains` | `0/1` | `0` | **实验项，不要开启（会降低性能甚至有害）**。`1` 把连续内核提交攒成 `NvAPI_D3D12_LaunchCuKernelChain`。5070 上无收益（每次 Evaluate 慢 2–3%），**310.9 上实测有害**（中位 Evaluate 超出最小值 3–120 倍）。保留只为在别的驱动 / GPU 上复测。 |
| `DisableFusions` | `0`–`63` | `0` | **诊断位掩码（打开会变慢）**，关闭 `OptimizedKernels` 的某类跨内核合并：1 解码器 upscale+add+1×1，2 解码器 1×1 对，4 `k_initial_merge`+convPre，8 conv0+池化，16 残差链，32 `k_central_block`+block1 conv0。默认 0 = 全部合并开启。 |
| `PlainVariant` | `0`–`3` | `0` | 同一内核登记了多个替换实现时选第 n 个（越界取最后一个）。**默认 0 是实测最快的一组**；改成 >0 是换备选实现复测，通常更慢。 |
| `ImagePatches` | `0/1` | **档位决定**（档位 ≥1 为 `1`） | `0` 关闭图像处理内核的**精确** PTX 级补丁（需要档位 ≥1）。补丁语义不变、逐位一致。有损行由 `ImageApprox` 管、不受它影响；**`CatmullRomWarp` 与 `DetailRestore` 的行也是图像补丁行，`ImagePatches=0` 会一并关掉它们**（那两个键因此记一条 `configuration_warning`）。档位 0 不建任何行，在那里写 `1` 不起作用（同样记一条）。 |
| `HardwareBilinear` | `0/1` | `0`（2026-10-05 起没有档位打开它），实际恒为 `0` | **不起作用**：后端把它强制关掉。它原是退役的 310.1 运行库一个合成内核的纹理单元路径（用纹理单元双线性采样代替手写 fp32 混合，旋转场景最底一行可差 12 LSB），310.9.1 没有那个内核。键仍被解析（第 3 级，诊断），写了就记一条 `configuration_warning` 说明它在本构建上不起作用；`Optimized=3` 不再要求它。 |
| `ChainBlock0` | `0/1` | `0` | `1` 把 DL2 block0 的 8 个残差卷积也换成持久化链内核。5070 上与 8 次原生提交**持平**（无收益），默认关闭；其它 GPU 可复测。 |

### [SuperResolution]

**DLSS 超分（NGX feature 1）路线**，与帧生成互相独立。**玩家只需要知道 `Mode=Off` 与 `Mode=On`**（2026-10-10 起；
`Mode` 的另外四个值与 `Tier` 是进阶键，见下面"进阶键"；机制与验证在 `docs/SR.md`）。**出厂 INI 写着 `Mode=Off`，与整节缺席
完全相同：这个进程与没有这段代码的版本逐字节相同**（不拦 `nvngx_dlss.dll`、不 hash 那份 74 MB 的 snippet、不装钩子、一条
`sr_*` 记录都没有，`configuration` 连字段都不多一个）。

**游戏里开着光线重建（Ray Reconstruction）时，这一节不起作用。** 光线重建取代超分：游戏创建的是 NGX feature 13（DLSS-D，
降噪与放大由同一个网络完成），**根本不创建 feature 1**，所以 `Mode` 与 `Tier` 一个都用不上；画质档仍然决定
渲染分辨率，跑的是游戏自己的光线重建（本项目不碰它，见下一节）。在游戏设置里关掉光线重建，超分路线就回来。
赛博朋克 2077 实测：路径追踪 + 光线重建的整局里没有一条 `sr_*` 记录、没有 feature 1。

**`Mode=On` 做什么**：把游戏请求的超分 snippet 换成随包的 **310.7.129**（`dlssg_sm86\sr\nvngx_dlss.dll`），**不改任何
画质档的预设**——每一档拿**游戏自己的请求**（下面单独一段：Streamline 写的提示被还原，NVIDIA App 的预设覆盖生效时照 App 的，
都没有时是运行库自己的答案）——然后看这个特性所在档**最终**是哪个预设：**是 L 或 M，就换成本项目的静态 INT8 内核**（M 的
12 个网络内核；L 在 RTX 30 / RTX 20 上两族游戏（地平线 6 / Resonance / 巫师 3 / 蜘蛛侠，以及悟空 / 霍格沃茨）都是 10 个——第一层
与最后一层留在运行库自己的 FP16 内核上，那两层的 INT8 在这两代卡上反而更慢，`docs/SR.md` 第 3 节——加上逐位等价的 post /
downsample 重写）；是 K 或更早的 CNN 预设，就跑 NVIDIA 自己的内核。多数游戏里被加速的是**性能档（M）与超级性能档（L）**，
画质 / 平衡 / DLAA 通常是 K、原样不动。3070 实测一次 Evaluate 的 GPU 时间（INT8 对同运行库、同预设的 FP16，1080p–4K × 四档 × 两族）：
M −9.4…−23.2 %（−0.10…−2.12 ms）、L −6.5…−16.3 %（−0.08…−1.89 ms）；巫师 3 游戏内帧率（帧生成关）M +5.1…+7.9 %、
L +1.2…+4.0 %。

**On 换掉的是游戏的 DLSS 版本**：游戏自带的超分运行库比 310.7.129 旧时，同一个提示在两个版本里可能解出不同的预设，所以开 On
之后某一档的预设可能随之变化（On 自己从不改预设）。地平线 6、Resonance、巫师 3 的抓取里 Streamline 写的提示都是
K/K/K/M/L（DLAA / 画质 / 平衡 / 性能 / 超级性能），还原之后就是这一组。

**同一局里在性能档与超级性能档之间切换**：L 与 M 共用十个同名内核，运行库每局只建一次，先用上的那个预设占着它们。所以一局里
先在性能档（M）玩、再切到超级性能档（L）时，超级性能档这一局跑 NVIDIA 自己的内核（日志一条 `sr_route_preset_refused`），
切回性能档照旧是 INT8；反过来也一样。想让后切到的那一档也加速，在那一档下重开游戏。其它档（K）不受影响。

**只在 RTX 30 与 RTX 20 上生效**。第一次加载 `nvngx_dlss.dll` 时、换任何东西之前，代理先问一次显卡（CUDA 驱动 API：
计算能力与显卡名）并读随包内核包 `sr_kernels.dll` 的索引：只有某块 NVIDIA 显卡是 sm_86 或 sm_75、**名字里有 `RTX`**、且包里有它的集合，
才介入。**其它任何情况——RTX 50、RTX 40、GTX 16 与 Turing T 系列（也是 sm_75，但没有张量核心）、MX570、没有 CUDA、
包读不到——行为与 `Mode=Off` 完全一样**：不换 snippet、不装钩子，日志里多一条警告级 `sr_gate` 说明原因（GTX 16 一类是
`reason:"device_not_rtx"`；`configuration` 里照抄 INI 的 `super_resolution` 字段仍在，那是读 INI 时写的）。
RTX 40 / 50 排除是因为它们自己的 FP8 路径比我们的 INT8 快，介入没有收益（RTX 50 的 sm_120a 验证集合产品里没有任何
配置执行，2026-10-11 起不进发布包，见下面 `KernelSetSM` 一行）。RTX 20 在名单上，但它的宿主权重宽度还没在真卡上量过：INT8 路线可能在第一帧拒绝，
那时每一档跑的是它的预设 + NVIDIA 自己的内核，没有崩溃路径。

| 配置项 | 值 | 默认 | 说明 |
|---|---|---|---|
| `Mode` | `Off`/`On` | **`Off`** | 上面几段。另外四个值见下面的进阶键。写错的值按 `Off` 处理并记一条 `configuration_warning`。 |

**"游戏自己的请求"是什么**：随包的 310.7.129 丢掉一切带位 31 的预设提示，而 Streamline 写的正是
`0x8000000B/C/D`（K/L/M），放着不管每款游戏就会落到运行库自己的候选表。3070 实测（`sr_create.tiers[].runtime_resolved`，
DLAA / 画质 / 平衡 / 性能 / 超级性能）：地平线 6 → K/K/K/M/L；Resonance → C/C/C/C/B；巫师 3 → F/A/A/A/F——后两款是比
游戏自带运行库更旧的 CNN 预设（它们自带的运行库在性能档跑的就是 M：帧率与钉成 M 的 FP16 相差不到 0.1 %，Resonance
47.77 对 47.79 fps，巫师 3 47.14 对 47.14 fps）。所以拿游戏自己请求的档——`On` 下是全部六档，进阶的四个值下是没选中的档——
**把游戏写的提示还原**（本构建有那个预设才还原：A–F、J、K、L、M）；裸提示（悟空的 `3` = C）与没写提示的档交给运行库自己。
**NVIDIA App 的预设覆盖生效时，这些档照 App 的来**（`On` 下 App 选的若是 L / M，同一预设换成 INT8 内核）；进阶值钉住的档是
你在 INI 里的明确选择，压过 App，日志里记一条 `sr_preset_drs_conflict`。

**游戏内 A/B（验证 On 的收益）**：同一场景、同一画质档，`Mode=On` 对 `Mode=M-FP16` + `Tier=Performance`（性能档两边都是
随包运行库 + 预设 M，只差内核；超级性能档用 `Mode=L-FP16` + `Tier=UltraPerformance`）。不要拿 `Mode=Off` 当基线：那是游戏
自带的运行库和它自己的预设，差的不只是内核。

**进阶键**（不在出厂 INI 里）：

| 配置项 | 值 | 默认 | 说明 |
|---|---|---|---|
| `Mode` | `M-INT8`/`L-INT8`/`M-FP16`/`L-FP16` | — | 2026-10-03 起的四个**钉值**，行为与日志不因 `On` 的加入改变。同样换成随包的 310.7.129，但在 `Tier` 选中的档上**钉住** M 或 L（没选中的档拿游戏自己的请求）。`X-INT8` 在选中的档上跑我们的静态 INT8 内核；`X-FP16` 一切相同、只是内核是 NVIDIA 自己的——**同字母 INT8 的 A/B 对照**（同运行库、同预设，只差内核）。 |
| `Tier` | `Auto`/`Quality`/`Balanced`/`Performance`/`UltraPerformance` | **`Auto`** | 钉值作用在哪些画质档上：`Auto` = 全部六档（含 DLAA 与超高画质），写一个档名就只作用于那一档；**没选中的档拿游戏自己的请求，并且永远跑 NVIDIA 自己的内核——哪怕它解出来也是 M / L**。在 `On` 下它只是过滤器：`Auto` = 六档都可以跑 INT8，写一个档名就只有那一档可以（其它档照样拿游戏自己的请求、跑 NVIDIA 的内核）。写错的值按 `Auto` 处理并记一条警告。 |

**钉值怎么用**：INT8 的收益在运行库本来就用 L / M 的档，数字与上面 `On` 一段相同（同一套内核；例：`Mode=M-INT8` +
`Tier=Performance`）。把 M 放到画质 / 平衡 / DLAA 档（`Tier=Auto`）是换网络，
3070 上 K 比 M 快 1.24–3.66 倍、比 L 快 1.48–4.77 倍，所以那是画质 / 实验选择，不是加速（Resonance 画质档 47.5 → 38.1 fps）——
这正是 `On` 不钉预设的原因。钉值的 A/B：同一个 `Tier`、同一场景，`Mode=M-INT8` 对 `Mode=M-FP16`，两局只差内核。

**预设与画质档是两个维度**：画质档决定渲染/输出分辨率的比例，预设再选权重与网络。**钉预设不改变渲染分辨率**。

**已移除的键**：`Int8`、`Int8L`、`Int8M`、`ForcePreset`、`ForcePresetDLAA` / `ForcePresetQuality` / `ForcePresetBalanced` /
`ForcePresetPerformance` / `ForcePresetUltraPerformance` / `ForcePresetUltraQuality`。旧 INI 里还有这些行时，每个记一条
`configuration_warning`（`default` 是 `(removed)`）然后忽略——**所以旧 INI 的 `Int8=1` 不再打开任何东西，没有 `Mode` 行
就是 Off**。

**诊断键**（不在出厂 INI 里，玩家不需要；没有一个能让介入在上面那道检查不放行的显卡上发生）：

| 配置项 | 值 | 默认 | 说明 |
|---|---|---|---|
| `Auxiliary` | 0/1 | 1 | 跑 INT8 的特性（`On` 下 L / M 的档、`X-INT8` 选中的档）连 post / downsample 的逐位等价重写一起替换。**只在 D3D12 上生效**：Vulkan 路线无条件拒绝它们（COMPAT C57 —— 在那条 API 上替换进去的不再是运行库自己的比特，而 post 内核写时域历史，差异每帧回灌到像素饱和），日志里是 `auxiliary_allowed:false` 与 `auxiliary_refused`。 |
| `KernelImage` | `Auto`/`Ptx`/`Cubin` | `Auto` | 先试哪一族镜像。集合里每个内核有两张：`.nvapi.fatbin`（PTX，驱动要 JIT）和 `.cubin.nvapi.fatbin`（本架构的原生 cubin，不用 JIT）。**`Auto` 与 `Cubin` 都优先 cubin**，`Ptx` 根本不看它。`Cubin` 永远是"优先"而不是"只要"：集合里没有 cubin 镜像、或驱动拒绝了它，就退回 PTX 并记一条 `sr_kernel_image_fallback`（每进程最多一条，错误级）。**这就是这张镜像存在的理由**：只有 PTX 时，游戏第一次创建特性（以及每次改画质档重建）要让驱动编译 12 个约 600 KB 的内核。诊断开关 `DLSSG_FORCE_CUBIN_FAIL=1` 只弄坏 cubin 镜像，用来在任何驱动上走一遍这条退回（与弄坏**全部**镜像的 `DLSS_SM86_FORCE_IMAGE_FAIL=1` 不是一回事，后者会让整条路线关掉）。 |
| `ObserveFrames` | 0–64 | 1 | 先观察几帧、把每个 launch 的合同逐条验过再开始替换。`1`（默认）观察第 1 帧、第 2 帧起替换。`0` 是测量用的：第一帧起就替换，每个 launch 仍先过自己的合同，但放弃了那一帧的"全有或全无"（3070 实测：8 帧里 8 帧都被替换，`1` 时是后 7 帧）。 |
| `KernelSet` | 路径 | `dlssg_sm86\sr` | 内核集**包**在哪里。默认目录里是发布的内核包 `sr_kernels.dll`（一个只有资源的 DLL，装着 RTX 30 / 20 的四套集合，每个 (架构, 输入族) 一套；后端读全部，按显卡的 compute capability 选）；它以文件随包、不内嵌进代理（约 106 MB，一个发布里有六个代理名）。目录里有 `sr_kernels.dll` 就读它，即使旁边还留着旧版的 `index.json`；没有就按目录包读（一个 `index.json` + 集合目录，研究用的集合就这么指，规则与以前相同）；值也可以直接是一个包 DLL 的路径。相对路径相对代理自己的目录。**设备闸也读这里**：没有本机集合 = Off。设备闸只读包的闸门摘要（`sr_kernels.dll` 的 INDEX 资源，或目录包 `index.json` 里的 `gate_summary`），所以指向单个集合的目录、2026-10-04 之前生成的目录包（没有摘要）、或缺了 `sr_kernels.dll` 的发布也 = Off，`sr_gate` 的 `sets` 里写着原因（`kernel_set_source` 说读的是包还是目录）。包本身损坏时由后端整包拒用（`sr_kernel_set{loaded:false}`，`source.reason` 写明哪一项），游戏跑 NVIDIA 自己的内核。 |
| `KernelSetSM` | `Auto`/`75`/`86`/`120` | `Auto` | **诊断/测量用，玩游戏请保持 `Auto`。** 换一个架构的内核集在本机上跑（前向 JIT）。`Auto` 用显卡自己的 compute capability，这是唯一正常的取值。**覆盖生效时镜像族被强制成 PTX**（cubin 是一个架构的机器码，驱动收不下），记一条 `sr_kernel_image{forced_ptx:true}`；**包里没有那个架构的集合时整条路线被拒绝**而不是悄悄换回本机的集合（`sr_kernel_set_override{applied:false}`、`route.disabled_reason="kernel_set_override_missing"`、`replaced` 恒 0）；外来架构上宿主权重缓冲宽度那道闸被豁免并逐 launch 计数（`route.binding_waivers`），其余合同（入口名、专用内核摘要、block、几何）照旧。设备闸判的是**显卡本身**，所以 3070 上的 `KernelSetSM=120` 能过闸；发布的内核包里没有 sm_120a 集合（2026-10-11 起），于是路线在建任何内核之前以 `kernel_set_override_missing` 拒绝，画面是 NVIDIA 自己的内核。把 `KernelSet` 指向带 sm_120a 集合的目录包时它会被选中——**但跑不起来**：PTX 只能往上 JIT，驱动不收 sm_120a 的 PTX，每个内核创建失败（`sr_kernel_create_failed`），路线以 `specialization_missing` 拒绝（3070 实测 2026-10-10）。一张卡只能这样跑本机或**更老**架构的集合：3070 上是 `75`，2080 Ti 上只有它自己的 `75`（在它上面写 `86` 同样建不出内核），任何 RTX 30 / 20 都跑不了 `120`。**它存在的理由**：`set_sm_75` 与 `set_sm_86` 的权重镜像逐字节相同，只有机器码不同，所以一台 RTX 30 跑一遍 `Auto`、一遍 `75` 就能证明 sm_75 那 12 个内核算出来的东西一样——而 RTX 50 上做同一件事什么都证明不了（Blackwell 的累加与 Ampere/Turing 不同）。详见 `docs/SR.md` 第 8 节。 |

每一道闸门都朝"游戏自己的 DLSS"失败：显卡不在名单上、文件缺失、哈希不符、预设或输入族没有对应资产、显卡不在内核集
声明的架构里——全部是"照原样转发、或跑 NVIDIA 自己的内核，并记一条日志"，绝不会让特性创建失败。

**LDR（色调映射后的颜色）输入的游戏按设计不加速**：这一族没有标定内容，路线在建任何内核之前就明确拒绝并记一条常规级
`sr_family{chosen:false, by_design:true, family:"mvlo_ldr"}`；`On` 下每一档是游戏自己的预设、钉值下选中的档照样钉
Mode 的预设，跑的都是 NVIDIA 自己的内核（等同 X-FP16）——这是 NVIDIA 自己的代码，不是故障，日志里也不会有任何错误级记录
（详见 `docs/SR.md`「输入族」一节）。

**Vulkan 游戏**（荒野大镖客 2 一类）上这条超分路线**同样成立**：同一份运行库、同一套内核集、同一组 `Mode` / `Tier`。
换内核的机制不同（改 snippet 自己那张 Vulkan 入口点表里的五个函数指针，而不是打代码补丁），但对使用者只有三条区别：
① **Vulkan 游戏只能用四个工具类代理名**（根目录的 `version`，或 `alternatives\` 的 `winmm` / `dbghelp` / `dinput8`）——
`dxgi.dll` / `d3d12.dll` 在 Vulkan 后端下根本不会被加载；② 游戏建 `VkDevice` 时若没开 `VK_NVX_binary_import`
扩展，路线整条关闭并记 `sr_vk_entrypoints{installed:false}`，游戏照跑 NVIDIA 自己的内核（这个决定发生在我们能
介入的一切之前，没有旋钮能改）；③ **`[Debug] Capture` 与 `[Debug] CaptureSR` 只在 D3D12 上工作**，
`[FrameGeneration]` 整节在 Vulkan 上本轮也未支持。日志里认这条 API 的字段是 `sr_install` / `sr_exit` 的
`api:"vulkan"`、`sr_vk_install`、`sr_vk_entrypoints`、`sr_device{api:"vulkan"}`、`sr_resource_hook{api:"vulkan"}`，
以及第一次用到 Vulkan NGX 时才出现的 `fg_gate_hooks_vk`。**这条路线目前只有静态与无 GPU 的证据**，见
`docs/COMPAT.md` 缺口 G13。

### [RayReconstruction]（已删除）

**2026-10-09 起本项目不碰光线重建**（NGX feature 13，业主决定；为什么见 `docs/RR.md`）。原来的 `Mode=Mixed` 把游戏请求的
光线重建 snippet 换成随包的 310.9.0.0、钉预设 F、跑混合 INT8 内核集；赛博朋克 2077 实测它与游戏自己的光线重建帧率持平
（4K 超级性能档、帧生成 4X：26.86 对 26.89 fps），对玩家没有好处，所以整条删除。现在 `nvngx_dlssd.dll`（游戏目录里的，或
NVIDIA App 覆盖时模型库里的）**原样加载**：不拦截、不 hash、不装钩子、一条 `rr_*` 记录都没有——与原来出厂的
`Mode=Off` 完全相同（写了 `[Debug] CaptureSR` 时，它的加载照旧像 `nvngx_dlss.dll` 的一样武装超分抓取，好让日志说清
"这个游戏用的是 feature 13"）。发布包里不再有 `dlssg_sm86\rr\`，老安装留下的这个目录不会被读取，可以删。

**光线重建一开就取代超分**：游戏只创建 feature 13，`[SuperResolution]` 的设置在这期间全部不生效（上一节开头）；
要测超分 INT8 就在游戏里关掉光线重建。

**旧键**：这一节的 `Mode`（原是第 2 级的键）、`KernelSet`、`KernelImage`、`Observe`、`ObserveFrames`，以及 `[Runtime] RRMode` /
`RRPath`、`[Debug] CaptureRR` / `CaptureFeature`，**仍被读取，只为告警**：写了（非空值）就记一条 `configuration_warning`
（`default` 是 `(no effect)`），不起任何作用；空值等同于没写。2026-10-03 就已删除的 `Int8`、`Int8Observe`、`ForcePreset`、
六个 `ForcePreset<档>`、`KernelSetSM` 照旧各记一条（`default` 是 `(removed)`）。所以旧 INI 里的 `Mode=Mixed` 不会让
任何东西发生。

### [Runtime]

| 配置项 | 值 | 默认 | 说明 |
|---|---|---|---|
| `Path` | 路径 | `dlssg_sm86\runtime\nvngx_dlssg.dll` | `Mode=External` 与 `Mode=Pinned` 使用，指向 `nvngx_dlssg.dll`。`Auto` 不使用；**默认值就是 `Bundled` 用的那个文件**，所以 `Mode=External` 不写 `Path` 等价于 `Bundled`（与 `SRPath` 同构）。 |
| `CacheDirectory` | 路径 | 空 | **惰性**。以前是 bundle 缓存的根目录；现在没有缓存（什么都不释放），写了非空值只会记一条 `configuration_warning`，其余什么都不变。键仍被解析，老 INI 不会因此失效。 |
| `SRMode` | `Bundled`/`External`/`Pinned` | 跟随 `Mode` | 超分 snippet 的同一套选择（`Auto` 与 `Mode=Auto` 一起在 0.4.0 删除，按 `Bundled` 运行并告警）。**默认跟随 `Mode`**：把一个 NVIDIA snippet 外置、钉住或关掉的人基本都是两个都想要。`Bundled` = **包里那个文件** `dlssg_sm86\sr\nvngx_dlss.dll`（74 MB，不内嵌进 DLL——一个发布有六个代理名），用之前校验 SHA-256；不在或不对就记 `sr_runtime_unavailable` 并把游戏交回它自己的 DLSS。 |
| `SRPath` | 路径 | `dlssg_sm86\sr\nvngx_dlss.dll` | `SRMode=External` 与 `SRMode=Pinned` 使用。哈希不符会记 `external_runtime_rejected{feature:"super_resolution"}`（`Pinned` 是 `sr_pinned_runtime_rejected`）+ `configuration_warning` 并回退 `Bundled`。 |
| `RRMode` / `RRPath` | — | — | **已删除**（2026-10-09，随光线重建路线）：没有可选的光线重建 snippet 了，游戏自己的 `nvngx_dlssd.dll` 原样加载。写了只记一条 `configuration_warning`（`default` 是 `(no effect)`）。 |

`Mode` 值：`Bundled`（普通安装，随包的 `dlssg_sm86\runtime\nvngx_dlssg.dll` + 随包的后端）；**`External`（运行库放在别处，由 `Path` 指定——见下一段）**；（`Auto`——加载游戏请求的原运行库——在 0.4.0 删除，旧值按 `Bundled` 运行并记一条 `configuration_warning`，COMPAT C86）；`Pinned`（使用 `Path` 指定的运行库，需匹配后端）。加载 / 安装失败会记 `runtime_selection_failed` 并回退原始请求。
超分那一侧，游戏（或 NVIDIA App 的覆盖）已经映射了 310.7.129 时，任何模式下都不需要替换，只装钩子，记 `sr_runtime_adopted`。

#### `Mode=External`：运行库放在代理外面

```ini
[Runtime]
Mode=External
Path=dlssg_sm86\runtime\nvngx_dlssg.dll
SRMode=External
SRPath=dlssg_sm86\sr\nvngx_dlss.dll
```

- **路径写法**：绝对路径，或**相对于代理 DLL 自己所在的目录**——不是进程的工作目录。Steam、快捷方式的"起始位置"、
  以及自己 `chdir()` 到数据目录的引擎都会让工作目录变成别的东西，而代理是用户亲手放在游戏 EXE 旁边的，
  所以只有它能让同一份安装每次解析到同一个文件（`[Logging] Directory` 等所有相对路径本来就是这条规则）。
  写 `%LOCALAPPDATA%` 这类**环境变量会先展开**（仅 `External`；`Pinned` 的路径按字面用）。
- **必须是这个构建的后端服务的那个运行库**（或在 `[Backends]` 里给它配了后端）。不符就记一条错误级
  `external_runtime_rejected{feature,path,sha256,reason,action:"bundled_runtime_used"}` + 一条 `configuration_warning`，
  然后**回退 `Bundled`**——绝不会变成"什么都不做"。拿错的是本项目另一个发布包里的运行库时，记录会直接把它叫出名字
  （`runtime_version` / `expected_version`，比如"它是 310.1.0.0，而这个构建的后端服务 310.9.1.0"）。
- `Mode=External` 而 `Path` 没写**不再是需要纠正的配置**：`Path` 的默认值就是随包那个文件，所以它解析到和 `Bundled`
  完全相同的结果（`SRPath` 一直是这样）。以前那条 `configuration_warning` 已经删掉。
- 日志里认哪一档：`runtime_redirect` / `sr_runtime_redirect` 的 `selected_source` = `bundled` / `external` / `pinned` /
  `game_own`，外加 `sha256`（**答话那个文件本身**的摘要，四种模式都写）；`source` 仍然只说请求是**从哪儿来的**：
  游戏目录 / NGX 模型库 / 驱动库。
- **包里的运行库缺失或不是这个构建的那一份**时 `Bundled` 无处可退：每进程一条错误级
  `bundled_runtime_unavailable{path,sha256,runtime_sha256,found_version,reason,remedy}`，把 `nvngx_dlssg.dll` 原样交回
  游戏——**绝不会悄悄变成 `Auto`**。最常见的原因是只复制了代理 DLL 而没有复制 `dlssg_sm86\` 这个文件夹。
  判定在**加载之前**：哈希不符的模块根本不会被映射进进程。

### [Backends]

高级外部后端映射，默认无此节。键是目标原运行库的完整 SHA256，值是匹配后端 DLL 路径，仅 `Pinned` / `External` 需要（`[DLSSG] Preset=C` 时非 310.9.16 的映射不会被用上，见上面 `Preset=C` 一句）：

```ini
[Backends]
; <runtime-sha256>=backends\matching_backend.dll
```

外部后端最好支持内核选择扩展（可选导出 `DlssgMod_SupportedRouteFlags`）。不支持（或只支持一部分）时，loader 把该后端答不了的标志位**去掉之后照常安装**，并记一条 `kernel_selection_unsupported{requested_flags,supported_flags,stripped_flags,effect:"installed without them"}`；那些开关无效，但帧生成本身不会因此没有。注意出厂默认的最佳集本身就带着 `NO_HW_BILINEAR` / `NO_CHAIN_BLOCK0` 两个诊断位，所以不带该导出的旧 ABI 后端一定会出现这条记录（它的 `supported_flags` 为 0，全部被去掉）。

### KernelImage 行为

| KernelImage 值 | 路由启用后的行为 |
|---|---|
| `Auto` | 物理架构与所选内核族相同时用预编译 cubin，否则用 PTX。cubin 被驱动拒绝时自动回退到 PTX。 |
| `PTX` | 总是用所选内核族的 PTX，由驱动 JIT；3080 Ti 也适用。 |
| `Cubin` | **优先**用预编译 cubin，要求物理架构与内核族**完全一致**，否则拒绝安装该路径（默认 Bundled 下回退原始加载）。架构一致但驱动拒绝 cubin 时仍会回退 PTX（宁可 JIT 也不要没有帧生成）。**cubin 在随包的内核包 `dlssg_sm86\kernels\fg_kernels.dll` 里**（与 PTX 同在，后端 DLL 不带任何内核）：那个文件不在时写 `Cubin` 会记一条 `configuration_warning` 并当作 `Auto`，后端随后记 `kernel_pack_missing`、不启用路由。 |
| `Original` | **诊断/参考用**：装钩子但**一个内核都不替换**，也不启用优化 / 合并 / 图像补丁。与 `PTX`/`Cubin` 互斥，与 `Router` 无关。**Ampere 上用不了。** |

`KernelImage` × `Router` 的实际选择：

| Router / 物理 GPU | `Auto` | `PTX` | `Cubin` |
|---|---|---|---|
| SM86 族，物理 SM86（3070/3080 Ti） | `cubin_sm86` | `ptx_sm86` | `cubin_sm86` |
| SM86 族，物理 SM89/SM120（`AccelerateNewerGpus`，0.4.0 起默认） | `ptx_sm86` | `ptx_sm86` | `ptx_sm86`（没有这两代的 cubin，按 PTX 跑） |
| SM86 族，物理 SM89/SM120（`ForceSM86Route` 强制路由验证） | `ptx_sm86` | `ptx_sm86` | 拒绝 |
| SM75 族，物理 SM75（RTX 20 系） | `cubin_sm75` | `ptx_sm75` | `cubin_sm75` |
| SM75 族，物理 SM86 及以上（前向 JIT 验证） | `ptx_sm75` | `ptx_sm75` | 拒绝 |

SM75 族与 SM86 族在 RTX 3070 的前向 JIT 上**逐位一致**（原厂族与优化集都是，box + rotate 两个场景 7 个分辨率 240/240 张，**`--multi 5`（6×）另外 80/80 张**；MFG 相位（`i/(N+1)` 质心）两条路线完全相同；`m16n8k16` 拆成两条 `m16n8k8` 并没有多出一次与原厂不同的舍入）。310.9.1 的 70 个内核里，44 个用与 310.1 共用的那一族 sm_75 原厂内核，26 个新内核的 sm_75 镜像由本项目从自己的 sm_86 PTX 改写而来。优化集在 SM75 上**一行不少**：63 个变体行（60 个网络变体 + 3 行图像补丁）都有 sm_75 镜像。退役的 310.1 构建上同样逐位一致（240/240 张，`HardwareBilinear=1` 时两条路线的输出也逐位相同）。

数值在 RTX 3070 上以 `.target sm_75` 前向 JIT 验证为与 SM86 路线逐位一致；**真 Turing（20 系实机，2026-09-15/17）**上 `sm_75` cubin 全族创建并运行、0 回退，cubin 与 PTX 逐位一致，档 0 与档 1 逐位一致，游戏内可用。Turing 上的耗时尚未量化。详见 `docs/VALIDATION.md`。

#### 驱动版本要求与 cubin → PTX 自动回退

| 路径 | 最低驱动 | 原因 |
|---|---|---|
| cubin（`Auto` 在物理 SM86 上、`Cubin`） | 约 **R580+**（本机 591.86 实测可用） | 全部 cubin 由 CUDA 13.0.2 的 `ptxas` 生成（ELF ABI 65） |
| PTX（其它架构、`PTX`） | 约 **R555+**（PTX ISA 8.5） | 所有 PTX 声明 `.version 8.5`，由驱动 JIT |

驱动落在两者之间时 cubin 创建会失败：**后端用同一内核的 PTX fatbin 原地重试一次**，之后该镜像家族（基础 / 变体 / 图像补丁三类各自独立）改用 PTX。因此驱动偏旧的唯一后果是首次加载多一次 JIT，帧生成照常、数值逐位一致。日志里找 `kernel_image_fallback`（错误级，每进程一次）。诊断变量 `DLSSG_FORCE_CUBIN_FAIL=1` 可强制触发这条路径（仅用于验证）。

#### `SkipRepeatedRealCopy`（已删除）

这个键曾让后端在 `MultiFrameIndex > 1` 时吞掉运行库的全分辨率 `CopyResource(Backbuffer → DLSSG.OutputReal)`。2026-10-08 删除：运行库只在调用方交出 `DLSSG.OutputReal` 时才发这次拷贝，而检查过的全部 Streamline `sl.dlss_g` 构建（2.6.10–2.14.1，9 个）只在 index 1 交出它、之后传空，所以 Streamline 游戏里没有重复的拷贝可跳（5 个游戏的抓取里 index ≥ 2 的 `OutputReal` 300/300 为空；巫师 3 实机 3486 次 Evaluate 跳过 0 次）。每真实帧省几十到几百微秒的数字只出现在本项目自己的 `sm86_scene` / `sm86_bench` 里，它们在 2026-10-08 之前每个 index 都传 `OutputReal`（之后与 Streamline 一样只在 index 1 传）。现在 INI 里写这个键（非空值）只记一条 `configuration_warning`（`default` 是 `(no effect)`），不起任何作用。

#### 档位 2 / 3：有损图像行，以及“看不出差别”是怎么回事

档位 2 / 3 武装的是本项目里**唯一一批刻意不与官方运行库逐位一致**的内核镜像（内核包清单里的 `approx` 行）。

**档位 2（2026-10-04 起出厂默认）只武装一行**：A6，`Kernel_OutputPull` 的两次 warp 取样从手写双线性降为最近点（掩码 `0x20`）。实测：

- **对官方数值**：RTX 3070，三份 4K 4X 真实游戏抓取，档位 2 的重放对档位 0 的重放（档位 0 就是官方运行库的数值），生成帧逐帧 PSNR 最差 / 中位：Resonance 44.06 / 48.06 dB（运动最快的一份，每真实帧位移 250–500 px，最低值在第 46–90 次 Evaluate 那一段），地平线 6 49.59 / 51.34 dB，黑神话悟空 49.87 / 52.09 dB；RTX 5070 上对官方 DLSS-G 输出：赛博朋克 2077 49.8 / 53.5 dB，黑神话悟空 53.2 / 56.3 dB。偏差随画面运动变大，不随历史累积：同一份抓取从中途新建特性重放，逐帧差在 ±0.5 dB 以内。
- **对真值**：五份抓取的跳帧真值上，全帧比档位 1 低 0.02–0.13 dB（五份都是“劣”）；94 648 个区块里比档位 1 差 1 dB 以上的 229 个、好 1 dB 以上的 36 个。把两者差得最多的区块（两个方向都挑）并排看，包括 Resonance 最快的那一段与地平线 6，**看不出差别**：档位 1 碎的地方档位 2 一样碎，位置也一样。
- **速度**：RTX 3070，4X，每生成帧比档位 1 快 1.8 %（1080p）/ 1.8 %（1440p）/ 2.9 %（4K，2207 → 2142 µs；`sm86_bench --hooks 0`，0.4.0）。0.4.0 之前是 2.6 / 2.9 / 4.5 %（2379 → 2272 µs，旧测法带逐 launch 打点与每个 index 一次真实帧拷贝），差距变小是因为 0.4.0 的精确补丁让档位 1 的 `Kernel_OutputPull` 快得更多：P8/P9 快了 58 µs，A6 本来就是 40 寄存器，只多拿到 P8 那一半；P10 在 bench 上让档位 1 再快 20 µs，而 A6 只剩两次取样可以提前，bench 上 1080p / 1440p 持平到略慢（每生成帧 +0.3…+2 µs）、4K 快 3 µs——真实 4K 游戏抓取上两档从 P10 拿到的差不多（这个内核 −4…−9 µs）。这个内核自己快约 16%（5070），但它只是生成帧里的一部分，帧率变化很小是预期。

**这一档出厂的理由是“并排看不出差别”，不是“离官方近”。** 档位的判据仍是“离官方输出多远”，按这个判据档位 2 在最快的运动上离官方 44 dB，所以它不逐位一致、也不再用“约 50 dB 以上”来描述；业主按并排目视判断它与档位 1 没有可见差别，换来每生成帧 3–5 %。要和官方画面逐位对照，用档位 1。

档位 3 再加两行实验性的：A1（`Kernel_WarpBlendingWeights`，40.5 / 46.8 dB 与 53.0 / 58.9 dB；4K 上这个内核快 12%、1080p 只快 0.9%，而它占一个生成帧的 2%）和 A5（`Kernel_EstimateIntermMvecsScatter`，scatter 半径钳到 3，52.9 / 62.7 dB 与 56.0 / 67.5 dB；合成场景上收益为 0，收益完全取决于画面内容，**从未在游戏内容上量过**；它同时是 MFG 相位内核，开它之后插值相位要重新核对）。用 `ImageApproxMask` 可以逐行点名。

**RTX 20（SM75）上这两档一样生效**：每一行都有 sm_75 镜像，后端武装它们时不看内核族。

怎么确认它到底武装了没有（把 `[Logging] Level` 临时改成 `2`，看后端日志）：

- 一条 `image_approx`：`enabled`、`optimized_tier`、`mask` 与 `mask_from`（INI 指定还是档位默认）、`rows`、`armed[]`（每行的入口名、标签 `A1`/`A5`/`A6`、槽位与资源号）、`exact_patches_replaced`。`enabled` 只对真正会运行的行为真：要求了却不会运行（档位 0、`KernelImage=Original`、路由没启用）时 `enabled=false`，`disabled_reason` 写明原因。
- 每武装一行各一条 `optimized_create`，带 `row="image_approx"`、`approx="A6"`、`entry`、`image`（`cubin_sm86` / `ptx_sm86` / `cubin_sm75` / `ptx_sm75`）和 `resource`。
- `install` 的 `optimized_tier` / `optimized_tier_name` 与 `optimized_knobs.image_approx` 说明档位最后解析成了什么。

这些记录都在、而画面与帧率都没有明显变化，就是这一档做到了它该做的事，不是它没生效。

#### Preset：A / B / C 预设（UI 重组、FG Lite）

`[DLSSG] Preset`（2026-10-14 之前是 `[Compatibility] Preset`）是**本 mod 自己的 INI 键**，不是 NVIDIA Inspector / NVIDIA App 里的那个设置——在那些工具里改预设不经过本键；反过来，本键写了 `A`/`B` 之后会盖掉驱动 / NVIDIA App 的预设覆盖，想让驱动说话就保持 `Auto`。

驱动 / NVIDIA App 里的 DLSS 帧生成“渲染预设 A / B”在 310.9.1 内部只对应一个布尔量：UI 重组（`DLSSG.UserInterfaceRecompositionEnabled`）。`A` = UI 被烘进颜色历史一起插值（HUD 会被运动矢量拖影）；`B` = HUD-less 颜色与“UI 颜色+Alpha”分开插值（静止 HUD 不被拖动）。`B` 需要游戏同时提供 `DLSSG.HUDLess` 和 `DLSSG.UI`，否则画面与 A 一致但白占两张全分辨率 FP16 表面（1080p 约 33 MB、4K 约 133 MB）。每次创建特性记一条 `preset_pinned`。

**预设 C（FG Lite，310.9.16 起，可选）。** 310.9.16 多了一个开关“轻量候选混合”（游戏参数 `DLSSG.LiteCandidateBlendingEnabled`，驱动预设 `0x10E41DF1 = 3`）：每个生成帧不跑 DL2 网络和它的后处理，改跑 `Kernel_BlendCandidatesFGLite` + 两个小内核，UI 重组同时关掉。`Preset=C` 把 UI 重组与 Lite 两组覆盖值一起钉住（`preset_pinned` 多出 `lite_*` 字段）。3070 实测（`sm86_bench`，档位 2）每生成帧 2× −32…−36 %、4× −46…−54 %（4× 下 1080p 0.946 → 0.437 ms、4K 2.167 → 1.181 ms）；画质对跳帧真值全帧 −0.20 / −0.27 dB，HUD 区块 −1.84 dB（赛博朋克，强制关 UI 重组），细节能量更高（更锐、遮挡处更块状）。**没有官方参照**：官方运行库在 RTX 30 上不跑，预设 C 对官方的逐位比较要一张 40 / 50 卡，目前只证明了本项目各条路线之间自洽（cubin / PTX / SM75 / 档位 0 逐位相同）。出厂仍是 `Auto`，C 只在写了才生效。

**两张平面交不交由游戏决定，不由这个键决定。** 本机的两份 4K 抓取正好是两种情况：黑神话悟空两张都交，`Preset=B` 真的改变画面；赛博朋克 2077 只交 `DLSSG.HUDLess`、不交 `DLSSG.UI`，在它上面写 `Preset=B` 是空操作。想知道自己的游戏属于哪一种，用 `scripts\game\dlssg_diag_capture.cmd` 录一份抓取，报告 `== 抓取 ==` 一节里的 `HUD 平面:` 一行直接写明游戏交出了哪几张。**这一行需要抓取才能给出**：普通运行的日志里没有任何记录能回答它。

**它不是细结构闪烁的解法。** `Preset` 只决定 UI / HUD 走哪条路，场景内容（植被、栏杆、细线条）本身的插值不受它影响。它对应的是 HUD / 浮空 UI 抖动那一类现象，见下一节。

#### 已知的画面瑕疵与它们的归属

**细结构闪烁（植被、草、栏杆、文字）、遮挡边缘的重影与画面左右边框伪影、转视角时的拖影**：这些是运行库自己的插值算法在做的事，不是本项目引入的。判据是逐位比较，**在档位 1 上做**——档位 1 是逐位一致的参照档：`Optimized=1` 下，两份 4K 真实游戏抓取（共 120 次 Evaluate）离线重放的输出与**官方 NVIDIA 运行库在同一批输入上的输出逐位相同**：`differing_pixels 0`、`max_abs_diff 0`，320 张平面全中。同样的输入产出同样的像素，所以这一类现象在官方路径上同样存在。出厂的档位 2 在档位 1 上只多换了一行图像内核（A6），输出不再逐位一致，但与档位 1 的差别并排看不出来，这一类现象在两档上以同样的样子、在同样的位置出现（上一节）。怀疑某个现象是本项目造成的，先把 `Optimized` 改成 `1` 再看。多位报告者一致说**倍率越高越明显**；但“基础帧率低”不是唯一因素——也有人在基础帧 90 以上、以及 4X 下 155 fps 时照样看到（公开 issue #61 / #493）。用户侧唯一有过闭环报告的缓解手段是降低 `MaxGeneratedFrames`（issue #82，2X），而 issue #171 报告 2X 下仍然有。

**整屏闪烁 / 频闪是另一回事**，它与画面内容无关。公开仓库里已经闭环的几例分别来自：RTSS / MSI Afterburner 的覆盖层（issue #99）、另一个改画面的 MOD（体积雾，issue #523）、交换链模式（切一次窗口化再切回、或打开垂直同步就消失，issue #60 / #68 等多条）。这几例都是报告者自己确认的闭环，不是本机实测。issue #532（绝区零，0.3.2）**没有闭环**：公开帖子里报告者没有确认过任何改动的效果。当时怀疑的 `SkipRepeatedRealCopy` 在 Streamline 游戏里不起作用：绝区零带的 `sl.dlss_g` 是 2.11.1（版本号来自同帖另一位用户的日志），本机验过的 2.11.1 与其余 8 个构建一样只在 index 1 交出 `OutputReal`。在绝区零那份是 NVIDIA 签名原版的前提下，闪屏不是这个键造成的；原因至今没有定位。遇到整屏闪烁按这个顺序排除：关掉覆盖层 → 只留本 mod、移除其它改画面的 MOD → 切一次窗口化 / 打开垂直同步。

**HUD / 浮空 UI 抖动**走的是另一条路径，见上面 `Preset` 一节。

**要把某一条现象真正定性，只能靠抓取。** 按 `docs/CAPTURE.md` 在现象正在发生时录一份（`scripts\game\dlssg_diag_capture.cmd`，按 Insert），同一机位再录一份 `Optimized=0` 的做对照，就能在一张受支持的显卡上离线重放并与官方运行库在同一批输入上的输出逐像素比较：官方输出同样有 = 运行库算法的性质；官方输出没有 = 本项目的缺陷，而且有了逐像素的定位起点。至今没有收到过任何一份画质抓取（`docs/COMPAT.md` 缺口 G8）。

**第三方分支里的画质开关**（例如 `QualityValidWarp`）改的是 NVIDIA 自己的候选混合内核，输出因此不再与官方运行库一致，上游三个项目对它的画质测量次数是 0。本项目**实现过并量过，然后撤回了**：在 11 份真实游戏抓取、14 组配置上，非 HUD 区域 13/14 组测不出改善，HUD 区块变坏，而在唯一一份真正会闪的抓取上 4X 的交替量也变坏。所以本项目**没有**这类键。走同一个内核但**不引入任何判据**的重采样改动是另一回事，见 `CatmullRomWarp`。

## 如何确认配置生效

在 Level 2 或 3 的日志中检查（出厂 `Level=1` 只记错误，验证配置时临时改成 `2` 或 `3`）：

| 事件 / 字段 | 含义 |
|---|---|
| loader：`configuration` | 本次读取的 INI、运行库模式、内核格式请求，以及 `optimized_tier`/`optimized_tier_name`（解析后的一致性档位）、该档位解出的每个旋钮（`optimized_kernels`/`image_patches`/`image_approx`/`image_approx_mask`/`hardware_bilinear`/`chain_block0`/`launch_chains`）、`warnings`（本次回退了几个键）、`proxies`（`{active, standby[]}`，哪个代理在干活）。 |
| loader：`configuration_warning`（Level 1） | 某个键的值非法，已回退到该键默认值：`section`/`key`/`value`/`default`/`reason`/`effect`。mod 仍然启用，只有这个键无效。每个出问题的键一条。另外两种：旧键名（`default` 为 `(honoured)` / `(ignored)`，`reason` 写出新键）与在当前配置下不起作用的键（`default` 为 `(no effect)`：档位 0 或 `ImagePatches=0` 下的 `CatmullRomWarp` / `DetailRestore`、档位 0 下的 `ImagePatches=1` / `ImageApprox=1` / `PlainVariant` / `DisableFusions` / `ChainBlock0`、没有有损行可选时的 `ImageApproxMask`、任何 `HardwareBilinear`、任何非空的 `SkipRepeatedRealCopy`（已删除））；`effect` 写明是哪一种。 |
| loader：`configuration_error`（Level 1） | 整份配置根本读不了（路径无法构成、内存不足），mod 关闭并保留游戏原始加载。**普通拼写错误不会走到这里**，那是上一行。 |
| loader：`kernel_selection_unsupported`（Level 1） | 后端不支持 INI 要求的某些标志位：`stripped_flags` 是被去掉的位，`effect` 为 `installed without them`——**安装照常进行**，只是这些开关无效。 |
| loader：`proxy_forward_incomplete`（Level 1） | 本机 System32 里的那个系统 DLL 没有导出代理转发表里的全部名字（Windows 版本比打包机器旧，或 Wine/Proton）：`library`/`resolved`/`missing`/`missing_names`。这几个转发器会答 `ERROR_PROC_NOT_FOUND`，**其余转发与 mod 本身不受影响**。以前缺一个名字就让 DllMain 失败、游戏直接 `0xc0000142` 起不来且不产生任何日志。 |
| loader：`runtime_redirect` | 这一次 `nvngx_dlssg.dll` 的请求是由谁来答的：`mode`（`bundled`/`external`/`pinned`/`auto`）、**`selected_source`（同一件事的四值写法：`bundled`/`external`/`pinned`/`game_own`，回退之后它说的是真正跑的那一档）**、`requested`、**`source`（请求是从哪儿来的：`game_dir` 游戏自己的安装目录 / `ngx_model_store` NGX 模型库 = NVIDIA App 的 DLSS 覆盖开着 / `driver_store` 驱动库里的那份 / `other`，裸文件名也算 `other`，真正解析到的路径在 `game_runtime.path`/`resolved_by`）**、`selected`、`game_runtime_used`，以及 **`game_runtime`——被替换掉的那个文件（游戏自带的那份）的身份**：`path`/`resolved_by`/`bytes`/`sha256`、`file_version`（该信的那一个）与它的两个来源 `file_version_fixed`（版本资源固定块）/`file_version_string`+`product_version_string`（`StringFileInfo` 字符串）、`snippet_version`（`NVSDK_NGX_GetSnippetVersion` 的立即数，`0x01360901` = 310.9.1）、`generation`（`A`/`B`/`unknown`）与 `generation_marker`（哪个判据定的）。读不了就只是 `available=false` + `reason`，重定向照常。 |
| loader：`external_runtime_rejected`（Level 1） | `[Runtime] Mode=External` / `SRMode=External` 指定的文件用不了：`feature`（`frame_generation` / `super_resolution`）、`key`、`configured`（INI 里怎么写的）、`path`（展开并解析之后的全路径）、`sha256`、`expected_sha256`/`expected_version`、`runtime_version`（认识它时把它叫出名字，比如"它是 310.1.0.0"）、`reason`、`action`（`bundled_runtime_used` / `bundled_snippet_used`）。**同时还有一条 `configuration_warning`**，mod 本身照常运行。 |
| loader：`bundled_runtime_unavailable`（Level 1） | 每进程一条：`[Runtime] Mode=Bundled`，但 `dlssg_sm86\runtime\nvngx_dlssg.dll` **不在**（最常见：只复制了代理 DLL）或**不是这个构建的那一份**。带 `path`（看的是哪个文件）、`sha256`（读到的摘要，文件不在时为 `null`）、`runtime_sha256` / `runtime_version`（该有的那一个）、`found_version`（拿错的是本项目另一个发布包的运行库时会直接叫出名字）与 `remedy`。此时 `nvngx_dlssg.dll` 原样交回游戏，不会改用别的文件。 |
| loader：`preset_runtime_override`（Level 1） | `[DLSSG] Preset=C` 且 `[Runtime] Mode=Pinned` / `External` 选中的文件不是 310.9.16（只有 `[Backends]` 给它配了后端时才会走到这里）：预设 C 只有 310.9.16 有，所以改用随包的 310.9.16。带 `preset`、`mode`、`path`、`sha256`、`runtime_version`、`reason` 与 `action:"bundled_runtime_used"`。不另记 `configuration_warning`。 |
| backend：`preset_ineffective`（Level 1） | `Preset=B` 钉住了，但游戏的 Evaluate 没交 `DLSSG.HUDLess` 和 / 或 `DLSSG.UI`：`hudless`、`ui`、`missing[]`、`handle`、`evaluate`、`effect`（运行库照自己的行为，生成帧与不写 `Preset=B` 相同）。每个特性一条，交出的平面变了才再记；变成两张都有时记 `preset_effective`（Level 2）。 |
| loader：`preset_unavailable`（Level 1） | 只在 `-RuntimeModel 310.9` 的开发构建上：它的运行库 310.9.1 没有 FG Lite，`Preset=C` 无法生效，每进程一条，写明原因与实际用的预设（运行库自己的，后端另记 `preset_unsupported`，也是 Level 1）。发布包是 310.9.16，不会出现。 |
| loader：`backend_loaded` | 每进程一条，成败都写：`path`（`dlssg_sm86\backend\sm86_backend.dll`，相对代理自己的目录解析）、`sha256`（这份后端的实际摘要，**这是"答话的是哪一份后端"唯一的答案**）、`loaded`/`load_error`、后端自报的 `abi`/`id`/`runtime_sha256`，以及这个包期望的 `expected_runtime_sha256`/`expected_runtime_version`。 |
| backend：`kernel_pack` | 每进程一条（只在需要替换内核的安装里）：用的是哪个内核包、它与这个运行库是否配套。`path`、`manifest`（包的 id）、`model`/`schema`/`fusion_abi`、`images`/`image_bytes`、`cubins`（包里有没有 cubin）、`kernels`/`variants`/`patches`/`approx_rows`/`detail_rows`、`runtime_blobs`/`kernels_matched`/`kernels_unused`（已加载运行库里的内核按身份对上了几个，`docs/PACK_FORMAT.md`）、`scan_ms`、`selected_image` → `image`（包里没有 cubin 时 `cubin_sm86` 会解析成 `ptx_sm86`；**这不是回退**：不计 `image_fallbacks`，也不会有 `kernel_image_fallback`）。2026-10-04 起取代 `kernel_cubin_pack`。 |
| backend：`kernel_pack_missing` / `kernel_pack_rejected`（Level 1） | 每进程一条：`dlssg_sm86\kernels\fg_kernels.dll` 不在（`missing`），或者不能用（`rejected`；`reason` 是 `manifest_missing`/`manifest_parse`/`tool`/`schema`/`fusion_abi`/`model`/`structure`/`detail_constants`/`missing_resource`/`resource_size`/`target`/`runtime_coverage` 之一，`detail` 说明具体哪一项）。带 `path`、`open_error`、`manifest`、`target_sm`/`actual_sm`、`effect:"route_inactive"` 与 `remedy`。此时本次安装不启用路由（`install.active=false`），游戏照常运行，帧生成交给运行库自己——RTX 30 / 20 上即没有帧生成。最常见的原因：只复制了代理和后端、没复制 `dlssg_sm86\kernels\`，或者拷进来的是另一个发布包（另一个运行库模型）的内核包。 |
| loader：`sr_gate.kernel_set_source`；backend：`sr_kernel_set.source`（拒用时 Level 1） | 超分的内核集从哪里来（2026-10-11 起）：`pack` = 发布的内核包 `dlssg_sm86\sr\sr_kernels.dll`，`directory` = `KernelSet` 指向的目录包。后端的 `source` 还带 `path`、`outcome`（`accepted` / `missing` / `rejected`）与拒用时的 `reason` / `detail`（`unmappable`/`manifest_missing`/`manifest_parse`/`tool`/`schema`/`runtime`/`structure`/`missing_resource`/`resource_size`/`index`/`set` 之一，`docs/PACK_FORMAT.md` 第三部分）。包不在时设备闸就不放行（`sr_gate` 的那一行写明找的是 `sr_kernels.dll`），等同 `Mode=Off`；包坏了而索引还在时 snippet 照换、路线整包拒用，画面是 NVIDIA 自己的内核。最常见的原因：只复制了 `nvngx_dlss.dll`、没复制 `sr_kernels.dll`。 |
| loader：`game_runtime_generation` | 每进程一条，说明游戏自带的运行库属于哪一代契约、这次替换因此损失了什么：`generation`、`sl_dlss_g_version`（进程里那个 Streamline 插件的版本，**按 `StringFileInfo` 读**，所以 SL 1.x 显示 `1.5.6.0` 而不是固定块里的 `1.0.0.0`）、`effect`、`lost[]`，以及 **`sl_dlss_g_path` + `plugin_match`（`leaf`/`ota`/`ota_override`/`none`）——那份插件是游戏自带的，还是 Streamline ≥ 2.11 从 NGX 模型库加载的 NVIDIA OTA 副本**（倍率上限由它自己的常量决定，本机地平线 6 / Resonance 跑的都是 OTA 那份 2.14.0）。**代 A 是 Level 1（错误级）**，因为"只有 2X 且 INI 改不了"是用户必须知道的限制；代 B / unknown 是 Level 2。 |
| loader：`ngx_override_active`（Level 1） | 每进程一条，只在 `runtime_redirect.source=ngx_model_store` 时出现：**用户在 NVIDIA App 里打开了「DLSS 优设 - 帧生成」**（或收到过 NGX OTA），于是 NGX 核心从 `C:\ProgramData\NVIDIA\NGX\models\dlssg\versions\<n>\files\<arch>_<appId>.bin` 要 snippet。字段 `feature`、`requested`、`store_version`（模型库的版本目录，等于 snippet 自己的版本常量，`20318464` = 310.9.0）、`snippet_sha256`。**那份 snippet 我们照常接管**，但同一个开关通常还会把 Streamline 的帧生成插件换成 NVIDIA 的 OTA 版（`\ngx\models\sl_dlss_g_0\`），而倍率上限是那份插件自己的常量——本 mod 和 INI 都改不动（见 `plugin_match`）。 |
| backend：`install` | `actual_sm` 物理架构；`active` 本次是否启用路由；`image` 选定格式；`target_sm`/`router` 解析后的内核族；`optimized_tier`/`optimized_tier_name` 与 `optimized_knobs`（该档位真正落地的整组旋钮）；`kernel_pack` 是内核包的结果（`accepted`/`missing`/`rejected`，不需要替换内核时 `not_needed`）。 |
| backend：`image_approx` | 有损图像行的解析结果——`enabled`、`disabled_reason`、`optimized_tier`、`mask`/`mask_from`（INI 指定还是档位默认）、`armed[]`（每一行的入口名、槽位、资源号）、`rows_shadowed`、`exact_patches_replaced`。`catmull_rom_warp`、`detail_restore`、`image_patches` 三条记录同样带 `enabled`（只对会运行的行为真）与 `disabled_reason`（要求了却不会运行时的原因）。 |
| backend：`cu_function_unrouted`（Level 1） | CU 路径上某个函数的入口名不是内核包为它所在模块列出的名字：这个函数不路由（不建变体、不参与融合），它的发射原样转发。目前支持的运行库不会出现。 |
| backend：`optimized_create` | 每个替换进去的变体 / 图像行各一条：`row` 是 `variant`（重写变体）、`image_patch`（精确补丁）还是 `image_approx`（有损行），`approx` 给出 `A1`/`A5`/`A6` 这样的标签，另有 `entry`、`image`、`resource`、`status`。判断某一档到底武装了哪几行就看这条。 |
| loader：`backend_install` | `status=0` 表示后端安装成功；结合 `install.active` 判断是否启用了内核替换。`-102` = 这个运行库 SHA 没有对应后端；`-100` = 后端本身不可用，原因见下一行。`kernel_pack`（2026-10-04 起）是后端在这次安装里对内核包的结论，经 `DlssgMod_GetInfo` 报回 loader：`outcome`（`accepted`/`missing`/`rejected`/`not_needed`）、`found`（文件映射上了没有）、包清单自报的 `model`/`schema`/`manifest`（被拒的包也照填——另一个运行库模型的包会在这里写出它是哪个模型）、`reason`（拒用理由，同 `kernel_pack_rejected`）；后端太旧、不报这几项时为 `null`。 |
| loader：`backend_unusable`（Level 1） | `backend_install` 报 `-100` 时紧挨着的那条，说清是哪一种：`loaded=false` + `load_error`（**最常见的一种：`dlssg_sm86\backend\sm86_backend.dll` 没被复制过来，或者杀毒软件 / Windows「智能应用控制」拦了它**，游戏侧表现为 `Bad Image 0xc0e90002`；上一行的 `backend_loaded` 会告诉你它去哪儿找的）、缺 `DlssgMod_GetInfo`/`DlssgMod_Install`、ABI 不符（一个安装里混了两个发布包的代理和后端），或后端与被安装模块的运行库 SHA 不匹配。`remedy` 字段给出处理办法。 |
| `image=ptx_sm86` / `cubin_sm86` / `original` | 已选择的 SM86 内核格式，或未替换。 |
| backend：`kernel_image_fallback` | 驱动拒绝了某个 cubin，该镜像家族已自动改用 PTX。 |
| backend：`preset_pinned` | `[DLSSG] Preset` 生效。 |
| backend：`drs_dlssg` | 每进程一条（第一次 `PopulateParameters`）：**NVIDIA 驱动 per-game profile 里的七个 DLSS-G 键**，只读。`profile`/`profile_source`（`application` = 这个 EXE 自己的 profile，`current_global` = 全局那一份）/`profile_settings`，`keys{<id>:{name,consumer,value,location,predefined}}`，以及单独拎出来的 `plugin_limit`（`0x104D6667`，Streamline 插件读的"请求帧数"）与 `runtime_limit`（私有键 `0x104C9A99`，运行库每次 Evaluate 自己读）。**单位是生成帧数**（NVIDIA App 的 `4x` 写成 `3`）。没被写过的键是 `value:null` + `status:-160`（`NVAPI_SETTING_NOT_FOUND`），**不是 0**——一台没动过的机器七个键全是这样。这两个上限都是驱动侧的，**本 mod 和 INI 都抬不动**（效果那一半见 `mfg_drs_clamp`）。 |
| backend：`mfg_probe` / `mfg_summary` | `[Debug] MfgProbe` 与 `[FrameGeneration] ForceGeneratedFrames` 的记录，判定见 `docs/MFG_PROBE.md`。 |
| loader：`ngx_log_requested` / `ngx_log_unsupported`；backend：`ngx_log_install` / `ngx_log_init` | `[Debug] NgxLog=1` 才有。`trigger` = `nvngx_core_load`（正常，早于核心初始化）或 `backend`（晚了，只有自己加载核心的工具才走得到）。`ngx_log_init` 每次 Init 一条（上限 4）：`sdk_version` 与 `logging_honoured`（`false` = 游戏声明的 SDK 版本低于 `0x14`，核心不会用我们的回调，日志会是空的）、`caller_callback`（游戏自己是否也装了一个）。核心自己的行在 `ngx_log_<pid>.txt`。 |
| Level 3：`kernel_create` / `evaluate` | 每次内核创建实际用的格式与状态；实际生成数量、结果、`image_fallbacks`。 |

确认路由安装成功时同时检查 `install.active=true` 和对应的 `backend_install.status=0`。仅出现 `image=ptx_sm86` 不代表内核已创建或执行，还要看后续 `kernel_create` / `evaluate`。

### 游戏自带的运行库是哪一代：代 A 的游戏只有 2X

DLSS-G 在 `3.8.1 → 310.1` 之间换过一整套契约，而**游戏自带的 `nvngx_dlssg.dll` 是哪一代，决定了这一款最多能生成几帧**：

- **代 B（310.x）**：有 `DLSSG.MultiFrameCount` / `MultiFrameCountMax` 这一对参数，也就是多帧生成（MFG）。`MaxGeneratedFrames`
  在这些游戏上是真正起作用的（最大 5 = 6X）。
- **代 A（1.0.1 – 3.8.x，本机 Steam 库里 13 份自带运行库中有 5 份是这一代：巫师 3、光明记忆、蜘蛛侠重制、原子之心、三角洲）**：
  那一代**根本没有 `DLSSG.MultiFrameCount` 这个参数名**，所以游戏自带的 Streamline 插件不会写它，运行库就一直用默认值 1。

我们照常接管代 A 的游戏，而且**是能跑的**：巫师 3 DX12（自带 Streamline 1.5.6 + `nvngx_dlssg.dll` 3.1.13.0）换成内嵌 310.9.1
之后特性创建成功、三次会话跑了 6009 / 7352 / 28757 次 Evaluate、96/96 个平面与官方运行库逐位一致。**代价是这一款被钉在 2X，
并且不是 INI 能改的**——往 `MaxGeneratedFrames` 里写 3 或 5 只会让上限变高，插件仍然只请求 1 帧。同时少掉的还有：UI 重组
（`Preset=B`）、Reflex Warp、动态 MFG，以及"这一帧别插值"这个逐帧开关（代 A 用 `DLSSG.EnableInterp` 表达，310.x 不读它；
310.9 用自己的菜单检测内核顶上了这件事）。

日志里怎么看：`runtime_redirect.game_runtime.generation` = `A` / `B` / `unknown`，判据在 `generation_marker`；
每进程还有一条 `game_runtime_generation`（代 A 是错误级，出厂 `Level=1` 也能看到）。
`scripts\game\dlssg_diag.cmd` 与 `python scripts\analysis\sm75_report.py` 都会把这一条讲成一句中文结论。
**不要用 `[Runtime] Mode=Pinned` 去换回游戏自己那份代 A 运行库**：那一族只有 sm_89 的内核，还带光流（OFA）硬件依赖，
在 Ampere / Turing 上等于完全没有帧生成——Bundled 至少给 2X。

### 帧生成为什么打不开：`fg_gate_*`（始终开启，无 INI 键）

装上之后 `install` 一切正常、却一条 `kernel_create` / `evaluate` 都没有，说明游戏根本没有创建 DLSS-G 特性，或者创建在运行库建第一个内核之前就失败了 —— 这两件事我们原来的日志分不出来，更说不出原因。决定权全在运行库之上：Streamline 自己的闸门（**硬件加速 GPU 计划（HAGS）关闭** → `eFeatureNotSupportedHWSchedulingDisabled`、驱动低于插件要求）、NGX 核心对 `GetFeatureRequirements` 的最终答复（核心会在运行库的答复之上再加自己的显卡 / 驱动 / HAGS 判断）、插件读的 NGX 能力参数，以及游戏自己的 UI 开关。`src/backend/ngx/fg_gate.cpp` 只观察这四处，五条记录都是 Level 2 可见（只有失败的 CreateFeature 是错误级，Level 1 也会记）：

| 事件（backend） | 内容 / 怎么读 |
|---|---|
| `fg_gate_environment` / `mfg_modules` 里的模块版本 | 每个模块的 `file_version` 取的是**该信的那一个**：版本资源固定块与 `StringFileInfo` 不一致时（Streamline 1.x 的固定块一律停在 `1.0.0.0`，真版本只在字符串里），记的是字符串里那个，并额外带 `file_version_fixed`/`file_version_string` 两个字段说明分歧。两者一致时只有 `file_version`，与旧版本日志完全相同。 |
| `fg_gate_environment` | 安装时一条。`hags`（`D3DKMTQueryAdapterInfo` 的 `KMTQAITYPE_WDDM_2_7_CAPS`：`supported`/`enabled`/`enabled_by_default`，`state=on\|off\|unsupported`）、`driver`（`NvAPI_SYS_GetDriverAndBranchVersion`，如 `610.74` / `r610_00`，外加已加载 `nvapi64.dll` 的文件版本）、`windows`（`RtlGetVersion`）、`ngx_core`（`_nvngx.dll` 路径+版本）、`streamline`（已加载的 `sl.interposer.dll` / `sl.common.dll` / `sl.dlss_g.dll` / `sl.dlss.dll`，只用 `GetModuleHandle` 看，绝不加载）。**`hags.state=off` 基本就是答案**。每一项都可选，取不到就写 `available=false` + 原因，永远不会让安装失败。 |
| `fg_gate_hags_disabled`（Level 1） | 上一条里唯一**既是用户可改的 Windows 设置、又能单独让帧生成在所有游戏里都打不开**的那一项：HAGS 本机支持但被关掉了。因为出厂 `Level=1` 根本不写 `fg_gate_environment`，这条单独按错误级记录，任何日志等级都能看到；`remedy` 字段写着怎么开。（公开 issue #513：有人为此排查了三个小时。） |
| `fg_gate_hooks` / `fg_gate_hooks_deferred` | 钩住的是 **NGX 核心 `_nvngx.dll` 的公开导出**（`GetFeatureRequirements` / `GetCapabilityParameters` / `GetParameters` / `CreateFeature`），四个导出各自报 `attached`。核心还没加载时先监视 `LoadLibrary`（`fg_gate_hooks_deferred`），等它出现再装；记录里还带一次 `ngx_core` 版本。 |
| `fg_gate_requirements` | 每次核心的 `GetFeatureRequirements`（最多 8 条）。`feature_supported` 是**调用方真正拿到的**那个值，`decoded` 按位解开（0 支持 / 1 显卡不支持 / 2 驱动版本不支持 / 4 系统版本不支持 / 8 硬件计划关闭），另有 `min_hw_architecture`、`min_os_version`、`caller`（调用模块+模块内偏移）与 `adapter_description`。注意与 backend 自己的 `feature_requirements` 区分：那条只是运行库对我们桥接的答复，核心还会在上面再加自己的判断。**`status_decoded` / `status_reason`** 说明这个状态是运行库自己那个函数里的哪一条路：310.x 的 `GetFeatureRequirements` 一共只能返回三个值——`1`（`success`）、`0xbad00002`（`nvapi_enum_physical_gpus_failed`，它五项检查里**唯一**会让整个调用失败的那一项）、`0xbad00005`（`input_is_nullptr`）。**`success` 不等于"支持"**：系统版本过低、`NvAPI_GPU_GetArchInfo` 失败、`getDeviceID` 失败这几条路都是**返回成功、把结论写进 flags 里**，所以要看的是 `decoded` 而不是状态。别的值（例如 `0xbad0000b`）说明答这个调用的不是 310.x 的运行库。 |
| `fg_gate_capability` | 每次能力查询后（最多 4 条）读回 `FrameGeneration.Available` / `.NeedsUpdatedDriver` / `.MinDriverVersionMajor` / `.MinDriverVersionMinor` / `.FeatureInitResult`、`DLSSG.MultiFrameCountMax`、`DLSSG.ReflexWarp.Available`，以及作为对照的 `SuperSampling.Available`。`Available=0` 或 `NeedsUpdatedDriver=1` = 插件在我们这边任何东西跑起来之前就拒了。`.FeatureInitResult` 是核心为这个特性记下的 NGX 状态：`3134193675` = `0xBAD0000B`（`NVSDK_NGX_Result_FAIL_OutOfDate`），含义与下一行的 `CreateFeature` 失败完全相同，只是核心早在能力查询阶段就记下了，插件看到 `Available=0` 就再也不会调 `CreateFeature`（RTX 2080 Ti / 巫师 3 实测）。 |
| `fg_gate_create_feature` | 每次核心的 `CreateFeature`（最多 16 条）：`feature_id`（DLSS-G = 11）、`status`、`succeeded`、`handle`、`caller`，DLSS-G 还带 `parameters`（`multi_frame_count` / `multi_frame_count_max` / `width` / `height`）。**失败是错误级**，`0xbad0000b`（`NVSDK_NGX_Result_FAIL_OutOfDate`）= 核心拿它在自己初始化时从 NVAPI 读到的显卡架构，去比 DLSS-G 运行库（snippet）导出的 `NVSDK_NGX_GetGPUArchitecture`（= 运行库声明的最低架构）后拒绝。后端把那个导出报成**物理架构**（`turing_host.gpu_architecture_export`，Turing 上 `0x160`；之前报的是 Ada `0x190`，那正是真 Turing 上帧生成打不开的原因）。`SpoofArchToGame` 管的是另一道闸门（游戏 / Streamline 自己的），对这一条没有帮助：重定向现在在游戏启动时就装好了（`trigger=dllmain`/`nvapi_load`/`dependency_load`），但核心这次比的不是 NVAPI 的答复，而是 snippet 导出的那个最低架构。 |
| `fg_gate_summary` | 一条，第一次 Evaluate 时（`reason=first_evaluate`）或进程退出时（`process_exit`）：requirements / capability / create 的次数与最后一次创建的状态。`create_calls=0` 而 `install` 一切正常 = 游戏从来没要过这个特性。 |
| `fg_gate_exit` | 一条，只在 `DllMain(DLL_PROCESS_DETACH)` 写：`evaluates`（总共跑了多少次 Evaluate）、`features`（创建了几次帧生成特性）、`last_evaluate_age_ms`（最后一次 Evaluate 距进程退出多久）、`clean:true`。**被杀掉或崩溃的进程走不到这里，所以日志末尾没有这条就等于"不是正常退出"**——上一条 summary 是第一次 Evaluate 就写掉的，单看它分不出"玩完退了"和"玩着玩着挂了"。老版本构建一条 `fg_gate` 记录都没有，不要误读成崩溃。 |
| `kernel_handle_recycled` | 每进程最多一条：驱动把某个内核句柄从 `old_rva` 换给了 `new_rva`（`had_variants` = 它当时还绑着上一个内核的变体集）。这是驱动的正常行为，每次创建都会重建该句柄的含义，所以它本身**不是问题**；累计数在 `evaluate.optimized.handles_recycled` / `stale_bindings_cleared` 与 `feature_create` 里。 |
| `stale_variant_rejected`（Level 1） | **本来应该永远不出现**：发射前的最后一道护栏拦下了一个属于别的内核的变体行，说明还有某条创建路径没有重置句柄。见到它请把日志发给开发者。 |

`python scripts\analysis\sm75_report.py <日志目录>` 的 `== fg gate ==` 一节把上面几条拼成一页，VERDICT 里多一行 `feature created`：创建成功 PASS、失败 FAIL（带状态）、从未调用 NOT RUN 并按证据给出最可能的闸门。

## 高级配置示例

以下示例仅在诊断 / 验证时用，正常安装不需要。把对应节和键补进出厂 INI 即可（`[Compatibility]` / `[Debug]` 节不存在就自己加）。

**3080 Ti 用 PTX JIT（等价于自动识别，一般不必写）：**

```ini
[Compatibility]
KernelImage=PTX
```

**RTX 40 / 50 回到运行库自己的帧生成内核（关掉 0.4.0 起的默认）：**

```ini
[Compatibility]
AccelerateNewerGpus=0
```

**RTX 5070 验证 SM86 PTX 路径（开发用的验证配置，与上一条无关）：**

```ini
[Compatibility]
KernelImage=PTX
ForceSM86Route=1
SimulateAmpere=1

[Logging]
Level=3
```

**取本机原厂数值参考（stock）：** 直接用出厂 INI 把 `Optimized` 改成 `0` 即可（Ampere 上不要用 `KernelImage=Original`）。

**开启生成帧标记（区分毛刺在生成帧还是真实帧）：**

```ini
[Debug]
MarkGeneratedFrames=1
```

**允许 6×：**

```ini
[FrameGeneration]
MaxGeneratedFrames=5
```

## 安装注意与卸载

游戏目录里只放一个代理：根目录的 `version.dll`（首选）；游戏不加载它时按 `alternatives/winmm.dll` → `alternatives/dbghelp.dll` → `alternatives/dinput8.dll` 的顺序换，**一次只放一个，换之前先删掉上一个**（判断方法见上面“代理只放一个”）。它们都从同一个 `dlssg_sm86\backend\` 加载同一个后端，只有文件名和转发目标不同。**`dlssg_sm86\` 这个文件夹必须跟着一起复制**——代理本身只是加载器。

渲染路径代理 `alternatives/dxgi.dll`、`alternatives/d3d12.dll`（可用，但风险更高）：它们在 D3D12 热路径上、加载顺序敏感，只在上面四个都没被游戏加载时才用，最后手段，两者只放一个。挑选说明随包放在 `alternatives/README.md`。

每个代理都把自己的全部导出转发给 `System32` 里的同名真实 DLL，只拦截 `nvngx_dlssg.dll` 的加载。

发布 DLL 的代码签名是可选的：`build.ps1 -SignCert <pfx> -SignPass <pw>`（或 `DLSSG_SIGN_CERT`/`DLSSG_SIGN_PASS`）会对本项目自己的每一个 DLL（根目录的 `version.dll`、`alternatives\` 的五个代理、`dlssg_sm86\` 下的后端与内核包）做 SHA-256 Authenticode 签名，NVIDIA 的运行库与 snippet 不碰；不提供证书则产物未签名。步骤、如何造一次性测试证书、以及自签名不提供默认信任等见 `docs/SIGNING.md`。

目前针对 Windows x64 / D3D12。本包的构建检查和可选 GPU 验证状态见 `manifest.json` / `validation.json`，架构见 `docs/ARCHITECTURE.md`，抓取与重放见 `docs/CAPTURE.md`，完整记录见 `docs/VALIDATION.md`。

卸载时退出游戏，移走放进去的那一个代理（`version.dll`，或换用的那个备用代理）、`dlssg_sm86.ini` 和 `dlssg_sm86\` 文件夹（日志也在里面）。原 NVIDIA DLL 及内核资源的归属见 `THIRD_PARTY_NOTICES.txt`；SM75 GPU 资源来自 Coldwood1026 的 RTX 20 系移植工作，在此致谢。
