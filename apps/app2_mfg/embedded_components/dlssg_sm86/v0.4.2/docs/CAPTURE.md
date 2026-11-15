# 游戏抓取与离线重放（GCR：Game Capture & Replay）

在**真实游戏里**把 DLSS-G 每次 Evaluate 的输入、参数和输出录下来，然后在本机离线重放：同一份抓取可以分别跑在原厂
运行库（native）和我们的 SM86 路由上，逐位对比两边的输出。这样一来"某个游戏画面不对"就不再需要那台游戏机器——
把抓取目录拷回来，在这里按帧比较就行。

抓取由代理 DLL 里的后端完成（`src/backend/diag/capture.{h,cpp}`），重放由 `sm86_replay.exe`
（`tests/native/replay.cpp`，需要 `-DDLSSG_BUILD_GPU_TESTS=ON`）完成，`scripts/perf/replay_check.py` 是把两半串起来的
驱动脚本。**`[Debug] Capture=0`（出厂默认）时整套机制完全不存在**：不装任何钩子、不建线程，Evaluate 钩子里只多一个
恒假的 `if`（1080p 实测每生成帧 1146 → 1147 µs，误差范围内）。

---

## 1. 在游戏里录一份抓取

把 `version.dll`、`dlssg_sm86.ini` 与 `dlssg_sm86\` 按 `INSTALL.md` 正常部署到游戏 EXE 旁边，然后在 INI 的
`[Debug]` 节加上：

```ini
[Debug]
; 录多少次 Evaluate。0（默认）= 关闭整套机制
Capture=12
; 抓取目录：绝对路径，或相对于游戏 EXE 目录。默认 dlssg_sm86\capture
CaptureDirectory=<工作目录>\captures\wukong
; 先跳过多少次 Evaluate（跳过加载画面、过场动画）
CaptureSkip=0
; 从哪一帧开始录：1（默认）= DLSSG.Reset 帧或新建特性的第一帧；2 = 只认新建特性（唯一能逐位一致的起点）；0 = 立刻录
CaptureStartOnReset=1
; 按键触发（默认 0 = 不用）：设成 F9 之后，CaptureSkip 满足后继续等，直到在游戏里按下 F9 才应用上面那条规则
CaptureStartKey=0
```

输入资源与两个输出资源总是全录（`CaptureInputs` / `CaptureOutputs` 2026-10-22 删除，`docs/COMPAT.md` C102；2026-10-26 起不读，C113）。

要点：

- **`Capture` 数的是 Evaluate 次数，不是帧数**。3×（`MaxGeneratedFrames=2`）的游戏每个真实帧调用 2 次，6× 调用 5 次。
  想录"完整的 4 个真实帧"就写 `4 × (倍率-1)`。
- **从哪一帧开始录由 `CaptureStartOnReset` 决定；只有"新建特性的第一帧"能逐位一致**。运行库在两次 Evaluate 之间
  保留颜色历史（预设 B 还有一对 UI 历史），而历史**不在抓取里**，所以重放只有从"历史为空"的那一帧开始才可能逐位
  一致。实测（2026-09-14，悟空，310.9.1，3070）：

  | 抓取从哪一帧开始 | 重放结果 |
  |---|---|
  | 刚 `CreateFeature` 完之后的第一次 Evaluate（`evaluatesAtCreate+1`，`MultiFrameIndex<=1`） | **逐位一致**（cap31b / cap91b，见第 4 节） |
  | `DLSSG.Reset` 置位的那一帧，但特性已经跑了 3169 次 Evaluate | 每张生成图 **64.9–73.3 dB**，`OutputReal` 逐位一致 |
  | 随便一帧（`CaptureStartOnReset=0`） | 第一帧约 33 dB（24.5 万像素里约 1000 个不同），第二帧回到 68–77 dB |

  也就是说 **`DLSSG.Reset=1` 并不会把运行库的内部缓冲清成"刚创建"的状态**——它只是让运行库丢弃运动历史，颜色/UI
  历史照样带过来。（那次 64.9 dB 不是重放不确定：同一份抓取重放两遍 70/70 张逐位相同，`OptimizedKernels=0` /
  `ImagePatches=0` 的重放也和默认重放逐位一致。）所以三个取值是：

  - `2`：**只认新建特性**，忽略 `DLSSG.Reset`。想要逐位一致的抓取就用这个，操作办法见第 4 节（进到要录的画面，
    在游戏设置里把帧生成关掉再打开）。
  - `1`（默认）：`DLSSG.Reset` 帧**或**新建特性的第一帧，先遇到哪个算哪个。省事，但如果先遇到的是 `Reset` 帧，
    生成图就只有 60–70 dB 这个量级。
  - `0`：`CaptureSkip` 之后立刻开始录。

  等待期间记 `capture_waiting_for_reset`（含已跳过多少次），真的开始时记 `capture_start_armed`（含 `reason` 与
  `bit_exact_replay`）；等满 3 分钟还没遇到就记 `capture_start_timeout` 并**什么都不录**（这时要么把 `CaptureSkip`
  调小、要么在游戏里切一次帧生成开关、要么写 `CaptureStartOnReset=0`）。起点不是"新建特性"时，`sm86_replay` 会打印
  `WARNING this slice does not begin at the first Evaluate of a freshly created feature` 并在报告里写
  `summary.first_is_new_feature=false`，逐帧判定照常给出。
- **`CaptureStartKey`：把起点交给玩家。** 上面三种起点都不由玩家掌握（固定跳过数、`Reset` 帧、在设置里切开关之后的
  第一帧——那一帧画面是静止的），而人物边缘的毛边这类问题只在运动中出现。设 `CaptureStartKey=F9`（F1–F24、单个字母/
  数字，或 VK 码 `120` / `0x78`）之后，`CaptureSkip` 满足后继续等，直到后端在 Evaluate 线程上看到这个键被按下
  （`GetAsyncKeyState`，游戏窗口有焦点即可），再从那一刻起应用 `CaptureStartOnReset`：`0` = 按下的那次 Evaluate 立刻
  开始录（`manifest.capture.start_reason=key`，同 GPU 重放不逐位一致——历史不空，但**两次重放之间**仍可直接比较，见
  第 3 节末尾）；`1`/`2` = 从按键起再等 `Reset` / 新建特性，3 分钟超时也从按键算起（先按 F9、再去设置里切一次帧生成，
  就得到一份逐位一致的抓取）。等待期间记 `capture_waiting_for_key`（第一次及之后每 600 次），按下时记
  `capture_start_key`。`Capture=0` 时和其它抓取键一样完全不存在。
- **`CaptureNoStall=1`：不拖慢游戏，整份抓取放在内存里。** 默认（`0`）是连续录：4 个回读槽位在 4K 下 17 ms 就满，之后
  每次 Evaluate 都等写盘（游戏线程最多等 2 秒抢槽位），游戏掉到几帧，录到的输入本身就是"卡顿中的运动"（每帧位移是
  正常游玩的十几倍）。`1` 时游戏线程**永远不等**：环和 `Capture` 的次数一样深，回读缓冲由写盘线程在等待起点期间就按
  `capture_prewarm` 学到的平面尺寸提前建好（录制时游戏线程不做任何分配），录满之后文件在后台写完（`capture_finishing`
  → `capture_done`，脚本等的就是它），所以录到的是**连续**的帧。内存预算 `CaptureMemoryMB`（默认可用物理内存的一半；
  回读堆在系统内存，48 GB 的机器放几十个 4K Evaluate 没有压力）用完时才按整组跳过——同一真实帧的全部生成帧
  （`MultiFrameIndex` 1..count），绝不在组中间丢——等写盘释放内存后再录。组是否放行按 `capture_prewarm` 学到的尺寸整组估算（`estimate_bytes`），已放行的组内不再做逐平面上限；被拒的平面会写进 `params.json` 的 `skipped_planes`，`sm86_replay` 据此判 `outputs_bit_exact=false`。测试用 `DLSSG_CAPTURE_WRITER_DELAY_MS=<ms>` 可以拖慢写盘线程，把跳组路径确定性地逼出来。代价只剩每次 Evaluate 命令列表里的回读拷贝
  （PCIe，4K 精简模式每组约 200 MB）。事件 `capture_group_skipped`（含原因：没槽位 / 预算用完），
  `manifest.capture.taken_groups` / `skipped_groups` / `skipped_groups_memory`。**重放时每个间隙后的第一组只用来暖运行库
  的上一帧历史**（生成帧插值的是上一真实帧和当前真实帧，上一帧不在抓取里、由运行库自己保留），所以真出现跳组时可比较的
  是每个连续段的第二组起，`capture_compare.py` 按 `params.json` 的 `evaluate_seen` 断点自动把它们标成 warm-up 并排除
  在汇总外；整份抓取的第一组同理。
- **`CaptureLean=1`：只回读不能重建的数据。** 同一组内 index>1 的 Evaluate 交出的输入资源和 index 1 完全相同
  （三份悟空抓取 cap31b / cap91b / 0619 共 54 个 index>1 的纹理平面逐字节一致，只有 16 字节的
  `OutputDisableInterpolation` buffer 每次不同，它照录），`DLSSG.OutputReal` 是运行库对 `DLSSG.Backbuffer` 的拷贝
  （18/18 逐字节一致）。所以 index>1 的输入纹理和每次的 `OutputReal` 都只记成**引用**：平面 json 里 `stored=false`、
  `source=<相对抓取根目录的文件>`、`lean=group_input|real_is_backbuffer`，不建回读缓冲、不进命令列表、不写 `.bin`；
  `sm86_replay`、`capture_compare.py` 与 `replay_check.py` 的 `scene_cross_check` 都跟着 `source` 取字节和 footprint。
  4X 下每组约 465 MB → 208 MB，回读的 PCIe 时间同比减少。引用只在**连续录下的同一组内**成立（index 1 重填表、
  断组清表），所以和 `CaptureNoStall` 的整组录制天然配套。
- 抓取只对 **D3D12** 有效（Vulkan 的 DLSS-G 走另一套接口，没有实现）。
- 录完之后这套机制自动停下（`capture_done`），游戏继续正常跑，写盘线程退出。

### 磁盘占用

一次 Evaluate 写的字节数 = 所有平面的 `宽 × 高 × 每像素字节` 之和，平面 = 游戏交出的每个输入资源 + 2 个输出，
**同一个资源被两个参数共用时只存一份**（例如不给 HUD-less 的游戏里 `DLSSG.HUDLess` 就是 `DLSSG.Backbuffer`）。
本机实测（RTX 3070，写到 E 盘）：

| 场景 | 平面 | 每次 Evaluate | 12 次合计 |
|---|---|---|---|
| 640×384，RGBA8，无 UI | 5（Backbuffer、Depth、MVecs、output、real） | 5.6 MiB | 67.5 MiB |
| 1280×720 ×2，RGBA8 | 5 | 21.1 MiB | 168.8 MiB（8 次） |
| 1280×720 + UI 平面 | 7（多 HUDLess、UI） | 28.1 MiB | 337.5 MiB |
| 1920×1080，RGBA8 + RG32F 运动矢量 | 5 | 47.5 MiB | 569.5 MiB |
| **悟空，4K HDR10 输出 / 1080p 渲染，4X** | 9（`i1`）/ 8（`i2`、`i3`） | **154.9 MiB 平均** | **1858.9 MiB** |

真实游戏一般是 HDR。悟空是 HDR10（`R10G10B10A2_UNORM`，4 B/像素）而不是 FP16，所以 4K 每张颜色平面 31.6 MiB、
每次 Evaluate 141–174 MB；换成 `R16G16B16A16_FLOAT` 的游戏要翻倍（4K 一张 66 MB，**每次 300 MB 上下**），
录 30 次要预留 **8–10 GB**。先录 6–12 次、确认内容对了再加量；`CaptureDirectory` 请指向 SSD 上的空目录。

### 代价与背压

- **回读拷贝是一次 PCIe 传输，录进游戏自己的命令列表就等于串在渲染队列上。** 3070（PCIe 4.0，实测有效 26.3 GB/s）
  上 `CaptureLean=1`：4K 的 index 1 从 3276 µs 涨到 9597 µs、index 2/3 从 2000 µs 涨到 3275 µs（每生成帧 +122 %），
  1080p +74 %。`CaptureAsyncCopy=1`（默认）改成：游戏的命令列表里只做显存→显存的 `CopyResource`（拷进按
  (设备, 格式, 尺寸) 池化的暂存纹理，走显存带宽），再由一条独立的 `COPY` 队列把暂存纹理搬进回读缓冲，和游戏渲染并行；
  `COPY` 队列先 `Wait` 游戏那次 `ExecuteCommandLists` 的 fence，槽位的完成判定改看 `COPY` 队列自己的 fence。
  暂存纹理的总量固定为 1536 MiB（`COPY` 队列读完就还池；`CaptureVramMB` 2026-10-22 删除），超预算的平面退回旧的内联回读并记一条
  `capture_plane_inline`；建不出 `COPY` 队列时记 `capture_async_copy_unavailable` 并整体退回。`CaptureAsyncCopy=0`
  强制旧路径，用来做对照。
- **实测开销**（3070，`sm86_bench` 自然提交、cubin、优化开，8 个测量帧 ×3，`Capture=48` + `CaptureNoStall=1` +
  `CaptureLean=1`，抓取开/关交错各跑两轮取均值）：

  | 分辨率 | 每生成帧（抓取关） | 异步（默认） | 内联（`CaptureAsyncCopy=0`） |
  |---|---|---|---|
  | 3840×2160 | 2606 µs | 3038 µs（**+432 µs，+16.6 %**） | 5485 µs（+2879 µs，+110.5 %） |
  | 1920×1080 | 1029 µs | 1174 µs（**+145 µs，+14.1 %**） | — |

  4K 逐 index：index 1 3565 → 4160 µs（异步）/ 9787 µs（内联），index 2 2084 → 2611 / 3356，index 3 2170 → 2344 / 3313。
  同配置两次"抓取关"之间的抖动：1080p 每生成帧 0.3 %、4K 每生成帧 4.0 %（4K 的 index 1 单独看能到 9 %），
  所以 1080p 的 +14 % 和 4K 的 +17 % 都远在噪声之外，而 4K 异步的绝对开销（0.43 ms）**不到内联的六分之一**。
  暂存纹理的实际占用很小（4K 30 次连续抓取 159 MiB、1080p 40 MiB），远低于 1536 MiB 的默认预算。
- 写盘在一个 `BELOW_NORMAL` 优先级的后台线程上，环里最多 4 个在飞的槽位；**游戏线程不等 GPU**，唯一例外是最后一次
  被录制的 Evaluate 提交之后的一次收尾（`capture_done` 的 `drain_ms`，本机 25–120 ms），这样进程立刻被关掉也不会丢
  最后几张图。
- 如果写盘跟不上，游戏线程最多等 2 秒抢一个槽位（等待期间自己帮着写），超时才丢弃并记 `capture_slot_dropped`。
  1080p 实测：4 帧 ×3 的场景总耗时 2062 ms → 2340 ms（+278 ms，写了 569 MiB），没有丢帧。
- 以上是默认模式。`CaptureNoStall=1` 时没有这些等待：整份抓取放在内存里（环 = 次数，预算默认可用物理内存的一半，回读
  缓冲提前建好），录满后 `capture_finishing` → 后台写完 → `capture_done`（`drain_ms=0`，游戏线程一次都不等），内存预算
  用完才整组跳过。合成场景实测（3070，310.9.1，lean）：1080p 24 次、4K 30 次全部连续录满、跳组 0、按键前池里已有
  406 / 597 MB 缓冲、scene 快照 48/48、60/60 匹配。剩下的代价只有命令列表里的回读拷贝本身。
- 一次 `Capture=N` 结束后 `manifest.json` 的 `complete` 必须是 `true`，`dropped` 必须是 0。

### 在 50 系上录"原厂"输出（native）

抓取**不要求替换内核**：RTX 40 / 50 自 0.4.0 起默认跑本项目的内核（`docs/COMPAT.md` C77），写 `[Compatibility] KernelImage=Original`
时一个内核都不替换，后端仍然会安装 Evaluate 与 CreateFeature 钩子，只为抓取服务（RTX 40 上运行库自己的内核只能 2X，
还要 `MaxGeneratedFrames=1`）。`manifest.json` 里 `backend.route_active` 为
`false`、`backend.kernel_image` 为 `original` 的抓取就是**原厂参考**。

50 系上录参考的 INI：

```ini
[General]
Enabled=1
[Compatibility]
KernelImage=Original
[Debug]
Capture=12
CaptureDirectory=<工作目录>\captures\native
```

**Ampere（3070/3080 Ti）上录不出 native 参考**：NGX 核心在 Ampere 上直接拒绝帧生成特性
（`sm86_replay --proxy 0` 实测 `CreateFeature 0xbad0000b`），所以原厂那一半只能在 40/50 系上录。同理，用
`KernelImage=Original` 在 Ampere 上取"运行库自己的数值"也不行：310.9 会干净地返回 `0xbad00002`（抓取仍然写出
`create_1.json`，记下失败状态，不崩）。

---

## 2. 抓取目录的内容

```
<CaptureDirectory>\
  manifest.json            EXE 路径、运行库 SHA/版本、后端 id、GPU、路由是否生效、完整 INI 文本、
                           NGX 核心（_nvngx.dll）路径与 FileVersion、以及每次 Evaluate 的清单
  create_1.json            CreateFeature 时的参数：探测快照（probe）、运行库真正读过的有序日志（reads）、
                           调用后的再次探测（probe_after）、返回状态
  0001_f0_i1\              一次 Evaluate：<序号>_f<BackbufferFrameID>_i<MultiFrameIndex>
    params.json            probe + reads + planes（每个平面的 desc/哈希/文件名）
    inputs\Backbuffer.bin  紧排（无行距填充）的原始像素 + 同名 .json（desc、别名、SHA-256、子资源布局）
    inputs\Depth.bin       多平面深度：两个平面首尾相接在同一个文件里
    inputs\OutputDisableInterpolation.bin    buffer 参数：Evaluate 之前的整块内容
    outputs\output.bin     DLSSG.OutputInterpolated
    outputs\real.bin       DLSSG.OutputReal
    outputs\OutputDisableInterpolation.bin   同一个 buffer，Evaluate 之后的内容
