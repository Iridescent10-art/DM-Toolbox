# 任务目标：实现 DLSS 5 神经重构注入器与 A/B/C 三种多帧生成模式的完全兼容、面板内统一调参、自动化实机验证与自动封包

## 1. 核心架构与痛点背景
当前项目包含“多帧生成预设与游戏内外双向同步配置”（模式 A/B/C）与“DLSS 5 神经重构与画质注入器（基于 ReShade/RHI Addon `dlss5-nr.addon64` / `RenoDX.DLSS5`）”。
目前在目标游戏（如 `D:\game\yysls\yysls_medium\Engine\Binaries\Win64r\yysls.exe`）中存在以下严重冲突：
1. **模式 A（dashdogy / MFG-Unlocker 独立代理）**：与 DLSS 5 同时开启会导致 DLSS 5 插件无法启动，且 DLSS 超分模型被强制降级/篡改为 Preset D。
2. **模式 B（RenoDX 插件优化 `renodx-mfgunlock.addon64`）**：与 DLSS 5 同时注入导致游戏启动或进入场景时直接闪退（Access Violation）。
3. **模式 C（OptiScaler 跨卡转译 + XeFG）**：与 DLSS 5 同时启动会导致游戏内 DLSS 选项直接消失，且 XeSS 2.0 多帧生成（XeFG）不生效。
4. **控制割裂**：用户希望直接在“DLSS 5 神经重构与画质注入器”主界面内直接控制当前激活的多帧生成模式（A/B/C）及核心参数（插帧倍率、超分 Preset、Blackwell 优化开关、XeFG 通道等），实现真正的单面板统一管控与双向同步。

---

## 2. 阶段一：状态机清理与 DLL 槽位隔离（解决交叉污染）
任何模式切换或注入前，必须先执行 **`CleanGameDirectoryState(gameDir)`** 状态机清理，严禁残留上一个模式的代理 DLL：
- 建立白名单备份机制：首次操作前将原版 `nvngx_dlss.dll`、`nvngx_dlssg.dll`、`sl.interposer.dll`、`sl.dlss_g.dll` 备份至 `.dm_backup/`。
- 每次切换模式（A ↔ B ↔ C）时，先移除以下易产生冲突的代理槽位文件（若存在且非游戏原生文件）：
  - `dxgi.dll`、`ReShade64.dll`、`version.dll`、`winmm.dll`、`bink2w64Hooked.dll`
  - `renodx-mfgunlock.addon64`、`RTXMFG-Universal.json`、`OptiScaler.ini`、`OptiScaler.log`

---

## 3. 阶段二：A / B / C 三种模式与 DLSS 5 共存核心修复方案

### 3.1 修复模式 A（dashdogy 独立代理 + DLSS 5 共存）
- **根因 1（DLSS 5 不启动）**：之前在模式 C 下将 ReShade 部署为 `ReShade64.dll`（等待 OptiScaler 唤起），切回模式 A 后，模式 A 使用 `version.dll` / `winmm.dll` 注入，没有任何宿主去加载 `ReShade64.dll`；或者两者同时抢占了 `dxgi.dll`。
  - **修复动作**：当处于【模式 A + DLSS 5】时，强制将 ReShade 64 位运行底座部署为 **`dxgi.dll`**，加载 `dlss5-nr.addon64`；模式 A（dashdogy `MFGUnlocker`）强制使用 **`version.dll`**（或勾选防篡改时使用 `bink2w64.dll` -> `bink2w64Hooked.dll` 链式劫持），严禁模式 A 触碰 `dxgi.dll`。
