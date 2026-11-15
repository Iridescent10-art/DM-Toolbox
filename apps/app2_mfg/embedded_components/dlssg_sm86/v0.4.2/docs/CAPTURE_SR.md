# DLSS 超分输入抓取（`[Debug] CaptureSR`）

在**真实游戏里**把 DLSS **超分**（Super Resolution，NGX feature id 1）的输入像素和参数录下来：颜色、深度、
运动矢量、曝光、可选的各种 mask，以及每次创建特性的全部参数。目的只有一个——离线标定把
SR 网络量化成静态 INT8（`docs/SR.md`），而**每个 producer 位点的 scale 就是它的饱和点**，
所以只用合成棋盘做的标定换到真实游戏上不能信。代价已经量出来了：同一段录制上，**棋盘标定的 INT8 只有 21–26 dB，
用这段录制重新标定后是 37–40 dB**。这套抓取就是把真实内容喂进去的入口。

抓取与 DLSS-G 的那套（`docs/CAPTURE.md`，`[Debug] Capture`）**完全独立**：它钩的是 NGX 核心而不是 DLSS-G 运行库。
**`[Debug] CaptureSR=0`（出厂默认）时整套机制完全不存在**：不装钩子、不建线程，代理连后端都不会为它加载。

v2（2026-09-18）把它从“录一次”变成“采集”。三条要求决定了现在的形状：

1. **入口就是普通的 DLSS 用法**——任何 DLSS 版本、任何 RTX 显卡、帧生成开不开都行，连我们这个 mod 都可以整体关掉。
2. **只存不能再生成的东西**——默认不录游戏自己的输出（重放能重新生成它），整局里内容相同的平面只存一份。
3. **采样，不是流式录制**——一段 = 按一次键；步长把一段摊到真实游玩上；整局用字节数收口。

---

## 1. 两种部署

### 1.1 采集部署（`[General] Enabled=0`）

这是采集真实游戏内容时该用的那一种：**帧生成那套完全不启用**，代理在进程里只做一件事——观察 NGX 核心的
`CreateFeature` / `EvaluateFeature`，只对 feature 1 动作。

```ini
[General]
Enabled=0
[Logging]
Level=2
Directory=dlssg_sm86\logs
[Debug]
CaptureSR=40
CaptureSRStride=30
CaptureSRBursts=0
CaptureSRMaxGB=8
CaptureSRDirectory=<工作目录>\srcap\<游戏名>
```

`[General] Enabled=0` **不再关掉 `CaptureSR`**。那个键关的是帧生成（替换 NVIDIA 内核的部分），而这套抓取不属于它，
并且抓取本身出厂就是关的（`CaptureSR=0`），所以没有写过这个键的人什么都不会变。这一档里**不做**的事情，
loader 会用一条 `capture_sr_only` 原样列出来：

| 不做 | 证据 |
|---|---|
| 随包的 DLSS-G 运行库文件连打开都不打开 | `backend_loaded{path:"...\\dlssg_sm86\\backend\\sm86_backend.dll",loaded:true,sha256:...}`，而 `dlssg_sm86\runtime\nvngx_dlssg.dll` 一个字节都没被读过（`capture_sr_disabled_mod` 用哨兵字节证明） |
| `nvngx_dlssg.dll` 原样交给系统 | 没有 `runtime_redirect`、没有 `backend_install` |
| 不调 `DlssgMod_Install` | 不检测 GPU、不替换内核、不做融合、不做图像补丁 |
| 不改 NVAPI 架构上报 | 没有 `arch_spoof_installed` / `_applied` / `_inert`（`Enabled=0` 时连解析前那次 kernel32 预读都判定为“永不装”） |
| 不做 `turing_host` | 没有 `turing_host` / `turing_host_defaults` |

做的只有两件：挂上 NGX 核心那两个导出（只对 feature 1 有反应），以及挂上参数存储的 getter（让录下的帧自述）。
CTest `capture_sr_disabled_mod` 把这一整套钉住：它自己搭一个目录（代理 + 一个用两个 NGX snippet 名字命名的假 DLL +
一份带自己缓存目录的 INI），fork 一个子进程去加载它们，再把日志读回来核对上表——不需要 GPU、不需要 NGX 核心、
不需要真运行库。

### 1.2 连帧生成一起（`[General] Enabled=1`）

一样能录。两套抓取共用回读缓冲、写盘线程与两个预算，`[Debug] Capture` 和 `[Debug] CaptureSR` 同时非零代码上允许
但没有实测过，一键工具直接拒绝这种组合。

### 1.3 对 DLSS 版本与显卡的要求：没有

钩的是 **NGX 核心（`_nvngx.dll`）的公开导出**，不是某个版本的 snippet，所以：

- 游戏自带的 DLSS 是 2.x / 3.x / 310.x 都一样；游戏直接调 NGX、经 UE 插件、还是经 Streamline `sl.dlss` 都一样。
- 参数名表（`kSrNames`）与创建标志（`NVSDK_NGX_DLSS_Feature_Flags`）都是 DLSS 2.0 以来没动过的 SDK 常量；
  `PerfQualityValue` 的枚举同样没动过（`0` MaxPerf、`1` Balanced、`2` MaxQuality、`3` UltraPerformance、
  `4` UltraQuality（从未真正出货）、`5` DLAA）。**DLAA 就是 `PerfQualityValue=5`，渲染分辨率等于输出分辨率**，
  录下来的 `creation.dlaa` 会为 `true`。