```

一个资源一个 `.bin`，里面按 `GetCopyableFootprints` 的顺序（`mip + arraySlice*mips + plane*mips*arraySize`）
把所有子资源紧排拼接。每个平面的 `.json` 里 `subresources[]` 逐条给出 `plane` / `mip` / `array_slice` /
`format` / `rows` / `row_bytes` / `offset_in_file`，所以要单独取深度平面（或模板平面）直接按 `offset_in_file`
切片就行，不用自己复算 footprint。`buffer:true` 的平面没有 `subresources`，整个文件就是那块 buffer。

`params.json` 里两份参数记录的分工：

- **`probe`**：把 188 个已知参数名（两个运行库的字符串表 + NGX 核心自己读的几个 + **代 A 独有的那 28 个**）逐个喂给
  **全部 8 个带类型的 getter 槽位**，凡是有回答的都记下来。这是"游戏侧状态"的权威快照，与运行库这一帧读了什么无关，
  重放就靠它。代 A 那 28 个名字（`QueueSubmitCallback` 这一族的队列 / 同步所有权、`FenceEvent`、`EvaluateIsReady` /
  `SynchronousInit`、`VkOFAModeRequest`，加九个调试名）**在 310.x 上没人读**，所以有序读日志 `reads` 里永远看不到它们
  ——只有这份 probe 能记下来。给一款自带 ≤3.8.x 运行库的游戏做抓取时（那类游戏照样被我们接管、照样能跑，见
  `docs/INSTALL.md` 的代际一节），这 28 个名字正是那份抓取里最值得看的部分。
- **`reads`**：运行库**实际**读过的顺序日志（名字、槽位、值、如果是资源则连它被抓到哪个文件）。用来看运行库这一版
  到底关心哪些参数、按什么顺序读——例如 310.1 的一次 Evaluate 读 72 个名字，CreateFeature 读 20 个。

参数存储的类型规则（在 591.86 驱动 + RTX 3070 上实测，`capture_parameter_hooks` 记录了实际槽位表）：8 个 getter 槽
位实际只有 7 个实现（`+0x40` 和 `+0x48` 是同一个函数，即 8 字节/指针 getter，所以 `+0x08` 是 8 字节 setter，浮点
setter 是 `+0x30`；槽位类型见 `src/backend/ngx/ngx_abi.h`），而数值 getter 之间**会互相转换**：用 `+0x20` 写进去的整数 3，从
`+0x58` 读出 3、从 `+0x70` 读出 3.0f、从 `+0x68` 读出 3.0（所以 `+0x68` 是 double getter）。重放因此不必猜"哪个
setter 配哪个 getter"，只要能让**每个被记录的 (名字, 槽位, 值)** 都原样读回来即可，而这一点是被逐项验证的。

**指针 getter 也会答数值参数**，这点坑过一次（见第 4 节）：float `DLSSG.CameraPosY=400061.78125` 从 `+0x78` 读出的是
截断后的 `0x61abd`。那个"指针"偶尔指向一块真的可读内存时，抓取会把它当成 64 字节 `buffer` 记下来，重放照它写一个真
指针进去就毁掉这个参数。所以 **同名只要还答过数值 getter，它的指针回答一律记成 `kind:"opaque"` +
`reproducible:false` + `numeric_alias:true`**（`capture.h` 的 `demoteNumericPointerAliases`），重放侧的优先级也是
"经 `QueryInterface` 证实的对象（`resource`/`command_queue`/`command_allocator`/`device`）→ 数值回答 → 裸指针（含
`buffer`）"。只答指针 getter 的参数（五个 4×4 矩阵、资源、回调）不受影响。

---

## 3. 在本机重放

```powershell
$py = "python"   # 带 numpy 的 Python 3.10+
# 用我们的 SM86 路由重放，逐帧和录下来的输出对比
& $py scripts\perf\replay_check.py --out <工作目录>\wukong --capture <工作目录>\captures\wukong --modes proxy
# --runtime-model 接受 310.9.16（默认）或 310.9：310.1 运行库已退役，它录的抓取喂给 310.9.x 就是跨运行库重放
# 原厂路由（无代理）和我们的路由各跑一遍，并且互相对比
& $py scripts\perf\replay_check.py --out <工作目录>\both --capture ... --modes proxy,native --cross
# 和另一次重放的输出对比（例如 5070 上的原厂重放 vs 3080 Ti 上的我们）
& $py scripts\perf\replay_check.py --out <工作目录>\b --capture ... --modes proxy --compare-with <工作目录>\a\replay-proxy\out
```

脚本还能顺手造一份抓取（拿 `sm86_scene.exe` 当游戏），这是这套机制的自检：

```powershell
& $py scripts\perf\replay_check.py --out <工作目录>\c1 --record --width 1920 --height 1080 --multi 3 --frames 4 --evaluates 12 --modes proxy
```

`--record` 会额外把抓到的每张图和 `sm86_scene` **自己**通过命令列表钩子独立存下的快照逐字节比对
（`scene_images_matched`），所以"抓取本身是否忠实"和"重放是否忠实"是两个互相独立的判据。`sm86_scene` 与 Streamline 一样只在
index 1 交出 `DLSSG.OutputReal`（2026-10-08 起），所以真实帧只在 index 1 有、也只在 index 1 比对。

`sm86_replay.exe` 也可以直接用：

```
sm86_replay.exe --capture <抓取目录> --dll <nvngx_dlssg.dll> --runtime <_nvngx.dll> --out <输出目录>
                [--proxy 0|1] [--start N] [--count M] [--compare 0|1]
                [--compare-with <另一次重放的 out 目录>] [--runtime-sha <期望的运行库 SHA-256>]
