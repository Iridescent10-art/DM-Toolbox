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