- 每次创建特性都单独记下**这个特性**用的 snippet（`creates[].dlss` 的路径 / 文件版本 / SHA-256）和解码后的预设
  （`render_preset_tier` = 这个 quality 档对应的那个 `DLSS.Hint.Render.Preset.*`，`render_preset` = 它的值，
  `render_preset_name` = 字母，12 = `L`、13 = `M`、11 = `K`）。一个进程里可以有多个 snippet 版本和多个特性，
  所以这些是**逐特性**记的，不是整局一份。
- “版本无关”不是声明而是每帧实测的：每帧都有运行库**真正读过**的有序日志，其中**表里没有的名字**会被汇总成
  `unknown_read_names`（只算读成功的；310.7.129 每次 Evaluate 开头有一次注定失败的垃圾名读取，会被滤掉）。
  空 = 这个 DLSS 版本没有要任何我们没扫的东西。非空不是失败——值还在有序日志里——而是一条待办：把名字加进
  `src/backend/diag/capture.cpp` 的 `kSrNames`，类型化探针才会扫它。
- 显卡只要能跑 DLSS 就行（抓取不需要 SM86，也不需要帧生成）。第 6 节的全部实测是在 RTX 5070（Blackwell）上做的。

---

## 2. 采样：段、步长、预算

一次 Evaluate = 一个游戏帧（超分不像 DLSS-G 的 3×/6× 每帧调多次）。

- **段（burst）= 按一次起录键**。段里录 `CaptureSR` 帧，然后这一段关闭；`CaptureSRBursts` 决定一局最多几段
  （`0` = 不限，按到写满 `CaptureSRMaxGB` 或游戏退出为止）。每段一个 `burst_NNNN\` 子目录，都在同一份
  `manifest.json` 的 `bursts[]` 里。**下一段必须重新按一次键**（按键要先松开），否则按住半秒就会把所有段一次开完。
- **步长（`CaptureSRStride`）在段内生效**：每 N 次 Evaluate 录 1 帧。这是把一段变得“多样”而不是“更长”的旋钮——
  60 fps 下 `CaptureSR=40` + `CaptureSRStride=30` 是 40 帧摊在约 20 秒的游玩上，而不是 0.7 秒里几乎一样的 40 帧。
- **`CaptureSRMaxGB` 是唯一对”不限段数”也成立的界**。检查的是”已落盘 + 在飞 + 再来一帧”，所以上限永远不会被越过，
  而不是越过之后才发现。到了就整局停下（`capture_sr_done{stage:”budget”}`），已录的照常可用，游戏继续正常跑。
  `CaptureSRBursts=0` 而 `CaptureSRMaxGB=0` 就是”完全没有界”，所以后端会**替你放一个 8 GiB 的默认上限**并记一条
  `capture_sr_options`（拒绝请求反而会让一份手写 INI 悄悄什么都不录）。上限只算像素字节：`params.json` 和每个平面的
  `.json` 不在预算里，几千帧的会话上那是几十 MB 的量。

### 起点与“能不能复现游戏自己的输出”

DLSS 超分把全部时域状态留在特性内部（warped colour history、luma history、hidden states、上一帧运动矢量），
这些**不在抓取里**，所以只有“刚 `CreateFeature` 完的第一帧”的历史是空的，也只有从那里起录，离线重放才可能复现
游戏自己的输出。

| `CaptureSRStartKey` | `CaptureSRStartOnCreate` | 步长 / 段数 | 起点 | 能复现游戏自己的输出 |
|---|---|---|---|---|
| `Insert`（默认） | `0`（默认） | 任意 | 按下 Insert 的那一帧（每段一次） | 否 |
| `Insert` | `1` | 必须 1 / 1 | 按键之后的第一个“新建特性的第一帧”（先按键、再去设置里把 DLSS 关掉再打开） | 是 |
| `0` | `1` | 必须 1 / 1 | 游戏第一次创建超分特性之后的第一帧（通常在主菜单/读盘画面） | 是 |
| `0` | `0` | 任意 | 立刻（`CaptureSRSkip` 2026-10-22 删除，不跳帧） | 否 |

`CaptureSRStartOnCreate=1` 配步长 >1 或段数 ≠1 时**后端会把它关掉**并记一条 `capture_sr_options`：那个起点的含义是
“某个特性生命里的前 N 次 Evaluate”，带步长或第二段以后本来就不是，静默录一份声称可复现的抓取是三种结果里最差的。

**做标定不需要“能复现游戏自己的输出”**：标定要的是真实激活值的最大值，两条重放（原厂 FP8 与静态 INT8）
都从同一个空历史开始，PSNR 比较照样成立。要和游戏自己的输出对账才需要那一档。

**要按预设分开录、而录下来的 `output` 必须是官方参考时**，`[SuperResolution]` 只有一份配置能用：
`Mode=<X>-FP16`（换成随包的 snippet、六档全钉到 X——2026-10-19 起每个 Mode 都钉全部六档，`Tier` 已删除，X 仍跑运行库自己的 FP16/FP8 内核，
`sr_evaluate.route.replaced` 恒为 0）。`Mode=Off` **不行**——它连运行库都不换，录下的是游戏自带运行库和它自己的预设。
2026-10-03 之前这一档写作 `Int8=1 ForcePreset=<X> Int8<X>=0`；那些键已移除，写了只记警告、整节等于 Off。
两行 INI、为什么、以及日志里怎么验，见 `docs/SR.md` 第 4 节“录官方参考 / A-B 对照的配置”。

### 标定该录多少、录什么

给一个游戏做标定集时（这些是经验建议，不是实测结论）：

| | 建议 | 为什么 |
|---|---|---|
| 每个游戏 | **200–600 帧**，分 5–15 段 | 逐位点的饱和值靠“见过多少不同内容”涨，不靠帧数；一段里第 2 帧和第 1 帧几乎相同 |
| 每段 | 20–50 帧，步长 20–60 | 一段覆盖 10–30 秒真实游玩；再长就开始重复同一片场景 |
| 场景 | 室内 / 室外、白天 / 夜晚、战斗 / 赶路、雨雪雾、UI 多的画面 | 颜色输入的动态范围与运动矢量的量级在这几类之间差最多 |
| 画质档 | **同一个 quality 档一份**（`PerfQualityValue` 决定渲染分辨率，也决定用哪个预设） | 换档就是换网络输入分辨率，混在一个包里会两边都描述不对；转换器会直接拒绝 |
| 分辨率 | 至少覆盖玩家常用的那一档输出分辨率 | 网络本身跑在固定的内部分辨率上，但输入级与输出级随分辨率缩放 |
| 不要 | 菜单、纯黑读盘画面、暂停界面 | 这些画面的激活值分布和游玩时无关，只会占预算 |

`CaptureSRMaxGB=8` 配上默认的 lean + dedup，在 1080p 渲染下约够 1300 帧、4K 渲染下约 240 帧。

### 磁盘与内存

默认（lean = 只录输入）下一帧 = 颜色 + 深度 + 运动矢量 + 曝光。本机实测（1920×1080 渲染 → 3840×2160 输出，
SDR：`prewarm` 记的 `estimate_frame_bytes`）是 **31.6 MiB / 帧**；HDR 颜色（`R16G16B16A16_FLOAT` 8 B/像素或
`R11G11B10_FLOAT` 4 B/像素）会把颜色那一份改掉，`R16G16` 的运动矢量与 `R32_FLOAT` 的深度更小。
`CaptureSRLean=0` 再加上按**输出**分辨率算的 FP16 输出（4K = 63 MiB），一帧就是约 95 MiB。

在飞的内存 = `min(每段帧数, 16)` 个槽位 × 每帧字节（4K lean 约 0.5 GB），再被回读内存预算
（配置时可用物理内存的一半）夹住；显存是暂存纹理，被 1536 MiB 夹住（`CaptureSRMemoryMB` / `CaptureSRVramMB` / `CaptureSRRingSlots` / `CaptureSRAsyncCopy` 2026-10-22 删除，这些值写死，`docs/COMPAT.md` C102），
超预算的平面退回内联回读（`capture_plane_inline`）。带步长时两帧之间隔着整帧时间，写盘线程有充足余量——
4K + 步长 4 的实测里 0 丢弃 0 跳过。

---

## 3. 抓取目录的内容

```
<CaptureSRDirectory>\
  manifest.json          schema 2：EXE、feature id、nvngx_dlss.dll 与 NGX 核心的路径/版本/SHA-256、显卡、驱动、
                         完整 INI 文本、假定的资源状态、creates[]、bursts[]、frames[]、总计、stop_reason、complete
  create_1.json          每次 CreateFeature：创建参数的完整 probe（前/后）+ 运行库读参数的有序日志 + 解码后的
                         创建标志 + 这个特性的 snippet 版本/哈希 + 解码后的 quality 档与预设
  burst_0001\
    frame_0001\
      params.json        这一帧的全部参数（probe）+ 运行库真正读过的有序日志（reads）+ planes[]
      color.bin          颜色输入，行紧密排列，无 D3D12 行对齐填充
      color.json         这个平面的 desc / footprint 格式 / 字节数 / SHA-256 / 逐 subresource 布局
      depth.bin  depth.json
      mv.bin     mv.json
      exposure.bin exposure.json
      output.bin output.json      游戏自己的输出（只有 `CaptureSRLean=0` 时才有）
    frame_0002\ ...
  burst_0002\ ...