sm86_replay.exe --selftest      # 只用 D3D12：多平面深度与 buffer 的上传/读回自检，不需要抓取和运行库
```

- `--dll` 必须是一个**名叫 `nvngx_dlssg.dll`** 的文件：代理只按这个文件名拦截（`src/proxy/loader.cpp` 的 `candidate()`），
  给别的名字会加载一个没被钩住的副本、然后让 NGX 核心再加载一个被钩住的。脚本会自动把运行库拷成这个名字。
- `--proxy 1` 断言这个进程里 SM86 路由真的生效了（读 `SM86Bridge_GetStats`），`--proxy 0` 不做要求。
- `--start/--count` 只重放其中一段；注意上面关于 `Reset` 帧的限制。
- 重放会把自己的输出也按抓取的目录结构写到 `--out`，所以任意两次重放都能用 `--compare-with` 相互比较。

重放做的事，按顺序：用录下来的创建参数调 `CreateFeature`（没有 `create_*.json` 时退化成用第一次被重放的 Evaluate 的
`probe`，游戏侧的创建参数一直留在存储里，所以这是等价的）→ 每个**被记录的资源指针**建一张纹理（指针相同就共用一
张，因为运行库会比较指针来判断"给了没给 HUD-less"）→ 上传录下来的字节 → 按录下来的 probe 逐个设参数 → 把输入转到
`NON_PIXEL_SHADER_RESOURCE`、输出转到 `UNORDERED_ACCESS` → `EvaluateFeature` → 读回输出并比较。

### 判定怎么读

`replay_report.json` 与控制台表格：

| 字段 | 含义 |
|---|---|
| `summary.inputs_match` | 重新上传的每张输入的 SHA-256 都等于抓取里记下的值。假 = 抓取目录损坏或被改过 |
| `summary.outputs_bit_exact` | 每张输出都和录下来的逐字节相同。**同一个运行库 + 同一块 GPU 上，这一项必须为真** |
| `summary.worst_psnr_db` | 不是逐位一致时，所有图里最差的 PSNR（按格式解码后按分量算，UNORM 峰值 1.0，浮点用参考图的最大绝对值） |
| `summary.first_is_new_feature` | 第一个被重放的 Evaluate 是不是"刚新建的特性的第一帧"。**只有它为真时生成帧才可能逐位一致**。新抓取直接来自 `manifest.capture.start_reason`，老抓取由 `creates[].evaluates_seen + 1 == params.evaluate_seen` 推出来 |
| `summary.first_is_reset_frame` | 第一个被重放的 Evaluate 是不是 `DLSSG.Reset=1`。保留给老报告用；它为真**不代表**能逐位一致 |
| `summary.capture_start_mode` / `capture_start_reason` | 这份抓取录制时 `CaptureStartOnReset` 的取值（0/1/2），以及真正触发起点的规则（`new_feature` / `reset` / `any_frame`；`pending` = 一直没等到起点，配合 `capture.start_timeout` 看）。`capture_start_on_reset` 是同一件事的布尔版，留给老读取方 |
| `parameters.mismatches` | 被记录的 (名字, 槽位, 值) 里没能在重放进程中原样读回的那些。**必须是空的** |
| `parameters.skipped` | 无法复现的参数：指向模块内部的函数指针（`DLSSG.EstimateVRAMCallback` 之类）和读不出宽度的不透明值 |
| `creation.status` | 重放侧 `CreateFeature` 的返回值 |
| `compare_with.planes[]` | 与另一次重放逐图对比的结果 |

差异的含义：

- **逐位一致**：同一运行库 + 同一 GPU 上，抓取、重放、参数复现三者都正确。
- **同一运行库、不同 GPU**：Ampere/Ada/Blackwell 的 Tensor Core 累加不同，本来就不会逐位一致，看 PSNR。
- **不同运行库**（310.1 抓取 → 310.9 重放）：实测每次 Evaluate 都成功，生成帧 50.5–94.3 dB（index 1 最差），
  `OutputReal` 逐位一致。这是"两个运行库对同一输入的差"，不是错误。

### 跨 GPU、同一份输入的逐图比较：`scripts/perf/capture_compare.py`

`sm86_replay` 只给数字（PSNR / 最大差 / 不同像素数）。要回答"差异在**哪里**、是不是沿着人物轮廓"，用
`capture_compare.py` 把任意几个**同输入**来源放在一起：参考是一份抓取目录，被比较的是同一批 Evaluate 的其它来源
（`sm86_replay` 的 `out/` 目录，或同一份输入的另一次抓取）：

```powershell
$py = "python"   # 带 numpy 的 Python 3.10+
# 3070 上录的抓取（我们的路线）vs 同一份输入在 5070 上分别经原厂内核 / 我们的内核重放
& $py scripts\perf\capture_compare.py --out <工作目录>\cmp_wukong --ref rec3070=<3070 上录的抓取> `
      --cmp native5070=<5070 上的重放>\replay-native\out --cmp ours5070=<5070 上的重放>\replay-proxy\out `
      --evaluates 4-45 --crops 3