- **根因 2（超分模型变成 Preset D）**：工具箱写入 `RTXMFG-Universal.json`（或相关 INI）时，将界面上的“Default（直通）”错误序列化为了枚举值 `4`（对应 `NVSDK_NGX_DLSS_Hint_Render_Preset_D`），或者将 DLSS-G 帧生成的 `Preset C/D` 字段写进了 Super Resolution 的 Preset 字段。
  - **修复动作**：
    1. 审查模式 A 的配置文件生成逻辑（`RTXMFG-Universal.json` / `config.ini`）。
    2. 当用户选择 `Default（直通·不覆盖游戏或驱动模型）` 时，必须写入 `OverrideDlssPreset: false` 且 `DlssPreset: 0`（`NVSDK_NGX_DLSS_Hint_Render_Preset_Default`），严禁覆写 NGX 超分 Hint。
    3. 当用户显式选择 `Preset J` 或 `Preset K`（DLSS 4 Transformer 模型）时，写入对应枚举值（`Preset J = 10`, `Preset K = 11`），并在 `ReShade.ini` 的 `[DLSS5]` 节同步锁定相同的超分 Preset，防止 dashdogy 劫持 `sl.common.dll` 时重置模型。

### 3.2 修复模式 B（RenoDX 插件优化 + DLSS 5 闪退修复）
- **根因（启动即闪退）**：模式 B 的 `renodx-mfgunlock.addon64` 与 DLSS 5 的 `dlss5-nr.addon64` 均为 ReShade Addon。两者同时在 `DLL_PROCESS_ATTACH` 或初始化阶段对 `sl.interposer.dll` / `sl.dlss_g.dll` 执行 Inline Hook（内存补丁）时发生读写冲突；此外，默认勾选全部 Blackwell 内核项与 `HDRUIRecomposition` 在部分未对齐版本的 `nvngx_dlssg.dll` 上会导致空指针异常。
  - **修复动作**：
    1. **单一宿主双 Addon 架构**：由唯一的 `dxgi.dll`（ReShade 64）同时加载 `dlss5-nr.addon64` 与 `renodx-mfgunlock.addon64`。
    2. **配置 Hook 避让**：在 `ReShade.ini` 中配置 `[RenoDX.DLSS5]`（或对应 DLSS 5 节）：
       ```ini
       [RenoDX.DLSS5]
       EnableHooks=2          ; 2 = 仅 Hook NGX 超分与神经重构管线，跳过对 sl.dlss_g 的重复 Inline Hook
       RuntimeSelectionMode=1 ; 锁定本地运行时，禁止驱动 OTA 动态替换导致偏移失效
       HDRCompatibilityMode=0 ; 默认 Native，避免与 RenoDX HDRUIRecomposition 产生双重 RHI 资源销毁闪退
       ```
    3. **Streamline 组件版本锁定**：部署模式 B 时，自动校验目标目录的 `sl.interposer.dll` 与 `sl.dlss_g.dll` 版本，确保使用与 `renodx-mfgunlock.addon64` 匹配的 Streamline 2.7+ 运行库套组。
    4. **安全初始化**：若勾选了 `HDRUIRecomposition=1`，自动在 `[RenoDX.MFG]` 中启用 `DeferredInit=1`（延迟 120 帧待交换链稳定后再激活光流倍率覆写）。

