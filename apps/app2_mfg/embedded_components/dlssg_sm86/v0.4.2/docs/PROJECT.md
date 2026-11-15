# DLSSG for SM86 项目说明

Windows x64 / D3D12 上让 DLSS 帧生成（DLSS-G）在 RTX 30（SM86）与 RTX 20（SM75）上运行：代理 DLL 拦截游戏对 `nvngx_dlssg.dll` 的请求，交给随包的、未经修改的 NVIDIA 运行库 310.9.16.0（2026-10-14 起的默认模型；`-RuntimeModel 310.9` 的包是 310.9.1.0），再由后端 `sm86_backend.dll` 把运行库里只为 Ada / Blackwell 编译的内核换成内核包 `fg_kernels.dll` 里的 SM86 / SM75 版本。默认 `[Runtime] Mode=Bundled`：游戏自带的 DLSS-G 版本不参与。两个运行库模型：默认 310.9.16，备选 310.9（都到 6X）；310.1 模型已于 2026-10-05 退役。不支持 AMD 显卡。

本文说明项目构成与从源码构建；面向用户的安装与使用见发布包根目录的 `README.md` 与 [`INSTALL.md`](INSTALL.md)，实现分工见 [`ARCHITECTURE.md`](ARCHITECTURE.md)。

## 发布包里有什么

| 文件 | 内容 |
|---|---|
| `version.dll` | 代理（只有加载器）：根目录唯一的钩子 DLL，用户只放这一个 |
| `alternatives/{winmm,dbghelp,dinput8,dxgi,d3d12}.dll` | 备用代理：游戏不加载 `version.dll` 时按 winmm → dbghelp → dinput8 → dxgi / d3d12 的顺序一次换一个（dxgi / d3d12 在渲染热路径上、加载顺序敏感，最后才用、不要同时放），见 `alternatives/README.md` |
| `dlssg_sm86.ini` | 用户配置（出厂键见 [`INSTALL.md`](INSTALL.md)） |
| `dlssg_sm86/backend/sm86_backend.dll` | 后端：NGX 钩子与分发、内核路由与融合、超分路线、抓取与诊断；不含任何内核镜像 |
| `dlssg_sm86/kernels/fg_kernels.dll` | 帧生成内核包：全部内核镜像（SM86 / SM75 两族）与清单，必需 |
| `dlssg_sm86/runtime/nvngx_dlssg.dll` | NVIDIA DLSS-G 运行库 310.9.16.0，原样（310.9 模型的包是 310.9.1.0） |
| `dlssg_sm86/sr/nvngx_dlss.dll`、`dlssg_sm86/sr/sr_kernels.dll` | 超分 snippet 310.9.16.0（原样）与 RTX 30 / 20 的 INT8 内核包，成对，只在 `[SuperResolution] Mode` 不是 `Off` 时用到 |
| `dlssg_sm86/xefg/xefg_kernels.dll` | XeSS-FG 模型包（`Engine=XeSS` 用） |
| `manifest.json` / `validation.json` | 每个文件的大小与 SHA-256、构建检查结果 / GPU 验证状态 |
| `README.md`、`README.en.md`、`MANUAL.html`、`MANUAL.en.html`、`LICENSE.md`、`THIRD_PARTY_NOTICES.txt`、`docs/` | 说明、安装手册、许可与第三方声明 |

## 源码仓库

C++ 源码以 MIT 许可发布（`LICENSE.md`）。仓库里没有任何 NVIDIA 文件，也没有内核：NVIDIA 运行库、超分的 snippet、帧生成内核包与超分的内核集都只以二进制随发布包提供，生成内核的工具链不公开。

```text
dlssg/
  build.cmd / build.ps1     自动发现工具链，配置、构建、跑 CTest、安装、打包
  CMakeLists.txt            CMake 入口：运行库模型表（310.9.16 默认、310.9 两行）、目标、测试
  cmake/                    BuildIdentity（运行库哈希闸门）、Package（发布清单与 zip）、SmallStack（测试夹具）
  config/                   出厂 INI
  src/                      按编进哪个二进制分目录
    proxy/                  代理：导出转发、DLSS-G 加载拦截、INI、运行库选择；generated/<name>/ 是生成的导出表
    common/                 代理与后端共用的头（加载器与后端的 ABI、档位、超分选项与设备闸）
    backend/                后端：ngx/（NGX 核心钩子与分发）、diag/（抓取、探针、帧标记）、fg/（内核路由）、
                            runtimes/310_9_x/（运行库 profile 与钩子）、snippet/（超分路线）
    pack/                   内核包与内核集的读取器
  third_party/              Detours、JSON for Modern C++、d3dx12.h（MIT）
  tests/
    native/                 无 GPU 的 CTest，以及 GPU 工具（sm86_scene、sm86_bench、sm86_replay、capability_probe 等）
    python/                 GPU 验证驱动（能力、加载、内核选择）
    golden/                 归一化日志基线与对外表面 surface.json
  scripts/
    generate_proxy.py       从 System32 的导出表生成代理的转发表
    analysis/               日志归一化与比较、对外表面快照、运行库 profile 推导、RTX 20 日志分诊
    game/                   dlssg_diag.ps1（给测试者的一键诊断）与开发用的部署 / 监视脚本
    perf/                   GPU 驱动脚本：check_scene、run_bench、replay_check、group_bench 等
  docs/                     安装、架构、兼容性账本、内核包格式、抓取、超分、光线重建（2026-10-09 删除，只剩说明）、验证记录
  out/                      构建树（不入库）
  dist/                     安装树与发布包（不入库）
```