# 只渲染一份抓取（没有可比的同输入来源时，例如 5070 上自己录的原厂抓取）
& $py scripts\perf\capture_compare.py --out <工作目录>\view_5070 --ref native5070=<5070 上录的原厂抓取>
```

每个 Evaluate 的每张输出（`output` = 生成帧、`real` = 真实帧）产出：所有来源用**同一个曝光**（取自参考图：HDR10 PQ
按 99.5 分位亮度定纸白，FP16 同理）色调映射后的缩略图、`|参考 − 来源|` 的放大热图（默认 ×16，缩略时按块取最大值，
一像素宽的毛边不会被缩没）、以及差异最强的 N 个区域的放大裁剪条（参考 | 各来源 | 各差异热图 | 深度边缘带），加
`index.html` 与 `report.json`。数字：PSNR（只算 RGB，`sm86_replay` 连 alpha 一起算所以高约 1.25 dB）、最大/平均差、不同
像素数，以及有深度平面时的**边缘带占比**——把 3×3 中值滤波后的深度里相邻像素相对跳变超过阈值的位置膨胀成一条带，
报告差异总量落在带内的份额与"带内平均差 / 带外平均差"。差异集中在轮廓上时后者远大于 1；历史差异那种弥散的噪声
（第 4 节的 64.9 dB 抓取实测约 0.6）则不会。只有**同一份输入**的来源才能逐像素比；另一台机器上录的抓取输入不同，
单独渲染后并排看裁剪即可。`--evaluates` 选序号（`4-45`）：按键起录的抓取（`start_reason=key`）第一个真实帧组的重放
带着"从空历史起步"的瞬态，比较时跳过前一组。

## 4. 实例：悟空

1. 按 `INSTALL.md` 把 `version.dll`、`dlssg_sm86.ini` 与 `dlssg_sm86\` 放到 `b1\Binaries\Win64\`（渲染 EXE 旁边）。
2. INI 里 `[Logging] Level=3`，`[Debug]` 按上面加 `Capture=12`、`CaptureDirectory=<工作目录>\captures\wukong_sm86`
   （1080p HDR 约 1.2 GB，4K 约 3.6 GB）、**`CaptureStartOnReset=2`**、`CaptureSkip=0`。
   其余保持你平时在玩的配置——抓取要记录的就是那套配置。
3. **进到要录的画面（游戏里，不是主菜单），然后在游戏设置里把帧生成关掉再打开。** 这一下会重建 DLSS-G 特性，
   抓取就在新特性的第一次 Evaluate 上起录，这是唯一能让重放逐位一致的起点（`CaptureStartOnReset=2` 就是在等它，
   所以不用掐时间：切完开关它立刻开始，日志里 `capture_start_armed.reason` = `first evaluate of a newly created
   feature`）。**不要指望 `DLSSG.Reset`**：`CaptureStartOnReset=1` 在长跑的特性上多半先撞到一个 `Reset` 帧，那样录出来
   的抓取重放只有 64.9–73.3 dB（见第 1 节的表）。主菜单虽然也在跑 DLSS-G（实测约 67 次 Evaluate/秒），但录的就是
   主菜单的画面，想看某个场景就到那个场景里去切开关。注意最后一张写完时会有一次 25–120 ms 的卡顿，这是收尾。
4. 退出游戏，检查 `<工作目录>\captures\wukong_sm86\manifest.json` 的 `complete=true`、`dropped=0`，以及
   `dlssg_sm86\logs\dlssg_sm86.log` 里的 `capture_started` / `capture_slot` / `capture_done`。
5. 把整个目录拷到开发机，`replay_check.py --capture ... --modes proxy` 重放；要和原厂对比就在 5070 上用
   `KernelImage=Original` 的 INI 再录一份，然后 `--compare-with` 比两次重放。

### 悟空实测（2026-09-14，RTX 3070，4K 输出 / 1080p 渲染）：**逐位一致**

两个构建各录 12 次（`Capture=12 CaptureSkip=0`，主菜单，出厂路由 `ForceSM86Route=0` + `KernelImage=Auto` → cubin
+ `OptimizedKernels=0`），`complete=true`、`written=12`、`dropped=0`，**1858.9 MiB/份**，
`CaptureStartOnReset=1` 如期从"特性刚创建完"那一帧起录（`first_is_new_feature=true`）。
**两份抓取各自经自己的构建重放：12/12 次 Evaluate 全部 `0x1`，每张输出逐位一致，参数 0 mismatch。**

### 同一天的反例：从 `DLSSG.Reset` 帧起录的游戏内抓取（310.9.1，3070，4K，`Capture=30 CaptureSkip=12000`）

`CaptureStartOnReset=1` 等了 1092 次 Evaluate 才撞到一个 `DLSSG.Reset` 帧起录，那时特性已经跑了 **3169 次**
Evaluate（`creates[1].evaluates_seen=9924`，起录的 `evaluate_seen=13093`）。经同一个构建重放：30/30 次 Evaluate
`0x1`、输入全部 SHA 吻合、`OutputReal` 与 buffer 全部逐位一致，但**每张 `OutputInterpolated` 只有 64.9–73.3 dB**
（前两个真实帧即 Evaluate 1–6 是 pass-through，本来就逐位一致）。管线本身是确定的：同一份抓取重放两遍 70/70 张
逐位相同，`OptimizedKernels=0`、`ImagePatches=0` 的重放也和默认重放逐位一致。**结论：`Reset` 不是逐位一致的起点，
逐位一致必须靠"重建特性"（`CaptureStartOnReset=2` + 游戏里的帧生成开关）。**

这份抓取还暴露了一个抓取/重放侧的 bug（已修）：`DLSSG.CameraPosY=400061.78125` 被 `+0x78` 指针 getter 读成截断后的
`0x61abd`，那个地址在游戏进程里恰好可读，于是被分类成 64 字节 `buffer`，重放就把一个**真的堆指针**写进了
`DLSSG.CameraPosY`（运行库读出 3.28e12，每次 Evaluate 4 项、共 120 项参数读不回来）。现在抓取侧对"同名还答过数值
getter"的指针回答一律记成 `opaque` + `reproducible:false`（`capture.h` 的 `demoteNumericPointerAliases`，
`capture_options` 测试覆盖），重放侧 `buffer` 也不再压过数值回答——五个 4×4 矩阵（`CameraViewToClip`、
`ClipToCameraView`、`ClipToLensClip`、`ClipToPrevClip`、`PrevClipToClip`）只答指针 getter，照旧走"没有数值回答才用
裸指针"那条回退。修好之后 `parameter_mismatches` 从 120 变成 0，**图像判定一个字节都没变**（最差 PSNR 仍是
64.87 dB），这也再次说明那 64.9 dB 只来自历史。

游戏交出的资源（`i1` 9 个平面，`i2`/`i3` 8 个——`OutputReal` 只在每组第一帧出现；那个 buffer 前后各算一个平面）：

| 参数 | 格式 | 尺寸 | 每次 Evaluate |
|---|---|---|---|
| `Backbuffer` / `HUDLess` / `OutputInterpolated` / `OutputReal` | `R10G10B10A2_UNORM`（24，HDR10） | 3840×2160 | 31.6 MiB 每张 |
| `UI` | `B8G8R8A8_UNORM_SRGB`（90，footprint 按 87 拷） | 3840×2160 | 31.6 MiB |
| `MVecs` | `R16G16_FLOAT`（34） | 1920×1080 | 7.9 MiB |
| `Depth` | **`R32G8X24_TYPELESS`（19）= 两个平面**：plane 0 `R32` 深度 7680 B/行、plane 1 1 字节模板 1920 B/行 | 1920×1080 | 9.89 MiB |
| `OutputDisableInterpolation` | **buffer**（`dimension=1`，UAV） | 16 B | 16 B ×2（Evaluate 前后各一次） |

`ColorBuffersHDR=1` 但是 HDR10 而非 FP16，所以每次 141–174 MB 而不是 300 MB。
`MultiFrameCount=MultiFrameCountMax=3`（4X）——即使 310.9 构建把上限报成 5，游戏也只要 3，
`GameUserSettings.ini` 的 `InsertFrame=4` 不等于 5X。

**这份抓取最初重放不了**：`DLSSG.Depth` 的 `format=19` 是 `R32G8X24_TYPELESS`（typeless 深度+模板，**不是**
`D24_UNORM_S8_UINT`——那是 45），命中当时"多平面格式直接跳过"那一条，于是重放把 `DLSSG.Depth` 置空，
`EvaluateFeature` 拒绝（310.1 `0xbad00005`、310.9.1 `0xbad0000a`，输出一个字节都没被写过，PSNR 6.02 dB）。
现在两种资源都抓了（多平面纹理按 `planes*mips*arraySize` 走 footprint，buffer 用 `CopyBufferRegion`），
重放侧保留原格式与 `ALLOW_DEPTH_STENCIL`、逐平面上传，于是上面的逐位一致成立。

交叉重放（同一份抓取喂给另一个运行库，PSNR 表）——两个方向的数字完全一样，说明差异只来自运行库版本：

| 被重放的 Evaluate | `OutputInterpolated` | `OutputReal` | `OutputDisableInterpolation` |
|---|---|---|---|
| 1–6（前两个真实帧） | **逐位一致** | 逐位一致 | 逐位一致 |
| 7（i1） | 97.6 dB，最大差 0.0020，3295 / 8.3 M 像素 | 逐位一致 | 逐位一致 |
| 8（i2） | 98.0 dB，0.0010，2958 px | — | 逐位一致 |
| 9（i3） | 95.5 dB，0.0049，2913 px | — | 逐位一致 |
| 10–12（第四个真实帧） | 117.8–120.9 dB，0.0010，12–35 px | 逐位一致 | 逐位一致 |

这四次重放里还能复现的是经 310.9 的两次（310.1 运行库已退役，`--runtime-model` 接受 310.9.16（默认）或 310.9）：

```powershell
$py = "python"   # 带 numpy 的 Python 3.10+
& $py scripts\perf\replay_check.py --out <工作目录>\rp91b --capture <310.9 构建录的抓取> --runtime-model 310.9 --modes proxy --multi 5 --force 0 --optimized 0 --kernel-image Auto
# 交叉方向 310.1 抓取 → 310.9：把 --capture 换成 310.1 构建录的那份
```

### `sm86_replay --selftest`：不需要游戏也能验证资源路径

新增的自检把已知字节经 `ensureResource` / `upload` / `stage` / `pack`（重放用的同一套函数）跑一遍，断言**重放需要的那条
性质**：把"抓到的字节"再上传一次，读回来必须逐字节相同。覆盖 `R32G8X24_TYPELESS`（悟空的深度）、
`D24_UNORM_S8_UINT` 和 16 字节 UAV buffer。它也是这台机器上量到下面这些事实的地方：

- `R32G8X24_TYPELESS`：两个平面，plane 0 footprint 格式 39（4 B/px）、plane 1 格式 60（1 B/px），
  两个平面的字节都完整往返（640×384 上 1228800/1228800）。
- `D24_UNORM_S8_UINT`：同样两个平面，但 plane 0 每 4 字节里有 1 字节是格式不存储的填充（983040 里 245760 读回 0），
  所以判据必须是"再上传能复现"而不是逐字节等于写进去的值。
- 16 字节 UAV buffer：完整往返。

---

## 5. 已知限制与风险

| 项 | 说明 |
|---|---|
| 多线程 Evaluate | 有序读日志（`reads`）挂在 thread_local 窗口上，只记录**调用 Evaluate 那个线程**的读取；运行库若在别的线程读参数会漏记（`probe` 不受影响，重放也不受影响）。抓取槽位本身是加锁的，多线程调用 Evaluate 只影响日志完整性 |
| 资源状态 | 抓取按 NGX D3D12 约定假设输入在 `NON_PIXEL_SHADER_RESOURCE`、输出在 `UNORDERED_ACCESS`（`marker.cpp` 一直依赖后者）。游戏若交出别的状态，那次 barrier 的 `StateBefore` 就是错的：开了 D3D12 调试层会报错，不开则像素可能不对。每个平面的 `assumed_state` 都记在 json 里 |
| typeless / 深度格式 | 单平面 typeless 纹理不能直接当"纹理 → 缓冲"拷贝的源（placed footprint 不允许 typeless），所以先 `CopyResource` 到同一拷贝组的有类型兄弟格式再读回，`via_intermediate=true` 标记这种平面。**深度+模板的多平面格式（悟空的 `R32G8X24_TYPELESS`、`D24_UNORM_S8_UINT` 等）现已支持**：平面数由 `CheckFeatureSupport(FORMAT_INFO)` 得到，子资源范围变成 `planes*mips*arraySize`，`GetCopyableFootprints` 逐平面给出自己的拷贝格式，两个平面都录进同一个 `.bin`（`subresources[].plane` / `offset_in_file` 指明边界）。重放保留原格式与 `ALLOW_DEPTH_STENCIL`（绝不加 UAV，那个组合非法）并逐平面上传。注意 `D24_UNORM_S8_UINT` 的 plane 0 每像素有 1 字节格式不存储的填充，读回是 0——所以判据是"再上传能复现"，不是"等于游戏内存里的字节" |
| buffer 参数 | **现已支持**：`dimension=1` 的资源（悟空的 `DLSSG.OutputDisableInterpolation` 是 16 字节 UAV buffer）用 `CopyBufferRegion` 整块拷贝，小于 16 MiB 时在 Evaluate **前后各录一次**（`inputs/` 与 `outputs/` 各一份），所以也能看到运行库往里写了什么。NGX 对 buffer 没有状态约定，所以状态按资源自己的 flag 判断：带 UAV 的按 `UNORDERED_ACCESS`，否则留在 `COMMON` 不加 barrier |
| 运行库内部历史 | 不在抓取里，而且**只有新建特性的第一帧**历史是空的（`DLSSG.Reset` 不算，实测 64.9–73.3 dB）。`CaptureStartOnReset=2` 把它变成非问题；用 `1` 撞到 `Reset` 帧、用 `0`、或者用 `--start` 跳过起点，都会看到生成图不同（真实帧仍逐位一致） |
| MSAA / 子采样视频格式（NV12 等） | 跳过并记录原因（DLSS-G 不会交出这类资源；子采样格式的两个平面尺寸不同，抓取与重放都没有建模） |
| 不可复现的参数 | 指向模块的指针（回调）和 `+0x50` 槽位的不透明值不会被重放设置，列在 `parameters.skipped` 里。实测运行库读的回调（`ResourceAllocCallback` / `ResourceReleaseCallback`）在游戏里没有设置过，重放也不需要 |
| 只有 `sm86_replay` 的进程能重放 | 抓取里存的是指针身份和像素，不是 D3D12 命令；重放重建的是**语义**，不是原进程的地址空间 |

---

## 6. 日志事件

| 事件 | 含义 |
|---|---|
| loader：`capture_requested` / `capture_unsupported` | INI 要求抓取，后端接受了 / 后端没有 `DlssgMod_ConfigureCapture` 导出 |
| `capture_waiting_for_reset` / `capture_start_armed` / `capture_start_timeout` | `CaptureStartOnReset=1`/`2` 的三种结局：还在等（第一次以及之后每 600 次记一条，含 `skipped_waiting` / `reset_known` / `waited_ms` / `start_mode`）、找到起点开始录（含 `reason`：`first evaluate of a newly created feature` 或 `DLSSG.Reset is set`，以及 `bit_exact_replay`——只有前者为真，这条**每次都记**，不再只在等过之后才记）、等满 3 分钟放弃（什么都不录，`manifest.json` 里 `capture.start_timeout=true`） |
| `capture_prewarm` / `capture_finishing` | `CaptureNoStall=1`：学到的平面尺寸（写盘线程据此提前建回读缓冲）/ 最后一次 Evaluate 已提交、文件在后台写（含还没落盘的字节数），之后才有 `capture_done` |
| `capture_group_skipped` | `CaptureNoStall=1` 时内存预算用完（或环满）、整组跳过（第一次及之后每 50 次，含 `needed` / `free_slots` / `outstanding_bytes` / `budget_bytes` / 累计 `skipped_groups`）。这是设计行为，不是丢帧；`capture_done` 与 manifest 给出 `taken_groups` / `skipped_groups` / `skipped_groups_memory` |
| `capture_waiting_for_key` / `capture_start_key` | `CaptureStartKey` 的两个阶段：还在等键（第一次以及之后每 600 次，含 `key` 与已跳过的次数）、键被按下（含 `evaluate`、`next` = 立刻开始录 / 从此刻起等 `CaptureStartOnReset` 的起点）。`CaptureStartOnReset=0` 时紧跟一条 `capture_start_armed{reason:"start key pressed"}`，`manifest.capture.start_reason=key` |
| `capture_parameter_hooks` | 参数存储 getter 钩子的安装结果，含 8 个槽位的目标地址与共享分组。装不上时 `probe` 照常，只是没有 `reads` |
| `capture_create_hook` | 抓取把自己登记成 NGX 核心 `NVSDK_NGX_D3D12_CreateFeature` 的观察者（`registered=true`、`hook_owner="fg_gate"`）。**trampoline 本身归 `src/backend/ngx/fg_gate.cpp`**（它始终安装），核心还没加载时也由它监视 `LoadLibrary` 补装，对应记录是 `fg_gate_hooks` / `fg_gate_hooks_deferred`；`installed` 就是登记那一刻钩子是否已经装好。**不能钩运行库自己的同名导出**：它把调用方的返回地址当参数往下传（`mov rdx,[rsp+0x2d8]`），有 trampoline 时特性创建会失败（实测 `0xbad00002`） |
| `capture_execute_hook` | `ID3D12CommandQueue::ExecuteCommandLists`（槽位 10，在活对象上用 `GetDesc` 验证过）钩子，用来在提交后打我们自己的 fence |
| `capture_started` | 第一次真正录制时的配置摘要 |
| `capture_slot` | 每次录完并落盘的 Evaluate：目录、平面数、字节数、状态 |
| `capture_slot_dropped` | 丢了一次：环满（等待超时）或那条命令列表一直没被提交（10 s 超时）。错误级 |
| `capture_plane_skipped` | 某个资源没抓（MSAA、子采样视频格式、非 Texture2D/非 buffer、超出内存上限）。错误级 |
| `capture_done` | 收尾完成：录了几次、写了几次、丢了几次、字节数、`drain_ms` |
| `evaluate` 记录里的 `capture` | 运行中的计数器（seen / recorded / written / dropped / 三个钩子是否装上） |
