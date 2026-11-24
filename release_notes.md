# 🧠 DM-Toolbox (DM工具箱) v3.3.11 · DLSS 5 双底座升级（SF PLUS 4.2.0 / DLSS5 NR v15.1.0）+ 默认面部参数 50%

**DLSS 5 注入器的 A / B 两套底座全部替换为新版本；从本版起，一键注入默认写入的面部（角色 / 皮肤）
重构强度为 50%（旧版为 100%）。**

---

### 🚀 1. 模式 A 升级为 SF PLUS 4.2.0

- 新底座拓扑：`renodx-dlss.addon64`（原生底座）+ `ShortFusePlus-Panel.addon64`（独立控制面板）
  + `nvngx_dlssnr.dll`（0.9 MB 面板 / NGX 代理）+ `nvngx_dlssnr_real.dll`（真实运行库）。
- 注入时按所选显卡自动部署：RTX 20/30/40 使用 263.37 MB 真实模型，RTX 50 使用 254.08 MB 模型；
  代理从自身目录加载 `nvngx_dlssnr_real.dll`，面板与 ReShade 互斥逻辑由代理接管。
- 卸载 / 切换模式时会一并清理代理与真实运行库，不再残留 250 MB 大文件。

### ⚡ 2. 模式 B 升级为 DLSS5 NR v15.1.0 Dev（Lecram）

- 主插件 `dlss5-nr.addon64` 更新为 v15.1.0 Dev（18.0 MB），32 位插件同步更新为 `dlss5-nr.addon32`。
- 64 位宿主 `dlss5-nr-host`（`nr-host64.exe` + `ReShade64.dll`）同步替换为新版；
  模式 B 仍按原逻辑把真实运行库直接部署为 `nvngx_dlssnr.dll`，宿主与预设库 / 对比 / 多 pass 面板可直接使用。
- 模式切换互斥清理现在同时覆盖 `ShortFusePlus-Panel.addon64`，避免 A/B 双面板残留导致 ReShade 重复加载。

### 🎭 3. 默认注入的面部参数调整为 50%

- 所有注入写盘位置统一为 50%：`NRSkinStructure=0.500000`、`SkinStructure=50`、`Skin=50`、
  `DirectNeuralRenderingSkinStructureStrength=0.500000`（含 preset1/2/3、`[RenoDX DLSS]`、
  `[RenoDX.DLSS5]`、`[RenoDX]`、`[DLSSNR]`、`RenoDX/DLSS5/Presets/*.ini` 与 `ReShadePreset.ini`）。
- `NRPass2Skin=-1`（多 pass 时沿用 pass 1 的 50%）。
- 模式 A / 模式 B / 多帧生成共存同步（`ini_sync.py`）写入的面部参数也统一为 0.5。
- 进游戏按 `Home` 打开 NR 面板仍可随时手动微调（0 = 保护原脸，100 = NVIDIA 原始重构强度）。

### 🔍 4. 回归

- 分文件全量回归：**180 passed, 1 skipped**（每个测试文件独立进程执行，避免 PySide6 无头环境下多窗口共用进程的堆损坏）。
- 唯一失败项 `test_v126_app4_indicators::test_1_discovery_uses_real_games_only` 依赖本机 app2 游戏缓存；
  当前缓存为空（0 款游戏），与本次改动无关。
- DLSS 5 专项：模式 A / B 注入、切换、状态识别、卸载还原、面部 50% 默认值断言全部通过。
- 新增/更新断言：A 模式面板 + 代理 + 真实运行库三件套部署；B 模式 v15.1.0 宿主与 addon32；
  `NRSkinStructure=0.500000` / `SkinStructure=50` / `Skin=50`；卸载后 `nvngx_dlssnr_real.dll` 不残留。

---

# 🖥 DM-Toolbox (DM工具箱) v3.3.10 · 修复核显被一起改名

**旧版 apply 脚本会把所有非虚拟显卡的 `DriverDesc/DeviceDesc` 都改成目标显卡名，
导致核显也被一起改名；本版只改目标显卡，并在还原时按 INF 找回核显真实型号。**

---

### 🐞 1. 原因

`apply_config.ps1` 的 DirectX / Control\Video / Class 三处循环只排除了 Virtual/Remote，
没有按目标显卡厂商过滤，于是核显也被写成了目标显卡的名称。

### ✅ 2. 修复

- apply 脚本按目标显卡厂商计算过滤正则，只修改匹配厂商的注册表节点，核显不再被改名。

### 🩹 3. 还原时修复已损坏的核显名

- 新增 `gpu_restore_repair.py`：
  - 遍历显示类 `Class\{4d36e968…}\000X`；
  - 对核显从对应驱动 INF（`C:\Windows\INF\oemXX.inf`）解析原始型号；
  - 写回 `DriverDesc`、`HardwareInformation.ChipType/AdapterString`、Enum `DeviceDesc/FriendlyName`、DirectX `Description`；
- 实测可正确解析出核显原始型号；
- 「一键还原官方真实硬件」会自动执行该修复。

### 🔍 4. 回归

- 全量测试：**186 passed**。

---

# 🧩 DM-Toolbox (DM工具箱) v3.3.9 · 修复主板只显示型号、不显示厂商

**小黑盒主板一栏之前只显示 `MS-Terminator B850BKB WIFI`，缺少 `MAXSUN`；
原因是 helper 的 `board.name` 只写了产品名，界面读的是 name 字段。**

---

### 🐞 1. 原因

- helper 输出里：
  - `board.product` = `MS-Terminator B850BKB WIFI`
  - `board.vendor` = `MAXSUN`
  - `board.name` = 之前被写成产品名（缺厂商）
- 小黑盒展示的是 `board.name`，所以只剩型号。

### ✅ 2. 修复

- shim 现在写：
  - `board.name` = `MAXSUN MS-Terminator B850BKB WIFI`
  - `board.product` = `MS-Terminator B850BKB WIFI`
  - `board.vendor` = `MAXSUN`
  - `computer.model` / `computer.vendor` 同步为完整名称/厂商

实测 shim 输出：

```
board: {name: MAXSUN MS-Terminator B850BKB WIFI, vendor: MAXSUN, product: MS-Terminator B850BKB WIFI}
computer: {model: MAXSUN MS-Terminator B850BKB WIFI, vendor: MAXSUN}
```

### 🔍 3. 回归

- 全量测试：**186 passed**。

---

# 💾 DM-Toolbox (DM工具箱) v3.3.8 · 硬盘 PCIe 代际/通道可改 + MAXSUN 预设置顶

---

### 💾 1. 硬盘 PCIe 通道伪装

「硬盘存储」页新增：

- **总线**：Auto / NVMe / SATA
- **PCIe 代际**：Auto / 3.0 / 4.0 / 5.0
- **通道**：Auto / x4 / x2 / x1

helper shim 会覆盖 `pcieGen` / `pcieMaxGen` / `pcieLanes` / `busType`，
小黑盒评分里的「PCIe 3.0 x4」会跟随设置变化（例如改成 PCIe 4.0 x4）。

实测：

```
name=WD_BLACK/Samsung… busType=NVMe pcieGen=4 pcieMaxGen=4 pcieLanes=4
```

### 🧩 2. MAXSUN 主板始终置顶

- 主板下拉构建时强制把 `MAXSUN MS-Terminator B850BKB WIFI` 放在第一项；
- 即使旧配置文件里没有/顺序靠后，也会显示在最上面。

### 🔍 3. 回归

- 全量测试：**186 passed**。

---

# 📜 DM-Toolbox (DM工具箱) v3.3.7 · 「主板与内存」页可滚动，输入框不再遮挡文字

**该页内容较长，窗口较小时输入框被压缩、文字被圆角框裁切；现在整页可上下滚动，输入框有最小高度。**

---

### 🐞 1. 输入框遮挡文字

- 原因：页面内容超过可视高度时，纵向布局把输入框压到最小高度，
  `padding` 把文字挤出圆角边框；
- 修复：`QLineEdit` / `QComboBox` 增加 `min-height: 22px`，
  文字完整显示在框内。

### 📜 2. 页面可滚动

- 「主板与内存」页现在包在透明 `QScrollArea` 中：
  - 窗口高度不足时出现纵向滚动条；
  - 鼠标滚轮可向下滑动，查看「立即单独生效当前 内存 DDR5 定制」等底部按钮；
  - 其他页面保持原布局（首页/CPU/GPU/硬盘等不受影响）。

### 🧩 3. MAXSUN 主板

- `MAXSUN MS-Terminator B850BKB WIFI` 仍在默认预设第 1 项
  （模板 config、内置预设、用户配置均已写入）。

### 🔍 4. 回归

- 全量测试：**186 passed**。

---

# 🎨 DM-Toolbox (DM工具箱) v3.3.6 · 修复「主板与内存」页文字看不见 + 主板预设确认

**该页在部分主题/半透明卡片下文字与背景对比度过低，已显式锁定配色；MAXSUN 主板预设已进入默认列表。**

---

### 🐞 1. 文字看不见

- 原因：页面标签/输入框继承的调色板与半透明卡片背景不一致
  （深色卡片 + 浅色主题文字 / 浅色卡片 + 深色文字都会出现低对比）；
- 修复：`create_board_ram_view` 给整页锁定配色：
  - 深色主题：文字 `#F1F5F9`、输入框 `#1F2023`、卡片 `rgba(30,31,34,235)`
  - 浅色主题：文字 `#111827`、输入框 `#FFFFFF`、卡片 `rgba(255,255,255,240)`
- 下拉框弹出列表也同步配色，不会再出现白底白字/黑底黑字。

### 🧩 2. MAXSUN 主板预设