## 一键构建

安装 Visual Studio 2022 或 2026 的“使用 C++ 的桌面开发”（含 Windows SDK 与 CMake），从同一版本的发布包取出运行库与内核包，然后在本目录执行：

```powershell
.\build.cmd -Runtime310916 <发布包>\dlssg_sm86\runtime\nvngx_dlssg.dll `
            -KernelPack <发布包>\dlssg_sm86\kernels\fg_kernels.dll
```

也可以直接运行 `build.ps1`。脚本自动发现 Visual Studio、配套 CMake 与 MSVC x64 工具链，依次配置、构建、跑 CTest（不给运行库时只注册不需要它的那部分，全部不需要 GPU）、安装、打包。不需要 Python、CUDA Toolkit 或显卡。运行库按 SHA-256 认，必须是 310.9.16.0 那一份（`-RuntimeModel 310.9` 时用 `-Runtime3109` 给 310.9.1.0）；内核包按清单的 `model` 与 `fusion_abi` 认，别的版本的包会被后端整包拒用。不给内核包也能构建与测试，只是打包那一步会报缺 `fg_kernels.dll`；配置时一行 `DLSSG tests not registered ...` 写明哪些内核侧测试因为输入不在仓库里而没有注册。

| 输出 | 内容 |
|---|---|
| `out/build-310.9.16/`（备选 `out/build-310.9/`） | 构建树；其中 `bundle/<配置>/` 就是发布树 |
| `dist/Release-310.9.16/`（备选 `dist/Release-310.9/`） | 安装树，即上一节的发布包内容 |
| `dist/dlssg-release-<版本>-x64.zip`（310.9.16，默认；`-RuntimeModel 310.9` 是 `…-x64-310.9.zip`；运行库模型见包内 `manifest.json` 的 `runtime_model`） | 部署包 |
| `dist/dlssg-release-<版本>-x64.zip.sha256` | 部署包校验值 |

默认构建只记录基础检查通过，`validation.json` 的 GPU 状态为 `performed: false`。

## 选择 PTX / cubin

在 `dlssg_sm86.ini` 中设置：

```ini
[Compatibility]
KernelImage=PTX
ForceSM86Route=0
SimulateAmpere=0
```

这会让 RTX 30 等真实 SM86 显卡使用 PTX JIT。默认 `Auto` 在 SM86 上使用预编译 cubin；`Cubin` 显式要求使用 SM86 cubin。此项不单独强制开启其他架构的 SM86 路由，修改后重启游戏。完整行为和日志字段见 [安装说明](INSTALL.md)。

## 构建选项

```powershell
.\build.cmd -BuildDirectory "out\custom build"
.\build.cmd -Configuration RelWithDebInfo
.\build.cmd -CMake "C:\path\to\cmake.exe" -Generator "Visual Studio 17 2022"
.\build.cmd -SignCert <证书.pfx> -SignPass <密码>
```

相对 `BuildDirectory` 以本项目为基准，脚本可以从其他工作目录调用。CMake 使用 Visual Studio 的多配置生成器，支持 Release、Debug 和 RelWithDebInfo，产物分配置存放。直接用 CMake 时对应的缓存变量是 `DLSSG_RUNTIME_MODEL`（`310.9.16`，默认；或 `310.9`）、`DLSSG_RUNTIME_310916`、`DLSSG_RUNTIME_3109`、`DLSSG_KERNEL_PACK`；`-DDLSSG_BUILD_GPU_TESTS=ON` 另外构建 GPU 工具，由 `tests/python/` 与 `scripts/perf/` 的脚本驱动。代码签名见 [`SIGNING.md`](SIGNING.md)。

随包的运行库与后端成对：后端只钩它的 profile 认得的运行库（按 SHA-256），构建时运行库文件的哈希也必须等于模型表里的那个值，不符就在构建时拒绝。换运行库就是加一个运行库模型，要做的事见 [`ARCHITECTURE.md`](ARCHITECTURE.md)。