### 3.3 修复模式 C（OptiScaler 跨卡转译 + DLSS 5 导致 DLSS 消失与 XeFG 失效）
- **根因（DLSS 选项消失 & XeFG 不生效）**：
  1. OptiScaler 与 ReShade 抢占 `dxgi.dll`，或者 OptiScaler 通过 `ReShade64.dll` 提前触发了 D3D12 Device Hook，导致游戏调用 `NVSDK_NGX_D3D12_Init` 时签名校验或接口查询失败，游戏判定不支持 DLSS 从而隐藏菜单选项。
  2. DLSS 选项一旦消失，游戏不再输出 Motion Vectors（运动矢量）与 Depth（深度缓冲）到 Streamline 通道，导致下游的 `Intel XeFG` 无输入源而彻底失效。
  - **修复动作**：
    1. **严格确定链式加载顺序**：
       - 将 OptiScaler 核心文件部署为 **`dxgi.dll`**。
       - 将 ReShade 宿主重命名部署为 **`ReShade64.dll`**，并确保 `dlss5-nr.addon64` 位于同目录。
    2. **重写 `OptiScaler.ini` 关键共存配置**：
       ```ini
       [Menu]
       OverlayMenu=true
       ShortcutKey=45 ; Insert 键 (避免与 DLSS 5 / ReShade Home 键冲突)
       Scale=2.0

       [Spoofing]
       Dxgi=false     ; N卡环境下关闭 DXGI 显卡欺骗，防止 NGX 硬件校验失败导致 DLSS 消失
       StreamlineSpoofing=true

       [Upscalers]
       Dx12Upscaler=dlss ; 强制使用原生 DLSS 管线直通，使游戏正常显示 DLSS 选项并交由 DLSS 5 Addon 神经重构处理

       [DLSS]
       Enabled=true
       RenderPresetOverride=true
       RenderPresetForAll=11 ; Preset K (Transformer)

       [FrameGeneration]
       FGType=xefg           ; 启用 Intel XeFG (XeSS 2.0 FG)
       FGInput=dlssg         ; 接收游戏原生 DLSS-G via Streamline 通道
       InterpolationCount=3  ; 对应 UI 设定的 2X/3X/4X 倍率

       [LoadDlls]
       LoadReshade=true      ; 由 OptiScaler 在 D3D12 管线就绪后安全链式加载 ReShade64.dll
       ReshadePath=ReShade64.dll
       ```
    3. **依赖库完整性自检**：部署模式 C 时，强制检查并复制 `libxess.dll`、`libxess_fg.dll`、`dlssg_to_fsr3_amd_is_better.dll` 到游戏执行目录。

---

## 4. 阶段三：在 DLSS 5 注入器界面内内嵌多帧生成参数控制（UI & 双向绑定）
修改“DLSS 5 神经重构与画质注入器”主界面（图 4 所在视图组件）：
1. **新增【多帧生成联动控制台】内嵌折叠/直显面板**：
   - **模式切换器**：在 DLSS 5 界面直接提供 `模式 A: dashdogy 独立代理` / `模式 B: RenoDX 插件优化` / `模式 C: OptiScaler 跨卡转译` 单选切换。
   - **动态参数区（根据所选模式实时切换控件）**：
     - **公共参数**：强制插帧倍率下拉框（`2X` / `3X` / `4X` / `6X`）、DLSS 超分预设档位（`Default` / `Preset J` / `Preset K`）、游戏内呼出快捷键。
     - **模式 A 专属**：`启用 Bink2 链式劫持` 复选框。
     - **模式 B 专属**：`Blackwell 架构优化内核`、`ISR`、`VWB`、`BAM`、`HDR UI 防撕裂`、`DynamicMFG`、`TemporalFix` 快捷开关组。
     - **模式 C 专属**：`插帧输出引擎 (XeFG / FSR3 FG)`、`插帧输入通道 (DLSSG via Streamline)`、`AMD RCAS 锐化滑块`。
2. **统一读写引擎（`ConfigSyncService`）**：
   - 在 DLSS 5 界面修改任何多帧生成参数时，立即同步写入目标游戏的对应配置文件（模式 A 写 `RTXMFG-Universal.json`，模式 B 写 `ReShade.ini` 的 `[RenoDX.MFG]` 节，模式 C 写 `OptiScaler.ini`），并与原有的“多帧生成预设弹窗”（图 1/2/3）共享同一个 ViewModel / State Store，实现双向实时回显。

---

## 5. 阶段四：Agent 自动化闭环测试协议（未通过严禁封包）
代码修改完成后，Agent 必须编写并执行自动化测试脚本（如 `tests/verify_coexistence.py` 或 PowerShell 自动化测试套件），针对目标目录 `D:\game\yysls\yysls_medium\Engine\Binaries\Win64r` 依次执行以下 4 组测试：