```

平面文件名是固定的短名（`color` / `depth` / `mv` / `exposure` / `output`，另有 `transparency`、
`bias_color_mask`、`particle_mask` 等），不是 NGX 参数名——`src/backend/diag/capture.cpp` 的 `planeFile()` 是这张映射表的权威。
其它没有短名的资源按参数名清洗后当文件名，不会丢。

`manifest.json` 的 `frames[].directory` 一直是**从抓取根到那一帧目录的相对路径**（现在是 `burst_0001/frame_0001`，
两级而不是一级），所以只走 `frames[]` 的 schema-1 读法照样能用。

### 3.1 引用：内容相同的平面只存一份

`CaptureSRDedup=1`（默认）时，整局里 SHA-256 相同的平面只写一份文件，后面的 json 不带字节而是指过去——和帧生成
抓取的 lean 引用同一套约定（`stored=false` + `source`）：

```json
{ "name": "Color", "file": "color.bin", "stored": false, "dedup": true, "lean": "dedup",
  "source": "burst_0001/frame_0001/color.bin", "bytes": 0, "source_bytes": 2073600,
  "sha256": "649b3a77…", "desc": {…}, "footprint_format": 28, "subresources": [ … ] }
```

引用是**完整描述 + 一个指针**，不是裸指针：一个被去重的平面每帧都会出现，转换器或索引不该为了知道眼前这帧是什么
格式而去追一个文件。`bytes` 记 0（这一帧在磁盘上的代价），`source_bytes` 是逻辑大小。1×1 曝光纹理、没变的 mask、
静态平面因此每局只存一次。合成场景上实测：8 帧的会话里 14 个平面被引用，省下 13.8 MiB / 49.4 MiB。
真实游戏里颜色每帧都不同，省下的主要是曝光与 mask。

### 3.2 压缩：落盘之后的一步

**后端不压缩**。`third_party/` 里没有 zlib，而 Windows 自带的压缩 API（MSZIP / XPRESS / XPRESS_HUFF / LZMS）
产出的流 Python 标准库解不开——而“离线一侧只用标准库就能读”是这套格式的前提。所以压缩是会话结束后、由开发者
离线做的一步。

判据是**解压回来的 SHA-256 等于录制方写下的那个**，原文件只在这一步通过之后才删。平面 json 与所属帧的
`params.json` 都会加上一个 `compression` 块（方法、文件名、压缩前后字节、比率），`manifest.json` 加一个
`compaction` 块；离线转换读到它会在装包的路上解压，所以**输入包永远是原始字节**（探针上传的就是它）。

选了 zlib（deflate，`zlib.decompress` 即可解）而不是 lzma：本机 RTX 5070 / 32 线程实测——

| 平面（合成场景，96 MB） | 格式 | zlib-6 | lzma-1 |
|---|---|---|---|
| `Output`（DLSS 的 FP16 输出） | `R16G16B16A16_FLOAT` | 0.799 | 0.667 |
| `Color`（**随机噪声**，最坏情况） | `R8G8B8A8_UNORM` | 1.000 | 1.000 |
| `Depth` / `MotionVectors`（合成的常量场，最好情况） | `R32_FLOAT` / `R32G32_FLOAT` | 0.002 | 0.001 |
| 整体吞吐 | | **184 MB/s**（zlib-1 253 MB/s） | 51 MB/s |

读法：探针的合成平面正好落在两个极端上，**真实游戏的数字还没有**（第 7 节）。能说的是：颜色如果是噪声就压不动，
FP16 图像数据在 0.67–0.80 之间，而 lzma 换来的那点比率要付 3.6 倍的时间——一份 8 GB 的会话 zlib 要 45 秒、
lzma 要 160 秒。默认 zlib-6，lzma 也能选（两种 Python 标准库都能解）。

### 3.3 `params.json` 的两半

和 DLSS-G 抓取同义：

- **`probe`**：150 多个已知 SR 参数名 × 8 个有类型的 getter 槽位的全部答复。这才是**游戏侧的状态**，
  和运行库这一帧读了什么无关。每条带 `slot` / `setter_slot` / `type`，因为存储只通过“写进去的那个类型槽位”
  回答，重放必须用对称的 setter。
- **`reads`**：运行库这一帧**真正读过**的有序日志（含类型槽位、状态、值）。这是用来发现“我们的名字表里没有的名字”
  的（`unknown_read_names`，见第 1.3 节）。310.7.129 每帧读 **120 个不同的名字**，CreateFeature 时另读 30 个——
  正是这份实测纠正了三处光看头文件会写错的地方：运动矢量 / 半透明 / bias mask 的 subrect base 运行库读的是
  `.Subrect.Base.X` 而不是 SDK 头文件里的 `.SubrectBase.X`（两种拼法现在都在表里）、`TonemapperType` 没有 `DLSS.`
  前缀、以及一整套光线重建的输入（`GBuffer.*` / `DLSSD.*` / 四个矩阵）在普通超分特性上也会被读。

`creates[].creation.create_flags` 把 `DLSS.Feature.Create.Flags` 解码成
`IsHDR / MVLowRes / MVJittered / DepthInverted / DoSharpening / AutoExposure / AlphaUpscaling`。**这一位组合决定
`nvngx_dlss.dll` 实例化哪一族内核**（输入级内核的名字里就写着 `mvlo`/`mvhi` 与 `ldr`/`hdr`），而随包的
静态 INT8 只覆盖其中 **`mvlo` + `hdr`** 与 **`mvhi` + `hdr`** 两族（两个 `ldr` 族按设计不出资产，见 `docs/SR.md`），
所以这是判断一份抓取能不能直接拿去做 INT8 标定/验证的第一个条件。

---

## 4. 从会话到输入包

抓取之后的转换由开发者离线做，录制方要发过去的是第 5 节一键工具打的两个 zip：报告 `dlssg_diag_<时间>.zip` 与抓取
`dlssg_sr_capture_<时间>.zip`（抓取超过 8 GB 时工具不打包，请直接压缩抓取目录或传网盘）。

离线转换把会话转成重放用的输入包：像素**逐字节照搬**（行本来就紧密排列），不做任何缩放、色调映射或通道重排；
去重引用与压缩在转换时解开，所以输入包永远是原始字节。**一个包只描述一个特性**：一局会话里可以有好几个
（玩家改画质档时游戏会重建 DLSS），而一个混了两种渲染分辨率的包两边都描述不对，所以这样的会话要按段或按帧拆开转。
带步长的包记着每一帧来自哪一段，不会被当成一个连续序列读。

---

## 5. 给测试者的一键工具

```
dlssg_sr_collect.cmd                             复制到游戏 EXE 目录，双击：按 Insert 采一段（40 帧 / 每 30 帧取 1），
                                                 想按几次按几次，写满 8 GB 或退出游戏为止