- `MAXSUN MS-Terminator B850BKB WIFI` 已写入：
  - `apps/app1_hardware/config.json` 默认预设（第 1 项）
  - `main_window.py` / `cpugpu_gui.py` 的内置预设
  - 当前用户配置 `%APPDATA%\ToolboxMaster\config\app1_hardware\config.json`

### 🔍 3. 回归

- 全量测试：**186 passed**。

---

# 🏷 DM-Toolbox (DM工具箱) v3.3.5 · 内存料号后缀可控（C32 后面的 VAM5UH64…）

**小黑盒内存行显示的 `C32 VAM5UH64C32AG-DVALWA` 是 SMBIOS 里的内存条料号（Part Number），
之前只改了品牌、没改料号，所以会露出真实条子的型号。**

---

### 🧠 1. 后缀是什么

- `127.66GB 6000MHz C32 Memory VAM5UH64C32AG-DVALWA`
  - `C32` = CAS 时序（SPD 读出）
  - `VAM5UH64C32AG-DVALWA` = 内存条料号（SMBIOS Part Number），你真实条子是 Asgard 的型号
- 别人的截图只显示 `Memory`，因为他们的条子没有可读料号，或料号为空。

### ✅ 2. 新增控制

- 「主板与内存」页新增：**内存料号 / 型号** 输入框
  - 留空 → 显示为 `Memory`（和大多数人一样）
  - 可填真实品牌料号，例如 `F5-6000J3038F16GX2-TZ5NR`
- helper shim 默认清空 `partNumber`（`memory.modules` 与 `smbiosMemory` 都清），
  只有填了料号才写入。

### 🔍 3. 实测

```
partNumber=''  vendor=Memory  type=DDR5
cpu cores 按配置输出
```

### 🔍 4. 回归

- 全量测试：**186 passed**。

---

# 🧩 DM-Toolbox (DM工具箱) v3.3.4 · 新增 MAXSUN 主板预设 / 还原修复 / 新版小黑盒路径识别

---

### ✨ 1. 新增主板预设

- 主板下拉新增：**MAXSUN MS-Terminator B850BKB WIFI**（排在列表首位）；
- 同时写入模板 `config.json` 与当前用户配置，重启软件即可选到。

### 🐞 2. 修复「还原后 CPU 名称没恢复」

- 「一键还原官方真实硬件」现在会同时：
  - 移除新版小黑盒的 IFEO 运行时代理（`HeyboxHelperShim`）；
  - 清空 `cpu_cores` / `cpu_threads` 伪装；
  - 把 CPU / GPU / 主板 / 硬盘型号恢复为备份的真实值。
- 之前只还原了注册表，helper 代理还在，所以小黑盒仍显示伪装 CPU 名。

### 🐞 3. 修复新版小黑盒目录识别

- 路径校验现在接受新版桌面版布局：
  - `小黑盒.exe`
  - `versions/` 目录
  - 旧版 `heyboxacc.exe` / `resources/`
- 选择 `C:\Program Files (x86)\Qingfeng\HeyboxDesktop` 不再报“未找到 heyboxacc.exe 或 resources”。

### 🔍 4. 回归

- 全量测试：**186 passed**。

---

# 🧮 DM-Toolbox (DM工具箱) v3.3.3 · 小黑盒 CPU 核心数 / 线程数也可修改

**之前只改了 CPU 型号，小黑盒仍显示真实核心数（6 核 / 12 线程）。本版支持自定义核心/线程，
并跟随 IFEO helper shim 输出。**

---

### ✨ 1. 新增

- 软件 1「处理器 CPU 深度定制」新增：
  - **核心数**（4/6/8/10/12/16/20/24/32/64，可手填）
  - **线程数**（8/12/16/20/24/32/40/48/64/128，可手填）
- 保存到配置 `cpu_cores` / `cpu_threads`；
- 留空时自动从 CPU 型号推断（`… 16-Core` → 16 核 / 32 线程）；
- helper shim 改写 `cpu.physicalCores` / `cpu.logicalCores`。

### 🧠 2. 实测

shim 对真实 helper 的 inventory 输出：

```
cpu: AMD Ryzen 9 9950X3D2 16-Core Processor | physical=16 logical=32
mem: Corsair 7200MHz
```

### 🔍 3. 回归

- 全量测试：**186 passed**。

---

# 🛡 DM-Toolbox (DM工具箱) v3.3.2 · 新版小黑盒改用运行时拦截（IFEO + helper shim）

**小黑盒桌面版 2.x 会校验扩展内容哈希，改 `hardware.mjs` 会被重新下载覆盖；
本版改为在运行时拦截硬件采集 helper，不再修改任何安装文件。**

---

### 🔍 1. 为什么换方案

- 2.x 启动时校验扩展包 `revision_id` / 文件封条；
- 被改过的 `hardware.mjs` 会被判定损坏，从 CDN 重新下载到新目录；
- 因此 v3.3.0 / v3.3.1 的文件 Hook 在新版上不持久。

### ✅ 2. 新方案：helper 运行时拦截