### Step 1：静态配置与文件树断言测试（必测）
分别模拟在 UI 上选择模式 A、模式 B、模式 C 并点击“一键注入 DLSS 5 + 保存配置”，断言目标目录下文件状态：
- **模式 A 断言**：
  - 存在 `dxgi.dll`（ReShade）、`dlss5-nr.addon64`、`version.dll`（或 `bink2w64Hooked.dll`）；**不存在** `ReShade64.dll`、`OptiScaler.ini`、`renodx-mfgunlock.addon64`。
  - 读取 `RTXMFG-Universal.json`：校验 `Multiplier == 3`，且当 UI 选 Default 时超分 Preset 未被写为 `4`（Preset D）。
- **模式 B 断言**：
  - 存在 `dxgi.dll`（ReShade）、`dlss5-nr.addon64`、`renodx-mfgunlock.addon64`；**不存在** `version.dll`、`OptiScaler.ini`。
  - 读取 `ReShade.ini`：校验 `[RenoDX.DLSS5]` 存在 `EnableHooks=2`，且 `[RenoDX.MFG]` 中 `ForceMultiplier=3`。
- **模式 C 断言**：
  - 存在 `dxgi.dll`（OptiScaler）、`ReShade64.dll`（ReShade）、`dlss5-nr.addon64`、`libxess_fg.dll`；**不存在** `version.dll`、`renodx-mfgunlock.addon64`。
  - 读取 `OptiScaler.ini`：校验 `Dx12Upscaler=dlss`、`FGType=xefg`、`LoadReshade=true`、`Dxgi=false`。

### Step 2：实机进程冒烟与日志断言测试（Automated Smoke Test）
对 A、B、C 三种模式分别启动目标游戏进程（或通过命令行拉起 `yysls.exe` 持续运行 45 秒后安全退出），自动采集并解析生成日志：
1. **模式 A 实机日志校验**：
   - 检查 `ReShade.log`：必须包含 `Loaded addon "DLSS 5"`（或对应 Addon 名称）且无 `Error`；证明 DLSS 5 成功启动。
   - 检查 NGX / dashdogy 日志：确认当前激活的 Super Resolution Preset 为 `Default` 或 `Preset K (0x0B)`，严禁出现 `Preset D (0x04)`。
2. **模式 B 实机日志校验**：
   - 监控 `yysls.exe` 进程存活满 45 秒且退出码正常（无 `0xC0000005` Access Violation 崩溃转储 `.dmp` 生成）。
   - 检查 `ReShade.log`：`dlss5-nr.addon64` 与 `renodx-mfgunlock.addon64` 均输出初始化成功日志。
3. **模式 C 实机日志校验**：
   - 检查 `OptiScaler.log`：必须包含 `NVNGX initialized successfully`（证明游戏内 DLSS 选项正常显示）、`XeFG context created successfully` 且 `InterpolationCount = 3`（证明 XeSS 多帧生成生效）、`ReShade64.dll loaded`（证明 DLSS 5 链式加载成功）。

---

## 6. 阶段五：自动化构建与封包（Packaging）
**仅当阶段四的所有静态断言与实机日志检查 100% PASS 后**，Agent 方可执行封包流程：
1. 清理构建缓存，以 `Release`（`x64`）配置编译主程序。
2. 校验内置资源包（Assets/Payload）中是否已包含对齐版本的 `ReShade64.dll`、`dlss5-nr.addon64`、`renodx-mfgunlock.addon64`、`OptiScaler` 核心组件及 `libxess_fg.dll`。
3. 执行封包脚本（如 `npm run build` / `dotnet publish` / `pyinstaller` / `InnoSetup`），生成最终发行包，并输出完整的《A/B/C 三模式 + DLSS 5 兼容性测试报告》及构建产物 SHA256 校验值。