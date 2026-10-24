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