1. 工具箱把当前硬件扩展包复制到 `C:\Users\Public\DMBOX\heybox-helper\`；
2. 原 `hardware-windows-helper.exe` 改名为 `helper_real.exe`；
3. 放入编译好的 `HeyboxHelperShim.exe`（C#，11 KB）；
4. 给 `hardware-windows-helper.exe` 注册 IFEO Debugger：
   - 小黑盒调用 helper 时，Windows 先启动 shim；
   - shim 再运行 `helper_real.exe`（不改名防递归）；
   - 读取其 stdout JSON，按 ToolboxMaster 配置改写
     CPU / 显卡 / 内存 / 主板 / 硬盘 字段后再输出。

**不修改小黑盒任何文件，也不改 app.asar**，因此不会触发扩展哈希校验。

### 🧠 3. 字段映射

- `cpu.name` ← `cpu_model`
- `gpus[]` 第一个非虚拟显卡 ← `gpu_model` + `gpu_vram_gb`
- `memory.modules[*]` / `smbiosMemory[*]` ← 容量（GB→字节，按条数均分）、品牌、频率、类型
- `board.name/product/vendor`、`computer.model` ← 主板配置
- `disks[0].name/sizeBytes` ← `disk_model`

### ↩️ 4. 还原

软件 1「还原官方真实配置」会删除 IFEO 项与 `C:\Users\Public\DMBOX\heybox-helper\`，
小黑盒恢复读取真实硬件。

### 🔍 5. 回归

- 本地实测 shim：127.66 GB / G.Skill / 6000MHz / RTX 4080 SUPER / WD_BLACK SN850X /
  MS-Terminator B850BKB WIFI 均正确输出；
- 新增 3 项测试；全量测试：**186 passed**。

---

# 🧩 DM-Toolbox (DM工具箱) v3.3.1 · 小黑盒桌面版 Hook 覆盖“扩展缓存”副本

**v3.3.0 只改安装了 `versions/.../services/hardware.mjs`，但小黑盒实际从用户目录的扩展缓存加载，
缓存没有被打补丁，所以内存/主板/硬盘仍显示真实值。**

---

### 🐞 1. 原因

小黑盒桌面版启动时会把扩展复制到：

```
%APPDATA%\HeyboxDesktop\desktop\extension-artifacts\v1\packages\<hash>\services\hardware.mjs
```

实际加载的是这份缓存；安装目录里的 `hardware.mjs` 只是源文件。
而且不同版本的缓存导出名不同（`Ct/Pt`、`ua/fa` 等），旧注入逻辑写死了 `Ct/Pt`。

### ✅ 2. 修复

- `heybox_desktop_patch.py` 现在会同时处理：
  - 安装目录 `versions/*/resources/extensions/.../hardware.mjs`
  - `%APPDATA%\HeyboxDesktop\desktop\extension-artifacts\**\services\hardware.mjs`
- 注入逻辑改为**通用解析** `export{X as create,Y as dispose}`，不再假设变量名；
- 每个文件独立备份 `.tbx_bak`，可逐个还原；
- 软件 1 每次「应用配置」都会重新覆盖缓存副本，避免小黑盒更新后失效。

### 🔍 3. 回归

- 新增 1 项测试：不同导出名（`ua/fa`）也能正确注入；
- 全量测试：**183 passed**。

---

# 🖥 DM-Toolbox (DM工具箱) v3.3.0 · 支持新版小黑盒桌面版（HeyboxDesktop 2.x）硬件伪装

**小黑盒换成了 `C:\Program Files (x86)\Qingfeng\HeyboxDesktop`（2.x），
硬件采集不再走 `resources/app/index.js`，旧 Hook 失效（CPU/显卡能变，内存/主板/硬盘还是真实值）。**

---

### 🔍 1. 新版小黑盒的结构变化

| 项目 | 旧版 HeyboxAccelerator | 新版 HeyboxDesktop 2.x |
|---|---|---|
| 主程序 | `heyboxacc.exe` | `小黑盒.exe` + `versions/<ver>/` |
| 界面 | `resources/app/index.js` | `resources/app.asar` |
| 硬件采集 | `resources/app/index.js` + `acc_hardware_helper.node` | `resources/extensions/internal/ai-desktop.hardware-detect/services/hardware.mjs` |
| 底层 | 自研 WMI | LibreHardwareMonitor + `hardware-windows-helper.exe` |

### ✅ 2. 工具箱改动

- 新增 `apps/app1_hardware/heybox_desktop_patch.py`：
  - 自动探测 `HeyboxDesktop`（已知路径 + 注册表）；
  - 找到 `versions/*/resources/extensions/internal/ai-desktop.hardware-detect/services/hardware.mjs`；
  - 在文件尾部注入 ESM 包装层，拦截 `getInventory` / `getReportInfo`，
    覆盖 CPU、显卡、内存（容量/品牌/频率/型号）、主板、硬盘；
  - 注入前备份为 `hardware.mjs.tbx_bak`，可一键还原；
  - 幂等：已注入则跳过；版本变化找不到 export 时安全报错，不会写坏文件。
- 软件 1 的「应用配置 / 一键应用」会自动同时处理旧版与桌面版；
- 「还原官方真实配置」同时还原桌面版 `hardware.mjs`；
- 路径探测回退顺序加入 `HeyboxDesktop`。

### 🧠 3. 内存小数兼容

- 注入使用 `memory_size_gb` 精确值（如 127.66 GB），内部换算成整数字节；
- 配置与界面保留小数，不再触发 JSON 整数校验问题。

### 🔍 4. 回归

- 新增 3 项测试：注入替换 export / 幂等、还原备份、缺失 export 安全失败；
- 全量测试：**182 passed**。

---

# 🧩 DM-Toolbox (DM工具箱) v3.2.1 · 修复设置小数内存后小黑盒弹「JSON错误」

**v3.2.0 支持小数容量后，注入脚本把 `127.66 GB` 原样换算成 `130723.84 MB` 写进小黑盒硬件数据，
小黑盒要求整数 MB，于是硬件页弹出「JSON错误」。**

---

### 🐞 1. 原因

- 小黑盒的硬件 JSON 里 `memory.memory_size` 单位是 **MB 且必须为整数**；
- v3.2.0 的 `xiaoheihe_index.js` 直接写 `memory_size_gb * 1024`，小数容量得到小数 MB；
- 小黑盒前端/原生模块校验失败 → 「JSON错误」提示。

### ✅ 2. 修复

```js
const memMb = Math.round(Number(target.memory_size_gb) * 1024);
if (Number.isFinite(memMb) && memMb > 0) info.memory.memory_size = memMb;
```

- 内存容量：换算后**四舍五入为整数 MB** 再写入（127.66 GB → 130724 MB）；
- 显存容量同样处理（`gpu_vram_gb`）；
- 非法值 / NaN 直接跳过，不再写入；
- 配置文件和界面仍保留小数（127.66），显示不受影响。

### 🔁 3. 生效方式

安装 v3.2.1 后，在「电脑硬件配置 → 小黑盒」重新点一次「应用配置 / 拦截小黑盒」
（以管理员权限重写 `index.js`），完全退出小黑盒再打开即可。

### 🔍 4. 回归

- 全量测试：**179 passed**。

---

# 🧮 DM-Toolbox (DM工具箱) v3.2.0 · 内存容量支持小数（如 127.5 GB）

**软件 1「内存容量与工作频率」原来只能填整数（127 GB），本版支持小数容量。**

---

### ✨ 1. 改动

- 自定义内存容量输入：允许 `96` / `127.5` / `128` 这类小数；
- 下拉框文本解析：`127.5 GB` 会正确保存为 `127.5`，不再被截断成 `127`；
- 快捷同步 / 批量应用路径同样支持小数；
- `apply_config.ps1` 的容量类型由 `[int]` 改为 `[double]`，应用时不再丢失小数；
- 整数容量保存时仍写回整数（`128` 不会变成 `128.0`），兼容旧配置。

### 🔍 2. 使用

1. 打开「电脑硬件配置 → 主板与内存」；
2. 内存容量下拉选「✏️ 自定义内存容量...」；
3. 输入 `127.5`（或 `96`、`128`），点「立即单独生效当前 内存定制」；
4. 小黑盒重新检测后显示对应容量。

### 🔍 3. 回归

- 全量测试：**179 passed**（本版只改输入解析与应用脚本，不影响注入逻辑）。

---

# 🧩 DM-Toolbox (DM工具箱) v3.1.9 · 模式 D 修复：注入不再回落模式 A、同步配置新增模式 D 页

**上次 v3.1.8 只是把模式 D 加进了后端枚举，UI 里没有它的状态分支，而且选中游戏时会把
`renodx-mfgunlock.addon64` 当“遗留模式 B”删掉，导致模式 D 看起来总是回到模式 A。**

---

### 🐞 1. 修复内容

- **删除破坏性逻辑**：选中/刷新游戏时不再自动删除 `renodx-mfgunlock.addon64`
  （它现在是模式 D 的正式组件）；
- **状态识别**：补丁清单里 `active_backend = mavismmg` 时，界面显示
  「模式 D (MFGAdaUnlock-RenoDX / ReShade 插件)」并自动把下拉框切到模式 D；
- **后端说明**：下拉选到模式 D 时显示紫色说明（RHI 插件 / 3x-6x / 与 DLSS 5 共存 / Home 打开面板）；
- **预设配置弹窗新增「🧩 模式 D」页**：不再是只有 A/B/C 三个页签；
  从模式 D 打开时直接定位到 D 页，并说明参数在游戏内 Home → MFG Unlock 面板调整。

### ✅ 2. 验证

- GUI 级验证：下拉选中模式 D 后，`on_patch_click` 实际传入的后端为 `mavismmg`（模式 D），
  不再解析成模式 A；
- 模式 D 部署 + 与 DLSS 5 共存测试继续通过。

### 🔍 3. 回归

- 全量测试：**179 passed**。

---

# 🧩 DM-Toolbox (DM工具箱) v3.1.8 · 新增多帧生成模式 D（MFGAdaUnlock-RenoDX · RHI/ReShade 插件）

**新增模式 D：`renodx-mfgunlock.addon64`（mavismmg/MFGAdaUnlock-RenoDx 1.10.1），
走 ReShade/RHI 底座，RTX 40 解锁 3x/4x/6x，RTX 20/30 实验性，且可与 DLSS 5 共存。**

---

### ✨ 1. 模式 D 是什么

- 上游：https://github.com/mavismmg/MFGAdaUnlock-RenoDx
- 形态：ReShade Addon（`renodx-mfgunlock.addon64`），需要 ReShade（RHI）宿主；
- 与模式 A 的区别：不占用 `dxgi.dll` 做代理，而是和 DLSS 5 共用同一个 ReShade 底座，
  两个 addon 同时加载；
- 解锁能力：RTX 40 系 3x/4x/6x，Dynamic MFG；XeMFG / XeMFG-DLSS-G 后端；
- 内置版本：1.10.1（已打进安装包，无需联网下载）。

### 🔧 2. 工具箱改动

- 主界面新增「🧩 模式 D: MFGAdaUnlock-RenoDX (ReShade/RHI 插件 · RTX 40 解锁 3x/4x/6x · 可与 DLSS 5 共存)」；
- 模式 D 部署：ReShade 6.8 宿主（dxgi.dll）+ `renodx-mfgunlock.addon64` + ReShade.ini 配置；
- **与 DLSS 5 共存**：
  - 已装 DLSS 5 时直接复用其 ReShade `dxgi.dll`，不再重复部署；
  - 清理阶段不再误删 `renodx-mfgunlock.addon64`（模式 D 专属保护）；
  - DLSS 5 注入时也保留模式 D 插件，两个 addon 可同时加载；
- 状态识别、还原流程与模式 A/B/C 一致。

### 🛠 3. 燕云十六声 模式 A 闪退/不生效

- 日志确认是 `xemfgStandalone=1` 但游戏内未开 DLSS 帧生成导致（`gameFG=0` → `no_inputs`
  → 设备移除）；
- 已把燕云当前配置恢复为 `Standalone=0`（DLSS-G 内核）；
- 使用模式 A 时请在游戏内开启【DLSS 帧生成】，否则 MFG 没有输入、表现就是“不生效”；
  想用 XeSS 内核则必须按 v3.1.6 的提示开启游戏内帧生成。

### 🔍 4. 回归

- 新增 2 项测试：模式 D 部署（ReShade + addon + ini）、模式 D 注入后 DLSS 5 注入不删模式 D 插件；
- 全量测试：**179 passed**。

---

# 🩹 DM-Toolbox (DM工具箱) v3.1.7 · 修复小黑盒内存显示多出「DDR5」后缀

**软件 1（电脑硬件配置）修改配置后，小黑盒「我的电脑」内存一栏从 `128GB Asgard 6000MHz`
变成了 `128GB Asgard 6000MHz DDR5`；本版去掉强制写入的内存类型。**

---

### 🐞 1. 原因

小黑盒 Electron 拦截脚本 `xiaoheihe_index.js` 在 Memory Hook 中无条件写入了：

```js
info.memory.type_name = "DDR5";
...
m.type_name = "DDR5";
```

小黑盒原本对这套内存不显示类型后缀，被强制赋值后就多出了「DDR5」。

### ✅ 2. 修复

- `apps/app1_hardware/xiaoheihe_index.js`：不再无条件覆盖 `type_name`；
- 只有配置里显式提供 `memory_type` 时才写入（默认不写），保持原版显示
  `容量 + 品牌 + 频率`；
- 品牌、容量、频率的伪装逻辑保持不变。

### 🔁 3. 已装小黑盒的更新方式

- 安装 v3.1.7 后，在「电脑硬件配置」里重新点一次「应用配置 / 拦截小黑盒」，
  工具会把新版 `index.js` 写入小黑盒目录；
- 完全退出小黑盒再打开，重新检测硬件即可看到无后缀显示。

---

# ⚠️ DM-Toolbox (DM工具箱) v3.1.6 · XeSS / XeMFG 内核选择提示（修复燕云选 XeSS 闪退的误用）

**模式 A 帧生成内核选择 XeSS / XeMFG 时，在 NVIDIA 显卡上会弹出实验性提示，并说明必须游戏内开启 DLSS 帧生成。**

---

### 🐞 1. 现象

燕云十六声在「多帧生成预设」里把「帧生成内核」切到 **XeSS / XeMFG** 后启动闪退。

### 🔍 2. 日志分析

```
XESS {"stage":"vk_host_config","enabled":true,"standalone":true,"frames":3}
State: route=pending ready=0 routeFailure=15 gameFG=0 appliedFG=0
MFG_PROXY_UI XeMFG standalone chain attached
First-chance exception 0xC0000005 ... at yysls.exe+0x3E2BD81
XESS d3d12_present ... "generating":false,"why":"no_inputs" ... hresult=-2005270523 (0x887A0005 设备移除)
```

- XeMFG 独立插帧已接管 swapchain，但游戏内 **DLSS 帧生成未开启**（`gameFG=0`），没有输入帧；
- 随后 XeFG 在无输入状态下首次 present，游戏访问违例 / 设备移除并闪退；
- 运行库本身是正确的 Intel XeSS SDK 3.0.2（`libxess_fg.dll 1.3.1.78`、`libxell.dll 1.3.2.10`），不是版本问题。

### ✅ 3. 修复

- 在「保存配置并同步」时，如果帧生成内核选择 XeSS / XeMFG 且当前不是 AMD 显卡：
  - 弹出说明：NVIDIA 上为实验性；**必须游戏内开启 DLSS 帧生成**，关闭自带 FSR/XeSS 帧生成；
  - 「改用 DLSS-G」（默认）会直接把内核切回 DLSS-G，「仍要使用」才保留 XeSS；
- AMD 显卡（原本就默认 XeSS 多帧生成）不再弹此提示。

### 🔍 4. 回归

- 全量测试：**177 passed**（无行为变更，仅新增 UI 提示路径）。

---

# 🛡 DM-Toolbox (DM工具箱) v3.1.5 · 反作弊游戏拦截（可选择强制继续）

**注入多帧生成 / DLSS 5 前识别带反作弊的游戏，弹窗警告；默认取消，也可「强制继续」。**

---

### 🚨 1. 背景

上游 MFG Unlocker 文档 `docs/compatibility.md` 明确把以下游戏列在「Games with anti-cheat」：

Forza Horizon 6、Battlefield 6 / RedSec、GTA V Enhanced、Gears of War: E-Day、Zenless Zone Zero 等。

这些游戏注入代理 DLL 后会在启动画面被反作弊强制结束（无崩溃日志、无 WER 记录），
实机验证：Forza Horizon 6 连上游原版 `MFGUnlocker-v1.7.1.zip` 直接改名 `version.dll` 也照样闪退。

### ✅ 2. 新增拦截

- `common/anti_cheat.py`：按游戏名 / exe 名匹配名单，并浅层扫描 `EasyAntiCheat`、`BattlEye` 等反作弊模块；
- 多帧生成「立即应用」与 DLSS 5「一键注入」前都会检查：
  - 命中 → 弹窗「反作弊游戏警告」，说明可能启动闪退；
  - 默认按钮为「取消」；
  - 点「强制继续」才会真正注入；
- 未命中名单的游戏（如 yysls、Cyberpunk 2077、黑神话）行为完全不变。

### 🔍 3. 回归

- 新增 5 项测试：FH6 名称/exe 识别、其它反作弊游戏、普通游戏不误报、反作弊模块目录识别、警告文案；
- 全量测试：**177 passed**。

---

# 🛠 DM-Toolbox (DM工具箱) v3.1.4 · 修复还原后 Cyberpunk 2077 / 巫师 3 无法启动（libxell / libxess_fg 缺失）

**模式 A/C 清理时误删了游戏本体静态导入的 XeSS 运行库，导致还原后游戏报「找不到 libxell.dll / libxess_fg.dll」。**

---

### 🐞 1. 现象

Cyberpunk 2077 还原后双击启动：

```
Cyberpunk2077.exe - 系统错误
由于找不到 libxell.dll，无法继续执行代码。
由于找不到 libxess_fg.dll，无法继续执行代码。
```

巫师 3 使用相同引擎，同样会命中。

### 🔍 2. 根因

- Cyberpunk 2077 / 巫师 3 的 exe **静态导入**了 `libxess.dll`、`libxess_fg.dll`、`libxell.dll`（XeSS 运行库）；
- 模式 A 的「清理旧模式残留」与模式 C 的冲突清理，把这些文件当成 OptiScaler 残留直接删除；
- 其中 `libxess_fg.dll` 删除时没有备份，导致还原后也无法恢复，游戏加载器直接报错。

### ✅ 3. 修复

- 模式 A / 模式 C 清理前先读取游戏 exe 的静态导入列表
  （`get_game_statically_imported_dlls`，含 Cyberpunk/巫师 3 的签名保护），
  **命中游戏导入的 DLL 一律跳过删除**；
- 「一键还原」结束时调用 `auto_heal_game_dependencies`，自动补齐缺失的游戏依赖；
- 清理范围仍保留 OptiScaler 配置、fakenvapi、dlssg_sm86 等真正需要替换的文件。

### 🔍 4. 回归

- 新增 1 项测试：Cyberpunk 结构的目录注入模式 A 后 `libxess_fg/libxell/libxess` 必须保留，
  还原后仍然存在；
- 全量测试：**172 passed**。

---

# 🔵 DM-Toolbox (DM工具箱) v3.1.3 · DLSS 5 默认底座改为模式 B（DLSS5 NR v13.4）

**DLSS 5 一键注入的默认模式由模式 A 改为模式 B（Lecram DLSS5 NR v13.4）。**

---

### 🔄 1. 默认模式

- `DEFAULT_DLSS5_MODE = MODE_B`，面板默认选中「⚡ 模式 B (默认推荐)」；
- 副标题同步：`DLSS5 NR v13.4 扩展底座 (模式 B 默认) / ShortFuse 原生底座 (模式 A 可选) / GITC Uplift (模式 C)`；
- 未检测到注入、旧版插件、卸载后复位，全部回到模式 B；
- 注入时未取到模式值时也回退到模式 B。

### 🧹 2. 关联调整

- 模式 B 使用 `dlss5-nr.addon64` + `dlss5-nr-host\` 整套部署（保留 v13.4 现状）；
- 「一键卸载」后的复位同时把模式 B 版本下拉复位到 v13.4；
- 模式 A / C 仍可手动切换，行为不变。

### 🔍 3. 回归

- 更新双模式测试：默认索引 1、默认值 `MODE_B`、默认提示文案；
- 全量测试：**171 passed**（本机 Qt 偶发退出崩溃与用例无关，重跑/分组均可通过）。

---

# 🩺 DM-Toolbox (DM工具箱) v3.1.2 · 修复 Streamline 目录里的 NR 运行库被优先加载

**注入 DLSS 5 后 NR 不生效（0xBAD00001）的真正原因：游戏更新在 `Streamline\` 里放了一份 50 系专用的
`nvngx_dlssnr.dll`，RenoDX 优先加载它，RTX 20/30/40 创建 NR 特性时被拒绝。**

---

### 🔍 1. 故障现象

- `ReShade.log`：

```
[RenoDX DLSS] DLSS-NR direct: attached snippet ...\Streamline\nvngx_dlssnr.dll
[RenoDX DLSS] DLSS-NR direct: CreateFeatureInstance end: result=0xbad00001
[RenoDX DLSS] RenoDX DLSS NR device feature initialization failed
```

- 插件加载、NGX 初始化都正常，但 NR 创建 0 次成功（实测 1920 次失败），画面没有任何 NR 效果。

### 🧠 2. 根因

游戏更新后目录里同时存在两份同名运行库：

| 位置 | 大小 | 内容 |
|---|---|---|
| 游戏根目录 `nvngx_dlssnr.dll` | 263.37 MB | 20/30/40 系可用 |
| `Streamline\nvngx_dlssnr.dll` | 254.08 MB | **50 系专用**（游戏更新带入） |

版本号同为 310.9.16，但内核架构不同；RenoDX 优先从 `Streamline\` 加载，于是 4070 上返回
`0xBAD00001`（`NVSDK_NGX_Result_FAIL_FeatureNotSupported`）。

### ✅ 3. 修复

- 注入 DLSS 5（模式 A / B）时，扫描游戏内的 Streamline 目录
  （`Streamline`、`*/Streamline`、`Engine/Binaries/*/Streamline` 等），
  把其中的 `nvngx_dlssnr.dll` 替换成与显卡架构匹配的版本；
- 替换前备份为 `nvngx_dlssnr.dll.dlss5_bak`，并记录到 `.dlss5_manifest.json`；
- 「一键卸载」时自动从 `.dlss5_bak` 还原游戏原文件；
- 模式 C（GITC Uplift）使用自己的 `GITC-Uplift\` 运行库，不做此替换。

### 🔍 4. 回归

- 新增 1 项测试：注入替换 Streamline 运行库并备份、卸载后还原；
- 全量测试：**171 passed**。

---

# 🩹 DM-Toolbox (DM工具箱) v3.1.1 · 回退模式 A 插件到可用版本

**v3.1.0 附带的 ShortFuse 26092809 构建会导致 DLSS 5 注入后 NR 初始化失败、游戏卡死；本版回退到可用的 2026.1025 构建。**

---

### 🐞 1. 问题现象

- 注入 DLSS 5 后进入游戏，`ReShade.log` 出现：

```
[RenoDX DLSS] DLSS-NR direct: CreateFeatureInstance end: result=0xbad00001 handle=0x0
[RenoDX DLSS] RenoDX DLSS NR device feature initialization failed
```

- NR 初始化失败后游戏无响应（Windows 事件 1002 AppHang），Yysls 实测 15:32 / 15:33 / 15:38 / 15:39 连续挂起。

### 🔍 2. 根因

v3.1.0 内置的 `renodx-dlss-SF-CN-26092809.addon64` 文件版本是 **0.2026.0928.0119**（9 月 28 日构建），
比 v3.1.0 之前使用的 **0.2026.1025.0409**（10 月 25 日构建）更旧；旧构建与当前 NR 310.9.16 运行库
在 `CreateFeatureInstance` 阶段返回 `0xbad00001`，随后挂起游戏。

### ✅ 3. 修复

- 模式 A 资源回退为 `renodx-dlss.addon64` = **0.2026.1025.0409**（3.49 MB，
  SHA-256 `dd5ed7ba…d93bace`），注入文件名不变；
- 其余内容与 v3.1.0 相同（MFG 1.7.1、模式 B DLSS5 NR v13.4、模式 C 0.4.2、从进程添加游戏）。

---

# 🖥️ DM-Toolbox (DM工具箱) v3.1.0 · 手动添加游戏支持「从运行中的进程选择」

**游戏库新增任务管理器式的添加方式：直接从正在运行的程序里挑游戏，自动定位安装目录。**

---

### 🆕 1. 「从进程添加」按钮

- 位置：
  - 多帧生成 → 游戏库管理 → 顶部「🖥️ 从进程添加」；
  - DLSS 5 面板 → 目标游戏选择 → 「🖥️ 从进程添加」（在「手动添加游戏 (.exe)」右侧）；
- 两个面板共用同一套进程枚举与选择对话框（`common/process_scanner.py`、`common/process_picker_dialog.py`）；
- 打开后列出当前**正在运行、带可见窗口**的程序，显示进程名 / PID / 完整路径；
- 支持搜索框过滤（进程名或路径）、刷新、双击直接添加；
- 选中后自动识别游戏目录与可执行文件（复用现有的 Shipping / Streamline 深度识别），
  识别为 QUALIFIED 后直接写入游戏库并切回首页。

### 🧠 2. 进程候选过滤

- 只保留用户目录 / 游戏目录下的 `.exe`；
- 排除 `C:\Windows\*`、`Program Files\WindowsApps\*`；
- 排除系统与常用工具进程（steam / epic / wegame / explorer / python / 浏览器 / 聊天工具等）；
- 排除安装器、卸载器、更新器、崩溃报告（`unins*` / `setup*` / `*updater*` / `*crash*`）；
- 有可见窗口的进程排在前面，同名多开只保留一个。

### 🔍 3. 回归

- 新增 2 项测试（候选过滤规则、进程枚举返回结构）；
- 全量测试：**170 passed**。

---

# 🧬 DM-Toolbox (DM工具箱) v3.0.9 · 模式 A / 模式 B 底座更新

**模式 A 换成 ShortFuse 中文新版，模式 B 换成 DLSS5 NR v13.4（Lecram），旧版本全部移除。**

---

### 🅰️ 1. 模式 A：ShortFuse 中文新版（26092809）

- 资源文件名保持 `renodx-dlss.addon64`（注入到游戏里也是这个名字）；
- 二进制替换为 `renodx-dlss-SF-CN-26092809.addon64`（2.77 MB，
  SHA-256 `9dda03ab…fac449`）；
- 旧版（3.49 MB）不再随包，也不再备份。

### 🅱️ 2. 模式 B：DLSS5 NR v13.4.0（Lecram）

- 旧版 `Lecram-v12.addon64` 与 `renodx-dlss5-Lecram-v12.5.addon64` 全部移除；
- 新版为 `dlss5-nr.addon64`（13.51 MB）+ `dlss5-nr.addon32`（1.48 MB）
  + **64 位宿主目录 `dlss5-nr-host\`**（`nr-host64.exe` + `ReShade64.dll`）；
- 注入时按上游 INSTALL 要求整套复制：`dlss5-nr.addon64`、`dlss5-nr.addon32`、`dlss5-nr-host\`；
- 面板去掉 v12 / v12.5 版本下拉，模式 B 固定为 v13.4；
- 热键改为 **Home** 呼出 NR 面板（v13.4 的 ReShade 菜单是 Shift+Home），不再使用 F12；
- 卸载时一并清理 `dlss5-nr-host\`。

### 🧹 3. 兼容与清理

- 停止识别旧 Lecram 文件名作为主路径，但仍会在切换模式时清理 `Lecram*.addon64` 残留；
- 冲突清单加入 `dlss5-nr.addon64/addon32`，避免与 RenoDX 模式 A、GITC 模式 C 同时加载。

### 🔍 4. 回归

- 更新双模式测试：模式 B 断言改为 `dlss5-nr.addon64` + `dlss5-nr-host\nr-host64.exe`；
- 全量测试：**168 passed**。

---

# 🔥 DM-Toolbox (DM工具箱) v3.0.8 · 模式 C 升级 dlssg_for_sm86 0.4.2 + 只保留 MFG Unlocker 1.7.1

**模式 C（dlssg_for_sm86）升级到 0.4.2；内置组件只保留 MFG Unlocker 1.7.1。**

---

### ⬆️ 1. 模式 C 升级到 dlssg_for_sm86 0.4.2

- 内置版本 `0.4.0 → 0.4.2`（上游 2026-11-14 发布）；
- 0.4.2 带来的变化：
  - **XeSS-FG 在 RTX 50（Blackwell）上的性能修复**（独立编 `.bw` 内核镜像）；
  - **XeSS-FG 支持抖动运动矢量**（`DLSSG.MvecJittered=1`），3X / 4X 不再报 `unsupported_input`；
  - 4K 下 MV splat 换成本项目 CUDA 内核，每真实帧再快 3–5.6%；
  - 新增 `dlssg_sm86ini_Configurator.html`（单文件 INI 配置器）；
  - `[XeSSFG] UseHudless=Auto` 行为对齐 `0`（整幅画面插值，不再产生 `xefg_hudless_unused`）。
- 配置结构同步 0.4.2：
  - `[DLSSG] Preset` 只接受 **A / B / C**（`Auto` / `Default` 已删除，写旧值会导致 `configuration_invalid` 并关闭帧生成）；
  - `[DLSSG] Optimized` 出厂值改为 **1**（与官方逐位一致），仍可在 0/1/2/3 间选择；
  - `[SuperResolution] Mode` 改为 `Off / M-INT8 / L-INT8 / M-FP16 / L-FP16`；
  - 面板下拉同步为新取值，旧预设会自动迁移（Auto/Default→C，SR On→Off）。
- **可选 sr 超分内核按需部署**：0.4.2 的 `dlssg_sm86\sr\`（约 172 MB）只有在用户把「超分辨率托管模式」设为非 Off 时才复制进游戏目录，默认注入不占用这份空间。

### 🧹 2. 内置组件精简

- 删除 `embedded_components/dashdogy/v1.6.1` 与 `v1.7.0`，只保留 **v1.7.1**（7.05 MB）；
- 组件注册表同步只保留 `v1.7.1` 条目，安装包体积随之下降；
- 模式 C 旧版 `v0.4.0` 目录升级为 `v0.4.2`，代码里的兜底路径全部指向新版本。

### 🔍 3. 回归

- 全量测试：**172 passed**；
- 覆盖：模式 C 预设迁移、INI 前向/反向同步、DLSS 5 共存链路、组件注册表版本比较。

---

# 🚀 DM-Toolbox (DM工具箱) v3.0.7 · MFG Unlocker 升级 1.7.1（全显卡 + AMD 默认 XeSS）

**多帧生成模式 A 升级到 dashdogy MFG Unlocker 1.7.1：全显卡可用，默认注入方式改为模式 A，
AMD 显卡默认走 XeSS 多帧生成（XeMFG）。**

---

### ⬆️ 1. 模式 A 升级到 MFG Unlocker 1.7.1

- 内置 `MFGUnlocker.dll` 版本 `v1.7.0 → v1.7.1`（7.05 MB，SHA-256 已校验）；
- 1.7.1 起 **DLSS MFG 覆盖 RTX 50/40/30/20 全系**，并新增：
  - XeSS 多帧生成（XeMFG）在 NVIDIA / AMD / Intel 上独立运行；
  - XeMFG pacing（AMD 帧节奏与延迟优化）；
  - RTX 40/30 的 RTX Hair；
  - DX11 游戏的菜单与 DLSS 5 支持；
  - OptiScaler 内新增 MFG Unlocker 标签页、快捷键标签页。
- 组件注册表升级逻辑修正：embedded 版本比本地缓存新时，会自动更新 `latest_tag`
  （旧逻辑只在本地没有版本时才写入，导致新内置版本用不上）。

### 🎯 2. 默认注入方式改为模式 A

- 智能优选不再按显卡分流（原先 RTX 20/30→模式 C、RTX 40/50→模式 A、其他→模式 B）；
- 现在 **所有显卡默认模式 A**，模式 B / C 仍可手动选择；
- 界面文案同步：模式 A 标注为「全显卡」，推荐说明改为「全显卡默认模式 A，AMD 默认 XeSS」。

### 🔴 3. AMD 显卡默认使用 XeSS 多帧生成

- 检测到 AMD / Radeon 显卡时，自动把模式 A 预设的 `xemfg_standalone` 打开（XeMFG 插帧内核）；
- 对应配置：`RTXMFG-Universal.json → "xemfgStandalone": 1`、`mfg_unlocker.ini → [XeMFG] Standalone=1`。

### 🔍 4. 回归

- 新增 4 项测试（AMD 判定、全显卡默认模式 A、AMD 自动开 XeMFG、版本号比较）；
- 全量测试：**172 passed**。

---

# 🎯 DM-Toolbox (DM工具箱) v3.0.6 · 修复 UE5 游戏（黑神话：悟空）识别不到多帧生成

**v3.0.6 修好了「游戏明明支持帧生成，工具箱却显示不支持」的 UE5 结构识别问题。**

---

### 🐒 1. 黑神话：悟空 为什么之前显示不支持

两个识别盲区叠加：

1. **可执行文件选错**：游戏根目录只有 350 KB 的启动器 `b1.exe`，真正的游戏进程在
   `b1\Binaries\Win64\b1-Win64-Shipping.exe`。旧逻辑优先认根目录，把启动器当成了游戏本体，
   注入目标目录也落在游戏根目录。
2. **Streamline 目录太深**：`sl.interposer.dll` 与 `nvngx_dlssg.dll` 放在
   `Engine\Plugins\Runtime\Nvidia\Streamline\Binaries\ThirdParty\Win64\`，
   旧逻辑只查根目录与少数几个标准位置，直接判定为「无 Streamline 集成」（不支持）。

### ✅ 2. 修复内容

- 新增 **UE Shipping 可执行文件探测**：按固定模式（`*/Binaries/Win64/*.exe` 等）查找
  `*-Win64-Shipping.exe`，优先选择体积最大的那个作为游戏本体；
- 新增 **Streamline 递归探测**：在游戏目录（及其上一级）内按深度上限递归查找
  `sl.interposer.dll` / `nvngx_dlssg.dll`，覆盖 UE 引擎插件目录；
- 修复后黑神话识别为：
  - 本体 `b1-Win64-Shipping.exe`
  - 注入目录 `b1\Binaries\Win64`
  - Streamline `2.7.2.0` / DLSS-G `310.1.0.0`
  - 资格 **QUALIFIED（原生支持，可注入多帧生成）**

### 🔍 3. 回归

- 新增 2 项 UE 结构测试（Shipping + 深层 Streamline；普通游戏不受影响）；
- 全量测试：**167 passed / 1 skipped**。

---

# 🎨 DM-Toolbox (DM工具箱) v3.0.5 · 模式 C 界面细节修正

**v3.0.5 是 v3.0.4 的界面补丁，只修 DLSS 5 面板模式 C 的显示细节。**

---

### 🟣 1. 模式 C 提示条可读性

- 模式 C 的模式提示改成紫色高对比底条（浅紫底 + 深紫字），不再被壁纸透到看不清；
- 提示文案精简为一行：`模式 C：GITC Uplift 1.7.0 · 全 API 通用 · 自动部署 addon / helper / NR 运行库 / 着色器 · 进游戏按 Home → GITC Uplift → 勾选 Enable`；
- 修正上一版文案里 `GITC-Uplift\nvngx_dlssnr.dll` 的反斜杠被转义吃掉的问题；
- 提示标签尺寸策略改为随内容收缩，避免多行文本压到上方资产清单。

### ✅ 2. 回归

- 本机 Qt 恢复正常后复跑全量测试：**165 passed / 1 skipped**（含模式 A/B/C 下拉、模式 C 文案、GITC 部署与卸载用例）。

---

# 🧪 DM-Toolbox (DM工具箱) v3.0.4 · DLSS 5 新增模式 C（GITC Uplift）

**v3.0.4 为 DLSS 5 一键注入加入第三种底座：GITC Uplift 1.7.0。**

---

### 🆕 1. 模式 C · GITC Uplift 神经重构底座

- DLSS 5 面板底座模式新增第三项：`模式 C · GITC Uplift 神经重构底座 (全 API 通用)`；
- 一键注入自动部署：
  - `gitc-uplift.addon64`
  - `gitc-uplift.addon32`（32 位游戏）
  - `gitc-uplift-helper64.exe`（DX9 / 32 位游戏的 NR 辅助进程）
  - `GITC-Uplift\nvngx_dlssnr.dll`（按显卡自动选模型）
  - `Uplift.fx` / `UpliftMask.fx` 着色器
- 模式 C 下 **不会** 把 `nvngx_dlssnr.dll` 放到游戏根目录（50 系驱动会抢先加载，导致 Uplift 用不了）；
- 支持 DX9 / 10 / 11 / 12、Vulkan、OpenGL，32 位与 64 位游戏；
- 自带显存预算检查（Video memory check）与简体中文界面（进游戏按 Home → GITC Uplift 标签 → Enable）。

### 🔁 2. 与其他底座互斥

- 模式 C 与模式 A（RenoDX ShortFuse）、模式 B（Lecram）互斥，注入前自动清理旧底座；
- 卸载时一并清理 GITC 专属文件、`GITC-Uplift\` 目录、`*.addon32` 与已废弃的 `*.addon*.bak`。

### 🧭 3. 状态识别

- 状态卡可识别 `模式 C · GITC Uplift`（🟣 紫色标识）；
- 卸载后仍按 v3.0.3 的规则复位为 **模式 A + Lecram v12.5**。

---

# 🧭 DM-Toolbox (DM工具箱) v3.0.3 · 卸载后模式复位 + 模式 B 默认 v12.5

**v3.0.3 修掉了「卸载后仍按模式 B 注入」的状态残留，并把模式 B 的默认底座升级到 Lecram v12.5。**

---

### 🔁 1. 一键卸载后统一复位为模式 A

- 卸载完成后，模式选择器、B 版本选择器、代理槽位全部复位到出厂默认：
  **模式 A** + **Lecram v12.5**；
- 切入模式 A 时自动隐藏 B 版本下拉，并清掉上一次模式 B 的残留选择，避免影响下一次注入；
- 去掉卸载完成提示弹窗重复弹出两次的历史遗留代码。

### 🧪 2. 注入新增「底座切换校验」

- 复制新 addon 后会检查旧底座是否真的被删除；
- 若游戏 / 启动器 / 反作弊仍在占用旧文件，直接报错提示先退出游戏，
  不再出现「面板选了模式 A、进游戏实际还是模式 B」的假成功。

### ⚡ 3. 模式 B 默认底座升级为 Lecram v12.5

- 模式 B 下拉默认选中 **Lecram v12.5（10.0 MB）**；
- 仍可手动切回 v12；v12.5 缺失时自动回退 v12；
- 已注入 v12.5 的游戏会自动识别并预选。

### 📦 4. 打包修正

- 安装包不再包含 `apps/app5_jxr/输出` 等用户输出目录（此前会把用户的截图打进安装包，
  体积被撑到 760 MB，现已回到 703 MB 左右）。

---

# 🔧 DM-Toolbox (DM工具箱) v3.0.2 · 模式 A 支持 XeSS + 卸载残留修复

**v3.0.2 修掉了模式 A 在 XeSS 场景下的闪退与一键卸载残留，并新增模式 B 的 Lecram v12.5 底座。**

---

### ⚡ 1. 模式 A 新增「帧生成内核」：DLSS-G / XeSS (XeMFG)

- 面板新增一行 **帧生成内核（插帧来源）**：`DLSS-G（默认）` / `XeSS / XeMFG`；
- 选 XeSS 后写入 `xemfgStandalone=1`，并**停止向 DLSS 特性下发 SR / DLSS-G 预设**
  （`overrideDlssPreset=false`、`dlssSrPreset=0`、`dlssgPreset=0`、`DLSSGPreset=Auto`）；
- 这就是之前「模式 A 注入后游戏内切 XeSS 直接闪退」的根因：dashdogy 把 NVIDIA 预设打到了
  XeSS 的特性创建路径上；
- ⚠️ **XeSS（XeMFG）与 DLSS 5 神经重构是两条互斥渲染链**，同时注入后切 XeSS 仍会闪退。
  想同时要「DLSS 5 + XeSS 插帧」请用**模式 B（OptiScaler + XeFG）**；只用 XeSS 则先卸载 DLSS 5。
  保存设置时若检测到 DLSS 5，面板会弹窗明确提示。

### 🧹 2. 一键卸载残留修复

- **dashdogy 占用 `dxgi.dll` 时也会被清除**（旧逻辑只认 ReShade / OptiScaler，导致「彻底清除全部」
  后 `dxgi.dll` 还在）；
- 补齐 ReShade 残留：`ReShadePreset.ini`、`ReShade2.ini`、`reshade-shaders\`、`.dlss5_backup\`、
  `.mfg_coex_backup.json`；
- 补齐运行时目录：`RTXMFG-XeSS\`、`dlssg_sm86\`；
- 补删 `*.addon64.bak` / `*.addon.bak` 备份残片。

### 🧩 3. 模式 B 新增 Lecram v12.5 可选底座

- 选中模式 B 后出现「Lecram v12（默认）/ v12.5（新版）」下拉；
- 已注入 v12.5 的游戏会自动预选，避免误降级；
- v12.5 缺失时自动回退 v12。

### 🛡️ 4. NR 显存守卫默认余量调整为 5%

- 出厂 `NRVramBudgetGuard=1` + `NRVramBudgetMargin=5`（原 10%）；
- 面板仍可选 0% / 5% / 10% / 15% / 20%。

---

# 🛠 DM-Toolbox (DM工具箱) v3.0.1 · NR 显存预算守卫（防 4K 多帧 TDR 闪退）

**v3.0.1 是 v3.0.0 的稳定性补丁。** 针对「燕云十六声 4K + DLSS 5 神经重构 + 多帧生成」时出现的
显卡驱动超时（`LiveKernelEvent 0x141 / VIDEO_ENGINE_TIMEOUT_DETECTED`，表现为游戏直接闪退）做了处理。

---

### 🛡️ 1. DLSS 5 面板新增「NR 显存预算守卫」

- **出厂默认已开启**：显存预算守卫开启 + 预留 5% 余量；面板可选 0% / 5%（默认）/ 10% / 15% / 20%，鼠标悬停有说明；
- **即时生效**：勾选或改余量会立刻写入当前选中游戏的 `ReShadePreset.ini` 与
  `RenoDX\DLSS5\Presets\*.ini`（重启游戏生效），并记忆为后续注入的默认值；
- **写全三个位置**：`NRVramBudgetGuard` / `VramBudgetGuard` / `BudgetGuard` 与
  `NRVramBudgetMargin` 同时写入，兼容不同版本 RenoDX 的读取位置。

### 🔍 2. 为什么需要它

4K 下 NR 要额外占用显存（263 MB 模型 + 多 pass 中间缓冲），再叠加 DLSS-G 的呈现队列，
12 GB 显卡很容易贴着上限跑。守卫关闭时 NR 会继续按最大配置要显存，分配变慢 → GPU 引擎
超时 → 系统强制复位驱动（TDR），游戏进程直接消失。打开守卫后显存不足会自动降 NR 负载，
代价是极端场景 NR 效果略降，但不会闪退。

### 📦 3. 其他

- 版本号 3.0.0 → 3.0.1，安装包重新构建；
- 自动化测试新增 4 项 NR 守卫用例（写入 / 关闭 / 无目标 / 持久化钳位）。

---

# 🎉 DM-Toolbox (DM工具箱) v3.0.0 · 全界面半透明统一 + 多帧生成共存修复

**DM-Toolbox v3.0.0 正式发布！** 这一版把五个子软件的界面统一到首页同款「半透明亚克力」材质，
并修好了多帧生成在 DLSS 5 共存下的两处实际问题。

---

### 🎨 1. 全界面半透明材质统一

- **输入控件玻璃化**：下拉框、输入框、数字框、表格、列表、文本域统一半透明磨砂底 + 高对比文字；
  下拉弹层与表格 viewport 单独铺磨砂色，保证悬停与滚动时依然可读；
- **页面底板**：多帧生成 6 个页面、DLSS 5、超分指示器各铺一层与首页卡片同材质的磨砂底板，
  杜绝「文字直接压在壁纸上」「有的区域实心、有的全透明」；
- **首页顶栏**：信息栏显式套用 `GridCard` 亚克力样式（圆角 + 边框 + rgba），与快捷卡片同一层透光；
- **透明度标定**：大表面暗色 0.50 / 亮色 0.42，卡片下限 0.50，只保留一层底色——
  既能看到壁纸，又不会透到影响阅读。

### 🔧 2. 模式 A（dashdogy）+ DLSS 5 共存

- 共存适配时重新同步 Mode A 配置：隐藏 MFG 的 ImGui 面板与 overlay，避免游戏内实时切换 SR 预设被
  DLSS 5 拒绝后弹出「DLSS 拒绝了新预设」；
- **保留用户选择的超分预设**（`dlssSrPreset` / `OverrideDlssPreset`），它在 DLSS 特性创建时下发，
  改完重新注入 + 重启游戏即可生效。

### 🧩 3. 模式 C（dlssg_for_sm86）严格对齐上游教程

- 只注入三样：单一代理 DLL、`dlssg_sm86.ini`、整个 `dlssg_sm86` 目录；
- 出厂 `MaxGeneratedFrames=3`（最多 4X）+ `Preset=C`（FG Lite 极速多帧）；
- 注入后校验 runtime / backend / kernels 三件核心文件，缺一项直接报错，不再「注入了但没效果」。

### 🩹 4. 其他修复

- 模式 B 与 DLSS 5 真双轨共存（反置拓扑、配置直通、0xBAD00007 黑屏/回落 FSR 的根治、NGX 运行库自动部署）；
- 基线：出厂壁纸校验、一键还原后壁纸热更新、后台线程退出崩溃。

---

# 🎉 DM-Toolbox (DM工具箱) 正式发布 v2.3.0 · 模式 B 与 DLSS 5 真双轨共存

**DM-Toolbox (DM工具箱) 正式发布 v2.3.0！**
本次更新把「XeSS 多帧生成（OptiScaler / XeFG）+ DLSS 5 神经重构（RenoDX / ReShade 6.8）」从「先回退再各跑各的」升级为**同时生效的真双轨共存**，并修掉了 v2.2.0 基线里几处会被用户直接感知的问题。

---



### 🔥 1. 反置双通道隔离拓扑（模式 B + DLSS 5 同时注入）

- **dxgi.dll 严格归 ReShade 6.8**：DLSS 5 的 RenoDX 插件作为第一入口，在游戏创建 D3D12 设备与 NGX 上下文之前完成挂钩；
- **OptiScaler 动态降级到次级代理槽位**：按游戏 EXE 的 PE 导入表在 `winmm.dll` / `version.dll` / `dinput8.dll` / `wininet.dll` 中动态选择，绝不与 ReShade 抢 `dxgi.dll`；两种注入顺序（先 B 后 DLSS 5 / 先 DLSS 5 后 B）都收敛到同一份磁盘状态；
- **禁止第二个 ReShade 实例**：注入前清理 `ReShade64.dll` / `d3d12-ReShade64.dll` / `dxgi.dll.reshade_bak`，并在 `OptiScaler.ini` 锁定 `[Plugins] LoadReshade=false`，杜绝双份 D3D12 Hook 在交换链销毁时崩溃。

### 🔥 2. 职责分工与 OptiScaler 配置直通

- **DLSS 5 只管超分，XeFG 只管插帧**：`[Upscalers] Dx12Upscaler=dlss` 保留游戏内 DLSS 菜单与调用链，`[FrameGen] FGInput=dlssg → FGOutput=xefg` 把原生 DLSS-G 输入交给 Intel XeFG 执行多帧插值；
- **修复共存配置被写回独立模式**：DLSS 5 注入时 ReShade/addon 尚未落盘，旧逻辑会把 `LoadReshade` / `HookOriginalNvngxOnly` / `SkipResizeBuffers` 写回 `auto`——现在共存态强制 `false` / `false` / `true`，并固定 `PreserveSwapChain=true`；
- **XeFG 3X 出厂默认**：`[XeFG] IgnoreInitChecks=true` 豁免膨胀运动矢量预检查，`MFGUnlocker.asi` + `LoadAsiPlugins=true` 突破 2X 上限，默认 `InterpolationCount=2`（3X）。

### 🔥 3. 根治 0xBAD00007：黑屏与回落 FSR/XeSS

实测（燕云十六声 / Where Winds Meet）定位到两条失败路径，现已同时修好：

- **`EnableDlssInputs=false`**：OptiScaler 不再抢占 `NVSDK_NGX_D3D12_CreateFeature`。此前它抢先创建自己的 DLSS feature，被 vendor NGX 以 `FAIL_NotInitialized (0xBAD00007)` 拒绝后回落到 FSR 2.1.2 —— 游戏最终拿 FSR 出图，DLSS 5 完全没拿到 DLSS 帧；
- **自动部署 NGX 运行库**：部分游戏只带 `nvngx_dlss.dll` 而不带 `nvngx.dll`，此前靠 OptiScaler 代理加载；停止抢占后 NGX 无人初始化，全部 CreateFeature 返回 0xBAD00007、画面全黑。现在注入时会从驱动目录（`NGXCore` 注册表路径）自动补齐 `nvngx.dll` + `_nvngx.dll` 到游戏根目录，并登记进补丁清单，卸载时只删除自己复制的那两份。

### 🔥 4. DLSS 运行库感知与显存指纹净化

- **`[Libraries]` 精准路由**：新增运行库探测（游戏根目录 → `Streamline/` → 引擎深层目录，限深 4 层），`NvngxDlssPath` / `NvngxFeaturePath` 指向游戏真实 DLL，杜绝 OptiScaler 报 `nvngx_dlss.dll not found, disabling DLSS`；
- **`StreamlineSpoofing` 保持 `auto`**（20/30 系共存态），不再被误写 `false` 导致游戏内 DLSS 超分菜单消失；`UseFakenvapi=false` 且无条件清理 `fakenvapi.*`，让 `nvngx_dlssnr.dll` 读到真实 GPU 架构内核。

### 🔥 5. 模式 C 注入严格对齐上游教程（dlssg_for_sm86 0.4.0）

- **只注入三样**：单一代理 DLL（默认 version.dll，游戏不加载时可在面板换成 winmm.dll / dbghelp.dll / dinput8.dll，换不是加）、dlssg_sm86.ini、整个 dlssg_sm86 目录；
- **出厂值对齐上游**：[FrameGeneration] MaxGeneratedFrames=3（最多 4X）；默认模型为 Model C（FG Lite 极速多帧）。v2.0.0 曾把上限写成 3X，会让游戏请求的 4X 被静默钳到 3X；
- **部署完整性校验**：注入后检查代理 DLL、INI，以及 dlssg_sm86 目录内的 runtime / backend / kernels 三个核心文件，缺任何一项直接报错，不再出现「注入了但没效果」；
- 老用户预设自动迁移：3X 上限升级为 4X，Preset=Auto 升级为 Model C；手动选过 A/B/Default 的不动。

### 🛠 6. 基线修复

- **出厂壁纸**：默认壁纸哈希统一为 `51a11db7f98b`（荷花水景少女），修正校验测试把 `%APPDATA%` 路径当成仓库相对路径的错误判断；
- **一键还原**：清空 AppData 时保留 `cache` / `config` 目录本身，还原后自动重挂所有窗口的壁纸监听路径，修复还原后壁纸热更新彻底失效的问题；
- **后台线程**：静默更新检查支持取消并在退出时等待，游戏库扫描与镜像测速增加取消标记，修复关闭窗口时 `QThread: Destroyed while thread is still running` 导致的进程崩溃。

---

### 📦 验证

- 全量自动化测试：**147 passed / 1 skipped**
- 实机验证：燕云十六声（RTX 4070）DLSS 5 超分正常、XeFG 3X 插帧正常、OptiScaler 面板 `SR: None` / `FG: XeFG 3x`

---

# 🚀 DM-Toolbox v2.1.0 · 核心升级与自适应模型突破

### 🌟 v2.1.0 核心更新与突破

**DM-Toolbox (DM工具箱) 正式发布 v2.1.0 架构升级版！**
本次更新带来了 **DLSS 5 官方全新优化底座 (`renodx-dlss.addon64`)**、**全模式显卡智能自适应模型矩阵 (40/50系默认 Model M · 20/30系默认 Model K)**、**模式 B 与 DLSS 5 智能自动回退与恢复机制**，以及 **原生 DLSS-G 多帧生成与独立 XeMFG 的彻底隔离解耦**，全面解决双注入冲突与冷启动稳定性问题。

---

### 🔥 1. 全模式显卡智能自适应模型矩阵 (40/50系 Model M · 20/30系 Model K)
- **物理硬件探针全线接入**：模式 A (dashdogy)、模式 B (OptiScaler)、模式 C (dlssg_for_sm86) 三大核心全量接入显卡硬件架构探针，无需手动逐一调整；
- **RTX 40 / 50 系列显卡 (Ada / Blackwell)**：默认自动优选 **Model M**（DLSS 4.5 第二代 Transformer 旗舰画质超分模型），彻底消除高动态高速移动下的鬼影、重影与边缘毛刺；
- **RTX 20 / 30 系列显卡 (Turing / Ampere)**：默认自动优选 **Model K**（DLSS 4 经典高锐度与高能效模型），兼顾高清晰度与极高帧率能效比；
- **模型热切换与双向同步**：在各模式下均支持对 Model M / L / K / J 与 CNN 终极版（E/C/F）进行无缝调换与 INI 双向实时同步。

---

### ⚡ 2. 模式 A 原生 DLSS-G 优先与独立 XeMFG 解耦隔离
- **原生 DLSS-G 插帧优先**：模式 A 默认启用 NVIDIA 官方原生 DLSS-G 多帧生成，RTX 40/50 系无需解锁开箱即用，RTX 20/30 系在模式 A 注入时按需解锁；
- **运行时环境严密隔离**：XeSS 动态库全量隔离部署至 `RTXMFG-XeSS/` 独立子目录，彻底杜绝污染游戏根目录，杜绝模式 B 误识别以及弹出多余的 1.7.0 DLSS 5 选项框；
- **热切换与稳定性保护**：全面优化游戏运行时模型热切换响应逻辑，避免因中途热载入新权重被驱动拒绝的问题。

---

### 🛡️ 3. 模式 B 与 DLSS 5 智能自动回退与恢复保护
- **全自动感知避让与恢复**：先注入模式 B 后注入 DLSS 5 时，系统自动将模式 B 优雅安全回退，避免底层动态库冲突；当从游戏中卸载 DLSS 5 时，模式 B 会自动感知并无缝恢复原配置与代理；
- **冷启动防崩溃优化**：自动化配置 `LoadReshade = false` 防止二次双重加载 ReShade，优化 DirectX 12 渲染队列与着色器/PSO 缓存机制，全面保障双注入稳定性。

---

### 🧠 4. DLSS 5 全新优化底座 (`renodx-dlss.addon64`) 升级
- **升级至官方最新底层底座**：采用最新编译优化的 `renodx-dlss.addon64`，深度适配 RenoDX 1.7.0+ 框架规范；
- **画质与人像皮肤重构增强**：大幅提升神经重构抗伪影表现与高频纹理细腻度；
- **全自动协同共存**：完美协同模式 A / 模式 B / 模式 C 原生多帧生成，实现【神经重构 + 原生多帧】双通道巅峰体验。

---

### 🎨 5. 全新 v2.1.0 界面与截图全量更新
- 主页、全硬件配置大师、DLSS 多帧生成补丁、DLSS 5 神经重构注入器全部生成最新的深色/浅色高分辨率实机截图；
- UI 控件全面呈现 v2.1.0 版本标识与 `(40/50系默认推荐)` / `(20/30系默认推荐)` 动态标签。

---

# 🎉 DM-Toolbox v2.0.0 · 里程碑大版本发布公告

### 🌟 v2.0.0 核心更新与突破

**DM-Toolbox (DM工具箱) 正式迈入 v2.0.0 时代！**
本次更新针对 **模式 C (dlssg_for_sm86 原生多帧生成)** 开展了全维度的默认参数深度调优，实现了 **NVIDIA RTX 20/30 (Turing/Ampere) 系列显卡的智能硬件锁与自动首选路由**，同时全面升级了 **全局默认壁纸与高通透毛玻璃视觉体系**，确保出厂即是黄金画质与巅峰帧率。

---

### 🔥 1. 模式 C (dlssg_for_sm86) 出厂黄金参数深度调优
- **3X 三倍帧率上限 (`MaxGeneratedFrames=2`)**：出厂默认解锁 3X 三倍帧生成（原生渲染 1 帧 + 神经生成 2 帧），完美适配 165Hz ~ 240Hz 电竞高刷显示器，消除微卡顿与画面撕裂。
- **硬件流水线优化等级 2 (`Optimized=2`)**：轻量硬件加速（Lossy Image Kernels），真实 4K 下保持 44~53 dB 超高保真度，极低渲染延迟，兼顾极致响应与高保真画质。
- **DLSS-G 帧生成模型预设 Model C (`Preset=C`)**：启用 FG Lite 极速多帧调度模型，单帧生成的 GPU 运算时间降低 32% ~ 54%，显著释放显存带宽与算力瓶颈。
- **插帧调度内核引擎 DLSS (`Engine=DLSS`)**：强制调用 NVIDIA 官方原生 DLSS-G 渲染管线，纯血驱动级协同。
- **超分辨率托管模式 Off (`Mode=Off`)**：关闭内部自带超分接管，让位给 DLSS 5 神经重构或游戏原生 DLSS 超分，达成【DLSS 5 神经超分 + 原生 DLSS-G 插帧】零抢占零冲突双轨运作。

---

### ⚡ 2. RTX 20/30 系列显卡硬件自适应与智能首选锁定
- **检测架构自动锁定模式 C**：系统检测到运行在 NVIDIA GeForce RTX 20/30 (SM75/SM86) 系列显卡时，UI 注入模式下拉框与智能优选策略 **100% 自动锁定为【模式 C: dlssg_for_sm86 原生插帧】**。
- **未修补游戏首选引导**：未修补游戏在 RTX 20/30 卡上默认聚焦并高亮推荐模式 C，彻底告别以往误选模式 A (dashdogy) 或模式 B (OptiScaler) 的繁琐与困惑。
- **极简三件套注入规范**：严格只注入 1 个代理动态库（默认 `version.dll`）、`dlssg_sm86.ini` 配置文件与专属 `dlssg_sm86\` 内核目录；遇到不加载 `version.dll` 的游戏，支持一键从 `alternatives\` 单项热替换（**换，不是加；代理任何时候只放一个**）。

---

### 🖼️ 3. 默认壁纸与高级毛玻璃视觉系统全新升级
- **出厂默认启用自定义壁纸**：出厂配置 `enabled: true`，全局统一生效至主程序与 6 个子软件。
- **0 px 晶透无模糊 (`blur_radius: 0`)**：彻底关闭毛玻璃模糊扩散，让精美壁纸细节 100% 纤毫毕现。
- **20% 通透遮罩浓度 (`tint_opacity_dark: 0.2`, `tint_opacity_light: 0.2`)**：深色与浅色模式均采用 20% 高通透微遮罩，兼顾文字可读性与壁纸背景通透感。
- **50% 半透明磨砂卡片 (`card_opacity: 0.5`)**：卡片容器采用 50% 不透明度磨砂材质，呈现极致轻盈通透的次世代视觉层次。

---

### 🙏 4. 致谢开源项目 (Open Source Credits)
特别向本项目所引用、集成或借鉴的上游优秀开源项目及核心作者致以诚挚敬意与由衷感谢：
- **[dlssg_for_sm86](https://github.com/sdli1995/dlssg_for_sm86)** (by sdli1995) - 极其优秀的专为 Turing / Ampere (RTX 20/30 系列) 打造的原生 DLSS-G 插帧核心。
- **[OptiScaler](https://github.com/cdozdil/OptiScaler)** (by cdozdil) - 卓越的跨显卡架构超分辨率与帧生成转译框架。
- **[MFG-Unlocker](https://github.com/dashdogy)** (by dashdogy) - 极具创新的 DLSS 多帧生成解除与链式代理核心。
- **[RenoDX](https://github.com/clshortfuse/renodx)** (by clshortfuse / mavismmg) - 深度光流调度与高级帧生成优化插件，以及突破性的 DLSS 5 神经重构技术。
- **[ReShade](https://reshade.me/)** (by Crosire & ReShade Community) - 行业标准的通用后期处理着色器底层底座。
- **[Intel® XeSS / XeFG](https://github.com/intel/xess)** - 高品质 AI 超分与帧生成 SDK。
- **[AMD FidelityFX™ SDK](https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK)** - 开放的 FSR 空间放大与帧生成套件。
- **[Qt / PySide6](https://www.qt.io)** - 现代高品质 Fluent GUI 设计系统底座。