dlssg_sr_capture.cmd                             老的单段模式：按 Insert 连录 12 帧
dlssg_diag.ps1 -CaptureSR 40 -SRStride 30 -SRBursts 0 -SRMaxGB 8     采集模式的完整写法
dlssg_diag.ps1 -CaptureSR 12 -CaptureKey End     换一个按键
dlssg_diag.ps1 -CaptureSR 12 -SRNewFeature       改成"在设置里切一次 DLSS"起录（能复现游戏自己的输出）
dlssg_diag.ps1 -CaptureSR 12 -SROutput           连游戏自己的输出一起录
dlssg_diag.ps1 -Analyze -CaptureSRDir <目录>     只验收一份已有的抓取
```

流程和 `-Capture` 那套一样（`scripts/game/README_MONITOR.md`）：临时往 `[Debug]` 写
`CaptureSR` / `CaptureSRStride` / `CaptureSRBursts` / `CaptureSRMaxGB` / `CaptureSRDedup` / `CaptureSRStartKey` /
`CaptureSRStartOnCreate` / `CaptureSRLean` / `CaptureSRNoStall` / `CaptureSRDirectory=dlssg_sm86\capture_sr_diag_<时间>`
（每次一个新目录），边跑边把 `capture_sr_requested` / `_only` / `_hooks` / `_options` / `_feature` /
`_waiting_for_key` / `_start` / `_burst` / `_frame` / `_skipped` / `_done` 讲成中文里程碑（包括“第 N 段录完，
走到另一个场景再按一次”和“已写满上限”），游戏退出后按 manifest 验收、写 `== DLSS 超分抓取 ==` 一节（含逐段表、
去重省下多少、以及“这个 DLSS 版本读了工具不认识的参数名”那一行）、把抓取**单独**打包成
`dlssg_sr_capture_<时间>.zip`（>8 GB 直接不打包），结束后把 INI 逐字节还原。
`-Capture` 和 `-CaptureSR` 不能同时用（两种抓取共用回读缓冲和同一份报告）。

`-CaptureSR` 的会话里帧生成本身不会被诊断（游戏可能根本没请求 DLSS-G 运行库），报告的结论会明说这一点；
`[General] Enabled=0` 时还会多一行说明帧生成完全没有启用。

---

## 6. 实现

代码在 `src/backend/diag/capture_sr.h`（接口）+ `src/backend/diag/capture.cpp`（实现）+ `src/proxy/loader.cpp`（INI 与安装），
在**后端** `sm86_backend.dll` 里。三条理由，按权重排：

1. **NGX 参数存储的 getter 实现和 `ID3D12CommandQueue::ExecuteCommandLists` 各自只能有一个 Detours 跳板**——
   两者都是进程里同类对象共用的，而 `src/backend/diag/capture.cpp` 已经拥有这两处 patch（DLSS-G 抓取、`[Debug] QueueTrace`（2026-10-21 删除）、
   MFG 探针都靠它们）。第二个翻译单元去 patch 同一个目标就是同一个目标上的第二个跳板。
2. **回读机制不值得复制一份**：资源 → 暂存纹理 → COPY 队列 → 回读缓冲（以及中间每个队列交接点都必须是 `COMMON`
   的状态舞蹈）、多平面深度的 footprint 遍历、池化、显存/系统内存预算、平面写盘，全是那个文件里实测过的代码。
3. **必须在后端而不是代理里**：代理跑在 loader lock 下、64 KiB 栈的线程上，刻意做得极小；抓取的每一步 GPU 和
   文件系统操作本来就都在后端。

钩的是 NGX 核心（`_nvngx.dll`）的两个公开导出 `NVSDK_NGX_D3D12_CreateFeature` 与
`NVSDK_NGX_D3D12_EvaluateFeature`，都经 `src/backend/ngx/fg_gate.h` 的 observer——跳板归 fg_gate 所有。
**运行库（snippet）自己的同名导出永远不能钩**：`nvngx_dlssg.dll` 310.1 会把调用方的返回地址当参数往下传
（`mov rdx,[rsp+0x2d8]`），有跳板就 `0xbad00002`。feature id 在入口处过滤：1 录，11（DLSS-G）和其它一律原样转发。

后端平时只在游戏请求 `nvngx_dlssg.dll` 时才被加载，而用 DLSS 超分的游戏可能根本不请求它。所以
`[Debug] CaptureSR` 非零时，`src/proxy/loader.cpp` 在 **`nvngx_dlss.dll` 的 LoadLibrary** 上（以及"已经装过 DLSS-G 后端"
时兜底一次）加载内嵌后端，并通过两个新导出 `DlssgMod_ConfigureCaptureSr` / `DlssgMod_InstallCaptureSr` 安装——
它们不需要 DLSS-G 运行库、不校验 SHA、不做 GPU 检测、不替换任何内核，装完 `DlssgMod_Install` 照样可用。
选 `nvngx_dlss.dll` 这个触发点有两个原因：NGX 核心是在普通游戏线程上 `LoadLibraryExW` 它的（所以那一刻不在
loader lock 上，可以放心哈希并加载后端文件），而且它一定发生在任何超分特性创建之前（核心必须先问 snippet
才能回答 `SuperSampling.Available`）。**只加载后端**：自后端改成随包文件起这件事不需要任何机制——
后端是 `dlssg_sm86\backend\sm86_backend.dll` 这一个文件，`LoadLibraryExW` 它就是了，而 7.6 MB 的 NVIDIA 运行库
在这种进程里**根本没有被打开过**（以前要靠 `prepareBundle` 的 `parts` 才能不释放它）。

两份抓取的 ring 是分开的（一份能在另一份还没配置时就开始录，共享 vector 的 resize 会移动活着的 `Slot`），
但池、写盘线程、完成 fence 和平面写盘全部共用；`Slot::sr` 决定那几步会话相关的动作（目录名、manifest、计数、收尾），
`Slot::index` 在 SR 槽位上是**段号**（DLSS-G 槽位上是 `MultiFrameIndex`）。
共享的回读内存预算与 `COPY` 队列开关（DLSS-G 一侧是 `CaptureMemoryMB` / `CaptureAsyncCopy`，SR 一侧是写死的默认值；
暂存纹理两边都是 1536 MiB）由**先配置的那一份**决定，另一份不覆盖；一般 SR 先配置（它在 `nvngx_dlss.dll` 加载时就装好了）。

去重是在 `writePlane()` 里做的：开了去重时先对映射着的回读内存哈希一遍（不落盘），命中就只写 json；没开时仍然是
和 v1 逐字节相同的单遍“边写边哈希”，所以帧生成抓取的写盘路径一个字节都没变。

**manifest 不再每帧重写**：v1 一局最多 128 帧，v2 能有几千，而 `frames[]` 随之增长——每帧重写一遍是 O(n²)，而且
它在 ring mutex 下深拷贝整份文档，那正是游戏线程要抢的那把锁。改成**每 8 帧 + 每个段边界 + 收尾**各写一次，
所以硬杀进程最多丢最后几帧的**索引条目**（它们的像素与 `params.json` 早就在盘上了），正常退出由 `srFinishAtExit` 兜住。

一局**不限段数**的会话通常是玩家直接退出游戏才结束的，所以收尾在后端的 `DllMain(PROCESS_DETACH)` 里
（`srFinishAtExit`）：那时其它线程已经死了，被死线程占着的锁永远不会释放，因此**三把锁全部用 `try_lock`**
（ring mutex、manifest 文件锁，以及去重计数器那把——写盘线程可能正是在 `writePlane` 的去重块里被终止的），
拿不到就不写。`stop_reason` 会是 `process_exit`。

`CaptureSRNoStall=0` 那条路上，"字节上限到了"和"起点等超时"都发生在一次**透传**的 Evaluate 上，而平时把会话收尾的
是"最后一个录下的槽位被提交"那条路径——那时那个槽位早已上过 fence。所以这两处会在 `srNoStall=0` 时自己调
`srDrain()`；否则不会有 `capture_sr_done{stage:"complete"}`，`manifest.complete` 会一直是 false，写盘线程也不会退出。
`srEstimateFrame` 也因此改成无条件学一次（它原来只在 no-stall 下学，于是 `srNoStall=0` 的预算检查少算一整帧）。

三个 CTest 用例：`capture_sr_options_off` / `capture_sr_options_on`（ABI 闸门、"CaptureSR=0 什么都不武装"、
各处钳位、`CaptureSRStartOnCreate` 在带步长的多段会话里被拒、install 一定会写出 manifest）和
`capture_sr_disabled_mod`（第 1.1 节那张表）。链的都是真的 `src/backend/diag/capture.cpp` / `src/proxy/loader.cpp`。

---

## 7. 本机验证（RTX 5070，驱动 610.74，`nvngx_dlss.dll` 310.7.129）

### 7.1 v1（2026-09-18，仍然成立）

把一个研究用的超分探针程序当"游戏"用：它经 NGX 核心用 `nvngx_dlss.dll` 310.7.129 创建一个真正的 DLSS 超分特性，
而且**它自己也会把每帧上传的 `color` / `motion` / `depth` 和读回的 `output` 写到磁盘上**，所以抓取到的字节可以和
"游戏自己知道的字节"逐位对账。注入方式：把探针 EXE 拷进一个临时目录，把 `alternatives\d3d12.dll` 放在旁边
（探针静态导入 `d3d12.dll` 和 `dxgi.dll`，两者都不是 KnownDLL，所以 EXE 目录里的先被加载；探针本身不导入
`version.dll` / `winmm.dll`），再放一份只有 `[Debug] CaptureSR*` 的 INI。

| 项 | 结果 |
|---|---|
| 320×192 → 640×384 / 960×540 → 1920×1080 / 1920×1080 → 3840×2160 三种，两种 NoStall 模式 | 全部录满，0 丢弃 0 跳过，`complete=true` |
| **像素逐位对账** | 三次共 **74 个平面对**（`color` / `depth` / `mv` / `output`）与探针自己写的 `frame_<n>/*.bin` **逐字节相同** |
| 参数对账 | 创建参数、`MV.Scale.X/Y`、`Jitter.Offset.X/Y`、`DLSS.Pre.Exposure`、`DLSS.Exposure.Scale`、`FrameTimeDeltaInMsec`、`Sharpness`、逐帧 `Reset` 全部与探针设的值一致 |
| 有序读日志 | 每帧 121 条 / 120 个不同名字，CreateFeature 时 38 条 / 30 个不同名字 |
| 离线转换 | 输入包里每个 sha256 自洽；8 帧 × 4 个平面与探针自己的输出**逐字节相同**；另写的 float32 深度恰好是探针写的 `0.990099` / `0.9967663` |
| 下游闭环 | 用这个流程产出的输入包在原厂 FP8 重放上**逐位复现了包里的参考输出**（8/8 帧），并第一次量出"换内容要重新标定"是 +11…+17 dB |

**赛博朋克 2077 没有录到**，原因是确定的而不是失败：2026-09-16 那次会话的后端日志里 NGX 核心创建的是
**feature 13（光线重建）**和 **feature 11（帧生成）**，`feature 1` 一次都没有——这台机器上的赛博朋克开的是
Ray Reconstruction，不会创建超分特性，所以 `CaptureSR` 本来就录不到东西。要在它上面录必须先在游戏设置里
关掉光线重建，而那属于"改游戏设置"。

### 7.2 v2（2026-09-18）

同一套探针注入法，960×540 → 1920×1080、preset L、噪声运动场景。

| 用例 | 结果 |
|---|---|
| 段 + 步长（`CaptureSR=4 CaptureSRStride=3 CaptureSRBursts=2`，40 次 Evaluate） | 2 段 × 4 帧 = 8/8 录下、写盘 8，`stride_skipped=12`，0 丢弃 0 跳过，`stop_reason=bursts_complete`，`complete=true`；目录 `burst_0001\frame_0001` … `burst_0002\frame_0004` |
| 去重 | 同一会话 14 个平面被引用、省下 13.8 MiB；引用 json 带完整 footprint + `source` + `source_bytes`；`dedup_unique_planes=18` |
| **字节预算**（`CaptureSR=20 CaptureSRBursts=0 CaptureSRMaxGB=1`，250 次 Evaluate） | 170 帧 / 9 段（8 段满 + 1 段 10 帧），**1010.5 MiB 对 1024 MiB 上限**（余 13.5 MiB，从未越过），0 丢弃 0 跳过，`stop_reason=budget` |
| 字节预算 + **`CaptureSRNoStall=0`**（`CaptureSR=6 CaptureSRBursts=0 CaptureSRMaxGB=1`） | 171 帧 / 29 段（28 满 + 1 段 3 帧），1016.5 MiB 对 1024 MiB，0 丢弃 0 跳过，两条记录都到位：`capture_sr_done{stage:"budget"}` 之后 `{stage:"complete",stop_reason:"budget"}`，`complete=true` |
| **没有任何界**（`CaptureSRBursts=0`，`CaptureSRMaxGB` 缺省） | 后端自己放上 8 GiB 上限并记 `capture_sr_options{key:"[Debug] CaptureSRMaxGB",requested:0,effect:8}`；同一局里 `CaptureSRStartOnCreate=1` 也被拒并记了自己那条 `capture_sr_options`（两条都是在 `configure` 里排队、由 `install` 放出来的——`configure` 跑在后端打开日志文件之前） |
| 不限段数 + 进程退出（`CaptureSR=3 CaptureSRStride=5 CaptureSRBursts=0`） | 11 帧 / 3 段满 + 1 段在飞，`stop_reason=process_exit`，`complete=true`（写盘 = 录到），manifest 由 `srFinishAtExit` 收尾 |
| 可复现档（`CaptureSRStride=1 CaptureSRBursts=1 CaptureSRStartOnCreate=1`） | 6/6，`start_reason=new_feature`，段记录 `consecutive=true` `reproducible_start=true`，包里同样 |
| **按键触发的段**（`CaptureSRStartKey=Insert CaptureSRBursts=0`，4000 次 Evaluate，用 `keybd_event` 注入按键） | 三次分开的按下 → **恰好 3 段 × 3 帧**，每段 `start_reason=key` 且 `start_evaluate` 就是按下那一帧（23 / 223 / 388）；每段结束后的**第一次** Evaluate 就发出"再按一次"的记录（`skipped_this_wait=1`）；随后按住 1.5 秒**没有**开出任何多余的段（如果边沿检测坏了，3000 次 Evaluate 会开出上千段）。注入的那次长按最终没被当成新的一次按下——注入的抬起与下一次按下之间的间隔太短，按键必须先被**看到**抬起才算新的一次，这是保守的那一边 |
| **`[General] Enabled=0`（采集部署）** | 抓取正常跑（11 帧 / 3 段）；loader 日志里**只有 4 条**：`configuration{enabled:false}`、`backend_loaded{loaded:true,sha256:...}`、`capture_sr_requested{mod_enabled:false,runtime_extracted:false,dlssg_untouched:true,trigger:"nvngx_dlss_load"}`、`capture_sr_only`；**没有** `backend_install` / `runtime_redirect` / `arch_spoof_*` / `turing_host*`；随包的 `dlssg_sm86\runtime\nvngx_dlssg.dll` 逐字节不变（2026-09-29 起的形态；此前这一行是 `bundle_ready{parts:"backend"}` + "缓存目录里只有 `sm86_backend.dll`"） |
| 版本无关的运行时检查 | `unknown_read_names` 为空（310.7.129 读的 120 个名字全在表里）；`creation` 解出 `perf_quality_name=MaxPerf`、`render_preset=12` → `render_preset_name=L`、`render_preset_tier=Performance`、`dlaa=false` |
| 压缩往返 | zlib-6 与 lzma-2 各压掉 17 个平面（4 字节的曝光低于压缩的最小尺寸，原样留着），解压校验全部通过，解压之后**两种方法都 18/18 个 `.bin` 与压缩前逐字节相同** |
| 离线转换跟引用与压缩 | 同一会话分别从**原始**、**zlib 压缩后**、**lzma 压缩后**三个目录转成包，**40/40 个 `.bin` 三者逐字节相同**，每个包的哈希自洽；按段拆包输出 2 / 9 个包；单独取一段时，被去重的颜色平面在包里报的是逻辑大小而不是它在那一帧的 0 字节 |
| 会话目录表 | 10 个会话目录（v1 的 schema 1 与 v2 的 schema 2 混在一起，含压缩过的）列成表：236 帧 / 1.7 GB，按族（`mvlo+ldr=236`）、分辨率、预设汇总，压缩过的会话带上 `compaction` 与比率。（这 10 个都是同一台机器上的探针会话，不是 10 个游戏——真实游戏的表要等第一份真抓取。） |
| 一键工具（离线） | `-Analyze -CaptureSRDir` 在 v2 多段会话、v2 可复现会话、v1（schema 1，平铺 `frame_*`）会话上都给出正确判定；脚本仍是 UTF-8 BOM + 纯 LF，`PSParser` 无错 |
| **一键工具（整条流程）** | 把 `dlssg_diag.ps1` + `dlssg_sr_collect.cmd` + 出厂 INI 和探针放在一个目录里，`-CaptureSR 6 -SRStride 4 -SRBursts 0 -SRMaxGB 2`，**1920×1080 → 3840×2160**：武装 INI（只加 `CaptureSR*` 与 `[Logging] Level`）→ 中文里程碑（武装 / 挂钩 / 创建特性 / prewarm `31.6 MiB` 每帧 / 逐段"第 N 段录完" / 写盘进度）→ 探针退出 → **INI 的 SHA-256 与改之前逐字节相同** → 按 manifest 验收 `采集成功：2 段，共 17 帧`（第 3 段在进程退出时只写了 5 帧）→ 报告 + 小 zip + 抓取单独打包。0 丢弃 0 跳过 |
| CTest | 21/21 通过（新增 `capture_sr_disabled_mod`） |
| **DLSS-G 抓取没有回归** | 共用的 `writePlane()` 被改过（去重是它的新分支），所以用 `sm86_scene`（640×384 ×3，`CaptureStartOnReset=2`）两种模式各录一次，再和 v1 验证时留下的那两份抓取逐字节比：`CaptureNoStall=1`+`CaptureLean=1` **12/12 个 `.bin` 相同**、`CaptureNoStall=0` **30/30 相同**；manifest 仍是 schema 1、目录名仍是 `0001_f0_i1` 式、`inputs/`+`outputs/` 布局不变、lean 引用仍写 `stored=false` + `source=0001_f0_i1/inputs/Backbuffer.bin`、json 里没有任何 `dedup` 字段 |

---

## 8. 已知限制

- 只有 **D3D12**，只有 **NGX feature 1**（feature 13 的会话 2026-10-09 随光线重建路线删除，见第 9 节）。DLSS-G（11）和别的特性一律原样转发。
  Vulkan 的 DLSS 走另一套接口，没有实现。
- **第 7 节的验证全是探针程序当游戏**（写于 2026-09-18，那时真实游戏上还没跑过；之后真实游戏数据的压缩比见第 9 节末尾）。
  本文没有逐项核对的：HDR 颜色格式、高分辨率运动矢量、反向深度、带 subrect offset 的游戏、DLAA。
- 假定的资源状态是 NGX 的 D3D12 约定：输入 `NON_PIXEL_SHADER_RESOURCE`、输出 `UNORDERED_ACCESS`
  （和 DLSS-G 抓取同一个假定，`manifest.json` 的 `states` 里有数值）。把输入留在别的状态上交给 DLSS 的游戏会在
  调试层上报一次错误的 before-state。
- 多重采样和子采样的视频格式跳过（记 `capture_plane_skipped`），DLSS 不会收到这些。
- 运行库的时域状态不在抓取里，所以只有"新建特性的第一帧"起录才可能复现游戏自己的输出（第 2 节的表）。
- 去重是**整局**的，跨会话不去重：两个会话里相同的平面会各存一份。跨会话去重需要一个共享的索引，而会话是分开
  压缩、分开传的，所以没做。
- `CaptureSRMaxGB` 的估算用的是"上一帧学到的平面尺寸"，游戏中途改分辨率后第一帧的估算会偏；上限本身仍不会被越过
  （检查的是已落盘 + 在飞 + 一帧），只是可能提前一帧停。
- 两套抓取同时武装（`Capture` 与 `CaptureSR` 都非零）代码上是允许的，但没有实测过，一键工具也直接拒绝这种组合。
- 压缩是离线的一步，不是录制时做的（原因见第 3.2 节）。所以录制期间的磁盘占用是未压缩的那个数。

---

## 9. 光线重建（`[Debug] CaptureRR`，NGX feature 13）：已删除

2026-10-09 随光线重建路线一起删除（业主决定，`docs/RR.md`）。原来 `CaptureRR=N`（= `CaptureSR=N` 加
`CaptureFeature=13`）把同一套会话指向 feature 13——开着光线重建的游戏只创建 feature 13（第 7.1 节末尾），那是在这类
游戏上录到 DLSS 输入的唯一办法；manifest 是 schema 3（`feature.id = 13`），平面 json 多一个 `role`，参数名另有一张表。

现在：

- `[Debug] CaptureRR` 与 `CaptureFeature` 不读（2026-10-26 起，`docs/COMPAT.md` C113；此前只为告警而读）：什么都不武装，
  `CaptureRR=N` 不等于 `CaptureSR=N`。
- 抓取只录 feature 1：`ModCaptureSrOptions::feature` 字段保留（结构只增不减），0 与 1 照办，其它值（含 13）由后端拒绝
  并记 `capture_sr_options`。manifest 恒为 schema 2，feature 1 的名字表、输出名与平面文件逐字照旧（`docs/COMPAT.md` C55）。
- `nvngx_dlssd.dll` 的加载照旧武装 `CaptureSR`：开着光线重建的游戏因此会在日志里留下
  `capture_sr_feature{stage:"other_feature",feature_id:13}`，而不是什么都不录也不说。
- 已经录好的 schema 3 会话是普通文件，读它们的是 `dlss` 那侧的转换器（私有），不需要这个后端。

删除之前的完整说明——键、赛博朋克 2077 的两局实测（2560×1440 → 3840×2160、预设 F、游戏真正交出的 11 个平面与
113 个非资源名字）、真实游戏数据的压缩比（主菜单 0.12–0.14、真实游玩 0.42）与 `-save=` 直接进游戏的办法——在这次
提交之前的 git 历史里。
